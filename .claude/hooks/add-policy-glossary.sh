#!/usr/bin/env bash
# Adds the expense-policy glossary to each prompt so Claude uses the same terms as finance.
set -euo pipefail
GLOSSARY="$CLAUDE_PROJECT_DIR/aidlc-docs/glossary/policy-glossary.md"
[[ -f "$GLOSSARY" ]] || exit 0   # no glossary yet: do nothing, never block
echo "## Expense policy glossary (auto-added by hook)"
cat "$GLOSSARY"
