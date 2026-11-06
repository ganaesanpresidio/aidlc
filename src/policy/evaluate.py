"""Check expense lines against limits, receipt rule, submission window. Pure: no storage, no clock."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from policy.errors import PolicyError
from policy.money import check_currency, plain, to_date, to_decimal

PER_QUANTITY_UNITS = {"per_night", "per_day", "per_km"}


def parse_lines(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise PolicyError(400, "INVALID_REQUEST", "lines must be a non-empty list")
    seen: set[str] = set()
    lines = []
    for i, ln in enumerate(raw):
        where = f"lines[{i}]"
        if not isinstance(ln, dict):
            raise PolicyError(400, "INVALID_REQUEST", f"{where} must be an object")
        line_id = ln.get("lineId")
        if not isinstance(line_id, str) or not line_id.strip():
            raise PolicyError(400, "INVALID_REQUEST", f"{where}.lineId is required")
        if line_id in seen:
            raise PolicyError(400, "INVALID_REQUEST", f"{where}.lineId '{line_id}' is repeated")
        seen.add(line_id)
        category = ln.get("category")
        if not isinstance(category, str) or not category:
            raise PolicyError(400, "INVALID_REQUEST", f"{where}.category is required")
        amount = to_decimal(ln.get("amount"), f"{where}.amount")
        if amount <= 0:
            raise PolicyError(400, "INVALID_REQUEST", f"{where}.amount must be above zero")
        has_receipt = ln.get("hasReceipt")
        if not isinstance(has_receipt, bool):
            raise PolicyError(400, "INVALID_REQUEST", f"{where}.hasReceipt must be true or false")
        out: dict[str, Any] = {
            "lineId": line_id, "category": category, "amount": amount, "hasReceipt": has_receipt,
            "currency": check_currency(ln.get("currency"), f"{where}.currency"),
            "expenseDate": to_date(ln.get("expenseDate"), f"{where}.expenseDate"),
            "quantity": None, "amountInr": None, "exceptionReason": "",
        }
        if ln.get("quantity") is not None:
            out["quantity"] = to_decimal(ln["quantity"], f"{where}.quantity")
            if out["quantity"] < 0:
                raise PolicyError(400, "INVALID_REQUEST", f"{where}.quantity must not be negative")
        if ln.get("amountInr") is not None:
            out["amountInr"] = to_decimal(ln["amountInr"], f"{where}.amountInr")
            if out["amountInr"] <= 0:
                raise PolicyError(400, "INVALID_REQUEST", f"{where}.amountInr must be above zero")
        reason = ln.get("exceptionReason")
        if reason is not None:
            if not isinstance(reason, str):
                raise PolicyError(400, "INVALID_REQUEST", f"{where}.exceptionReason must be text")
            out["exceptionReason"] = reason.strip()
        lines.append(out)
    return lines


def _limit_cap(rules: dict, line: dict, grade: str) -> tuple[Decimal | None, str | None]:
    """Return (cap in base currency, problem code). A problem code means the limit cannot be applied."""
    spec = rules["category_limits"][line["category"]]
    per = to_decimal(spec[grade], "limit")
    unit = spec["unit"]
    if unit in PER_QUANTITY_UNITS:
        qty = line["quantity"]
        if qty is None and unit != "per_km":
            qty = Decimal(1)  # one night or one day when not stated
        if qty is None or qty <= 0:
            return None, "INVALID_QUANTITY"
        return per * qty, None
    return per, None


def evaluate_lines(rules: dict, grade: str, submission_date: date, lines: list[dict]) -> dict[str, Any]:
    base = rules["base_currency"]
    threshold = to_decimal(rules["receipt_threshold"], "receipt_threshold")
    window = rules.get("submission_window_days")
    violations: list[dict[str, Any]] = []
    requires_exception = False

    for ln in lines:
        def add(code: str, limit: Decimal | None = None) -> None:
            v: dict[str, Any] = {"lineId": ln["lineId"], "code": code}
            if limit is not None:
                v["limit"] = plain(limit)
            violations.append(v)

        if ln["expenseDate"] > submission_date:
            add("FUTURE_DATE_EXPENSE")
        elif window is not None and (submission_date - ln["expenseDate"]).days > window:
            add("WINDOW_EXPIRED")

        if ln["category"] not in rules["category_limits"]:
            add("UNKNOWN_CATEGORY")
        else:
            in_base = ln["currency"] == base
            amount_base = ln["amount"] if in_base else ln["amountInr"]
            cap, problem = _limit_cap(rules, ln, grade)
            if problem:
                add(problem)
            elif amount_base is None:
                add("MISSING_INR_EQUIVALENT")
            elif amount_base > cap:
                if ln["exceptionReason"]:
                    requires_exception = True
                else:
                    add("LIMIT_EXCEEDED", cap)

        needs_receipt = ln["currency"] != base or ln["amount"] >= threshold
        if needs_receipt and not ln["hasReceipt"]:
            add("RECEIPT_REQUIRED")

    return {"ok": not violations, "violations": violations, "requiresException": requires_exception}
