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
| `cpl.csv`                   | Component Placement List (64 components) |
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

### v1.8 — 2026-02-25 (current)

- **R17/R18 LED resistors relocated** near LEDs on B.Cu for shorter traces
- **Shoulder buttons adjusted** (y=35 to y=32) for better PCB edge clearance
- **IP5306 routing corrected** per datasheet: pin 5=KEY, 6=BAT, 7=SW/LX, 8=VOUT
- **Footprint silkscreen improvements**: SOP-16 body outline + pin 1 marker
- **DFM improvements**: solder mask margin, per-footprint text offset for pad clearance
- Zone fill applied via kicad-cli 9.0.7 (inner layers >290KB each)
- CPL updated to match all board layout changes
- DRC: 0 errors, 6 warnings

### v1.7 — 2026-02-25

- **CRITICAL: FPC 40-pin pinout corrected** from ILI9488 panel datasheet
  - Previous pinout was a generic/typical mapping that did NOT match the actual panel
  - Old mapping would have connected GPIOs to power pins (6=VDDI, 7=VDDA) and +3V3 to backlight cathodes (34-36=LED-K)
  - Corrected pin assignments: 9=CS, 10=DC, 11=WR, 12=RD, 15=RESET, 17-24=DB0-DB7, 33=LED-A
  - Added power connections: 5/16/37=GND, 6=VDDI(+3V3), 7=VDDA(+3V3), 34-36=LED-K(GND)
  - Added interface mode pins: 38=IM0(+3V3), 39=IM1(+3V3), 40=IM2(GND) for 8080 8-bit parallel
- All DRC checks pass (0 errors), drill spacing verified
- Updated schematics, documentation, BOM, CPL

### v1.3 — 2026-02-14

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
| DRC Check                 | ✅ PASS (0 errors, 6 warnings)         |
| Schematic/PCB Consistency | ✅ PASS (64 JLCPCB components matched) |
| Zone Priorities           | ✅ PASS                                |
| Zone Fill Data            | ✅ PASS (In1.Cu 292KB, In2.Cu 332KB)   |
| Trace Shorts              | ⚠️ 52 pre-existing crossings (needs routing rework) |

## Notes

- J4 (FPC-40P 0.5mm) LCSC part number: C2856812
- Battery (BT1), display panel, speaker, and joystick are manual assembly
- Power switch (SW_PWR) is through-hole, verify orientation
- Inner layer Gerber files contain full copper pour data (zone fill applied via kicad-cli 9.0.7)
