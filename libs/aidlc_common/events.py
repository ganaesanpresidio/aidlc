"""Event bus and audit trail. Events carry ids and amounts only, never personal data."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from aidlc_common.clock import Clock, SystemClock, new_uuid


def envelope(name: str, payload: dict[str, Any], *, claim_ref: str | None = None,
             rules_version: int | None = None, clock: Clock | None = None, version: int = 1,
             include_claim_ref: bool = True) -> dict[str, Any]:
    """Standard event envelope from interfaces.md. `claimRef` is omitted for events with no claim."""
    clock = clock or SystemClock()
    event: dict[str, Any] = {
        "event": name,
        "version": version,
        "id": new_uuid(),
        "occurredAt": clock.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "payload": payload,
    }
    if include_claim_ref:
        event["claimRef"] = claim_ref
    if rules_version is not None:
        event["rulesVersion"] = rules_version
    return event


class EventBus(Protocol):
    def publish(self, event: dict[str, Any]) -> None: ...


class InMemoryEventBus:
    """Mock bus. Keeps every event and calls subscribers, so units can be wired together locally."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._subs: dict[str, list[Callable[[dict[str, Any]], None]]] = {}

    def subscribe(self, name: str, handler: Callable[[dict[str, Any]], None]) -> None:
        self._subs.setdefault(name, []).append(handler)

    def publish(self, event: dict[str, Any]) -> None:
        self.events.append(json.loads(json.dumps(event)))  # store a copy, as a real bus would
        for handler in self._subs.get(event["event"], []):
            handler(event)

    def of(self, name: str) -> list[dict[str, Any]]:
        return [e for e in self.events if e["event"] == name]


class EventBridgeBus:
    """Real bus. UNVERIFIED against AWS until a login is available (tested with botocore Stubber only)."""

    def __init__(self, client, bus_name: str, source: str) -> None:
        self._client, self._bus, self._source = client, bus_name, source

    def publish(self, event: dict[str, Any]) -> None:
        out = self._client.put_events(Entries=[{
            "EventBusName": self._bus,
            "Source": self._source,
            "DetailType": f"{event['event']}.v{event.get('version', 1)}",
            "Detail": json.dumps(event),
        }])
        if out.get("FailedEntryCount"):
            raise RuntimeError(f"event publish failed: {out['Entries'][0].get('ErrorCode', 'unknown')}")


class ReliableBus:
    """Wraps a bus so a publish failure never undoes a write that already happened (Q44).

    A failed event is queued and retried by `flush`. Used for every event and audit record.
    """

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self.pending: list[dict[str, Any]] = []

    def publish(self, event: dict[str, Any]) -> None:
        try:
            self._bus.publish(event)
        except Exception as exc:
            self.pending.append(event)
            from aidlc_common import log

            log.error("event publish failed, queued for retry", code=type(exc).__name__)

    def flush(self) -> int:
        """Retry queued events in order, stopping at the first failure. Returns how many were sent."""
        sent = 0
        for event in list(self.pending):
            try:
                self._bus.publish(event)
            except Exception:
                break
            self.pending.remove(event)
            sent += 1
        return sent


class AuditLog:
    """Audit trail: who, what, when, which claim. Written as an `Audit` event on the bus."""

    def __init__(self, bus: EventBus, clock: Clock | None = None) -> None:
        self._bus, self._clock = bus, clock or SystemClock()

    def record(self, *, actor: str, action: str, ref: str | None = None, rules_version: int | None = None,
               outcome: str = "ok", detail: dict[str, Any] | None = None) -> None:
        payload = {"actor": actor, "action": action, "outcome": outcome, "detail": detail or {}}
        self._bus.publish(envelope("Audit", payload, claim_ref=ref, rules_version=rules_version,
                                   clock=self._clock))
