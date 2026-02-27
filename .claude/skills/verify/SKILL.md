---
name: verify
description: Run the complete DFM and design verification suite for the PCB
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# DFM & Design Verification Suite

Run all verification scripts and produce a summary report.

## Steps

### 1. DFM Verification (21 tests)

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/verify_dfm_v2.py
```

Tests include:
- CPL position corrections (J1, SW_PWR, U1, U5)
- Silkscreen text on Fab layer (not SilkS)
- Mounting hole text on Fab
- C1/C2 spacing from U3 (>= 1.5mm gap)
- gr_text clearance from mounting holes (>= 6mm)
- Via annular ring (>= 0.175mm)
- Gerber zip file count (>= 12 files)
- U5 pin alignment analysis (informational)
- SOP-16 aperture verification
- KiCad DRC: copper_edge_clearance, hole_to_hole, silk issues
- Trace spacing regression guard (baseline 27)
- Via-to-via hole spacing (>= 0.25mm)
- Display stagger vs ESP32 pin midpoints

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

## Summary Report

After running all tests, summarize results in a table:

| Suite | Tests | Pass | Fail | Status |
|-------|-------|------|------|--------|
| DFM v2 | 21 | ? | ? | PASS/FAIL |
| DRC | ? | ? | ? | PASS/FAIL |
| Connectivity | ? | ? | ? | PASS/FAIL |
| Schematic sync | ? | ? | ? | PASS/FAIL |

Report any failures with details and suggested fixes.

## Key Files

- `scripts/verify_dfm_v2.py` — DFM verification (main)
- `scripts/drc_check.py` — Design rule check
- `scripts/test_pcb_connectivity.py` — Connectivity test
- `scripts/verify_schematic_pcb.py` — Schematic/PCB sync
- `scripts/short_circuit_analysis.py` — Short circuit analysis
