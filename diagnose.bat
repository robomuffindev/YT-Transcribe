@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo The app is not installed yet. Run install.bat first.
  pause
  exit /b 1
)

echo.
echo  YT Transcriber diagnostics
echo  ==========================
echo.
".venv\Scripts\python.exe" -m yt_transcriber.hardware
echo.
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo FFmpeg: NOT FOUND
) else (
  echo FFmpeg: found
  where ffmpeg
)
echo.
".venv\Scripts\python.exe" -c "import sys, faster_whisper, ctranslate2, yt_dlp; print('Python:', sys.version.split()[0]); print('faster-whisper:', faster_whisper.__version__); print('CTranslate2:', ctranslate2.__version__); print('yt-dlp:', yt_dlp.version.__version__)"
echo.
echo Runtime log: %~dp0logs\yt-transcriber.log
pause
