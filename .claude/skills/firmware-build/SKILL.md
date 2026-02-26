---
name: firmware-build
description: Build, flash, and test ESP-IDF firmware for ESP32-S3 (via Docker or native)
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: [build|flash|monitor|clean|all]
---

# ESP-IDF Firmware Build Pipeline

Build, flash, and monitor the ESP32-S3 firmware using ESP-IDF v5.4.

**Argument** (optional): `build` (default), `flash`, `monitor`, `clean`, or `all`.

## Prerequisites

- Docker running (for containerized builds)
- USB device connected at `$ESP_PORT` (default: `/dev/ttyUSB0`) for flash/monitor
- ESP-IDF v5.4 Docker image: `espressif/idf:v5.4`

## Commands

### Build firmware (Docker)

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
docker compose run --rm idf-build
```

This runs `idf.py set-target esp32s3 && idf.py build` inside the container.

### Flash + Monitor (Docker)

```bash
ESP_PORT=/dev/ttyUSB0 docker compose run --rm idf-flash
```

Flashes firmware and opens serial monitor. Requires USB device passthrough.

### Monitor only

```bash
ESP_PORT=/dev/ttyUSB0 docker compose run --rm idf-flash idf.py -p /dev/ttyUSB0 monitor
```

### Clean build artifacts

```bash
docker compose run --rm idf-build idf.py fullclean
```

### Build via Makefile

```bash
make firmware-build    # Build
make firmware-flash    # Flash + monitor
make firmware-monitor  # Monitor only
make firmware-clean    # Clean
```

## Firmware Architecture

The firmware validates all hardware subsystems:

| Module | File | Purpose |
|--------|------|---------|
| Display | `software/main/display.c` | ILI9488 8-bit 8080 parallel init + test pattern |
| Audio | `software/main/audio.c` | I2S DAC → PAM8403 speaker output |
| Input | `software/main/input.c` | 12 buttons + optional joystick polling |
| SD Card | `software/main/sdcard.c` | SPI SD card mount + file listing |
| Power | `software/main/power.c` | IP5306 I2C battery monitoring |
| Main | `software/main/main.c` | Init sequence + hardware validation loop |

## GPIO Pin Reference

All GPIO assignments are in `software/main/board_config.h` (source of truth for firmware).
Master GPIO mapping is in `scripts/generate_schematics/config.py`.

Use the `firmware-sync` skill to verify GPIO consistency between firmware and schematic.

## Configuration Files

- `software/sdkconfig.defaults` — ESP-IDF project defaults (target, flash size, PSRAM)
- `software/partitions.csv` — Flash partition table
- `software/main/idf_component.yml` — IDF component dependencies
- `software/CMakeLists.txt` — Top-level CMake project
- `software/main/CMakeLists.txt` — Main component sources

## Retro-Go Emulator (Phase 2)

For building the Retro-Go emulator firmware:

```bash
make retro-go-build           # Build all apps
make retro-go-build-launcher  # Build launcher only (quick test)
make retro-go-flash           # Flash + monitor
make retro-go-monitor         # Serial monitor
make retro-go-clean           # Clean
```

Uses separate compose file: `docker-compose.retro-go.yml`

## Key Files

- `software/main/board_config.h` — GPIO pin definitions
- `software/main/main.c` — Entry point and init sequence
- `software/sdkconfig.defaults` — ESP-IDF configuration
- `docker-compose.yml` — Docker service definitions (idf-build, idf-flash)
- `Makefile` — Build automation targets
