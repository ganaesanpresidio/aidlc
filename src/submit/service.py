"""ClaimService: all submit-unit behaviour (lld.md sections 2 to 6). No AWS imports: only interfaces."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from aidlc_common import log
from aidlc_common.clock import Clock, SystemClock, new_ulid
from aidlc_common.events import AuditLog, EventBus, ReliableBus, envelope
from submit import money
from submit.errors import ConditionFailed, PolicyRejected, PolicyUnavailable, SubmitError, not_found
from submit.objects import ALLOWED_MIME, MAX_BYTES, MockObjectStore, ObjectStore, sniff_mime
from submit.policy_client import PolicyClient
from submit.scanner import Scanner, Verdict
from submit.table import Item, Table

CATEGORIES = ("Travel", "Accommodation", "Meals", "Mileage", "Other")
DRAFT, SUBMITTED, APPROVED, REJECTED, WITHDRAWN, PAID = "Draft", "Submitted", "Approved", "Rejected", "Withdrawn", "Paid"
STATUSES = (DRAFT, SUBMITTED, APPROVED, REJECTED, WITHDRAWN, PAID)
MESSAGES = {
    "RECEIPT_REQUIRED": "Add a receipt",
    "LIMIT_EXCEEDED": "Amount is above the limit for your grade. Add a reason to request an exception",
    "WINDOW_EXPIRED": "This expense is too old to claim",
    "FUTURE_DATE_EXPENSE": "The expense date is in the future",
    "UNKNOWN_CATEGORY": "This category is not in the policy",
    "INVALID_QUANTITY": "Enter the number of nights, days or kilometres",
    "MISSING_INR_EQUIVALENT": "Enter the amount in INR",
}
_SHA = re.compile(r"^[A-Fa-f0-9]{64}$")
_KEY = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")


@dataclass
class Settings:
    retention_days: int = 365          # Q13, configurable (Q42)
    max_lines: int = 50
    max_receipts_per_line: int = 5     # PRD FR-3
    scan_timeout: timedelta = timedelta(minutes=5)
    upload_ttl: timedelta = timedelta(hours=1)
    idempotency_ttl: timedelta = timedelta(hours=24)


@dataclass
class Caller:
    sub: str
    grade: str = ""
    groups: list[str] = field(default_factory=list)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class ClaimService:
    def __init__(self, table: Table, objects: ObjectStore, scanner: Scanner, policy: PolicyClient, bus: EventBus,
                 clock: Clock | None = None, settings: Settings | None = None) -> None:
        self._t, self._objects, self._scanner, self._policy = table, objects, scanner, policy
        self._clock = clock or SystemClock()
        self._bus = ReliableBus(bus)
        self._audit = AuditLog(self._bus, self._clock)
        self.settings = settings or Settings()

    @property
    def pending_events(self) -> list[dict[str, Any]]:
        return self._bus.pending

    def flush_pending(self) -> int:
        return self._bus.flush()

    # ---- loading ---------------------------------------------------------------------------------------

    def _meta(self, claim_id: str, emp: str) -> Item:
        item = self._t.get(f"CLAIM#{claim_id}", "META") if isinstance(claim_id, str) and len(claim_id) == 26 else None
        if item is None or item["employeeId"] != emp:
            raise not_found()
        return item

    def _lines(self, claim_id: str) -> list[Item]:
        return self._t.query(f"CLAIM#{claim_id}", "LINE#")

    def _receipts(self, claim_id: str) -> list[Item]:
        return self._t.query(f"CLAIM#{claim_id}", "RCPT#")

    def _editable(self, meta: Item) -> None:
        if meta["status"] != DRAFT:
            raise SubmitError(409, "CLAIM_NOT_EDITABLE", "A submitted claim cannot be changed")

    def _mutate(self, meta: Item, ops: list[dict[str, Any]]) -> Item:
        """Apply writes and bump the claim version together, so a submit that read the old version fails."""
        new = dict(meta, version=meta["version"] + 1, updatedAt=_iso(self._clock.now()))
        try:
            self._t.transact(ops + [{"put": new, "if_version": meta["version"]}])
        except ConditionFailed:
            raise SubmitError(409, "CONFLICT", "The claim changed at the same time. Reload and retry") from None
        return new

    # ---- claims ----------------------------------------------------------------------------------------

    def create_claim(self, who: Caller) -> dict[str, Any]:
        if not who.grade:
            raise SubmitError(403, "NO_GRADE", "Your sign-in has no grade, so a claim cannot be created")
        now, claim_id = self._clock.now(), new_ulid(self._clock)
        meta = {"PK": f"CLAIM#{claim_id}", "SK": "META", "claimId": claim_id, "employeeId": who.sub, "grade": who.grade,
                "status": DRAFT, "createdAt": _iso(now), "updatedAt": _iso(now), "version": 1,
                "gsi1pk": f"EMP#{who.sub}", "gsi1sk": f"{_iso(now)}#{claim_id}"}
        self._t.put(meta, if_absent=True)
        self._audit.record(actor=who.sub, action="claim.create", ref=None, detail={"claimId": claim_id})
        return self._view(meta)

    def get_claim(self, who: Caller, claim_id: str) -> dict[str, Any]:
        return self._view(self._meta(claim_id, who.sub))

    def list_claims(self, who: Caller, status: str | None = None, cursor: str | None = None,
                    limit: int = 20) -> dict[str, Any]:
        if status is not None and status not in STATUSES:
            raise money.bad("status", f"must be one of {', '.join(STATUSES)}")
        if not 1 <= limit <= 100:
            raise money.bad("limit", "must be 1 to 100")
        rows = self._t.query_index(1, f"EMP#{who.sub}", descending=True)
        if status:
            rows = [r for r in rows if r["status"] == status]
        if cursor:
            rows = [r for r in rows if r["gsi1sk"] < cursor]
        page = rows[:limit]
        out: dict[str, Any] = {"items": [self._view(r, with_lines=False) for r in page]}
        if len(rows) > limit:
            out["nextCursor"] = page[-1]["gsi1sk"]
        return out

    # ---- lines -----------------------------------------------------------------------------------------

    def _clean_line(self, data: Any, base: Item | None = None) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise money.bad("body", "must be an object")
        merged = {**({} if base is None else {k: base.get(k) for k in (
            "expenseDate", "category", "amount", "currency", "amountInr", "quantity", "description", "exceptionReason")}),
            **data}
        d = money.day(merged.get("expenseDate"), "expenseDate")
        category = merged.get("category")
        if category not in CATEGORIES:
            raise money.bad("category", f"must be one of {', '.join(CATEGORIES)}")
        amt = money.amount(merged.get("amount"), "amount")
        currency = merged.get("currency") or "INR"
        if not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency):
            raise money.bad("currency", "must be a 3-letter code like INR")
        amount_inr = None
        if currency != "INR":
            if merged.get("amountInr") is None:
                raise money.bad("amountInr", "is needed when the currency is not INR")
            amount_inr = money.amount(merged["amountInr"], "amountInr")
        desc = merged.get("description")
        if not isinstance(desc, str) or not desc.strip():
            raise money.bad("description", "is required")
        if len(desc.strip()) > 500:
            raise money.bad("description", "must be 500 characters or fewer")
        reason = merged.get("exceptionReason")
        if reason is not None and (not isinstance(reason, str) or len(reason) > 500):
            raise money.bad("exceptionReason", "must be text of 500 characters or fewer")
        qty = None if merged.get("quantity") is None else money.quantity(merged["quantity"], "quantity")
        return {"expenseDate": d.isoformat(), "category": category, "amount": str(amt), "currency": currency,
                "amountInr": None if amount_inr is None else str(amount_inr), "description": desc.strip(),
                "exceptionReason": (reason or "").strip() or None, "quantity": None if qty is None else str(qty)}

    def add_line(self, who: Caller, claim_id: str, data: Any) -> dict[str, Any]:
        meta = self._meta(claim_id, who.sub)
        self._editable(meta)
        if len(self._lines(claim_id)) >= self.settings.max_lines:
            raise SubmitError(422, "LINE_LIMIT", f"A claim can have at most {self.settings.max_lines} lines")
        clean = self._clean_line(data)
        line_id = new_ulid(self._clock)
        item = {"PK": f"CLAIM#{claim_id}", "SK": f"LINE#{line_id}", "lineId": line_id, **clean}
        self._mutate(meta, [{"put": item, "if_absent": True}])
        self._audit.record(actor=who.sub, action="line.add", detail={"claimId": claim_id, "lineId": line_id})
        return self._line_view(item, [])

    def update_line(self, who: Caller, claim_id: str, line_id: str, data: Any) -> dict[str, Any]:
        meta = self._meta(claim_id, who.sub)
        self._editable(meta)
        current = self._t.get(f"CLAIM#{claim_id}", f"LINE#{line_id}")
        if current is None:
            raise not_found("Line")
        item = {**current, **self._clean_line(data, current)}
        self._mutate(meta, [{"put": item}])
        self._audit.record(actor=who.sub, action="line.update", detail={"claimId": claim_id, "lineId": line_id})
        return self._line_view(item, self._receipts_for_line(claim_id, line_id))

    def delete_line(self, who: Caller, claim_id: str, line_id: str) -> None:
        meta = self._meta(claim_id, who.sub)
        self._editable(meta)
        if self._t.get(f"CLAIM#{claim_id}", f"LINE#{line_id}") is None:
            raise not_found("Line")
        ops: list[dict[str, Any]] = [{"delete": (f"CLAIM#{claim_id}", f"LINE#{line_id}")}]
        receipts = self._receipts_for_line(claim_id, line_id)
        for r in receipts:
            ops += self._receipt_delete_ops(meta, r)
        self._mutate(meta, ops)
        for r in receipts:
            self._remove_files(r)
        self._audit.record(actor=who.sub, action="line.delete", detail={"claimId": claim_id, "lineId": line_id})

    # ---- receipts --------------------------------------------------------------------------------------

    def _receipts_for_line(self, claim_id: str, line_id: str) -> list[Item]:
        return [r for r in self._receipts(claim_id) if r["lineId"] == line_id]

    def _live(self, r: Item) -> bool:
        return r["status"] not in ("REJECTED", "EXPIRED")

    def request_receipt_upload(self, who: Caller, claim_id: str, line_id: str, data: Any) -> dict[str, Any]:
        meta = self._meta(claim_id, who.sub)
        self._editable(meta)
        if self._t.get(f"CLAIM#{claim_id}", f"LINE#{line_id}") is None:
            raise not_found("Line")
        if not isinstance(data, dict):
            raise money.bad("body", "must be an object")
        mime, size, sha = data.get("mimeType"), data.get("sizeBytes"), data.get("sha256")
        if mime not in ALLOWED_MIME:
            raise SubmitError(422, "FILE_TYPE_NOT_ALLOWED", "Use JPEG, PNG, HEIC or PDF")
        if isinstance(size, bool) or not isinstance(size, int) or size < 1:
            raise money.bad("sizeBytes", "must be a whole number of 1 or more")
        if size > MAX_BYTES:
            raise SubmitError(422, "FILE_TOO_LARGE", "Files can be at most 10 MB")
        if not isinstance(sha, str) or not _SHA.match(sha):
            raise money.bad("sha256", "must be 64 hex characters")
        live = [r for r in self._receipts_for_line(claim_id, line_id) if self._live(r)]
        if len(live) >= self.settings.max_receipts_per_line:
            raise SubmitError(422, "RECEIPT_LIMIT", f"A line can have at most {self.settings.max_receipts_per_line} receipts")

        receipt_id, now = new_ulid(self._clock), self._clock.now()
        key = f"{claim_id}/{receipt_id}"
        item = {"PK": f"CLAIM#{claim_id}", "SK": f"RCPT#{receipt_id}", "receiptId": receipt_id, "claimId": claim_id,
                "lineId": line_id, "objectKey": key, "mimeType": mime, "sizeBytes": size, "sha256": sha.lower(),
                "status": "PENDING_UPLOAD", "statusSince": _iso(now), "gsi3pk": "WAIT#PENDING_UPLOAD",
                "gsi3sk": f"{_iso(now)}#{receipt_id}"}
        slot = self._objects.create_upload_slot(key, mime, MAX_BYTES, sha.lower())
        self._mutate(meta, [{"put": item, "if_absent": True}])
        self._audit.record(actor=who.sub, action="receipt.request", detail={"claimId": claim_id, "receiptId": receipt_id})
        return {"receiptId": receipt_id, "uploadUrl": slot.url, "fields": slot.fields, "expiresInSeconds": slot.expires_in}

    def _set_receipt(self, meta: Item, r: Item, **changes: Any) -> Item:
        new = {**r, **changes}
        self._mutate(meta, [{"put": new}])
        return new

    def _meta_by_id(self, claim_id: str) -> Item:
        item = self._t.get(f"CLAIM#{claim_id}", "META")
        if item is None:
            raise not_found()
        return item

    def handle_upload_event(self, claim_id: str, receipt_id: str) -> None:
        """S3 says an object arrived in quarantine: the receipt is now being scanned."""
        r = self._t.get(f"CLAIM#{claim_id}", f"RCPT#{receipt_id}")
        if r is None or r["status"] != "PENDING_UPLOAD" or not self._objects.exists(MockObjectStore.QUARANTINE, r["objectKey"]):
            return
        now = _iso(self._clock.now())
        self._set_receipt(self._meta_by_id(claim_id), r, status="SCANNING", statusSince=now,
                          gsi3pk="WAIT#SCANNING", gsi3sk=f"{now}#{receipt_id}")

    def handle_scan_result(self, claim_id: str, receipt_id: str) -> str:
        """Act on the scanner's verdict. Safe to call again: it only acts on receipts that are being scanned."""
        r = self._t.get(f"CLAIM#{claim_id}", f"RCPT#{receipt_id}")
        if r is None or r["status"] != "SCANNING":
            return r["status"] if r else "MISSING"
        meta = self._meta_by_id(claim_id)
        verdict = self._scanner.verdict(r["objectKey"])
        if verdict is Verdict.PENDING:
            return "SCANNING"
        if verdict is Verdict.INFECTED:
            self._reject(meta, r, "MALWARE", security=True)
            return "REJECTED"
        if verdict is Verdict.FAILED:
            self._reject(meta, r, "SCAN_FAILED")
            return "REJECTED"
        if sniff_mime(self._objects.head_bytes(MockObjectStore.QUARANTINE, r["objectKey"])) != r["mimeType"]:
            self._reject(meta, r, "BAD_TYPE")
            return "REJECTED"
        self._objects.move_to_clean(r["objectKey"], r["objectKey"])
        now = self._clock.now()
        expires = (now.date() + timedelta(days=self.settings.retention_days)).isoformat()
        stored = {k: v for k, v in r.items() if k not in ("gsi3pk", "gsi3sk")}
        stored.update(status="CLEAN", statusSince=_iso(now), expiresOn=expires, gsi2pk="EXPIRY",
                      gsi2sk=f"{expires}#{receipt_id}")
        dup = {"PK": f"DUP#{meta['employeeId']}#{r['sha256']}", "SK": f"{claim_id}#{receipt_id}",
               "claimId": claim_id, "receiptId": receipt_id}
        self._mutate(meta, [{"put": stored}, {"put": dup}])
        self._emit_receipt_stored(meta, stored)
        self._audit.record(actor=meta["employeeId"], action="receipt.stored", ref=meta.get("claimRef"),
                           detail={"claimId": claim_id, "receiptId": receipt_id})
        return "CLEAN"

    def _reject(self, meta: Item, r: Item, reason: str, security: bool = False) -> None:
        self._objects.delete(MockObjectStore.QUARANTINE, r["objectKey"])
        self._set_receipt(meta, {k: v for k, v in r.items() if k not in ("gsi3pk", "gsi3sk")}, status="REJECTED",
                          statusSince=_iso(self._clock.now()), rejectReason=reason)
        self._audit.record(actor=meta["employeeId"], action="receipt.malware" if security else "receipt.reject",
                           ref=meta.get("claimRef"), outcome="blocked",
                           detail={"claimId": meta["claimId"], "receiptId": r["receiptId"], "reason": reason})

    def _emit_receipt_stored(self, meta: Item, r: Item) -> None:
        self._bus.publish(envelope("ReceiptStored", {
            "receiptId": r["receiptId"], "claimId": meta["claimId"], "lineId": r["lineId"],
            "mimeType": r["mimeType"], "sizeBytes": r["sizeBytes"]},
            claim_ref=meta.get("claimRef"), rules_version=meta.get("rulesVersion"), clock=self._clock))

    def get_receipt(self, who: Caller, claim_id: str, line_id: str, receipt_id: str) -> dict[str, Any]:
        meta = self._meta(claim_id, who.sub)
        r = self._t.get(f"CLAIM#{claim_id}", f"RCPT#{receipt_id}")
        if r is None or r["lineId"] != line_id:
            raise not_found("Receipt")
        return self._receipt_view(meta, r)

    def _receipt_delete_ops(self, meta: Item, r: Item) -> list[dict[str, Any]]:
        ops: list[dict[str, Any]] = [{"delete": (r["PK"], r["SK"])}]
        if r["status"] == "CLEAN":
            ops.append({"delete": (f"DUP#{meta['employeeId']}#{r['sha256']}", f"{meta['claimId']}#{r['receiptId']}")})
        return ops

    def _remove_files(self, r: Item) -> None:
        self._objects.delete(MockObjectStore.QUARANTINE, r["objectKey"])
        self._objects.delete(MockObjectStore.CLEAN, r["objectKey"])

    def delete_receipt(self, who: Caller, claim_id: str, line_id: str, receipt_id: str) -> None:
        meta = self._meta(claim_id, who.sub)
        self._editable(meta)
        r = self._t.get(f"CLAIM#{claim_id}", f"RCPT#{receipt_id}")
        if r is None or r["lineId"] != line_id:
            raise not_found("Receipt")
        self._mutate(meta, self._receipt_delete_ops(meta, r))
        self._remove_files(r)
        self._audit.record(actor=who.sub, action="receipt.delete", detail={"claimId": claim_id, "receiptId": receipt_id})

    def receipt_content_url(self, who: Caller, claim_id: str, line_id: str, receipt_id: str) -> str:
        meta = self._meta(claim_id, who.sub)
        r = self._t.get(f"CLAIM#{claim_id}", f"RCPT#{receipt_id}")
        if r is None or r["lineId"] != line_id:
            raise not_found("Receipt")
        if r["status"] != "CLEAN":
            raise SubmitError(409, "RECEIPT_NOT_READY", "This receipt is not available")
        self._audit.record(actor=who.sub, action="receipt.view", ref=meta.get("claimRef"), detail={"receiptId": receipt_id})
        return self._objects.signed_url(r["objectKey"], 60)

    def receipt_access_url(self, receipt_id: str, claim_ref: str, requested_by: str) -> dict[str, Any]:
        """For `approve`, which has already checked that requested_by is assigned to this claim (Q43)."""
        ref = self._t.get(f"REF#{claim_ref}", "META") if isinstance(claim_ref, str) else None
        if ref is None:
            raise not_found()
        r = self._t.get(f"CLAIM#{ref['claimId']}", f"RCPT#{receipt_id}")
        meta = self._meta_by_id(ref["claimId"])
        if r is None or meta["status"] == DRAFT:
            raise not_found("Receipt")
        if r["status"] != "CLEAN":
            raise SubmitError(409, "RECEIPT_NOT_READY", "This receipt is not available")
        self._audit.record(actor=requested_by, action="receipt.access", ref=claim_ref, detail={"receiptId": receipt_id})
        return {"url": self._objects.signed_url(r["objectKey"], 60), "expiresInSeconds": 60}

    # ---- submit ----------------------------------------------------------------------------------------

    def submit(self, who: Caller, claim_id: str, idempotency_key: str | None) -> dict[str, Any]:
        if not isinstance(idempotency_key, str) or not _KEY.match(idempotency_key):
            raise money.bad("Idempotency-Key", "must be 8 to 64 letters, digits or . _ : -")
        meta = self._meta(claim_id, who.sub)
        idem = self._t.get(f"IDEM#{claim_id}#{idempotency_key}", "META")
        if idem and idem["expiresAt"] > _iso(self._clock.now()):
            return self._view(self._meta(claim_id, who.sub))  # same key again: same answer, no new event
        self._editable(meta)

        lines, receipts = self._lines(claim_id), self._receipts(claim_id)
        if not lines:
            raise SubmitError(422, "NO_LINES", "Add at least one expense line before submitting")
        if any(r["status"] in ("PENDING_UPLOAD", "SCANNING") for r in receipts):
            raise SubmitError(422, "RECEIPT_STILL_CHECKING", "Receipt still being checked. Try again in a moment")

        clean_by_line: dict[str, int] = {}
        for r in receipts:
            if r["status"] == "CLEAN":
                clean_by_line[r["lineId"]] = clean_by_line.get(r["lineId"], 0) + 1
        today = self._clock.today()
        result = self._evaluate(meta, lines, clean_by_line, today)
        if not result["ok"]:
            details = [{"lineId": v["lineId"], "code": v["code"], "message": MESSAGES.get(v["code"], v["code"])}
                       for v in result["violations"]]
            raise SubmitError(422, "POLICY_VIOLATIONS", "Fix the lines below, then submit again", details)

        total_inr = sum((Decimal(ln["amount"] if ln["currency"] == "INR" else ln["amountInr"]) for ln in lines), Decimal(0))
        by_currency: dict[str, Decimal] = {}
        for ln in lines:
            by_currency[ln["currency"]] = by_currency.get(ln["currency"], Decimal(0)) + Decimal(ln["amount"])
        n = self._t.increment(f"COUNTER#CLM#{today.year}", "META", "n")
        ref = f"CLM-{today.year}-{n:06d}"
        now = self._clock.now()
        new = dict(meta, status=SUBMITTED, claimRef=ref, submittedAt=_iso(now), updatedAt=_iso(now),
                   rulesVersion=result["rulesVersion"], totalInr=str(total_inr),
                   totalsByCurrency={c: str(v) for c, v in by_currency.items()},
                   requiresException=result["requiresException"], version=meta["version"] + 1)
        try:
            self._t.transact([
                {"put": new, "if_version": meta["version"]},
                {"put": {"PK": f"REF#{ref}", "SK": "META", "claimId": claim_id}, "if_absent": True},
                {"put": {"PK": f"IDEM#{claim_id}#{idempotency_key}", "SK": "META",
                         "expiresAt": _iso(now + self.settings.idempotency_ttl)}},
            ])
        except ConditionFailed:
            raise SubmitError(409, "CONFLICT", "The claim changed at the same time. Reload and retry") from None
        self._bus.publish(envelope("ClaimSubmitted", {
            "submitterId": who.sub, "gradeOfSubmitter": meta["grade"], "totalInr": money.out(total_inr),
            "lineCount": len(lines), "requiresException": result["requiresException"]},
            claim_ref=ref, rules_version=result["rulesVersion"], clock=self._clock))
        self._audit.record(actor=who.sub, action="claim.submit", ref=ref, rules_version=result["rulesVersion"],
                           detail={"claimId": claim_id, "lines": len(lines)})
        log.info("submitted", unit="submit", action="submit", claim_ref=ref, rules_version=result["rulesVersion"], count=len(lines))
        return self._view(new)

    def _evaluate(self, meta: Item, lines: list[Item], clean_by_line: dict[str, int], today: date) -> dict[str, Any]:
        body = {"grade": meta["grade"], "submissionDate": today.isoformat(), "lines": [
            {k: v for k, v in {
                "lineId": ln["lineId"], "category": ln["category"], "amount": money.out(ln["amount"]),
                "currency": ln["currency"], "amountInr": money.out(ln.get("amountInr")), "expenseDate": ln["expenseDate"],
                "quantity": money.out(ln.get("quantity")), "hasReceipt": clean_by_line.get(ln["lineId"], 0) > 0,
                "exceptionReason": ln.get("exceptionReason")}.items() if v is not None} for ln in lines]}
        try:
            return self._policy.evaluate(body)
        except PolicyUnavailable:
            raise SubmitError(503, "POLICY_UNAVAILABLE", "Policy checks are unavailable. Nothing was submitted. Try again") from None
        except PolicyRejected as exc:
            raise SubmitError(422, "POLICY_REJECTED_REQUEST", f"Policy could not check this claim ({exc.code})") from None

    # ---- withdraw and later states -----------------------------------------------------------------------

    def withdraw(self, who: Caller, claim_id: str) -> dict[str, Any]:
        meta = self._meta(claim_id, who.sub)
        if meta["status"] != SUBMITTED:
            raise SubmitError(409, "CANNOT_WITHDRAW", f"A claim that is {meta['status']} cannot be withdrawn")
        new = dict(meta, status=WITHDRAWN, updatedAt=_iso(self._clock.now()), version=meta["version"] + 1)
        try:
            self._t.put(new, if_version=meta["version"])
        except ConditionFailed:
            raise SubmitError(409, "CONFLICT", "The claim changed at the same time. Reload and retry") from None
        self._bus.publish(envelope("ClaimWithdrawn", {}, claim_ref=meta["claimRef"],
                                   rules_version=meta.get("rulesVersion"), clock=self._clock))
        self._audit.record(actor=who.sub, action="claim.withdraw", ref=meta["claimRef"])
        return self._view(new)

    _TRANSITIONS = {"ClaimApproved": (SUBMITTED, APPROVED), "ClaimRejected": (SUBMITTED, REJECTED),
                    "PayoutIssued": (APPROVED, PAID)}

    def on_event(self, event: dict[str, Any]) -> bool:
        """Show the employee how their claim moved on. Out-of-order or repeated events are ignored."""
        rule = self._TRANSITIONS.get(event.get("event"))
        ref = self._t.get(f"REF#{event.get('claimRef')}", "META") if rule and event.get("claimRef") else None
        if rule is None or ref is None:
            return False
        meta = self._meta_by_id(ref["claimId"])
        if meta["status"] != rule[0]:
            self._audit.record(actor="system", action="claim.status", ref=event["claimRef"], outcome="ignored",
                               detail={"event": event["event"], "status": meta["status"]})
            return False
        try:
            self._t.put(dict(meta, status=rule[1], updatedAt=_iso(self._clock.now()), version=meta["version"] + 1),
                        if_version=meta["version"])
        except ConditionFailed:
            return self.on_event(event)  # someone else changed it first: look again
        self._audit.record(actor="system", action="claim.status", ref=event["claimRef"], detail={"to": rule[1]})
        return True

    # ---- housekeeping jobs ------------------------------------------------------------------------------

    def sweep_stuck_receipts(self) -> dict[str, int]:
        """Scans that never finish and uploads that never happened (lld.md section 6)."""
        now = self._clock.now()
        stats = {"scan_timeout": 0, "upload_expired": 0}
        for r in self._t.query_index(3, "WAIT#SCANNING", sk_lte=f"{_iso(now - self.settings.scan_timeout)}#~"):
            if self._guarded("sweep", r, lambda r=r: self._reject(self._meta_by_id(r["claimId"]), r, "SCAN_TIMEOUT")):
                stats["scan_timeout"] += 1
        for r in self._t.query_index(3, "WAIT#PENDING_UPLOAD", sk_lte=f"{_iso(now - self.settings.upload_ttl)}#~"):
            if self._guarded("sweep", r, lambda r=r: self._drop_pending(r)):
                stats["upload_expired"] += 1
        return stats

    def _drop_pending(self, r: Item) -> None:
        self._mutate(self._meta_by_id(r["claimId"]), [{"delete": (r["PK"], r["SK"])}])
        self._remove_files(r)

    def _guarded(self, job: str, r: Item, action) -> bool:
        """Run one item of a batch job. A bad item is logged and skipped, so it cannot stop the rest."""
        try:
            action()
            return True
        except (SubmitError, ConditionFailed, KeyError) as exc:
            log.error("job item skipped", unit="submit", action=job, receipt_id=r.get("receiptId"),
                      claim_id=r.get("claimId"), code=type(exc).__name__)
            return False

    def expire_receipts(self, today: date | None = None) -> int:
        """Delete receipts whose retention ended. Catches up on missed days. Safe to run twice (US-006)."""
        today = today or self._clock.today()
        due = self._t.query_index(2, "EXPIRY", sk_lte=f"{today.isoformat()}#~")
        by_claim: dict[str, list[Item]] = {}
        for r in due:
            by_claim.setdefault(r["claimId"], []).append(r)
        expired: list[str] = []
        for claim_id, rs in by_claim.items():
            if self._guarded("expire", rs[0], lambda c=claim_id, rs=rs: self._expire_claim(c, rs)):
                expired += [r["receiptId"] for r in rs]
        return len(expired)

    def _expire_claim(self, claim_id: str, rs: list[Item]) -> None:
        meta = self._meta_by_id(claim_id)
        ops: list[dict[str, Any]] = []
        for r in rs:
            gone = {k: v for k, v in r.items() if k not in ("gsi2pk", "gsi2sk")}
            gone.update(status="EXPIRED", statusSince=_iso(self._clock.now()))
            ops += [{"put": gone}, {"delete": (f"DUP#{meta['employeeId']}#{r['sha256']}", f"{claim_id}#{r['receiptId']}")}]
        self._mutate(meta, ops)
        for r in rs:
            self._remove_files(r)
            self._audit.record(actor="system", action="receipt.expire", ref=meta.get("claimRef"),
                               detail={"claimId": claim_id, "receiptId": r["receiptId"]})
        self._bus.publish(envelope("ReceiptsExpired", {
            "receiptIds": [r["receiptId"] for r in rs], "retentionDays": self.settings.retention_days},
            claim_ref=meta.get("claimRef"), clock=self._clock))

    # ---- views -----------------------------------------------------------------------------------------

    def _duplicate_of(self, meta: Item, r: Item) -> str | None:
        if r["status"] != "CLEAN":
            return None
        for d in self._t.query(f"DUP#{meta['employeeId']}#{r['sha256']}"):
            if d["claimId"] != meta["claimId"]:
                other = self._t.get(f"CLAIM#{d['claimId']}", "META")
                if other:
                    return other.get("claimRef") or other["claimId"]
        return None

    def _receipt_view(self, meta: Item, r: Item) -> dict[str, Any]:
        out = {"receiptId": r["receiptId"], "status": r["status"], "mimeType": r["mimeType"], "sizeBytes": r["sizeBytes"]}
        if r.get("rejectReason"):
            out["rejectReason"] = r["rejectReason"]
        dup = self._duplicate_of(meta, r)
        if dup:
            out["duplicateOf"] = dup
        return out

    def _line_view(self, ln: Item, receipts: list[dict[str, Any]]) -> dict[str, Any]:
        out = {"lineId": ln["lineId"], "expenseDate": ln["expenseDate"], "category": ln["category"],
               "amount": money.out(ln["amount"]), "currency": ln["currency"], "description": ln["description"],
               "receipts": receipts}
        for k in ("amountInr", "quantity"):
            if ln.get(k) is not None:
                out[k] = money.out(ln[k])
        if ln.get("exceptionReason"):
            out["exceptionReason"] = ln["exceptionReason"]
        return out

    def _view(self, meta: Item, with_lines: bool = True) -> dict[str, Any]:
        out: dict[str, Any] = {"claimId": meta["claimId"], "status": meta["status"], "createdAt": meta["createdAt"]}
        for k in ("claimRef", "submittedAt"):
            if meta.get(k):
                out[k] = meta[k]
        lines = self._lines(meta["claimId"])
        totals: dict[str, Decimal] = {}
        for ln in lines:
            totals[ln["currency"]] = totals.get(ln["currency"], Decimal(0)) + Decimal(ln["amount"])
        out["totalsByCurrency"] = {c: money.out(v) for c, v in totals.items()}
        if meta.get("totalInr") is not None:
            out["totalInr"] = money.out(meta["totalInr"])
        if with_lines:
            receipts = self._receipts(meta["claimId"])
            out["lines"] = [self._line_view(ln, [self._receipt_view(meta, r) for r in receipts if r["lineId"] == ln["lineId"]])
                            for ln in lines]
        else:
            out["lines"] = []
        return out
