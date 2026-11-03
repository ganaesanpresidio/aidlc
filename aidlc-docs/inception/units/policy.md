---
id: UNIT-policy
title: Unit — policy
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
build_order: 1
---

# Unit `policy`

| Field | Value |
| --- | --- |
| Scope | Hold versioned policy rules, validate them, evaluate limits, compute the approval chain and check SoD |
| Owner | Architect (team to be named) |
| Stories | None yet. Needs new stories (rules admin, routing). See [story-map.md](story-map.md) |
| Depends on | Nothing |
| Build order | 1 |

## Data owned

Policy rules versions, tiers, grades, category limits. Source format: [policy-rules.schema.json](../policy-rules.schema.json). Every version has an effective date.

## APIs (v1)

| Method and path | Purpose |
| --- | --- |
| `GET /v1/policy/rules?effectiveOn=` | Read the rules in force on a date |
| `POST /v1/policy/evaluate` | Check lines against limits and receipt threshold |
| `POST /v1/policy/route` | Return the approval chain for a claim and the SoD result |
| `PUT /v1/policy/rules` | Publish a new version (finance admin only, schema-validated) |

## Events

Publishes `PolicyRulesPublished`. Consumes nothing.

## PII and controls

No PII. Rule changes are audited with the actor and the version.

## AWS services (candidates)

Lambda, S3 or DynamoDB for versioned config, API Gateway.
