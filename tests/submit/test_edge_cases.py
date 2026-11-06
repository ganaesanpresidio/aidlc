import pytest

from submit.errors import SubmitError
from submit.service import Caller
from tests.submit.conftest import JPEG, LINE, PNG, new_line, ready_claim, sha, upload

KEY = "idem-key-0001"


def err(fn):
    with pytest.raises(SubmitError) as e:
        fn()
    return e.value


# ---- numbers and text -------------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-0", "1e400", "", [], {}, "1,000"])
def test_text_amounts_that_are_not_numbers(svc, me, claim, bad):
    assert err(lambda: svc.add_line(me, claim, {**LINE, "amount": bad})).status == 422


def test_amounts_as_text_are_accepted(svc, me, claim):
    assert svc.add_line(me, claim, {**LINE, "amount": "250.50"})["amount"] == 250.5


def test_emoji_and_non_latin_text_is_kept(svc, me, claim):
    out = svc.add_line(me, claim, {**LINE, "description": "चाय ☕ और नाश्ता 🍳"})
    assert out["description"] == "चाय ☕ और नाश्ता 🍳"


def test_description_limit_counts_characters_not_bytes(svc, me, claim):
    assert svc.add_line(me, claim, {**LINE, "description": "é" * 500})["description"]
    assert err(lambda: svc.add_line(me, claim, {**LINE, "description": "é" * 501})).status == 422


@pytest.mark.parametrize("d", ["2026-02-29", "2025-02-29", "2026-13-01", "0000-01-01", "2026-1-5"])
def test_impossible_expense_dates(svc, me, claim, d):
    assert err(lambda: svc.add_line(me, claim, {**LINE, "expenseDate": d})).status == 422


def test_leap_day_expense(svc, me, claim):
    assert svc.add_line(me, claim, {**LINE, "expenseDate": "2028-02-29"})["expenseDate"] == "2028-02-29"


# ---- ids, ordering ---------------------------------------------------------------------------------

def test_lines_come_back_in_the_order_they_were_added(svc, clock, me, claim):
    ids = []
    for i in range(5):
        ids.append(new_line(svc, me, claim, description=f"line {i}"))
        clock.advance(milliseconds=5)
    assert [l["lineId"] for l in svc.get_claim(me, claim)["lines"]] == ids


def test_ids_from_the_same_moment_are_still_unique(svc, me, claim):
    ids = {new_line(svc, me, claim) for _ in range(20)}  # the clock does not move
    assert len(ids) == 20


def test_a_line_from_one_claim_cannot_be_reached_through_another(svc, me):
    c1, c2 = svc.create_claim(me)["claimId"], svc.create_claim(me)["claimId"]
    l1 = new_line(svc, me, c1)
    assert err(lambda: svc.update_line(me, c2, l1, {"amount": 5})).status == 404
    assert err(lambda: svc.delete_line(me, c2, l1)).status == 404


def test_a_receipt_from_one_claim_cannot_be_opened_through_another(stack, svc, me):
    c1, l1 = ready_claim(stack, me)
    c2 = svc.create_claim(me)["claimId"]
    rid = svc.get_claim(me, c1)["lines"][0]["receipts"][0]["receiptId"]
    assert err(lambda: svc.receipt_content_url(me, c2, l1, rid)).status == 404


# ---- receipts ------------------------------------------------------------------------------------------

def test_non_object_receipt_request(svc, me, claim):
    l = new_line(svc, me, claim)
    for body in ("x", None, [1], 5):
        assert err(lambda: svc.request_receipt_upload(me, claim, l, body)).status == 422


def test_unknown_receipt_content_is_404(svc, me, claim):
    l = new_line(svc, me, claim)
    assert err(lambda: svc.receipt_content_url(me, claim, l, "NOPE")).status == 404


def test_expired_receipts_free_a_place_on_the_line(stack, svc, clock, me, claim):
    l = new_line(svc, me, claim)
    for i in range(5):
        upload(stack, me, claim, l, PNG + bytes([i]))
    clock.advance(days=366)
    svc.expire_receipts()
    assert svc.request_receipt_upload(me, claim, l, {"mimeType": "image/png", "sizeBytes": 5, "sha256": "a" * 64})["receiptId"]


def test_same_file_twice_on_the_same_line_gets_two_receipts(stack, svc, me, claim):
    l = new_line(svc, me, claim)
    a, b = upload(stack, me, claim, l), upload(stack, me, claim, l)
    assert a["receiptId"] != b["receiptId"] and a["status"] == b["status"] == "CLEAN"


def test_deleting_one_of_two_identical_receipts_keeps_the_other_counted(stack, svc, me):
    c1 = svc.create_claim(me)["claimId"]
    l1 = new_line(svc, me, c1)
    upload(stack, me, c1, l1)
    c2 = svc.create_claim(me)["claimId"]
    l2 = new_line(svc, me, c2)
    r2 = upload(stack, me, c2, l2)
    assert r2["duplicateOf"] == c1
    upload(stack, me, c1, l1)  # a second identical file on claim one
    svc.delete_receipt(me, c1, l1, svc.get_claim(me, c1)["lines"][0]["receipts"][0]["receiptId"])
    assert svc.get_receipt(me, c2, l2, r2["receiptId"])["duplicateOf"] == c1  # still flagged by the remaining one


def test_orphan_duplicate_entries_are_ignored(stack, svc, me):
    c1 = svc.create_claim(me)["claimId"]
    upload(stack, me, c1, new_line(svc, me, c1))
    c2 = svc.create_claim(me)["claimId"]
    l2 = new_line(svc, me, c2)
    stack.table.delete(f"CLAIM#{c1}", "META")  # the other claim vanished (should never happen)
    assert "duplicateOf" not in upload(stack, me, c2, l2)


def test_heic_that_claims_to_be_jpeg_is_rejected(stack, me, claim):
    l = new_line(stack.service, me, claim)
    assert upload(stack, me, claim, l, JPEG[:3] + b"zz" + b"x" * 40, "image/jpeg")["status"] == "CLEAN"  # starts like a JPEG
    assert upload(stack, me, claim, l, b"\x00\x00\x00\x18ftypheic" + b"x" * 40, "image/jpeg")["rejectReason"] == "BAD_TYPE"


def test_a_tiny_one_byte_file_is_rejected_as_not_a_real_type(stack, me, claim):
    l = new_line(stack.service, me, claim)
    assert upload(stack, me, claim, l, b"x", "image/png")["rejectReason"] == "BAD_TYPE"


# ---- idempotency scope ---------------------------------------------------------------------------------

def test_the_same_key_on_different_claims_is_independent(stack, svc, me):
    c1, _ = ready_claim(stack, me)
    c2, _ = ready_claim(stack, me)
    r1, r2 = svc.submit(me, c1, KEY), svc.submit(me, c2, KEY)
    assert r1["claimRef"] != r2["claimRef"]


def test_someone_elses_key_does_not_leak_a_result(stack, svc, me, other):
    c, _ = ready_claim(stack, me)
    svc.submit(me, c, KEY)
    assert err(lambda: svc.submit(other, c, KEY)).status == 404


# ---- batch jobs survive bad data -----------------------------------------------------------------------

def test_expiry_skips_an_orphan_and_still_does_the_rest(stack, svc, clock, me):
    c1, _ = ready_claim(stack, me)
    c2, _ = ready_claim(stack, me)
    stack.table.delete(f"CLAIM#{c1}", "META")  # one claim's record is gone
    clock.advance(days=366)
    assert svc.expire_receipts() == 1  # the other claim is still processed
    assert svc.get_claim(me, c2)["lines"][0]["receipts"][0]["status"] == "EXPIRED"


def test_sweeper_skips_an_orphan_and_still_does_the_rest(stack, svc, clock, me):
    c1 = svc.create_claim(me)["claimId"]
    c2 = svc.create_claim(me)["claimId"]
    for c in (c1, c2):
        l = new_line(svc, me, c)
        svc.request_receipt_upload(me, c, l, {"mimeType": "image/png", "sizeBytes": 5, "sha256": "a" * 64})
    stack.table.delete(f"CLAIM#{c1}", "META")
    clock.advance(hours=2)
    assert svc.sweep_stuck_receipts()["upload_expired"] == 1


def test_scan_result_for_a_vanished_claim_is_a_clean_404(stack, svc, me, claim):
    l = new_line(svc, me, claim)
    s = svc.request_receipt_upload(me, claim, l, {"mimeType": "image/png", "sizeBytes": len(PNG), "sha256": sha(PNG)})
    stack.objects.post(s["fields"], PNG, "image/png")
    svc.handle_upload_event(claim, s["receiptId"])
    stack.table.delete(f"CLAIM#{claim}", "META")
    assert err(lambda: svc.handle_scan_result(claim, s["receiptId"])).status == 404


# ---- races ----------------------------------------------------------------------------------------------

def test_withdraw_racing_with_another_change(stack, svc, me):
    c, _ = ready_claim(stack, me)
    svc.submit(me, c, KEY)
    real = stack.table.put
    done = {"x": False}

    def other_writer_first(item, **kw):
        if not done["x"]:
            done["x"] = True
            stack.table.put = real
            real({**stack.table.get(f"CLAIM#{c}", "META"), "version": 99}, if_version=stack.table.get(f"CLAIM#{c}", "META")["version"])
        return real(item, **kw)

    stack.table.put = other_writer_first
    assert err(lambda: svc.withdraw(me, c)).code == "CONFLICT"


def test_status_event_racing_with_a_withdraw_looks_again(stack, svc, bus, me):
    from aidlc_common.events import envelope
    c, _ = ready_claim(stack, me)
    ref = svc.submit(me, c, KEY)["claimRef"]
    real = stack.table.put
    done = {"x": False}

    def withdraw_first(item, **kw):
        if not done["x"]:
            done["x"] = True
            stack.table.put = real
            svc.withdraw(me, c)  # the employee withdraws between the read and the write
        return real(item, **kw)

    stack.table.put = withdraw_first
    assert svc.on_event(envelope("ClaimApproved", {}, claim_ref=ref)) is False  # withdrawn wins, approval ignored
    assert svc.get_claim(me, c)["status"] == "Withdrawn"


# ---- the table API ------------------------------------------------------------------------------------

def test_in_memory_delete(stack):
    stack.table.put({"PK": "A", "SK": "1"})
    stack.table.delete("A", "1")
    stack.table.delete("A", "1")  # deleting twice is fine
    assert stack.table.get("A", "1") is None


# ---- approve's access over HTTP shape ---------------------------------------------------------------------

def test_internal_header_gives_an_iam_identity_on_the_dev_server(clock, bus):
    import json
    import threading
    import urllib.request

    from submit.factory import build_mock_stack
    from submit.server import serve
    st = build_mock_stack(clock=clock, bus=bus)
    who = Caller("emp1", "G1")
    c, _ = ready_claim(st, who)
    ref = st.service.submit(who, c, KEY)["claimRef"]
    rid = st.service.get_claim(who, c)["lines"][0]["receipts"][0]["receiptId"]
    server = serve(st, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}/internal/v1/receipts/{rid}/access-url",
                                     method="POST", headers={"X-Dev-Internal": "approve"},
                                     data=json.dumps({"claimRef": ref, "requestedBy": "mgr1"}).encode())
        with urllib.request.urlopen(req) as r:
            assert r.status == 200 and json.loads(r.read())["expiresInSeconds"] == 60
        req = urllib.request.Request(f"http://127.0.0.1:{server.server_address[1]}/v1/claims/{c}/lines/x/receipts/{rid}/content",
                                     headers={"X-Dev-User": "emp1", "X-Dev-Grade": "G1"})
        import urllib.error
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.build_opener(NoRedirect).open(req)  # line "x" does not own the receipt: 404
    finally:
        server.shutdown()
        server.server_close()
