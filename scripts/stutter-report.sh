#!/usr/bin/env bash
# Tally playback diagnostics from bot.log without touching the running bot.
# Usage: bash scripts/stutter-report.sh [logdir]
set -euo pipefail
LOGDIR="${1:-logs}"

echo "=== MusicBot stutter report ($(date)) ==="
echo "--- event tally ---"
grep -h "METRIC event=" "$LOGDIR"/bot.log* 2>/dev/null \
  | grep -oE "event=[a-z_0-9]+" | sort | uniq -c | sort -rn

echo "--- last 15 events ---"
grep -h "METRIC event=" "$LOGDIR"/bot.log* 2>/dev/null | tail -15

echo "--- voice reconnect waits (top 10) ---"
grep -h "event=voice_disconnect" "$LOGDIR"/bot.log* 2>/dev/null \
  | grep -oE "wait=[0-9.]+" | sort -t= -k2 -rn | head -10
