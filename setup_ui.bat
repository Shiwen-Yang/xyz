@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -c "import sys; raise SystemExit(sys.version_info < (3,11))"
  if errorlevel 1 (
    echo Python 3.11 or newer and the Windows Python launcher are required. Install using your approved process, then try again.
    pause
    exit /b 1
  )
  py -3 -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-ui.txt
if errorlevel 1 (
  echo Setup did not finish. Your work files were not changed.
  pause
  exit /b 1
)
echo Setup complete. Double-click start_ui.bat to open Protocol Review.
pause
