"""The real AWS adapters, checked with botocore's own request validation and stubs. No AWS login needed."""

import base64
import json

import boto3
import pytest
import requests
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber

from submit.errors import ConditionFailed, PolicyRejected, PolicyUnavailable
from submit.objects import MockObjectStore, S3ObjectStore, sniff_mime
from submit.policy_client import HttpPolicyClient, _interpret
from submit.scanner import GuardDutyScanner, Verdict
from submit.table import DynamoTable, InMemoryTable, _plain


def client(service):
    return boto3.client(service, region_name="ap-south-1", aws_access_key_id="x", aws_secret_access_key="y")


# ---- InMemoryTable behaves like the real thing ---------------------------------------------------------

@pytest.fixture
def t():
    return InMemoryTable()


def item(pk="A", sk="1", **kw):
    return {"PK": pk, "SK": sk, **kw}


def test_put_get_returns_copies(t):
    t.put(item(x=[1]))
    got = t.get("A", "1")
    got["x"].append(2)
    assert t.get("A", "1")["x"] == [1] and t.get("A", "nope") is None


def test_if_absent(t):
    t.put(item(), if_absent=True)
    with pytest.raises(ConditionFailed):
        t.put(item(), if_absent=True)


def test_if_version(t):
    t.put(item(version=1))
    t.put(item(version=2), if_version=1)
    with pytest.raises(ConditionFailed):
        t.put(item(version=3), if_version=1)  # stale
    with pytest.raises(ConditionFailed):
        t.put(item(pk="missing", version=1), if_version=1)  # nothing to update


def test_query_by_prefix_sorted(t):
    for sk in ("RCPT#2", "LINE#b", "LINE#a", "META"):
        t.put(item(sk=sk))
    t.put(item(pk="B", sk="LINE#z"))
    assert [i["SK"] for i in t.query("A", "LINE#")] == ["LINE#a", "LINE#b"]
    assert [i["SK"] for i in t.query("A")] == ["LINE#a", "LINE#b", "META", "RCPT#2"]


def test_index_queries(t):
    for n, d in enumerate(["2027-01-01", "2027-03-01", "2027-02-01"]):
        t.put(item(sk=str(n), gsi2pk="EXPIRY", gsi2sk=f"{d}#r{n}"))
    t.put(item(sk="x", gsi2pk="OTHER", gsi2sk="2020"))
    assert [i["gsi2sk"][:10] for i in t.query_index(2, "EXPIRY")] == ["2027-01-01", "2027-02-01", "2027-03-01"]
    assert len(t.query_index(2, "EXPIRY", sk_lte="2027-02-01#~")) == 2
    assert [i["gsi2sk"][:7] for i in t.query_index(2, "EXPIRY", descending=True, limit=1)] == ["2027-03"]


def test_transaction_is_all_or_nothing(t):
    t.put(item(sk="existing"))
    with pytest.raises(ConditionFailed):
        t.transact([{"put": item(sk="new")}, {"put": item(sk="existing"), "if_absent": True}])
    assert t.get("A", "new") is None  # the first write was not applied
    t.transact([{"put": item(sk="new")}, {"delete": ("A", "existing")}])
    assert t.get("A", "new") and t.get("A", "existing") is None


def test_increment(t):
    assert [t.increment("C", "META", "n") for _ in range(3)] == [1, 2, 3]


# ---- DynamoTable ---------------------------------------------------------------------------------------

@pytest.fixture
def ddb():
    c = client("dynamodb")
    with Stubber(c) as stub:
        yield DynamoTable(c, "submit-claims"), stub
        stub.assert_no_pending_responses()


def test_number_conversion_back_to_python():
    from decimal import Decimal
    assert _plain({"a": Decimal("3"), "b": [Decimal("2.5")], "c": "x"}) == {"a": 3, "b": [2.5], "c": "x"}


def test_get_and_put_round_trip(ddb):
    table, stub = ddb
    stub.add_response("get_item", {"Item": {"PK": {"S": "A"}, "SK": {"S": "1"}, "version": {"N": "4"}}},
                      {"TableName": "submit-claims", "Key": {"PK": {"S": "A"}, "SK": {"S": "1"}}, "ConsistentRead": True})
    assert table.get("A", "1") == {"PK": "A", "SK": "1", "version": 4}
    stub.add_response("get_item", {}, None)
    assert table.get("A", "2") is None
    stub.add_response("put_item", {}, {"TableName": "submit-claims", "Item": {"PK": {"S": "A"}, "SK": {"S": "1"},
                                                                                 "n": {"N": "2"}, "ok": {"BOOL": True}}})
    table.put({"PK": "A", "SK": "1", "n": 2, "ok": True, "skipme": None})  # None values are not written


def test_put_conditions(ddb):
    table, stub = ddb
    stub.add_response("put_item", {}, {"TableName": "submit-claims", "Item": ANY, "ConditionExpression": "attribute_not_exists(PK)"})
    table.put(item(), if_absent=True)
    stub.add_response("put_item", {}, {"TableName": "submit-claims", "Item": ANY, "ConditionExpression": "version = :v",
                                       "ExpressionAttributeValues": {":v": {"N": "3"}}})
    table.put(item(version=4), if_version=3)


def test_failed_condition_becomes_condition_failed(ddb):
    table, stub = ddb
    stub.add_client_error("put_item", service_error_code="ConditionalCheckFailedException")
    with pytest.raises(ConditionFailed):
        table.put(item(), if_absent=True)
    stub.add_client_error("transact_write_items", service_error_code="TransactionCanceledException")
    with pytest.raises(ConditionFailed):
        table.transact([{"put": item(), "if_absent": True}])


def test_transact_builds_puts_and_deletes(ddb):
    table, stub = ddb
    stub.add_response("transact_write_items", {}, {"TransactItems": [
        {"Put": {"TableName": "submit-claims", "Item": ANY, "ConditionExpression": "version = :v",
                 "ExpressionAttributeValues": {":v": {"N": "1"}}}},
        {"Delete": {"TableName": "submit-claims", "Key": {"PK": {"S": "A"}, "SK": {"S": "x"}}}}]})
    table.transact([{"put": item(version=2), "if_version": 1}, {"delete": ("A", "x")}])


def test_query_and_pagination(ddb):
    table, stub = ddb
    page = lambda sk: {"PK": {"S": "A"}, "SK": {"S": sk}}
    stub.add_response("query", {"Items": [page("LINE#a")], "LastEvaluatedKey": page("LINE#a")},
                      {"TableName": "submit-claims", "KeyConditionExpression": "PK = :pk AND begins_with(SK, :p)",
                       "ExpressionAttributeValues": {":pk": {"S": "A"}, ":p": {"S": "LINE#"}}, "ConsistentRead": True})
    stub.add_response("query", {"Items": [page("LINE#b")]}, None)
    assert [i["SK"] for i in table.query("A", "LINE#")] == ["LINE#a", "LINE#b"]


def test_index_query(ddb):
    table, stub = ddb
    stub.add_response("query", {"Items": []}, {"TableName": "submit-claims", "IndexName": "GSI2", "ScanIndexForward": True,
                                               "KeyConditionExpression": "gsi2pk = :pk AND gsi2sk <= :hi",
                                               "ExpressionAttributeValues": {":pk": {"S": "EXPIRY"}, ":hi": {"S": "2027-01-01#~"}}})
    assert table.query_index(2, "EXPIRY", sk_lte="2027-01-01#~") == []
    stub.add_response("query", {"Items": []}, {"TableName": "submit-claims", "IndexName": "GSI1", "ScanIndexForward": False,
                                               "Limit": 1, "KeyConditionExpression": "gsi1pk = :pk",
                                               "ExpressionAttributeValues": {":pk": {"S": "EMP#e"}}})
    table.query_index(1, "EMP#e", descending=True, limit=1)


def test_dynamo_increment(ddb):
    table, stub = ddb
    stub.add_response("update_item", {"Attributes": {"n": {"N": "7"}}}, {
        "TableName": "submit-claims", "Key": {"PK": {"S": "C"}, "SK": {"S": "META"}}, "UpdateExpression": "ADD #f :one",
        "ExpressionAttributeNames": {"#f": "n"}, "ExpressionAttributeValues": {":one": {"N": "1"}}, "ReturnValues": "UPDATED_NEW"})
    assert table.increment("C", "META", "n") == 7


def test_delete(ddb):
    table, stub = ddb
    stub.add_response("delete_item", {}, {"TableName": "submit-claims", "Key": {"PK": {"S": "A"}, "SK": {"S": "1"}}})
    table.delete("A", "1")


# ---- files ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("head,mime", [
    (b"\xff\xd8\xff\xe0abc", "image/jpeg"), (b"\x89PNG\r\n\x1a\nabc", "image/png"), (b"%PDF-1.4", "application/pdf"),
    (b"\x00\x00\x00\x18ftypheic", "image/heic"), (b"\x00\x00\x00\x18ftypmif1", "image/heic"),
    (b"\x00\x00\x00\x18ftypisom", None), (b"MZ\x90\x00", None), (b"", None), (b"GIF89a", None), (b"PK\x03\x04", None)])
def test_file_type_sniffing(head, mime):
    assert sniff_mime(head) == mime


def test_s3_presigned_post_carries_the_conditions():
    store = S3ObjectStore(client("s3"), "q-bucket", "c-bucket")
    slot = store.create_upload_slot("claim/r1", "image/png", 10 * 1024 * 1024, "ab" * 32)
    assert "q-bucket" in slot.url and slot.fields["key"] == "claim/r1" and slot.fields["Content-Type"] == "image/png"
    assert slot.fields["x-amz-checksum-sha256"] == base64.b64encode(bytes.fromhex("ab" * 32)).decode()
    policy = json.loads(base64.b64decode(slot.fields["policy"]))
    assert ["content-length-range", 1, 10485760] in policy["conditions"] and {"Content-Type": "image/png"} in policy["conditions"]


def test_s3_move_delete_and_signed_url():
    c = client("s3")
    store = S3ObjectStore(c, "q-bucket", "c-bucket", kms_key_id="key-1")
    with Stubber(c) as stub:
        stub.add_response("copy_object", {}, {"Bucket": "c-bucket", "Key": "k", "CopySource": {"Bucket": "q-bucket", "Key": "k"},
                                              "ServerSideEncryption": "aws:kms", "SSEKMSKeyId": "key-1"})
        stub.add_response("delete_object", {}, {"Bucket": "q-bucket", "Key": "k"})
        store.move_to_clean("k", "k")
        stub.add_response("delete_object", {}, {"Bucket": "c-bucket", "Key": "k"})
        store.delete("receipts", "k")
        stub.add_response("head_object", {}, {"Bucket": "q-bucket", "Key": "k"})
        assert store.exists("quarantine", "k")
        stub.add_client_error("head_object", service_error_code="404", http_status_code=404)
        assert not store.exists("quarantine", "k")
        stub.assert_no_pending_responses()
    url = store.signed_url("k", 60)
    assert "c-bucket" in url and "X-Amz-Expires=60" in url


def test_s3_reads_only_the_first_bytes():
    import io
    c = client("s3")
    with Stubber(c) as stub:
        stub.add_response("get_object", {"Body": StreamingBody(io.BytesIO(b"%PDF-1.4"), 8)},
                          {"Bucket": "q-bucket", "Key": "k", "Range": "bytes=0-15"})
        assert S3ObjectStore(c, "q-bucket", "c-bucket").head_bytes("quarantine", "k") == b"%PDF-1.4"


def test_mock_signed_url_needs_a_clean_file():
    with pytest.raises(KeyError):
        MockObjectStore().signed_url("nope")


# ---- GuardDuty scanner ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("tags,verdict", [
    ([], Verdict.PENDING), ([{"Key": "x", "Value": "y"}], Verdict.PENDING),
    ([{"Key": "GuardDutyMalwareScanStatus", "Value": "NO_THREATS_FOUND"}], Verdict.CLEAN),
    ([{"Key": "GuardDutyMalwareScanStatus", "Value": "THREATS_FOUND"}], Verdict.INFECTED),
    ([{"Key": "GuardDutyMalwareScanStatus", "Value": "UNSUPPORTED"}], Verdict.FAILED),
    ([{"Key": "GuardDutyMalwareScanStatus", "Value": "ACCESS_DENIED"}], Verdict.FAILED),
    ([{"Key": "GuardDutyMalwareScanStatus", "Value": "FAILED"}], Verdict.FAILED)])
def test_guardduty_tag_mapping(tags, verdict):
    c = client("s3")
    with Stubber(c) as stub:
        stub.add_response("get_object_tagging", {"TagSet": tags}, {"Bucket": "q-bucket", "Key": "k"})
        assert GuardDutyScanner(c, "q-bucket").verdict("k") is verdict


# ---- policy client ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("status,body,outcome", [(200, {"ok": True}, "ok"), (400, {"code": "UNKNOWN_GRADE", "message": "m"}, "rejected"),
                                                 (404, {"code": "NO_RULES_IN_FORCE"}, "down"), (500, None, "down"),
                                                 (403, {"code": "FORBIDDEN"}, "down"), (503, None, "down")])
def test_policy_answers_are_interpreted(status, body, outcome):
    if outcome == "ok":
        assert _interpret(status, body) == {"ok": True}
    elif outcome == "rejected":
        with pytest.raises(PolicyRejected) as e:
            _interpret(status, body)
        assert e.value.code == "UNKNOWN_GRADE"
    else:
        with pytest.raises(PolicyUnavailable):
            _interpret(status, body)


class FakeResp:
    def __init__(self, status, payload):
        self.status_code, self._p = status, payload

    def json(self):
        if self._p is None:
            raise ValueError
        return self._p


def test_http_client_signs_and_posts(monkeypatch):
    seen = {}

    def post(url, data, headers, timeout):
        seen.update(url=url, headers=headers, data=data, timeout=timeout)
        return FakeResp(200, {"ok": True, "violations": []})

    monkeypatch.setattr(requests, "post", post)
    session = boto3.Session(aws_access_key_id="x", aws_secret_access_key="y")
    out = HttpPolicyClient("https://policy.internal/", "ap-south-1", session).evaluate({"a": 1})
    assert out["ok"] and seen["url"] == "https://policy.internal/v1/policy/evaluate"
    assert seen["headers"]["Authorization"].startswith("AWS4-HMAC-SHA256") and "execute-api" in seen["headers"]["Authorization"]
    assert json.loads(seen["data"]) == {"a": 1} and seen["timeout"] == 3.0


@pytest.mark.parametrize("raiser", [requests.ConnectionError, requests.Timeout])
def test_http_client_network_failure_fails_closed(monkeypatch, raiser):
    def post(*a, **k):
        raise raiser()

    monkeypatch.setattr(requests, "post", post)
    session = boto3.Session(aws_access_key_id="x", aws_secret_access_key="y")
    with pytest.raises(PolicyUnavailable):
        HttpPolicyClient("https://p", "ap-south-1", session).evaluate({})


def test_http_client_non_json_error_page_fails_closed(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp(502, None))
    session = boto3.Session(aws_access_key_id="x", aws_secret_access_key="y")
    with pytest.raises(PolicyUnavailable):
        HttpPolicyClient("https://p", "ap-south-1", session).evaluate({})
