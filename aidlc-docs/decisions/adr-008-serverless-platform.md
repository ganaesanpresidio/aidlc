---
id: ADR-008
title: Serverless AWS platform in one region
status: Proposed
date: 2026-11-03
deciders: [Architect]
---

# ADR-008 · Serverless AWS platform in one region

## Context

Six small units, bursty load, a regulated bank that wants data in India, and a team that builds in bolts of a few days. Servers or clusters would add upkeep that none of these needs.

## Decision

Use Lambda and Step Functions for compute, DynamoDB and S3 for data, EventBridge and SQS for integration, API Gateway for the API, and CDK for infrastructure. Run in `ap-south-1` only, with separate dev, test and prod accounts.

## Consequences

Little to operate, scales with load, cost follows use. Cold starts and the 15 minute Lambda limit shape the design. DynamoDB needs access patterns decided up front, so each LLD must list its queries. If a unit outgrows Lambda, it can move to containers without changing its API or events.
