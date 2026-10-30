---
id: BLD-01
title: Build Each Unit in Bolts
phase: Build
phase_focus: How
sequence: 5 of 8
actors: [Engineer, FED (on demand)]
status: Draft
version: 1.1.0
last_updated: 2026-10-30
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 2, row 5
previous: DIS-04
next: BLD-02
---

# BLD-01 · Build Each Unit in Bolts

> **One line:** In Mob Construction, Claude proposes the domain code and tests for one unit at a time, in bolts of hours or days; the team decides the design trade-offs each bolt and reviews every AI change.

## At a glance

| Field | Value |
| --- | --- |
| Phase | Build · How |
| Actor (role) | Engineer · FED on demand |
| Tools & agents | Claude Code subagents, Amazon Textract, AWS Step Functions |
| Skills | AO `/agent-skills:build` · MP `tdd` · AO `frontend-ui-engineering` |
| Workflow | Mob Construction: code + tests to approved LLD |
| Hooks | `PostToolUse`: lint, type-check, unit tests |
| Entry gate | `lld-<unit>.md` approved (DIS-04) |
| Exit gate (HUMAN GATE) | Engineer accepts the bolt: code + tests match the LLD, all checks green |

## 1. Objective

For each approved unit, deliver working, tested code in small bolts:

- **Backend units** (`policy`, `approve`, `payout`): domain code + unit and contract tests, written test-first.
- **OCR unit** (`ocr`): Amazon Textract `AnalyzeExpense` integration with confidence thresholds and a manual-review path.
- **Approval flow**: AWS Step Functions state machine matching the Claim state machine from DIS-02.
- **Frontend** (`submit`, approver UX, `bi` views): built with the FED on demand.

A **bolt** is the smallest shippable slice of a unit (one story or less). It replaces the sprint.

## 2. Roles and responsibilities

| Role | Responsibility in this activity | Decision rights |
| --- | --- | --- |
| Engineer | Drives agents each bolt; reviews every AI change; merges | **Accepts** each bolt |
| FED (on demand) | Leads UI bolts (claim form, approver inbox, dashboards) | Accepts UI bolts |
| Architect | Joins when a bolt needs a design trade-off or LLD change | **Approves** any LLD change |
| Test (on demand) | Prepares test data and UAT cases in parallel | Advises |
| Claude (AI) | Writes failing test, then code, then refactors; one subagent per unit | None — proposes only |

## 3. Entry criteria (inputs)

- [ ] `aidlc-docs/approvals/lld-<unit>.md` shows `Status: APPROVED`.
- [ ] Bolt plan in `aidlc-docs/design/<unit>/plan.md`.
- [ ] Repo has `make lint`, `make typecheck`, `make test-unit` targets (used by the hook).
- [ ] Dev AWS account with Textract and Step Functions access; no production data.
- [ ] Synthetic receipt set for OCR tests (no real employee receipts).

## 4. Tools, MCP servers and agents

### 4.1 Tools and MCP servers

| Tool / MCP server | Used for | Access notes |
| --- | --- | --- |
| Claude Code subagents | One builder per unit, running in parallel | Each limited to its own `src/<unit>/` |
| Amazon Textract | Receipt OCR (`AnalyzeExpense`) for the `ocr` unit | Dev account; synthetic receipts only |
| AWS Step Functions | Approval workflow orchestration | State machine defined as code in `infra/` |

### 4.2 Agents

| Agent | Type | Responsibility |
| --- | --- | --- |
| `unit-builder-<unit>` | Claude Code subagent (one per unit) | TDD build of one unit to its LLD |
| `ui-builder` | Claude Code subagent | Frontend bolts with the FED |
| Main Claude session | Orchestrator | Assigns bolts, merges results, keeps `aidlc-docs/construction/bolt-log.md` |

Subagent definition (`.claude/agents/unit-builder.md` — copy per unit and set the path):

```markdown
---
name: unit-builder
description: Builds one unit of the expense platform test-first, strictly to its approved LLD. Use in Build / BLD-01, one bolt at a time.
tools: Read, Grep, Glob, Write, Edit, Bash
---

Rules:
- Read aidlc-docs/design/<unit>/lld.md and plan.md before every bolt.
- TDD: write a failing test, make it pass, refactor. Show the failing test first.
- Write only under src/<unit>/ and tests/<unit>/. Never edit another unit.
- If the LLD is wrong or unclear, STOP and ask. Do not change the design yourself.
- No real PII, card or bank numbers in code, tests or fixtures. Use synthetic data.
- End each bolt with: what changed, tests added, open questions.
```

## 5. Skills

| Skill | Library | When to invoke | Expected output |
| --- | --- | --- | --- |
| `/agent-skills:build` | AO · Addy Osmani | Start of each bolt: implement the next plan task | Code change for one task |
| `tdd` | MP · Matt Pocock | Inside every bolt: red → green → refactor | Failing test, then passing code |
| `frontend-ui-engineering` | AO · Addy Osmani | UI bolts with the FED | Accessible, tested UI components |

## 6. Workflow

**Flow:** Mob Construction: code + tests to approved LLD

1. **Pick the bolt** · Engineer · Next task from `plan.md`; confirm scope fits hours to a few days.
2. **Mob kick-off (10 min)** · Engineer (+ FED/Architect if needed) · Decide trade-offs for this bolt (e.g. sync vs async OCR call, retry policy).
3. **Red** · `unit-builder` (`tdd`) · Write failing tests from the LLD's acceptance criteria and contracts.
4. **Green** · `unit-builder` (`/agent-skills:build`) · Minimum code to pass. The `PostToolUse` hook runs lint, type-check and unit tests after each edit and feeds failures back to Claude.
5. **Refactor** · `unit-builder` · Clean up with tests green.
6. **Integrate AWS services** · `unit-builder` · Textract and Step Functions behind interfaces; unit tests use fakes, integration tests hit the dev account.
7. **Review the diff** · Engineer · Read every AI change. Reject anything outside the LLD.
8. **HUMAN GATE — accept the bolt** · Engineer records the bolt in `aidlc-docs/construction/bolt-log.md` and opens a PR into BLD-02.

## 7. Hooks

| Event | Matcher | Purpose | Behaviour |
| --- | --- | --- | --- |
| `PostToolUse` | `Write\|Edit\|MultiEdit` | Fast feedback: lint, type-check, unit tests after every code edit | For files under `src/<unit>/`, runs `make lint typecheck test-unit UNIT=<unit>`. On failure, exit `2` sends the error output back to Claude to fix |

`.claude/settings.json` snippet:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-edit-checks.sh",
            "timeout": 300
          }
        ]
      }
    ]
  }
}
```

`.claude/hooks/post-edit-checks.sh`:

```bash
#!/usr/bin/env bash
# Runs lint, type-check and unit tests for the unit that was just edited.
set -uo pipefail
FILE=$(jq -r '.tool_input.file_path // empty')
REL="${FILE#"$CLAUDE_PROJECT_DIR"/}"
case "$REL" in
  src/*/*) UNIT=$(cut -d/ -f2 <<<"$REL") ;;
  *) exit 0 ;;
esac
cd "$CLAUDE_PROJECT_DIR"
if ! OUT=$(make -s lint typecheck test-unit UNIT="$UNIT" 2>&1); then
  echo "Checks failed for unit '$UNIT' after editing $REL:" >&2
  echo "$OUT" | tail -n 80 >&2
  exit 2   # PostToolUse: the edit already happened; stderr goes to Claude to fix it
fi
```

> `PostToolUse` cannot undo an edit. It gives Claude instant feedback. The hard stop on broken code is the commit gate in BLD-02.

## 8. Outputs and artifacts

| Artifact | Location in repo / tool | Owner |
| --- | --- | --- |
| Unit source code | `src/<unit>/` | Engineer |
| Unit and contract tests | `tests/<unit>/` | Engineer |
| Step Functions definition | `infra/<unit>/` | Engineer |
| Synthetic test data / receipts | `tests/fixtures/` | Test |
| Bolt log (what, tests, decisions, open questions) | `aidlc-docs/construction/bolt-log.md` | Engineer |
| LLD change requests (if any) | `aidlc-docs/design/<unit>/changes.md` | Architect |

## 9. Exit criteria (Definition of Done)

- [ ] Code matches the approved LLD and contracts; no unapproved design change.
- [ ] Tests written first; unit test coverage meets the team threshold (e.g. ≥ 80% on domain code).
- [ ] Lint, type-check and unit tests green (hook output clean).
- [ ] OCR path handles low-confidence results with manual review.
- [ ] No real PII in code, tests or fixtures.
- [ ] **HUMAN GATE:** Engineer has reviewed the full diff and logged the bolt.

## 10. Starter prompts

```text
Use the unit-builder agent for unit "policy". Bolt: <task from plan.md>.
Follow tdd: show me the failing tests first, then wait for my OK before writing code.
```

```text
/agent-skills:build the next task in aidlc-docs/design/ocr/plan.md. Wrap Textract AnalyzeExpense behind an
interface; unit tests use a fake; send results under the confidence threshold to manual review.
```

```text
With the FED: use frontend-ui-engineering to build the approver inbox from the LLD.
Keyboard-accessible, with loading, empty and error states.
```

## 11. Best practices

- **Small bolts.** If a bolt runs past a few days, split it.
- **Tests first, always.** Tests come from the LLD's acceptance criteria, not from the code.
- **One subagent per unit.** Parallel work without merge pain, because units own their folders.
- **Humans review every diff.** AI proposes, the Engineer owns the merge.
- **Design changes go back to the Architect.** Record them; don't let them slip in silently.
- **Fakes for AWS in unit tests.** Real Textract / Step Functions only in integration tests.

## 12. Anti-patterns to avoid

- Accepting large AI diffs without reading them.
- Writing tests after the code to "hit coverage".
- Using real receipts or employee data as fixtures.
- Disabling the hook because it is "slow" — make the unit tests faster instead.

## 13. References

- Claude Code subagents — <https://docs.claude.com/en/docs/claude-code/sub-agents>
- Claude Code hooks — <https://docs.claude.com/en/docs/claude-code/hooks>
- Addy Osmani agent-skills — <https://github.com/addyosmani/agent-skills>
- Matt Pocock skills — <https://github.com/mattpocock/skills>
- Amazon Textract — <https://aws.amazon.com/textract>
- AWS Step Functions — <https://aws.amazon.com/step-functions>
- Full list: [../references.md](../references.md)

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 2, row 5 |
| 1.1.0 | 2026-10-30 | AI-DLC team | Skill names updated to installed versions (MP 1.3.2, AO 0.6.14) |
