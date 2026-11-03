---
id: NFR-001
title: NFR matrix per unit
activity: DIS-03
status: Draft — awaiting Architect approval
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
inputs: [nfr-baseline.md, prd.md, units/README.md]
---

# NFR matrix

Targets start from the [NFR baseline](nfr-baseline.md), which is still ASSUMPTION. Each row has a metric, a target and a way to verify it. Unit columns: P policy, S submit, A approve, O ocr, Y payout, B bi.

## 1. Minimum NFR set

| NFR | Metric | Target | Applies to | Verified by | Baseline |
| --- | --- | --- | --- | --- | --- |
| Audit | Share of state changes that write an immutable audit event | 100%, kept 7 years | P S A Y | Integration test and log query | B3, B9 |
| PII in logs | PII or receipt content found in logs | 0 | all | SAST and log scan in BLD-02 | B10 |
| SoD | Self-approval or payer-as-approver accepted | 0 | A Y P | Unit tests with the 8 sample claims, UAT | B12 |
| Latency, reads | p95 API response | under 300 ms | P S A Y B | Load test | B8 |
| Latency, writes | p95 API response, excluding upload and OCR | under 500 ms | S A Y | Load test | B8 |
| Upload | 10 MB receipt upload | 10 s or less | S | Load test | B8 |
| Availability | Monthly uptime | 99.9% | S A P Y | CloudWatch SLO | B6 |
| Recovery | RPO and RTO | 1 hour and 4 hours | all | DR test | B7 |
| OCR accuracy | Field accuracy on the sample set | 95% or more | O | OCR test pack | n/a |
| Encryption | Data at rest and in transit | KMS AES-256, TLS 1.2 or higher | all | IaC scan, config check | B4, B5 |
| Residency | Data stored outside the India region | none | all | IaC scan, region guardrail | B1 |
| Retention | Receipts deleted after the period | 1 year, configurable, 100% deleted | S O | Scheduled test with a short period | B2 |
| Malware | Uploads stored without a scan | 0 | S | Test with the EICAR file | B13 |
| Capacity | Load sustained | 5,000 claims a day, 10x burst | all | Load test | B14 |
| Cost | Monthly cloud cost per 1,000 claims | Target to set from the first LLD estimate | all | Cost report | n/a |

## 2. OCR throughput check (from AWS Knowledge MCP, 2026-11-03)

- Baseline B14 is 5,000 claims a day. At about 3 receipts a claim that is 15,000 receipts a day, or 0.2 per second on average.
- A 10x burst is about 2 per second. Synchronous `AnalyzeExpense` in Mumbai allows 1 per second per account, so it would throttle.
- `StartExpenseAnalysis` (asynchronous) allows 5 per second in Mumbai. Use it behind a queue, and request a quota increase if needed ([ADR-007](../decisions/adr-007-async-ocr.md)).
- Textract and Step Functions are available in `ap-south-1`.

## 3. PII fields and controls per unit

| Unit | PII fields | Control |
| --- | --- | --- |
| policy | none | n/a |
| submit | receipt image (names, part card numbers), description, employee id | Encrypt with KMS, malware scan, role-based access, never log, delete at retention end |
| approve | employee id, comment text | Access only while assigned, never log comments |
| ocr | extracted merchant, amounts, any card digits | Mask card digits, encrypt, never log values, delete with the receipt |
| payout | employee id, amount, payment reference | No bank details stored in v1, reference only, audit every change |
| bi | pseudonymised employee id | Pseudonymise, no receipt content, finance and audit roles only |

## 4. Open points

- Every baseline value is an ASSUMPTION until the bank confirms it (see [nfr-baseline.md](nfr-baseline.md)).
- Cost target needs a first estimate from the LLDs in DIS-04.
- HEIC conversion for OCR (see [ocr.md](units/ocr.md)).
