"""Malware verdicts. The mock spots the standard EICAR test string. The real one reads GuardDuty's object tag (ADR-009)."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from submit.objects import MockObjectStore

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class Verdict(StrEnum):
    CLEAN = "CLEAN"
    INFECTED = "INFECTED"
    PENDING = "PENDING"   # no result yet
    FAILED = "FAILED"     # scanner could not scan (unsupported, access denied, error)


class Scanner(Protocol):
    def verdict(self, key: str) -> Verdict: ...


class MockScanner:
    def __init__(self, store: MockObjectStore) -> None:
        self._store = store
        self.stalled: set[str] = set()   # keys whose scan never finishes (tests the timeout sweeper)
        self.broken: set[str] = set()    # keys the scanner cannot scan

    def verdict(self, key: str) -> Verdict:
        if key in self.stalled:
            return Verdict.PENDING
        if key in self.broken:
            return Verdict.FAILED
        return Verdict.INFECTED if EICAR in self._store.read(MockObjectStore.QUARANTINE, key) else Verdict.CLEAN


class GuardDutyScanner:
    """GuardDuty Malware Protection for S3 tags each object with GuardDutyMalwareScanStatus."""

    def __init__(self, client, quarantine_bucket: str) -> None:
        self._c, self._b = client, quarantine_bucket

    def verdict(self, key: str) -> Verdict:
        tags = self._c.get_object_tagging(Bucket=self._b, Key=key).get("TagSet", [])
        status = next((t["Value"] for t in tags if t["Key"] == "GuardDutyMalwareScanStatus"), None)
        return {None: Verdict.PENDING, "NO_THREATS_FOUND": Verdict.CLEAN, "THREATS_FOUND": Verdict.INFECTED}.get(
            status, Verdict.FAILED)
