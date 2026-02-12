# ESP32 Emu Turbo — Firmware

Phase 1 hardware validation firmware for the ESP32-S3 N16R8 handheld console.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- USB-C cable connected to the board (for flashing)
- (Optional) Micro SD card with ROMs in `/roms/<system>/` folders

## Quick Start (Docker — recommended)

No local ESP-IDF installation needed. Everything runs inside the `espressif/idf:v5.4` Docker image.

```bash
# From the project root (not software/)

# 1. Build firmware
make firmware-build

# 2. Connect board via USB-C, hold SELECT at power-on for download mode

# 3. Flash + open serial monitor
make firmware-flash

# If your board is on a different port:
ESP_PORT=/dev/ttyACM0 make firmware-flash
```

> **Tip:** Press `Ctrl+]` to exit the serial monitor.

### Other Docker commands

```bash
make firmware-monitor   # Serial monitor only (no flash)
make firmware-clean     # Clean build artifacts
```

### docker compose directly

```bash
# Build only
docker compose run --rm idf-build

# Flash + monitor
docker compose run --rm idf-flash

# Custom port
ESP_PORT=/dev/ttyACM0 docker compose run --rm idf-flash
```

## Alternative: Native ESP-IDF

If you prefer a local installation instead of Docker:

```bash
# 1. Install ESP-IDF v5.4
mkdir -p ~/esp && cd ~/esp
git clone --recursive https://github.com/espressif/esp-idf.git -b v5.4
cd esp-idf && ./install.sh esp32s3
source export.sh

# 2. Build and flash
cd software
idf.py set-target esp32s3
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

## What It Does

The firmware runs a sequential hardware test on boot:

| # | Test | What to expect |
|---|------|----------------|
| 1 | Display | Color bars fill the screen for 3 seconds |
| 2 | Power | Battery % and charge status logged to serial |
| 3 | Input | All 12 button GPIOs configured, initial state logged |
| 4 | SD Card | Mounts FAT32, lists ROM files in `/roms/<system>/` |
| 5 | Audio | 440 Hz tone plays from speaker for 2 seconds |

After all tests, the firmware enters **interactive mode**:
- Press any button → highlighted on screen + logged to serial
- Poll rate printed every 5 seconds

## Project Structure

```
software/
├── CMakeLists.txt          ESP-IDF project root
├── sdkconfig.defaults      ESP32-S3 N16R8 config (240MHz, 16MB flash, 8MB PSRAM)
├── partitions.csv          Flash layout (4MB app + 12MB storage)
└── main/
    ├── CMakeLists.txt      Component build config
    ├── idf_component.yml   ESP Registry dependency (esp_lcd_st7796)
    ├── board_config.h      All GPIO pin definitions
    ├── main.c              Test harness entry point
    ├── display.c/h         ST7796S 320x480 8-bit i80 parallel + backlight PWM
    ├── input.c/h           12-button GPIO polling (active-low, HW debounce)
    ├── sdcard.c/h          SD card SPI + FAT32 mount + ROM listing
    ├── audio.c/h           I2S 32kHz mono → PAM8403 amplifier
    └── power.c/h           IP5306 I2C battery level + charge status
```

## GPIO Map

| Peripheral | GPIOs | Notes |
|---|---|---|
| Display data | 4–11 | 8-bit bus (contiguous for DMA) |
| Display ctrl | 3, 12–14, 45, 46 | RD, CS, RST, DC, BL, WR |
| SD card | 36–39 | SPI: MOSI, MISO, CLK, CS |
| Audio | 15–17 | I2S: BCLK, LRCK, DOUT |
| D-pad | 40, 41, 42, 1 | UP, DOWN, LEFT, RIGHT |
| Face buttons | 2, 48, 47, 21 | A, B, X, Y |
| System | 18, 0 | START, SELECT (GPIO0 = boot) |
| Shoulder | 35, 19 | L, R |
| IP5306 I2C | 33, 34 | SDA, SCL |

## SD Card ROM Layout

```
/sdcard/roms/
├── nes/    .nes files
├── snes/   .smc / .sfc files
├── gb/     .gb files
├── gbc/    .gbc files
├── sms/    .sms files
├── gg/     .gg files
├── pce/    .pce files
└── gen/    .bin / .md files
```

## Troubleshooting

| Problem | Fix |
|---|---|
| Build fails on `esp_lcd_st7796` | Run `idf.py reconfigure` to fetch managed components |
| No serial output | Check USB cable is data-capable, try `/dev/ttyACM0` |
| Display stays black | Verify FPC cable seated correctly, check GPIO45 (BL) |
| SD card not detected | Ensure FAT32 format, check SPI wiring (GPIO36–39) |
| IP5306 not responding | Board may use non-I2C variant — warning is expected |
