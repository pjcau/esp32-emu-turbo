# ESP32 Emu Turbo

Handheld retro gaming console based on ESP32-S3 — **SNES** (primary) and **NES** (secondary) emulation.

## Project Goal

Build a portable battery-powered device based on ESP32-S3, capable of loading and playing retro games via SD card, with USB-C charging and an ILI9488 3.95" color LCD display.

## Development Phases

### Phase 1 — Feasibility Analysis ✅
- Evaluate ESP32-S3 capabilities for SNES/NES emulation
- Select components (display, controller, power supply)

### Phase 2 — Hardware Design ✅
- KiCad electrical schematics (7 hierarchical sheets, 68 components)
- OpenSCAD 3D enclosure model
- GPIO pin mapping and validation
- Docker rendering pipeline
- 4-layer PCB layout (160x75mm, JLCPCB-ready)

### Phase 3 — PCB Fabrication (In Progress)
- Production files ready in `release_jlcpcb/` v1.3 (Gerber ZIP + BOM + CPL)
- All pre-production checks pass: 0 trace shorts, zone fill verified, DRC clean
- JLCPCB order and assembly
- Testing and performance optimization

### Phase 4 — Software

#### 4.1 — Hardware Validation (ESP-IDF) ✅
Standalone firmware in `software/` to test all hardware before emulator integration.
- 1.1 ESP-IDF v5.x project setup (N16R8, 240MHz, 16MB flash, 8MB PSRAM) ✅
- 1.2 ST7796S display driver (i80 8-bit parallel, 20MHz) ✅
- 1.3 Display test pattern (color bars) ✅
- 1.4 SD card via SPI (FAT32, ROM directory scan) ✅
- 1.5 12-button GPIO input (1ms polling, HW debounce) ✅
- 1.6 I2S audio output (440Hz test tone) ✅
- 1.7 IP5306 power management (battery %, charge status) ✅

#### 4.2 — Retro-Go Integration (In Progress)
Fork and adapt [Retro-Go](https://github.com/ducalex/retro-go) for our hardware (`retro-go/` git submodule).
- 2.1 Add retro-go as git submodule ✅
- 2.2 Create target `targets/esp32-emu-turbo/` (config.h, env.py, sdkconfig) ✅
- 2.3 Docker build pipeline (`docker-compose.retro-go.yml`) ✅
- 2.4 Custom display driver `st7796s_i80.h` (i80 parallel, async DMA, 5-buffer pool) ✅
- 2.5 Frame scaling (320x480 portrait, integer scale + letterbox) ✅
- 2.6 Input mapping (12 GPIO direct buttons) ✅
- 2.7 Audio routing (I2S ext DAC → PAM8403) ✅
- 2.8 First boot: NES test (nofrendo @ 60fps) ⏳ Needs hardware

#### 4.3 — Emulator Testing (Needs Hardware)
Enable and validate each emulator core at target frame rate.
- 3.1 NES (nofrendo) → 60 fps
- 3.2 Game Boy (gnuboy) → 60 fps
- 3.3 Game Boy Color (gnuboy) → 60 fps
- 3.4 Master System (smsplus) → 60 fps
- 3.5 Game Gear (smsplus) → 60 fps
- 3.6 PC Engine (pce-go) → 60 fps
- 3.7 Atari Lynx (handy) → 60 fps
- 3.8 Genesis (gwenesis) → 50-60 fps
- 3.9 Game & Watch (gw-emulator) → 60 fps

#### 4.4 — SNES Optimization (Needs Hardware)
Progressive optimization of the snes9x core for ESP32-S3.
- 4.1 Baseline snes9x2010 → 15-20 fps
- 4.2 Critical buffers → IRAM → 25-30 fps
- 4.3 Audio DSP on Core 1 → 30-35 fps
- 4.4 Adaptive frameskip → 35-45 fps perceived
- 4.5 Interlaced rendering → 40-50 fps perceived

### Phase 5 — Final Version (v2)
- Revised PCB if needed
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
| **Components**     | 64 assembled by JLCPCB               |
| **Trace Shorts**   | 0 (verified)                         |
| **Zone Fill**      | ✅ Inner layers filled (GND + 3V3/5V) |
| **Release**        | v1.3 (2026-02-14)                    |
| **Estimated Cost** | ~$40/board (5 pcs, fully assembled)  |

## Key Requirements

| Component     | Specification                                                    |
| ------------- | ---------------------------------------------------------------- |
| **MCU**       | ESP32-S3 N16R8 (16MB flash, 8MB Octal PSRAM)                     |
| **Display**   | ILI9488 3.95" 320x480, 8-bit 8080 parallel, bare panel + 40P FPC |
| **Power**     | LiPo 3.7V 5000mAh + IP5306 (SOP-8) + AMS1117                     |
| **Charging**  | USB-C (charge-and-play)                                          |
| **Audio**     | I2S -> PAM8403 -> 28mm speaker                                   |
| **Controls**  | 13 buttons (D-pad, ABXY, Start, Select, L, R, Menu)              |
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
│   ├── render_pcb_svg.py   # PCB SVG renderer
│   ├── render_pcb_animation.py  # PCB PNG/GIF renderer
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
- [Feasibility Analysis](website/docs/feasibility.md)
- [SNES Hardware Spec](website/docs/snes-hardware.md)
- [Bill of Materials](website/docs/components.md)
- [Electrical Schematics](website/docs/schematics.md)
- [Prototyping Guide](website/docs/prototyping.md)
- [Enclosure Design](website/docs/enclosure.md)
- [PCB Design](website/docs/pcb.md)

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
