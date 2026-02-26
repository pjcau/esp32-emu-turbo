---
name: fix-rotation
description: Investigate and fix JLCPCB CPL rotation for a component using mathematical pin alignment analysis
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Write, Edit
argument-hint: <REF> (e.g. U5)
---

# Component Rotation Investigation

Mathematically analyze and fix the JLCPCB CPL rotation for a component.

**Argument**: Component reference designator (e.g., `U5`).

## Steps

### 1. Gather component data

Read these files to collect component info:

- **BOM**: `release_jlcpcb/bom.csv` — get LCSC part number and footprint
- **CPL**: `release_jlcpcb/cpl.csv` — get current position, rotation, layer
- **Footprint def**: `scripts/generate_pcb/footprints.py` — get pad positions and sizes
- **Board placement**: `scripts/generate_pcb/board.py` — get placement (x, y, rot, layer)
- **JLCPCB export**: `scripts/generate_pcb/jlcpcb_export.py` — get current override/correction

### 2. Compute gerber pad positions

For each pad in the footprint:
1. Start with local pad coordinates from `footprints.py`
2. Apply pre-rotation (if component has non-zero placement rotation)
3. Apply B.Cu X-mirror (negate X if bottom layer)
4. Add placement center (x, y) to get absolute board position

Verify by reading actual pad positions from `hardware/kicad/esp32-emu-turbo.kicad_pcb`.

### 3. Define standard model pin positions

For common packages:
- **SOP-16 (SOIC-16W)**: pins 1-8 on left (x=-4.65), pins 9-16 on right (x=+4.65), pitch 1.27mm
- **ESOP-8**: pins 1-4 on left, pins 5-8 on right, pitch 1.27mm, exposed pad center
- **SOT-223**: 3 signal pins + 1 tab
- **USB-C-16P**: see datasheet for pin layout

### 4. Test all 4 rotations

For each JLCPCB CPL rotation (0, 90, 180, 270):

**JLCPCB convention (bottom-side)**:
1. Start with standard model pin positions
2. Y-mirror: negate X (viewing from bottom)
3. CW rotation by angle: `x' = x*cos(a) + y*sin(a)`, `y' = -x*sin(a) + y*cos(a)`
4. Add CPL center position

Compare transformed model positions with gerber pad positions. Compute max error.

Print an ASCII table:

```
Rotation | Max Error | Pin 1 Match | Status
---------|-----------|-------------|-------
   0     | 9.1mm     | NO          | MISMATCH
  90     | 0.0mm     | YES         | ALIGN  <-- CPL
 180     | 9.1mm     | NO          | MISMATCH
 270     | 0.0mm     | YES         | ALIGN (mirrored)
```

### 5. Cross-validate with known-working component

Use SW11 (bottom, rot=90) as reference:
- SW11 footprint has 4 pads at known positions
- Its CPL rotation=90 is confirmed working
- Verify our JLCPCB convention math matches SW11

### 6. Generate CPL variants

Create 4 test CPL files:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
for rot in 0 90 180 270; do
    cp release_jlcpcb/cpl.csv release_jlcpcb/cpl_${REF,,}_rot${rot}.csv
    # Replace the rotation value for this component
done
```

### 7. Apply recommended fix

Update `scripts/generate_pcb/jlcpcb_export.py`:

```python
_JLCPCB_ROT_OVERRIDES = {
    "REF": RECOMMENDED_ROTATION,
}
```

Then regenerate: `python3 -m scripts.generate_pcb hardware/kicad`

### 8. Update verification test

Update `scripts/verify_dfm_v2.py` to expect the new rotation value.

## Key Files

- `scripts/generate_pcb/jlcpcb_export.py` — `_JLCPCB_ROT_OVERRIDES`, `_JLCPCB_POS_CORRECTIONS`
- `scripts/generate_pcb/footprints.py` — `get_pads()`, `_pre_rotate_element()`, `_mirror_pad_x()`
- `scripts/generate_pcb/board.py` — `_component_placeholders()`
- `scripts/verify_dfm_v2.py` — `test_u5_pin_alignment()`
- `release_jlcpcb/cpl.csv` — Current CPL

## JLCPCB Rotation Convention

For bottom-side components, JLCPCB 3D viewer applies:
1. **Y-mirror** (negate X coordinate) — views the board from bottom
2. **CW rotation** by CPL rotation angle

Our generic formula:
```python
rot = (rot - 180) % 360         # mirror correction for bottom
rot = (rot + correction) % 360  # per-footprint DB correction
```

Per-footprint corrections (JLCKicadTools DB):
- SOP-*: +270   |  SOIC-*: +270
- SOT-23: -90   |  ESOP-*: +180 (default)
- QFP/QFN: +270 |  Crystal: +180
