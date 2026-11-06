"""Backend flag: `mock` (in-memory, no AWS) or `aws` (real boto3 calls).

Set AIDLC_BACKEND in the environment or in the env file chosen by AIDLC_ENV_FILE.
Default is `mock`, so nothing reaches AWS unless someone turns it on.
"""

from __future__ import annotations

from enum import StrEnum

from aidlc_e2e.config import get


class Backend(StrEnum):
    MOCK = "mock"
    AWS = "aws"


def current_backend() -> Backend:
    raw = (get("AIDLC_BACKEND", "mock") or "mock").strip().lower()
    try:
        return Backend(raw)
    except ValueError:
        raise ValueError(f"AIDLC_BACKEND must be 'mock' or 'aws', got {raw!r}") from None


def aws_client(service: str, region: str | None = None):
    """Create a boto3 client. Imported lazily so mock mode needs no boto3 and no credentials."""
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - only when the aws extra is missing
        raise RuntimeError("AIDLC_BACKEND=aws needs boto3: uv sync --extra aws") from exc
    return boto3.client(service, region_name=region or get("AWS_REGION", "ap-south-1"))
