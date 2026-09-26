---
id: emulators
title: Emulators
sidebar_position: 2
---

# Emulators

## Cores built but never measured

These are compiled into the firmware but have not been measured on the
board yet.

| Core | What is missing |
|:---|:---|
| Atari 2600 (Stella) | test ROM ready in `test-roms/a26/` (Halo 2600), not yet on the SD card |
| Duke Nukem 3D | shareware data ready in `test-roms/duke3d/`, not yet on the SD card |
| Atari Lynx (Handy) | a free homebrew ROM (Running Knight) |
| Game & Watch | `.gw` files come from Nintendo's ROMs and artwork; no free source |
| MSX (fMSX) | boots to a black screen: the BIOS files are missing from `/sd/bios/msx/` |

## Known bugs

| Bug | Measured | Next step |
|:---|:---|:---|
| **DOOM memory leak** | 35 fps, but free heap falls from 7.2 to 2.0 MB in 20 s | find the leak before it runs out of memory |
| **Super Mario Kart at 57 fps** | the DSP-1 cartridge chip costs 11 ms per frame | CPU-side work on the DSP-1 emulation |

## Smoother picture on the cores that already reach 60

Every tested core runs at full game speed, but most draw only every other
frame.

- **Frameskip 0 on the light cores.** NES, Game Boy, GBC and PC Engine
  draw 30 fps while the CPU is 30–55% busy, so there is room to draw all
  60.
- **SNES audio (S-DSP) on the second core.** Frees a slice of core 0 for
  the renderer, the same move that took the Genesis from 20 to 30 drawn
  fps.

**Proof:** `scripts/emu_check.py` and `scripts/snes_bench.py`, with the
numbers copied into the
[firmware table](/docs/software/firmware#phase-3--all-emulators-at-full-speed).
