#!/bin/bash
# Post-hook: after a Bash call that actually REGENERATES the PCB, remind to
# verify DFM — once. The reminder stays silent until verify_dfm runs, then
# re-arms so the next regeneration reminds again.
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

# Marker = "reminder already given, verification still pending".
# Keyed by session so parallel sessions don't swallow each other's reminder.
MARKER="${TMPDIR:-/tmp}/claude-dfm-remind-${SESSION_ID:-$PPID}"

# Running the DFM verification (directly or via make) re-arms the reminder.
if echo "$COMMAND" | grep -qE 'verify_dfm|make +(verify-fast|verify-all|fast-check)'; then
  rm -f "$MARKER"
  exit 0
fi

# Only an actual generator invocation counts — not reads/greps of files that
# merely live under scripts/generate_pcb/.
if echo "$COMMAND" | grep -qE '(python3? +[^ ]*scripts/generate_pcb|make +(generate-pcb|release-prep))'; then
  if [ ! -e "$MARKER" ]; then
    touch "$MARKER"
    echo '{"systemMessage": "PCB was regenerated. Run DFM verification: python3 scripts/verify_dfm_v2.py"}'
  fi
fi

exit 0
