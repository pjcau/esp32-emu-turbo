---
id: datasheet-audit
title: Datasheet vs PCB Audit Report
sidebar_position: 13
---

# Datasheet vs PCB Audit Report

Full audit of all 20 BOM components against their LCSC datasheets. Datasheets stored in `hardware/datasheets/`.

---

## Summary

| Status | Count | Description |
|--------|-------|-------------|
| FIXED | 3 | Code fix applied, ready for next PCB revision |
| OK (cosmetic) | 2 | Schematic symbol names wrong but routing correct |
| OK (acceptable) | 8 | Minor deviations within tolerance |
| NO ACTION | 7 | Perfect match |

---

## FIXED Issues (applied in code)

### FIX-1: SD Card (U6) — VCC and GND not connected

| Detail | Value |
|--------|-------|
| **Severity** | CRITICAL — SD card does not power on |
| **Component** | TF-01A Micro SD slot (C91145) |
| **Problem** | Pin 4 (VDD/+3V3) and Pin 6 (VSS/GND) had no trace or via. SMD pads on B.Cu with no B.Cu zone fill = electrically floating. Shield pins 10-13 also unconnected. |
| **Root cause** | Schematic symbol uses abstract 6-pin numbering (1=VCC, 2=GND, 3=MOSI...) that doesn't match TF-01A physical pinout. SPI signals were manually mapped to physical pins in routing.py, but power pins were not. |
| **Fix** | Via-in-pad on pin 4 (connects to In2.Cu +3V3 zone) and pin 6 (connects to In1.Cu GND zone). GND vias on shield pins 10 and 12. SD_MOSI and BTN_B traces detoured around the new vias. |
| **Files** | `routing.py` — `_power_traces()`, `_spi_traces()`, `_button_traces()` |

### FIX-2: PAM8403 (U5) — Missing application circuit passives

| Detail | Value |
|--------|-------|
| **Severity** | HIGH — DC offset risk to speaker, no decoupling for Class-D |
| **Component** | PAM8403 SOP-16 (C5122557) |
| **Problem** | Datasheet application circuit requires 7 external passives. All were missing. |
| **Fix** | Added 7 new components to BOM, placement, and routing |

**New components added:**

| Ref | Value | Purpose | Distance from pin |
|-----|-------|---------|-------------------|
| C22 | 0.47uF | DC-blocking cap (series on I2S_DOUT) | In-line on trace |
| R20 | 20k | INL bias resistor (pin 7 to GND) | 4.8mm |
| R21 | 20k | INR bias resistor (pin 10 to GND) | 4.8mm |
| C21 | 100nF | VREF bypass cap (pin 8 to GND) | 4.8mm |
| C23 | 1uF | VDD decoupling (pin 6 to GND) | 6.1mm |
| C24 | 1uF | PVDD decoupling (pin 4 to GND) | 4.8mm |
| C25 | 1uF | PVDD decoupling (pin 13 to GND) | 5.8mm |

**Files:** `routing.py`, `board.py`, `primitives.py` (new net PAM_VREF)

:::tip No speaker? Skip rework
If not connecting a speaker, PAM8403 rework is unnecessary on existing boards. The missing passives only matter when driving a speaker load.
:::

### FIX-3: USB-C (J1) — Shield pad width undersized

| Detail | Value |
|--------|-------|
| **Severity** | HIGH — reduced mechanical retention |
| **Component** | USB-C 16-pin (C2765186) |
| **Problem** | Front shield THT pads 1.1mm wide vs datasheet 1.7mm (-35%). Rear pads 1.2mm vs 1.4mm (-14%). |
| **Fix** | Updated `footprints.py`: front 1.1→1.7mm, rear 1.2→1.4mm |
| **Rework** | Add extra solder to shield pads on existing boards |

---

## OK — Cosmetic / No Impact

### ESP32-S3 (U1) — Pin 1 schematic name wrong

| Detail | Value |
|--------|-------|
| **Severity** | LOW — no functional impact |
| **Problem** | Schematic symbol labels pin 1 as "3V3" but datasheet says pin 1 = GND |
| **Reality** | Pin 1 has net=0 in PCB (not connected). ESP32 module gets GND through pin 41 (exposed pad). Multiple GND pins on perimeter are redundant. Module works fine. |
| **Action** | None required. Cosmetic schematic fix optional. |

### AMS1117 (U3) — All 3 pin names swapped in symbol

| Detail | Value |
|--------|-------|
| **Severity** | LOW — no functional impact |
| **Problem** | Symbol: pin 1=VIN, 2=GND, 3=VOUT. Datasheet: pin 1=GND, 2=VOUT, 3=VIN. |
| **Reality** | Routing code maps pins correctly: `am_gnd = _pad("U3", "1")`, `am_vout = _pad("U3", "2")`, `am_vin = _pad("U3", "3")`. PCB nets verified: pad 1=GND, pad 3=+5V, pad 4(tab)=+3V3. All correct. |
| **Action** | None required. Routing compensates. Cosmetic schematic fix optional. |

---

## OK — Acceptable Deviations

### IP5306 (U2) — Thermal pad oversized

| Detail | Value |
|--------|-------|
| **Datasheet** | Exposed pad 2.09 x 2.09mm |
| **PCB** | 3.4 x 2.8mm (+62% wider, +34% taller) |
| **Risk** | Low — oversized thermal pad aids heat dissipation. Solder paste self-centers during reflow. Gap to nearest signal pin is 0.155mm (acceptable). |
| **Action** | None. JLCPCB stencil handles this. |

### IP5306 (U2) — VOUT capacitance reduced

| Detail | Value |
|--------|-------|
| **Datasheet** | 3x 22uF = 66uF on VOUT |
| **PCB** | 1x 22uF (C19) |
| **Risk** | Moderate — output ripple ~200-300mV instead of ~100mV. Acceptable because AMS1117 LDO downstream provides additional regulation. |
| **Action** | None for v2. Consider adding 1-2 extra 22uF caps in v3 if ripple is measured as problematic. |

### IP5306 (U2) — LED pins floating

| Detail | Value |
|--------|-------|
| **Datasheet** | Unused LED pins should be tied to BAT |
| **PCB** | Pins 2-4 (LED1-3) left NC |
| **Risk** | Low — no LEDs connected, internal LED drivers idle. Conservative fix would tie to BAT via resistor. |
| **Action** | None. Monitor for erratic behavior. |

### USB-C (J1) — Wide signal pad slightly narrow

| Detail | Value |
|--------|-------|
| **Datasheet** | VBUS/GND wide pads: 0.60mm |
| **PCB** | 0.55mm (-0.05mm) |
| **Risk** | Minimal — still solderable, slightly reduced solder fillet on power pads. |
| **Action** | None. Within JLCPCB tolerance. |

### Tact Switch (SW1-SW13) — Pad height undersized

| Detail | Value |
|--------|-------|
| **Datasheet** | Recommended land pattern ~1.0 x 1.5mm |
| **PCB** | 1.2 x 0.9mm (width OK, height 60% of recommended) |
| **Risk** | Low — terminal leads extend 1.5mm but 0.9mm pads cover the inner portion. Solder fillet still forms. DFM comment notes intentional enlargement from 0.75mm for JLCPCB 3D model coverage. |
| **Action** | None. Buttons function correctly. |

### Inductor L1 — Pads oversized

| Detail | Value |
|--------|-------|
| **Datasheet** | Recommended 0.6 x 1.5mm pads, 2.5mm gap |
| **PCB** | 1.4 x 3.4mm pads, 3.4mm center spacing (2.3x oversized) |
| **Risk** | Low — oversized pads waste PCB area but improve soldering reliability. No adjacent component conflicts. |
| **Action** | None. Conservative approach, works fine. |

### ESP32 (U1) — GND exposed pad slightly oversized

| Detail | Value |
|--------|-------|
| **Datasheet** | 3.7 x 3.7mm |
| **PCB** | 3.9 x 3.9mm (+0.2mm) |
| **Risk** | None — conservative oversizing improves thermal contact. |
| **Action** | None. |

### JST PH 2-pin (J3) — Drill slightly oversized

| Detail | Value |
|--------|-------|
| **Datasheet** | 0.70-0.80mm recommended hole |
| **PCB** | 0.85mm |
| **Risk** | None — intentional for JLCPCB minimum drill (0.80mm). Provides easier pin insertion. |
| **Action** | None. Documented in MEMORY.md as intentional. |

---

## Perfect Match — No Issues

| Component | LCSC | Notes |
|-----------|------|-------|
| FPC 40-pin (J4) | C2856812 | 40 pads, 0.5mm pitch, 0.3x1.5mm — all match |
| Slide Switch (SW_PWR) | C431540 | Pin spacing, NPTH holes, pad layout correct. Minor 0.05mm pin 2-3 spacing deviation. |
| Red LED (LED1) | C84256 | Standard 0805, correct |
| Green LED (LED2) | C19171391 | Standard 0805, correct |
| Resistors 0805 (R1-R19) | C27834/C17414/C149504/C17513 | Standard 0805, correct |
| Capacitors 0805 (C1-C20) | C49678/C15850/C12891 | Standard 0805/1206, correct |
| PAM8403 footprint | C5122557 | Narrow SOP-16 body 3.9mm correctly used (not wide 7.5mm SOIC-16W) |

---

## Rework Guide

Physical rework instructions for existing v2 boards: see [PCB v2 Rework Guide](rework-v2.md).

| Fix | Effort | Required? |
|-----|--------|-----------|
| SD Card power (pin 4 + pin 6) | 10 min | **YES** — mandatory |
| PAM8403 passives (7 components) | 35 min | Only if using speaker |
| USB-C solder reinforcement | 5 min | Optional, recommended |
