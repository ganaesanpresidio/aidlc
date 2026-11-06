"""Validate the policy rules config against its schema and route sample claims.

`uv run aidlc-e2e rules` runs DIS-02 step 7: proves the rules work as config only.
All sample data is synthetic.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from aidlc_e2e.config import PROJECT_ROOT

INCEPTION = PROJECT_ROOT / "aidlc-docs" / "inception"
GRADE_RANK = {"G1": 1, "G2": 2, "G3": 3}
ROLE_RANK = {"LINE_MANAGER": 2, "DEPARTMENT_HEAD": 3, "FINANCE_CONTROLLER": 3, "CFO": 3}


def load_rules(path: Path | None = None) -> dict:
    return yaml.safe_load((path or INCEPTION / "policy-rules.example.yaml").read_text())


def validate(rules: dict) -> list[str]:
    schema = json.loads((INCEPTION / "policy-rules.schema.json").read_text())
    errors = [e.message for e in Draft202012Validator(schema).iter_errors(rules)]
    tiers = rules["approval_tiers"]
    caps = [t["max_total"] for t in tiers]
    if caps[-1] is not None:
        errors.append("last tier must have max_total null (no upper bound)")
    finite = [c for c in caps[:-1] if c is not None]
    if finite != sorted(finite) or len(set(finite)) != len(finite):
        errors.append("tier max_total values must be strictly increasing")
    for cat, lim in rules["category_limits"].items():
        for g in rules["grades"]:
            if g not in lim:
                errors.append(f"category {cat} has no limit for grade {g}")
    return errors


def route(rules: dict, claim: dict) -> dict:
    """Return the approval chain for a claim, or the reason it is blocked."""
    grade = claim["grade"]
    lines = claim["lines"]
    over = [ln for ln in lines if ln["amount"] > rules["category_limits"][ln["category"]][grade]
            and not ln.get("exception_reason")]
    if over:
        return {"blocked": f"{over[0]['category']} line above {grade} limit, needs exception reason"}
    total = sum(ln["amount"] for ln in lines)
    tier = next(t for t in rules["approval_tiers"] if t["max_total"] is None or total <= t["max_total"])
    steps = list(tier["steps"])
    if any(ln.get("exception_reason") for ln in lines) and rules["exception_approver"] not in steps:
        steps.append(rules["exception_approver"])
    chain = []
    for role in steps:
        who = claim["people"][role]
        if who == claim["submitter"]:
            return {"blocked": f"SOD-1: {role} is the submitter, escalate"}
        if who in chain:
            return {"blocked": f"SOD-2: {who} would approve twice"}
        if claim["people"].get("PAYER") == who:
            return {"blocked": f"SOD-3: {who} is also the payer"}
        if claim["grades"].get(who, 3) < GRADE_RANK[grade]:
            return {"blocked": f"SOD-4: {who} grade below submitter"}
        chain.append(who)
    return {"tier": tier["id"], "chain": chain}


SAMPLES = [
    ("S1 small meals claim", dict(grade="G1", submitter="Asha", grades={"Ravi": 2},
        people={"LINE_MANAGER": "Ravi"}, lines=[{"category": "Meals", "amount": 1200}]),
     {"tier": "T1", "chain": ["Ravi"]}),
    ("S2 mid travel claim", dict(grade="G1", submitter="Asha", grades={"Ravi": 2, "Dev": 3},
        people={"LINE_MANAGER": "Ravi", "DEPARTMENT_HEAD": "Dev"},
        lines=[{"category": "Travel", "amount": 20000}, {"category": "Meals", "amount": 1500}]),
     {"tier": "T2", "chain": ["Ravi", "Dev"]}),
    ("S3 large claim by manager", dict(grade="G2", submitter="Ravi", grades={"Dev": 3, "Fin": 3},
        people={"DEPARTMENT_HEAD": "Dev", "FINANCE_CONTROLLER": "Fin"},
        lines=[{"category": "Travel", "amount": 50000}, {"category": "Accommodation", "amount": 10000}]),
     {"tier": "T3", "chain": ["Dev", "Fin"]}),
    ("S4 self approval blocked", dict(grade="G2", submitter="Ravi", grades={"Ravi": 2},
        people={"LINE_MANAGER": "Ravi"}, lines=[{"category": "Meals", "amount": 900}]),
     {"blocked": "SOD-1: LINE_MANAGER is the submitter, escalate"}),
    ("S5 over limit, no reason", dict(grade="G1", submitter="Asha", grades={"Ravi": 2},
        people={"LINE_MANAGER": "Ravi"}, lines=[{"category": "Meals", "amount": 2000}]),
     {"blocked": "Meals line above G1 limit, needs exception reason"}),
    ("S6 exception adds finance", dict(grade="G1", submitter="Asha", grades={"Ravi": 2, "Fin": 3},
        people={"LINE_MANAGER": "Ravi", "FINANCE_CONTROLLER": "Fin"},
        lines=[{"category": "Meals", "amount": 2000, "exception_reason": "client dinner"}]),
     {"tier": "T1", "chain": ["Ravi", "Fin"]}),
    ("S7 payer also approver", dict(grade="G1", submitter="Asha", grades={"Ravi": 2},
        people={"LINE_MANAGER": "Ravi", "PAYER": "Ravi"}, lines=[{"category": "Meals", "amount": 900}]),
     {"blocked": "SOD-3: Ravi is also the payer"}),
    ("S8 approver below submitter grade", dict(grade="G3", submitter="Zed", grades={"Ravi": 2},
        people={"LINE_MANAGER": "Ravi"}, lines=[{"category": "Meals", "amount": 900}]),
     {"blocked": "SOD-4: Ravi grade below submitter"}),
]


def run() -> bool:
    rules = load_rules()
    errors = validate(rules)
    print("Rules config:", "valid" if not errors else "INVALID")
    for e in errors:
        print("  ERROR", e)
    ok = not errors
    for name, claim, expected in SAMPLES:
        got = route(rules, claim)
        good = got == expected
        ok &= good
        print(f"  {'OK  ' if good else 'FAIL'}  {name}: {got}")
    return ok


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
