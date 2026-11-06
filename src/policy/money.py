"""Exact money and date parsing. Floats are never compared directly (999.99 must stay 999.99)."""

from __future__ import annotations

import math
import re
from datetime import date
from decimal import Decimal

from policy.errors import PolicyError

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


MAX_ABS = Decimal(10) ** 15  # far above any real claim; stops absurd exponents before any arithmetic


def to_decimal(value, field: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise PolicyError(400, "INVALID_REQUEST", f"{field} must be a number")
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise PolicyError(400, "INVALID_REQUEST", f"{field} must be a finite number")
    try:
        d = Decimal(str(value))
    except Exception:
        raise PolicyError(400, "INVALID_REQUEST", f"{field} must be a number") from None
    if not d.is_finite():
        raise PolicyError(400, "INVALID_REQUEST", f"{field} must be a finite number")
    if d.copy_abs() > MAX_ABS:  # copy_abs does no arithmetic, so it cannot overflow
        raise PolicyError(400, "INVALID_REQUEST", f"{field} is too large")
    return d


def to_date(value, field: str) -> date:
    if not isinstance(value, str) or not _DATE.match(value):
        raise PolicyError(400, "INVALID_DATE", f"{field} must be a date like 2026-11-04")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise PolicyError(400, "INVALID_DATE", f"{field} is not a real date") from None


def check_currency(value, field: str) -> str:
    if not isinstance(value, str) or not _CURRENCY.match(value):
        raise PolicyError(400, "INVALID_REQUEST", f"{field} must be a 3-letter code like INR")
    return value


def plain(d: Decimal):
    """Decimal to int when whole, else float, for JSON output."""
    return int(d) if d == d.to_integral_value() else float(d)
