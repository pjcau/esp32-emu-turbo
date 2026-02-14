# ESP32 Emu Turbo - JLCPCB Production Files

## Board Specification

| Parameter       | Value                          |
| --------------- | ------------------------------ |
| Board size      | 160 x 75 mm                    |
| Layers          | 4 (F.Cu, In1.Cu, In2.Cu, B.Cu) |
| Thickness       | 1.6 mm                         |
| Min trace width | 0.2 mm                         |
| Min drill       | 0.3 mm                         |
| Surface finish  | HASL or ENIG                   |
| Copper weight   | 1 oz                           |

## Files Included

### Gerber Files (`gerbers/`)

Upload the entire `gerbers/` folder as a ZIP to JLCPCB.

| File    | Layer                          |
| ------- | ------------------------------ |
| `*.gtl` | Front Copper (F.Cu)            |
| `*.g1`  | Inner Layer 1 (In1.Cu - GND)   |
| `*.g2`  | Inner Layer 2 (In2.Cu - Power) |
| `*.gbl` | Back Copper (B.Cu)             |
| `*.gto` | Front Silkscreen               |
| `*.gbo` | Back Silkscreen                |
| `*.gts` | Front Solder Mask              |
| `*.gbs` | Back Solder Mask               |
| `*.gtp` | Front Paste                    |
| `*.gbp` | Back Paste                     |
| `*.gm1` | Board Outline (Edge.Cuts)      |
| `*.drl` | Drill File                     |

### Assembly Files (root folder)

| File                        | Description                              |
| --------------------------- | ---------------------------------------- |
| `bom.csv`                   | Bill of Materials (JLCPCB format)        |
| `cpl.csv`                   | Component Placement List (65 components) |
| `bom-summary.md`            | Human-readable BOM with cost estimate    |
| `esp32-emu-turbo.kicad_pcb` | KiCad source (for reference)             |

## JLCPCB Order Instructions

1. Go to [jlcpcb.com](https://jlcpcb.com) > Order Now
2. Upload `gerbers/` folder as ZIP
3. Set board parameters (4 layers, 160x75mm, 1.6mm)
4. Enable "SMT Assembly" (both sides)
5. Upload `bom.csv` as BOM file
6. Upload `cpl.csv` as CPL file
7. Review placement and confirm order

## Component Layout

- **Top (F.Cu):** D-pad, ABXY, Start/Select, Menu buttons + 2 LEDs
- **Bottom (B.Cu):** ESP32-S3, ICs, connectors, passives, L/R shoulder buttons

## Release History

### v1.3 — 2026-02-14 (current)

- **Trace shorts fixed:** SD_MOSI and SD_MISO rerouted with B.Cu vertical bypass columns (x=120, x=118) to avoid FPC approach zone conflicts with LCD_D4, LCD_D6, and BTN_Y on F.Cu
- **Zone fill verified:** Inner layers (In1.Cu GND, In2.Cu +3V3/+5V) correctly filled via kicad-cli — Gerber files confirmed >200KB each
- **All pre-production checks pass:** 0 trace shorts, 0 zone priority conflicts, zone fill data present, Gerber file sizes validated
- Updated BOM, CPL, and PCB source file

### v1.2 — 2026-02-12

- SPI trace routing fix (reduced shorts from 77 to 9)
- FPC slot clearance improvements
- Drill spacing optimizations

### v1.1 — Initial release

- First JLCPCB-ready production files
- 4-layer stackup with power planes

## Pre-Production Verification Status

| Check                     | Result                                |
| ------------------------- | ------------------------------------- |
| Trace Shorts              | ✅ PASS (0 shorts)                     |
| Zone Fill Data            | ✅ PASS (7 filled polygons)            |
| Zone Priorities           | ✅ PASS                                |
| Gerber File Sizes         | ✅ PASS (In1_Cu=243KB, In2_Cu=260KB)   |
| Electrical Simulation     | ✅ PASS (0 errors, 5 warnings)         |
| Schematic/PCB Consistency | ✅ PASS (65 JLCPCB components matched) |

## Notes

- J4 (FPC-40P 0.5mm) LCSC part number: C2856812
- Battery (BT1), display panel, speaker, and joystick are manual assembly
- Power switch (SW_PWR) is through-hole, verify orientation
- Inner layer Gerber files contain full copper pour data (zone fill applied via Docker kicad-cli pipeline)
