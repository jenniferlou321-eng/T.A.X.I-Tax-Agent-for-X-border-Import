#!/usr/bin/env bash
# Serve the T.A.X.I. frontend production build on port 9000.
#
# Usage:
#   ./serve_frontend_9000.sh                  # serves frontend/dist on 0.0.0.0:9000
#   PORT=9100 ./serve_frontend_9000.sh        # different port
#   DIST=/path/to/dist ./serve_frontend_9000.sh
#
# Make sure the FastAPI backend is running on 8765 in another process — the
# public tunnel / reverse proxy in front of this server is expected to route
# /api → 127.0.0.1:8765. See docs/deployment/port-9000.md for the full recipe.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DIST="${DIST:-$PROJECT_ROOT/frontend/dist}"
PORT="${PORT:-9000}"
HOST="${HOST:-0.0.0.0}"

if [[ ! -f "$DIST/index.html" ]]; then
  echo "[serve_frontend_9000] $DIST/index.html not found."
  echo "[serve_frontend_9000] Build the frontend first:"
  echo "    cd $PROJECT_ROOT/frontend && npm install && npm run build"
  echo "[serve_frontend_9000] Or set DIST=/path/to/prebuilt-dist and re-run."
  exit 1
fi

exec python3 "$SCRIPT_DIR/serve_frontend_9000.py" \
  --dist "$DIST" \
  --port "$PORT" \
  --host "$HOST"
