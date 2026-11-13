#!/usr/bin/env bash
# One-time setup: create an isolated .venv and install the UI packages (Linux / WSL).
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python 3 was not found. Install it (for WSL/Ubuntu: sudo apt install python3 python3-venv), then try again." >&2
  exit 1
fi
if ! "$PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "Python 3.10 or newer is required (found $("$PYTHON" -V 2>&1)). Set PYTHON=/path/to/python3.x to choose another." >&2
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  "$PYTHON" -m venv .venv || { echo "Could not create .venv. On Ubuntu/Debian run: sudo apt install python3-venv" >&2; exit 1; }
fi
.venv/bin/python -m pip install -r requirements-ui.txt
echo "Setup complete. Run ./start_ui.sh to open Protocol Review."
