---
id: arcade-60fps-plan
title: Arcade 60 fps plan
sidebar_position: 9
---

# Arcade 60 fps plan

The plan was to run the 68000 arcade games of `mame-go` (Neo Geo, CPS1, later
Sega System 16) at **60 drawn frames a second** on the ESP32-S3, with no
frameskip. This page says where that stands, what was done and what is left.
The day-by-day record (every measurement, the original phases, the logs) is
in the repository: `docs/archived/arcade-60fps-plan-log.md`.

Related pages: [Arcade (MAME)](arcade.md), [68000 dynarec](../software/optimizations.md#arcade-the-68000),
[JIT plan](jit-plan.md), [Software overview](../software/overview.md).

## Where we are (2026-10-04)

**The goal is not reached on any 68000 arcade game, and on this hardware it is
not in sight for most of them.** What was reached: the games run at or near
full speed while about a third of their frames is drawn. Work on the plan was
stopped here by the user's decision.

| Game | Every frame drawn: core 0 ms a frame (16.7 needed), start → now | In play with the frameskip: game fps / drawn |
|---|---|---|
| Metal Slug (Neo Geo) | 29.2 → 22.4 | 58 / 20-21 |
| Metal Slug 2 (Neo Geo, raster) | 36.2 → 33.5 | 46 / 15-16 |
| Final Fight (CPS1) | 40.1 → 29.5 | 55 / 18 |
| Street Fighter II CE (CPS1) | 38.9 → 36.1 | 46 / 15 |
| Golden Axe (System 16) | not measured | 54 / 18 |
| Alien Syndrome, Wonder Boy III (System 16) | not measured | 58 / 19, 57 / 19-20 |

- The 68000 came down by a third (Metal Slug 10.8 → 7.0 ms, Final Fight
  9.7 → 6.8 in play), not by the half that was the intermediate objective.
- Metal Slug is 6 ms from 60 drawn frames, with 10 ms of video on core 0 and
  7 ms of 68000. No measured lead gives that.
- The CPS1 and the raster Neo Geo games are at twice the frame budget.
- **The realistic target on this board**: the game always at full speed
  (60 frames of logic a second, clean sound) with 20 to 30 frames drawn. Metal
  Slug and Final Fight are nearly there, and since 2026-10-05 the System 16
  games (54 to 58); Street Fighter II and Metal Slug 2 run at 45 to 50.

Launch times: the same arcade game again starts in 9 to 13 s; after another
arcade game it takes 20 to 28 s, because the 4 MB flash cache holds one game
and is rewritten (the screen says "game cache NN%").

## What was done

In the order it was done; each step was proven frame by frame on the PC
harness, then measured on the board in play.

| Step | Scope | What it gave |
|---|---|---|
| Palette fast paths, hot code in IRAM, aligned 16-bit accesses, inline RAM/ROM path in Musashi | all MAME games | about 2 ms a frame together |
| The display task reads MAME's 8-bit bitmap itself; change test per line; branch-free scalers | every emulator | display task 12.2 → about 4.5 ms of CPU |
| Neo Geo frame drawn in 16-line bands in internal RAM, handed to the display as they finish | Neo Geo | video off the PSRAM frame bitmap |
| Sound board (Z80 + FM) on core 1; chips rendered at 16 kHz, doubled to the 32 kHz output | Neo Geo, CPS1 | 1.5 to 2 ms a frame, not audible |
| Exact skips of the 68000's waiting code (counting loops, idle turns) | Neo Geo, CPS1, System 16 | 68000 −3 to −4.7 ms where they fire |
| Card pages through a DMA-capable buffer | Neo Geo sprite and sample pagers | 17 → 7 ms and 12 → 5 ms a read |
| CPS1: clears cut to the visible area; 8-bit frame handed to the display task | CPS1 | Final Fight 40.1 → 29.5 ms; 48.6 → 55.3 fps in play |
| SD reads into PSRAM several KB per command instead of one sector | every emulator | SNES 4 MB launch 10.9 → 5.8 s, GBA 8 MB 10.8 → 6.8 s |
| Resume at boot fixed; CPS1 states smaller; SF2 states borrow a video cache | Neo Geo, CPS1 | saves work on every tested game |
| Screenshot from a frame-boundary copy | mame-go (not the Neo Geo band mode) | right pictures on the indexed path |

Also added on the way: a loading percentage in every emulator, a CPS-1 tab and
covers in the launcher, Sega System 16 in `mame-go`, OutRun through Cannonball,
Arcade 3D Racing.

**Tried and dropped** (measured; do not retry without a new reason):

- the 68000 dynarec: exact, slower than the interpreter here (see [68000 dynarec](../software/optimizations.md#arcade-the-68000));
- PSRAM at 120 MHz and the LCD bus at 25 MHz: out of spec, excluded by the user;
- 16-bit bitmaps for the Neo Geo, sprites on core 1, a faster sprite plotter,
  the program's first megabyte in PSRAM, FAME/C, lazy cycle counting;
- FatFs with 512-byte sectors for internal RAM: no gain;
- a cache of decoded CPS1 tiles on the card: slower than the zip;
- an even frameskip cadence (one frame in N): the same drawn frames, off (file `skip_even`);
- a screenshot in the Neo Geo band mode by running one more frame: it hung the game.

## What is left

In the order of what it could give.

1. **System 16**: done on 2026-10-05 (sound board on core 1, frames handed to
   the display, idle skips stepping aside where the driver has its own idle
   hack, full screen): Golden Axe 50 -> 54 fps in play, Alien Syndrome
   50 -> 58, Wonder Boy III 49 -> 57. Left: Shinobi and Altered Beast (no set
   at hand); the System 16 save states, which keep only the CPUs and RAM.
2. **The CPS1's renderer on core 1**, which is half idle: the one large move
   left for the CPS1. Estimated at about 25 drawn frames, large and risky.
3. **Street Fighter II** has about 70 KB of PSRAM free in play, so it cannot
   take the indexed path; the 16-bit CPS1 games (Knights of the Round) are not
   measured in play on it.
4. **The Neo Geo raster games' 16-bit video path** (Metal Slug 2, KOF '95): 16 ms.
5. **A screenshot for the Neo Geo band mode**, with a PC reproduction first.
6. **Open defects**: a CPS1 state is not an exact continuation; the dead
   buttons of 2026-10-03 were never explained (the binary and the card were
   cleared). `robby.zip` resuming black was fixed on 2026-10-05 (the
   Astrocade video registers are now in the save state), and Street Fighter
   II's saves complete again.

What the hardware would change: a module with 32 MB of flash and 16 MB of
PSRAM removes the flash cache rewrite, the lack of room for apps (64 KB left)
and Street Fighter II's memory limits, not the frame rates. See
[Plan D](plan-esp32-s3-n32r16v.md).

## How to work on it

- **Measure in play.** `MAMEBENCH=2` (Neo Geo) and `MAMEBENCH=4` (CPS1, System
  16) insert a coin, press START and play a script; `MAMEPROF=1` samples core
  0, `NEOPROF=1` times the parts. The attract loop and the intro screens
  flatter every figure. Details: `scripts/mamebench/README.md`.
- **Prove a change on the PC first.** `scripts/neogeo_frames.py` compares
  pictures and sound frame by frame (`ref`, `compare`, `turn`, `count`).
- **Compile on the Mac**, test on the board: `scripts/retro_go_build.sh <app>`
  (for `mame-go` with the play options, or the band code is not compiled).
- **Switch files** in `/sd/retro-go/mame/` turn single changes off for a
  comparison: `cps1_noturn`, `cps1_fullclear`, `cps1_noindexed`,
  `cps1_indexed`, `sys16_noturn`, `skip_even`, `neo_nocount`.
- **After any bench or profile run** the play build goes back
  (`scripts/mamebench/board_install.sh`, which refuses a bench binary), the
  switch files are removed, and coin + START are checked on Metal Slug: a
  bench build ignores the gamepad.
- Limits: 64 KB of flash left outside the app partitions, about 18 KB in the
  launcher's, 0 to 5 KB of internal RAM in Metal Slug.
