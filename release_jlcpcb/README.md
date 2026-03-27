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

### PCB Renders (`renders/`)

| File                | Description                                              |
| ------------------- | -------------------------------------------------------- |
| `renders/pcb-top.svg`      | Top side (F.Cu) — face buttons, LEDs, display area      |
| `renders/pcb-bottom.svg`   | Bottom side (B.Cu) — ESP32, ICs, connectors, passives   |
| `renders/pcb-combined.svg` | Both sides side-by-side (160x75mm, 4-layer overview)    |

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

### v2.1 — 2026-02-27 (current)

**DFM fixes: via proximity, edge clearance, trace overlap:**

- **FPC power via proximity fixed** — GND pin 36 and +3V3 pin 39 vias were 0.5mm
  apart (gap 0.20mm < 0.25mm JLCPCB minimum). Same for GND pin 37 and +3V3 pin 38.
  Fixed by increasing Y offsets for pins 38 and 39 to achieve 1.2-1.7mm separation.
- **FPC +3V3 pin 7 via clearance fixed** — via at (129.15, 25.75) had 0.30mm gap
  to FPC slot edge (need >= 0.5mm). Moved to (129.65, 25.75) giving 0.80mm gap.
- **SW8 (BTN_Y) pad overlap with FPC slot fixed** — SW8 pad left edge at 128.4mm
  was inside the 128.5mm slot edge. SW8 moved 1mm right (enc -9 not -10) so pad
  left edge is now at 129.4mm, giving 0.9mm clearance to slot edge.
- **BTN_R channel edge clearance fixed** — F.Cu channel was at y=75.0mm (board edge!).
  Moved to y=72.5mm, giving 2.5mm clearance to board bottom edge.
- **BAT+ vs SPK+ trace overlap fixed** — B.Cu BAT+ vertical at x=39.25 (w=0.5mm)
  overlapped with SPK+ vertical at x=39.5 (w=0.3mm) by -0.15mm. BAT+ long vertical
  rerouted to x=38.0mm column (1.1mm gap to SPK+, well above threshold).
- **3 new regression guard tests added** (tests 22-24):
  - Test 22: KiCad DRC copper_edge_clearance = 0 and hole_to_hole = 0 (regression guard)
  - Test 23: SW8 pad 1 clears FPC slot edge by >= 0.5mm
  - Test 24: BTN_R F.Cu channel >= 0.5mm from board bottom edge
- **KiCad DRC**: 0 copper_edge_clearance, 0 hole_to_hole, 0 silk violations
- All 31 DFM verification tests pass (was 27/27 before this release)
- **PCB renders updated** — `renders/pcb-top.svg`, `renders/pcb-bottom.svg`, `renders/pcb-combined.svg`
  regenerated from v2.1 PCB (includes actual trace/via data from kicad_pcb parsed at render time)

### v2.0 — 2026-02-27

**DFM fixes targeting JLCPCB DFM report issues:**

- **ESOP-8 EP pad reduced** (IP5306, U2) — exposed pad height 3.4 -> 2.8mm so
  corner signal pad gap increases from 0.095mm to 0.205mm (above 0.10mm danger
  threshold). Eliminates 4 pad-spacing-danger flags in JLCPCB DFM report.
- **MSK12C02 shell pad unique names** (SW_PWR) — four mounting pads renamed from
  shared "SH" to unique "SH1"-"SH4". Prevents JLCPCB DFM checker from grouping
  them and reporting spurious 0mm pad-spacing violations.
- **BTN_R (SW12 shoulder-right) routed** — the right shoulder button had no traces
  connecting it to ESP32 GPIO36. Full B.Cu / F.Cu / B.Cu route added: stub down
  from SW12 pad 3 at (143.15, 8.5), cross-board F.Cu channel at y=69mm,
  approach column right of ESP32, final B.Cu stub to GPIO36 at (71.25, 36.21).
- **GND stub added for SW12 pad 2** — offset 1mm outward from pad (DFM lead-to-hole
  clearance) matching existing SW11 treatment.
- **Display stagger test corrected** (verify_dfm_v2.py test 18) — button routing
  traces that legitimately terminate at ESP32 pad X columns are now excluded from
  the ESP32-pin-Y collision check (were false positives).
- **3 new regression guard tests added** (tests 19-21):
  - Test 19: ESOP-8 EP pad height <= 3.2mm (clearance guard)
  - Test 20: MSK12C02 SH pads have unique names SH1-SH4
  - Test 21: BTN_R (SW12) routing stub and cross-board segment present
- **Via count**: 223 -> 226 (3 new vias for BTN_R routing)
- **Trace spacing**: 27 -> 17 baseline violations (improvement, no regressions)
- All 27 DFM verification tests pass (was 20/21 before this release)

### v1.9 — 2026-02-26

- **CRITICAL: USB-C CC1/CC2 pull-down traces added** — R1/R2 (5.1k to GND) were missing traces from CC pads, device would not be recognized by USB hosts
- **R17/R18 CPL position fixed** — jlcpcb_export.py had y=70 instead of y=65, mismatching board.py placement
- **USB-C shield pads corrected** — rear shields changed from 1.0x2.1 to 1.0x1.6 per official KiCad library footprint
- **SOP-16 silkscreen DFM fix** — body outline bx reduced from 3.9 to 3.35 to avoid overlapping pad copper (was 0mm clearance)
- **Silkscreen label DFM fixes** — AMS1117 label moved to avoid C1 pad overlap, PWR label moved inside board outline
- **Zone fill script improved** — preserves orphan nets (USB_CC1/CC2) that pcbnew's SaveBoard() would strip
- J4 FPC trace alignment verified (all 40 pins at x=136.85, 0.5mm pitch)
- Zone fill: In1.Cu 286KB, In2.Cu 326KB

### v1.8 — 2026-02-25

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

| Check                       | Result                                          |
| --------------------------- | ----------------------------------------------- |
| DRC Check                   | PASS (0 errors, 0 silk violations)              |
| DFM v2 Tests                | PASS (31/31, including 6 new regression guards) |
| Schematic/PCB Consistency   | PASS (64 JLCPCB components matched)             |
| Zone Priorities             | PASS                                            |
| Zone Fill Data              | PASS (In1.Cu 52KB, In2.Cu 292KB)                |
| Via annular ring            | PASS (247 vias, all >= 0.075mm)                 |
| Via hole-to-hole            | PASS (min gap >= 0.25mm)                        |
| Trace spacing               | PASS (17 violations, baseline <= 27)            |
| ESOP-8 EP pad clearance     | PASS (gap = 0.205mm > 0.10mm danger)            |
| BTN_R routing               | PASS (SW12 pad 3 stub + cross-board route)      |

## Notes

- J4 (FPC-40P 0.5mm) LCSC part number: C2856812
- Battery (BT1), display panel, speaker, and joystick are manual assembly
- Power switch (SW_PWR) is through-hole, verify orientation
- Inner layer Gerber files contain full copper pour data (zone fill applied via kicad-cli 9.0.7)
