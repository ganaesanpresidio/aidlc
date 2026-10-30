---
id: INT-001
title: Intent — Submit expenses with receipt attachments
activity: DIS-01
status: Draft
version: 0.2.0
last_updated: 2026-10-30
owner: Solution Owner
---

# Intent — Submit expenses with receipt attachments

## Intent statement

> Employees can submit expenses with receipt attachments.

As stated by the Solution Owner on 2026-10-30.

## Problem

Employees need one place to claim back business costs and prove each cost with a receipt.
Without it, claims arrive by email or paper, receipts get lost, and finance cannot check or audit them.

## Who it is for

| Role | Need |
| --- | --- |
| Employee (submitter) | Claim costs quickly, from a laptop or phone, with the receipt attached |
| Approver | See the receipt next to each expense line (later story, `approve` unit) |
| Finance | Have a complete, auditable claim with evidence (later story) |

## Success measures (proposed — Solution Owner to confirm)

| Measure | Target | Status |
| --- | --- | --- |
| Time for an employee to submit a 3-line claim with receipts | ≤ 3 minutes | ASSUMPTION |
| Submitted lines of ₹1,000 or more that have a receipt (or a missing-receipt declaration) | 100% | ASSUMPTION |
| Claims returned to the employee for missing information | < 5% | ASSUMPTION |

## Scope of this intent

- **In:** create a claim, add expense lines, attach receipts, submit.
- **Out (later intents or units):** approval routing, OCR, policy limit checks, reimbursement, reporting.

## Links

- Questions and assumptions: [question-log.md](question-log.md)
- PRD: [prd.md](prd.md)
- Stories: [user-stories.md](user-stories.md)
- Playbook activity: [DIS-01](../../docs/1-discover/dis-01-intent-to-stories.md)
