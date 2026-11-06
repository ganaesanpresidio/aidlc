import base64
import json
import threading
import urllib.error
import urllib.request

import pytest

from aidlc_common.backend import Backend
from submit.factory import build_mock_stack, build_service, settings_from_config
from submit.objects import MockObjectStore, S3ObjectStore
from submit.scanner import GuardDutyScanner
from submit.server import serve
from submit.table import DynamoTable, InMemoryTable
from tests.submit.conftest import EICAR, PNG, sha


def test_mock_is_the_default_and_touches_no_aws(monkeypatch):
    monkeypatch.delenv("AIDLC_BACKEND", raising=False)
    s = build_service()
    assert isinstance(s._t, InMemoryTable) and isinstance(s._objects, MockObjectStore)


def test_aws_flag_builds_real_adapters_without_calling_aws(monkeypatch):
    for k, v in {"AWS_REGION": "ap-south-1", "AWS_ACCESS_KEY_ID": "x", "AWS_SECRET_ACCESS_KEY": "y",
                 "SUBMIT_TABLE": "t1", "QUARANTINE_BUCKET": "q1", "RECEIPTS_BUCKET": "r1", "POLICY_URL": "https://p.internal"}.items():
        monkeypatch.setenv(k, v)
    s = build_service(Backend.AWS)
    assert isinstance(s._t, DynamoTable) and s._t._t == "t1"
    assert isinstance(s._objects, S3ObjectStore) and isinstance(s._scanner, GuardDutyScanner)
    assert s._policy._base == "https://p.internal"


def test_retention_days_setting(monkeypatch):
    assert settings_from_config().retention_days == 365
    monkeypatch.setenv("AIDLC_RETENTION_DAYS", "90")
    assert settings_from_config().retention_days == 90


def test_dev_server_refuses_to_run_against_aws(monkeypatch, clock, bus):
    monkeypatch.setenv("AIDLC_BACKEND", "aws")
    with pytest.raises(RuntimeError, match="mock"):
        serve(build_mock_stack(clock=clock, bus=bus), port=0)


@pytest.fixture
def live(clock, bus):
    stack = build_mock_stack(clock=clock, bus=bus)
    server = serve(stack, port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", stack
    server.shutdown()
    server.server_close()


def call(base, method, path, body=None, headers=None):
    h = {"X-Dev-User": "emp1", "X-Dev-Grade": "G1", **(headers or {})}
    req = urllib.request.Request(base + path, method=method, headers=h,
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def upload_over_http(base, cid, lid, content, mime="image/png"):
    status, slot = call(base, "POST", f"/v1/claims/{cid}/lines/{lid}/receipts",
                        {"mimeType": mime, "sizeBytes": len(content), "sha256": sha(content)})
    assert status == 201
    s2, out = call(base, "POST", f"/dev/uploads/{cid}/{slot['receiptId']}",
                   {"contentBase64": base64.b64encode(content).decode(), "contentType": mime})
    return slot["receiptId"], s2, out


def test_whole_journey_over_http(live):
    base, _ = live
    cid = call(base, "POST", "/v1/claims")[1]["claimId"]
    lid = call(base, "POST", f"/v1/claims/{cid}/lines",
               {"expenseDate": "2026-11-03", "category": "Meals", "amount": 1200, "description": "lunch"})[1]["lineId"]
    # AC7: blocked without a receipt
    assert call(base, "POST", f"/v1/claims/{cid}/submit", headers={"idempotency-key": "idem-key-0001"})[0] == 422
    rid, status, out = upload_over_http(base, cid, lid, PNG)
    assert status == 200 and out == {"status": "CLEAN"}
    status, claim = call(base, "POST", f"/v1/claims/{cid}/submit", headers={"idempotency-key": "idem-key-0001"})
    assert status == 200 and claim["status"] == "Submitted" and claim["claimRef"].startswith("CLM-")


def test_malware_over_http(live):
    base, _ = live
    cid = call(base, "POST", "/v1/claims")[1]["claimId"]
    lid = call(base, "POST", f"/v1/claims/{cid}/lines",
               {"expenseDate": "2026-11-03", "category": "Meals", "amount": 100, "description": "x"})[1]["lineId"]
    rid, status, out = upload_over_http(base, cid, lid, EICAR)
    assert out == {"status": "REJECTED"}
    assert call(base, "GET", f"/v1/claims/{cid}/lines/{lid}/receipts/{rid}")[1]["rejectReason"] == "MALWARE"


def test_dev_upload_edge_cases(live):
    base, _ = live
    assert call(base, "POST", "/dev/uploads/NOPE/NOPE", {})[0] == 404
    cid = call(base, "POST", "/v1/claims")[1]["claimId"]
    lid = call(base, "POST", f"/v1/claims/{cid}/lines",
               {"expenseDate": "2026-11-03", "category": "Meals", "amount": 100, "description": "x"})[1]["lineId"]
    _, slot = call(base, "POST", f"/v1/claims/{cid}/lines/{lid}/receipts",
                   {"mimeType": "image/png", "sizeBytes": len(PNG), "sha256": sha(PNG)})
    assert call(base, "POST", f"/dev/uploads/{cid}/{slot['receiptId']}", {})[0] == 400
    s, out = call(base, "POST", f"/dev/uploads/{cid}/{slot['receiptId']}",
                  {"contentBase64": base64.b64encode(PNG + b"tampered").decode(), "contentType": "image/png"})
    assert s == 403 and out["code"] == "UPLOAD_REJECTED"
    assert call(base, "POST", f"/dev/uploads/{cid}/{slot['receiptId']}", {"contentBase64": "***", "contentType": "x"})[0] == 400


def test_dev_jobs_and_auth(live):
    base, _ = live
    assert call(base, "POST", "/dev/jobs/sweep")[1] == {"scan_timeout": 0, "upload_expired": 0}
    assert call(base, "POST", "/dev/jobs/expire")[1] == {"expired": 0}
    assert call(base, "GET", "/v1/claims", headers={"X-Dev-User": ""})[0] == 401
    req = urllib.request.Request(base + "/v1/claims")  # no dev headers at all
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 401


def test_bad_json_is_400(live):
    base, _ = live
    req = urllib.request.Request(base + "/v1/claims", method="POST", data=b"{nope", headers={"X-Dev-User": "e", "content-length": "5"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400


def test_test_page_is_served_at_the_root(live):
    base, _ = live
    for path in ("/", "/ui"):
        with urllib.request.urlopen(base + path) as r:
            body = r.read().decode()
            assert r.status == 200 and r.headers["content-type"].startswith("text/html")
            assert "<title>Expense submission test page</title>" in body and r.headers["cache-control"] == "no-store"


def test_the_page_uses_only_real_routes_and_the_documented_rules():
    """The page must call routes that exist in the contract and keep to the same limits as the service."""
    import re
    from pathlib import Path

    import yaml
    html = (Path(__file__).resolve().parents[2] / "web" / "expense-submit.html").read_text()
    spec = yaml.safe_load((Path(__file__).resolve().parents[2] / "aidlc-docs/design/submit/api/openapi.yaml").read_text())
    paths = set(spec["paths"])
    used = set(re.findall(r'api\("(?:GET|POST|PATCH|DELETE)", [`"](/v1/[^`"?]*)', html))
    normalised = {re.sub(r"\$\{[^}]+\}", "{x}", u) for u in used}
    spec_norm = {re.sub(r"\{[^}]+\}", "{x}", p) for p in paths}
    assert normalised <= spec_norm, normalised - spec_norm
    from submit.objects import ALLOWED_MIME, MAX_BYTES
    from submit.service import CATEGORIES, Settings
    assert all(f'"{m}"' in html for m in ALLOWED_MIME)
    assert f"MAX_BYTES = {MAX_BYTES // (1024 * 1024)} * 1024 * 1024" in html
    assert f"MAX_RECEIPTS = {Settings().max_receipts_per_line}" in html
    assert all(c in html for c in CATEGORIES)
    assert "WINDOW_DAYS = 30" in html and "RECEIPT_THRESHOLD = 1000" in html
