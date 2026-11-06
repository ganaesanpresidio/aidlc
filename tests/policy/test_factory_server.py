import json
import threading
import urllib.error
import urllib.request

import pytest

from aidlc_common.backend import Backend
from aidlc_common.events import InMemoryEventBus
from policy.factory import build_service, seed_example_rules
from policy.server import serve
from policy.store import InMemoryRulesStore


def test_mock_is_the_default_and_needs_no_aws(monkeypatch):
    monkeypatch.delenv("AIDLC_BACKEND", raising=False)
    s = build_service()
    assert isinstance(s._store, InMemoryRulesStore) and isinstance(s._bus._bus, InMemoryEventBus)


def test_aws_flag_builds_real_adapters_without_calling_aws(monkeypatch):
    from aidlc_common.events import EventBridgeBus
    from policy.store import DynamoRulesStore
    monkeypatch.setenv("AWS_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    s = build_service(Backend.AWS)
    assert isinstance(s._store, DynamoRulesStore) and isinstance(s._bus._bus, EventBridgeBus)


def test_aws_table_and_bus_names_come_from_settings(monkeypatch):
    monkeypatch.setenv("POLICY_TABLE", "my-table")
    monkeypatch.setenv("EVENT_BUS_NAME", "my-bus")
    s = build_service(Backend.AWS)
    assert s._store._t == "my-table" and s._bus._bus._bus == "my-bus"


def test_seed_publishes_example_rules_for_today(clock):
    s = build_service(Backend.MOCK, clock=clock)
    r = seed_example_rules(s)
    assert r["version"] == 1 and r["effectiveFrom"] == "2026-11-04"
    assert seed_example_rules(s) == r  # running the seed twice changes nothing


def test_dev_server_refuses_to_run_against_aws(monkeypatch):
    monkeypatch.setenv("AIDLC_BACKEND", "aws")
    with pytest.raises(RuntimeError, match="mock"):
        serve(build_service(Backend.MOCK), port=0)


@pytest.fixture
def live(clock):
    service = build_service(Backend.MOCK)
    seed_example_rules(service)
    server = serve(service, port=0)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def call(base, method, path, body=None, headers=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def test_http_end_to_end(live):
    user = {"X-Dev-User": "emp1"}
    status, body = call(live, "GET", "/v1/policy/rules", headers=user)
    assert status == 200 and body["version"] == 1
    assert call(live, "GET", "/v1/policy/rules")[0] == 401
    internal = {"X-Dev-Internal": "submit"}
    line = {"lineId": "L1", "category": "Meals", "amount": 2000, "currency": "INR", "hasReceipt": True,
            "expenseDate": "2026-11-03"}
    from datetime import date
    status, body = call(live, "POST", "/v1/policy/evaluate",
                        {"grade": "G1", "submissionDate": date.today().isoformat(), "lines": [line]}, internal)
    assert status == 200 and body["violations"][0]["code"] == "LIMIT_EXCEEDED"
    assert call(live, "POST", "/v1/policy/evaluate", {}, user)[0] == 403


def test_http_bad_json_is_400(live):
    req = urllib.request.Request(live + "/v1/policy/evaluate", method="POST", data=b"{not json",
                                 headers={"X-Dev-Internal": "submit", "content-length": "9"})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req)
    assert e.value.code == 400
