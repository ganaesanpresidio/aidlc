"""Local HTTP server for the policy unit. MOCK BACKEND ONLY: it trusts dev headers instead of a real JWT.

Run:  uv run aidlc-e2e serve policy
Dev headers: X-Dev-User, X-Dev-Groups (comma list), X-Dev-Internal (submit or approve).
"""

from __future__ import annotations

import json
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

from aidlc_common.backend import Backend, current_backend
from policy.api import Auth, Request, handle
from policy.service import PolicyService


class LocalServer(ThreadingHTTPServer):
    """Skips the reverse-DNS lookup HTTPServer does on bind, which can stall startup for 30 seconds."""

    daemon_threads = True

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[0], self.server_address[1]


def make_handler(service: PolicyService):
    class H(BaseHTTPRequestHandler):
        def _do(self) -> None:
            parts = urlsplit(self.path)
            headers = {k.lower(): v for k, v in self.headers.items()}
            body = None
            length = int(headers.get("content-length", "0") or 0)
            if length:
                try:
                    body = json.loads(self.rfile.read(length))
                except ValueError:
                    return self._send(400, {"code": "INVALID_JSON", "message": "Body is not valid JSON"})
            auth = None
            if headers.get("x-dev-internal"):
                auth = Auth(kind="iam", principal=headers["x-dev-internal"])
            elif headers.get("x-dev-user"):
                auth = Auth(kind="jwt", sub=headers["x-dev-user"],
                            groups=[g.strip() for g in headers.get("x-dev-groups", "").split(",") if g.strip()])
            resp = handle(service, Request(self.command, parts.path, dict(parse_qsl(parts.query)), headers, body, auth))
            self._send(resp.status, resp.body, resp.headers)

        def _send(self, status: int, body, extra: dict | None = None) -> None:
            data = json.dumps(body).encode() if body is not None else b""
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = do_PATCH = _do

        def log_message(self, *args) -> None:  # request lines can hold ids; keep the console quiet
            pass

    return H


def serve(service: PolicyService, host: str = "127.0.0.1", port: int = 8101) -> ThreadingHTTPServer:
    if current_backend() is not Backend.MOCK:
        raise RuntimeError("The local dev server trusts dev headers and runs only with AIDLC_BACKEND=mock")
    return LocalServer((host, port), make_handler(service))
