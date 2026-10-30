#!/usr/bin/env bash
# Blocks code writes for a unit until that unit's LLD is approved.
set -euo pipefail
FILE=$(jq -r '.tool_input.file_path // empty')
REL="${FILE#"$CLAUDE_PROJECT_DIR"/}"
case "$REL" in
  src/*/*) UNIT=$(cut -d/ -f2 <<<"$REL") ;;
  *) exit 0 ;;
esac
GATE="$CLAUDE_PROJECT_DIR/aidlc-docs/approvals/lld-$UNIT.md"
if ! grep -q '^Status: APPROVED' "$GATE" 2>/dev/null; then
  echo "Blocked: LLD for unit '$UNIT' not approved (aidlc-docs/approvals/lld-$UNIT.md). Finish DIS-04 for this unit first." >&2
  exit 2
fi
