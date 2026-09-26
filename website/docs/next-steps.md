---
id: next-steps
title: Next Steps
sidebar_position: 4.5
---

# Next Steps

Studies for new consoles to emulate after the current ones. These are
proposals, not commitments. What is still needed to close the current
console (audio, known emulator bugs, hardware backlog) is under
[Remediation](/docs/remediation).

Every figure on these pages comes from a measurement (`scripts/emu_check.py`,
`scripts/snes_bench.py`, the serial stats line), and new work keeps that
rule. The feasibility tiers below are estimates until a port is measured.

## 1. More systems, up to the PlayStation

A realistic ranking for the ESP32-S3 (2 × 240 MHz, 8 MB PSRAM). All of
these are **estimates** from the original hardware's CPU and ROM sizes;
only a port and a measurement settle them.

| Tier | Systems | Why |
|:---|:---|:---|
| 🟢 **Should fit** | Atari 7800, Atari 5200/800, WonderSwan / Color, Vectrex, Intellivision, Odyssey² / Videopac, ZX Spectrum, Amstrad CPC | 1–4 MHz 8/16-bit CPUs, small ROMs, lighter than the NES/SMS cores that already run at 60 |
| 🟡 **Possible with work** | PC Engine CD, Commodore 64, Game Boy Advance | PCE CD reuses the PCE core (60 fps at 43% busy) plus CD audio streamed from the SD. C64 needs a cycle-accurate video chip. GBA needs an ARM7 interpreter at 16.78 MHz: expect slow, a measurement would say how slow |
| 🔴 **Out of reach on this chip** | Sega CD, 32X, Neo Geo, Virtual Boy, PlayStation, Saturn, N64 | Too many fast CPUs (32X: two SH-2 at 23 MHz; Sega CD: a second 68000), ROMs larger than the 8 MB PSRAM (Neo Geo up to ~90 MB), or 3D hardware |

**PlayStation.** A MIPS R3000A at 33.9 MHz plus a geometry coprocessor, a
GPU with 1 MB of VRAM and a sound chip. The emulators that run it on cheap
handhelds depend on a dynarec that translates MIPS into the host's machine
code; there is none for Xtensa, and an interpreter would be many times too
slow. Not realistic on the ESP32-S3, and doubtful even on an ESP32-P4
without a RISC-V dynarec.

## 2. Arcade (MAME)

Full MAME is far too large for a microcontroller, but the classic 8-bit
arcade boards are within reach, the same class of work as the home
consoles above.

| Tier | Boards | Approach |
|:---|:---|:---|
| 🟢 **Should fit** | Pac-Man, Galaga, Donkey Kong, Space Invaders, Frogger and similar Z80 / 6502 / 8080 boards of 1978–84 | Port the drivers one by one from an old, small MAME release, or follow the approach of ESP32 projects that already run a handful of these games |
| 🟡 **Hard** | 68000 boards (Sega System 16, Capcom CPS1) | One 10 MHz 68000 plus sound CPUs: the Genesis core shows this is at the edge |
| 🔴 **No** | CPS2, Neo Geo MVS, 3D boards | CPU load and ROM size, as in the table above |

**ROMs.** Arcade ROMs are copyrighted. For testing, the MAME team
publishes a few games whose owners allowed free distribution (on
mamedev.org), for example Gridlee and Robby Roto.

## Suggested order

1. Close [Remediation](/docs/remediation) first: those bugs are on
   the board today and affect every game.
2. Port one 🟢 system and one classic arcade board, to size the porting
   effort before planning the rest.
3. Decide on the 🟡 systems from those two measurements.
