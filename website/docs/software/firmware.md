---
id: firmware
title: ESP32 Firmware
sidebar_position: 2
---

# ESP32 Firmware

ESP-IDF v5.x firmware for the ESP32 Emu Turbo hardware. Phase 1 validates all hardware subsystems, Phase 2 integrates Retro-Go, Phase 3 enables all emulator cores. Phases 1 and 2 are complete and proven on the v4.9.0 first article (bring-up GREEN, Retro-Go NES at 60 fps, 2026-09-12); Phase 3 is in progress.

---

## Phase 1 — Hardware Abstraction

Standalone ESP-IDF v5.x project in `software/` that validates all hardware before integrating Retro-Go. See [`software/README.md`](https://github.com/pjcau/esp32-emu-turbo/blob/main/software/README.md) for build instructions.

| Step | Task | Details | Status |
|:---|:---|:---|:---|
| 1.1 | ESP-IDF v5.x project setup | sdkconfig for N16R8 (240MHz, 16MB flash, 8MB PSRAM) | ✅ Done |
| 1.2 | ILI9488 display driver (i80 8-bit parallel) | `esp_lcd_panel_io_i80` + `esp_lcd_ili9488` component, 20MHz | ✅ Done |
| 1.3 | Display test pattern | Color bars, fill screen, status indicators | ✅ Done |
| 1.4 | SD card (SPI mode) | `esp_vfs_fat_sdspi_mount`, FAT32, ROM directory scanner | ✅ Done |
| 1.5 | 12-button input | GPIO polling @ 1ms, bitmask API, HW RC debounce | ✅ Done |
| 1.6 | Audio output | `i2s_pdm_tx` PDM sigma-delta 32kHz 16-bit mono, 440Hz test tone. Only DOUT (GPIO17) is routed — BCLK/LRCK unused; the PAM8403 input RC network reconstructs the analog signal. | ✅ Done |
| 1.7 | Power management | **Not available on this board**: the IP5306's I2C is not routed (GPIO33/34 belong to the Octal PSRAM — see `board_config.h`). Charge state is the on-board LED only; `power.c` survives as a stub | ⚠️ N/A on hardware |

### Firmware project structure

```
software/
├── CMakeLists.txt              ESP-IDF project root
├── sdkconfig.defaults          ESP32-S3 N16R8 hardware config
├── partitions.csv              4MB app + 12MB storage
└── main/
    ├── idf_component.yml       esp_lcd_ili9488 ^1.4.0
    ├── board_config.h          All GPIO pin definitions (source of truth)
    ├── main.c                  Test harness → interactive button display
    ├── display.c/h             ILI9488 320×480 i80 parallel (backlight is hardwired — `display_set_backlight()` is a no-op)
    ├── input.c/h               12 buttons, active-low, bitmask polling
    ├── sdcard.c/h              SPI @ 20MHz, FAT32, ROM listing
    ├── audio.c/h               I2S PDM TX (sigma-delta) → PAM8403 amplifier
    └── power.c/h               stub — IP5306 I2C is NOT routed on this PCB (GPIO33/34 = Octal PSRAM)
```

### Build & flash (Docker)

No local toolchain needed — the build runs inside the official `espressif/idf:v5.4` Docker image.

```bash
# Build firmware
make firmware-build

# Flash + serial monitor (connect board, hold SELECT at power-on)
make firmware-flash

# Custom USB port
ESP_PORT=/dev/ttyACM0 make firmware-flash
```

Native ESP-IDF is also supported — see [`software/README.md`](https://github.com/pjcau/esp32-emu-turbo/blob/main/software/README.md) for details.

### Test sequence on boot

1. Display shows color bars for 3 seconds (verifies 8-bit data bus)
2. Power status line in the serial log (IP5306 I2C is not routed — no battery %/charge readout; charge state is the on-board LED only)
3. All 12 button GPIOs initialized
4. SD card mounted, ROM directories scanned
5. 440 Hz test tone plays for 2 seconds
6. Interactive mode: button presses shown on screen + serial

---

## SD Card Setup

The console loads ROMs from a micro SD card formatted as **FAT32**. Each emulated system has its own folder under `/roms/`.

### Directory structure

```
SD Card (FAT32)
└── roms/
    ├── nes/       .nes files
    ├── snes/      .smc / .sfc files
    ├── gb/        .gb files
    ├── gbc/       .gbc files
    ├── sms/       .sms files
    ├── gg/        .gg files
    ├── pce/       .pce files
    └── gen/       .bin / .md files
```

### Preparation steps

1. **Format** the micro SD card as FAT32 (most cards come pre-formatted)
2. **Create** the `roms/` directory in the root of the card
3. **Create sub-folders** for each system you want to emulate
4. **Copy ROM files** into the matching folder

### Automated setup

A script is provided to format the SD card and copy test ROMs in one step:

```bash
# Format SD card as FAT32 + copy all homebrew test ROMs
sudo ./scripts/setup-sdcard.sh /dev/sdX

# Copy only (skip formatting)
sudo ./scripts/setup-sdcard.sh /dev/sdX --no-format
```

### Included homebrew test ROMs

The project includes 8 freely distributable homebrew ROMs in `test-roms/` for testing without commercial ROMs:

| System | ROM | Author | Size |
|:---|:---|:---|:---|
| NES | Owlia | Gradual Games | 512 KB |
| GB | Blargg's CPU Instructions | Blargg | 64 KB |
| GBC | ucity v1.3 | AntonioND | 128 KB |
| SMS | Silver Valley | Enrique Ruiz | 256 KB |
| GG | Swabby v1.11 | Anders S. Jensen | 128 KB |
| PCE | Reflectron | Aetherbyte | 256 KB |
| Genesis | Miniplanets | Sik | 256 KB |
| SNES | Super Boss Gaiden v1.2 | Dieter Von Laser | 512 KB |

### Recommended commercial test ROMs

| System | ROM | File | Size | Why |
|:---|:---|:---|:---|:---|
| NES | Super Mario Bros | `smb.nes` | 40 KB | Universal test — scrolling, sprites, audio |
| SNES | Super Mario World | `smw.smc` | 512 KB | Good baseline — 2 BG layers, Mode 1 |
| SNES | FF6 | `ff6.smc` | 3 MB | Turn-based RPG — best SNES genre for ESP32 |
| GB | Tetris | `tetris.gb` | 32 KB | Minimal — verifies basic emulation |
| Genesis | Sonic | `sonic.bin` | 512 KB | Fast scrolling stress test |

### Size limits

| Constraint | Value |
|:---|:---|
| Max ROM size (PSRAM) | **6 MB** |
| SD card format | FAT32 (max 32 GB recommended) |
| Max filename length | 255 characters (long filename support enabled) |

:::tip SNES ROM sizes
Most SNES games are 1–4 MB. SuperFX games (Star Fox) run since 2026-09-27: the GSU runs on core 1 and needs the full 6 MB ROM buffer (the GSU sees the ROM through a 2 MB mirror). SA-1 games are still not supported.
:::

---

## Phase 2 — Retro-Go Integration

Fork and adapt Retro-Go for our hardware. Retro-Go is included as a git submodule at `retro-go/` and built via a separate Docker Compose file.

| Step | Task | Details | Status |
|:---|:---|:---|:---|
| 2.1 | Add `ducalex/retro-go` as submodule | `retro-go/` directory, upstream repo | ✅ Done |
| 2.2 | Create target `targets/esp32-emu-turbo/` | `config.h` + `env.py` + `sdkconfig` | ✅ Done |
| 2.3 | Docker build pipeline | `docker-compose.retro-go.yml` + Makefile targets | ✅ Done |
| 2.4 | Custom display driver `ili9488_i80.h` | 8-bit i80 parallel via `esp_lcd_panel_io_i80`, async DMA, 5-buffer pool | ✅ Done |
| 2.5 | Frame scaling | Automatic via Retro-Go core (480x320 landscape — the panel sits along the handheld's long axis; the earlier portrait plan was wrong, first article 2026-09-11) | ✅ Done |
| 2.6 | Input mapping | 12 GPIO direct buttons + MENU=SELECT (GPIO 0) | ✅ Done |
| 2.7 | Audio routing | I2S **PDM TX** on DOUT only (GPIO17) → C22 → PAM8403. No external DAC, no BCLK/LRCK — same path as step 1.6. Since 2026-09-12 the fork drives the PDM peripheral in IDF **DAC line mode** (128 × 48 kHz carrier, tuned sigma-delta scaling): music is distinct; the residual hiss is the missing reconstruction filter (R38, RC rework sheet ready) and has no software lever left | ✅ Done |
| 2.8 | First boot: NES test | nofrendo on the v4.9.0 first article: Owlia (homebrew) and Mario Bros played from SD, all 12 buttons verified (2026-09-11). **Super Mario Bros: 60 fps, 35% busy** (2026-09-12) — target met. Four fork fixes on the way: i80 0x3C continuation, landscape, silent PDM at volume 0, RIGHT/A GPIO swap (R39-HIGH-1) | ✅ Done |

### Build & flash (Docker)

Retro-Go uses a separate Docker Compose file (`docker-compose.retro-go.yml`) with the `espressif/idf:v5.4` image.

```bash
# Build all Retro-Go apps (launcher + emulators)
make retro-go-build

# Build launcher only (quick test)
make retro-go-build-launcher

# Flash firmware + serial monitor
make retro-go-flash

# Serial monitor only
make retro-go-monitor

# Custom USB port
ESP_PORT=/dev/ttyACM0 make retro-go-flash

# Clean build cache
make retro-go-clean
```

### Build output

All 5 Retro-Go applications compile successfully for the ESP32 Emu Turbo target (ESP-IDF v5.4, ESP32-S3):

| Binary | Contents | Size | Partition free |
|:---|:---|:---|:---|
| `launcher.bin` | Retro-Go launcher UI + ROM browser | 1037 KB | 67% |
| `retro-core.bin` | All emulators (NES, SNES, GB, GBC, SMS, GG, SG-1000, Coleco, PCE) | ~2.5 MB | ~17% |
| `gwenesis.bin` | Sega Genesis / Mega Drive (standalone) | ~1.5 MB | ~50% |
| `prboom-go.bin` | Doom port (PrBoom) | ~1.5 MB | ~50% |

:::note
The build produces `Device doesn't support fw format, try build-img!` at the end — this is expected. Our target uses individual app flashing via `make retro-go-flash`, not a combined firmware image.
:::

### Target configuration

The target lives at `retro-go/components/retro-go/targets/esp32-emu-turbo/` with:
- `config.h` — GPIO mapping, display/audio/input config (mirrors `board_config.h`)
- `env.py` — `IDF_TARGET = "esp32s3"`, firmware format
- `sdkconfig` — ESP-IDF config (240MHz, 16MB flash QIO, 8MB Octal PSRAM)

### GPIO mapping verification

All 31 GPIO pins have been cross-verified between three sources with **zero discrepancies**:

| Group | Pins | board_config.h | Retro-Go config.h | KiCad schematic |
|:---|:---|:---|:---|:---|
| Display data D0–D7 | GPIO 4–11 | ✅ | ✅ | ✅ |
| Display control | GPIO 12–14, 46 | ✅ | ✅ | ✅ |
| Display hardwired | RD → +3V3, BL → +5V via R27 (no GPIO) | ✅ | ✅ | ✅ |
| SD card SPI | GPIO 44, 43, 38, 39 | ✅ | ✅ | ✅ |
| Audio (PDM DOUT only) | GPIO 17 | ✅ | ✅ | ✅ |
| D-pad | GPIO 40, 41, 42, 1 | ✅ | ✅ | ✅ |
| Face buttons | GPIO 2, 48, 47, 21 | ✅ | ✅ | ✅ |
| System buttons | GPIO 18, 0 | ✅ | ✅ | ✅ |
| Shoulder buttons | GPIO 45, 3 | ✅ | ✅ | ✅ |

**Notes:**
- MENU and SELECT share GPIO 0 in Retro-Go (intentional — 12 physical buttons, 13 logical)
- GPIO 19/20 are used for native USB data (D-/D+) — firmware flash + CDC debug console
- GPIO 3 is BTN_R, GPIO 45 is BTN_L (shoulder buttons freed by hardwiring LCD_RD and the backlight on the PCB)
- GPIO 43 is SD_MISO (was TX0 UART debug, replaced by USB native)
- GPIO 26–32 are the module's internal SPI flash bus and GPIO 33–37 the Octal PSRAM — neither may be used
- GPIO 15/16 are unconnected: the audio path is PDM and needs only DOUT

### Display driver: `ili9488_i80.h`

Custom driver replacing Retro-Go's SPI-based `ili9341.h` with 8-bit 8080 parallel interface. Located at `retro-go/components/retro-go/drivers/display/ili9488_i80.h`.

| Feature | Value |
|:---|:---|
| Bus | 8-bit i80 parallel (`esp_lcd_panel_io_i80`) |
| Clock | 20 MHz write clock |
| Resolution | 480x320 landscape (MADCTL MV; panel native 320x480) |
| Color format | RGB565 (16-bit) |
| DMA | Async with 5-buffer pool |
| Backlight | Always-on — LED-A fed from **+5V through R27 (20 Ω)** on the PCB, no GPIO control |
| Driver ID | `RG_SCREEN_DRIVER 2` |

The driver uses `esp_lcd_panel_io_tx_param` for commands (CASET/RASET) and `esp_lcd_panel_io_tx_color` for async DMA pixel transfers. A completion callback recycles buffers to the pool, providing natural backpressure without explicit sync.

### Launcher art for new systems

Every launcher tab shows three images from `retro-go/themes/default/`,
named after the tab's short name: `logo_<tab>.png` (46×50),
`banner_<tab>.png` (272×24, magenta `0xF81F` = transparent) and
`background_<tab>.png` (320×240). Systems the upstream theme has no art for
take theirs from **[es-theme-gbz35](https://github.com/rxbrad/es-theme-gbz35)**
by rxbrad, the EmulationStation theme retro-go already credits for its
backgrounds (its art in turn comes from the Carbon, Spare and SimpleBigArt
themes; the repository ships no licence file, the project is
non-commercial).

`retro-go/tools/import_gbz35_art.py` does the conversion from the theme's
originals: `background.png` downscaled, the `system.svg` logo rendered with a
headless Chromium into the banner, and the system icon of the background
turned into a light logo card. It only writes the images that are missing.

```bash
git clone --depth 1 https://github.com/rxbrad/es-theme-gbz35.git /tmp/gbz35
cd retro-go
python3 tools/import_gbz35_art.py /tmp/gbz35 <path-to>/chrome-headless-shell
python3 tools/gen_images.py      # re-embed themes/default/*.png in launcher/main/images.c
```

A new system is one line in the script's `SYSTEMS` table (tab short name →
theme folder). Imported so far: Arcade (MAME), Duke Nukem 3D (the theme's
`pc` art), SG-1000, and the missing pieces of GBA and Neo Geo
Pocket (the MSX art went with fMSX, the Atari 2600 art with Stella, both removed 2026-09-29).

---

## Phase 3 — All Emulators at Full Speed

Enable and test each emulator core on the first article. The number to read is
the `[debug] ... BUSY:x%, FPS:t (S:s R:r+p)` line `rg_system` prints once a
second on the USB serial (t = emulated frames/s, s = skipped, r = rendered).
Bench rule: the battery must be **unplugged from J3** for any serial session
from a laptop port — with a cell attached the IP5306 starts charging the moment
it sees VBUS and a 500 mA port collapses (`device not accepting address,
error -71`).

### Driving the board from the host

Since 2026-09-14 the firmware answers commands on the USB console
(`RG_GAMEPAD_CONSOLE` in `rg_input.c`, enabled in the esp32-emu-turbo
`config.h`): every line on stdin is a command, every reply is a `CTL ...`
line. `scripts/board_ctl.py` wraps it:

```bash
scripts/board_ctl.py ping                       # which app is running
scripts/board_ctl.py ls /sd/roms/snes
scripts/board_ctl.py put ~/rom.sfc "/sd/roms/snes/rom.sfc"   # raw bytes (putb) + CRC32 check, from the launcher: 190-490 KB/s, bound by the card's SPI write speed (USB side ~520 KB/s)
scripts/board_ctl.py launch snes "/sd/roms/snes/rom.sfc"
scripts/board_ctl.py key start 150              # tap; "key a+b", "hold right", "release"
scripts/board_ctl.py save 0 / load 0            # emulator save state
scripts/board_ctl.py resume snes "/sd/roms/snes/rom.sfc"     # launch + load slot 0 = repeatable scene
scripts/board_ctl.py capture 10                 # SNES_PROF counters, averaged
scripts/board_cam.py                            # one webcam frame of the screen
```

`put` streams raw bytes (`putb`) read straight from the USB-Serial-JTAG FIFO
while a second task writes the card, and fails on a CRC32 mismatch; it falls
back to base64 on firmware without `putb`. The console also takes
`format ERASE-ALL-SD-DATA` (a new FAT with 32 KB clusters, also on a card that
no longer mounts) — test a replacement card for write retention before
restoring onto it (a 32 GB card that dropped FAT writes was found this way).

Injected keys are OR-ed into the gamepad state, so menus and games see real
presses; app switches and save states run at the frame boundary
(`rg_system_tick()`), not from the input task. `scripts/snes_bench.py` resumes
the SNES benchmark scenes and prints a comparison table;
`scripts/emu_check.py` launches every other core's test ROM and reads the
`FPS/BUSY` line below.

| Step | Core | Test ROM | Target | Measured (article 0003; `emu_check.py` rerun 2026-09-27) |
|:---|:---|:---|:---|:---|
| 3.1 | nofrendo (NES) | Super Mario Bros / owlia | 60 fps | ✅ 60 fps, BUSY 36% / 31%, 30 drawn (frameskip 1) — unchanged 2026-09-27 |
| 3.2 | gnuboy (GB) | Tetris | 60 fps | ✅ 60 fps, BUSY 34%, 30 drawn |
| 3.3 | gnuboy (GBC) | Space Invaders / ucity | 60 fps | ✅ 60 fps, BUSY 53% / 35%, 30 drawn |
| 3.4 | smsplus (SMS) | Silver Valley | 60 fps | ✅ 60 fps, BUSY 35%, 55 drawn |
| 3.5 | smsplus (GG) | Swabby | 60 fps | ✅ 60 fps, BUSY 40%, 55 drawn |
| 3.6 | pce-go (PCE) | Reflectron / Street Fighter II' CE (2.5 MB HuCard) | 60 fps | ✅ 60 fps, BUSY 43%, 30 drawn; SF2' CE 60 fps, BUSY 33-43% (2026-09-26). Audio moved from 22050 to 32000 Hz: it crackled |
| 3.7 | ~~handy (Lynx)~~ | — | — | removed 2026-09-29: not needed (core, launcher tab and art deleted) |
| 3.8 | gwenesis (Genesis) | miniplanets | 50-60 fps | ✅ 59.4 fps, BUSY 94%, 29 drawn — YM2612 synthesis on core 1; audio resampled from 26633 to 32000 Hz (2026-09-27) |
| 3.9 | ~~gw-emulator (G&W)~~ | — | — | removed 2026-09-29: not needed (core, launcher tab and art deleted) |
| 3.10 | smsplus (SG-1000) | GP World | 60 fps | ✅ 60 fps, BUSY 33%, 55 drawn (START is pause: `emu_check` presses none) |
| 3.11 | RACE (Neo Geo Pocket / Color, `retro-extra`) | Metal Slug 1st Mission | 60 fps | ✅ 60 fps, ~29 drawn, BUSY 93–99%; sound chip at 16 kHz doubled to 32 kHz (2026-09-27) |
| 3.12 | ~~Stella (Atari 2600, `retro-extra`)~~ | — | — | removed 2026-09-29: not needed (core, launcher tab and art deleted) |
| 3.13 | duke3d-go (Duke Nukem 3D) | Duke3D 1.3D shareware `.grp` | playable | ✅ playable 2026-09-27: E1L1 48–53 fps with movement and fire, menus 73 fps, audio 16 kHz mix doubled to 32 kHz. Fixed on the way: FatFs overwritten by an ODROID-GO audio conversion, START arriving as Insert, the frame drawn into the surface being sent (broken menus), a non-volatile spin-wait hanging the level start |
| 3.14 | mame-go (arcade, MAME 0.37b5) | Pac-Man, 1942, 1943, free mamedev.org ROMs, Blood Bros., Aero Fighters | 60 fps / native | ✅ Pac-Man, 1942, Robby Roto 60; Exidy/Circus boards 57 (native); 1943 60 emulated / 27 drawn; Blood Bros. 60, Aero Fighters 47–57 after the idle-loop speed-ups — see [Arcade (MAME)](../next-steps/arcade) |
| 3.15 | ~~fMSX (MSX)~~ | — | — | removed 2026-09-29 (not needed): the 640 KB partition went to the GBA app `gbsp` |
| 3.16 | prboom-go (DOOM) | Freedoom 1 | 35 fps (engine rate) | ✅ 35 fps, BUSY 100%; mix at 16 kHz doubled to 32 kHz, sfx interpolated. The in-game crash is fixed (2026-09-27, fork `66d251ed`): the game outgrew the 8 KB main-task stack (9.4 KB used in E1 play) and now runs in its own 16 KB task; the lump cache keeps 1.5 MB of PSRAM free for the rest of the system instead of filling it. 6 min of scripted play without a crash |
| 3.17 | wolf3d-go (Wolfenstein 3D, Wolf4SDL via [retro-go-pro](https://github.com/pcgamer404/retro-go-pro)) | shareware v1.4 `.WL1` in `/sd/roms/wolf3d/data/` | 70 fps (engine cap) | ✅ 62 fps, BUSY 34% in E1M1 (2026-09-27); mix at 16 kHz doubled to 32 kHz. Built for shareware data: the full game (`.WL6`) needs `version.h` changed and a rebuild. Menus redraw only on change (1–2 fps in the HUD is normal there) |
| 3.18 | quake-go (WinQuake software renderer, via retro-go-pro) | shareware `id1/pak0.pak` | playable | ✅ played (2026-09-27): New Game → start map, 90 s of scripted walking/turning/firing: 39.7 fps average (19–56), no crash; attract demo 21–44 fps, BUSY 100%, heap stable; mixer at 32 kHz on core 1. The 18.7 MB `pak0.pak` is copied with a card reader (console `put` is ~40 KB/s) |
| 3.19 | opentyrian-go (OpenTyrian, via [DynaMight1124/retro-go](https://github.com/DynaMight1124/retro-go/tree/opentyrian)) | Tyrian 2.1 freeware data in `/sd/roms/opentyrian/` | 35 fps (engine rate) | ✅ 36 fps, BUSY ~30% in game, 2 min of play without a crash (2026-09-27, fork `a4b3c228`). Audio resampled 11 → 32 kHz, mixer task above the display task (it skipped at priority 2), music gain 2x. Data: `tyrian21.zip` from [camanis.net](https://camanis.net/tyrian/tyrian21.zip) (freeware since 2004) without the DOS `.exe/.ovl/.doc`, plus an empty `OpenTyrian.tyr` for the launcher |
| — | ColecoVision (smsplus) | Pac-Man | 60 fps | ✅ 60 fps, BUSY 31% (START opens the keypad: `emu_check` presses none) |
| — | snes9x + SuperFX (SNES) | Star Fox (Rev 2) | 60 fps | ✅ 53–60 emulated fps, 7–10 drawn, BUSY 99% (2026-09-27, fork `98f88705`): SuperFX from snes9x2005, GSU on core 1 while core 0 emulates the 65816 (inline it cost 50–67% of each second: 22–30 fps). Save states include the GSU state (saved and reloaded during the 3D flight on the board, 2026-09-27) |
| — | snes9x (SNES) | 7 scenes | 60 fps (Phase 4) | ✅ 60 emulated fps on 6 of 7 (Kart 57), 19-26 drawn — see [SNES Optimization](snes-optimization#measured-log-2026-09-13--14--read-this-before-the-steps) |

**Audio sample rate rule (2026-09-26): every app runs its audio at 32000 Hz.**
The PDM sink (`drivers/audio/pdm.c`, DAC line mode) derives its clocks from
`sample_rate / 100`, and at 22050 Hz the output was wrong in two apps: in
mame-go the music ignored the volume setting (loud at volume 5, while the
launcher splash at the same volume was quiet), in pce-go it crackled. Both
were fixed by moving to 32000 Hz, where every other core already ran. A new
core must use 32000 too (or verify its rate on the speaker first).

The non-SNES cores run with retro-go's default frameskip 1 (every other
frame drawn) and 30-55% CPU, so they have room for frameskip 0 once the
display path is tuned. Genesis: the frame is M68K 5.5 ms + Z80 3.1 ms +
VDP 11.3 ms per drawn frame on core 0, and the YM2612 (6 ms per frame,
37% of the budget, measured with `GEN_PROF=1`) now runs on core 1 —
register writes are logged with their clock and replayed with exact sync
one frame later (`ym2612.c`, `GWENESIS_YM_WORKER`). Audio lags the
picture by one frame.

**Pending on-device verification (2026-09-14).** Steps 3.10-3.13 were
compiled with the board disconnected and have never booted on it. First
bench session: flash the full image (below), populate `/roms/sg1`,
`/roms/ngp`, `/roms/a26`, `/roms/duke3d` (the Duke 1.3D shareware `.grp`
plus its `.CON`/`.RTS`/`.DMO` files), run `scripts/emu_check.py` with the
webcam, then fix what breaks — expected suspects: button mapping, audio
sample rates (NGP 22 kHz, 2600 31.4 kHz, Duke 11 kHz mono→stereo), Duke3D
file paths (`Engine/cache.c game_dir`), Stella frame height per ROM.

**Partition table (2026-09-26).** Since the arcade app: launcher 1.125 MB
(it had filled 1 MB), mame-go 2 MB, and a 4 MB `mamerom` data partition
where mame-go keeps big read-only ROM regions memory-mapped (arcade page).
The image is 14.8 MB; a board flashed before needs the full image again.

**Partition table (2026-09-14).** `rg_tool.py` now lays out launcher 1 MB,
retro-core 1.5 MB, prboom-go 768 KB, gwenesis 1 MB, fmsx 576 KB (removed 2026-09-29),
duke3d-go 1 MB and retro-extra 2 MB (RACE lives apart because
its ~26 KB of static tables would take internal RAM from every
retro-core emulator). A board flashed before that date needs the full
image once — `software/retro-go-build/retro-go_esp32-emu-turbo.img` at
offset 0 (`rg_tool.py install`, or `esptool.py write_flash 0x0 …`); single
apps flash as before afterwards. Save states and settings on the SD card
are untouched.

**Debug HUD.** Options menu → *Debug HUD: On* (or `board_ctl.py raw "hud
on"`) prints FPS, drawn, skipped, busy and free internal heap once a
second in the left letterbox bar of every emulator, plus per-core lines
where a profiling build provides them (SNES: R, N, strips, tiles…; Genesis:
68K/Z80/VDP/YM). The bar must be wide enough — with a 320-pixel-wide
console (Genesis) set *Scaling: Off* to read it.

**How the 60 fps claim is tested.** `scripts/emu_check.py` launches every
core's test ROM over the console, presses START twice and averages the
`rg_system` stats line for 6 s; `scripts/snes_bench.py` resumes the seven
SNES scenes (save states) and averages the `SNES_PROF` counters. Both are
run after every renderer change; the tables above and in
[SNES Optimization](snes-optimization) are their output. The 32 KB I-cache / 64 KB D-cache configuration and
the console remote control are shared by every app; `gwenesis`, `gbsp` and
`prboom-go` must be rebuilt after a shared-component change or they keep
the old code (and, without the console, block the host's USB writes).

Super Boss Gaiden (SNES homebrew) hangs snes9x and is not usable as a
benchmark; Super Mario Kart (Mode 7) behaves like Super Mario World.

For SNES-specific optimization (Phase 4) and why audio stays on the main chip instead of a coprocessor, see [SNES Optimization](snes-optimization#audio-no-coprocessor).

---

## Firmware update from the SD card (2026-09-28)

After one USB flash of a build that has it, apps are updated from the card:

1. Put `<app>.bin` (the image the build writes, e.g.
   `retro-go/mame-go/build/mame-go.bin`) in `retro-go/update/` on the card —
   `scripts/sd_update.py --card <mount> [apps]` copies them, or
   `scripts/sd_update.py --console [apps]` uploads them over USB (190-490 KB/s depending on the card)
   and reboots to the launcher.
2. At boot the launcher writes each image into the partition of the same
   name, verifies it (`esp_image_verify`) and renames the file to `.done`
   (`.failed` if the check fails).
3. `launcher.bin` cannot be written by the running launcher: it hands over
   to another app, whose boot writes the launcher partition and switches
   back (`components/retro-go/rg_update.c`, called at the end of
   `rg_system_init()`).

Tested on the board: OpenTyrian (585 KB) and the launcher itself (1.06 MB).
Limits: only app partitions — a change of the partition table (the sizes in
`rg_tool.py`) still needs `rg_tool.py install` over USB; an image larger
than its partition is refused by the script and by the board.

## Build & Flash

```bash
# Clone fork
git clone https://github.com/pjcau/retro-go.git
cd retro-go

# Build for ESP32 Emu Turbo
python3 rg_tool.py --target=esp32-emu-turbo build

# Flash via USB-C (GPIO0/SELECT = download mode at boot)
python3 rg_tool.py --target=esp32-emu-turbo flash

# Copy ROMs to SD card
# /roms/nes/  — .nes files
# /roms/snes/ — .smc/.sfc files
# /roms/gb/   — .gb files
# /roms/gbc/  — .gbc files
# /roms/sms/  — .sms files
# /roms/gg/   — .gg files
# /roms/pce/  — .pce files
# /roms/md/   — .bin/.md/.gen files (Mega Drive; the launcher scans /roms/<tab short name>)
```

For the full software architecture overview, see [Software Architecture](/docs/software).
