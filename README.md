# ESP32 Emu Turbo

Handheld retro gaming console based on ESP32-S3 — **SNES** (primary) and **NES** (secondary) emulation.

## Project Goal

Build a portable battery-powered device based on ESP32-S3, capable of loading and playing retro games via SD card, with USB-C charging and a 4.0" color TFT display.

## Development Phases

### Phase 1 — Feasibility Analysis ✓
- Evaluate ESP32-S3 capabilities for SNES/NES emulation
- Select components (display, controller, power supply)

### Phase 2 — Hardware Design (In Progress)
- KiCad electrical schematics
- OpenSCAD 3D enclosure model
- GPIO pin mapping and validation
- Docker rendering pipeline

### Phase 3 — Hardware Prototype
- Breadboard assembly
- Testing and validation
- Performance optimization

### Phase 4 — Final Version (v2)
- Custom PCB design
- 3D-printed enclosure
- Final assembly

## Key Requirements

| Component | Specification |
|---|---|
| **MCU** | ESP32-S3 N16R8 (16MB flash, 8MB Octal PSRAM) |
| **Display** | ST7796S 4.0" 320x480, 8-bit 8080 parallel |
| **Power** | LiPo 3.7V 5000mAh + IP5306 + AMS1117 |
| **Charging** | USB-C (charge-and-play) |
| **Emulation** | SNES (primary), NES (secondary) |

## Estimated Budget

| Configuration | Cost |
|---|---|
| Recommended (SNES Primary) | ~$42 |
| With margin for extras | ~$55 |

## Quick Start

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

### Build for production

```bash
make all   # render + build website
```

## Project Structure

```
esp32-emu-turbo/
├── hardware/
│   ├── kicad/          # KiCad 9.0 schematic project
│   └── enclosure/      # OpenSCAD parametric 3D model
├── docker/             # Docker containers (KiCad + OpenSCAD)
├── scripts/            # Rendering automation
├── website/            # Docusaurus documentation site
│   └── docs/           # All documentation pages
├── docker-compose.yml  # Container orchestration
├── Makefile            # Top-level automation
└── CLAUDE.md           # AI assistant instructions
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
