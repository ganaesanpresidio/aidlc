---
id: NFR-BASE-001
title: NFR baseline for the bank (starter assumptions)
activity: DIS-03
status: ASSUMPTION — starter values, not confirmed by the bank
version: 0.1.0
last_updated: 2026-11-03
owner: Architect
---

# NFR baseline (starter)

> **Starter assumptions.** The bank has not supplied its baseline. Every value below is an ASSUMPTION for DIS-03 to work from. The Architect and Compliance confirm or replace each one. Replace before go-live.

Sources: [PRD](prd.md) NFR-1 to NFR-5, [question log](question-log.md) Q13, Q14, risk R1.

| ID | Area | Baseline | Source | Status |
| --- | --- | --- | --- | --- |
| B1 | Data residency | All data stored and processed in one India AWS region (ap-south-1, Mumbai). No cross-border copy | Assumption for an INR bank | ASSUMPTION |
| B2 | Retention, receipts | 1 year, then deleted. Configurable | PRD NFR-4, Q13, risk R1 | ASSUMPTION, Compliance to confirm |
| B3 | Retention, audit events | 7 years, immutable | Assumption for a regulated bank | ASSUMPTION |
| B4 | Encryption at rest | AES-256 with customer-managed KMS keys, rotated yearly | PRD NFR-1 | ASSUMPTION |
| B5 | Encryption in transit | TLS 1.2 or higher on every hop | PRD NFR-1 | ASSUMPTION |
| B6 | Availability | 99.9% monthly for submit and approve. Planned downtime outside business hours | Assumption | ASSUMPTION |
| B7 | Recovery | RPO 1 hour, RTO 4 hours | Assumption | ASSUMPTION |
| B8 | Performance | 10 MB receipt upload in 10 s or less. API p95 under 500 ms | PRD NFR-5 | ASSUMPTION |
| B9 | Audit | Every create, attach, remove, submit, approve, reject and pay writes an immutable audit event with actor, time and rules version | PRD NFR-3, ADR-001 | ASSUMPTION |
| B10 | PII | Receipts may show names and part card numbers. Only the submitter, their approvers and finance can open them. Never in logs | PRD NFR-1, NFR-2, Q14 | ASSUMPTION |
| B11 | Access | Company SSO. Role-based access. No shared accounts | Q1 | ASSUMPTION |
| B12 | Segregation of duties | SOD-1 to SOD-4 enforced in the domain logic | ADR-002 | Decided in DIS-02 |
| B13 | Malware scanning | Every upload scanned before it is stored | PRD FR-5 | ASSUMPTION |
| B14 | Capacity | Sized for 10,000 employees and 5,000 claims a day | Assumption | ASSUMPTION |

## Open points for the Architect and Compliance

- B1 and B3: residency region and audit retention period.
- B2: legal minimum for receipt retention (risk R1).
- B6 and B7: availability and recovery targets.
