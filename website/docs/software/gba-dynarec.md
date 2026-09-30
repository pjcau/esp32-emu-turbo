---
id: gba-dynarec
title: GBA Dynarec (Xtensa JIT)
sidebar_position: 6
---

# GBA Dynarec (Xtensa JIT)

How the Game Boy Advance core (gpSP, `retro-go/gbsp`) translates ARM/Thumb code into native ESP32-S3 (Xtensa LX7) code at run time: the pieces, where each one lives in memory, how a frame runs, how every change is verified, and what the measurements taught us. The step-by-step plan and the other systems that can reuse the same core are in [JIT (dynarec) plan](../next-steps/jit-plan.md).

:::info Status (2026-09-30)
Step 7 of the plan (tuning on the board). The dynarec produces the **same video and audio as gpSP's own x86 dynarec** (bit-identical hashes in QEMU on Sonic Advance, Metal Slug Advance and TMNT). On the board the games now run at 56-59 emulated fps and show 54-59 fps (Sonic, Metal Slug, TMNT, played): most of the late gains came from the two cores and the display, not from the generated code.
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
- **Internal RAM is shared by both cores, and they contend for it.** Moving the renderer's 100 KB OBJ lists from internal RAM to PSRAM made Metal Slug's display faster (19-20 → 11.5-13.5 ms per frame); drawing lines into an internal-RAM buffer made both cores ~5% slower. Keep core-1 data in PSRAM, core-0 hot data (IWRAM, `reg[]`) internal.
- **Watch the internal RAM budget.** Every function moved to IRAM takes internal RAM: at 13 KB free the file system can no longer open the ROM. The dynarec build boots with ~113 KB free.

## How a frame runs

![How a frame runs](/img/gba-dynarec/frame.svg)

Two mechanisms keep the cores from waiting on each other:

- **The renderer has its own copy of VRAM.** Core 1 draws lines late (core 0 emulates the 160 visible lines in ~3 ms, the renderer needs ~6 ms), so when the game writes VRAM at the start of the vblank the queued lines still need the old contents. Instead of waiting for them, CPU stores, dynarec stores and DMA mark the 1 KB pages they write, and the dirty pages are copied into the renderer's copy when the next line is queued, by which time the renderer has long caught up. This removed ~2 ms of waiting per frame on Sonic (vblank DMA) and TMNT (sprite tiles). OAM and palette use per-line copies.
- **Three frame buffers.** Core 1 draws into one, the display task sends another, and a finished frame waits in the third until the display is free (checked every 32 lines): emulation never waits for the LCD. The render task runs below the display task, so the LCD's DMA buffers are refilled as soon as they free up.

### Host register map

| Xtensa | Use |
|---|---|
| `a0`, `a1` | return address and stack of `xt_enter` (windowed ABI) |
| `a2` | `&reg[0]`: guest registers, flags, helper table |
| `a3` | cycles left in the time slice |
| `a4`, `a6`, `a7` | guest `r0`, `r1`, `r2` (survive `callx8`; synced with `reg[]` only on entry/exit and around the HLE divide, m4a, cheats) |
| `a5` | start PC of the block (PC-relative constants) |
| `a10`, `a11`, `a12` | x86 `eax`/`edx`/`ecx`: operands, helper arguments, result |
| `a8` | helper call target, x86 `esi`; `a9`, `a13`–`a15` scratch |

The other guest registers and the flags live in `reg[]` (flags as 0/1 words), as in the x86 backend. The common Thumb ALU ops (`add`/`sub`, `and`/`eor`/`orr`, `cmp`/`cmn`/`tst`, `mov` immediate) work on the mapped registers directly. `callx8` preserves only `a0`–`a7`, so more mapped registers would need `call0` stubs that save them around every C call.

### Code shape

- **Exits** are patchable: in the hot path a branch is `bgez a3, +2; j cold; j exit`. The end-of-slice `update_gba` call, the exit literal (`.word target; l32r; jx`) and the redirect after a store go to a cold area at the end of the block. Once the target block exists, the exit `j` is rewritten into a direct jump.
- **Stores** pass the PC and the cycles left as arguments; the handler writes them to `reg[]` (the x86 code stored them before every call).
- **Constants** use `movi`, a PC-relative `addi` from `a5`, or an inline literal.
- **Flags** are computed only when the translator says they are live (`saltu`/`nsau`/`extui`), then stored.
- **16-bit density forms** (`l32i.n`, `s32i.n`, `mov.n`, `add.n`, `addi.n`, `movi.n`) wherever they fit. All guest registers sit within reach of `l32i.n` (offset ≤ 60).

## How every change is verified

![How every change is verified](/img/gba-dynarec/verify.svg)

1. **Bit-exact reference**: gbajit-test runs gpSP in QEMU from a level save state with a fixed input script. It must print the same video and audio hashes as gpSP's x86 dynarec (`x86ref/refs_x86jit.txt`) at 300 and 600 frames. The only accepted difference is audio on Metal Slug, where the m4a mixer HLE is active.
2. **Board benchmark (`GBABENCH=1`)**: the app resumes the save state and plays a frame-numbered input script by itself. Every 300 frames it prints the work time per frame (without frame pacing) and a screen hash. The hash must not change between two builds of the dynarec.
3. **Played run**: release build, 35 s per game with right held, fire and jump, fps from the on-screen counter, three webcam photos per game.

## Results so far

Board, release builds, same save states, same played input on all three games (right held, B and A tapped; fps on the on-screen counter, 35 s). *Emulated* is the game speed, *shown* the frames that reach the LCD:

| Game | Interpreter | Dynarec, first run | Dynarec now: emulated / shown |
|---|---|---|---|
| Sonic Advance | 55.5 | 48 | 58.8 / 54.5 |
| Metal Slug Advance | 47.4 | 29 | 55.7 / 55.6 |
| TMNT | 44.7 | 52 | 59.5 / 58.7 |

What each step gave (Metal Slug in action for the early ones, the deterministic benchmark for the later ones):

| Change | Effect |
|---|---|
| direct aligned loads/stores (no `memcpy`) | ~29 → ~31 fps |
| 16-bit density instructions | ~31 → ~35 fps |
| hot C helpers in IRAM (`XT_HOT`) | ~35 → 40-45 fps |
| three frame buffers (emulation stops waiting for the LCD) | Sonic 49.7 → 57.5 emulated fps |
| renderer VRAM copy | CPU time per frame −9 to −13 % (Sonic, TMNT) |
| render task below the display task | Sonic 46.6 → 54.5 shown fps |
| cold code out of line, compact stores, `r0`–`r2` in registers | 0-2 % each |

### What the counters say

The deterministic benchmark (`GBABENCH`) also reads the LX7 performance counters around the CPU emulation. On a Sonic window the dynarec executes 1.3 M host instructions per frame against the interpreter's 2.0 M, at 2.4 cycles per instruction (interpreter 1.6), with ~0.8 M cycles per frame of extra instruction-fetch stall: the translated code comes from PSRAM. The translated code itself is only ~29 % of core 0; the rest is the GBA hardware model in C (timers, DMA, sound, memory handlers, block lookup), which is why code-generation tweaks now give little.

The LCD is a hard limit: a full-screen 2x frame is ~307 KB, 15.4 ms at the 20 MHz 8-bit bus (already above the ILI9488's rated write cycle). Scrolling games cannot show much more than ~60 fps even with a free core 1.

## Next steps

1. **Faster renderer on core 1** (tile layers, sprites): less work per line, and the display task gets more of core 1.
2. **Guest registers in host registers** with `call0` stubs, as in the MIPS/arm64/RISC-V gpSP backends: bounded by the ~29 % share of translated code.
3. **The C hardware model** (timers, DMA, sound mixing, memory handlers): now the largest part of core 0.
4. **LCD bus clock** above 20 MHz: a hardware decision (signal margin), to be tried with the webcam.
