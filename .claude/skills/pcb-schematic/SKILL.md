---
name: pcb-schematic
description: Schematic design operations — create, edit, wire, net labels, export (KiCAD MCP tools 50-58)
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: [create | edit | wire | export | info]
---

# Schematic Design Operations

Map KiCAD MCP schematic tools to our project's programmatic schematic generation infrastructure.

## Overview

The schematic is **not edited manually in KiCad**. It is generated programmatically via Python scripts in `scripts/generate_schematics/`. The master GPIO mapping lives in `scripts/generate_schematics/config.py`, and the generated output lands in `hardware/kicad/`.

## Steps

1. Read current schematic config:

```bash
cat scripts/generate_schematics/config.py
```

2. Depending on the argument:

   - **`create`**: Generate the full schematic from scratch:
     ```bash
     cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -m scripts.generate_schematics hardware/kicad
     ```

   - **`edit`**: Modify GPIO mapping or component list in `scripts/generate_schematics/config.py`. Individual sheet generators live in `scripts/generate_schematics/sheets/`:
     - `mcu.py` -- ESP32-S3 module connections
     - `power_supply.py` -- IP5306, AMS1117, USB-C
     - `display.py` -- ILI9488 FPC-40P connections
     - `audio.py` -- I2S DAC, PAM8403
     - `controls.py` -- D-pad, ABXY, Start/Select, L/R buttons
     - `sd_card.py` -- SPI SD card interface
     - `joystick.py` -- PSP joystick (optional)

   - **`wire`**: Edit wiring connections in the sheet generator files under `scripts/generate_schematics/sheets/`. Wiring primitives are in `scripts/generate_schematics/kicad_primitives.py`.

   - **`export`**: Export schematic to PDF:
     ```bash
     kicad-cli sch export pdf --output /tmp/schematic.pdf hardware/kicad/esp32-emu-turbo.kicad_sch
     ```

   - **`info`**: Show current schematic stats (component count, nets, sheets):
     ```bash
     cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -c "
     from scripts.generate_schematics import config
     config._init()
     print(f'GPIO pins defined: {len(config.GPIO_MAP)}')
     "
     ```
     Or count components in the generated schematic:
     ```bash
     grep -c '(symbol (lib_id' hardware/kicad/esp32-emu-turbo.kicad_sch
     ```

3. After any changes, regenerate:

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo && python3 -m scripts.generate_schematics hardware/kicad
```

## Key Files

| File | Purpose |
|------|---------|
| `scripts/generate_schematics/config.py` | Master GPIO mapping and component configuration |
| `scripts/generate_schematics/__main__.py` | CLI entry point for generation |
| `scripts/generate_schematics/__init__.py` | Top-level generator orchestrator |
| `scripts/generate_schematics/root_schematic.py` | Root schematic with sheet hierarchy |
| `scripts/generate_schematics/sheet_base.py` | Base class for sheet generators |
| `scripts/generate_schematics/kicad_primitives.py` | S-expression primitives for schematics |
| `scripts/generate_schematics/lib_symbols.py` | Symbol library definitions |
| `scripts/generate_schematics/sheets/*.py` | Individual sheet generators (mcu, power, display, audio, controls, sd_card, joystick) |
| `scripts/generate_pcb/primitives.py` | NET_LIST definitions (shared with PCB) |
| `hardware/kicad/esp32-emu-turbo.kicad_sch` | Generated schematic output |

## MCP Tool Mapping

| MCP Tool | Our Implementation |
|----------|-------------------|
| `create_schematic` | `python3 -m scripts.generate_schematics hardware/kicad` |
| `load_schematic` | `Read hardware/kicad/esp32-emu-turbo.kicad_sch` |
| `add_schematic_component` | Edit component list in `config.py` + relevant sheet in `sheets/` |
| `add_schematic_wire` | Edit wiring in sheet generators under `sheets/` |
| `add_schematic_net_label` | Edit NET_LIST in `scripts/generate_pcb/primitives.py` |
| `connect_to_net` | Edit routing connections in sheet generators |
| `export_schematic_pdf` | `kicad-cli sch export pdf --output /tmp/schematic.pdf hardware/kicad/esp32-emu-turbo.kicad_sch` |
| `list_schematic_libraries` | `kicad-cli sym search <query>` |

## Important Notes

- Never edit `hardware/kicad/esp32-emu-turbo.kicad_sch` directly -- it is a generated file.
- Always regenerate after modifying any source file in `scripts/generate_schematics/`.
- The GPIO mapping in `config.py` must stay in sync with `software/main/board_config.h` (firmware). Use the `/firmware-sync` skill to verify.
