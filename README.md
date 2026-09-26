# ESP32 Emu Turbo

Handheld retro gaming console based on ESP32-S3 — **SNES** (primary) and **NES** (secondary) emulation.

## Project Goal

Build a portable battery-powered device based on ESP32-S3, capable of loading and playing retro games via SD card, with USB-C charging and an ILI9488 3.95" color LCD display.

## Where the project stands (2026-09-14)

- **The first article works.** Board v4.9.0 (article 0003, JLCPCB-assembled) passed
  every bring-up stage on 2026-09-11: USB power, rails, boot, display, SD, audio, all
  12 buttons, and **battery** — boots from the cell alone, charge-and-play, SW16
  charge-only, and the C33 wake pulse after the IP5306 light-load shutdown.
- **Every emulator runs at 60 fps.** NES, GB, GBC, SMS, GG, PC Engine and Genesis
  measured on the board (`scripts/emu_check.py`); Genesis needed its FM chip moved
  to the second core.
- **SNES runs at real speed.** 60 emulated fps on Super Mario World, Zelda ALttP,
  Mega Man X, Super Metroid and Donkey Kong Country with 19–26 drawn fps; Super
  Mario Kart at 57 (DSP-1 CPU load). Two days of renderer work, measured on seven
  save-state scenes — see below.
- **The board is driven from the host.** `scripts/board_ctl.py` launches ROMs,
  presses buttons, saves/loads states and reads the profiling counters over the USB
  console; a webcam checks the picture. A Debug HUD (options menu) shows FPS, drawn,
  busy and heap on every emulator.
- **No board defect found.** Three findings, all closed in firmware or deferred to v2:
  R37 (J4 FPC contact face inverted for the purchased panel — workaround validated),
  R38 (no PDM reconstruction filter — audible hiss, 1 kΩ + 10 nF rework sheet ready),
  R39 (module pins 38/39 were swapped in every project table — names fixed, copper
  was right).

Details: [first-boot session log](docs/first-boot-session-2026-08-29.md).

## Development Phases

### Phase 1 — Feasibility Analysis ✅
- Evaluate ESP32-S3 capabilities for SNES/NES emulation
- Select components (display, controller, power supply)

### Phase 2 — Hardware Design ✅
- KiCad electrical schematics (7 hierarchical sheets)
- OpenSCAD 3D enclosure model
- GPIO pin mapping and validation
- Docker rendering pipeline
- 4-layer PCB layout (160x75mm, JLCPCB-ready)

### Phase 3 — PCB Fabrication and First Article ✅
- Production files in `release_jlcpcb/` (current set **v4.9.0**: Gerber ZIP + BOM + CPL)
- All pre-production gates green (`make verify-all`): DFM, DFA, DRC, power-net integrity, JLCDFM
- First article (article 0003) assembled by JLCPCB and commissioned 2026-08-29 → 2026-09-11:
  bring-up firmware GREEN 53/0/6, stages 0–5 all PASS including battery
- Bench rules learned the hard way: unplug J3 for any flash/serial session from a
  laptop USB port (the IP5306 charge current collapses a 500 mA port); a freshly
  connected cell needs one USB "kick" before the IP5306 wakes from the switch
- v2 backlog: R37 top-contact J4, R38 PDM RC filter, J3 "+" and SPK polarity silkscreen

### Phase 4 — Software

#### 4.1 — Hardware Validation (ESP-IDF) ✅
Standalone firmware in `software/` to test all hardware before emulator integration.
- 1.1 ESP-IDF v5.x project setup (N16R8, 240MHz, 16MB flash, 8MB PSRAM) ✅
- 1.2 ILI9488 display driver (i80 8-bit parallel, 20MHz) ✅
- 1.3 Display test pattern (color bars) ✅
- 1.4 SD card via SPI (FAT32, ROM directory scan) ✅
- 1.5 12-button GPIO input (1ms polling, HW debounce) ✅
- 1.6 Audio output (I2S PDM on DOUT only → PAM8403, 440Hz test tone) ✅
- 1.7 IP5306 power management — N/A on this board (I2C not routed; charge state = LEDs) ⚠️

#### 4.2 — Retro-Go Integration ✅
Fork and adapt [Retro-Go](https://github.com/ducalex/retro-go) for our hardware (`retro-go/` git submodule).
- 2.1 Add retro-go as git submodule ✅
- 2.2 Create target `targets/esp32-emu-turbo/` (config.h, env.py, sdkconfig) ✅
- 2.3 Docker build pipeline (`docker-compose.retro-go.yml`) ✅
- 2.4 Custom display driver `ili9488_i80.h` (i80 parallel, async DMA, 5-buffer pool, 0x2C/0x3C continuation) ✅
- 2.5 Frame scaling (480x320 landscape, Retro-Go scaler) ✅
- 2.6 Input mapping (12 GPIO direct buttons) ✅
- 2.7 Audio routing (PDM DOUT → PAM8403, IDF DAC line mode) ✅
- 2.8 First boot: NES at 60 fps on the real board (Super Mario Bros, 2026-09-12) ✅

#### 4.3 — Emulator Testing ✅
Every core at target frame rate on the first article (2026-09-14, `scripts/emu_check.py`):
- 3.1 NES (nofrendo) → 60 fps, 31–36% busy ✅
- 3.2 / 3.3 Game Boy / Color (gnuboy) → 60 fps ✅
- 3.4 / 3.5 Master System / Game Gear (smsplus) → 60 fps, 60 drawn ✅
- 3.6 PC Engine (pce-go) → 60 fps ✅
- 3.7 Atari Lynx (handy), 3.9 Game & Watch — no test ROM on the card yet
- 3.8 Genesis (gwenesis) → 60 fps, 30 drawn — YM2612 synthesis on core 1 ✅

#### 4.3b — New cores, compiled but not yet run on the board (2026-09-14)
Built while the board was away; first thing to verify at the next bench session.
- **SG-1000** (smsplus, launcher entry) · **Neo Geo Pocket / Color** (libretro RACE) ·
  **Atari 2600** (Stella, from stella-odroid-go) · **Duke Nukem 3D** (upstream `duke3d`
  branch, ported: input, audio task, GRP as ROM)
- NGP + 2600 live in a new `retro-extra` app, Duke3D in `duke3d-go`; the **partition
  table changed** (retro-core 1.5 MB, + 1 MB + 2 MB) — flash the full image once:
  `software/retro-go-build/retro-go_esp32-emu-turbo.img` at 0x0 (`rg_tool.py install`).
- ROM folders ready in `test-roms/` (`sg1 ngp a26 duke3d lynx gw col msx doom`);
  `scripts/emu_check.py` picks the first ROM of each folder on the card.
- Not planned: GBA (no full-speed port exists for the ESP32-S3).

#### 4.4 — SNES Optimization (Milestone A reached)
Measured on seven save-state scenes (`scripts/snes_bench.py`), renderer cost per
drawn frame, baseline → now:

| Scene | R (ms) | fps emulated / drawn |
|:---|---:|:---|
| Super Mario World (map / level) | 18.2 → 16.4 / 14.8 | 60 / 26 |
| Zelda: A Link to the Past | 24.9 → 9.5 | 60 / 25 |
| Mega Man X | 12.9 → 10.9 | 60 / 24 |
| Super Metroid (Mode 7) | 24.6 → 14.4 | 60 / 22 |
| Donkey Kong Country | 16.1 → 11.6 | 60 / 19 |
| Super Mario Kart (Mode 7 + DSP-1) | 22.5 → 22.5 | 57 / 11 |

What paid: blank-tile cache, audio pacing credit, 32/64 KB caches, main z-buffer in
SRAM, a colour-math fast path when the sub-screen is empty (Zelda −56%), tile
writers with `restrict` pointers, Mode 7 invariants in locals, per-line backdrop
and palette-0 so HDMA gradients no longer split the frame into strips (DKC 97 → 1).
What did not: `IRAM_ATTR` on the renderer, VRAM in internal SRAM — the loops are
instruction-bound, not memory-bound. Also fixed on the way: the save-state loader
wrote the APU RAM through a stale pointer (heap corruption on any rebuild).

Open: painter's-order fast path, budget-driven frameskip, and the SNES APU on the
second core (the Kart/Metroid lever). Details and every measurement:
[`website/docs/software/snes-optimization.md`](website/docs/software/snes-optimization.md).

### Phase 5 — Final Version (v2)
- Respin with the first-article backlog (R37 + silkscreen) and an I2S amplifier in place of the PDM audio chain (no audio coprocessor — the second ESP32-S3 core covers it)
- 3D-printed enclosure
- Final assembly

## PCB Design

![PCB Bottom](/website/static/img/renders/pcba/pcba-bottom.png)
![PCB Top](/website/static/img/renders/pcba/pcba-iso-front.png)

| Parameter          | Value                                |
| ------------------ | ------------------------------------ |
| **Dimensions**     | 160 x 75 mm                          |
| **Layers**         | 4 (Signal / GND / Power / Signal)    |
| **Surface Finish** | ENIG                                 |
| **Assembly**       | JLCPCB PCBA (BOM + CPL in `release_jlcpcb/`) |
| **Trace Shorts**   | 0 (verified)                         |
| **Zone Fill**      | ✅ Inner layers filled (GND + 3V3/5V) |
| **Release**        | v4.9.0 — first article passed bring-up 2026-09-11 |
| **Estimated Cost** | ~$40/board (5 pcs, fully assembled)  |

## Key Requirements

| Component     | Specification                                                    |
| ------------- | ---------------------------------------------------------------- |
| **MCU**       | ESP32-S3 N16R8 (16MB flash, 8MB Octal PSRAM)                     |
| **Display**   | ILI9488 3.95" 320x480, 8-bit 8080 parallel, bare panel + 40P FPC |
| **Power**     | LiPo 3.7V 5000mAh + IP5306 (charger + boost) + SY8089 2A buck    |
| **Charging**  | USB-C (charge-and-play)                                          |
| **Audio**     | I2S PDM -> PAM8403 -> 28mm speaker                               |
| **Controls**  | 12 buttons (D-pad, ABXY, Start, Select, L, R)                    |
| **Storage**   | Micro SD card via SPI                                            |
| **Emulation** | SNES (primary), NES (secondary)                                  |

## Quick Start

### Clone (with submodules)

```bash
git clone --recurse-submodules https://github.com/pjcau/esp32-emu-turbo.git
cd esp32-emu-turbo

# If you already cloned without --recurse-submodules:
git submodule update --init --recursive
```

### Prerequisites

- **Python 3.12+**
- **KiCad 10** with `kicad-cli` (for local DRC/gerber export)
- **OrbStack** (lightweight Docker alternative, replaces Docker Desktop)

```bash
brew install --cask orbstack    # Container runtime (16x faster than Docker Desktop)
brew install --cask kicad       # Includes kicad-cli
```

### Generate hardware files

```bash
# Generate schematics (7 sheets + hierarchical root)
python3 -m scripts.generate_schematics hardware/kicad

# Generate PCB layout + JLCPCB exports
make generate-pcb

# Render PCB images (SVG + PNG + GIF)
make render-pcb

# Quick DFM check (1.4s, no Docker needed)
make verify-fast

# Full check pipeline: generate + DFM + DRC + gerbers + connectivity (~5s)
make fast-check

# Export Gerbers (local kicad-cli + Docker for zone fill only)
make export-gerbers-fast

# Full verification suite (DRC + simulation + consistency + short circuit)
make verify-all

# Export Gerbers with zone fill (all Docker)
make export-gerbers
```

### Render schematics and 3D model

```bash
# Build Docker images and render all assets
make render-all

# Or individually:
make render-schematics   # KiCad -> SVG
make render-enclosure    # OpenSCAD -> PNG
```

### Run documentation site locally

```bash
make website-dev
# or: cd website && npm start
```

## Project Structure

```
esp32-emu-turbo/
├── hardware/
│   ├── kicad/              # KiCad 10 schematics + PCB
│   │   ├── esp32-emu-turbo.kicad_sch   # Hierarchical root
│   │   ├── 01-power-supply.kicad_sch   # 7 sub-sheets
│   │   ├── ...
│   │   ├── esp32-emu-turbo.kicad_pcb   # PCB layout
│   │   └── jlcpcb/         # BOM + CPL for JLCPCB
│   └── enclosure/          # OpenSCAD parametric 3D model
├── release_jlcpcb/         # Production files for JLCPCB ordering
│   ├── gerbers/            # Gerber + drill files (22 layers)
│   ├── gerbers.zip         # Ready-to-upload ZIP
│   ├── bom.csv             # Bill of Materials (JLCPCB format)
│   ├── cpl.csv             # Component Placement List (65 parts)
│   └── bom-summary.md      # Human-readable BOM + cost estimate
├── retro-go/               # Retro-Go emulator (git submodule)
│   └── components/retro-go/targets/esp32-emu-turbo/  # Our target config
├── test-roms/              # Homebrew/public-domain test ROMs
│   ├── nes/ gb/ gbc/ sms/ gg/ pce/ gen/ snes/
│   └── README.md           # ROM sources and licenses
├── scripts/
│   ├── setup-sdcard.sh     # Format SD card + copy ROMs
│   ├── generate_schematics/ # Schematic generator (Python)
│   ├── generate_pcb/       # PCB layout generator (Python)
│   ├── render_pcba.sh      # Raytraced PCBA renders (only board imagery)
│   └── verify_schematic_pcb.py  # Consistency checker
├── docker/                 # Docker containers (KiCad + OpenSCAD)
├── website/                # Docusaurus documentation site
│   └── docs/               # All documentation pages
├── docker-compose.yml      # Hardware rendering containers
├── docker-compose.retro-go.yml  # Retro-Go build/flash containers
├── Makefile                # Top-level automation
└── CLAUDE.md               # AI assistant instructions
```

## Documentation

All project documentation lives in `website/docs/` and is published via Docusaurus to GitHub Pages:

- [Documentation Site](https://pjcau.github.io/esp32-emu-turbo/) — full docs online
- [Feasibility Analysis](website/docs/overview/feasibility.md)
- [SNES Hardware Spec](website/docs/overview/snes-hardware.md)
- [Bill of Materials](website/docs/design/components.md)
- [Electrical Schematics](website/docs/design/schematics.md)
- [PCB Design](website/docs/design/pcb.md)
- [Enclosure Design](website/docs/design/enclosure.md)
- [Manufacturing (JLCPCB)](website/docs/manufacturing/manufacturing.md)
- [First boot — staged session](website/docs/manufacturing/first-boot.md)
- [Software overview](website/docs/software/overview.md) · [Firmware](website/docs/software/firmware.md) · [SNES Optimization](website/docs/software/snes-optimization.md)

Engineering notes live in `docs/`:

- [**Known issues**](docs/known-issues.md) — what is still broken and what
  must not be "fixed". Re-derive the live state with `make open-issues`.
- [Waiver audit recovery](docs/archived/waiver-audit-recovery.md) — how the
  suppressions that could hide a dead board were retired.
- [Repository map](docs/REPO_MAP.md) — generated index of every script.

## 🤖 Claude Code Integration

This repository is also a **production-grade Claude Code skill suite** for KiCad + JLCPCB PCB design. All 43 skills used to design this PCB are available in `.claude/skills/`, and the 27 PCB-specific ones are packaged as the reusable `kicad-jlcpcb-skills` plugin.

### Install the plugin in your own project

```bash
# Inside Claude Code:
/plugin marketplace add pjcau/esp32-emu-turbo
/plugin install kicad-jlcpcb-skills
```

### What you get

- **27 PCB skills** — Design (5), Generate (7), Verify (11), Fix (4)
- **6 lifecycle slash commands** — `/design-pcb`, `/generate-pcb`, `/verify-pcb`, `/fix-pcb`, `/release-pcb`, `/bootstrap-new-pcb`
- **115 DFM tests + 9 DFA tests + 26 JLCPCB rules** (150 total manufacturing checks)
- **Pythonic KiCad generator** pipeline (no manual `.kicad_pcb` editing)
- **Deterministic, CI-friendly** workflow — full pipeline runs in ~5 seconds

### 5-phase design lifecycle

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Design  │ → │ Generate │ → │  Verify  │ → │   Fix    │ → │ Release  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
  5 skills       7 skills      11 skills      4 skills      shares Generate
```

### Documentation

- [`.claude/README.md`](.claude/README.md) — index of all 43 skills, 6 commands, 6 agents, 9 hooks
- [`docs/getting-started.md`](docs/getting-started.md) — install + first-run + first PCB walkthrough
- [`docs/lifecycle.md`](docs/lifecycle.md) — the 5-phase design lifecycle with exit criteria
- [`docs/skill-anatomy.md`](docs/skill-anatomy.md) — how to author your own skills on top of the base suite

### Credits

Plugin packaging (`.claude-plugin/`, lifecycle slash commands, flat `skills/` layout) is modeled on [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) — the first production-grade general-purpose Claude Code skill suite. If you want a non-hardware equivalent focused on SDLC workflows, go check it out. Our hardware-focused adaptation is fully complementary.
