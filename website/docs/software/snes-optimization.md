---
id: snes-optimization
title: SNES Optimization
sidebar_position: 4
---

# SNES Optimization

How SNES gets from "playable at 75–85%" to real speed on the existing board: measured baseline, a renderer-first software plan (no hardware change), the original February plan as an appendix, and why audio stays on the main chip (no coprocessor).

---

## Measured on the first article (2026-09-12)

The plan below was written before the board existed, from a CPU-only QEMU
benchmark and an estimated cost model. The v4.9.0 first article now gives real
numbers (Retro-Go fork with `RG_ENABLE_PROFILING`, Super Mario World (U), board
on USB with the battery unplugged):

| What | Measured | Meaning |
|:---|:---|:---|
| Emulated speed | **45–52 fps of 60 (75–85%)** | after fixing the per-frame audio size (533 samples/frame NTSC); 42/60 before |
| Drawn frames | **~10–13 fps** | `frameskip = 3` fixed in `main_snes.c` |
| `S9xMainLoop`, frame **not** rendered | **~8.5 ms** | CPU (65C816) + APU (SPC700) alone would run 60 fps with margin |
| `S9xMainLoop`, frame rendered | **~40–50 ms** | the **PPU tile renderer** — ~5x the cost of everything else |
| `rg_display_submit` | 5 µs | asynchronous DMA; the display path is not a factor |
| Audio mix | 1.5 ms | |
| Audio pacing sleep | exact (requested = actual) | Dummy and PDM drivers identical; the earlier "idle 28%" was frames arriving late after a rendered one |
| Free heap under SNES | 167 KB internal, 566 KB PSRAM | |
| BUSY (rg_system) | 68–75% | |

**What this changes.** The cost model in [Why SNES is Hard](#why-snes-is-hard-on-esp32-s3)
put the SPC700 DSP at 48% of the frame and the PPU at 30%; on the real board the
CPU+APU pair fits in ~8.5 ms and the renderer alone blows the 16.67 ms budget three
times over. The order of the sub-phases is therefore being inverted:

1. **Renderer first** — the PPU renderer (`gfx.c`, `tile.c` in snes9x) is the
   Phase 4 target. Rendering alone costs ~32–42 ms (the 40–50 ms figure includes
   the 8.5 ms of CPU+APU): **30 drawn fps at real speed needs ~2.5x on the
   renderer, 60 drawn fps ~5x** (budget table below). The rest of the plan cannot
   get there without it.
2. **Frameskip becomes adaptive**, not fixed: with 13 rendered frames/s eating half
   the machine time, every rendered frame that could be skipped is worth 40 ms.
3. **ASM DSP and dual-core SPC700 become second-order** — they buy back part of
   the 8.5 ms, not the 40 ms.

The renderer-first plan is the next section; the original February plan is kept
as an appendix for the DSP and dual-core material.

Benchmark notes: Super Boss Gaiden (homebrew) hangs snes9x and is not usable as
a benchmark; Super Mario Kart (Mode 7) behaves like Super Mario World. Audio
crackles at 75–85% speed as expected (underruns) on top of the R38 carrier hiss.
Source: [first-boot session log](https://github.com/pjcau/esp32-emu-turbo/blob/main/docs/first-boot-session-2026-08-29.md).

---

## Phase 4 — Renderer-first plan (2026-09-13)

Written against the code as it is in the fork (`retro-core/components/snes9x`,
a snes9x-2005 lineage; `retro-core/main/main_snes.c`), not against a generic
snes9x. Same hardware, same board: everything below is software and
`sdkconfig`.

### The budget

`S9xMainLoop` costs ~8.5 ms of CPU+APU per emulated frame whether or not the
frame is drawn, plus **R ≈ 32–42 ms** when it is. At 60 emulated fps the wall
time per second is `60 × 8.5 ms + drawn × R`, so:

| Milestone | Emulated / drawn fps | R must be ≤ | Speed-up on today's R | Feel |
|:---|:---|---:|---:|:---|
| **today** | 45–52 / 10–13 | 32–42 ms | 1x | playable, choppy, audio underruns |
| **A** | 60 / 20 | ~25 ms | ~1.5x | real speed, audio clean, visibly stepped |
| **B** | 60 / 30 | ~16 ms | ~2.5x | real speed, smooth enough for platformers |
| **C** | 60 / 60 | ~8 ms | ~5x | native — not expected in C on this chip |

**A** is the acceptance bar for Phase 4, **B** the goal. C is listed so nobody
promises it: reaching it would mean the renderer costs less than the CPU+APU
emulation, which no ESP32-S3 snes9x port has shown.

### What a rendered frame actually does today

Facts read from the code, each of which is a lever below:

- **Lazy strip rendering.** Nothing is drawn per scanline; `RenderLine()` only
  snapshots the BG scroll (and Mode 7 matrix) per line. `S9xUpdateScreen()`
  draws the pending strip `PreviousLine..CurrentLine` and is triggered by
  `FLUSH_REDRAW()` from ~30 PPU register-write sites (`ppu.c`, `ppu.h`,
  `dma.c`) plus once at end of frame. Each call recomputes clip windows,
  clears the z-buffers for the strip, and runs `RenderScreen()` once — or
  twice when colour math is on (`ADD_OR_SUB_ON_ANYTHING`: sub-screen pass
  first, then main, then a per-line combine).
- **Per-pixel z-test.** `RenderScreen()` draws OBJ first, then BG0..BG3, each
  through `WRITE_4PIXELS16*()` (`tile.c`): for every pixel a z-byte read,
  compare, z-byte write and a 16-bit screen write. Tiles come from a 512 KB
  decoded-tile cache (`IPPU.TileCache`, filled by `ConvertTile()` from VRAM,
  invalidated on VRAM writes).
- **Everything hot lives in PSRAM.** `CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL=32768`
  sends every allocation above 32 KB to external RAM, and all of these are
  above it: `GFX.Screen` 122 KB (256×239×2), `GFX.SubScreen` 122 KB,
  `GFX.ZBuffer` 61 KB, `GFX.SubZBuffer` 61 KB, `IPPU.TileCache` 512 KB,
  `Memory.VRAM` 64 KB, `Memory.RAM` 128 KB. Between them and the core: a
  **32 KB data cache with 32-byte lines** (`CONFIG_ESP32S3_DATA_CACHE_32KB`),
  Octal PSRAM at 80 MHz. The z-test is therefore a PSRAM read-modify-write
  per pixel.
- **Code from flash through a 16 KB instruction cache.** The core has **zero**
  `IRAM_ATTR`; `gfx.c` + `tile.c` are ~4 200 lines, the whole core ~28 000.
  The framework is built `-Os` (`CONFIG_COMPILER_OPTIMIZATION_SIZE=y`), the
  snes9x component `-O2` (its `CMakeLists.txt`).
- **One core.** The emulator is the main task, pinned to CPU0
  (`CONFIG_ESP_MAIN_TASK_AFFINITY_CPU0`). CPU1 runs nothing but the display
  driver's DMA completion callbacks and `rg_sysmon`.
- **Frameskip is a constant.** `app->frameskip = 3` in `main_snes.c`; the
  adaptive branch of the loop (`frameskip == 0` → skip when `elapsed >
  frameTime + 1.5 ms` or the display was late) is dead code for SNES.
- **Free internal SRAM under SNES: ~167 KB** (566 KB PSRAM). That is the
  budget for every "move it internal" step below; the cache upgrades in 4.1
  come out of it too.

### Measured log (2026-09-13 / 14) — read this before the steps

The steps below were written from the code before the first measurements.
Two days on the first article settled several of them; the numbers here
override the estimates further down.

**Method that replaced the guesswork.** `SNES_PROF=1` counters + on-screen
HUD (step 4.0), a USB-console remote control (`scripts/board_ctl.py`:
launch a ROM, inject keys, save/resume a state, upload files to the card)
and `scripts/snes_bench.py`, which resumes six saved scenes and averages the
counters: SMW overworld map, SMW inside Yoshi's Island 2, Super Mario Kart
first race (Mode 7 + DSP-1), Zelda ALttP inside Link's house (colour
math), Mega Man X first stage, Super Metroid Ceres elevator (Mode 7).
Results live in `software/benchmark/results/*.json`; `--compare <label>`
prints the deltas. A webcam on the screen (`scripts/board_cam.py`) checks
that the picture did not change.

**Corrections to the plan.** The real renderer cost was 18-25 ms per drawn
frame, not 32-42 (that figure came from `-finstrument-functions`, which
inflates hot loops). Adaptive frameskip is *not* dead code: `rg_system`
raises and lowers it every second. And the two "move it internal" levers
of 4.2 do not pay: `IRAM_ATTR` on the whole renderer bought 1-6% (the 32 KB
instruction cache already holds it), `Memory.VRAM` in internal SRAM bought
nothing measurable (the Mode 7 loop is instruction-bound at ~60 cycles per
pixel, not latency-bound) and exposed a heap-layout-dependent corruption
with the 512 KB ROMs (open). The main z-buffer *did* pay (Mario Kart 38 →
57 fps), and the cache upgrade to 32 KB I / 64 KB D is kept.

**What paid.** Blank tiles cached by depth (-1500 `ConvertTile` per frame in
SMW); the audio pacing credit (SMW 46 → 60 fps); the Mode 7 macro with its
invariants in locals (-12%); the **sub-screen-empty colour-math fast path**:
when nothing is on the sub screen the sub z-buffer is 0/1 by column, so a
256-byte table replaces the per-pixel PSRAM read and a precomputed
"palette op fixed colour" replaces the arithmetic (Zelda R 24.9 → 11.0 ms,
Super Metroid 24.6 → 15.9); and the plain tile writers rewritten with
`restrict` pointers and register-resident depths (SMW -13%, Zelda -16%,
Mega Man X -18%).

| Scene | R baseline (ms) | R now | emulated / drawn fps now |
|:---|---:|---:|:---|
| SMW map | 18.2 | 16.4 | 60 / 26 |
| SMW Yoshi's Island 2 | — | 14.8 | 60 / 26 |
| Mario Kart race | 22.5 | 22.5 | 57 / 11 (CPU: DSP-1 11 ms per frame) |
| Zelda house | 24.9 | 9.5 | 60 / 25 |
| Mega Man X | 12.9 | 10.9 | 60 / 24 |
| Super Metroid Ceres | 24.6 | 14.4 | 60 / 22 |
| Donkey Kong Country, Jungle Hijinxs | 16.1 (97 strips) | 11.6 (1 strip) | 60 / 19 |

**Strips.** `PROF/flush` and `PROF/cgram` name the PPU register and the
CGRAM entry that force a mid-frame `S9xUpdateScreen()`. Donkey Kong Country
writes CGRAM entries 0 and 1 on every scanline (HDMA sky gradient) and paid
97 strips per frame — every tile band cut to 1-3 lines. Entry 0 is the
backdrop and is never read by a tile, entries 0-15 are only read by tiles
whose palette starts below 16: both are now snapshotted per line in
`LineData` (like the scroll registers) and read per line — `LineData.Backdrop`
in the backdrop fills, `DrawTile16PalLine` for the tiles, selected only while
`IPPU.PalLineDirty`. Writes to entries ≥ 16, in Mode 7 or with 8-bpp tiles
still flush. Cost elsewhere: +2-3% on SMW/Zelda.

**A bug that looked like a memory-placement problem.** `S9xLoadState()` read
the `IAPU` struct from the file and then `fread()` the 64 KB APU RAM through
`IAPU.RAM` *before* restoring the pointer — i.e. at the address the saving
process had. It only worked while the heap layout was identical; any change
in the binary or in the allocations corrupted the heap (TLSF walk crash right
after "Loaded chunks"). Fixed in `snapshot.c`; save states now survive
rebuilds.

**Roadmap status (2026-09-14).** Milestone **A** (60 emulated / 20 drawn)
is met on every scene except Mario Kart (57 / 11, limited by the DSP-1 CPU
emulation, not the renderer). Milestone **B** (60 / 30) is reached on SMW,
Zelda and Mega Man X and not on the Mode 7 games or DKC. Of the plan's
steps: 4.0 done, 4.1 done, 4.2 partly (z-buffer yes; IRAM and VRAM
disproven), 4.3 done in a different form (colour-math fast path, per-line
backdrop/palette instead of fewer strips), 4.4 (painter's order) and 4.5
(budget-driven frameskip) not started, 4.6 (second core) done for Genesis'
FM chip and still open for the SNES APU. The renderer is no longer the
first thing to optimise for the SNES: the next wins are the APU/CPU side
on core 1 (Kart, Metroid) and frameskip that follows the budget (every
scene sits at frameskip 1-2 with 40-70% busy). What is left in the renderer is instruction count: the
per-pixel loops (Mode 7, `WRITE_4PIXELS16`, the backdrop combine — 5 ms in
SMW because the sky *is* the backdrop) run 20-45 instructions on a
single-issue 240 MHz core; a 4-pixels-at-a-time skip on the combine made
it slower, not faster. Tried since: the Mode 7 loop
with a per-span counter (Metroid -7%, Kart ±0), a per-colour-window-run
plain Mode 7 loop (Kart slower — disabled), a 4-pixel "covered" skip in the
backdrop combine (slower: in SMW the sky *is* the backdrop, so z is mostly
zero). Next levers: the painter's order fast path (4.4) that removes the
z-buffer read-modify-write, and a dedicated SNES app partition (the
retro-core binary carries 43 KB of IRAM for nofrendo/gnuboy/smsplus) to
make room for the sub z-buffer. Mario Kart's ceiling is the CPU side.

### Steps, in order

Each step is measured the same way (see *Method*) and reverted if the number
does not move. Days are effort, not calendar.

#### 4.0 — Instrument the renderer before touching it (½ day)

Extend the existing `RG_ENABLE_PROFILING` block (`main_snes.c`) with counters
reset every second, printed on the `PROF` line:

- `S9xUpdateScreen()` calls per frame and lines per strip (how fragmented is a
  frame — 1 strip or 30?);
- frames with the sub-screen pass (`ANYTHING_ON_SUB && ADD_OR_SUB_ON_ANYTHING`);
- tiles drawn, `ConvertTile()` calls (cache misses) per frame;
- time inside `DrawOBJS()`, `DrawBackground()` (per BG), the z-buffer
  `memset`s, and the colour-math combine loop — `esp_timer_get_time()` around
  each, accumulated;
- BG-mode histogram per frame.

Run on the three reference scenes (*Method*). Deliverable: one table in the
session log. **Every estimate below is provisional until this exists.**

#### 4.1 — Configuration-only wins (½ day)

No source change; each toggled alone and measured:

| Change | Where | Cost | Why |
|:---|:---|:---|:---|
| Data cache 32 → **64 KB**, line 32 → **64 B** | `CONFIG_ESP32S3_DATA_CACHE_64KB`, `..._LINE_64B` | 32 KB internal SRAM | every hot buffer is behind this cache |
| Instruction cache 16 → **32 KB** | `CONFIG_ESP32S3_INSTRUCTION_CACHE_32KB` | 16 KB internal SRAM | 1 MB of code through 16 KB thrashes on the tile writers |
| Framework `-Os` → `-O2` | `CONFIG_COMPILER_OPTIMIZATION_PERF=y` | flash size | `rg_display`, `rg_audio`, the surface scaler |
| `-O3` / `-funroll-loops` on `tile.c`, `gfx.c` only | snes9x `CMakeLists.txt` | flash size | inner loops are 4-pixel unrolled by hand, the compiler can do 8 |
| Flash 80 → 120 MHz | `CONFIG_ESPTOOLPY_FLASHFREQ_120M` + `CONFIG_SPI_FLASH_HPM_ENABLE` | marked experimental by IDF | instruction-cache misses fill 50% faster |

Expected: 10–25% on R (the code is memory-bound, and both caches are
under-sized for it). Budget after this step: ~167 − 48 = **~119 KB** internal.

#### 4.2 — Put the right buffers in internal SRAM, and the hot code in IRAM (1 day)

Priority order, one at a time, each measured:

1. **`GFX.ZBuffer` + `GFX.SubZBuffer`** (2 × 61 KB) — the per-pixel
   read-modify-write. `heap_caps_malloc(…, MALLOC_CAP_INTERNAL)` in
   `S9xInitDisplay()` (`main_snes.c`). This alone eats the 119 KB; if it does
   not fit, the strip trick applies: `GFX.DB` is a base pointer and the
   writers index it by `y × ZPitch`, so a z-buffer sized for the tallest
   strip (224 lines = 57 KB) with `GFX.DB = strip − StartY × ZPitch` serves
   any strip — one 57 KB buffer instead of 122 KB, if 4.0 shows strips
   never overlap the sub/main passes.
2. **`Memory.VRAM`** (64 KB) — `ConvertTile()` source and Mode 7's direct
   reads. Pays off on tile-cache-miss-heavy scenes (Mode 7, animated tiles).
3. **Not** `GFX.Screen`: its writes are sequential (write-allocate friendly)
   and the display DMA reads it from PSRAM anyway.
4. **Not** `IPPU.TileCache` (512 KB): stays in PSRAM; shrink it instead if
   4.0 shows most of it is never touched (SMW uses a fraction of the 4096
   2-bpp-equivalent slots).
5. **`IRAM_ATTR`** on the writers: `WRITE_4PIXELS16*`, `DrawTile16*`,
   `DrawClippedTile16*`, `DrawBackground()`, `DrawOBJS()`, `ConvertTile()`,
   `S9xUpdateScreen()`. ~15–20 KB of IRAM; ESP-IDF places `IRAM_ATTR` code
   in the instruction RAM, outside the flash cache entirely.

Where the internal budget comes from if it runs short: the display driver's
5-buffer pool (`ili9488_i80.h`; 3 is enough at these frame rates), and
`GFX.SubScreen` can be dropped when transparency is off (4.3).

Expected: **1.3–1.8x** on R. This is the step the ESP32-S3 snes9x ports that
report ~45 fps (`fcipaq/snes9x_esp32`) lean on hardest.

#### 4.3 — Draw fewer pixels: strips, passes, clears (2 days)

Driven entirely by the 4.0 counters:

- **Z-buffer clears** — the two `memset`s per strip line (122 KB of writes
  per full frame) go away with frame-stamped depth: depth values carry
  `frame & 0xC0` in their top bits and the compare becomes "older stamp =
  empty", so the buffer is never cleared. `MAIN_SCREEN_DEPTH`,
  `SUB_SCREEN_DEPTH` and the `D + n` priorities in `RenderScreen()` fit in
  6 bits.
- **Strip fragmentation** — if 4.0 shows many `S9xUpdateScreen()` calls per
  frame, audit the `FLUSH_REDRAW()` sites: several already guard on "value
  changed"; the ones that do not (mid-frame writes of an unchanged value)
  are free strips saved.
- **Sub-screen pass** — when 4.0 shows colour math enabled but the
  sub-screen result cannot reach the screen (no layer on sub, or the colour
  window covers nothing), skip the pass. Add an operator switch
  **"Transparency: on / off"** in the SNES options menu: off skips the
  sub-screen pass and the combine loop entirely (visual downgrade in fades
  and water; a legitimate trade on a handheld).
- **Sprites** — `S9xSetupOBJ()` runs whenever `OBJChanged` (every frame with
  OAM DMA); measure it; the per-line OBJ lists are rebuilt from all 128
  sprites each time.

Expected: **1.2–1.5x** on top of 4.2.

#### 4.4 — The inner loop: painter's-order fast path (2–3 days)

This is the February plan's "PPU fast-path (Mode 1)" made concrete. The
z-buffer exists because this core draws **front-to-back** (OBJ first, then
BGs by priority) and lets the z-test reject covered pixels. For the common
case — **Mode 1, no colour math, no windows, no mosaic, no offset-per-tile,
no hi-res** — a **back-to-front** renderer needs no z-buffer at all: draw
BG3 low, BG2 low, BG1 low, BG0 low, OBJ by priority, BG highs, in the
documented SNES priority order, each layer writing opaque pixels only. Per
pixel: one 16-bit write, no z read, no z write. Sprites-vs-BG priority is
handled by drawing sprite priority classes at the right slots in that order
(the OBJ per-line lists already carry priority).

- Detect the fast-path conditions once per strip in `S9xUpdateScreen()`;
  fall back to the existing z-buffer renderer otherwise (nothing is lost).
- Writers for the fast path: `WRITE_8PIXELS16_OPAQUE` variants (8 pixels per
  call, 2 × 32-bit stores for the fully opaque tile case — `ConvertTile()`
  already returns `BLANK_TILE`, extend it to report "fully opaque").
- Xtensa specifics once the C version is measured: the zero-overhead `loop`
  instruction and 32-bit stores; no need for hand assembly to get there.

Expected: **1.5–2x** on the fast-path frames. Cumulative with 4.1–4.3 this
is the **B** milestone (~2.5x) for Mode 1 games — SMW, Zelda, Mega Man X,
most platformers. Mode 7 games stay on the z-buffer path and land near
**A**.

#### 4.5 — Frameskip that follows the budget, not a constant (½ day)

Replace `app->frameskip = 3` with a policy on the measured frame time:

- keep a rolling average of R and of the non-rendered frame time;
- choose the drawn rate so that `60 × 8.5 + drawn × R ≤ 1000 ms` with 10%
  headroom, quantised to 60/n (60, 30, 20, 15, 12);
- render on a fixed cadence at that rate (steady 20 fps looks better than
  bursts of 3 renders then 6 skips);
- never skip when the audio sink reports it is about to underrun — the
  audio pacing sleep is already exact (measured), so the sink is the
  authority on "are we late".

Retro-Go's own adaptive branch (`frameskip == 0`) is the starting point; it
only lacks the cadence and the audio-aware rule. This step turns every
speed-up above into steady visual fps automatically.

#### 4.6 — Second core (2–3 days, only after 4.4 is measured)

CPU1 is idle. What can move there without rewriting snes9x:

- **SPC700 + DSP** (the February 4.2.1): the APU is stepped from the CPU
  loop (`APU_EXECUTE` in `cpuexec.c`) and its output mixed per frame; moving
  it to CPU1 with a lock-free sample ring cuts the 8.5 ms to ~5–6 ms — on
  **every** frame, drawn or not. Worth ~15% of wall time at milestone B.
- **Not** the renderer: `S9xUpdateScreen()` reads live VRAM/CGRAM/OAM while
  the CPU keeps mutating them, so a strip would need a snapshot (64 KB VRAM
  per strip) — rejected on memory grounds.
- The audio mix (1.5 ms) and the display scaler are already cheap/async.

The February 4.1 (Xtensa assembly for BRR / Gaussian / mixer / echo) lives
here as an optional follow-up to shrink what CPU1 has to do; it is no longer
on the critical path.

#### Not doing

- **Overclock to 260 MHz**: the ESP32-S3 is specified to 240 MHz; there is
  no supported higher setting.
- **Audio sample-rate reduction**: the mix is 1.5 ms; nothing to gain.
- **Reducing emulated speed to hide the renderer**: the target is real speed
  with fewer drawn frames, never the reverse.

### Method

- Build with `RG_ENABLE_PROFILING`, board on USB with **the battery unplugged
  from J3**, read the `PROF` and `FPS` lines on the serial for 60 s from the
  same save state.
- Three scenes, saved as slots: **Super Mario World** level 1 (Mode 1, the
  reference), **Super Mario Kart** first race (Mode 7), **Zelda: A Link to
  the Past** outdoor rain (Mode 1 with colour math and windows). Super Boss
  Gaiden is not a benchmark (it hangs the core).
- One change per commit in the fork, numbers in the commit message and in
  the [session log](https://github.com/pjcau/esp32-emu-turbo/blob/main/docs/first-boot-session-2026-08-29.md);
  a change that does not move R by its expected share is reverted, not kept
  "because it should help".
- Report R (rendered-frame `main` minus non-rendered `main`), drawn fps,
  emulated fps and BUSY; the milestone table above is the pass/fail.

---

## Appendix — the pre-hardware plan (February 2026, superseded)

Kept for its DSP, dual-core and PPU material, which the renderer-first plan above references by step number. Do not read its fps columns as predictions.

Progressive optimization of the snes9x core (Snes9x 2005 via Retro-Go) in 3 sub-phases over ~14 days. Target: **60 FPS stable** on standard titles (Super Mario World, Zelda ALttP, Chrono Trigger, Final Fantasy VI, Mega Man X). Baseline: ~30 FPS *(pre-hardware estimate — measured: 45–52 emulated / 10–13 drawn, see above; the sub-phase order is being re-prioritised around the renderer)*. See below for full technical details.

| Sub-phase | Step | Optimization | Days | Gain | Cumulative FPS |
|:---|:---|:---|---:|:---|:---|
| **4.1 — ASM DSP** | 4.1.1 | BRR Decode assembly (Xtensa LX7) | 1 | +5–7% | 30 → 32–33 |
| | 4.1.2 | Gaussian Interpolation assembly | 0.5 | +3–4% | 33 → 34–35 |
| | 4.1.3 | Voice Mixing assembly (fast-path) | 2 | +5–8% | 35 → 38–40 |
| | 4.1.4 | Echo FIR Filter assembly (8-tap unrolled) | 0.5 | +2–3% | 40 → 41–42 |
| **4.2 — Architecture** | 4.2.1 | Dual-Core SPC700 (Core 1 dedicated audio) | 2–3 | +35–45% | 42 → 50–52 |
| | 4.2.2 | Memory Layout (PSRAM → SRAM, ~100 KB) | 1 | +15–20% | 52 → 54–56 |
| | 4.2.3 | Overclock to 260 MHz | 0.01 | +8% | 56 → 57–58 |
| | 4.2.4 | Audio sample rate 32 → 16 kHz | 0.05 | +2–3% | 57–58 |
| **4.3 — PPU & Display** | 4.3.1 | PPU Fast-Path rendering (Mode 1) | 3–4 | +5–8% | 58 → 59–60 |
| | 4.3.2 | Tile Cache in SRAM (dirty-flag) | 1 | +3–5% | 60 + headroom |
| | 4.3.3 | DMA Display Push (double-buffer) | 1 | +2–3% | 60 + headroom |
| | 4.3.4 | Adaptive Frameskip (safety net) | 0.5 | safety net | **60 stable** |

---

### Why SNES is Hard on ESP32-S3

The SNES has three CPU-intensive subsystems that must be emulated in real-time:

```
Frame time budget: 16.67 ms (for 60 fps)

┌────────────────────────────────────────────┐
│ 65C816 CPU emulation         ~4.5 ms  27%  │
│ PPU rendering (2 BG layers)  ~5.0 ms  30%  │
│ SPC700 audio DSP             ~8.0 ms  48%  │  ← bottleneck
│ Display transfer             ~1.5 ms   9%  │
├────────────────────────────────────────────┤
│ TOTAL                       ~19.0 ms 114%  │  ← over budget
└────────────────────────────────────────────┘
```

:::caution Estimate, superseded by measurement
This breakdown was the pre-hardware estimate. On the first article the CPU+APU
pair costs ~8.5 ms per frame and a rendered frame ~40–50 ms — the PPU renderer,
not the SPC700 DSP, is the bottleneck. See
[Measured on the first article](#measured-on-the-first-article-2026-09-12).
:::

At 114% of the frame budget on a single core, the estimate put SNES emulation via Retro-Go (Snes9x 2005) at ~30 FPS on a target of 60 FPS. The 3-phase optimization plan below combines assembly-level DSP work, architectural changes (dual-core, memory layout), and rendering optimizations (PPU fast-path, tile cache, DMA display) to reach 60 FPS stable.

:::note
Performance gains are not perfectly additive — each optimization reduces the total frame time, so subsequent ones operate on a smaller base. The estimates account for this non-linearity.
:::

---

### Phase 4.1 — Assembly DSP (Xtensa LX7)

**Goal:** Rewrite the 4 heaviest S-DSP audio functions in native Xtensa assembly. These consume ~50% of the total SPC700 audio emulation time. ~120 lines of ASM, ~4 days.

#### 4.1.1 — BRR Decode (`DecodeBlockAsm`)

| | |
|:---|:---|
| **C function** | `DecodeBlock()` in soundux.cpp |
| **What it does** | Decodes BRR blocks (9 bytes → 16 PCM 16-bit samples). Native compressed format for all SNES audio samples. |
| **Call frequency** | ~2000–4000 times/frame (8 voices x sample rate x variable pitch) |
| **C bottleneck** | Loop with branches for clamping, stack spill for filter variables, unoptimized buffer access |
| **ASM optimization** | Zero-overhead `LOOP`, branchless `MIN`/`MAX` clamping, dedicated registers for filter state (a7/a8), load/compute interleaving |
| **Expected gain** | **+5–7%** on total frame time |
| **Effort** | ~30 lines ASM — 1 day |

Each BRR block has a header byte (shift amount + filter type 0–3) followed by 8 bytes of compressed data. Filters apply linear prediction using the 2 previous samples. The assembly eliminates branches in [-32768, +32767] clamping via native Xtensa `MIN`/`MAX` instructions, keeping old/older samples in registers a7/a8 without touching the stack.

#### 4.1.2 — Gaussian Interpolation (`GaussianInterpAsm`)

| | |
|:---|:---|
| **C function** | Inline interpolation in MixStereo/MixMono loop |
| **What it does** | 4-point filter with 512-entry Gaussian lookup table. Interpolates between decoded samples for resampling at desired pitch. |
| **Call frequency** | 32000/sec x 8 voices = 256,000 calls/sec |
| **C bottleneck** | 4 loads from gauss table + 4 multiplications + accumulate. Compiler generates ~18 instructions with intermediate load/stores. |
| **ASM optimization** | Gauss table in IRAM (`.section .iram1`), 4x `MULL`+`ADD` pipeline-scheduled, result in 8 net instructions. All 4 samples and 4 coefficients live in registers. |
| **Expected gain** | **+3–4%** on total frame time |
| **Effort** | ~10 lines ASM — half day |

The key is placing the Gaussian table (1 KB) in IRAM with `.section .iram1` — this eliminates PSRAM latency for every lookup. With coefficients pre-loaded in registers, the computation reduces to 4 `MULL` + 3 `ADD` + 1 `SRAI`. The C compiler typically cannot keep everything in registers because it has no aliasing guarantees on the pointers.

#### 4.1.3 — Voice Mixing (`MixVoiceAsm`)

| | |
|:---|:---|
| **C function** | `MixStereo()` / `MixMono()` in soundux.cpp |
| **What it does** | For each voice: applies ADSR/GAIN envelope, multiplies by L/R volume, accumulates into mix buffer. Handles pitch modulation, noise, and echo enable. |
| **Call frequency** | 1 per output sample x 8 voices = core loop of the entire DSP |
| **C bottleneck** | Most complex loop: per-voice branching (envelope state machine, pitch mod check, noise check, echo check), volume multiplications, stereo accumulate. Many variables, heavy register pressure. |
| **ASM optimization** | Fast-path for the common case (no pitch mod, no noise): eliminates branches, unrolls 8 voices, optimized stereo volume MAC. Fallback to C for special cases. |
| **Expected gain** | **+5–8%** on total frame time |
| **Effort** | ~60 lines ASM — 2 days (most complex) |

The strategy is a fast-path for the most frequent case (active voice, envelope in SUSTAIN state, no pitch modulation, no noise). This covers ~80% of real gameplay situations. For edge cases (ATTACK/DECAY/RELEASE, active pitch mod, noise generator), it falls back to the original C function. The fast-path uses Xtensa register windowing to keep all 8 volumes (L+R) and 8 envelopes in registers.

#### 4.1.4 — Echo FIR Filter (`EchoFIRAsm`)

| | |
|:---|:---|
| **C function** | Echo processing in main MixStereo loop |
| **What it does** | 8-tap FIR (Finite Impulse Response) on echo buffer. Each echo output sample = sum of 8 previous samples x 8 programmable coefficients. |
| **Call frequency** | 32000/sec (one per output sample, stereo) |
| **C bottleneck** | 8-iteration loop with signed multiplication and accumulate. Compiler doesn't fully unroll and doesn't optimally schedule the `MULL`. |
| **ASM optimization** | Full 8x unroll, `MULL` pipeline-scheduled with next sample load in parallel. Echo buffer pointer in register. Branchless clamping. |
| **Expected gain** | **+2–3%** on total frame time |
| **Effort** | ~20 lines ASM — half day |

With 8 taps fully unrolled, each `MULL` is scheduled while the next sample load is in flight, hiding memory latency. The 8 FIR coefficients (signed bytes) are loaded into two 32-bit registers (4 coefficients per register) and extracted with shift+mask, avoiding 8 separate loads.

#### Phase 4.1 Summary

| Function | ASM lines | Days | Gain % | FPS impact |
|:---|---:|---:|:---|:---|
| DecodeBlockAsm | ~30 | 1 | +5–7% | 30 → 32–33 |
| GaussianInterpAsm | ~10 | 0.5 | +3–4% | 33 → 34–35 |
| MixVoiceAsm | ~60 | 2 | +5–8% | 35 → 38–40 |
| EchoFIRAsm | ~20 | 0.5 | +2–3% | 40 → 41–42 |
| **TOTAL Phase 4.1** | **~120** | **4** | **+15–22%** | **30 → 38–42 FPS** |

---

### Phase 4.2 — Architectural Optimization

**Goal:** Restructure the emulator to leverage the ESP32-S3 dual-core and optimize memory layout. This phase has the single biggest impact overall. ~4 days.

#### 4.2.1 — Dual-Core SPC700 Separation

| | |
|:---|:---|
| **Intervention** | Move the entire SPC700 + DSP emulation (now ASM-optimized from Phase 4.1) to a dedicated FreeRTOS task on Core 1. |
| **Current state** | CPU 65C816, PPU, and SPC700 all run on Core 0 sequentially. Core 1 is fully idle — Wi-Fi and Bluetooth are not enabled in `sdkconfig.defaults` for Phase 1 hardware validation, so there is no WiFi/BT stack consuming Core 1. Future revisions that enable Wi-Fi will need to reserve Core 1 budget. |
| **Target architecture** | **Core 0:** CPU 65C816 + PPU + game logic. **Core 1:** SPC700 CPU + DSP (Phase 4.1 assembly) + I2S output via DMA. Communication via 4 lock-free I/O ports (atomic read/write). |
| **Implementation** | FreeRTOS task pinned to Core 1 with high priority. DMA-capable ring buffer (`MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL`) between DSP and I2S driver. The 4 SPC ↔ CPU ports are atomic variables (no mutex needed). |
| **Risks** | Temporal synchronization: some games depend on exact timing between CPU and SPC700. **Solution:** timestamp-based sync with ±64 sample tolerance (~2ms). Works for 95%+ of games. |
| **Expected gain** | **+35–45%** on total frame time |
| **Effort** | 2–3 days |

This is the single most impactful change in the entire plan. Freeing Core 0 from all audio emulation virtually doubles the available CPU budget for CPU+PPU.

```
Core 0 (main):                 Core 1 (audio):
  65C816 CPU emulation           SPC700 CPU emulation
  PPU rendering                  DSP (assembly from Phase 4.1)
  Display transfer               I2S DMA output feed
  Input polling

  ~10.5 ms/frame                 ~8.0 ms/frame → ~5 ms with ASM
  → bottleneck at 11ms           (runs fully in parallel)
```

#### 4.2.2 — Memory Layout Optimization

| | |
|:---|:---|
| **Intervention** | Relocate critical data structures from PSRAM to internal SRAM (512 KB). |
| **Structures to move** | SPC700 RAM (64 KB), PPU tile cache (~32 KB), palette RAM (512 B), OAM sprite table (544 B), CGRAM (512 B), DSP registers (128 B). **Total: ~100 KB in SRAM.** |
| **Impact** | Octal PSRAM has ~80–120ns random access latency vs ~10ns for internal SRAM. The DSP and PPU make thousands of random accesses per frame. **8–10x latency difference.** |
| **Implementation** | Replace `malloc()` with `heap_caps_malloc(size, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)` for identified structures. Verify remaining SRAM budget with `heap_caps_get_free_size()`. |
| **Expected gain** | **+15–20%** on total frame time |
| **Effort** | 1 day (few lines of code, but requires profiling) |

#### 4.2.3 — Overclock to 260 MHz

| | |
|:---|:---|
| **Intervention** | Increase clock from 240 to 260 MHz via ESP-IDF menuconfig (unofficial but stable). |
| **Implementation** | In sdkconfig: `CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ=260`. Or runtime: `esp_pm_configure()` with `max_freq_mhz=260`. |
| **Risks** | Minimal. The S3 is officially tested to 240 MHz, but 260 MHz is widely used in the community without stability issues. No significant power consumption increase. |
| **Expected gain** | **+8%** linear across everything |
| **Effort** | 10 minutes |

#### 4.2.4 — Audio Sample Rate Reduction

| | |
|:---|:---|
| **Intervention** | Reduce DSP sample rate from 32 kHz to 16 kHz. Halves the number of samples to compute per second. |
| **Audio impact** | Slightly lower perceived quality on high frequencies (cymbals, hi-hat). For most SNES music the difference is minimal on a handheld speaker. |
| **Expected gain** | **+5–8%** on audio processing (~2–3% total after dual-core) |
| **Effort** | 30 minutes |

#### Phase 4.2 Summary

| Intervention | Days | Gain % | Cumulative FPS |
|:---|---:|:---|:---|
| Dual-Core SPC700 | 2–3 | +35–45% | 42 → 50–52 |
| Memory Layout SRAM | 1 | +15–20% | 52 → 54–56 |
| Overclock 260 MHz | 0.01 | +8% | 56 → 57–58 |
| Sample Rate 16 kHz | 0.05 | +2–3% | 57–58 |
| **TOTAL Phase 4.2** | **~4** | **cumulative** | **42 → 56–58 FPS** |

---

### Phase 4.3 — The Last Mile: PPU & Display

**Goal:** Go from ~57 to 60 FPS stable by optimizing PPU rendering and the display pipeline. More complex optimizations but necessary for the final 5%. ~6 days.

#### 4.3.1 — PPU Fast-Path Rendering

| | |
|:---|:---|
| **Intervention** | Create optimized paths for common PPU cases: Mode 1 (used by 70%+ of games), no clipping windows, no mosaic, no complex color math. |
| **Detail** | The Snes9x 2005 PPU handles ALL cases (Mode 0–7, windows, mosaic, color math, hi-res, interlace, offset-per-tile) in a single generic code path with many branches. The fast-path eliminates checks for features not used in the current scanline. |
| **Expected gain** | **+5–8%** on total frame time |
| **Effort** | 3–4 days (requires deep PPU understanding) |

#### 4.3.2 — Tile Cache in SRAM

| | |
|:---|:---|
| **Intervention** | Cache decoded tiles in internal SRAM. The PPU decodes the same tiles hundreds of times per frame (repeated background tiles). With dirty-flag tracking, only re-decode when VRAM changes. |
| **Expected gain** | **+3–5%** |
| **Effort** | 1 day |

#### 4.3.3 — DMA Display Push

| | |
|:---|:---|
| **Intervention** | Use the ESP32-S3 DMA to transfer the framebuffer to the display (8-bit 8080 parallel) without engaging the CPU. Double-buffering: while DMA sends frame N, the CPU renders frame N+1. |
| **Expected gain** | **+2–3%** |
| **Effort** | 1 day |

#### 4.3.4 — Adaptive Frameskip (Safety Net)

| | |
|:---|:---|
| **Intervention** | If the frame budget (16.67ms) is exceeded, skip rendering the next frame (but still execute game logic). Frameskip 1 = 30 FPS perceived but gameplay at 60. |
| **Strategy** | Auto-adaptive: measure previous frame time. If over 16.67ms, skip render. If under 15ms, never skip. Zone 15–16.67ms: skip 1 every 4 frames. **Perceived result: 45–60 FPS constant.** |
| **Expected gain** | Safety net — maintains 60 perceived FPS even at ~55 real FPS |
| **Effort** | Half day |

---

### Complete FPS Progression

| # | Intervention | FPS pre | FPS post | Delta FPS | Days cum. |
|:---|:---|---:|---:|:---|---:|
| F4.1 | BRR Decode ASM | 30 | 32–33 | +2–3 | 1 |
| F4.1 | Gaussian Interp ASM | 33 | 34–35 | +1–2 | 1.5 |
| F4.1 | Voice Mixing ASM | 35 | 38–40 | +3–5 | 3.5 |
| F4.1 | Echo FIR ASM | 40 | 41–42 | +1–2 | 4 |
| F4.2 | Dual-Core SPC700 | 42 | 50–52 | **+8–10** | 7 |
| F4.2 | Memory Layout SRAM | 52 | 54–56 | +2–4 | 8 |
| F4.2 | Overclock 260 MHz | 56 | 57–58 | +1–2 | 8 |
| F4.2 | Sample Rate 16 kHz | 58 | 58 | +0–1 | 8 |
| F4.3 | PPU Fast-Path | 58 | 59–60 | +1–2 | 12 |
| F4.3 | Tile Cache SRAM | 60 | 60 | +headroom | 13 |
| F4.3 | DMA Display | 60 | 60 | +headroom | 14 |
| F4.3 | Adaptive Frameskip | — | **60 stable** | safety net | 14.5 |

---

### Game Compatibility

| Game | Complexity | Expected FPS | Playable? |
|:---|:---|:---|:---|
| Super Mario World | Low | 60 | **Yes** |
| Zelda: A Link to the Past | Low | 58–60 | **Yes** |
| Chrono Trigger | Medium | 55–60 | **Yes** |
| Final Fantasy VI | Medium | 55–60 | **Yes** |
| Mega Man X | Medium | 55–58 | **Yes** |
| Super Metroid | Medium-High | 50–58 | **Yes*** |
| Donkey Kong Country | High | 45–55 | Partial |
| Street Fighter II Turbo | High | 45–55 | Partial |
| Star Fox (Super FX) | Extreme | 20–30 | **No** |
| Yoshi's Island (Super FX 2) | Extreme | 15–25 | **No** |

\* With occasional adaptive frameskip in heavy scenes.

:::note Games with special coprocessors
Games using special coprocessors (Super FX, Super FX 2, SA-1, DSP-1/2/3/4) would require an ESP32-P4 (400 MHz) or better to reach full speed. These chips add a significant computation overhead that cannot be optimized away on the ESP32-S3.
:::

:::tip SNES on v2 (ESP32-P4)
The ESP32-P4 at 400MHz with 2.1x the CoreMark score would bring SNES to full-speed with full audio quality for virtually all standard games, and make Super FX titles partially playable.
:::

### Audio Profiles

The SPC700 audio DSP is the single biggest CPU bottleneck before Phase 4.1 assembly optimizations. Three selectable profiles trade audio quality for frame rate, toggled in-game via **Menu button → Audio: Full / Fast / OFF**.

#### Profile Comparison

| Profile | Sample rate | Interpolation | Echo/Reverb | Channels | DSP time (pre-ASM) | DSP time (post-ASM) |
|:---|:---|:---|:---|:---|---:|---:|
| **Full** | 32 kHz | Gaussian (4-tap) | Yes | Stereo | ~8.0 ms | ~5.0 ms |
| **Fast** | 16 kHz | Linear (2-tap) | No | Mono | ~2.5 ms | ~1.5 ms |
| **OFF** | — | — | — | — | 0 ms | 0 ms |

After Phase 4.1 (ASM DSP) + Phase 4.2 (dual-core), audio runs on Core 1 in parallel. With all optimizations applied, Full audio profile at 60 FPS is the target — no quality compromise needed for standard games.

:::tip Recommended: Full audio after all optimizations
Unlike the pre-optimization estimates, the 3-phase plan targets **60 FPS with full 32kHz stereo audio** for standard games (Super Mario World, Zelda, Chrono Trigger, FF6). Audio Fast/OFF remain available as fallback options for heavy scenes or complex games.
:::

---

## Audio — no separate coprocessor {#audio-no-coprocessor}

The February plan added an ESP32-S3-MINI-1 module as a dedicated audio
coprocessor on the next board. That plan was dropped on 2026-09-26: the
measurements on the first article removed the reason for it.

| What | Measured on the board | Consequence |
|:---|:---|:---|
| CPU (65C816) + APU (SPC700) together | ~8.5 ms of the 16.7 ms frame | fits, with margin |
| Audio mix | 1.5 ms | negligible |
| PPU renderer | 10–16 ms per drawn frame | the actual bottleneck |
| Super Mario Kart (57 fps) | DSP-1 cartridge chip, 11 ms per frame | CPU side, not audio |

The pre-hardware estimate put the SPC700 + S-DSP at ~8 ms, 48% of the
frame (see the appendix). On the board the renderer dominates, so a chip
that takes audio away would speed up the part that already fits and leave
the slow part untouched.

**The second core already does this job.** The ESP32-S3 has two cores and
the second one is almost idle during games (Wi-Fi runs only in the
launcher). The Genesis core already moves its YM2612 FM synthesis to
core 1, which took it from 20 to 30 drawn fps at a full 60 emulated fps.
Moving the SNES S-DSP sample generation to core 1 is the matching software
step, with no hardware change.

**An external chip would be worse than core 1.** The SPC700 and the 65C816
talk through four I/O ports that games poll in lockstep; the latency of an
SPI link would break that sync. Only the final stage (the S-DSP producing
samples) can be separated, which is exactly what core 1 can take. The
module would also have cost $3.27 per board, 15.4 × 20.5 mm of board area,
an SPI link to route, a second firmware to build and flash, and ~50 mA more
on the 3.3 V rail.

**Where the next board (v4) spends on audio instead.** The real audio
problem on the current board is analog: the PDM carrier hiss, reduced by
the R38 rework (1 kΩ + 10 nF) but not removed, and the reason this target
starts at volume 0. The v4 plan replaces the PDM → RC filter → PAM8403
chain with an I2S class-D amplifier with an integrated DAC (for example the
MAX98357A class of part; the exact part is chosen against JLCPCB stock when
the v4 schematic starts). That gives clean audio with fewer parts and lets
the default volume come back up.

**If more headroom is ever needed**, the only hardware change that moves
frame rates is a faster main MCU, for example the ESP32-P4 (dual RISC-V at
400 MHz; it has no radio, so Wi-Fi would need a companion chip). An audio
coprocessor does not.
