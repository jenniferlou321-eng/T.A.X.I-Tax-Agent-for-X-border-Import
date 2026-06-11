#!/bin/bash
# Start the T.A.X.I. FastAPI backend on port 8765.
#
# Usage:
#   ./start_backend.sh                  # default 0.0.0.0:8765
#   PORT=9001 ./start_backend.sh        # override
#   HOST=127.0.0.1 ./start_backend.sh
#   UVICORN_RELOAD=1 ./start_backend.sh # hot-reload (dev)
#   SKIP_PORT_KILL=1 ./start_backend.sh # don't kill whatever's on $PORT
#
# Behaviour:
#   - If a previous `uvicorn backend.main:app` is bound to $PORT (or any
#     stray process is), it is killed before the new server starts. Set
#     SKIP_PORT_KILL=1 to opt out (e.g. when another service owns the port).
#   - Auto-activates the conda env `taxagent` if miniconda is installed in
#     one of the standard locations. Falls back to whatever `python` is on
#     $PATH if conda is missing.
#   - `.venv` (if present) is a symlink into the conda env so any tool that
#     hardcodes `.venv/bin/python` keeps working.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

PORT="${PORT:-8765}"

# ── 启动前清理：杀掉占着目标端口的旧进程 ──
# 用 ss/lsof 拿 PID；CentOS 7 上 ss 是 iproute2 自带的，lsof 不一定有
kill_port_occupants() {
  local port="$1"
  if [ "${SKIP_PORT_KILL:-0}" = "1" ]; then
    return 0
  fi
  local pids=""
  if command -v ss >/dev/null 2>&1; then
    pids="$(ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $0}' | grep -oP 'pid=\K[0-9]+' || true | sort -u)"
  fi
  if [ -z "$pids" ] && command -v lsof >/dev/null 2>&1; then
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  fi
  # 兜底：按命令行特征找旧的 uvicorn（即便监听在别的端口）
  local extra_pids
  extra_pids="$(pgrep -f "uvicorn backend.main:app" 2>/dev/null || true)"
  pids="$(printf "%s\n%s\n" "$pids" "$extra_pids" | grep -E '^[0-9]+$' || true | sort -u)"

  if [ -n "$pids" ]; then
    echo "[start_backend] killing existing backend on port $PORT: $pids"
    # 先 SIGTERM 让它清理；3 秒不退就 SIGKILL
    for pid in $pids; do
      kill "$pid" 2>/dev/null || true
    done
    local waited=0
    while [ "$waited" -lt 3 ]; do
      local alive=""
      for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then alive="$alive $pid"; fi
      done
      [ -z "$alive" ] && break
      sleep 1
      waited=$((waited + 1))
    done
    for pid in $pids; do
      if kill -0 "$pid" 2>/dev/null; then
        echo "[start_backend] force-killing $pid"
        kill -9 "$pid" 2>/dev/null || true
      fi
    done
  fi
}
kill_port_occupants "$PORT"

# Locate miniconda (if not already on $PATH). This lets the script work
# on machines where conda was installed but not added to /etc/profile.
_CONDA_BASE=""
for cand in "${CONDA_BASE:-}" "$HOME/miniconda3" "/opt/miniconda3" "/usr/local/miniconda3"; do
  if [ -n "$cand" ] && [ -x "$cand/bin/conda" ]; then
    _CONDA_BASE="$cand"; break
  fi
done
if [ -n "$_CONDA_BASE" ]; then
  # shellcheck disable=SC1091
  source "$_CONDA_BASE/etc/profile.d/conda.sh"
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
    --port "$PORT" \
    $( [ "${UVICORN_RELOAD:-0}" = "1" ] && echo "--reload" )
else
  exec python "$PROJECT_DIR/run_backend.py"
fi
