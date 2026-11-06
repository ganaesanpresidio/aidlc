import pytest

from submit.api import Auth, Request, handle
from tests.submit.conftest import LINE, PNG, sha

ME = Auth(kind="jwt", sub="emp1", grade="G1")
OTHER = Auth(kind="jwt", sub="emp2", grade="G1")
APPROVE = Auth(kind="iam", principal="approve")


@pytest.fixture
def call(svc):
    def _call(method, path, auth=ME, body=None, query=None, headers=None):
        return handle(svc, Request(method, path, query or {}, headers or {}, body, auth))
    return _call


def make_claim(call):
    return call("POST", "/v1/claims").body["claimId"]


# ---- the AC1 journey over the API ----------------------------------------------------------------------

def test_create_get_list(call):
    r = call("POST", "/v1/claims")
    assert r.status == 201 and r.body["status"] == "Draft"
    cid = r.body["claimId"]
    assert call("GET", f"/v1/claims/{cid}").body["claimId"] == cid
    assert [c["claimId"] for c in call("GET", "/v1/claims").body["items"]] == [cid]
    assert call("GET", "/v1/claims", query={"status": "Draft", "limit": "1"}).status == 200


def test_line_crud(call):
    cid = make_claim(call)
    r = call("POST", f"/v1/claims/{cid}/lines", body=LINE)
    assert r.status == 201
    lid = r.body["lineId"]
    assert call("PATCH", f"/v1/claims/{cid}/lines/{lid}", body={"amount": 900}).body["amount"] == 900
    d = call("DELETE", f"/v1/claims/{cid}/lines/{lid}")
    assert d.status == 204 and d.body is None
    assert call("GET", f"/v1/claims/{cid}").body["lines"] == []


def test_receipt_flow_and_302(svc, stack, call):
    cid = make_claim(call)
    lid = call("POST", f"/v1/claims/{cid}/lines", body=LINE).body["lineId"]
    slot = call("POST", f"/v1/claims/{cid}/lines/{lid}/receipts",
                body={"mimeType": "image/png", "sizeBytes": len(PNG), "sha256": sha(PNG)})
    assert slot.status == 201 and slot.body["uploadUrl"]
    rid = slot.body["receiptId"]
    stack.objects.post(slot.body["fields"], PNG, "image/png")
    svc.handle_upload_event(cid, rid)
    svc.handle_scan_result(cid, rid)
    got = call("GET", f"/v1/claims/{cid}/lines/{lid}/receipts/{rid}")
    assert got.status == 200 and got.body["status"] == "CLEAN"
    c = call("GET", f"/v1/claims/{cid}/lines/{lid}/receipts/{rid}/content")
    assert c.status == 302 and c.headers["location"].startswith("mock://receipts/")
    assert call("DELETE", f"/v1/claims/{cid}/lines/{lid}/receipts/{rid}").status == 204


def test_submit_and_withdraw(stack, call):
    from submit.service import Caller
    from tests.submit.conftest import ready_claim
    cid, _ = ready_claim(stack, Caller("emp1", "G1"))
    r = call("POST", f"/v1/claims/{cid}/submit", headers={"idempotency-key": "idem-key-0001"})
    assert r.status == 200 and r.body["claimRef"] == "CLM-2026-000001"
    assert call("POST", f"/v1/claims/{cid}/withdraw").body["status"] == "Withdrawn"


def test_submit_without_a_key_is_422(stack, call):
    cid = make_claim(call)
    assert call("POST", f"/v1/claims/{cid}/submit").status == 422


def test_policy_violations_come_back_as_422_with_details(call):
    cid = make_claim(call)
    call("POST", f"/v1/claims/{cid}/lines", body={**LINE, "amount": 2000, "category": "Other"})
    r = call("POST", f"/v1/claims/{cid}/submit", headers={"idempotency-key": "idem-key-0001"})
    assert r.status == 422 and r.body["code"] == "POLICY_VIOLATIONS" and r.body["details"][0]["message"] == "Add a receipt"


# ---- auth ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("method,path", [("POST", "/v1/claims"), ("GET", "/v1/claims"), ("GET", "/v1/claims/" + "A" * 26),
                                         ("POST", "/v1/claims/" + "A" * 26 + "/submit")])
def test_no_identity_is_401(call, method, path):
    assert call(method, path, auth=None).status == 401


def test_internal_callers_cannot_use_employee_routes(call):
    assert call("GET", "/v1/claims", auth=Auth(kind="iam", principal="approve")).status == 401


def test_a_user_without_an_id_is_401(call):
    assert call("GET", "/v1/claims", auth=Auth(kind="jwt", sub="")).status == 401


def test_x4_other_users_claim_is_404(call):
    cid = make_claim(call)
    assert call("GET", f"/v1/claims/{cid}", auth=OTHER).status == 404
    assert call("POST", f"/v1/claims/{cid}/lines", auth=OTHER, body=LINE).status == 404


# ---- internal access-url -----------------------------------------------------------------------------

def _submitted(stack):
    from submit.service import Caller
    from tests.submit.conftest import ready_claim
    who = Caller("emp1", "G1")
    cid, _ = ready_claim(stack, who)
    ref = stack.service.submit(who, cid, "idem-key-0001")["claimRef"]
    return ref, stack.service.get_claim(who, cid)["lines"][0]["receipts"][0]["receiptId"]


def test_approve_can_get_an_access_url(stack, call):
    ref, rid = _submitted(stack)
    r = call("POST", f"/internal/v1/receipts/{rid}/access-url", auth=APPROVE, body={"claimRef": ref, "requestedBy": "mgr1"})
    assert r.status == 200 and r.body["expiresInSeconds"] == 60


@pytest.mark.parametrize("auth,status", [(None, 401), (ME, 403), (Auth(kind="iam", principal="payout"), 403),
                                         (Auth(kind="iam", principal="submit"), 403)])
def test_access_url_is_for_approve_only(stack, call, auth, status):
    ref, rid = _submitted(stack)
    assert call("POST", f"/internal/v1/receipts/{rid}/access-url", auth=auth,
                body={"claimRef": ref, "requestedBy": "mgr1"}).status == status


@pytest.mark.parametrize("body", [None, {}, {"claimRef": "x"}, {"requestedBy": "m"}, {"claimRef": 1, "requestedBy": "m"},
                                  {"claimRef": "x", "requestedBy": ""}, "text"])
def test_access_url_bad_body(stack, call, body):
    _, rid = _submitted(stack)
    assert call("POST", f"/internal/v1/receipts/{rid}/access-url", auth=APPROVE, body=body).status == 422


def test_access_url_wrong_method(stack, call):
    _, rid = _submitted(stack)
    assert call("GET", f"/internal/v1/receipts/{rid}/access-url", auth=APPROVE).status == 405


# ---- plumbing ----------------------------------------------------------------------------------------

@pytest.mark.parametrize("method,path,allow", [("DELETE", "/v1/claims", "GET, POST"), ("POST", "/v1/claims/" + "A" * 26, "GET"),
                                               ("GET", "/v1/claims/" + "A" * 26 + "/submit", "POST"),
                                               ("PUT", "/v1/claims/" + "A" * 26 + "/lines", "POST")])
def test_wrong_method_is_405(call, method, path, allow):
    r = call(method, path)
    assert r.status == 405 and r.headers["allow"] == allow


def test_unknown_route_is_404(call):
    assert call("GET", "/v1/nothing").status == 404
    assert call("GET", "/v1/claims/abc/def/ghi").status == 404


def test_bad_limit_is_422(call):
    assert call("GET", "/v1/claims", query={"limit": "lots"}).status == 422


def test_request_id_is_echoed_and_trailing_slash_ok(call):
    r = call("GET", "/v1/claims/", headers={"x-request-id": "r-1"})
    assert r.status == 200 and r.headers["x-request-id"] == "r-1"


def test_unexpected_errors_are_500_without_details(svc, call, monkeypatch):
    monkeypatch.setattr(svc, "list_claims", lambda *a, **k: 1 / 0)
    r = call("GET", "/v1/claims")
    assert r.status == 500 and r.body == {"code": "INTERNAL", "message": "Something went wrong"}


def test_error_bodies_follow_the_contract(call):
    r = call("GET", "/v1/claims/" + "A" * 26)
    assert set(r.body) == {"code", "message"}
