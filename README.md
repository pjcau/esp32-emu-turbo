# ESP32 Emu Turbo

Handheld retro gaming console based on ESP32-S3 — **SNES** (primary) and **NES** (secondary) emulation.

## Project Goal

Build a portable battery-powered device based on ESP32-S3, capable of loading and playing retro games via SD card, with USB-C charging and an ILI9488 3.95" color LCD display.

## Development Phases

### Phase 1 — Feasibility Analysis ✓
- Evaluate ESP32-S3 capabilities for SNES/NES emulation
- Select components (display, controller, power supply)

### Phase 2 — Hardware Design ✓
- KiCad electrical schematics (7 hierarchical sheets, 68 components)
- OpenSCAD 3D enclosure model
- GPIO pin mapping and validation
- Docker rendering pipeline
- 4-layer PCB layout (160x75mm, JLCPCB-ready)

### Phase 3 — PCB Fabrication (In Progress)
- Production files ready in `release_jlcpcb/` (Gerber ZIP + BOM + CPL)
- JLCPCB order and assembly
- Testing and performance optimization

### Phase 4 — Final Version (v2)
- Revised PCB if needed
- 3D-printed enclosure
- Final assembly

## PCB Design

![PCB Layout](/website/static/img/pcb/pcb-combined.png)

| Parameter | Value |
|-----------|-------|
| **Dimensions** | 160 x 75 mm |
| **Layers** | 4 (Signal / GND / Power / Signal) |
| **Surface Finish** | ENIG |
| **Components** | 65 assembled by JLCPCB |
| **Estimated Cost** | ~$18/board (5 pcs) |

## Key Requirements

| Component | Specification |
|---|---|
| **MCU** | ESP32-S3 N16R8 (16MB flash, 8MB Octal PSRAM) |
| **Display** | ILI9488 3.95" 320x480, 8-bit 8080 parallel, bare panel + 40P FPC |
| **Power** | LiPo 3.7V 5000mAh + IP5306 (SOP-8) + AMS1117 |
| **Charging** | USB-C (charge-and-play) |
| **Audio** | I2S -> PAM8403 -> 28mm speaker |
| **Controls** | 13 buttons (D-pad, ABXY, Start, Select, L, R, Menu) |
| **Storage** | Micro SD card via SPI |
| **Emulation** | SNES (primary), NES (secondary) |

## Quick Start

### Generate hardware files

```bash
# Generate schematics (7 sheets + hierarchical root)
python3 -m scripts.generate_schematics hardware/kicad

# Generate PCB layout + JLCPCB exports
make generate-pcb

# Render PCB images (SVG + PNG + GIF)
make render-pcb

# Verify schematic/PCB/JLCPCB consistency
python3 scripts/verify_schematic_pcb.py
```

### Render schematics and 3D model

```bash
# Build Docker images and render all assets
make render-all

# Or individually:
make render-schematics   # KiCad -> SVG
make render-enclosure    # OpenSCAD -> PNG
```

### Run documentation site locally

```bash
make website-dev
# or: cd website && npm start
```

## Project Structure

```
esp32-emu-turbo/
├── hardware/
│   ├── kicad/              # KiCad 9.0 schematics + PCB
│   │   ├── esp32-emu-turbo.kicad_sch   # Hierarchical root
│   │   ├── 01-power-supply.kicad_sch   # 7 sub-sheets
│   │   ├── ...
│   │   ├── esp32-emu-turbo.kicad_pcb   # PCB layout
│   │   └── jlcpcb/         # BOM + CPL for JLCPCB
│   └── enclosure/          # OpenSCAD parametric 3D model
├── release_jlcpcb/         # Production files for JLCPCB ordering
│   ├── gerbers/            # Gerber + drill files (22 layers)
│   ├── gerbers.zip         # Ready-to-upload ZIP
│   ├── bom.csv             # Bill of Materials (JLCPCB format)
│   ├── cpl.csv             # Component Placement List (65 parts)
│   └── bom-summary.md      # Human-readable BOM + cost estimate
├── scripts/
│   ├── generate_schematics/ # Schematic generator (Python)
│   ├── generate_pcb/       # PCB layout generator (Python)
│   ├── render_pcb_svg.py   # PCB SVG renderer
│   ├── render_pcb_animation.py  # PCB PNG/GIF renderer
│   └── verify_schematic_pcb.py  # Consistency checker
├── docker/                 # Docker containers (KiCad + OpenSCAD)
├── website/                # Docusaurus documentation site
│   └── docs/               # All documentation pages
├── docker-compose.yml      # Container orchestration
├── Makefile                # Top-level automation
└── CLAUDE.md               # AI assistant instructions
```

## Documentation

All project documentation lives in `website/docs/` and is published via Docusaurus to GitHub Pages:

- [Documentation Site](https://pjcau.github.io/esp32-emu-turbo/) — full docs online
- [Feasibility Analysis](website/docs/feasibility.md)
- [SNES Hardware Spec](website/docs/snes-hardware.md)
- [Bill of Materials](website/docs/components.md)
- [Electrical Schematics](website/docs/schematics.md)
- [Prototyping Guide](website/docs/prototyping.md)
- [Enclosure Design](website/docs/enclosure.md)
- [PCB Design](website/docs/pcb.md)
