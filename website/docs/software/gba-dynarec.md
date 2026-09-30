---
id: gba-dynarec
title: GBA Dynarec (Xtensa JIT)
sidebar_position: 6
---

# GBA Dynarec (Xtensa JIT)

How the Game Boy Advance core (gpSP, `retro-go/gbsp`) translates ARM/Thumb code into native ESP32-S3 (Xtensa LX7) code at run time: the pieces, where each one lives in memory, how a frame runs, how every change is verified, and what the measurements taught us. The step-by-step plan and the other systems that can reuse the same core are in [JIT (dynarec) plan](../next-steps/jit-plan.md).

:::info Status (2026-09-30)
Step 7 of the plan (tuning on the board). The dynarec produces the **same video and audio as gpSP's own x86 dynarec** (bit-identical hashes in QEMU on Sonic Advance, Metal Slug Advance and TMNT). On the board it beats the interpreter on TMNT and is at par on Sonic and Metal Slug; the next steps below target the remaining gap.
:::

## Interpreter vs dynarec in one picture

![Interpreter vs dynarec](/img/gba-dynarec/interp-vs-dynarec.svg)

The interpreter pays fetch + decode + dispatch on **every** instruction, every frame. The dynarec pays them **once per block** and then runs native code. That only wins if the generated code runs fast, and on the ESP32-S3 that depends on where it is stored (see [Where everything lives](#where-everything-lives)).

## The stack, layer by layer

From the silicon up to the game. Each layer only talks to the one next to it; the new parts are the dynarec layers in the middle.

![The stack, layer by layer](/img/gba-dynarec/stack.svg)

## How it is used

### As a player

Nothing changes: pick a GBA game in the launcher, it starts in the `gbsp` app. Which CPU core runs the game is decided **at build time**: a `GBAJIT=1` build of `gbsp` uses the dynarec, a normal build uses the interpreter. Save states, menus and controls are the same in both.

### As a developer

![How it is used by a developer](/img/gba-dynarec/usage.svg)

| Build flag | What it adds |
|---|---|
| `GBAJIT=1` | the dynarec instead of the interpreter (`HAVE_DYNAREC XTENSA_ARCH`) |
| `GBAPROF=1` | once a second: ms per frame (CPU, render, display, sound), a 1 kHz PC sampler for both cores, cache-sync / flush / notify counters |
| `GBABENCH=1` | the game plays itself from the save state with a frame-numbered input script; every 300 frames prints the work time per frame and a screen hash |
| `GBAJIT_IRAM=1` | experiment: code cache in internal RAM (needs memory protection off, does not fit today) |

## Life of a block

![Life of a block](/img/gba-dynarec/lifecycle.svg)

- A **block** is a straight run of guest instructions ending at a branch. It is translated once into the ROM cache (code running from the cartridge) or the RAM cache (code the game copied into IWRAM/EWRAM).
- **Linking**: the first time an exit is taken it goes through a lookup; then the exit is rewritten into a direct `j` to the next block, so hot loops jump block to block with no C code in between.
- **Time slices**: each block subtracts its cycles from `a3`; when it goes negative the block calls `update_gba`, which advances timers, DMA, sound and the scanline, raises interrupts and eventually ends the frame.

## One instruction, end to end

The Thumb instruction `adds r0, r1, r2` (flags not needed afterwards), as the translator handles it:

![One instruction, end to end](/img/gba-dynarec/instruction.svg)

If a later instruction reads the flags, the translator asks for them and `xt_add_op` also emits the carry (`saltu`), overflow (`xor`/`and`/`extui`), zero (`nsau`/`extui`) and negative (`extui`) computations and stores each as a 0/1 word in `reg[]`. A memory access (`ldr r0, [r1, #4]`) computes the address the same way and calls `xt_load_u32` through the helper table (`l32i a8, a2, slot; callx8 a8`). That handler, in IRAM, reads IWRAM/EWRAM/ROM directly and falls back to gpSP's C code for I/O.

## The pieces

![The pieces](/img/gba-dynarec/pieces.svg)

| Piece | File(s) | Role |
|---|---|---|
| Shared JIT core | `components/xjit/` | Xtensa encoders (byte-identical to `as`), block/label/literal helpers, executable memory in IRAM or PSRAM. Reused later by the 68000 frontend (Neo Geo, CPS1, Mega Drive). |
| Translator | `gbsp-libretro/cpu_threaded.c` | gpSP's own: decodes ARM/Thumb, splits blocks, computes which flags are live, looks blocks up in hash tables, flushes on self-modifying code. Unchanged except small `XTENSA_ARCH` hooks. |
| Backend | `gbsp-libretro/xtensa/xtensa_emit*.h` | Turns each guest instruction into Xtensa code. Port of gpSP's x86 backend, so its results can be compared with the x86 dynarec instruction by instruction. |
| Runtime stubs | `gbsp-libretro/xtensa/xtensa_stub.c` | The C side the generated code calls: memory handlers per region, `update_gba` at the end of a time slice, indirect-branch lookup, CPSR/SPSR, SWI, HLE divide, m4a mixer hook; also generates the `xt_enter` trampoline. |
| App | `gbsp/main/main.c` | Allocates the code cache, runs the frame loop, profiler (`GBAPROF`) and deterministic benchmark (`GBABENCH`). |
| Test benches | `retro-go/xjit-test`, `retro-go/gbajit-test`, `gbajit-test/x86ref` | Encoder test vs objdump, generated-code tests in QEMU and on the board, gpSP in QEMU with ROM + level state, x86 dynarec reference. |

## Where everything lives

The ESP32-S3 has 8 MB of PSRAM but only ~190 KB of free internal RAM, and one **32 KB instruction cache shared by both cores**. That cache is the main constraint of this design.

![Where everything lives](/img/gba-dynarec/memory.svg)

Rules that came out of the measurements:

- **Translated code is fetched from PSRAM through the I-cache.** Metal Slug generates ~900 KB of it; whatever is hot must stay small and dense.
- **Everything else that runs every frame goes to IRAM** so it does not evict translated code: the C helpers called by the generated code (`XT_HOT`) and the core-1 renderer's common case. This was the largest single gain.
- A code cache in internal RAM was tried (`GBAJIT_IRAM=1`): with retro-go's memory use there is not enough internal RAM left (the file system stops loading the game), so it is off.

## How a frame runs

![How a frame runs](/img/gba-dynarec/frame.svg)

### Host register map

| Xtensa | Use |
|---|---|
| `a0`, `a1` | return address and stack of `xt_enter` (windowed ABI) |
| `a2` | `&reg[0]`: guest registers, flags, helper table |
| `a3` | cycles left in the time slice |
| `a4` | temporary that survives helper calls (x86 `esi`) |
| `a5` | start PC of the block (PC-relative constants) |
| `a10`, `a11`, `a12` | x86 `eax`/`edx`/`ecx`: operands, helper arguments, result |
| `a8` | helper call target; `a9`, `a13`–`a15` scratch |

Guest registers and flags live in `reg[]` (flags as 0/1 words), exactly as in the x86 backend: every guest instruction loads its operands, computes, stores the result. `callx8` preserves only `a0`–`a7`, which is why nothing else is kept in registers yet (see next steps).

### Code shape

- **Exits** are patchable: `j over; .word target; l32r; jx`. Once the target block exists, the first `j` is rewritten into a direct jump.
- **Constants** use `movi`, a PC-relative `addi` from `a5`, or an inline literal.
- **Flags** are computed only when the translator says they are live (`saltu`/`nsau`/`extui`), then stored.
- **16-bit density forms** (`l32i.n`, `s32i.n`, `mov.n`, `add.n`, `addi.n`, `movi.n`) wherever they fit. All guest registers sit within reach of `l32i.n` (offset ≤ 60).

## How every change is verified

![How every change is verified](/img/gba-dynarec/verify.svg)

1. **Bit-exact reference**: gbajit-test runs gpSP in QEMU from a level save state with a fixed input script. It must print the same video and audio hashes as gpSP's x86 dynarec (`x86ref/refs_x86jit.txt`) at 300 and 600 frames. The only accepted difference is audio on Metal Slug, where the m4a mixer HLE is active.
2. **Board benchmark (`GBABENCH=1`)**: the app resumes the save state and plays a frame-numbered input script by itself. Every 300 frames it prints the work time per frame (without frame pacing) and a screen hash. The hash must not change between two builds of the dynarec.
3. **Played run**: release build, 35 s per game with right held, fire and jump, fps from the on-screen counter, three webcam photos per game.

## Results so far

Board, release builds, same save states, same played input on all three games (fps on screen, 35 s):

| Game | Interpreter | Dynarec (first run) | Dynarec (now) |
|---|---|---|---|
| Sonic Advance | 55.5 | 48 | 49.7–54.7 |
| Metal Slug Advance | 47.4 | 29 | 44.9–49.8 |
| TMNT | 44.7 | 52 | 55.5–58.7 |

The range is the spread between runs (the played input hits enemies differently each time). What each step gave, on Metal Slug in action:

| Change | Metal Slug fps |
|---|---|
| first correct board run | ~29 |
| direct aligned loads/stores (no `memcpy`) | ~31 |
| 16-bit density instructions | ~35 |
| hot C helpers in IRAM (`XT_HOT`) | 40–45 (60 in light scenes) |

## Next steps

From the profile (translated code ≈ 37–40 % of core 0) and the [research on other gpSP backends and ESP32-S3 cache features](../next-steps/jit-plan.md):

1. **Guest registers in host registers.** The MIPS/arm64/RISC-V gpSP backends keep all guest registers and flags in registers. Here that needs `call0` assembly stubs that save and restore them around C calls, because `callx8` only preserves `a0`–`a7`.
2. **Cold code out of line.** The end-of-slice `update_gba` call and the exit literals move away from the hot path, so the hot blocks stay dense in the I-cache.
3. **Inline memory fast paths** for IWRAM/EWRAM, with the C helper only as the slow path.
4. **I-cache lock/preload** of a small hot region, using the ESP32-S3 ROM cache functions (experiment).
