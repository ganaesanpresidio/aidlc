---
id: ADR-005
title: Six units, each owns its data
status: Proposed
date: 2026-11-03
deciders: [Architect]
---

# ADR-005 · Six units, each owns its data

## Context

The platform has distinct jobs with different risk, load and owners: rules, submission, approval, payment, receipt reading and reporting. A shared database would tie their releases together.

## Decision

Split into six units: policy, submit, approve, payout, ocr, bi. Each owns its tables and files. No unit reads another unit's data. Contact is by versioned API or event only.

## Consequences

Units can be built in separate bolts and deployed on their own. Cross-unit questions need an API or an event, which costs some extra design. The submit unit is the largest and is watched in DIS-04.
