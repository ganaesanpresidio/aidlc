---
id: BUILD-policy
title: Build notes — policy unit
activity: BLD-01
unit: policy
status: Built on the mock backend — awaiting Architect review of the changes below
version: 0.1.0
last_updated: 2026-11-04
owner: Engineer
---

# Build notes: `policy` unit

Code: [src/policy/](../../../src/policy/). Tests: [tests/policy/](../../../tests/policy/). Approved design: [lld.md](lld.md).

## Status by bolt

| Bolt | Result |
| --- | --- |
| P1 Store and read rules | Done on the mock backend. Real DynamoDB adapter written and checked with botocore's stubber only |
| P2 Evaluate | Done |
| P3 Route and SoD | Done |
| P4 Publish | Done: idempotency, immutability, event, audit, retry of failed events |
| P5 Harden | Partly: PII-safe logger and number limits done. **Not done** (needs AWS): load test, IaC scan, alarms, DR test |

## How to run it

```bash
uv run pytest tests/policy
uv run aidlc-e2e serve policy
```

`AIDLC_BACKEND=mock` (default) uses in-memory storage and no AWS. `AIDLC_BACKEND=aws` uses real DynamoDB and EventBridge and needs a login. The real adapters are **unverified against AWS**.

## Differences from the approved design (review these)

| # | Change | Why | Contract file touched |
| --- | --- | --- | --- |
| 1 | `evaluate` can return 4 more codes: `FUTURE_DATE_EXPENSE`, `INVALID_QUANTITY`, `MISSING_INR_EQUIVALENT` (and the existing ones) | Real cases the LLD did not list: a future expense date, mileage with no distance, a foreign line with no INR amount (Q40) | [openapi.yaml](api/openapi.yaml): violation enum |
| 2 | Evaluate lines accept optional `amountInr` | Limits are in INR, so a foreign line needs its INR equivalent (Q40) | openapi.yaml: `Line` |
| 3 | `route` accepts optional `rulesVersion` | A claim must be routed by the rules it was checked against, not by whatever is in force later | openapi.yaml: `RouteRequest` |
| 4 | All numbers above 10^15 are refused with 400 | A number like `1e999999999` crashed Python's decimal maths. Found by an edge test | none |
| 5 | Failed event or audit publishes are queued and retried (`flush_pending`) | The write must not be undone, and the audit record must not be lost, if the bus is down (Q44) | none |
| 6 | Denied publish attempts are written to the audit trail | Useful security record; the LLD only audited successes | none |
| 7 | "Today" is the business date in `AIDLC_TIMEZONE` (default Asia/Kolkata), not UTC | Rule dates, the 30-day window and claim references should follow the company day (Q48) | none |
| 8 | Grade order is the order in the rules `grades` list | SOD-4 needs a rank. First is lowest | none |

The contract changes are additive: callers that do not send the new fields still work.

## Not built, on purpose

Real JWT checking (API Gateway does it), the CDK stack, and the deploy pipeline. The local server trusts dev headers and refuses to start unless the backend is `mock`.

## Open items

Load test and p95 check, PII log scan in CI, KMS and region scans, alarms, DR test. All need an AWS account.
