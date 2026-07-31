---
name: verify
model: claude-opus-5
description: Run the complete DFM and design verification suite for the PCB
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# DFM & Design Verification Suite (124 DFM + 9 DFA tests)

Run all verification scripts and produce a summary report.

## Steps

### 1. DFM Verification (124 tests)

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/verify_dfm_v2.py
```

Tests include:
- CPL position corrections (J1, SW_PWR, U1, U5)
- Silkscreen text on Fab layer (not SilkS)
- Mounting hole text on Fab
- SY8089 buck (U3) hot-loop geometry: C2 absent from the CPL, C1 (C_IN) tight
  to U3, C30 (C_OUT) tight to L2. **C2 no longer exists** — the old "C1/C2
  spacing" test was replaced when the AMS1117 LDO became the buck
- gr_text clearance from mounting holes (>= 6mm)
- Via annular ring (>= 0.075mm, JLCPCB min)
- Gerber zip file count (>= 12 files)
- U5 pin alignment analysis (informational)
- SOP-16 aperture verification
- KiCad DRC: copper_edge_clearance, hole_to_hole, silk issues
- Trace spacing regression guard
- Via-to-via hole spacing (>= 0.25mm)
- Display stagger vs ESP32 pin midpoints
- Mounting hole trace clearance
- Drill-trace clearance (JLCPCB hole-cuts-trace prevention)
- Trace-pad different-net clearance (JLCPCB net assignment check)
- **Batch JLCPCB alignment** (7 ICs: rotation, position correction, pin-net assignment)

### 1b. DFA Verification (9 tests)

```bash
python3 scripts/verify_dfa.py
```

Tests include:
- BOM file presence and component counts
- CPL file presence and component positions
- Polarity-sensitive component verification

### 1c. Datasheet Physical Verification (29 tests)

```bash
python3 scripts/verify_datasheet.py
```

Cross-checks PCB component physical characteristics against datasheets:
- Pin count per component (ICs, connectors, passives, switches)
- Pad pitch (0.5mm, 1.27mm, 2.0mm etc.)
- Pad span / body dimensions (catches wrong package variants)
- NPTH positioning hole count and drill size
- THT drill sizes
- Datasheet PDF presence

### 2. Design Rule Check (JLCPCB rules)

```bash
python3 scripts/drc_check.py
```

Checks: trace width, via spacing, drill clearance, silkscreen width.

### 3. Electrical Connectivity

```bash
python3 scripts/test_pcb_connectivity.py
```

Verifies trace/pad/via graph connectivity for all nets.

### 4. Schematic-PCB Consistency

```bash
python3 scripts/verify_schematic_pcb.py
```

Checks footprint count, part values, net consistency between schematic and PCB.

### 5. Short Circuit Analysis (optional)

```bash
python3 scripts/short_circuit_analysis.py
```

Detects net connectivity conflicts and zone priority issues.

### 6. Gerber E-Test (release copper, not the design)

```bash
make verify-gerber-etest
```

Electrical test on the **release gerbers**: builds the copper graph from the
fabricated artwork and requires every net to be one piece of copper touching
no other net (e-test points on all nets, plated holes included). Catches
release-dir drift that design-side gates cannot see.

Also reports **ORPHAN dead copper**: any copper island that belongs to no
net — dead zone-fill fragments, forgotten artwork. NC pads are exempt
without an allowlist because they are exposed through the solder mask,
while dead copper is always mask-covered. Mutation-tested by
`test_gerber_etest.py` (M5 paints a 1 mm² blob and requires the ORPHAN
verdict).

### 7. Gate Coverage (mutation suite over the gates themselves)

```bash
make verify-gate-coverage   # ~2 min
```

Injects the 9 historical fault classes (missing CPL part, reprogrammed BOM
value, release netlist drift, firmware desync, ...) into a sandbox and fails
unless at least one gate catches each. This is the guard against gates that
never fire.

## Summary Report

After running all tests, summarize results in a table:

| Suite | Tests | Pass | Fail | Status |
|-------|-------|------|------|--------|
| DFM v2 | 124 | ? | ? | PASS/FAIL |
| DFA | 9 | ? | ? | PASS/FAIL |
| Datasheet | 29 | ? | ? | PASS/FAIL |
| DRC | ? | ? | ? | PASS/FAIL |
| Connectivity | ? | ? | ? | PASS/FAIL |
| Schematic sync | ? | ? | ? | PASS/FAIL |
| Gerber e-test | ? | ? | ? | PASS/FAIL |
| Gate coverage | 9 faults | ? | ? | PASS/FAIL |

Report any failures with details and suggested fixes.

## Key Files

- `scripts/verify_dfm_v2.py` — DFM verification (124 tests, includes JLCPCB alignment)
- `scripts/verify_dfa.py` — DFA verification (9 tests)
- `scripts/verify_datasheet.py` — Datasheet vs PCB physical verification (29 tests)
- `scripts/drc_check.py` — Design rule check
- `scripts/test_pcb_connectivity.py` — Connectivity test
- `scripts/verify_schematic_pcb.py` — Schematic/PCB sync
- `scripts/short_circuit_analysis.py` — Short circuit analysis
- `scripts/verify_gerber_etest.py` — E-test on release gerbers (net isolation on fabricated copper)
- `scripts/test_gate_coverage.py` — Mutation suite: 9 historical fault classes must each be caught by a gate
