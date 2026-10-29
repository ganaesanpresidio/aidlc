---
id: REF-00
title: References — Method, Skills, Agents and Tools
status: Draft
version: 1.0.0
last_updated: 2026-10-29
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
| MP · Matt Pocock skills | `grill-me`, `to-prd`, `grill-with-docs`, `ubiquitous-language`, `tdd`, `diagnose` | <https://github.com/mattpocock/skills> |
| AO · Addy Osmani agent-skills | `/spec`, `/plan`, `/build`, `/ship`, `api-and-interface-design`, `frontend-ui-engineering`, `code-review-and-quality` | <https://github.com/addyosmani/agent-skills> |
| GS · gstack (Garry Tan) | `/office-hours`, `/autoplan`, `/plan-eng-review`, `/review`, `/qa`, `/cso`, `/ship`, `/land-and-deploy`, `/canary`, `/investigate`, `/retro` | <https://github.com/garrytan/gstack> |

> Skill names change between library versions. Pin the version you install and check names with `/help` in Claude Code.

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
