#!/bin/bash
# Post-hook: after editing a generate_pcb script, remind to regenerate
INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if echo "$FILE_PATH" | grep -q "scripts/generate_pcb/"; then
  FILENAME=$(basename "$FILE_PATH")
  echo "{\"systemMessage\": \"You edited ${FILENAME}. Remember to regenerate the PCB: python3 -m scripts.generate_pcb hardware/kicad\"}"
fi

exit 0
