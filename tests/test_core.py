import inspect
import zipfile

from yt_transcriber.core import (
    JobResult,
    TranscriptSegment,
    _paragraph_text,
    clock_time,
    create_transcript_zip,
    is_youtube_url,
    process_video,
    safe_filename,
)


def test_youtube_url_validation() -> None:
    assert is_youtube_url("https://www.youtube.com/watch?v=abc123")
    assert is_youtube_url("https://youtu.be/abc123")
    assert is_youtube_url("https://music.youtube.com/watch?v=abc123")
    assert not is_youtube_url("https://example.com/watch?v=abc123")
    assert not is_youtube_url("not a url")


def test_clock_formats() -> None:
    assert clock_time(65.432) == "00:01:05.432"
    assert clock_time(3661.007, srt=True) == "01:01:01,007"
    assert clock_time(-2) == "00:00:00.000"


def test_safe_filename_removes_windows_characters() -> None:
    assert safe_filename('A: video / with * bad? "chars"') == "A_ video _ with _ bad_ _chars_"


def test_paragraph_text_groups_segments() -> None:
    segments = [
        TranscriptSegment(0, 1, "One two."),
        TranscriptSegment(1, 2, "Three four."),
        TranscriptSegment(2, 3, "Five six."),
    ]
    assert _paragraph_text(segments, max_chars=22) == "One two. Three four.\n\nFive six."


def test_high_quality_gpu_defaults() -> None:
    parameters = inspect.signature(process_video).parameters
    assert parameters["model_name"].default == "large-v3"
    assert parameters["device_preference"].default == "auto"


def test_transcript_zip_excludes_large_media(tmp_path) -> None:
    paths = {}
    for name in ["transcript.txt", "timestamped.txt", "AI-ready.md", "captions.srt", "metadata.json", "video.mp4"]:
        path = tmp_path / name
        path.write_text(name, encoding="utf-8")
        paths[name] = path
    result = JobResult(
        title="Example",
        video_id="abc",
        source_url="https://youtu.be/abc",
        language="en",
        language_probability=1.0,
        duration_seconds=10,
        device="cuda",
        compute_type="float16",
        media_path=str(paths["video.mp4"]),
        transcript_path=str(paths["transcript.txt"]),
        timestamped_path=str(paths["timestamped.txt"]),
        ai_ready_path=str(paths["AI-ready.md"]),
        srt_path=str(paths["captions.srt"]),
        json_path=str(paths["metadata.json"]),
        text="Example transcript",
    )
    archive_path = create_transcript_zip([result], tmp_path / "export.zip")
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
    assert "README.txt" in names
    assert "AI-ready.md" in names
    assert "video.mp4" not in names
