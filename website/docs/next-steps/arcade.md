---
id: arcade
title: Arcade (MAME)
sidebar_position: 2
---

# Arcade (MAME)

Full MAME is far too large for a microcontroller, but the classic 8-bit
arcade boards are within reach, the same class of work as the home
consoles in [More Systems](/docs/next-steps/more-systems).

| Tier | Boards | Approach |
|:---|:---|:---|
| 🟢 **Should fit** | Pac-Man, Galaga, Donkey Kong, Space Invaders, Frogger and similar Z80 / 6502 / 8080 boards of 1978–84 | Port the drivers one by one from an old, small MAME release, or follow the approach of ESP32 projects that already run a handful of these games |
| 🟡 **Hard** | 68000 boards (Sega System 16, Capcom CPS1) | One 10 MHz 68000 plus sound CPUs: the Genesis core shows this is at the edge |
| 🔴 **No** | CPS2, Neo Geo MVS, 3D boards | CPU load and ROM size, as for the home consoles in [More Systems](/docs/next-steps/more-systems) |

## On the current console (v3)

- **Where it lives:** a new retro-go app in the ~8 MB of free flash.
- **Which code:** either the drivers of an old, small MAME release (the
  0.37-era codebase used on low-end devices), compiled with only the
  chosen drivers so the app stays within a few MB, or one-by-one ports of
  individual games, as existing ESP32 arcade projects do.
- **What fits:** Z80 / 6502 / 8080 boards of 1978–85 run comfortably
  (lighter than the NES / SMS cores already at 60 fps); CPS1 is at the
  limit (see [More Systems](/docs/next-steps/more-systems#sega-family-and-mame-on-the-current-console-v3));
  CPS2 and Neo Geo do not fit (ROM sizes beyond the 8 MB PSRAM).
- **Controls:** the 12 buttons cover joystick, 1–3 fire buttons, coin
  (Select) and start.
- **Proof:** the same `emu_check.py` measurement on 3 reference games per
  board family.

## Board families, not single games

Every arcade game runs on a specific board, and many games share the same
one: the Capcom CPS1 board, for example, runs Street Fighter II, Final
Fight, Ghouls'n Ghosts and dozens more. **Feasibility is decided per board
family**; if v3 runs the board, it runs nearly all of its games. The few
exceptions inside a family are ROM sets too large for the PSRAM or a
special chip on one title.

**How to tell which board and CPU a game uses:** look the game up on the
Arcade Database (adb.arcadeitalia.net) or the Killer List of Videogames
(arcade-museum.com), or run `mame -listxml <game>`. Rule of thumb: a Z80,
6502, 8080 or 6809 at up to ~4 MHz, 1978–85, is classic and fits v3; a
68000 (CPS1, Sega System 16, Neo Geo) is the 16-bit tier, at the limit or
beyond.

## Classic games (8-bit boards)

| CPU | Games |
|:---|:---|
| **Intel 8080 / 8085** | Space Invaders (Taito, 1978), Lunar Rescue (Taito, 1979), Phoenix (Amstar, 1980, 8085) |
| **Zilog Z80** | Galaxian (Namco, 1979), Pac-Man (Namco, 1980), Crazy Climber (Nichibutsu, 1980), Galaga (Namco, 1981), Donkey Kong (Nintendo, 1981), Frogger (Konami, 1981), Scramble (Konami, 1981), Lady Bug (Universal, 1981), Ms. Pac-Man (Midway, 1982), Donkey Kong Jr. (Nintendo, 1982), Dig Dug (Namco, 1982), Xevious (Namco, 1982), Pengo (Sega, 1982), Zaxxon (Sega, 1982), Mr. Do! (Universal, 1982), Time Pilot (Konami, 1982), Pooyan (Konami, 1982), Moon Patrol (Irem, 1982), Popeye (Nintendo, 1982), Mario Bros. (Nintendo, 1983), Bomb Jack (Tehkan, 1984), 1942 (Capcom, 1984), Commando (Capcom, 1985) |
| **MOS 6502** | Super Breakout (Atari, 1978), Asteroids (Atari, 1979, vector), Lunar Lander (Atari, 1979, vector), Missile Command (Atari, 1980), Centipede (Atari, 1981), Tempest (Atari, 1981, vector), BurgerTime (Data East, 1982) |
| **Motorola 6809** | Defender, Robotron: 2084, Joust (Williams): same era and weight, a different CPU to emulate |

Vector games (Asteroids, Tempest, Lunar Lander) drew lines instead of
pixels: they emulate fine but need a line rasteriser on top.

## Development on v3: decisions (2026-09-26)

| Decision | Choice | Why |
|:---|:---|:---|
| **Code base** | **mame2000** (MAME 0.37b5, the libretro port used on low-end handhelds) | written in C, 426 drivers including Pac-Man, Galaga, Donkey Kong, Galaxian, Scramble, Space Invaders (8080bw), Centipede, Exidy and Astrocade; built with only the chosen drivers so it fits the free flash |
| **License** | **non-commercial project** | MAME 0.37's license forbids use in a commercial product without the authors' written permission; non-commercial use is allowed if the full source of the port is published. Recent MAME is GPL / BSD but C++ and far too large for the ESP32. A console for sale would need drivers written from scratch |
| **First milestone** | **Pac-Man at 60 fps on the board** | the simplest and best-known Z80 board; the ROM set (`pacman.zip`, 0.37b5 set) comes from the user |
| **Free test ROMs** | Robby Roto (Z80, Bally Astrocade board) and the Exidy games (6502: Targ, Spectar, Side Trak, Teeter Torture) | published by the MAME team with the owners' permission, for download from mamedev.org only |

**ROMs.** Arcade ROMs are copyrighted. For testing, the MAME team
publishes a few games whose owners allowed free distribution (on
mamedev.org), for example Gridlee and Robby Roto.

## Status on the board (2026-09-26)

The arcade app runs on article 0003: **`mame-go`**, a retro-go app on its
own 2 MB partition (launcher tab **Arcade (MAME)**, ROMs in
`/sd/roms/arcade/`). Source: `retro-go/mame-go/` in the fork; what was
changed in the MAME code is listed in
`mame-go/components/mame2000/README_MAMEGO.md`.

| Game | Board / CPU | Measured on the board | Notes |
|:---|:---|:---|:---|
| Pac-Man | Namco, Z80 | ✅ 60 fps | the user's `pacman.zip` (Midway set, driver `pacmanm`) |
| 1942 | Capcom, 2× Z80 + 2× AY8910 | ✅ 60 fps | `1942a.zip` holds set 1 under modern file names: loaded by CRC |
| 1943 | Capcom, 2× Z80 + 2× YM2203 | ✅ 60 emulated fps, ~25 drawn | Euro revision, added to the driver as `1943e`; auto frameskip keeps speed and audio right |
| Robby Roto | Bally Astrocade, Z80 | ✅ 60 fps | was 28 fps: line renderer fast path, same frames |
| Targ, Spectar, Side Trak, Hard Hat | Exidy, 6502 | ✅ 57 fps (native rate) | free ROMs, mamedev.org |
| Circus, Crash, Rip Cord, Robot Bowl | Exidy Circus, 6502 | ✅ 57 fps (native rate) | Circus was 40 fps: overlay colours 33022 → 510, same frames |
| Starfire, Fire One | Exidy, Z80 | ✅ 57 fps | free ROMs |
| Fax | Exidy, 6502 | ❌ stuck on its EPROM test | the mamedev.org dump is a different ROM set from 0.37b5 |
| Victory | Exidy, Z80 + 6502 | ❌ interrupt self-test fails | 0.37b5 driver |
| Galaga, Donkey Kong (Jr, 3), Galaxian, Moon Cresta, Frogger, Scramble | Namco / Nintendo / Konami | compiled, **not tested** | no ROMs on the card yet |

What the app does besides running the games:

- **ROM sets:** the zip picked in the launcher is matched to a driver by
  file names and CRCs, so modern sets with renamed files load, and it is
  read whatever its name.
- **Save states** from the retro-go menu and *Resume* from the launcher
  (CPU contexts, interrupts, timer scheduler, CPU RAM; a state loads only
  on the firmware that wrote it). **Hiscores** saved on the card
  (`hiscore.dat` in `/sd/retro-go/mame/mame2000/`).
- **Display 1:1** by default (224×288 Pac-Man centred; a non-integer
  upscale doubled every ninth line of the maze), changeable in the options.
- **Audio at 32000 Hz** like the other apps (at 22050 Hz the music ignored
  the volume setting).
- **Driver tables in flash:** they are `const`, so adding drivers does not
  eat internal RAM (214 KB → 50 KB of initialised data).

## 16-bit boards on v3: the user's ROMs (2026-09-26)

| Game | Hardware | On the board |
|:---|:---|:---|
| **Blood Bros.** | 68000 10 MHz + Seibu sound (Z80, YM3812, OKI6295) | ✅ runs: 55–58 emulated fps, ~19 drawn |
| **Aero Fighters** | 68000 10 MHz + Z80 + YM2610 | ✅ runs: ~45 emulated fps, ~15 drawn (played for a minute, no crash) |
| **Out Run** | 2× 68000 12.5 MHz + Z80 + YM2151 + SegaPCM, sprite-scaled road | ❌ beyond the ESP32-S3 |
| **Sonic Wings 2** | Neo Geo (68000 + Z80 + YM2610), 7 MB zipped + BIOS | ❌ ROMs larger than the 8 MB PSRAM |

The 68000 (MAME's Musashi core) is fast enough; memory was the wall.
Measured after start-up with everything in PSRAM: Aero Fighters 2.0 MB of
program/sound ROMs + **7.0 MB of decoded graphics**, Blood Bros. 0.8 +
4.3 MB, against 7.0 MB of free PSRAM. Blood Bros. first stopped with
"Out of memory decoding gfx", Aero Fighters crashed during start-up.
Solved in two blocks, both checked frame by frame against the fully
decoded build:

1. **Tile cache.** Graphics sets larger than 256 KB are no longer expanded
   to 1 byte per pixel: the raw ROM stays and tiles are decoded on demand
   into a 192 KB cache per set. Tiles used in the current frame are never
   evicted; multi-tile sprites get a contiguous copy per frame.
2. **ROM regions in flash.** Graphics and sound-sample regions of 256 KB
   and more are moved, after the driver's own init, to a 4 MB `mamerom`
   flash partition and read memory-mapped. The first start of a game
   writes them (a few seconds); later starts only compare and map.

Free PSRAM while playing: Blood Bros. 1.8 MB, Aero Fighters 2.6 MB. Speed
is the next limit (the emulation runs at 75–95 %), not memory.
