---
id: HOOK-00
title: Hooks Catalog — All Claude Code Hooks in One Place
status: Draft
version: 1.0.0
last_updated: 2026-10-29
source: AI-DLC_usercase_for_ExpenseManagement_V1.0.pptx, slide 2, Hooks column
---

# Hooks Catalog — All Claude Code Hooks in One Place

> **One line:** Eight hooks enforce the human gates of AI-DLC inside Claude Code. The Architect owns them.

## Summary

| Activity | Event | Matcher | Script | Effect |
| --- | --- | --- | --- | --- |
| DIS-01 | `UserPromptSubmit` | — | `add-policy-glossary.sh` | Adds policy glossary to every prompt |
| DIS-02 | `PreToolUse` | `Write\|Edit\|MultiEdit` | `require-spec-signoff.sh` | Blocks `src/` and `infra/` writes before spec sign-off |
| DIS-03 | `PreToolUse` | `Write\|Edit\|MultiEdit` | `require-units-nfr-approval.sh` | Blocks LLD writes before units + NFRs approval |
| DIS-04 | `PreToolUse` | `Write\|Edit\|MultiEdit` | `require-lld-approval.sh` | Blocks `src/<unit>/` writes before that unit's LLD approval |
| BLD-01 | `PostToolUse` | `Write\|Edit\|MultiEdit` | `post-edit-checks.sh` | Lint, type-check, unit tests after each edit |
| BLD-02 | `PreToolUse` | `Bash` | `guard-commit.sh` | Blocks `git commit` on failing tests or PII |
| DEP-01 | `PreToolUse` | `Bash` | `guard-prod-deploy.sh` | Prod deploy asks a human; pipeline approval denied to Claude |
| DEP-02 | `Notification` | — | `forward-alert.sh` | Forwards Claude alerts (SLA breach, policy drift) to the team channel |

Each script is listed in full in its activity file, section **7. Hooks**.

## How hooks talk back to Claude Code

| Mechanism | Meaning |
| --- | --- |
| Exit `0` | Allow. For `UserPromptSubmit`, stdout is added as context |
| Exit `2` | Block (`PreToolUse`) or report a problem (`PostToolUse`). stderr is sent to Claude |
| JSON `permissionDecision` (`allow` / `ask` / `deny`) | `PreToolUse` only: fine-grained decision with a reason |

## Combined `.claude/settings.json` (activate when the team is ready)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/add-policy-glossary.sh" } ] }
    ],
    "PreToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/require-spec-signoff.sh" },
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/require-units-nfr-approval.sh" },
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/require-lld-approval.sh" }
        ]
      },
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-commit.sh", "timeout": 600 },
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/guard-prod-deploy.sh" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [
          { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/post-edit-checks.sh", "timeout": 300 }
        ]
      }
    ],
    "Notification": [
      { "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/forward-alert.sh" } ] }
    ]
  }
}
```

## Rollout steps

1. Copy each script from its activity file into `.claude/hooks/` and run `chmod +x .claude/hooks/*.sh`.
2. Make sure `jq` is installed (all scripts use it).
3. Merge the block above into `.claude/settings.json` (shared, committed). Personal overrides go in `.claude/settings.local.json` (git-ignored).
4. Test each hook with a dry run, e.g. `echo '{"tool_input":{"file_path":"'$PWD'/src/policy/x.ts"}}' | CLAUDE_PROJECT_DIR=$PWD .claude/hooks/require-lld-approval.sh; echo $?`.
5. Run `/hooks` in a Claude Code terminal session to confirm they are loaded.

## Best practices

- **Hooks are code.** Review, version and test them like code; changes need Architect approval.
- **Fail safe, fail clear.** Every block message says what is missing and which activity fixes it.
- **Fast hooks.** Keep `PreToolUse` checks under a second; long checks belong in `PostToolUse` or CI.
- **Defence in depth.** Hooks guard Claude. Git pre-commit hooks, CI and IAM guard everyone.
- **No secrets in hooks.** Read webhooks and tokens from environment variables.

## Change log

| Version | Date | Author | Change |
| --- | --- | --- | --- |
| 1.0.0 | 2026-10-29 | AI-DLC team | First version from slide 2, Hooks column |
