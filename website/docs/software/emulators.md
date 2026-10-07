---
id: emulators
title: Emulators — Tests and Speed
sidebar_position: 3
---

# Emulators — tests and speed

What runs on the board, which game it was checked with, and how fast it goes.
Every figure was measured on the v4.9.0 first article, from the `BUSY:x% FPS:t (S:s R:r)`
line `rg_system` prints once a second on the USB console (t = emulated frames
a second, s = skipped, r = drawn) or from an emulator's own profile line.

**How to read it.** *Full speed* means the game runs at its machine's own rate
(60, 50 for PAL, or the engine's rate for the PC ports). Not every emulated frame
is drawn: most cores draw one in two at full speed, which is still smooth on
this screen. *Busy* is how much of the main core the emulator takes.

## Consoles and handhelds

| System | App (core) | Checked with | Speed on the board | Date |
|:---|:---|:---|:---|:---|
| NES | retro-core (nofrendo) | Super Mario Bros., Owlia | ✅ 60 fps, busy 36–39 %, 55–60 drawn | 2026-10-03 |
| Game Boy | retro-core (gnuboy) | Tetris | ✅ 60 fps, busy 34 % | 2026-09-27 |
| Game Boy Color | retro-core (gnuboy) | Space Invaders, ucity | ✅ 60 fps, busy 35–53 % | 2026-09-27 |
| Master System | retro-core (smsplus) | Sonic, Silver Valley | ✅ 60 fps, busy 35 % | 2026-09-27 |
| Game Gear | retro-core (smsplus) | Shinobi II and 5 more | ✅ 60 fps, busy 31–41 % | 2026-10-03 |
| SG-1000 | retro-core (smsplus) | GP World | ✅ 60 fps, busy 33 % | 2026-09-27 |
| ColecoVision | retro-core (smsplus) | Pac-Man | ✅ 60 fps, busy 31 % | 2026-09-27 |
| PC Engine | retro-core (pce-go) | Street Fighter II' CE, OutRun | ✅ 60 fps, busy 33–43 % | 2026-10-03 |
| SNES | retro-core (snes9x 2005) | 7 benchmark scenes, Donkey Kong Country | ✅ 60 fps on every scene, 19–28 drawn, busy 80 % | 2026-10-04 |
| SNES Mode 7 | retro-core (snes9x) | Super Mario Kart | ✅ 57–62, mostly 60 | 2026-09-28 |
| SNES SuperFX | retro-core (snes9x + GSU) | Star Fox | 🟡 53–60 fps, 7–10 drawn | 2026-09-27 |
| Atari Lynx | retro-core (handy) | 5 PD demos | ✅ 56–60 fps | 2026-10-03 |
| Mega Drive | gwenesis | Sonic, Miniplanets | ✅ 60 fps, 30 drawn, busy 85 % | 2026-10-03 |
| Game Boy Advance | gbsp (gpSP + Xtensa dynarec) | Sonic Advance, Metal Slug Advance, TMNT | 🟡 56–60 in play (Sonic 56, Metal Slug 46–56, TMNT 49–59); Mario Kart 44–51 | 2026-10-03 |
| Atari 2600 | retro-extra (Stella) | Halo 2600, Donkey Kong, Asteroids | ✅ 60 fps (50 PAL), busy 30–68 % | 2026-10-03 |
| Neo Geo Pocket | retro-extra (RACE) | Metal Slug 1st Mission and 7 more | ✅ 60 fps, busy 70–89 % | 2026-10-03 |
| Atari 5200 | retro-home (Atari800 via MCUME) | Galaxian, Pole Position, Space Invaders | ✅ 60 fps, busy 33 % | 2026-10-08 |
| Atari 7800 | retro-home (ProSystem) | Donkey Kong | 🟡 50 of 60 fps (was 42) | 2026-10-08 |
| Commodore 64 | retro-home (Teensy64 + reSID) | Ghostbusters (.d64) | ✅ 50 fps (PAL), busy 70 % | 2026-10-08 |
| MSX 1 / MSX 2 | fmsx (fMSX) | Nemesis, Metal Gear 2 | ✅ 60 fps, busy 21–26 % | 2026-10-07 |

## Arcade

| Board | App | Checked with | Speed on the board | Date |
|:---|:---|:---|:---|:---|
| 8-bit boards (Z80, 6502...) | mame-go (MAME 0.37b5) | Pac-Man, 1942, Robby Roto | ✅ 60 fps | 2026-09-27 |
| 68000 boards | mame-go | Blood Bros., Aero Fighters | ✅ Blood Bros. 60; 🟡 Aero Fighters 47–57 | 2026-09-28 |
| Neo Geo | mame-go | Metal Slug, Metal Slug 2, KOF95 | 🟡 Metal Slug 58 game fps; Metal Slug 2 and KOF95 52–55 | 2026-10-06 |
| Capcom CPS1 | mame-go | Final Fight, Street Fighter II CE | 🟡 Final Fight about 55, SF2 38–47 in a fight | 2026-10-08 |
| Sega System 16 | mame-go | Golden Axe, Alien Syndrome, Wonder Boy III | 🟡 54, 58, 57 | 2026-10-06 |

## PC games and native ports

| Game | App | Speed on the board | Date |
|:---|:---|:---|:---|
| DOOM (Freedoom) | prboom-go | ✅ 35 fps, the engine's rate | 2026-09-27 |
| Wolfenstein 3D (shareware) | wolf3d-go | ✅ 62 fps, busy 34 % | 2026-09-27 |
| OpenTyrian | opentyrian-go | ✅ 36 fps (engine rate 35), busy 30 % | 2026-09-27 |
| OutRun (Cannonball) | sdapp, from the SD card | ✅ 30 fps, the engine's rate | 2026-10-04 |
| Arcade 3D Racing | retro-extra | ✅ 47–64 fps | 2026-10-04 |
| Duke Nukem 3D, Quake | — | out of the flash since 2026-10-05 (were 48–53 and 34–41 fps) | |
| Super Mario 64, Mario Kart 64 | — | out of the flash since 2026-10-07: [Nintendo 64 through native ports](/docs/next-steps/n64-native-ports) | |

## The check every release gets

Before a build is recorded as a release, one game per launcher tab is started
from the console and checked on the webcam; then SELECT, START, A, START and
RIGHT are pressed and the game must react. The last such check (22 tabs plus
the four home systems) is in [Firmware → Current build](/docs/software/firmware#current-build).

The tools: `scripts/emu_check.py` starts each core's test game and averages
the stats line; `scripts/snes_bench.py` resumes the seven SNES scenes from save
states; `scripts/mamebench/` runs the arcade benchmarks (`MAMEBENCH`,
`MAMEPROF`); a webcam (`scripts/board_cam.py`) checks the picture.

## Buttons

The handheld has a D-pad, A, B, X, Y, START, SELECT, L, R, MENU and OPTION.
MENU opens retro-go's game menu (save, load, quit), OPTION its options. The
consoles use their own pad on the same buttons; the systems with more keys:

| System | Mapping |
|:---|:---|
| Arcade | B / A / Y / X / L / R = buttons 1–6, SELECT coin, START start |
| Atari 7800 | A (and X) button 1, B button 2, START console Reset, SELECT Select, Y Pause, L / R flip the difficulty switches |
| Atari 5200 | A fire, B side button, START, SELECT alone Pause; keypad X 1, Y 2, L *, R #; SELECT held + X, Y, A, B 3–6, + UP, RIGHT, DOWN, LEFT 7, 8, 9, 0, + L Reset |
| Commodore 64 | D-pad + A or B joystick in port 2 (L swaps to port 1), START SPACE, SELECT RUN/STOP, X F1, Y F3, R RETURN; options menu: *Type key* for any other key |
| MSX | A / B fire, X SPACE, Y RETURN, L F1, R ESC, SELECT on-screen keyboard, START fMSX's menu |

## System files on the card

No ROM is kept in any repository; the emulator that misses a required file
says which one and where.

| System | File | |
|:---|:---|:---|
| Atari 5200 | `/retro-go/bios/5200.rom` | required |
| Atari 7800 | `/retro-go/bios/7800 BIOS (U).rom` or `(E).rom` | optional |
| Commodore 64 | `/retro-go/bios/c64/kernal.rom`, `basic.rom`, `chargen.rom` | required |
| MSX | `/retro-go/bios/msx/MSX.ROM` | required |
| MSX 2 | `MSX2.ROM` + `MSX2EXT.ROM` of the same version | MSX2 games (C-BIOS's `MSX2.ROM` with a real `MSX2EXT.ROM` gives a black screen; without them fMSX starts as an MSX1) |
| NES FDS, GB, GBC | `/retro-go/bios/fds_bios.bin`, `gb_bios.bin`, `gbc_bios.bin` | optional |
| Neo Geo | `neogeo.zip` in the Neo Geo games folder | required |

## Limits worth knowing

- **Commodore 64:** no 1541 drive. A game is loaded from its `.prg`, or the
  first program of a `.d64`, and started by itself; games that load more parts
  from the disk stop after the first, and saving to disk does not work.
- **Atari 5200:** cartridges of 8, 16 and 32 KB (nearly all); not the
  bank-switched ones of 64 KB and more.
- **SNES:** SA-1 games do not run.
- **Amiga:** not available. The only microcontroller Amiga emulator (MCUME's
  UAE) needs a 600 MHz Teensy 4.1; this chip runs at 240 MHz.
- Open defects by emulator: [Remediation — Emulators](/docs/remediation/emulators).
