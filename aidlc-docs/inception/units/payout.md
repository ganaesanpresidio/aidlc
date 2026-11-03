---
id: UNIT-payout
title: Unit — payout
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
build_order: 4
---

# Unit `payout`

| Field | Value |
| --- | --- |
| Scope | Create a reimbursement for an approved claim, pass to finance, record paid or failed, show status |
| Owner | Architect (team to be named) |
| Stories | None yet. Needs new stories (reimbursement tracking). See [story-map.md](story-map.md) |
| Depends on | `approve` (events) |
| Build order | 4 |

## Data owned

Reimbursement records (claim ref, amount in INR, payer, status, paid at).

## APIs (v1)

| Method and path | Purpose |
| --- | --- |
| `GET /v1/payouts/{claimRef}` | Status of a reimbursement |
| `POST /v1/payouts/{claimRef}/mark-paid` | Finance records payment (payer must not be an approver of the claim) |

## Events

Consumes `ClaimApproved`. Publishes `PayoutIssued`, `PayoutFailed`.

## PII and controls

Employee bank details are not stored in v1. Payment runs through the bank's existing finance system by reference only. Every state change writes an immutable audit event. SOD-3 enforced here.

## AWS services (candidates)

Lambda, DynamoDB, EventBridge, SQS.
