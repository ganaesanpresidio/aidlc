---
id: ADR-002
title: Segregation of duties is enforced in the model
status: Proposed
date: 2026-11-03
deciders: [Solution Owner, Architect]
---

# ADR-002 · Segregation of duties is enforced in the model

## Context

A UI-only check can be bypassed by an API call. A bank needs provable separation between submitter, approver and payer.

## Decision

Enforce SOD-1 to SOD-4 in the routing and approval domain logic, driven by flags in the rules config. The UI only reflects the result.

## Consequences

Every approval path is covered by the same checks. Tests use synthetic claims (8 in the rules check). A clash escalates or blocks, never silently passes.
