---
id: BLD-02
title: Verify, Review and Secure
phase: Build
phase_focus: How
sequence: 6 of 8
actors: [Engineer, Test (on demand)]
status: Draft
version: 1.0.0
last_updated: 2026-10-29
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 2, row 6
previous: BLD-01
next: DEP-01
---

# BLD-02 · Verify, Review and Secure

> **One line:** Every bolt gets a two-axis review — does it match the spec, and does it meet our standards — plus QA, security checks and UAT packs before it can be shipped.

## At a glance

| Field | Value |
| --- | --- |
| Phase | Build · How |
| Actor (role) | Engineer + Test (on demand) |
| Tools & agents | Claude Code, Playwright, SAST scanners |
| Skills | GS `/review`, `/qa`, `/cso` · AO `code-review-and-quality` |
| Workflow | Two-axis review: spec match + standards; UAT packs |
| Hooks | `PreToolUse`: block commit on failing tests or PII |
| Entry gate | Bolt accepted in BLD-01; PR open |
| Exit gate (HUMAN GATE) | Engineer approves the PR; Test signs the UAT pack for the unit |

## 1. Objective

1. **Axis 1 — spec match:** the change does what the LLD and acceptance criteria say, nothing more.
2. **Axis 2 — standards:** code quality, security, PII handling, performance, accessibility.
3. **QA:** end-to-end browser tests (Playwright) for the claim journey.
4. **Security:** SAST, dependency and secrets scans; a security review of money and approval paths.
5. **UAT and compliance packs:** evidence the Solution Owner and audit can rely on.

## 2. Roles and responsibilities

| Role | Responsibility in this activity | Decision rights |
| --- | --- | --- |
| Engineer | Runs reviews, fixes findings, owns the PR | **Approves** PR merge |
| Test (on demand) | Builds UAT and compliance packs; runs exploratory tests | **Signs** UAT pack |
| Architect | Reviews security and NFR findings above medium severity | Can block release |
| Solution Owner | Accepts UAT results for business flows | Accepts UAT |
| Claude (AI) | Runs review skills, writes Playwright tests, triages scanner output | None — proposes only |

## 3. Entry criteria (inputs)

- [ ] Bolt logged in `aidlc-docs/construction/bolt-log.md`; PR open.
- [ ] LLD and acceptance criteria for the unit.
- [ ] Playwright set up with a test environment and synthetic users (submitter, approver L1/L2, finance).
- [ ] SAST, dependency and secret scanners installed (e.g. Semgrep, Gitleaks — pick per bank standard).

## 4. Tools, MCP servers and agents

### 4.1 Tools and MCP servers

| Tool / MCP server | Used for | Access notes |
| --- | --- | --- |
| Claude Code | Run reviews and fix findings | Works on the PR branch only |
| Playwright | E2E tests: submit → OCR → approve → payout status | Test env, synthetic data |
| SAST scanners | Static security analysis, secrets, dependency CVEs | Also run in CI; same rules |

### 4.2 Agents

| Agent | Type | Responsibility |
| --- | --- | --- |
| `spec-reviewer` | Claude Code subagent | Axis 1: compares diff to LLD and acceptance criteria |
| `standards-reviewer` | Claude Code subagent | Axis 2: quality, security, PII, performance |
| `qa-engineer` | Claude Code subagent | Writes and runs Playwright tests; builds UAT pack draft |

Subagent definitions (`.claude/agents/spec-reviewer.md`, `.claude/agents/standards-reviewer.md`):

```markdown
---
name: spec-reviewer
description: Reviews a change only for match with the approved LLD and acceptance criteria. Use in Build / BLD-02. Read-only.
tools: Read, Grep, Glob, Bash
---

Report: (1) criteria met, with test name as evidence; (2) criteria missing;
(3) behaviour added that is NOT in the spec. Do not comment on style. Do not edit files.
```

```markdown
---
name: standards-reviewer
description: Reviews a change for code quality, security, PII handling, performance and accessibility against team standards. Use in Build / BLD-02. Read-only.
tools: Read, Grep, Glob, Bash
---

Check: input validation, authZ on every approval action, SoD enforcement, PII in logs,
secrets, idempotency on payout, error handling, N+1 queries, accessibility on UI.
Rate each finding Critical / High / Medium / Low with file:line and a proposed fix.
Do not edit files.
```

## 5. Skills

| Skill | Library | When to invoke | Expected output |
| --- | --- | --- | --- |
| `/review` | GS · gstack | On every PR, first pass | Review findings |
| `code-review-and-quality` | AO · Addy Osmani | Standards axis, deeper pass | Graded findings + fixes |
| `/qa` | GS · gstack | After review fixes, to test the running app | QA report, Playwright tests |
| `/cso` | GS · gstack | Security review of money, approval and PII paths | Security findings + threat notes |

## 6. Workflow

**Flow:** Two-axis review: spec match + standards; UAT packs

1. **Axis 1 — spec match** · `spec-reviewer` · Diff vs LLD and acceptance criteria.
2. **Axis 2 — standards** · Claude (`/review`, `code-review-and-quality`) + `standards-reviewer`.
3. **Security** · Claude (`/cso`) + SAST scanners · Focus: authZ, SoD, payout idempotency, PII, secrets.
4. **Fix** · Engineer + Claude · Fix Critical/High findings; log accepted risks with a reason.
5. **QA** · `qa-engineer` (`/qa`) + Playwright · E2E journeys incl. rejection, delegation, low-confidence OCR, policy breach.
6. **UAT pack** · Test (on demand) + Claude · Test cases, results, screenshots, traceability (story → test → result).
7. **Commit** · Engineer · The `PreToolUse` hook blocks any `git commit` with failing tests or PII in the staged diff.
8. **HUMAN GATE — approve** · Engineer approves PR; Test signs the UAT pack; Architect clears any High security finding.

## 7. Hooks

| Event | Matcher | Purpose | Behaviour |
| --- | --- | --- | --- |
| `PreToolUse` | `Bash` | Block commit on failing tests or PII | When the command contains `git commit`: runs `make test`, then scans the staged diff for PII patterns. On failure, exit `2` blocks the commit and tells Claude why |

`.claude/settings.json` snippet:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-commit.sh",
            "timeout": 600
          }
        ]
      }
    ]
  }
}
```

`.claude/hooks/guard-commit.sh`:

```bash
#!/usr/bin/env bash
# Blocks git commit when tests fail or the staged diff contains likely PII.
set -uo pipefail
CMD=$(jq -r '.tool_input.command // empty')
grep -Eq '(^|[;&|[:space:]])git[[:space:]]+commit' <<<"$CMD" || exit 0
cd "$CLAUDE_PROJECT_DIR"

if ! OUT=$(make -s test 2>&1); then
  echo "Blocked commit: tests are failing." >&2
  echo "$OUT" | tail -n 60 >&2
  exit 2
fi

# Simple PII patterns: email, 13-19 digit card numbers, IBAN. Extend per bank standard.
PII='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|\b([0-9][ -]?){13,19}\b|\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b'
if git diff --cached -U0 | grep -E '^\+[^+]' | grep -Eq "$PII"; then
  echo "Blocked commit: staged changes look like they contain PII (email, card or IBAN). Use synthetic data." >&2
  exit 2
fi
```

> This hook only guards commits made **through Claude**. Run the same checks in a git `pre-commit` hook and in CI so human commits are covered too. Allow-list synthetic test emails (e.g. `@example.com`) if needed.

## 8. Outputs and artifacts

| Artifact | Location in repo / tool | Owner |
| --- | --- | --- |
| Spec-match report | `aidlc-docs/construction/<unit>/review-spec.md` | Engineer |
| Standards + security report | `aidlc-docs/construction/<unit>/review-standards.md` | Engineer |
| Playwright tests | `tests/e2e/` | Test |
| QA report | `aidlc-docs/construction/<unit>/qa-report.md` | Test |
| UAT / compliance pack | `aidlc-docs/construction/<unit>/uat-pack.md` | Test |
| Accepted-risk log | `aidlc-docs/construction/risk-log.md` | Architect |

## 9. Exit criteria (Definition of Done)

- [ ] Axis 1: all acceptance criteria met with test evidence; no unspecified behaviour.
- [ ] Axis 2: no open Critical/High findings; Medium/Low logged.
- [ ] SAST, secrets and dependency scans clean or risk-accepted by the Architect.
- [ ] Playwright E2E green for the unit's journeys.
- [ ] UAT pack complete with story → test → result traceability.
- [ ] **HUMAN GATE:** PR approved by Engineer; UAT pack signed by Test (and Solution Owner for business flows).

## 10. Starter prompts

```text
Use spec-reviewer on this PR against aidlc-docs/design/approve/lld.md.
List: met (with test name), missing, and extra behaviour not in the spec.
```

```text
/cso on src/approve and src/payout. Focus: authorisation on every approve action, SoD,
payout idempotency, PII in logs. Rate findings and propose fixes.
```

```text
/qa — write Playwright tests for: submit with receipt, low-confidence OCR to manual review,
L1 approve, L2 approve above threshold, reject with reason, self-approval attempt (must fail).
```

## 11. Best practices

- **Two separate axes.** Spec match and standards are different questions — review them separately.
- **Reviewers are read-only.** Review agents never edit; fixes are a separate, visible step.
- **Test the unhappy paths.** Self-approval, duplicate claims and payout retries matter most in finance.
- **Same rules everywhere.** Local hook, git pre-commit and CI run the same scanners and rules.
- **Evidence over opinion.** UAT packs link every story to a test and a result for audit.

## 12. Anti-patterns to avoid

- One "LGTM" review that mixes spec and style.
- Skipping `/cso` on "small" changes to payout or approval code.
- Real customer data in Playwright fixtures or screenshots.
- Bypassing the commit gate with `--no-verify` or by committing outside Claude.

## 13. References

- gstack — <https://github.com/garrytan/gstack>
- Addy Osmani agent-skills — <https://github.com/addyosmani/agent-skills>
- Playwright — <https://playwright.dev>
- Claude Code hooks — <https://docs.claude.com/en/docs/claude-code/hooks>
- Full list: [../references.md](../references.md)

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 2, row 6 |
