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
| 🟡 **Runs, at part speed** | Neo Geo MVS (unencrypted sets, up to ~50 MB) | Sprites and large sample ROMs paged from the SD card; see [Neo Geo on v3](#neo-geo-on-v3-sprites-paged-from-the-sd-card-2026-09-27) |
| 🔴 **No** | CPS2, encrypted Neo Geo sets (KOF '99 and later), 3D boards | CPU load, encryption this MAME version lacks, 3D hardware |

## On the current console (v3)

- **Where it lives:** a new retro-go app in the ~8 MB of free flash.
- **Which code:** either the drivers of an old, small MAME release (the
  0.37-era codebase used on low-end devices), compiled with only the
  chosen drivers so the app stays within a few MB, or one-by-one ports of
  individual games, as existing ESP32 arcade projects do.
- **What fits:** Z80 / 6502 / 8080 boards of 1978–85 run comfortably
  (lighter than the NES / SMS cores already at 60 fps); CPS1 is at the
  limit (see [More Systems](/docs/next-steps/more-systems#sega-family-and-mame-on-the-current-console-v3));
  CPS2 does not fit; Neo Geo runs at part speed with its large ROMs
  paged from the SD card (see [below](#neo-geo-on-v3-sprites-paged-from-the-sd-card-2026-09-27)).
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
| Fax, Victory | Exidy | ❌ removed from the card and `test-roms/` (2026-09-27) | Fax: the mamedev.org dump is a different ROM set from 0.37b5; Victory: interrupt self-test fails with the 0.37b5 driver |
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
| **Blood Bros.** | 68000 10 MHz + Seibu sound (Z80, YM3812, OKI6295) | ✅ **60 fps** (full speed) after the idle-loop speed-up, ~20 drawn (was 55–58) |
| **Aero Fighters** | 68000 10 MHz + Z80 + YM2610 | ✅ 47–57 emulated fps after the speed-up, ~18 drawn (was ~45) |
| **Out Run** | 2× 68000 12.5 MHz + Z80 + YM2151 + SegaPCM, sprite-scaled road | ❌ beyond the ESP32-S3 |
| **Sonic Wings 2** | Neo Geo (68000 + Z80 + YM2610), 7 MB zipped + BIOS | ✅ 38–50 emulated fps since 2026-09-27, with sprites paged from the SD card (it needs ~11 MB, and only 4 MB of flash were free); see [Neo Geo on v3](#neo-geo-on-v3-sprites-paged-from-the-sd-card-2026-09-27) |

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

**Speed (2026-09-26, measured on the board 2026-09-27: Blood Bros. 60,
Aero Fighters 47–57):** both games spend a large share of the 68000's time in a loop
that polls a vblank flag (Aero Fighters `0B84: cmpi.b #1,$FF8055 / bcs`,
about 4000 passes per frame; Blood Bros. `0988: btst #7,$8004C / beq`). A
MAME-style speed-up handler now stops the 68000 until the interrupt
instead: the 68000's instruction count roughly halves (Aero Fighters 42 →
20 million instruction fetches over 1800 frames), with identical frames.
The Z80 sound CPU has no dominant idle loop. Remaining costs: YM2610 FM
synthesis, the 8 → 16 bpp screen conversion, the 68000 itself.

## Neo Geo on v3: sprites paged from the SD card (2026-09-27)

Aero Fighters 2 / Sonic Wings 2 runs on the board (fork `d0430d65`): 38–50
emulated fps in game, 16 frames drawn per second, CPU at 100% (68000 + Z80 +
YM2610), audio at 32 kHz.

**How it fits in 8 MB of PSRAM**

| Part | Sonic Wings 2 | Where it lives |
|:---|:---|:---|
| Sprites (C ROMs) | 8 MB | Converted once (first launch, 51 s) into `/sd/retro-go/mame/mame2000/neospr/<game>_gfx<n>.spr`: tiles already decoded + their `pen_usage`. Read through an LRU cache of 8 KB pages in PSRAM (864 KB here); transparent tiles never touch the card. ~40 page reads per 600 frames, worst frame 11 |
| Sound samples (V ROMs) | 3 MB | Written straight to the `mamerom` flash partition file by file while loading, never allocated in PSRAM |
| Program (P), BIOS, Z80, text layer | 2.4 MB | PSRAM |

The paged build draws **bit-identical frames** to the sprites-in-RAM build
(PC harness, 3000 frames, caches of 256 KB to 9 MB). Modern ROM sets load:
the newer `sfix.sfix` BIOS dump is accepted and the rest is matched by CRC.

**Games of 30–50 MB (2026-09-27, fork `643adbb2`)**

Metal Slug 2 (49 MB: 3 MB program, 8 MB samples, 32 MB sprites) runs on
the board: 47–50 emulated fps on the title, 28–33 in game (CPU-bound, see
below). What made it fit:

| Part | Where it lives |
|:---|:---|
| Sprites (any size) | `.spr` on the SD, 8 KB-page cache in PSRAM (2.3 MB here) |
| Samples up to 3.5 MB | `mamerom` flash partition, streamed there while loading |
| Samples above 3.5 MB | `<game>_snd<n>.pcm` on the SD, 512 KB cache of 4 KB pages read by the YM2610 (~130 page reads per 600 frames in play) |
| Program ≥ 1 MB | the flash partition when the samples left it free (pointers rebased after the move) |
| Program of 5 MB (Shock Troopers, KOF '97, Last Blade) | first MB (fixed at 0x000000) in PSRAM, the 4 MB banked part in the flash partition; the samples are then always paged from the SD |

The conversion reads the zip 64 KB at a time (8 MB ROM files never sit in
memory). On the board it is slow the first time (Metal Slug 2: ~5 min); on
the PC it takes seconds with the same code:

```bash
python3 scripts/neogeo_prepare.py test-roms/neogeo/*.zip
cp -r build/neogeo-prepare/sys/mame2000/neospr /media/<card>/retro-go/mame/mame2000/
```

**Folder:** Neo Geo games have their own launcher tab, **Neo Geo**
(`/sd/roms/neogeo/`, same mame-go app). Put `neogeo.zip` (the BIOS:
`sp-s2.sp1`, `sfix.sfix`, `sm1.sm1`, `000-lo.lo`) there too, for the sets
that do not include it (Puzzle Bobble 2). Art: rxbrad/es-theme-gbz35.

**Limits on the board today**

- Speed (Metal Slug 2 in play, `NEOPROF=1` build, ms per emulated frame):

  | Step | ms/frame | emulated fps |
  |:---|:---|:---|
  | start | ~34 | 29 |
  | YM2610 once per frame (fast_sound) | 32.1 | 31 |
  | YM2610 synthesis on core 1 (register-write queue, one frame of latency) | 28.6 | 35 |
  | generic 68000 idle-loop skip | 25.9 | 39 |
  | generic Z80 idle-loop skip | 25.3 | 39 |
  | palette lookup + display copy on core 1 (second screen bitmap) | 23.6 | 42 |

  All generic for the Neo Geo (no per-game speed-ups): a short backward loop
  that repeats with the same registers and the same RAM writes, and writes
  nothing to I/O, gives away the rest of its timeslice. Left on core 0:
  68000 12, video 5, Z80 4, other 2.2 ms. Next: the sprite renderer on
  core 1 (needs the per-frame palette recalculation moved with it).
- `init_mgd2` sets reorder their sprites in memory and are not paged yet.
- Encrypted sets (KOF '99 and later, Metal Slug 3+) need decryption this
  MAME version does not have.
- Save states restore Neo Geo games exactly (fork `ec8acd7b`): see
  *Save states* below.

**Sprites on core 1 (2026-09-27 evening, fork `15e1790f`, PC-verified,
board pending).** The sprite + fix-layer renderer (~5 ms of core 0 in
Metal Slug 2) runs in the present task on core 1, one frame behind; core 0
keeps the MAME palette bookkeeping (global state). The renderer reads a
copy of the video RAM refreshed from the 256-byte blocks written during the
frame (a few hundred words, not 67 KB). Only with paged sprites. On the PC
harness, with a present step that also runs one frame late: frames and
audio identical to the inline renderer on Metal Slug 2, Shock Troopers
(16-bit) and Thrash Rally, Sonic Wings 2, Magician Lord (8-bit).

### What was changed in mame-go for Neo Geo

Fork commits `d0430d65` and `643adbb2`. Every change was checked on the PC
harness against the build that keeps everything in RAM: frames and audio
are identical.

| Change | Problem it solves |
|:---|:---|
| **Sprite pages on the SD** (`mamego_neospr.c`): C ROMs converted once into `.spr` files (decoded tiles + `pen_usage`), read through an LRU cache of 8 KB pages sized from the free PSRAM | 8–32 MB of sprites against 8 MB of PSRAM; transparent tiles are skipped without touching the card |
| **Samples to flash while loading** (`common.c`): V ROMs written file by file straight to the `mamerom` partition | a 3 MB sample region plus a 2 MB unzipped file did not fit next to the program |
| **Samples paged from the SD** (`<game>_snd<n>.pcm`, 512 KB cache of 4 KB pages, read by the YM2610's ADPCM-A/B) | sample sets larger than the 3.5 MB flash partition (Metal Slug 2: 8 MB) |
| **Program ROM in flash** (`memory_rebase()` moves every CPU pointer onto the flash copy) | frees 3 MB of PSRAM on Metal Slug 2 for a larger sprite cache |
| **Streamed unzip** (`zipstream_*`, 64 KB at a time) | 8 MB ROM files never sit in memory during the conversion |
| **ROM-set matching**: `neogeo.zip` next to the game, the newer `sfix.sfix` BIOS dump, optional ROMs read correctly, a "later set" driver `sonicwi2m` | modern zips and sets without the BIOS load |
| **8 open files** instead of 4 (`rg_storage`) | Metal Slug 2 keeps 3 open while playing; the conversion needed 5 |
| **PC preparation** (`tools/neoprep.c`, `scripts/neogeo_prepare.py`) | the same conversion code runs in seconds on the PC instead of minutes on the board |
| **Neo Geo launcher tab** (`/sd/roms/neogeo/`) | Neo Geo games separate from the 8-bit arcade games |
| **Exact save states** (`neogeo_mamego_state()` in `drivers/neogeo.c`, `YM2610_state()` in `fm.c`, `AY8910_state()`) | the generic mame-go state saved only the CPU regions: Neo Geo keeps its work RAM, video RAM, palettes, latches and sound chip elsewhere, and its program ROM is in flash |
| **Per-game fixes for modern sets** (`neogeo_name()` in `machine/neogeo.c`; the generator copies the 0.37b5 flags) | a modern set named `<name>m` missed the 153 name-keyed fixes of `<name>`: Metal Slug 2 and KOF '95 stopped at the warning screen (no SRAM protection hack), and no set got its `NEO_CYCLE_R` speed-up |

### Save states

A Neo Geo state (~506 KB) holds the CPU contexts and scheduler (as for every
mame-go board), the Z80 region, and from the driver: 64 KB work RAM, the
68 KB of video RAM in use, both palette banks and which one is active, the
64 KB backup RAM, the memory card, the IRQ2/raster and latch variables, the
calendar chip, both CPUs' bank offsets, and the YM2610 with its SSG. The
YM2610 struct holds pointers into itself and into a malloc'd table: they
are relocated on load, so a state loads in a new run of the same build.
The program ROM is left out (read-only, in flash).

PSRAM is almost all given to the sprite page cache while a game runs, so
the state buffer is that cache, borrowed between frames and emptied
(`neospr_borrow()`); it refills from the card in the next frames.

Checked on the PC harness: save at frame 1500, then 200 frames compared
with the run that never saved, in the same process and in a new process
that loads the file: 200/200 identical on Metal Slug 2, KOF '95 and Puzzle
Bobble 2 (before: 0/200). On the board: save and load in play on Metal
Slug 2, game continues at 51–54 fps.

### Strategy

**The idea.** Memory was the wall, and it is solved by one rule: anything
too large for the PSRAM lives on the SD card or in flash, is read through a
small cache, and must give the same frames as the all-in-RAM build (checked
on the PC before it goes on the board). That opens every unencrypted Neo Geo
set up to ~50 MB. What is left is **speed**: in play, big games run at
about half speed with the CPU at 100%.

**Order of work**, cheapest and surest first:

1. **Per-game idle-loop hacks: they already exist.** MAME 0.37b5's
   `machine/neogeo.c` has 86 `NEO_CYCLE_R` handlers that stop the 68000
   while a game polls for vblank, the same trick that took Blood Bros. to
   60 fps. They are keyed on the driver name, so the one for Sonic Wings 2
   (`sonicwi2`, PC `0x1e6c8`) is probably not active for the `sonicwi2m`
   set our zip loads as. Check and enable it. Metal Slug 2's hack is off in
   MAME ("breaks the game"): find a working loop with the PC's PC-count
   profiler, as for Aero Fighters.
2. **Measure where the time goes** on the board (68000 / Z80 / YM2610 /
   sprite renderer / 8 → 16 bpp conversion), the way `GEN_PROF` did it for
   the Genesis.
3. **YM2610 on core 1.** Core 1 is idle in these games. Moving FM synthesis
   there took the Genesis from 20 to 30 drawn fps; the Neo Geo has the same
   kind of chip.
4. **Sprite renderer**: skip fully transparent sprite columns and zoomed-out
   strips early, and go straight to 16 bpp without the conversion pass.
5. **Correctness**: exact save states, and the `init_mgd2` sets whose
   sprites are reordered in memory (not paged yet).

**Out of scope on this board:** encrypted sets (KOF '99 and later, Metal
Slug 3+), because MAME 0.37b5 has no decryption for them, and sets over
~50 MB. **Target:** 60 emulated fps in play on the 1990–95 games (the 54
ready sets below), and Metal Slug 2 above 45.

**Tested on the board (2026-09-27, fork `3d1734d3`)** — modern ROM sets
from `/sd/roms/neogeo/` with `neogeo.zip` (BIOS) next to them, sprite and
sample files prepared on the PC with `scripts/neogeo_prepare.py` (start in
12–26 s, no conversion on the board), FIT scaling (434×320), audio 32 kHz.
Emulated fps in the attract mode (no input); real play is heavier
(Metal Slug 2: 42 fps in play).

**Caveat (found later the same day):** this table was measured before the
`neogeo_name()` fix. Metal Slug 2 and KOF '95 were stuck on the warning
screen, so their numbers are for that screen, and no game had its
per-game speed-up. To be measured again.

| Game | Set | fps (attract) |
|:---|:---|:---|
| Alpha Mission II | `alpham2m` | 60.1 |
| KOF '95 | `kof95m` | 60.1 |
| Blazing Star | `blazstarm` | 59.9 |
| NAM-1975 | `nam1975m` | 59.8 |
| Aero Fighters 3 / Sonic Wings 3 | `sonicwi3m` | 59.8 |
| Windjammers | `wjammersm` | 59.5 |
| Aero Fighters 2 / Sonic Wings 2 | `sonicwi2m` | 59.4 |
| Magician Lord | `maglordm` | 59.3 |
| Cyber-Lip | `cyberlip` | 59.1 |
| Neo Drift Out | `neodriftm` | 57.8 |
| Metal Slug 2 | `mslug2m` | 57.0 (42 in play) |
| Metal Slug | `mslugm` | 53.8 |
| Puzzle Bobble 2 | `pbobbl2nm` | 40.8 (real 68000 load, see below) |

**Puzzle Bobble 2 is slow because it works harder, not because of a bug.**
On the PC (gprof + a 68000 PC histogram, `-DPCHIST` builds only) it runs 6x
the 68000 instructions of Sonic Wings 2 and draws 2.5x the sprite strips.
There is no wait loop to skip: the time is spread over 0x2460–0x2c40 (game
logic) and a random-number routine at 0x25da, and MAME 0.37b5 found no
speed-up for this game either. Only the general work helps (sprite renderer
on core 1, a faster 68000).

**Shock Troopers and Thrash Rally (2026-09-27, evening, PC only so far):**
- 5 MB programs are split: 1 MB in PSRAM, 4 MB in flash (the partition is
  exactly 4 MB, so their samples always come from the SD). Shock Troopers
  (set 2) reaches the route select; frames identical to the all-in-RAM
  build for 6000 frames; save/load 200/200. This unlocks 9 sets: Shock
  Troopers 1 and 2, KOF '97, The Last Blade 1 and 2, Metal Slug X, Real
  Bout Fatal Fury 2 and Special, Samurai Shodown IV. On the board PSRAM is
  tighter (1.3 MB more than Metal Slug 2 in use): to be checked.
- Thrash Rally never needed its MCU: it only drives the link between two
  cabinets, was never dumped, and current MAME does not emulate it either.
  The generator now drops that region; the game reaches the tutorial.

**Modern ROM sets:** `scripts/neogeo_modern_sets.py` translates current
MAME's `neogeo.cpp` into 0.37b5 definitions (166 sets: the parents, then
the clones of a translated parent, since the zip people have is often a
clone such as `shocktroa`; encrypted sets and programs over 5 MB skipped),
so any modern zip loads without a hand-written definition. The picker looks
at the whole family of the zip's name (`shocktro` → `shocktrom` →
`shocktroa`). mame-go's partition is nearly full (1.56 of 1.57 MB) after
this.

**Ready to try on the board (54 sets, MAME 0.37b5 names):** 2020bb, 2020bbh,
androdun, bjourney, bstars, bstars2, burningf, burningh, crsword, cyberlip,
fatfury1, fightfev, flipshot, goalx3, gpilots, gururin, janshin, joyjoy,
karnovr, kotm2, legendos, lresort, maglord, maglordh, mahretsu, mosyougi,
mutnat, nam1975, ncombat, neomrdo, panicbom, pbobble, popbounc, pspikes2,
puzzldpr, puzzledp, quizdai2, quizdais, roboarmy, sengokh, sengoku,
sengoku2, socbrawl, sonicwi2, sonicwi2m, spinmast, ssideki, stakwin,
strhoop, superspy, tpgolf, trally, wh1, wjammers.

## Capcom CPS1 on v3 (2026-09-27, PC-verified, board pending)

**Where the games go:** CPS1 zips go in the **Arcade** tab (`/sd/roms/arcade/`,
repo folder `test-roms/cps1/`); mame-go picks the driver from the zip.

**What was added (fork `929fc118`, `e245fffa`):**

| Change | Why |
|:---|:---|
| `drivers/cps1.c`, `vidhrdw/cps1.c`, YM2151, kabuki from mame2000-libretro (CPS2 left out) | the 0.37b5 CPS1 driver, 80 sets |
| Graphics streamed from the zip: four readers feed the tile conversion (it reads the ROM's four quarters in step), 64 KB tile blocks go to the `mamerom` flash partition, the rest to PSRAM | the ROM never sits in memory; Street Fighter II's 6 MB of tiles = 4 MB flash + 2 MB PSRAM. Sets whose graphics are not plain `ROM_LOAD`s (Ghouls'n Ghosts) load the ROM and convert it into flash |
| `scripts/cps1_modern_sets.py`: 69 modern sets | today's zips often carry a newer program on the same chips (SF2 CE "World 920513"); the set reuses the 0.37b5 definition with the modern program ROMs (bootlegs and hacks skipped for binary space) |
| Generic 68000 idle skip on, Z80 skip off | the Z80 feeds the YM2151/OKI through memory: its skip changed the audio on the PC |
| 384-wide screens fit the panel width (480×280) | CPS1 is 384×224 |
| mame-go partition 1.5 → 1.75 MB (retro-extra 1.75 → 1.5 MB, binary 1.43 MB) | CPS1 adds ~150 KB |

**Checked on the PC harness:** Final Fight, Carrier Air Wing, Ghouls'n
Ghosts, Knights of the Round, SF2 Champion Edition reach attract / title /
select screens; the flash and streamed paths give the same frames and audio
as the in-RAM conversion. In use after start: ~5.6 MB for SF2 CE (program
1.5 MB, 2 MB of tiles, 2 MB scroll-2 cache bitmap).

**Not yet:** speed on the board (one 10–12 MHz 68000 + Z80 + YM2151 + a
384-wide renderer: expect it at the limit, like the Neo Geo), Q-Sound games
(Cadillacs and Dinosaurs, Warriors of Fate, Punisher: kabuki-encrypted Z80 +
4 MB of Q-Sound samples) untested.


## Metal Slug 2 toward 60 fps: board measurements (2026-09-28)

Target set by the user: Metal Slug 2 in play at 55–60 fps. Measured on the
board with the `NEOPROF=1` build (core 0 split per part, core 1 busy from an
idle hook, display task time), in play from a save state, 30 s windows.

| Build | Light scenes | Heavy scenes | Core 0 | Core 1 |
|:---|:---|:---|:---|:---|
| Sound on core 0, sprites on core 0 | 45–53 fps | 34–38 fps | 98% | ~50% |
| Sprites on core 1 (present task) | 43 fps | — | 97% | 96% |
| Sound board (Z80 + YM2610) on core 1 | 49–54 fps | 36–39 fps | 98% | 95–99% |

What the numbers say:

- **Heavy scenes are the 68000's.** It takes 14–18 ms a frame there
  (7–10 ms in light scenes): the game's logic is really that busy (Metal
  Slug 2 slows down on a real MVS too), no wait loop to skip (PC histogram:
  the time is spread over the game's code).
- **Moving work to core 1 is paid back in memory contention.** Both cores
  share the 64 KB data cache and the PSRAM: with the sprites on core 1 the
  68000 went from 11.8 to 14 ms, with the sound board from ~15 to ~17 ms in
  heavy scenes. Net: +0 fps for the sprites (kept off by default,
  `NEODEFER=1` builds it), +2–3 fps for the sound board (kept on).
- **The display task** (scale to 434×320 + smoothing filter + line
  checksums) costs ~4.5 ms per emulated frame on core 1; with the LCD off
  the game gains only 2–4 fps, so it is not the main limit. Turning the
  filter off looked bad at 1.43× and was reverted.
- `-O3` on the 68000 core does not fit the 1.75 MB partition (+110 KB).

**Sound board on core 1 (fork, PC-verified + board):** a private Z80
(`cpu/z80/z80snd.c`, z80.c built again with its own memory/port accessors)
runs the Neo Geo sound program with direct ROM banks and RAM, the YM2610
written directly with its timers counted in Z80 cycles and samples rendered
as the Z80 runs; the 68000's commands are delivered one frame later at the
same point in the frame, the reply it reads comes from the previous frame.
PC: audio envelope 95% equal to MAME's scheduling (shifted one frame), same
frames on screen, save/load 200/200.

**Next levers for heavy scenes (not started):** a faster 68000 core
(direct-pointer fast paths for the Neo Geo's ROM/RAM instead of MAME's
memory handlers, hot opcode handlers in IRAM if memory allows), or less
cache traffic from core 1 (the display reading the MAME bitmap directly
with a 16-bit palette, dropping the separate conversion pass).
