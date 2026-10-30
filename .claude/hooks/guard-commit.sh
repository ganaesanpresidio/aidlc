#!/usr/bin/env bash
# Blocks git commit when tests fail or the staged diff contains likely PII.
set -uo pipefail
CMD=$(jq -r '.tool_input.command // empty')
grep -Eq '(^|[;&|[:space:]])git[[:space:]]+commit' <<<"$CMD" || exit 0
cd "$CLAUDE_PROJECT_DIR"

if ! OUT=$(make -s test 2>&1); then
  echo "Blocked commit: tests are failing." >&2
  echo "$OUT" | tail -n 60 >&2
  exit 2
fi

# Simple PII patterns: email, 13-19 digit card numbers, IBAN. Extend per bank standard.
PII='[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|\b([0-9][ -]?){13,19}\b|\b[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}\b'
if git diff --cached -U0 | grep -E '^\+[^+]' | grep -Eq "$PII"; then
  echo "Blocked commit: staged changes look like they contain PII (email, card or IBAN). Use synthetic data." >&2
  exit 2
fi
