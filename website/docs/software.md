---
id: software
title: Software Architecture
sidebar_position: 11
---

# Software Architecture

Firmware based on a [Retro-Go](https://github.com/ducalex/retro-go) fork with a custom display driver and target configuration for the ESP32 Emu Turbo hardware.

---

## Platform: Retro-Go

Retro-Go is a multi-system emulator for ESP32 devices. It provides a launcher UI, save states, ROM browser (SD card), and a unified input/display/audio framework.

### Why Retro-Go

| Criteria | Retro-Go | esp-box-emu | Custom from scratch |
|:---|:---|:---|:---|
| Emulator count | 10+ systems | 6 systems | 1 at a time |
| ESP32-S3 support | Mature | ESP32-S3-BOX only | Manual porting |
| Launcher UI | Built-in | LVGL-based | Must build |
| Save states | Yes | Yes | Must implement |
| SD card ROM browser | Yes | Yes | Must implement |
| Community / forks | Large | Small | None |
| SNES core | snes9x2010 (slow) | WIP | Must port |

### Supported Emulators

| Core | System | Resolution | FPS on ESP32-S3 |
|:---|:---|:---|:---|
| nofrendo | NES / Famicom | 256x240 | **60 fps** |
| gnuboy | Game Boy | 160x144 | **60 fps** |
| gnuboy | Game Boy Color | 160x144 | **60 fps** |
| smsplus | Master System | 256x192 | **60 fps** |
| smsplus | Game Gear | 160x144 | **60 fps** |
| pce-go | PC Engine / TurboGrafx-16 | 256x240 | **60 fps** |
| handy | Atari Lynx | 160x102 | **60 fps** |
| gwenesis | Sega Genesis / Mega Drive | 320x224 | **50-60 fps** |
| gw-emulator | Game & Watch | various | **60 fps** |
| snes9x | **SNES / Super Famicom** | 256x224 | **20-45 fps** |

All systems except SNES run at full speed on ESP32-S3 N16R8 @ 240MHz.

---

## Implementation Plan

### Phase 1 — Hardware Abstraction (bootstrap) ✅

Standalone ESP-IDF v5.x project in `software/` that validates all hardware before integrating Retro-Go. See [`software/README.md`](https://github.com/pjcau/esp32-emu-turbo/blob/main/software/README.md) for build instructions.

| Step | Task | Details | Status |
|:---|:---|:---|:---|
| 1.1 | ESP-IDF v5.x project setup | sdkconfig for N16R8 (240MHz, 16MB flash, 8MB PSRAM) | ✅ Done |
| 1.2 | ST7796S display driver (i80 8-bit parallel) | `esp_lcd_panel_io_i80` + `esp_lcd_st7796` component, 20MHz | ✅ Done |
| 1.3 | Display test pattern | Color bars, fill screen, status indicators | ✅ Done |
| 1.4 | SD card (SPI mode) | `esp_vfs_fat_sdspi_mount`, FAT32, ROM directory scanner | ✅ Done |
| 1.5 | 12-button input | GPIO polling @ 1ms, bitmask API, HW RC debounce | ✅ Done |
| 1.6 | I2S audio output | `i2s_std` 32kHz 16-bit mono, 440Hz test tone | ✅ Done |
| 1.7 | Power management | IP5306 I2C (0x75), battery %, charge status | ✅ Done |

#### Firmware project structure

```
software/
├── CMakeLists.txt              ESP-IDF project root
├── sdkconfig.defaults          ESP32-S3 N16R8 hardware config
├── partitions.csv              4MB app + 12MB storage
└── main/
    ├── idf_component.yml       esp_lcd_st7796 ^1.4.0
    ├── board_config.h          All GPIO pin definitions (source of truth)
    ├── main.c                  Test harness → interactive button display
    ├── display.c/h             ST7796S 320×480 i80 parallel + LEDC backlight
    ├── input.c/h               12 buttons, active-low, bitmask polling
    ├── sdcard.c/h              SPI @ 40MHz, FAT32, ROM listing
    ├── audio.c/h               I2S mono → PAM8403 amplifier
    └── power.c/h               IP5306 I2C battery level + charge status
```

#### Build & flash (Docker)

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

#### Test sequence on boot

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

### Phase 2 — Retro-Go Integration

Fork and adapt Retro-Go for our hardware. Retro-Go is included as a git submodule at `retro-go/` and built via a separate Docker Compose file.

| Step | Task | Details | Status |
|:---|:---|:---|:---|
| 2.1 | Add `ducalex/retro-go` as submodule | `retro-go/` directory, upstream repo | ✅ Done |
| 2.2 | Create target `targets/esp32-emu-turbo/` | `config.h` + `env.py` + `sdkconfig` | ✅ Done |
| 2.3 | Docker build pipeline | `docker-compose.retro-go.yml` + Makefile targets | ✅ Done |
| 2.4 | Custom display driver `st7796s_i80.h` | 8-bit i80 parallel via `esp_lcd_panel_io_i80`, async DMA, 5-buffer pool | ✅ Done |
| 2.5 | Frame scaling | Automatic via Retro-Go core (320x480 portrait, integer scale + letterbox) | ✅ Done |
| 2.6 | Input mapping | 12 GPIO direct buttons + MENU=SELECT (GPIO 0) | ✅ Done |
| 2.7 | Audio routing | I2S ext DAC (BCLK=15, WS=16, DATA=17) → PAM8403 | ✅ Done |
| 2.8 | First boot: NES test | nofrendo running Super Mario Bros at 60fps | ⏳ Needs hardware |

#### Build & flash (Docker)

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

#### Build output

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

#### Target configuration

The target lives at `retro-go/components/retro-go/targets/esp32-emu-turbo/` with:
- `config.h` — GPIO mapping, display/audio/input config (mirrors `board_config.h`)
- `env.py` — `IDF_TARGET = "esp32s3"`, firmware format
- `sdkconfig` — ESP-IDF config (240MHz, 16MB flash QIO, 8MB Octal PSRAM)

#### GPIO mapping verification

All 33 GPIO pins have been cross-verified between three sources with **zero discrepancies**:

| Group | Pins | board_config.h | Retro-Go config.h | KiCad schematic |
|:---|:---|:---|:---|:---|
| Display data D0–D7 | GPIO 4–11 | ✅ | ✅ | ✅ |
| Display control | GPIO 3, 12–14, 45, 46 | ✅ | ✅ | ✅ |
| SD card SPI | GPIO 36–39 | ✅ | ✅ | ✅ |
| I2S audio | GPIO 15–17 | ✅ | ✅ | ✅ |
| D-pad | GPIO 40, 41, 42, 1 | ✅ | ✅ | ✅ |
| Face buttons | GPIO 2, 48, 47, 21 | ✅ | ✅ | ✅ |
| System buttons | GPIO 18, 0 | ✅ | ✅ | ✅ |
| Shoulder buttons | GPIO 35, 19 | ✅ | ✅ | ✅ |
| I2C (IP5306) | GPIO 33, 34 | ✅ | ✅ | ✅ |

**Notes:**
- MENU and SELECT share GPIO 0 in Retro-Go (intentional — 12 physical buttons, 13 logical)
- Joystick (GPIO 20, 44) is in the schematic but optional (not in firmware config)
- GPIO 26–32 are reserved for Octal PSRAM (cannot be used)

#### Display driver: `st7796s_i80.h`

Custom driver replacing Retro-Go's SPI-based `ili9341.h` with 8-bit 8080 parallel interface. Located at `retro-go/components/retro-go/drivers/display/st7796s_i80.h`.

| Feature | Value |
|:---|:---|
| Bus | 8-bit i80 parallel (`esp_lcd_panel_io_i80`) |
| Clock | 20 MHz write clock |
| Resolution | 320x480 portrait |
| Color format | RGB565 (16-bit) |
| DMA | Async with 5-buffer pool |
| Backlight | PWM via LEDC (GPIO 45) |
| Driver ID | `RG_SCREEN_DRIVER 2` |

The driver uses `esp_lcd_panel_io_tx_param` for commands (CASET/RASET) and `esp_lcd_panel_io_tx_color` for async DMA pixel transfers. A completion callback recycles buffers to the pool, providing natural backpressure without explicit sync.

### Phase 3 — All Emulators at Full Speed

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

### Phase 4 — SNES Optimization

Progressive optimization of the snes9x core (see [SNES Deep Dive](#snes-deep-dive) below).

| Step | Optimization | FPS gain | Cumulative |
|:---|:---|:---|:---|
| 4.1 | Baseline snes9x2010 | — | 15-20 fps |
| 4.2 | Critical buffers → IRAM | +8-10 fps | 25-30 fps |
| 4.3 | Audio DSP on Core 1 | +5-8 fps | 30-35 fps |
| 4.4 | Adaptive frameskip | +10 perceived | 35-45 fps perceived |
| 4.5 | Interlaced rendering | +5 perceived | 40-50 fps perceived |

---

## Display Driver

### ST7796S 8-bit Parallel (i80 Bus)

Retro-Go ships with an SPI-only ILI9341 driver. Our hardware uses 8-bit 8080 parallel which requires a custom driver. The firmware uses the [`esp_lcd_st7796`](https://components.espressif.com/components/espressif/esp_lcd_st7796) component with the `esp_lcd_panel_io_i80` bus API.

```
ESP32-S3                      ST7796S (4.0" 320x480)
─────────                     ──────────────────────────
GPIO 4-11  (D0-D7) ────────► DB0-DB7 (8-bit data bus)
GPIO 12    (CS)     ────────► CS  (chip select)
GPIO 14    (DC)     ────────► DC  (data/command)
GPIO 46    (WR)     ────────► WR  (write strobe)
GPIO 3     (RD)     ────────► RD  (read strobe)
GPIO 13    (RST)    ────────► RST (reset)
GPIO 45    (BL)     ────────► LED (backlight PWM via LEDC)
```

GPIO4–11 form a contiguous 8-bit bus, enabling efficient DMA transfers.

### Bandwidth

| Interface | Clock | Throughput | 60fps 320x480 16-bit |
|:---|:---|:---|:---|
| SPI (ILI9341) | 40 MHz | 5.0 MB/s | 54% utilization |
| **8-bit i80 (ours)** | **20 MHz** | **20.0 MB/s** | **14% utilization** |

The 8080 parallel bus has **4x the bandwidth** of SPI, leaving headroom for scaling and double-buffering.

### Frame Scaling

| Source system | Native res | → Display 320x480 | Method |
|:---|:---|:---|:---|
| NES | 256x240 | 256x240 centered | 1:1 letterbox |
| SNES | 256x224 | 256x448 (2x V) | Integer 2x vertical |
| Game Boy | 160x144 | 320x288 (2x both) | Integer 2x |
| Genesis | 320x224 | 320x448 (2x V) | Integer 2x vertical |
| Master System | 256x192 | 256x384 (2x V) | Integer 2x vertical |

The ST7796S at 320x480 is well-suited: most systems are ≤320px wide and can be doubled vertically for a crisp image with black bars.

---

## SNES Deep Dive

### Why SNES is Hard on ESP32-S3

The SNES has three CPU-intensive subsystems that must be emulated in real-time:

```
Frame time budget: 16.67 ms (for 60 fps)

┌────────────────────────────────────────────┐
│ 65C816 CPU emulation         ~4.5 ms  27%  │
│ PPU rendering (2 BG layers)  ~5.0 ms  30%  │
│ SPC700 audio DSP             ~8.0 ms  48%  │  ← bottleneck
│ Display transfer             ~1.5 ms   9%  │
├────────────────────────────────────────────┤
│ TOTAL                       ~19.0 ms 114%  │  ← over budget
└────────────────────────────────────────────┘
```

At 114% of the frame budget on a single core, SNES cannot reach 60fps without optimizations.

### Optimization 1 — IRAM Buffer Placement

**Problem:** Octal PSRAM at 80MHz has ~100ns access latency. Internal SRAM has ~10ns (10x faster). The snes9x core does thousands of random-access reads per frame into screen buffers and tile caches.

**Solution** (from [fcipaq/snes9x_esp32](https://github.com/fcipaq/snes9x_esp32)):

| Buffer | Size | Default | Optimized |
|:---|:---|:---|:---|
| Screen buffer | 115 KB | PSRAM | **IRAM** |
| Tile cache | ~32 KB | PSRAM | **IRAM** |
| CPU opcode table | ~8 KB | Flash | **IRAM** |
| Subscreen | 115 KB | PSRAM | **Shared with Screen** |

The "Subscreen = Screen" hack shares a single buffer for both layers, halving VRAM usage and allowing the main screen buffer to fit in the 520KB internal SRAM.

**Expected gain:** +8-10 fps (from 15-20 → 25-30 fps)

### Optimization 2 — Dual-Core Audio Offloading

**Problem:** `S9xMixSamples()` (SPC700 DSP emulation) takes ~8ms per frame — nearly half the budget.

**Solution:** Dedicate Core 1 entirely to audio processing:

```
Core 0 (main):                 Core 1 (audio):
  65C816 CPU emulation           SPC700 DSP emulation
  PPU rendering                  S9xMixSamples()
  Display transfer               I2S DMA feed
  Input polling

  ~10.5 ms/frame                 ~8.0 ms/frame
  → 95 fps theoretical           (runs in parallel)
```

Communication via a lock-free ring buffer: Core 0 pushes audio commands, Core 1 consumes and mixes asynchronously.

**Expected gain:** +5-8 fps (from 25-30 → 30-35 fps)

### Optimization 3 — Adaptive Frameskip

Instead of rendering every frame, skip rendering when behind schedule while still running the CPU/audio emulation:

```
Frame 1: emulate + render  (16ms)
Frame 2: emulate only      (8ms)   ← skipped render saves ~8ms
Frame 3: emulate + render  (16ms)
Frame 4: emulate only      (8ms)
...
Average: 12ms/frame → ~45 fps perceived with 22 frames rendered
```

The game logic stays at full speed (60 ticks/sec) but the screen updates at 22-30 fps. For RPGs and puzzle games this is visually indistinguishable from full speed.

**Expected gain:** +10 perceived fps (from 30-35 → 35-45 fps perceived)

### Optimization 4 — Interlaced Rendering (experimental)

Render only even rows on even frames and odd rows on odd frames:

```
Frame N:   render rows 0, 2, 4, 6, ...  (half the PPU work)
Frame N+1: render rows 1, 3, 5, 7, ...  (other half)
```

Doubles apparent framerate at the cost of slight vertical flicker. Works well for static scenes (menus, dialogue), visible during fast horizontal scrolling.

**Expected gain:** +5 perceived fps

### Optimization 5 — Audio Profiles

The SPC700 audio DSP is the single biggest CPU bottleneck at ~8ms/frame (48% of budget). Three selectable profiles trade audio quality for frame rate, toggled in-game via **Menu button → Audio: Full / Fast / OFF**.

#### Profile Comparison

| Profile | Sample rate | Interpolation | Echo/Reverb | Channels | DSP time | Frame budget used |
|:---|:---|:---|:---|:---|---:|---:|
| **Full** | 32 kHz | Gaussian (4-tap) | Yes | Stereo | ~8.0 ms | 48% |
| **Fast** | 16 kHz | Linear (2-tap) | No | Mono | ~2.5 ms | 15% |
| **OFF** | — | — | — | — | 0 ms | 0% |

#### CPU Timing Breakdown per Profile

```
Frame time budget: 16.67 ms (60 fps)

                        Audio Full    Audio Fast    Audio OFF
                        ──────────    ──────────    ─────────
65C816 CPU emulation      4.5 ms        4.5 ms       4.5 ms
PPU rendering             5.0 ms        5.0 ms       5.0 ms
SPC700 audio DSP          8.0 ms        2.5 ms       0.0 ms
Display transfer          1.5 ms        1.5 ms       1.5 ms
                        ──────────    ──────────    ─────────
TOTAL (single-core)      19.0 ms       13.5 ms      11.0 ms
Theoretical fps            53            74           91
```

With dual-core audio offloading, the audio DSP runs in parallel on Core 1 and no longer blocks the main loop — but only if Core 1 finishes within the frame budget:

```
                        Audio Full    Audio Fast    Audio OFF
                        ──────────    ──────────    ─────────
Core 0 (CPU+PPU+LCD)    11.0 ms       11.0 ms      11.0 ms
Core 1 (audio DSP)        8.0 ms        2.5 ms       0.0 ms
Bottleneck               11.0 ms       11.0 ms      11.0 ms
Theoretical fps            91            91           91
```

With Fast or OFF, Core 1 finishes well within budget, so the bottleneck is always Core 0 at 11ms. With Full audio, Core 1 at 8ms is still under Core 0's 11ms — but in practice, cache contention and memory bus sharing between cores reduce the effective throughput.

### SNES Performance Summary

#### With Audio Full (32kHz Gaussian stereo)

| Level | Optimizations applied | Rendered fps | Perceived fps | Best for |
|:---|:---|---:|---:|:---|
| Baseline | None | 15-20 | 15-20 | Not playable |
| **Good** | **IRAM + dual-core** | **25-30** | **25-30** | **Turn-based RPGs** |
| **Better** | **+ adaptive frameskip** | **20-25** | **35-45** | **RPGs, puzzle, platformers** |
| Best | + interlaced + all | 25-30 | 40-50 | Most games playable |

#### With Audio Fast (16kHz linear mono)

| Level | Optimizations applied | Rendered fps | Perceived fps | Best for |
|:---|:---|---:|---:|:---|
| Baseline | Audio Fast only | 25-30 | 25-30 | Barely playable |
| **Good** | **IRAM + dual-core** | **35-40** | **35-40** | **Most games** |
| **Better** | **+ adaptive frameskip** | **30-35** | **45-55** | **All genres** |
| **Best** | **+ interlaced + all** | **35-40** | **55-60** | **Near full-speed** |

#### With Audio OFF

| Level | Optimizations applied | Rendered fps | Perceived fps | Best for |
|:---|:---|---:|---:|:---|
| Baseline | Audio OFF only | 30-35 | 30-35 | Playable |
| Good | IRAM + dual-core | 40-45 | 40-45 | Most games |
| Better | + adaptive frameskip | 35-40 | 50-55 | All genres |
| Best | + interlaced + all | 40-45 | 55-60 | Full-speed |

:::tip Sweet spot: Audio Fast + all optimizations
With Audio Fast and all optimizations applied, SNES reaches **55-60 perceived fps** — near full-speed for virtually all games. Audio quality is reduced (16kHz mono, no echo) but still very usable for gameplay. This is the recommended default for action games and platformers.
:::

### Game Compatibility by Genre

| Genre | Examples | Audio Full | Audio Fast | Audio OFF |
|:---|:---|:---|:---|:---|
| Turn-based RPG | FF6, Chrono Trigger, Earthbound | **35-45** | **50-55** | **55-60** |
| Puzzle | Tetris Attack, Dr. Mario, Panel de Pon | **40-50** | **55-60** | **55-60** |
| Simple platformer | Super Mario World (early levels) | **30-40** | **45-55** | **50-60** |
| Complex platformer | DKC, Yoshi's Island | **20-30** | **35-45** | **40-50** |
| Action / Mode 7 | F-Zero, Star Fox, Mario Kart | **15-25** | **30-40** | **35-45** |

All values assume all optimizations enabled (IRAM + dual-core + frameskip + interlaced).

:::tip SNES on v2 (ESP32-P4)
The ESP32-P4 at 400MHz with 2.1x the CoreMark score achieves ~50fps SNES with Full audio enabled. A future v2 PCB with ESP32-P4 would bring SNES to full-speed Audio Full for all genres.
:::

---

## Reference Projects

| Project | What it does | Useful for |
|:---|:---|:---|
| [ducalex/retro-go](https://github.com/ducalex/retro-go) | Multi-system emulator for ESP32 | Base framework (our fork) |
| [fcipaq/snes9x_esp32](https://github.com/fcipaq/snes9x_esp32) | Optimized SNES on ESP32-P4/S3 | IRAM optimizations, ~45fps on S3 |
| [ohdarling/retro-go](https://github.com/ohdarling/retro-go) | Retro-Go fork for ESP32-S3 | S3-specific patches |
| [esp-box-emu](https://github.com/esp-cpp/esp-box-emu) | Emulators on ESP32-S3-BOX | LVGL UI reference |
| [atanisoft/esp_lcd_ili9488](https://github.com/atanisoft/esp_lcd_ili9488) | ILI9488 ESP-IDF driver | Display driver reference |
| [libretro/snes9x2010](https://github.com/libretro/snes9x2010) | Lightweight snes9x fork | SNES core source |

---

## Memory Map

```
┌─────────────────────────────────────────────────┐
│ Internal SRAM (520 KB)                          │
│   ├─ FreeRTOS stacks          ~32 KB            │
│   ├─ DMA buffers (display)    ~40 KB            │
│   ├─ I2S audio DMA            ~8 KB             │
│   ├─ Emulator hot buffers     ~150 KB (SNES)    │
│   ├─ Input / misc             ~10 KB            │
│   └─ Free                     ~280 KB           │
├─────────────────────────────────────────────────┤
│ Octal PSRAM (8 MB)                              │
│   ├─ ROM image                up to 6 MB        │
│   ├─ Emulator state / VRAM    ~512 KB           │
│   ├─ Frame buffer (x2)        ~300 KB           │
│   ├─ Save states              ~256 KB           │
│   └─ Free                     ~1 MB             │
├─────────────────────────────────────────────────┤
│ Flash (16 MB)                                   │
│   ├─ Firmware                 ~2-4 MB           │
│   ├─ NVS (settings)          ~64 KB             │
│   ├─ OTA partition            ~4 MB (optional)  │
│   └─ Free / SPIFFS            ~8 MB             │
└─────────────────────────────────────────────────┘
```

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
