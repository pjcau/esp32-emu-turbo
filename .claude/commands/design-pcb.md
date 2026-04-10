---
description: Full schematic → board → component placement → routing design workflow. Composes /pcb-schematic → /pcb-board → /pcb-components → /pcb-routing.
---

# Design PCB (lifecycle phase: Design)

Execute the full PCB design workflow, composing the 5 MCP design skills in order.

## Steps

1. **Schematic** — `/pcb-schematic`
   - Define sheets, nets, components, cross-sheet labels.
   - Source of truth: `scripts/generate_schematics/config.py` (GPIO_NETS, ESP_PINS).
   - Regenerate with `python3 -m scripts.generate_schematics hardware/kicad`.

2. **Board outline** — `/pcb-board`
   - Set board dimensions, layers, mounting holes, silkscreen text.
   - Source of truth: `scripts/generate_pcb/board.py` (BOARD_W, BOARD_H, CX, CY).

3. **Component placement** — `/pcb-components`
   - Place footprints per board.py `_component_placeholders()`.
   - Auto-handles B.Cu mirroring, 90° rotation for FPC connectors.

4. **Routing** — `/pcb-routing`
   - Route all traces + vias per `scripts/generate_pcb/routing.py`.
   - Uses collision grid, net-aware clearance, Manhattan paths.

## After design

Next: `/generate-pcb` to emit .kicad_pcb + run DFM/DFA verification.

## When to use

- Starting a new PCB from scratch
- Major redesign (moving components, re-routing entire bus)
- After changing board dimensions or layer stack

## Critical rules

- NEVER edit `.kicad_pcb` or `.kicad_sch` files directly — always regenerate from Python sources.
- Changes to `config.py` / `board.py` / `routing.py` MUST be followed by `/generate-pcb` and `/verify-pcb`.
