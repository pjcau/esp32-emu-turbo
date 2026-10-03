# mamebench: mame-go board benchmark

Tools for the [Arcade 60 fps plan](../../website/docs/next-steps/arcade-60fps-plan.md).
They need the board on `/dev/ttyACM0` and the retro-go Docker build image.

| Script | What it does |
|---|---|
| `mamebench.sh <JIT 0\|1> <rom> [secs]` | Builds mame-go with `MAMEBENCH` + `NEOPROF` (and `M68KJIT=<JIT>`), installs it through the SD updater, resumes save slot 0 of `<rom>` and prints the hash and profile lines. Env: `NOBUILD=1` skips the build, `RESUME=0` cold-boots, `MAMEPROF=1` (or `core1`) turns on the sampling profiler, `NEOBAND=1` builds the band renderer (V1), `NEOBAND=2` hands the bands to the display (V2h), `LCD_MHZ=25` sets the LCD write clock. |
| `mbsum.py <log>` | The 7 MAMEBENCH hashes and the average ms per frame (68000, video, other, core 0), plus the V0 video split (palette, clear, sprites, fix layer) and the KB each part moves per frame, from the `NEOPROF video ms/frame:` line. The sprite and fix write counts are upper bounds (the plotters skip transparent pixels); the clear and the reads are exact. |
| `profsym.sh <log> [n]` | Turns the `MAMESAMPLE` lines of a `MAMEPROF=1` run into a per-function profile (addr2line on `mame-go/build/mame-go.elf`). |
| `wait_launcher.py` | Waits until the launcher answers `ping`. |
| `board_run.sh <step> <rom-name> [secs] [JIT]` | The whole board side of a step: pull, submodules, one `mamebench.sh` run saved under `results/`, summary, commit and push. |

## What a run can be told (2026-10-03)

Environment of `mamebench.sh` / `board_run.sh` (each becomes a build option of
`retro-go/mame-go/CMakeLists.txt`):

| Variable | Meaning |
|---|---|
| `MAMEBENCH=2` | **the play benchmark**: the script inserts a coin, presses START and plays mission 1 (frames 1200 to ~3450 on Metal Slug). Use with `RESUME=0`. `1` (the default) only watches the attract loop: a save state cannot be used, it loads only in the firmware that wrote it |
| `MAMEBENCH=4` | **the play benchmark for CPS1 games**: 30-frame coin at 600 and 1500, 30-frame START at 900 and 1800, the script from 1900 (`--input play2` on the PC). `MAMEBENCH=2`'s 6-frame presses are not taken by the CPS1: Final Fight ignores the coin, Street Fighter II the START, and Ghouls'n Ghosts is still in its RAM test at frame 600, so every CPS1 "play" figure taken with `2` before 2026-10-04 is the intro or the title screen |
| `MAMEBENCH=3` | the play benchmark with every other frame not drawn (a fixed one-in-two frameskip): twice the per-frame average is a drawn frame plus a skipped one |
| `MAMEPROF=1` / `core1` | sampling profiler of core 0 / core 1; with `MAMEBENCH>=2` it samples frames 1300-2800 |
| `NEOBAND=2 NB_LINES=16 LCD_BUFS=3 BAND_INTERNAL=3` | the band renderer handed to the display, as the play build has it |
| `AUDIO_MIX_HZ=16000` | the sound chips render at 16 kHz, doubled to the 32 kHz the speaker always gets |
| `LCD_MHZ=25` | LCD write clock (really 26.7 MHz, outside the ILI9488's 40 ns write cycle: measurement only, the play build stays at 20) |
| `NEOSND_PRIO`, `SD_HOLD_CS` | sound task priority, SD chip select held: both measured, no gain |

Switch files on the card, read at start, no rebuild (`/sd/retro-go/mame/<name>`):
`neo_nomix1` (sound mix on core 0), `neo_nosnd1` (sound board on core 0),
`neo_nocount` (counting wait loops not skipped), `neo_uclock` containing a
percentage (main CPU underclocked), `neo_program` (first program MB in PSRAM:
measured, a loss). A benchmark must start with none of them on the card unless
it is the thing being measured, and remove what it added.

Reading a run: compare two runs on the same NEOPROF samples (20 to 48 is
mission 1 on Metal Slug), never on `mbsum.py`'s average over runs of different
lengths. The `mixer` column is core 0 waiting for core 1's sound job once the
mix runs there. `NEOPROF card reads/frame` gives the SD reads of the sprite
and sample pagers and their cost. MAMEBENCH hashes one frame in 300: the
frame-by-frame proof is the PC's.

One job at a time: the three board scripts hold `/tmp/esp32-emu-turbo-board.lock`.

## The PC gates (`scripts/neogeo_frames.py`)

Every change to what is drawn or computed is proven on the PC before a board
run. All commands run the harness with the Neo Geo's clock frozen
(`FIXEDTIME=1`), otherwise two runs differ by the time they were started.

| Command | Proves |
|---|---|
| `compare` | band renderer against the full-frame one: same picture |
| `ref <harness built before the change>` | a change with no switch: same picture and samples as before |
| `mix` | sound mix inside the sound board's job: same picture and samples |
| `pal` | palette kept across frames: same picture, every frame's array checked |
| `count` | exact skip of counting wait loops: same picture and samples, and the share of cycles skipped by each run |
| `run` with `--input play`, `--rate N`, `--dump DIR@N`, `PALSTAT=1`, `IDLESTAT=1`, a `-DPCHIST` build | measurements: page reads (`PAGES`), loudness (`LEVEL`), palette work, idle loops, where the 68000's cycles go |

A gate must say when a game does not reach the changed code ("NOT
APPLICABLE", "nothing proven"): Metal Slug 2 and KOF95 are 16-bit raster
games and take other paths.

## Two machines

Development happens on a machine without the board (the Mac); the board, its
`/dev/ttyACM0` console and the webcam are on the Linux PC. The two sync through
git only:

1. Development machine: commit and push the retro-go fork **and** this repo
   (the submodule pointer must move with the fork).
2. Board PC: `scripts/mamebench/board_run.sh v0 mslug 70` — pulls, updates the
   submodules, runs the benchmark, commits the log to `results/` and pushes.
3. Development machine: `git pull`, `mbsum.py scripts/mamebench/results/<file>`.

Hands-free variant: the development machine commits jobs to `queue/` and the
board PC keeps `scripts/mamebench/board_agent.sh` running from a `/loop`
(`/loop 3m run scripts/mamebench/board_agent.sh and show me its last 15 lines`);
it pulls, runs each job, pushes the log and the results.


Reference run (Metal Slug, save slot 0 = level 1):

```
scripts/mamebench/mamebench.sh 0 /sd/roms/neogeo/mslug.zip 70 > mb.txt
scripts/mamebench/mbsum.py mb.txt
```

The hashes must stay `300:d26de693 600:18f0c216 900:4b82b950 1200:d14c1cce
1500:7a2d2ee7 1800:beaa3e8b 2100:fba4fa44`. When you compare two runs, average both
over the same window of samples (for example the first 36 `NEOPROF` lines); runs of
different lengths give different averages.

Board rules: the volume stays at 0 while testing. Never send keys without first
checking with `ping` which app is running. Look at the screen with
`scripts/board_cam.py` on every run.
