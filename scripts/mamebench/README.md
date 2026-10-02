# mamebench: mame-go board benchmark

Tools for the [Arcade 60 fps plan](../../website/docs/next-steps/arcade-60fps-plan.md).
They need the board on `/dev/ttyACM0` and the retro-go Docker build image.

| Script | What it does |
|---|---|
| `mamebench.sh <JIT 0\|1> <rom> [secs]` | Builds mame-go with `MAMEBENCH` + `NEOPROF` (and `M68KJIT=<JIT>`), installs it through the SD updater, resumes save slot 0 of `<rom>` and prints the hash and profile lines. Env: `NOBUILD=1` skips the build, `RESUME=0` cold-boots, `MAMEPROF=1` (or `core1`) turns on the sampling profiler. |
| `mbsum.py <log>` | The 7 MAMEBENCH hashes and the average ms per frame (68000, video, other, core 0). |
| `profsym.sh <log> [n]` | Turns the `MAMESAMPLE` lines of a `MAMEPROF=1` run into a per-function profile (addr2line on `mame-go/build/mame-go.elf`). |
| `wait_launcher.py` | Waits until the launcher answers `ping`. |

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
