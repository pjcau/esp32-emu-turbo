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

### Phase 1 — Hardware Abstraction (bootstrap)

Standalone ESP-IDF project to validate all hardware before integrating Retro-Go.

| Step | Task | Details |
|:---|:---|:---|
| 1.1 | ESP-IDF v5.x project setup | `idf.py create-project`, sdkconfig for N16R8 |
| 1.2 | ILI9488 display driver (i80 8-bit parallel) | `esp_lcd_panel_io_i80` API, 14 GPIO (D0-D7 + CS/DC/WR/RD/RST/BL) |
| 1.3 | Display test pattern | Color bars, fill speed, FPS counter |
| 1.4 | SD card (SPI mode) | `sdmmc_host` SPI, FAT32, ROM file listing |
| 1.5 | 12-button input | GPIO interrupt + 1ms polling, debounce via hardware RC |
| 1.6 | I2S audio output | `i2s_std_config`, 32kHz 16-bit mono, PAM8403 amplifier |
| 1.7 | Power management | IP5306 status read, battery LED control |

### Phase 2 — Retro-Go Integration

Fork and adapt Retro-Go for our hardware.

| Step | Task | Details |
|:---|:---|:---|
| 2.1 | Fork `ducalex/retro-go` | Branch `esp32-emu-turbo` |
| 2.2 | Create target `targets/esp32-emu-turbo/` | `config.h` with GPIO map, display config, sdkconfig.defaults |
| 2.3 | New display driver `ili9488_i80.h` | Replace SPI ILI9341 driver with i80 parallel |
| 2.4 | Frame scaling | 256x224 → 320x480 (integer scale + letterbox) |
| 2.5 | Input mapping | `rg_input` config for D-pad, ABXY, Start, Select, L, R, Menu |
| 2.6 | Audio routing | I2S output config for PAM8403 |
| 2.7 | First boot: NES test | nofrendo running Super Mario Bros at 60fps |

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

### ILI9488 8-bit Parallel (i80 Bus)

Retro-Go ships with an SPI-only ILI9341 driver. Our hardware uses 8-bit 8080 parallel which requires a custom driver.

```
ESP32-S3                      ILI9488 (3.95" 320x480)
─────────                     ──────────────────────────
GPIO 33-40 (D0-D7) ────────► DB0-DB7 (8-bit data bus)
GPIO 41    (CS)     ────────► CS  (chip select)
GPIO 42    (DC)     ────────► DC  (data/command)
GPIO 45    (WR)     ────────► WR  (write strobe)
GPIO 46    (RD)     ────────► RD  (read strobe, optional)
GPIO 47    (RST)    ────────► RST (reset)
GPIO 48    (BL)     ────────► LED (backlight PWM)
```

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

The ILI9488 at 320x480 is well-suited: most systems are ≤320px wide and can be doubled vertically for a crisp image with black bars.

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

### SNES Performance Summary

| Level | Optimizations applied | Rendered fps | Perceived fps | Best for |
|:---|:---|---:|---:|:---|
| Baseline | None | 15-20 | 15-20 | Not playable |
| **Good** | **IRAM + dual-core** | **25-30** | **25-30** | **Turn-based RPGs** |
| **Better** | **+ adaptive frameskip** | **20-25** | **35-45** | **RPGs, puzzle, platformers** |
| Best | + interlaced + all | 25-30 | 40-50 | Most games playable |

### Game Compatibility by Genre

| Genre | Examples | Difficulty | Expected fps |
|:---|:---|:---|:---|
| Turn-based RPG | FF6, Chrono Trigger, Earthbound | Low CPU | **35-45** |
| Puzzle | Tetris Attack, Dr. Mario, Panel de Pon | Minimal animation | **40-50** |
| Simple platformer | Super Mario World (early levels) | 1-2 BG layers | **30-40** |
| Complex platformer | DKC, Yoshi's Island | Many effects | **20-30** |
| Action / Mode 7 | F-Zero, Star Fox, Mario Kart | Heavy 3D math | **15-25** |

:::tip SNES on v2 (ESP32-P4)
The ESP32-P4 at 400MHz with 2.1x the CoreMark score achieves ~50fps SNES with audio enabled. A future v2 PCB with ESP32-P4 would bring SNES to near full-speed for all genres.
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
