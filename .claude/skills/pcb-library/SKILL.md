---
name: pcb-library
description: Footprint library management — search, list, inspect footprint details (KiCAD MCP tools 32-35)
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, WebSearch, WebFetch
argument-hint: [list | search <query> | info <footprint> | pads <footprint>]
---

# Footprint Library Management

Map KiCAD MCP library tools to our project's custom footprint infrastructure and the KiCad CLI.

## Overview

Footprints are defined procedurally in `scripts/generate_pcb/footprints.py`. Each footprint is a Python function that returns a list of pad S-expression strings for embedding inside a `(footprint ...)` block. Coordinates are relative to the footprint origin (center).

Pad dimensions are sourced from:
- KiCad 10 standard library footprints (RF_Module, Package_SO, etc.)
- JLCPCB/EasyEDA official component library (C91145, C318884, etc.)
- Manufacturer datasheets (Espressif, HCTL, Korean Hroparts Elec)

## Steps

1. Depending on the argument:

   - **`list`**: Show all registered footprints from our custom library:
     ```bash
     cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -c "
     import inspect
     from scripts.generate_pcb import footprints as FP
     funcs = [name for name, obj in inspect.getmembers(FP) if inspect.isfunction(obj) and not name.startswith('_')]
     for f in sorted(funcs):
         print(f)
     "
     ```

   - **`search <query>`**: Search the KiCad official footprint library:
     ```bash
     kicad-cli fp search "<query>"
     ```
     Or use WebSearch for datasheets and JLCPCB part footprints.

   - **`info <footprint>`**: Show pad count, dimensions, and pin assignments for a custom footprint:
     ```bash
     cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -c "
     from scripts.generate_pcb import footprints as FP
     pads = FP.<footprint_function>()
     print(f'Pad count: {len(pads)}')
     for p in pads:
         print(p.strip())
     "
     ```

   - **`pads <footprint>`**: List all pad positions, sizes, and layers for a footprint. Use `pad_positions.py` utilities:
     ```bash
     cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -c "
     from scripts.generate_pcb.pad_positions import get_all_pad_positions, get_pad
     pads = get_all_pad_positions()
     # Show pads for a specific reference designator:
     for pad_num in range(1, 10):
         try:
             x, y = get_pad(pads, '<REF>', str(pad_num))
             print(f'Pad {pad_num}: ({x:.2f}, {y:.2f})')
         except:
             break
     "
     ```

2. For custom footprints: Read `scripts/generate_pcb/footprints.py`
3. For KiCad library footprints: Use `kicad-cli fp list` or `kicad-cli fp search`

## Key Files

| File | Purpose |
|------|---------|
| `scripts/generate_pcb/footprints.py` | All custom footprint definitions (pad geometry, pin assignments) |
| `scripts/generate_pcb/pad_positions.py` | Pad position utilities: `get_all_pad_positions()`, `get_pad()`, `esp32_gpio_pos()`, `fpc_pin_pos()` |
| `scripts/generate_pcb/primitives.py` | Low-level pad helper used by footprints |

## Footprint Helpers in footprints.py

- `_pad(num, typ, shape, x, y, w, h, layers, net, drill)` -- Generate a single KiCad pad S-expression
- `_smd(num, x, y, w, h, layer)` -- Shorthand for SMD rectangular pad
- `_fp_line(x1, y1, x2, y2, layer, width)` -- Footprint-local silkscreen/fab line
- `_fp_circle(cx, cy, r, layer, width)` -- Footprint-local circle (pin 1 marker)
- Layer constants: `SMD_F` (front), `SMD_B` (back), `THT` (through-hole)

## MCP Tool Mapping

| MCP Tool | Our Implementation |
|----------|-------------------|
| `list_libraries` | `kicad-cli fp list --libraries` (KiCad official) + list functions in `footprints.py` (custom) |
| `search_footprints` | `kicad-cli fp search <query>` + grep through `footprints.py` |
| `list_library_footprints` | `kicad-cli fp list <library>` |
| `get_footprint_info` | Read footprint generator function from `footprints.py` and inspect pad output |

## Important Notes

- Our project uses **custom procedural footprint generators**, not KiCad library `.kicad_mod` files.
- Each footprint function returns a list of pad S-expression strings, not a complete footprint file.
- The footprints are embedded directly into the PCB file during generation by `board.py`.
- To add a new footprint: create a new function in `footprints.py` following the existing pattern, then reference it in `board.py`'s `_component_placeholders()`.
