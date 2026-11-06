import json
import logging
from datetime import UTC, datetime, timedelta

import pytest

from aidlc_common import log
from aidlc_common.backend import Backend, aws_client, current_backend
from aidlc_common.clock import FixedClock, SystemClock, new_ulid, new_uuid
from aidlc_common.events import AuditLog, EventBridgeBus, InMemoryEventBus, envelope

# ---- backend flag -----------------------------------------------------------------------------------

def test_default_is_mock(monkeypatch):
    monkeypatch.delenv("AIDLC_BACKEND", raising=False)
    assert current_backend() is Backend.MOCK


@pytest.mark.parametrize("raw,expected", [("mock", Backend.MOCK), ("MOCK", Backend.MOCK), (" aws ", Backend.AWS),
                                          ("AWS", Backend.AWS), ("", Backend.MOCK)])
def test_flag_values(monkeypatch, raw, expected):
    monkeypatch.setenv("AIDLC_BACKEND", raw)
    assert current_backend() is expected


@pytest.mark.parametrize("raw", ["real", "prod", "1", "true"])
def test_unknown_flag_value_fails_loudly(monkeypatch, raw):
    monkeypatch.setenv("AIDLC_BACKEND", raw)
    with pytest.raises(ValueError, match="mock"):
        current_backend()


def test_flag_can_come_from_the_env_file(monkeypatch, tmp_path):
    f = tmp_path / "x.env"
    f.write_text("AIDLC_BACKEND=aws\n")
    monkeypatch.delenv("AIDLC_BACKEND", raising=False)
    from aidlc_e2e import config
    monkeypatch.setattr(config, "ENV_FILE", f)
    assert config.get("AIDLC_BACKEND", "mock", env_file=f) == "aws"


def test_environment_beats_the_env_file(monkeypatch, tmp_path):
    f = tmp_path / "x.env"
    f.write_text("AIDLC_BACKEND=aws\n")
    monkeypatch.setenv("AIDLC_BACKEND", "mock")
    from aidlc_e2e import config
    assert config.get("AIDLC_BACKEND", "x", env_file=f) == "mock"


def test_aws_client_builds_without_calling_aws():
    c = aws_client("dynamodb", "ap-south-1")
    assert c.meta.region_name == "ap-south-1"


# ---- clock and ids ----------------------------------------------------------------------------------

def test_fixed_clock_moves_only_when_told():
    c = FixedClock(datetime(2026, 11, 4, 23, 59))
    assert c.now().tzinfo is not None and c.today().isoformat() == "2026-11-04"
    c.advance(minutes=2)
    assert c.today().isoformat() == "2026-11-05"
    c.set(datetime(2027, 1, 1))
    assert c.today().isoformat() == "2027-01-01"


def test_system_clock_is_utc_now():
    assert abs((SystemClock().now() - datetime.now(UTC)) < timedelta(seconds=2))
    assert SystemClock().today() == SystemClock().now().date()


def test_ulid_shape_and_order():
    c = FixedClock(datetime(2026, 11, 4, 9, 0))
    a = new_ulid(c, b"\x00" * 10)
    c.advance(seconds=1)
    b = new_ulid(c, b"\x00" * 10)
    assert len(a) == 26 and a.isalnum() and a == a.upper()
    assert a < b  # sortable by time
    assert not set(a) & set("ILOU")  # Crockford alphabet


def test_ulid_random_part_differs():
    assert new_ulid() != new_ulid()


def test_uuid_is_a_uuid():
    import uuid
    assert str(uuid.UUID(new_uuid())) == new_uuid.__call__.__self__ if False else uuid.UUID(new_uuid())


# ---- events -----------------------------------------------------------------------------------------

def test_envelope_shape():
    c = FixedClock(datetime(2026, 11, 4, 9, 0))
    e = envelope("ClaimSubmitted", {"x": 1}, claim_ref="CLM-1", rules_version=3, clock=c)
    assert e["event"] == "ClaimSubmitted" and e["version"] == 1 and e["claimRef"] == "CLM-1"
    assert e["rulesVersion"] == 3 and e["occurredAt"] == "2026-11-04T09:00:00Z" and e["payload"] == {"x": 1}
    assert "claimRef" not in envelope("X", {}, include_claim_ref=False)
    assert "rulesVersion" not in envelope("X", {})


def test_event_ids_are_unique():
    assert envelope("X", {})["id"] != envelope("X", {})["id"]


def test_in_memory_bus_keeps_copies_and_calls_subscribers():
    bus, seen = InMemoryEventBus(), []
    bus.subscribe("A", seen.append)
    ev = envelope("A", {"n": 1})
    bus.publish(ev)
    bus.publish(envelope("B", {}))
    ev["payload"]["n"] = 99  # changing the original must not change what the bus stored
    assert bus.of("A")[0]["payload"]["n"] == 1 and len(seen) == 1 and len(bus.events) == 2


def test_audit_log_writes_who_what_when():
    bus = InMemoryEventBus()
    AuditLog(bus, FixedClock(datetime(2026, 11, 4, 9, 0))).record(actor="u1", action="claim.submit", ref="CLM-1",
                                                                  detail={"lines": 2})
    [a] = bus.of("Audit")
    assert a["payload"] == {"actor": "u1", "action": "claim.submit", "outcome": "ok", "detail": {"lines": 2}}
    assert a["claimRef"] == "CLM-1" and a["occurredAt"] == "2026-11-04T09:00:00Z"


class FakeEvents:
    def __init__(self, failed=0):
        self.calls, self.failed = [], failed

    def put_events(self, **kw):
        self.calls.append(kw)
        return {"FailedEntryCount": self.failed, "Entries": [{"ErrorCode": "Throttled"}] if self.failed else [{}]}


def test_eventbridge_bus_sends_the_right_shape():
    fake = FakeEvents()
    EventBridgeBus(fake, "aidlc-events", "aidlc.policy").publish(envelope("PolicyRulesPublished", {"a": 1}))
    [entry] = fake.calls[0]["Entries"]
    assert entry["EventBusName"] == "aidlc-events" and entry["Source"] == "aidlc.policy"
    assert entry["DetailType"] == "PolicyRulesPublished.v1" and json.loads(entry["Detail"])["payload"] == {"a": 1}


def test_eventbridge_failure_raises_so_callers_can_retry():
    with pytest.raises(RuntimeError, match="Throttled"):
        EventBridgeBus(FakeEvents(failed=1), "b", "s").publish(envelope("X", {}))


# ---- safe logging -----------------------------------------------------------------------------------

def test_only_allowed_fields_are_logged(caplog):
    with caplog.at_level(logging.INFO, logger="aidlc"):
        rec = log.info("hello", claim_ref="CLM-1", description="lunch with Ravi", file_name="r.pdf",
                       employee_name="Asha", amount=100, size_bytes=5)
    assert rec == {"message": "hello", "claim_ref": "CLM-1", "size_bytes": 5}
    text = caplog.text
    assert "Ravi" not in text and "Asha" not in text and "r.pdf" not in text


def test_error_level(caplog):
    with caplog.at_level(logging.ERROR, logger="aidlc"):
        log.error("bad", code="X")
    assert caplog.records[0].levelno == logging.ERROR


def test_no_personal_looking_field_is_on_the_allow_list():
    for banned in ("name", "email", "description", "file_name", "filename", "amount", "url", "token", "content"):
        assert banned not in log.ALLOWED_FIELDS
