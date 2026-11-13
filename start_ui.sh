#!/usr/bin/env bash
# Start the local app (Linux / WSL). Keep this terminal open; Ctrl+C stops the app.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "Run ./setup_ui.sh once before starting the app." >&2
  exit 1
fi
if ! .venv/bin/python -c "import streamlit, streamlit_pdf_viewer" 2>/dev/null; then
  echo "UI dependencies are missing. Run ./setup_ui.sh once." >&2
  exit 1
fi
exec .venv/bin/python scripts/start_ui.py
