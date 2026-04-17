---
name: pcb-routing
model: claude-opus-4-7
description: Trace routing operations — route, via, differential pair, copper pour, net classes (KiCAD MCP tools 24-31)
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: [info | trace <net> | via <x> <y> | diff-pair | zone | netclass]
---

# Trace Routing Operations

Map KiCAD MCP routing tools to our project's programmatic trace routing infrastructure.

## Overview

All routing is generated in `scripts/generate_pcb/routing.py`. Traces use **Manhattan (orthogonal) routing only** -- horizontal and vertical segments with L-shaped or Z-shaped paths. No diagonal lines.

### Trace Width Classes

| Constant | Width | Usage |
|----------|-------|-------|
| `W_PWR` | 0.5mm | Power: VBUS, +5V, +3V3, BAT+, GND returns |
| `W_SIG` | 0.25mm | Signal: buttons, passives |
| `W_DATA` | 0.2mm | Data: display bus, SPI, I2S, USB |
| `W_AUDIO` | 0.3mm | Audio: PAM8403 to speaker |

### Board Geometry

- Board: 160 x 75 mm, center at (80.0, 37.5)
- FPC slot zone (no traces allowed): x=[125.5, 128.5], y=[23.5, 47.5]
- 4-layer stack: F.Cu, In1.Cu (GND plane), In2.Cu (+3V3/+5V plane), B.Cu

## Steps

1. Read current routing:

```bash
cat /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo/scripts/generate_pcb/routing.py
```

2. Depending on the argument:

   - **`info`**: Show routing statistics:
     ```bash
     cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -c "
     import re
     with open('scripts/generate_pcb/routing.py') as f:
         code = f.read()
     segs = len(re.findall(r'P\.segment\(', code))
     vias = len(re.findall(r'P\.via\(', code))
     zones = len(re.findall(r'P\.zone_fill\(', code))
     print(f'Segments: {segs}')
     print(f'Vias: {vias}')
     print(f'Zones: {zones}')
     "
     ```

   - **`trace <net>`**: Add or modify trace routing for a specific net in `routing.py`. Use the primitives:
     ```python
     P.segment(x1, y1, x2, y2, layer="B.Cu", width=W_SIG, net=NET_ID["net_name"])
     ```
     Pad positions are computed via `pad_positions.get_pad(pads, ref, pad_num)`.

   - **`via <x> <y>`**: Add a via at the specified coordinates:
     ```python
     P.via(x, y, size=0.9, drill=0.35, net=NET_ID["net_name"])
     ```

   - **`diff-pair`**: Route USB D+/D- as a differential pair with matched lengths. These traces must be routed together with controlled impedance.

   - **`zone`**: Add or modify a copper zone (ground/power fill):
     ```python
     P.zone_fill(layer="In1.Cu", pts_list=[(x1,y1), (x2,y2), ...], net=1, net_name="GND")
     ```

   - **`netclass`**: Edit trace width constants `W_PWR`, `W_SIG`, `W_DATA`, `W_AUDIO` at the top of `routing.py`.

3. After changes, regenerate the PCB:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -m scripts.generate_pcb hardware/kicad
```

4. Verify connectivity and DRC:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 scripts/test_pcb_connectivity.py && python3 scripts/drc_check.py
```

## Key Files

| File | Purpose |
|------|---------|
| `scripts/generate_pcb/routing.py` | All trace routing, vias, zones (main routing file) |
| `scripts/generate_pcb/primitives.py` | `segment()`, `via()`, `zone_fill()` S-expression generators + NET_LIST/NET_ID |
| `scripts/generate_pcb/pad_positions.py` | Pad position computation: `get_all_pad_positions()`, `get_pad()`, `esp32_gpio_pos()`, `fpc_pin_pos()` |
| `scripts/generate_pcb/board.py` | Component positions (needed for routing endpoints) |
| `scripts/test_pcb_connectivity.py` | Connectivity verification |
| `scripts/drc_check.py` | Design rule check |
| `hardware/kicad/esp32-emu-turbo.kicad_pcb` | Generated PCB output |

## Routing Helpers in routing.py

- `enc(ex, ey)` -- Convert enclosure center-origin coordinates to PCB top-left origin
- `_crosses_slot(x1, y1, x2, y2)` -- Check if a segment crosses the FPC slot cutout
- Pad positions are retrieved at generation time via `pad_positions.get_all_pad_positions()`

## MCP Tool Mapping

| MCP Tool | Our Implementation |
|----------|-------------------|
| `route_trace` | Add `P.segment()` calls in `routing.py` |
| `add_via` | Add `P.via()` call in `routing.py` |
| `add_net` | Add entry to `NET_LIST` in `primitives.py` |
| `delete_trace` | Remove `P.segment()` calls from `routing.py` |
| `get_nets_list` | Read `NET_LIST` from `primitives.py` (line 135+) |
| `create_netclass` | Edit `W_PWR`/`W_SIG`/`W_DATA`/`W_AUDIO` constants in `routing.py` |
| `add_copper_pour` | Add `P.zone_fill()` call in `routing.py` |
| `route_differential_pair` | Route USB D+/D- with matched lengths in `routing.py` |

## Important Notes

- Never edit `hardware/kicad/esp32-emu-turbo.kicad_pcb` directly -- it is a generated file.
- All routing must be Manhattan (orthogonal). No 45-degree traces.
- The FPC slot at x=[125.5, 128.5], y=[23.5, 47.5] is a physical cutout. Use `_crosses_slot()` to validate.
- Net IDs are resolved via `NET_ID["net_name"]` dictionary from `primitives.py`.
- Inner layers: In1.Cu is for GND plane, In2.Cu is for power planes (+3V3, +5V).
