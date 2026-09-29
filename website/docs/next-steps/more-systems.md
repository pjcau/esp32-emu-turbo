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
| 🟡 **Possible with work** | Sega CD / Mega CD, PC Engine CD, Commodore 64, Game Boy Advance | Sega CD: **to do** (user, 2026-09-29), through PicoDrive — see below. PCE CD reuses the PCE core (60 fps at 43% busy) plus CD audio streamed from the SD. C64 needs a cycle-accurate video chip. GBA runs since 2026-09-29 (`gbsp`, gpSP interpreter): Sonic 59, TMNT 52, Metal Slug 46 fps on screen; 60 on the heavy games likely needs a dynarec ([existing building blocks](/docs/software/retro-go-forks-survey#jit--dynarec-building-blocks-checked-2026-09-29)) |
| 🔴 **Out of reach on this chip** | 32X, Virtual Boy, PlayStation, Saturn, N64 | Too many fast CPUs (32X: two SH-2 at 23 MHz), ROMs larger than the 8 MB PSRAM, or 3D hardware. Neo Geo was listed here: it now runs at part speed with its ROMs paged from the SD card (see [Arcade (MAME)](/docs/next-steps/arcade#neo-geo-on-v3-sprites-paged-from-the-sd-card-2026-09-27)) |

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
on core 1. **Flash is the constraint now:** the image is 15.3 MB of the
16 MB (2026-09-29: 11 apps + the 4 MB `mamerom` partition), about 700 KB
free, so a new emulator app needs room made first (a smaller `mamerom`,
or trimming an app partition) and one USB flash for the new partition
table.

| System | Verdict on v3 | Why |
|:---|:-:|:---|
| **Mega Drive / Genesis** | ✅ done | 60 emulated / 30 drawn. Drawing all 60 would need ~20 ms per frame against 16.7 ms, so 30–40 drawn is the ceiling without deeper VDP work |
| **Sega Pico** | 🟢 feasible | a Mega Drive without the Z80 and the YM2612, plus a simple ADPCM chip: lighter than what already runs. PicoDrive emulates it; the pen and page tablet map to the D-pad and buttons. A niche library of edutainment titles |
| **Sega CD / Mega CD** | 🎯 **to do** (user, 2026-09-29) — 🟡 at the limit | adds a second 68000 at 12.5 MHz (~9 ms per frame by scaling the measured 5.5 ms), a PCM chip and CD audio. With the sub-CPU on core 1 next to the YM2612, core 1 reaches ~15–17 ms of its 16.7 ms, and the two 68000s must stay in step across cores. Expect heavy frameskip and slowdowns in demanding scenes. Needs a different emulator (gwenesis has no CD support: PicoDrive with its C 68000 core), the Sega CD BIOS supplied by the user, and bin/cue images (CHD decompression is too heavy) |
| **32X** | 🔴 no | two SH-2 CPUs at 23 MHz on top of the Mega Drive: an interpreter needs several hundred MHz of CPU per SH-2, and PicoDrive's SH-2 dynarec has no Xtensa backend |
| **Classic arcade (MAME)** | 🟢 feasible | Z80 / 6502 / 8080 boards of 1978–85 (Pac-Man, Galaga, Donkey Kong, Frogger, 1942, Bomb Jack…). See [Arcade (MAME)](/docs/next-steps/arcade#on-the-current-console-v3) |
| **Capcom CPS1** | 🟡 at the limit | one 68000 at 10 MHz (~7 ms by scaling) + Z80 + YM2151 (FM, on core 1 like the YM2612) and a heavier tile / sprite renderer at 384 × 224. ROM sets of 2–6 MB fit the 8 MB PSRAM. Frameskip needed |

**One emulator for three systems.** PicoDrive covers Mega Drive, Pico,
Sega CD and 32X (plus SMS / Game Gear). On v3 it would be added as a new
app for Pico and Sega CD, keeping the tuned gwenesis for Mega Drive games.

### Sega CD through PicoDrive: the plan (to do, decided 2026-09-29)

Source: the `PicoDrive` directory of the retro-go forks (PicoDrive Genesis +
Sega CD on the FAME 68000 core, "about the same speed as gwenesis" on the
S3, Sega CD disabled on the original ESP32 for memory) — see the
[forks survey](/docs/software/retro-go-forks-survey).

1. **Flash room:** a `picodrive-go` partition of about 1–1.5 MB. Only
   ~700 KB is free: shrink `mamerom` (4 MB) or another partition, then one
   USB flash (`rg_tool.py install`) for the new table.
2. **Port as a new app** with the Mega CD enabled; Mega Drive games stay
   on gwenesis. Launcher tab "Sega CD" (`/roms/segacd`), BIOS from the user
   in `/sd/bios/segacd/` (US/EU/JP), disc images as bin/cue (CHD is too
   heavy to decompress).
3. **Memory:** the Mega CD adds 512 KB program RAM + 256 KB word RAM + the
   PCM RAM; everything in PSRAM, the CD read from the SD a sector at a time.
4. **Speed:** the sub-CPU 68000 on core 1 (as the YM2612 / S-DSP), the two
   68000s kept in step at the frame or line boundary; measure one game
   before promising a frame rate (estimate: heavy frameskip).
5. **Audio:** CD audio (CDDA) streamed from the `.bin` tracks and the PCM
   chip mixed at 32 kHz, like every other app.

**Proof:** a Sega CD game boots from the card, its CD music plays, and the
frame rate in play is measured on the board.

### Suggested order on v3

1. **Classic MAME:** the highest value for the effort, and existing ESP32
   projects already run a handful of these games.
2. **Sega Pico** through PicoDrive: cheap once PicoDrive is ported, and it
   prepares the ground for Sega CD.
3. **Sega CD:** chosen by the user (2026-09-29); the hardest, measure a first game before promising it.
4. **32X:** not on v3.
