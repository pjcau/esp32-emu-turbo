---
id: more-systems
title: More Systems
sidebar_position: 1
---

# More Systems

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

## Sega family and MAME on the current console (v3)

What the ESP32-S3 board can add without new hardware. Starting point, all
measured on the board: the Mega Drive core (gwenesis) runs at 60 emulated
/ 30 drawn fps, with the 68000 at 5.5 ms, the Z80 at 3.1 ms and the video
chip at 11.3 ms per drawn frame on core 0, and the YM2612 at 6 ms per frame
on core 1. The 16 MB flash has **~8 MB free** after the current app
partitions (which end at 8 MB), so there is room for one or two new
emulator apps.

| System | Verdict on v3 | Why |
|:---|:-:|:---|
| **Mega Drive / Genesis** | ✅ done | 60 emulated / 30 drawn. Drawing all 60 would need ~20 ms per frame against 16.7 ms, so 30–40 drawn is the ceiling without deeper VDP work |
| **Sega Pico** | 🟢 feasible | a Mega Drive without the Z80 and the YM2612, plus a simple ADPCM chip: lighter than what already runs. PicoDrive emulates it; the pen and page tablet map to the D-pad and buttons. A niche library of edutainment titles |
| **Sega CD / Mega CD** | 🟡 at the limit | adds a second 68000 at 12.5 MHz (~9 ms per frame by scaling the measured 5.5 ms), a PCM chip and CD audio. With the sub-CPU on core 1 next to the YM2612, core 1 reaches ~15–17 ms of its 16.7 ms, and the two 68000s must stay in step across cores. Expect heavy frameskip and slowdowns in demanding scenes. Needs a different emulator (gwenesis has no CD support: PicoDrive with its C 68000 core), the Sega CD BIOS supplied by the user, and bin/cue images (CHD decompression is too heavy) |
| **32X** | 🔴 no | two SH-2 CPUs at 23 MHz on top of the Mega Drive: an interpreter needs several hundred MHz of CPU per SH-2, and PicoDrive's SH-2 dynarec has no Xtensa backend |
| **Classic arcade (MAME)** | 🟢 feasible | Z80 / 6502 / 8080 boards of 1978–85 (Pac-Man, Galaga, Donkey Kong, Frogger, 1942, Bomb Jack…). See [Arcade (MAME)](/docs/next-steps/arcade#on-the-current-console-v3) |
| **Capcom CPS1** | 🟡 at the limit | one 68000 at 10 MHz (~7 ms by scaling) + Z80 + YM2151 (FM, on core 1 like the YM2612) and a heavier tile / sprite renderer at 384 × 224. ROM sets of 2–6 MB fit the 8 MB PSRAM. Frameskip needed |

**One emulator for three systems.** PicoDrive covers Mega Drive, Pico,
Sega CD and 32X (plus SMS / Game Gear). On v3 it would be added as a new
app for Pico and Sega CD, keeping the tuned gwenesis for Mega Drive games.

### Suggested order on v3

1. **Classic MAME:** the highest value for the effort, and existing ESP32
   projects already run a handful of these games.
2. **Sega Pico** through PicoDrive: cheap once PicoDrive is ported, and it
   prepares the ground for Sega CD.
3. **Sega CD:** the hardest; measure a first game before promising it.
4. **32X:** not on v3.
