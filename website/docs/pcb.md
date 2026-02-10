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
| **Mounting Holes** | 6× M2.5 (matches 3D enclosure) |

## Layer Stackup

| Layer | Function |
|-------|----------|
| **F.Cu** (Top) | Face buttons, menu button, charging LEDs |
| **In1.Cu** | Full GND copper pour |
| **In2.Cu** | +3V3 / +5V power plane |
| **B.Cu** (Bottom) | ESP32, ICs, connectors, passives, shoulder buttons |

## Component Placement

### Top Side (F.Cu) — User-facing
- **12× SMT tact switches** — D-pad (left), ABXY (right), Start/Select
- **SW13** Menu button — bottom right
- **LED1, LED2** — charging indicators (bottom left)
- Display module sits on top (connected via FPC on back)

### Bottom Side (B.Cu) — Electronics
- **U1 ESP32-S3-WROOM-1** — center
- **U2 IP5306** (eSOP-8) — charger + boost, right area
- **U3 AMS1117-3.3** (SOT-223) — 3.3V LDO, near IP5306
- **U5 PAM8403** (SOP-16) — audio amp, left area
- **L1** 1µH inductor — near IP5306
- **J1** USB-C — bottom center
- **U6** Micro SD slot — bottom right
- **J4** FPC 16-pin — top center (display ribbon)
- **J3** JST PH 2-pin — battery connector, center
- **SW11, SW12** — L/R shoulder buttons
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
| J4 | FPC 16-pin 0.5mm | C2856801 | Extended | 1 |
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

### Manual Assembly (off-board)

| Component | Connection |
|-----------|------------|
| LiPo 3.7V 5000mAh battery | JST PH connector (J3) |
| ST7796S 4.0" display module | FPC ribbon cable (J4) |
| 28mm 8Ω speaker | Solder pads on PCB |
| PSP joystick (optional) | Pin header on PCB |

## JLCPCB Ordering

### Files Needed
1. **Gerber ZIP** — exported from KiCad (`kicad-cli pcb export gerbers`)
2. **BOM.csv** — `hardware/kicad/jlcpcb/bom.csv`
3. **CPL.csv** — `hardware/kicad/jlcpcb/cpl.csv`

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
| 3 | `03-display.kicad_sch` | ST7796S module + FPC connector (J4) |
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

## Next Steps

After generating the PCB:
1. Open `esp32-emu-turbo.kicad_pcb` in KiCad 9
2. Route traces (8080 display bus, SPI, I2S, USB differential pair, button GPIOs)
3. Run DRC with JLCPCB 4-layer design rules
4. Export Gerbers: `kicad-cli pcb export gerbers`
5. Upload Gerber + BOM + CPL to [jlcpcb.com](https://jlcpcb.com/)
