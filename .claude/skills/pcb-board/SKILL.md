---
name: pcb-board
description: Board setup operations — dimensions, outline, layers, mounting holes, text (KiCAD MCP tools 5-13)
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: [info | outline | layers | holes | text]
---

# Board Setup Operations

Map KiCAD MCP board setup tools to our project's programmatic PCB generation infrastructure.

## Overview

Board setup is managed across multiple files in `scripts/generate_pcb/`. The board is generated programmatically -- never edited manually in KiCad.

### Current Board Specs

| Property | Value |
|----------|-------|
| Dimensions | 160 x 75 mm |
| Layer count | 4 (F.Cu, In1.Cu, In2.Cu, B.Cu) |
| Thickness | 1.6 mm |
| Corner radius | 6 mm |
| Mounting holes | 6x M2.5 |
| FPC slot cutout | 3 x 24 mm at center-right |

### Layer Stack

| Layer | Name | Purpose |
|-------|------|---------|
| 0 | F.Cu | Front copper -- face buttons + charging LEDs |
| 4 | In1.Cu | Inner layer 1 -- GND plane |
| 6 | In2.Cu | Inner layer 2 -- +3V3/+5V power planes |
| 2 | B.Cu | Back copper -- all electronics, ICs, connectors |

## Steps

1. Depending on the argument:

   - **`info`**: Show board dimensions, layer stack, and stats:
     ```bash
     cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -c "
     from scripts.generate_pcb import board
     print(f'Board: {board.BOARD_W} x {board.BOARD_H} mm')
     print(f'Corner radius: {board.CORNER_R} mm')
     print(f'Center: ({board.CX}, {board.CY})')
     print(f'Mounting holes (enclosure coords): {board.MOUNT_HOLES_ENC}')
     print(f'FPC slot: {board.FPC_SLOT_W}x{board.FPC_SLOT_H}mm at enc{board.FPC_SLOT_ENC}')
     print(f'Display area: {board.DISPLAY_W}x{board.DISPLAY_H}mm')
     "
     ```

   - **`outline`**: Edit board outline in `scripts/generate_pcb/board.py`:
     - Function: `_board_outline()` (line 117)
     - Controls: `BOARD_W`, `BOARD_H`, `CORNER_R` constants
     - Includes the FPC slot cutout defined by `FPC_SLOT_ENC`, `FPC_SLOT_W`, `FPC_SLOT_H`

   - **`layers`**: View or edit the 4-layer stack:
     - Layer definitions: `layers_4layer()` function in `scripts/generate_pcb/primitives.py` (line 33)
     - Layer setup (design rules): `setup_4layer()` function in `scripts/generate_pcb/primitives.py` (line 62)

   - **`holes`**: Edit mounting hole positions:
     - Defined in `MOUNT_HOLES_ENC` in `scripts/generate_pcb/board.py` (line 39)
     - 6 positions in enclosure coordinates: `(-70, 30.5), (70, 30.5), (-70, -30.5), (70, -30.5), (-25, 0), (25, 0)`
     - Converted to PCB coordinates via `enc_to_pcb()`

   - **`text`**: Edit board text and silkscreen labels:
     - Function: `_silkscreen_labels()` in `scripts/generate_pcb/board.py` (line 167)
     - Includes project name, version, component labels

2. After changes, regenerate the PCB:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -m scripts.generate_pcb hardware/kicad
```

3. Verify with DRC:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 scripts/drc_check.py
```

## Key Files

| File | Purpose |
|------|---------|
| `scripts/generate_pcb/board.py` | Board outline (`_board_outline`, line 117), mounting holes (`MOUNT_HOLES_ENC`, line 39), text labels (`_silkscreen_labels`, line 167), component placements |
| `scripts/generate_pcb/primitives.py` | Layer stack (`layers_4layer`, line 33), board setup (`setup_4layer`, line 62), header, S-expression generators |
| `scripts/generate_pcb/routing.py` | References board geometry: `BOARD_W`, `BOARD_H`, FPC slot zone |
| `scripts/drc_check.py` | Design rule check |
| `scripts/verify_dfm_v2.py` | DFM verification |
| `hardware/kicad/esp32-emu-turbo.kicad_pcb` | Generated PCB output |

## Coordinate System

- **Enclosure coordinates**: Center origin `(0, 0)`, X+ = right, Y+ = up
- **PCB coordinates**: Top-left origin `(0, 0)`, X+ = right, Y+ = down (KiCad convention)
- Conversion: `enc_to_pcb(ex, ey)` returns `(CX + ex, CY - ey)` where CX=80.0, CY=37.5

## MCP Tool Mapping

| MCP Tool | Our Implementation |
|----------|-------------------|
| `set_board_size` | Edit `BOARD_W`, `BOARD_H` in `board.py` |
| `add_board_outline` | Edit `_board_outline()` in `board.py` |
| `add_layer` | Edit `layers_4layer()` in `primitives.py` |
| `set_active_layer` | N/A (generated, not interactive) |
| `get_layer_list` | Read `layers_4layer()` from `primitives.py` |
| `get_board_info` | Parse board dimensions/stats from `board.py` constants |
| `get_board_2d_view` | `kicad-cli pcb render --output /tmp/board.png hardware/kicad/esp32-emu-turbo.kicad_pcb` |
| `add_mounting_hole` | Edit `MOUNT_HOLES_ENC` list in `board.py` |
| `add_board_text` | Edit `_silkscreen_labels()` in `board.py` |

## Important Notes

- Never edit `hardware/kicad/esp32-emu-turbo.kicad_pcb` directly -- it is a generated file.
- Board dimensions are coupled with the enclosure design (`hardware/enclosure/enclosure.scad`). Changing board size requires updating the enclosure too.
- The FPC slot is a physical cutout in the board for the display ribbon cable. No copper, traces, or components may occupy that area.
- Inner layers (In1.Cu, In2.Cu) are primarily used as ground and power planes via `zone_fill()` in `routing.py`.
