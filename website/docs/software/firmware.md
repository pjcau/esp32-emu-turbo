---
id: firmware
title: ESP32 Firmware
sidebar_position: 2
---

# ESP32 Firmware

ESP-IDF v5.x firmware for the ESP32 Emu Turbo hardware. Phase 1 validates all hardware subsystems, Phase 2 integrates Retro-Go, Phase 3 enables all emulator cores.

---

## Phase 1 — Hardware Abstraction

Standalone ESP-IDF v5.x project in `software/` that validates all hardware before integrating Retro-Go. See [`software/README.md`](https://github.com/pjcau/esp32-emu-turbo/blob/main/software/README.md) for build instructions.

| Step | Task | Details | Status |
|:---|:---|:---|:---|
| 1.1 | ESP-IDF v5.x project setup | sdkconfig for N16R8 (240MHz, 16MB flash, 8MB PSRAM) | ✅ Done |
| 1.2 | ILI9488 display driver (i80 8-bit parallel) | `esp_lcd_panel_io_i80` + `esp_lcd_ili9488` component, 20MHz | ✅ Done |
| 1.3 | Display test pattern | Color bars, fill screen, status indicators | ✅ Done |
| 1.4 | SD card (SPI mode) | `esp_vfs_fat_sdspi_mount`, FAT32, ROM directory scanner | ✅ Done |
| 1.5 | 12-button input | GPIO polling @ 1ms, bitmask API, HW RC debounce | ✅ Done |
| 1.6 | I2S audio output | `i2s_std` 32kHz 16-bit mono, 440Hz test tone | ✅ Done |
| 1.7 | Power management | IP5306 I2C (0x75), battery %, charge status | ✅ Done |

### Firmware project structure

```
software/
├── CMakeLists.txt              ESP-IDF project root
├── sdkconfig.defaults          ESP32-S3 N16R8 hardware config
├── partitions.csv              4MB app + 12MB storage
└── main/
    ├── idf_component.yml       esp_lcd_ili9488 ^1.4.0
    ├── board_config.h          All GPIO pin definitions (source of truth)
    ├── main.c                  Test harness → interactive button display
    ├── display.c/h             ILI9488 320×480 i80 parallel + LEDC backlight
    ├── input.c/h               12 buttons, active-low, bitmask polling
    ├── sdcard.c/h              SPI @ 20MHz, FAT32, ROM listing
    ├── audio.c/h               I2S mono → PAM8403 amplifier
    └── power.c/h               IP5306 I2C battery level + charge status
```

### Build & flash (Docker)

No local toolchain needed — the build runs inside the official `espressif/idf:v5.4` Docker image.

```bash
# Build firmware
make firmware-build

# Flash + serial monitor (connect board, hold SELECT at power-on)
make firmware-flash

# Custom USB port
ESP_PORT=/dev/ttyACM0 make firmware-flash
```

Native ESP-IDF is also supported — see [`software/README.md`](https://github.com/pjcau/esp32-emu-turbo/blob/main/software/README.md) for details.

### Test sequence on boot

1. Display shows color bars for 3 seconds (verifies 8-bit data bus)
2. IP5306 battery % and charge status (serial log)
3. All 12 button GPIOs initialized
4. SD card mounted, ROM directories scanned
5. 440 Hz test tone plays for 2 seconds
6. Interactive mode: button presses shown on screen + serial

---

## SD Card Setup

The console loads ROMs from a micro SD card formatted as **FAT32**. Each emulated system has its own folder under `/roms/`.

### Directory structure

```
SD Card (FAT32)
└── roms/
    ├── nes/       .nes files
    ├── snes/      .smc / .sfc files
    ├── gb/        .gb files
    ├── gbc/       .gbc files
    ├── sms/       .sms files
    ├── gg/        .gg files
    ├── pce/       .pce files
    ├── gen/       .bin / .md files
    ├── lynx/      .lnx files
    └── gw/        .gw files
```

### Preparation steps

1. **Format** the micro SD card as FAT32 (most cards come pre-formatted)
2. **Create** the `roms/` directory in the root of the card
3. **Create sub-folders** for each system you want to emulate
4. **Copy ROM files** into the matching folder

### Automated setup

A script is provided to format the SD card and copy test ROMs in one step:

```bash
# Format SD card as FAT32 + copy all homebrew test ROMs
sudo ./scripts/setup-sdcard.sh /dev/sdX

# Copy only (skip formatting)
sudo ./scripts/setup-sdcard.sh /dev/sdX --no-format
```

### Included homebrew test ROMs

The project includes 8 freely distributable homebrew ROMs in `test-roms/` for testing without commercial ROMs:

| System | ROM | Author | Size |
|:---|:---|:---|:---|
| NES | Owlia | Gradual Games | 512 KB |
| GB | Blargg's CPU Instructions | Blargg | 64 KB |
| GBC | ucity v1.3 | AntonioND | 128 KB |
| SMS | Silver Valley | Enrique Ruiz | 256 KB |
| GG | Swabby v1.11 | Anders S. Jensen | 128 KB |
| PCE | Reflectron | Aetherbyte | 256 KB |
| Genesis | Miniplanets | Sik | 256 KB |
| SNES | Super Boss Gaiden v1.2 | Dieter Von Laser | 512 KB |

### Recommended commercial test ROMs

| System | ROM | File | Size | Why |
|:---|:---|:---|:---|:---|
| NES | Super Mario Bros | `smb.nes` | 40 KB | Universal test — scrolling, sprites, audio |
| SNES | Super Mario World | `smw.smc` | 512 KB | Good baseline — 2 BG layers, Mode 1 |
| SNES | FF6 | `ff6.smc` | 3 MB | Turn-based RPG — best SNES genre for ESP32 |
| GB | Tetris | `tetris.gb` | 32 KB | Minimal — verifies basic emulation |
| Genesis | Sonic | `sonic.bin` | 512 KB | Fast scrolling stress test |

### Size limits

| Constraint | Value |
|:---|:---|
| Max ROM size (PSRAM) | **6 MB** |
| SD card format | FAT32 (max 32 GB recommended) |
| Max filename length | 255 characters (long filename support enabled) |

:::tip SNES ROM sizes
Most SNES games are 1–4 MB. Games with special chips (SA-1, SuperFX) are larger and may not be compatible with snes9x on ESP32-S3.
:::

---

## Phase 2 — Retro-Go Integration

Fork and adapt Retro-Go for our hardware. Retro-Go is included as a git submodule at `retro-go/` and built via a separate Docker Compose file.

| Step | Task | Details | Status |
|:---|:---|:---|:---|
| 2.1 | Add `ducalex/retro-go` as submodule | `retro-go/` directory, upstream repo | ✅ Done |
| 2.2 | Create target `targets/esp32-emu-turbo/` | `config.h` + `env.py` + `sdkconfig` | ✅ Done |
| 2.3 | Docker build pipeline | `docker-compose.retro-go.yml` + Makefile targets | ✅ Done |
| 2.4 | Custom display driver `ili9488_i80.h` | 8-bit i80 parallel via `esp_lcd_panel_io_i80`, async DMA, 5-buffer pool | ✅ Done |
| 2.5 | Frame scaling | Automatic via Retro-Go core (320x480 portrait, integer scale + letterbox) | ✅ Done |
| 2.6 | Input mapping | 12 GPIO direct buttons + MENU=SELECT (GPIO 0) | ✅ Done |
| 2.7 | Audio routing | I2S ext DAC (BCLK=15, WS=16, DATA=17) → PAM8403 | ✅ Done |
| 2.8 | First boot: NES test | nofrendo running Super Mario Bros at 60fps | ⏳ Needs hardware |

### Build & flash (Docker)

Retro-Go uses a separate Docker Compose file (`docker-compose.retro-go.yml`) with the `espressif/idf:v5.4` image.

```bash
# Build all Retro-Go apps (launcher + emulators)
make retro-go-build

# Build launcher only (quick test)
make retro-go-build-launcher

# Flash firmware + serial monitor
make retro-go-flash

# Serial monitor only
make retro-go-monitor

# Custom USB port
ESP_PORT=/dev/ttyACM0 make retro-go-flash

# Clean build cache
make retro-go-clean
```

### Build output

All 5 Retro-Go applications compile successfully for the ESP32 Emu Turbo target (ESP-IDF v5.4, ESP32-S3):

| Binary | Contents | Size | Partition free |
|:---|:---|:---|:---|
| `launcher.bin` | Retro-Go launcher UI + ROM browser | 1037 KB | 67% |
| `retro-core.bin` | All emulators (NES, GB, GBC, SMS, GG, PCE, Lynx, SNES, G&W) | ~2.5 MB | ~17% |
| `gwenesis.bin` | Sega Genesis / Mega Drive (standalone) | ~1.5 MB | ~50% |
| `prboom-go.bin` | Doom port (PrBoom) | ~1.5 MB | ~50% |
| `fmsx.bin` | MSX emulator | 655 KB | 79% |

:::note
The build produces `Device doesn't support fw format, try build-img!` at the end — this is expected. Our target uses individual app flashing via `make retro-go-flash`, not a combined firmware image.
:::

### Target configuration

The target lives at `retro-go/components/retro-go/targets/esp32-emu-turbo/` with:
- `config.h` — GPIO mapping, display/audio/input config (mirrors `board_config.h`)
- `env.py` — `IDF_TARGET = "esp32s3"`, firmware format
- `sdkconfig` — ESP-IDF config (240MHz, 16MB flash QIO, 8MB Octal PSRAM)

### GPIO mapping verification

All 33 GPIO pins have been cross-verified between three sources with **zero discrepancies**:

| Group | Pins | board_config.h | Retro-Go config.h | KiCad schematic |
|:---|:---|:---|:---|:---|
| Display data D0–D7 | GPIO 4–11 | ✅ | ✅ | ✅ |
| Display control | GPIO 12–14, 46 | ✅ | ✅ | ✅ |
| Display hardwired | RD, BL → +3V3 (no GPIO) | ✅ | ✅ | ✅ |
| SD card SPI | GPIO 44, 43, 38, 39 | ✅ | ✅ | ✅ |
| I2S audio | GPIO 15–17 | ✅ | ✅ | ✅ |
| D-pad | GPIO 40, 41, 42, 1 | ✅ | ✅ | ✅ |
| Face buttons | GPIO 2, 48, 47, 21 | ✅ | ✅ | ✅ |
| System buttons | GPIO 18, 0 | ✅ | ✅ | ✅ |
| Shoulder buttons | GPIO 45, 3 | ✅ | ✅ | ✅ |

**Notes:**
- MENU and SELECT share GPIO 0 in Retro-Go (intentional — 12 physical buttons, 13 logical)
- GPIO 19/20 are used for native USB data (D-/D+) — firmware flash + CDC debug console
- GPIO 3 is BTN_R, GPIO 45 is BTN_L (shoulder buttons freed by hardwiring LCD_RD/LCD_BL to +3V3)
- GPIO 43 is SD_MISO (was TX0 UART debug, replaced by USB native)
- GPIO 26–32 are reserved for Octal PSRAM (cannot be used)

### Display driver: `ili9488_i80.h`

Custom driver replacing Retro-Go's SPI-based `ili9341.h` with 8-bit 8080 parallel interface. Located at `retro-go/components/retro-go/drivers/display/ili9488_i80.h`.

| Feature | Value |
|:---|:---|
| Bus | 8-bit i80 parallel (`esp_lcd_panel_io_i80`) |
| Clock | 20 MHz write clock |
| Resolution | 320x480 portrait |
| Color format | RGB565 (16-bit) |
| DMA | Async with 5-buffer pool |
| Backlight | Always-on (tied to +3V3 via resistor on PCB) |
| Driver ID | `RG_SCREEN_DRIVER 2` |

The driver uses `esp_lcd_panel_io_tx_param` for commands (CASET/RASET) and `esp_lcd_panel_io_tx_color` for async DMA pixel transfers. A completion callback recycles buffers to the pool, providing natural backpressure without explicit sync.

---

## Phase 3 — All Emulators at Full Speed

Enable and test each emulator core.

| Step | Core | Test ROM | Target |
|:---|:---|:---|:---|
| 3.1 | nofrendo (NES) | Super Mario Bros | 60 fps |
| 3.2 | gnuboy (GB) | Tetris | 60 fps |
| 3.3 | gnuboy (GBC) | Pokemon Crystal | 60 fps |
| 3.4 | smsplus (SMS) | Sonic the Hedgehog | 60 fps |
| 3.5 | smsplus (GG) | Sonic Triple Trouble | 60 fps |
| 3.6 | pce-go (PCE) | Bonk's Adventure | 60 fps |
| 3.7 | handy (Lynx) | California Games | 60 fps |
| 3.8 | gwenesis (Genesis) | Sonic the Hedgehog | 50-60 fps |
| 3.9 | gw-emulator (G&W) | Ball | 60 fps |

For SNES-specific optimization (Phase 4) and v2 hardware audio coprocessor (Phase 5), see [SNES Optimization](snes-optimization).

---

## Build & Flash

```bash
# Clone fork
git clone https://github.com/pjcau/retro-go.git
cd retro-go

# Build for ESP32 Emu Turbo
python3 rg_tool.py --target=esp32-emu-turbo build

# Flash via USB-C (GPIO0/SELECT = download mode at boot)
python3 rg_tool.py --target=esp32-emu-turbo flash

# Copy ROMs to SD card
# /roms/nes/  — .nes files
# /roms/snes/ — .smc/.sfc files
# /roms/gb/   — .gb files
# /roms/gbc/  — .gbc files
# /roms/sms/  — .sms files
# /roms/gg/   — .gg files
# /roms/pce/  — .pce files
# /roms/gen/  — .bin/.md files
```

For the full software architecture overview, see [Software Architecture](/docs/software).
