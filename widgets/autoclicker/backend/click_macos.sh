#!/bin/bash
# Autoclicker backend for macOS. Prints a JSON status line to stdout after
# each click, until the process is terminated by its parent.
#
# Requires cliclick (brew install cliclick): AppleScript/System Events
# can't post a synthetic click at an arbitrary screen position without an
# accessibility helper, and cliclick is the standard lightweight one.
#
# Usage: click_macos.sh <interval_ms> <button> <randomize_percent> [dry_run]
# button: left or right. cliclick has no middle-click command, so middle
#   isn't supported here and the script exits with an error line instead.
# randomize_percent: if greater than 0, jitters each wait by up to this
#   percent in either direction so the click pattern isn't perfectly
#   periodic.
# dry_run: pass 1 to print status lines without clicking, for testing.

interval_ms="${1:-100}"
button="${2:-left}"
randomize_percent="${3:-0}"
dry_run="${4:-0}"

if [ "$button" = "middle" ]; then
  echo '{"error": "Middle click isn'\''t supported on macOS. cliclick has no middle-click command, so left or right are the only options here."}'
  exit 1
fi

if [ "$dry_run" != "1" ] && ! command -v cliclick >/dev/null 2>&1; then
  echo '{"error": "Couldn'\''t find cliclick. Is it installed? Run: brew install cliclick"}'
  exit 1
fi

click_command="c:."
if [ "$button" = "right" ]; then
  click_command="rc:."
fi

count=0

while true; do
  if [ "$dry_run" != "1" ]; then
    cliclick "$click_command"
  fi
  count=$((count + 1))
  echo "{\"count\": $count}"

  wait_ms="$interval_ms"
  if awk "BEGIN { exit !($randomize_percent > 0) }"; then
    wait_ms=$(awk -v base="$interval_ms" -v pct="$randomize_percent" -v r="$RANDOM" \
      'BEGIN {
        deviation = base * (pct / 100)
        offset = ((r % 2001) / 1000 - 1) * deviation
        wait = base + offset
        if (wait < 1) wait = 1
        print wait
      }')
  fi
  sleep_seconds=$(awk -v ms="$wait_ms" "BEGIN { print ms / 1000 }")
  sleep "$sleep_seconds"
done
