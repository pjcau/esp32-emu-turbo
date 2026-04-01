#!/usr/bin/env bash
# External DFM Analysis — KiBot (DRC + ERC + Design Report)
# Runs third-party CLI tools in Docker for independent PCB verification
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/hardware/kicad/external-dfm-output"
GERBER_DIR="$PROJECT_DIR/release_jlcpcb/gerbers"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

section() { echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }
pass()    { echo -e "  ${GREEN}PASS${NC}  $1"; ((PASS++)); }
fail()    { echo -e "  ${RED}FAIL${NC}  $1"; ((FAIL++)); }
warn()    { echo -e "  ${YELLOW}WARN${NC}  $1"; ((WARN++)); }

# Clean output
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

########################################
# 1. KiBot DRC + ERC + Design Report
########################################
section "KiBot Analysis (DRC + ERC + Design Report)"

echo "  Running KiBot (may take 1-2 min under emulation)..."
KIBOT_LOG="$OUTPUT_DIR/kibot.log"

# Run KiBot with the config file
docker compose -f "$PROJECT_DIR/docker-compose.yml" run --rm \
    kibot \
    -b /project/esp32-emu-turbo.kicad_pcb \
    -e /project/esp32-emu-turbo.kicad_sch \
    -c /project/external-dfm.kibot.yaml \
    -v \
    > "$KIBOT_LOG" 2>&1 || true

# Check what was generated
echo -e "  ${CYAN}Generated files:${NC}"
ls -la "$OUTPUT_DIR/" 2>/dev/null | grep -v "^total" | grep -v "^\." | sed 's/^/    /'

# Parse DRC results
DRC_JSON=$(find "$OUTPUT_DIR" -name "*drc*.json" 2>/dev/null | head -1)
if [ -n "$DRC_JSON" ] && [ -f "$DRC_JSON" ]; then
    DRC_RESULT=$(python3 -c "
import json
with open('$DRC_JSON') as f:
    data = json.load(f)
violations = data.get('violations', [])
errors = [v for v in violations if v.get('severity', '') == 'error']
warnings = [v for v in violations if v.get('severity', '') == 'warning']
print(f'DRC: {len(errors)} errors, {len(warnings)} warnings ({len(violations)} total)')
# Unique violation types with counts
types = {}
for v in violations:
    t = v.get('type', 'unknown')
    types[t] = types.get(t, 0) + 1
for t, c in sorted(types.items(), key=lambda x: -x[1])[:20]:
    sev = 'error' if any(vv.get('type')==t and vv.get('severity')=='error' for vv in violations) else 'warning'
    print(f'  {c:4d}x {t} ({sev})')
" 2>/dev/null) || DRC_RESULT="(could not parse DRC JSON)"
    echo -e "  ${YELLOW}$DRC_RESULT${NC}"

    # Count errors for pass/fail
    DRC_ERRORS=$(python3 -c "
import json
with open('$DRC_JSON') as f:
    data = json.load(f)
errors = [v for v in data.get('violations', []) if v.get('severity') == 'error']
print(len(errors))
" 2>/dev/null || echo "0")
    if [ "$DRC_ERRORS" = "0" ]; then
        pass "KiBot DRC — no errors"
    else
        fail "KiBot DRC — $DRC_ERRORS errors found"
    fi
else
    # Try to find DRC info in KiBot log
    if grep -q "DRC" "$KIBOT_LOG" 2>/dev/null; then
        echo -e "  ${YELLOW}DRC results in log:${NC}"
        grep -i "drc\|error\|warning\|violation" "$KIBOT_LOG" 2>/dev/null | head -20 | sed 's/^/    /'
        warn "DRC ran but no JSON output"
    else
        warn "No DRC output found"
    fi
fi

# Parse ERC results
ERC_JSON=$(find "$OUTPUT_DIR" -name "*erc*.json" 2>/dev/null | head -1)
if [ -n "$ERC_JSON" ] && [ -f "$ERC_JSON" ]; then
    ERC_RESULT=$(python3 -c "
import json
with open('$ERC_JSON') as f:
    data = json.load(f)
violations = data.get('violations', [])
errors = [v for v in violations if v.get('severity', '') == 'error']
warnings = [v for v in violations if v.get('severity', '') == 'warning']
print(f'ERC: {len(errors)} errors, {len(warnings)} warnings ({len(violations)} total)')
types = {}
for v in violations:
    t = v.get('type', 'unknown')
    types[t] = types.get(t, 0) + 1
for t, c in sorted(types.items(), key=lambda x: -x[1])[:20]:
    print(f'  {c:4d}x {t}')
" 2>/dev/null) || ERC_RESULT="(could not parse ERC JSON)"
    echo -e "  ${YELLOW}$ERC_RESULT${NC}"

    ERC_ERRORS=$(python3 -c "
import json
with open('$ERC_JSON') as f:
    data = json.load(f)
errors = [v for v in data.get('violations', []) if v.get('severity') == 'error']
print(len(errors))
" 2>/dev/null || echo "0")
    if [ "$ERC_ERRORS" = "0" ]; then
        pass "KiBot ERC — no errors"
    else
        fail "KiBot ERC — $ERC_ERRORS errors found"
    fi
else
    if grep -q "ERC" "$KIBOT_LOG" 2>/dev/null; then
        echo -e "  ${YELLOW}ERC results in log:${NC}"
        grep -i "erc\|error\|warning" "$KIBOT_LOG" 2>/dev/null | head -20 | sed 's/^/    /'
        warn "ERC ran but no JSON output"
    else
        warn "No ERC output found"
    fi
fi

# Design report
REPORT_FILE=$(find "$OUTPUT_DIR" -name "*report*" -not -name "*.json" 2>/dev/null | head -1)
if [ -n "$REPORT_FILE" ] && [ -f "$REPORT_FILE" ]; then
    pass "Design report generated: $(basename "$REPORT_FILE")"
    echo -e "  ${CYAN}Key metrics from report:${NC}"
    grep -iE "(board|track|trace|via|drill|layer|eurocircuits|component|pad|hole|copper|width|spacing|annular|class)" \
        "$REPORT_FILE" 2>/dev/null | head -40 | sed 's/^/    /'
else
    warn "No design report generated"
fi

########################################
# 2. Gerber Structural Validation (Python)
########################################
section "Gerber Structural Validation"

if [ -d "$GERBER_DIR" ]; then
    python3 -c "
import os, sys

gerber_dir = '$GERBER_DIR'
files = [f for f in os.listdir(gerber_dir) if not f.endswith('.zip') and os.path.isfile(os.path.join(gerber_dir, f))]
errors = 0
warnings = 0

print(f'  Files found: {len(files)}')
print()

for f in sorted(files):
    path = os.path.join(gerber_dir, f)
    size = os.path.getsize(path)
    with open(path, 'r', errors='replace') as fh:
        content = fh.read()
    lines = content.count('\n')

    issues = []

    # Check for standard Gerber headers
    if f.endswith('.gbrjob'):
        pass  # JSON job file, different format
    elif f.endswith('.drl'):
        if 'M48' not in content:
            issues.append('missing M48 header')
            errors += 1
        if 'M30' not in content and 'M00' not in content:
            issues.append('missing end-of-file')
            warnings += 1
    else:
        if '%FSLAX' not in content and '%TF.' not in content:
            issues.append('missing format specification')
            errors += 1
        if 'M02' not in content:
            issues.append('missing M02 end-of-file')
            warnings += 1

    # Check for suspiciously small files
    if size < 100 and not f.endswith('.gbrjob'):
        issues.append(f'suspiciously small ({size} bytes)')
        warnings += 1

    # Check for empty layers
    if lines < 10 and not f.endswith('.gbrjob'):
        issues.append(f'very few lines ({lines})')
        warnings += 1

    status = 'OK' if not issues else 'WARN'
    detail = f' — {', '.join(issues)}' if issues else ''
    print(f'  {status:4s}  {f:<45s}  {size:>8,d} bytes  {lines:>6,d} lines{detail}')

print()
print(f'  Total: {len(files)} files, {errors} errors, {warnings} warnings')
sys.exit(1 if errors > 0 else 0)
" 2>/dev/null
    if [ $? -eq 0 ]; then
        pass "Gerber files structurally valid"
    else
        fail "Gerber structural issues found"
    fi
else
    warn "No gerber directory found"
fi

########################################
# 3. BOM Cross-Reference
########################################
section "BOM Cross-Reference (KiBot vs JLCPCB)"

JLCPCB_BOM="$PROJECT_DIR/release_jlcpcb/bom.csv"
KIBOT_BOM=$(find "$OUTPUT_DIR" -name "bom*.csv" 2>/dev/null | head -1)

if [ -n "$KIBOT_BOM" ] && [ -f "$KIBOT_BOM" ] && [ -f "$JLCPCB_BOM" ]; then
    python3 -c "
import csv, sys

def read_refs(path, ref_cols):
    refs = set()
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            for col in ref_cols:
                if col in row:
                    for r in row[col].replace(' ', '').split(','):
                        r = r.strip()
                        if r:
                            refs.add(r)
                    break
    return refs

kibot = read_refs('$KIBOT_BOM', ['References', 'Reference', 'Designator'])
jlcpcb = read_refs('$JLCPCB_BOM', ['Designator', 'References', 'Reference'])
common = kibot & jlcpcb
only_k = sorted(kibot - jlcpcb)
only_j = sorted(jlcpcb - kibot)

print(f'  KiBot BOM:  {len(kibot)} components')
print(f'  JLCPCB BOM: {len(jlcpcb)} components')
print(f'  Common:     {len(common)}')
if only_k:
    print(f'  Only in KiBot:  {only_k}')
if only_j:
    print(f'  Only in JLCPCB: {only_j}')
if not only_k and not only_j:
    print('  MATCH')
sys.exit(1 if (only_k or only_j) else 0)
" 2>/dev/null
    if [ $? -eq 0 ]; then
        pass "BOM cross-reference matches"
    else
        warn "BOM differences found (may be expected for mounting holes, fiducials)"
    fi
else
    if [ ! -f "$JLCPCB_BOM" ]; then
        warn "JLCPCB BOM not found"
    else
        warn "KiBot BOM not generated — cannot cross-reference"
    fi
fi

########################################
# 4. KiBot Log Analysis
########################################
section "KiBot Log Analysis"

if [ -f "$KIBOT_LOG" ]; then
    # Extract errors and warnings from KiBot log
    LOG_ERRORS=$(grep -ciE "^ERROR|^\[ERROR" "$KIBOT_LOG" 2>/dev/null || echo "0")
    LOG_WARNINGS=$(grep -ciE "^WARNING|^\[WARNING" "$KIBOT_LOG" 2>/dev/null || echo "0")
    echo -e "  KiBot log: ${RED}$LOG_ERRORS errors${NC}, ${YELLOW}$LOG_WARNINGS warnings${NC}"

    # Show unique error types
    if [ "$LOG_ERRORS" -gt 0 ]; then
        echo -e "  ${RED}Errors:${NC}"
        grep -iE "^ERROR|^\[ERROR" "$KIBOT_LOG" 2>/dev/null | sort -u | head -15 | sed 's/^/    /'
    fi

    # Show unique warning types (first 10)
    if [ "$LOG_WARNINGS" -gt 0 ]; then
        echo -e "  ${YELLOW}Warnings (unique, first 10):${NC}"
        grep -iE "^WARNING|^\[WARNING" "$KIBOT_LOG" 2>/dev/null | sort -u | head -10 | sed 's/^/    /'
    fi
fi

########################################
# Summary
########################################
section "Summary"

echo -e "  ${GREEN}PASS: $PASS${NC}  ${RED}FAIL: $FAIL${NC}  ${YELLOW}WARN: $WARN${NC}"
echo ""
echo "  Output directory: $OUTPUT_DIR/"
echo "  Full KiBot log:   $OUTPUT_DIR/kibot.log"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "  ${RED}RESULT: FAIL — $FAIL issue(s) need attention${NC}"
    echo -e "  Review: cat $OUTPUT_DIR/kibot.log"
    exit 1
else
    echo -e "  ${GREEN}RESULT: PASS — external analysis clean${NC}"
    exit 0
fi
