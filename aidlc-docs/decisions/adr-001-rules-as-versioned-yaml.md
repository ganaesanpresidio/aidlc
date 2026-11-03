---
id: ADR-001
title: Policy rules are versioned YAML config
status: Proposed
date: 2026-11-03
deciders: [Solution Owner, Architect]
---

# ADR-001 · Policy rules are versioned YAML config

## Context

Limits and approver tiers change often and need an audit trail. Hard-coding them means a release for every change.

## Decision

Store rules in YAML validated by policy-rules.schema.json. Each version has an effective date. A claim records the rules version it was checked against.

## Consequences

A new limit is a config change, reviewed like code. Past claims stay explainable. A bad edit is caught by schema validation and the sample-claim check.
