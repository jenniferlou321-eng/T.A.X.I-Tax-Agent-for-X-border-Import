#!/usr/bin/env bash
# Serve the T.A.X.I. frontend production build on port 9000.
#
# Usage:
#   ./serve_frontend_9000.sh                  # serves frontend/dist on 0.0.0.0:9000
#   PORT=9100 ./serve_frontend_9000.sh        # different port
#   DIST=/path/to/dist ./serve_frontend_9000.sh
#   SKIP_PORT_KILL=1 ./serve_frontend_9000.sh # don't kill whatever's on $PORT
#
# Behaviour:
#   - Before starting, kills any process bound to $PORT (typically a stale
#     `serve_frontend_9000.py` from a previous run). Set SKIP_PORT_KILL=1
#     to opt out.
#   - This server ALSO acts as a reverse proxy for /api/* → 127.0.0.1:8765
#     so a developer hitting http://localhost:9000 directly gets a working
#     frontend + backend without needing a tunnel. The FastAPI backend on
#     8765 must still be running in another process. Override with
#     BACKEND_URL=... or BACKEND_PREFIX=... env vars. See
#     docs/deployment/port-9000.md for public-internet deployment.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DIST="${DIST:-$PROJECT_ROOT/frontend/dist}"
PORT="${PORT:-9000}"
HOST="${HOST:-0.0.0.0}"

# ── 启动前清理：杀掉占着目标端口的旧静态服务 ──
if [ "${SKIP_PORT_KILL:-0}" != "1" ]; then
  pids=""
  if command -v ss >/dev/null 2>&1; then
    pids="$(ss -ltnp 2>/dev/null | awk -v p=":$PORT" '$4 ~ p {print $0}' | grep -oP 'pid=\K[0-9]+' || true | sort -u)"
  fi
  if [ -z "$pids" ] && command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti tcp:"$PORT" 2>/dev/null || true)"
  fi
  # 兜底：按命令行特征找旧的 serve_frontend_9000
  extra="$(pgrep -f "serve_frontend_9000\.py" 2>/dev/null || true)"
  pids="$(printf "%s\n%s\n" "$pids" "$extra" | grep -E '^[0-9]+$' || true | sort -u)"

  if [ -n "$pids" ]; then
    echo "[serve_frontend_9000] killing existing frontend on port $PORT: $pids"
    for pid in $pids; do
      kill "$pid" 2>/dev/null || true
    done
    waited=0
    while [ "$waited" -lt 3 ]; do
      alive=""
      for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then alive="$alive $pid"; fi
      done
      [ -z "$alive" ] && break
      sleep 1
      waited=$((waited + 1))
    done
    for pid in $pids; do
      if kill -0 "$pid" 2>/dev/null; then
        echo "[serve_frontend_9000] force-killing $pid"
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
  fi
fi

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
  --host "$HOST" \
  --backend-url "${BACKEND_URL:-http://127.0.0.1:8765}" \
  --backend-prefix "${BACKEND_PREFIX:-/api}"
