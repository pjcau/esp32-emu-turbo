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

DFM_OUTPUT=$(cd "$PROJECT_DIR" && python3 "$DFM_SCRIPT" 2>&1 || true)

# Count failures (grep -c returns 1 when no matches; strip with tr)
FAIL_COUNT=$(printf "%s\n" "$DFM_OUTPUT" | grep -cE "FAIL|DANGER" || true)
FAIL_COUNT=$(printf "%s" "$FAIL_COUNT" | tr -d '[:space:]')
: "${FAIL_COUNT:=0}"

# ── Trace-through-pad overlap check ───────────────────────────────
# Blocking guard against the v3.3 regression (commit 775e9fd) where
# _PAD_NETS assignments were removed, leaving netted traces physically
# crossing unnetted pads — real shorts on the fabricated board.
TTP_SCRIPT="$PROJECT_DIR/scripts/verify_trace_through_pad.py"
TTP_FAIL_COUNT=0
TTP_OUTPUT=""
if [ -f "$TTP_SCRIPT" ]; then
    TTP_OUTPUT=$(cd "$PROJECT_DIR" && python3 "$TTP_SCRIPT" 2>&1 || true)
    TTP_FAIL_COUNT=$(printf "%s\n" "$TTP_OUTPUT" | grep -cE "^[[:space:]]*FAIL" || true)
    TTP_FAIL_COUNT=$(printf "%s" "$TTP_FAIL_COUNT" | tr -d '[:space:]')
    : "${TTP_FAIL_COUNT:=0}"
fi

# ── Net connectivity check ────────────────────────────────────────
# Blocking guard against the R5 class of electrical bugs where every
# pad-net assignment is "correct" per datasheet_specs but the copper
# is fragmented into isolated islands (see hardware-audit-bugs.md R5).
NC_SCRIPT="$PROJECT_DIR/scripts/verify_net_connectivity.py"
NC_FAIL_COUNT=0
NC_OUTPUT=""
if [ -f "$NC_SCRIPT" ]; then
    NC_OUTPUT=$(cd "$PROJECT_DIR" && python3 "$NC_SCRIPT" 2>&1 || true)
    NC_FAIL_COUNT=$(printf "%s\n" "$NC_OUTPUT" | grep -cE "^[[:space:]]*FAIL" || true)
    NC_FAIL_COUNT=$(printf "%s" "$NC_FAIL_COUNT" | tr -d '[:space:]')
    : "${NC_FAIL_COUNT:=0}"
fi

# ── EasyEDA reference footprint check ─────────────────────────────
# Blocking guard against the C2 tantalum class of bugs (footprint pad-1
# on opposite side vs EasyEDA/JLCPCB reference → reversed polarity at
# assembly). Only runs when BOM/jlcpcb_export/footprints files change.
EE_FAIL_COUNT=0
EE_OUTPUT=""
EE_SCRIPT="$PROJECT_DIR/scripts/verify_easyeda_footprint.py"
EE_CHANGED=false
if git -C "$PROJECT_DIR" diff --name-only HEAD 2>/dev/null | grep -qE '(bom\.csv|jlcpcb_export|footprints\.py|generate_pcb/board\.py)'; then
    EE_CHANGED=true
fi
if git -C "$PROJECT_DIR" diff --cached --name-only 2>/dev/null | grep -qE '(bom\.csv|jlcpcb_export|footprints\.py|generate_pcb/board\.py)'; then
    EE_CHANGED=true
fi
if [ "$EE_CHANGED" = true ] && [ -f "$EE_SCRIPT" ]; then
    # Capture both output and exit code. The script exits 0 for OK /
    # ALLOW / PENDING / REVIEW / WARN and non-zero only on real FAIL.
    # PENDING entries (suspected polarity bugs awaiting empirical
    # validation on a named batch) MUST NOT trigger Stop-hook noise,
    # so we defer to the script's exit code rather than grep-counting
    # [FAIL lines. If the script says "exit 0", no warning fires.
    EE_OUTPUT=$(cd "$PROJECT_DIR" && python3 "$EE_SCRIPT" 2>&1) && EE_EXIT=0 || EE_EXIT=$?
    if [ "$EE_EXIT" -ne 0 ]; then
        EE_FAIL_COUNT=$(printf "%s\n" "$EE_OUTPUT" | grep -cE "^[[:space:]]*\[FAIL" || true)
        EE_FAIL_COUNT=$(printf "%s" "$EE_FAIL_COUNT" | tr -d '[:space:]')
        : "${EE_FAIL_COUNT:=0}"
        # Safety net: if the exit code is non-zero but grep found no
        # [FAIL lines (shouldn't happen), still signal at least one
        # failure so the hook fires.
        if [ "$EE_FAIL_COUNT" -eq 0 ]; then
            EE_FAIL_COUNT=1
        fi
    else
        EE_FAIL_COUNT=0
    fi
fi

TOTAL_FAIL=$((FAIL_COUNT + TTP_FAIL_COUNT + NC_FAIL_COUNT + EE_FAIL_COUNT))

if [ "$TOTAL_FAIL" -gt 0 ]; then
    echo "" >&2
    echo "## PCB Verification Found Issues" >&2
    echo "" >&2
    echo "PCB files were modified. Verification found $TOTAL_FAIL issue(s):" >&2
    echo "" >&2
    if [ "$FAIL_COUNT" -gt 0 ]; then
        echo "── DFM (verify_dfm_v2.py): $FAIL_COUNT failure(s) ──" >&2
        echo "$DFM_OUTPUT" | grep -E "FAIL|DANGER" | head -15 >&2
        echo "" >&2
    fi
    if [ "$TTP_FAIL_COUNT" -gt 0 ]; then
        echo "── Trace-through-pad (verify_trace_through_pad.py): $TTP_FAIL_COUNT failure(s) ──" >&2
        echo "$TTP_OUTPUT" | grep -E "^\s*(FAIL|U[0-9]+\.|SW_|J[0-9]+\.)" | head -15 >&2
        echo "" >&2
    fi
    if [ "$NC_FAIL_COUNT" -gt 0 ]; then
        echo "── Net connectivity (verify_net_connectivity.py): $NC_FAIL_COUNT fragmented net(s) ──" >&2
        echo "$NC_OUTPUT" | grep -E "^\s*(FAIL|──)" | head -15 >&2
        echo "" >&2
    fi
    if [ "$EE_FAIL_COUNT" -gt 0 ]; then
        echo "── EasyEDA footprint (verify_easyeda_footprint.py): $EE_FAIL_COUNT mismatch(es) ──" >&2
        echo "$EE_OUTPUT" | grep -E "^\s*\[FAIL" | head -15 >&2
        echo "" >&2
    fi
    echo "Run for full details:" >&2
    [ "$FAIL_COUNT" -gt 0 ]     && echo "  python3 scripts/verify_dfm_v2.py" >&2
    [ "$TTP_FAIL_COUNT" -gt 0 ] && echo "  python3 scripts/verify_trace_through_pad.py" >&2
    [ "$NC_FAIL_COUNT" -gt 0 ]  && echo "  python3 scripts/verify_net_connectivity.py" >&2
    [ "$EE_FAIL_COUNT" -gt 0 ]  && echo "  python3 scripts/verify_easyeda_footprint.py" >&2
    echo "Fix issues before committing." >&2
    exit 2
fi

# If all passed, report success briefly
PASS_COUNT=$(echo "$DFM_OUTPUT" | grep -c "PASS\|OK" 2>/dev/null || echo "0")
if [ "$PASS_COUNT" -gt 0 ]; then
    echo "" >&2
    echo "PCB verification passed: DFM $PASS_COUNT tests OK, trace-through-pad clean." >&2
fi

exit 0
