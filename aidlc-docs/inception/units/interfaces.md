---
id: IFACE-001
title: Interface contracts (draft)
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.2.0
last_updated: 2026-11-04
owner: Architect
---

# Interface contracts (draft)

Rules: events are past tense, carry a version, and hold ids not personal data. APIs are versioned in the path. No unit reads another unit's tables ([ADR-005](../../decisions/adr-005-unit-boundaries.md), [ADR-006](../../decisions/adr-006-versioned-events.md)). Full payload schemas are written per unit in DIS-04.

## Envelope for every event

```json
{
  "event": "ClaimSubmitted",
  "version": 1,
  "id": "uuid",
  "occurredAt": "2026-11-03T10:00:00Z",
  "claimRef": "CLM-0001",
  "rulesVersion": 1,
  "payload": {}
}
```

## Events

| Event (v1) | Producer | Consumers | Payload (ids and amounts only) |
| --- | --- | --- | --- |
| `PolicyRulesPublished` | policy | submit, approve, bi | rulesVersion, effectiveFrom |
| `ReceiptStored` | submit | ocr, bi | receiptId, claimRef, lineId, mimeType, sizeBytes |
| `ReceiptsExpired` | submit | bi | receiptIds, retentionVersion |
| `ClaimSubmitted` | submit | approve, bi | claimRef, submitterId, gradeOfSubmitter, totalInr, lineCount, requiresException |
| `ClaimWithdrawn` | submit | approve, bi | claimRef |
| `ReceiptExtracted` | ocr | submit, bi | receiptId, confidence |
| `ReceiptExtractionFailed` | ocr | submit | receiptId, reason |
| `ClaimStepApproved` | approve | bi | claimRef, role, stepNo |
| `ClaimStepEscalated` | approve | bi | claimRef, fromRole, toRole |
| `ClaimApproved` | approve | payout, submit, bi | claimRef, totalInr |
| `ClaimRejected` | approve | submit, bi | claimRef, role |
| `PayoutIssued` | payout | submit, bi | claimRef, paidAt |
| `PayoutFailed` | payout | submit, bi | claimRef, reason |

## APIs between units

| Caller | Callee | Call | Why synchronous |
| --- | --- | --- | --- |
| submit | policy | `POST /v1/policy/evaluate` | Employee needs an answer before submit |
| approve | policy | `POST /v1/policy/route` | Chain is needed when the claim arrives |
| submit, approve | policy | `GET /v1/policy/rules?effectiveOn=` | Read rules in force |

Everything else is event-driven.

## Compatibility rule

A change that removes or renames a field is a new major version (`v2`) and both versions run side by side until consumers move.

## Change log

| Version | Date | Change |
| --- | --- | --- |
| 0.1.0 | 2026-11-03 | First draft |
| 0.2.0 | 2026-11-04 | `ClaimSubmitted` gains `submitterId` and `requiresException` so `approve` can route without reading `submit` data (found in the submit LLD) |
