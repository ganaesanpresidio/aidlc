import copy

import pytest

from policy.service import PolicyService
from policy.store import InMemoryRulesStore


@pytest.fixture
def store():
    return InMemoryRulesStore()


@pytest.fixture
def service(store, bus, clock):
    return PolicyService(store, bus, clock)


@pytest.fixture
def published(service, example_rules):
    """A service with the example rules published as version 1, effective today."""
    service.publish(copy.deepcopy(example_rules), actor="fin1", groups=["finance-admin"], idempotency_key="key-00000001")
    return service


def line(**kw):
    base = {"lineId": "L1", "category": "Meals", "amount": 500, "currency": "INR",
            "expenseDate": "2026-11-03", "hasReceipt": True}
    base.update(kw)
    return base


def evaluate_body(lines, grade="G1", submission="2026-11-04"):
    return {"grade": grade, "submissionDate": submission, "lines": lines}


def holders(**people):
    """holders(LINE_MANAGER=("Ravi","G2")) -> roleHolders dict"""
    return {role: {"id": who, "grade": grade} for role, (who, grade) in people.items()}


def route_body(total=5000, submitter="Asha", grade="G1", exception=False, payer=None, **people):
    body = {"claimRef": "CLM-2026-000001", "submitter": submitter, "grade": grade, "totalInr": total,
            "requiresException": exception, "roleHolders": holders(**people)}
    if payer:
        body["payer"] = payer
    return body
