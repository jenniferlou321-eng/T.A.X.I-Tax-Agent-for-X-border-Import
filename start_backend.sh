#!/bin/bash
# Start the T.A.X.I. FastAPI backend on port 8765.
#
# Usage:
#   ./start_backend.sh                  # default 0.0.0.0:8765
#   PORT=9001 ./start_backend.sh        # override
#   HOST=127.0.0.1 ./start_backend.sh
#   UVICORN_RELOAD=1 ./start_backend.sh # hot-reload (dev)
#
# Path-agnostic: derives PROJECT_DIR from $BASH_SOURCE so it works on macOS
# dev machines and Linux servers.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

# Activate conda env `taxagent` if it exists, but don't fail if conda is
# missing (e.g. on a bare-bones Linux server) — fall back to whatever python
# is on $PATH.
if command -v conda >/dev/null 2>&1; then
  # shellcheck disable=SC1091
  source "$(conda info --base)/etc/profile.d/conda.sh"
  if conda env list | awk '{print $1}' | grep -qx "taxagent"; then
    conda activate taxagent
  fi
fi

# If `backend` is importable from PROJECT_DIR (the repo root), use uvicorn
# directly. Otherwise fall back to the path-portable Python wrapper which
# injects the right sys.path.
cd "$PROJECT_DIR"
if PYTHONPATH="$PROJECT_DIR:${PYTHONPATH:-}" python -c "import backend" >/dev/null 2>&1; then
  exec python -m uvicorn backend.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-8765}" \
    $( [ "${UVICORN_RELOAD:-0}" = "1" ] && echo "--reload" )
else
  exec python "$PROJECT_DIR/run_backend.py"
fi
