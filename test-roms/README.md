# Test ROMs

One folder per system, mirroring `/roms/<system>/` on the SD card (the
launcher only scans `/roms/<tab short name>`, so the folder names are the
short names: `md/` not `gen/`). **No ROM is committed**
— the whole tree is git-ignored except this README and one `.gitkeep` per
folder; drop your own copies here (free homebrew or your bench ROMs) and
upload to the card without pulling it:
`scripts/board_ctl.py put test-roms/<sys>/<file> "/sd/roms/<sys>/<file>"`
(from the launcher, ~38 KB/s).

| Folder | Core (app) | Extensions | Status on the first article |
|:---|:---|:---|:---|
| `nes/` | nofrendo (retro-core) | .nes .fds | 60 fps ✅ |
| `snes/` | snes9x (retro-core) | .sfc .smc | 60 fps ✅ (seven bench scenes) |
| `gb/`, `gbc/` | gnuboy (retro-core) | .gb .gbc | 60 fps ✅ |
| `sms/`, `gg/` | smsplus (retro-core) | .sms .gg | 60 fps ✅ |
| `pce/` | pce-go (retro-core) | .pce .zip (PC Engine and TurboGrafx-16 both go here) | 60 fps ✅ (Reflectron; Street Fighter II' CE 2026-09-26, audio at 32 kHz) |
| `md/` | gwenesis | .bin .md .gen | 60 fps ✅ (YM2612 on core 1) — folder is `md/`, not `gen/`: the launcher only scans `/roms/<tab short name>` |
| `col/` | smsplus (retro-core) | .col .rom | 60 fps ✅ (2026-09-21, pacman.col) |
| `doom/` | prboom-go | .wad | `freedoom1.wad` runs at 35 fps (2026-09-21) but the heap drops steadily (7.2 → 2.0 MB in 20 s) — watch for OOM |
| `sg1/` | smsplus (retro-core) | .sg .sg1 (a `.rom` must be renamed `.sg`) | 60 fps ✅ (2026-09-21, GP World + Gulkave) — needed the `sg1` → `sms_main()` dispatch in retro-core `main.c`, missing since 2026-09-14 |
| `ngp/` | RACE (retro-extra) | .ngp .ngc | 60 fps ✅ (2026-09-21, Metal Slug 1st Mission, BUSY 75-99%) |
| `duke3d/` | duke3d-go | .grp (+ the other Duke3D 1.3D/1.5 data files in the same folder) | boots to the menus (2026-09-26); menu rendering fix pending verification |
| `wolf3d/` | wolf3d-go | shareware v1.4 `.WL1` files in `wolf3d/data/`, plus a small `Wolfenstein 3D.wl1` at the top to pick in the launcher | 62 fps in E1M1 (2026-09-27) |
| `quake/` | quake-go | `id1/pak0.pak` (shareware); add `id1/pak1.pak` for the registered game | built, not yet run |
| `arcade/` | mame-go (MAME 0.37b5) | .zip (MAME ROM sets; modern sets with renamed files are matched by CRC) | 60 fps ✅ Pac-Man, 1942, Robby Roto; 57 fps (native) ✅ Exidy/Circus free ROMs from mamedev.org; 1943 60 emulated / ~25 drawn — see [Arcade (MAME)](../website/docs/next-steps/arcade.md) |
| `cps1/` | mame-go (Capcom CPS1) | .zip — **on the card they go in `/roms/arcade/`** (Arcade tab) | PC harness only so far (Final Fight, SF2 CE, Knights, Ghouls, Carrier Air Wing) |

`scripts/emu_check.py` launches the first ROM of every folder that has one
and reads the FPS/BUSY line, so a new system is covered as soon as its
folder is populated on the card.

Some SNES bench ROMs currently sit in `nes/` (they were dropped there);
the SD copies are in `/roms/snes/`.

The desktop simulator (`./scripts/sim-run.sh run`) mounts this directory too.
