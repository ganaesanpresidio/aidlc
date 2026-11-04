"""Validate DIS-04 contracts: OpenAPI files and event JSON schemas under aidlc-docs/design/<unit>/api/.

`uv run aidlc-e2e design` — exit 1 if any file is invalid.
"""

from __future__ import annotations

import json
import sys

import yaml
from jsonschema import Draft202012Validator
from openapi_spec_validator import validate

from aidlc_e2e.config import PROJECT_ROOT

DESIGN = PROJECT_ROOT / "aidlc-docs" / "design"


def run() -> bool:
    ok = True
    files = sorted(DESIGN.glob("*/api/openapi.yaml")) + sorted(DESIGN.glob("*/api/events/*.schema.json"))
    if not files:
        print("  FAIL  no contract files found under aidlc-docs/design/*/api/")
        return False
    for f in files:
        rel = f.relative_to(PROJECT_ROOT)
        try:
            if f.suffix == ".yaml":
                validate(yaml.safe_load(f.read_text()))
            else:
                Draft202012Validator.check_schema(json.loads(f.read_text()))
            print(f"  OK    {rel}")
        except Exception as exc:  # report and continue so every bad file is listed
            ok = False
            print(f"  FAIL  {rel}: {type(exc).__name__}: {str(exc).splitlines()[0][:160]}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
