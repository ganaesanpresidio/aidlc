---
id: DEP-01
title: Deploy with IaC and Release Gates
phase: Deploy & Monitor
phase_focus: Run & learn
sequence: 7 of 8
actors: [Engineer, Architect]
status: Draft
version: 1.1.0
last_updated: 2026-10-30
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 2, row 7
previous: BLD-02
next: DEP-02
---

# DEP-01 · Deploy with IaC and Release Gates

> **One line:** Claude drafts the infrastructure as code and the pipeline; releases go blue/green through human-gated stages, and only a human can approve a production deploy.

## At a glance

| Field | Value |
| --- | --- |
| Phase | Deploy & Monitor · Run & learn |
| Actor (role) | Engineer + Architect |
| Tools & agents | AWS CDK, AWS CodePipeline, GitHub Actions |
| Skills | GS `/ship`, `/land-and-deploy`, `/canary` · AO `/agent-skills:ship` |
| Workflow | Operations: IaC, deploy, observability set-up |
| Hooks | `PreToolUse`: prod deploy needs human OK |
| Entry gate | BLD-02 passed: PR approved, UAT pack signed |
| Exit gate (HUMAN GATE) | Human approves the production release; canary healthy; NFRs met in prod |

## 1. Objective

1. **IaC** for every unit in AWS CDK: compute, API, Step Functions, Textract permissions, data stores, encryption, IAM least privilege.
2. **Pipeline** (CodePipeline and/or GitHub Actions): build → test → scan → deploy dev → deploy staging → **manual approval** → blue/green prod.
3. **Observability** set up with the deploy: logs, metrics, traces, alarms for each NFR.
4. **Safe release:** blue/green with canary traffic shift and automatic rollback on alarm.

## 2. Roles and responsibilities

| Role | Responsibility in this activity | Decision rights |
| --- | --- | --- |
| Engineer | Drives Claude to write CDK and pipeline; runs non-prod deploys | Deploys non-prod |
| Architect | Reviews IaC for security and NFRs; owns release gates and hooks | **Approves** prod release |
| Solution Owner | Confirms business readiness (UAT signed, comms ready) | **Approves** go-live |
| Claude (AI) | Drafts CDK, pipeline, alarms and runbook; watches canary telemetry | None — cannot approve prod |

## 3. Entry criteria (inputs)

- [ ] BLD-02 exit criteria met for the units in this release.
- [ ] Separate AWS accounts for dev, staging and prod (AWS Organizations).
- [ ] Pipeline roles use OIDC / short-lived credentials — no long-lived keys in the repo.
- [ ] NFR matrix from DIS-03 (drives alarms and SLOs).
- [ ] Rollback plan and on-call owner named.

## 4. Tools, MCP servers and agents

### 4.1 Tools and MCP servers

| Tool / MCP server | Used for | Access notes |
| --- | --- | --- |
| AWS CDK | IaC for all units | `cdk diff` reviewed on every PR; `cdk-nag` for security rules |
| AWS CodePipeline | Release pipeline with manual approval action before prod | Approval action limited to Architect / Solution Owner IAM group |
| GitHub Actions | PR checks (build, test, scan, `cdk synth`/`diff`) | OIDC to AWS; no stored secrets |
| AWS CDK MCP (`awslabs/mcp`) *(optional)* | CDK guidance and construct checks while drafting | Read / advisory |

### 4.2 Agents

| Agent | Type | Responsibility |
| --- | --- | --- |
| `release-engineer` | Claude Code subagent | Drafts CDK stacks, pipeline, alarms, runbook |
| Main Claude session | Orchestrator | Runs `/ship`, `/land-and-deploy`, `/canary` and reports status |

Subagent definition (`.claude/agents/release-engineer.md`):

```markdown
---
name: release-engineer
description: Drafts AWS CDK infrastructure, CI/CD pipelines, alarms and runbooks for the expense platform. Use in Deploy & Monitor / DEP-01. Never deploys to production.
tools: Read, Grep, Glob, Write, Edit, Bash
---

Rules:
- All infra in CDK under infra/. No console changes.
- Least-privilege IAM; encryption at rest and in transit; no public buckets.
- Every NFR in nfr-matrix.md has a CloudWatch alarm or SLO.
- Prod uses blue/green with canary and automatic rollback on alarm.
- You may deploy to dev and staging. You must NEVER deploy to prod or approve a pipeline stage.
- Always show `cdk diff` before any deploy.
```

## 5. Skills

| Skill | Library | When to invoke | Expected output |
| --- | --- | --- | --- |
| `/agent-skills:ship` | AO · Addy Osmani | Prepare the release: checklist, notes, version | Release checklist + notes |
| `/ship` | GS · gstack | Merge-ready check and PR landing | Shipped PR |
| `/land-and-deploy` | GS · gstack | Land the PR and drive the non-prod deploy | Deployed to dev/staging |
| `/canary` | GS · gstack | During prod traffic shift, watch health signals | Go / rollback recommendation |

## 6. Workflow

**Flow:** Operations: IaC, deploy, observability set-up

1. **Draft IaC** · `release-engineer` · CDK stacks per unit; run `cdk synth` and `cdk-nag`.
2. **Review IaC** · Architect · Review `cdk diff`, IAM and encryption. Fix findings.
3. **Observability** · `release-engineer` · Dashboards, alarms per NFR (p95 latency, error rate, OCR failure rate, approval SLA, payout failures).
4. **Release prep** · Claude (`/agent-skills:ship`) · Version, release notes, checklist, rollback steps.
5. **Non-prod deploy** · Claude (`/land-and-deploy`) · Dev → staging; smoke + Playwright suite on staging.
6. **HUMAN GATE — prod approval** · Architect + Solution Owner approve in CodePipeline's manual approval action. Claude cannot approve (see hook).
7. **Blue/green + canary** · Pipeline · Shift e.g. 10% → 50% → 100% traffic; Claude (`/canary`) watches telemetry and recommends go or rollback.
8. **Confirm** · Engineer · NFRs met in prod; record release in `aidlc-docs/operations/releases.md`.

## 7. Hooks

| Event | Matcher | Purpose | Behaviour |
| --- | --- | --- | --- |
| `PreToolUse` | `Bash` | Prod deploy needs human OK | Prod deploy commands → `permissionDecision: "ask"` (a human must confirm in Claude Code). Pipeline approval commands → `"deny"` (AI must never approve its own release) |

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
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-prod-deploy.sh"
          }
        ]
      }
    ]
  }
}
```

`.claude/hooks/guard-prod-deploy.sh`:

```bash
#!/usr/bin/env bash
# Prod deploys need a human OK; pipeline approvals are never done by Claude.
set -euo pipefail
CMD=$(jq -r '.tool_input.command // empty')

decide() {  # $1 = ask|deny, $2 = reason
  jq -n --arg d "$1" --arg r "$2" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:$d,permissionDecisionReason:$r}}'
  exit 0
}

if grep -Eq 'put-approval-result' <<<"$CMD"; then
  decide deny "Pipeline approvals are human-only (DEP-01). Ask the Architect or Solution Owner."
fi
if grep -Eiq '(cdk[[:space:]]+deploy|start-pipeline-execution|gh[[:space:]]+workflow[[:space:]]+run).*(prod|production)' <<<"$CMD"; then
  decide ask "Production deploy: human approval required (DEP-01). Check release notes and cdk diff first."
fi
exit 0
```

> Defence in depth: the hook stops Claude; the CodePipeline manual approval and IAM (Claude's role has no prod deploy rights) stop everyone else.

## 8. Outputs and artifacts

| Artifact | Location in repo / tool | Owner |
| --- | --- | --- |
| CDK stacks | `infra/` | Engineer |
| Pipeline definition | `infra/pipeline/`, `.github/workflows/` | Engineer |
| Alarms and dashboards (as code) | `infra/observability/` | Engineer |
| Release notes + checklist | `aidlc-docs/operations/releases.md` | Engineer |
| Runbook + rollback steps | `aidlc-docs/operations/runbook.md` | Architect |
| Prod approval record | CodePipeline approval history | Architect + Solution Owner |

## 9. Exit criteria (Definition of Done)

- [ ] All infra in CDK; `cdk-nag` clean or exceptions approved.
- [ ] No long-lived credentials; pipeline uses OIDC / roles.
- [ ] Every NFR has an alarm or SLO in prod.
- [ ] Blue/green with canary and automatic rollback tested in staging.
- [ ] Runbook and rollback steps written and tried once.
- [ ] **HUMAN GATE:** Prod approval recorded in CodePipeline by an authorised human; canary completed healthy.

## 10. Starter prompts

```text
Use release-engineer to draft CDK for units submit and approve, following the LLDs and nfr-matrix.md.
Run cdk synth and cdk-nag and show me cdk diff. Do not deploy.
```

```text
Create CloudWatch alarms for every NFR in aidlc-docs/inception/nfr-matrix.md as code,
plus one dashboard per unit.
```

```text
/canary — prod traffic is at 10%. Compare error rate, p95 latency and OCR failure rate
between blue and green for 15 minutes and recommend go or rollback with evidence.
```

## 11. Best practices

- **Everything as code.** No console changes; drift is a defect.
- **Separate accounts.** Dev, staging and prod in separate AWS accounts.
- **Humans release prod.** Enforce it three ways: hook, pipeline approval, IAM.
- **Small, frequent releases.** One or a few units per release make rollback easy.
- **Observability ships with the code.** No alarm, no release.
- **Show the diff.** `cdk diff` is part of every review and every release note.

## 12. Anti-patterns to avoid

- Giving Claude's credentials prod deploy rights.
- Approving prod without reading `cdk diff` and release notes.
- Big-bang releases of all six units at once.
- Adding alarms "after go-live".

## 13. References

- AWS CDK — <https://aws.amazon.com/cdk>
- AWS CodePipeline — <https://aws.amazon.com/codepipeline>
- GitHub Actions — <https://github.com/features/actions>
- AWS MCP servers (CDK) — <https://github.com/awslabs/mcp>
- gstack — <https://github.com/garrytan/gstack>
- Addy Osmani agent-skills — <https://github.com/addyosmani/agent-skills>
- Full list: [../references.md](../references.md)

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 2, row 7 |
| 1.1.0 | 2026-10-30 | AI-DLC team | Skill names updated to installed versions (MP 1.3.2, AO 0.6.14) |
