---
id: firmware
title: Firmware
sidebar_position: 2
---

# Firmware

The firmware is a fork of [Retro-Go](https://github.com/ducalex/retro-go)
(`pjcau/retro-go`, a submodule at `retro-go/`), built with ESP-IDF v5.4 for the
ESP32-S3 N16R8. Each launcher tab runs one *app*, a separate program in its own
flash partition. This page: what is in the flash now, how to build it, write
it, update it from the SD card, and what the card must hold.

## Current build {#current-build}

On the board since 2026-10-07, updated 2026-10-08. Fork master `07cd18f2`.

| | |
|---|---|
| Image | `~/flash-backups/flash-2026-10-07-home-computers.img` on the bench PC, 16 711 936 bytes, SHA-1 `35305311f8b3aa3214949efb7b0a1508cb98439d` |
| Updated since through the card | `fmsx` (9543588b), `retro-home` (07cd18f2) |
| Flash before it | `~/flash-backups/flash-2026-10-07-before-home-computers.bin` |
| Type | play build: `mame-go` has no benchmark code (`grep -a -c "MAMEBENCH frames" mame-go.bin` = 0) |

### Flash layout (16 MB)

| Partition | Offset | Size | Contents |
|:---|:---|---:|:---|
| bootloader, table, nvs, otadata, phy_init | 0x000000 | 64 KB | boot and settings |
| launcher | 0x010000 | 1152 KB | menu, covers, updates from the card |
| retro-core | 0x130000 | 1216 KB | NES, SNES, GB, GBC, Master System, SG-1000, Game Gear, PC Engine, ColecoVision, Lynx |
| prboom-go | 0x260000 | 832 KB | DOOM |
| gwenesis | 0x330000 | 1024 KB | Mega Drive |
| retro-extra | 0x430000 | 1280 KB | Atari 2600, Neo Geo Pocket, Arcade 3D Racing |
| mame-go | 0x570000 | 2048 KB | Arcade (MAME), Neo Geo, CPS1 |
| wolf3d-go | 0x770000 | 640 KB | Wolfenstein 3D |
| opentyrian-go | 0x810000 | 704 KB | OpenTyrian |
| gbsp | 0x8c0000 | 832 KB | Game Boy Advance |
| sdapp | 0x990000 | 640 KB | OutRun, copied from the card when started |
| fmsx | 0xa30000 | 704 KB | MSX |
| retro-home | 0xae0000 | 1088 KB | Atari 5200, Atari 7800, Commodore 64 |
| mamerom | 0xbf0000 | 4096 KB | cache of large arcade ROM regions, rebuilt by the first arcade game started |
| free | 0xff0000 | 64 KB | must stay free: the image ends with the updater's footer |

The flash is full: a new app needs room taken from another one, or it can run
from the card through `sdapp` (its binary in `/retro-go/apps/`, copied into the
partition when started, a few seconds). Super Mario 64 and Mario Kart 64 are
kept that way in `/retro-go/apps-n64-off/`, out of use.

### Checked on the board

For each launcher tab one game was started from the console and checked on the
webcam, then SELECT, START, A, START and RIGHT were pressed and the game had to
react. All 22 tabs passed on 2026-10-07 (NES, SNES, GB, GBC, GBA, SG-1000,
Master System, Game Gear, Mega Drive, ColecoVision, PC Engine, Lynx, 2600,
Neo Geo Pocket, DOOM, Wolfenstein 3D, OpenTyrian, Arcade 3D Racing, Arcade,
Neo Geo, CPS1, OutRun), and the four home systems the same evening. Which game
and at what speed: [Emulators — tests and speed](/docs/software/emulators).

## Building

Everything builds in Docker (`espressif/idf:v5.4`); no local toolchain.

```bash
# the whole image (all apps), from the repository root
docker compose -f docker-compose.retro-go.yml run --rm \
  -e NB_LINES=16 -e LCD_BUFS=3 -e BAND_INTERNAL=3 -e NEOBAND=2 -e AUDIO_MIX_HZ=16000 \
  retro-go-build sh -c "rm -f mame-go/sdkconfig; python rg_tool.py --target=esp32-emu-turbo build-img"

# one or more apps
docker compose -f docker-compose.retro-go.yml run --rm retro-go-build \
  python rg_tool.py --target=esp32-emu-turbo build retro-core launcher
```

The five options are the arcade app's play settings (band renderer, display
buffers, 16 kHz sound chips); without them `mame-go` is not the play build.
The partition sizes and the app list are `PROJECT_APPS` in
`retro-go/rg_tool.py`; it refuses an image larger than the flash.

The target lives in `retro-go/components/retro-go/targets/esp32-emu-turbo/`:
`config.h` (GPIO, display, audio, input; it mirrors `software/main/board_config.h`),
`env.py` (`IDF_TARGET = esp32s3`) and `sdkconfig` (240 MHz, 16 MB flash QIO,
8 MB octal PSRAM, 32 KB instruction / 64 KB data cache).

## Writing it

- **Full image, over USB** (needed when the partition table changes, and for
  a board that does not boot): hold SELECT (GPIO0) at power-on for download
  mode, then `esptool --chip esp32s3 -b 921600 write_flash 0x0 <image>`, or
  `python rg_tool.py --target=esp32-emu-turbo install`. Back up the flash
  first (`read_flash`).
- **Bench rule:** unplug the battery from J3 for any serial session from a
  laptop port; with a cell attached the charger draws more than a 500 mA port
  gives.

## Updating apps from the SD card {#firmware-update-from-the-sd-card-2026-09-28}

Since 2026-09-28 apps are updated from the card, with no cable.

1. Build the apps that changed.
2. Copy them to `retro-go/update/<app>.bin` on the card:
   `scripts/sd_update.py --card <card mount> <apps>` with a card reader, or
   `scripts/sd_update.py --console <apps>` over USB with the card in the
   console (190–490 KB/s). The script refuses an unknown app or an image
   larger than its partition.
3. At boot the launcher writes each file into the partition of the same name
   (a progress bar), verifies it and renames the file `.done` (or `.failed`).
   The launcher updates itself through another app's boot.

USB is still needed when the partition table changes, when the launcher no
longer boots (there is no recovery app yet), and for a board that predates
2026-09-28. A change in `components/retro-go` (display, audio, input, the
updater) reaches an app only when that app is rebuilt.

## The SD card

FAT32. One folder per launcher tab, `/roms/<tab>/`: `nes`, `snes`, `gb`, `gbc`,
`gba`, `sms`, `gg`, `sg1`, `col`, `pce`, `lnx`, `md`, `a26`, `ngp`, `a52`, `a78`,
`c64`, `msx`, `arcade`, `neogeo`, `cps1`, `doom`, `wolf3d`, `opentyrian`,
`cannonball`, `arcade3d`. A ROM up to 6 MB is loaded into PSRAM; `.zip` files
are opened by most consoles.

| Path | What |
|:---|:---|
| `/romart/<tab>/<rom file>.png` | game covers: `scripts/console_art.py` (libretro thumbnails) and `scripts/arcade_art.py` (ArcadeDB) |
| `/retro-go/bios/` | system files: see [Emulators → System files](/docs/software/emulators#system-files-on-the-card) |
| `/retro-go/apps/` | apps run from the card through `sdapp` (OutRun) |
| `/retro-go/update/` | app images to install at the next boot |

`scripts/setup-sdcard.sh /dev/sdX` formats a card and copies the free homebrew
test games in `test-roms/` (no commercial ROM is in any repository).

## Launcher art

Each tab shows `logo_<tab>.png` (46×50), `banner_<tab>.png` (272×24, magenta =
transparent) and `background_<tab>.png` (320×240) from `retro-go/themes/default/`.
Systems the upstream theme lacks take theirs from
[es-theme-gbz35](https://github.com/rxbrad/es-theme-gbz35) through
`retro-go/tools/import_gbz35_art.py` (one line per system in its `SYSTEMS`
table; dark logos are turned white, unreadable ones become a text banner), then
`python3 tools/gen_images.py` embeds them in the launcher.

## Boot splash

The "GAME BRO!" splash shown at cold boot: [Boot Splash](/docs/software/boot-splash).

## Driving the board from a PC

The firmware answers commands on the USB console (`scripts/board_ctl.py`):
`ping`, `ls`, `put` (file upload with CRC32 check), `launch <tab> <rom>`,
`key start` / `hold right` (injected buttons), `save 0` / `load 0`, `launcher`,
`volume 0`. Apps run from the card are started the same way. Options menu →
*Debug HUD* shows fps, busy and free memory on screen.

## Hardware bring-up firmware

`software/` is a separate ESP-IDF project that tested every hardware block
before Retro-Go: display (ILI9488, 8-bit i80 at 20 MHz), SD card (SPI), the 12
buttons, audio (PDM on GPIO17 into the PAM8403). It passed on the first article
in September 2026 (`make firmware-build`, `make firmware-flash`).
The IP5306 battery chip has no I2C on this board: charge state is its LED only.
