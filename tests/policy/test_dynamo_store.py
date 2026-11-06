"""The real DynamoDB adapter, checked against botocore's own request validation (no AWS login needed)."""

import json
from datetime import date

import boto3
import pytest
from botocore.stub import Stubber

from policy.errors import VersionExists
from policy.store import DynamoRulesStore

RECORD = {"version": 2, "effectiveFrom": "2026-12-01", "publishedAt": "2026-11-04T09:00:00Z",
          "publishedBy": "fin1", "checksum": "abc", "rules": {"k": "v"}}


@pytest.fixture
def ddb():
    client = boto3.client("dynamodb", region_name="ap-south-1", aws_access_key_id="x", aws_secret_access_key="x")
    with Stubber(client) as stub:
        yield client, stub
        stub.assert_no_pending_responses()


def test_put_version_writes_document_and_pointer_in_one_transaction(ddb):
    client, stub = ddb
    stub.add_response("transact_write_items", {}, {"TransactItems": [
        {"Put": {"TableName": "policy-rules", "ConditionExpression": "attribute_not_exists(PK)", "Item": {
            "PK": {"S": "RULES"}, "SK": {"S": "V#000002"}, "record": {"S": json.dumps(RECORD)}}}},
        {"Put": {"TableName": "policy-rules", "ConditionExpression": "attribute_not_exists(PK)", "Item": {
            "PK": {"S": "RULES"}, "SK": {"S": "E#2026-12-01#000002"}, "version": {"N": "2"}}}}]})
    DynamoRulesStore(client, "policy-rules").put_version(RECORD)


def test_existing_version_is_reported_as_immutable(ddb):
    client, stub = ddb
    stub.add_client_error("transact_write_items", service_error_code="TransactionCanceledException",
                          http_status_code=400)
    with pytest.raises(VersionExists):
        DynamoRulesStore(client, "policy-rules").put_version(RECORD)


def test_get_version_found_and_missing(ddb):
    client, stub = ddb
    key = {"PK": {"S": "RULES"}, "SK": {"S": "V#000002"}}
    stub.add_response("get_item", {"Item": {**key, "record": {"S": json.dumps(RECORD)}}},
                      {"TableName": "policy-rules", "Key": key, "ConsistentRead": True})
    stub.add_response("get_item", {}, {"TableName": "policy-rules", "Key": key, "ConsistentRead": True})
    store = DynamoRulesStore(client, "policy-rules")
    assert store.get_version(2) == RECORD
    assert store.get_version(2) is None


def test_latest_reads_newest_first(ddb):
    client, stub = ddb
    stub.add_response("query", {"Items": [{"record": {"S": json.dumps(RECORD)}}]}, {
        "TableName": "policy-rules", "ConsistentRead": True, "ScanIndexForward": False, "Limit": 1,
        "KeyConditionExpression": "PK = :pk AND begins_with(SK, :p)",
        "ExpressionAttributeValues": {":pk": {"S": "RULES"}, ":p": {"S": "V#"}}})
    stub.add_response("query", {"Items": []}, None)
    store = DynamoRulesStore(client, "policy-rules")
    assert store.latest() == RECORD
    assert store.latest() is None


def test_in_force_uses_the_date_pointer_then_the_document(ddb):
    client, stub = ddb
    stub.add_response("query", {"Items": [{"version": {"N": "2"}}]}, {
        "TableName": "policy-rules", "ScanIndexForward": False, "Limit": 1,
        "KeyConditionExpression": "PK = :pk AND SK BETWEEN :lo AND :hi",
        "ExpressionAttributeValues": {":pk": {"S": "RULES"}, ":lo": {"S": "E#0000"},
                                      ":hi": {"S": "E#2026-12-15#999999"}}})
    stub.add_response("get_item", {"Item": {"record": {"S": json.dumps(RECORD)}}}, None)
    assert DynamoRulesStore(client, "policy-rules").in_force(date(2026, 12, 15)) == RECORD


def test_in_force_with_no_pointer(ddb):
    client, stub = ddb
    stub.add_response("query", {"Items": []}, None)
    assert DynamoRulesStore(client, "policy-rules").in_force(date(2020, 1, 1)) is None


def test_idempotency_round_trip(ddb):
    client, stub = ddb
    entry = {"bodyHash": "h", "result": {"version": 1}, "expiresAtEpoch": 1800000000}
    stub.add_response("put_item", {}, {"TableName": "policy-rules", "Item": {
        "PK": {"S": "IDEM#key-00000001"}, "SK": {"S": "META"}, "entry": {"S": json.dumps(entry)},
        "ttl": {"N": "1800000000"}}})
    stub.add_response("get_item", {"Item": {"entry": {"S": json.dumps(entry)}}}, None)
    stub.add_response("get_item", {}, None)
    store = DynamoRulesStore(client, "policy-rules")
    store.put_idempotent("key-00000001", entry)
    assert store.get_idempotent("key-00000001") == entry
    assert store.get_idempotent("other-key-0001") is None
