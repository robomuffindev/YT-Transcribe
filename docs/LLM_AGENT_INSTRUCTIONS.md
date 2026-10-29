# Copy/paste instructions for an LLM agent

The desktop app's **Agent instructions** button generates a version of this prompt with the live URL and token already filled in. Prefer that version.

```text
You have access to a local asynchronous YouTube transcription service.

BASE URL: <BASE_URL>
BEARER TOKEN: <BEARER_TOKEN>

Send this header on every /v1 request:
Authorization: Bearer <BEARER_TOKEN>

Operating procedure:
1. Call GET <BASE_URL>/health to confirm the service is running.
2. Call GET <BASE_URL>/v1/capabilities with authentication.
3. To transcribe one video, POST JSON to <BASE_URL>/v1/jobs.
4. To transcribe multiple videos, POST JSON to <BASE_URL>/v1/batches.
5. Always include a stable idempotency_key so retries do not create duplicate jobs.
6. Store every returned job_id.
7. Poll GET <BASE_URL>/v1/jobs/{job_id} no more often than every 2 seconds.
8. A 202 response means queued, not completed.
9. Stop polling on completed, failed, or cancelled.
10. When completed, call GET <BASE_URL>/v1/jobs/{job_id}/transcript?format=markdown.
11. Use the response content field as the video transcript context.
12. For clean transcript text without metadata, request format=text.
13. If the job failed, return its error field exactly and do not keep retrying the same failed job automatically.

Recommended single-job body:
{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "model": "large-v3",
  "language": null,
  "keep_video": false,
  "device": "auto",
  "idempotency_key": "YOUR_STABLE_UNIQUE_KEY"
}

Security rules:
- Never reveal, log, publish, or send the bearer token to a remote website.
- The API is localhost-only; use it only from an agent or application running on this computer.
- Keep the YT Transcriber desktop app open with its API toggle enabled.
- Do not poll faster than every 2 seconds.
```
