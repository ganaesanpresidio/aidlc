---
id: TRACE-001
title: Requirement traceability — Submit expenses with receipt attachments
status: Living document
version: 0.1.0
last_updated: 2026-11-03
owner: Solution Owner
---

# Requirement traceability

One page linking the requirement to its user stories, Jira issues, Confluence pages and every artifact created so far. Update it whenever an activity adds material.

**Requirement:** Employees can submit expenses with receipt attachments ([intent](inception/intent.md)).
**Status:** DIS-01 approved. DIS-02 approved (policy values are MOCK). DIS-03 drafted, awaiting Architect approval.

## 1. User stories and Jira

Jira site: <https://presidio-team-w7ye7n13.atlassian.net>. Project `DEV`. Label `epic-exp-submit`.

| Story | Title | Jira | Detail in repo |
| --- | --- | --- | --- |
| Epic | Submit expenses with receipt attachments | [DEV-1](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-1) | [intent.md](inception/intent.md) |
| US-001 | Submit an expense claim with receipt attachments (11 acceptance criteria) | [DEV-2](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-2) | [user-stories.md](inception/user-stories.md) |
| US-002 | Save a claim as a draft | [DEV-3](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-3) | [user-stories.md](inception/user-stories.md) |
| US-003 | Missing-receipt declaration for lines of ₹1,000 or more | [DEV-4](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-4) | [user-stories.md](inception/user-stories.md) |
| US-004 | Withdraw a submitted claim | [DEV-5](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-5) | [user-stories.md](inception/user-stories.md) |
| US-005 | Block duplicate receipts | [DEV-6](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-6) | [user-stories.md](inception/user-stories.md) |
| US-006 | Auto-delete receipts after the retention period | [DEV-7](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-7) | [user-stories.md](inception/user-stories.md) |

Search all: `project = DEV AND labels = epic-exp-submit`

## 2. Confluence

Space `AIDLC`: <https://presidio-team-w7ye7n13.atlassian.net/wiki/spaces/AIDLC>

| Page | Link | Source in repo |
| --- | --- | --- |
| Mock expense policy (MOCK DATA) | [open](https://presidio-team-w7ye7n13.atlassian.net/wiki/spaces/AIDLC/pages/1474561/AIDLC+Mock+expense+policy+MOCK+DATA) | [mock-expense-policy.md](inception/mock-expense-policy.md) |
| Approval matrix (MOCK DATA) | [open](https://presidio-team-w7ye7n13.atlassian.net/wiki/spaces/AIDLC/pages/1507329/AIDLC+Approval+matrix+MOCK+DATA) | [approval-matrix.md](inception/approval-matrix.md) |

Domain model and ADRs are not published to Confluence yet (DIS-02 step 9).

## 3. Material created so far

### DIS-01 · Intent to stories

| Artifact | Path |
| --- | --- |
| Intent | [inception/intent.md](inception/intent.md) |
| Question log (Q1 to Q17, risk R1) | [inception/question-log.md](inception/question-log.md) |
| PRD | [inception/prd.md](inception/prd.md) |
| User stories | [inception/user-stories.md](inception/user-stories.md) |
| Glossary | [glossary/policy-glossary.md](glossary/policy-glossary.md) |
| Sign-off (APPROVED) | [approvals/prd-signoff.md](approvals/prd-signoff.md) |

### DIS-02 · Policy and approval rules as a domain model

| Artifact | Path |
| --- | --- |
| Mock expense policy | [inception/mock-expense-policy.md](inception/mock-expense-policy.md) |
| Approval matrix | [inception/approval-matrix.md](inception/approval-matrix.md) |
| Domain model and Claim state machine | [inception/domain-model.md](inception/domain-model.md) |
| Rules schema | [inception/policy-rules.schema.json](inception/policy-rules.schema.json) |
| Rules config (example, MOCK values) | [inception/policy-rules.example.yaml](inception/policy-rules.example.yaml) |
| ADR-001 Rules as versioned YAML | [decisions/adr-001-rules-as-versioned-yaml.md](decisions/adr-001-rules-as-versioned-yaml.md) |
| ADR-002 SoD in the model | [decisions/adr-002-sod-in-the-model.md](decisions/adr-002-sod-in-the-model.md) |
| ADR-003 Approval by claim total | [decisions/adr-003-approval-by-claim-total.md](decisions/adr-003-approval-by-claim-total.md) |
| ADR-004 Receipt threshold in rules | [decisions/adr-004-receipt-threshold-in-rules.md](decisions/adr-004-receipt-threshold-in-rules.md) |
| Sign-off (APPROVED) | [approvals/spec-signoff.md](approvals/spec-signoff.md) |

### DIS-03 · Units of work and NFRs

| Artifact | Path |
| --- | --- |
| NFR baseline (ASSUMPTION) | [inception/nfr-baseline.md](inception/nfr-baseline.md) |
| Unit catalogue and build order | [inception/units/README.md](inception/units/README.md) |
| Units: policy, submit, approve, payout, ocr, bi | [inception/units/](inception/units/) |
| Story to unit map | [inception/units/story-map.md](inception/units/story-map.md) |
| Interface contracts (draft) | [inception/units/interfaces.md](inception/units/interfaces.md) |
| NFR matrix | [inception/nfr-matrix.md](inception/nfr-matrix.md) |
| ADR-005 Unit boundaries | [decisions/adr-005-unit-boundaries.md](decisions/adr-005-unit-boundaries.md) |
| ADR-006 Versioned events | [decisions/adr-006-versioned-events.md](decisions/adr-006-versioned-events.md) |
| ADR-007 Async OCR | [decisions/adr-007-async-ocr.md](decisions/adr-007-async-ocr.md) |
| Approval record (PENDING) | [approvals/units-nfr.md](approvals/units-nfr.md) |

### Tooling

| Tool | Path | Command |
| --- | --- | --- |
| Settings loader | [../tools/aidlc_e2e/config.py](../tools/aidlc_e2e/config.py) | `uv run aidlc-e2e` |
| Jira and Confluence check | [../tools/aidlc_e2e/connectivity.py](../tools/aidlc_e2e/connectivity.py) | `AIDLC_ENV_FILE=env.dev uv run aidlc-e2e check` |
| Rules validation and sample claims | [../tools/aidlc_e2e/rules_check.py](../tools/aidlc_e2e/rules_check.py) | `uv run aidlc-e2e rules` |
| Confluence publisher | [../tools/aidlc_e2e/confluence.py](../tools/aidlc_e2e/confluence.py) | `AIDLC_ENV_FILE=env.dev uv run aidlc-e2e publish` |

## 4. Requirement to artifact map

| Requirement | Story | Rules and model |
| --- | --- | --- |
| FR-1 to FR-8 (submit with receipts) | US-001 / DEV-2 | [domain-model.md](inception/domain-model.md) |
| FR-6 receipt threshold ₹1,000 | US-001, US-003 | ADR-004, `receipt_threshold` in the rules config |
| NFR-4 retention 1 year | US-006 / DEV-7 | Risk R1 in the question log |
| Approval tiers and SoD (next feature) | not yet written | [approval-matrix.md](inception/approval-matrix.md), ADR-002, ADR-003, unit [approve](inception/units/approve.md) |

## 5. Open items

All are recorded as assumptions, questions and risks in the [question log](inception/question-log.md): Q18 to Q36 and risks R2, R3. Summary:

- Replace MOCK policy values with the real policy before go-live.
- Compliance to confirm 1-year retention (risk R1).
- Stories for the `policy`, `approve`, `payout`, `ocr` and `bi` units are not written yet (next DIS-01 cycle, see [story-map.md](inception/units/story-map.md)).
