"""Static file server for the T.A.X.I. frontend on port 9000.

Why a hand-rolled server instead of nginx / caddy / vite preview:
  - The deployment target (CentOS 7) ships Python 3.6 by default and may
    not have nginx installed. This script needs nothing beyond the stdlib.
  - We need SPA fallback (any non-asset 404 -> /index.html) so React Router
    can handle deep links like /filings/abc123 or /agent.
  - We also act as a reverse proxy for `/api/*` -> 127.0.0.1:8765 so the
    same `:9000` URL works for both the static UI and the FastAPI backend
    on a developer laptop with no public tunnel in front. A public-internet
    tunnel/reverse-proxy may still take over `/api/*` upstream of this
    process if desired -- it can simply talk to `:8765` directly.

Python 3.6 compatibility:
  - SimpleHTTPRequestHandler.directory was added in Python 3.7, so we set
    it as a class attribute per-request via a small factory.
  - urllib.request is used for the proxy leg because the stdlib ships it.

Run:
  python serve_frontend_9000.py [--dist frontend/dist] [--port 9000]
                               [--host 0.0.0.0]
                               [--backend-url http://127.0.0.1:8765]
                               [--backend-prefix /api]
  # 0.0.0.0:9000 by default so it's reachable from outside the host.
"""
import argparse
import http.server
import os
import socketserver
import sys
import urllib.parse
import urllib.request
from pathlib import Path

DEFAULT_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
DEFAULT_PORT = 9000
DEFAULT_BACKEND_URL = "http://127.0.0.1:8765"
DEFAULT_BACKEND_PREFIX = "/api"

# File extensions that should NEVER be SPA-rewritten -- the browser would
# request a 200 OK asset, not the SPA shell.
ASSET_EXTS = {
    ".js", ".mjs", ".css", ".map", ".json", ".svg", ".png", ".jpg",
    ".jpeg", ".gif", ".webp", ".ico", ".woff", ".woff2", ".ttf", ".eot",
    ".otf", ".wasm", ".txt", ".xml",
}

# Hop-by-hop headers from RFC 7230 §6.1 — strip on both inbound and outbound.
HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
}


class SPAStaticHandler(http.server.SimpleHTTPRequestHandler):
    """Serves files from `self.serve_dir` with SPA fallback to /index.html."""

    # Bound by the factory below (avoids the Python 3.7+ `self.directory =
    # os.getcwd()` shadow that the stdlib applies at instance init).
    serve_dir = ""
    backend_url = ""
    backend_prefix = ""

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

    # ── /api/* reverse proxy ──

    def _is_proxy_request(self):
        return self.backend_prefix and self.path.startswith(self.backend_prefix + "/")

    def _proxy_to_backend(self):
        """Forward self.path → backend_url. Streams body for SSE."""
        backend = self.backend_url.rstrip("/")
        # `self.path` 在 SimpleHTTPRequestHandler 里是 percent-decoded 后的
        # 形式。urllib.request.Request 用 ASCII 编码 target URL，
        # 中文字符（消息 / VRN 里的非 ASCII）会爆 UnicodeEncodeError。
        # 重新 percent-encode，保留路径 / 查询中常见的 safe 字符。
        target_url = backend + urllib.parse.quote(self.path, safe="/?&=#:%")

        # Build upstream headers, stripping hop-by-hop and Host.
        upstream_headers = {}
        for k, v in self.headers.items():
            lk = k.lower()
            if lk in HOP_BY_HOP or lk == "host":
                continue
            upstream_headers[k] = v
        # Pin Host to the backend so FastAPI's `Host` header validation
        # (and any vhost routing) sees 127.0.0.1:8765, not 127.0.0.1:9000.
        upstream_headers["Host"] = urllib.parse.urlparse(backend).netloc
        upstream_headers["Connection"] = "close"

        # Read the request body (POST/PUT/PATCH may have one).
        body = None
        if self.command in ("POST", "PUT", "PATCH", "DELETE"):
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
            except ValueError:
                length = 0
            if length:
                body = self.rfile.read(length)

        req = urllib.request.Request(
            target_url,
            data=body,
            method=self.command,
            headers=upstream_headers,
        )

        try:
            upstream = urllib.request.urlopen(req, timeout=300)
        except urllib.error.HTTPError as e:
            # Pass backend's status + body through verbatim (FastAPI error JSON
            # gives the React Query client a proper {detail:"..."} payload).
            self._write_upstream_response(e.code, e.headers, e.read())
            return
        except Exception as e:
            msg = "backend unreachable: %s" % e
            sys.stderr.write("[frontend:9000] %s %s -> %s FAILED: %s\n"
                             % (self.address_string(), self.command, target_url, e))
            body = ('{"detail":"%s"}' % msg).encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
            return

        # SSE / chunked streaming: copy body byte-for-byte without buffering.
        try:
            self._write_upstream_response(upstream.status, upstream.headers, upstream)
        finally:
            try:
                upstream.close()
            except Exception:
                pass

    def _write_upstream_response(self, status, upstream_headers, body_or_stream):
        """Send `status` + headers + body to the client. Streams if needed."""
        headers_sent = {}
        try:
            self.send_response(status)
            content_type = None
            for k, v in upstream_headers.items():
                lk = k.lower()
                if lk in HOP_BY_HOP:
                    continue
                # First Content-Type wins (skip duplicates from multi-value).
                if lk == "content-type":
                    if content_type is None:
                        content_type = v
                        self.send_header("Content-Type", v)
                    continue
                self.send_header(k, v)
                headers_sent[lk] = v
            # If backend used chunked transfer, it won't have sent a
            # Content-Length. Don't fabricate one — stream as-is.
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()

            if hasattr(body_or_stream, "read"):
                # File-like body (HTTPError or urlopen stream). 读小
                # 块（256B）保证 SSE 增量尽快到客户端：SDK 路径下
                # 第一个 TEXT_MESSAGE_CONTENT 可能只有几十字节，
                # 用 8KB 会让反代等满 8KB 才 flush → 客户端长时间
                # 看不到首字节。每次写完必须 flush，浏览器才能渲染。
                while True:
                    chunk = body_or_stream.read(256)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            else:
                # bytes body
                self.wfile.write(body_or_stream or b"")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            # Client gave up (e.g. navigated away mid-SSE). Nothing to do.
            pass

    # Override HTTP verbs to intercept /api/* before the static handler runs.
    def do_GET(self):       self._dispatch()
    def do_POST(self):      self._dispatch()
    def do_PUT(self):       self._dispatch()
    def do_DELETE(self):    self._dispatch()
    def do_PATCH(self):     self._dispatch()
    def do_OPTIONS(self):   self._dispatch()
    def do_HEAD(self):      self._dispatch()

    def _dispatch(self):
        if self._is_proxy_request():
            self._proxy_to_backend()
            return
        # Fall through to SimpleHTTPRequestHandler for static files.
        if self.command == "GET":
            super().do_GET()
        elif self.command == "HEAD":
            super().do_HEAD()
        else:
            # POST/PUT/... for non-/api paths: 405.
            self.send_error(405, "Method Not Allowed")

    def log_message(self, fmt, *args):
        sys.stderr.write("[frontend:9000] %s %s\n" % (self.address_string(), fmt % args))


def make_handler(directory, backend_url, backend_prefix):
    """Return a handler class bound to `directory` and the proxy target.

    We bind the path to a custom `serve_dir` attribute rather than the
    stdlib's `directory`: on Python 3.7+ the base __init__ overwrites
    `self.directory` with os.getcwd(), so a class-level `directory` would
    be ignored. `serve_dir` is read by our translate_path/_send_index.
    """
    return type(
        "SPAStaticHandler_%s" % abs(hash(directory)),
        (SPAStaticHandler,),
        {
            "serve_dir": directory,
            "backend_url": backend_url,
            "backend_prefix": backend_prefix,
        },
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dist", type=Path, default=DEFAULT_DIST,
                   help="Path to the built frontend (default: %s)" % DEFAULT_DIST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--host", default="0.0.0.0",
                   help="Bind address (default: 0.0.0.0 so it's reachable from outside)")
    p.add_argument("--backend-url", default=DEFAULT_BACKEND_URL,
                   help="Backend base URL to proxy /api/* to "
                        "(default: %s). Set to empty string to disable proxying." % DEFAULT_BACKEND_URL)
    p.add_argument("--backend-prefix", default=DEFAULT_BACKEND_PREFIX,
                   help="Path prefix that triggers the proxy "
                        "(default: %s). Set to empty string to disable." % DEFAULT_BACKEND_PREFIX)
    args = p.parse_args()

    dist = str(args.dist.resolve())
    if not os.path.isfile(os.path.join(dist, "index.html")):
        sys.stderr.write(
            "ERROR: %s/index.html not found.\n"
            "Build the frontend first: cd frontend && npm install && npm run build\n"
            "Or pass --dist to point at a pre-built directory.\n" % dist
        )
        return 2

    backend_url = args.backend_url.strip().rstrip("/") if args.backend_url else ""
    backend_prefix = args.backend_prefix.strip()
    if backend_url and backend_prefix and not backend_prefix.startswith("/"):
        backend_prefix = "/" + backend_prefix

    if backend_url and backend_prefix:
        sys.stdout.write("[frontend:9000] proxying %s/* -> %s\n"
                         % (backend_prefix, backend_url))
    else:
        sys.stdout.write("[frontend:9000] API proxy disabled "
                         "(backend_url=%r, backend_prefix=%r)\n"
                         % (backend_url, backend_prefix))

    sys.stdout.write("[frontend:9000] serving %s on http://%s:%d\n"
                     % (dist, args.host, args.port))
    sys.stdout.flush()

    handler_cls = make_handler(dist, backend_url, backend_prefix)

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    httpd = ThreadedHTTPServer((args.host, args.port), handler_cls)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\n[frontend:9000] shutting down\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())