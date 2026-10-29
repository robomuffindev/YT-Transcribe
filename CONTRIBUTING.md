# Contributing

Thanks for helping improve YT Transcriber.

## Development setup

1. Install Python 3.11 or 3.12 and FFmpeg.
2. Create and activate a virtual environment.
3. Install the project and development dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"
   ```

4. Run the checks:

   ```powershell
   python -m compileall -q run.py yt_transcriber tests
   python -m pytest
   python -m pip check
   ```

5. When changing API behavior, also run the real localhost smoke test in an environment that permits loopback sockets:

   ```powershell
   python scripts\smoke_api.py
   ```

## Pull requests

- Keep changes focused and explain the user-facing reason for them.
- Add or update tests for behavior changes.
- Do not commit downloaded videos, transcripts, model weights, logs, virtual environments, API tokens, cookies, or browser profiles.
- Test CPU mode for all transcription changes. If changing GPU behavior, also include the CUDA/cuDNN versions used for testing.
- Preserve the sequential queue design unless resource use and cancellation behavior are explicitly addressed.
- Keep the API bound to loopback, authenticate new `/v1` routes, and avoid returning arbitrary local file paths or secrets.

## Reporting bugs

Use the bug-report issue template. Include the output from `diagnose.bat`, the relevant portion of `logs/yt-transcriber.log`, the selected model and processing mode, and whether the video is public. Remove personal paths, private URLs, and tokens before posting.
