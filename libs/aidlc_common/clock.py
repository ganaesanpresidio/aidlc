"""Clock and id helpers, injectable so tests control time."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, date, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    """Real time. `today()` is the business date: dates in the rules, the 30-day window and claim
    references follow the company calendar (AIDLC_TIMEZONE, default Asia/Kolkata), not UTC."""

    def __init__(self, tz_name: str | None = None) -> None:
        from zoneinfo import ZoneInfo

        from aidlc_e2e.config import get

        self._tz = ZoneInfo(tz_name or get("AIDLC_TIMEZONE", "Asia/Kolkata"))

    def now(self) -> datetime:
        return datetime.now(UTC)

    def today(self) -> date:
        return self.now().astimezone(self._tz).date()


class FixedClock:
    """Test clock. `advance` moves it forward."""

    def __init__(self, at: datetime) -> None:
        if at.tzinfo is None:
            at = at.replace(tzinfo=UTC)
        self._at = at

    def now(self) -> datetime:
        return self._at

    def today(self) -> date:
        return self._at.date()

    def set(self, at: datetime) -> None:
        self._at = at if at.tzinfo else at.replace(tzinfo=UTC)

    def advance(self, **delta) -> None:
        from datetime import timedelta

        self._at = self._at + timedelta(**delta)


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid(clock: Clock | None = None, rand: bytes | None = None) -> str:
    """26-character sortable id: 48-bit millisecond time + 80 random bits."""
    ms = int((clock.now() if clock else SystemClock().now()).timestamp() * 1000)
    value = (ms << 80) | int.from_bytes(rand if rand is not None else os.urandom(10), "big")
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def new_uuid() -> str:
    return str(uuid.uuid4())
