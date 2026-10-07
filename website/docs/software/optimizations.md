---
id: optimizations
title: Optimizations
sidebar_position: 4
---

# Optimizations

What was done to make the slow emulators faster, what each change was worth
on the board, and what was tried and did not pay. Every number is a board
measurement; a change that does not move the measured number is reverted.

**The method.** Each emulator prints its own profile line once a second
(`SNES_PROF`, `GEN_PROF`, `GBAPROF`, `MAMEPROF`, `A78PROF`): time per frame of
each part (CPU, video, sound, display). One change at a time, the same scene
(save state or a scripted input), the picture checked identical, on the PC
where a reference build exists (SNES, GBA, arcade, Atari 7800) and on the
webcam.

## What the board is like

- Two cores at 240 MHz, 32 KB instruction cache, 64 KB data cache (the
  firmware's configuration), about 100–190 KB of internal RAM free while a
  game runs, 8 MB of PSRAM behind the data cache.
- The display is an 8-bit parallel bus at 20 MHz: a full 480×320 frame takes
  15 ms, so about 60 frames a second is the most any core can show.
- Core 1 is free during games: moving work there is usually the largest gain.

## SNES

From 45–52 emulated fps (10–13 drawn) on 2026-09-12 to 60 fps on every test
scene.

| Change | Effect |
|:---|:---|
| Audio per frame computed from the ROM's frame rate, audio pacing credit | Super Mario World 46 → 60 fps |
| Data cache 32 → 64 KB, instruction cache 16 → 32 KB | kept for every app |
| Main z-buffer in internal RAM | Mario Kart 38 → 57 fps |
| Blank tiles cached by depth | −1500 tile conversions a frame in SMW |
| Mode 7 loop with its invariants in registers | −12 % |
| Colour-math fast path when the sub screen is empty | Zelda 24.9 → 9.5 ms a drawn frame, Super Metroid 24.6 → 14.4 |
| Tile writers rewritten (`restrict`, depths in registers) | SMW −13 %, Zelda −16 %, Mega Man X −18 % |
| Backdrop and palette 0–15 read per line instead of a new strip | Donkey Kong Country 97 strips → 1, 16.1 → 11.6 ms |
| S-DSP (sound) on core 1, one frame of audio latency | Mario Kart 57 → 57–62, mostly 60 |
| SuperFX (GSU) on core 1 | Star Fox 22–30 → 53–60 fps |

**Did not pay:** the whole renderer in IRAM (1–6 %), VRAM in internal RAM
(nothing), a Mode 7 loop per colour window (slower), a 4-pixel skip in the
backdrop combine (slower). What is left in the renderer is instruction count:
20–45 instructions a pixel on a single-issue core.

### Audio stays on the main chip {#audio-no-coprocessor}

A separate audio coprocessor (an ESP32-S3-MINI module) was planned before the
board existed. The board showed the 65816 + SPC700 fit in 8.5 ms and the
renderer was the bottleneck, so the coprocessor was dropped (2026-09-26) and
the sound moved to core 1 instead. The real audio problem is analog (the PDM
carrier hiss); the next board plans an I2S class-D amplifier with its own DAC.

## Mega Drive

The YM2612 FM synthesis (6 ms a frame, 37 % of the budget) runs on core 1:
register writes are logged with their clock and replayed one frame later.
20 → 30 drawn fps at 60 emulated.

## Game Boy Advance: the Xtensa dynarec

gpSP's ARM/Thumb code is translated into native Xtensa code at run time
(source: [pjcau/xtensa-68000-dynarec](https://github.com/pjcau/xtensa-68000-dynarec),
GPL-2.0). It gives the same video and audio as gpSP's own x86 dynarec
(bit-identical hashes in QEMU). The interpreter stays in the app as an
automatic fallback (a game that rewrites its own code, or a crash), and the
choice is remembered per game.

| Game | Interpreter | Dynarec, first run | Now (emulated / shown) |
|:---|---:|---:|:---|
| Sonic Advance | 55.5 | 48 | 58.8 / 54.5 |
| Metal Slug Advance | 47.4 | 29 | 55.7 / 55.6 |
| TMNT | 44.7 | 52 | 59.5 / 58.7 |

| Change | Effect |
|:---|:---|
| Direct aligned loads and stores, 16-bit instruction forms | Metal Slug 29 → 35 fps |
| Hot C helpers in IRAM | 35 → 40–45 fps |
| Three frame buffers (emulation stops waiting for the LCD) | Sonic 49.7 → 57.5 emulated |
| Renderer's own copy of VRAM (no wait on core 1) | −9 to −13 % CPU time |
| Render task below the display task | Sonic 46.6 → 54.5 shown |

The translated code itself is only ~29 % of core 0; the rest is the GBA
hardware model in C, which is why more code-generation work gives little now.

## Arcade: the 68000

A 68000 dynarec was built on the same core and is exact (same screen hashes
as the interpreter), but **slower**: 13.1 ms of 68000 a frame on Metal Slug
against the interpreter's 7.7 ms. It turns each 68000 instruction into 70–80
bytes of host code fetched through the 32 KB instruction cache, against 2–6
bytes of guest code for the interpreter. It is off. Of a Neo Geo frame (24.7
ms in play), the 68000 is 10.9 ms and the video 10.4 ms, and core 1 is as full
with sound and display: a faster 68000 alone does not reach 60.

What was done on the interpreter and the drivers instead: idle-loop skipping
(Aero Fighters 47–57), frame clears skipped when a layer covers the screen
(CPS1: the clears were about 16 % of core 0), the band renderer and display buffers of the play
build, sound chips at 16 kHz.

## Atari 7800

| Change | Effect (Donkey Kong in play) |
|:---|:---|
| Start | 42 fps; MARIA (graphics chip) 17.1 ms + 6502 6.5 ms a frame |
| 64 KB address space in internal RAM | nothing |
| MARIA's line colours read once a line, its code in IRAM | 50 fps, MARIA 13.0 ms |
| MARIA's common case written directly, the core's small state in internal RAM (branch `a78-speed2`, not merged) | 56 fps, MARIA 10.9 ms |

## What did not pay, across emulators

Three predictions in a row about memory were wrong on the board, which is why
nothing is promised before it is measured:

- Moving data from PSRAM to internal RAM: the 7800's address space, the SNES
  VRAM, the 68000 program from flash to PSRAM — no gain each time.
- Writing pixels four at a time from a buffer instead of one byte at a time
  (CPS1, 2026-10-08): **slower** (25.6 → 26.6 ms a frame). Byte stores to
  PSRAM are already merged by the data cache; the buffer added work.
- Code in IRAM helps only for code that misses the instruction cache (GBA
  helpers, MARIA); for code already hot it gives 1–6 %.

## What is left

| System | Measured | Next lever |
|:---|:---|:---|
| Atari 7800 | 50 fps (56 on the unmerged branch) | merge `a78-speed2`; the 6502 is 6.5 ms |
| CPS1 | Final Fight 55, SF2 38–47 | the scroll-2 copy (18 % of core 0), the opaque drawer |
| Neo Geo raster games | Metal Slug 2, KOF95 52–55 | 16-bit video path (about 16 ms) |
| GBA | 46–59 | faster renderer on core 1; the C hardware model |
| System 16 | 54–58 | not profiled yet |

The plans behind these are in [Arcade 60 fps plan](/docs/next-steps/arcade-60fps-plan)
and [JIT (dynarec) plan](/docs/next-steps/jit-plan).
