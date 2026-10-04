---
id: jit-plan
title: JIT (dynarec) plan
sidebar_position: 8
---

# JIT (dynarec) plan

The plan of 2026-09-29 was to translate guest code to native Xtensa code (a
JIT, or dynarec) for the systems whose interpreter was the limit: the Game Boy
Advance first, then the 68000 of the Neo Geo, CPS1 and Mega Drive. This page
says where that stands. The plan as it was agreed, step by step, is in the
repository: `docs/archived/jit-plan-2026-09-29.md`.

## Where we are (2026-10-04)

| Frontend | State | Result |
|:---|:---|:---|
| **Game Boy Advance** (ARM7TDMI / Thumb, an Xtensa backend for gpSP) | **finished and in use** | 56–60 fps in play, 11 of 12 tested games on the dynarec, video and audio bit-identical to gpSP's x86 dynarec; automatic fallback to the interpreter. See [GBA dynarec](../software/gba-dynarec.md) |
| **Motorola 68000** (`m68kjit`, blocks on top of Musashi) | **finished, exact, switched off** | slower than the interpreter on the board: 13.1 ms against 7.7 ms of 68000 a frame on Metal Slug. See [68000 dynarec](../software/m68k-dynarec.md) |
| Mega Drive, other systems | not started | nothing to gain until the 68000 frontend wins somewhere |

The code is public: [pjcau/xtensa-68000-dynarec](https://github.com/pjcau/xtensa-68000-dynarec)
(a submodule of the retro-go fork), with one page per frontend.

## What was done, in short

1. **`xjit`, the shared core**: Xtensa instruction encoders checked byte for
   byte against the assembler, labels and literal pools, executable memory in
   PSRAM with cache synchronisation. Tested in QEMU and on the board.
2. **GBA**: an Xtensa backend for gpSP's translator, verified in QEMU against
   gpSP's x86 dynarec frame by frame, then the board work that made it pay
   (hot helpers in internal RAM, three frame buffers, the renderer on the
   second core).
3. **68000**: instruction lengths, block cache, native forms for the common
   instructions with Musashi's own handlers for the rest, block chaining; a
   differential fuzz against Musashi with zero mismatches; plugged into
   mame-go and measured.

## Why one wins and the other does not

Translated code is fetched from PSRAM through a 32 KB instruction cache that
both cores and all the firmware share. A GBA game's hot code per frame fits,
and its interpreter was slow; a Neo Geo game runs a lot of distinct code every
frame (635 KB of translated code for Metal Slug) and its interpreter's own
code is small and stays hot. The 68000 dynarec ran at 78 host cycles per guest
instruction against the interpreter's 46.

## What is left

Nothing is in progress. The 68000 time was cut in the interpreter instead
(exact skips of waiting code: see the [Arcade 60 fps plan](arcade-60fps-plan.md)).
The 68000 dynarec is reopened only on a measurement: a build with 64 KB or
more of internal RAM free for a code cache, or code three times denser
(steps F3 to F5 of the code generation plan in the dynarec repository).

## Rules that held

- Both engines in one app, the interpreter as the fallback.
- Never slower than the interpreter: a game where the dynarec loses runs on
  the interpreter.
- Bit-exact first: every change passes a differential test in QEMU before it
  touches the board.
