@echo off
setlocal
cd /d "%~dp0"

echo.
echo  YT Transcriber installer
echo  ========================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or 3.12 from python.org,
  echo check "Add Python to PATH" during installation, and run install.bat again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating the private Python environment...
  python -m venv .venv
  if errorlevel 1 goto :failed
)

echo Installing or updating app dependencies. This can take a few minutes...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :failed
".venv\Scripts\python.exe" -m pip install --upgrade -r requirements.txt
if errorlevel 1 goto :failed

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo.
  echo WARNING: FFmpeg was not found. Keeping a merged video requires FFmpeg.
  echo Install it with: winget install Gyan.FFmpeg
)

echo.
echo Checking transcription hardware...
".venv\Scripts\python.exe" -m yt_transcriber.hardware

echo.
echo Installation complete. Double-click run.bat to use the app.
pause
exit /b 0

:failed
echo.
echo Installation did not finish. Review the error above, then run install.bat again.
pause
exit /b 1
