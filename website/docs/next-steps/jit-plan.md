---
id: jit-plan
title: JIT (dynarec) plan
sidebar_position: 8
---

# JIT (dynarec) plan

**Status: plan, agreed with the user on 2026-09-29. Top priority.**

The interpreters are now the limit. With the GBA scanline renderer on the
second core, the ARM7 interpreter takes 16 ms per frame on Sonic Advance and
22 ms on Metal Slug Advance and TMNT. Trimming the interpreter gives a few
percent per step. On Neo Geo and CPS1 the 68000 takes 14–18 ms in the heavy
scenes of Metal Slug 2, and there is no wait loop to skip. Translating guest
code to native Xtensa code once and running it many times (a JIT, or
dynarec) is the lever left for these systems.

The plan builds **one shared JIT core** first, as a standalone test app that
no emulator depends on. The emulators that work today stay untouched until
the core passes its tests. Then the core goes into the emulators one at a
time, behind a switch, with the interpreter as the fallback.

:::note Where the code is now
Since 2026-09-30 `components/xjit`, `gbsp-libretro`, `xjit-test` and `gbajit-test` live in the public repository [pjcau/xtensa-68000-dynarec](https://github.com/pjcau/xtensa-68000-dynarec) (`components/` and `test/`), a submodule of retro-go. The paths below are the ones they had when each step was done.
:::

## What already exists

Nobody has a GBA or 68000 dynarec for Xtensa (the ESP32-S3 CPU), but the
pieces exist:

| Piece | What it gives us | License |
|:---|:---|:---|
| [HowBoyAdvance](https://github.com/Irak4t0n/HowBoyAdvance), in retro-go as [rapha-tech `GBA_dynarec`](https://github.com/rapha-tech/retro-go/tree/GBA_dynarec) ([issue #349](https://github.com/ducalex/retro-go/issues/349)) | A gpSP dynarec backend for the ESP32-P4 (RISC-V): `riscv_emit.h`, `riscv_codegen.h`, `riscv_stub.S`. It is the same gpSP as ours, and its code cache is in PSRAM mapped executable. They report 4–13x over retro-go's plain interpreter. | GPL-2 (gpSP) |
| [Dragonfruit](https://github.com/megabytefisher/Dragonfruit) | A complete 68000 → Xtensa JIT on the ESP32 (LX6): instruction emitter with host tests, executable memory in IRAM, compile on one core and run on the other. JIT at 87% of real speed against 58% for its interpreter. | MIT |
| [igrr's gist](https://gist.github.com/igrr/ef5a3ad9f5fbf835f06c88b6b36defcc), [`esp_mmu_map`](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/system/mm.html) | Running code from PSRAM on the ESP32-S3 | example |
| MicroPython `py/asmxtensa.c` | A mature Xtensa emitter, windowed ABI included | MIT |

RISC-V is closer to Xtensa than gpSP's MIPS backend: neither has flags, and
both compare and branch in one instruction.

## The shared core: `xjit`

A retro-go component, `components/xjit`, that every emulator can use:

| Part | Job |
|:---|:---|
| **Emitter** | Encodes the LX7 instructions (ALU, loads and stores, branches, `call0`/`callx0`, `l32r` literals) into a buffer. Starts from Dragonfruit's emitter. |
| **Executable memory** | The code cache: internal RAM (IRAM) or PSRAM mapped executable, whichever step 3 shows is fast enough, plus the cache sync after writing code. |
| **Block cache** | Guest PC → native block, invalidation for self-modifying code (GBA IWRAM), flush when full. |
| **Glue** | Entry and exit stubs to and from C, calls to the emulator's memory handlers, cycle counting. |
| **Tests** | Encode-and-disassemble tests on the PC against `xtensa-esp32s3-elf-as`/`objdump`; run tests in QEMU and on the board. |

Each emulator adds a **frontend**, the part that decodes its CPU:
- **ARM7 (GBA)**: a gpSP backend `xtensa_emit.h` / `xtensa_codegen.h` /
  `xtensa_stub.S` built on `xjit`, following the RISC-V backend. gpSP's
  common translator (`cpu_threaded.c`) stays as it is.
- **68000 (Neo Geo, CPS1, then Mega Drive)**: Dragonfruit's 68000 frontend
  adapted to the MAME 68000 core in mame-go (and later gwenesis), whose
  memory access goes through handlers.

## Where each step runs

Espressif's QEMU has an ESP32-S3 machine. It runs the S3 instruction set,
so it can check that generated code is **correct**. It says nothing about
**speed**: it does not model the caches, PSRAM timing or cycles. The QEMU
in the ESP-IDF v5.4 Docker image (esp_develop 9.0.0) has no S3 PSRAM; the
newer esp_develop 9.2.2 emulates the board's 8 MB octal PSRAM
(`-m 8M -global driver=ssi_psram,property=is_octal,value=true`), and
`retro-go/xjit-test` uses it (see its README).

| Step | What | Where | Board needed? |
|:---|:---|:---|:---|
| **0. Harness** ✅ 2026-09-29 | Standalone test app `retro-go/xjit-test` (ESP-IDF). Machine code written at run time runs in QEMU from internal RAM and from PSRAM mapped for instruction fetch (`esp_mmu_map` exec + cache sync). | PC + QEMU | No |
| **1. Emitter** ✅ 2026-09-29 | `components/xjit/include/xjit_emit.h`: byte-identical to `xtensa-esp32s3-elf-as` on ~125 KB of random instructions of every kind (`components/xjit/test/run_emit_test.sh`). | PC | No |
| **2. Generated code runs** ✅ 2026-09-29 | Blocks with labels, literal pool, calls into C, 26 branch kinds, loads/stores, plus 2000 random ALU programs against a C reference: 16/16 in QEMU and on the board, from IRAM and from PSRAM. The board found what QEMU cannot: the instruction-cache invalidate must cover whole lines. | QEMU, then board | Done |
| **3. Speed (decision gate)** ✅ GO, 2026-09-29 | Board: generated ALU code 1.0–1.3 cycles/op (gcc C 0.94); block call+return 13 cycles; call into C 14; code bigger than the 32 KB I-cache runs at 1.0 cycles/op from IRAM but 11.6 from PSRAM. So: native speed, and the hot code must stay in IRAM or fit the I-cache (see below). | Board | Done |
| **4. Mini frontend** ✅ 2026-09-29 | Thumb formats 1–5 (shifts, ADD/SUB, imm8 ops, the 16 ALU ops, hi-register ops) translated by `xjit`: equal to a reference interpreter on 3000 random sequences × 6 states in QEMU (IRAM and PSRAM), and the reference equal to gpSP's own interpreter on 18000 runs on the PC (`xjit-test/host/run_thumb_gpsp_check.sh`). | PC + QEMU | No |
| **5. GBA backend** ✅ 2026-09-29 | `gbsp-libretro/xtensa/`: a port of gpSP's x86 backend (ARM state and flags in memory, memory handlers and trampolines in C) on `xjit`. In QEMU (`retro-go/gbajit-test`, 8 MB PSRAM) its frame and audio hashes equal the x86 dynarec's on Sonic Advance, Metal Slug Advance and TMNT (300/600 frames of the level states). The reference is the x86 dynarec, not the interpreter: the dynarec counts cycles per block, so its frames differ from the interpreter's. | QEMU | No |
| **6. GBA on the board** ✅ 2026-09-30 | `GBAJIT=1` build of gbsp: Sonic Advance, Metal Slug Advance and TMNT run correctly on the board (webcam checked). Interpreter kept as the fallback (normal build). | Board | Done |
| **7. GBA speed** ✅ 2026-10-01 | Played on the board, emulated / shown fps: Sonic Advance 58.4 / 53.6, Metal Slug Advance 54.1 / 53.9, TMNT 59.7 / 58.6 (interpreter 55.5 / 47.4 / 44.7 emulated); deterministic benchmark 68-88 fps-equivalent at steady state. 11 of 12 games run on the dynarec, NFS Underground falls back to the interpreter by itself; save states and battery saves work on both engines. The dynarec is now the default `gbsp` build. Details: [GBA Dynarec (Xtensa JIT)](../software/gba-dynarec.md). | Board | Done |
| **8. 68000 frontend** ✅ 2026-10-01 | `m68kjit` in [xtensa-68000-dynarec](https://github.com/pjcau/xtensa-68000-dynarec) (see its `docs/m68k.md`): blocks built **on top of the emulator's own Musashi** interpreter, which runs every instruction the translator does not; native Xtensa code for moves (all addressing modes, MOVEM), ALU and immediate forms, read-modify-write, TST/CLR, LEA/PEA, shifts by `#n`, Bcc/DBcc, BSR/JSR/RTS, plus block chaining. Differential fuzz against Musashi on random machines: equal on 600 seeds in QEMU, 84 % of random 68000 code native; every native group was broken on purpose once and caught. Speed is measured on the board in step 9. | PC + QEMU | No |
| **9. Neo Geo and CPS1** | Into mame-go behind a switch: Metal Slug 2 in play (goal 55–60 fps), CPS1 games, webcam checks. The dynarec is exact but slower than the faster interpreter (13.87 vs 8.71 ms of 68000 per frame on Metal Slug): its code is 70-80 bytes per 68000 instruction and does not fit the 32 KB I-cache. Step 9f shrinks it to ~20-25 bytes: [code generation plan](https://github.com/pjcau/xtensa-68000-dynarec/blob/main/docs/codegen-plan.md). | Board | **Yes** |
| **10. Mega Drive** | The same 68000 frontend in gwenesis, if it helps there. | Board | **Yes** |

**Summary: steps 0, 1, 4, 5 and 8 need no board. Step 2 needs it at the end,
and steps 3, 6, 7, 9 and 10 need it throughout.** Step 3 is the go/no-go
point: if generated code is not clearly faster than the interpreter there,
the plan stops before any emulator changes.

## Which systems gain, and how much

A JIT speeds up only the emulated CPU. Rendering, audio and memory stay
as they are, so the frame rate gains much less than the CPU part. Every
number below is an **estimate**; step 3 gives the first measured one.

The `xjit` core is shared, but every guest CPU needs its own frontend.
The plan has two: ARM7 and 68000.

| System | CPU | Gain | Why |
|:---|:---|:---|:---|
| **GBA** | ARM7 | High | The ARM7 interpreter takes 16–22 ms per frame and is the limit |
| **Neo Geo** | 68000 | High | 14–18 ms of 68000 in Metal Slug 2's heavy scenes, no wait loop to skip |
| **CPS1** | 68000 | High | Same as the Neo Geo |
| **68000 MAME boards** (Blood Bros, Aero Fighters, Sega System 16) | 68000 | Medium-high | The Neo Geo frontend, at no extra cost |
| **Mega Drive** | 68000 | Medium | 60 emulated but 30 drawn fps: drawing all 60 needs ~20 ms against 16.7. The 68000's 5.5 ms shrinking to ~2–3 ms brings that near the budget; the VDP (11.3 ms) remains the main cost |
| **CPS2** | 68000 + Z80 | CPU only | See below: memory and encryption, not the CPU, keep it out |
| Z80 systems (SMS, GG, SG-1000, Coleco, 8-bit MAME), NES, SNES, GB/GBC, PC Engine, NGP | various | None | Already at 60 fps, or (SNES) limited by the renderer and DSP-1, not the CPU. No frontend planned |
| DOOM, Quake, Duke3D, Wolf3D | native | None | Native ports, nothing is emulated |

Expected speedup (estimate):

| | Pessimistic | Realistic | Optimistic |
|:---|:---|:---|:---|
| ARM7 CPU time | 1.5x | **2–3x** | 4x |
| 68000 CPU time | 1.3x | **1.5–2.5x** | 3x |

- HowBoyAdvance's 4–13x is against retro-go's plain interpreter on the P4
  (larger caches). Our gpSP interpreter is already trimmed, so less is left.
- Dragonfruit measured only 1.5x over its own 68000 interpreter (58% →
  87% of real speed): addressing modes, flags and memory handlers in C
  stay expensive.
- The pessimistic case is the code cache in PSRAM losing to I-cache
  misses. Step 3 decides it.

On screen (capped at 60):

| Game | Today | With the JIT (realistic) |
|:---|:---|:---|
| GBA Sonic Advance | 56 | 60, with headroom |
| GBA Metal Slug Advance / TMNT | 46 / 49 | 60 |
| Neo Geo Metal Slug 2, heavy scenes | ~42 | 55–60 |
| CPS1 | as Neo Geo | 55–60 |
| Mega Drive | 60 emulated / 30 drawn | 60 emulated / 40–60 drawn |

### Systems ruled out before

Which systems from the 🔴 lists in [More Systems](/docs/next-steps/more-systems)
and [Arcade (MAME)](/docs/next-steps/arcade) the JIT could bring back:

| System | CPU | With the JIT | Why |
|:---|:---|:---|:---|
| **CPS2** | 68000 11.8 MHz + Z80 (QSound) | 🟡 the CPU fits, the rest does not yet | The 68000 frontend covers the CPU. Still blocking: graphics sets of 16–40 MB against 8 MB of PSRAM (needs the Neo Geo sprite paging from the SD card), MAME 0.37b5's CPS2 encryption support, and QSound |
| **Sega System 16/18** | 68000 10 MHz + Z80 | 🟢 likely | Was 🟡 "hard"; the same class as CPS1 |
| **Virtual Boy** | NEC V810 20 MHz | 🟡 possible, large work | Small ROMs (≤ 2 MB), simple graphics (one eye shown). Red Viper runs it at full speed with a dynarec on the 3DS's 268 MHz ARM11. Needs a new V810 frontend and an emulator port |
| Sega CD | 2 × 68000 | ⛔ not planned | The JIT would make the second 68000 fit, but the user does not want it (games too big) |
| Encrypted Neo Geo (KOF '99 and later, Metal Slug 3+) | 68000 | 🔴 unchanged | The limit is the encryption missing from MAME 0.37b5 and the program size, not the CPU |
| 32X | 2 × SH-2 23 MHz + Mega Drive | 🔴 unchanged | Even with a JIT, two SH-2 need about 150–200 MHz on top of a Mega Drive that already fills core 0 |
| PlayStation, Saturn, N64 | MIPS / 2 × SH-2 / MIPS + RCP | 🔴 unchanged | Beyond the CPU: 3D or heavy 2D GPUs, CD streaming, memory |

Every new system also needs flash: about 700 KB are free today.

## Rules

- No emulator changes before step 5 passes: the working emulators stay as
  they are.
- Every emulator integration has a switch and keeps the interpreter as the
  fallback.
- Correctness is proven with the existing hashes (PC harness references,
  bit-identical) before any speed number counts, and on the board with
  webcam shots of the screen.
- Licenses: gpSP is GPL-2, Dragonfruit and MicroPython are MIT, both usable
  in this GPL project; code from repos without a license (ESPB) is read,
  never copied.

## Step 3 results and what they mean

Generated code runs as fast as compiled C, so a translated ARM or 68000
instruction costs what its few Xtensa instructions cost, against ~78 cycles
per ARM instruction in today's GBA interpreter. The limit is where the code
lives: PSRAM code is fine while the hot blocks fit the 32 KB instruction
cache (shared with the emulator's own code in flash), and 11x slower when
they do not. Internal RAM has no such cliff, but gbsp and mame-go have little
of it free (~12 KB in gbsp): making room for an IRAM code cache (moving
tables or buffers to PSRAM) is part of the GBA work.

## Known risks

- **Internal RAM is full** in gbsp and mame-go. If the code cache must live
  in PSRAM, its speed depends on the instruction cache (step 3 measures it).
- **Instruction cache**: the S3 has 16–32 KB of I-cache, and PSRAM-mapped
  code competes with the emulator's own code in flash.
- **Windowed ABI**: calls from generated code into C must respect Xtensa's
  register windows (`call8`/`entry`), or use `call0` helpers.
- **Self-modifying code**: GBA games copy code into IWRAM and rewrite it; the
  block cache must notice (gpSP already tracks it for its dynarecs).
- **Estimated effort**: about 8–13 sessions to a GBA dynarec on the board,
  then the 68000 frontend on top of the same core.
