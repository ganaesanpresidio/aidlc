import pytest

from submit.errors import SubmitError
from submit.objects import UploadRejected
from tests.submit.conftest import EICAR, HEIC, JPEG, PDF, PNG, new_line, sha, upload


def err(fn):
    with pytest.raises(SubmitError) as e:
        fn()
    return e.value


def slot(svc, who, claim, line, content=PNG, mime="image/png", **kw):
    return svc.request_receipt_upload(who, claim, line, {"mimeType": mime, "sizeBytes": len(content),
                                                          "sha256": sha(content), **kw})


@pytest.fixture
def line(svc, me, claim):
    return new_line(svc, me, claim)


# ---- AC2: attach a receipt ---------------------------------------------------------------------------

@pytest.mark.parametrize("content,mime", [(PNG, "image/png"), (JPEG, "image/jpeg"), (PDF, "application/pdf"),
                                           (HEIC, "image/heic")])
def test_ac2_each_allowed_type_ends_clean(stack, me, claim, line, content, mime):
    r = upload(stack, me, claim, line, content, mime)
    assert r["status"] == "CLEAN" and r["mimeType"] == mime and r["sizeBytes"] == len(content)


def test_clean_file_moves_out_of_quarantine(stack, me, claim, line):
    r = upload(stack, me, claim, line)
    key = f"{claim}/{r['receiptId']}"
    assert stack.objects.exists("receipts", key) and not stack.objects.exists("quarantine", key)


def test_receipt_shows_on_the_line(svc, stack, me, claim, line):
    upload(stack, me, claim, line)
    assert [r["status"] for r in svc.get_claim(me, claim)["lines"][0]["receipts"]] == ["CLEAN"]


def test_ten_megabytes_exactly_is_allowed(stack, svc, me, claim, line):
    s = svc.request_receipt_upload(me, claim, line, {"mimeType": "application/pdf", "sizeBytes": 10 * 1024 * 1024,
                                                      "sha256": "a" * 64})
    assert s["receiptId"] and s["expiresInSeconds"] == 300


def test_slot_carries_the_upload_conditions(svc, me, claim, line):
    s = slot(svc, me, claim, line)
    assert s["fields"]["Content-Type"] == "image/png" and s["fields"]["x-amz-checksum-sha256"] == sha(PNG)


def test_receipt_starts_pending_then_scanning(stack, svc, me, claim, line):
    s = slot(svc, me, claim, line)
    get = lambda: svc.get_receipt(me, claim, line, s["receiptId"])["status"]
    assert get() == "PENDING_UPLOAD"
    stack.objects.post(s["fields"], PNG, "image/png")
    svc.handle_upload_event(claim, s["receiptId"])
    assert get() == "SCANNING"
    svc.handle_scan_result(claim, s["receiptId"])
    assert get() == "CLEAN"


# ---- AC4: wrong file type -----------------------------------------------------------------------------

@pytest.mark.parametrize("mime", ["application/x-msdownload", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                  "text/plain", "image/gif", "", None, 5])
def test_ac4_wrong_type_refused_and_nothing_stored(stack, svc, me, claim, line, mime):
    e = err(lambda: svc.request_receipt_upload(me, claim, line, {"mimeType": mime, "sizeBytes": 10, "sha256": "a" * 64}))
    assert e.status == 422 and e.code == "FILE_TYPE_NOT_ALLOWED" and "JPEG, PNG, HEIC or PDF" in e.message
    assert stack.table.query(f"CLAIM#{claim}", "RCPT#") == []


def test_a_lying_file_is_caught_by_its_first_bytes(stack, me, claim, line):
    r = upload(stack, me, claim, line, content=b"MZ" + b"\x00" * 60, mime="image/png")  # an .exe called a PNG
    assert r["status"] == "REJECTED" and r["rejectReason"] == "BAD_TYPE"
    assert not stack.objects.buckets["quarantine"] and not stack.objects.buckets["receipts"]


def test_a_png_declared_as_pdf_is_rejected(stack, me, claim, line):
    assert upload(stack, me, claim, line, content=PNG, mime="application/pdf")["rejectReason"] == "BAD_TYPE"


# ---- AC5: size and count -------------------------------------------------------------------------------

def test_ac5_too_large(svc, me, claim, line):
    e = err(lambda: svc.request_receipt_upload(me, claim, line, {"mimeType": "image/png", "sizeBytes": 10 * 1024 * 1024 + 1,
                                                                 "sha256": "a" * 64}))
    assert e.status == 422 and e.code == "FILE_TOO_LARGE" and "10 MB" in e.message


@pytest.mark.parametrize("size", [0, -1, 1.5, "10", True, None])
def test_bad_sizes(svc, me, claim, line, size):
    assert err(lambda: svc.request_receipt_upload(me, claim, line, {"mimeType": "image/png", "sizeBytes": size,
                                                                    "sha256": "a" * 64})).status == 422


@pytest.mark.parametrize("digest", ["", "abc", "g" * 64, "a" * 63, "a" * 65, None, 7])
def test_bad_checksums(svc, me, claim, line, digest):
    assert err(lambda: svc.request_receipt_upload(me, claim, line, {"mimeType": "image/png", "sizeBytes": 5,
                                                                    "sha256": digest})).status == 422


def test_ac5_sixth_receipt_refused(stack, svc, me, claim, line):
    for i in range(5):
        upload(stack, me, claim, line, PNG + bytes([i]))
    e = err(lambda: slot(svc, me, claim, line, PNG + b"6"))
    assert e.status == 422 and e.code == "RECEIPT_LIMIT"


def test_a_rejected_receipt_does_not_use_a_place(stack, svc, me, claim, line):
    for i in range(4):
        upload(stack, me, claim, line, PNG + bytes([i]))
    upload(stack, me, claim, line, EICAR + b"1", "image/png")  # rejected
    assert slot(svc, me, claim, line, PNG + b"new")["receiptId"]  # still room for a 5th good one


def test_the_store_enforces_the_conditions_too(stack, svc, me, claim, line):
    s = slot(svc, me, claim, line)
    with pytest.raises(UploadRejected):
        stack.objects.post(s["fields"], PNG + b"tampered", "image/png")       # wrong checksum
    with pytest.raises(UploadRejected):
        stack.objects.post(s["fields"], PNG, "application/pdf")               # wrong type
    with pytest.raises(UploadRejected):
        stack.objects.post({**s["fields"], "key": "someone/else"}, PNG, "image/png")  # someone else's key
    with pytest.raises(UploadRejected):
        stack.objects.post({**s["fields"], "token": "bogus"}, PNG, "image/png")
    with pytest.raises(UploadRejected):
        stack.objects.post(s["fields"], b"", "image/png")                     # empty


def test_store_rejects_a_file_over_the_range(stack, svc, me, claim, line):
    s = slot(svc, me, claim, line)
    stack.objects._slots[s["fields"]["token"]]["max"] = 10
    with pytest.raises(UploadRejected):
        stack.objects.post(s["fields"], PNG, "image/png")


def test_unknown_line_or_receipt(svc, me, claim, line):
    assert err(lambda: slot(svc, me, claim, "NOPE")).status == 404
    assert err(lambda: svc.get_receipt(me, claim, line, "NOPE")).status == 404
    assert err(lambda: svc.delete_receipt(me, claim, line, "NOPE")).status == 404


def test_receipt_must_be_asked_for_through_its_own_line(svc, stack, me, claim, line):
    other_line = new_line(svc, me, claim)
    r = upload(stack, me, claim, line)
    assert err(lambda: svc.get_receipt(me, claim, other_line, r["receiptId"])).status == 404


# ---- AC6: malware --------------------------------------------------------------------------------------

def test_ac6_malware_is_not_stored_and_is_audited(stack, bus, me, claim, line):
    r = upload(stack, me, claim, line, EICAR, "image/png")
    assert r["status"] == "REJECTED" and r["rejectReason"] == "MALWARE"
    assert not stack.objects.buckets["quarantine"] and not stack.objects.buckets["receipts"]
    sec = [e for e in bus.of("Audit") if e["payload"]["action"] == "receipt.malware"]
    assert len(sec) == 1 and sec[0]["payload"]["outcome"] == "blocked"
    assert not bus.of("ReceiptStored")


def test_malware_inside_a_pdf_is_caught(stack, me, claim, line):
    assert upload(stack, me, claim, line, b"%PDF-1.4\n" + EICAR, "application/pdf")["rejectReason"] == "MALWARE"


def test_scan_that_has_not_finished_changes_nothing(stack, svc, me, claim, line):
    s = slot(svc, me, claim, line)
    stack.objects.post(s["fields"], PNG, "image/png")
    stack.scanner.stalled.add(f"{claim}/{s['receiptId']}")
    svc.handle_upload_event(claim, s["receiptId"])
    assert svc.handle_scan_result(claim, s["receiptId"]) == "SCANNING"
    assert svc.get_receipt(me, claim, line, s["receiptId"])["status"] == "SCANNING"


def test_scanner_failure_rejects_the_file(stack, svc, me, claim, line):
    s = slot(svc, me, claim, line)
    stack.objects.post(s["fields"], PNG, "image/png")
    stack.scanner.broken.add(f"{claim}/{s['receiptId']}")
    svc.handle_upload_event(claim, s["receiptId"])
    svc.handle_scan_result(claim, s["receiptId"])
    assert svc.get_receipt(me, claim, line, s["receiptId"])["rejectReason"] == "SCAN_FAILED"
    assert not stack.objects.buckets["quarantine"]


def test_scan_result_is_idempotent(stack, svc, bus, me, claim, line):
    s = slot(svc, me, claim, line)
    stack.objects.post(s["fields"], PNG, "image/png")
    svc.handle_upload_event(claim, s["receiptId"])
    svc.handle_scan_result(claim, s["receiptId"])
    assert svc.handle_scan_result(claim, s["receiptId"]) == "CLEAN"  # second delivery does nothing
    assert len(bus.of("ReceiptStored")) == 1


def test_upload_event_without_a_file_does_nothing(svc, me, claim, line):
    s = slot(svc, me, claim, line)
    svc.handle_upload_event(claim, s["receiptId"])
    assert svc.get_receipt(me, claim, line, s["receiptId"])["status"] == "PENDING_UPLOAD"


def test_events_for_missing_receipts_are_ignored(svc, claim):
    svc.handle_upload_event(claim, "NOPE")
    assert svc.handle_scan_result(claim, "NOPE") == "MISSING"


# ---- ReceiptStored event ---------------------------------------------------------------------------------

def test_stored_event_has_ids_only(stack, bus, me, claim, line):
    r = upload(stack, me, claim, line)
    [e] = bus.of("ReceiptStored")
    assert e["payload"] == {"receiptId": r["receiptId"], "claimId": claim, "lineId": line, "mimeType": "image/png",
                            "sizeBytes": len(PNG)}
    assert e["claimRef"] is None  # still a draft


# ---- AC9: duplicates -------------------------------------------------------------------------------------

def test_ac9_same_file_on_another_claim_warns_and_still_works(stack, svc, me):
    c1 = svc.create_claim(me)["claimId"]
    l1 = new_line(svc, me, c1)
    upload(stack, me, c1, l1)
    c2 = svc.create_claim(me)["claimId"]
    l2 = new_line(svc, me, c2)
    r2 = upload(stack, me, c2, l2)
    assert r2["status"] == "CLEAN" and r2["duplicateOf"] == c1  # draft: shown by claim id


def test_duplicate_warning_uses_the_reference_once_submitted(stack, svc, me):
    from tests.submit.conftest import ready_claim
    c1, l1 = ready_claim(stack, me)
    ref = svc.submit(me, c1, "idem-key-0001")["claimRef"]
    c2 = svc.create_claim(me)["claimId"]
    l2 = new_line(svc, me, c2)
    assert upload(stack, me, c2, l2)["duplicateOf"] == ref


def test_same_file_on_two_lines_of_one_claim_is_not_flagged(stack, svc, me, claim, line):
    l2 = new_line(svc, me, claim)
    upload(stack, me, claim, line)
    assert "duplicateOf" not in upload(stack, me, claim, l2)


def test_other_peoples_files_are_never_compared(stack, svc, me, other):
    c1 = svc.create_claim(me)["claimId"]
    upload(stack, me, c1, new_line(svc, me, c1))
    c2 = svc.create_claim(other)["claimId"]
    assert "duplicateOf" not in upload(stack, other, c2, new_line(svc, other, c2))


def test_different_files_are_not_duplicates(stack, svc, me):
    c1 = svc.create_claim(me)["claimId"]
    upload(stack, me, c1, new_line(svc, me, c1), PNG)
    c2 = svc.create_claim(me)["claimId"]
    assert "duplicateOf" not in upload(stack, me, c2, new_line(svc, me, c2), JPEG, "image/jpeg")


def test_rejected_files_do_not_count_as_duplicates(stack, svc, me):
    c1 = svc.create_claim(me)["claimId"]
    upload(stack, me, c1, new_line(svc, me, c1), EICAR)
    c2 = svc.create_claim(me)["claimId"]
    assert "duplicateOf" not in upload(stack, me, c2, new_line(svc, me, c2), PNG)


def test_removing_the_first_receipt_clears_the_warning(stack, svc, me):
    c1 = svc.create_claim(me)["claimId"]
    l1 = new_line(svc, me, c1)
    r1 = upload(stack, me, c1, l1)
    c2 = svc.create_claim(me)["claimId"]
    l2 = new_line(svc, me, c2)
    r2 = upload(stack, me, c2, l2)
    svc.delete_receipt(me, c1, l1, r1["receiptId"])
    assert "duplicateOf" not in svc.get_receipt(me, c2, l2, r2["receiptId"])


# ---- remove a receipt ------------------------------------------------------------------------------------

def test_delete_receipt_removes_file_and_record(stack, svc, me, claim, line):
    r = upload(stack, me, claim, line)
    svc.delete_receipt(me, claim, line, r["receiptId"])
    assert err(lambda: svc.get_receipt(me, claim, line, r["receiptId"])).status == 404
    assert not stack.objects.buckets["receipts"]


def test_delete_pending_receipt_removes_quarantine_file(stack, svc, me, claim, line):
    s = slot(svc, me, claim, line)
    stack.objects.post(s["fields"], PNG, "image/png")
    svc.delete_receipt(me, claim, line, s["receiptId"])
    assert not stack.objects.buckets["quarantine"]


# ---- viewing a receipt -----------------------------------------------------------------------------------

def test_owner_gets_a_60_second_link(stack, svc, me, claim, line):
    r = upload(stack, me, claim, line)
    assert svc.receipt_content_url(me, claim, line, r["receiptId"]).endswith("?expires=60")


def test_only_clean_receipts_can_be_opened(stack, svc, me, claim, line):
    r = upload(stack, me, claim, line, EICAR)
    assert err(lambda: svc.receipt_content_url(me, claim, line, r["receiptId"])).code == "RECEIPT_NOT_READY"


def test_strangers_cannot_open_receipts(stack, svc, me, other, claim, line):
    r = upload(stack, me, claim, line)
    assert err(lambda: svc.receipt_content_url(other, claim, line, r["receiptId"])).status == 404


def test_viewing_is_audited(stack, svc, bus, me, claim, line):
    r = upload(stack, me, claim, line)
    svc.receipt_content_url(me, claim, line, r["receiptId"])
    assert any(e["payload"]["action"] == "receipt.view" for e in bus.of("Audit"))


# ---- stuck uploads and scans (lld.md section 6) ----------------------------------------------------------

def test_scan_that_never_finishes_times_out_after_5_minutes(stack, svc, clock, me, claim, line):
    s = slot(svc, me, claim, line)
    stack.objects.post(s["fields"], PNG, "image/png")
    stack.scanner.stalled.add(f"{claim}/{s['receiptId']}")
    svc.handle_upload_event(claim, s["receiptId"])
    clock.advance(minutes=4, seconds=59)
    assert svc.sweep_stuck_receipts() == {"scan_timeout": 0, "upload_expired": 0}
    clock.advance(seconds=2)
    assert svc.sweep_stuck_receipts()["scan_timeout"] == 1
    r = svc.get_receipt(me, claim, line, s["receiptId"])
    assert r["status"] == "REJECTED" and r["rejectReason"] == "SCAN_TIMEOUT"
    assert not stack.objects.buckets["quarantine"]


def test_upload_that_never_happened_is_cleaned_after_an_hour(stack, svc, clock, me, claim, line):
    s = slot(svc, me, claim, line)
    clock.advance(minutes=59)
    assert svc.sweep_stuck_receipts()["upload_expired"] == 0
    clock.advance(minutes=2)
    assert svc.sweep_stuck_receipts()["upload_expired"] == 1
    assert err(lambda: svc.get_receipt(me, claim, line, s["receiptId"])).status == 404


def test_sweeper_leaves_healthy_receipts_alone_and_is_repeatable(stack, svc, clock, me, claim, line):
    r = upload(stack, me, claim, line)
    clock.advance(days=3)
    assert svc.sweep_stuck_receipts() == {"scan_timeout": 0, "upload_expired": 0}
    assert svc.sweep_stuck_receipts() == {"scan_timeout": 0, "upload_expired": 0}
    assert svc.get_receipt(me, claim, line, r["receiptId"])["status"] == "CLEAN"
