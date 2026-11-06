"""Build a PolicyService for the chosen backend. `mock` needs no AWS; `aws` uses real boto3 calls."""

from __future__ import annotations

from datetime import date

from aidlc_common.backend import Backend, aws_client, current_backend
from aidlc_common.clock import Clock, SystemClock
from aidlc_common.events import EventBridgeBus, EventBus, InMemoryEventBus
from aidlc_e2e.config import get
from policy.rules import REPO_ROOT
from policy.service import PolicyService
from policy.store import DynamoRulesStore, InMemoryRulesStore


def build_service(backend: Backend | None = None, clock: Clock | None = None,
                  bus: EventBus | None = None) -> PolicyService:
    backend = backend or current_backend()
    clock = clock or SystemClock()
    if backend is Backend.MOCK:
        return PolicyService(InMemoryRulesStore(), bus or InMemoryEventBus(), clock)
    table = get("POLICY_TABLE", "policy-rules")
    bus_name = get("EVENT_BUS_NAME", "aidlc-events")
    store = DynamoRulesStore(aws_client("dynamodb"), table)
    return PolicyService(store, bus or EventBridgeBus(aws_client("events"), bus_name, "aidlc.policy"), clock)


def seed_example_rules(service: PolicyService, today: date | None = None) -> dict:
    """Publish the example rules (MOCK values) effective today. For local runs only."""
    import yaml

    doc = yaml.safe_load((REPO_ROOT / "aidlc-docs" / "inception" / "policy-rules.example.yaml").read_text())
    doc["effective_from"] = (today or service._clock.today()).isoformat()
    return service.publish(doc, actor="seed", groups=["finance-admin"], idempotency_key="seed-example-rules")
