---
id: m68k-dynarec
title: 68000 Dynarec (Neo Geo, CPS1, MAME)
sidebar_position: 7
---

# 68000 Dynarec (Neo Geo, CPS1, MAME)

How the arcade emulator (`mame-go`: Neo Geo, Capcom CPS1 and the other 68000 MAME boards) is getting a dynarec: blocks of Motorola 68000 code translated into native ESP32-S3 (Xtensa LX7) code at run time, instead of interpreted one instruction at a time. It is the second frontend on the shared `xjit` core built for the [GBA dynarec](gba-dynarec.md). The step-by-step plan is in [JIT (dynarec) plan](../next-steps/jit-plan.md).

:::info Status (2026-10-01)
Step 8 of the plan is done: `m68kjit` translates 68000 blocks, with native Xtensa code for the common instructions, and it is **bit-exact against the Musashi interpreter** on 600 random-code seeds in QEMU. Step 9 is in progress: the glue for mame-go's Musashi 3.1, then Neo Geo and CPS1 games on the board. No board speed has been measured yet.
:::

## Why the 68000

On the Neo Geo and CPS1 the 68000 is the largest single cost of a frame, and the usual tricks are already spent: the idle-loop skip is on, the YM2610 and the display copy already run on core 1. Metal Slug 2 in play runs at 42 fps, and 12 of its 23.6 ms per frame on core 0 are the 68000 (source: [Arcade (MAME)](../next-steps/arcade.md)).

![Metal Slug 2 frame budget](/img/m68k-dynarec/frame-budget.svg)

The plan's estimate for the 68000 is 1.5-2.5x faster CPU emulation. At 2.5x the frame fits 16.67 ms, which means 60 fps. At 1.5x it lands near 19 ms (~52 fps). Video, Z80 and sound are untouched by the dynarec, so the next gains after it come from moving more of them to core 1.

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
4. **Board** (step 9): the speed guard against the interpreter, then games played with the webcam.

## Rules (same as the GBA)

- **Both engines in one app**, the interpreter as the fallback.
- **Automatic fallback** after a crash or hang, remembered per game, with a menu switch.
- **Never slower than the interpreter:** the first seconds of a game measure the dynarec's time per frame against the interpreter's; a game where the dynarec loses runs on the interpreter.
- **Bit-exact first:** every change passes the differential fuzz in QEMU before any board run.

Lessons carried over from the GBA: hot C helpers in IRAM, core-1 work kept out of core 0's way, the tight internal RAM budget, and translated code running from PSRAM through the shared 32 KB instruction cache.

## Steps

![68000 dynarec steps](/img/m68k-dynarec/roadmap.svg)

| Step | Goal |
|---|---|
| 9 | mame-go: Musashi 3.1 glue, build switch, fallback, speed guard; Metal Slug 2 in play toward 55-60 fps, CPS1 games |
| 10 | gwenesis (Mega Drive), if it helps there: its 68000 takes 5.5 ms, the VDP (11.3 ms) is the main cost |

The 68000 frontend also covers Sega System 16/18 and the other 68000 MAME boards at no extra cost, and the CPU side of CPS2 (see [JIT (dynarec) plan](../next-steps/jit-plan.md)).
