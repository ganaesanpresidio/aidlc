import json
from datetime import datetime

import pytest
import yaml
from jsonschema import Draft202012Validator

from submit.errors import SubmitError
from submit.service import Caller
from tests.conftest import EXAMPLE_RULES, ROOT
from tests.submit.conftest import EICAR, LINE, new_line, ready_claim, upload

KEY = "idem-key-0001"
SCHEMAS = ROOT / "aidlc-docs/design/submit/api/events"


def schema(name):
    return Draft202012Validator(json.loads((SCHEMAS / f"{name}.v1.schema.json").read_text()))


def err(fn):
    with pytest.raises(SubmitError) as e:
        fn()
    return e.value


def codes(e):
    return [(d["lineId"], d["code"]) for d in e.details]


# ---- AC8: submit successfully ------------------------------------------------------------------------

def test_ac8_submit_gives_reference_status_and_locks_the_claim(stack, svc, me):
    c, _ = ready_claim(stack, me)
    out = svc.submit(me, c, KEY)
    assert out["status"] == "Submitted" and out["claimRef"] == "CLM-2026-000001" and out["totalInr"] == 800
    assert out["submittedAt"] == "2026-11-04T09:00:00Z"
    assert err(lambda: svc.add_line(me, c, LINE)).code == "CLAIM_NOT_EDITABLE"


def test_references_count_up_and_are_never_reused(stack, svc, me):
    refs = []
    for i in range(3):
        c, _ = ready_claim(stack, me)
        refs.append(svc.submit(me, c, f"idem-key-000{i}")["claimRef"])
    assert refs == ["CLM-2026-000001", "CLM-2026-000002", "CLM-2026-000003"]


def test_references_restart_each_year(stack, svc, clock, me):
    c, _ = ready_claim(stack, me)
    svc.submit(me, c, KEY)
    clock.set(datetime(2027, 1, 5, 9, 0))
    rules = yaml.safe_load(EXAMPLE_RULES.read_text())
    rules["effective_from"] = "2027-01-05"
    stack.policy_service.publish(rules, actor="f", groups=["finance-admin"], idempotency_key="key-2027-0001")
    c2, _ = ready_claim(stack, me, expenseDate="2027-01-04")
    assert svc.submit(me, c2, "idem-key-0002")["claimRef"] == "CLM-2027-000001"


def test_submit_emits_a_valid_claim_submitted_event(stack, svc, bus, me):
    c, _ = ready_claim(stack, me)
    svc.submit(me, c, KEY)
    [e] = bus.of("ClaimSubmitted")
    assert list(schema("ClaimSubmitted").iter_errors(e)) == []
    assert e["claimRef"] == "CLM-2026-000001" and e["rulesVersion"] == 1
    assert e["payload"] == {"submitterId": "emp1", "gradeOfSubmitter": "G1", "totalInr": 800, "lineCount": 1,
                            "requiresException": False}


def test_event_holds_no_personal_data(stack, svc, bus, me):
    c, _ = ready_claim(stack, me, description="dinner with Ravi Kumar")
    svc.submit(me, c, KEY)
    assert "Ravi" not in json.dumps(bus.events) and "dinner" not in json.dumps(bus.events)


def test_submit_writes_an_audit_event(stack, svc, bus, me):
    c, _ = ready_claim(stack, me)
    svc.submit(me, c, KEY)
    [a] = [e for e in bus.of("Audit") if e["payload"]["action"] == "claim.submit"]
    assert a["claimRef"] == "CLM-2026-000001" and a["rulesVersion"] == 1 and a["payload"]["actor"] == "emp1"


def test_totals_use_the_inr_equivalent_for_foreign_lines(stack, svc, me):
    c = svc.create_claim(me)["claimId"]
    new_line(svc, me, c, amount=500)
    l2 = new_line(svc, me, c, amount=20, currency="USD", amountInr=1400, category="Meals")
    upload(stack, me, c, l2)
    out = svc.submit(me, c, KEY)
    assert out["totalInr"] == 1900 and out["totalsByCurrency"] == {"INR": 500, "USD": 20}


# ---- AC7 and AC7a: a receipt is needed from 1,000 -----------------------------------------------------

@pytest.mark.parametrize("amount,blocked", [(999.99, False), (1000, True), (1000.01, True), (5000, True), (1, False)])
def test_ac7_threshold_boundary(stack, svc, me, amount, blocked):
    c = svc.create_claim(me)["claimId"]
    new_line(svc, me, c, amount=amount, category="Other")
    if blocked:
        e = err(lambda: svc.submit(me, c, KEY))
        assert e.status == 422 and e.code == "POLICY_VIOLATIONS" and codes(e)[0][1] == "RECEIPT_REQUIRED"
        assert e.details[0]["message"] == "Add a receipt"
    else:
        assert svc.submit(me, c, KEY)["status"] == "Submitted"  # AC7a: small INR line, no receipt


def test_ac7_the_violation_names_the_line(stack, svc, me):
    c = svc.create_claim(me)["claimId"]
    ok = new_line(svc, me, c, amount=500)
    bad = new_line(svc, me, c, amount=2000, category="Other")
    e = err(lambda: svc.submit(me, c, KEY))
    assert codes(e) == [(bad, "RECEIPT_REQUIRED")] and ok not in [d["lineId"] for d in e.details]


def test_foreign_line_always_needs_a_receipt(stack, svc, me):
    c = svc.create_claim(me)["claimId"]
    l = new_line(svc, me, c, amount=5, currency="USD", amountInr=400)
    assert codes(err(lambda: svc.submit(me, c, KEY))) == [(l, "RECEIPT_REQUIRED")]
    upload(stack, me, c, l)
    assert svc.submit(me, c, KEY)["status"] == "Submitted"


def test_a_rejected_receipt_does_not_count(stack, svc, me):
    c = svc.create_claim(me)["claimId"]
    l = new_line(svc, me, c, amount=2000, category="Other")
    upload(stack, me, c, l, EICAR)
    assert codes(err(lambda: svc.submit(me, c, KEY))) == [(l, "RECEIPT_REQUIRED")]


def test_a_removed_receipt_is_missing_again(stack, svc, me):
    c, l = ready_claim(stack, me, amount=2000, category="Other")
    r = svc.get_claim(me, c)["lines"][0]["receipts"][0]
    svc.delete_receipt(me, c, l, r["receiptId"])
    assert err(lambda: svc.submit(me, c, KEY)).code == "POLICY_VIOLATIONS"


# ---- other policy results ----------------------------------------------------------------------------

def test_over_the_limit_is_blocked_with_a_clear_message(stack, svc, me):
    c, l = ready_claim(stack, me, amount=2000, category="Meals")
    e = err(lambda: svc.submit(me, c, KEY))
    assert codes(e) == [(l, "LIMIT_EXCEEDED")] and "limit" in e.details[0]["message"]


def test_over_the_limit_with_a_reason_goes_through_and_is_flagged(stack, svc, bus, me):
    c, _ = ready_claim(stack, me, amount=2000, category="Meals", exceptionReason="client dinner")
    svc.submit(me, c, KEY)
    assert bus.of("ClaimSubmitted")[0]["payload"]["requiresException"] is True


def test_old_expenses_are_blocked(stack, svc, me):
    c, l = ready_claim(stack, me, expenseDate="2026-09-01")
    assert codes(err(lambda: svc.submit(me, c, KEY))) == [(l, "WINDOW_EXPIRED")]


def test_future_dated_expenses_are_blocked(stack, svc, me):
    c, l = ready_claim(stack, me, expenseDate="2026-11-09")
    assert codes(err(lambda: svc.submit(me, c, KEY))) == [(l, "FUTURE_DATE_EXPENSE")]


def test_several_problems_are_all_reported_at_once(stack, svc, me):
    c = svc.create_claim(me)["claimId"]
    a = new_line(svc, me, c, amount=2000, category="Other")
    b = new_line(svc, me, c, amount=2000, category="Meals", expenseDate="2026-09-01")
    got = codes(err(lambda: svc.submit(me, c, KEY)))
    assert (a, "RECEIPT_REQUIRED") in got and (b, "WINDOW_EXPIRED") in got and (b, "LIMIT_EXCEEDED") in got


def test_a_failed_submit_changes_nothing(stack, svc, bus, me):
    c = svc.create_claim(me)["claimId"]
    new_line(svc, me, c, amount=2000, category="Other")
    err(lambda: svc.submit(me, c, KEY))
    assert svc.get_claim(me, c)["status"] == "Draft" and not bus.of("ClaimSubmitted")
    assert stack.table.get("COUNTER#CLM#2026", "META") is None  # no reference was used up


def test_claim_with_no_lines(svc, me, claim):
    assert err(lambda: svc.submit(me, claim, KEY)).code == "NO_LINES"


# ---- X3: receipts still being checked -----------------------------------------------------------------

def test_x3_scanning_receipt_blocks_submit(stack, svc, me):
    c = svc.create_claim(me)["claimId"]
    l = new_line(svc, me, c, amount=2000, category="Other")
    upload(stack, me, c, l, scan=False)
    e = err(lambda: svc.submit(me, c, KEY))
    assert e.code == "RECEIPT_STILL_CHECKING" and "Receipt still being checked" in e.message


def test_a_receipt_slot_never_used_also_blocks_submit(stack, svc, me):
    c = svc.create_claim(me)["claimId"]
    l = new_line(svc, me, c, amount=500)
    svc.request_receipt_upload(me, c, l, {"mimeType": "image/png", "sizeBytes": 5, "sha256": "a" * 64})
    assert err(lambda: svc.submit(me, c, KEY)).code == "RECEIPT_STILL_CHECKING"


# ---- X1: idempotency ---------------------------------------------------------------------------------

def test_x1_same_key_same_reference_one_event(stack, svc, bus, me):
    c, _ = ready_claim(stack, me)
    first = svc.submit(me, c, KEY)
    again = svc.submit(me, c, KEY)
    assert again["claimRef"] == first["claimRef"]
    assert len(bus.of("ClaimSubmitted")) == 1
    assert len([a for a in bus.of("Audit") if a["payload"]["action"] == "claim.submit"]) == 1


def test_a_different_key_on_a_submitted_claim_is_refused(stack, svc, me):
    c, _ = ready_claim(stack, me)
    svc.submit(me, c, KEY)
    assert err(lambda: svc.submit(me, c, "another-key-02")).code == "CLAIM_NOT_EDITABLE"


def test_key_expires_after_24_hours(stack, svc, clock, me):
    c, _ = ready_claim(stack, me)
    svc.submit(me, c, KEY)
    clock.advance(hours=25)
    assert err(lambda: svc.submit(me, c, KEY)).code == "CLAIM_NOT_EDITABLE"


@pytest.mark.parametrize("key", [None, "", "short", "x" * 65, "bad key with spaces", "emoji-key-☃☃", 12345678])
def test_bad_idempotency_keys(stack, svc, me, key):
    c, _ = ready_claim(stack, me)
    assert err(lambda: svc.submit(me, c, key)).status == 422


@pytest.mark.parametrize("key", ["12345678", "x" * 64, "a.b_c:d-e1"])
def test_good_idempotency_key_edges(stack, svc, me, key):
    c, _ = ready_claim(stack, me)
    assert svc.submit(me, c, key)["status"] == "Submitted"


# ---- fail closed (lld.md section 6) --------------------------------------------------------------------

def test_policy_down_means_nothing_is_submitted(stack, svc, bus, me):
    c, _ = ready_claim(stack, me)
    stack.policy_client.down = True
    e = err(lambda: svc.submit(me, c, KEY))
    assert e.status == 503 and e.code == "POLICY_UNAVAILABLE"
    assert svc.get_claim(me, c)["status"] == "Draft" and not bus.of("ClaimSubmitted")
    stack.policy_client.down = False
    assert svc.submit(me, c, KEY)["status"] == "Submitted"  # retry with the same key works


def test_no_rules_in_force_also_fails_closed(clock, bus, me):
    from submit.factory import build_mock_stack
    st = build_mock_stack(clock=clock, bus=bus, seed_policy=False)
    c, _ = ready_claim(st, me)
    assert err(lambda: st.service.submit(me, c, KEY)).status == 503


def test_policy_refusing_the_request_is_reported(stack, svc, me):
    odd = Caller("emp7", "G9")  # a grade the rules do not know
    c = svc.create_claim(odd)["claimId"]
    new_line(svc, odd, c)
    e = err(lambda: svc.submit(odd, c, KEY))
    assert e.status == 422 and e.code == "POLICY_REJECTED_REQUEST" and "UNKNOWN_GRADE" in e.message


# ---- races -----------------------------------------------------------------------------------------

def test_two_submits_at_once_only_one_wins(stack, svc, bus, me):
    c, _ = ready_claim(stack, me)
    real = stack.table.transact
    state = {"first": True}

    def racing(ops):
        if state["first"]:
            state["first"] = False
            stack.table.transact = real  # another request submits the claim between our read and our write
            svc.submit(me, c, "winner-key-001")
        return real(ops)

    stack.table.transact = racing
    e = err(lambda: svc.submit(me, c, "loser-key-0001"))
    assert e.status == 409 and e.code == "CONFLICT"
    assert len(bus.of("ClaimSubmitted")) == 1


def test_a_line_added_while_submitting_is_not_lost(stack, svc, me):
    c, _ = ready_claim(stack, me)
    real = stack.table.transact
    done = {"x": False}

    def adds_a_line_first(ops):
        if not done["x"]:
            done["x"] = True
            stack.table.transact = real
            svc.add_line(me, c, LINE)  # bumps the claim version after submit already read it
        return real(ops)

    stack.table.transact = adds_a_line_first
    assert err(lambda: svc.submit(me, c, KEY)).code == "CONFLICT"
    assert svc.get_claim(me, c)["status"] == "Draft" and len(svc.get_claim(me, c)["lines"]) == 2


def test_event_failure_after_submit_keeps_the_claim_and_retries(stack, svc, bus, me):
    c, _ = ready_claim(stack, me)
    original = bus.publish

    def down(e):
        raise RuntimeError("bus down")

    bus.publish = down
    out = svc.submit(me, c, KEY)  # the claim is saved even though the bus is down
    assert out["status"] == "Submitted" and len(svc.pending_events) >= 2
    bus.publish = original
    assert svc.flush_pending() >= 2 and not svc.pending_events
    assert len(bus.of("ClaimSubmitted")) == 1
