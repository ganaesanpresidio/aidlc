---
id: ADR-007
title: OCR is asynchronous and never blocks submit
status: Proposed
date: 2026-11-03
deciders: [Architect]
---

# ADR-007 · OCR is asynchronous and never blocks submit

## Context

AWS Knowledge MCP shows synchronous AnalyzeExpense is limited to 1 request per second per account in Mumbai, and asynchronous StartExpenseAnalysis to 5. Peak load could be about 2 per second.

## Decision

Receipt reading runs after upload through a queue and the asynchronous API. Results arrive as ReceiptExtracted events and are only suggestions. Submit never waits for them.

## Consequences

Submit stays fast and available if OCR is slow or down. Employees may see suggestions a few seconds late. A quota increase may still be needed.
