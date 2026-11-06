"""Rules storage. `InMemoryRulesStore` is the mock; `DynamoRulesStore` is the real adapter.

The real adapter is UNVERIFIED against AWS until a login is available (botocore Stubber tests only).
Layout follows lld.md section 4: PK `RULES`; SK `V#000001` (document), `E#<date>#000001` (pointer).
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, Protocol

from policy.errors import VersionExists


class RulesStore(Protocol):
    def put_version(self, record: dict[str, Any]) -> None: ...
    def get_version(self, version: int) -> dict[str, Any] | None: ...
    def latest(self) -> dict[str, Any] | None: ...
    def in_force(self, on: date) -> dict[str, Any] | None: ...
    def get_idempotent(self, key: str) -> dict[str, Any] | None: ...
    def put_idempotent(self, key: str, entry: dict[str, Any]) -> None: ...


class InMemoryRulesStore:
    def __init__(self) -> None:
        self._versions: dict[int, dict[str, Any]] = {}
        self._idem: dict[str, dict[str, Any]] = {}
        self.reads = 0  # lets tests prove the cache works

    @staticmethod
    def _copy(record: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if record is None else json.loads(json.dumps(record))

    def put_version(self, record: dict[str, Any]) -> None:
        if record["version"] in self._versions:
            raise VersionExists(record["version"])
        self._versions[record["version"]] = self._copy(record)

    def get_version(self, version: int) -> dict[str, Any] | None:
        self.reads += 1
        return self._copy(self._versions.get(version))

    def latest(self) -> dict[str, Any] | None:
        self.reads += 1
        return self._copy(self._versions[max(self._versions)]) if self._versions else None

    def in_force(self, on: date) -> dict[str, Any] | None:
        self.reads += 1
        eligible = [r for r in self._versions.values() if r["effectiveFrom"] <= on.isoformat()]
        if not eligible:
            return None
        return self._copy(max(eligible, key=lambda r: (r["effectiveFrom"], r["version"])))

    def get_idempotent(self, key: str) -> dict[str, Any] | None:
        return self._copy(self._idem.get(key))

    def put_idempotent(self, key: str, entry: dict[str, Any]) -> None:
        self._idem[key] = self._copy(entry)


def _s(value: str) -> dict[str, str]:
    return {"S": value}


class DynamoRulesStore:
    """Real adapter over a boto3 DynamoDB low-level client."""

    PK = "RULES"

    def __init__(self, client, table: str) -> None:
        self._c, self._t = client, table

    @staticmethod
    def _vsk(version: int) -> str:
        return f"V#{version:06d}"

    @staticmethod
    def _esk(effective_from: str, version: int) -> str:
        return f"E#{effective_from}#{version:06d}"

    def put_version(self, record: dict[str, Any]) -> None:
        doc = {"PK": _s(self.PK), "SK": _s(self._vsk(record["version"])), "record": _s(json.dumps(record))}
        pointer = {"PK": _s(self.PK), "SK": _s(self._esk(record["effectiveFrom"], record["version"])),
                   "version": {"N": str(record["version"])}}
        cond = "attribute_not_exists(PK)"
        try:
            self._c.transact_write_items(TransactItems=[
                {"Put": {"TableName": self._t, "Item": doc, "ConditionExpression": cond}},
                {"Put": {"TableName": self._t, "Item": pointer, "ConditionExpression": cond}},
            ])
        except self._c.exceptions.TransactionCanceledException as exc:
            raise VersionExists(record["version"]) from exc

    def get_version(self, version: int) -> dict[str, Any] | None:
        out = self._c.get_item(TableName=self._t, Key={"PK": _s(self.PK), "SK": _s(self._vsk(version))},
                               ConsistentRead=True)
        return json.loads(out["Item"]["record"]["S"]) if "Item" in out else None

    def latest(self) -> dict[str, Any] | None:
        out = self._c.query(TableName=self._t, ConsistentRead=True, ScanIndexForward=False, Limit=1,
                            KeyConditionExpression="PK = :pk AND begins_with(SK, :p)",
                            ExpressionAttributeValues={":pk": _s(self.PK), ":p": _s("V#")})
        items = out.get("Items", [])
        return json.loads(items[0]["record"]["S"]) if items else None

    def in_force(self, on: date) -> dict[str, Any] | None:
        out = self._c.query(TableName=self._t, ScanIndexForward=False, Limit=1,
                            KeyConditionExpression="PK = :pk AND SK BETWEEN :lo AND :hi",
                            ExpressionAttributeValues={":pk": _s(self.PK), ":lo": _s("E#0000"),
                                                       ":hi": _s(f"E#{on.isoformat()}#999999")})
        items = out.get("Items", [])
        return self.get_version(int(items[0]["version"]["N"])) if items else None

    def get_idempotent(self, key: str) -> dict[str, Any] | None:
        out = self._c.get_item(TableName=self._t, Key={"PK": _s(f"IDEM#{key}"), "SK": _s("META")})
        return json.loads(out["Item"]["entry"]["S"]) if "Item" in out else None

    def put_idempotent(self, key: str, entry: dict[str, Any]) -> None:
        self._c.put_item(TableName=self._t, Item={
            "PK": _s(f"IDEM#{key}"), "SK": _s("META"), "entry": _s(json.dumps(entry)),
            "ttl": {"N": str(int(entry.get("expiresAtEpoch", 0)))}})
