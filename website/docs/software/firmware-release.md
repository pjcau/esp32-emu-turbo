---
id: firmware-release
title: Firmware Release 2026-10-07
sidebar_position: 2.5
---

# Firmware release 2026-10-07

:::info Updated the same evening: home computers in the free room
The 1856 KB the Nintendo 64 ports left were taken, at the user's request, by
two new apps: `fmsx` (MSX, 704 KB) and `retro-home` (Atari 5200, Atari 7800,
Commodore 64; 1088 KB). The current image and its checks are in
[the evening build](#evening-build-home-computers) below; the morning build
further down is kept as the record of the Nintendo 64 removal.
:::

The firmware build that is on the board as of 2026-10-07, recorded as the
definitive build of this version: what it contains, how it was checked, and
how to write it again or rebuild it.

## What changed from the previous build

- **The Nintendo 64 ports are out of the flash** (user's decision,
  2026-10-07). Super Mario 64 and Mario Kart 64 shared one partition
  (`n64app`, 1792 KB); it is gone and the room is left free. Their programs
  stay on the card in `/retro-go/apps-n64-off/` and can be put back: see
  [Nintendo 64 through native ports](/docs/next-steps/n64-native-ports).
- **Bench builds of the arcade app can give the gamepad back.** A `mame-go`
  benchmark build plays a scripted input instead of the buttons. One was left
  on the board on 2026-10-06 and made the buttons look broken in Aero Fighters.
  Such builds now have *Options → Emulator options → Bench input*: *On
  (script)* / *Off (gamepad)*. The play build in this release is not a bench
  build and reads the gamepad normally.

## The image

| | |
|---|---|
| File | `~/flash-backups/flash-2026-10-07-release.img` (on the Linux bench PC) |
| Size | 14 876 928 bytes |
| SHA-1 | `4361bab6cf2506f06a9ba88e31c4c446b7551a58` |
| Written at | offset `0x0`, `esptool --chip esp32s3 -b 921600 write_flash 0x0 <img>`, hash verified |
| Flash before it | `~/flash-backups/flash-2026-10-07-before-n64-removal.bin`, SHA-1 `36bf3aeea077069166bc21bc475a169a53c23eb8` |

The image holds the bootloader, the partition table and every app. It is a
play build: `mame-go` contains no benchmark code (no `MAMEBENCH frames`
string in its binary).

## Partition table (read back from the board)

| Partition | Offset | Size | Contents |
|---|---|---|---|
| nvs | 0x009000 | 16 KB | settings |
| otadata | 0x00d000 | 8 KB | which app boots |
| phy_init | 0x00f000 | 4 KB | radio calibration |
| launcher | 0x010000 | 1152 KB | menu, covers, updates from the card |
| retro-core | 0x130000 | 1216 KB | NES, SNES, Game Boy, Game Boy Color, Master System, SG-1000, Game Gear, PC Engine, ColecoVision, Atari Lynx |
| prboom-go | 0x260000 | 832 KB | DOOM |
| gwenesis | 0x330000 | 1024 KB | Mega Drive |
| retro-extra | 0x430000 | 1280 KB | Atari 2600, Neo Geo Pocket, Arcade 3D Racing |
| mame-go | 0x570000 | 2048 KB | Arcade (MAME), Neo Geo, Capcom CPS-1 |
| wolf3d-go | 0x770000 | 640 KB | Wolfenstein 3D |
| opentyrian-go | 0x810000 | 704 KB | OpenTyrian |
| gbsp | 0x8c0000 | 832 KB | Game Boy Advance |
| sdapp | 0x990000 | 640 KB | OutRun (Cannonball), copied from the card |
| mamerom | 0xa30000 | 4096 KB | cache of large arcade ROMs, rebuilt by the first arcade game started |
| free | 0xe30000 | 1856 KB | — |

## Rebuilding it

- **Source.** Retro-go fork `pjcau/retro-go` commit `fe040554` (master). The
  flashed image was built from `468e0c5f` with the same two changes, before
  they were committed. The difference between the two (the `sm64-go` and
  `mk64-go` submodule pointers) is not in the image.
- **Command**, from the repository root:

  ```bash
  docker compose -f docker-compose.retro-go.yml run --rm \
    -e NB_LINES=16 -e LCD_BUFS=3 -e BAND_INTERNAL=3 -e NEOBAND=2 -e AUDIO_MIX_HZ=16000 \
    retro-go-build sh -c "rm -f mame-go/sdkconfig; python rg_tool.py --target=esp32-emu-turbo build-img"
  ```

  The five options are the arcade app's play settings: band renderer, display
  buffers, 16 kHz sound chips. Without them `mame-go` is not the play build.
- **Check before writing:** `grep -a -c "MAMEBENCH frames"
  retro-go/mame-go/build/mame-go.bin` must print `0`.

## The SD card this build expects

- `/retro-go/apps/cannonball.bin`: OutRun, copied into `sdapp` when started.
- `/roms/<tab>/`: the games, one folder per launcher tab. `/romart/<tab>/`:
  their covers. No ROM is kept in any repository.
- `/retro-go/apps-n64-off/`: the two Nintendo 64 programs, not used by this
  build.

## Checks on the board (2026-10-07)

For each launcher tab, one game was started from the console and checked on
the webcam. Then SELECT, START, A, START and RIGHT were pressed: each game must
react to the keys.

| Tab (app) | Game | Started | Reacts to the keys |
|---|---|---|---|
| NES (retro-core) | Super Mario Bros. + Duck Hunt | ✅ | ✅ Duck Hunt starts |
| SNES | Donkey Kong Country | ✅ | ✅ game select |
| Game Boy | Tetris | ✅ | ✅ game type menu |
| Game Boy Color | Space Invaders | ✅ | ✅ title menu |
| Game Boy Advance (gbsp) | Metal Slug Advance | ✅ | ✅ file select |
| SG-1000 | GP World | ✅ | ✅ |
| Master System | Sonic the Hedgehog | ✅ | ✅ in play |
| Game Gear | Shinobi II | ✅ | ✅ title menu (the homebrew Swabby does not react to these keys) |
| Mega Drive (gwenesis) | Sonic the Hedgehog | ✅ | ✅ |
| ColecoVision | Pac-Man | ✅ | ✅ keypad overlay |
| PC Engine | OutRun | ✅ | ✅ configuration menu |
| Atari Lynx | Mario Plus Demo | ✅ | ✅ Mario moves |
| Atari 2600 (retro-extra) | Asteroids | ✅ | ✅ |
| Neo Geo Pocket | Metal Slug 1st Mission | ✅ | ✅ |
| DOOM (prboom-go) | Freedoom | ✅ | ✅ |
| Wolfenstein 3D | shareware | ✅ | ✅ in play |
| OpenTyrian | OpenTyrian | ✅ | ✅ players menu |
| Arcade 3D Racing | Race | ✅ | ✅ steers |
| Arcade (mame-go) | Aero Fighters | ✅ | ✅ coin, START, player select, the plane moves |
| Neo Geo | Metal Slug | ✅ | ✅ in mission 1 |
| Capcom CPS-1 | Final Fight | ✅ | ✅ in play |
| OutRun (sdapp) | OutRun | ✅ | ✅ race starts |

The arcade games map the buttons as follows. Street Fighter II was checked in
a fight: B, A, Y and X each start a different attack. L and R were not
separated from the opponent's hits in that test.

| Board | Arcade input |
|---|---|
| B / A / Y / X / L / R | Button 1 / 2 / 3 / 4 / 5 / 6 |
| SELECT | coin |
| START | start |

## Known limits

- Free flash: 1856 KB at the end. A future change can use it; the arcade
  cache `mamerom` stays where it is in this layout.
- The first arcade game started after writing the image rebuilds the
  `mamerom` cache, so it takes longer to load once.

## Evening build: home computers

Written to the board on 2026-10-07 after the user's approval, with a backup
first. The apps up to `sdapp` are the same builds at the same offsets as in
the morning build; `mamerom` moved back to `0xbf0000`, so its cache was
rebuilt by the first arcade game started (Metal Slug: coin, START, "HOW TO
PLAY").

| | |
|---|---|
| File | `~/flash-backups/flash-2026-10-07-home-computers.img` |
| Size | 16 711 936 bytes (64 KB of the flash left free) |
| SHA-1 | `35305311f8b3aa3214949efb7b0a1508cb98439d` |
| Flash before it | `~/flash-backups/flash-2026-10-07-before-home-computers.bin`, SHA-1 `de0c4afbc33bd36373cd23639b43208a2dc04257` |
| Source | fork branch `home-computers` at 97ae8890; afterwards `fmsx` (9543588b) and `retro-home` (23934129) were updated through the card (`/retro-go/update/`) |

| Partition | Offset | Size |
|---|---|---|
| launcher … sdapp | as above | as above |
| fmsx | 0xa30000 | 704 KB |
| retro-home | 0xae0000 | 1088 KB |
| mamerom | 0xbf0000 | 4096 KB |

The emulators, the BIOS files they need on the card and what was checked are
on [Atari 5200 / 7800, Commodore 64, MSX](/docs/software/home-systems).
