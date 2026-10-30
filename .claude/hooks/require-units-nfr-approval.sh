#!/usr/bin/env bash
# Blocks design (LLD) writes until units and NFRs are approved.
set -euo pipefail
FILE=$(jq -r '.tool_input.file_path // empty')
case "$FILE" in
  */aidlc-docs/design/*|aidlc-docs/design/*) ;;
  *) exit 0 ;;
esac
GATE="$CLAUDE_PROJECT_DIR/aidlc-docs/approvals/units-nfr.md"
if ! grep -q '^Status: APPROVED' "$GATE" 2>/dev/null; then
  echo "Blocked: units + NFRs (audit, PII) not approved (aidlc-docs/approvals/units-nfr.md). Finish DIS-03 first." >&2
  exit 2
fi
