---
id: PLAN-policy
title: Bolt plan — policy unit
activity: DIS-04
unit: policy
status: Draft — awaiting design review
version: 0.1.0
last_updated: 2026-11-04
owner: Engineer
---

# Bolt plan: `policy` unit

Each bolt is 1 to 2 days and ends with passing tests. Code goes in `src/policy/` only after [lld-policy.md](../../approvals/lld-policy.md) shows `Status: APPROVED`.

| Bolt | Goal | Tasks | Done when |
| --- | --- | --- | --- |
| P1 | Store and read rules | CDK table with KMS and PITR. Rules loader, schema validation, 60 s cache. `GET` rules in force and by version | A1 and A10 pass. Schema errors listed |
| P2 | Evaluate | Limit check by grade and unit, receipt rule, window, unknown category, exception flag | A2 to A5 pass. Tier and limit boundary tests pass |
| P3 | Route and SoD | Tier pick, exception approver, SOD-1 to SOD-4, missing role holder | A6 and A7 pass. Prototype samples S1 to S8 pass as fixtures. Property tests pass |
| P4 | Publish | `PUT` with idempotency, extra checks, transaction, event, audit | A8 and A9 pass. Event validates against the schema |
| P5 | Harden | Load test, PII log scan, IaC scan, alarms, runbook | p95 under 300 ms. 0 PII in logs. Alarms wired to the alert hook |

## Order and dependencies

P1, then P2 and P3 in either order, then P4, then P5. No other unit is needed to build or test `policy`.

## Definition of done per bolt

Tests written first and passing. Lint clean. OpenAPI and event schema unchanged or versioned. No numbers from the policy in code. Reviewed in one sitting.
