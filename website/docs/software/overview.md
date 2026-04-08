---
id: software-overview
title: Software Overview
sidebar_position: 1
slug: /software
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

| Core | System | Resolution | QEMU Benchmark | FPS on ESP32-S3 |
|:---|:---|:---|:---|:---|
| nofrendo | NES / Famicom | 256x240 | 655 fps (10.9x) | **60 fps** |
| gnuboy | Game Boy | 160x144 | 432 fps (7.2x) | **60 fps** |
| gnuboy | Game Boy Color | 160x144 | 393 fps (6.5x) | **60 fps** |
| smsplus | Master System | 256x192 | 481 fps (8.0x) | **60 fps** |
| smsplus | Game Gear | 160x144 | 484 fps (8.1x) | **60 fps** |
| pce-go | PC Engine / TurboGrafx-16 | 256x240 | 617 fps (10.3x) | **60 fps** |
| handy | Atari Lynx | 160x102 | — | **60 fps** |
| gwenesis | Sega Genesis / Mega Drive | 320x224 | — | **50-60 fps** |
| gw-emulator | Game & Watch | various | — | **60 fps** |
| snes9x | **SNES / Super Famicom** | 256x224 | 556 fps CPU (9.3x) | **~60 fps** (estimated) |

All systems run at full speed on ESP32-S3 N16R8 @ 240MHz. QEMU benchmark confirms 6.5-10.9x headroom vs 60fps target. See [QEMU Benchmark](/docs/software/simulator#qemu-esp32-s3-benchmark) for full details.

---

## Implementation Roadmap

| Phase | Description | Status | Details |
|:---|:---|:---|:---|
| **Phase 1** | Hardware Abstraction (ESP-IDF bootstrap) | ✅ Done | [Firmware](/docs/software/firmware) |
| **Phase 2** | Retro-Go Integration (fork + custom drivers) | ✅ Done | [Firmware](/docs/software/firmware#phase-2--retro-go-integration) |
| **Phase 3** | All Emulators at Full Speed | ⏳ Needs HW | [Firmware](/docs/software/firmware#phase-3--all-emulators-at-full-speed) |
| **Phase 4** | SNES Optimization (30→60 FPS) | 📋 Planned | [SNES Optimization](/docs/software/snes-optimization) |
| **Phase 5** | v2 Audio Coprocessor (ESP32-S3-MINI-1) | 📋 Planned | [SNES Optimization](/docs/software/snes-optimization#phase-5--v2-hardware-audio-coprocessor-esp32-s3-mini-1) |

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
+3V3       (RD)     ────────► RD  (tied HIGH, no read-back)
GPIO 13    (RST)    ────────► RST (reset)
+3V3       (BL)     ────────► LED (always-on via resistor)
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

## Reference Projects

| Project | What it does | Useful for |
|:---|:---|:---|
| [ducalex/retro-go](https://github.com/ducalex/retro-go) | Multi-system emulator for ESP32 | Base framework (our fork) |
| [fcipaq/snes9x_esp32](https://github.com/fcipaq/snes9x_esp32) | Optimized SNES on ESP32-P4/S3 | IRAM optimizations, ~45fps on S3 |
| [ohdarling/retro-go](https://github.com/ohdarling/retro-go) | Retro-Go fork for ESP32-S3 | S3-specific patches |
| [esp-box-emu](https://github.com/esp-cpp/esp-box-emu) | Emulators on ESP32-S3-BOX | LVGL UI reference |
| [atanisoft/esp_lcd_ili9488](https://github.com/atanisoft/esp_lcd_ili9488) | ILI9488 ESP-IDF driver | Display driver reference |
| [libretro/snes9x2010](https://github.com/libretro/snes9x2010) | Lightweight snes9x fork | SNES core source |
