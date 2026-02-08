# ESP32 Emu Turbo

Handheld retro gaming console based on ESP32-S3 for NES and SNES emulation.

## Project Goal

Analyze feasibility and build a portable battery-powered device based on ESP32-S3, capable of loading and playing retro games via SD card, with USB-C charging.

## Development Phases

### Phase 1 — Feasibility Analysis
- Evaluate ESP32-S3 capabilities for NES/SNES emulation
- Select components (display, controller, power supply)
- Build proof-of-concept software

### Phase 2 — Hardware Prototype
- Breadboard/perfboard assembly
- Testing and validation
- Performance optimization

### Phase 3 — Final Version (v2)
- Custom PCB design
- 3D-printed case/enclosure
- Final assembly

## Key Requirements

| Component | Specification |
|---|---|
| **MCU** | ESP32-S3 (N16R8: 16MB flash, 8MB PSRAM) |
| **Display** | Color TFT/LCD, 3.5"–4" |
| **Power** | LiPo 3.7V 5000mAh |
| **Charging** | USB-C |
| **Emulation** | NES (primary), SNES (secondary) |

## Estimated Budget

| Configuration | Cost |
|---|---|
| Recommended (NES + SNES) | ~$42 |
| With margin for extras | ~$55 |

## Documentation

All project documentation lives in `website/docs/` and is published via Docusaurus to GitHub Pages:

- [Documentation Site](https://pjcau.github.io/esp32-emu-turbo/) — full docs online
- [Feasibility Analysis](website/docs/feasibility.md)
- [Bill of Materials](website/docs/components.md)
