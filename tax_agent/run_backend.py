"""Launch uvicorn with the right sys.path so the flat-layout `tax_agent`
package (i.e. /Users/gtc/Learning/智能会计/finalreport/tax_agent/tax_agent/)
is importable.

Why: the .pth editable install points at the package dir itself, but Python's
FileFinder needs the dir to be a *subdirectory* of a sys.path entry — not the
entry itself. The original start_backend.sh worked with the old inner-dir
layout; the current flat layout requires this wrapper.
"""
import os
import sys
from pathlib import Path

PKG_PARENT = Path("/Users/gtc/Learning/智能会计/finalreport")
PKG_DIR = PKG_PARENT / "tax_agent"

# Ensure the parent (so `tax_agent/` is a subdir) is on sys.path FIRST.
parent = str(PKG_PARENT)
if parent not in sys.path:
    sys.path.insert(0, parent)

# Run uvicorn programmatically
import uvicorn

if __name__ == "__main__":
    os.chdir(PKG_DIR)
    uvicorn.run(
        "tax_agent.server.main:app",
        host="0.0.0.0",
        port=8765,
        reload=True,
        reload_dirs=[str(PKG_DIR)],
    )
