---
id: ADR-003
title: Approval tier is chosen by claim total
status: Proposed
date: 2026-11-03
deciders: [Solution Owner, Architect]
---

# ADR-003 · Approval tier is chosen by claim total

## Context

The tier could depend on the largest line, the total, or the category. The mock policy sets tiers by the claim total.

## Decision

Pick the tier from the claim total in INR. Exception lines add the Finance Controller. Non-INR conversion is out of scope for v1.

## Consequences

Simple to explain and audit. A claim of many small lines can reach a higher tier. Revisit when currency conversion is added.
