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
