@echo off
setlocal
cd /d "%~dp0..\.."
if not exist ".venv\Scripts\python.exe" (
  echo Run setup_ui.bat once before starting the app.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import streamlit, streamlit_pdf_viewer"
if errorlevel 1 (
  echo UI dependencies are missing. Run setup_ui.bat once.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\start_ui.py
if errorlevel 1 pause
