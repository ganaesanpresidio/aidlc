"""HTTP-shaped handler for the submit unit (same shape as the policy unit's)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aidlc_common import log
from submit.errors import SubmitError, not_found
from submit.service import Caller, ClaimService


@dataclass
class Auth:
    kind: str  # "jwt" for signed-in employees, "iam" for internal callers
    sub: str = ""
    grade: str = ""
    groups: list[str] = field(default_factory=list)
    principal: str = ""


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: Any = None
    auth: Auth | None = None


@dataclass
class Response:
    status: int
    body: Any = None
    headers: dict[str, str] = field(default_factory=dict)


_ID = r"([A-Za-z0-9]+)"
_ROUTES: list[tuple[re.Pattern, str]] = [(re.compile(f"^{p}$"), name) for p, name in [
    (r"/v1/claims", "claims"),
    (rf"/v1/claims/{_ID}", "claim"),
    (rf"/v1/claims/{_ID}/lines", "lines"),
    (rf"/v1/claims/{_ID}/lines/{_ID}", "line"),
    (rf"/v1/claims/{_ID}/lines/{_ID}/receipts", "receipts"),
    (rf"/v1/claims/{_ID}/lines/{_ID}/receipts/{_ID}", "receipt"),
    (rf"/v1/claims/{_ID}/lines/{_ID}/receipts/{_ID}/content", "content"),
    (rf"/v1/claims/{_ID}/submit", "submit"),
    (rf"/v1/claims/{_ID}/withdraw", "withdraw"),
    (rf"/internal/v1/receipts/{_ID}/access-url", "access"),
]]
_ALLOWED = {"claims": "GET, POST", "claim": "GET", "lines": "POST", "line": "PATCH, DELETE", "receipts": "POST",
            "receipt": "GET, DELETE", "content": "GET", "submit": "POST", "withdraw": "POST", "access": "POST"}
INTERNAL_CALLERS = {"approve"}


def _caller(req: Request) -> Caller:
    a = req.auth
    if a is None or a.kind != "jwt" or not a.sub:
        raise SubmitError(401, "UNAUTHENTICATED", "Sign in first")
    return Caller(sub=a.sub, grade=a.grade, groups=a.groups)


def handle(service: ClaimService, req: Request) -> Response:
    rid = req.headers.get("x-request-id", "")
    try:
        resp = _dispatch(service, req)
    except SubmitError as exc:
        resp = Response(exc.status, exc.body())
    except Exception as exc:
        log.error("unhandled error", unit="submit", request_id=rid, code=type(exc).__name__)
        resp = Response(500, {"code": "INTERNAL", "message": "Something went wrong"})
    if rid:
        resp.headers["x-request-id"] = rid
    return resp


def _dispatch(svc: ClaimService, req: Request) -> Response:
    path, method = req.path.rstrip("/") or "/", req.method.upper()
    for pattern, name in _ROUTES:
        m = pattern.match(path)
        if not m:
            continue
        if name == "access":
            return _access(svc, req, method, m.group(1))
        who = _caller(req)
        ids = m.groups()
        h = _HANDLERS[name].get(method)
        if h is None:
            return Response(405, {"code": "METHOD_NOT_ALLOWED", "message": f"Use {_ALLOWED[name]}"}, {"allow": _ALLOWED[name]})
        return h(svc, who, req, *ids)
    raise not_found("Route")


def _access(svc: ClaimService, req: Request, method: str, receipt_id: str) -> Response:
    if req.auth is None:
        raise SubmitError(401, "UNAUTHENTICATED", "Internal call needs an IAM identity")
    if req.auth.kind != "iam" or req.auth.principal not in INTERNAL_CALLERS:
        raise SubmitError(403, "FORBIDDEN", "This route is internal")
    if method != "POST":
        return Response(405, {"code": "METHOD_NOT_ALLOWED", "message": "Use POST"}, {"allow": "POST"})
    body = req.body if isinstance(req.body, dict) else {}
    if not isinstance(body.get("claimRef"), str) or not isinstance(body.get("requestedBy"), str) or not body["requestedBy"]:
        raise SubmitError(422, "INVALID_REQUEST", "claimRef and requestedBy are required")
    return Response(200, svc.receipt_access_url(receipt_id, body["claimRef"], body["requestedBy"]))


def _list(svc, who, req):
    q = req.query
    try:
        limit = int(q.get("limit", 20))
    except ValueError:
        raise SubmitError(422, "INVALID_REQUEST", "limit must be a whole number") from None
    return Response(200, svc.list_claims(who, q.get("status"), q.get("cursor"), limit))


def _content(svc, who, req, c, ln, r):
    return Response(302, None, {"location": svc.receipt_content_url(who, c, ln, r)})


_HANDLERS: dict[str, dict[str, Any]] = {
    "claims": {"POST": lambda s, w, r: Response(201, s.create_claim(w)), "GET": _list},
    "claim": {"GET": lambda s, w, r, c: Response(200, s.get_claim(w, c))},
    "lines": {"POST": lambda s, w, r, c: Response(201, s.add_line(w, c, r.body))},
    "line": {"PATCH": lambda s, w, r, c, ln: Response(200, s.update_line(w, c, ln, r.body)),
             "DELETE": lambda s, w, r, c, ln: (s.delete_line(w, c, ln), Response(204))[1]},
    "receipts": {"POST": lambda s, w, r, c, ln: Response(201, s.request_receipt_upload(w, c, ln, r.body))},
    "receipt": {"GET": lambda s, w, r, c, ln, x: Response(200, s.get_receipt(w, c, ln, x)),
                "DELETE": lambda s, w, r, c, ln, x: (s.delete_receipt(w, c, ln, x), Response(204))[1]},
    "content": {"GET": _content},
    "submit": {"POST": lambda s, w, r, c: Response(200, s.submit(w, c, r.headers.get("idempotency-key")))},
    "withdraw": {"POST": lambda s, w, r, c: Response(200, s.withdraw(w, c))},
}
