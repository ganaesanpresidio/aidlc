---
id: LLD-submit
title: LLD — submit unit
activity: DIS-04
unit: submit
status: Draft — awaiting design review
version: 0.1.0
last_updated: 2026-11-04
owner: Architect + Engineer
---

# LLD: `submit` unit

Spec: [spec.md](spec.md). HLD: [hld.md](../hld.md). API: [api/openapi.yaml](api/openapi.yaml). Events: [api/events/](api/events/). Policy contract: [policy openapi](../policy/api/openapi.yaml).

## 1. Context

Lambda behind API Gateway (JWT). Receipts go straight from the browser to a quarantine S3 bucket with a presigned POST, are scanned by Amazon GuardDuty Malware Protection for S3, and move to a clean bucket only if safe ([ADR-009](../../decisions/adr-009-malware-scan-guardduty.md)). Submit calls `policy` `evaluate` over IAM. Other units are reached by events only.

```text
browser -> API Gateway -> submit Lambda -> DynamoDB (claims)
browser -> presigned POST -> quarantine bucket -> GuardDuty scan -> scan-result event
scan-result Lambda -> clean bucket (receipts) -> ReceiptStored event
submit Lambda -> policy evaluate (IAM) -> ClaimSubmitted event
```

## 2. APIs

Contract in [api/openapi.yaml](api/openapi.yaml). All paths need a JWT and act only on the caller's own claims.

| Operation | Purpose | Notes |
| --- | --- | --- |
| `POST /v1/claims` | Create a draft | Returns `claimId` (ULID) |
| `GET /v1/claims`, `GET /v1/claims/{claimId}` | My claims, one claim | Other people's claims give 404 |
| `POST /v1/claims/{claimId}/lines`, `PATCH`, `DELETE` | Edit lines | Draft only |
| `POST /v1/claims/{claimId}/lines/{lineId}/receipts` | Get a presigned POST | Enforces type, size, count, SHA-256 |
| `GET /v1/claims/{claimId}/lines/{lineId}/receipts/{receiptId}` | Status: `PENDING_UPLOAD`, `SCANNING`, `CLEAN`, `REJECTED` | Includes duplicate warning |
| `DELETE` same path | Remove a receipt | Draft only |
| `GET .../receipts/{receiptId}/content` | 302 to a 60 second signed URL | Owner only here |
| `POST /v1/claims/{claimId}/submit` | Submit | Needs `Idempotency-Key` |
| `POST /v1/claims/{claimId}/withdraw` | Withdraw | Only before any approval step |
| `POST /internal/v1/receipts/{receiptId}/access-url` | Signed URL for an approver or finance | IAM, called by `approve` only (Q43) |

## 3. Events

| Event | Direction | Schema |
| --- | --- | --- |
| `ReceiptStored` v1 | publishes | [schema](api/events/ReceiptStored.v1.schema.json) |
| `ClaimSubmitted` v1 | publishes | [schema](api/events/ClaimSubmitted.v1.schema.json) |
| `ClaimWithdrawn` v1 | publishes | [schema](api/events/ClaimWithdrawn.v1.schema.json) |
| `ReceiptsExpired` v1 | publishes | [schema](api/events/ReceiptsExpired.v1.schema.json) |
| `ClaimApproved`, `ClaimRejected`, `PayoutIssued` | consumes | Update the claim status shown to the employee |

**Change to the DIS-03 contract:** `ClaimSubmitted` needs `submitterId`, `requiresException` and `rulesVersion` so `approve` can call `policy` route without reading submit's tables. [interfaces.md](../../inception/units/interfaces.md) is updated to match.

## 4. Data model

DynamoDB table `submit-claims` (KMS CMK, point-in-time recovery). Receipts bucket and quarantine bucket are separate, both KMS, public access blocked, versioning on.

| Item | PK | SK | Main attributes |
| --- | --- | --- | --- |
| Claim | `CLAIM#<claimId>` | `META` | employeeId, gradeAtCreate, status, claimRef (after submit), totalInr, rulesVersion, createdAt, submittedAt, version |
| Line | `CLAIM#<claimId>` | `LINE#<lineId>` | date, category, amount, currency, amountInr, description, exceptionReason |
| Receipt | `CLAIM#<claimId>` | `RCPT#<receiptId>` | lineId, objectKey, mimeType, sizeBytes, sha256, status, uploadedAt, expiresOn |
| Duplicate index | `DUP#<employeeId>#<sha256>` | `<claimId>#<receiptId>` | none |
| Counter | `COUNTER#CLM#<year>` | `META` | last number |
| Idempotency | `IDEM#<claimId>#<key>` | `META` | result, ttl 24 h |

| Index | Key | Answers |
| --- | --- | --- |
| GSI1 | `EMP#<employeeId>` / `createdAt` | My claims, newest first |
| GSI2 | `EXP#<yyyy-mm-dd>` / `receiptId` | Receipts to delete today (US-006) |

Access patterns: get claim with lines and receipts (one query on `PK`), my claims (GSI1), duplicate check (one get on the `DUP` key), expiry (GSI2). Claim reference is `CLM-<year>-<6 digits>` from the counter, assigned at submit only. Status values follow the [domain model](../../inception/domain-model.md). Optimistic locking uses `version`.

Receipt `status` and `expiresOn` are set after scan. `expiresOn` is upload date plus the retention days in the rules (Q13, Q42).

## 5. Sequences

### Attach a receipt (AC2 to AC6, AC9)

1. Client asks for an upload slot for a line. Submit checks: claim is a draft and the caller's, line has fewer than 5 receipts, declared type is allowed, declared size is 10 MB or less.
2. Submit creates the receipt item as `PENDING_UPLOAD` and returns a presigned POST valid for 5 minutes. Its conditions fix the key, the content length range (1 byte to 10 MB), the content type and the SHA-256 checksum.
3. Browser uploads to the quarantine bucket. S3 rejects anything outside the conditions.
4. GuardDuty scans the object and sends a scan-result event. Receipt becomes `SCANNING` on the S3 event, then:
5. **Clean:** a Lambda checks the file's first bytes match its type, copies the object to the receipts bucket, sets `CLEAN`, writes the `DUP` item, and emits `ReceiptStored`. If the `DUP` key already exists for another claim, the status response carries `duplicateOf` with that claim reference.
6. **Infected or bad type:** delete the object, set `REJECTED`, write a security audit event, show "This file can't be used".

### Submit (AC7, AC7a, AC8)

1. Check the claim is the caller's and a draft, has at least 1 line, and every line is complete.
2. Check no receipt is `SCANNING` or `PENDING_UPLOAD` (X3).
3. Build `hasReceipt` per line from `CLEAN` receipts. Call `policy` `evaluate`. If it fails or times out, refuse with 503 (fail closed).
4. If `ok` is false, return 422 with the violations per line. "Add a receipt" is the message for `RECEIPT_REQUIRED`.
5. In one DynamoDB transaction: take the next counter value, set `claimRef`, `status=Submitted`, `submittedAt`, `rulesVersion`, `totalInr`, store the idempotency result. Condition: `version` unchanged and status still `Draft`.
6. Emit `ClaimSubmitted` and an audit event.

### Retention expiry (US-006)

1. A daily EventBridge Scheduler job queries GSI2 for today's date.
2. For each receipt: delete the object (and versions), delete the `DUP` item, mark `EXPIRED`.
3. Emit `ReceiptsExpired` with the ids and an audit event.

## 6. Errors and retries

| Case | Behaviour |
| --- | --- |
| `policy` unavailable | Submit returns 503 `POLICY_UNAVAILABLE`. Nothing changes. Client retries with the same key |
| Scan result never arrives | Receipt stays `SCANNING`. After 5 minutes an alarm fires and a sweeper marks it `REJECTED` with reason `SCAN_TIMEOUT` |
| Two submits at once | One wins by the version condition. The other gets 409 and re-reads |
| Upload expired | Receipt stays `PENDING_UPLOAD`. A sweeper deletes it after 1 hour |
| Event publish fails | Same pattern as `policy`: DynamoDB stream to EventBridge Pipe, so the write is the source of truth (Q44) |
| Counter gap after failed transaction | Allowed. References are unique, not gap-free |

Error body: `{code, message, details[]}`. Codes include `CLAIM_NOT_EDITABLE`, `RECEIPT_LIMIT`, `FILE_TOO_LARGE`, `FILE_TYPE_NOT_ALLOWED`, `RECEIPT_STILL_CHECKING`, `POLICY_VIOLATIONS`, `POLICY_UNAVAILABLE`.

## 7. Security and PII

- Receipts hold names and part card numbers. SSE-KMS, TLS only, block public access, no direct bucket URLs.
- Access: the submitter through `GET .../content`. Approvers and finance through the internal access-url call by `approve` (Q43). Signed URLs last 60 seconds and are never logged.
- Quarantine objects cannot be read by users, only by the scan and move Lambdas.
- Logs and events carry ids, codes and sizes only. No file names, no descriptions, no amounts with names.
- Strangers get 404, never 403 (X4), so claim ids are not guessable by response.
- One IAM role per function: the submit API cannot read the quarantine bucket, the mover cannot call the API tables beyond receipt items.
- Audit events: who, what, when, claimRef, rulesVersion.
- Duplicate index uses a hash of the file, not the file.

## 8. NFR mapping

| NFR | Design element | Verified by |
| --- | --- | --- |
| Audit 100% | Audit event in every state-changing path, including rejects and expiry | Integration test and log query |
| PII in logs: 0 | Allow-list logger. Presigned URLs redacted | Log scan in BLD-02 |
| Latency reads p95 under 300 ms | Keyed queries, no scans | Load test |
| Latency writes p95 under 500 ms (no upload) | One transaction per write, `policy` call about tens of ms | Load test |
| Upload 10 MB in 10 s | Direct to S3 by presigned POST | Load test with 10 MB file |
| Availability 99.9% | Managed services, retries, sweepers | CloudWatch SLO |
| RPO 1 h, RTO 4 h | PITR, S3 versioning, IaC | DR test |
| Encryption | KMS CMK, TLS | IaC scan |
| Residency | One region, SCP guard | IaC scan |
| Retention | Expiry index and daily job. 100% deleted | Test with a 1-day period |
| Malware: 0 stored unscanned | Quarantine first, move only after clean result | Test with the EICAR file |
| Capacity 5,000 claims a day, 10x | On-demand DynamoDB, S3 scaling. About 15,000 uploads a day | Load test |

## 9. Test approach

| AC | Test |
| --- | --- |
| AC1 | API test: create, add 2 lines, totals per currency |
| AC2 | Upload each allowed type of 10 MB or less |
| AC3 | Camera is the same upload. Front-end test in a mobile browser |
| AC4 | `.exe` and `.docx` refused at slot request and by magic bytes |
| AC5 | 10 MB + 1 byte refused. 6th file refused |
| AC6 | EICAR file ends `REJECTED`, object deleted, security audit event written |
| AC7 / AC7a | Line of 1,000.00 needs a receipt. 999.99 does not. USD line always does |
| AC8 | Reference format, status, no edits after (X2), idempotent (X1) |
| AC9 | Same hash on a second claim returns `duplicateOf` and still allows continue |
| AC10 | Every action writes an audit event. Log scan finds no names or file content |
| X3, X4 | Submit during scan blocked. Other employee's claim gives 404 |

Also: contract tests against both OpenAPI files, event schema validation, `policy` stub that returns the prototype's sample results, load test, IaC scan.

## 10. Open questions

| # | Question | Owner |
| --- | --- | --- |
| Q40 | Non-INR lines have no INR total, so tiers cannot be picked. Proposal: the employee enters an INR equivalent for each non-INR line, finance verifies at payout | Solution Owner |
| Q41 | Q15 said submit does not check limits. The approved mock policy says an over-limit line cannot be submitted without a reason. Proposal: Q15 is superseded, and submit enforces limits through `evaluate` | Solution Owner |
| Q42 | Retention days must be configurable. Proposal: add optional `retention_days` to the rules schema | Architect |
| Q43 | Approvers cannot read `submit` data directly. Proposal: `approve` asks `submit` for a signed URL over IAM after it has checked the assignment | Architect |
| Q44 | Event publishing: transactional write plus DynamoDB stream to EventBridge Pipe | Architect |
| Q47 | Who builds the web app? Proposal: one web app, screens added in each unit's bolts, reviewed by FED | Architect |
