---
id: DM-001
title: Domain model — expense claims, policy and approval
activity: DIS-02
status: Draft — awaiting Solution Owner and Architect sign-off
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
sources: [prd.md, mock-expense-policy.md, policy-rules.example.yaml]
---

# Domain model

Terms follow the [glossary](../glossary/policy-glossary.md). Rules values live in [policy-rules.example.yaml](policy-rules.example.yaml), never in code ([ADR-001](../decisions/adr-001-rules-as-versioned-yaml.md)).

## Entities

| Entity | Key fields | Notes |
| --- | --- | --- |
| Employee | id, grade (G1 to G3), line manager, department, cost centre | Grade picks the category limits |
| Claim | reference, submitter, status, total (INR), submitted at, rules version | Holds 1 or more expense lines |
| Expense line | date, category, amount, currency, description, exception reason (optional) | Checked against the category limit |
| Receipt | file, type, size, line | Required at or above the receipt threshold |
| Policy rules | version, effective from, limits, tiers, SoD flags | Versioned config; a claim records the version used |
| Approval tier | id, max total, ordered roles (1 or 2) | From the approval matrix |
| Approval step | claim, role, approver, decision, decided at, comment | One per role in the chain |
| Approver | employee, role (Line Manager, Department Head, Finance Controller, CFO) | Role is held per employee |
| Reimbursement | claim, amount, payer, paid at | Created only after final approval |

## Relationships

```text
Employee 1 --- * Claim 1 --- * Expense line 1 --- * Receipt
Claim * --- 1 Policy rules (version used at submit)
Claim 1 --- 1..2 Approval step * --- 1 Approver (Employee)
Claim 1 --- 0..1 Reimbursement
Policy rules 1 --- * Approval tier
```

## Claim state machine

| From | Event | To | Guard |
| --- | --- | --- | --- |
| Draft | submit | Submitted | Lines complete, receipts present, no line over its limit without a reason, within 30 days |
| Submitted | step approved (not last) | Submitted | SOD-1 to SOD-4 hold |
| Submitted | last step approved | Approved | All steps decided Approve |
| Submitted | any step rejected | Rejected | Comment required |
| Submitted | withdraw | Withdrawn | No step decided yet |
| Submitted | no action in 5 working days | Submitted | Step escalates one role up |
| Approved | pay | Paid | Payer is not an approver of this claim (SOD-3) |

Rejected, Withdrawn and Paid are final.

## Routing rule (summary)

1. Sum the lines in INR. Pick the first tier whose max total is at or above it.
2. If any line has an exception reason, append the Finance Controller.
3. Check SOD-1 to SOD-4 for each step; on a clash the claim escalates or is blocked.

Executable check: `uv run aidlc-e2e rules` runs 8 synthetic claims through this rule.

## Open points

None blocking. Values are MOCK; the real policy replaces them without a code change.
