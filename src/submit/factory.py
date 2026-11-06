"""Build the submit unit for the chosen backend. `mock` runs everything in memory; `aws` uses real boto3 calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aidlc_common.backend import Backend, aws_client, current_backend
from aidlc_common.clock import Clock, SystemClock
from aidlc_common.events import EventBridgeBus, EventBus, InMemoryEventBus
from aidlc_e2e.config import get
from submit.objects import MockObjectStore, S3ObjectStore
from submit.policy_client import HttpPolicyClient, InProcessPolicyClient, PolicyClient
from submit.scanner import GuardDutyScanner, MockScanner
from submit.service import ClaimService, Settings
from submit.table import DynamoTable, InMemoryTable


@dataclass
class MockStack:
    """Everything behind the service in mock mode, so tests and the local server can reach the fakes."""

    service: ClaimService
    table: InMemoryTable
    objects: MockObjectStore
    scanner: MockScanner
    policy_client: InProcessPolicyClient
    policy_service: Any
    bus: InMemoryEventBus
    clock: Clock


def wire_status_events(bus: InMemoryEventBus, service: ClaimService) -> None:
    for name in ("ClaimApproved", "ClaimRejected", "PayoutIssued"):
        bus.subscribe(name, service.on_event)


def settings_from_config() -> Settings:
    return Settings(retention_days=int(get("AIDLC_RETENTION_DAYS", "365")))


def build_mock_stack(clock: Clock | None = None, bus: InMemoryEventBus | None = None,
                     settings: Settings | None = None, seed_policy: bool = True) -> MockStack:
    from policy.factory import build_service as build_policy
    from policy.factory import seed_example_rules

    clock = clock or SystemClock()
    bus = bus or InMemoryEventBus()
    policy_service = build_policy(Backend.MOCK, clock=clock, bus=bus)
    if seed_policy:
        seed_example_rules(policy_service)
    policy_client = InProcessPolicyClient(policy_service)
    table, objects = InMemoryTable(), MockObjectStore()
    scanner = MockScanner(objects)
    service = ClaimService(table, objects, scanner, policy_client, bus, clock, settings or settings_from_config())
    wire_status_events(bus, service)
    return MockStack(service, table, objects, scanner, policy_client, policy_service, bus, clock)


def build_service(backend: Backend | None = None, clock: Clock | None = None, bus: EventBus | None = None,
                  policy: PolicyClient | None = None) -> ClaimService:
    backend = backend or current_backend()
    if backend is Backend.MOCK:
        return build_mock_stack(clock, bus if isinstance(bus, InMemoryEventBus) else None).service
    region = get("AWS_REGION", "ap-south-1")
    quarantine, clean = get("QUARANTINE_BUCKET", "aidlc-quarantine"), get("RECEIPTS_BUCKET", "aidlc-receipts")
    s3 = aws_client("s3", region)
    return ClaimService(
        DynamoTable(aws_client("dynamodb", region), get("SUBMIT_TABLE", "submit-claims")),
        S3ObjectStore(s3, quarantine, clean, get("RECEIPTS_KMS_KEY_ID") or None),
        GuardDutyScanner(s3, quarantine),
        policy or HttpPolicyClient(get("POLICY_URL", "https://policy.internal.invalid"), region),
        bus or EventBridgeBus(aws_client("events", region), get("EVENT_BUS_NAME", "aidlc-events"), "aidlc.submit"),
        clock or SystemClock(), settings_from_config())
