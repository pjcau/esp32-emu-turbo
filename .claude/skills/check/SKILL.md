---
name: check
description: Full PCB verification loop using local kicad-cli (DRC + 3D render + gerbers)
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
---

# Full PCB Check — Local kicad-cli Feedback Loop

Complete modify → generate → verify → render cycle using local tools. No JLCPCB upload needed.

## Pipeline

### Step 1: Generate PCB from Python specs

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -m scripts.generate_pcb hardware/kicad
```

### Step 2: Run KiCad DRC (Design Rules Check)

```bash
kicad-cli pcb drc \
    --output /tmp/drc-report.json \
    --format json \
    --severity-all \
    --units mm \
    --all-track-errors \
    hardware/kicad/esp32-emu-turbo.kicad_pcb
```

Parse the JSON output and summarize violations by type:

```python
import json
from collections import Counter
with open('/tmp/drc-report.json') as f:
    data = json.load(f)
types = Counter()
for v in data.get('violations', []):
    types[v['type']] += 1
for v in data.get('unconnected_items', []):
    types['unconnected'] += 1
for t, c in types.most_common():
    print(f"  {t:30s} {c:4d}")
```

**Known acceptable violations** (generated PCB has no net assignments on pads):
- `shorting_items` ~200: traces near unnetted pads (false positive — nets not assigned in generated PCB)
- `solder_mask_bridge` ~199: fine-pitch FPC/USB-C (expected, JLCPCB handles this)
- `hole_clearance` ~178: via-in-pad for buttons (intentional)
- `via_dangling` ~50: zone-connected vias (not dangling in practice)
- `track_dangling` ~24: zone-connected tracks

**Real violations to fix** (track these numbers — they should decrease):
- `clearance`: trace-to-pad spacing violations
- `copper_edge_clearance`: traces too close to board edge / FPC slot
- `silk_over_copper`: silkscreen text overlapping exposed copper
- `silk_edge_clearance`: silkscreen near board edge
- `silk_overlap`: overlapping silkscreen text

### Step 3: Render 3D views

```bash
mkdir -p /tmp/pcb-renders

# Top view (front side — buttons, LEDs, display area)
kicad-cli pcb render \
    --output /tmp/pcb-renders/top.png \
    --side top --width 2400 --height 1200 --quality basic \
    hardware/kicad/esp32-emu-turbo.kicad_pcb

# Bottom view (back side — ESP32, ICs, connectors)
kicad-cli pcb render \
    --output /tmp/pcb-renders/bottom.png \
    --side bottom --width 2400 --height 1200 --quality basic \
    hardware/kicad/esp32-emu-turbo.kicad_pcb

# Isometric view
kicad-cli pcb render \
    --output /tmp/pcb-renders/iso.png \
    --side top --width 2400 --height 1200 --quality basic \
    --perspective --rotate '-45,0,45' \
    hardware/kicad/esp32-emu-turbo.kicad_pcb
```

Read the rendered images to visually inspect the PCB layout.

### Step 4: Export gerbers + create ZIP

```bash
rm -rf hardware/kicad/gerbers && mkdir -p hardware/kicad/gerbers

kicad-cli pcb export gerbers \
    --output hardware/kicad/gerbers/ \
    --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
    --subtract-soldermask --use-drill-file-origin \
    hardware/kicad/esp32-emu-turbo.kicad_pcb

kicad-cli pcb export drill \
    --output hardware/kicad/gerbers/ \
    --format excellon --drill-origin plot \
    --excellon-units mm --generate-map --map-format gerberx2 \
    hardware/kicad/esp32-emu-turbo.kicad_pcb

cd hardware/kicad/gerbers && zip -j ../jlcpcb/gerbers.zip *.gtl *.g1 *.g2 *.gbl *.gto *.gbo *.gts *.gbs *.gtp *.gbp *.gm1 *.drl
```

### Step 5: Run custom DFM tests

```bash
python3 scripts/verify_dfm_v2.py
```

### Step 6: Copy to release

```bash
cp hardware/kicad/jlcpcb/bom.csv release_jlcpcb/bom.csv
cp hardware/kicad/jlcpcb/cpl.csv release_jlcpcb/cpl.csv
rm -rf release_jlcpcb/gerbers
cp -r hardware/kicad/gerbers release_jlcpcb/gerbers
cp hardware/kicad/jlcpcb/gerbers.zip release_jlcpcb/gerbers.zip
```

## Summary Report Format

After running all steps, present results as:

| Check | Result | Count/Detail |
|-------|--------|-------------|
| PCB generation | OK/FAIL | — |
| KiCad DRC clearance | X violations | (should be 0) |
| KiCad DRC copper_edge | X violations | (should be 0) |
| KiCad DRC silk issues | X violations | (should be 0) |
| Custom DFM tests | X/21 pass | — |
| 3D render top | [image] | visual check |
| 3D render bottom | [image] | visual check |

## Available kicad-cli commands reference

| Command | Purpose |
|---------|---------|
| `kicad-cli pcb drc` | Design Rules Check (JSON/report) |
| `kicad-cli pcb render` | 3D render to PNG (top/bottom/iso) |
| `kicad-cli pcb export gerbers` | Export Gerber files |
| `kicad-cli pcb export drill` | Export drill/Excellon files |
| `kicad-cli pcb export pos` | Export component position file |
| `kicad-cli pcb export svg` | Export layers to SVG |
| `kicad-cli pcb export pdf` | Export layers to PDF |
| `kicad-cli pcb export step` | Export 3D STEP model |
| `kicad-cli sch erc` | Schematic Electrical Rules Check |
