from pathlib import Path

import pytest
from pydantic import ValidationError

from yt_transcriber.api import ApiServer, BatchRequest, JobRequest
from yt_transcriber.core import JobResult


def make_server(tmp_path: Path) -> tuple[ApiServer, list[dict]]:
    queued: list[dict] = []
    server = ApiServer(
        on_enqueue=lambda jobs: queued.extend(jobs),
        default_settings={
            "output_dir": str(tmp_path),
            "model_name": "small",
            "language": None,
            "keep_video": False,
            "device_preference": "auto",
        },
        port=18765,
    )
    return server, queued


def test_request_validation() -> None:
    request = JobRequest(url="https://youtu.be/abc123", model="small")
    assert request.url == "https://youtu.be/abc123"
    batch = BatchRequest(urls=["https://youtu.be/one", "https://youtu.be/one", "https://youtu.be/two"])
    assert batch.urls == ["https://youtu.be/one", "https://youtu.be/two"]
    with pytest.raises(ValidationError):
        JobRequest(url="https://example.com/not-youtube")


def test_openapi_contract(tmp_path) -> None:
    server, _ = make_server(tmp_path)
    schema = server.app.openapi()
    paths = schema["paths"]
    assert "/health" in paths
    assert "/v1/capabilities" in paths
    assert "/v1/jobs" in paths
    assert "/v1/batches" in paths
    assert "/v1/jobs/{job_id}/transcript" in paths
    assert "/v1/jobs/{job_id}/files/{kind}" in paths
    assert "HTTPBearer" in schema["components"]["securitySchemes"]


def test_job_store_completion_and_public_result(tmp_path) -> None:
    server, _ = make_server(tmp_path)
    settings = dict(server.default_settings)
    job, created = server.store.create("https://youtu.be/abc123", settings)
    assert created
    server.store.set_processing(job.id)
    server.store.update_event(job.id, "transcribe", {"percent": 42.5})
    current = server.store.get(job.id)
    assert current is not None
    assert current.status == "processing"
    assert current.progress == 42.5

    transcript = tmp_path / "transcript.txt"
    markdown = tmp_path / "AI-ready.md"
    timestamped = tmp_path / "timestamped.txt"
    srt = tmp_path / "captions.srt"
    metadata = tmp_path / "metadata.json"
    media = tmp_path / "audio.webm"
    for path in [transcript, markdown, timestamped, srt, metadata, media]:
        path.write_text("content", encoding="utf-8")
    result = JobResult(
        title="Example",
        video_id="abc123",
        source_url="https://youtu.be/abc123",
        language="en",
        language_probability=0.99,
        duration_seconds=60,
        device="cpu",
        compute_type="int8",
        media_path=str(media),
        transcript_path=str(transcript),
        timestamped_path=str(timestamped),
        ai_ready_path=str(markdown),
        srt_path=str(srt),
        json_path=str(metadata),
        text="Plain transcript",
    )
    server.store.complete(job.id, result)
    public = server.store.public(job, server.base_url)
    assert public["status"] == "completed"
    assert public["result"]["title"] == "Example"
    assert public["result"]["available_formats"] == ["text", "markdown", "timestamped", "srt", "json"]


def test_idempotency_key_reuses_existing_job(tmp_path) -> None:
    server, _ = make_server(tmp_path)
    settings = dict(server.default_settings)
    first, first_created = server.store.create("https://youtu.be/abc123", settings, "agent-request-1")
    second, second_created = server.store.create("https://youtu.be/abc123", settings, "agent-request-1")
    assert first_created
    assert not second_created
    assert first.id == second.id


def test_request_settings_use_ui_defaults_but_allow_explicit_language_detection(tmp_path) -> None:
    server, _ = make_server(tmp_path)
    server.update_defaults({**server.default_settings, "language": "en", "model_name": "medium"})
    omitted = JobRequest(url="https://youtu.be/default-language")
    omitted_settings = server._resolve_settings(
        model=omitted.model,
        language=omitted.language,
        language_provided="language" in omitted.model_fields_set,
        keep_video=omitted.keep_video,
        device=omitted.device,
    )
    assert omitted_settings["language"] == "en"
    assert omitted_settings["model_name"] == "medium"

    explicit_auto = JobRequest(url="https://youtu.be/auto-language", language=None)
    auto_settings = server._resolve_settings(
        model=explicit_auto.model,
        language=explicit_auto.language,
        language_provided="language" in explicit_auto.model_fields_set,
        keep_video=explicit_auto.keep_video,
        device=explicit_auto.device,
    )
    assert auto_settings["language"] is None


def test_agent_instructions_contain_live_credentials(tmp_path) -> None:
    server, _ = make_server(tmp_path)
    instructions = server.agent_instructions()
    assert server.base_url in instructions
    assert server.token in instructions
    assert "Authorization: Bearer" in instructions
    assert "no more often than every 2 seconds" in instructions
