---
name: pcb-components
description: Component placement operations — place, move, rotate, align, array (KiCAD MCP tools 14-23)
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: [list | place <ref> | move <ref> <x> <y> | rotate <ref> <angle> | align]
---

# Component Placement Operations

Map KiCAD MCP component placement tools to our project's programmatic PCB generation.

## Overview

Component placement is managed in `scripts/generate_pcb/board.py` via the `_component_placeholders()` function (line 251+). All components are defined with reference designator, position (x, y), rotation, layer, footprint, and value. The board uses enclosure-center coordinates converted to PCB top-left origin via `enc_to_pcb(ex, ey)`.

Layout convention:
- **F.Cu (top)**: Face buttons (D-pad, ABXY, Start, Select, Menu) + charging LEDs
- **B.Cu (bottom)**: All electronics (ESP32, ICs, connectors, speaker, power, passives) + L/R shoulder buttons

## Steps

1. Read current placements:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -c "
from scripts.generate_pcb.board import _component_placeholders
comp_str, placements = _component_placeholders()
for ref, (x, y, rot, layer) in sorted(placements.items()):
    print(f'{ref:8s}  x={x:7.2f}  y={y:7.2f}  rot={rot:5.1f}  {layer}')
"
```

2. Depending on the argument:

   - **`list`**: Show all components with positions, rotations, and layers (use the command above).

   - **`place <ref>`**: Add a new component entry to `_component_placeholders()` in `scripts/generate_pcb/board.py`. Each entry needs:
     - Reference designator (e.g., `R15`)
     - Position in enclosure coordinates via `enc_to_pcb(ex, ey)`
     - Rotation angle in degrees
     - Layer (`F.Cu` or `B.Cu`)
     - Footprint function from `scripts/generate_pcb/footprints.py`
     - Net assignments for each pad

   - **`move <ref> <x> <y>`**: Change the `enc_to_pcb(ex, ey)` coordinates for the component in `board.py`.

   - **`rotate <ref> <angle>`**: Change the rotation value for the component in `board.py`. Note: JLCPCB CPL rotation corrections are in `scripts/generate_pcb/jlcpcb_export.py`.

   - **`align`**: Check component alignment against the grid and ensure no overlapping courtyard areas.

3. After changes, regenerate the PCB:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -m scripts.generate_pcb hardware/kicad
```

4. Verify DFM constraints:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 scripts/verify_dfm_v2.py
```

## Key Files

| File | Purpose |
|------|---------|
| `scripts/generate_pcb/board.py` | Component placements (`_component_placeholders()` at line 251), board outline, mounting holes |
| `scripts/generate_pcb/footprints.py` | Footprint pad definitions (geometry, pin assignments) |
| `scripts/generate_pcb/pad_positions.py` | Pad position computation (`get_all_pad_positions()`, `get_pad()`) |
| `scripts/generate_pcb/jlcpcb_export.py` | CPL rotation corrections for JLCPCB assembly |
| `hardware/kicad/esp32-emu-turbo.kicad_pcb` | Generated PCB output |

## Coordinate System

- **Enclosure coordinates**: Center origin, Y+ = up. Used in `board.py` constants (e.g., `DPAD_ENC = (-62, 5)`).
- **PCB coordinates**: Top-left origin, Y+ = down (KiCad convention). Converted via `enc_to_pcb(ex, ey)`.
- Board dimensions: 160 x 75 mm. Center at (80.0, 37.5).

## MCP Tool Mapping

| MCP Tool | Our Implementation |
|----------|-------------------|
| `place_component` | Add entry to `_component_placeholders()` in `board.py` |
| `move_component` | Edit `(x, y)` coordinates in `board.py` |
| `rotate_component` | Edit rotation value in `board.py` |
| `delete_component` | Remove entry from `_component_placeholders()` in `board.py` |
| `edit_component` | Modify ref/value/footprint in `board.py` |
| `get_component_properties` | Read `board.py` + `footprints.py` for a specific reference |
| `get_component_list` | Parse all placements from `_component_placeholders()` |
| `place_component_array` | Add multiple entries with calculated positions in `board.py` |
| `align_components` | Check/fix component alignment in `board.py` |
| `duplicate_component` | Copy entry with new reference designator in `board.py` |

## Important Notes

- Never edit `hardware/kicad/esp32-emu-turbo.kicad_pcb` directly -- it is a generated file.
- Mounting holes are defined separately in `MOUNT_HOLES_ENC` (6x M2.5 holes).
- The FPC slot cutout at `enc(47, 2)` is a 3x24mm no-go zone -- do not place components there.
- L/R shoulder buttons are on B.Cu, rotated 90 degrees, aligned to the top edge.
