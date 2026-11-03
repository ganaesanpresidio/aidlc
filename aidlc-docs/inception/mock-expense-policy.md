---
id: POL-MOCK-001
title: Mock expense policy (synthetic, for the playbook walkthrough)
activity: DIS-02
status: MOCK — not a real company policy
version: 0.1.0
last_updated: 2026-11-03
owner: Solution Owner
---

# Mock expense policy

> **MOCK DATA.** Every number below is invented so DIS-02 can be exercised. Replace it with the real policy before go-live. Rows cite this page as `POL-MOCK-001 §n`.

## 1. Scope and currency

Applies to all employees. Claims are reimbursed in INR (base currency). Lines in other currencies need a receipt; conversion is out of scope for v1.

## 2. Grades

| Grade | Who |
| --- | --- |
| G1 Staff | Individual contributors |
| G2 Manager | People managers |
| G3 Director | Directors and above |

## 3. Category limits per expense line (INR)

| Category | Unit | G1 Staff | G2 Manager | G3 Director |
| --- | --- | --- | --- | --- |
| Travel | per line | 25,000 | 50,000 | 100,000 |
| Accommodation | per night | 6,000 | 10,000 | 15,000 |
| Meals | per day | 1,500 | 2,500 | 4,000 |
| Mileage | per km | 12 | 12 | 12 |
| Other | per line | 5,000 | 10,000 | 20,000 |

A line above its limit cannot be submitted. It needs an exception approved by the Finance Controller (§6).

## 4. Receipts

A receipt is required for lines of ₹1,000 or more, and for all non-INR lines (see the [PRD](prd.md)).

## 5. Approval tiers (by claim total in INR)

| Tier | Claim total | Approvers needed |
| --- | --- | --- |
| T1 | up to 10,000 | Line Manager |
| T2 | 10,001 to 50,000 | Line Manager, then Department Head |
| T3 | 50,001 to 200,000 | Department Head, then Finance Controller |
| T4 | above 200,000 | Finance Controller, then CFO |

## 6. Segregation of duties

1. No one approves their own claim. If the routed approver is the submitter, the claim goes to the next role up.
2. When two approvers are needed, they must be two different people.
3. Finance staff who pay a claim cannot also approve it.
4. An approver must hold a grade equal to or above the submitter's.

## 7. Timing

Claims must be submitted within 30 days of the expense date. Approvers act within 5 working days, then the claim escalates one role up.

## 8. Exceptions

A line above its category limit may be submitted with a written reason. It adds the Finance Controller as an extra approver.
