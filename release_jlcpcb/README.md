# ESP32 Emu Turbo - JLCPCB Production Files

## Board Specification

| Parameter | Value |
|-----------|-------|
| Board size | 160 x 75 mm |
| Layers | 4 (F.Cu, In1.Cu, In2.Cu, B.Cu) |
| Thickness | 1.6 mm |
| Min trace width | 0.2 mm |
| Min drill | 0.3 mm |
| Surface finish | HASL or ENIG |
| Copper weight | 1 oz |

## Files Included

### Gerber Files (`gerbers/`)

Upload the entire `gerbers/` folder as a ZIP to JLCPCB.

| File | Layer |
|------|-------|
| `*.gtl` | Front Copper (F.Cu) |
| `*.g1` | Inner Layer 1 (In1.Cu - GND) |
| `*.g2` | Inner Layer 2 (In2.Cu - Power) |
| `*.gbl` | Back Copper (B.Cu) |
| `*.gto` | Front Silkscreen |
| `*.gbo` | Back Silkscreen |
| `*.gts` | Front Solder Mask |
| `*.gbs` | Back Solder Mask |
| `*.gtp` | Front Paste |
| `*.gbp` | Back Paste |
| `*.gm1` | Board Outline (Edge.Cuts) |
| `*.drl` | Drill File |

### Assembly Files (root folder)

| File | Description |
|------|-------------|
| `bom.csv` | Bill of Materials (JLCPCB format) |
| `cpl.csv` | Component Placement List (65 components) |
| `bom-summary.md` | Human-readable BOM with cost estimate |
| `esp32-emu-turbo.kicad_pcb` | KiCad source (for reference) |

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

## Notes

- J4 (FPC-40P 0.5mm) LCSC part number TBD - select matching connector on JLCPCB
- Battery (BT1), display panel, speaker, and joystick are manual assembly
- Power switch (SW_PWR) is through-hole, verify orientation
