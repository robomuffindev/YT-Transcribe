@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
  echo YT Transcriber needs its one-time installation first.
  call install.bat
  if errorlevel 1 exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "%~dp0run.py"
