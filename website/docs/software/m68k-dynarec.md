---
id: m68k-dynarec
title: 68000 Dynarec (Neo Geo, CPS1, MAME)
sidebar_position: 7
---

# 68000 Dynarec (Neo Geo, CPS1, MAME)

The arcade emulator (`mame-go`: Neo Geo, Capcom CPS1 and the other 68000 MAME boards) has a dynarec for the Motorola 68000: blocks of 68000 code translated into native ESP32-S3 (Xtensa LX7) code at run time, instead of interpreted one instruction at a time. It is the second frontend on the shared `xjit` core built for the [GBA dynarec](gba-dynarec.md).

:::info Status (2026-10-03)
The dynarec **works and is exact, and it is slower than the interpreter** on the board: 13.1 ms of 68000 per frame against 7.7 ms on Metal Slug's attract loop. It is switched off and on hold. This page says why, what would have to change for it to win, and what is being done instead to make the 68000 cheaper. The open work is in the [Arcade 60 fps plan](../next-steps/arcade-60fps-plan.md).
:::

## What is expensive, measured

Everything below is Metal Slug, mission 1 being played (the play benchmark of the Arcade 60 fps plan), 2026-10-03, with the interpreter.

**The frame.** A drawn frame takes 24.7 ms; 60 fps needs 16.7.

| Core | Part | ms per frame |
|---|---|---|
| 0 | 68000 (interpreter) | 10.9 |
| 0 | video: sprite list, palette, sprites, fix layer | 10.4 |
| 0 | everything else | 1.1 |
| 0 | waiting for core 1's sound job | 2.3 |
| 1 | sound board: Z80, YM2610, ADPCM, mixer | about 12 |
| 1 | display: scaling, filter, the LCD bus | 11.3 |

The 68000 is the largest single item on core 0, but it is under half of that core's work, and core 1 is as full as core 0. A faster 68000 alone does not reach 60 fps.

**Inside the 68000.** The sampling profile of core 0 in play:

| Where the samples land | Share of core 0 |
|---|---|
| reading the next opcode word (`m68ki_read_imm_16`) | 15 % |
| the opcode handlers, memory handlers and dispatch, together | about 29 % |

The opcode read is one array access with prefetch emulation off, so its 15 % is not instructions being executed: it is the CPU waiting for memory. Metal Slug's 2 MB program is served from the flash partition through the 64 KB data cache, which it shares with everything the game keeps in PSRAM. The interpreter runs at about 46 host cycles per 68000 instruction, and a third of that is this wait.

## Does a dynarec make sense here?

The usual argument for a dynarec is that it removes the interpreter's decode and dispatch. On this chip the argument fails on memory, not on instruction counts.

| | Interpreter | Dynarec (measured) |
|---|---|---|
| Host cycles per 68000 instruction | 46 | 78 |
| 68000 per frame, Metal Slug attract | 7.7 ms | 13.1 ms |
| Bytes fetched per 68000 instruction | 2-6 (the guest code itself) | 70-80 (translated Xtensa code) |
| Which cache they come through | data cache, 64 KB | instruction cache, 32 KB, shared with all the firmware's code |
| Where they live | flash partition | PSRAM, 1 MB code cache |

- The interpreter's code (Musashi's handlers) is a few tens of kilobytes that stay hot; what streams through the cache is the guest program, 2 to 6 bytes per instruction.
- The dynarec turns every guest instruction into 70-80 bytes of host code. On Metal Slug that was 635 KB of translated code behind a 32 KB instruction cache, with the code cache flushed 12 times in 70 seconds. The sampler put about 9 % of core 0 in translation and 7 % in synchronising the caches for new code.
- So the dynarec trades the interpreter's memory wait for a larger one, fifteen to twenty times more bytes through a cache half the size.

**What would have to be true for it to win**, in order:

1. The hot translated code in internal RAM, not PSRAM. There is no internal RAM for it: 5 to 15 KB are free while a game runs, and the file system needs them.
2. Or the translated code three times denser, about 25 bytes per instruction, which is steps F3 to F5 of the code generation plan (direct ROM and RAM access, guest registers pinned in host registers, lazy flags) and 8 to 12 days of work, with the gain still decided by the cache.
3. And a game whose hot code per frame fits what the cache can hold. Neo Geo games run a lot of distinct code every frame.

The steps already done confirm the direction: 16-bit instruction forms gave 10 % less code and 0.8 ms (F1); taking interrupts between instructions removed the flag bookkeeping before every memory access (F2). Neither changes the order of magnitude.

**Decision (2026-10-03).** The 68000 dynarec stays off and on hold. It is not the way to halve the 68000 on this hardware. It is reopened only if one of these is measured: a build that frees 64 KB or more of internal RAM for a code cache, or a step of the code generation plan that brings a full MAMEBENCH run under the interpreter's time. The estimate that started this work (1.5 to 2.5 times faster 68000, 55-60 fps on Metal Slug 2) was made before any board measurement and did not hold.

**What is done instead**, on the interpreter, where the memory wait is the target:

- the first megabyte of the program in PSRAM instead of flash, on the reasoning that a cache line fills about three times faster from the octal PSRAM than from the quad flash: **measured, no gain** (68000 10.88 → 10.62 ms, and the sprite page cache that gave up the memory cost more than that). The wait is the cache's size, not the speed of what is behind it;
- candidates after it, each to be measured the same way: the hot opcode handlers and the memory fast paths in internal RAM where they are not already, and the Neo Geo memory map's common cases (work RAM, program ROM) read without going through MAME's handler tables.

The rest of this page describes the dynarec as built, for when it is reopened and because the same design serves the GBA.

## Built on top of the interpreter

![Musashi interpreter vs m68kjit](/img/m68k-dynarec/interp-vs-jit.svg)

The key design choice: `m68kjit` does **not** replace Musashi, it runs **on top of** the emulator's own copy of it. The translated code works directly on Musashi's registers, flags and cycle counter. Any instruction the translator does not know becomes a call to Musashi's own handler for that opcode. So:

- **every instruction works from the first day**, including the rare ones (BCD, MULU/DIVU, MOVE to SR, TRAP...);
- **the result is the interpreter's**, instruction by instruction, which is what the fuzz checks;
- the translator can grow one instruction family at a time, each one verified before the next.

## The stack, layer by layer

![The 68000 dynarec stack](/img/m68k-dynarec/stack.svg)

| Layer | Where | Role |
|---|---|---|
| mame-go | `retro-go/mame-go` | MAME 0.37b5 drivers for the Neo Geo, CPS1 and 68000 boards; calls `m68k_execute()` for each CPU time slice |
| Musashi 3.1 | inside mame-go | the 68000 interpreter the dynarec leans on |
| glue | `components/m68kjit/glue/glue_musashi31.c` | compiled against mame-go's Musashi: fills `m68kjit_host_t` and provides a `m68k_execute()` whose loop body is `m68kjit_run()` |
| m68kjit | `components/m68kjit/` | length decoder, block builder, native forms, block cache (4096 blocks, 1 MB of code in PSRAM), chaining |
| xjit | `components/xjit/` | the shared Xtensa encoders, labels and executable PSRAM, same as the GBA |

All of it is in the public repository **[pjcau/xtensa-68000-dynarec](https://github.com/pjcau/xtensa-68000-dynarec)**, next to the GBA backend (the 68000 frontend's own notes: `docs/m68k.md`, `docs/roadmap-68000.md`).

### What the emulator hands over

The emulator connects through one struct, `m68kjit_host_t`, so the same dynarec serves different Musashi versions (mame-go has 3.1, gwenesis 3.32, the test bench 4.5):

| Field | What it is |
|---|---|
| `pc`, `ppc`, `ir`, `dar[16]` | the interpreter's PC, previous PC, current opcode, D0-D7/A0-A7 |
| `flag_x/n/z/v/c`, `cycles` | Musashi's flags (X/C in bit 8, N/V in bit 7, Z = 0 when set) and the cycles left in the slice |
| `handlers`, `cyc` | the 65536-entry opcode handler and base cycle tables |
| cycle adjustments | per-CPU-type extras: not-taken branches, DBcc, shift counts, MOVEM registers |
| `read8/16/32`, `write8/16/32` | memory as the interpreter's instructions see it (address mask, function code) |
| `branch_back`, `pc_changed` | optional hooks: mame-go's idle-loop check after a short backward branch, `m68ki_jump()` after JSR/RTS |
| `step`, `is_code`, `read_code16` | one interpreted step for untranslated code; which addresses are fixed code (ROM) |

## Inside a block

![Inside a block](/img/m68k-dynarec/block.svg)

- A **block** is up to 64 instructions from one PC, only in fixed code (ROM). Code in RAM stays interpreted, so a game writing memory can never leave a stale block behind.
- It ends after an instruction that never falls through (BRA, JMP, JSR, BSR, RTS, RTE, TRAP...).
- It leaves exactly where `m68k_execute()` would stop or change course: a taken branch, an exception, an interrupt taken inside a memory handler (mame-go's Musashi 3.1 takes it immediately), or the end of the time slice.

### Native instructions

| Group | Forms |
|---|---|
| Moves | MOVEQ; MOVE/MOVEA between registers, `#imm` and every memory mode (`(An)`, `(An)+`, `-(An)`, `(d16,An)`, `(d8,An,Xn)`, abs.w/.l, PC-relative); MOVEM (register list unrolled) |
| Arithmetic / logic | ADD SUB CMP AND OR from registers, `#imm` or memory; EOR Dn,Dm; ADDA SUBA CMPA; ADDQ SUBQ; ORI ANDI SUBI ADDI EORI CMPI; the read-modify-write forms on memory |
| Other | TST, CLR, SWAP, EXT.w/.l, LEA and PEA on every control mode; LSL LSR ASL ASR ROL ROR by `#n` on Dn |
| Flow | Bcc and DBcc, BSR, JSR, RTS |

Left to Musashi's handlers on purpose: BRA and JMP (the branch-to-self idle rule differs between Musashi versions), MULU/DIVU, ADDX/SUBX, BCD, bit operations, shifts by a register or on memory, ROXL/ROXR, MOVE to/from SR/CCR/USP, TRAP, RTE. In random valid 68000 code, **84 %** of the executed instructions are native.

Memory goes through the interpreter's own accessors, in Musashi's order (source before destination, reads before writes), with PC holding what the interpreter's `REG_PC` holds at each access.

## Chaining

![Block chaining](/img/m68k-dynarec/chaining.svg)

An exit with a known target jumps through a slot. The first time, the slot holds a stub that returns to the dispatcher; once the dispatcher has the target block, it writes that block's chain entry into the slot and the exit goes straight there. The cycle check stays in front of every chained jump, so a chained run still stops where `m68k_execute()` stops.

## How every change is verified

![How the 68000 dynarec is verified](/img/m68k-dynarec/verify.svg)

`test/m68k-test` in the repository:

1. **Lengths**: `m68kjit_insn_len()` equals Musashi's disassembler on all 45799 opcodes valid on the 68000 (PC).
2. **Block model**: the C form of the blocks against `m68k_execute()` on random machines, with four mutations the fuzz must catch (PC).
3. **Generated code in QEMU**: 300 seeds of random valid code, 300 seeds whose ROM is 85 % native forms, and 20 seeds for each of the 23 instruction families alone. They are compared after each of 32 time slices with random interrupt levels: registers, SR, USP/ISP, cycles used and left, RAM hash.
4. **Board** (step 9): MAMEBENCH with the dynarec gives the interpreter's 7 screen hashes on Metal Slug; the speed guard against the interpreter is what keeps it off.

## Rules (same as the GBA)

- **Both engines in one app**, the interpreter as the fallback.
- **Automatic fallback** after a crash or hang, remembered per game, with a menu switch.
- **Never slower than the interpreter:** the first seconds of a game measure the dynarec's time per frame against the interpreter's; a game where the dynarec loses runs on the interpreter.
- **Bit-exact first:** every change passes the differential fuzz in QEMU before any board run.

Lessons carried over from the GBA: hot C helpers in IRAM, core-1 work kept out of core 0's way, the tight internal RAM budget, and translated code running from PSRAM through the shared 32 KB instruction cache.

## Steps

![68000 dynarec steps](/img/m68k-dynarec/roadmap.svg)

| Step | State |
|---|---|
| 8 | done: `m68kjit` translates 68000 blocks, bit-exact against Musashi on the QEMU fuzz |
| 9 | done as far as the measurement: the glue for mame-go's Musashi 3.1, the build switch, Metal Slug on the board with the 7 screen hashes of the interpreter. Slower than the interpreter, so the switch stays off |
| 9f | the code generation plan ([`docs/codegen-plan.md`](https://github.com/pjcau/xtensa-68000-dynarec/blob/main/docs/codegen-plan.md)): F0 counters, F1 16-bit forms and F2 interrupts between instructions done; F3 direct ROM and RAM access, F4 pinned registers and F5 lazy flags on hold; F6, a code cache in internal RAM, has no RAM to live in |
| 10 | gwenesis (Mega Drive): not started. Its 68000 takes 5.5 ms and the VDP 11.3 ms, and the same cache limit applies |

The 68000 frontend would also cover Sega System 16/18 and the other 68000 MAME boards, and the CPU side of CPS2 (see [JIT (dynarec) plan](../next-steps/jit-plan.md)), under the same condition.
