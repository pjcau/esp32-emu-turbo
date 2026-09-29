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

QEMU with an ESP32-S3 machine is in the ESP-IDF Docker image
(`esp_develop_9.0.0_20240606`, `idf.py qemu`). It runs the S3 instruction
set, so it can check that generated code is **correct**. It says nothing
about **speed**: it does not model the caches, PSRAM timing or cycles.

| Step | What | Where | Board needed? |
|:---|:---|:---|:---|
| **0. Harness** | Standalone test app `retro-go/xjit-test` (ESP-IDF). Hello world and a hand-written native function called through a pointer, run in QEMU. Check what QEMU supports: IRAM execution, PSRAM, `esp_mmu_map` with exec. | PC + QEMU | No |
| **1. Emitter** | Port Dragonfruit's emitter to `xjit`. For every instruction: encode on the PC, disassemble with `objdump`, compare with the assembler's bytes. | PC | No |
| **2. Generated code runs** | Generate small functions (add, loop, load/store, call back into C), run them from IRAM; then from PSRAM mapped executable, with the cache sync. | QEMU, then board | Board for PSRAM exec and cache sync (QEMU may not model them) |
| **3. Speed (decision gate)** | Microbenchmarks: a generated loop from IRAM and from PSRAM, the same loop in compiled C, the cost of an I-cache miss, entering and leaving a block. Decide where the code cache lives and what speedup to expect. | Board | **Yes**: timing only on the board |
| **4. Mini frontend** | A small Thumb subset (ALU, compare, branch, load/store) translated by `xjit`. Differential test: random instruction sequences run through gpSP's interpreter and through the JIT, registers and memory compared. | PC (interpreter) + QEMU (JIT) | No; one board spot check |
| **5. GBA backend** | The full gpSP Xtensa backend. Run the existing level save states in QEMU (ROM in a flash partition, frame and audio hashes on the UART) and compare with the PC interpreter's reference hashes, bit for bit. | QEMU | No |
| **6. GBA on the board** | Sonic Advance, Metal Slug Advance, TMNT and more games: on-screen fps, webcam shots of every game, save and load. Interpreter kept as the fallback (a setting, and automatic for games that fail). | Board | **Yes** |
| **7. GBA speed** | Profile on the board, tune the code cache, register allocation, block linking. | Board | **Yes** |
| **8. 68000 frontend** | Dragonfruit's 68000 frontend on `xjit` in the test app. Differential test against the MAME 68000 interpreter (instruction sequences, then whole frames of a Neo Geo attract). | PC + QEMU | No |
| **9. Neo Geo and CPS1** | Into mame-go behind a switch: Metal Slug 2 in play (goal 55–60 fps), CPS1 games, webcam checks. | Board | **Yes** |
| **10. Mega Drive** | The same 68000 frontend in gwenesis, if it helps there. | Board | **Yes** |

**Summary: steps 0, 1, 4, 5 and 8 need no board. Step 2 needs it at the end,
and steps 3, 6, 7, 9 and 10 need it throughout.** Step 3 is the go/no-go
point: if generated code is not clearly faster than the interpreter there,
the plan stops before any emulator changes.

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
