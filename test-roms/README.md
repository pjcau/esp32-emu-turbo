# Test ROMs

One folder per system, mirroring `/roms/<system>/` on the SD card (the
launcher only scans `/roms/<tab short name>`, so the folder names are the
short names: `md/` not `gen/`, `lnx/` not `lynx/`). **No ROM is committed**
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
| `pce/` | pce-go (retro-core) | .pce | 60 fps ✅ |
| `md/` | gwenesis | .bin .md .gen | 60 fps ✅ (YM2612 on core 1) — folder is `md/`, not `gen/`: the launcher only scans `/roms/<tab short name>` |
| `lnx/` | handy (retro-core) | .lnx | untested — drop a ROM here (folder is `lnx/`, not `lynx/`) |
| `gw/` | gw-emulator (retro-core) | .gw | untested — drop a ROM here |
| `col/` | smsplus (retro-core) | .col .rom | 60 fps ✅ (2026-09-21, pacman.col) |
| `msx/` | fmsx | .rom .mx1 .mx2 .dsk | `Road Fighter` on the card (2026-09-21): boots but draws nothing (R:0) — **needs `/bios/msx/MSX.ROM`, `MSX2.ROM`, `MSX2EXT.ROM`**, not on the card yet |
| `doom/` | prboom-go | .wad | `freedoom1.wad` runs at 35 fps (2026-09-21) but the heap drops steadily (7.2 → 2.0 MB in 20 s) — watch for OOM |
| `sg1/` | smsplus (retro-core) | .sg .sg1 (a `.rom` must be renamed `.sg`) | 60 fps ✅ (2026-09-21, GP World + Gulkave) — needed the `sg1` → `sms_main()` dispatch in retro-core `main.c`, missing since 2026-09-14 |
| `ngp/` | RACE (retro-extra) | .ngp .ngc | 60 fps ✅ (2026-09-21, Metal Slug 1st Mission, BUSY 75-99%) |
| `a26/` | Stella (retro-extra) | .a26 .bin | added 2026-09-14 (stella-odroid-go), untested |
| `duke3d/` | duke3d-go | .grp (+ the other Duke3D 1.3D/1.5 data files in the same folder) | added 2026-09-14, untested; shareware 1.3D works |

`scripts/emu_check.py` launches the first ROM of every folder that has one
and reads the FPS/BUSY line, so a new system is covered as soon as its
folder is populated on the card.

Some SNES bench ROMs currently sit in `nes/` (they were dropped there);
the SD copies are in `/roms/snes/`.

The desktop simulator (`./scripts/sim-run.sh run`) mounts this directory too.
