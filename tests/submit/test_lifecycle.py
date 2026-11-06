import json
from datetime import date, datetime

import pytest
from jsonschema import Draft202012Validator

from aidlc_common.events import envelope
from submit.errors import SubmitError
from tests.conftest import ROOT
from tests.submit.conftest import PNG, new_line, ready_claim, upload

KEY = "idem-key-0001"
SCHEMAS = ROOT / "aidlc-docs/design/submit/api/events"


def err(fn):
    with pytest.raises(SubmitError) as e:
        fn()
    return e.value


@pytest.fixture
def submitted(stack, svc, me):
    c, l = ready_claim(stack, me)
    return c, l, svc.submit(me, c, KEY)["claimRef"]


# ---- withdraw (US-004 base) ----------------------------------------------------------------------------

def test_withdraw_a_submitted_claim(svc, bus, me, submitted):
    c, _, ref = submitted
    out = svc.withdraw(me, c)
    assert out["status"] == "Withdrawn"
    [e] = bus.of("ClaimWithdrawn")
    assert e["claimRef"] == ref and Draft202012Validator(json.loads((SCHEMAS / "ClaimWithdrawn.v1.schema.json").read_text())).is_valid(e)
    assert any(a["payload"]["action"] == "claim.withdraw" for a in bus.of("Audit"))


def test_cannot_withdraw_a_draft(svc, me, claim):
    assert err(lambda: svc.withdraw(me, claim)).code == "CANNOT_WITHDRAW"


def test_cannot_withdraw_twice(svc, me, submitted):
    svc.withdraw(me, submitted[0])
    assert err(lambda: svc.withdraw(me, submitted[0])).code == "CANNOT_WITHDRAW"


@pytest.mark.parametrize("event", ["ClaimApproved", "ClaimRejected"])
def test_cannot_withdraw_after_a_decision(svc, bus, me, submitted, event):
    bus.publish(envelope(event, {}, claim_ref=submitted[2]))
    assert err(lambda: svc.withdraw(me, submitted[0])).code == "CANNOT_WITHDRAW"


def test_a_withdrawn_claim_stays_locked(svc, me, submitted):
    svc.withdraw(me, submitted[0])
    assert err(lambda: svc.add_line(me, submitted[0], {"amount": 1})).code == "CLAIM_NOT_EDITABLE"


# ---- status follows approval and payment events -----------------------------------------------------------

def status(svc, me, c):
    return svc.get_claim(me, c)["status"]


def test_approved_then_paid(svc, bus, me, submitted):
    c, _, ref = submitted
    bus.publish(envelope("ClaimApproved", {"totalInr": 800}, claim_ref=ref))
    assert status(svc, me, c) == "Approved"
    bus.publish(envelope("PayoutIssued", {}, claim_ref=ref))
    assert status(svc, me, c) == "Paid"


def test_rejected(svc, bus, me, submitted):
    bus.publish(envelope("ClaimRejected", {}, claim_ref=submitted[2]))
    assert status(svc, me, submitted[0]) == "Rejected"


@pytest.mark.parametrize("first,then", [("ClaimRejected", "ClaimApproved"), ("ClaimApproved", "ClaimRejected")])
def test_a_decision_cannot_be_reversed(svc, bus, me, submitted, first, then):
    bus.publish(envelope(first, {}, claim_ref=submitted[2]))
    bus.publish(envelope(then, {}, claim_ref=submitted[2]))
    assert status(svc, me, submitted[0]) == {"ClaimRejected": "Rejected", "ClaimApproved": "Approved"}[first]


def test_payment_before_approval_is_ignored_and_audited(svc, bus, me, submitted):
    bus.publish(envelope("PayoutIssued", {}, claim_ref=submitted[2]))
    assert status(svc, me, submitted[0]) == "Submitted"
    assert any(a["payload"]["outcome"] == "ignored" for a in bus.of("Audit"))


def test_repeated_events_are_harmless(svc, bus, me, submitted):
    for _ in range(3):
        bus.publish(envelope("ClaimApproved", {}, claim_ref=submitted[2]))
    assert status(svc, me, submitted[0]) == "Approved"


def test_withdrawn_claims_ignore_approval(svc, bus, me, submitted):
    svc.withdraw(me, submitted[0])
    bus.publish(envelope("ClaimApproved", {}, claim_ref=submitted[2]))
    assert status(svc, me, submitted[0]) == "Withdrawn"


@pytest.mark.parametrize("ev", [envelope("ClaimApproved", {}, claim_ref="CLM-2026-999999"), envelope("ClaimApproved", {}),
                                envelope("SomethingElse", {}, claim_ref="CLM-2026-000001")])
def test_unknown_references_and_events_are_ignored(svc, ev):
    assert svc.on_event(ev) is False


# ---- internal receipt access for approvers (Q43) -----------------------------------------------------------

def test_access_url_for_a_submitted_claim(stack, svc, bus, me, submitted):
    c, _, ref = submitted
    rid = svc.get_claim(me, c)["lines"][0]["receipts"][0]["receiptId"]
    out = svc.receipt_access_url(rid, ref, "approver1")
    assert out["expiresInSeconds"] == 60 and out["url"].endswith("?expires=60")
    a = [e for e in bus.of("Audit") if e["payload"]["action"] == "receipt.access"]
    assert a[0]["payload"]["actor"] == "approver1"


def test_access_url_refuses_unknown_and_draft(stack, svc, me, claim):
    assert err(lambda: svc.receipt_access_url("x", "CLM-2026-123456", "a")).status == 404
    l = new_line(svc, me, claim)
    r = upload(stack, me, claim, l)
    # a draft has no reference yet, so there is nothing to ask for
    assert err(lambda: svc.receipt_access_url(r["receiptId"], "CLM-2026-000001", "a")).status == 404


def test_access_url_wrong_receipt_for_that_claim(stack, svc, me, submitted):
    c2, _ = ready_claim(stack, me)
    other_rid = svc.get_claim(me, c2)["lines"][0]["receipts"][0]["receiptId"]
    assert err(lambda: svc.receipt_access_url(other_rid, submitted[2], "a")).status == 404


def test_access_url_refuses_a_rejected_receipt(stack, svc, me):
    c = svc.create_claim(me)["claimId"]
    l = new_line(svc, me, c, amount=500)
    r = upload(stack, me, c, l, b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
    ref = svc.submit(me, c, KEY)["claimRef"]
    assert err(lambda: svc.receipt_access_url(r["receiptId"], ref, "a")).code == "RECEIPT_NOT_READY"


# ---- retention (US-006 base, Q13) -------------------------------------------------------------------------

def test_receipt_gets_an_expiry_date_from_the_retention_setting(stack, svc, me, claim):
    l = new_line(svc, me, claim)
    r = upload(stack, me, claim, l)
    item = stack.table.get(f"CLAIM#{claim}", f"RCPT#{r['receiptId']}")
    assert item["expiresOn"] == "2027-11-04"  # 365 days from 2026-11-04


def test_retention_is_configurable(clock, bus, me):
    from submit.factory import build_mock_stack
    from submit.service import Settings
    st = build_mock_stack(clock=clock, bus=bus, settings=Settings(retention_days=30))
    c = st.service.create_claim(me)["claimId"]
    r = upload(st, me, c, new_line(st.service, me, c))
    assert st.table.get(f"CLAIM#{c}", f"RCPT#{r['receiptId']}")["expiresOn"] == "2026-12-04"


def test_nothing_expires_early(stack, svc, clock, me, submitted):
    clock.set(datetime(2027, 11, 3, 9, 0))
    assert svc.expire_receipts() == 0


def test_expiry_deletes_the_file_and_marks_the_receipt(stack, svc, bus, clock, me, submitted):
    c, l, ref = submitted
    rid = svc.get_claim(me, c)["lines"][0]["receipts"][0]["receiptId"]
    clock.set(datetime(2027, 11, 4, 9, 0))
    assert svc.expire_receipts() == 1
    assert not stack.objects.buckets["receipts"]
    assert svc.get_claim(me, c)["lines"][0]["receipts"][0]["status"] == "EXPIRED"
    [e] = bus.of("ReceiptsExpired")
    assert e["payload"] == {"receiptIds": [rid], "retentionDays": 365} and e["claimRef"] == ref
    assert Draft202012Validator(json.loads((SCHEMAS / "ReceiptsExpired.v1.schema.json").read_text())).is_valid(e)
    assert any(a["payload"]["action"] == "receipt.expire" for a in bus.of("Audit"))


def test_expiry_catches_up_after_missed_days(stack, svc, clock, me, submitted):
    clock.set(datetime(2028, 3, 1, 9, 0))  # the job did not run for months
    assert svc.expire_receipts() == 1


def test_expiry_is_safe_to_run_twice(stack, svc, bus, clock, me, submitted):
    clock.set(datetime(2027, 11, 4, 9, 0))
    assert svc.expire_receipts() == 1
    assert svc.expire_receipts() == 0
    assert len(bus.of("ReceiptsExpired")) == 1


def test_expiry_handles_several_claims_and_leaves_newer_receipts(stack, svc, clock, me, other):
    ready_claim(stack, me)
    ready_claim(stack, other)
    clock.advance(days=10)
    c2, l2 = ready_claim(stack, me)  # uploaded 10 days later, expires later
    clock.set(datetime(2027, 11, 5, 9, 0))  # first and third are due, second is not
    assert svc.expire_receipts() == 2
    assert svc.get_claim(me, c2)["lines"][0]["receipts"][0]["status"] == "CLEAN"


def test_expiry_clears_the_duplicate_index(stack, svc, clock, me, submitted):
    clock.set(datetime(2027, 11, 4, 9, 0))
    svc.expire_receipts()
    from tests.submit.conftest import sha
    assert stack.table.query(f"DUP#emp1#{sha(PNG)}") == []


def test_expired_receipts_cannot_be_opened(stack, svc, clock, me, submitted):
    c, l, _ = submitted
    rid = svc.get_claim(me, c)["lines"][0]["receipts"][0]["receiptId"]
    clock.set(datetime(2027, 11, 4, 9, 0))
    svc.expire_receipts()
    assert err(lambda: svc.receipt_content_url(me, c, l, rid)).code == "RECEIPT_NOT_READY"


def test_expire_for_an_explicit_date(stack, svc, me, submitted):
    assert svc.expire_receipts(date(2027, 11, 4)) == 1
