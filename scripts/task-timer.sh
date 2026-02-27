#!/usr/bin/env bash
# Task Timer — logs execution time of make targets to CSV
# Usage: scripts/task-timer.sh <target-name> <command...>
#
# Appends a row to logs/task-times.csv:
#   timestamp, target, duration_sec, exit_code
#
# Analyze with: scripts/task-stats.sh

set -euo pipefail

TARGET="$1"
shift

LOG_DIR="$(dirname "$0")/../logs"
LOG_FILE="$LOG_DIR/task-times.csv"

mkdir -p "$LOG_DIR"

# Create header if file doesn't exist
if [ ! -f "$LOG_FILE" ]; then
    echo "timestamp,target,duration_sec,exit_code" > "$LOG_FILE"
fi

START=$(date +%s.%N 2>/dev/null || python3 -c "import time; print(f'{time.time():.3f}')")

# Run the actual command
set +e
"$@"
EXIT_CODE=$?
set -e

END=$(date +%s.%N 2>/dev/null || python3 -c "import time; print(f'{time.time():.3f}')")
DURATION=$(python3 -c "print(f'{$END - $START:.2f}')")
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "$TIMESTAMP,$TARGET,$DURATION,$EXIT_CODE" >> "$LOG_FILE"

# Show timing inline
if [ "$EXIT_CODE" -eq 0 ]; then
    printf "\033[32m✓ %s completed in %ss\033[0m\n" "$TARGET" "$DURATION"
else
    printf "\033[31m✗ %s failed in %ss (exit %d)\033[0m\n" "$TARGET" "$DURATION" "$EXIT_CODE"
fi

exit $EXIT_CODE
