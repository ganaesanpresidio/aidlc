import pytest

from submit.errors import SubmitError
from submit.service import Caller
from tests.submit.conftest import LINE, PNG, new_line, sha, upload


def err(fn):
    with pytest.raises(SubmitError) as e:
        fn()
    return e.value


# ---- AC1: create a claim with lines -----------------------------------------------------------------

def test_new_claim_is_an_empty_draft(svc, me):
    c = svc.create_claim(me)
    assert c["status"] == "Draft" and c["lines"] == [] and "claimRef" not in c and len(c["claimId"]) == 26


def test_ac1_two_lines_and_totals_per_currency(svc, me, claim):
    new_line(svc, me, claim, amount=500)
    svc.add_line(me, claim, {**LINE, "amount": 20, "currency": "USD", "amountInr": 1700, "category": "Other"})
    new_line(svc, me, claim, amount=250.5)
    c = svc.get_claim(me, claim)
    assert len(c["lines"]) == 3 and c["totalsByCurrency"] == {"INR": 750.5, "USD": 20}


def test_currency_defaults_to_inr(svc, me, claim):
    assert svc.add_line(me, claim, LINE)["currency"] == "INR"


def test_amounts_stay_exact(svc, me, claim):
    new_line(svc, me, claim, amount=0.1)
    new_line(svc, me, claim, amount=0.2)
    assert svc.get_claim(me, claim)["totalsByCurrency"] == {"INR": 0.3}  # not 0.30000000000000004


def test_user_without_a_grade_cannot_create(svc):
    assert err(lambda: svc.create_claim(Caller("emp9", ""))).status == 403


def test_create_writes_an_audit_event(svc, bus, me):
    svc.create_claim(me)
    [a] = [e for e in bus.of("Audit") if e["payload"]["action"] == "claim.create"]
    assert a["payload"]["actor"] == "emp1"


# ---- line validation -------------------------------------------------------------------------------

@pytest.mark.parametrize("change", [
    {"category": "Yacht"}, {"category": None}, {"category": ""},
    {"amount": 0}, {"amount": -1}, {"amount": "abc"}, {"amount": True}, {"amount": None},
    {"amount": float("nan")}, {"amount": float("inf")}, {"amount": 12.345}, {"amount": 100000000},
    {"currency": "rupees"}, {"currency": "inr"}, {"currency": 5},
    {"expenseDate": "2026-02-30"}, {"expenseDate": "03/11/2026"}, {"expenseDate": None}, {"expenseDate": ""},
    {"description": ""}, {"description": "   "}, {"description": None}, {"description": "x" * 501},
    {"quantity": -2}, {"quantity": "many"}, {"exceptionReason": "x" * 501}, {"exceptionReason": 7},
])
def test_bad_lines_are_422(svc, me, claim, change):
    e = err(lambda: svc.add_line(me, claim, {**LINE, **change}))
    assert e.status == 422 and e.code == "INVALID_REQUEST"


def test_boundary_amounts_are_accepted(svc, me, claim):
    assert svc.add_line(me, claim, {**LINE, "amount": 0.01})["amount"] == 0.01
    assert svc.add_line(me, claim, {**LINE, "amount": 99999999.99})["amount"] == 99999999.99
    assert len(svc.add_line(me, claim, {**LINE, "description": "x" * 500})["description"]) == 500


def test_description_is_trimmed(svc, me, claim):
    assert svc.add_line(me, claim, {**LINE, "description": "  lunch  "})["description"] == "lunch"


def test_foreign_currency_needs_an_inr_amount(svc, me, claim):
    assert err(lambda: svc.add_line(me, claim, {**LINE, "currency": "USD"})).status == 422
    assert svc.add_line(me, claim, {**LINE, "currency": "USD", "amountInr": 1700})["amountInr"] == 1700


def test_every_category_is_accepted(svc, me, claim):
    for cat in ("Travel", "Accommodation", "Meals", "Mileage", "Other"):
        assert svc.add_line(me, claim, {**LINE, "category": cat})["category"] == cat


def test_body_must_be_an_object(svc, me, claim):
    assert err(lambda: svc.add_line(me, claim, ["x"])).status == 422
    assert err(lambda: svc.add_line(me, claim, None)).status == 422


def test_line_limit(svc, me, claim):
    svc.settings.max_lines = 3
    for _ in range(3):
        new_line(svc, me, claim)
    assert err(lambda: new_line(svc, me, claim)).code == "LINE_LIMIT"


# ---- update and delete ------------------------------------------------------------------------------

def test_update_changes_only_what_was_sent(svc, me, claim):
    l = new_line(svc, me, claim, amount=800)
    out = svc.update_line(me, claim, l, {"amount": 900})
    assert out["amount"] == 900 and out["description"] == "lunch" and out["category"] == "Meals"


def test_update_is_validated_after_merging(svc, me, claim):
    l = new_line(svc, me, claim)
    assert err(lambda: svc.update_line(me, claim, l, {"amount": -5})).status == 422
    assert svc.get_claim(me, claim)["lines"][0]["amount"] == 800  # unchanged


def test_switching_to_foreign_currency_needs_inr_amount(svc, me, claim):
    l = new_line(svc, me, claim)
    assert err(lambda: svc.update_line(me, claim, l, {"currency": "USD"})).status == 422
    assert svc.update_line(me, claim, l, {"currency": "USD", "amountInr": 100})["amountInr"] == 100


def test_switching_back_to_inr_drops_the_inr_amount(svc, me, claim):
    l = new_line(svc, me, claim, currency="USD", amountInr=100)
    assert "amountInr" not in svc.update_line(me, claim, l, {"currency": "INR"})


def test_update_and_delete_unknown_line(svc, me, claim):
    assert err(lambda: svc.update_line(me, claim, "NOPE", {"amount": 1})).status == 404
    assert err(lambda: svc.delete_line(me, claim, "NOPE")).status == 404


def test_delete_line(svc, me, claim):
    l = new_line(svc, me, claim)
    svc.delete_line(me, claim, l)
    assert svc.get_claim(me, claim)["lines"] == []


def test_delete_line_removes_its_receipts_and_files(stack, svc, me, claim):
    l = new_line(svc, me, claim)
    r = upload(stack, me, claim, l)
    assert stack.objects.exists("receipts", f"{claim}/{r['receiptId']}")
    svc.delete_line(me, claim, l)
    assert not stack.objects.exists("receipts", f"{claim}/{r['receiptId']}")
    assert stack.table.query(f"CLAIM#{claim}", "RCPT#") == []
    assert stack.table.query(f"DUP#emp1#{sha(PNG)}") == []


# ---- ownership (X4) --------------------------------------------------------------------------------

def test_other_peoples_claims_look_missing(svc, me, other, claim):
    l = new_line(svc, me, claim)
    for call in (lambda: svc.get_claim(other, claim), lambda: svc.add_line(other, claim, LINE),
                 lambda: svc.update_line(other, claim, l, {"amount": 5}), lambda: svc.delete_line(other, claim, l),
                 lambda: svc.submit(other, claim, "idem-key-0001"), lambda: svc.withdraw(other, claim),
                 lambda: svc.request_receipt_upload(other, claim, l, {})):
        e = err(call)
        assert e.status == 404 and e.code == "NOT_FOUND"  # 404, never 403


@pytest.mark.parametrize("bad_id", ["", "short", "x" * 26, "x" * 27, None, 5, "../../etc/passwd"])
def test_made_up_claim_ids_are_404(svc, me, bad_id):
    assert err(lambda: svc.get_claim(me, bad_id)).status == 404


# ---- listing ---------------------------------------------------------------------------------------

def test_list_shows_only_my_claims_newest_first(svc, clock, me, other):
    ids = []
    for _ in range(3):
        ids.append(svc.create_claim(me)["claimId"])
        clock.advance(seconds=1)
    svc.create_claim(other)
    assert [c["claimId"] for c in svc.list_claims(me)["items"]] == ids[::-1]


def test_list_filter_and_paging(svc, clock, me):
    for _ in range(5):
        svc.create_claim(me)
        clock.advance(seconds=1)
    page1 = svc.list_claims(me, limit=2)
    assert len(page1["items"]) == 2 and "nextCursor" in page1
    page2 = svc.list_claims(me, cursor=page1["nextCursor"], limit=2)
    page3 = svc.list_claims(me, cursor=page2["nextCursor"], limit=2)
    seen = [c["claimId"] for p in (page1, page2, page3) for c in p["items"]]
    assert len(seen) == 5 and len(set(seen)) == 5 and "nextCursor" not in page3
    assert svc.list_claims(me, status="Submitted")["items"] == []


@pytest.mark.parametrize("kw", [{"status": "Done"}, {"limit": 0}, {"limit": 101}])
def test_list_bad_params(svc, me, kw):
    assert err(lambda: svc.list_claims(me, **kw)).status == 422


def test_list_of_nothing(svc, me):
    assert svc.list_claims(me) == {"items": []}


# ---- editing a submitted claim (X2) ---------------------------------------------------------------

def test_submitted_claim_cannot_be_edited(stack, svc, me):
    from tests.submit.conftest import ready_claim
    c, l = ready_claim(stack, me)
    svc.submit(me, c, "idem-key-0001")
    for call in (lambda: svc.add_line(me, c, LINE), lambda: svc.update_line(me, c, l, {"amount": 1}),
                 lambda: svc.delete_line(me, c, l), lambda: svc.request_receipt_upload(me, c, l, {})):
        e = err(call)
        assert e.status == 409 and e.code == "CLAIM_NOT_EDITABLE"


# ---- concurrency -----------------------------------------------------------------------------------

def test_two_edits_at_once_one_loses(stack, svc, me, claim, monkeypatch):
    new_line(svc, me, claim)
    stale = stack.table.get(f"CLAIM#{claim}", "META")
    svc.add_line(me, claim, LINE)  # moves the claim version on
    monkeypatch.setattr(svc, "_meta", lambda *a, **k: stale)  # the second caller read the old version
    e = err(lambda: svc.add_line(me, claim, LINE))
    assert e.status == 409 and e.code == "CONFLICT"
