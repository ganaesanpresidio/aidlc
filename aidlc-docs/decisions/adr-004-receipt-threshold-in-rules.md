---
id: ADR-004
title: Receipt threshold moves into the rules config
status: Proposed
date: 2026-11-03
deciders: [Solution Owner, Architect]
---

# ADR-004 · Receipt threshold moves into the rules config

## Context

DIS-01 made the receipt threshold (₹1,000) a setting. DIS-02 now has one rules file for all policy numbers.

## Decision

Keep receipt_threshold in policy-rules YAML next to the limits, so the submit unit reads one source.

## Consequences

One place to change policy numbers. The submit unit must read rules, not its own setting.
