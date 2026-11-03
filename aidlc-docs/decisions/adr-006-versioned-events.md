---
id: ADR-006
title: Integration by versioned past-tense events
status: Proposed
date: 2026-11-03
deciders: [Architect]
---

# ADR-006 · Integration by versioned past-tense events

## Context

Approval, payment, reporting and OCR all react to a claim changing state. Direct calls between them would make a chain of dependencies.

## Decision

Units publish past-tense events (for example ClaimSubmitted) with a version and an id-only payload, on EventBridge. Synchronous calls are kept only where the user waits for an answer (policy evaluate and route).

## Consequences

Loose coupling and an audit trail for free. Consumers must handle duplicates and late events. A breaking change needs a new major version run side by side.
