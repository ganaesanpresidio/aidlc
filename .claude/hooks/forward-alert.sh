#!/usr/bin/env bash
# Forwards Claude Code notifications to the team alert channel.
set -uo pipefail
MSG=$(jq -r '.message // "Claude Code notification"')
[[ -n "${AIDLC_ALERT_WEBHOOK:-}" ]] || exit 0   # not configured: skip quietly
curl -sS -m 10 -X POST -H 'Content-Type: application/json' \
  -d "$(jq -n --arg t "[AI-DLC expense] $MSG" '{text:$t}')" \
  "$AIDLC_ALERT_WEBHOOK" >/dev/null || true
exit 0
