---
id: STORIES-001
title: User stories — Submit expenses with receipt attachments
activity: DIS-01
status: Approved (Tom, Solution Owner) — in Jira
version: 0.3.0
last_updated: 2026-10-30
owner: Solution Owner
unit: submit
jira_epic: DEV-1 (New Feature used as epic stand-in)
jira_site: https://presidio-team-w7ye7n13.atlassian.net
---

# User stories — Submit expenses with receipt attachments

Source: [PRD-001](prd.md) · Assumptions: [question log](question-log.md)

## US-001 · Submit an expense claim with receipt attachments

> **As an** employee,
> **I want to** submit an expense claim with a receipt attached to each expense line,
> **so that** I can be reimbursed for business costs with the proof finance needs.

| Field | Value |
| --- | --- |
| Jira | [DEV-2](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-2) (epic [DEV-1](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-1)) |
| Unit | `submit` |
| Priority | Must have (Jira: High) |
| Size | 1 bolt (2–3 days) — estimate, to confirm in DIS-04 |
| Labels | `aidlc-discover`, `nfr-candidate` (PII in receipts, audit) |
| Depends on | Company SSO sign-in available |
| Confirmed answers | Q8 (₹1,000 receipt threshold), Q11 (INR), Q12 (starter categories), Q13 (1-year retention) |
| Assumptions used | Q1, Q2, Q3, Q6, Q7, Q9, Q10, Q14, Q15, Q16, Q17 |
| Risks | R1 — retention period to be confirmed by compliance |

### Acceptance criteria

**AC1 — Create a claim with lines**
Given I am signed in as an employee
When I start a new claim and add two expense lines with date, category (Travel, Accommodation, Meals, Mileage or Other), amount, currency (INR by default) and description
Then the claim shows both lines and their total per currency.

**AC2 — Attach a receipt**
Given I have an expense line
When I attach a JPEG, PNG, HEIC or PDF file of 10 MB or less
Then the file is checked, stored, and shown as a receipt on that line.

**AC3 — Take a photo on a phone**
Given I am using the app in a mobile browser
When I choose "Take photo" on an expense line
Then the camera opens and the photo is attached as that line's receipt.

**AC4 — Reject a wrong file type**
Given I have an expense line
When I attach a `.exe` or `.docx` file
Then the upload is refused with the message "Use JPEG, PNG, HEIC or PDF" and nothing is stored.

**AC5 — Reject a file that is too large or too many files**
Given I have an expense line
When I attach a file over 10 MB, or a 6th file to the same line
Then the upload is refused with a message that states the limit.

**AC6 — Block unsafe files**
Given I attach a file that fails the malware scan
When the scan completes
Then the file is not stored, I see "This file can't be used", and a security event is recorded.

**AC7 — Cannot submit without a required receipt**
Given my claim has a line of ₹1,000 or more, or a line in a currency other than INR, with no receipt
When I select Submit
Then submit is blocked and that line is highlighted with "Add a receipt".

**AC7a — Small INR lines need no receipt**
Given my claim has an INR line of ₹999.99 or less with no receipt, and every other line meets AC7
When I select Submit
Then submit is allowed and the line is marked "No receipt (under ₹1,000)".

**AC8 — Submit successfully**
Given every line is complete and every line that needs a receipt has at least one
When I select Submit
Then the claim gets a unique reference, its status becomes `Submitted`, I see a confirmation with the reference, and the claim can no longer be edited.

**AC9 — Duplicate receipt warning**
Given a receipt with the same file content is already on another of my claims
When I attach it again
Then I see a warning naming the other claim reference, and I can still continue.

**AC10 — Privacy and audit**
Given any create, attach, remove or submit action
When it completes
Then an audit event is written with who, what and when, and no receipt content or personal data appears in application logs.

### Jira fields (as created)

| Jira field | Value |
| --- | --- |
| Key | DEV-2 |
| Project | DEV — Development Requests Project (Jira Service Management) |
| Issue type | Task (the project has no Story type) |
| Summary | US-001 Submit an expense claim with receipt attachments |
| Labels | aidlc-discover, nfr-candidate, epic-exp-submit, unit-submit |
| Epic | DEV-1, linked with "relates to" (the project has no Epic type or parent hierarchy) |
| Description | User story text + AC1–AC10 (incl. AC7a) above |

## Backlog — follow-up stories (titles only, detailed later)

| ID | Jira | Story | Related question |
| --- | --- | --- | --- |
| US-002 | [DEV-3](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-3) | Save a claim as a draft and finish later | Q4 |
| US-003 | [DEV-4](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-4) | Submit a line of ₹1,000 or more without a receipt using a missing-receipt declaration | Q8 |
| US-004 | [DEV-5](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-5) | Withdraw a submitted claim before approval | Q5 |
| US-005 | [DEV-6](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-6) | Block (not just warn about) duplicate receipts, per policy | Q10 |
| US-006 | [DEV-7](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-7) | Delete receipts automatically when the retention period ends | Q13, R1 |

All backlog items are Jira Tasks labelled `backlog`, `epic-exp-submit`, `unit-submit`, linked to DEV-1.
Find them all: `project = DEV AND labels = epic-exp-submit`.

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 0.1.0 | 2026-10-30 | Claude (proposed) | US-001 with 10 acceptance criteria; backlog US-002 to US-005 |
| 0.2.0 | 2026-10-30 | Claude (from Solution Owner answers) | ₹1,000 receipt threshold (AC7, new AC7a), INR default, categories; backlog US-006 |
| 0.3.0 | 2026-10-30 | Claude | Created in Jira: epic stand-in DEV-1, US-001 = DEV-2, backlog DEV-3 to DEV-7; backlog table re-ordered |
