---
id: UNIT-ocr
title: Unit — ocr
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
build_order: 5
---

# Unit `ocr`

| Field | Value |
| --- | --- |
| Scope | Read receipts asynchronously and return date, amount, merchant as suggestions. Never blocks submit |
| Owner | Architect (team to be named) |
| Stories | None yet. Optional enhancement. See [story-map.md](story-map.md) |
| Depends on | `submit` (events) |
| Build order | 5 |

## Data owned

Extraction results (field, value, confidence) keyed by receipt id.

## APIs (v1)

| Method and path | Purpose |
| --- | --- |
| `GET /v1/extractions/{receiptId}` | Read the suggestion |

## Events

Consumes `ReceiptStored`. Publishes `ReceiptExtracted`, `ReceiptExtractionFailed`.

## PII and controls

Extracted fields may hold names and part card numbers. Store encrypted, mask card digits, never log values, delete with the receipt.

## AWS notes (from AWS Knowledge MCP, checked 2026-11-03)

- Amazon Textract is available in `ap-south-1`.
- `AnalyzeExpense` synchronous is limited to 1 transaction per second per account in Mumbai. `StartExpenseAnalysis` (asynchronous) allows 5. Use a queue and the asynchronous call ([ADR-007](../../decisions/adr-007-async-ocr.md)).
- Synchronous document size limit is 10 MB, which matches the PRD upload limit.
- Textract reads JPEG, PNG and PDF. HEIC is accepted by `submit`, so it must be converted to JPEG first. Confirm in the LLD.
