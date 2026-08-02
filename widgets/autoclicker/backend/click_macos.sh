#!/bin/bash
# Autoclicker backend for macOS. Prints a JSON status line to stdout after
# each click, until the process is terminated by its parent.
#
# Requires cliclick (brew install cliclick): AppleScript/System Events
# can't post a synthetic click at an arbitrary screen position without an
# accessibility helper, and cliclick is the standard lightweight one.
#
# Usage: click_macos.sh <interval_ms> [dry_run]
# dry_run: pass 1 to print status lines without clicking, for testing.

interval_ms="${1:-100}"
dry_run="${2:-0}"

if [ "$dry_run" != "1" ] && ! command -v cliclick >/dev/null 2>&1; then
  echo '{"error": "Couldn'\''t find cliclick. Is it installed? Run: brew install cliclick"}'
  exit 1
fi

sleep_seconds=$(awk "BEGIN { print $interval_ms / 1000 }")
count=0

while true; do
  if [ "$dry_run" != "1" ]; then
    cliclick c:.
  fi
  count=$((count + 1))
  echo "{\"count\": $count}"
  sleep "$sleep_seconds"
done
