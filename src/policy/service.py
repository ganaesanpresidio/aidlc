"""PolicyService: read, evaluate, route and publish rules (lld.md sections 2 to 6)."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import date, timedelta
from typing import Any

from aidlc_common import log
from aidlc_common.clock import Clock, SystemClock
from aidlc_common.events import AuditLog, EventBus, ReliableBus, envelope
from policy.errors import NoRulesInForce, PolicyError, VersionExists
from policy.evaluate import evaluate_lines, parse_lines
from policy.money import to_date
from policy.route import parse_route_request, route_claim
from policy.rules import validate_rules
from policy.store import RulesStore

CACHE_TTL_SECONDS = 60
ADMIN_GROUP = "finance-admin"
IDEMPOTENCY_TTL = timedelta(hours=24)


class PolicyService:
    def __init__(self, store: RulesStore, bus: EventBus, clock: Clock | None = None,
                 cache_ttl: int = CACHE_TTL_SECONDS) -> None:
        self._store = store
        self._bus = ReliableBus(bus)
        self._clock = clock or SystemClock()
        self._audit = AuditLog(self._bus, self._clock)  # audit must not be lost if the bus is down
        self._ttl = cache_ttl
        self._by_version: dict[int, dict[str, Any]] = {}  # versions are immutable, safe to keep
        self._in_force: dict[str, tuple[float, dict[str, Any]]] = {}  # date -> (expires, record)

    # ---- reads -------------------------------------------------------------------------------

    def rules_in_force(self, on: date) -> dict[str, Any]:
        now = self._clock.now().timestamp()
        hit = self._in_force.get(on.isoformat())
        if hit and hit[0] > now:
            return copy.deepcopy(hit[1])
        record = self._store.in_force(on)
        if record is None:
            raise NoRulesInForce(on.isoformat())  # misses are not cached, so a new publish shows at once
        self._in_force[on.isoformat()] = (now + self._ttl, record)
        self._by_version[record["version"]] = record
        return copy.deepcopy(record)

    def rules_by_version(self, version: int) -> dict[str, Any]:
        if version not in self._by_version:
            record = self._store.get_version(version)
            if record is None:
                raise PolicyError(404, "NOT_FOUND", f"No rules version {version}")
            self._by_version[version] = record
        return copy.deepcopy(self._by_version[version])

    # ---- evaluate and route ----------------------------------------------------------------------

    def evaluate(self, body: Any) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise PolicyError(400, "INVALID_REQUEST", "body must be an object")
        submission = to_date(body.get("submissionDate"), "submissionDate")
        lines = parse_lines(body.get("lines"))
        record = self.rules_in_force(submission)
        rules = record["rules"]
        grade = body.get("grade")
        if grade not in rules["grades"]:
            raise PolicyError(400, "UNKNOWN_GRADE", f"grade must be one of {', '.join(rules['grades'])}")
        result = evaluate_lines(rules, grade, submission, lines)
        result["rulesVersion"] = record["version"]
        log.info("evaluate", unit="policy", action="evaluate", rules_version=record["version"],
                 count=len(result["violations"]), outcome="ok" if result["ok"] else "violations")
        return result

    def route(self, body: Any) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise PolicyError(400, "INVALID_REQUEST", "body must be an object")
        version = body.get("rulesVersion")
        if version is None:
            record = self.rules_in_force(self._clock.today())
        else:
            if isinstance(version, bool) or not isinstance(version, int) or version < 1:
                raise PolicyError(400, "INVALID_REQUEST", "rulesVersion must be a whole number of 1 or more")
            record = self.rules_by_version(version)
        req = parse_route_request(body, record["rules"]["grades"])
        result = route_claim(record["rules"], req)
        result["rulesVersion"] = record["version"]
        log.info("route", unit="policy", action="route", claim_ref=req["claimRef"],
                 rules_version=record["version"], code=result.get("blocked", {}).get("code", "ok"))
        return result

    # ---- publish ---------------------------------------------------------------------------------

    def publish(self, rules: Any, *, actor: str, groups: list[str], idempotency_key: str | None) -> dict[str, Any]:
        if ADMIN_GROUP not in groups:
            self._audit.record(actor=actor, action="policy.publish", outcome="denied")
            raise PolicyError(403, "FORBIDDEN", f"Publishing rules needs the {ADMIN_GROUP} group")
        if not isinstance(idempotency_key, str) or not 8 <= len(idempotency_key) <= 64:
            raise PolicyError(400, "INVALID_REQUEST", "Idempotency-Key header must be 8 to 64 characters")
        body_hash = hashlib.sha256(json.dumps(rules, sort_keys=True, default=str).encode()).hexdigest()

        now = self._clock.now()
        prior = self._store.get_idempotent(idempotency_key)
        if prior and prior["expiresAtEpoch"] > now.timestamp():
            if prior["bodyHash"] != body_hash:
                raise PolicyError(409, "IDEMPOTENCY_KEY_REUSED", "This key was used with different rules")
            return prior["result"]

        problems = validate_rules(rules)
        if problems:
            raise PolicyError(422, "INVALID_RULES", "Rules failed validation", problems)
        effective = to_date(rules["effective_from"], "effective_from")
        if effective < self._clock.today():
            raise PolicyError(422, "EFFECTIVE_DATE_IN_PAST", "effective_from cannot be before today")
        latest = self._store.latest()
        if latest and effective.isoformat() <= latest["effectiveFrom"]:
            raise PolicyError(409, "EFFECTIVE_DATE_NOT_AFTER_LATEST",
                              f"effective_from must be after {latest['effectiveFrom']} (version {latest['version']})")

        version = (latest["version"] if latest else 0) + 1
        doc = copy.deepcopy(rules)
        doc["version"] = version  # the stored version number always wins over the one in the file
        record = {
            "version": version, "effectiveFrom": effective.isoformat(),
            "publishedAt": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "publishedBy": actor,
            "checksum": hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest(), "rules": doc,
        }
        try:
            self._store.put_version(record)
        except VersionExists:
            raise PolicyError(409, "CONFLICT", "Another version was published at the same time. Retry") from None

        public = {k: record[k] for k in ("version", "effectiveFrom", "publishedAt", "rules")}
        self._store.put_idempotent(idempotency_key, {
            "bodyHash": body_hash, "result": public,
            "expiresAtEpoch": int((now + IDEMPOTENCY_TTL).timestamp())})
        self._bus.publish(envelope("PolicyRulesPublished", {"rulesVersion": version, "effectiveFrom": record["effectiveFrom"]},
                            include_claim_ref=False, clock=self._clock))
        self._audit.record(actor=actor, action="policy.publish", rules_version=version,
                           detail={"effectiveFrom": record["effectiveFrom"]})
        log.info("published", unit="policy", action="publish", rules_version=version)
        return public

    # ---- reliable events ---------------------------------------------------------------------------

    @property
    def pending_events(self) -> list[dict[str, Any]]:
        return self._bus.pending

    def flush_pending(self) -> int:
        """Retry events whose publish failed. Returns how many were sent."""
        return self._bus.flush()
