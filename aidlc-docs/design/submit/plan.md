---
id: PLAN-submit
title: Bolt plan — submit unit
activity: DIS-04
unit: submit
status: Draft — awaiting design review
version: 0.1.0
last_updated: 2026-11-04
owner: Engineer
---

# Bolt plan: `submit` unit

Each bolt is 1 to 3 days and ends with passing tests. Code goes in `src/submit/` only after [lld-submit.md](../../approvals/lld-submit.md) shows `Status: APPROVED`. The Jira estimate for US-001 was 1 bolt; the design shows it is larger, see the note at the end.

| Bolt | Goal | Covers | Done when |
| --- | --- | --- | --- |
| S1 | Claims and lines | AC1, drafts (US-002), X4 | Create, list, edit and delete lines on a draft. Other people's claims give 404 |
| S2 | Receipt upload path | AC2, AC4, AC5 | Presigned POST with type, size and checksum rules. 6th file refused. Status endpoint |
| S3 | Scan and store | AC6, ReceiptStored | EICAR file ends `REJECTED` and is deleted. Clean file moves to the receipts bucket. Magic-byte check. Scan timeout sweeper |
| S4 | Submit | AC7, AC7a, AC8, X1 to X3 | Calls `policy` evaluate (stub until policy P2 is ready). Reference, immutability, idempotency, `ClaimSubmitted` event |
| S5 | Duplicates and privacy | AC9, AC10 | `DUP` index and `duplicateOf`. Audit event on every action. Log scan has 0 PII |
| S6 | Retention and withdraw | US-006 base, US-004 base | Daily expiry job and `ReceiptsExpired`. Withdraw before any approval step |
| S7 | Harden | NFRs | Load test, IaC scan, alarms, runbook, DR check |

## Order and dependencies

S1, S2, S3 in order. S4 needs `policy` bolt P2 (evaluate), or a stub with the prototype's samples. S5 after S3. S6 and S7 last. The web screens for each bolt are built in the same bolt and reviewed by FED (Q47).

## Note on size

US-001 has 11 acceptance criteria, an upload and scan pipeline, and a submit transaction. The Jira estimate of 1 bolt (2 to 3 days) is too small. The plan has about 7 bolts for the unit. Update the DEV-2 estimate after review.

## Definition of done per bolt

Tests first and passing. Lint clean. OpenAPI and event schemas unchanged or versioned. No policy numbers in code. Audit event on every state change. Reviewed in one sitting.
