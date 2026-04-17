#!/usr/bin/env bash
# stop-regen-ibom.sh
# Stop hook: if PCB / BOM / gerber files were modified during the response,
# regenerate the Interactive HTML BOM (website/static/ibom/ibom.html).
#
# Non-blocking: runs the generator in the background so it doesn't slow the turn.
# Never fails the Stop hook — iBOM regeneration is a best-effort convenience.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# Only trigger when PCB-, BOM-, or gerber-related files changed
PATTERN='(\.kicad_pcb|generate_pcb/|footprints\.py|routing\.py|bom\.csv|cpl\.csv|jlcpcb_export|release_jlcpcb/|gerbers/|gerbers\.zip)'

CHANGED=false
if git -C "$PROJECT_DIR" diff --name-only HEAD 2>/dev/null | grep -qE "$PATTERN"; then
    CHANGED=true
fi
if git -C "$PROJECT_DIR" diff --cached --name-only 2>/dev/null | grep -qE "$PATTERN"; then
    CHANGED=true
fi

if [ "$CHANGED" = false ]; then
    exit 0
fi

SCRIPT="$PROJECT_DIR/scripts/generate_ibom.sh"
if [ ! -x "$SCRIPT" ]; then
    exit 0
fi

# Kick off in background — Docker+Xvfb takes ~15s, don't block Stop hook
LOG="$PROJECT_DIR/.claude/logs/ibom-regen.log"
mkdir -p "$(dirname "$LOG")"
nohup "$SCRIPT" >"$LOG" 2>&1 &
disown || true

echo "iBOM: regeneration started in background (log: .claude/logs/ibom-regen.log)" >&2
exit 0
