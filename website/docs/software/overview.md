---
id: software-overview
title: Software Overview
sidebar_position: 1
slug: /software
---

# Software

The console runs a fork of [Retro-Go](https://github.com/ducalex/retro-go), the
multi-system emulator for ESP32 devices: a launcher with one tab per system, a
ROM browser on the SD card, save states, and one framework for display, sound
and buttons. The fork adds the ESP32 Emu Turbo target, a display driver for the
8-bit parallel ILI9488, and the apps that upstream does not have.

## The pages of this section

| Page | What it has |
|:---|:---|
| [Firmware](/docs/software/firmware) | the build on the board, the flash layout, building, writing, updating from the SD card, the card's folders |
| [Emulators — tests and speed](/docs/software/emulators) | every system, the game it was checked with, its speed on the board, the buttons, the system files |
| [Optimizations](/docs/software/optimizations) | what made SNES, GBA, Mega Drive, arcade and Atari 7800 faster, measured, and what did not pay |
| [Simulator & QEMU](/docs/software/simulator) | testing without the board |
| [Boot Splash](/docs/software/boot-splash) | the "GAME BRO!" boot animation |

What the other Retro-Go forks add, and what was taken from them, is in
[Retro-Go forks survey](/docs/next-steps/retro-go-forks-survey).

## What runs

Nearly every system runs at its full speed; the ones that do not yet are the
68000 arcade boards (Neo Geo, CPS1, System 16: 38–58 fps), the GBA (46–59) and
the Atari 7800 (58–59). The table is on [Emulators](/docs/software/emulators).

| App | Systems |
|:---|:---|
| retro-core | NES, SNES (SuperFX, DSP-1), Game Boy, Game Boy Color, Master System, Game Gear, SG-1000, ColecoVision, PC Engine, Atari Lynx |
| gwenesis | Mega Drive |
| gbsp | Game Boy Advance (with an Xtensa dynarec) |
| retro-extra | Atari 2600, Neo Geo Pocket, Arcade 3D Racing |
| retro-home | Atari 5200, Atari 7800, Commodore 64 |
| fmsx | MSX 1 / 2 |
| mame-go | Arcade (MAME 0.37b5), Neo Geo, Capcom CPS1, Sega System 16 |
| prboom-go, wolf3d-go, opentyrian-go | DOOM, Wolfenstein 3D, OpenTyrian |
| sdapp | OutRun (Cannonball), run from the SD card |

## Display

The ILI9488 (3.95", 480×320 landscape) is driven over an **8-bit 8080 parallel
bus** at 20 MHz (GPIO4–11 data, async DMA), 20 MB/s, about four times what SPI
gives. A full frame takes about 15 ms, so roughly 60 frames a second is the
most any app can show. Retro-Go's scaler fits every system in 480×320 with
less than 1.5× scaling. The backlight is wired to +5 V on the board.

![ESP32-S3 to ILI9488 8080 wiring: GPIO4-11 data bus, CS GPIO12, DC GPIO14, WR GPIO46, RD tied to +3V3, RST GPIO13, backlight from +5V via R27](/img/diagrams/wiring-lcd-8080.svg)

## Memory

![Memory map: internal SRAM 520 KB, Octal PSRAM 8 MB and flash 16 MB, with what lives in each](/img/diagrams/sw-memory-map.svg)

## Sound and buttons

Sound is PDM on one pin (GPIO17) into the PAM8403 amplifier; every app plays at
32 kHz (other rates misbehaved on the PDM output). The 12 buttons are read
directly on GPIOs; MENU shares GPIO0 with SELECT.

## Where things came from

| Project | Used for |
|:---|:---|
| [ducalex/retro-go](https://github.com/ducalex/retro-go) | the base of the fork |
| [atanisoft/esp_lcd_ili9488](https://components.espressif.com/components/atanisoft/esp_lcd_ili9488) | display driver (the namespace is `atanisoft/`, not `espressif/`) |
| [pcgamer404/retro-go-pro](https://github.com/pcgamer404/retro-go-pro) | Wolfenstein 3D, Quake |
| [DynaMight1124/retro-go](https://github.com/DynaMight1124/retro-go) | OpenTyrian |
| [libretro mame2000](https://github.com/libretro/mame2000-libretro) | the arcade app |
| [libretro gpSP](https://github.com/libretro/gpsp) | Game Boy Advance |
| [libretro ProSystem](https://github.com/libretro/prosystem-libretro) | Atari 7800 |
| [MCUME](https://github.com/Jean-MarcHarvengt/MCUME) | Atari 5200 (Atari800), Commodore 64 (Teensy64) |
| [fMSX](https://fms.komkon.org/fMSX/) | MSX |
