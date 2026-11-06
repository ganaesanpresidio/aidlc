---
id: BUILD-submit
title: Build notes — submit unit
activity: BLD-01
unit: submit
status: Built on the mock backend — awaiting Architect review of the changes below
version: 0.1.0
last_updated: 2026-11-04
owner: Engineer
---

# Build notes: `submit` unit

Code: [src/submit/](../../../src/submit/). Tests: [tests/submit/](../../../tests/submit/) and [tests/integration/](../../../tests/integration/). Approved design: [lld.md](lld.md).

## Status by bolt

| Bolt | Result |
| --- | --- |
| S1 Claims and lines | Done |
| S2 Receipt upload path | Done: presigned slot, type, size, count, checksum rules |
| S3 Scan and store | Done: quarantine, scan, first-bytes check, move, timeout sweeper |
| S4 Submit | Done: policy check, reference, idempotency, immutability, events. Policy runs in the same process in mock mode |
| S5 Duplicates and privacy | Done |
| S6 Retention and withdraw | Done: daily expiry job, withdraw, status follows approve and payout events |
| S7 Harden | Partly. **Not done** (needs AWS): load test, IaC scan, alarms, DR test |

All AC1 to AC10 and X1 to X4 have tests. The mapping is in [lld.md](lld.md) section 9.

## How to run it

```bash
uv run pytest
uv run aidlc-e2e demo
uv run aidlc-e2e serve submit
```

`AIDLC_BACKEND=mock` (default) uses in-memory tables, files, scanner and policy. `AIDLC_BACKEND=aws` uses DynamoDB, S3, GuardDuty and a signed call to `policy`. The real adapters are **unverified against AWS**: they are checked with botocore's stubber and presigned-URL generation only.

## Differences from the approved design (review these)

| # | Change | Why | Contract file touched |
| --- | --- | --- | --- |
| 1 | Receipt reject reason `SCAN_FAILED` added | GuardDuty can report unsupported, access denied or failed. These were not covered | [openapi.yaml](api/openapi.yaml): `Receipt.rejectReason` |
| 2 | Index GSI3 (`WAIT#<status>`) added | The sweeper needs receipts waiting on a scan or an upload. The LLD named the sweepers but no index | none (data model) |
| 3 | Expiry index uses one key `EXPIRY` with the date in the sort key, not `EXP#<date>` | A range query catches up if the daily job misses days. One key per date would never see them again | none |
| 4 | Pointer item `REF#<claimRef>` added | Status events carry the reference, so the claim must be found by it | none |
| 5 | Every line, receipt and claim write also bumps the claim version | A submit that read the old version must fail if a line changes meanwhile (race test) | none |
| 6 | At most 50 lines per claim | A guard against runaway data | none |
| 7 | Amounts have at most 2 decimals and a maximum of 99,999,999.99 | Money precision and a crash found by an edge test with huge exponents | none |
| 8 | Batch jobs skip a bad item and carry on | One orphaned receipt must not stop the whole sweep or expiry run | none |
| 9 | Failed event and audit publishes are queued and retried | Same as policy (Q44) | none |
| 10 | "Today" is the business date in `AIDLC_TIMEZONE` (default Asia/Kolkata) | Reference year and the policy date follow the company day (Q48) | none |
| 11 | Duplicate warning shows the claim id when the other claim is still a draft | Drafts have no reference yet | none |

## Behaviour to confirm

- A receipt slot that was never used blocks submit (it counts as "still being checked"), until the sweeper removes it after one hour.
- Duplicate checks use only the same employee's other claims, not the same claim.
- `retention_days` is a submit setting (`AIDLC_RETENTION_DAYS`, default 365), not yet a field in the policy rules (Q42).

## Test page for lower environments

[web/expense-submit.html](../../../web/expense-submit.html) is one file with no libraries. It is **a test tool, not the product screen** (Q47 is still open).

```bash
uv run aidlc-e2e serve submit      # then open http://127.0.0.1:8102/
```

- **Flow:** create a claim, add lines, attach receipts, submit, withdraw, refresh.
- **Checks in the page:** the same rules as the service, shown next to each field: date, category, amount (at most 2 decimals), currency code, INR equivalent for foreign lines, kilometres for mileage, 500-character limits, file type, size and the 5-receipt limit. It warns about the 30-day window and the ₹1,000 receipt rule.
- **Server stays the judge:** the switch "Test mode: skip this page's checks" sends whatever you type so you can see the server's own errors.
- **Other environments:** set the API base URL and choose "Bearer token". Receipt upload then posts to the storage URL the API returns. The API must allow this page's origin (CORS), which is not set up yet.
- **Data:** the token is kept in the page only. Settings other than the token are kept for the browser session. Do not use real receipts.
- **Tested** in the browser pane (desktop, phone width, dark mode) and by a pytest that checks the page calls only routes in the OpenAPI file and uses the same limits as the code.

## Not built, on purpose

The product web screens (Q47), real JWT checking, the CDK stack, and the deploy pipeline.
