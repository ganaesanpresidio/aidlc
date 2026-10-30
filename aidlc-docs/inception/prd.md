---
id: PRD-001
title: PRD — Submit expenses with receipt attachments
activity: DIS-01
status: Draft — awaiting Solution Owner sign-off
version: 0.2.0
last_updated: 2026-10-30
owner: Solution Owner
unit: submit
---

# PRD — Submit expenses with receipt attachments

## 1. Summary

Employees create a claim, add one or more expense lines, attach a receipt to each line, and submit it for approval.
Source intent: [INT-001](intent.md). Every assumption below traces to the [question log](question-log.md).

## 2. Goals

| Goal | Measure | Target |
| --- | --- | --- |
| Fast submission | Time to submit a 3-line claim with receipts | ≤ 3 min (ASSUMPTION) |
| Complete evidence | Lines of ₹1,000 or more with a receipt or missing-receipt declaration | 100% (ASSUMPTION) |
| Fewer returns | Claims sent back for missing information | < 5% (ASSUMPTION) |

## 3. Users

Employees signed in with company SSO (Q1). Approvers and finance consume the result in later stories.

## 4. Functional requirements

| ID | Requirement | Source |
| --- | --- | --- |
| FR-1 | Employee can create a claim with 1 to many expense lines | Q3 |
| FR-2 | Each expense line has: date, category (Travel, Accommodation, Meals, Mileage, Other), amount, currency (default INR), description | Q11, Q12 |
| FR-3 | Employee can attach receipts to a line: JPEG, PNG, HEIC, PDF; ≤ 10 MB each; ≤ 5 per line | Q6, Q7 |
| FR-4 | On a phone, employee can take a photo with the camera as the receipt | Q2 |
| FR-5 | Each file is checked for type, size and malware before it is stored | Q9 |
| FR-6 | Submit is allowed only when every line is complete, and every line of ₹1,000 or more — or in a currency other than INR — has a receipt (or, later, a missing-receipt declaration). INR lines under ₹1,000 need no receipt. The threshold is configuration, not code | Q8, Q15, Q16, Q17 |
| FR-7 | On submit, the claim gets a unique reference, status `Submitted`, and the employee sees a confirmation | — |
| FR-8 | Employee is warned if a receipt file is already attached to another of their claims | Q10 |

## 5. Non-functional requirements (candidates for DIS-03)

| ID | Requirement | Source |
| --- | --- | --- |
| NFR-1 | Receipts encrypted at rest and in transit; access limited to submitter, approvers, finance | Q14 |
| NFR-2 | Receipt content and personal data never written to logs | Q14 |
| NFR-3 | Every create, attach, remove and submit action writes an audit event | Playbook audit NFR |
| NFR-4 | Receipts kept for 1 year, then deleted. Period is configurable (see risk R1) | Q13 |
| NFR-5 | Upload of a 10 MB file completes in ≤ 10 s on a normal connection | ASSUMPTION |

## 6. Out of scope

Drafts (US-002), missing-receipt declaration (US-003), withdraw (US-004), duplicate blocking (US-005), OCR, policy limit checks, approval routing, currency conversion, reimbursement, native mobile app.

## 7. Open questions and risks

No open questions remain (all answered 2026-10-30, see the [question log](question-log.md)).

| # | Risk | Action before go-live |
| --- | --- | --- |
| R1 | 1-year receipt retention may be shorter than legal / audit requirements | Compliance confirms the period; it stays configurable |

## 8. Sign-off

HUMAN GATE — recorded only by the Solution Owner in [`../approvals/prd-signoff.md`](../approvals/prd-signoff.md).
