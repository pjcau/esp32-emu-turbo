---
name: drc-native
model: claude-opus-4-7
description: Run native KiCad DRC with smart violation filtering, delta tracking, and fix suggestions
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# Native KiCad DRC with Smart Analysis

Run kicad-cli DRC and analyze violations with smart filtering, delta tracking, and fix suggestions.

## Step 1: Run KiCad Native DRC

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
kicad-cli pcb drc \
    --output /tmp/drc-report.json \
    --format json \
    --severity-all \
    --units mm \
    --all-track-errors \
    hardware/kicad/esp32-emu-turbo.kicad_pcb
```

## Step 2: Smart Analysis

```bash
python3 scripts/drc_native.py /tmp/drc-report.json
```

## Step 3: Review Results

The script categorizes violations into:
- **Known-acceptable**: Expected violations from the generated PCB (nets not assigned to pads)
- **Real issues**: Actual design problems that need fixing
- **New since baseline**: Violations that appeared since the last saved baseline

## Step 4: Fix Issues

For each real issue, the script maps it to the source file that controls it:

| Violation Type | Source File | Suggested Fix |
|---|---|---|
| `clearance` | `scripts/generate_pcb/routing.py` | Increase trace spacing or move traces apart |
| `copper_edge_clearance` | `scripts/generate_pcb/routing.py` | Move traces away from board edge or FPC slot |
| `silk_over_copper` | `scripts/generate_pcb/board.py` | Move silkscreen text to Fab layer |
| `silk_overlap` | `scripts/generate_pcb/board.py` | Reduce text size or reposition labels |
| `silk_edge_clearance` | `scripts/generate_pcb/board.py` | Move silkscreen text away from board edge |
| `track_width` | `scripts/generate_pcb/routing.py` | Increase trace width constants |
| `via_annular_ring` | `scripts/generate_pcb/primitives.py` | Increase via size or reduce drill diameter |
| `unconnected_items` | `scripts/generate_pcb/routing.py` | Add missing trace connection |
| `min_copper_clearance` | `scripts/generate_pcb/routing.py` | Increase clearance between copper elements |

## Step 5: Update Baseline (optional)

After fixing issues or accepting the current state, save a new baseline:

```bash
python3 scripts/drc_native.py /tmp/drc-report.json --update-baseline
```

## Key Differences from /check and /verify

- `/verify`: Uses custom Python DRC checks (15 tests)
- `/check`: Full pipeline (generate -> DRC -> render -> gerbers)
- `/drc-native`: Focused DRC-only with smart filtering, delta tracking, and fix mapping

## Key Files

- `scripts/drc_native.py` -- Smart DRC analysis wrapper
- `scripts/drc_baseline.json` -- Violation baseline (auto-generated)
- `hardware/kicad/esp32-emu-turbo.kicad_pcb` -- PCB file to check
