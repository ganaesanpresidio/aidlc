---
id: DIS-04
title: HLD and LLD per Unit + Design Approval
phase: Discover
phase_focus: What & why
sequence: 4 of 8
actors: [Architect, Engineer]
status: Draft
version: 1.0.0
last_updated: 2026-10-29
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 2, row 4
previous: DIS-03
next: BLD-01
---

# DIS-04 · HLD and LLD per Unit + Design Approval

> **One line:** For each unit, Claude drafts the high-level and low-level design (APIs, data, sequences); the Architect and Engineer review it, and the client approves it before any build starts.

## At a glance

| Field | Value |
| --- | --- |
| Phase | Discover · What & why |
| Actor (role) | Architect + Engineer |
| Tools & agents | Claude Code plan mode, AWS Diagram MCP |
| Skills | GS `/plan-eng-review` · AO `/spec`, `/plan` |
| Workflow | HLD → LLD (APIs, data, sequence) → design review |
| Hooks | `PreToolUse`: no build until LLD approved |
| Entry gate | DIS-03 units + NFRs approved |
| Exit gate (HUMAN GATE) | Design review passed and client approval recorded, per unit |

## 1. Objective

1. One **HLD** for the platform: context diagram, AWS architecture, unit boundaries, security zones.
2. One **LLD per unit**: API contracts (OpenAPI), events (schemas), data model (tables, keys, retention), sequence diagrams for key flows, error handling, NFR mapping.
3. A **design review** and **client approval** per unit. A unit with an approved LLD can enter Build; others cannot.

## 2. Roles and responsibilities

| Role | Responsibility in this activity | Decision rights |
| --- | --- | --- |
| Architect | Owns HLD; reviews every LLD against NFRs and ADRs | **Approves** design |
| Engineer | Co-writes LLDs; confirms buildability and testability | Advises; may block if unbuildable |
| Solution Owner / Client | Reviews design document | **Approves** for client sign-off |
| FED (on demand) | Reviews approver UX and dashboard flows in `submit`, `approve`, `bi` | Advises |
| Claude (AI) | Drafts specs, plans, diagrams; runs the engineering review | None — proposes only |

## 3. Entry criteria (inputs)

- [ ] `aidlc-docs/approvals/units-nfr.md` shows `Status: APPROVED`.
- [ ] Unit files, interfaces and NFR matrix from DIS-03.
- [ ] ADRs from DIS-02.
- [ ] AWS Diagram MCP connected (needs local Graphviz per its README).

## 4. Tools, MCP servers and agents

### 4.1 Tools and MCP servers

| Tool / MCP server | Used for | Access notes |
| --- | --- | --- |
| Claude Code **plan mode** | Explore options and trade-offs before writing designs | Exit plan mode only to write files under `aidlc-docs/design/` |
| AWS Diagram MCP (`awslabs/mcp`) | Generate AWS architecture and sequence diagrams as code | Commit the diagram source and the image |

### 4.2 Agents

| Agent | Type | Responsibility |
| --- | --- | --- |
| `solution-designer` | Claude Code subagent | Drafts HLD and LLD per unit, runs one per unit in parallel |
| Main Claude session | Orchestrator | Runs `/plan-eng-review` and collects review findings |

Subagent definition (`.claude/agents/solution-designer.md`):

```markdown
---
name: solution-designer
description: Writes the HLD and per-unit LLD (OpenAPI, event schemas, data model, sequence diagrams) for the expense platform. Use in Discover / DIS-04, one invocation per unit.
---

Rules:
- Follow the approved unit scope, interfaces, NFR matrix and ADRs. Do not change scope.
- Each LLD has these sections: Context, APIs (OpenAPI), Events, Data model, Sequences,
  Errors and retries, Security and PII, NFR mapping, Test approach, Open questions.
- Every NFR in the matrix maps to a design element or is flagged.
- Diagrams are code (AWS Diagram MCP / Mermaid) and are committed next to the LLD.
- Write only under aidlc-docs/design/.
```

## 5. Skills

| Skill | Library | When to invoke | Expected output |
| --- | --- | --- | --- |
| `/spec` | AO · Addy Osmani | Start of each unit: turn the unit file into a precise spec | `aidlc-docs/design/<unit>/spec.md` |
| `/plan` | AO · Addy Osmani | After spec: break the unit into bolts and tasks | `aidlc-docs/design/<unit>/plan.md` |
| `/plan-eng-review` | GS · gstack | Before human review: AI engineering review of the design | Review findings list |

## 6. Workflow

**Flow:** HLD → LLD (APIs, data, sequence) → design review

1. **HLD** · Architect + Claude (plan mode, AWS Diagram MCP) · Platform context, AWS architecture (API Gateway, Lambda/containers, Step Functions, Textract, data stores), security zones. Output: `aidlc-docs/design/hld.md`.
2. **Spec per unit** · `solution-designer` (`/spec`) · One run per unit, in parallel.
3. **LLD per unit** · `solution-designer` · APIs, events, data model, sequences (e.g. *submit → OCR → policy check → route to approver*).
4. **Plan per unit** · Claude (`/plan`) · Bolts and tasks, each small enough for one bolt.
5. **AI engineering review** · Claude (`/plan-eng-review`) · Findings on coupling, failure modes, NFR gaps, test gaps.
6. **Design review** · Architect + Engineer (+ FED for UX units) · Accept, change or reject each finding; update LLD.
7. **Client approval** · Solution Owner / client · Review the design document (publish to Confluence if needed).
8. **HUMAN GATE — LLD approval** · Architect records `aidlc-docs/approvals/lld-<unit>.md` per unit. This unlocks `src/<unit>/` for Build (see hook).

## 7. Hooks

| Event | Matcher | Purpose | Behaviour |
| --- | --- | --- | --- |
| `PreToolUse` | `Write\|Edit\|MultiEdit` | No build until the unit's LLD is approved | If the target is under `src/<unit>/` and `lld-<unit>.md` is not `APPROVED`, exit `2` blocks the write |

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
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/require-lld-approval.sh"
          }
        ]
      }
    ]
  }
}
```

`.claude/hooks/require-lld-approval.sh`:

```bash
#!/usr/bin/env bash
# Blocks code writes for a unit until that unit's LLD is approved.
set -euo pipefail
FILE=$(jq -r '.tool_input.file_path // empty')
REL="${FILE#"$CLAUDE_PROJECT_DIR"/}"
case "$REL" in
  src/*/*) UNIT=$(cut -d/ -f2 <<<"$REL") ;;
  *) exit 0 ;;
esac
GATE="$CLAUDE_PROJECT_DIR/aidlc-docs/approvals/lld-$UNIT.md"
if ! grep -q '^Status: APPROVED' "$GATE" 2>/dev/null; then
  echo "Blocked: LLD for unit '$UNIT' not approved (aidlc-docs/approvals/lld-$UNIT.md). Finish DIS-04 for this unit first." >&2
  exit 2
fi
```

## 8. Outputs and artifacts

| Artifact | Location in repo / tool | Owner |
| --- | --- | --- |
| HLD + architecture diagram | `aidlc-docs/design/hld.md`, `aidlc-docs/design/diagrams/` | Architect |
| Spec per unit | `aidlc-docs/design/<unit>/spec.md` | Engineer |
| LLD per unit | `aidlc-docs/design/<unit>/lld.md` | Architect + Engineer |
| OpenAPI / event schemas | `aidlc-docs/design/<unit>/api/` | Engineer |
| Bolt plan per unit | `aidlc-docs/design/<unit>/plan.md` | Engineer |
| Review findings | `aidlc-docs/design/<unit>/review.md` | Architect |
| LLD approval per unit | `aidlc-docs/approvals/lld-<unit>.md` | Architect |
| Client-approved design document | Confluence design space | Solution Owner |

## 9. Exit criteria (Definition of Done)

- [ ] HLD approved and published.
- [ ] Each LLD has all required sections and maps every NFR.
- [ ] OpenAPI and event schemas validate (lint passes).
- [ ] All `/plan-eng-review` findings are closed or accepted with a reason.
- [ ] Bolt plan exists for the unit.
- [ ] **HUMAN GATE:** `lld-<unit>.md` shows `Status: APPROVED`; client approval link recorded.

## 10. Starter prompts

```text
Plan mode. Draft the HLD for the expense platform from aidlc-docs/inception/.
Use AWS Diagram MCP for the architecture diagram. Show me options before writing.
```

```text
Run the solution-designer agent for unit "policy": /spec then LLD, then /plan.
Map every NFR in nfr-matrix.md to a design element.
```

```text
/plan-eng-review on aidlc-docs/design/policy/. List findings by severity with a proposed fix each.
```

## 11. Best practices

- **One LLD per unit, reviewed on its own.** Approve units one by one; Build can start on the first approved unit.
- **Contracts first.** Freeze OpenAPI and event schemas before code; they drive tests in BLD-01.
- **Diagrams as code.** Commit diagram source so designs are diff-able and reviewable.
- **Design for failure.** Every sequence shows retries, timeouts and the dead-letter path (e.g. OCR fails).
- **Trade-offs in writing.** Big trade-offs become ADRs, not chat history.

## 12. Anti-patterns to avoid

- One giant LLD for all units.
- Approving LLDs with open NFR gaps "to fix in build".
- Diagrams only as images with no source.
- Starting code in `src/` "just to try" before approval (the hook blocks this).

## 13. References

- AWS MCP servers (Diagram) — <https://github.com/awslabs/mcp>
- Addy Osmani agent-skills — <https://github.com/addyosmani/agent-skills>
- gstack — <https://github.com/garrytan/gstack>
- Claude Code subagents — <https://docs.claude.com/en/docs/claude-code/sub-agents>
- Full list: [../references.md](../references.md)

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 2, row 4 |
