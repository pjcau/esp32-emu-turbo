---
id: pcb
title: PCB Design (JLCPCB)
sidebar_position: 6
---

# PCB Design — JLCPCB PCBA

Custom 4-layer PCB designed for fabrication and assembly by [JLCPCB](https://jlcpcb.com/). Maximum components assembled on-board to minimize manual soldering.

## PCB Renders

### Top & Bottom Views

![PCB Animation](/img/pcb/pcb-animation.gif)

| Top View (F.Cu) | Bottom View (B.Cu) |
|:---:|:---:|
| ![PCB Top](/img/pcb/pcb-top.png) | ![PCB Bottom](/img/pcb/pcb-bottom.png) |

### Interactive 3D Viewer

<a href="/pcb-viewer.html" target="_blank">Open interactive 3D PCB viewer</a> — rotate, zoom, explode view, top/bottom toggle.

## Board Specifications

| Parameter | Value |
|-----------|-------|
| **Dimensions** | 160 × 75 mm |
| **Layers** | 4 (F.Cu, In1.Cu GND, In2.Cu Power, B.Cu) |
| **Thickness** | 1.6 mm |
| **Surface Finish** | ENIG (gold) |
| **Corner Radius** | 6 mm |
| **FPC Slot** | 3 × 24 mm vertical cutout (40-pin ribbon pass-through) |
| **Mounting Holes** | 6× M2.5 (matches 3D enclosure) |

## Layer Stackup

| Layer | Function |
|-------|----------|
| **F.Cu** (Top) | Face buttons, menu button, charging LEDs |
| **In1.Cu** | Full GND copper pour |
| **In2.Cu** | +3V3 / +5V power plane |
| **B.Cu** (Bottom) | ESP32, ICs, connectors, passives, L/R shoulder buttons |

## Component Placement

### Top Side (F.Cu) — User-facing
- **11× SMT tact switches** — D-pad (left), ABXY (right), Start/Select
- **SW13** Menu button — bottom right
- **LED1, LED2** — charging indicators (bottom left)
- ILI9488 3.95" bare LCD panel sits on top (FPC ribbon passes through slot to J4 on back)

### FPC Slot
- **3 × 24 mm** vertical cutout between display area and ABXY buttons
- Allows the 40-pin FPC ribbon cable to pass from top (display) to bottom (J4 connector)
- Located at x=127mm from left edge, vertically centered with display

### Bottom Side (B.Cu) — Electronics
- **SW11, SW12** — L/R shoulder buttons (top edge, rotated 90°)
- **U1 ESP32-S3-WROOM-1** — center
- **U2 IP5306** (eSOP-8) — charger + boost, left-center area
- **U3 AMS1117-3.3** (SOT-223) — 3.3V LDO, below center
- **U5 PAM8403** (SOP-16) — audio amp, left area
- **L1** 1µH inductor — near IP5306
- **J1** USB-C — bottom center
- **U6** Micro SD slot — bottom right
- **J4** FPC 40-pin 0.5mm — right of FPC slot (display ribbon, ILI9488)
- **J3** JST PH 2-pin — battery connector, center
- **SW_PWR** — power slide switch, left edge
- **SPK1** — 22mm speaker, left area
- **26× passives** — organized in 2 centered rows below ESP32

## Bill of Materials (BOM)

### JLCPCB-Assembled Components

| Ref | Component | LCSC | Type | Qty |
|-----|-----------|------|------|-----|
| U1 | ESP32-S3-WROOM-1-N16R8 | C2913202 | Extended | 1 |
| U2 | IP5306 charger+boost | C181692 | Extended | 1 |
| U3 | AMS1117-3.3 LDO | C6186 | Basic | 1 |
| U5 | PAM8403 audio amp | C5122557 | Extended | 1 |
| J1 | USB-C 16-pin | C2765186 | Extended | 1 |
| U6 | Micro SD slot (TF-01A) | C91145 | Extended | 1 |
| J4 | FPC 40-pin 0.5mm (display) | TBD | Extended | 1 |
| J3 | JST PH 2-pin (battery) | C173752 | Extended | 1 |
| L1 | 1µH inductor 4.5A | C280579 | Extended | 1 |
| LED1 | Red LED 0805 (charging) | C84256 | Basic | 1 |
| LED2 | Green LED 0805 (full) | C72043 | Basic | 1 |
| R1-R2 | 5.1k 0805 | C27834 | Basic | 2 |
| R3-R15,R19 | 10k 0805 | C17414 | Basic | 14 |
| R16 | 100k 0805 | C149504 | Basic | 1 |
| R17-R18 | 1k 0805 (LED) | C17513 | Basic | 2 |
| C3-C16,C20 | 100nF 0805 | C49678 | Basic | 15 |
| C1,C17,C18 | 10µF 0805 | C15850 | Basic | 3 |
| C2,C19 | 22µF 1206 | C29632 | Basic | 2 |
| SW1-SW13 | SMT tact switch | C318884 | Extended | 13 |
| SW_PWR | Slide switch SS-12D00G3 | C431540 | Extended | 1 |
| SPK1 | 22mm speaker pads | — | Manual | 1 |

### Manual Assembly — Buy Separately

These components are **NOT provided by JLCPCB** and must be purchased from AliExpress (see [BOM](components.md)):

| Component | Buy | Connection | Soldering |
|-----------|-----|------------|-----------|
| **LiPo 3.7V 5000mAh** (105080) | ~$6-8 | Plug into JST PH connector (J3) | No — plug-in connector |
| **ILI9488 3.95" bare LCD panel** (40P FPC, touch NC) | ~$3.95 | Insert 40-pin FPC ribbon into J4 connector, close latch | No — plug-in FPC |
| **28mm 8Ω speaker** | ~$0.80 | Solder 2 wires to pads on PCB | Yes — 2 solder points |
| **PSP joystick** (optional) | ~$2 | Solder to pin header on PCB | Yes — 4 solder points |

:::tip Display purchase
Buy the **bare LCD panel** (NOT a module with PCB breakout):
- **ILI9488** 3.95" 320×480, **40-pin FPC 0.5mm pitch**
- Resistive touch (not connected on PCB)
- [AliExpress](https://it.aliexpress.com/item/1005009422879126.html)
- The FPC ribbon slides into J4 and locks — **zero soldering**.
:::

## JLCPCB Ordering

### Files Needed

All production files are pre-packaged in the **`release_jlcpcb/`** folder at the project root:

1. **Gerber ZIP** — `release_jlcpcb/gerbers.zip` (ready to upload)
2. **BOM.csv** — `release_jlcpcb/bom.csv`
3. **CPL.csv** — `release_jlcpcb/cpl.csv`

### Order Settings
- Layers: **4**
- PCB Qty: **5**
- Thickness: **1.6mm**
- Surface Finish: **ENIG**
- Assembly: **Both sides**
- Tooling holes: **Added by JLCPCB**

### Estimated Cost (5 boards)

| Item | Cost |
|------|------|
| PCB fabrication (4-layer) | ~$20 |
| SMT setup + extended fees | ~$35 |
| Components | ~$35 |
| **Total** | **~$90** (~$18/board) |

## Schematic Architecture

The design uses a **hierarchical schematic** with a root file referencing 7 sub-sheets:

| Sheet | File | Components |
|-------|------|-----------|
| Root | `esp32-emu-turbo.kicad_sch` | 7 sheet references |
| 1 | `01-power-supply.kicad_sch` | USB-C, IP5306, AMS1117, battery, LEDs, power switch |
| 2 | `02-mcu.kicad_sch` | ESP32-S3 + decoupling |
| 3 | `03-display.kicad_sch` | ILI9488 bare panel + FPC 40-pin connector (J4) |
| 4 | `04-audio.kicad_sch` | PAM8403 + speaker (SPK1) |
| 5 | `05-sd-card.kicad_sch` | Micro SD SPI interface |
| 6 | `06-controls.kicad_sch` | 13 buttons + pull-ups + debounce caps |
| 7 | `07-joystick.kicad_sch` | PSP joystick (optional) |

Total: **68 unique component references** across all sheets, **65 assembled by JLCPCB**.

## Generation

```bash
# Generate schematics (7 sheets + root)
python3 -m scripts.generate_schematics hardware/kicad

# Generate PCB + JLCPCB exports
make generate-pcb

# Render PCB images
make render-pcb

# Verify schematic/PCB/JLCPCB consistency
python3 scripts/verify_schematic_pcb.py
```

Output files:
- `hardware/kicad/esp32-emu-turbo.kicad_sch` — Hierarchical root schematic
- `hardware/kicad/01-07-*.kicad_sch` — 7 sub-sheet schematics
- `hardware/kicad/esp32-emu-turbo.kicad_pcb` — KiCad PCB layout
- `hardware/kicad/jlcpcb/cpl.csv` — Component Placement List (65 parts)

## Pre-Production Verification

All automated checks passed before JLCPCB production order:

### DRC (Design Rule Check) — PASS

| Rule | JLCPCB Min | Our Design | Status |
|------|-----------|------------|--------|
| Trace width | 0.09mm | 0.2mm (signal), 0.5mm (power) | PASS |
| Trace spacing | 0.09mm | 0.2mm | PASS |
| Via drill | 0.15mm | 0.3mm | PASS |
| Via pad | 0.45mm | 0.6mm | PASS |
| Annular ring | 0.13mm | 0.15mm | PASS |
| Board edge clearance | 0.3mm | 0.5mm | PASS |
| Drill spacing | 0.5mm | all OK | PASS |

Script: `python3 scripts/drc_check.py`

### Electrical Simulation — PASS (6 warnings)

**Power Budget:**
- +3V3 rail: 335mA max / 800mA capacity (42% utilization)
- +5V rail: 387mA max / 2.4A capacity (16% utilization)
- AMS1117 thermal: 0.57W dissipation, Tj=91°C (safe)
- Battery life: **11.8h typical**, 8.6h heavy use (5000mAh LiPo)

**Signal Timing:**
- Display 8080 bus: 18.4 MB/s required, 20 MB/s available (8% margin)
- SPI SD card: 6MB ROM loads in 1.3s
- I2S audio: 32kHz SNES rate, BCLK 1.024MHz (ESP32 max 8MHz)
- Button debounce: RC = 1.0ms (acceptable range 1-10ms)

**Component Values:**
- USB-C CC pull-down: R1,R2 = 5.1kΩ (USB-C spec: 4.7k-5.6k) ✓
- LED current: 1.1-1.3mA (safe, visible) ✓
- Pull-up logic: 3.3V > Vih 2.475V ✓
- Decoupling caps present near all ICs ✓

**GPIO Mapping:**
- 35/45 GPIOs used, no conflicts with PSRAM (GPIO 26-32)
- Strapping pins documented (GPIO0, GPIO3, GPIO45, GPIO46)
- Joystick optional: GPIO44 (JOY_Y) needs reassignment for ADC

Script: `python3 scripts/simulate_circuit.py`

### Schematic/PCB Consistency — PASS

- All **65 JLCPCB components** matched between schematic, PCB, and CPL
- 3 off-board components excluded: battery (BT1), display module (U4), joystick (J2)
- PCB: 211 trace segments, 15 vias, 45 nets, 26 footprints

Script: `python3 scripts/verify_schematic_pcb.py`

### Run All Verifications

```bash
python3 scripts/drc_check.py              # DRC manufacturing rules
python3 scripts/simulate_circuit.py       # Electrical verification
python3 scripts/verify_schematic_pcb.py   # Schematic/PCB consistency
# or: make verify-all
```

## Next Steps

1. Upload `release_jlcpcb/gerbers.zip` to [jlcpcb.com](https://jlcpcb.com/)
2. Upload `release_jlcpcb/bom.csv` and `release_jlcpcb/cpl.csv` for SMT assembly
3. Order 5× PCBs with SMT assembly (65 components)
4. Buy off-board components: bare LCD panel (40P FPC), LiPo battery, speaker (see table above)
5. Manual assembly: plug battery into J3, insert 40-pin FPC into J4, solder speaker wires
