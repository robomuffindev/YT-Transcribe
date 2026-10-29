from __future__ import annotations

import hmac
import logging
import secrets
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
import uvicorn

from . import __version__
from .core import JobResult, is_youtube_url


logger = logging.getLogger(__name__)

ModelName = Literal["tiny", "base", "small", "medium", "large-v3"]
DeviceName = Literal["auto", "cuda", "cpu"]
TranscriptFormat = Literal["text", "markdown", "timestamped", "srt", "json"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobRequest(BaseModel):
    url: str = Field(description="A youtube.com or youtu.be video URL")
    model: ModelName | None = Field(default=None, description="Defaults to the model selected when the API was enabled")
    language: str | None = Field(default=None, min_length=2, max_length=12, description="Whisper language code, or null for auto-detection")
    keep_video: bool = Field(default=False, description="Keep merged video media in addition to transcript files")
    device: DeviceName | None = Field(default=None, description="Defaults to the processing mode selected when the API was enabled")
    idempotency_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=128,
        description="Optional caller-generated key that prevents duplicate submission during this app session",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip()
        if not is_youtube_url(value):
            raise ValueError("A valid youtube.com or youtu.be URL is required")
        return value


class BatchRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=50, description="One to fifty YouTube video URLs")
    model: ModelName | None = None
    language: str | None = Field(default=None, min_length=2, max_length=12)
    keep_video: bool = False
    device: DeviceName | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            value = value.strip()
            if not is_youtube_url(value):
                raise ValueError(f"Invalid YouTube URL: {value}")
            if value not in cleaned:
                cleaned.append(value)
        return cleaned


@dataclass
class ApiJob:
    id: str
    url: str
    settings: dict[str, Any]
    idempotency_key: str | None = None
    status: str = "queued"
    stage: str = "Waiting in the sequential queue"
    progress: float | None = None
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    completed_at: str | None = None
    result: JobResult | None = None


class ApiJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, ApiJob] = {}
        self._idempotency: dict[str, str] = {}
        self._lock = threading.RLock()

    def create(self, url: str, settings: dict[str, Any], idempotency_key: str | None = None) -> tuple[ApiJob, bool]:
        with self._lock:
            if idempotency_key and idempotency_key in self._idempotency:
                existing = self._jobs[self._idempotency[idempotency_key]]
                return existing, False
            job = ApiJob(
                id=str(uuid4()),
                url=url,
                settings=dict(settings),
                idempotency_key=idempotency_key,
            )
            self._jobs[job.id] = job
            if idempotency_key:
                self._idempotency[idempotency_key] = job.id
        return job, True

    def get(self, job_id: str) -> ApiJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[ApiJob]:
        with self._lock:
            return list(reversed(self._jobs.values()))

    def set_processing(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "processing"
                job.stage = "Starting"
                job.started_at = utc_now()

    def update_event(self, job_id: str, event: str, payload: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            if event == "stage":
                job.stage = str(payload.get("message") or "Processing")
            elif event == "download":
                job.stage = "Downloading media"
                percent = payload.get("percent")
                job.progress = round(float(percent), 2) if percent is not None else None
            elif event == "transcribe":
                job.stage = "Transcribing locally"
                percent = payload.get("percent")
                job.progress = round(float(percent), 2) if percent is not None else None

    def complete(self, job_id: str, result: JobResult) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "completed"
                job.stage = "Transcript ready"
                job.progress = 100.0
                job.completed_at = utc_now()
                job.result = result

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.stage = "Failed"
                job.error = error
                job.completed_at = utc_now()

    def cancel(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "cancelled"
                job.stage = "Cancelled"
                job.completed_at = utc_now()

    def public(self, job: ApiJob, base_url: str) -> dict[str, Any]:
        result = job.result
        data: dict[str, Any] = {
            "id": job.id,
            "url": job.url,
            "status": job.status,
            "stage": job.stage,
            "progress_percent": job.progress,
            "error": job.error,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "settings": {
                "model": job.settings.get("model_name"),
                "language": job.settings.get("language"),
                "keep_video": job.settings.get("keep_video"),
                "device": job.settings.get("device_preference"),
            },
            "idempotency_key": job.idempotency_key,
            "links": {
                "self": f"{base_url}/v1/jobs/{job.id}",
                "transcript": f"{base_url}/v1/jobs/{job.id}/transcript",
                "files": f"{base_url}/v1/jobs/{job.id}/files/{{kind}}",
            },
        }
        if result:
            data["result"] = {
                "title": result.title,
                "video_id": result.video_id,
                "source_url": result.source_url,
                "language": result.language,
                "language_probability": result.language_probability,
                "duration_seconds": result.duration_seconds,
                "device": result.device,
                "compute_type": result.compute_type,
                "available_formats": ["text", "markdown", "timestamped", "srt", "json"],
            }
        return data


class ApiServer:
    def __init__(
        self,
        *,
        on_enqueue: Callable[[list[dict[str, Any]]], None],
        default_settings: dict[str, Any],
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.token = secrets.token_urlsafe(32)
        self.on_enqueue = on_enqueue
        self.default_settings = dict(default_settings)
        self.store = ApiJobStore()
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._start_error: BaseException | None = None
        self.app = self._build_app()

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._server and self._server.started)

    def update_defaults(self, settings: dict[str, Any]) -> None:
        self.default_settings = dict(settings)

    def _authorize_value(self, authorization: str | None) -> None:
        expected = f"Bearer {self.token}"
        if not authorization or not hmac.compare_digest(authorization, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid bearer token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def _resolve_settings(
        self,
        *,
        model: str | None,
        language: str | None,
        language_provided: bool,
        keep_video: bool,
        device: str | None,
    ) -> dict[str, Any]:
        return {
            "output_dir": self.default_settings["output_dir"],
            "model_name": model or self.default_settings["model_name"],
            "language": language if language_provided else self.default_settings.get("language"),
            "keep_video": keep_video,
            "device_preference": device or self.default_settings["device_preference"],
        }

    def _queued_response(self, job: ApiJob) -> dict[str, Any]:
        return {
            "job_id": job.id,
            "status": "queued",
            "status_url": f"{self.base_url}/v1/jobs/{job.id}",
            "transcript_url": f"{self.base_url}/v1/jobs/{job.id}/transcript",
        }

    def _require_job(self, job_id: str) -> ApiJob:
        job = self.store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    def _require_result(self, job_id: str) -> tuple[ApiJob, JobResult]:
        job = self._require_job(job_id)
        if job.status != "completed" or not job.result:
            raise HTTPException(status_code=409, detail=f"Transcript is not ready; current status is {job.status}")
        return job, job.result

    def _build_app(self) -> FastAPI:
        app = FastAPI(
            title="YT Transcriber Local API",
            version=__version__,
            description=(
                "Authenticated localhost API for asynchronous YouTube transcription. "
                "Submit jobs, poll status, retrieve transcript content, or download output files."
            ),
            docs_url="/docs",
            redoc_url="/redoc",
        )
        bearer = HTTPBearer(auto_error=False)

        async def authorize(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
            authorization = None
            if credentials:
                authorization = f"{credentials.scheme} {credentials.credentials}"
            self._authorize_value(authorization)

        auth = [Depends(authorize)]

        @app.get("/health", tags=["System"])
        async def health() -> dict[str, Any]:
            return {"status": "ok", "service": "yt-transcriber", "version": __version__, "api_version": "v1"}

        @app.get("/v1/capabilities", dependencies=auth, tags=["System"])
        async def capabilities() -> dict[str, Any]:
            return {
                "api_version": "v1",
                "asynchronous": True,
                "queue_mode": "sequential",
                "max_batch_size": 50,
                "models": ["tiny", "base", "small", "medium", "large-v3"],
                "devices": ["auto", "cuda", "cpu"],
                "transcript_formats": ["text", "markdown", "timestamped", "srt", "json"],
                "default_model": self.default_settings["model_name"],
                "default_device": self.default_settings["device_preference"],
                "authentication": "Bearer token",
            }

        @app.post("/v1/jobs", status_code=202, dependencies=auth, tags=["Jobs"])
        async def create_job(request: JobRequest) -> dict[str, Any]:
            settings = self._resolve_settings(
                model=request.model,
                language=request.language,
                language_provided="language" in request.model_fields_set,
                keep_video=request.keep_video,
                device=request.device,
            )
            job, created = self.store.create(request.url, settings, request.idempotency_key)
            if created:
                self.on_enqueue([{"job_id": job.id, "url": job.url, "settings": settings}])
                logger.info("API job accepted: %s", job.id)
            response = self._queued_response(job)
            response["deduplicated"] = not created
            return response

        @app.post("/v1/batches", status_code=202, dependencies=auth, tags=["Jobs"])
        async def create_batch(request: BatchRequest) -> dict[str, Any]:
            queued: list[dict[str, Any]] = []
            jobs: list[ApiJob] = []
            deduplicated = 0
            for index, url in enumerate(request.urls):
                settings = self._resolve_settings(
                    model=request.model,
                    language=request.language,
                    language_provided="language" in request.model_fields_set,
                    keep_video=request.keep_video,
                    device=request.device,
                )
                item_key = f"{request.idempotency_key}:{index}" if request.idempotency_key else None
                job, created = self.store.create(url, settings, item_key)
                jobs.append(job)
                if created:
                    queued.append({"job_id": job.id, "url": job.url, "settings": settings})
                else:
                    deduplicated += 1
            if queued:
                self.on_enqueue(queued)
            logger.info("API batch accepted: %s jobs (%s deduplicated)", len(jobs), deduplicated)
            return {
                "jobs": [self._queued_response(job) for job in jobs],
                "count": len(jobs),
                "deduplicated": deduplicated,
            }

        @app.get("/v1/jobs", dependencies=auth, tags=["Jobs"])
        async def list_jobs(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
            jobs = self.store.list()[:limit]
            return {"jobs": [self.store.public(job, self.base_url) for job in jobs], "count": len(jobs)}

        @app.get("/v1/jobs/{job_id}", dependencies=auth, tags=["Jobs"])
        async def get_job(job_id: str) -> dict[str, Any]:
            return self.store.public(self._require_job(job_id), self.base_url)

        @app.get("/v1/jobs/{job_id}/transcript", dependencies=auth, tags=["Transcripts"])
        async def get_transcript(job_id: str, format: TranscriptFormat = "markdown") -> dict[str, Any]:
            job, result = self._require_result(job_id)
            paths = {
                "text": result.transcript_path,
                "markdown": result.ai_ready_path,
                "timestamped": result.timestamped_path,
                "srt": result.srt_path,
                "json": result.json_path,
            }
            path = Path(paths[format])
            if not path.exists():
                raise HTTPException(status_code=404, detail=f"{format} transcript file is missing")
            return {
                "job_id": job.id,
                "title": result.title,
                "source_url": result.source_url,
                "language": result.language,
                "format": format,
                "content": path.read_text(encoding="utf-8"),
            }

        @app.get("/v1/jobs/{job_id}/files/{kind}", dependencies=auth, tags=["Transcripts"])
        async def download_file(job_id: str, kind: TranscriptFormat) -> FileResponse:
            _, result = self._require_result(job_id)
            paths = {
                "text": result.transcript_path,
                "markdown": result.ai_ready_path,
                "timestamped": result.timestamped_path,
                "srt": result.srt_path,
                "json": result.json_path,
            }
            path = Path(paths[kind])
            if not path.exists():
                raise HTTPException(status_code=404, detail=f"{kind} transcript file is missing")
            media_types = {
                "text": "text/plain",
                "markdown": "text/markdown",
                "timestamped": "text/plain",
                "srt": "application/x-subrip",
                "json": "application/json",
            }
            return FileResponse(path, filename=path.name, media_type=media_types[kind])

        return app

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind((self.host, self.port))
            except OSError as exc:
                raise RuntimeError(f"Local API port {self.port} is already in use") from exc
        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
            log_config=None,
        )
        self._server = uvicorn.Server(config)
        self._start_error = None

        def serve() -> None:
            try:
                assert self._server is not None
                self._server.run()
            except BaseException as exc:
                self._start_error = exc
                logger.exception("Local API server thread failed")

        self._thread = threading.Thread(target=serve, name="yt-transcriber-api", daemon=True)
        self._thread.start()
        logger.info("Local API starting at %s", self.base_url)

    def wait_until_started(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.running:
                return True
            if self._thread and not self._thread.is_alive():
                return False
            time.sleep(0.05)
        return self.running

    def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("Local API stopped")

    def agent_instructions(self) -> str:
        return f"""YT Transcriber Local API — Agent Connection Instructions

Base URL: {self.base_url}
Bearer token: {self.token}
OpenAPI schema: {self.base_url}/openapi.json
Interactive docs: {self.base_url}/docs

AUTHENTICATION
Send this header on every /v1 request:
Authorization: Bearer {self.token}

RECOMMENDED AGENT WORKFLOW
1. Call GET /health without authentication to confirm the local service is running.
2. Call GET /v1/capabilities with the bearer token before submitting work.
3. Submit one video with POST /v1/jobs or several with POST /v1/batches.
4. Save each returned job_id and status_url.
5. Poll GET /v1/jobs/{{job_id}} no more often than every 2 seconds.
6. When status is completed, call GET /v1/jobs/{{job_id}}/transcript?format=markdown.
7. Use the returned content field as the transcript context. For a raw transcript use format=text.
8. If status is failed, report the error field exactly and do not keep polling.

SINGLE-JOB EXAMPLE
POST {self.base_url}/v1/jobs
Content-Type: application/json
Authorization: Bearer {self.token}

{{
  "url": "https://www.youtube.com/watch?v=VIDEO_ID",
  "model": "large-v3",
  "language": null,
  "keep_video": false,
  "device": "auto",
  "idempotency_key": "my-agent-video-001"
}}

BATCH EXAMPLE
POST {self.base_url}/v1/batches

{{
  "urls": [
    "https://www.youtube.com/watch?v=VIDEO_ID_1",
    "https://www.youtube.com/watch?v=VIDEO_ID_2"
  ],
  "model": "large-v3",
  "language": null,
  "keep_video": false,
  "device": "auto",
  "idempotency_key": "my-agent-batch-001"
}}

TRANSCRIPT FORMATS
markdown (recommended for LLM context), text, timestamped, srt, json

IMPORTANT RULES
- This is an asynchronous sequential queue; a 202 response means accepted, not completed.
- Include a unique idempotency_key when your agent may retry requests.
- Do not poll more often than every 2 seconds.
- Never send the bearer token to a remote website or include it in public logs.
- The API listens on localhost only. The agent or application must run on this computer.
- Keep the desktop app open and leave the API toggle enabled while jobs are running.
"""
