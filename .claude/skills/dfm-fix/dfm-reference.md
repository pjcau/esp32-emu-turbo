# DFM Issue Reference — Known Patterns & Solutions

## Previously Fixed Issues (v1.0 → v1.8)

### Silkscreen-to-pad DANGER
**Problem**: Footprint Reference/Value text on SilkS layer overlaps SMD pads.
**Solution**: Move ALL footprint text to Fab layer (`F.Fab` / `B.Fab`).
**File**: `board.py` — `_component_placeholders()`, set `text_layer` to Fab for all footprints.

### Silkscreen-to-hole DANGER
**Problem**: Mounting hole Reference text on `F.SilkS` at (0,0) overlaps the hole.
**Solution**: Change mounting hole Reference layer to `F.Fab`.
**File**: `primitives.py` — `mounting_hole()`, line with `"F.SilkS"` → `"F.Fab"`.

### gr_text near mounting holes
**Problem**: Board labels (gr_text) placed within 6mm of mounting hole centers.
**Solution**: Move labels away from holes. Known hole positions: (10,7), (150,7), (10,68), (150,68), (55,37.5), (105,37.5).
**File**: `board.py` — `_silkscreen_labels()`.

### Component spacing (C1/C2 vs U3)
**Problem**: Capacitors C1/C2 too close to AMS1117 (SOT-223).
**Solution**: Increase Y offset from ±5mm to ±7mm from U3 center.
**Files**: `board.py` (placement), `routing.py` (C1_POS/C2_POS constants).

### Via annular ring
**Problem**: Via annular ring < 0.175mm (JLCPCB minimum).
**Solution**: All vias must have `(size - drill) / 2 >= 0.175mm`.
**File**: `routing.py` — check all `_via_net()` calls.

### SOP-16 merged pad apertures
**Problem**: KiCad's gerber export didn't rotate pad apertures for pre-rotated footprints.
**Solution**: `_pre_rotate_element()` in `footprints.py` swaps pad width/height for 90°/270° rotation.
**File**: `footprints.py` — `_pre_rotate_element()`.

### Soldermask bridge
**Problem**: Mask openings on close pads create solder bridges.
**Solution**: Reduce mask expansion or increase pad spacing. JLCPCB minimum mask bridge = 0.1mm.
**File**: `footprints.py` — pad definitions with `(solder_mask_margin ...)`.

### CPL position corrections
**Problem**: JLCPCB 3D model origin differs from footprint center.
**Solution**: Add offset in `_JLCPCB_POS_CORRECTIONS`. Only needed when model origin ≠ body center.
**File**: `jlcpcb_export.py`.
- U1 (ESP32): +(0, 3.62) — asymmetric pin layout
- J1 (USB-C): NO correction — symmetric body
- SW_PWR: NO correction — symmetric body

### CPL rotation corrections
**Problem**: JLCPCB 3D model default orientation doesn't match KiCad footprint.
**Solution**: Per-footprint DB correction (generic) or per-component override.
**File**: `jlcpcb_export.py` — `_JLCPCB_ROT_OVERRIDES` and `_JLCPCB_ROT_CORRECTIONS`.

## JLCPCB DFM Report Categories

| JLCPCB Code | Category | Our Source |
|-------------|----------|-----------|
| Silkscreen to Pad | Text overlap | board.py (text layer) |
| Silkscreen to Hole | Text overlap | primitives.py (mounting hole) |
| Solder Mask Bridge | Mask gap | footprints.py (pad mask margin) |
| Mask Exceeding Trace | Mask overflow | footprints.py / routing.py |
| Trace Clearance | Spacing | routing.py (trace separation) |
| Via Annular Ring | Via size | routing.py (via size/drill) |
| Component Spacing | Placement | board.py (coordinates) |
| Missing Solder Mask | No mask | footprints.py |
