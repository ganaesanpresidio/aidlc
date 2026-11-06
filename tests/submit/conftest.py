import hashlib

import pytest

from submit.factory import build_mock_stack
from submit.service import Caller

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 64
PDF = b"%PDF-1.7\n" + b"x" * 64
HEIC = b"\x00\x00\x00\x18ftypheic" + b"x" * 64
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

LINE = dict(expenseDate="2026-11-03", category="Meals", amount=800, description="lunch")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def stack(clock, bus):
    return build_mock_stack(clock=clock, bus=bus)


@pytest.fixture
def svc(stack):
    return stack.service


@pytest.fixture
def me():
    return Caller("emp1", "G1")


@pytest.fixture
def other():
    return Caller("emp2", "G1")


@pytest.fixture
def claim(svc, me):
    return svc.create_claim(me)["claimId"]


def new_line(svc, who, claim_id, **kw):
    return svc.add_line(who, claim_id, {**LINE, **kw})["lineId"]


def upload(stack, who, claim_id, line_id, content=PNG, mime="image/png", scan=True, size=None):
    """Request a slot, post the file like a browser, then let the upload and scan events run."""
    svc = stack.service
    slot = svc.request_receipt_upload(who, claim_id, line_id,
                                      {"mimeType": mime, "sizeBytes": size or len(content), "sha256": sha(content)})
    stack.objects.post(slot["fields"], content, mime)
    svc.handle_upload_event(claim_id, slot["receiptId"])
    if scan:
        svc.handle_scan_result(claim_id, slot["receiptId"])
    return svc.get_receipt(who, claim_id, line_id, slot["receiptId"])


def ready_claim(stack, who, amount=800, category="Meals", **kw):
    """A draft claim with one line and one clean receipt."""
    c = stack.service.create_claim(who)["claimId"]
    l = new_line(stack.service, who, c, amount=amount, category=category, **kw)
    upload(stack, who, c, l)
    return c, l
