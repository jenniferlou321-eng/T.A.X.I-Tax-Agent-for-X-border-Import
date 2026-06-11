#!/usr/bin/env bash
# Rebuild the T.A.X.I. frontend production bundle.
#
# This requires Node 18+ — which the host's glibc 2.17 (CentOS 7) cannot run
# via the official upstream binaries. We work around this by using the
# `fe-build` conda env (conda-forge nodejs 20, glibc-2.17-compatible sysroot).
#
# Usage:
#   ./start_frontend_build.sh                 # full: npm install + npm run build
#   ./start_frontend_build.sh --no-install    # skip npm install, only rebuild
#   ./start_frontend_build.sh --watch         # dev mode (HMR, port 9000)
#   CONDA_BASE=/path/to/miniconda3 ./start_frontend_build.sh
#
# Output:
#   frontend/dist/   ← 重新生成, 直接由 scripts/serve_frontend_9000.sh 服务
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
FRONTEND_DIR="$PROJECT_DIR/frontend"
MODE="build"
SKIP_INSTALL=0
for arg in "$@"; do
  case "$arg" in
    --no-install) SKIP_INSTALL=1 ;;
    --watch)      MODE="watch" ;;
    --help|-h)    sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

# Locate miniconda (same logic as start_backend.sh)
_CONDA_BASE=""
for cand in "${CONDA_BASE:-}" "$HOME/miniconda3" "/opt/miniconda3" "/usr/local/miniconda3"; do
  if [ -n "$cand" ] && [ -x "$cand/bin/conda" ]; then
    _CONDA_BASE="$cand"; break
  fi
done
if [ -z "$_CONDA_BASE" ]; then
  echo "ERROR: conda not found. Install miniconda first:" >&2
  echo "  curl -sSLO https://repo.anaconda.com/miniconda/Miniconda3-py39_4.10.3-Linux-x86_64.sh" >&2
  echo "  bash Miniconda3-py39_4.10.3-Linux-x86_64.sh -b -p \$HOME/miniconda3" >&2
  echo "  \$_CONDA_BASE/bin/conda create -n fe-build -y nodejs=20" >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$_CONDA_BASE/etc/profile.d/conda.sh"
if ! conda env list | awk '{print $1}' | grep -qx "fe-build"; then
  echo "ERROR: conda env 'fe-build' not found. Create it:" >&2
  echo "  conda create -n fe-build -y nodejs=20" >&2
  exit 1
fi
conda activate fe-build
echo "[fe-build] node $(node --version) | npm $(npm --version)"

cd "$FRONTEND_DIR"
if [ "$SKIP_INSTALL" = "0" ]; then
  echo "[fe-build] npm install ..."
  npm install
fi

case "$MODE" in
  build)
    echo "[fe-build] npm run build ..."
    npm run build
    echo "[fe-build] done → frontend/dist/"
    ;;
  watch)
    echo "[fe-build] npm run dev (Ctrl-C to stop) ..."
    exec npm run dev
    ;;
esac
