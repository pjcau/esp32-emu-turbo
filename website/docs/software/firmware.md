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
    ├── gen/       .bin / .md files
    ├── lynx/      .lnx files
    └── gw/        .gw files
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
Most SNES games are 1–4 MB. Games with special chips (SA-1, SuperFX) are larger and may not be compatible with snes9x on ESP32-S3.
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
| `retro-core.bin` | All emulators (NES, GB, GBC, SMS, GG, PCE, Lynx, SNES, G&W) | ~2.5 MB | ~17% |
| `gwenesis.bin` | Sega Genesis / Mega Drive (standalone) | ~1.5 MB | ~50% |
| `prboom-go.bin` | Doom port (PrBoom) | ~1.5 MB | ~50% |
| `fmsx.bin` | MSX emulator | 655 KB | 79% |

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
`pc` art), SG-1000, Atari 2600, and the missing pieces of GBA, MSX and Neo Geo
Pocket.

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
scripts/board_ctl.py put ~/rom.sfc "/sd/roms/snes/rom.sfc"   # base64 over USB, ~38 KB/s (from the launcher)
scripts/board_ctl.py launch snes "/sd/roms/snes/rom.sfc"
scripts/board_ctl.py key start 150              # tap; "key a+b", "hold right", "release"
scripts/board_ctl.py save 0 / load 0            # emulator save state
scripts/board_ctl.py resume snes "/sd/roms/snes/rom.sfc"     # launch + load slot 0 = repeatable scene
scripts/board_ctl.py capture 10                 # SNES_PROF counters, averaged
scripts/board_cam.py                            # one webcam frame of the screen
```

Injected keys are OR-ed into the gamepad state, so menus and games see real
presses; app switches and save states run at the frame boundary
(`rg_system_tick()`), not from the input task. `scripts/snes_bench.py` resumes
the SNES benchmark scenes and prints a comparison table;
`scripts/emu_check.py` launches every other core's test ROM and reads the
`FPS/BUSY` line below.

| Step | Core | Test ROM | Target | Measured (article 0003, 2026-09-14, `emu_check.py`) |
|:---|:---|:---|:---|:---|
| 3.1 | nofrendo (NES) | Super Mario Bros / owlia | 60 fps | ✅ 60 fps, BUSY 36% / 31%, 30 drawn (frameskip 1) |
| 3.2 | gnuboy (GB) | Tetris | 60 fps | ✅ 60 fps, BUSY 34%, 30 drawn |
| 3.3 | gnuboy (GBC) | Space Invaders / ucity | 60 fps | ✅ 60 fps, BUSY 53% / 35%, 30 drawn |
| 3.4 | smsplus (SMS) | Silver Valley | 60 fps | ✅ 60 fps, BUSY 37%, 60 drawn |
| 3.5 | smsplus (GG) | Swabby | 60 fps | ✅ 60 fps, BUSY 43%, 60 drawn |
| 3.6 | pce-go (PCE) | Reflectron | 60 fps | ✅ 60 fps, BUSY 43%, 30 drawn (intro text screen) |
| 3.7 | handy (Lynx) | — | 60 fps | no ROM on the card yet |
| 3.8 | gwenesis (Genesis) | miniplanets | 50-60 fps | ✅ 60 fps, **30 drawn** — YM2612 synthesis moved to core 1 (was 20 drawn, BUSY 93% with the FM chip on core 0) |
| 3.9 | gw-emulator (G&W) | — | 60 fps | no ROM on the card yet |
| 3.10 | smsplus (SG-1000) | — | 60 fps | enabled 2026-09-14, no ROM yet |
| 3.11 | RACE (Neo Geo Pocket / Color, `retro-extra`) | — | 60 fps | ported from libretro RACE 2026-09-14, untested |
| 3.12 | Stella (Atari 2600, `retro-extra`) | — | 60 fps | ported from stella-odroid-go 2026-09-14, untested |
| 3.13 | duke3d-go (Duke Nukem 3D) | Duke3D 1.3D shareware `.grp` | playable | ported from the upstream `duke3d` branch 2026-09-14, untested |
| — | snes9x (SNES) | 7 scenes | 60 fps (Phase 4) | ✅ 60 emulated fps on 6 of 7 (Kart 57), 19-26 drawn — see [SNES Optimization](snes-optimization#measured-log-2026-09-13--14--read-this-before-the-steps) |

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

**Partition table (2026-09-14).** `rg_tool.py` now lays out launcher 1 MB,
retro-core 1.5 MB, prboom-go 768 KB, gwenesis 1 MB, fmsx 576 KB,
duke3d-go 1 MB and retro-extra 2 MB (RACE + Stella live apart because
their ~30 KB of static tables each would take internal RAM from every
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
the console remote control are shared by every app; `gwenesis`, `fmsx` and
`prboom-go` must be rebuilt after a shared-component change or they keep
the old code (and, without the console, block the host's USB writes).

Super Boss Gaiden (SNES homebrew) hangs snes9x and is not usable as a
benchmark; Super Mario Kart (Mode 7) behaves like Super Mario World.

For SNES-specific optimization (Phase 4) and why audio stays on the main chip instead of a coprocessor, see [SNES Optimization](snes-optimization#audio-no-coprocessor).

---

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
