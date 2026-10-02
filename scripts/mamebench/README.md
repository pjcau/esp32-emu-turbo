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
