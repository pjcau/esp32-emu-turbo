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
| **Phase 5** | v2 Audio Coprocessor (ESP32-S3-MINI-1) | 📋 Planned | [SNES Optimization](/docs/software/snes-optimization#phase-5--v2-hardware-audio-coprocessor) |

---

## Display Driver

### ILI9488 8-bit Parallel (i80 Bus)

Retro-Go ships with an SPI-only ILI9341 driver. Our hardware uses 8-bit 8080 parallel which requires a custom driver. The firmware uses the [`atanisoft/esp_lcd_ili9488`](https://components.espressif.com/components/atanisoft/esp_lcd_ili9488) component with the `esp_lcd_panel_io_i80` bus API.

:::warning There is no `espressif/esp_lcd_ili9488`
`idf_component.yml` required that non-existent component for months, so the
firmware had never actually built. The namespace is **`atanisoft/`** — see
[Virtual Bench findings](/docs/vbench/findings-and-limits).
:::

```
ESP32-S3                      ILI9488 (3.95" 320x480)
─────────                     ──────────────────────────
GPIO 4-11  (D0-D7) ────────► DB0-DB7 (8-bit data bus)
GPIO 12    (CS)     ────────► CS  (chip select)
GPIO 14    (DC)     ────────► DC  (data/command)
GPIO 46    (WR)     ────────► WR  (write strobe)
+3V3       (RD)     ────────► RD  (tied HIGH, no read-back)
GPIO 13    (RST)    ────────► RST (reset)
+5V via R27 (20 Ω)  ────────► LED-A (always-on backlight, net LED_BLA)
```

GPIO4–11 form a contiguous 8-bit bus, enabling efficient DMA transfers.

### Bandwidth

A full 320×480 RGB565 frame at 60 fps needs **18.4 MB/s**:

| Interface | Clock | Throughput | 60fps 320x480 16-bit |
|:---|:---|:---|:---|
| SPI (ILI9341) | 40 MHz | 5.0 MB/s | **368% — impossible** |
| **8-bit i80 (ours)** | **20 MHz** | **20.0 MB/s** | **92% utilization** |

The 8080 parallel bus has **4x the bandwidth** of SPI. Full-screen 60 fps fits with
~8% margin; the real headroom for scaling and double-buffering comes from the fact
that emulator frames are letterboxed, not full-screen.

### Frame Scaling

The framebuffer is **480x320 landscape** (the panel is mounted along the
handheld's long axis; the first article settled this on 2026-09-11 — the
earlier "portrait, 2x vertical" plan would have shown games rotated by
90°). Retro-Go's own scaler handles every core:

| Source system | Native res | → Display 480x320 | Method |
|:---|:---|:---|:---|
| NES | 256x240 | 320x240 centered (fit) or 427x320 (fill) | Retro-Go scaler, user-selectable |
| SNES | 256x224 | 366x320 (fit, 1.43x) | Retro-Go scaler |
| Game Boy | 160x144 | 320x288 (2x both) | Integer 2x |
| Genesis | 320x224 | 457x320 (fit) | Retro-Go scaler |
| Master System | 256x192 | 427x320 (fit) | Retro-Go scaler |

Every core fits inside 480x320 with less than 1.5x scaling, so the 20 MHz
8-bit bus budget above (full-frame 60 fps with ~8% margin) still holds.

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
