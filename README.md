# YT Transcriber

YT Transcriber is a local Windows desktop application that downloads public or otherwise authorized YouTube videos and turns their speech into files that are easy to review with an LLM. It supports unattended multi-video queues, NVIDIA GPU acceleration, CPU fallback, transcript previews, subtitles, structured JSON, and batch ZIP exports.

Built and maintained by [Robomuffin Labs](https://robomuffinlabs.com/), home to AI-augmented tools, experiments, and resources.

No transcription API key is required. Audio is transcribed locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper); media downloading is handled by [yt-dlp](https://github.com/yt-dlp/yt-dlp).

> [!IMPORTANT]
> Download and transcribe only media you are authorized to use. You are responsible for complying with YouTube's terms, copyright law, privacy obligations, and any rules governing the source material.

## Features

- Paste one URL or several URLs at once.
- Process a queue sequentially and leave it unattended.
- Continue the queue when an individual item fails.
- Use Whisper `large-v3` for maximum quality on a correctly configured NVIDIA GPU.
- Automatically choose a lighter default on CPU-only machines.
- Detect incomplete CUDA installations before work begins.
- Retry on CPU when Auto mode encounters a GPU inference failure.
- Keep the downloaded video or retain only its audio.
- Preview and copy completed transcripts inside the app.
- Export an individual transcript or all completed transcripts as a ZIP.
- Write rotating diagnostic logs for troubleshooting.

## Generated files

Every successful queue item can produce:

| File | Purpose |
| --- | --- |
| Downloaded `.mp4`, `.webm`, or audio file | Local source media |
| `*-transcript.txt` | Clean paragraph text for pasting into an LLM |
| `*-AI-ready.md` | Source metadata plus a clean transcript |
| `*-timestamped.txt` | Human-readable timestamped transcript |
| `.srt` | Standard subtitle file |
| `.json` | Metadata, device information, and timed segments |
| Exported `.zip` | All transcript formats for completed jobs, without large media files |

The default output directory is `%USERPROFILE%\Documents\YT Transcripts`.

## Supported environment

The desktop launcher is designed for 64-bit Windows 10 or Windows 11.

### Required

| Requirement | Version or purpose |
| --- | --- |
| Python | CPython 3.11 or 3.12, 64-bit |
| Internet connection | Required for YouTube downloads and the first download of each Whisper model |
| Disk space | Enough for the selected model, downloaded media, and transcript outputs |

### Strongly recommended

| Requirement | Why |
| --- | --- |
| FFmpeg binary | Required to merge separate video and audio streams when **Keep the downloaded video** is enabled |
| Current yt-dlp dependencies | YouTube changes frequently; rerun `install.bat` when downloads begin failing |
| Deno or Node.js | A JavaScript runtime can be required by newer yt-dlp YouTube extraction paths |

FFmpeg means the actual `ffmpeg.exe` and `ffprobe.exe` programs—not a Python package named `ffmpeg`.

## Quick start

1. Download or clone this repository.
2. Install 64-bit Python 3.11 or 3.12 from [python.org](https://www.python.org/downloads/windows/). Enable **Add Python to PATH** during installation.
3. Install FFmpeg. One Windows option is:

   ```powershell
   winget install Gyan.FFmpeg
   ```

4. Double-click **`install.bat`**. It creates an isolated `.venv`, installs the application dependencies, checks FFmpeg, and reports GPU readiness.
5. Double-click **`run.bat`**.
6. Paste one or more YouTube URLs, one per line, and select **Add to queue**.
7. Choose the output directory, model, language, and processing mode.
8. Select **Run queued videos**.

`run.bat` invokes the installer automatically when `.venv` does not exist. The older `SETUP.bat` and `START_YT_TRANSCRIBER.bat` names remain as compatibility wrappers.

## NVIDIA GPU acceleration

An NVIDIA driver and a visible GPU are not sufficient by themselves. The current faster-whisper/CTranslate2 GPU stack requires both:

- **CUDA 12.x cuBLAS**, providing `cublas64_12.dll`
- **cuDNN 9 for CUDA 12**, providing `cudnn64_9.dll`

These requirements come from the [faster-whisper GPU installation documentation](https://github.com/SYSTRAN/faster-whisper#gpu). CTranslate2's Windows wheels support CUDA execution, but the NVIDIA runtime libraries must be installed separately.

> [!WARNING]
> CUDA 13 does not replace CUDA 12 for this application. A machine can have a working NVIDIA driver and CUDA 13 while still failing with `Library cublas64_12.dll is not found`. CUDA 12 can be installed side-by-side with CUDA 13.

### Recommended Windows GPU setup

1. Install or update the [NVIDIA display driver](https://www.nvidia.com/Download/index.aspx).
2. Install a [CUDA Toolkit 12.x release](https://developer.nvidia.com/cuda-toolkit-archive).
3. Install [cuDNN 9 for CUDA 12](https://developer.nvidia.com/cudnn-downloads).
4. Ensure the CUDA 12 `bin` directory containing `cublas64_12.dll` and the directory containing `cudnn64_9.dll` are on the system `PATH`.
5. Close and reopen terminals and the application. A Windows restart is the simplest way to refresh all environment variables.
6. Run **`diagnose.bat`**.

Expected result:

```text
NVIDIA GPU acceleration is ready (1 CUDA device detected).
Default: large-v3 with float16 for the best transcription quality.
```

You can also check the DLLs directly:

```powershell
where.exe cublas64_12.dll
where.exe cudnn64_9.dll
```

### Processing modes

| Mode | Behavior |
| --- | --- |
| Auto | Uses CUDA only when the GPU and required CUDA 12/cuDNN 9 libraries are loadable; otherwise uses CPU |
| NVIDIA GPU | Requires a complete CUDA runtime and stops with a clear error if it is unavailable |
| CPU | Never attempts CUDA; uses `int8` computation |

GPU mode uses `float16`. CPU mode uses `int8`. The output JSON records the device and compute type actually used.

### This machine has an NVIDIA GPU but uses CPU

Run `diagnose.bat`. The most common causes are:

- CUDA 13 is installed but CUDA 12 is not.
- `cublas64_12.dll` is missing or its CUDA 12 `bin` directory is not on `PATH`.
- cuDNN 9 is not installed or `cudnn64_9.dll` is not on `PATH`.
- The application was already open when PATH or CUDA was changed.
- NVIDIA drivers are outdated.

Auto mode deliberately falls back to CPU rather than abandoning the queue. The app's status line and output JSON show which device was ultimately used.

## CPU-only operation

A GPU is optional. On a machine without a complete CUDA runtime, the application defaults to the `small` model and CPU processing. Long videos can take considerably longer on CPU.

| Model | Suggested use |
| --- | --- |
| `large-v3` | Best general transcription quality; recommended for a capable NVIDIA GPU such as a 12 GB RTX card |
| `medium` | High quality with less GPU memory and compute demand |
| `small` | Recommended balance for CPU-only computers |
| `base` | Lower-powered or older computers |
| `tiny` | Fastest processing when accuracy is less important |

The first use of each model downloads it from Hugging Face. Later runs reuse the cached model, normally stored under `%USERPROFILE%\.cache\huggingface\hub`.

## Batch workflow

1. Paste multiple URLs into the URL box, one per line.
2. Select **Add to queue**.
3. Add more groups of URLs if needed.
4. Select **Run queued videos**.

Jobs run one at a time. Sequential processing avoids exhausting GPU memory and makes failures easier to isolate. A failed job is marked **Failed** and the next queued job continues. Select a failed row to see its error.

The **Stop** button cancels the active job after the current operation reaches a safe cancellation point. Items that have not started remain queued and can be run later.

## Delivering transcripts to an LLM

- Select a completed queue row and use **Copy transcript** for a quick paste.
- Use **Save transcript as…** to make another copy of the AI-ready Markdown or plain text.
- Use **Export completed ZIP** to bundle all completed transcript formats and a source manifest.
- Use **Open output folder** to access the original files directly.

The ZIP intentionally excludes downloaded video and audio files.

## Privacy and network behavior

Transcription runs locally. The application does not send transcript text to OpenAI or another LLM service.

Network access is still used for:

- downloading media from YouTube;
- downloading the selected Whisper model from Hugging Face on first use;
- installing or updating Python dependencies when `install.bat` is run.

Logs, media, and transcripts remain local unless you choose to upload or share them. Do not publish logs containing private URLs or personal file paths without reviewing them first.

## Diagnostics and logs

Run:

```text
diagnose.bat
```

It reports:

- whether CTranslate2 sees a CUDA device;
- whether the required CUDA 12 and cuDNN 9 libraries can actually be loaded;
- FFmpeg location;
- Python, faster-whisper, CTranslate2, and yt-dlp versions;
- the runtime log location.

The application writes rotating logs to:

```text
logs\yt-transcriber.log
```

Up to three older 2 MB log files are retained. Logs are excluded from Git.

## Troubleshooting

### `Library cublas64_12.dll is not found or cannot be loaded`

Install CUDA Toolkit 12.x and ensure its `bin` directory is on `PATH`. CUDA 13 alone does not supply this DLL.

### `cudnn64_9.dll` is missing

Install cuDNN 9 built for CUDA 12 and ensure its DLL directory is on `PATH`.

### The GPU is detected but transcription falls back to CPU

Run `diagnose.bat`. Auto mode requires both CUDA DLLs to load successfully. Restart the application after correcting PATH.

### A download fails

1. Confirm the video is public and available in your region.
2. Run `install.bat` again to update yt-dlp and its dependencies.
3. Confirm FFmpeg is installed.
4. Review `logs\yt-transcriber.log`.

Age-restricted, members-only, private, DRM-protected, or authentication-dependent videos may not work. The current UI does not import browser cookies.

### The queue appears idle

The first run may be downloading a large Whisper model. Check the status text and log. If no Python process is running, restart with `run.bat`; already downloaded media remains in the output directory.

### Transcription is too slow

- Confirm GPU readiness with `diagnose.bat`.
- Select Auto or NVIDIA GPU processing when the CUDA runtime is complete.
- On CPU, choose `small`, `base`, or `tiny`.
- Turn off **Keep the downloaded video** when disk use matters more than retaining media.

## Project structure

```text
.
├── .github/                 # CI, issue forms, and pull request template
├── tests/                   # Unit tests
├── yt_transcriber/
│   ├── core.py              # Download, transcription, and output pipeline
│   ├── hardware.py          # CUDA device and runtime validation
│   └── ui.py                # Tk desktop interface and batch queue
├── diagnose.bat             # Hardware and dependency diagnostics
├── install.bat              # Windows environment installer/updater
├── run.bat                  # Windows application launcher
├── run.py                   # Logging and application entry point
├── pyproject.toml           # Package metadata and dependencies
└── requirements*.txt        # Simple installer/developer dependency lists
```

## Development

```powershell
git clone <your-repository-url>
cd YT-Transcribe
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
```

Run all local checks:

```powershell
python -m compileall -q run.py yt_transcriber tests
python -m pytest
python -m pip check
```

GitHub Actions runs these checks on Windows and Ubuntu with Python 3.11 and 3.12. The desktop batch launchers are Windows-specific, but the core package and tests are kept portable where practical.

See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

## Known limitations

- No browser-cookie import for protected videos.
- No speaker diarization or speaker labels.
- No queue persistence after the application closes.
- Jobs are intentionally sequential rather than parallel.
- The application does not summarize or analyze transcripts; it prepares them for another tool.

## Security

See [SECURITY.md](SECURITY.md) for private vulnerability reporting and data-handling guidance.

## About Robomuffin Labs

YT Transcriber is a [Robomuffin Labs](https://robomuffinlabs.com/) project. Robomuffin Labs builds and shares practical AI-augmented tools and experiments for creators, researchers, and people who enjoy running useful technology locally.

## License

This project is licensed under the [MIT License](LICENSE). Third-party packages, model files, FFmpeg builds, downloaded media, and YouTube content retain their own licenses and terms.
