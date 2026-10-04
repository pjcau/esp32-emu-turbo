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
and `scripts/snes_bench.py`; the rows dated 2026-10-03 or 2026-10-04 were
measured again on those days, after the display scaler was rewritten, the
others stand from 2026-09-27/29. "Drawn" is how many of the 60 emulated frames
reach the display each second; the full per-step table,
test ROMs and fixes are in
[Firmware — Phase 3](/docs/software/firmware#phase-3--all-emulators-at-full-speed).

| Core | System | Native res | QEMU benchmark | Measured on the board |
|:---|:---|:---|:---|:---|
| nofrendo | NES / Famicom | 256x240 | 655 fps (10.9x) | ✅ 60 fps, BUSY 39%, 55–60 drawn (2026-10-03) |
| gnuboy | Game Boy | 160x144 | 432 fps (7.2x) | ✅ 60 fps, BUSY 34%, 30 drawn |
| gnuboy | Game Boy Color | 160x144 | 393 fps (6.5x) | ✅ 60 fps, BUSY 35–53%, 30 drawn |
| smsplus | Master System / Game Gear / SG-1000 / ColecoVision | 256x192 | 481 fps (8.0x) | ✅ Game Gear: 6 games at 60 fps, BUSY 31–41%, 32–55 drawn (2026-10-03); GG Aleste 3 runs but the screen stays black. Master System not measured again |
| pce-go | PC Engine / TurboGrafx-16 | 256x240 | 617 fps (10.3x) | ✅ 60 fps (SF2' CE and OutRun, title screens, 2026-10-03) |
| gwenesis | Sega Genesis / Mega Drive | 320x224 | — | ✅ 60 fps, 30 drawn, BUSY 85% (94% before the 2026-10-03 scaler; YM2612 on core 1) |
| RACE | Neo Geo Pocket / Color | 160x152 | — | ✅ 60 fps on 8 games, BUSY 70–89%, ~30 drawn (2026-10-03); opens `.zip` files; a 4 MB cartridge must stay unzipped |
| Stella | Atari 2600 | 160x192 | — | ✅ 60 fps (NTSC: Halo, Donkey Kong, Mario Bros.) and 50 fps (PAL), BUSY 30–68%, half the frames drawn (2026-10-03). Removed 2026-09-29, brought back 2026-10-03 with its cartridge database cut to fit `retro-extra`; opens `.zip` files |
| ~~fMSX~~ | MSX | — | — | removed 2026-09-29: not needed; its partition went to GBA (`gbsp`) |
| mame-go (MAME 0.37b5) | Arcade (8-bit boards, 68000 boards) | various | — | ✅ Pac-Man / 1942 / Blood Bros. 60 fps; Aero Fighters 47–57 — see [Arcade](/docs/next-steps/arcade) |
| mame-go (Neo Geo driver) | Neo Geo MVS (sprites paged from the SD) | 304x224 | — | 🟡 Metal Slug in play: 58 game frames a second, 19 drawn (2026-10-03); every frame drawn: 44 fps. Metal Slug 2 ~42–46 in play (2026-09-28) — see the [Arcade 60 fps plan](/docs/next-steps/arcade-60fps-plan) |
| mame-go (CPS1 driver) | Capcom CPS1 | 384x224 | — | 🟡 in play: Final Fight 55 fps (18 drawn), SF2 CE 46 (15 drawn) (2026-10-04); with every frame drawn 34 and 28 fps — see the [Arcade 60 fps plan](/docs/next-steps/arcade-60fps-plan) |
| gbsp (gpSP, Xtensa dynarec) | Game Boy Advance | 240x160 | — | ✅ 56–60 fps in play, 60 of 60 drawn at 30% busy on a title screen (2026-10-03); Mario Kart 44–51 — see [GBA dynarec](/docs/software/gba-dynarec) |
| snes9x | **SNES / Super Famicom** | 256x224 | 556 fps CPU (9.3x) | ✅ 60 emulated fps on every test scene; Donkey Kong Country 60 fps, 28.5 drawn, BUSY 80% (2026-10-04); Super Mario Kart 57–62, mostly 60 (S-DSP on core 1) |
| snes9x + SuperFX | SNES Star Fox | 256x224 | — | ✅ 53–60 emulated fps, 7–10 drawn (GSU on core 1) |
| prboom-go | DOOM (Freedoom) | 320x200 | — | ✅ 35 fps (engine rate), BUSY 100% |
| wolf3d-go | Wolfenstein 3D (shareware) | 320x200 | — | ✅ 62 fps, BUSY 34% |
| opentyrian-go | OpenTyrian (Tyrian 2.1 freeware) | 320x200 | — | ✅ 36 fps (engine rate 35), BUSY ~30% |
| duke3d-go | Duke Nukem 3D (shareware) | 320x200 | — | ✅ playable, 48–53 fps in E1L1 |
| quake-go | Quake (shareware, software renderer) | 320x200 | — | ✅ 34–41 fps in the attract demo, every frame drawn, BUSY 100% (2026-10-03) |
| handy | Atari Lynx | 160x102 | — | ✅ 56-60 fps on 5 PD demos (2026-10-03, after fixing the BS93 homebrew loader and a divide by zero on silent frames). Removed 2026-09-29, brought back 2026-10-03 |
| cannonball | OutRun (Cannonball engine, native) | 320x224 | — | ✅ 30 fps, the engine's own rate, every frame drawn, BUSY 35–44% (2026-10-04); needs the OutRun rev. B ROM files |
| arcade3d (in `retro-extra`) | Arcade 3D Racing (native OutRun-style game) | 320x240 | — | ✅ 35–71 fps, mostly 47–64 (2026-10-04); steering, brake and menu work; BUSY 100% (it runs as fast as it can) |
| mame-go (System 16 driver) | Sega System 16 (Golden Axe, Alien Syndrome, Wonder Boy III…) | 320x224 | — | 🟡 Golden Axe 50 fps in play (17 drawn), Alien Syndrome 48, Wonder Boy III 45; picture and sound right (2026-10-04, first runs of the driver). Shinobi and Altered Beast not tried |
| ~~gw-emulator~~ | Game & Watch | — | — | removed 2026-09-29: not needed |

**What "60 fps" means here.** Every 8-bit and 16-bit console core runs its
game at full speed (60 emulated frames a second, 50 for PAL), and the GBA
reaches 56–60 in play. Not all of those frames are drawn: the NES, the GBA and
the Game Gear draw nearly all of them, the SNES, the Mega Drive, the Neo Geo
Pocket and the 2600 about one in two. What does **not** run at 60: the 68000
arcade boards (Neo Geo and CPS1: near full game speed with about 20 frames
drawn a second), DOOM 35, OpenTyrian 36, OutRun 30 (their own engine rates),
Quake 34–41 and Duke Nukem 3D 45–53. Game Boy / Color and Master System were
not measured again in October.

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
| **Phase 4** | SNES Optimization (renderer → 60 FPS) | ✅ Milestone A done — 60 emulated fps on every test scene; Mario Kart reached 60 with the S-DSP on core 1 (2026-09-28); next: more drawn frames | [SNES Optimization](/docs/software/snes-optimization) |
| **Phase 5** | Firmware update from SD card (cable-free flashing) | ✅ Done 2026-09-28 — apps (launcher included) updated from `retro-go/update/` on the card; recovery without USB still missing | [Firmware](/docs/software/firmware#firmware-update-from-the-sd-card-2026-09-28) |

### Firmware update from SD card — done (2026-09-28)

The launcher applies app images found in `retro-go/update/` on the card at
boot (`components/retro-go/rg_update.c`), itself included; build, copy
(`scripts/sd_update.py --card` or `--console`) and check are described in
[Firmware → Firmware update from the SD card](/docs/software/firmware#firmware-update-from-the-sd-card-2026-09-28).

Not done from the original plan: a **recovery app in `factory`** (a broken
launcher still needs USB), the `.fw` package format, and "upload from the
browser, reboot to flash" over Wi-Fi (the WebUI works, but the Wi-Fi on this
board is weak — see the known issues).

---

## Display Driver

### ILI9488 8-bit Parallel (i80 Bus)

Retro-Go ships with an SPI-only ILI9341 driver. Our hardware uses 8-bit 8080 parallel which requires a custom driver. The firmware uses the [`atanisoft/esp_lcd_ili9488`](https://components.espressif.com/components/atanisoft/esp_lcd_ili9488) component with the `esp_lcd_panel_io_i80` bus API.

:::warning There is no `espressif/esp_lcd_ili9488`
`idf_component.yml` required that non-existent component for months, so the
firmware had never actually built. The namespace is **`atanisoft/`** — see
[Virtual Bench findings](/docs/vbench/findings-and-limits).
:::

![ESP32-S3 to ILI9488 8080 wiring: GPIO4-11 data bus, CS GPIO12, DC GPIO14, WR GPIO46, RD tied to +3V3, RST GPIO13, backlight from +5V via R27](/img/diagrams/wiring-lcd-8080.svg)

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

![Memory map: internal SRAM 520 KB, Octal PSRAM 8 MB and flash 16 MB, with what lives in each](/img/diagrams/sw-memory-map.svg)

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
