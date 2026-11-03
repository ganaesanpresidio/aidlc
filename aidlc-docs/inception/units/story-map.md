---
id: STORYMAP-001
title: Story to unit map
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
---

# Story to unit map

| Story | Jira | Primary unit | Also touches |
| --- | --- | --- | --- |
| US-001 Submit a claim with receipts | [DEV-2](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-2) | `submit` | `policy` (receipt threshold, limits) |
| US-002 Save as draft | [DEV-3](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-3) | `submit` | none |
| US-003 Missing-receipt declaration | [DEV-4](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-4) | `submit` | `policy` (threshold) |
| US-004 Withdraw a claim | [DEV-5](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-5) | `submit` | `approve` (stops open steps) |
| US-005 Block duplicate receipts | [DEV-6](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-6) | `submit` | none |
| US-006 Auto-delete after retention | [DEV-7](https://presidio-team-w7ye7n13.atlassian.net/browse/DEV-7) | `submit` | none |

**No orphan stories:** all six map to exactly one primary unit.

## Gaps: units with no stories

These are flagged for the next DIS-01 cycle. Suggested stories:

| Unit | Suggested stories |
| --- | --- |
| `policy` | Finance admin publishes a new rules version. Limit check at submit. Compute the approval chain |
| `approve` | Approver sees the claim and receipt, approves or rejects. Escalation after 5 working days. SoD checks |
| `payout` | Finance marks a claim paid. Employee sees status |
| `ocr` | Receipt fields suggested from the image |
| `bi` | Finance sees spend and cycle time |

The `submit` unit holds 6 stories of about 1 bolt each. It is large for one unit, so DIS-04 should confirm it can be built in bolts of 2 to 3 days per story.
