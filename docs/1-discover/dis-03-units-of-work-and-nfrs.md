---
id: DIS-03
title: Units of Work and NFRs
phase: Discover
phase_focus: What & why
sequence: 3 of 8
actors: [Architect]
status: Draft
version: 1.0.0
last_updated: 2026-10-29
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 2, row 3
previous: DIS-02
next: DIS-04
---

# DIS-03 · Units of Work and NFRs

> **One line:** The Architect splits the platform into independent units of work and sets the non-functional requirements (audit, PII, SoD, performance) each unit must meet.

## At a glance

| Field | Value |
| --- | --- |
| Phase | Discover · What & why |
| Actor (role) | Architect |
| Tools & agents | Claude Code, AWS Knowledge MCP |
| Skills | GS `/autoplan` · AO `api-and-interface-design` |
| Workflow | Decompose: submit, approve, OCR, policy, payout, BI |
| Hooks | Approval gate: units + NFRs (audit, PII) |
| Entry gate | DIS-02 spec signed off |
| Exit gate (HUMAN GATE) | Architect approves the unit list, interfaces and NFR matrix |

## 1. Objective

1. Break the platform into **six units of work** that can be built and deployed in parallel bolts:

   | Unit | Scope |
   | --- | --- |
   | `submit` | Claim capture (web/mobile), receipt upload, draft/submit |
   | `approve` | Approval routing by tier, delegation, SoD checks |
   | `ocr` | Receipt extraction (Amazon Textract), confidence scoring |
   | `policy` | Rules engine reading the DIS-02 rules config |
   | `payout` | Reimbursement file / payment instruction, status tracking |
   | `bi` | Spend data feed and dashboards |

2. Define the **interfaces** (APIs and events) between units.
3. Set **NFRs** per unit with measurable targets.

## 2. Roles and responsibilities

| Role | Responsibility in this activity | Decision rights |
| --- | --- | --- |
| Architect | Owns decomposition, interfaces and NFRs; owns hooks | **Approves** units + NFRs |
| Engineer | Checks each unit fits in bolts; flags build risk | Advises |
| Solution Owner | Confirms business priority / build order of units | Approves order |
| Claude (AI) | Proposes decomposition, interface contracts and NFR matrix using AWS guidance | None — proposes only |

## 3. Entry criteria (inputs)

- [ ] `aidlc-docs/approvals/spec-signoff.md` shows `Status: APPROVED`.
- [ ] Domain model, rules schema and stories available.
- [ ] Bank's NFR baseline known (data residency, retention, encryption, availability).
- [ ] AWS Knowledge MCP connected.

## 4. Tools, MCP servers and agents

### 4.1 Tools and MCP servers

| Tool / MCP server | Used for | Access notes |
| --- | --- | --- |
| Claude Code | Drive decomposition and write unit specs | Plan mode first, then write under `aidlc-docs/` only |
| AWS Knowledge MCP (`awslabs/mcp`) | AWS service limits, Well-Architected guidance, service choices | Read-only |

### 4.2 Agents

| Agent | Type | Responsibility |
| --- | --- | --- |
| `unit-decomposer` | Claude Code subagent | Splits stories into units, maps stories → units, drafts interfaces |
| `nfr-analyst` | Claude Code subagent | Builds the NFR matrix (audit, PII, SoD, latency, availability, cost) |

Subagent definitions (`.claude/agents/unit-decomposer.md`, `.claude/agents/nfr-analyst.md`):

```markdown
---
name: unit-decomposer
description: Splits the expense platform into independent units of work and drafts the interfaces between them. Use in Discover / DIS-03.
tools: Read, Grep, Glob, Write, Edit
---

Rules:
- Each unit owns its data. No shared database tables between units.
- Every user story maps to exactly one primary unit.
- Units talk through versioned APIs or events only. Name every event in past tense.
- A unit must be buildable in bolts of hours to a few days.
- Write only under aidlc-docs/inception/units/.
```

```markdown
---
name: nfr-analyst
description: Defines measurable non-functional requirements per unit for a regulated bank (audit, PII, SoD, performance, availability, cost). Use in Discover / DIS-03.
---

Rules:
- Every NFR has a metric, a target and a verification method.
- Mark each unit's PII fields and the control for each (mask, encrypt, tokenise, do not store).
- Every state change on money or approval must write an immutable audit event.
- Use AWS Knowledge MCP to check service limits before setting a target.
```

## 5. Skills

| Skill | Library | When to invoke | Expected output |
| --- | --- | --- | --- |
| `/autoplan` | GS · gstack | First pass: produce a reviewed plan for the decomposition | Unit list, dependencies, build order |
| `api-and-interface-design` | AO · Addy Osmani | Once units are agreed, to design contracts between them | API and event contracts per unit |

## 6. Workflow

**Flow:** Decompose: submit, approve, OCR, policy, payout, BI

1. **Plan** · Architect + Claude (`/autoplan`) · Propose units, dependencies and build order.
2. **Map stories** · `unit-decomposer` · Every Jira story mapped to one unit; gaps flagged.
3. **Design interfaces** · Claude (`api-and-interface-design`) · Draft API and event contracts (e.g. `ClaimSubmitted`, `ClaimApproved`, `ReceiptExtracted`, `PayoutIssued`).
4. **Set NFRs** · `nfr-analyst` + AWS Knowledge MCP · NFR matrix per unit (see table below).
5. **Engineer check** · Engineer · Confirm each unit is buildable in bolts; split any that are too big.
6. **HUMAN GATE — approval gate** · Architect signs `aidlc-docs/approvals/units-nfr.md`. This unlocks LLD writing in DIS-04 (see hook).

Minimum NFR set for every unit:

| NFR | Example target | Verified by |
| --- | --- | --- |
| Audit | 100% of state changes write an immutable audit event | Integration test + log query |
| PII | No PII in logs; card / bank data tokenised | SAST + log scan in BLD-02 |
| SoD | Self-approval impossible; dual approval above threshold | Unit + UAT tests |
| Latency | p95 API < 300 ms (excl. OCR) | Load test |
| Availability | 99.9% monthly | CloudWatch SLO |
| OCR accuracy | ≥ 95% field accuracy on sample set | OCR test pack |

## 7. Hooks

| Event | Matcher | Purpose | Behaviour |
| --- | --- | --- | --- |
| `PreToolUse` (approval gate) | `Write\|Edit\|MultiEdit` | No LLD work before units + NFRs (audit, PII) are approved | If the target is under `aidlc-docs/design/` and `units-nfr.md` is not `APPROVED`, exit `2` blocks the write |

> The slide calls this an **approval gate**. Claude Code has no event with that name; it is built with a `PreToolUse` hook that checks the approval record.

`.claude/settings.json` snippet:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/require-units-nfr-approval.sh"
          }
        ]
      }
    ]
  }
}
```

`.claude/hooks/require-units-nfr-approval.sh`:

```bash
#!/usr/bin/env bash
# Blocks design (LLD) writes until units and NFRs are approved.
set -euo pipefail
FILE=$(jq -r '.tool_input.file_path // empty')
case "$FILE" in
  */aidlc-docs/design/*|aidlc-docs/design/*) ;;
  *) exit 0 ;;
esac
GATE="$CLAUDE_PROJECT_DIR/aidlc-docs/approvals/units-nfr.md"
if ! grep -q '^Status: APPROVED' "$GATE" 2>/dev/null; then
  echo "Blocked: units + NFRs (audit, PII) not approved (aidlc-docs/approvals/units-nfr.md). Finish DIS-03 first." >&2
  exit 2
fi
```

## 8. Outputs and artifacts

| Artifact | Location in repo / tool | Owner |
| --- | --- | --- |
| Unit catalogue (scope, owner, dependencies) | `aidlc-docs/inception/units/README.md` | Architect |
| One file per unit | `aidlc-docs/inception/units/<unit>.md` | Architect |
| Story → unit map | `aidlc-docs/inception/units/story-map.md` | Architect |
| Interface contracts (draft) | `aidlc-docs/inception/units/interfaces.md` | Architect |
| NFR matrix | `aidlc-docs/inception/nfr-matrix.md` | Architect |
| Approval record | `aidlc-docs/approvals/units-nfr.md` | Architect |

## 9. Exit criteria (Definition of Done)

- [ ] Six units defined, each with scope, owner, data ownership and dependencies.
- [ ] Every story mapped to one unit; no orphan stories.
- [ ] Every interface named and versioned; no shared tables.
- [ ] Every NFR has a metric, target and verification method.
- [ ] PII fields and controls listed per unit.
- [ ] **HUMAN GATE:** `units-nfr.md` shows `Status: APPROVED`, approver and date.

## 10. Starter prompts

```text
/autoplan — decompose the expense platform into units: submit, approve, ocr, policy, payout, bi.
Use the domain model and stories in aidlc-docs/inception/. Show dependencies and a build order.
```

```text
Using api-and-interface-design, draft the events and APIs between the six units.
Events in past tense, each with a version and payload schema. No shared tables.
```

```text
Using the nfr-analyst agent and AWS Knowledge MCP, build the NFR matrix per unit.
Include audit, PII, SoD, latency, availability, cost. Every row needs a verification method.
```

## 11. Best practices

- **Units own their data.** Independent units mean independent bolts and safer deploys.
- **Measurable NFRs only.** "Secure" is not an NFR; "no PII in logs, verified by scan" is.
- **Audit is a feature.** Treat the audit trail as a first-class output of every unit.
- **Build order by risk.** Start with `policy` and `approve` — they carry the most business risk.
- **Keep the gate honest.** The Architect owns hooks; changes to gate scripts need Architect review.

## 12. Anti-patterns to avoid

- One "core" unit that does everything.
- NFRs copied from a template with no targets.
- Units that share a database "for now".
- Starting LLDs while the unit list is still moving.

## 13. References

- AWS MCP servers — <https://github.com/awslabs/mcp>
- gstack — <https://github.com/garrytan/gstack>
- Addy Osmani agent-skills — <https://github.com/addyosmani/agent-skills>
- Amazon Textract — <https://aws.amazon.com/textract>
- Full list: [../references.md](../references.md)

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 2, row 3 |
