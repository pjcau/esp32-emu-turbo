---
id: retro-go-forks-survey
title: Retro-Go Forks Survey
sidebar_position: 99
description: Survey of the forks and derivatives of ducalex/retro-go (2026-09-27) — new emulators, game ports, launcher features and performance work that could be pulled into the ESP32 Emu Turbo firmware, with port effort, license and value.
---

# Retro-Go Forks Survey (2026-09-27)

This page lists what the forks of [ducalex/retro-go](https://github.com/ducalex/retro-go)
add that our fork ([pjcau/retro-go](https://github.com/pjcau/retro-go)) doesn't have yet.

**Method.** We listed all 299 visible forks (`gh api repos/ducalex/retro-go/forks`)
and compared each default branch against `ducalex:master`, then against
`ducalex:dev`. Most forks sit on `dev`, which is 174 commits ahead of `master`.
We fetched all 45 forks with real divergence into a scratch repository and
read their commits and new top-level directories. We also read every branch
of the two big "megapack" forks (DynaMight1124, pcgamer404), the other
upstream branches, rapha-tech's branches, and three well-known derivatives
outside the fork graph: sylverb/game-and-watch-retro-go,
esp-cpp/esp-box-emu and Svarkovsky/s3-msx-pc.

**Baseline.** Our fork is on upstream `master` (0 commits behind) plus 46 of
our own commits. We don't have upstream `dev`. We already have: launcher +
splash, retro-core (NES, SNES + SuperFX, GB/GBC, SMS/GG/SG-1000, PCE, Lynx,
G&W, Coleco), gwenesis, fmsx, prboom-go, duke3d-go, retro-extra (NGP via RACE,
Atari 2600 via stella-odroid-go), mame-go (MAME 0.37b5 subset, 8-bit and
68000 boards), wolf3d-go and quake-go (both from pcgamer404/retro-go-pro).
Overclock support for the ESP32-S3 is already in `master`.

**Flash budget.** This constrains every recommendation below. The app
partitions in `rg_tool.py` add up to about 10.3 MB, plus the 4 MB `mamerom`
data partition, so the 16 MB flash is close to full. Every new app either
replaces an existing one or needs the "bootstrap" mechanism in item 2.

## Top 10 recommendations

| # | What | Source | Already ours? | Effort | License | Value |
|---|------|--------|---------------|--------|---------|-------|
| 1 | **Duke3D fixes**: palette/gamma fix (green cast, RGB565 overflow), PSRAM-sized tile cache, speed improvements, FPS cap, death glitch, cheats menu, expansions | [DynaMight1124 `Duke3D`](https://github.com/DynaMight1124/retro-go/tree/Duke3D), [ThomasFarstrike `integration/fri3d-2026`](https://github.com/ThomasFarstrike/retro-go/tree/integration/fri3d-2026) | No (same upstream `duke3d` base as ours) | Low: cherry-pick into `duke3d-go` | GPL-2 | High. Our Duke3D rendering fix is still unverified |
| 2 | **Bootstrap flasher**: cores and native apps live as `.bin` files on the SD card and get flashed on demand into one `bootstrapped` partition, with a bootloader hook for recovery on power-cycle | [DynaMight1124 `bootstrap`](https://github.com/DynaMight1124/retro-go/tree/bootstrap) | No | Medium: launcher + bootloader hook + `rg_tool.py` | GPL-2 | High. It unblocks every other new app, because flash is full |
| 3 | **Zelda 3 and Super Mario World as native C ports** (not emulated). They run on the 280 MHz STM32H7 Game & Watch | [sylverb/game-and-watch-retro-go](https://github.com/sylverb/game-and-watch-retro-go) (`zelda3/`, `smw/`) | No | Medium-high: STM32 porting layer to retro-go API; assets extracted from the user's ROM | MIT (zelda3) / check smw | High. Two flagship SNES games at a guaranteed 60 fps with no emulation cost |
| 4 | **OpenLara** (Tomb Raider 1 engine), software rasteriser with PSRAM-resident levels, S3/P4 only | [pcgamer404/retro-go-pro `openlara/`](https://github.com/pcgamer404/retro-go-pro/tree/main/openlara), also in DynaMight1124 `megapack` | No | Medium: 320x240 renderer, fits 480x320 with scaling | BSD-2 | High. A 3D FPS-class port, the kind the user likes |
| 5 | **Cannonball** (OutRun engine), README says "full speed on the ESP32-S3", double-buffered PSRAM, parallel road/sprite render | pcgamer404 `cannonball/`, DynaMight1124 `cannonball` branch | No | Low-medium: already a retro-go app | Cannonball license (non-commercial, MAME-style) | High. Arcade classic; complements mame-go |
| 6 | **Rise of the Triad** (Dark War + shareware), OPL3 music, PSRAM memory manager | pcgamer404 `rott/`, DynaMight1124 | No | Low-medium: already a retro-go app | GPL-2 | Medium-high. Another FPS port next to DOOM/Wolf3D/Duke3D/Quake |
| 7 | **WonderSwan / WonderSwan Color** (Oswan core) with double buffering, IRAM render path, save states | [nod3011/retro-go-nano-s3 `oswan/`](https://github.com/nod3011/retro-go-nano-s3/tree/master/oswan) (pcgamer404's copy is marked "not working") | No | Medium: standalone app on an older API | Unclear (Oswan has no license file in the fork), check before shipping | Medium-high. New system |
| 8 | **Commodore 64** (Frodo 4 Lite): PRG/CRT/T64/D64, 1541 drive, SID, virtual keyboard | pcgamer404 `frodo/`, DynaMight1124 `c64-frodo` | No | Medium: needs a keyboard UX for 12 buttons | GPL-2 | Medium. New system |
| 9 | **PICO-8** (PicoPico + z8lua, tested on about 200 carts) and the **Celeste Classic** native port | DynaMight1124 `picopico`, pcgamer404 `pico8/` + `celeste/` | No | Low-medium | PicoPico: check; ccleste: CC BY-SA 4.0 | Medium. Huge homebrew library, free carts |
| 10 | **Upstream `dev` merge**: standalone **updater** app (flash `.img`/`.fw` from SD, including partition-table rewrite), SNES audio task + double buffering (#211), multi-core gwenesis option, UTF-8 virtual keyboard for Wi-Fi, improved overclock, gpSP GBA | [ducalex/retro-go `dev`](https://github.com/ducalex/retro-go/tree/dev) | Partly (overclock yes; updater app, GBA, SNES audio task no) | Medium: 174 commits, conflicts expected with our SNES/gwenesis work. Cherry-pick | GPL-2 | Medium. The updater fits the bench/SD workflow |

**Honourable mentions (not in the top 10):**

- **OpenTyrian**: GPL-2, 35/50 fps shoot-'em-up.
- **ClassiCube**: BSD-3, Minecraft Classic.
- **PicoDrive**: Mega CD support. On the ESP32-S3 its Genesis speed is about the same as gwenesis.
- **MAME4ALL**: 1,603 drivers. Worth diffing against our mame-go driver list.
- **ESP-NOW wireless gamepad / 2-player** (thangvv-tech).
- **USB MSC SD access** (ashkan89, devinzhang91).
- **Star Wars: Dark Forces** (esp-box-emu).

## Details per fork

### DynaMight1124/retro-go (51★, most active "megapack")

<https://github.com/DynaMight1124/retro-go>. The default branch `megapack` is
upstream `dev` plus about 12 commits. Every port also has its own branch.
The author says openly that most ports were done with AI help and tuned
afterwards.

| Branch / dir | What | Ours? | Effort / notes | Value |
|---|---|---|---|---|
| `Duke3D` (47 commits over dev) | Palette → RGB565 fixes, gamma, PSRAM-sized tile cache, loading-screen fixes, speed-ups, FPS cap, death glitch, cheats + expansions, swim/fly controls | Base only | Low: same code lineage as our `duke3d-go` | **High** |
| `bootstrap` | SD-resident cores + bootloader recovery hook (see top 10 #2) | No | Medium | **High** |
| `openlara`, `rott`, `cannonball`, `celeste`, `opentyrian` (via `retro-ports/`) | Game ports; `retro-ports` bundles Cannonball/Celeste/OpenTyrian into **one** app partition | No | Low-medium each; the `retro-ports` bundling idea saves partitions | High / Medium |
| `ecwolf` | ECWolf engine (all Wolf3D/SoD versions); "runs fine on S3" | wolf4sdl variant only | Low | Low: our wolf3d-go already hits 62 fps; only useful for Spear of Destiny/mods |
| `PicoDrive` | PicoDrive Genesis + experimental Sega CD (FAME 68k). "Works at a similar speed to Gwenesis"; Sega CD disabled on the original ESP32 for memory, full speed on the P4 | No | Medium; 1,340 files | Medium: Mega CD on S3 + 8 MB PSRAM is untested; gwenesis already does 60 fps |
| `mame4all` | MAME4ALL 0.37b5, 1,603 drivers, metadata forced into `.rodata`, `.bss` in PSRAM; CPS1 / Midway T-unit disabled | Similar (our mame-go = mame2000 0.37b5 subset) | Low to diff; same romset | Medium: compare driver coverage, borrow the const-ification tool |
| `PCSX-ReARMed-POC` | PS1 interpreter "boots, very unplayable", no sound, frameskip 7+ | No | High | Low (curiosity) |
| `sm64` | Super Mario 64 (sm64-funkey software renderer) | No | High, asset pipeline from ROM | Low: "very slow" |
| `picopico` / `pico8` | PICO-8 interpreter | No | Low-medium | Medium |
| `c64-frodo` | Commodore 64 | No | Medium | Medium |
| `neogeopocket` | NGP app (`ngp-go`) | Yes (RACE in retro-core/retro-extra) | — | None |
| `PocketSNES` | Snes9x-derived speed-focused SNES | No | Medium | Low: our snes9x already hits 60 fps on everything except Kart |
| `gbsp_dynarec` | rapha-tech's gpSP RISC-V dynarec (P4 only), falls back to the interpreter on S3 | No | — | Low for S3 |
| `Ports-Menu` | One "Ports" tab for DOOM/Duke3D/Quake/… instead of one tab each | No | Low (2 files) | Medium: our launcher tab count keeps growing |
| `dynamic-themes` | Theme backgrounds generated for any number of systems (Art Book Next v3) | No | Low | Low-medium |
| `SPI2HDMI`, `CYD`, `GB300-P4`, `p4-overclock` | Other targets / P4 overclock | — | — | See Zepan below for HDMI |

### pcgamer404/retro-go-pro (source of our Wolf3D/Quake)

<https://github.com/pcgamer404/retro-go-pro>. This is DynaMight1124's
megapack plus 26 commits.

| Item | What | Ours? | Notes | Value |
|---|---|---|---|---|
| `openlara/`, `rott/`, `cannonball/`, `celeste/`, `opentyrian/`, `classicube/`, `frodo/`, `pico8/`, `stella/` (StellaDS) | Same ports as the megapack, sometimes newer ("Added Open Tyrian & improved other ports", 2026-09-12) | wolf4sdl + quake yes; rest no | Take the newest of pcgamer404 vs DynaMight1124 per port | See top 10 |
| `oswan/` | WonderSwan, ships `oswan not working.zip` | No | Use nod3011's working version instead | — |
| `store/` | On-device ROM store; needs self-hosted [RG-Store-Backend](https://github.com/pcgamer404/RG-Store-Backend) | No | Low-medium; legal exposure depends on what the backend serves | Low |
| Controls | Select+Start opens the menu, turbo A/B for NES, ROM art next to the ROM file | No | Low | Low-medium |
| `sm64-go` | See above | No | — | Low |

### nod3011/retro-go-nano-s3 (ESP32-S3 Nano, 227 own commits)

<https://github.com/nod3011/retro-go-nano-s3>. Heavy rework for an S3 board,
with commit messages partly in Thai.

| Item | What | Ours? | Effort | Value |
|---|---|---|---|---|
| `oswan/` WonderSwan | Working WS/WSC, double buffering, IRAM render, save states, resets | No | Medium | **Medium-high** |
| FCEUmm NES core | Wider mapper coverage than nofrendo, FDS disk swap, cheats, "FCEUMM FULL SPEED!" | No (nofrendo) | Medium | Medium: only if nofrendo misses a mapper we need |
| Cheats | Game Genie / Pro Action Replay / GameShark menus for NES, GB, SMS/GG, Genesis, SNES, persisted per game | No | Medium (touches every core) | Medium |
| Netplay | GB link cable over UDP ("stable GB Netplay v3"), generic netplay setup | No | Medium-high | Low-medium (needs a second board) |
| Self-updater | Updater for the nano-s3 target | No | — | See upstream `dev` |
| NGP with IRAM / double buffering | NGP optimisations | We have NGP (RACE) | Low to compare | Low |

### ThomasFarstrike/retro-go (`integration/fri3d-2026`, 84 own commits over `dev`)

<https://github.com/ThomasFarstrike/retro-go/tree/integration/fri3d-2026>.
This is the Fri3d Camp 2026 badge integration.

- **Duke3D**: the same palette/gamma/tile-cache fixes that DynaMight1124
  picked up (see top 10 #1), plus the upstream-style `load_duke3d_groupfile`
  cleanup and PNG texture overrides. Effort: low. Value: **high**.
- In-game Retro-Go settings menu inside Duke3D, and a cheats menu.
- `esp_littlefs` component, `RG_GPIO_SND_I2S_MCK`, a CH32X035 I2C expander
  driver, an ESP-IDF 5.5.1 bump. Useful only as reference.

### ashkan89/retro-go (80 own commits, ESP32-S3 N16R8 targets)

<https://github.com/ashkan89/retro-go>. The fork includes `managed_components`
copies, so its diff is noisy.

| Item | What | Ours? | Effort | Value |
|---|---|---|---|---|
| `rg_usb_msc.c` | SD card exposed as a USB mass-storage drive over USB OTG | No | Medium. Conflicts with our USB console (`RG_GAMEPAD_CONSOLE` / `board_ctl.py`) if both need the same USB port | Medium: copying ROMs without pulling the SD card |
| `rg_usb_hid.c`, `rg_usb_host.c`, `rg_usb_xinput.c` | USB HID/XInput gamepad + keyboard/mouse (host mode) | No | Medium | Low-medium |
| `libs/netplay` | Local multiplayer (Wi-Fi AP, NES/SMS lock-step) | No | Medium-high | Low-medium |
| Media player | Audio player with codecs, library index, streaming, artwork, lyrics | No | Medium-high | Low |
| `factory/` + `rg_firmware.c` | OTA: launcher downloads `.img`, factory app installs it | No | Medium | Low-medium |
| Screen dim/off timeout, RGB-LED SD activity, haptics | UX | No | Low | Low |

### Zepan/retro-go: SPI2HDMI bridge

<https://github.com/Zepan/retro-go>. This adds an `spi2hdmi-s3` target: an
ESP32-S3 drives an SPI→HDMI bridge over QSPI, with 48 kHz PCM HDMI audio
through the bridge and UART recovery commands. DynaMight1124 has a matching
`SPI2HDMI` branch. Effort: medium. Value: **medium for planning the next
console**. It is a working reference for TV output on a retro-go S3, to
weigh against the LT8912B idea in Plan A.

### thangvv-tech/retro-go: ESP-NOW wireless gamepad

<https://github.com/thangvv-tech/retro-go>. This adds an ESP-NOW gamepad with
pairing/bonding UI, a web gamepad, and Wi-Fi coexistence fixes, plus an
ES8311 codec fix. Effort: medium. Value: low-medium; it would allow a
wireless second controller.

### alecu/retro-go

<https://github.com/alecu/retro-go>. This is a Ventilastation POV-disc
target and has nothing to reuse for us. It has two small generic fixes worth
cherry-picking: a stack buffer overflow fix in `rg_system_vlog`, and a
`rg_task_create` queue-creation race fix. It also adds gzip-compressed MSX
ROMs in fmsx and an unchecked `fopen` fix in `msx_fopen`. Effort: very low.
Value: medium, because these are real bugs that are probably in our tree too.

### Fri3dCamp/badge_retro-go (and tomvanbraeckel copy)

<https://github.com/Fri3dCamp/badge_retro-go>. It has 148 commits but is
based on 2024 `dev` (251 behind `master`). Items:

- `find_games`: downloads games over Wi-Fi.
- romart and CRC cache for `.zip` files.
- Folder previews.
- Storage free space in the debug menu.
- A non-recursive `rg_storage_delete`.

Value: low-medium. Zip romart is the only one we might want.

### Upstream ducalex/retro-go branches

| Branch | Status vs our fork | Notes |
|---|---|---|
| `dev` (174 ahead of master, 2026-01) | Not merged | See top 10 #10. Also: mapper 165, ADC oneshot driver, `rg_system_init(config)`, REDROID-GO/brutzelboy targets |
| `snes9x-fcipaq` (138 ahead) | Not merged | fcipaq's SNES test changes on top of dev. Our SNES renderer has diverged a lot, so only mine it for ideas |
| `duke3d`, `negeopocket`, `SDL2`, `input-drivers`, `launcher-core`, `background-previews`, `test-sticky-center` | 1–4 commits, mostly stale | `duke3d` is already the base of our duke3d-go; `background-previews` (4 commits, 2025) is a small launcher feature |

### Derivatives outside the fork graph

| Project | What | Ours? | Effort / license | Value |
|---|---|---|---|---|
| [sylverb/game-and-watch-retro-go](https://github.com/sylverb/game-and-watch-retro-go) (145★) | Retro-go for the STM32 Game & Watch. Extra cores: **Zelda 3 and SMW native ports**, Atari 7800 (prosystem), Amstrad CPC (caprice32), Watara Supervision (potator), Tamagotchi (tamalib), blueMSX, FCEUmm | No | Porting layer is `odroid_*` compatible (old retro-go API); GPL-2 / per-core | **High** (Zelda3/SMW), Medium (7800, CPC) |
| [esp-cpp/esp-box-emu](https://github.com/esp-cpp/esp-box-emu) (136★) | ESP32-S3 emulator collection; **Star Wars: Dark Forces** port | No | High: C++ `espp` framework, not retro-go; MIT | Medium-high (FPS port) |
| [Svarkovsky/s3-msx-pc](https://github.com/Svarkovsky/s3-msx-pc) (60★) | Deeply optimised MSX2 on ESP32-S3 with LCD_CAM VGA output (featured on CNX-Software) | fMSX yes | License NOASSERTION; ideas only | Low-medium: mine it for fMSX speed-ups |
| [kbeckmann/retro-go-stm32](https://github.com/kbeckmann/retro-go-stm32) | Original G&W port, superseded by sylverb | — | — | None |
| [rapha-tech/retro-go](https://github.com/rapha-tech/retro-go) | `GBA_dynarec` (RISC-V only), `osd` (transparent OSD), `self-updater` (2024) | No | P4 only / low | Low |
| [Rbel12b/retro-go](https://github.com/Rbel12b/retro-go) | VGA output via bitluni's ESP32-S3 VGA lib | No | Medium | Low |
| [vanBassum/retro-go](https://github.com/vanBassum/retro-go) | WT-SC01-PLUS target (**ESP32-S3 + 8080 parallel display**, like ours), MCP23S17 gamepad, local `sdmmc` override for the SD CMD59 issue | We have our own 8080 driver | Reference only | Low |
| [fffonion/retro-go](https://github.com/fffonion/retro-go) | gpSP with RISC-V JIT for ESP32-S31 | No | Not for Xtensa | Low |
| [devinzhang91/retro-go](https://github.com/devinzhang91/retro-go) | esplay-nano target + USB MSC | No | See ashkan89 | Low |

## Checked but nothing new for us

These forks only add a board target, pin maps, CI/Docker tweaks, ROM
uploads or translations, with no new emulators, ports or reusable features:

- **Board targets:**
  - Hzrd-code (LilyGO T-Deck / T-Deck Plus keyboard + PMU)
  - greigs (`openbrickgb`)
  - canwdev (ESPlay Micro, 20 kHz backlight PWM)
  - mk-822 (T-HMI)
  - lakiax (Xbox BT controller + 0.96" screen)
  - bphermansson (IceQueen)
  - aseoista (REDROID-GO, already upstream in `dev`)
  - goshansp (brutzelboy, already upstream)
  - GBeetle (ESP32-P4)
  - Chreeperfighter (RV32IM emulator target)
  - KhaledMahfouz5 (Arduino UART keypad)
  - jhq198 (xueersi board)
  - wheniseeyouagain (Katarina/Majula themes, Chinese font)
  - longxiangam (C19 target, font converter with glyph positions)
  - 206003723 (RETRO-BOY-COLOR hardware files)
  - CodingTheRobot, ohdarling, jobitjoseph (ST7789 variants)
- **CI/config-only or ROM/binary uploads:**
  - muhammed251210ai
  - Pilothorizon
  - kamilstanik516-cmd
  - serofuku (VFS image injector script)
  - Dewey1975
  - gitboy123455
  - VIHAAN121317
  - skofen
  - KiKi170987
  - Jojotheamazing
  - asger-andersen
  - hazzed-codez
  - pceslayer
  - Zerolone, marchetto1983, hagbardZ and other DynaMight1124 forks (no own commits)
- **Documentation-only:** simplyrohan (BUILDING/PATCHING docs).
- **About 250 remaining forks:** 0–2 commits ahead, or years stale.

## Suggested order of work

1. **Duke3D fixes.** Cherry-pick from DynaMight1124 `Duke3D` into
   `duke3d-go`, then verify on the board. It's low effort and fixes a known
   open item.
2. **alecu's `rg_system_vlog` overflow and `rg_task_create` race fixes.**
   These are small and generic.
3. **Bootstrap flasher.** Decide between it and a rebalanced partition map;
   everything below needs flash space.
4. **Cannonball, ROTT and OpenLara.** Bundle them into one `retro-ports`-style
   app to save partitions.
5. **Zelda 3 / SMW native ports.** A larger project, with the biggest payoff
   for the SNES-first goal.
6. **New systems: WonderSwan, C64 and PICO-8.** Do them by user interest.
