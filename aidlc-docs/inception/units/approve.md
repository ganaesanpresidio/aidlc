---
id: UNIT-approve
title: Unit — approve
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
build_order: 3
---

# Unit `approve`

| Field | Value |
| --- | --- |
| Scope | Approver inbox, show receipt beside each line, approve or reject with comment, step chain, escalation after 5 working days |
| Owner | Architect (team to be named) |
| Stories | None yet. Needs new stories (approval routing). See [story-map.md](story-map.md) |
| Depends on | `policy` (route), `submit` (events) |
| Build order | 3 |

## Data owned

Approval step records (claim ref, role, approver, decision, time, comment).

## APIs (v1)

| Method and path | Purpose |
| --- | --- |
| `GET /v1/approvals/inbox` | Claims waiting for the signed-in approver |
| `POST /v1/approvals/{id}/decision` | Approve or reject, comment required on reject |

## Events

Consumes `ClaimSubmitted`, `ClaimWithdrawn`. Publishes `ClaimStepApproved`, `ClaimApproved`, `ClaimRejected`, `ClaimStepEscalated`.

## PII and controls

Approver sees claim and receipt only while assigned. SOD-1 to SOD-4 enforced here using the `policy` result ([ADR-002](../../decisions/adr-002-sod-in-the-model.md)). Every decision writes an audit event.

## AWS services (candidates)

Step Functions (step chain and timers), Lambda, DynamoDB, EventBridge.
