from datetime import UTC, datetime

from aidlc_common.clock import SystemClock


class At(SystemClock):
    def __init__(self, at, tz=None):
        super().__init__(tz)
        self._at = at

    def now(self):
        return self._at


def test_business_date_is_india_time_not_utc():
    # 19:00 UTC on the 4th is 00:30 IST on the 5th
    clock = At(datetime(2026, 11, 4, 19, 0, tzinfo=UTC))
    assert clock.now().date().isoformat() == "2026-11-04" and clock.today().isoformat() == "2026-11-05"


def test_just_before_midnight_india_time_is_still_the_same_day():
    assert At(datetime(2026, 11, 4, 18, 29, tzinfo=UTC)).today().isoformat() == "2026-11-04"
    assert At(datetime(2026, 11, 4, 18, 30, tzinfo=UTC)).today().isoformat() == "2026-11-05"


def test_timezone_can_be_set_by_name_or_setting(monkeypatch):
    at = datetime(2026, 11, 4, 19, 0, tzinfo=UTC)
    assert At(at, "UTC").today().isoformat() == "2026-11-04"
    monkeypatch.setenv("AIDLC_TIMEZONE", "America/New_York")
    assert At(at).today().isoformat() == "2026-11-04"
    monkeypatch.setenv("AIDLC_TIMEZONE", "Pacific/Auckland")
    assert At(at).today().isoformat() == "2026-11-05"


def test_year_end_in_india():
    assert At(datetime(2026, 12, 31, 19, 0, tzinfo=UTC)).today().isoformat() == "2027-01-01"
