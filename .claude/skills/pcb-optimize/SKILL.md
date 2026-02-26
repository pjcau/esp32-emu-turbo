---
name: pcb-optimize
description: Analyze PCB layout and suggest optimizations (traces, copper balance, thermal, vias)
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# PCB Layout Optimization Analysis

Analyze the generated `.kicad_pcb` file for layout quality and suggest optimizations across five categories: trace length, copper balance, thermal vias, via count, and crosstalk risk.

## Steps

### 1. Run the optimization analysis

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/pcb_optimize.py
```

Optionally pass a custom PCB path:

```bash
python3 scripts/pcb_optimize.py path/to/custom.kicad_pcb
```

### 2. Review the scored report

The script produces a report with five modules, each scored 0-20 (total 100):

| Module | What it checks | Threshold |
|--------|---------------|-----------|
| Trace Length | Total length per net, single segment length | >80mm net, >40mm segment |
| Copper Balance | F.Cu vs B.Cu trace distribution | >50% difference |
| Thermal Vias | GND vias near power ICs (IP5306, AMS1117, PAM8403) | min 3 vias within 5mm |
| Via Optimization | Vias per net count | >4 vias/net |
| Parallel Traces | Crosstalk risk between data signals | gap < 3x trace width |

### 3. Fix identified issues

Based on the report, edit the routing or board layout:

```bash
# Edit routing traces
$EDITOR scripts/generate_pcb/routing.py

# Edit component placement
$EDITOR scripts/generate_pcb/board.py
```

### 4. Regenerate and re-analyze

```bash
python3 -m scripts.generate_pcb hardware/kicad
python3 scripts/pcb_optimize.py
```

Repeat until the score is satisfactory.

## Summary Report

After running the analysis, present results as:

| Module | Score | Issues | Status |
|--------|-------|--------|--------|
| Trace Length | ?/20 | ? flags | OK/WARN |
| Copper Balance | ?/20 | F.Cu ?% / B.Cu ?% | OK/WARN |
| Thermal Vias | ?/20 | ? ICs under-viad | OK/WARN |
| Via Optimization | ?/20 | ? nets with excess vias | OK/WARN |
| Parallel Traces | ?/20 | ? crosstalk pairs | OK/WARN |
| **Overall** | **?/100** | | |

## Key Files

- `scripts/pcb_optimize.py` -- PCB layout optimization analyzer
- `scripts/generate_pcb/routing.py` -- Trace routing definitions
- `scripts/generate_pcb/board.py` -- Component placement and board generation
- `scripts/generate_pcb/primitives.py` -- Net IDs and PCB element helpers
- `scripts/drc_check.py` -- DRC check (complementary, manufacturing rules)
- `hardware/kicad/esp32-emu-turbo.kicad_pcb` -- Generated PCB file (analysis target)
