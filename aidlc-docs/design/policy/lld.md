---
id: LLD-policy
title: LLD — policy unit
activity: DIS-04
unit: policy
status: Draft — awaiting design review
version: 0.1.0
last_updated: 2026-11-04
owner: Architect + Engineer
---

# LLD: `policy` unit

Spec: [spec.md](spec.md). HLD: [hld.md](../hld.md). API: [api/openapi.yaml](api/openapi.yaml). Event: [api/events/PolicyRulesPublished.v1.schema.json](api/events/PolicyRulesPublished.v1.schema.json).

## 1. Context

Stateless Lambda functions behind two entry points. Public path (API Gateway, JWT): read rules, publish rules. Internal path (IAM-signed calls from `submit` and `approve`): evaluate, route. This refines the HLD, where all calls went through the gateway. Internal calls skip the gateway to save latency and keep the rules logic off the public surface.

| Caller | Call | Auth |
| --- | --- | --- |
| Any signed-in user | `GET /v1/policy/rules` | JWT |
| Finance admin | `PUT /v1/policy/rules` | JWT with group `finance-admin` |
| `submit` | `POST /v1/policy/evaluate` | IAM (SigV4), internal only |
| `approve` | `POST /v1/policy/route` | IAM (SigV4), internal only |

## 2. APIs

Contract in [api/openapi.yaml](api/openapi.yaml). Summary:

| Operation | Success | Errors |
| --- | --- | --- |
| `GET /v1/policy/rules?effectiveOn=` | 200 rules document | 404 `NO_RULES_IN_FORCE`, 400 bad date |
| `GET /v1/policy/rules/{version}` | 200 | 404 |
| `PUT /v1/policy/rules` | 201 with new version | 403, 409 `EFFECTIVE_DATE_NOT_AFTER_LATEST`, 422 schema errors |
| `POST /v1/policy/evaluate` | 200 `{ok, violations[], requiresException}` | 400, 404 no rules |
| `POST /v1/policy/route` | 200 `{tier, chain[]}` or `{blocked}` | 400, 404 |

A failed rule check is a normal 200 answer with `ok: false`, not an HTTP error. HTTP errors mean the request itself was wrong.

## 3. Events

| Event | When | Schema |
| --- | --- | --- |
| `PolicyRulesPublished` v1 | After a version is stored | [schema](api/events/PolicyRulesPublished.v1.schema.json) |

The payload holds `rulesVersion` and `effectiveFrom` only. Consumers fetch the rules through the API.

## 4. Data model

One DynamoDB table `policy-rules`, KMS customer-managed key, point-in-time recovery on.

| Item | PK | SK | Attributes |
| --- | --- | --- | --- |
| Rules document | `RULES` | `V#000001` | version, effectiveFrom, rules (the YAML as JSON), checksum, publishedBy, publishedAt |
| Effective-date pointer | `RULES` | `E#2026-11-03#000001` | version |

Access patterns:

| Question | Query |
| --- | --- |
| Rules in force on date D | Query `PK=RULES`, `SK <= E#D#~`, reverse order, limit 1, then get `V#n` |
| Rules by version | Get `RULES`, `V#n` |
| Latest version number | Query `PK=RULES`, `SK begins_with V#`, reverse, limit 1 |

Rules are immutable: writes use a condition that the item does not exist. The Lambda caches the rules document in memory for 60 seconds (keyed by version), because published versions never change.

Retention: kept for 7 years with the audit baseline (B3). No deletion path.

## 5. Sequences

### Evaluate (called by `submit`)

1. `submit` calls `POST /v1/policy/evaluate` with lines, grade and submission date.
2. Policy loads the rules in force for the submission date (cache, else one DynamoDB read).
3. For each line: check category exists, limit for the grade (using the unit per category), receipt rule, window.
4. Return `ok` plus violations. No state is written.

### Route (called by `approve`)

1. `approve` receives `ClaimSubmitted` and calls `POST /v1/policy/route` with total, submitter, grade, exception flag and the role holders it resolved from the directory.
2. Policy picks the first tier whose cap is at or above the total, appends the exception approver if flagged.
3. For each step it checks SOD-1 to SOD-4. The first failure returns `blocked` with the code.
4. Otherwise it returns the tier and the ordered chain.

### Publish

1. A finance admin calls `PUT /v1/policy/rules` with the rules document and an `Idempotency-Key`.
2. Policy validates against [policy-rules.schema.json](../../inception/policy-rules.schema.json) and the extra checks (tiers rise, last tier open, every category has every grade).
3. It checks `effectiveFrom` is on or after today and after the latest version's date.
4. It writes both items in one transaction, then puts `PolicyRulesPublished` on the bus and an audit event.
5. A repeat call with the same key returns the stored result.

## 6. Errors and retries

| Case | Behaviour |
| --- | --- |
| DynamoDB throttled or timeout | Retry twice with jitter inside the Lambda, then 503 with `Retry-After` |
| Event publish fails after the write | The write stands. A retry job on the outbox flag re-emits. See open question Q44 |
| Rules missing for a date | 404 `NO_RULES_IN_FORCE`. Callers must not guess a default |
| Corrupt cached document | Checksum mismatch discards the cache entry and re-reads |
| Caller retries | Evaluate and route are pure, so repeats are safe. Publish uses the idempotency key |

## 7. Security and PII

- No PII. Requests carry amounts, categories, grades and ids.
- Logs hold request id, rules version, violation codes. Never line descriptions or names.
- IAM role for `policy` can read and write only its table and put events on the bus.
- Publish needs the `finance-admin` group. Every publish is audited with the actor.
- KMS CMK on the table, TLS 1.2 or higher, region guard in `ap-south-1`.

## 8. NFR mapping

| NFR | Design element | Verified by |
| --- | --- | --- |
| Audit 100% | Publish writes audit event and `PolicyRulesPublished`. Reads are not state changes | Integration test and log query |
| PII in logs: 0 | Logger takes allow-listed fields only | Log scan in BLD-02 |
| SoD | `route` checks SOD-1 to SOD-4 for every step | Unit tests with the 8 sample claims |
| Latency reads p95 under 300 ms | 60 s cache, single keyed read on a miss | Load test |
| Availability 99.9% | Stateless Lambda, DynamoDB multi-AZ | CloudWatch SLO |
| RPO 1 h / RTO 4 h | Point-in-time recovery, IaC redeploy | DR test |
| Encryption | KMS CMK, TLS | IaC scan |
| Residency | One region, SCP guard | IaC scan |
| Capacity 5,000 claims a day, 10x | Two calls per claim, trivial load. Reserved concurrency set | Load test |
| Retention | 7 years for rules versions | Config check |

## 9. Test approach

| Level | What |
| --- | --- |
| Unit | Tier boundaries (10,000 vs 10,001, 50,000 vs 50,001, 200,000 vs 200,001). Every violation code. SOD-1 to SOD-4. Unknown category and grade |
| Contract | OpenAPI and event schema validation. Prototype samples S1 to S8 as fixtures |
| Property | A routed chain never contains the submitter, never repeats a person, never skips a tier |
| Integration | Publish then read in force on date. Idempotent publish. Immutable versions |
| Non-functional | Load test for p95. Log scan for PII. IaC scan for KMS and region |

## 10. Open questions

| # | Question | Owner |
| --- | --- | --- |
| Q44 | Use a transactional outbox or EventBridge retry for the publish event? Proposal: DynamoDB stream to EventBridge Pipe so the write is the source of truth | Architect |
| Q45 | Should reads of rules be allowed for all employees or only approvers and finance? Proposal: all signed-in users, since limits are not secret | Solution Owner |
| Q46 | Should `effectiveFrom` allow back-dating for corrections? Proposal: no, immutable and forward only | Solution Owner |
| Q39 | Who resolves role holders (line manager, department head, finance controller, CFO)? Proposal: `approve` via a directory adapter, so `policy` stays free of HR data | Architect |
