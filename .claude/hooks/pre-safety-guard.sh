#!/usr/bin/env bash
# Pre-tool-use safety guard — blocks dangerous commands
# Adapted from lvalics/claude_code_stuffs pre_tool_use.py
# Exit code 2 = block the tool call

set -euo pipefail

# Read JSON from stdin
INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || echo "")
TOOL_INPUT=$(echo "$INPUT" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin).get('tool_input',{})))" 2>/dev/null || echo "{}")

# --- Check 1: Block dangerous rm commands ---
if [ "$TOOL_NAME" = "Bash" ]; then
    COMMAND=$(echo "$TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" 2>/dev/null || echo "")
    CMD_LOWER=$(echo "$COMMAND" | tr '[:upper:]' '[:lower:]')

    # Block rm -rf with dangerous paths
    if echo "$CMD_LOWER" | grep -qE '\brm\s+.*-[a-z]*r[a-z]*f|\brm\s+.*-[a-z]*f[a-z]*r|\brm\s+--recursive\s+--force|\brm\s+--force\s+--recursive'; then
        # Check for dangerous target paths
        if echo "$CMD_LOWER" | grep -qE '(^|\s)(\/\s|\/\*|\~|\.\.|\$HOME|\.\s*$)'; then
            echo ">>> BLOCKED: Dangerous rm -rf command targeting critical path" >&2
            exit 2
        fi
    fi

    # Block .env file access via bash
    if echo "$COMMAND" | grep -qE '(cat|echo.*>|touch|cp|mv|source|\.)\s+.*\.env\b' && ! echo "$COMMAND" | grep -qE '\.env\.(sample|example|template)'; then
        echo ">>> BLOCKED: Direct .env file access. Use .env.sample for templates." >&2
        exit 2
    fi
fi

# --- Check 2: Block .env file access via file tools ---
if [ "$TOOL_NAME" = "Read" ] || [ "$TOOL_NAME" = "Edit" ] || [ "$TOOL_NAME" = "Write" ]; then
    FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null || echo "")
    if echo "$FILE_PATH" | grep -qE '\.env$|\.env\.local$|\.env\.[^.]*\.local$' && ! echo "$FILE_PATH" | grep -qE '\.(sample|example|template)$'; then
        echo ">>> BLOCKED: Access to .env files with sensitive data. Use .env.sample instead." >&2
        exit 2
    fi
fi

exit 0
