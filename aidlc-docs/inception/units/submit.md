---
id: UNIT-submit
title: Unit — submit
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
build_order: 2
---

# Unit `submit`

| Field | Value |
| --- | --- |
| Scope | Create and edit claims and expense lines, upload receipts, validate and submit, withdraw, drafts, retention clean-up |
| Owner | Architect (team to be named) |
| Stories | US-001 to US-006 (DEV-2 to DEV-7) |
| Depends on | `policy` (reads rules) |
| Build order | 2 |

## Data owned

Claim, Expense line, Receipt metadata, receipt files (encrypted S3 bucket). No other unit reads these tables.

## APIs (v1)

| Method and path | Purpose |
| --- | --- |
| `POST /v1/claims`, `GET /v1/claims/{ref}`, `PATCH /v1/claims/{ref}` | Create, read, edit a draft |
| `POST /v1/claims/{ref}/lines/{id}/receipts` | Upload a receipt |
| `POST /v1/claims/{ref}/submit` | Submit |
| `POST /v1/claims/{ref}/withdraw` | Withdraw |

## Events

Publishes `ClaimSubmitted`, `ClaimWithdrawn`, `ReceiptStored`, `ReceiptsExpired`. Consumes `ClaimApproved`, `ClaimRejected`, `PayoutIssued` to show status.

## PII and controls

Receipt images (names, part card numbers): encrypt with KMS, scan for malware, access only for submitter, approvers and finance, never log content.

## AWS services (candidates, confirmed in DIS-04)

S3, KMS, API Gateway, Lambda, DynamoDB or Aurora, EventBridge.
