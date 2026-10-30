---
id: DIS-01
title: Intent to Stories (Mob Elaboration)
phase: Discover
phase_focus: What & why
sequence: 1 of 8
actors: [Solution Owner, BA (on demand)]
status: Draft
version: 1.1.0
last_updated: 2026-10-30
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 2, row 1
previous: none
next: DIS-02
---

# DIS-01 · Intent to Stories (Mob Elaboration)

> **One line:** AI turns the business intent for the expense platform into requirements and user stories; the Solution Owner validates every AI question and proposal live, in the room.

## At a glance

| Field | Value |
| --- | --- |
| Phase | Discover · What & why |
| Actor (role) | Solution Owner · BA on demand |
| Tools & agents | Claude Projects, AWS AI-DLC workflows, Jira MCP |
| Skills | GS `/office-hours` · `aidlc-workflows` · MP `/grill-me`, `/to-spec`, `/to-tickets` |
| Workflow | Inception: intent → requirements → user stories |
| Hooks | `UserPromptSubmit`: add policy glossary |
| Entry gate | A written business intent exists and the Solution Owner is in the session |
| Exit gate (HUMAN GATE) | Solution Owner signs off the PRD and the story set in Jira |

## 1. Objective

Convert a short business intent (for example *"Employees submit expenses from a phone photo and get reimbursed within 5 working days, with policy checks built in"*) into:

1. A product requirements document (PRD) the whole team agrees on.
2. A set of INVEST user stories with acceptance criteria, pushed to Jira.
3. A list of open questions and assumptions that later activities must close.

The AI drafts; humans decide. Nothing leaves this activity without Solution Owner sign-off.

## 2. Roles and responsibilities

| Role | Responsibility in this activity | Decision rights |
| --- | --- | --- |
| Solution Owner | States the intent, answers AI questions live, prioritises stories | **Approves** PRD and stories |
| BA (on demand) | Brings finance policy detail and edge cases (per-diems, FX, split bills) | Advises |
| Architect (observer) | Flags early NFR signals (audit, PII, SoD) for DIS-03 | Advises |
| Claude (AI) | Asks clarifying questions, drafts PRD and stories, keeps the question log | None — proposes only |

## 3. Entry criteria (inputs)

- [ ] Business intent written down (one paragraph is enough).
- [ ] Current expense policy document available (PDF or Confluence page).
- [ ] Policy glossary file exists at `aidlc-docs/glossary/policy-glossary.md` (used by the hook).
- [ ] Jira project and epic created; Jira MCP connected and authorised.
- [ ] Mob Elaboration session booked with the Solution Owner (and BA if policy is complex).

## 4. Tools, MCP servers and agents

### 4.1 Tools and MCP servers

| Tool / MCP server | Used for | Access notes |
| --- | --- | --- |
| Claude Projects | Shared project knowledge (policy docs, intent) for the mob session | Upload only sanitised policy docs — no real employee data |
| AWS AI-DLC workflows (`awslabs/aidlc-workflows`) | Inception stage rules that drive Claude through intent → requirements → stories | Install per the repo README; keep version pinned |
| Jira MCP (Atlassian remote MCP) | Create epics, stories and acceptance criteria | Use a scoped account; write access to the project only |

### 4.2 Agents

| Agent | Type | Responsibility |
| --- | --- | --- |
| `requirements-analyst` | Claude Code subagent | Runs the question loop, drafts PRD and stories |
| Main Claude session | Orchestrator | Runs the AI-DLC Inception workflow and calls the subagent |

Subagent definition (`.claude/agents/requirements-analyst.md`):

```markdown
---
name: requirements-analyst
description: Turns business intent for the expense management platform into a PRD and INVEST user stories with acceptance criteria. Use in Discover / DIS-01. Asks questions before drafting.
---

You are a requirements analyst for a banking-grade expense management platform.
Rules:
- Ask clarifying questions in batches of at most 5 before you draft anything.
- Use only terms from the policy glossary. If a term is missing, flag it.
- Every story: "As a <role>, I want <capability>, so that <outcome>" + Given/When/Then criteria.
- Tag stories that touch money movement, PII or approvals with `nfr-candidate`.
- Never invent policy limits. Mark unknowns as OPEN QUESTION.
- Output to aidlc-docs/inception/. Do not write code.
```

> Leave `tools` unset so the subagent inherits the Jira MCP tools. Restrict it once your MCP tool names are fixed.

## 5. Skills

| Skill | Library | When to invoke | Expected output |
| --- | --- | --- | --- |
| `/office-hours` | GS · gstack | Start of session, to pressure-test the intent and the "why" | Sharpened problem statement and success measures |
| `aidlc-workflows` (Inception) | AWS | Main driver of the session | Requirements and stories in AI-DLC format |
| `/grill-me` | MP · Matt Pocock | After the first draft, to surface gaps and edge cases | Question list with answers recorded |
| `/to-spec` | MP · Matt Pocock | When questions are closed: turns the session into a spec (replaces the older `to-prd`) | `prd.md` |
| `/to-tickets` | MP · Matt Pocock | After the PRD: splits it into stories with their dependencies | Story list for Jira |

## 6. Workflow

**Flow:** Inception: intent → requirements → user stories

1. **Frame the intent** · Solution Owner + Claude (`/office-hours`) · Output: one-paragraph intent and 3–5 success measures (e.g. "95% of claims reimbursed in ≤ 5 days").
2. **Load context** · Engineer/facilitator · Add the policy doc and glossary to the Claude Project; confirm the `UserPromptSubmit` hook is active.
3. **Run Inception** · Claude (`aidlc-workflows`) · Claude asks clarifying questions; Solution Owner answers live. Every Q&A is saved to `aidlc-docs/inception/question-log.md`.
4. **Grill the draft** · Claude (`/grill-me`) + BA · Surface edge cases: lost receipts, foreign currency, split bills, delegate approvers, duplicate claims.
5. **Write the PRD** · Claude (`/to-spec`) · Output: `aidlc-docs/inception/prd.md`.
6. **Generate stories** · `requirements-analyst` (`/to-tickets`) · Output: `aidlc-docs/inception/user-stories.md` with acceptance criteria.
7. **Push to Jira** · Claude via Jira MCP · Stories linked to the epic, labelled `aidlc-discover`.
8. **HUMAN GATE — sign-off** · Solution Owner reviews PRD and stories, then records approval in `aidlc-docs/approvals/prd-signoff.md`.

## 7. Hooks

| Event | Matcher | Purpose | Behaviour |
| --- | --- | --- | --- |
| `UserPromptSubmit` | *(none — runs on every prompt)* | Add the expense-policy glossary to every prompt | Prints the glossary to stdout; Claude Code adds it as context. Never blocks. |

`.claude/settings.json` snippet:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/add-policy-glossary.sh"
          }
        ]
      }
    ]
  }
}
```

`.claude/hooks/add-policy-glossary.sh`:

```bash
#!/usr/bin/env bash
# Adds the expense-policy glossary to each prompt so Claude uses the same terms as finance.
set -euo pipefail
GLOSSARY="$CLAUDE_PROJECT_DIR/aidlc-docs/glossary/policy-glossary.md"
[[ -f "$GLOSSARY" ]] || exit 0   # no glossary yet: do nothing, never block
echo "## Expense policy glossary (auto-added by hook)"
cat "$GLOSSARY"
```

Keep the glossary short (under ~150 lines) — it is sent with every prompt.

## 8. Outputs and artifacts

| Artifact | Location in repo / tool | Owner |
| --- | --- | --- |
| Intent and success measures | `aidlc-docs/inception/intent.md` | Solution Owner |
| Question log (Q&A) | `aidlc-docs/inception/question-log.md` | Claude, reviewed by BA |
| PRD | `aidlc-docs/inception/prd.md` | Solution Owner |
| User stories | `aidlc-docs/inception/user-stories.md` + Jira epic | Solution Owner |
| Sign-off record | `aidlc-docs/approvals/prd-signoff.md` | Solution Owner |

## 9. Exit criteria (Definition of Done)

- [ ] Every story follows the role/capability/outcome form and has Given/When/Then criteria.
- [ ] No OPEN QUESTION is left without an owner and due date.
- [ ] Stories cover the full journey: submit → approve → reimburse → report.
- [ ] Stories tagged `nfr-candidate` are listed for DIS-03.
- [ ] Jira and `user-stories.md` match (same IDs, same count).
- [ ] **HUMAN GATE:** `prd-signoff.md` shows `Status: APPROVED`, approver name and date.

## 10. Starter prompts

```text
Using the AI-DLC Inception workflow, here is our intent: <paste>.
Ask me up to 5 clarifying questions at a time. Do not draft requirements until I say "draft".
```

```text
/grill-me on aidlc-docs/inception/prd.md — focus on finance edge cases:
foreign currency, missing receipts, split bills, delegated approval, duplicate claims.
```

```text
Create the stories in Jira under epic <KEY> with label aidlc-discover. Show me the list before creating them.
```

## 11. Best practices

- **Questions before answers.** Let Claude ask first; a fast draft built on guesses costs more later.
- **Live validation.** Run it as a mob: the Solution Owner answers in the session, not by email later.
- **One vocabulary.** The glossary hook keeps "claim", "expense line", "approver" and "cost centre" consistent.
- **Small stories.** Each story should fit in one bolt (hours to a few days).
- **Trace everything.** Keep the question log; it is the audit trail for why a requirement exists.
- **Preview before write.** Ask Claude to show Jira changes before it creates them.

## 12. Anti-patterns to avoid

- Letting AI invent policy limits or approval thresholds.
- Uploading real receipts or employee data to Claude Projects.
- Skipping the sign-off because "the stories look fine".
- Writing solution design (APIs, tables) into stories — that belongs to DIS-04.

## 13. References

- AWS AI-DLC method — <https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle>
- AI-DLC workflows — <https://github.com/awslabs/aidlc-workflows>
- Matt Pocock skills — <https://github.com/mattpocock/skills>
- gstack — <https://github.com/garrytan/gstack>
- Atlassian remote MCP — <https://www.atlassian.com/platform/remote-mcp-server>
- Claude Code hooks — <https://docs.claude.com/en/docs/claude-code/hooks>
- Full list: [../references.md](../references.md)

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 2, row 1 |
| 1.1.0 | 2026-10-30 | AI-DLC team | Skill names updated to installed versions (MP 1.3.2, AO 0.6.14) |
