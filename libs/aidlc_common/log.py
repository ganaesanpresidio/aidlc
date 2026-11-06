"""Safe logging: only allow-listed fields are written, so personal data cannot leak by accident."""

from __future__ import annotations

import json
import logging
from typing import Any

ALLOWED_FIELDS = frozenset({
    "request_id", "unit", "action", "claim_ref", "claim_id", "receipt_id", "line_id", "status",
    "code", "rules_version", "count", "size_bytes", "mime_type", "outcome", "duration_ms", "backend",
})

_logger = logging.getLogger("aidlc")


def safe_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}


def log(level: int, message: str, **fields: Any) -> dict[str, Any]:
    record = {"message": message, **safe_fields(fields)}
    _logger.log(level, json.dumps(record, default=str))
    return record


def info(message: str, **fields: Any) -> dict[str, Any]:
    return log(logging.INFO, message, **fields)


def error(message: str, **fields: Any) -> dict[str, Any]:
    return log(logging.ERROR, message, **fields)
