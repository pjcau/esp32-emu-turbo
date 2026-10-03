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

## Where we stand (close of 2026-10-03)

**60 frames a second is not reached on any 68000 arcade game.** What is
measured on the board, playing the game, every frame drawn (the play benchmark,
`MAMEBENCH=2`; "before" is the code of the morning of 2026-10-03):

| Game | Frames a second | core 0, ms a frame | 68000, ms | Limit now |
|---|---|---|---|---|
| Metal Slug (Neo Geo) | 34 → **44** | 29.2 → 22.6 | 10.8 → 7.0 | video 10.4 ms on core 0, the sound job on core 1 |
| Metal Slug 2 (Neo Geo, raster) | 27 → 29 | 36.2 → 33.5 | 12.9 → 12.8 | video 16 ms (16-bit raster path), 68000 |
| Final Fight (CPS1) | 28 → 30.5 | 31.2 → 28.0 | 7.4 → 2.7 | video 17 ms plus 5 ms of output, all on core 0; core 1 at 42 % |
| Street Fighter II CE (CPS1) | 27 → 31 | 32.7 → 27.8 | 8.3 → 3.6 | video 19 ms; core 1 at 29 % |

:::caution The two CPS1 rows are not play
Found on 2026-10-04: the CPS1 does not take the play script's 6-frame coin and
START. Final Fight stayed in its intro story and Street Fighter II on its title
screen with one credit, in the "before" run and in the "after" run alike. The
rows compare like with like, but on screens where the game mostly waits, which
is where the idle-turn skip gains most. The play figures need `MAMEBENCH=4`
(30-frame presses, given twice) and are being measured.
:::

With the automatic frameskip the games run at or near full speed and show
about a third of the frames; a fixed one-in-two frameskip at full speed needs a
drawn frame plus a skipped one in 33.3 ms, and Metal Slug takes 39.8.

**Kept from 2026-10-03** (each proven on the PC frame by frame, then measured
on the board):

| Change | Scope | Gain |
|---|---|---|
| Palette scaler without a test per pixel, vertical blend two pixels a word, blend colour fix | every emulator drawing through a palette at 1x-2x | Metal Slug −4.0 ms a frame |
| Exact skip of wait loops that count (`cl_verify`) | Neo Geo; fires on Metal Slug only among 16 sets | 68000 −4.7 ms, frame −1.0 |
| Exact skip of idle turns longer than one loop (`turn_check`) | CPS1, all six sets | 68000 −4.7 ms (49-82 % of its cycles) |
| Sound chips at 16 kHz, doubled to the 32 kHz output with a 12-tap interpolation | mame-go | frame −1.5 ms; not detectable through the speaker |
| Card pages read through a DMA-capable buffer (multi-sector) | Neo Geo sprite and sample pagers | 17 → 7 ms and 12 → 5 ms a read |
| Sound mix on core 1, palette kept across frames | Neo Geo | about −0.5 ms together |
| Resume at boot loads the state where saves are made; CPS1 states 94 KB smaller | Neo Geo, CPS1 | resume works; CPS1 saves fit in memory |
| Launcher: a CPS-1 tab, covers for every game of every system | launcher | |

**Measured and dropped** (do not retry without a new reason): the sound task
above the display; a sprite plotter with fewer instructions; the program's
first megabyte in PSRAM; two fewer loads in the 68000's run loop; the LCD bus
at 25 MHz (really 26.7, outside the ILI9488's 40 ns write cycle); the SD chip
select held; larger sprite and sample caches (the reads are first touches);
FAME/C; the 68000 dynarec (see [68000 dynarec](../software/m68k-dynarec.md)).

**What is left, in the order of what it could give:**

1. **CPS1: the video.** 17 to 19 ms of rendering and about 5 ms of output on
   core 0 while core 1 is 30 to 40 % busy. The CPS1 does not use the band
   path the Neo Geo has. Largest single gain available, and the largest job.
2. **The Neo Geo raster games** (Metal Slug 2, KOF '95): their 16-bit video
   path costs 16 ms and takes neither the bands nor the palette work.
3. **Internal RAM.** The play build has 5 KB free, 1 KB at times: the
   multi-sector card read then falls back to the slow path, and anything new
   has nowhere to go. A lead: the file system's buffers are 4 KB per open file
   (`CONFIG_FATFS_SECTOR_4096`), a card needs 512 bytes. Board-wide, to be
   measured with care.
4. **A fixed one-in-two frameskip** once a pair of frames fits 33.3 ms: even
   motion at 30 frames instead of an uneven third. Metal Slug is 6.5 ms short
   a pair; the 68000's clock at −20 % (measured: −1.2 ms a frame, nothing
   visible in stills) is an option for the user to judge by playing.
5. **Metal Slug's remaining frame**: sprites 4.9 ms and the sprite list walk
   2.3 ms on core 0, the sound job on core 1 (FM synthesis 4 ms).
6. **Open defects found on the way:** `robby.zip` resumes to a black screen
   for 20 s; a CPS1 state is not an exact continuation (a character of text or
   a pixel off); one unexplained loss of sound in one of three takes of the
   16 kHz bench build, not reproduced in four minutes on the play build.

### The build left on the board (evening of 2026-10-03)

Every app and the launcher from fork `0423ff54`; `mame-go` built with
`NB_LINES=16 LCD_BUFS=3 BAND_INTERNAL=3 NEOBAND=2 AUDIO_MIX_HZ=16000`, LCD bus
at 20 MHz. The full record is `scripts/mamebench/results/2026-10-03-final-checks.md`.

The figures below are the game's own speed with the automatic frameskip on
(the play build), filmed and driven from the console; they are not the
benchmark's "every frame drawn" figures of the table above.

| Check | Result |
|---|---|
| Metal Slug in play | 57.9 game frames/s, 19.3 drawn/s (was 50.3 and 16.8) |
| Final Fight, moving intro | 59.2 / 21.7 drawn with the turn skip; 51.7 / 17.2 without (`cps1_noturn`) |
| CPS1 save, resume, load | pass on Carrier Air Wing, Final Fight, Ghouls'n Ghosts, Knights of the Round (314 KB states); **fail on SF2 CE and SF2 HF**: 77 KB of PSRAM left in play, the state cannot be allocated |
| Sound through the microphone | same level and click rate as the afternoon's 32 kHz and 16 kHz builds, no dropout in 2 x 85 s |
| Lowest internal heap | Metal Slug 0 to 5 KB, Final Fight 18 KB |
| Other emulators (NES, SNES, Mega Drive, GBA, PC Engine, Doom) | boot, picture, sound and buttons right after the generalised scaler; no before/after timing was taken |

Two things were added for the user the same evening:

- **A loading percentage under the hourglass**, in every emulator.
  `rg_storage_read_file()`, `rg_storage_unzip_file()` and the new
  `rg_storage_fread()` report their progress to `rg_gui_draw_loading()` from
  `rg_system_init()` to the first `rg_system_tick()`; files under 256 KB and
  the launcher draw nothing. `mame-go` counts the ROM bytes of the set in
  `src/common.c` (`mamego_load_add()`). Filmed: smooth on SNES, PC Engine and
  CPS1; Metal Slug shows nothing for 1.5 s (the program ROM is inflated in one
  go) and stands at 90 % for 3 s (copy to flash and machine start, not
  counted). **No figure yet on GBA and Doom** (their own loaders), nor on
  Duke Nukem 3D, Wolfenstein 3D, Quake and OpenTyrian.
- **`board_install.sh` refuses a bench build.** The user was handed a board on
  which no button worked in the arcade games, across several launches. The
  firmware on it was a one-off measurement build (`NEOPROF`, no `MAMEBENCH`).
  The first explanation, bench flags left in the build directory, was
  **disproven**: the same two builds repeated in a row give a binary without
  the bench code. The sources show no difference on any input path either, so
  the cause is not known yet; the play build installed right after works. The
  guard stays as cheap insurance (a play build must not contain the bench-only
  string `MAMEBENCH frames`), and the rule is to hand the board over only on a
  build installed by that script and checked with a key press.

Added to the open defects: the SF2 saves above; Mega Drive sound was not
confirmed by the microphone (quiet title screen). Final Fight, Street Fighter II
and Ghouls'n Ghosts do not take the play script's coin and START: explained on
2026-10-04 (the CPS1 needs presses of about 30 frames, and Ghouls'n Ghosts is
still in its RAM test at frame 600), fixed by the `MAMEBENCH=4` script. Whether
a quick tap by hand can be missed the same way is being measured.

How to work on it: `scripts/mamebench/README.md` (the run options, the switch
files, the PC gates). The rule that paid every time: measure in play before
changing anything, prove the change frame by frame on the PC, then measure on
the board on the same samples.

The sections below are the record: the numbers of 2026-10-02 (attract loop,
which flattered every figure), the plan as it was, and the log of 2026-10-03.

## Where we were on 2026-10-02 (attract-loop figures)

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

### Log of 2026-10-03: the morning's checklist and what each step gave

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
   **Both written 2026-10-03** (fork `02bfd752`): the launcher has a "Capcom
   CPS-1" tab on `/sd/roms/cps1/` with its own background, banner and logo;
   `scripts/arcade_art.py sets cps1` lists the CPS1 set names from mame-go's
   driver sources (which zips to move out of `/sd/roms/arcade/`), and
   `scripts/arcade_art.py fetch <outdir> <tab> <set>...` writes each game's
   title screen, scaled to the launcher's preview box, as
   `romart/<tab>/<set>.png` (ArcadeDB by set name; a clone falls back to its
   parent). The images are not kept in the repository. To do on the board PC:
   launcher build and install, the zips moved, the art fetched and copied to
   the card.

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

A/B runs on the same play benchmark, same window (hashes identical in all):

| Run | core 0 | of it, sound wait | core 1 display | core 1 sound job (wall) | verdict |
|---|---|---|---|---|---|
| 125, reference | 29.08 | 6.73 | 15.92 | 25.72 | |
| 127, mix back on core 0 (`neo_nomix1`) | 28.83 | 7.02 | 15.99 | 24.35 | no difference: core 1 paces the frame either way; the mix stays on core 1 |
| display filter off (`DispFilter 0`, the user has 3 = both) | **27.16** | 4.85 | **13.99** | 23.63 | the filter costs 1.9 ms of core 1, and core 0 waits 1.9 ms less; sharper pixels |
| scaling off | not run | | | | mame-go forces `RG_DISPLAY_SCALING_FIT` for `/neogeo/` at every boot (`mame_task`), the setting is overridden: needs a build switch |

Without the filter the display task still takes 14 ms to scale 304x224 to
434x320: about 24 CPU cycles per output pixel, with the bus idle (DMA wait
0.19 ms). That is the next thing to open up.

**The objective, set by the user on 2026-10-03: halve the 68000's time and the
display's time, measured in play.** From the job-125 window that is the 68000
from 10.8 to about 5.4 ms and the display task from 15.9 to about 8 ms. Core 0
would then be 5.4 + video 10.4 + other 1.1 = 16.9 ms and core 1 about 8 +
sound 10 = 18 ms: at the edge of 16.7 on both, so the sound job and the video
each have to give another millisecond or two. First step: sampling profiles of
both cores in the play window (jobs 129 and 131, `MAMEPROF` with `MAMEBENCH=2`
samples frames 1300-2800), then the display task's inner loops.

**Display, step 1 (2026-10-03, fork `a6fd8bf5`, job `133-play-scaler-mslug.sh`).**
The palette scaler's loop compiled to about 35 instructions per source pixel
(two nested loops, five or six branches, the palette pointer reloaded every
pixel); `rg_display.c` is already built `-O2`, so it is the loop's shape, not
the compiler. For upscales between 1x and 2x (the Neo Geo's 304 → 434, the
CPS1's 384 → 480) `rg_scale_line_pal12` stores each pixel twice and moves the
pointer by its repeat count, unrolled by four, no test per pixel; the vertical
filter blends two pixels per 32-bit word (`rg_blend_line`). Proven on the PC
by `components/retro-go/test/run_scale_line_test.sh` (same output as the map
loop, nothing written past the line; mutation-checked). Also fixed there:
`rg_blend_pixels` left the pixels' high byte in bits 16-23 after its swaps and
OR-ed it back, so every blended pixel had its low green bits and blue up to
one step too bright. Open question the profiles answer: how much of the
display task's 14-16 ms is CPU and how much is the LCD bus (434 x 320 x 2
bytes at 20 MHz is 13.9 ms when every line changes).

**Display step 1, measured (job 133, same play window, hashes identical,
screen clean on 8 shots with the webcam's focus locked):**

| | core 0 | sound wait | core 1 display | core 1 sound job (wall) | DMA wait |
|---|---|---|---|---|---|
| 125, before | 29.08 | 6.73 | 15.92 | 25.72 | 0.22 |
| 133, new scaler | **25.12** | 2.70 | 12.55 | 21.60 | 1.45 |

Four milliseconds a frame. The display task now waits for DMA buffers: the
scaler outruns the LCD bus, so the rest of its 12.5 ms is the bus, not CPU
(the core-1 profile gives the display about 18 % of the samples, ~4.5 ms:
`rg_scale_line_pal12` 6.1, `rg_blend_line` + `rg_blend_pixels` 5.9,
`source_row` 1.9, `write_lines` 1.0). Job 135 runs the bus at 25 MHz in play.

**The play profiles (jobs 129 and 131, fork `a6fd8bf5`, frames 1300-2800):**

- **Core 1**: the sound board is about 47 % of the samples (~12 ms a frame):
  `FM_CALC_CH` 16.7, the Z80 about 11 (`z80snd_execute` 5.6, `neosnd_z80_rm`
  3.1, `ROP` 2.9, `RM16` 1.3), ADPCM A and B 6.5, `YM2610UpdateOne_` 3.1, the
  SSG 2.1, the mixer 1.1. The display about 18 %. Timers, IPC and the idle
  hook about 17 % (mostly idle time being measured).
- **Core 0**: `cpu_utility_ll_unstall_cpu` 21.7 (stalled or waiting),
  **`m68ki_read_imm_16` 15.0**, `NeoMVSDrawGfx` 9.1, `neoband_walk` 3.6,
  `neoband_draw` 2.5. The opcode fetch is one array read
  (`READ_WORD_A(&OP_RAM[address])`, prefetch emulation is off): 15 % there is
  time waiting for memory, the 68000 program being read through the data cache
  (64 KB, already the largest setting, shared with everything in PSRAM). That
  is where "half the 68000" has to come from: the program's hot pages in
  faster or closer memory, not fewer instructions.

After step 1 core 0's own work (22.4 ms: 68000 10.9, video 10.4, other 1.1)
is the larger part of the 25.1 ms frame; the sound job is next.

**The LCD bus at 25 MHz in play (job 135, `LCD_MHZ=25`, same window):**
core 0 25.12 → 24.67, display 12.55 → 11.27, DMA wait 1.45 → 0.36, hashes
identical, screen clean on 8 shots (no sparkle, no shifted rows). Unlike
yesterday's attract runs the bus now shows, because the scaler no longer hides
it. The clock the driver really sets is not logged: with an integer divider of
80 MHz it would be 26.7 MHz, 37.5 ns a write. **Correction (same day): the panel's
controller is an ILI9488, not an ST7796S** (the driver file is named after the
compatible command set), and its datasheet, kept in
`hardware/datasheets/DS1_ILI9488-controller_ILITEK.pdf` (DBI type B timing
table, page 329), gives a minimum write cycle of **40 ns** with 15 ns minimum
for each half. So 20 MHz (50 ns) is inside the datasheet and `LCD_MHZ=25`,
which esp_lcd rounds to 80 MHz / 3 = 26.7 MHz, is 2.5 ns under the minimum:
it works on this unit at room temperature and is outside the specification.
The "30 ns, about 33 MHz" figure quoted earlier in this page was for another
controller. It went into the play build of 2026-10-03 on the wrong figure; the
user decides whether it stays.

**The 68000's program in PSRAM (fork `355aaeeb`, job `137-play-program-mslug.sh`).**
Metal Slug's whole 2 MB program is served from the flash partition through
the data cache, and about 850 KB of PSRAM are free in play. With the file
`/sd/retro-go/mame/neo_program` on the card the first MB stays in PSRAM (the
split the 5 MB programs already use, `mamego_prog_hi`) and the sprite page
cache gives up the room (1152 → about 832 KB). The reason to expect a gain is
the bus, not a measurement: a cache line of 64 bytes takes about 32 clocks
from the octal PSRAM and about 128 from the quad flash. Compare with job 135.

**Result of the program in PSRAM (job 139; job 137 was not a valid run, the
first cache sizing left the display surfaces without memory):** 68000 10.88 →
10.62 ms, sprites 4.94 → 5.75 (the sprite page cache at 448 KB instead of
1152 misses more), display +0.6: core 0 24.67 → 25.06, a loss. Dropped; the
switch stays in the code, off. What it says about the opcode-fetch wait: it is
not the flash's line-fill time against PSRAM's, since moving the hot megabyte
to the faster memory gave 0.26 ms. The wait is the cache being too small for
what both cores keep reading, wherever the lines come from.

**Next 68000 measurement: the main CPU's clock (job 141, fork `6d54a7e7`).**
mame2000 already has the option (`underclock_cpu`, a percentage), unused. The
file `/sd/retro-go/mame/neo_uclock` with `20` in it runs the 68000 for 20 %
fewer cycles a frame. The hashes change by construction (the game's timing
moves); the screen and the play window tell what it costs and what it gives.
A user-visible trade, to be decided by the user from the numbers.

**Decisions of the evening (2026-10-03, the user's):** the LCD bus goes back
to 20 MHz for good (0.45 ms does not pay for running the ILI9488 outside its
datasheet; the baseline for every later comparison is job 133, 25.12 ms). The
next lever is the sound board's cost through the output rate: the chips render
at the rate the core is given. **The speaker's rate stays 32000 Hz**, the
project's rule since 2026-09-26 (at other output rates the PDM driver's
clocks misbehave: the volume ignored at 22050, crackle in other apps), so the
measurement is `AUDIO_MIX_HZ=16000`: the chips render at 16 kHz and the
samples are doubled, with the midpoint interpolated, on the way out, as DOOM,
Duke Nukem 3D and the Neo Geo Pocket already do (job 149; the two jobs that
changed the output rate were withdrawn before they ran). The near target is a fixed one-in-two frameskip at full game
speed (30 even frames a second): a drawn frame plus a skipped one must fit
33.3 ms, and today they take about 37.

On the 68000's opcode fetch: `m68ki_read_imm_16` is already inlined everywhere
(no out-of-line copy in the object file); the profiler names it because
addr2line reports the innermost inlined function. The 15 % is therefore time
at the fetch's own instructions inside `m68k_execute` and the handlers, next
to the two table lookups every instruction makes (the 256 KB handler table and
the 64 KB cycle table, indexed by opcode). Which of those loads stalls is the
next thing to measure, at the level of addresses, before changing anything.

**Measured that evening, play window, 20 MHz (baseline job 133: 25.12 ms):**

| Run | core 0 | 68000 | sound wait | core 1 busy | note |
|---|---|---|---|---|---|
| 133, baseline | 25.12 | 10.89 | 2.70 | 87 % | |
| 143, 68000 clock −20 % (at 25 MHz, against 135's 24.67) | 23.75 | 9.64 | 2.95 | | −11 % of 68000 time, not −20: the idle skip already removed part of those cycles. New hashes (the game's timing moves). The scripted play gets exactly as far; nothing slow or flickering in 10 stills |
| 149, chips at 16 kHz, doubled to 32 kHz out | **23.77** | 10.30 | 1.68 | 83 % | hashes identical; the 68000 gains 0.6 ms from a quieter core 1 |

The 16 kHz mix keeps the speaker at 32000 Hz (`rg_audio_init ... samplerate=32000`,
`audio 16000 Hz` for the core). Its level is the same as at 32 kHz: on the PC,
same scene, the rms of every 300-frame window differs by 1 to 6 %
(`neoframes --rate`, `LEVEL` lines). A microphone comparison on the board
showed 12 dB less, but the two recordings were not the same moment of the
sound (the builds boot at different speeds); not confirmed, to be closed with a
capture at the same frame or by ear. Job 151 runs both together: the near
target, a drawn frame plus a skipped one inside 33.3 ms.

**Both levers together (job 151, chips at 16 kHz and the 68000's clock −20 %):**
core 0 **22.72 ms** (68000 9.02, video 10.32, other 1.23, sound wait 2.15),
core 1 87 % busy; hashes equal job 143's. One of six webcam shots showed a
dark rectangle beside an explosion in the helicopter scene, not seen in the
earlier runs of that scene: open, see below.

**The 68000's run loop, at the level of addresses (job 131's samples against
the disassembly of `m68k_execute`).** 14.5 % of core 0 falls in one 64-byte
window that holds the loop's dozen instructions: five loads before the handler
(PC, address mask, the `OP_RAM` pointer, the opcode word, the handler's
address) and four after it (the cycle table's pointer, the opcode again, the
cycles left, the cycle count). The two opcode-indexed tables are in PSRAM
(`m68ki_instruction_jump_table` 256 KB, `m68ki_cycles` 192 KB), and so is the
`OP_RAM` pointer. Fifteen host cycles per 68000 instruction for a dozen
instructions is their plain cost, not a stall: the opcode fetch is not waiting
for memory, which is also what job 139 said. The 68000's cost is structural,
about a third dispatch and the rest the handlers; halving it with this
interpreter is not realistic, 8 ms is. First trim (fork `7a2f7312`, job 153):
the opcode and the cycle table's address stay in registers across the handler
instead of being reloaded. Next candidates: the idle-loop analysis
(`IDLESTAT`) on the play scene, and direct reads of work RAM and ROM instead
of MAME's handler tables.

**The dark rectangle of job 151: the emulator's own picture, not today's
changes.** On the PC with the same timing (`NEOUCLOCK=20`, `--input play`):
the `pal` gate over 3600 frames, every frame compared, is IDENTICAL with the
per-frame array check, so the palette change is not it; and of the frames
dumped through the helicopter scene only frame 2880 has it: the explosion's
flash, a white disc in frames 2440, 3240, 3360 and 3400, is drawn solid black
there, byte for byte the same in the full-frame build, the band build, the
harness from before the palette work and with `PALFAST=0`. Not today's work,
then. The first guess, MAME 0.37b5's 8-bit palette out of its 256 pens, was
measured and is wrong: over the whole run no frame asks for more colours than
there are pens (`PALSHORT total: 0 frames short of pens`). What is left: the
game's own picture (a flash that alternates white and black frames is a common
arcade effect) or an emulation fault in the sprite's palette. The frames
around 2880, dumped one by one, say which: a regular alternation is the game.
**Result: the game's own effect.** Frames 2880-2881 black, 2882-2883 white
(the game updates every second frame), then a smaller dark-then-bright pair at
2896-2899: a black-then-white flash at each explosion. Closed, nothing to fix.
Lesson for the benchmark: MAMEBENCH hashes one frame in 300, the PC gates
compare every frame.

**Job 153, the run-loop trim: no measurable gain** (68000 10.83 against 10.89
ms, core 0 25.08 against 25.12, hashes identical; the PC gate was IDENTICAL on
five games). Reverted (fork `b485c1fd`): two loads fewer in a dozen
instructions are inside the noise.

The board scripts now take a lock (`/tmp/esp32-emu-turbo-board.lock`): twice on
2026-10-03 two job loops ran at once on the board PC and spoiled both runs.

**Job 155, one frame in two drawn (16 kHz mix, 68000 clock −20 %), play
window:** core 0 averages 19.20 ms a frame, so a drawn frame plus a skipped one
take **38.4 ms against the 33.3 needed** for full game speed at 30 drawn
frames. Per frame: 68000 9.12, video 6.65, other 1.32, sound wait 2.09; core 1
92 % busy, and it sends a whole screen for every drawn frame (81 buffers: after
a skipped frame every line has changed). Skipping does not halve the video:
its average only falls from 10.3 to 6.65 ms, so the drawn frames cost about
13 ms each here against 10.3 when every frame is drawn. Five milliseconds a
pair are still missing; they are in the 68000 (18 ms a pair), the sound wait
(4 ms a pair) and the dearer drawn frames.

`MAMEBENCH=3` draws every other frame (job 155): what a fixed one-in-two
frameskip costs per pair of frames.

**The 68000's time in play is mostly a wait loop (PC analysis, `IDLESTAT` and
`PCHIST`, Metal Slug, 3600 frames of play).** The idle skip removes 12.5 % of
the cycles asked; of the 87.5 % executed, **55.7 % are sixteen bytes of code at
`0x1FE0-0x200F`**, the game's wait for the vertical blank:

    001fe2 addq.w #1,$106ee0     a counter of the loop's own turns
    001fe8 clr.b  $106edd
    001fee cmpi.b #0,$106ede ; beq.w $2004
    001ffa cmpi.b #1,$106ed9 ; bls.b $1fe2
    002004 tst.b  $106ed8    ; beq.b $1fe2      the flag the vblank interrupt sets

about 970 turns a frame. The skip calls it busy because the counter makes the
loop's writes differ every turn ("busy writes 3484676, regs changed 0").
Sonic Wings 2 has no such single loop (its top loop changes registers).

**Fork `57790088`: such loops are skipped exactly.** The loop is proven first
(its code decodes to one ADDQ/SUBQ on an absolute address, CLR, TST, CMPI,
BTST on absolute addresses and forward branches; nothing else touches the
counter; nothing in the I/O window; registers unchanged; two consecutive turns
of equal cost that each moved the counter one step), then N turns become N
times the turn's cycles and N steps of the counter. Gate:
`scripts/neogeo_frames.py count` (the skip off against on: same picture, same
samples, and the cycles each run skipped). Job 157 measures it on the board,
same configuration as job 133. On paper it removes about half of the 68000's
executed cycles in this scene.

**The counting-loop skip, measured (job 157, fork `b9928c9f`, and the same
build with `neo_nocount`; PC gate IDENTICAL on 19 runs with equal cycle
totals once the harness froze the Neo Geo's clock, `FIXEDTIME`):**

| play window | skip off | skip on |
|---|---|---|
| 68000 | 12.05 | **7.31** |
| core 0 | 25.32 | 24.31 |
| sound wait (`mixer`) | 1.92 | 5.45 |
| core 1 sound job (wall) | 21.68 | 21.76 |

The hashes equal job 133's in both runs: exact on the board too. The 68000
loses 4.7 ms and core 0 gains only 1.0: it now waits 3.5 ms longer for core
1's sound job, whose 21.7 ms of wall time is the frame's floor. On the PC the
skip takes the 68000 from 87.5 % of its cycles executed to 39.7 % in play
(Metal Slug only: none of the other 15 games gated has such a loop). The
sound job's CPU share is about half of that wall time; the rest is the display
task ahead of it and, to be measured, the card reads of its sample pager
(fork `6284092f` prints them: `NEOPROF card reads/frame`). Jobs 159 and 161
add the 16 kHz mix, all frames drawn and one in two.

**Skip plus the 16 kHz mix (jobs 159 and 161, hashes exact, screen clean):**

| play window | 157, skip | 159, skip + 16 kHz mix | 161, the same, one frame in two |
|---|---|---|---|
| core 0 | 24.31 | **22.65** | 20.15 a frame = 40.3 a pair |
| 68000 | 7.31 | 6.63 | 7.71 |
| video | 10.42 | 10.90 | 6.82 |
| sound wait | 5.45 | 3.92 | 4.33 |
| core 1 sound job (wall) | 21.76 | 19.30 | 18.41 |
| core 1 busy | 90 % | 86 % | 93 % |

The frame is 22.65 ms with every frame drawn; a drawn frame plus a skipped one
is still 40 ms against 33.3. **The card reads are the new finding:** one
sprite-page read every ~17 frames and one sample-page read every ~12, rare,
but about **17 ms and 12 ms each** — a whole frame lost when one lands, on
core 0 for the sprites and inside the sound job (so core 0 waits) for the
samples, about 1 ms a frame each on average. A read of 8 KB at the card's
20 MHz should take about 4 ms: the rest is to be found (job 163 times the
seek and the read apart; `neoframes` prints the page reads of a run for given
cache sizes, to see what larger caches would save with the ~850 KB of PSRAM
free in play).

**Larger caches do not remove the card reads** (PC, same run, the reads are
deterministic): Metal Slug 182 sprite pages and 294 sample pages over 3600
frames with today's 1152 / 512 KB, 181-182 and 272-294 with any larger pair;
Metal Slug 2 170 and 166 whatever the size. They are first-touch reads, not
evictions. The lever is the cost of one read. From the sources: the card runs
at 20 MHz on its own SPI bus (40 MHz was unreliable on this board's traces),
FATFS fast seek is on with a 64-entry cluster map, and
`RG_STORAGE_SDSPI_HOLD_CS` is not set for this target although `rg_storage.c`
says it is needed with IDF 5 on an unshared bus (esp-idf issue 10493, slow
SDSPI accesses). Job 163 times the seek and the read apart; job 165 is the
same run with the chip select held (`SD_HOLD_CS=1`).

**Jobs 163 and 165: the chip select held changes nothing; the read is a
command per sector.** Sprite page 17.1 ms (seek 1.5), sample page 11.7 ms
(seek 2.0), with or without `SD_HOLD_CS`; the card mounts at 20 MHz at the
first attempt, no fast-seek warning. 8 KB in 15 ms is 0.5 MB/s against the
2.5 MB/s of the bus: about 1 ms per 512-byte sector. The pagers read straight
into their PSRAM caches, and the SD driver cannot use PSRAM for DMA, so it
reads each sector into its own buffer and copies. Fork (job 167): the pages go
through a DMA-capable buffer of 4 KB taken from the internal RAM for the time
of the read, so the file system can ask for eight sectors in one command.
`SD_HOLD_CS` is not made a default.

**Job 167, multi-sector page reads (fork `e477135c`): every read 2.4 times
faster, hashes exact, the buffer always obtained.**

| play window | 163 | 167 |
|---|---|---|
| sprite page read | 17.1 ms | **7.2 ms** |
| sample page read | 11.7 ms | **4.9 ms** |
| card reads, ms a frame (both) | 2.04 | 0.86 |
| core 0 | 22.77 | **21.91** |

What is left is the card's own latency per block (0.45 ms a sector against
0.2 ms of transfer at 20 MHz): only a faster card, reading ahead of need, or
40 MHz (ruled out by the traces) would hide it.

**Where the play benchmark stands at the end of 2026-10-03** (Metal Slug,
mission 1, every frame drawn, 20 MHz LCD bus, 32 kHz at the speaker):

| | morning | night |
|---|---|---|
| core 0, a frame | 29.08 | **21.91** |
| 68000 | 10.82 | 6.72 |
| video | 10.43 | 10.34 |
| sound wait | 6.73 | 3.64 |
| core 1 display | 15.92 | 12.39 |

from: the branch-free scaler (−4.0), the exact skip of the counting wait loop
(−1.0 on the frame, −4.7 on the 68000), the chips at 16 kHz doubled to 32
(−1.5), the multi-sector card reads (−0.9). Not yet in a play build.

**Save and load on every game (sweep of 2026-10-03, play build `6d54a7e7`,
table in `scripts/mamebench/results/2026-10-03-saveload.md`,
`scripts/saveload_check.py`).** Save, resume at boot and in-session load pass
on NES, SNES, Game Boy, GBC, GBA, SG-1000, Master System, Game Gear, Mega
Drive, ColecoVision, PC Engine, Neo Geo Pocket, the arcade set and the Neo
Geo, after the rows that had failed only on a screenshot taken too early were
rerun. Two real failures, both open:

- **CPS1: the save fails** on Carrier Air Wing, Final Fight, Street Fighter II
  CE and HF; Ghouls'n Ghosts and Knights of the Round pass. Cause, from the
  board's logs: the state is one allocation of its full size, 401 KB, and
  Final Fight's largest free PSRAM block in play is 384 KB (Ghouls has
  2176 KB). The firmware then shows its "Save failed" dialog and waits for a
  key, which the test took for a hang. Fix: the state no longer carries the
  96 KB of the sound Z80's region, only its 2 KB of RAM (`mamego_region_ram`):
  316644 bytes, saved and loaded on the PC. A CPS1 state was never an exact
  continuation, before or after this change (same result with a harness of
  the old format): Final Fight runs the same for about 128 frames after a
  load, then its intro text is one character behind; Knights differs by one
  pixel in the last column from the sixth frame. Something the games read is
  not in the state (a timer or frame phase, a video latch). A known limit,
  small on screen, not fixed.
- **`robby.zip` (arcade): resume at boot gives a black screen** for about 20 s
  after the state loads; the in-session load is fine.

Also seen: `targ.zip` shows MAME's "colortable out of range" message over the
picture after a resume.

**Survey of the other games (PC, `IDLESTAT` and `PCHIST`, 2026-10-03 night).**
No other Neo Geo set has a wait like Metal Slug's (Thrash Rally's hot blocks
are real work and a polling loop with a timeout; Blazing Star and Magician
Lord are borderline, not looked into). **Every CPS1 set spends 50 to 66 % of
its 68000 cycles in Capcom's task scheduler**, a scan of 16 task slots that
waits for the vertical blank (Final Fight 66.5 %, SF2 CE 60.1, Carrier Air
Wing 58.8, Knights 58.6, SF2 HF 54.1, Ghouls 51.6), and the plain idle skip
catches none of it (0.0 % skipped): the turn is an outer loop around a DBRA.
That is Final Fight's 31 fps on a still screen. Fork: idle turns longer than
one loop are skipped exactly (`turn_check` in `m68kcpu.c`, on for the CPS1
only), gate `scripts/neogeo_frames.py turn`, bench switch `cps1_noturn`.

**Can the 16 kHz mix be heard? Measured, 2026-10-03 night
(`scripts/audio_compare.py`).** On the PC, same frames: against a 32 kHz
rendering the 16 kHz one is about 0.5 dB further off per frame in the bass
than a 44.1 kHz rendering is (the yardstick for two good renderings, itself
0.5 to 1.5 dB), has about 1 dB more between 2.2 and 7 kHz (what the chips
produce above 8 kHz folds back), and nothing above 8 kHz. The first doubling,
the midpoint of two samples, also lost 1.2 to 3.3 dB between 5 and 8 kHz and
was replaced by a 12-tap interpolation, flat to 6 kHz. At the speaker, with
the webcam's microphone, two takes of each build: two takes of the SAME build
differ by 5 to 6 dB per frame (room, microphone), the two builds by the same
amount, the level by 0.2 dB, and less than 0.02 % of the energy that leaves
the speaker is above 8 kHz in either build. **Not detectable through this
speaker**; the play build gets `AUDIO_MIX_HZ=16000`. Open: in one of three
takes of the 16 kHz build the sound stopped after 34 s and did not come back;
not reproduced, to be watched on the play build.

**The CPS1 turn skip, gate and review (fork `80176a94`).** PC gate on
`08c08686`: picture and samples identical with equal cycle totals on six
sets, skipped 49 to 81 % of the cycles (Carrier Air Wing 67/81, Knights 67,
SF2 HF 63/76, SF2 CE 75/77, Ghouls 49); Final Fight 0 %, its turn closes 92
bytes back, beyond the 64 looked at: now 96. The board session's adversarial
reading found two holes, both closed: a turn could span two time slices (a
slice serial is now stored), and reads in the I/O window were not seen (now
tracked while the skip is on, and they refuse the turn).

**Before and after, measured on the board (2026-10-03 night, play benchmark,
every frame drawn; "before" is fork `be5e7fd5`, the code of that morning,
"after" is fork `80176a94` with the chips at 16 kHz; FPS is `rg_system`'s
count of the frames really run per second):**

| Game | core 0, ms | 68000, ms | video, ms | FPS |
|---|---|---|---|---|
| Metal Slug | 29.2 → **22.6** | 10.8 → 7.0 | 10.5 → 10.4 | 34 → **44.2** |
| Metal Slug 2 | 36.2 → 33.5 | 12.9 → 12.8 | 17.1 → 15.9 | 27.1 → 29.2 |
| Final Fight (CPS1) | 31.2 → 28.0 | 7.4 → **2.7** | 16.7 → 17.4 | 27.8 → 30.5 |
| Street Fighter II CE (CPS1) | 32.7 → 27.8 | 8.3 → **3.6** | 20.2 → 19.2 | 27.1 → 31.2 |

(Metal Slug's "before" FPS is 1000 / 29.2; that run did not keep the line.
The two CPS1 rows are the intro and the title screen, not play: see the
caution under the table at the top of this page.)
Metal Slug with one frame in two drawn: 20.0 ms a frame, 49.8 frames run a
second, 25 drawn.

What the table says:
- Metal Slug gained a third. Metal Slug 2 has no counting wait loop and draws
  through the 16-bit raster path: its video is 16 ms, its 68000 untouched.
- **On the CPS1 the 68000 is no longer the cost**: 2.7 and 3.6 ms after the
  turn skip. The frame is the video, 17 to 19 ms on core 0, while core 1 is
  30 to 40 % busy. The CPS1's next step is its renderer, or giving part of it
  to the idle core.
- `other` rose from about 1.1 to 2.1 ms in every "after" run: the first
  12-tap doubling shifted its history for every sample. Rewritten without the
  shift (fork `9c920b47`, same samples; job 187 measures it).

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
