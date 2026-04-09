---
name: hardware-audit
description: Deep electrical/functional audit of the ESP32 Emu Turbo hardware design. Finds bugs that prevent power-on, component operation, or emulator functionality. Cross-checks schematics, PCB, datasheets, and firmware.
disable-model-invocation: false
allowed-tools: Bash, Read, Edit, Grep, Glob, Agent, Write
---

# Hardware Functional Audit

Iterative deep-dive to find electrical, connectivity, and functional bugs that would prevent the device from working.

## Audit Domains

1. **Power chain**: USB-C → IP5306 → +5V → AMS1117 → +3.3V → ESP32
2. **ESP32 boot**: Strapping pins, EN reset, flash/PSRAM config
3. **Display**: 8-bit parallel bus, FPC connector, ILI9488 init sequence
4. **Audio**: I2S → PAM8403 → speaker
5. **SD card**: SPI interface, card detect, voltage levels
6. **Buttons**: Pull-ups, debounce, GPIO conflicts
7. **USB**: D+/D- routing, ESD protection, CC pull-downs
8. **Emulator performance**: PSRAM access, DMA, bus contention

## Key Files

- `scripts/generate_schematics/` — schematic generator (all sheets)
- `scripts/generate_pcb/routing.py` — PCB trace routing
- `hardware/datasheet_specs.py` — component pin specs
- `software/main/board_config.h` — firmware GPIO config
- `hardware/datasheets/` — component datasheets
