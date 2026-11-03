---
id: AM-001
title: Approval matrix
activity: DIS-02
status: Draft — awaiting Solution Owner and Architect sign-off
version: 0.1.0
last_updated: 2026-11-03
owner: Solution Owner
source: mock-expense-policy.md §5, §6 (MOCK data)
---

# Approval matrix

Source of truth is the rules config [policy-rules.example.yaml](policy-rules.example.yaml). This page is a readable copy. Also published to the Confluence `AIDLC` space.

## Tiers by claim total (INR)

| Tier | Claim total | Step 1 | Step 2 |
| --- | --- | --- | --- |
| T1 | up to 10,000 | Line Manager | none |
| T2 | 10,001 to 50,000 | Line Manager | Department Head |
| T3 | 50,001 to 200,000 | Department Head | Finance Controller |
| T4 | above 200,000 | Finance Controller | CFO |

An exception line (above its category limit) adds the Finance Controller as a final step if not already in the chain.

## Segregation of duties

| Rule | Meaning |
| --- | --- |
| SOD-1 | Submitter never approves own claim; routing skips to the next role up |
| SOD-2 | Two steps need two different people |
| SOD-3 | Payer cannot approve the same claim |
| SOD-4 | Approver grade is at least the submitter's grade |

## Escalation

No action in 5 working days: the claim moves to the next role up the chain.
