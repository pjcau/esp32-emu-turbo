---
name: jlcpcb-check
model: claude-opus-4-7
description: Investigate JLCPCB 3D model alignment for a component (rotation, position, pin mapping)
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, WebFetch, WebSearch
argument-hint: <REF or LCSC_PART> (e.g. U5, C5122557)
---

# JLCPCB Component Alignment Investigation

Investigate and fix JLCPCB 3D model alignment issues for a specific component.

**Argument**: Component reference (e.g., `U5`) or LCSC part number (e.g., `C5122557`).

## Steps

### 1. Identify the component

Look up the component in the BOM:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
grep "$ARGUMENTS" release_jlcpcb/bom.csv
```

Extract: reference designator, LCSC part number, footprint name.

### 2. Get our pad positions from the PCB

Read the component's footprint definition from `scripts/generate_pcb/footprints.py` and its placement from `scripts/generate_pcb/board.py`. Determine:
- Footprint center position (x, y) on the board
- Pad positions relative to center
- Rotation applied at placement
- Layer (F.Cu or B.Cu)

Verify by checking the actual `.kicad_pcb` file:

```bash
grep -A 50 'footprint.*COMPONENT_FOOTPRINT' hardware/kicad/esp32-emu-turbo.kicad_pcb | head -80
```

### 3. Get our CPL data

```bash
grep "$ARGUMENTS" release_jlcpcb/cpl.csv
```

Note the current Mid X, Mid Y, Rotation, and Layer values.

### 4. Fetch JLCPCB/EasyEDA model data

Search for the LCSC part number on JLCPCB/EasyEDA to understand the 3D model orientation:

1. Search web for: `LCSC <part_number> EasyEDA 3D model pin orientation`
2. Fetch the EasyEDA component page: `https://easyeda.com/component/<LCSC_PART>`
3. Look for model pin 1 location, body orientation, and coordinate system

### 5. Mathematical rotation analysis

For all 4 JLCPCB CPL rotations (0, 90, 180, 270), compute:

**JLCPCB rotation convention (bottom-side):**
1. Y-mirror: negate X coordinate of each pin
2. CW rotation by CPL rotation angle

Compare model pin positions after transform with our gerber pad positions. Report alignment error for each rotation.

### 6. Cross-reference with known-working components

Compare the rotation correction approach with known-working components:
- **SW11** (SW-SMD-5.1x5.1, bottom, rot=90): CPL rotation should produce correct alignment
- **U1** (ESP32, bottom, rot=0): confirmed working with position correction +3.62mm Y
- **U2** (IP5306, ESOP-8, bottom, rot=0): check alignment

### 7. Generate CPL variants

Create 4 CPL variants with different rotations for the target component:

```bash
for rot in 0 90 180 270; do
    sed "s/^$REF,\(.*\),\(.*\),\(.*\),\(.*\),[0-9]*,/$REF,\1,\2,\3,\4,$rot,/" release_jlcpcb/cpl.csv > release_jlcpcb/cpl_${ref}_rot${rot}.csv
done
```

### 8. Recommend fix

Based on the analysis:
- Report which CPL rotation aligns best
- If none align, investigate position correction (origin offset)
- Update `scripts/generate_pcb/jlcpcb_export.py`:
  - `_JLCPCB_ROT_OVERRIDES` for rotation fixes
  - `_JLCPCB_POS_CORRECTIONS` for position fixes

## Key Files

- `scripts/generate_pcb/jlcpcb_export.py` — JLCPCB rotation/position corrections
- `scripts/generate_pcb/footprints.py` — Footprint pad definitions
- `scripts/generate_pcb/board.py` — Component placement positions
- `release_jlcpcb/bom.csv` — BOM with LCSC part numbers
- `release_jlcpcb/cpl.csv` — Current CPL
- `hardware/kicad/esp32-emu-turbo.kicad_pcb` — Actual PCB file

## JLCPCB Rotation Convention Reference

For **bottom-side** components, JLCPCB applies:
1. **Y-mirror** (negate X) — viewing from bottom
2. **CW rotation** by the CPL rotation angle

The generic formula in our codebase:
```python
rot = (rot - 180) % 360  # mirror correction
rot = (rot + correction) % 360  # per-footprint DB correction
```

Per-footprint corrections (from JLCKicadTools community DB):
- SOP-*: +270 degrees
- SOIC-*: +270 degrees
- SOT-23: -90 degrees
- ESOP-*: +180 degrees (default)
