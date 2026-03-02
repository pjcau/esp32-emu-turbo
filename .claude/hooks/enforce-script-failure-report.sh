#!/usr/bin/env bash
# enforce-script-failure-report.sh
# Adapted from agent-sh/agentsys
#
# PostToolUse hook for Bash: detects project script execution and reminds
# the agent to report failures before falling back to manual work.
#
# Input: JSON on stdin with tool_input.command
# Output: Reminder on stdout if project script detected
# Exit: Always 0 (hooks must not block)

set -euo pipefail

INPUT=$(cat 2>/dev/null || true)
[ -z "$INPUT" ] && exit 0

COMMAND=""
if command -v jq >/dev/null 2>&1; then
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)
else
  COMMAND=$(echo "$INPUT" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*:[[:space:]]*"//;s/"$//' 2>/dev/null || true)
fi

[ -z "$COMMAND" ] && exit 0

IS_PROJECT_SCRIPT=false
case "$COMMAND" in
  *make\ *|*python3\ scripts/*|*python3\ -m\ scripts*|*./scripts/*|*verify_dfm*|*verify_dfa*|*generate_pcb*|*export-gerbers*)
    IS_PROJECT_SCRIPT=true
    ;;
esac

if [ "$IS_PROJECT_SCRIPT" = true ]; then
  echo "[HOOK] Project script detected. If this command failed, REPORT the failure with exact error output before attempting any manual workaround. Fix the script, not the symptom."
fi

exit 0
