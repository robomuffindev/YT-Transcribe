from __future__ import annotations

import json
import logging
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Callable, Iterable
from urllib.parse import urlparse

from .hardware import detect_hardware


logger = logging.getLogger(__name__)


StatusCallback = Callable[[str, dict], None]


class JobCancelled(RuntimeError):
    """Raised when the user stops an active job."""


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class JobResult:
    title: str
    video_id: str
    source_url: str
    language: str
    language_probability: float
    duration_seconds: float
    device: str
    compute_type: str
    media_path: str
    transcript_path: str
    timestamped_path: str
    ai_ready_path: str
    srt_path: str
    json_path: str
    text: str


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}


def is_youtube_url(value: str) -> bool:
    """Return True for an HTTP(S) URL hosted by YouTube."""
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in YOUTUBE_HOSTS


def safe_filename(value: str, limit: int = 140) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value)
    value = re.sub(r"\s+", " ", value).strip(" .")
    return (value[:limit].rstrip(" .") or "YouTube video")


def clock_time(seconds: float, *, srt: bool = False) -> str:
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _emit(callback: StatusCallback | None, event: str, **payload: object) -> None:
    if callback:
        callback(event, payload)


def _check_cancel(cancel_event: Event | None) -> None:
    if cancel_event and cancel_event.is_set():
        raise JobCancelled("Stopped by user.")


def _download_media(
    url: str,
    output_dir: Path,
    keep_video: bool,
    callback: StatusCallback | None,
    cancel_event: Event | None,
) -> tuple[dict, Path]:
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - exercised by launcher
        raise RuntimeError("yt-dlp is not installed. Run install.bat first.") from exc

    if not shutil.which("ffmpeg") and keep_video:
        raise RuntimeError("FFmpeg is required when keeping the video, but it was not found on PATH.")

    logger.info("Starting YouTube download: %s", url)
    _emit(callback, "stage", message="Reading video information…")
    output_template = str(output_dir / "%(title).140s [%(id)s].%(ext)s")

    def progress_hook(data: dict) -> None:
        _check_cancel(cancel_event)
        status = data.get("status")
        if status == "downloading":
            downloaded = float(data.get("downloaded_bytes") or 0)
            total = float(data.get("total_bytes") or data.get("total_bytes_estimate") or 0)
            percent = (downloaded / total * 100) if total else None
            _emit(
                callback,
                "download",
                percent=percent,
                speed=data.get("speed"),
                eta=data.get("eta"),
                downloaded=downloaded,
                total=total,
            )
        elif status == "finished":
            _emit(callback, "stage", message="Download complete. Preparing transcription…")

    options = {
        "format": "bestvideo*+bestaudio/best" if keep_video else "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 5,
        "windowsfilenames": True,
    }
    if keep_video:
        options["merge_output_format"] = "mp4"

    output_dir.mkdir(parents=True, exist_ok=True)
    before = set(output_dir.iterdir())
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=True)
    except JobCancelled:
        raise
    except Exception as exc:
        logger.exception("YouTube download failed for %s", url)
        if cancel_event and cancel_event.is_set():
            raise JobCancelled("Stopped by user.") from exc
        raise RuntimeError(f"YouTube download failed: {exc}") from exc

    _check_cancel(cancel_event)
    video_id = str(info.get("id") or "")
    created = [
        path
        for path in output_dir.iterdir()
        if path not in before
        and path.is_file()
        and path.suffix.lower() not in {".part", ".ytdl", ".json", ".txt", ".srt", ".md"}
    ]
    matching = [path for path in created if f"[{video_id}]" in path.name]
    candidates = matching or created
    if not candidates:
        candidates = [
            path
            for path in output_dir.iterdir()
            if path.is_file()
            and f"[{video_id}]" in path.name
            and path.suffix.lower() not in {".part", ".ytdl", ".json", ".txt", ".srt", ".md"}
        ]
    if not candidates:
        raise RuntimeError("The download finished, but the media file could not be located.")

    media_path = max(candidates, key=lambda path: path.stat().st_size)
    logger.info("Downloaded media to %s", media_path)
    return info, media_path


def _transcribe(
    media_path: Path,
    model_name: str,
    language: str | None,
    device_preference: str,
    callback: StatusCallback | None,
    cancel_event: Event | None,
) -> tuple[list[TranscriptSegment], str, float, float, str, str]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - exercised by launcher
        raise RuntimeError("faster-whisper is not installed. Run install.bat first.") from exc

    preference = device_preference.lower().strip()
    if preference not in {"auto", "cuda", "cpu"}:
        raise ValueError(f"Unknown processing device: {device_preference}")
    hardware = detect_hardware()
    cuda_available = hardware.cuda_ready

    if preference == "cuda" and not cuda_available:
        details = hardware.summary
        raise RuntimeError(
            "NVIDIA GPU mode was selected, but the complete runtime is unavailable. "
            f"{details} Install CUDA 12 (cuBLAS) and cuDNN 9, or choose Auto/CPU."
        )

    device = "cuda" if preference in {"auto", "cuda"} and cuda_available else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"

    _check_cancel(cancel_event)
    accelerator = "NVIDIA GPU" if device == "cuda" else "CPU"
    _emit(
        callback,
        "stage",
        message=f"Loading the {model_name} speech model on {accelerator}…",
        device=device,
        compute_type=compute_type,
    )
    try:
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
    except Exception as exc:
        if preference == "auto" and device == "cuda":
            device, compute_type = "cpu", "int8"
            _emit(
                callback,
                "stage",
                message="GPU runtime unavailable; safely falling back to CPU…",
                device=device,
                compute_type=compute_type,
            )
            try:
                model = WhisperModel(model_name, device=device, compute_type=compute_type)
            except Exception as cpu_exc:
                raise RuntimeError(f"Could not load the transcription model: {cpu_exc}") from cpu_exc
        else:
            raise RuntimeError(f"Could not load the transcription model: {exc}") from exc

    _check_cancel(cancel_event)
    _emit(
        callback,
        "stage",
        message=f"Transcribing locally on {'NVIDIA GPU' if device == 'cuda' else 'CPU'}…",
        device=device,
        compute_type=compute_type,
    )
    def consume(active_model: object) -> tuple[list[TranscriptSegment], object, float]:
        generated_segments, transcription_info = active_model.transcribe(
            str(media_path),
            language=language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=True,
        )
        active_duration = float(getattr(transcription_info, "duration", 0.0) or 0.0)
        active_segments: list[TranscriptSegment] = []
        for segment in generated_segments:
            _check_cancel(cancel_event)
            item = TranscriptSegment(float(segment.start), float(segment.end), segment.text.strip())
            if item.text:
                active_segments.append(item)
            percent = (item.end / active_duration * 100) if active_duration else None
            _emit(callback, "transcribe", percent=percent, current=item.end, duration=active_duration)
        return active_segments, transcription_info, active_duration

    try:
        segments, info, duration = consume(model)
    except JobCancelled:
        raise
    except Exception as exc:
        if preference == "auto" and device == "cuda":
            logger.exception("GPU transcription failed; retrying on CPU")
            device, compute_type = "cpu", "int8"
            _emit(
                callback,
                "stage",
                message="GPU transcription failed; retrying safely on CPU…",
                device=device,
                compute_type=compute_type,
            )
            try:
                model = WhisperModel(model_name, device=device, compute_type=compute_type)
                segments, info, duration = consume(model)
            except JobCancelled:
                raise
            except Exception as cpu_exc:
                logger.exception("CPU fallback transcription failed")
                raise RuntimeError(f"Transcription failed on GPU and CPU fallback: {cpu_exc}") from cpu_exc
        else:
            logger.exception("Transcription failed")
            raise RuntimeError(f"Transcription failed: {exc}") from exc

    detected_language = str(getattr(info, "language", language or "unknown"))
    probability = float(getattr(info, "language_probability", 0.0) or 0.0)
    logger.info("Transcription complete: %s (%s/%s)", media_path.name, device, compute_type)
    return segments, detected_language, probability, duration, device, compute_type


def _paragraph_text(segments: Iterable[TranscriptSegment], max_chars: int = 1400) -> str:
    paragraphs: list[str] = []
    current: list[str] = []
    length = 0
    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue
        if current and length + len(text) + 1 > max_chars:
            paragraphs.append(" ".join(current))
            current, length = [], 0
        current.append(text)
        length += len(text) + 1
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


def _write_outputs(
    output_dir: Path,
    info: dict,
    media_path: Path,
    segments: list[TranscriptSegment],
    model_name: str,
    language: str,
    language_probability: float,
    duration: float,
    device: str,
    compute_type: str,
) -> JobResult:
    title = str(info.get("title") or media_path.stem)
    video_id = str(info.get("id") or "unknown")
    source_url = str(info.get("webpage_url") or info.get("original_url") or "")
    stem = safe_filename(f"{title} [{video_id}]")
    plain_text = _paragraph_text(segments)

    timestamped = "\n".join(f"[{clock_time(item.start)}] {item.text}" for item in segments)
    srt_blocks = [
        f"{index}\n{clock_time(item.start, srt=True)} --> {clock_time(item.end, srt=True)}\n{item.text}"
        for index, item in enumerate(segments, start=1)
    ]

    header = (
        f"# {title}\n\n"
        f"- Source: {source_url}\n"
        f"- Detected language: {language}\n"
        f"- Duration: {clock_time(duration)}\n"
        f"- Transcription model: faster-whisper {model_name}\n"
        f"- Processing: {'NVIDIA GPU' if device == 'cuda' else 'CPU'} ({compute_type})\n\n"
        "## Transcript\n\n"
    )

    transcript_path = output_dir / f"{stem} - transcript.txt"
    timestamped_path = output_dir / f"{stem} - timestamped.txt"
    ai_ready_path = output_dir / f"{stem} - AI-ready.md"
    srt_path = output_dir / f"{stem}.srt"
    json_path = output_dir / f"{stem}.json"

    transcript_path.write_text(plain_text + "\n", encoding="utf-8")
    timestamped_path.write_text(timestamped + "\n", encoding="utf-8")
    ai_ready_path.write_text(header + plain_text + "\n", encoding="utf-8")
    srt_path.write_text("\n\n".join(srt_blocks) + "\n", encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "title": title,
                "video_id": video_id,
                "source_url": source_url,
                "channel": info.get("channel") or info.get("uploader"),
                "upload_date": info.get("upload_date"),
                "duration_seconds": duration,
                "language": language,
                "language_probability": language_probability,
                "model": model_name,
                "device": device,
                "compute_type": compute_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "segments": [asdict(segment) for segment in segments],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return JobResult(
        title=title,
        video_id=video_id,
        source_url=source_url,
        language=language,
        language_probability=language_probability,
        duration_seconds=duration,
        device=device,
        compute_type=compute_type,
        media_path=str(media_path),
        transcript_path=str(transcript_path),
        timestamped_path=str(timestamped_path),
        ai_ready_path=str(ai_ready_path),
        srt_path=str(srt_path),
        json_path=str(json_path),
        text=plain_text,
    )


def process_video(
    url: str,
    output_dir: str | Path,
    *,
    model_name: str = "large-v3",
    language: str | None = None,
    keep_video: bool = True,
    device_preference: str = "auto",
    callback: StatusCallback | None = None,
    cancel_event: Event | None = None,
) -> JobResult:
    """Download one YouTube URL, transcribe it, and write portable outputs."""
    url = url.strip()
    if not is_youtube_url(url):
        raise ValueError("Enter a valid youtube.com or youtu.be URL.")
    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)

    info, media_path = _download_media(url, destination, keep_video, callback, cancel_event)
    segments, detected_language, probability, duration, device, compute_type = _transcribe(
        media_path, model_name, language, device_preference, callback, cancel_event
    )
    _check_cancel(cancel_event)
    _emit(callback, "stage", message="Saving transcript files…")
    result = _write_outputs(
        destination,
        info,
        media_path,
        segments,
        model_name,
        detected_language,
        probability,
        duration,
        device,
        compute_type,
    )
    _emit(callback, "complete", result=result)
    return result


def create_transcript_zip(results: Iterable[JobResult], destination: str | Path) -> Path:
    """Bundle transcript artifacts (not media) for easy upload to an LLM."""
    completed = list(results)
    if not completed:
        raise ValueError("There are no completed transcripts to export.")
    archive_path = Path(destination).expanduser().resolve()
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = ["YT Transcriber export", "", f"Completed videos: {len(completed)}", ""]
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for result in completed:
            files = [
                result.ai_ready_path,
                result.transcript_path,
                result.timestamped_path,
                result.srt_path,
                result.json_path,
            ]
            for file_path in files:
                path = Path(file_path)
                if path.exists():
                    archive.write(path, arcname=path.name)
            manifest.append(f"- {result.title}: {result.source_url}")
        archive.writestr("README.txt", "\n".join(manifest) + "\n")
    return archive_path
