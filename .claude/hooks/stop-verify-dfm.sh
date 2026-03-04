#!/usr/bin/env bash
# stop-verify-dfm.sh
# Stop hook: runs after Claude finishes responding.
# Checks if any PCB-related files were modified during the response,
# and if so, runs DFM verification and feeds results back.
#
# Inspired by diet103/claude-code-infrastructure-showcase stop-build-check pattern.
# Adapted for hardware/PCB workflow: runs verify_dfm_v2.py instead of tsc.
#
# Exit 0 = no issues, exit 2 = feedback for Claude (DFM failures found)

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"

# Check if any PCB-related files have been modified (staged or unstaged)
PCB_CHANGED=false
if git -C "$PROJECT_DIR" diff --name-only HEAD 2>/dev/null | grep -qE '(generate_pcb/|\.kicad_pcb|footprints\.py|routing\.py|jlcpcb_export|release_jlcpcb/)'; then
    PCB_CHANGED=true
fi
if git -C "$PROJECT_DIR" diff --cached --name-only 2>/dev/null | grep -qE '(generate_pcb/|\.kicad_pcb|footprints\.py|routing\.py|jlcpcb_export|release_jlcpcb/)'; then
    PCB_CHANGED=true
fi

if [ "$PCB_CHANGED" = false ]; then
    exit 0
fi

# Run DFM verification
DFM_SCRIPT="$PROJECT_DIR/scripts/verify_dfm_v2.py"
if [ ! -f "$DFM_SCRIPT" ]; then
    exit 0
fi

DFM_OUTPUT=$(cd "$PROJECT_DIR" && python3 "$DFM_SCRIPT" 2>&1) || true
DFM_EXIT=$?

# Count failures
FAIL_COUNT=$(echo "$DFM_OUTPUT" | grep -c "FAIL\|DANGER" 2>/dev/null || echo "0")

if [ "$FAIL_COUNT" -gt 0 ]; then
    echo "" >&2
    echo "## DFM Verification Found Issues" >&2
    echo "" >&2
    echo "PCB files were modified. DFM check found $FAIL_COUNT issue(s):" >&2
    echo "" >&2
    # Show only failure lines, limit to 20 to avoid flooding
    echo "$DFM_OUTPUT" | grep -E "FAIL|DANGER" | head -20 >&2
    echo "" >&2
    echo "Run 'python3 scripts/verify_dfm_v2.py' for full details." >&2
    echo "Fix issues before committing." >&2
    exit 2
fi

# If DFM passed, report success briefly
PASS_COUNT=$(echo "$DFM_OUTPUT" | grep -c "PASS\|OK" 2>/dev/null || echo "0")
if [ "$PASS_COUNT" -gt 0 ]; then
    echo "" >&2
    echo "DFM verification passed ($PASS_COUNT tests OK)." >&2
fi

exit 0
