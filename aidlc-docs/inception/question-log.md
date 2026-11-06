---
id: QLOG-001
title: Question log — Submit expenses with receipt attachments
activity: DIS-01
status: DIS-01 approved. DIS-02 and DIS-03 assumptions open
version: 0.6.0
last_updated: 2026-11-04
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

## Batch E — DIS-02 (policy and approval rules)

All policy numbers come from the invented [mock policy](mock-expense-policy.md). Due before go-live, owner Solution Owner.

| # | Question | Starter answer | Status |
| --- | --- | --- | --- |
| Q18 | What are the real limits, tiers and thresholds? | The values in the mock policy (POL-MOCK-001). They are invented and must be replaced by the real policy. See risk R2 | ASSUMPTION |
| Q19 | Which grades exist? | Three: G1 Staff, G2 Manager, G3 Director | ASSUMPTION |
| Q20 | What decides the approval tier? | The claim total in INR. Non-INR conversion is out of scope for v1 ([ADR-003](../decisions/adr-003-approval-by-claim-total.md)) | ASSUMPTION |
| Q21 | What if an approver does not act? | After 5 working days the claim escalates one role up | ASSUMPTION |
| Q22 | How long after the expense can a claim be submitted? | 30 days | ASSUMPTION |
| Q23 | Can a line go over its category limit? | Yes, with a written reason. It adds the Finance Controller as an approver | ASSUMPTION |

## Batch F — DIS-03 (units and NFRs) and DIS-04 (designs)

Owner Architect, with Compliance for Q24 and Q25. Due before the units and NFRs are approved (`aidlc-docs/approvals/units-nfr.md`). Values are in the [NFR baseline](nfr-baseline.md) and [NFR matrix](nfr-matrix.md).

| # | Question | Starter answer | Status |
| --- | --- | --- | --- |
| Q24 | Where must data live? | One India region, `ap-south-1` (Mumbai). No cross-border copy | ASSUMPTION |
| Q25 | How long are audit events kept? | 7 years, immutable | ASSUMPTION |
| Q26 | Availability and recovery targets? | 99.9% monthly. RPO 1 hour, RTO 4 hours | ASSUMPTION |
| Q27 | What load must it carry? | 10,000 employees, 5,000 claims a day, 10x burst | ASSUMPTION |
| Q28 | Latency targets? | p95 under 300 ms for reads and under 500 ms for writes. 10 MB upload in 10 s or less | ASSUMPTION |
| Q29 | How many receipts per claim, for sizing? | About 3 | ASSUMPTION |
| Q30 | How are HEIC receipts read by OCR? | Converted to JPEG first, because Amazon Textract reads JPEG, PNG and PDF. Verify in the LLD | ASSUMPTION |
| Q31 | Is the OCR request limit enough? | Asynchronous calls allow 5 a second in Mumbai. A quota increase may be needed. See risk R3 | ASSUMPTION |
| Q32 | Is `submit` one unit? | Yes, with all six stories. DIS-04 checks it fits in bolts of 2 to 3 days | ASSUMPTION |
| Q33 | Which teams own the units? | Not named yet. Owner is the Architect for now | ASSUMPTION |
| Q34 | Are employee bank details stored? | No. Payment goes through the bank's finance system by reference | ASSUMPTION |
| Q35 | What is the monthly cloud cost target per 1,000 claims? | No number proposed. Set it from the first LLD estimate | OPEN QUESTION |
| Q36 | Which stories come next? | Stories for `policy`, `approve`, `payout`, `ocr` and `bi` are written in the next DIS-01 cycle ([story-map.md](units/story-map.md)) | ASSUMPTION |
| Q37 | Which sign-in does the company use? | An OIDC single sign-on provider that sends grade and role as group claims | ASSUMPTION |
| Q38 | How many AWS accounts? | Three: dev, test and prod | ASSUMPTION |
| Q39 | Who resolves the holders of each approval role (line manager, department head, finance controller, CFO)? | The `approve` unit, from the company directory, so `policy` holds no HR data | ASSUMPTION |
| Q40 | How are non-INR lines turned into an INR total for the approval tier? | The employee enters an INR equivalent per non-INR line. Finance verifies it at payout. No automatic conversion in v1 | ASSUMPTION |
| Q41 | Does submit check category limits? Q15 said no, the approved mock policy says an over-limit line needs a reason | Q15 is superseded: submit enforces limits through `policy` evaluate | ASSUMPTION |
| Q42 | Where is the retention period configured? | An optional `retention_days` field in the policy rules, so it changes without code | ASSUMPTION |
| Q43 | How do approvers and finance open receipts? | `approve` asks `submit` for a 60 second signed link over IAM, after checking the assignment | ASSUMPTION |
| Q44 | How are events published reliably? | Write to the table first, then a DynamoDB stream and EventBridge Pipe publish the event | ASSUMPTION |
| Q45 | Who can read the policy rules? | Every signed-in user, because limits are not secret | ASSUMPTION |
| Q46 | Can rules be back-dated? | No. Versions are immutable and move forward only | ASSUMPTION |
| Q47 | Who builds the web app? | One web app. Each unit's bolts add its screens, reviewed by the front-end developer | ASSUMPTION |
| Q48 | Which calendar does "today" follow? | The company day in India (`AIDLC_TIMEZONE`, default Asia/Kolkata), for rule dates, the 30-day window and claim references | ASSUMPTION |
| Q49 | Are there safety limits on claim data? | Yes, as guards: at most 50 lines per claim, amounts up to 99,999,999.99 with 2 decimals, any number above 10^15 refused | ASSUMPTION |

## Risks raised

| # | Risk | Impact | Recommended action | Owner |
| --- | --- | --- | --- | --- |
| R1 | 1-year receipt retention is much shorter than usual for financial records. In India, company law and GST rules generally expect books and supporting documents to be kept for several years | Receipts may be deleted before an audit or tax assessment needs them | Confirm the period with compliance / the finance controller before go-live. Keep retention configurable so it can change without code | Solution Owner + Compliance |
| R2 | The approval gates accept the mock policy values, because the gates check only that the sign-off says APPROVED | Mock limits and tiers could reach build and go-live | Replace Q18 with the real policy and re-sign DIS-02 before go-live. Mock pages in Confluence are labelled MOCK DATA | Solution Owner |
| R3 | Receipt reading could hit the Textract request limit at peak (about 2 a second against 1 a second for synchronous calls) | Slow or failed suggestions. Submit is not affected ([ADR-007](../decisions/adr-007-async-ocr.md)) | Use asynchronous calls and a queue. Request a quota increase if needed | Architect |

## Summary

| Status | Count |
| --- | --- |
| ASSUMPTION | 44 (Q1–Q7, Q9, Q10, Q14–Q34, Q36–Q49) |
| OPEN QUESTION | 1 (Q35) |
| CONFIRMED | 4 (Q8, Q11, Q12, Q13) |
| Risks | 3 (R1 to R3) |

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 0.1.0 | 2026-10-30 | Claude (proposed) | First 15 questions with starter answers |
| 0.2.0 | 2026-10-30 | Solution Owner (answers), Claude (recorded) | Q8, Q11, Q12, Q13 confirmed; added Q16, Q17 and risk R1 |
| 0.3.0 | 2026-11-03 | Claude (proposed) | Added Batch E (Q18 to Q23, DIS-02) and Batch F (Q24 to Q36, DIS-03), risks R2 and R3 |
| 0.4.0 | 2026-11-03 | Claude (proposed) | Added Q37 (SSO) and Q38 (AWS accounts) from the HLD |
| 0.5.0 | 2026-11-04 | Claude (proposed) | Added Q39 to Q47 from the policy and submit LLDs |
| 0.6.0 | 2026-11-04 | Claude (proposed) | Added Q48 (business calendar) and Q49 (data guards) from the build |
