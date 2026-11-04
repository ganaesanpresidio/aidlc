---
id: SPEC-policy
title: Spec — policy unit
activity: DIS-04
unit: policy
status: Draft — awaiting design review
version: 0.1.0
last_updated: 2026-11-04
owner: Engineer
---

# Spec: `policy` unit

Scope comes from [policy.md](../../inception/units/policy.md). Build order 1. Design: [lld.md](lld.md). Plan: [plan.md](plan.md).

## Purpose

Keep expense policy as data and answer three questions for other units: what rules are in force, does this claim break them, and who must approve it.

## In scope

| ID | Requirement | Source |
| --- | --- | --- |
| P-FR1 | Return the rules in force on a given date, or a given version | ADR-001 |
| P-FR2 | Evaluate expense lines: category limit by grade, receipt rule, submission window, unknown category | Approval matrix, PRD FR-6, Q22 |
| P-FR3 | Route a claim: pick the tier by claim total, add the exception approver, check SOD-1 to SOD-4 | ADR-002, ADR-003 |
| P-FR4 | Publish a new rules version: schema-validated, immutable, with an effective date | ADR-001, Q18 |
| P-FR5 | Audit every publish with actor, time and version | NFR audit |

## Out of scope

Who holds each role for a given employee (the `approve` unit resolves this from the directory, Q39). Currency conversion (Q20). Any UI for rule editing in v1: publishing is an API call by a finance admin.

## Acceptance criteria

| # | Given / When / Then |
| --- | --- |
| A1 | Given rules v1 effective 2026-11-03, when I read rules for 2026-11-04, then I get v1. For 2026-11-02 I get 404 `NO_RULES_IN_FORCE` |
| A2 | Given a G1 meals line of ₹2,000 without an exception reason, when I evaluate, then the result is not ok and has `LIMIT_EXCEEDED` for that line |
| A3 | Given the same line with an exception reason, when I evaluate, then the result is ok and `requiresException` is true |
| A4 | Given an INR line of ₹1,000 with no receipt, then `RECEIPT_REQUIRED`. At ₹999.99, no violation. A USD line with no receipt gets `RECEIPT_REQUIRED` (Q16, Q17) |
| A5 | Given an expense date 31 days before submission, then `WINDOW_EXPIRED` |
| A6 | Given a claim total of ₹10,000 the tier is T1. At ₹10,001 the tier is T2 |
| A7 | Given the routed approver is the submitter, then `SOD-1` and no chain |
| A8 | Given a finance admin publishes rules that fail the schema, then 422 with the schema errors and nothing is stored |
| A9 | Given a valid publish, then version n+1 is stored, `PolicyRulesPublished` is emitted and an audit event is written |
| A10 | Given any published version, when I try to change it, then it is refused. Versions are immutable |

## Constraints from the NFR matrix

p95 under 300 ms for reads and evaluate/route. Audit 100%. No PII. KMS encrypted. `ap-south-1` only. All numbers come from rules, none in code.

## Reference behaviour

The prototype in [rules_check.py](../../../tools/aidlc_e2e/rules_check.py) already routes 8 synthetic claims correctly. Its samples become the first contract tests.
