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
