#!/usr/bin/env bash
# check-claudeignore — Block file access via .claudeignore patterns
# Adapted from RobinHamers/claude_hooks
#
# Prevents Claude from reading/editing/writing files that match patterns
# in .claudeignore at the project root. Uses gitignore-style patterns.
#
# Exit code 2 = block the tool call
# Exit code 0 = allow

set -euo pipefail

INPUT=$(cat)

TOOL_NAME=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || echo "")

# Only check file-access tools
case "$TOOL_NAME" in
    Read|Edit|Write|Grep) ;;
    *) exit 0 ;;
esac

# Find project root (where .claudeignore lives)
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
IGNOREFILE="$PROJECT_DIR/.claudeignore"

# No .claudeignore file = allow everything
if [ ! -f "$IGNOREFILE" ]; then
    exit 0
fi

# Extract file path from tool input
FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
data = json.load(sys.stdin)
ti = data.get('tool_input', {})
# Different tools use different keys
path = ti.get('file_path', '') or ti.get('path', '')
print(path)
" 2>/dev/null || echo "")

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Convert to path relative to project root
REL_PATH=$(python3 -c "
import os, sys
project = '$PROJECT_DIR'
fpath = '$FILE_PATH'
try:
    rel = os.path.relpath(os.path.realpath(fpath), os.path.realpath(project))
    # Skip paths outside the project
    if rel.startswith('..'):
        sys.exit(0)
    print(rel)
except ValueError:
    sys.exit(0)
" 2>/dev/null || echo "")

if [ -z "$REL_PATH" ]; then
    exit 0
fi

# Check each pattern in .claudeignore against the relative path
# Uses git check-ignore style matching via python fnmatch
BLOCKED=$(python3 -c "
import fnmatch, sys

rel_path = '$REL_PATH'
patterns = []

with open('$IGNOREFILE') as f:
    for line in f:
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith('#'):
            continue
        patterns.append(line)

for pattern in patterns:
    # Match against full relative path and just the filename
    if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(rel_path.split('/')[-1], pattern):
        print(f'Blocked: {rel_path} matches pattern: {pattern}')
        sys.exit(0)

# Also check directory components
import pathlib
parts = pathlib.PurePath(rel_path).parts
for pattern in patterns:
    if pattern.endswith('/'):
        # Directory pattern
        dir_pattern = pattern.rstrip('/')
        for part in parts[:-1]:
            if fnmatch.fnmatch(part, dir_pattern):
                print(f'Blocked: {rel_path} is inside directory matching: {pattern}')
                sys.exit(0)
" 2>/dev/null || echo "")

if [ -n "$BLOCKED" ]; then
    echo ">>> $BLOCKED" >&2
    echo ">>> File is listed in .claudeignore. Access denied." >&2
    exit 2
fi

exit 0
