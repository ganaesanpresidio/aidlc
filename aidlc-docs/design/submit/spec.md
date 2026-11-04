---
id: SPEC-submit
title: Spec — submit unit
activity: DIS-04
unit: submit
status: Draft — awaiting design review
version: 0.1.0
last_updated: 2026-11-04
owner: Engineer
---

# Spec: `submit` unit

Scope from [submit.md](../../inception/units/submit.md). Build order 2. Design: [lld.md](lld.md). Plan: [plan.md](plan.md). Stories: [user-stories.md](../../inception/user-stories.md).

## Purpose

Let an employee build a claim of expense lines, attach receipts, and submit it for approval, with every action audited and no personal data in logs.

## Coverage

| Story | Jira | Design depth in this LLD |
| --- | --- | --- |
| US-001 Submit with receipts | [DEV-2](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-2) | Full: AC1 to AC10 mapped |
| US-002 Draft | [DEV-3](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-3) | Built in: a claim starts as `Draft` |
| US-003 Missing-receipt declaration | [DEV-4](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-4) | Extension point only. Story is title-only |
| US-004 Withdraw | [DEV-5](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-5) | State change and event defined. Details when story is written |
| US-005 Block duplicates | [DEV-6](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-6) | Detection built for AC9 (warn). Block is a rule flag later |
| US-006 Retention delete | [DEV-7](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-7) | Expiry index and daily job defined |

Stories US-002 to US-006 are title-only in Jira, so only the hooks they need are designed. They get detailed specs when written.

## Requirements

| ID | Requirement | Source |
| --- | --- | --- |
| S-FR1 | Create a claim with 1 or more lines: date, category, amount, currency (INR default), description | PRD FR-1, FR-2 |
| S-FR2 | Attach 1 to 5 receipts per line: JPEG, PNG, HEIC, PDF, up to 10 MB each | PRD FR-3 |
| S-FR3 | Camera capture on a phone is a normal receipt upload | PRD FR-4 |
| S-FR4 | Check type, size and malware before a receipt is stored | PRD FR-5 |
| S-FR5 | Submit only when lines are complete and every line needing a receipt has one. Policy `evaluate` decides | PRD FR-6, AC7, AC7a |
| S-FR6 | On submit: unique reference, status `Submitted`, no more edits | PRD FR-7, AC8 |
| S-FR7 | Warn if the same file is on another of the employee's claims | PRD FR-8, AC9 |
| S-FR8 | Audit event for every create, attach, remove, submit, withdraw. No personal data in logs | AC10, NFR audit |
| S-FR9 | Delete receipts when the retention period ends | PRD NFR-4, US-006 |

## Acceptance criteria

US-001 AC1 to AC10 apply as written in [user-stories.md](../../inception/user-stories.md). The test mapping is in [lld.md](lld.md) section 9. Added criteria:

| # | Given / When / Then |
| --- | --- |
| X1 | Given I submit twice with the same `Idempotency-Key`, then I get the same reference and one `ClaimSubmitted` event |
| X2 | Given a submitted claim, when I try to edit a line or receipt, then 409 `CLAIM_NOT_EDITABLE` |
| X3 | Given a receipt is still being scanned, when I submit, then submit is blocked with "Receipt still being checked" |
| X4 | Given another employee's claim id, when I read it, then 404, not 403 |

## Constraints

p95 under 300 ms reads and 500 ms writes (excluding upload). 10 MB upload in 10 s or less. KMS, TLS, `ap-south-1` only. Fail closed: if `policy` is down, submit is refused, never allowed.
