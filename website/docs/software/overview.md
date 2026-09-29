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

Measured on the v4.9.0 first article (article 0003) with `scripts/emu_check.py`
and `scripts/snes_bench.py`, last rerun 2026-09-27. "Drawn" is how many of the
60 emulated frames reach the display each second; the full per-step table,
test ROMs and fixes are in
[Firmware — Phase 3](/docs/software/firmware#phase-3--all-emulators-at-full-speed).

| Core | System | Native res | QEMU benchmark | Measured on the board |
|:---|:---|:---|:---|:---|
| nofrendo | NES / Famicom | 256x240 | 655 fps (10.9x) | ✅ 60 fps, BUSY 36%, 30 drawn |
| gnuboy | Game Boy | 160x144 | 432 fps (7.2x) | ✅ 60 fps, BUSY 34%, 30 drawn |
| gnuboy | Game Boy Color | 160x144 | 393 fps (6.5x) | ✅ 60 fps, BUSY 35–53%, 30 drawn |
| smsplus | Master System / Game Gear / SG-1000 / ColecoVision | 256x192 | 481 fps (8.0x) | ✅ 60 fps, BUSY 31–40%, 55 drawn |
| pce-go | PC Engine / TurboGrafx-16 | 256x240 | 617 fps (10.3x) | ✅ 60 fps, BUSY 33–43%, 30 drawn |
| gwenesis | Sega Genesis / Mega Drive | 320x224 | — | ✅ 59.4 fps, BUSY 94%, 29 drawn (YM2612 on core 1) |
| RACE | Neo Geo Pocket / Color | 160x152 | — | ✅ 60 fps, BUSY 93–99%, ~29 drawn |
| ~~Stella~~ | Atari 2600 | — | — | removed 2026-09-29: not needed |
| ~~fMSX~~ | MSX | — | — | removed 2026-09-29: not needed; its partition went to GBA (`gbsp`) |
| mame-go (MAME 0.37b5) | Arcade (8-bit boards, 68000 boards) | various | — | ✅ Pac-Man / 1942 / Blood Bros. 60 fps; Aero Fighters 47–57 — see [Arcade](/docs/next-steps/arcade) |
| mame-go (Neo Geo driver) | Neo Geo MVS (sprites paged from the SD) | 304x224 | — | 🟡 Sonic Wings 2 38–50 emulated fps; Metal Slug 2 (49 MB) 28–33 in play — see [Neo Geo on v3](/docs/next-steps/arcade#neo-geo-on-v3-sprites-paged-from-the-sd-card-2026-09-27) |
| snes9x | **SNES / Super Famicom** | 256x224 | 556 fps CPU (9.3x) | ✅ 60 emulated fps on 6 of 7 test scenes, 19–26 drawn; Super Mario Kart 57 (DSP-1) |
| snes9x + SuperFX | SNES Star Fox | 256x224 | — | ✅ 53–60 emulated fps, 7–10 drawn (GSU on core 1) |
| prboom-go | DOOM (Freedoom) | 320x200 | — | ✅ 35 fps (engine rate), BUSY 100% |
| wolf3d-go | Wolfenstein 3D (shareware) | 320x200 | — | ✅ 62 fps, BUSY 34% |
| opentyrian-go | OpenTyrian (Tyrian 2.1 freeware) | 320x200 | — | ✅ 36 fps (engine rate 35), BUSY ~30% |
| duke3d-go | Duke Nukem 3D (shareware) | 320x200 | — | ✅ playable, 48–53 fps in E1L1 |
| quake-go | Quake (shareware, software renderer) | 320x200 | — | ✅ runs, 21–44 fps (mostly 25–35) in the attract demo |
| ~~handy~~ | Atari Lynx | — | — | removed 2026-09-29: not needed |
| ~~gw-emulator~~ | Game & Watch | — | — | removed 2026-09-29: not needed |

The QEMU column is a CPU-only benchmark (6.5–10.9x headroom for the 8-bit
cores). It could never show the SNES bottleneck: the snes9x PPU renderer, not
CPU+APU emulation (~8.5 ms per frame). The Phase 4 renderer work took SNES
from 45–52 to 60 emulated fps — see
[SNES Optimization](/docs/software/snes-optimization). Open items (DOOM heap
drift, Mario Kart DSP-1, Neo Geo Pocket near the CPU limit) are tracked in
[Remediation — Emulators](/docs/remediation/emulators).

---

## Implementation Roadmap

| Phase | Description | Status | Details |
|:---|:---|:---|:---|
| **Phase 1** | Hardware Abstraction (ESP-IDF bootstrap) | ✅ Done — validated on the first article (bring-up GREEN 53/0/6) | [Firmware](/docs/software/firmware) |
| **Phase 2** | Retro-Go Integration (fork + custom drivers) | ✅ Done — runs on the first article, NES at 60 fps (2026-09-12) | [Firmware](/docs/software/firmware#phase-2--retro-go-integration) |
| **Phase 3** | All Emulators at Full Speed | ✅ Almost done — every tested core at full speed, plus new cores and PC game ports (2026-09-21 → 09-27) | [Firmware](/docs/software/firmware#phase-3--all-emulators-at-full-speed) |
| **Phase 4** | SNES Optimization (renderer → 60 FPS) | ✅ Milestone A done — 60 emulated fps on all test scenes but Mario Kart (57); next: S-DSP on core 1, more drawn frames | [SNES Optimization](/docs/software/snes-optimization) |
| **Phase 5** | Firmware update from SD card (cable-free flashing) | 🗓️ Future | [below](#future--firmware-update-from-sd-card) |

### Future — firmware update from SD card

Today every firmware change is flashed over USB (`rg_tool.py install`, a
full `.img`). The plan is to make the SD card the normal update path, so
the board can be updated on battery, with no cable and no esptool on the
host. USB stays for the very first flash and for recovery only.

**Why not the launcher itself.** The ESP32-S3 ROM bootloader only knows
USB/UART, and an app cannot safely rewrite the partition it runs from.
Retro-go's upstream solution (ODROID-GO, Esplay) is a separate **flasher
app in the `factory` partition**, which is never overwritten by an update.

**What is missing for this board** (checked 2026-09-24):

- `retro-go/components/retro-go/targets/esp32-emu-turbo/env.py` has
  `FW_FORMAT = "none"`, so `rg_tool.py build-fw` produces no `.fw`.
- The target `config.h` defines neither `RG_APP_FACTORY` nor
  `RG_UPDATER_APPLICATION`, so the launcher updater only checks versions;
  `RG_UPDATER_GITHUB_RELEASES` still points at upstream `ducalex/retro-go`.
- There is no flasher app.

**Planned work:**

1. **Flasher app** (~200–300 KB) in `factory`: on boot, look for
   `/sd/firmware/*.fw` or a held recovery button (`RG_RECOVERY_BTN`); verify
   the checksum, write the app partitions with a progress bar on the
   display, rename the file so it is not re-flashed on the next boot, and
   reboot. Otherwise jump straight to the launcher.
2. **`.fw` format:** reuse the Esplay/ODROID format `rg_tool.py` already
   packs; enable it in `env.py`.
3. **Partition table:** `factory` = flasher, then the existing apps.
4. **Launcher:** set `RG_APP_FACTORY` / `RG_UPDATER_APPLICATION` /
   `RG_UPDATER_DOWNLOAD_LOCATION`, point the release URL at this repo.
5. **Tooling:** `make firmware-sd` builds the `.fw` ready to copy to the card.

**Pairs with Wi-Fi:** the launcher is already built with networking and has
a WebUI that uploads files to the SD, so "upload `.fw` from the browser →
reboot to flash" becomes a fully wireless update without adding an OTA
stack (the emulator cores keep networking off to save internal RAM).

**Acceptance:** an update applied from SD on a first article, a deliberately
broken `.fw` rejected by the checksum, and a boot-looping launcher
recovered via the recovery button — all without a USB cable.

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
| [pcgamer404/retro-go-pro](https://github.com/pcgamer404/retro-go-pro) | Retro-Go fork with PC game ports | Source of our Wolfenstein 3D and Quake apps |
| [DynaMight1124/retro-go](https://github.com/DynaMight1124/retro-go) | Retro-Go "megapack" fork | Source of our OpenTyrian app |

What the other Retro-Go forks add, and what is worth pulling in:
[Retro-Go Forks Survey](/docs/software/retro-go-forks-survey).
