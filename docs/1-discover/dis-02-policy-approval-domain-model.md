---
id: DIS-02
title: Policy and Approval Rules as a Domain Model
phase: Discover
phase_focus: What & why
sequence: 2 of 8
actors: [Solution Owner, Architect]
status: Draft
version: 1.0.0
last_updated: 2026-10-29
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 2, row 2
previous: DIS-01
next: DIS-03
---

# DIS-02 · Policy and Approval Rules as a Domain Model

> **One line:** Expense policy and the approval matrix become an explicit domain model and rules-as-config, so limits and approver tiers change by config — not by code.

## At a glance

| Field | Value |
| --- | --- |
| Phase | Discover · What & why |
| Actor (role) | Solution Owner + Architect |
| Tools & agents | Claude Code plan mode, Confluence MCP |
| Skills | MP `grill-with-docs`, `ubiquitous-language` → ADRs |
| Workflow | Rules as config: tiers per team/role, limits |
| Hooks | `PreToolUse`: no code writes before spec sign-off |
| Entry gate | DIS-01 PRD and stories signed off |
| Exit gate (HUMAN GATE) | Solution Owner + Architect sign off the spec (domain model, rules config, ADRs) |

## 1. Objective

Produce a single, reviewed specification of:

1. **Domain model** — entities and their relationships (Employee, Claim, Expense Line, Receipt, Policy, Approval Tier, Approver, Cost Centre, Reimbursement).
2. **Ubiquitous language** — one meaning per term, shared by finance, product and code.
3. **Policy rules as config** — limits per category, per role, per team; approval tiers by amount; segregation of duties (SoD).
4. **ADRs** — the key decisions (e.g. "rules stored as versioned YAML", "approver cannot approve own claim").

## 2. Roles and responsibilities

| Role | Responsibility in this activity | Decision rights |
| --- | --- | --- |
| Solution Owner | Owns policy content, limits and approval matrix | **Approves** rules and limits |
| Architect | Owns the domain model shape, SoD rules, ADRs | **Approves** model and ADRs |
| BA (on demand) | Checks rules against the written finance policy | Advises |
| Claude (AI) | Reads docs, proposes model, glossary, config schema and ADR drafts | None — proposes only |

## 3. Entry criteria (inputs)

- [ ] `aidlc-docs/approvals/prd-signoff.md` shows `Status: APPROVED`.
- [ ] Expense policy and current approval matrix available in Confluence.
- [ ] Confluence MCP connected (read; write to the design space only).
- [ ] Policy glossary from DIS-01 present.

## 4. Tools, MCP servers and agents

### 4.1 Tools and MCP servers

| Tool / MCP server | Used for | Access notes |
| --- | --- | --- |
| Claude Code **plan mode** | Explore and propose without editing files | Use for all modelling; exit plan mode only to write spec files |
| Confluence MCP (Atlassian remote MCP) | Read policy pages, publish the approved model and ADRs | Read-wide, write to the design space only |

### 4.2 Agents

| Agent | Type | Responsibility |
| --- | --- | --- |
| `domain-modeler` | Claude Code subagent | Builds the model, glossary and rules schema from policy docs |
| Main Claude session (plan mode) | Orchestrator | Runs the grilling loop with humans and drafts ADRs |

Subagent definition (`.claude/agents/domain-modeler.md`):

```markdown
---
name: domain-modeler
description: Builds the expense-policy domain model, ubiquitous language and rules-as-config schema from policy documents. Use in Discover / DIS-02. Writes spec files only, never code.
tools: Read, Grep, Glob, Write, Edit
---

You model expense policy for a regulated bank.
Rules:
- Every limit, tier and role must cite its source (Confluence page + section).
- Rules live in config (YAML), never hard-coded. Propose a JSON Schema for the config.
- Apply segregation of duties: a submitter can never approve their own claim; approvers
  above a threshold need a second approver.
- Write only under aidlc-docs/. Never write under src/ or infra/.
```

## 5. Skills

| Skill | Library | When to invoke | Expected output |
| --- | --- | --- | --- |
| `grill-with-docs` | MP · Matt Pocock | Against the policy docs, to find gaps, conflicts and ambiguous limits | Gap list, resolved with the Solution Owner |
| `ubiquitous-language` | MP · Matt Pocock | After grilling, to fix the shared vocabulary | Updated `policy-glossary.md` |
| ADR authoring | Claude Code (built-in) | For each significant modelling decision | `aidlc-docs/decisions/adr-NNN-*.md` |

## 6. Workflow

**Flow:** Rules as config: tiers per team/role, limits

1. **Enter plan mode** · Architect · Claude reads policy pages via Confluence MCP; no file edits yet.
2. **Grill the policy** · Claude (`grill-with-docs`) + Solution Owner · Find conflicts (e.g. two different meal limits), missing rules (e.g. weekend travel), unclear owners.
3. **Fix the language** · Claude (`ubiquitous-language`) · Update `aidlc-docs/glossary/policy-glossary.md`; the DIS-01 hook then shares it everywhere.
4. **Propose the domain model** · `domain-modeler` · Entities, relationships and state machine for a Claim (Draft → Submitted → Approved/Rejected → Paid).
5. **Design rules as config** · `domain-modeler` · Config schema with: category limits, per-role / per-team tiers, approval thresholds, SoD rules, effective dates and version.
6. **Record decisions** · Claude + Architect · One ADR per decision (context, options, decision, consequences).
7. **Review together** · Solution Owner + Architect · Walk through 5–10 real (anonymised) claims against the rules to prove they work.
8. **HUMAN GATE — spec sign-off** · Both sign `aidlc-docs/approvals/spec-signoff.md`. This unlocks code writes (see hook).
9. **Publish** · Claude via Confluence MCP · Publish model and ADRs to the design space.

## 7. Hooks

| Event | Matcher | Purpose | Behaviour |
| --- | --- | --- | --- |
| `PreToolUse` | `Write\|Edit\|MultiEdit` | No code writes before spec sign-off | If the target is under `src/` or `infra/` and `spec-signoff.md` is not `APPROVED`, exit code `2` blocks the write and tells Claude why |

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
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/require-spec-signoff.sh"
          }
        ]
      }
    ]
  }
}
```

`.claude/hooks/require-spec-signoff.sh`:

```bash
#!/usr/bin/env bash
# Blocks writes to code folders until the spec is signed off.
set -euo pipefail
FILE=$(jq -r '.tool_input.file_path // empty')
case "$FILE" in
  */src/*|*/infra/*|src/*|infra/*) ;;   # code paths: check the gate
  *) exit 0 ;;                          # docs and config: allowed
esac
SIGNOFF="$CLAUDE_PROJECT_DIR/aidlc-docs/approvals/spec-signoff.md"
if ! grep -q '^Status: APPROVED' "$SIGNOFF" 2>/dev/null; then
  echo "Blocked: spec not signed off (aidlc-docs/approvals/spec-signoff.md). Finish DIS-02 first." >&2
  exit 2
fi
```

## 8. Outputs and artifacts

| Artifact | Location in repo / tool | Owner |
| --- | --- | --- |
| Domain model (entities + Claim state machine) | `aidlc-docs/inception/domain-model.md` | Architect |
| Ubiquitous language / glossary | `aidlc-docs/glossary/policy-glossary.md` | Solution Owner |
| Rules config schema | `aidlc-docs/inception/policy-rules.schema.json` | Architect |
| Example rules config | `aidlc-docs/inception/policy-rules.example.yaml` | Solution Owner |
| Approval matrix | `aidlc-docs/inception/approval-matrix.md` | Solution Owner |
| ADRs | `aidlc-docs/decisions/adr-NNN-<slug>.md` | Architect |
| Sign-off record | `aidlc-docs/approvals/spec-signoff.md` | Solution Owner + Architect |

## 9. Exit criteria (Definition of Done)

- [ ] Every limit and tier in config traces to a policy source.
- [ ] SoD rules are explicit and tested against sample claims.
- [ ] Glossary has no duplicate or conflicting terms.
- [ ] Each significant decision has an ADR with status `Accepted`.
- [ ] Rules change by editing config only — no code change needed for a new limit.
- [ ] **HUMAN GATE:** `spec-signoff.md` shows `Status: APPROVED` with both approvers and date.

## 10. Starter prompts

```text
Plan mode. Read the expense policy pages <links> via Confluence MCP.
/grill-with-docs — list conflicts, missing rules and unclear limits. Do not propose a model yet.
```

```text
Using the domain-modeler agent, propose the domain model and a JSON Schema for policy rules
(category limits, role/team tiers, approval thresholds, SoD, effective dates). Cite sources.
```

```text
Write ADRs for the decisions we made today. One file each, status Proposed.
```

## 11. Best practices

- **Model first, code later.** Use plan mode so nothing is built on an unapproved model.
- **Rules are data.** Version the rules config and give each version an effective date for audit.
- **SoD by design.** Encode "no self-approval" and "two approvers above threshold" in the model, not just in UI.
- **Prove with examples.** Run real, anonymised claims through the rules before sign-off.
- **Small ADRs.** One decision per ADR; link ADRs from the domain model.

## 12. Anti-patterns to avoid

- Hard-coding limits or approver tiers in code.
- Two names for the same thing (e.g. "report" and "claim").
- Treating the approval matrix as a picture instead of structured data.
- Bypassing the hook by asking Claude to "just scaffold the service".

## 13. References

- Matt Pocock skills — <https://github.com/mattpocock/skills>
- Atlassian remote MCP — <https://www.atlassian.com/platform/remote-mcp-server>
- Claude Code hooks — <https://docs.claude.com/en/docs/claude-code/hooks>
- Full list: [../references.md](../references.md)

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 2, row 2 |
