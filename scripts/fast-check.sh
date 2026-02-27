#!/usr/bin/env bash
# Fast full check pipeline: generate + DRC + DFM + gerbers
# Uses local kicad-cli where possible, Docker only for zone fill.
#
# Benchmarks on M1 Max:
#   Full Docker pipeline:  ~15-20s
#   This script:           ~5-6s
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
KICAD_DIR="$PROJECT_ROOT/hardware/kicad"
PCB_FILE="$KICAD_DIR/esp32-emu-turbo.kicad_pcb"

START=$(date +%s%N)
ERRORS=0

step() { echo ""; echo "==> [$1] $2"; }
elapsed() { echo "  ($(( ($(date +%s%N) - START) / 1000000 ))ms elapsed)"; }

# ── Step 1: Generate PCB ──────────────────────────────────────
step "1/5" "Generating PCB from Python scripts..."
python3 -m scripts.generate_pcb hardware/kicad
elapsed

# ── Step 2: DFM quick check ──────────────────────────────────
step "2/5" "Running DFM verification (31 tests)..."
if python3 scripts/verify_dfm_v2.py; then
    echo "  DFM: ALL PASS"
else
    echo "  DFM: SOME FAILURES"
    ERRORS=$((ERRORS + 1))
fi
elapsed

# ── Step 3: KiCad DRC (local) ────────────────────────────────
step "3/5" "Running KiCad DRC (local kicad-cli)..."
if command -v kicad-cli &>/dev/null; then
    kicad-cli pcb drc \
        --output /tmp/drc-report.json \
        --format json \
        --severity-all \
        --units mm \
        --all-track-errors \
        "$PCB_FILE" 2>&1 | tail -3
    # Count real violations (not known false positives)
    python3 -c "
import json
with open('/tmp/drc-report.json') as f:
    data = json.load(f)
v = len(data.get('violations', []))
u = len(data.get('unconnected_items', []))
print(f'  DRC: {v} violations, {u} unconnected')
"
else
    echo "  SKIP: kicad-cli not found locally"
fi
elapsed

# ── Step 4: Zone fill (Docker) + Gerber export (local) ───────
step "4/5" "Exporting gerbers (zone fill via Docker, export local)..."
"$SCRIPT_DIR/export-gerbers-fast.sh" 2>&1 | grep -E "^==>|ZIP:|files exported"
elapsed

# ── Step 5: Connectivity check ───────────────────────────────
step "5/5" "Running connectivity check..."
python3 scripts/test_pcb_connectivity.py 2>&1 | tail -3
elapsed

# ── Summary ──────────────────────────────────────────────────
TOTAL_MS=$(( ($(date +%s%N) - START) / 1000000 ))
echo ""
echo "============================================================"
if [ $ERRORS -eq 0 ]; then
    echo "RESULT: ALL CHECKS COMPLETE (${TOTAL_MS}ms)"
else
    echo "RESULT: $ERRORS CHECK(S) FAILED (${TOTAL_MS}ms)"
fi
echo "============================================================"
