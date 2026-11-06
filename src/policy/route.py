"""Pick the approval tier and chain, and check segregation of duties (SOD-1 to SOD-4). Pure."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from policy.errors import PolicyError
from policy.money import check_currency, to_decimal  # noqa: F401  (check_currency kept for symmetry)

ROLES = ("LINE_MANAGER", "DEPARTMENT_HEAD", "FINANCE_CONTROLLER", "CFO")


def parse_route_request(raw: Any, grades: list[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PolicyError(400, "INVALID_REQUEST", "body must be an object")
    for field in ("claimRef", "submitter"):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise PolicyError(400, "INVALID_REQUEST", f"{field} is required")
    grade = raw.get("grade")
    if grade not in grades:
        raise PolicyError(400, "UNKNOWN_GRADE", f"grade must be one of {', '.join(grades)}")
    total = to_decimal(raw.get("totalInr"), "totalInr")
    if total <= 0:
        raise PolicyError(400, "INVALID_REQUEST", "totalInr must be above zero")
    if not isinstance(raw.get("requiresException"), bool):
        raise PolicyError(400, "INVALID_REQUEST", "requiresException must be true or false")
    payer = raw.get("payer")
    if payer is not None and (not isinstance(payer, str) or not payer.strip()):
        raise PolicyError(400, "INVALID_REQUEST", "payer must be a non-empty id when given")
    holders = raw.get("roleHolders")
    if not isinstance(holders, dict):
        raise PolicyError(400, "INVALID_REQUEST", "roleHolders must be an object")
    parsed: dict[str, dict[str, str]] = {}
    for role, h in holders.items():
        if role not in ROLES:
            raise PolicyError(400, "INVALID_REQUEST", f"unknown role '{role}'")
        if not isinstance(h, dict) or not isinstance(h.get("id"), str) or not h["id"].strip():
            raise PolicyError(400, "INVALID_REQUEST", f"roleHolders.{role}.id is required")
        if h.get("grade") not in grades:
            raise PolicyError(400, "UNKNOWN_GRADE", f"roleHolders.{role}.grade must be one of {', '.join(grades)}")
        parsed[role] = {"id": h["id"], "grade": h["grade"]}
    return {"claimRef": raw["claimRef"], "submitter": raw["submitter"], "grade": grade, "total": total,
            "requiresException": raw["requiresException"], "payer": payer, "holders": parsed}


def route_claim(rules: dict, req: dict[str, Any]) -> dict[str, Any]:
    total: Decimal = req["total"]
    tier = next(t for t in rules["approval_tiers"]
                if t["max_total"] is None or total <= to_decimal(t["max_total"], "max_total"))
    steps = list(tier["steps"])
    if req["requiresException"] and rules["exception_approver"] not in steps:
        steps.append(rules["exception_approver"])

    sod = rules["segregation_of_duties"]
    rank = {g: i for i, g in enumerate(rules["grades"])}
    chain: list[dict[str, str]] = []
    seen: set[str] = set()
    for role in steps:
        holder = req["holders"].get(role)
        if holder is None:
            return {"tier": tier["id"], "blocked": {"code": "MISSING_ROLE_HOLDER", "role": role}}
        who = holder["id"]
        if sod["no_self_approval"] and who == req["submitter"]:
            return {"tier": tier["id"], "blocked": {"code": "SOD-1", "role": role}}
        if sod["distinct_approvers"] and who in seen:
            return {"tier": tier["id"], "blocked": {"code": "SOD-2", "role": role}}
        if sod["payer_cannot_approve"] and req["payer"] is not None and who == req["payer"]:
            return {"tier": tier["id"], "blocked": {"code": "SOD-3", "role": role}}
        if sod["approver_grade_at_least_submitter"] and rank[holder["grade"]] < rank[req["grade"]]:
            return {"tier": tier["id"], "blocked": {"code": "SOD-4", "role": role}}
        seen.add(who)
        chain.append({"role": role, "approver": who})
    return {"tier": tier["id"], "chain": chain}
