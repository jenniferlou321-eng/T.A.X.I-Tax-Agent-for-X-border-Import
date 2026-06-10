"""Static file server for the T.A.X.I. frontend on port 9000.

Why a hand-rolled server instead of nginx / caddy / vite preview:
  - The deployment target (CentOS 7) ships Python 3.6 by default and may
    not have nginx installed. This script needs nothing beyond the stdlib.
  - We need SPA fallback (any non-asset 404 -> /index.html) so React Router
    can handle deep links like /filings/abc123 or /agent.
  - We deliberately do NOT proxy /api to the backend here -- the frontend
    already runs same-origin, and the public-internet tunnel/proxy in front
    of this process is expected to forward /api -> 127.0.0.1:8765. Keeping
    a single frontend-only port makes the deploy topology obvious.

Python 3.6 compatibility:
  - SimpleHTTPRequestHandler.directory was added in Python 3.7, so we set
    it as a class attribute per-request via a small factory.

Run:
  python serve_frontend_9000.py [--dist frontend/dist] [--port 9000]
  # 0.0.0.0:9000 by default so it's reachable from outside the host.
"""
import argparse
import http.server
import os
import socketserver
import sys
from pathlib import Path

DEFAULT_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
DEFAULT_PORT = 9000

# File extensions that should NEVER be SPA-rewritten -- the browser would
# request a 200 OK asset, not the SPA shell.
ASSET_EXTS = {
    ".js", ".mjs", ".css", ".map", ".json", ".svg", ".png", ".jpg",
    ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot",
    ".otf", ".wasm", ".txt", ".xml",
}


class SPAStaticHandler(http.server.SimpleHTTPRequestHandler):
    """Serves files from `self.directory` with SPA fallback to /index.html."""

    def translate_path(self, path):
        # Python 3.6's SimpleHTTPRequestHandler ignores the `directory`
        # class attribute inside translate_path (that branch was added in
        # 3.7). Reimplement the safe-join here so the served root is the
        # dist directory and not CWD.
        #
        # NB: we read `self.serve_dir`, NOT `self.directory`. On Python 3.7+
        # the base __init__ sets `self.directory = os.getcwd()` as an instance
        # attribute, which shadows any class attribute — so a class-level
        # `directory` is silently overwritten with CWD. `serve_dir` is ours
        # alone and survives on every version.
        # Drop the query string and percent-decode (the parent's first steps).
        import posixpath
        import urllib.parse
        path = path.split("?", 1)[0]
        path = path.split("#", 1)[0]
        path = posixpath.normpath(urllib.parse.unquote(path))
        words = [w for w in path.split("/") if w]
        root = os.path.abspath(self.serve_dir)
        full = root
        for w in words:
            if os.path.dirname(w) or w in (os.curdir, os.pardir):
                # Path component with separators or traversal — refuse.
                continue
            candidate = os.path.join(full, w)
            if os.path.commonpath([root, os.path.abspath(candidate)]) != root:
                # Escaped the root — refuse.
                continue
            full = candidate
        return full

    def send_error(self, code, message=None, explain=None):
        # 404s on non-asset paths get rewritten to /index.html (SPA fallback).
        if code == 404 and not self._is_asset_request():
            self.path = "/index.html"
            self._send_index()
            return
        return super().send_error(code, message, explain)

    def _send_index(self):
        try:
            with open(os.path.join(self.serve_dir, "index.html"), "rb") as f:
                body = f.read()
        except (OSError, AttributeError):
            self.send_error(500, "index.html not found -- did you run `npm run build`?")
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _is_asset_request(self):
        # Strip query string before checking the suffix.
        path = self.path.split("?", 1)[0]
        _, ext = os.path.splitext(path)
        return ext.lower() in ASSET_EXTS

    def log_message(self, fmt, *args):
        sys.stderr.write("[frontend:9000] %s %s\n" % (self.address_string(), fmt % args))


def make_handler(directory):
    """Return a handler class bound to `directory` (Python 3.6 compatible).

    We bind the path to a custom `serve_dir` attribute rather than the
    stdlib's `directory`: on Python 3.7+ the base __init__ overwrites
    `self.directory` with os.getcwd(), so a class-level `directory` would
    be ignored. `serve_dir` is read by our translate_path/_send_index.
    """
    return type(
        "SPAStaticHandler_%s" % abs(hash(directory)),
        (SPAStaticHandler,),
        {"serve_dir": directory},
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dist", type=Path, default=DEFAULT_DIST,
                   help="Path to the built frontend (default: %s)" % DEFAULT_DIST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--host", default="0.0.0.0",
                   help="Bind address (default: 0.0.0.0 so it's reachable from outside)")
    args = p.parse_args()

    dist = str(args.dist.resolve())
    if not os.path.isfile(os.path.join(dist, "index.html")):
        sys.stderr.write(
            "ERROR: %s/index.html not found.\n"
            "Build the frontend first: cd frontend && npm install && npm run build\n"
            "Or pass --dist to point at a pre-built directory.\n" % dist
        )
        return 2

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = ThreadedHTTPServer((args.host, args.port), make_handler(dist))
    sys.stdout.write("[frontend:9000] serving %s on http://%s:%d\n"
                     % (dist, args.host, args.port))
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\n[frontend:9000] shutting down\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
