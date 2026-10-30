---
id: QLOG-001
title: Question log — Submit expenses with receipt attachments
activity: DIS-01
status: Answered — awaiting PRD sign-off
version: 0.2.0
last_updated: 2026-10-30
owner: Solution Owner
---

# Question log — Submit expenses with receipt attachments

Questions Claude raised for intent [INT-001](intent.md). Each has a **starter answer** so work can continue.
Nothing here is final until the Solution Owner confirms it.

## How to read this log

| Status | Meaning | Who closes it |
| --- | --- | --- |
| ASSUMPTION | Sensible default for product behaviour. Used in the story now | Solution Owner confirms or changes |
| OPEN QUESTION | Finance policy or compliance decision. Claude must not guess the number | Solution Owner / BA / Compliance answers |
| CONFIRMED | Agreed by the Solution Owner | — |

All items: **Owner** Solution Owner · **Due** before PRD sign-off (`aidlc-docs/approvals/prd-signoff.md`).

## Batch A — Scope and users

| # | Question | Starter answer | Status |
| --- | --- | --- | --- |
| Q1 | Who can submit claims? | Permanent employees who sign in with company SSO. Contractors are out of scope for v1 | ASSUMPTION |
| Q2 | Which channels? | Responsive web app, working in desktop and mobile browsers, including taking a photo with the phone camera. No native app in v1 | ASSUMPTION |
| Q3 | Does one claim hold one expense or many? | One claim holds 1 to many expense lines (e.g. a trip). Each line has its own receipts | ASSUMPTION |
| Q4 | Can an employee save a claim and finish later? | Yes, as a draft. Covered by a separate story (US-002), not US-001 | ASSUMPTION |
| Q5 | Can a claim be edited after submit? | No. The employee can withdraw it before approval, edit, and resubmit. Separate story (US-004) | ASSUMPTION |

## Batch B — Receipts

| # | Question | Starter answer | Status |
| --- | --- | --- | --- |
| Q6 | Which file types are allowed? | JPEG, PNG, HEIC and PDF | ASSUMPTION |
| Q7 | Size and count limits? | Up to 10 MB per file and up to 5 files per expense line | ASSUMPTION |
| Q8 | Is a receipt required on every line? Is there an amount below which no receipt is needed? | **Receipt required for lines of ₹1,000 or more.** Lines under ₹1,000 may be submitted without one. A line of ₹1,000 or more without a receipt needs a missing-receipt declaration (US-003). *Answered 2026-10-30 as "1000"; read as ₹1,000 in base currency* | CONFIRMED |
| Q9 | What checks run on an uploaded file? | File type and size check, plus malware scan before the file is stored. Reading the receipt (OCR) is out of scope here — it belongs to the `ocr` unit | ASSUMPTION |
| Q10 | What if the same receipt is attached twice? | Warn the employee if the same file (same content hash) is already on another of their claims. Blocking duplicates is a policy decision for DIS-02 (US-005) | ASSUMPTION |

## Batch C — Money, compliance and data

| # | Question | Starter answer | Status |
| --- | --- | --- | --- |
| Q11 | Which currency? | **Base currency is INR.** Employee enters amount and currency per line (INR by default). Conversion to INR is out of scope for v1 | CONFIRMED |
| Q12 | Which expense categories? | **Starter list for v1: Travel, Accommodation, Meals, Mileage, Other.** Limits per category come from the expense policy (DIS-02) | CONFIRMED |
| Q13 | How long are receipts kept? | **1 year**, then deleted. Period must be configurable. ⚠️ See risk R1 below | CONFIRMED (with risk) |
| Q14 | How is personal data in receipts protected? | Receipts can show names and part card numbers. Store encrypted; only the submitter, their approvers and finance can open them; receipt content never written to logs | ASSUMPTION |
| Q15 | Are policy limits checked at submit? | No. Submit checks only that the claim is complete. Policy checks are the `policy` unit's job (DIS-02 / DIS-03) | ASSUMPTION |

## Batch D — Follow-ups from the answers

| # | Question | Starter answer | Status |
| --- | --- | --- | --- |
| Q16 | The ₹1,000 receipt threshold is in INR, but there is no currency conversion in v1. How is it applied to a line in another currency? | Lines in any currency other than INR always need a receipt | ASSUMPTION |
| Q17 | Is a line of exactly ₹1,000 above or below the threshold? | ₹1,000 and above needs a receipt; ₹999.99 and below does not | ASSUMPTION |

## Risks raised

| # | Risk | Impact | Recommended action | Owner |
| --- | --- | --- | --- | --- |
| R1 | 1-year receipt retention is much shorter than usual for financial records. In India, company law and GST rules generally expect books and supporting documents to be kept for several years | Receipts may be deleted before an audit or tax assessment needs them | Confirm the period with compliance / the finance controller before go-live. Keep retention configurable so it can change without code | Solution Owner + Compliance |

## Summary

| Status | Count |
| --- | --- |
| ASSUMPTION | 13 (Q1–Q7, Q9, Q10, Q14–Q17) |
| OPEN QUESTION | 0 |
| CONFIRMED | 4 (Q8, Q11, Q12, Q13) |
| Risks | 1 (R1) |

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 0.1.0 | 2026-10-30 | Claude (proposed) | First 15 questions with starter answers |
| 0.2.0 | 2026-10-30 | Solution Owner (answers), Claude (recorded) | Q8, Q11, Q12, Q13 confirmed; added Q16, Q17 and risk R1 |
