"""Exact money and dates for submit. Amounts are Decimal, stored as text, never floats."""

from __future__ import annotations

import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from submit.errors import SubmitError

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_AMOUNT = Decimal("99999999.99")
CENT = Decimal("0.01")


def bad(field: str, why: str) -> SubmitError:
    return SubmitError(422, "INVALID_REQUEST", f"{field} {why}", [{"code": "INVALID_FIELD", "message": f"{field} {why}"}])


def amount(value, field: str, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise bad(field, "must be a number")
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise bad(field, "must be a finite number")
    try:
        d = Decimal(str(value))
    except InvalidOperation:
        raise bad(field, "must be a number") from None
    if not d.is_finite():
        raise bad(field, "must be a finite number")
    if d < 0 or (d == 0 and not allow_zero):
        raise bad(field, "must be above zero")
    if d > MAX_AMOUNT:
        raise bad(field, f"must not exceed {MAX_AMOUNT}")
    if d != d.quantize(CENT):
        raise bad(field, "can have at most 2 decimal places")
    return d.quantize(CENT)


def quantity(value, field: str) -> Decimal:
    d = amount(value, field, allow_zero=True)
    return d


def day(value, field: str) -> date:
    if not isinstance(value, str) or not _DATE.match(value):
        raise bad(field, "must be a date like 2026-11-04")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise bad(field, "is not a real date") from None


def out(d: Decimal | str | None):
    """Decimal text to a JSON number: whole numbers as int."""
    if d is None:
        return None
    d = Decimal(str(d))
    return int(d) if d == d.to_integral_value() else float(d)
