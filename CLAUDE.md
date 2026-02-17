# ESP32 Emu Turbo

## Language

All code, comments, commit messages, documentation, and any written content in this project MUST be in **English**.

## Overview

Handheld retro gaming console based on ESP32-S3 with color TFT/LCD display (3.5"–4"), battery-powered with USB-C charging. SNES emulation (primary) and NES (secondary).

## Project Phases

1. **Feasibility analysis** — evaluate ESP32-S3 capabilities, select components, proof-of-concept software
2. **Hardware design** — KiCad schematics, OpenSCAD enclosure, GPIO mapping
3. **Hardware prototype** — assembly, testing and optimization
4. **Final version (v2)** — custom PCB + 3D-printed enclosure

## Hardware Requirements

- **MCU:** ESP32-S3 N16R8 (16MB flash, 8MB Octal PSRAM, dual-core LX7 240MHz)
- **Display:** ILI9488 3.95" 320x480, 8-bit 8080 parallel, bare panel 40P FPC 0.5mm
- **Power:** LiPo 3.7V 5000mAh (105080, 50x80x10mm)
- **Charging:** USB-C via IP5306 (charge-and-play)
- **Regulator:** AMS1117 5V->3.3V
- **Audio:** I2S DAC -> PAM8403 -> 28mm speaker
- **Storage:** Micro SD card via SPI (for ROMs)
- **Emulation targets:** SNES (primary), NES (secondary)
- **Controls:** 12 buttons (D-pad, A, B, X, Y, Start, Select, L, R) + optional PSP joystick
- **Prototype budget:** ~$33-45

## Project Structure

- `software/` — ESP-IDF v5.x firmware (Phase 1 hardware validation)
- `software/main/board_config.h` — GPIO pin definitions (source of truth for firmware)
- `hardware/kicad/` — KiCad 10 schematic project (full circuit design)
- `hardware/enclosure/` — OpenSCAD parametric 3D enclosure model
- `docker/` — Docker containers for headless rendering (KiCad + OpenSCAD)
- `scripts/` — Rendering and verification scripts
- `Makefile` — Top-level automation (`make render-all`, `make website-dev`)
- `docker-compose.yml` — Orchestrates rendering containers
- `website/` — Docusaurus site for GitHub Pages (https://pjcau.github.io/esp32-emu-turbo/)
- `website/docs/` — All documentation (single source of truth)

## Documentation

- `website/docs/feasibility.md` — feasibility analysis
- `website/docs/snes-hardware.md` — SNES hardware specification + GPIO mapping
- `website/docs/components.md` — BOM with AliExpress links
- `website/docs/schematics.md` — electrical schematic documentation
- `website/docs/prototyping.md` — breadboard wiring guide
- `website/docs/enclosure.md` — 3D enclosure design + renderings
- `website/docs/manufacturing.md` — JLCPCB PCBA ordering + cost analysis
- `website/docs/verification.md` — pre-production DRC/simulation/consistency checks
- `website/docs/software.md` — software architecture, SNES optimization, audio profiles

## Reference Software

- **Retro-Go** (github.com/ducalex/retro-go) — NES, GB, GBC, SMS
- **esp-box-emu** (github.com/esp-cpp/esp-box-emu) — NES, SNES, Genesis on ESP32-S3
