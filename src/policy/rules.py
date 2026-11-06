"""Validate a rules document: JSON Schema plus the cross-field checks the schema cannot express."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = Path(os.environ.get("AIDLC_RULES_SCHEMA",
                                  REPO_ROOT / "aidlc-docs" / "inception" / "policy-rules.schema.json"))
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    return Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))


def validate_rules(doc: Any) -> list[str]:
    """Return a list of problems. Empty means valid."""
    if not isinstance(doc, dict):
        return ["rules must be a JSON object"]
    errors = sorted(f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
                    for e in _validator().iter_errors(doc))
    if errors:
        return errors
    out: list[str] = []
    ef = doc["effective_from"]
    if not _DATE.match(ef):
        out.append("effective_from must be a date like 2026-11-04")
    else:
        try:
            date.fromisoformat(ef)
        except ValueError:
            out.append("effective_from is not a real date")
    tiers = doc["approval_tiers"]
    if tiers[-1]["max_total"] is not None:
        out.append("last tier must have max_total null (no upper bound)")
    caps = [t["max_total"] for t in tiers[:-1]]
    if any(c is None for c in caps):
        out.append("only the last tier may have max_total null")
    else:
        if caps != sorted(caps) or len(set(caps)) != len(caps):
            out.append("tier max_total values must be strictly increasing")
        if any(c <= 0 for c in caps):
            out.append("tier max_total values must be above zero")
    ids = [t["id"] for t in tiers]
    if len(set(ids)) != len(ids):
        out.append("tier ids must be unique")
    for t in tiers:
        if len(set(t["steps"])) != len(t["steps"]):
            out.append(f"tier {t['id']} lists the same role twice")
    for cat, lim in doc["category_limits"].items():
        for g in doc["grades"]:
            if g not in lim:
                out.append(f"category {cat} has no limit for grade {g}")
            elif isinstance(lim[g], bool) or not isinstance(lim[g], (int, float)) or lim[g] < 0:
                out.append(f"category {cat} limit for {g} must be a number of 0 or more")
        extra = set(lim) - set(doc["grades"]) - {"unit"}
        if extra:
            out.append(f"category {cat} has limits for unknown grades: {', '.join(sorted(extra))}")
    return out
