#!/usr/bin/env bash
set -e
INTERVAL=${1:-15}
LOG=/tmp/live_monitor.log
while true; do
  python3 data.py >> "$LOG" 2>&1
  python3 signals.py >> "$LOG" 2>&1
  sleep "$INTERVAL"m
done
