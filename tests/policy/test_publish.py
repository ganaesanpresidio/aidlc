import copy
import json
from datetime import datetime

import pytest
from jsonschema import Draft202012Validator

from policy.errors import NoRulesInForce, PolicyError
from policy.service import PolicyService
from policy.store import InMemoryRulesStore
from tests.conftest import ROOT

EVENT_SCHEMA = json.loads((ROOT / "aidlc-docs/design/policy/api/events/PolicyRulesPublished.v1.schema.json").read_text())
ADMIN = ["finance-admin"]


def pub(service, rules, key="key-00000001", groups=ADMIN, actor="fin1"):
    return service.publish(copy.deepcopy(rules), actor=actor, groups=groups, idempotency_key=key)


def err(fn):
    with pytest.raises(PolicyError) as e:
        fn()
    return e.value


# ---- happy path (A9) -------------------------------------------------------------------------------

def test_first_publish_is_version_1(service, example_rules):
    r = pub(service, example_rules)
    assert r["version"] == 1 and r["effectiveFrom"] == "2026-11-04" and r["publishedAt"] == "2026-11-04T09:00:00Z"
    assert r["rules"]["version"] == 1


def test_stored_version_number_overrides_the_file(service, example_rules):
    example_rules["version"] = 77
    assert pub(service, example_rules)["rules"]["version"] == 1


def test_publish_emits_a_valid_event(service, bus, example_rules):
    pub(service, example_rules)
    [ev] = bus.of("PolicyRulesPublished")
    assert list(Draft202012Validator(EVENT_SCHEMA).iter_errors(ev)) == []
    assert ev["payload"] == {"rulesVersion": 1, "effectiveFrom": "2026-11-04"}
    assert "claimRef" not in ev


def test_publish_writes_an_audit_event(service, bus, example_rules):
    pub(service, example_rules)
    [a] = bus.of("Audit")
    assert a["payload"]["actor"] == "fin1" and a["payload"]["action"] == "policy.publish"
    assert a["rulesVersion"] == 1 and a["payload"]["outcome"] == "ok"


def test_second_version_follows_and_both_stay_readable(service, example_rules):
    pub(service, example_rules)
    example_rules["effective_from"] = "2026-12-01"
    r2 = pub(service, example_rules, key="key-00000002")
    assert r2["version"] == 2
    assert service.rules_by_version(1)["effectiveFrom"] == "2026-11-04"
    assert service.rules_by_version(2)["effectiveFrom"] == "2026-12-01"


def test_future_version_is_not_in_force_until_its_date(service, example_rules, clock):
    pub(service, example_rules)
    example_rules["effective_from"] = "2026-12-01"
    pub(service, example_rules, key="key-00000002")
    from datetime import date
    assert service.rules_in_force(date(2026, 11, 30))["version"] == 1
    assert service.rules_in_force(date(2026, 12, 1))["version"] == 2
    assert service.rules_in_force(date(2027, 6, 1))["version"] == 2


# ---- permissions and request checks ----------------------------------------------------------------

@pytest.mark.parametrize("groups", [[], ["employee"], ["Finance-Admin"], ["finance-admins"]])
def test_only_finance_admin_can_publish(service, bus, example_rules, groups):
    e = err(lambda: pub(service, example_rules, groups=groups))
    assert e.status == 403
    [a] = bus.of("Audit")
    assert a["payload"]["outcome"] == "denied"  # denied attempts are recorded
    assert not bus.of("PolicyRulesPublished")


@pytest.mark.parametrize("key", [None, "", "short", "x" * 65, 12345678])
def test_idempotency_key_rules(service, example_rules, key):
    assert err(lambda: pub(service, example_rules, key=key)).status == 400


@pytest.mark.parametrize("key", ["12345678", "x" * 64])
def test_idempotency_key_length_edges_are_allowed(service, example_rules, key):
    assert pub(service, example_rules, key=key)["version"] == 1


def test_invalid_rules_are_422_with_reasons_and_nothing_stored(service, store, bus, example_rules):
    example_rules["approval_tiers"][-1]["max_total"] = 5
    e = err(lambda: pub(service, example_rules))
    assert e.status == 422 and e.code == "INVALID_RULES" and e.details
    assert store.latest() is None and not bus.of("PolicyRulesPublished")


def test_not_an_object_is_422(service):
    assert err(lambda: service.publish("rules", actor="f", groups=ADMIN, idempotency_key="key-00000001")).status == 422


def test_effective_date_in_the_past(service, example_rules):
    example_rules["effective_from"] = "2026-11-03"
    e = err(lambda: pub(service, example_rules))
    assert e.status == 422 and e.code == "EFFECTIVE_DATE_IN_PAST"


def test_effective_today_is_allowed(service, example_rules):
    example_rules["effective_from"] = "2026-11-04"
    assert pub(service, example_rules)["version"] == 1


@pytest.mark.parametrize("date_", ["2026-11-04", "2026-11-03", "2026-10-01"])
def test_effective_date_must_be_after_latest(service, example_rules, clock, date_):
    pub(service, example_rules)
    example_rules["effective_from"] = date_
    e = err(lambda: pub(service, example_rules, key="key-00000002"))
    assert e.status in (409, 422)
    if date_ == "2026-11-04":
        assert e.status == 409 and e.code == "EFFECTIVE_DATE_NOT_AFTER_LATEST"


def test_failed_publish_does_not_use_up_a_version(service, example_rules):
    bad = copy.deepcopy(example_rules)
    bad["effective_from"] = "nope"
    err(lambda: pub(service, bad, key="key-00000009"))
    assert pub(service, example_rules)["version"] == 1


# ---- idempotency (X1-style) -------------------------------------------------------------------------

def test_same_key_same_body_returns_the_first_result(service, bus, example_rules):
    first = pub(service, example_rules)
    again = pub(service, example_rules)
    assert again == first
    assert len(bus.of("PolicyRulesPublished")) == 1 and len(bus.of("Audit")) == 1
    assert service.rules_by_version(1)["version"] == 1
    assert err(lambda: service.rules_by_version(2)).status == 404


def test_same_key_different_body_is_a_conflict(service, example_rules):
    pub(service, example_rules)
    example_rules["receipt_threshold"] = 2000
    e = err(lambda: pub(service, example_rules))
    assert e.status == 409 and e.code == "IDEMPOTENCY_KEY_REUSED"


def test_key_can_be_reused_after_24_hours(service, store, clock, example_rules):
    pub(service, example_rules)
    clock.advance(hours=25)
    example_rules["effective_from"] = "2026-12-01"
    assert pub(service, example_rules)["version"] == 2


# ---- immutability and concurrency (A10) --------------------------------------------------------------

def test_published_version_cannot_be_overwritten(store, example_rules):
    from policy.errors import VersionExists
    store.put_version({"version": 1, "effectiveFrom": "2026-11-04", "rules": {}})
    with pytest.raises(VersionExists):
        store.put_version({"version": 1, "effectiveFrom": "2027-01-01", "rules": {"x": 1}})
    assert store.get_version(1)["effectiveFrom"] == "2026-11-04"


def test_read_copies_cannot_change_stored_rules(published):
    r = published.rules_by_version(1)
    r["rules"]["receipt_threshold"] = 1
    assert published.rules_by_version(1)["rules"]["receipt_threshold"] == 1000
    assert published.rules_in_force(datetime(2026, 11, 4).date())["rules"]["receipt_threshold"] == 1000


def test_lost_race_is_a_409(store, bus, clock, example_rules, monkeypatch):
    service = PolicyService(store, bus, clock)
    monkeypatch.setattr(store, "latest", lambda: None)  # both callers think they are first
    pub(service, example_rules)
    e = err(lambda: pub(service, example_rules, key="key-00000002"))
    assert e.status == 409 and e.code == "CONFLICT"


# ---- reading ---------------------------------------------------------------------------------------

def test_no_rules_before_any_publish(service):
    from datetime import date
    with pytest.raises(NoRulesInForce):
        service.rules_in_force(date(2026, 11, 4))


def test_no_rules_before_the_first_effective_date(published):
    from datetime import date
    assert err(lambda: published.rules_in_force(date(2026, 11, 3))).code == "NO_RULES_IN_FORCE"


def test_unknown_version_is_404(published):
    assert err(lambda: published.rules_by_version(5)).status == 404


# ---- cache (60 s, lld.md section 4) -------------------------------------------------------------------

def test_rules_in_force_is_cached_for_60_seconds(published, store, clock):
    from datetime import date
    published.rules_in_force(date(2026, 11, 4))
    reads = store.reads
    for _ in range(5):
        published.rules_in_force(date(2026, 11, 4))
    assert store.reads == reads
    clock.advance(seconds=59)
    published.rules_in_force(date(2026, 11, 4))
    assert store.reads == reads
    clock.advance(seconds=2)
    published.rules_in_force(date(2026, 11, 4))
    assert store.reads == reads + 1


def test_missing_rules_are_not_cached(service, example_rules):
    from datetime import date
    with pytest.raises(NoRulesInForce):
        service.rules_in_force(date(2026, 11, 4))
    pub(service, example_rules)
    assert service.rules_in_force(date(2026, 11, 4))["version"] == 1  # shows at once


def test_version_reads_are_cached(published, store):
    published.rules_by_version(1)
    reads = store.reads
    published.rules_by_version(1)
    assert store.reads == reads


# ---- reliable events (Q44) ---------------------------------------------------------------------------

class FlakyBus:
    def __init__(self):
        self.fail, self.sent = True, []

    def publish(self, event):
        if self.fail:
            raise RuntimeError("bus down")
        self.sent.append(event)


def test_event_failure_keeps_the_write_and_retries_later(clock, example_rules):
    flaky = FlakyBus()
    service = PolicyService(InMemoryRulesStore(), flaky, clock)
    r = pub(service, example_rules)  # does not raise
    assert r["version"] == 1 and service.rules_by_version(1)
    assert len(service.pending_events) == 2  # the event and its audit record
    assert service.flush_pending() == 0 and len(service.pending_events) == 2  # still down
    flaky.fail = False
    assert service.flush_pending() == 2 and not service.pending_events
    assert sorted(e["event"] for e in flaky.sent) == ["Audit", "PolicyRulesPublished"]


def test_flush_stops_at_the_first_failure_and_keeps_the_rest(clock, example_rules):
    flaky = FlakyBus()
    service = PolicyService(InMemoryRulesStore(), flaky, clock)
    pub(service, example_rules)
    flaky.fail = False
    original = flaky.publish
    calls = []

    def one_then_fail(event):
        calls.append(event)
        if len(calls) > 1:
            raise RuntimeError("down again")
        original(event)

    flaky.publish = one_then_fail
    assert service.flush_pending() == 1 and len(service.pending_events) == 1
