# Local API reference

YT Transcriber's API lets a local agent or application submit YouTube transcription work, monitor the sequential queue, retrieve transcript content, and download generated files.

## Enable the API

1. Open YT Transcriber with `run.bat`.
2. Choose the output folder, model, and processing mode that API jobs should use by default.
3. Turn on **Enable localhost API**.
4. Select **Agent instructions** to copy the live base URL and bearer token.
5. Optionally select **API docs** for interactive Swagger documentation.

The API listens on `127.0.0.1:8765`. It is deliberately unavailable to other computers and the public internet. The desktop app must remain open and the toggle must remain enabled.

## Authentication

`GET /health` is unauthenticated. Every `/v1` endpoint requires:

```http
Authorization: Bearer YOUR_SESSION_TOKEN
```

The token is generated locally for the current app session. Do not publish it, place it in source control, send it to a remote service, or include it in logs. Restarting the app generates a new token.

## Agent workflow

1. Check `GET /health`.
2. Read `GET /v1/capabilities`.
3. Submit `POST /v1/jobs` or `POST /v1/batches`.
4. Store every returned `job_id`.
5. Poll `GET /v1/jobs/{job_id}` every two seconds or less frequently.
6. Stop polling when status becomes `completed`, `failed`, or `cancelled`.
7. For completed jobs, request `GET /v1/jobs/{job_id}/transcript?format=markdown`.
8. Use the returned `content` field as LLM context.

A `202 Accepted` response means the job entered the queue. It does not mean transcription has finished.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Check whether the local service is reachable |
| `GET` | `/v1/capabilities` | Discover models, devices, formats, defaults, and limits |
| `POST` | `/v1/jobs` | Submit one video |
| `POST` | `/v1/batches` | Submit up to 50 videos |
| `GET` | `/v1/jobs` | List recent jobs |
| `GET` | `/v1/jobs/{job_id}` | Read status, progress, errors, and result metadata |
| `GET` | `/v1/jobs/{job_id}/transcript` | Return transcript content as JSON |
| `GET` | `/v1/jobs/{job_id}/files/{kind}` | Download a generated transcript file |
| `GET` | `/openapi.json` | OpenAPI schema |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/redoc` | ReDoc documentation |

## Submit one job

```http
POST /v1/jobs
Authorization: Bearer YOUR_SESSION_TOKEN
Content-Type: application/json

{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "model": "large-v3",
  "language": null,
  "keep_video": false,
  "device": "auto",
  "idempotency_key": "research-video-2026-001"
}
```

All fields except `url` are optional. Omitting `model`, `language`, or `device` uses the corresponding selection from the desktop app when the API was enabled. Sending `"language": null` explicitly enables Whisper language detection. `keep_video` defaults to `false` for API jobs.

Example response:

```json
{
  "job_id": "7817fc64-1352-4a42-a188-8962e1222bdd",
  "status": "queued",
  "status_url": "http://127.0.0.1:8765/v1/jobs/7817fc64-1352-4a42-a188-8962e1222bdd",
  "transcript_url": "http://127.0.0.1:8765/v1/jobs/7817fc64-1352-4a42-a188-8962e1222bdd/transcript",
  "deduplicated": false
}
```

## Submit a batch

```json
{
  "urls": [
    "https://www.youtube.com/watch?v=VIDEO_ID_1",
    "https://www.youtube.com/watch?v=VIDEO_ID_2"
  ],
  "model": "large-v3",
  "language": null,
  "keep_video": false,
  "device": "auto",
  "idempotency_key": "research-batch-2026-001"
}
```

Duplicate URLs within one batch are removed. The maximum batch size is 50.

## Idempotency

Agents often retry after timeouts. Include a stable, caller-generated `idempotency_key` to prevent the same request from entering the queue twice during the current app session.

Reusing a key returns the original job and sets `deduplicated` to `true`. Batch keys are applied to each item by position. Idempotency state resets when the desktop app closes.

## Job states

| Status | Meaning |
| --- | --- |
| `queued` | Accepted and waiting for earlier jobs |
| `processing` | Downloading, loading a model, or transcribing |
| `completed` | Transcript and files are ready |
| `failed` | Processing stopped; inspect the `error` field |
| `cancelled` | The desktop user cancelled or removed the job |

`progress_percent` describes the current download or transcription stage; it is not an overall batch percentage.

## Transcript formats

Use the `format` query parameter or file `kind`:

| Format | Recommended use |
| --- | --- |
| `markdown` | Best default for LLM context; includes source metadata |
| `text` | Clean transcript only |
| `timestamped` | Readable timestamped transcript |
| `srt` | Subtitle/caption workflows |
| `json` | Structured metadata and timed segments |

Transcript-content response:

```json
{
  "job_id": "...",
  "title": "Video title",
  "source_url": "https://www.youtube.com/watch?v=...",
  "language": "en",
  "format": "markdown",
  "content": "# Video title\n\n..."
}
```

## cURL example

```bash
curl -X POST "http://127.0.0.1:8765/v1/jobs" \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtu.be/VIDEO_ID","device":"auto","idempotency_key":"demo-001"}'
```

## Python example

```python
import time
import requests

BASE_URL = "http://127.0.0.1:8765"
TOKEN = "YOUR_SESSION_TOKEN"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

response = requests.post(
    f"{BASE_URL}/v1/jobs",
    headers=HEADERS,
    json={
        "url": "https://youtu.be/VIDEO_ID",
        "device": "auto",
        "keep_video": False,
        "idempotency_key": "demo-001",
    },
    timeout=30,
)
response.raise_for_status()
job_id = response.json()["job_id"]

while True:
    job = requests.get(f"{BASE_URL}/v1/jobs/{job_id}", headers=HEADERS, timeout=30).json()
    if job["status"] == "completed":
        break
    if job["status"] in {"failed", "cancelled"}:
        raise RuntimeError(job.get("error") or job["status"])
    time.sleep(2)

transcript = requests.get(
    f"{BASE_URL}/v1/jobs/{job_id}/transcript",
    params={"format": "markdown"},
    headers=HEADERS,
    timeout=30,
).json()["content"]
print(transcript)
```

## Security model

- The server binds only to `127.0.0.1`.
- `/v1` endpoints require a high-entropy session bearer token.
- CORS is not enabled.
- API clients cannot choose an arbitrary output directory.
- API file downloads are limited to files created for completed jobs.
- API jobs use the same sequential processor as desktop jobs.
- Disabling the toggle stops new API access; already-started transcription work continues locally.

This is a local integration surface, not an internet-facing production service. Do not place it behind a public tunnel without adding network-level authentication, TLS, rate limiting, and an explicit threat review.

## Error handling guidance for agents

- Treat `401` as a missing, stale, or incorrect session token.
- Treat `409` from transcript endpoints as “job not finished”; continue status polling.
- Treat `422` as invalid request data and correct the request rather than retrying unchanged.
- Treat a job `failed` status as terminal. Return its `error` field to the user.
- Use exponential backoff for transient connection failures, but reuse the same `idempotency_key`.
