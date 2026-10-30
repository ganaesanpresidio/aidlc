---
id: REF-00
title: References — Method, Skills, Agents and Tools
status: Draft
version: 1.1.0
last_updated: 2026-10-30
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 3 (addresses as of 28 Oct 2026)
---

# References — Method, Skills, Agents and Tools

Every name used in the activity files, with its web address.

## Method and workflows

| Reference | What it gives | Link |
| --- | --- | --- |
| AWS AI-DLC method | Phases, Mob Elaboration, bolts | <https://aws.amazon.com/blogs/devops/ai-driven-development-life-cycle> |
| AI-DLC workflows | Open-source stage rules for Claude Code | <https://github.com/awslabs/aidlc-workflows> |
| Claude Code hooks | `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `Notification` | <https://docs.claude.com/en/docs/claude-code/hooks> |
| Claude Code subagents | One subagent per unit of work | <https://docs.claude.com/en/docs/claude-code/sub-agents> |
| Kiro | Optional spec-mode IDE from AWS | <https://kiro.dev> |

## Skill libraries

| Reference | What it gives | Link |
| --- | --- | --- |
| MP · Matt Pocock skills | `/grill-me`, `/to-spec`, `/to-tickets`, `/grill-with-docs`, `domain-modeling`, `tdd`, `diagnosing-bugs`, `/mattpocock-skills:code-review` | <https://github.com/mattpocock/skills> |
| AO · Addy Osmani agent-skills | `/agent-skills:spec`, `/agent-skills:plan`, `/agent-skills:build`, `/agent-skills:ship`, `api-and-interface-design`, `frontend-ui-engineering`, `code-review-and-quality` | <https://github.com/addyosmani/agent-skills> |
| GS · gstack (Garry Tan) | `/office-hours`, `/autoplan`, `/plan-eng-review`, `/review`, `/qa`, `/cso`, `/ship`, `/land-and-deploy`, `/canary`, `/investigate`, `/retro` | <https://github.com/garrytan/gstack> |

### Installed versions

| Library | Version | Installed as |
| --- | --- | --- |
| MP · Matt Pocock skills | 1.3.2 | Claude Code plugin `mattpocock-skills@mattpocock` |
| AO · Addy Osmani agent-skills | 0.6.14 | Claude Code plugin `agent-skills@addy-agent-skills` |
| GS · gstack | main branch (names checked 2026-10-30) | `~/.claude/skills/gstack` (clone + `./setup`) |

### Names changed from the original deck

| Deck name | Use now | Why |
| --- | --- | --- |
| MP `to-prd` | `/to-spec` | Renamed in MP skills; `/to-tickets` now splits the spec into stories |
| MP `ubiquitous-language` | `domain-modeling` | Renamed in MP skills (also maintains the glossary and ADRs) |
| MP `diagnose` | `diagnosing-bugs` | Renamed in MP skills |
| AO `/spec`, `/plan`, `/build`, `/ship` | `/agent-skills:spec`, `/agent-skills:plan`, `/agent-skills:build`, `/agent-skills:ship` | gstack also has `/spec` and `/ship`, and Claude Code has built-in `/plan` and `/review`; the full name always picks Addy Osmani's version |

### How to invoke

- A name starting with `/` is typed as a command. MP's `grill-me`, `grill-with-docs`, `to-spec` and `to-tickets` work **only** this way.
- A name without `/` (e.g. `domain-modeling`, `tdd`, `code-review-and-quality`) is used by Claude automatically when the task fits. You can also ask for it by name.
- Use the full `<plugin>:<skill>` form whenever two libraries share a name.
- Pin library versions. After an upgrade, re-check names with `/help` and update this table.

## Tools, MCP and AWS

| Reference | What it gives | Link |
| --- | --- | --- |
| AWS MCP servers | Diagram, CDK, Knowledge servers | <https://github.com/awslabs/mcp> |
| Atlassian remote MCP | Jira and Confluence access | <https://www.atlassian.com/platform/remote-mcp-server> |
| Build services | Receipt OCR, approval flow, AI | <https://aws.amazon.com/textract> · <https://aws.amazon.com/step-functions> · <https://aws.amazon.com/bedrock> |
| Ship tooling | IaC and release pipeline | <https://aws.amazon.com/cdk> · <https://aws.amazon.com/codepipeline> · <https://github.com/features/actions> |
| Test and run | Browser tests, monitoring, spend BI | <https://playwright.dev> · <https://aws.amazon.com/cloudwatch> · <https://aws.amazon.com/quicksight> |

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 3 |
| 1.1.0 | 2026-10-30 | AI-DLC team | Installed versions, renamed skills and how to invoke them |
