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

### Resume checklist (2026-10-03, agreed with the user: nothing starts before this is read)

The board holds the known-good play build: fork `bbcf99f5`, `NB_LINES=16 NEOBAND=2`
(22 ms a frame on Metal Slug's attract loop). The steps, in order, each gated by
identical hashes and, for drawing changes, by the 4-game PC proof before any board run:

1. **V2i on the board** — **done 2026-10-03** (job 111, fork `c654abbc`,
   `results/2026-10-03-v2i-mslug.txt`): hashes the reference ones, no hang,
   core 0 22.11 ms (68000 7.38, video 10.61, other 2.78, mixer 0.88). Not the
   ~21 expected: the video's `copy` part is back at 1.96 ms (13.6 KB a frame,
   core 0 short of band buffers), and core 1 is busier (YM2610 9.39, display
   12.68). The screen was not checked: the webcam no longer frames the panel.
2. **A level-1 save state saved by hand** with the current build (the old one is
   4280 bytes longer and never loads): MAMEBENCH then measures play, not attract.
3. **Phase O, core 1 takes the SD paging and the mixer** (`neosnd_update`,
   `sdspi` and `mixer` in the core-0 profile): −1.5 ms. **The mixer part is
   written (2026-10-03, fork `cbabb161`), job `113-o1mix-mslug.sh`**: the
   frame's mix (`sound_update_mix()`: the YM2610 stream's copy, the SSG, the
   mixer) is the first part of the sound board's job on core 1; core 0 only
   hands over the frame's commands and, before the samples go out, waits for
   the mix. Gate before the board: `scripts/neogeo_frames.py mix <sysdir>
   <rom> 3000 --input attract` must say IDENTICAL (same picture and same
   samples as with `NEOMIX1=0`, sound playing) on the four games. Expect the
   `mixer` column near 0 and core 0 ~21.2 ms; core 1's `ym2610` column now
   includes the mix (~+0.9). Bench switch on the card:
   `/sd/retro-go/mame/neo_nomix1`. The SD paging part waits for a count of the
   sprite page misses per frame on core 0 (the profile shows ~0.1 ms of
   `sdspi`, not the 0.6 the estimate assumed).
4. **Palette**: pens of unchanged strips kept across frames, `palette_recalc`
   dirty set: −0.8 ms. **Written 2026-10-03, job `117-o2pal-mslug.sh`.**
   Measured first on the PC (`PALSTAT=1`, 3000 attract frames): Metal Slug
   changes nothing on 65 % of the frames and ~25 colours in 3 of the 256
   palettes on the others (Sonic Wings 2: 61 %, ~6 colours in 2 palettes);
   Metal Slug 2 and KOF95 take the 16-bit palette path, not `palette_recalc_8`.
   So: the band path keeps `palette_used_colors` across frames and rebuilds
   only the 16-colour blocks whose pens changed (before: 4096 colours copied
   and marked every frame), and `palette_recalc_8()` skips 8 colours at a time
   where its four loops have nothing to do. Gate:
   `scripts/neogeo_frames.py pal <sysdir> <rom> 3000 --input attract` (the old
   behaviour with `PALFAST=0` against the new with every frame's array checked
   against the full rebuild) must say IDENTICAL on the four games. Expect
   0.4-0.6 ms off the `palette` part, not 0.8: the walk over the sprite list
   (1.3 of the 2.2 ms) stays.
5. **The sprite plotter again**, PC proof first (the 2026-10-02 attempt broke the
   zoomed strips): −1 ms. **Re-applied 2026-10-03, job `119-plotter2-mslug.sh`.**
   The cause of the scrambled picture was one line: the strip's 16 pens were
   copied to the stack from the stack copy itself, not from the colour table,
   so every sprite drew with garbage (first seen on the title letters because
   they are the first sprites of the attract loop, not because of the zoom).
   Gate: `scripts/neogeo_frames.py ref <harness built before the change>
   <sysdir> <rom> 3000` on Metal Slug and Sonic Wings 2, attract and in game
   (the two 8-bit games; the raster games use the untouched 16-bit plotter).
   **Result (job 119): exact, and slower.** Picture and samples IDENTICAL on
   the PC (six runs) and the reference hashes on the board, screen clean, but
   the sprites went from 4.87 to 5.58 ms a frame and core 0 from 21.75 to
   22.10. The plotter is bound by the tile reads from PSRAM; the word tests
   and the 16-pen copy per strip cost more than they save. Reverted (fork
   `01f02b9d`). Do not try this a third time: the lever on the sprites is
   fewer PSRAM reads, not fewer instructions.
6. Reserves, only if short: the LCD bus at 25 MHz on play scenes (not the cause of
   the 103 hang), the dynarec's cache policy. PSRAM at 120 MHz: out, by the user's
   decision (experimental clock).

Expected: 22 → 17-18 ms, 55-58 fps with the interpreter; the last 1-2 ms are the
uncertain part.

Two more items for tomorrow, asked by the user on 2026-10-03 (launcher, not
performance):

7. **CPS1 in its own launcher section**, separate from the 8-bit "arcade" games,
   as the Neo Geo already has (`/sd/roms/neogeo/`): its own folder, tab and icon
   (Final Fight, SF2, Carrier Air Wing, Knights of the Round, Ghouls'n Ghosts, ...).
8. **The artwork for all of them**: launcher covers and previews (the `romart`
   images and the per-game `.png` previews) for every Neo Geo and CPS1 set on the
   card, fetched and named the way the launcher expects, so no game shows without
   a picture.

**State at the end of the 2026-10-03 session.** Best build: fork `01f02b9d`
(V2i + sound mix on core 1 + palette), `NB_LINES=16 LCD_BUFS=3
BAND_INTERNAL=3 NEOBAND=2`: core 0 21.75 ms on the common 31-sample window
(22.11 at the start of the day). Steps 1, 3 (mixer part), 4 and 5 are closed;
step 2 (the hand-saved level-1 state) waits for the user at the board; the SD
paging part of step 3 was not started (the profile shows ~0.1 ms of it on
core 0); steps 7 and 8 (launcher) are open.

**The real game, measured 2026-10-03 (play build `01f02b9d`, the user's own
save at the end of mission 1, 64 s driven from the console, `rg_system`'s
counters once a second):**

| Scene | Game speed | Frames drawn | Frames skipped | Busy |
|---|---|---|---|---|
| attract (before the load) | 60-61 fps | 20 /s | 40 /s | 100 % |
| in play | **50.3 fps average (84 %)**, 41-55 | **16.8 /s** | 33.5 /s | 99 % |

The auto frameskip sits at its limit (two frames skipped for one drawn) and in
play the game still runs below full speed, so the sound underruns: that is the
crackle the user hears, and it predates today's changes. **Every MAMEBENCH
number in this page is the attract loop**, where a drawn frame costs ~22 ms; in
play a drawn frame costs about 30 ms. Two things were wrong with the benchmark
and are fixed: (1) no state saved in play ever loaded at boot (the Neo Geo
state includes the core-1 sound board from the third frame; the resume loaded
after one; fork `54120339` loads after six); (2) a state only loads in the
firmware that wrote it (the header's fingerprint is a function address), so a
bench build can never load a play build's save. `MAMEBENCH=2` therefore inserts
a coin and presses START before the input script and measures mission 1 from a
cold boot (job `125-play-mslug.sh`, `neoframes --input play` on the PC). From
here on the target is measured in play, not in attract.

**The play benchmark (job 125, `MAMEBENCH=2`, fork `be5e7fd5`, cold boot,
`results/2026-10-03-play-mslug.txt`).** The script takes the coin, starts and
plays mission 1 from frame 1200 until the player dies at the helicopter
(~3450); `compare --input play` is IDENTICAL on the PC. Averages per frame:

| Window | core 0 | 68000 | video | other | sound wait (`mixer`) | core 1 sound job (wall) | core 1 display | core 1 busy |
|---|---|---|---|---|---|---|---|---|
| boot + attract (samples 2-14) | 19.0 | 4.7 | 6.8 | 5.7 | 1.8 | 11.1 | 7.4 | 64 % |
| **mission 1 (samples 20-48)** | **29.1** | 10.8 | 10.4 | 1.1 | **6.7** | **25.7** | **15.9** | **90 %** |

In play the frame is set by **core 1**: the display task takes 15.9 ms of CPU
(not the bus: DMA wait 0.22 ms, 40 buffers sent a frame, the picture scrolls
so D1 skips little) and the sound board about 10 ms, 26 ms of work for one
core; core 0, whose own work is 22.4 ms, waits 6.7 ms a frame for the sound
job. Neither core fits 16.7 ms. The levers in play, in order of size: the
display task's scaling and filtering (15.9 ms), the YM2610's cost (sample
rate), then core 0's 68000 and sprites. The sound mix moved to core 1 today
(O1) was a gain in the attract loop and is probably a loss here: job 127
measures it with the `neo_nomix1` switch.

**The sound, measured the same day** (the user's idea: the webcam's microphone
next to the firmware's own capture, `acap`/`adump`, same play scene):

| | Firmware capture (as submitted to the driver) | Microphone |
|---|---|---|
| game silent (volume 0) | | floor −62.3 dBFS, 0 clicks/s, mains hum at 100, 250, 50, 300 Hz |
| in play | no run of zeros, no repeated 1/60 s block (0 of 179), no jump tied to the frame boundaries | −42.9 dBFS, **1.81 clicks/s** |

The samples leave the mixer clean and the clicks exist only at the speaker in
play: the crackle is delivery timing, the game at 50 of 60 fps feeding the PDM
driver 17 % too slowly (8 DMA descriptors, no underrun counter in
`drivers/audio/pdm.c`). The background noise is another thing: a steady
50/100 Hz hum present with the volume at 0, analog, consistent with USB power
and no battery. The crackle goes when the game holds full speed.

Found on the way (2026-10-03): **core 1 is the limit, not core 0's own work.**
The display task takes 12.6-14.9 ms of core 1 a frame and the sound board
9.6-11 ms of wall time under it; whenever the display starts late core 0 has
no free band buffer and copies (1.8-2.1 ms a frame, 4.3 with the sound task
above the display). The next measurement after the plotter is where the
display task's time goes with two thirds of the blocks skipped.

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

  | 097 | + LCD bus at 25 MHz | 22.15 | 0.06 | no change again (29.7 KB spilled): the clock either does not reach the bus or the bus is not the limit; jobs 101/103 measure the DMA wait at 20 and 25 MHz |
  | 099 | + 3 internal band buffers (display DMA buffers 5 → 3) | 22.08 | 0.05 | spill halved (16.4 KB) but no net gain: the display task was copying almost every internal band to the PSRAM stage (its "give waiting bands precedence" policy with a deep queue) — V1's traffic on core 1: 68000 8.6, YM2610 11.4 |
  | 101 | the bus measured at 20 MHz | 22.15 | 0.05 | DMA wait 0.23 ms, 29 buffers sent a frame: D1 skips two thirds of the blocks in the attract scene, the bus is nowhere near its limit |
  | 103 | the same at 25 MHz, on the first V2i build | hang | | frozen on the state-load hourglass: not the clock — a V2i bug (the first band of a run filed under a frame that never began, so the sync spun forever), fixed in the fork; 25 MHz stays an open option for play scenes |
  | 105 | V2i: accepted bands scaled in place, the stage only when the emulator is short of buffers | hang | | the same bug; the fixed build runs as job 109 (with the plotter) |
  | 107 (held) | PSRAM at 120 MHz | | | waits for the user's go: an experimental clock |
  | 109 | faster sprite plotter (opaque/empty words, pens on the stack) + V2i | **wrong** | | hashes not the reference ones, scrambled picture on the board; the PC proof found it at frame 133 of Metal Slug (the zoomed title letters). Reverted. Rule restated: a drawing change reaches the board only after the PC proof says IDENTICAL — the queue pulls HEAD, so the proof comes first |
  | 111 (2026-10-03) | V2i with the first-frame fix, original plotter | 22.11 | copy 1.96 | hashes identical, no hang; 68000 7.38 as hoped, but core 0 waits for or copies bands again (13.6 KB/frame) and core 1 is at 64 % (YM2610 9.39, display 12.68): no net gain over job 095 |
  | 113 (2026-10-03) | + the sound mix on core 1 (O1, fork `cbabb161`) | 21.87 (111: 22.02, same 31 samples) | copy 2.10 | PC gate IDENTICAL on the four games (picture and samples); hashes identical. The mix left core 0 (0.02 ms in calm samples, with the stream copy 1.0 before) but core 0 now waits 0.4-0.9 ms for the sound job at the frame end: the job is 0.9 ms longer and the display task (priority 6) runs before it (priority 5) on core 1. Steady samples 10-33: 23.40 → 23.04. `mbsum.py`'s 22.95 is over 40 samples, 111's 22.11 over 33: not comparable |
  | 115 (2026-10-03) | + the sound task above the display (`NEOSND_PRIO=7`) | 22.84 (same 31 samples) | copy 4.27 | the wait is gone (mixer 0.03) but the display starts later and the band copies more than double (14.8 → 33.5 KB a frame): +0.9 ms. Dropped; the task stays at priority 5 |
  | 117 (2026-10-03) | O2, the palette (fork `1c1b1faf`, default priority) | 21.75 (same 31 samples; 113: 21.95) | copy 1.82 | PC gate: `pal` IDENTICAL with the per-frame check on Metal Slug (attract and in game) and Sonic Wings 2; Metal Slug 2 and KOF95 are 16-bit raster games and reach neither changed function (picture identical); `compare` and `mix` IDENTICAL. Board: hashes identical, palette 2.24 → 1.86 ms, the rest unchanged. Screen clean on 8 webcam shots (the webcam frames the whole panel again) |

  Also found: **the MAMEBENCH scene is the attract loop, not level 1** — the
  slot-0 state (519976 bytes) is 4280 bytes longer than what the current build
  serialises (515696), so `rg_emu_load_state` fails on every run ("file larger
  than the state"); the reference hashes are attract hashes. A new level-1 state
  must be saved by hand with a current build (the play scene has more sprites).

### What the research says (2026-10-02, night)

- **PSRAM at 120 MHz.** ESP-IDF allows octal PSRAM at 120 MHz DDR with the
  N16R8's quad flash at 120 MHz SDR (`CONFIG_IDF_EXPERIMENTAL_FEATURES`,
  `CONFIG_SPIRAM_SPEED_120M`, `CONFIG_ESPTOOLPY_FLASHFREQ_120M`), +50 % PSRAM
  bandwidth — the resource every part of this plan is bound by. Experimental:
  after a ~20 °C drift from power-on, accesses may crash unless the timing point
  is retuned from the temperature sensor
  (`CONFIG_SPIRAM_TIMING_TUNING_POINT_VIA_TEMPERATURE_SENSOR`); some modules
  fail to boot at 120 MHz. Prepared as `targets/esp32-emu-turbo/sdkconfig.psram120`
  (`RG_SDKCONFIG_EXTRA=sdkconfig.psram120`): a measurement, not a shipping config.
- **PSRAM bandwidth, measured by others** (esp32-s3-memorycopy): PSRAM → internal
  ~312 MB/s sequential, internal → PSRAM ~82 MB/s, PSRAM → PSRAM ~35 MB/s. Writes
  are the expensive side, three to four times the reads: every change that moves
  writes out of PSRAM (bands) pays, every PSRAM copy on core 1 costs both cores.
- **The i80 bus.** Espressif: 8-bit i8080 "recommended below 80 MHz", panel
  limit (ST7796S write cycle 30 ns) ~33 MHz; the IDF derives the real pixel
  clock from a PLL with an integer divider, so 25 MHz may land on another value.
  Measured by jobs 101/103 before anything else is decided about it.
- **esp-box-emu / other handhelds**: the same recipe we have (strips to the
  display from internal RAM, the second core for sound and present, no full
  frame in PSRAM); nothing beyond it.

### The path to 60 fps (core 0, with the interpreter)

| | now (095) | target | lever |
|---|---|---|---|
| 68000 | 8.4 | 7.0 | V2i (no PSRAM traffic on core 1), then PSRAM 120 MHz |
| sprites | 5.1 | 3.5 | the writes are internal now: retry the faster plotter dropped when PSRAM-bound (opaque-word fast path, skip empty words) |
| palette + walk | 2.3 | 1.5 | pens of the unchanged strips kept across frames; `palette_recalc` dirty set |
| clear + fix + rest | 1.7 | 1.2 | V2i, 16-line bands |
| other + mixer | 3.6 | 2.0 | SD paging (sprite pages, samples: `sdspi`, `neosnd_update` in the core-0 profile) and the mixer to core 1 |
| **total** | **21.1** | **15.2** | **60 fps with margin, no dynarec** |
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
