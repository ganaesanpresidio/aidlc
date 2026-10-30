---
id: DEP-02
title: Operate, Spend Analytics and Feedback Loop
phase: Deploy & Monitor
phase_focus: Run & learn
sequence: 8 of 8
actors: [Solution Owner, Engineer]
status: Draft
version: 1.2.0
last_updated: 2026-10-30
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 2, row 8
previous: DEP-01
next: DIS-01 (next Inception cycle)
---

# DEP-02 · Operate, Spend Analytics and Feedback Loop

> **One line:** Run the platform, track reimbursements and spend, investigate incidents with AI help — and turn production and finance signals into the next Inception intent.

## At a glance

| Field | Value |
| --- | --- |
| Phase | Deploy & Monitor · Run & learn |
| Actor (role) | Solution Owner + Engineer |
| Tools & agents | Amazon CloudWatch, Amazon QuickSight, Claude analytics agent |
| Skills | GS `/investigate`, `/retro` · MP `diagnosing-bugs` |
| Workflow | Prod & finance signals → next Inception intent |
| Hooks | `Notification`: SLA breach or policy drift |
| Entry gate | DEP-01 release live and healthy |
| Exit gate (HUMAN GATE) | Solution Owner accepts the retro and approves the next intent for DIS-01 |

## 1. Objective

1. **Operate:** keep NFRs green; detect, investigate and resolve incidents fast.
2. **Reimbursement tracking:** every claim's status and time-to-pay visible to employees and finance.
3. **Spend dashboard:** spend by team, category, merchant, policy breaches (QuickSight).
4. **Policy drift:** spot when real behaviour drifts from policy (e.g. rising out-of-policy claims in one team, limits that no longer fit).
5. **Feedback loop:** turn signals into a new, written intent that starts the next DIS-01 cycle.

## 2. Roles and responsibilities

| Role | Responsibility in this activity | Decision rights |
| --- | --- | --- |
| Solution Owner | Reads finance signals; decides policy changes and next intent | **Approves** next intent |
| Engineer | On-call; runs investigations with Claude; fixes defects | Owns incident fix |
| Architect | Approves fixes that change design or NFRs | Approves design changes |
| Claude (AI) | Analytics agent: reads telemetry and spend data, drafts findings, retros and intents | None — proposes only; humans own incident decisions |

## 3. Entry criteria (inputs)

- [ ] Release live; alarms and dashboards from DEP-01 active.
- [ ] QuickSight dataset fed by the `bi` unit (no raw PII; aggregated or tokenised).
- [ ] Alert route defined: CloudWatch alarm → SNS → on-call channel.
- [ ] Read-only access for Claude to CloudWatch logs/metrics and the BI dataset.

## 4. Tools, MCP servers and agents

### 4.1 Tools and MCP servers

| Tool / MCP server | Used for | Access notes |
| --- | --- | --- |
| Amazon CloudWatch | Logs, metrics, alarms, SLOs | Claude read-only |
| Amazon QuickSight | Spend dashboard and reimbursement tracking | Row-level security by team / cost centre |
| Claude analytics agent | Scheduled analysis of ops + spend signals; drift detection | Read-only; outputs to `aidlc-docs/operations/` |

### 4.2 Agents

| Agent | Type | Responsibility |
| --- | --- | --- |
| `spend-analytics` | Claude Code subagent | Weekly spend and policy-drift analysis; proposes policy or product changes |
| `incident-investigator` | Claude Code subagent | Reads logs/metrics/traces to find root cause; drafts postmortem |

Subagent definitions (`.claude/agents/spend-analytics.md`, `.claude/agents/incident-investigator.md`):

```markdown
---
name: spend-analytics
description: Analyses reimbursement times, spend and policy breaches to find policy drift and improvement ideas for the expense platform. Use in Deploy & Monitor / DEP-02. Read-only on data.
---

Rules:
- Use aggregated data only. Never output individual employee names or amounts.
- Compare actuals with the current rules config version; flag drift with numbers and trend.
- Every finding: signal, evidence (query/metric), impact, suggested action, owner.
- Write findings to aidlc-docs/operations/insights/YYYY-MM-DD.md.
```

```markdown
---
name: incident-investigator
description: Investigates production incidents on the expense platform from CloudWatch logs, metrics and traces, and drafts a blameless postmortem. Use in DEP-02. Read-only.
tools: Read, Grep, Glob, Bash
---

Rules:
- Start from the alarm and timeline. Form hypotheses, test each against evidence.
- Never change production. Propose fixes; humans apply them.
- Redact PII from any log excerpt you quote.
```

## 5. Skills

| Skill | Library | When to invoke | Expected output |
| --- | --- | --- | --- |
| `/investigate` | GS · gstack | On an alarm or incident | Root-cause analysis with evidence |
| `diagnosing-bugs` | MP · Matt Pocock | For hard bugs found in prod: reproduce, isolate, fix (replaces the older `diagnose`) | Fix with a regression test |
| `/retro` | GS · gstack | End of each release / cycle | Retro: what worked, what to change |

## 6. Workflow

**Flow:** Prod & finance signals → next Inception intent

1. **Monitor** · CloudWatch + QuickSight · Ops signals (latency, errors, OCR failures, approval SLA) and finance signals (time-to-pay, spend, breaches).
2. **Alert** · CloudWatch alarm → SNS → on-call. Claude Code's `Notification` hook forwards Claude's own alerts to the same channel.
3. **Investigate** · Engineer + `incident-investigator` (`/investigate`) · Root cause with evidence.
4. **Fix** · Engineer + Claude (`diagnosing-bugs`) · Fix with regression test; goes back through BLD-01 → BLD-02 → DEP-01.
5. **Analyse spend** · `spend-analytics` (weekly) · Reimbursement times, breaches by team/category, policy drift.
6. **Retro** · Team + Claude (`/retro`) · Per release: delivery, quality, AI usage, gate effectiveness.
7. **Draft next intent** · Claude · From incidents, insights and retro, draft `aidlc-docs/operations/next-intent.md`.
8. **HUMAN GATE — next intent** · Solution Owner approves the next intent; it becomes the input to DIS-01.

## 7. Hooks

| Event | Matcher | Purpose | Behaviour |
| --- | --- | --- | --- |
| `Notification` | *(none)* | Surface SLA breach or policy drift alerts raised during Claude sessions | Forwards the notification text to the team alert channel (webhook from env var). Never blocks |

> Claude Code's `Notification` event fires when **Claude Code** sends a notification (for example, it needs input or permission, or a long analysis finished). It does not watch AWS. Real SLA breaches come from **CloudWatch alarms → SNS**. The hook makes sure findings from the analytics agent (e.g. *"policy drift: meal claims +40% over limit in Sales"*) reach the same channel.

`.claude/settings.json` snippet:

```json
{
  "hooks": {
    "Notification": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/forward-alert.sh"
          }
        ]
      }
    ]
  }
}
```

`.claude/hooks/forward-alert.sh`:

```bash
#!/usr/bin/env bash
# Forwards Claude Code notifications to the team alert channel.
set -uo pipefail
MSG=$(jq -r '.message // "Claude Code notification"')
# Read the webhook from .env if it isn't already set (parsed, not executed).
if [[ -z "${AIDLC_ALERT_WEBHOOK:-}" && -f "$CLAUDE_PROJECT_DIR/.env" ]]; then
  AIDLC_ALERT_WEBHOOK=$(grep -E '^AIDLC_ALERT_WEBHOOK=' "$CLAUDE_PROJECT_DIR/.env" | tail -n 1 | cut -d= -f2- | tr -d "\"'")
fi
[[ -n "${AIDLC_ALERT_WEBHOOK:-}" ]] || exit 0   # not configured: skip quietly
curl -sS -m 10 -X POST -H 'Content-Type: application/json' \
  -d "$(jq -n --arg t "[AI-DLC expense] $MSG" '{text:$t}')" \
  "$AIDLC_ALERT_WEBHOOK" >/dev/null || true
exit 0
```

Put `AIDLC_ALERT_WEBHOOK` in the git-ignored `.env` file (template: `env.example`), or export it in your shell. Never commit the webhook URL.

## 8. Outputs and artifacts

| Artifact | Location in repo / tool | Owner |
| --- | --- | --- |
| Reimbursement tracking view | QuickSight | Solution Owner |
| Spend dashboard | QuickSight | Solution Owner |
| Incident postmortems | `aidlc-docs/operations/incidents/YYYY-MM-DD-<slug>.md` | Engineer |
| Weekly insights / policy drift | `aidlc-docs/operations/insights/YYYY-MM-DD.md` | Solution Owner |
| Retro | `aidlc-docs/operations/retros/<release>.md` | Team |
| Next intent (input to DIS-01) | `aidlc-docs/operations/next-intent.md` | Solution Owner |

## 9. Exit criteria (Definition of Done)

- [ ] Reimbursement tracking and spend dashboard live with row-level security.
- [ ] Every alarm has an owner and a runbook entry.
- [ ] Every incident has a blameless postmortem with actions and owners.
- [ ] Weekly insight report produced; drift findings reviewed by the Solution Owner.
- [ ] Retro done for the release.
- [ ] **HUMAN GATE:** Solution Owner approves `next-intent.md`, which opens the next DIS-01 cycle.

## 10. Starter prompts

```text
/investigate — alarm "approve-p95-latency" fired at 10:42. Use CloudWatch logs and metrics
for the approve unit from 10:00 to 11:00. Give a timeline, hypotheses and evidence. Do not change anything.
```

```text
Use spend-analytics on last week's BI data. Compare out-of-policy claims by team and category
with rules config v<n>. Flag drift with numbers. Aggregated data only.
```

```text
/retro for release <version>. Then draft next-intent.md from the retro, incidents and insights.
```

## 11. Best practices

- **Close the loop.** Every cycle ends with a written next intent — that is what makes AI-DLC continuous.
- **Read-only AI in prod.** Claude analyses and proposes; humans change production.
- **Privacy in analytics.** Aggregate or tokenise; use QuickSight row-level security.
- **Alarms with owners.** An alarm without an owner and a runbook is noise.
- **Blameless postmortems.** Focus on gates and systems, including AI gates that missed the issue.
- **Measure the method.** Track lead time per bolt, gate rework and escaped defects in retros.

## 12. Anti-patterns to avoid

- Dashboards nobody owns or reads.
- Letting Claude restart services or change config in prod "to save time".
- Individual employee spend in AI outputs or shared reports.
- Retros that produce no change to the next intent.

## 13. References

- Amazon CloudWatch — <https://aws.amazon.com/cloudwatch>
- Amazon QuickSight — <https://aws.amazon.com/quicksight>
- gstack — <https://github.com/garrytan/gstack>
- Matt Pocock skills — <https://github.com/mattpocock/skills>
- Claude Code hooks — <https://docs.claude.com/en/docs/claude-code/hooks>
- Full list: [../references.md](../references.md)

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 2, row 8 |
| 1.1.0 | 2026-10-30 | AI-DLC team | Skill names updated to installed versions (MP 1.3.2, AO 0.6.14) |
| 1.2.0 | 2026-10-30 | AI-DLC team | Alert webhook read from `.env` |
