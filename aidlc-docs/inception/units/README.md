---
id: UNITS-001
title: Unit catalogue
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
---

# Unit catalogue

Six independent units. Each owns its data, and units talk only through versioned APIs and events ([ADR-005](../../decisions/adr-005-unit-boundaries.md), [ADR-006](../../decisions/adr-006-versioned-events.md)).

| Order | Unit | Scope in one line | Stories | Depends on |
| --- | --- | --- | --- | --- |
| 1 | [policy](policy.md) | Versioned rules, limits, approval routing, SoD | none yet | none |
| 2 | [submit](submit.md) | Claims, lines, receipts, submit, withdraw | US-001 to US-006 | policy |
| 3 | [approve](approve.md) | Approver inbox, decisions, escalation | none yet | policy, submit |
| 4 | [payout](payout.md) | Reimbursement and paid status | none yet | approve |
| 5 | [ocr](ocr.md) | Receipt reading, async, optional | none yet | submit |
| 6 | [bi](bi.md) | Reports from events | none yet | all (events) |

**Build order by risk:** `policy` first (no dependencies, carries the most business risk), then `submit` (the approved stories), then `approve` and `payout`. `ocr` and `bi` are last because nothing waits on them.

```text
policy ──> submit ──> approve ──> payout
              │                     │
              └──> ocr              │
all units ──events──> bi <──────────┘
```

## Related files

- [story-map.md](story-map.md) · [interfaces.md](interfaces.md) · [NFR matrix](../nfr-matrix.md) · [NFR baseline](../nfr-baseline.md)
- Approval: [units-nfr.md](../../approvals/units-nfr.md)
