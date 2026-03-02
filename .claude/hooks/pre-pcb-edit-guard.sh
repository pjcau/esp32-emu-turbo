#!/usr/bin/env bash
# Pre-tool-use PCB edit guard — prevents direct .kicad_pcb edits
# Inspired by PreToolUse hook pattern from shintaro-sprech/agent-orchestrator-template
# Project convention: never edit .kicad_pcb directly, always regenerate from Python scripts
# Exit code 2 = block the tool call

set -euo pipefail

# Read JSON from stdin
INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || echo "")

# Only check Edit and Write tools (Read is fine)
if [ "$TOOL_NAME" != "Edit" ] && [ "$TOOL_NAME" != "Write" ]; then
    exit 0
fi

TOOL_INPUT=$(echo "$INPUT" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('tool_input',{})))" 2>/dev/null || echo "{}")
FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null || echo "")

# Block direct edits to .kicad_pcb files (except the 3D-injected one which is .gitignored)
if echo "$FILE_PATH" | grep -qE '\.kicad_pcb$' && ! echo "$FILE_PATH" | grep -q 'esp32-emu-turbo-3d.kicad_pcb'; then
    echo ">>> BLOCKED: Direct .kicad_pcb edit is not allowed." >&2
    echo ">>> Convention: modify Python scripts in scripts/generate_pcb/ then run 'make generate-pcb'" >&2
    exit 2
fi

exit 0
