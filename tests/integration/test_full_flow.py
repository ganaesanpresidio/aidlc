"""Both units together on the mock backend: the journey, the contracts, the audit trail, no personal data."""

import hashlib
import json
import logging
from datetime import datetime

import pytest
import yaml
from jsonschema import Draft202012Validator

from aidlc_common.events import envelope
from policy.api import Auth as PAuth
from policy.api import Request as PReq
from policy.api import handle as policy_handle
from submit.api import Auth, Request, handle
from submit.service import Caller
from tests.conftest import EXAMPLE_RULES, ROOT
from tests.submit.conftest import JPEG, LINE, PNG, new_line, ready_claim, upload

POLICY_SPEC = yaml.safe_load((ROOT / "aidlc-docs/design/policy/api/openapi.yaml").read_text())
SUBMIT_SPEC = yaml.safe_load((ROOT / "aidlc-docs/design/submit/api/openapi.yaml").read_text())


def check(spec, name, body):
    """Validate a body against a named schema in an OpenAPI file."""
    schema = {"$ref": f"#/components/schemas/{name}", "components": spec["components"]}
    errors = [e.message for e in Draft202012Validator(schema).iter_errors(body)]
    assert errors == [], errors


def holders(**people):
    return {r: {"id": w, "grade": g} for r, (w, g) in people.items()}


@pytest.fixture
def me():
    return Caller("emp-asha", "G1")


# ---- the whole journey -------------------------------------------------------------------------------

def test_submit_then_route_then_approve_then_pay(stack, svc, bus, me):
    c = svc.create_claim(me)["claimId"]
    meals = new_line(svc, me, c, amount=1200, category="Meals", description="team lunch")
    stay = svc.add_line(me, c, {**LINE, "category": "Accommodation", "amount": 12000, "quantity": 2,
                                "description": "hotel"})["lineId"]
    upload(stack, me, c, meals)
    upload(stack, me, c, stay, JPEG, "image/jpeg")
    out = svc.submit(me, c, "idem-key-0001")
    assert out["totalInr"] == 13200

    # `approve` reads only the event, then asks policy for the chain
    [ev] = bus.of("ClaimSubmitted")
    p = ev["payload"]
    routed = stack.policy_service.route({
        "claimRef": ev["claimRef"], "rulesVersion": ev["rulesVersion"], "submitter": p["submitterId"],
        "grade": p["gradeOfSubmitter"], "totalInr": p["totalInr"], "requiresException": p["requiresException"],
        "roleHolders": holders(LINE_MANAGER=("mgr-ravi", "G2"), DEPARTMENT_HEAD=("head-dev", "G3"))})
    assert routed["tier"] == "T2" and [c_["approver"] for c_ in routed["chain"]] == ["mgr-ravi", "head-dev"]

    bus.publish(envelope("ClaimApproved", {"totalInr": 13200}, claim_ref=ev["claimRef"]))
    assert svc.get_claim(me, c)["status"] == "Approved"
    bus.publish(envelope("PayoutIssued", {}, claim_ref=ev["claimRef"]))
    assert svc.get_claim(me, c)["status"] == "Paid"


def test_exception_claim_gets_the_finance_controller(stack, svc, bus, me):
    c, _ = ready_claim(stack, me, amount=2000, category="Meals", exceptionReason="client dinner")
    svc.submit(me, c, "idem-key-0001")
    ev = bus.of("ClaimSubmitted")[0]
    routed = stack.policy_service.route({
        "claimRef": ev["claimRef"], "submitter": "emp-asha", "grade": "G1", "totalInr": ev["payload"]["totalInr"],
        "requiresException": ev["payload"]["requiresException"],
        "roleHolders": holders(LINE_MANAGER=("mgr", "G2"), FINANCE_CONTROLLER=("fin", "G3"))})
    assert [x["role"] for x in routed["chain"]] == ["LINE_MANAGER", "FINANCE_CONTROLLER"]


def test_approver_who_is_the_submitter_is_blocked(stack, svc, bus):
    boss = Caller("mgr-ravi", "G2")
    c, _ = ready_claim(stack, boss, amount=500)
    svc.submit(boss, c, "idem-key-0001")
    ev = bus.of("ClaimSubmitted")[0]
    routed = stack.policy_service.route({
        "claimRef": ev["claimRef"], "submitter": "mgr-ravi", "grade": "G2", "totalInr": 500, "requiresException": False,
        "roleHolders": holders(LINE_MANAGER=("mgr-ravi", "G2"))})
    assert routed["blocked"]["code"] == "SOD-1"


# ---- rules changes while claims are in flight ------------------------------------------------------------

def test_a_new_rules_version_applies_from_its_date_and_old_claims_keep_theirs(stack, svc, clock, bus, me):
    rules = yaml.safe_load(EXAMPLE_RULES.read_text())
    rules["effective_from"] = "2026-11-10"
    rules["category_limits"]["Meals"]["G1"] = 500  # stricter from the 10th
    stack.policy_service.publish(rules, actor="fin", groups=["finance-admin"], idempotency_key="key-v2-00001")

    c1, _ = ready_claim(stack, me, amount=800)
    assert svc.submit(me, c1, "idem-key-0001")["status"] == "Submitted"  # v1 still in force today
    assert bus.of("ClaimSubmitted")[0]["rulesVersion"] == 1

    clock.set(datetime(2026, 11, 10, 9, 0))
    c2, l2 = ready_claim(stack, me, amount=800, expenseDate="2026-11-09")
    with pytest.raises(Exception) as e:
        svc.submit(me, c2, "idem-key-0002")
    assert "POLICY_VIOLATIONS" in str(e.value.code)
    ref1 = bus.of("ClaimSubmitted")[0]["claimRef"]
    again = stack.policy_service.route({"claimRef": ref1, "rulesVersion": 1, "submitter": "emp-asha", "grade": "G1",
                                        "totalInr": 800, "requiresException": False,
                                        "roleHolders": holders(LINE_MANAGER=("mgr", "G2"))})
    assert again["rulesVersion"] == 1  # an old claim is still routed by its own rules


# ---- the contracts are really followed -----------------------------------------------------------------------

def test_submit_sends_policy_exactly_what_the_policy_contract_says(stack, svc, me):
    seen = []
    real = stack.policy_client.evaluate

    def spy(body):
        seen.append(body)
        return real(body)

    stack.policy_client.evaluate = spy
    c = svc.create_claim(me)["claimId"]
    new_line(svc, me, c, amount=20, currency="USD", amountInr=1700, category="Other")
    svc.add_line(me, c, {**LINE, "category": "Mileage", "amount": 600, "quantity": 50, "exceptionReason": "site visit"})
    upload(stack, me, c, svc.get_claim(me, c)["lines"][0]["lineId"])
    try:
        svc.submit(me, c, "idem-key-0001")
    except Exception:
        pass
    assert seen, "policy was never called"
    check(POLICY_SPEC, "EvaluateRequest", seen[0])
    result = real(seen[0])
    check(POLICY_SPEC, "EvaluateResult", result)


def test_policy_answers_match_its_contract(stack):
    svc = stack.policy_service
    from tests.policy.conftest import evaluate_body, line, route_body
    check(POLICY_SPEC, "EvaluateResult", svc.evaluate(evaluate_body([line(amount=2000), line(lineId="L2", amount=1000, hasReceipt=False, category="Other")])))
    check(POLICY_SPEC, "RouteResult", svc.route(route_body(total=20000, LINE_MANAGER=("Ravi", "G2"), DEPARTMENT_HEAD=("Dev", "G3"))))
    check(POLICY_SPEC, "RouteResult", svc.route(route_body(total=20000, submitter="Ravi", grade="G2", LINE_MANAGER=("Ravi", "G2"))))
    check(POLICY_SPEC, "RulesVersion", policy_handle(svc, PReq("GET", "/v1/policy/rules", auth=PAuth("jwt", "u"))).body)
    check(POLICY_SPEC, "Error", policy_handle(svc, PReq("GET", "/v1/policy/rules", query={"effectiveOn": "x"}, auth=PAuth("jwt", "u"))).body)


def test_submit_answers_match_its_contract(stack, svc, me):
    ME = Auth(kind="jwt", sub=me.sub, grade=me.grade)
    call = lambda m, p, b=None, h=None, q=None: handle(svc, Request(m, p, q or {}, h or {}, b, ME))
    cid = call("POST", "/v1/claims").body["claimId"]
    lid = call("POST", f"/v1/claims/{cid}/lines", {**LINE, "amount": 1500}).body
    check(SUBMIT_SPEC, "Line", lid)
    slot = call("POST", f"/v1/claims/{cid}/lines/{lid['lineId']}/receipts", {"mimeType": "image/png", "sizeBytes": len(PNG),
                                                                              "sha256": hashlib.sha256(PNG).hexdigest()}).body
    check(SUBMIT_SPEC, "ReceiptUploadSlot", slot)
    stack.objects.post(slot["fields"], PNG, "image/png")
    svc.handle_upload_event(cid, slot["receiptId"])
    check(SUBMIT_SPEC, "Receipt", call("GET", f"/v1/claims/{cid}/lines/{lid['lineId']}/receipts/{slot['receiptId']}").body)
    svc.handle_scan_result(cid, slot["receiptId"])
    check(SUBMIT_SPEC, "Claim", call("GET", f"/v1/claims/{cid}").body)
    check(SUBMIT_SPEC, "ClaimPage", call("GET", "/v1/claims").body)
    check(SUBMIT_SPEC, "Claim", call("POST", f"/v1/claims/{cid}/submit", h={"idempotency-key": "idem-key-0001"}).body)
    check(SUBMIT_SPEC, "Error", call("GET", "/v1/claims/" + "A" * 26).body)
    check(SUBMIT_SPEC, "Error", call("POST", f"/v1/claims/{cid}/lines", LINE).body)


def test_rejected_and_duplicate_receipts_match_the_contract(stack, svc, me):
    from tests.submit.conftest import EICAR
    c = svc.create_claim(me)["claimId"]
    l = new_line(svc, me, c)
    check(SUBMIT_SPEC, "Receipt", upload(stack, me, c, l, EICAR))
    c2 = svc.create_claim(me)["claimId"]
    l2 = new_line(svc, me, c2)
    upload(stack, me, c, l, PNG)
    check(SUBMIT_SPEC, "Receipt", upload(stack, me, c2, l2, PNG))
    check(SUBMIT_SPEC, "Receipt", upload(stack, me, c2, l2, b"MZ" + b"0" * 30, "image/png"))


# ---- audit, privacy, logs -----------------------------------------------------------------------------------

SECRET_WORDS = ["Kumar", "dinner with the board", "ACME-secret-vendor"]


def test_no_personal_data_in_events_or_logs(stack, svc, bus, me, caplog):
    with caplog.at_level(logging.DEBUG):
        c = svc.create_claim(me)["claimId"]
        l = svc.add_line(me, c, {**LINE, "description": "dinner with the board, Mr Kumar", "category": "Other",
                                 "amount": 1500, "exceptionReason": "ACME-secret-vendor"})["lineId"]
        upload(stack, me, c, l)
        svc.submit(me, c, "idem-key-0001")
        svc.flush_pending()
    everything = json.dumps(bus.events) + caplog.text
    for word in SECRET_WORDS:
        assert word not in everything


def test_every_action_is_audited(stack, svc, bus, me):
    c = svc.create_claim(me)["claimId"]
    l = new_line(svc, me, c, amount=1500, category="Other")
    r = upload(stack, me, c, l)
    svc.delete_receipt(me, c, l, r["receiptId"])
    upload(stack, me, c, l, b"%PDF-1.4" + b"y" * 40, "application/pdf")
    svc.update_line(me, c, l, {"amount": 1600})
    svc.submit(me, c, "idem-key-0001")
    svc.withdraw(me, c)
    actions = [a["payload"]["action"] for a in bus.of("Audit")]
    for expected in ("claim.create", "line.add", "receipt.request", "receipt.stored", "receipt.delete", "line.update",
                     "claim.submit", "claim.withdraw"):
        assert expected in actions, expected
    for a in bus.of("Audit"):
        assert a["payload"]["actor"] and a["occurredAt"]


def test_audit_events_never_contain_file_content_or_names(stack, svc, bus, me):
    c = svc.create_claim(me)["claimId"]
    l = new_line(svc, me, c, description="Mr Kumar")
    upload(stack, me, c, l)
    text = json.dumps(bus.of("Audit"))
    assert "Kumar" not in text and "PNG" not in text
