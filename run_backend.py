"""Launch uvicorn for the T.A.X.I. backend.

The repo root (the directory containing this file) is the import root: the
`backend/` package lives directly under it, so adding the repo root to
sys.path makes `import backend` work without an editable install.

This script is path-agnostic — it derives the repo root from its own location,
so it works on macOS dev machines and on Linux servers alike.
"""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

# Load .env (stdlib only — no python-dotenv dependency) so the engine sees
# ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN / model names without the launcher
# having to export them.
_env_file = REPO_ROOT / ".env"
if _env_file.is_file():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

# Ensure the repo root is on sys.path so `backend` is importable.
root = str(REPO_ROOT)
if root not in sys.path:
    sys.path.insert(0, root)

# Run uvicorn programmatically
import uvicorn

if __name__ == "__main__":
    os.chdir(root)
    # Honour $PORT and $HOST so the deployment platform (e.g. Heroku-style,
    # systemd with overrides) can override without code changes.
    uvicorn.run(
        "backend.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8765")),
        reload=os.environ.get("UVICORN_RELOAD", "0") == "1",
    )
