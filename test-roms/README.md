# Test ROMs

One folder per system, mirroring `/roms/<system>/` on the SD card. Only free
homebrew/test ROMs are committed; everything else is ignored by pattern
(`.gitignore`). Upload to the card without pulling it:
`scripts/board_ctl.py put test-roms/<sys>/<file> "/sd/roms/<sys>/<file>"`
(from the launcher, ~38 KB/s).

| Folder | Core (app) | Extensions | Status on the first article |
|:---|:---|:---|:---|
| `nes/` | nofrendo (retro-core) | .nes .fds | 60 fps ✅ |
| `snes/` | snes9x (retro-core) | .sfc .smc | 60 fps ✅ (seven bench scenes) |
| `gb/`, `gbc/` | gnuboy (retro-core) | .gb .gbc | 60 fps ✅ |
| `sms/`, `gg/` | smsplus (retro-core) | .sms .gg | 60 fps ✅ |
| `pce/` | pce-go (retro-core) | .pce | 60 fps ✅ |
| `gen/` | gwenesis | .bin .md .gen | 60 fps ✅ (YM2612 on core 1) |
| `lynx/` | handy (retro-core) | .lnx | untested — drop a ROM here |
| `gw/` | gw-emulator (retro-core) | .gw | untested — drop a ROM here |
| `col/` | smsplus (retro-core) | .col .rom | untested — drop a ROM here |
| `msx/` | fmsx | .rom .mx1 .mx2 .dsk | untested — drop a ROM here |
| `doom/` | prboom-go | .wad | `freedoom1.wad` (Freedoom 0.13.0, free) — untested |

`scripts/emu_check.py` launches the first ROM of every folder that has one
and reads the FPS/BUSY line, so a new system is covered as soon as its
folder is populated on the card.

Some SNES bench ROMs currently sit in `nes/` (they were dropped there);
the SD copies are in `/roms/snes/`.

The desktop simulator (`./scripts/sim-run.sh run`) mounts this directory too.
