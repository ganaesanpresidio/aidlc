"""HTTP-shaped handler for the policy unit. Works the same behind API Gateway, Lambda or the local server."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aidlc_common import log
from policy.errors import PolicyError
from policy.money import to_date
from policy.service import PolicyService


@dataclass
class Auth:
    kind: str  # "jwt" for signed-in users, "iam" for internal callers
    sub: str = ""
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


INTERNAL_CALLERS = {"submit", "approve"}
_VERSION = re.compile(r"^/v1/policy/rules/(\d+)$")


def _require_user(req: Request) -> Auth:
    if req.auth is None or req.auth.kind != "jwt" or not req.auth.sub:
        raise PolicyError(401, "UNAUTHENTICATED", "Sign in first")
    return req.auth


def _require_internal(req: Request) -> Auth:
    if req.auth is None:
        raise PolicyError(401, "UNAUTHENTICATED", "Internal call needs an IAM identity")
    if req.auth.kind != "iam" or req.auth.principal not in INTERNAL_CALLERS:
        raise PolicyError(403, "FORBIDDEN", "This route is internal")
    return req.auth


def _rules_body(record: dict[str, Any]) -> dict[str, Any]:
    return {k: record[k] for k in ("version", "effectiveFrom", "publishedAt", "rules") if k in record}


def handle(service: PolicyService, req: Request) -> Response:
    rid = req.headers.get("x-request-id", "")
    try:
        resp = _route(service, req)
    except PolicyError as exc:
        resp = Response(exc.status, exc.body())
    except Exception as exc:  # last resort: never leak internals
        log.error("unhandled error", unit="policy", request_id=rid, code=type(exc).__name__)
        resp = Response(500, {"code": "INTERNAL", "message": "Something went wrong"})
    if rid:
        resp.headers["x-request-id"] = rid
    return resp


def _route(service: PolicyService, req: Request) -> Response:
    path, method = req.path.rstrip("/") or "/", req.method.upper()
    if path == "/v1/policy/rules":
        if method == "GET":
            _require_user(req)
            on = to_date(req.query["effectiveOn"], "effectiveOn") if "effectiveOn" in req.query \
                else service._clock.today()
            return Response(200, _rules_body(service.rules_in_force(on)))
        if method == "PUT":
            user = _require_user(req)
            rec = service.publish(req.body, actor=user.sub, groups=user.groups,
                                  idempotency_key=req.headers.get("idempotency-key"))
            return Response(201, rec)
        return _not_allowed("GET, PUT")
    m = _VERSION.match(path)
    if m:
        if method != "GET":
            return _not_allowed("GET")
        _require_user(req)
        return Response(200, _rules_body(service.rules_by_version(int(m.group(1)))))
    if path == "/v1/policy/evaluate":
        if method != "POST":
            return _not_allowed("POST")
        _require_internal(req)
        return Response(200, service.evaluate(req.body))
    if path == "/v1/policy/route":
        if method != "POST":
            return _not_allowed("POST")
        _require_internal(req)
        return Response(200, service.route(req.body))
    raise PolicyError(404, "NOT_FOUND", "No such route")


def _not_allowed(allow: str) -> Response:
    return Response(405, {"code": "METHOD_NOT_ALLOWED", "message": f"Use {allow}"}, {"allow": allow})
