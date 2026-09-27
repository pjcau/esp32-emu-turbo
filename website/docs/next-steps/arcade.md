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

  All generic for the Neo Geo (no per-game speed-ups): a short backward loop
  that repeats with the same registers and the same RAM writes, and writes
  nothing to I/O, gives away the rest of its timeslice. Left on core 0:
  68000 10.8, video 4.7, Z80 3.8, palette blit 2.2, frame copy 1.5 ms.
  Next: the video renderer on core 1 (would bring core 0 near 17.5 ms).
- `init_mgd2` sets reorder their sprites in memory and are not paged yet.
- Encrypted sets (KOF '99 and later, Metal Slug 3+) need decryption this
  MAME version does not have.
- Save states do not restore Neo Geo games exactly yet.

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

**Ready to try on the board (54 sets, MAME 0.37b5 names):** 2020bb, 2020bbh,
androdun, bjourney, bstars, bstars2, burningf, burningh, crsword, cyberlip,
fatfury1, fightfev, flipshot, goalx3, gpilots, gururin, janshin, joyjoy,
karnovr, kotm2, legendos, lresort, maglord, maglordh, mahretsu, mosyougi,
mutnat, nam1975, ncombat, neomrdo, panicbom, pbobble, popbounc, pspikes2,
puzzldpr, puzzledp, quizdai2, quizdais, roboarmy, sengokh, sengoku,
sengoku2, socbrawl, sonicwi2, sonicwi2m, spinmast, ssideki, stakwin,
strhoop, superspy, tpgolf, trally, wh1, wjammers.
