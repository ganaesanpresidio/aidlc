#!/usr/bin/env bash
# Runs lint, type-check and unit tests for the unit that was just edited.
set -uo pipefail
FILE=$(jq -r '.tool_input.file_path // empty')
REL="${FILE#"$CLAUDE_PROJECT_DIR"/}"
case "$REL" in
  src/*/*) UNIT=$(cut -d/ -f2 <<<"$REL") ;;
  *) exit 0 ;;
esac
cd "$CLAUDE_PROJECT_DIR"
if ! OUT=$(make -s lint typecheck test-unit UNIT="$UNIT" 2>&1); then
  echo "Checks failed for unit '$UNIT' after editing $REL:" >&2
  echo "$OUT" | tail -n 80 >&2
  exit 2   # PostToolUse: the edit already happened; stderr goes to Claude to fix it
fi
