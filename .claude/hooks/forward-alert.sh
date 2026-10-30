#!/usr/bin/env bash
# Forwards Claude Code notifications to the team alert channel.
set -uo pipefail
MSG=$(jq -r '.message // "Claude Code notification"')
# Read the webhook from .env if it isn't already set (parsed, not executed).
if [[ -z "${AIDLC_ALERT_WEBHOOK:-}" && -f "$CLAUDE_PROJECT_DIR/.env" ]]; then
  AIDLC_ALERT_WEBHOOK=$(grep -E '^AIDLC_ALERT_WEBHOOK=' "$CLAUDE_PROJECT_DIR/.env" | tail -n 1 | cut -d= -f2- | tr -d "\"'")
fi
[[ -n "${AIDLC_ALERT_WEBHOOK:-}" ]] || exit 0   # not configured: skip quietly
curl -sS -m 10 -X POST -H 'Content-Type: application/json' \
  -d "$(jq -n --arg t "[AI-DLC expense] $MSG" '{text:$t}')" \
  "$AIDLC_ALERT_WEBHOOK" >/dev/null || true
exit 0
