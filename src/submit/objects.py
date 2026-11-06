"""Receipt files: quarantine and clean buckets. `MockObjectStore` behaves like S3 for the rules that matter.

The real adapter (`S3ObjectStore`) is UNVERIFIED against AWS until a login is available.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Protocol

MAX_BYTES = 10 * 1024 * 1024
ALLOWED_MIME = ("image/jpeg", "image/png", "image/heic", "application/pdf")
HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"}


def sniff_mime(head: bytes) -> str | None:
    """Work out the real file type from its first bytes. The declared type is never trusted."""
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if len(head) >= 12 and head[4:8] == b"ftyp" and head[8:12] in HEIC_BRANDS:
        return "image/heic"
    return None


class UploadRejected(Exception):
    """The store refused an upload (it broke a condition of the presigned POST)."""


@dataclass
class UploadSlot:
    url: str
    fields: dict[str, str]
    expires_in: int = 300


class ObjectStore(Protocol):
    def create_upload_slot(self, key: str, mime: str, max_bytes: int, sha256_hex: str) -> UploadSlot: ...
    def head_bytes(self, bucket: str, key: str, n: int = 16) -> bytes: ...
    def move_to_clean(self, key_from: str, key_to: str) -> None: ...
    def delete(self, bucket: str, key: str) -> None: ...
    def signed_url(self, key: str, seconds: int = 60) -> str: ...
    def exists(self, bucket: str, key: str) -> bool: ...


class MockObjectStore:
    QUARANTINE, CLEAN = "quarantine", "receipts"

    def __init__(self) -> None:
        self.buckets: dict[str, dict[str, bytes]] = {self.QUARANTINE: {}, self.CLEAN: {}}
        self._slots: dict[str, dict[str, Any]] = {}

    def create_upload_slot(self, key: str, mime: str, max_bytes: int, sha256_hex: str) -> UploadSlot:
        token = hashlib.sha256(f"{key}{sha256_hex}".encode()).hexdigest()[:16]
        self._slots[token] = {"key": key, "mime": mime, "max": max_bytes, "sha": sha256_hex.lower()}
        return UploadSlot(url=f"mock://{self.QUARANTINE}", fields={"key": key, "token": token,
                                                                    "Content-Type": mime,
                                                                    "x-amz-checksum-sha256": sha256_hex})

    def post(self, fields: dict[str, str], content: bytes, content_type: str) -> None:
        """What the browser does with the presigned POST. Enforces the same conditions S3 would."""
        slot = self._slots.get(fields.get("token", ""))
        if slot is None or slot["key"] != fields.get("key"):
            raise UploadRejected("slot not valid")
        if not 1 <= len(content) <= slot["max"]:
            raise UploadRejected("size outside the allowed range")
        if content_type != slot["mime"]:
            raise UploadRejected("content type does not match")
        if hashlib.sha256(content).hexdigest() != slot["sha"]:
            raise UploadRejected("checksum does not match")
        self.buckets[self.QUARANTINE][slot["key"]] = content

    def head_bytes(self, bucket: str, key: str, n: int = 16) -> bytes:
        return self.buckets[bucket][key][:n]

    def read(self, bucket: str, key: str) -> bytes:
        return self.buckets[bucket][key]

    def move_to_clean(self, key_from: str, key_to: str) -> None:
        self.buckets[self.CLEAN][key_to] = self.buckets[self.QUARANTINE].pop(key_from)

    def delete(self, bucket: str, key: str) -> None:
        self.buckets[bucket].pop(key, None)

    def signed_url(self, key: str, seconds: int = 60) -> str:
        if key not in self.buckets[self.CLEAN]:
            raise KeyError(key)
        return f"mock://{self.CLEAN}/{key}?expires={seconds}"

    def exists(self, bucket: str, key: str) -> bool:
        return key in self.buckets[bucket]


class S3ObjectStore:
    def __init__(self, client, quarantine_bucket: str, clean_bucket: str, kms_key_id: str | None = None) -> None:
        self._c, self._q, self._b, self._kms = client, quarantine_bucket, clean_bucket, kms_key_id

    def _bucket(self, name: str) -> str:
        return {MockObjectStore.QUARANTINE: self._q, MockObjectStore.CLEAN: self._b}.get(name, name)

    def create_upload_slot(self, key: str, mime: str, max_bytes: int, sha256_hex: str) -> UploadSlot:
        import base64

        b64 = base64.b64encode(bytes.fromhex(sha256_hex)).decode()
        fields = {"Content-Type": mime, "x-amz-checksum-sha256": b64}
        conditions = [{"Content-Type": mime}, {"x-amz-checksum-sha256": b64}, ["content-length-range", 1, max_bytes]]
        post = self._c.generate_presigned_post(self._q, key, Fields=fields, Conditions=conditions, ExpiresIn=300)
        return UploadSlot(url=post["url"], fields=post["fields"], expires_in=300)

    def head_bytes(self, bucket: str, key: str, n: int = 16) -> bytes:
        out = self._c.get_object(Bucket=self._bucket(bucket), Key=key, Range=f"bytes=0-{n - 1}")
        return out["Body"].read()

    def move_to_clean(self, key_from: str, key_to: str) -> None:
        extra = {"ServerSideEncryption": "aws:kms", **({"SSEKMSKeyId": self._kms} if self._kms else {})}
        self._c.copy_object(Bucket=self._b, Key=key_to, CopySource={"Bucket": self._q, "Key": key_from}, **extra)
        self._c.delete_object(Bucket=self._q, Key=key_from)

    def delete(self, bucket: str, key: str) -> None:
        self._c.delete_object(Bucket=self._bucket(bucket), Key=key)

    def signed_url(self, key: str, seconds: int = 60) -> str:
        return self._c.generate_presigned_url("get_object", Params={"Bucket": self._b, "Key": key}, ExpiresIn=seconds)

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self._c.head_object(Bucket=self._bucket(bucket), Key=key)
            return True
        except self._c.exceptions.ClientError:
            return False
