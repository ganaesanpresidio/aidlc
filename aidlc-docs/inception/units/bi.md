---
id: UNIT-bi
title: Unit — bi
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
build_order: 6
---

# Unit `bi`

| Field | Value |
| --- | --- |
| Scope | Spend, cycle time and policy-breach reporting from events. Read only |
| Owner | Architect (team to be named) |
| Stories | None yet. See [story-map.md](story-map.md) |
| Depends on | Events from all other units |
| Build order | 6 |

## Data owned

Its own analytics store, filled only from events. It never reads another unit's tables.

## APIs (v1)

| Method and path | Purpose |
| --- | --- |
| `GET /v1/reports/spend`, `GET /v1/reports/cycle-time`, `GET /v1/reports/breaches` | Finance reports |

## Events

Consumes all events. Publishes none.

## PII and controls

Pseudonymise employee ids. No receipt content. Access for finance and audit roles only.

## AWS services (candidates)

S3, Glue, Athena, QuickSight.
