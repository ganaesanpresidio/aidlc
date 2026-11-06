"""Local HTTP server for the submit unit. MOCK BACKEND ONLY: it trusts dev headers instead of a real JWT.

Run:  uv run aidlc-e2e serve submit      then open http://127.0.0.1:8102/ for the test page (web/expense-submit.html)
Dev headers: X-Dev-User, X-Dev-Grade, X-Dev-Groups, X-Dev-Internal (approve).
Extra dev routes stand in for the browser upload and the S3/GuardDuty events:
  POST /dev/uploads/{claimId}/{receiptId}   {"contentBase64": "...", "contentType": "image/png"}
  POST /dev/jobs/sweep      POST /dev/jobs/expire
"""

from __future__ import annotations

import base64
import binascii
import json
import socketserver
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from aidlc_common.backend import Backend, current_backend
from submit.api import Auth, Request, handle
from submit.factory import MockStack
from submit.objects import UploadRejected


class LocalServer(ThreadingHTTPServer):
    """Skips the reverse-DNS lookup HTTPServer does on bind, which can stall startup for 30 seconds."""

    daemon_threads = True

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[0], self.server_address[1]


UI_PAGE = Path(__file__).resolve().parents[2] / "web" / "expense-submit.html"


def dev_upload(stack: MockStack, claim_id: str, receipt_id: str, body: dict) -> tuple[int, dict]:
    """What the browser and AWS do after the slot is issued: POST the file, then the scan runs."""
    r = stack.table.get(f"CLAIM#{claim_id}", f"RCPT#{receipt_id}")
    if r is None:
        return 404, {"code": "NOT_FOUND", "message": "No such receipt"}
    try:
        content = base64.b64decode(body["contentBase64"], validate=True)
        stack.objects.post({"key": r["objectKey"], "token": _token(stack, r)}, content, body["contentType"])
    except (KeyError, TypeError, binascii.Error):
        return 400, {"code": "INVALID_REQUEST", "message": "contentBase64 and contentType are required"}
    except UploadRejected as exc:
        return 403, {"code": "UPLOAD_REJECTED", "message": str(exc)}
    stack.service.handle_upload_event(claim_id, receipt_id)
    return 200, {"status": stack.service.handle_scan_result(claim_id, receipt_id)}


def _token(stack: MockStack, r: dict) -> str:
    import hashlib
    return hashlib.sha256(f"{r['objectKey']}{r['sha256']}".encode()).hexdigest()[:16]


def make_handler(stack: MockStack):
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
            if self.command == "GET" and parts.path in ("/", "/ui") and UI_PAGE.is_file():
                data = UI_PAGE.read_bytes()
                self.send_response(200)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(data)))
                self.send_header("cache-control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            segs = parts.path.strip("/").split("/")
            if segs[0] == "dev" and self.command == "POST":
                if segs[1:2] == ["uploads"] and len(segs) == 4:
                    return self._send(*dev_upload(stack, segs[2], segs[3], body or {}))
                if segs[1:3] == ["jobs", "sweep"]:
                    return self._send(200, stack.service.sweep_stuck_receipts())
                if segs[1:3] == ["jobs", "expire"]:
                    return self._send(200, {"expired": stack.service.expire_receipts()})
            auth = None
            if headers.get("x-dev-internal"):
                auth = Auth(kind="iam", principal=headers["x-dev-internal"])
            elif headers.get("x-dev-user"):
                auth = Auth(kind="jwt", sub=headers["x-dev-user"], grade=headers.get("x-dev-grade", ""),
                            groups=[g.strip() for g in headers.get("x-dev-groups", "").split(",") if g.strip()])
            resp = handle(stack.service, Request(self.command, parts.path, dict(parse_qsl(parts.query)), headers, body, auth))
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

        def log_message(self, *args) -> None:
            pass

    return H


def serve(stack: MockStack, host: str = "127.0.0.1", port: int = 8102) -> ThreadingHTTPServer:
    if current_backend() is not Backend.MOCK:
        raise RuntimeError("The local dev server trusts dev headers and runs only with AIDLC_BACKEND=mock")
    return LocalServer((host, port), make_handler(stack))
