#!/bin/bash
# Post-hook: after any Bash call that runs generate_pcb, remind to verify DFM
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if echo "$COMMAND" | grep -q "generate_pcb"; then
  echo '{"systemMessage": "PCB was regenerated. Run DFM verification: python3 scripts/verify_dfm_v2.py"}'
fi

exit 0
