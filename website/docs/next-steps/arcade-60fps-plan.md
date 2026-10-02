---
id: arcade-60fps-plan
title: Arcade 60 fps plan
sidebar_position: 9
---

# Arcade 60 fps plan

The work plan for running the 68000 arcade games of `mame-go` (Neo Geo first, then
CPS1 and the other 68000 MAME boards) at **60 rendered frames per second** on the
ESP32-S3, without frameskip. It merges our own measurements, an external review
(Gemini) and a review of the dynarec code generator. Every step is generic where it
can be: the board-wide steps help every emulator, the MAME steps every MAME game, the
Neo Geo steps every Neo Geo game. Metal Slug is only the reference benchmark.

Related pages: [Arcade (MAME)](arcade.md), [JIT (dynarec) plan](jit-plan.md),
[68000 dynarec](../software/m68k-dynarec.md).

## Where we are (2026-10-02)

Reference: `MAMEBENCH`, a deterministic on-board benchmark. It loads a save state of
Metal Slug at level 1, plays a scripted input, and hashes the frame every 300
frames. The **7 reference hashes must stay identical** after every change, unless a
step says otherwise.

| Core 0, ms per frame | Start | Now |
|---|---|---|
| 68000 (Musashi interpreter) | 10.06 | **7.72** |
| Video (sprites, fix layer, clear, palette) | 12.25 | **~9.8** |
| Other (MAME frame loop, input, mixer, waits) | ~4.1 | ~5 |
| **Total** | **26.4** | **~22.8** (about 44 fps) |

The target is **16.7 ms**. Core 1 runs the display task (7-11 ms per frame) and
the YM2610 + Z80 (4-7 ms per frame). It is 61-71 % busy.

Two facts drive the whole plan:

1. **PSRAM is the bottleneck, not the instruction count.** Writes to PSRAM run at
   ~32 MB/s, and both cores share that bandwidth. A sprite renderer with fewer
   instructions gained nothing. Moving a PSRAM job to core 1 gained nothing either,
   because it slowed core 0's own PSRAM accesses by the same amount.
2. **The LCD bus is not the limit.** The display task's time is CPU work (scaling,
   palette lookup, line hashing); the bus runs by DMA in parallel. Going from 20 to
   25 MHz changed nothing.

## Done

| Step | Scope | Gain on core 0 |
|---|---|---|
| Palette fast paths (dirty flags, cached used-pen base) | all MAME 8-bit-pen games | 0.8 ms |
| Direct display: the display task reads MAME's 8-bit bitmap itself | all MAME games on the 8-bit path | 1.75 ms |
| Hot code in IRAM, CPU state in DRAM | all MAME games | 0.4 ms |
| Aligned 16-bit RAM/ROM accesses and opcode fetch (`ALIGN_SHORTS` made every word access two byte loads) | all 16-bit MAME CPUs, the 68000 opcode fetch | 0.6 ms |
| Inline RAM/ROM fast path in Musashi (no call into `memory.c`) | all 68000 games | 0.13 ms |
| V1: Neo Geo frame drawn in 16-line bands in internal RAM, one strip walk for pens and list (2026-10-02) | all Neo Geo games | 0.3 ms on its own (the band copy eats the rest; V2 removes it) |
| D1: the display's change test on the source line + palette, unchanged blocks not rendered (2026-10-02) | all emulators | core 1: display task 12.2 → 8.6 ms |
| D2: pattern-driven horizontal scaling with the filter fused in (2026-10-02) | all emulators | core 1: 8.6 → 8.0 ms |
| F1: 16-bit forms in the dynarec (2026-10-02) | all 68000 games on the dynarec | 68000 13.9 → 13.1 ms (dynarec only) |

## Tried and dropped

All of these were measured and kept the hashes identical; none of them gave a gain:

- **16-bit bitmaps** for the Neo Geo: video got 2 ms slower.
- **Clearing the bitmap on core 1**: no gain, because the PSRAM is shared.
- **Turning off the per-line change hash**: the display task went to 20.4 ms and
  core 1 saturated. The hash pays for itself.
- **A faster sprite plotter** (skip empty words, no per-pixel tests on opaque words,
  palette in internal RAM): no gain. Sprite drawing is bound by PSRAM.
- **LCD bus at 25 MHz**: no gain, as explained above. We stay at 20 MHz for signal
  margin.
- **Sprites on core 1**: there is no room. Core 1 has 4-6 ms free, and the sprites
  need about 10 ms.
- **Lazy cycle counting** in the interpreter: it changes when interrupts are taken,
  so the results would no longer be exact.
- **A Rust rewrite**: the problem is the generated code and the memory hierarchy, not
  the language.
- Already in place: a **64 KB data cache with 64-byte lines**, FC emulation off, and
  Musashi's jump-table dispatch (there is no `switch` to replace).

## The plan

Rules for every step:

- **Exactness.** The interpreter steps keep the 7 MAMEBENCH hashes identical. The
  dynarec steps must also pass the QEMU differential fuzz with 0 mismatches against
  both Musashi 4.5 and 3.1.
- **Measure it, or drop it.** Each step is measured with MAMEBENCH on the board,
  always averaged over the same window of frames. A step that does not gain is
  reverted.
- **Look at the screen.** Every board run is checked through the webcam
  (`board_cam.py`).
- **Test more than one game.** Before a step is closed, check at least Metal Slug,
  Metal Slug 2, Sonic Wings 2 and KOF95 for the Neo Geo, and SF2 and Final Fight
  when CPS1 or generic MAME code changed.

### Phase V: band rendering for the Neo Geo (all Neo Geo games)

Expected gain: 3-4.5 ms. Risk: medium. This is the largest video gain, and it attacks
the PSRAM bottleneck directly.

Every step has a PC part (development, correctness on the x86 harness
`scripts/neogeo_frames.py`) and a board part (timing with MAMEBENCH, the webcam);
the **Board?** column says what cannot be done without the board.

| Step | What | Board? |
|---|---|---|
| **V0** | **Measure.** Split the video time into palette, clear, sprites and fix layer, and count how many PSRAM bytes each part reads and writes. | **Yes, all of it**: the timings and the PSRAM counts only mean something on the board (`board_run.sh v0 mslug`). |
| **V1** | **Draw in bands in internal RAM.** 16-line bands of 304 pixels at 8-bit pens, two buffers of 4.9 KB each in internal RAM (22 KB free). Each band is cleared to the backdrop in internal RAM, the sprite strips are drawn clipped to the band, the fix layer is drawn per band. Before the first band, one pass over the 381 strips sorts them into a list per band, so that a band does not walk every strip. | **Only the timing** (about an hour). The correctness — the band image byte-identical to the full frame — is proven on the PC: `neogeo_frames.py compare` must say IDENTICAL on Metal Slug, Metal Slug 2, Sonic Wings 2 and KOF95. |
| **V2** | **Hand bands to the display.** The display task scales each finished band and sends it, with the per-line change hash kept. Core 0 draws band N+1 while core 1 sends band N. The PSRAM frame bitmap disappears: no 72 KB clear, no 72 KB write, no 72 KB read. | **Yes, all of it**: display task, DMA, core sync; the longest board block of the plan. |
| **V3** | **Raster effects.** Games that change the scroll in the middle of a frame (the `ssideki`-style partial refresh) have to cut bands at the changes, or fall back to the full-frame path. | **Only the timing and the webcam** on a raster game; the correctness on the PC as for V1. |

Exit criterion: hashes identical (the band image must equal the full-frame image),
and video at 6 ms or less.

### Phase D: the display task on core 1 (all emulators)

Expected gain: 1-2 ms on core 1. Risk: low. It gives the audio more room on core 1,
and the bands of phase V more room on the display side.

| Step | What | Board? |
|---|---|---|
| **D1** | A cheaper line hash (a 32-bit sum or xor over words, instead of byte-wise FNV), or a SIMD (PIE) version of it. | **Only the timing and the screen**; the new hash is checked against the current one on the PC. |
| **D2** | Scaling 304 to 434 pixels from a precomputed pattern, unrolled; with SIMD if D1 shows that PIE pays. | **Only the timing and the screen**; the scaled lines are compared with the current function's on the PC. |

### Phase J: a denser dynarec (all 68000 games)

The interpreter is now at 7.72 ms, and that is the number to beat. The dynarec is at
13.9 ms, with ~70-80 bytes of Xtensa code per 68000 instruction executed from PSRAM
through the 32 KB instruction cache. The steps follow the code-generator review
(F0-F6), with the corrections listed below.

| Step | What | Time, risk | Board? |
|---|---|---|---|
| **F0** | Starting measurement: bytes per 68000 instruction by kind (register-only, memory, call-out), cache flushes per minute, 68000 ms on MAMEBENCH. **Added:** decide whether the cost is instruction-cache misses or instruction count. Use Xtensa performance counters if the IDF exposes them; if not, run the same blocks with a small hot set and compare. | 0.5 day, low | **Yes, all of it**: instruction cache behaviour and MAMEBENCH timings exist only on the board. |
| **F1** | 16-bit narrow instructions (`l32i.n`/`s32i.n` for 68000 registers at offsets of 60 or less, `mov.n`, `add.n`, `addi.n`, `movi.n`, `beqz.n`/`bnez.n`). Expected 20-25 % less code, same results. | 1 day, low | **Only the final timing** (about an hour). The development and the QEMU fuzz at 0 mismatches are on the PC. |
| **F2** | Interrupts taken only between instructions (`m68k_set_irq` marks the interrupt, and the next instruction boundary takes it, as on the real 68000 and in Musashi 4.x). Same change in the interpreter and the dynarec. **Added, first:** count how often an IRQ is raised from inside a memory handler. If it never happens on Neo Geo or CPS1, the hashes do not change at all. If it does, take new reference hashes once, validated in play with the webcam. Then `mem_may_interrupt = false`: no PPC/IR/PC stores and no flag materialisation before each access. Expected 30-40 % less code on memory instructions. | 2-3 days, medium | **Partly**: counting the IRQs raised inside handlers, the hashes and a real game with the webcam are on the board; the development is on the PC. |
| **F3** | Direct RAM/ROM access in the generated code. **Changed:** start from the interpreter fast path that already exists, MAME's first-level table (a shift, a byte load, a compare, the bank base, a 16-bit load), emitted inline, with the slow call kept outside the block. A dedicated direct-pointer page table (FAME/C `Fetch[]` style) comes later, only if F0 shows the extra loads matter; it must follow `cpu_setbank` and CPU context switches. Writes keep the idle-loop write hash. | 2-3 days, medium | **Only the final timing**; development and fuzz on the PC. |
| **F4** | 68000 registers held in Xtensa registers across a block. `callx8` keeps only the caller's a0-a7, so the review's switch to `callx12` (which keeps a0-a11) is correct. **Added:** `callx12` rotates the window further and causes more window-overflow spills, so measure it. Keep the 4 most-used 68000 registers (chosen from F0's statistics) in a8-a11, and write them back only before a handler call and at block exit. | 2-3 days, medium | **Only the final timing** (the window-spill cost is a board measurement); development and fuzz on the PC. |
| **F5** | Lazy flags, only if F0 repeated after F2 shows that flags are still more than 15 % of the code. | only if needed | **Only the final timing**; development and fuzz on the PC. |
| **F6** | JIT cache in IRAM: postponed. It needs at least 24 KB of free internal RAM, and below ~13 KB free the file system no longer opens ROMs. Phase V takes ~10 KB, so F6 is out unless something else frees memory. | postponed | — |

Target: 20-25 bytes per 68000 instruction, so that the hot working set fits the
instruction cache, and **68000 time below the interpreter's 7.72 ms**, aiming at
5-6 ms.

### What 60 fps needs, honestly

| Core 0 | Now | After V | After V + J |
|---|---|---|---|
| 68000 | 7.7 | 7.7 | 5-6 |
| Video | 9.8 | ~5.5-6 | ~5.5-6 |
| Other | ~5 | ~4 | ~4 |
| **Total** | **~22.8** | **~17.5** | **~15-16** |

Neither phase is enough on its own: 60 fps without frameskip needs both phase V and
phase J. The remaining "other" (MAME's frame loop, input, the mixer, the wait for
the display) gets its own profiling pass after phase V. If phase J falls short,
the fallback is an automatic frameskip of 1 frame in 2, only under load.

## Revised plan (2026-10-02, evening)

Three measurements of the day change the order of the plan.

1. **The LCD bus is the display's wall.** 434 × 320 × 2 bytes at 20 MHz is 13.9 ms a
   frame when every line changes; D1 + D2 removed the CPU work that hid it. Core 0
   must never wait for the display, and the pipeline must absorb bursts without
   PSRAM traffic: the V2 run without a frame in PSRAM ran the 68000 at 6.96 ms
   against 8.2-8.3 with one (PSRAM contention, fact 1 of this plan), 1.2 ms
   that a PSRAM stage would give back.
2. **The dynarec is I-cache bound.** 78 host cycles per 68000 instruction against
   the interpreter's 46 (13.08 vs 7.72 ms), with 635 KB of code in PSRAM behind
   a 32 KB instruction cache and the code cache flushed 12 times in 70 s. Denser
   code helps at the margin (F1: −10 % bytes, −0.8 ms); beating the interpreter
   needs an internal-RAM code cache (F6), and the internal RAM is spoken for.
   Phase J is a bet, not a plan.
3. **Core 0 after V2 is ~18.5 ms with the interpreter**: 68000 7-8, sprites 4.7,
   palette + strip walk 2.25, fix 0.8, other 2.6, mixer 0.9. The 2 ms to 16.7 are
   in the parts never profiled (other, mixer, palette), not only in the 68000.

### The order now

| Step | What | Expected | Board? |
|---|---|---|---|
| **V2h** | **Hybrid band hand-over.** The display task scales a band straight from its internal-RAM buffer while it keeps up; when the next band arrives before it is done, only the rows not yet scaled are copied to a PSRAM stage and the buffer is released. Zero PSRAM traffic in steady state (the bus, 13.9 ms, is faster than core 0's 18.5), the stage only as a shock absorber. Replaces the "stage everything" V2 of job 060 (kept as a data point). | core 0 ~18.5 ms, 68000 back near 7 | timing + screen |
| **B1** | **LCD bus at 25 MHz** (`RG_LCD_I80_CLK_HZ`), now that the bus shows: 13.9 → 11.1 ms a frame, more slack for the band pipeline. The earlier "no gain" was measured when the display's CPU work was the limit. Signal margin: the webcam decides (artefacts), the hashes cannot see the bus. | display pipeline slack | **yes, all** |
| **O1** | **Mixer to core 1** (0.9 ms; core 1 is 50-60 % busy and the YM2610 already runs there). | −0.9 ms core 0 | timing |
| **O2** | **Palette:** `palette_recalc()` over 4096 entries every frame and the strip walk (2.25 ms together). Dirty tracking of the pens actually used, and the walk's list kept across frames when the sprite list did not change. | −1 ms | PC + timing |
| **O3** | **"Other" 2.6 ms:** profile the frame loop, input, the waits (MAMEPROF on core 0 with the interpreter). | −0.5-1 ms | profile |
| **J (optional)** | Only steps with a measurable gate: the code-cache flush policy and hot threshold (12 flushes/70 s; `hot_threshold` is a host parameter), then F3 as an IRAM stub for the memory fast path, then the decision on F4 from the register counts (Metal Slug: pending job 050). The dynarec stays off by default until a MAMEBENCH run beats the interpreter's 7.72 ms. | 68000 < 7.72 or stop | timing |

With V2h and O1-O3, core 0 lands at **~16-16.5 ms with the interpreter**: 60 fps
without the dynarec. J then buys margin for heavier games (Puzzle Bobble 2).

## Order (original)

1. Phase V (V0 → V1 → V2 → V3), Neo Geo.
2. Phase D (D1 → D2), all emulators.
3. Phase J (F0 → F1 → F2 → F3 → F4 → F5 if needed), all 68000 games.
4. Then the same band approach for the CPS1, if its video turns out to be the
   limit there.

The dynarec steps are developed and fuzzed in the public
[xtensa-68000-dynarec](https://github.com/pjcau/xtensa-68000-dynarec) repository;
the detailed F0-F6 design is its
[`docs/codegen-plan.md`](https://github.com/pjcau/xtensa-68000-dynarec/blob/main/docs/codegen-plan.md).
The mame-go steps live in the retro-go fork.

## Status and how to resume

- **2026-10-02:** plan written. Interpreter memory work done (retro-go fork
  `9a9ec1f1`): 68000 at 7.72 ms. **Next: V0.**
- **2026-10-02, later:** V0 instrumentation in place (retro-go fork, `NEOPROF`
  builds): the video time is split into palette / clear / sprites / fix layer, with
  the bytes each part moves (`NEOPROF video ms/frame:` line, summarised by
  `mbsum.py`). The normal build is untouched. **Next: run V0 on the board** —
  `scripts/mamebench/mamebench.sh 0 /sd/roms/neogeo/mslug.zip 70 > mb.txt` then
  `mbsum.py mb.txt`; hashes must stay the reference ones. Record the split here,
  then V1.
- **2026-10-02, V0 done** (`results/2026-10-02-v0-mslug.txt`, fork `cec99363`,
  hashes identical, 38 samples):

  | Core 0 | ms | | Video part | ms | PSRAM KB/frame |
  |---|---|---|---|---|---|
  | 68000 | 7.94 | | palette (`neogeo_palette`) | 1.73 | vidram reads only |
  | video | 10.13 | | clear | 1.53 | 66.5 written |
  | other | 2.48 | | sprites (369 tile strips) | 6.05 | 44.3 read, up to 88.0 written |
  | mixer | 0.85 | | fix layer (130 tiles) | 0.76 | 8.1 read, up to 8.1 written |
  | **total** | **23.20** | | rest | 0.06 | |

  Two findings for V1. (1) The clear writes 66.5 KB at ~43 MB/s and the sprites
  write up to 88 KB: with bands both go to internal RAM, which is the 3-4.5 ms
  the plan expects. V1 alone copies each finished band to the PSRAM bitmap
  (66.5 KB sequential, ~1.5 ms), so its full gain only shows with V2.
  (2) **The sprite list is walked twice per frame**: `neogeo_palette()` walks all
  381 strips and their tiles to find the pens in use (`colmask`) before
  `palette_recalc()`, then `screenrefresh_()` walks them again to draw. V1's
  pre-pass does both in one walk: it records every visible tile strip (about
  370 entries of 12 bytes on Metal Slug, in order, bucketed per band) and the
  pen masks, then `palette_recalc()`, then the bands draw from the list without
  reading the video RAM again. **Next: V1** (PC first, `neogeo_frames.py compare`).
- **2026-10-02, V1 written, not yet proven** (fork, `NEOBAND=1` builds,
  `vidhrdw/neogeo_band.c`): the one walk records the ~370 visible tile strips in
  a list per 16-line band (PSRAM, 16 bytes each) and the pen masks, then each
  band is cleared, drawn and fix-layered in a 5.6 KB internal-RAM buffer and
  copied to the frame bitmap (304 visible columns). Builds for the PC (both
  variants) and for the board. **Two gates before it counts**: (1) on the PC,
  `scripts/neogeo_frames.py compare <sysdir> <rom> 3000 --input attract` must
  say IDENTICAL on Metal Slug, Metal Slug 2, Sonic Wings 2 and KOF95 (needs the
  ROMs on the development machine); (2) on the board,
  `NEOBAND=1 scripts/mamebench/board_run.sh v1 mslug 70`: the 7 hashes must be
  the reference ones, and the `copy` part of the split shows what V2 will remove.
- **2026-10-02, D1 written, proven on the PC, not yet timed** (fork,
  `components/retro-go/rg_line_hash.h`, `rg_display.c`): the display task's
  "did this line change" test now hashes the **source** line (304 pens on the
  Neo Geo instead of 868 bytes of scaled RGB565) plus, once per frame, the
  palette, with a 2-operations-per-word hash; a block of lines that are all
  unchanged is not rendered at all. The decision is the same as before by
  construction (same source and palette, same rendered line);
  `components/retro-go/test/run_line_hash_test.sh` proves the hash
  (determinism, alignment, every 1-bit change seen, 0 collisions in 1e6).
  It is in every build from now on: the gain is the `display` ms of the
  `NEOPROF core1` line against V0's 8.42 ms, at the same NEOBAND setting.
- **2026-10-02, D2 written, proven on the PC, not yet timed** (fork,
  `components/retro-go/rg_scale_line.h`): the horizontal scaling is driven by
  the per-source-pixel repeat pattern (304 source pixels walked once, no map
  lookup per output pixel) and the horizontal filter is fused into the same
  loop, so the separate filter pass over the 434-pixel line is gone.
  `test/run_scale_line_test.sh` proves it byte-identical to the map loop + filter
  pass on 2400 cases (the Neo Geo's 304→434, 1:1, downscales, 3x, random
  sizes; palette, 565 LE/BE; filter on/off), including the map's habit of
  reading one pixel past the source line on some sizes. The board runs for
  D1+D2 and V1+D1+D2 are queued (`scripts/mamebench/queue/`).
- **2026-10-02, V1 proven and timed** (fork `4d1c24c0`: two fixes from the
  board PC's session — the fix layer's row pitch, and y-zoomed sprites cut at a
  band edge — then IDENTICAL on Metal Slug, Metal Slug 2, Sonic Wings 2 and
  KOF95 over 3000 attract frames; `results/2026-10-02-v1-mslug.txt`, hashes
  identical, 38 samples):

  | Core 0 | V0 | V1 | | Video part | V0 | V1 |
  |---|---|---|---|---|---|---|
  | 68000 | 7.94 | 8.30 | | palette + walk | 1.73 | 2.25 |
  | video | 10.13 | 9.67 | | clear | 1.53 | 0.17 |
  | other | 2.48 | 2.56 | | sprites | 6.05 | 4.90 |
  | mixer | 0.85 | 0.86 | | fix layer | 0.76 | 0.75 |
  | **total** | **23.20** | **22.90** | | band copy | — | 1.36 |

  As expected: the clear and the sprite writes in internal RAM gain 2.5 ms, the
  list walk costs 0.5 ms more than the old palette walk, and the band copy to
  PSRAM (66.5 KB) costs 1.36 ms — the part V2 removes, together with the
  display task's read of the PSRAM bitmap. The 68000 lost 0.36 ms; to be
  watched in the next runs (PSRAM contention from the copy, or noise). The
  strip count (539 vs 369) counts a strip once per band it touches.
  **Next: V2** (board), with D1+D2 measured first by the queued jobs.
- **2026-10-02, V2 written, builds, not yet run** (fork, `NEOBAND=2` builds): each
  finished band goes to the display task (`rg_display_submit_band`), which scales
  and sends it while core 0 draws the next band into the other of two internal-RAM
  buffers; the PSRAM frame bitmap is neither written nor read. The display
  writer now works on a range of viewport lines with the frame state kept
  across bands; at a band edge whose next viewport line repeats the band's last
  row, that row's lines are written with the next band from a kept copy, so the
  vertical filter sees the same neighbours as before. The 8-bit palette table
  is brought up to date before the first band (`mamego_apply_palette8`). The
  MAMEBENCH hash is taken band by band over the same bytes in the same order, so
  the reference hashes still apply. Queued as `030-v2-mslug.sh`.
- **2026-10-02, D1 + D2 timed** (`results/2026-10-02-d12-mslug.txt`, full-frame
  renderer, hashes identical; core-1 averages over the same 37-sample window,
  `mbsum.py` now prints them):

  | Core 1, ms per frame | V0 | V1 + D1 | D1 + D2 |
  |---|---|---|---|
  | display task | 12.18 | 8.58 | 7.95 |
  | YM2610 + Z80 | 8.87 | 6.87 | 6.87 |
  | core 1 busy | 77 % | 62 % | 60 % |

  (The V1 run already carried D1: the board PC's V1 fixes were rebased on top
  of it.) D1 and D2 take 4.2 ms off the display task, and the sound task on the
  same core gains 2 ms from the lower contention. Core 0 is unchanged by them
  (22.79 ms), as expected. V0's single-line "8.42" quoted above was one sample;
  the window average is 12.18. V1 + D1 + D2 (`results/2026-10-02-v1d12-mslug.txt`,
  hashes identical): core 0 22.64 ms, display 8.12 ms, core 1 61 % busy.
- **2026-10-02, phase J started on the PC** (dynarec repo `89b5513`, QEMU in the
  arm64 image): F0's counters measure Xtensa bytes per kind of 68000 instruction
  and the flag share; F1's density forms are in. Fuzz ROMs, bytes per
  instruction, 24-bit forms → density forms: register-only 32.7 → 29.8, memory
  100.7 → 90.0, handler call 46.9 → 42.1, branch 51.5 → 48.4 (about −10 %, not
  the −20-25 % hoped: most of a memory instruction is not loads and stores);
  flag code 8 % (below F5's 15 % rule). 0 mismatches on every QEMU pass. The
  memory instruction at 90 bytes is the target of F2 and F3. Board: a
  `M68KJIT=1` MAMEBENCH run (`results/2026-10-02-jitf1-mslug.txt`, hashes identical):
  68000 13.08 ms with the dynarec (13.9 before F1); Metal Slug bytes per
  instruction reg 28.0, mem 72.3, call 37.5, branch 45.1, flags 9 %; 12 code-cache
  flushes in 70 s. That run had already pulled the F2 glue, so jobs 040 and 050
  measured the same code generation (050: 12.90 ms).
- **2026-10-02, F2 on the PC** (dynarec `glue_musashi31.c`): mame-go's glue
  no longer asks for the flags before every memory call-out
  (`mem_may_interrupt = false`): the 68000's interrupts on Neo Geo and CPS1
  arrive through MAME's timers, between instructions — the only direct
  `cpu_set_irq_line()` calls from handlers go to the Z80 — and Musashi itself is
  unchanged, so the hashes cannot move. NEOPROF builds count any interrupt
  raised inside a memory call-out (must read 0 in the `M68KJIT` report). QEMU
  against Musashi 3.1: 0 mismatches. Board jobs 040 (F1) and 050 (F2) queued.
- **2026-10-02, V2 run, correct but slower, fixed on the PC**
  (`results/2026-10-02-v2-mslug.txt`, hashes identical, screen clean): core 0
  26.25 ms, of which 7.75 ms waiting in the band submit. With D1 + D2 the
  display task has almost no CPU work left and runs at the pace of the LCD bus:
  434 × 320 × 2 bytes at 20 MHz is **13.9 ms a frame when every line changes**,
  the next wall. With a one-message queue and two band buffers, core 0 stalled
  whenever it was ahead. No internal RAM for more buffers (the file system
  needs ~13 KB free), so the display task now copies each band into a PSRAM
  stage on arrival and scales it later, giving waiting bands precedence (fork
  `rg_display.c`): core 0 should drop to its own work, ~18.5 ms. Queued as
  `060-v2s-mslug.sh`. The bus itself is the next question: 25 MHz would make it
  11.1 ms; the plan kept 20 MHz for signal margin.
- **2026-10-02, night: the hand-over, run by run** (all hashes identical, screen
  clean on every webcam check):

  | Job | Change | core 0 | band wait | note |
  |---|---|---|---|---|
  | 060/070 | V2h, 16-line bands, 2 buffers, 1-deep queue | 25.4 | 6.0 | the display lags on the cheap bottom bands, the next frame waits |
  | 080 | + LCD bus at 25 MHz | 25.4 | 5.9 | no change: latency, not bandwidth |
  | 085 | + frame-deep pipeline, 8-line bands, 4 buffers | 28.3 | 0.1 (+9.2 queue) | the 1-deep queue now the wait, 28 bands |
  | 087/055/089 | + 4-deep queue | hang | | the state-load hourglass interleaved its i80 stream with the band stream (`rg_display_sync` saw an empty queue): fixed, sync waits for the band frame |
  | 091 | + sync fix | 24.1 | 3.75 | internal RAM buffers 32 lines of slack, ~2 ms of bus time: not enough for Metal Slug's cheap bands |
  | 093 | + buffer pool: 4 internal, 32 PSRAM reserve, 36-deep queue | **22.42** | 0.15 | 18 KB/frame drawn in PSRAM; the 8-line bands cost ~2 ms of per-band overhead (sprites 5.6, clear 0.6, 68000 8.4) |

  | 095 | pool with 16-line bands: 2 internal + 32 PSRAM | **22.06** | 0.06 | 30 KB/frame drawn in PSRAM (5-6 bands of 14): those bands cost (clear 0.87, sprites 5.14, 68000 8.39 from contention) |

  What is left is the PSRAM spill. Two levers, queued: the LCD bus at 25 MHz
  (now it matters: the display consumes at the bus rate, job 097) and a third
  internal band buffer paid for by the display's DMA buffers (5 → 3, 7.5 KB
  back, job 099).
- **2026-10-02, V2h written and built** (fork `rg_display.c`): the hybrid
  hand-over of the revised plan, queued as `070-v2h-mslug.sh`; the LCD clock
  switch (`LCD_MHZ=25`, B1) built and queued as `080-v2h25-mslug.sh`. Board
  profile of the dynarec (`results/2026-10-02-jitprof-mslug.prof.txt`): the
  sampler sees ~9 % of core 0 in translation (`xjb_finalize`, `xjb_lit`,
  `classify`, `mem_ea`, `lookup`) and ~7 % in the cache synchronisation of
  new code (`cpu_utility_ll_unstall_cpu`, the other core stalled for it) —
  the churn of 12 flushes in 70 s; the generated code itself is not
  symbolised by the sampler (PSRAM). First J step if J goes on: the flush
  policy and the hot threshold.
- Benchmark tools: [`scripts/mamebench/`](https://github.com/pjcau/esp32-emu-turbo/tree/main/scripts/mamebench)
  (`mamebench.sh`, `mbsum.py`, `profsym.sh`; the README has the reference hashes).
- Estimates: phase V 2-3 days, phase D about 1 day, phase J 8-12 days.
