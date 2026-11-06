"""Single-table storage. `InMemoryTable` is the mock; `DynamoTable` is the real adapter.

The real adapter is UNVERIFIED against AWS until a login is available (botocore Stubber tests only).
Items are plain dicts. Indexes (lld.md section 4):
  GSI1 gsi1pk/gsi1sk  my claims.   GSI2 gsi2pk/gsi2sk  receipt expiry.   GSI3 gsi3pk/gsi3sk  receipts waiting on a scan.
"""

from __future__ import annotations

import copy
from decimal import Decimal
from typing import Any, Protocol

from submit.errors import ConditionFailed

Item = dict[str, Any]


class Table(Protocol):
    def get(self, pk: str, sk: str) -> Item | None: ...
    def put(self, item: Item, *, if_absent: bool = False, if_version: int | None = None) -> None: ...
    def delete(self, pk: str, sk: str) -> None: ...
    def query(self, pk: str, sk_prefix: str | None = None) -> list[Item]: ...
    def query_index(self, index: int, pk: str, *, sk_lte: str | None = None, descending: bool = False,
                    limit: int | None = None) -> list[Item]: ...
    def transact(self, ops: list[dict[str, Any]]) -> None: ...
    def increment(self, pk: str, sk: str, field: str) -> int: ...


class InMemoryTable:
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], Item] = {}

    def get(self, pk: str, sk: str) -> Item | None:
        item = self._items.get((pk, sk))
        return copy.deepcopy(item) if item is not None else None

    def _check(self, item: Item, if_absent: bool, if_version: int | None) -> None:
        current = self._items.get((item["PK"], item["SK"]))
        if if_absent and current is not None:
            raise ConditionFailed("item exists")
        if if_version is not None and (current is None or current.get("version") != if_version):
            raise ConditionFailed("version changed")

    def put(self, item: Item, *, if_absent: bool = False, if_version: int | None = None) -> None:
        self._check(item, if_absent, if_version)
        self._items[(item["PK"], item["SK"])] = copy.deepcopy(item)

    def delete(self, pk: str, sk: str) -> None:
        self._items.pop((pk, sk), None)

    def query(self, pk: str, sk_prefix: str | None = None) -> list[Item]:
        rows = [i for (p, s), i in self._items.items() if p == pk and (sk_prefix is None or s.startswith(sk_prefix))]
        return [copy.deepcopy(i) for i in sorted(rows, key=lambda i: i["SK"])]

    def query_index(self, index: int, pk: str, *, sk_lte: str | None = None, descending: bool = False,
                    limit: int | None = None) -> list[Item]:
        pk_f, sk_f = f"gsi{index}pk", f"gsi{index}sk"
        rows = [i for i in self._items.values() if i.get(pk_f) == pk and (sk_lte is None or i[sk_f] <= sk_lte)]
        rows.sort(key=lambda i: i[sk_f], reverse=descending)
        return [copy.deepcopy(i) for i in (rows[:limit] if limit else rows)]

    def transact(self, ops: list[dict[str, Any]]) -> None:
        """All or nothing. Each op: {"put": item, "if_absent": bool, "if_version": int} or {"delete": (pk, sk)}."""
        for op in ops:
            if "put" in op:
                self._check(op["put"], op.get("if_absent", False), op.get("if_version"))
        for op in ops:
            if "put" in op:
                self._items[(op["put"]["PK"], op["put"]["SK"])] = copy.deepcopy(op["put"])
            else:
                self._items.pop(op["delete"], None)

    def increment(self, pk: str, sk: str, field: str) -> int:
        item = self._items.setdefault((pk, sk), {"PK": pk, "SK": sk, field: 0})
        item[field] = item.get(field, 0) + 1
        return item[field]


def _plain(value: Any) -> Any:
    """DynamoDB returns numbers as Decimal. Whole numbers go back to int."""
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


class DynamoTable:
    """Real adapter over a boto3 DynamoDB low-level client."""

    def __init__(self, client, table: str) -> None:
        from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

        self._c, self._t = client, table
        self._ser, self._de = TypeSerializer(), TypeDeserializer()

    def _to(self, item: Item) -> dict[str, Any]:
        return {k: self._ser.serialize(v) for k, v in item.items() if v is not None}

    def _from(self, raw: dict[str, Any]) -> Item:
        return {k: _plain(self._de.deserialize(v)) for k, v in raw.items()}

    @staticmethod
    def _cond(if_absent: bool, if_version: int | None) -> dict[str, Any]:
        if if_absent:
            return {"ConditionExpression": "attribute_not_exists(PK)"}
        if if_version is not None:
            return {"ConditionExpression": "version = :v", "ExpressionAttributeValues": {":v": {"N": str(if_version)}}}
        return {}

    def get(self, pk: str, sk: str) -> Item | None:
        out = self._c.get_item(TableName=self._t, Key={"PK": {"S": pk}, "SK": {"S": sk}}, ConsistentRead=True)
        return self._from(out["Item"]) if "Item" in out else None

    def put(self, item: Item, *, if_absent: bool = False, if_version: int | None = None) -> None:
        try:
            self._c.put_item(TableName=self._t, Item=self._to(item), **self._cond(if_absent, if_version))
        except self._c.exceptions.ConditionalCheckFailedException as exc:
            raise ConditionFailed(str(exc)) from exc

    def delete(self, pk: str, sk: str) -> None:
        self._c.delete_item(TableName=self._t, Key={"PK": {"S": pk}, "SK": {"S": sk}})

    def _query(self, **kw) -> list[Item]:
        items: list[Item] = []
        while True:
            out = self._c.query(TableName=self._t, **kw)
            items += [self._from(i) for i in out.get("Items", [])]
            if "LastEvaluatedKey" not in out or kw.get("Limit"):
                return items
            kw["ExclusiveStartKey"] = out["LastEvaluatedKey"]

    def query(self, pk: str, sk_prefix: str | None = None) -> list[Item]:
        cond = "PK = :pk" + (" AND begins_with(SK, :p)" if sk_prefix else "")
        vals = {":pk": {"S": pk}, **({":p": {"S": sk_prefix}} if sk_prefix else {})}
        return self._query(KeyConditionExpression=cond, ExpressionAttributeValues=vals, ConsistentRead=True)

    def query_index(self, index: int, pk: str, *, sk_lte: str | None = None, descending: bool = False,
                    limit: int | None = None) -> list[Item]:
        cond = f"gsi{index}pk = :pk" + (f" AND gsi{index}sk <= :hi" if sk_lte else "")
        vals = {":pk": {"S": pk}, **({":hi": {"S": sk_lte}} if sk_lte else {})}
        kw: dict[str, Any] = {"IndexName": f"GSI{index}", "KeyConditionExpression": cond,
                              "ExpressionAttributeValues": vals, "ScanIndexForward": not descending}
        if limit:
            kw["Limit"] = limit
        return self._query(**kw)

    def transact(self, ops: list[dict[str, Any]]) -> None:
        items = []
        for op in ops:
            if "put" in op:
                items.append({"Put": {"TableName": self._t, "Item": self._to(op["put"]),
                                      **self._cond(op.get("if_absent", False), op.get("if_version"))}})
            else:
                pk, sk = op["delete"]
                items.append({"Delete": {"TableName": self._t, "Key": {"PK": {"S": pk}, "SK": {"S": sk}}}})
        try:
            self._c.transact_write_items(TransactItems=items)
        except self._c.exceptions.TransactionCanceledException as exc:
            raise ConditionFailed(str(exc)) from exc

    def increment(self, pk: str, sk: str, field: str) -> int:
        out = self._c.update_item(TableName=self._t, Key={"PK": {"S": pk}, "SK": {"S": sk}},
                                  UpdateExpression="ADD #f :one", ExpressionAttributeNames={"#f": field},
                                  ExpressionAttributeValues={":one": {"N": "1"}}, ReturnValues="UPDATED_NEW")
        return int(out["Attributes"][field]["N"])
