# ESP32 Emu Turbo

## Language

All code, comments, commit messages, documentation, and any written content in this project MUST be in **English**.

## Overview

Handheld retro gaming console based on ESP32-S3 with color TFT/LCD display (3.5"–4"), battery-powered with USB-C charging. NES emulation (primary) and SNES (secondary).

## Project Phases

1. **Feasibility analysis** — evaluate ESP32-S3 capabilities, select components, proof-of-concept software
2. **Hardware prototype** — assembly, testing and optimization
3. **Final version (v2)** — custom PCB + 3D-printed enclosure

## Hardware Requirements

- **MCU:** ESP32-S3 N16R8 (16MB flash, 8MB Octal PSRAM, dual-core LX7 240MHz)
- **Display:** Color TFT/LCD, 3.5"–4", ST7796S or ILI9488 (parallel preferred for gaming)
- **Power:** LiPo 3.7V 5000mAh (105080, 50x80x10mm)
- **Charging:** USB-C via IP5306 (charge-and-play)
- **Regulator:** AMS1117 5V->3.3V
- **Audio:** I2S DAC -> PAM8403 -> 28mm speaker
- **Storage:** Micro SD card via SPI (for ROMs)
- **Emulation targets:** NES (primary), SNES (secondary)
- **Controls:** 12 buttons (D-pad, A, B, X, Y, Start, Select, L, R) + optional PSP joystick
- **Prototype budget:** ~$42-55

## Documentation

All documentation lives in `website/docs/` (single source of truth), published via Docusaurus to GitHub Pages:
- `website/docs/feasibility.md` — full analysis: components, schematics, BOM, budget, risks
- `website/docs/components.md` — BOM with AliExpress links for every part
- Site URL: https://pjonny.github.io/esp32-emu-turbo/

## Reference Software

- **Retro-Go** (github.com/ducalex/retro-go) — NES, GB, GBC, SMS
- **esp-box-emu** (github.com/esp-cpp/esp-box-emu) — NES, SNES, Genesis on ESP32-S3
