# Complete Short Circuit Map & Rework Guide — PCB v1 (commit adc073b)

**Date:** 2026-03-28
**PCB version:** commit `adc073b` (2026-03-19)
**Analysis method:** Automated segment-to-via collision detection on manufactured PCB

---

## Summary

**44 routing violations** found (gap < 0.05mm between trace and different-net via).
**8 power bridges** where a signal trace shorts two different power nets.
**3 severity levels:** CRITICAL (power-to-power bridge), HIGH (signal-to-power short), MEDIUM (marginal clearance, may or may not manifest).

---

## Priority Rework Order

Fix in this exact order. Test with multimeter after each fix.

### FIX 1 — BUG #1: VBUS trace overlaps GND via (ALREADY FIXED)

| | Detail |
|---|---|
| **Layer** | F.Cu |
| **Trace** | VBUS horizontal (82.0, 61.0) → (111.0, 61.0) w=0.5mm |
| **Via** | GND @ (108.50, 60.50) size=0.9mm |
| **Overlap** | -0.200mm |
| **Effect** | VBUS shorted to GND |
| **Status** | FIXED by user (scraped F.Cu around GND via) |

### FIX 2 — BUG #2: VBUS trace overlaps +5V via (ALREADY FIXED)

| | Detail |
|---|---|
| **Layer** | F.Cu |
| **Trace** | VBUS vertical (111.0, 61.0) → (111.0, 40.1) w=0.5mm |
| **Via** | +5V @ (111.50, 56.50) size=0.9mm |
| **Overlap** | -0.200mm |
| **Effect** | VBUS shorted to +5V |
| **Status** | FIXED by user (scraped F.Cu around +5V via) |

### FIX 3 — BUG #3: LCD_RST bridges VBUS and GND (CRITICAL — DO THIS NEXT)

| | Detail |
|---|---|
| **Layer** | F.Cu |
| **Trace** | LCD_RST horizontal (79.4, 33.0) → (119.6, 33.0) w=0.2mm |
| **Via 1** | GND @ (81.50, 32.96) size=0.9mm — overlap **-0.475mm** |
| **Via 2** | VBUS @ (110.95, 33.00) size=0.9mm — overlap **-0.515mm** |
| **Effect** | GND ↔ LCD_RST copper ↔ VBUS = direct power short |
| **Status** | NOT FIXED |

**Rework procedure:**

1. Work on **F.Cu side** (front — display/buttons side)
2. Locate the LCD_RST trace: thin horizontal copper line at y=33mm (about 5mm above ESP32 module top edge)
3. Cut the trace at **one point between x=83 and x=110** (anywhere in the 27mm gap between the two vias)
4. Recommended cut point: **x=95, y=33** (center of board, easy access)
5. Use a precision knife to scrape ~1mm of copper off the trace

```
F.Cu — y=33mm (under display area)

  x=79.4                     x=95            x=110.95    x=119.6
  ════◉══════════════════════╳═══════════════════◉════════════════
      GND via             CUT HERE           VBUS via
   (81.50, 32.96)         scrape 1mm      (110.95, 33.00)

  BEFORE: GND ──── LCD_RST copper ──── VBUS  (BRIDGE!)
  AFTER:  GND ────╳                    VBUS  (ISOLATED)
```

**LCD_RST will still work:** the signal reaches the FPC connector via B.Cu routing on the right side of the board.

**Verify after fix:** multimeter continuity between VBUS and GND should read open (>1MΩ).

---

### FIX 4 — USB_D- bridges +3V3 and GND (HIGH)

| | Detail |
|---|---|
| **Layer** | B.Cu |
| **Trace** | USB_D- vertical (91.7, 64.9) → (91.7, 37.5) w=0.2mm |
| **Via 1** | +3V3 @ (92.05, 44.60) size=0.9mm — overlap **-0.200mm** |
| **Via 2** | GND @ (92.05, 52.00) size=0.9mm — overlap **-0.200mm** |
| **Effect** | +3V3 ↔ USB_D- copper ↔ GND = power short |

**Rework:** On B.Cu (back), cut USB_D- trace at **y=48** (midpoint between the two vias). USB data will not work after this cut — only needed if USB flashing is required.

```
B.Cu — x=91.7mm

  y=44.60  ◉ +3V3 via           y=44.60  ◉ +3V3 via
           ║                              ║
           ║ USB_D-                       ╳ CUT at y=48
           ║                              ║
  y=52.00  ◉ GND via            y=52.00  ◉ GND via
```

---

### FIX 5 — BTN_UP bridges +3V3 and GND (HIGH)

| | Detail |
|---|---|
| **Layer** | B.Cu |
| **Trace** | BTN_UP vertical (67.5, 62.0) → (67.5, 31.1) w=0.25mm |
| **Via 1** | +3V3 @ (67.05, 44.60) size=0.9mm — overlap **-0.175mm** |
| **Via 2** | GND @ (67.05, 52.00) size=0.9mm — overlap **-0.175mm** |
| **Effect** | +3V3 ↔ BTN_UP copper ↔ GND = power short |

**Rework:** On B.Cu, cut BTN_UP trace at **y=48** (midpoint). Then bridge with thin wire from y=45.5 to y=51 on the opposite side to restore button function.

---

### FIX 6 — BTN_LEFT bridges +3V3 and GND (HIGH)

| | Detail |
|---|---|
| **Layer** | B.Cu |
| **Trace** | BTN_LEFT vertical (62.5, 64.4) → (62.5, 28.6) w=0.25mm |
| **Via 1** | +3V3 @ (62.05, 44.60) size=0.9mm — overlap **-0.175mm** |
| **Via 2** | GND @ (62.05, 52.00) size=0.9mm — overlap **-0.175mm** |
| **Effect** | +3V3 ↔ BTN_LEFT copper ↔ GND = power short |

**Rework:** On B.Cu, cut BTN_LEFT trace at **y=48**. Bridge with wire to restore button.

---

### FIX 7 — BTN_A bridges +3V3 and GND (HIGH)

| | Detail |
|---|---|
| **Layer** | B.Cu |
| **Trace** | BTN_A vertical (52.5, 66.8) → (52.5, 23.5) w=0.25mm |
| **Via 1** | +3V3 @ (52.05, 44.60) size=0.9mm — overlap **-0.175mm** |
| **Via 2** | GND @ (52.05, 52.00) size=0.9mm — overlap **-0.175mm** |
| **Effect** | +3V3 ↔ BTN_A copper ↔ GND = power short |

**Rework:** On B.Cu, cut BTN_A trace at **y=48**. Bridge with wire to restore button.

---

### FIX 8 — BTN_L bridges +3V3 and GND (HIGH)

| | Detail |
|---|---|
| **Layer** | B.Cu |
| **Trace** | BTN_L vertical (72.5, 73.5) → (72.5, 37.5) w=0.25mm |
| **Via 1** | +3V3 @ (72.05, 44.60) size=0.9mm — overlap **-0.125mm** |
| **Via 2** | GND @ (72.05, 52.00) size=0.9mm — overlap **-0.125mm** |
| **Via 3** | GND @ (73.05, 65.50) size=0.9mm — overlap **-0.025mm** |
| **Effect** | +3V3 ↔ BTN_L copper ↔ GND = power short |

**Rework:** On B.Cu, cut BTN_L trace at **y=48**. Bridge with wire.

---

## Single-Net Shorts (signal touches ONE power net)

These don't create power-to-power bridges but may cause signal malfunction.

| # | Layer | Signal | Power Via | Gap (mm) | Effect |
|---|-------|--------|-----------|----------|--------|
| 9 | F.Cu | BTN_Y | +3V3 (70.45, 44.00) | -0.475 | BTN_Y stuck to +3V3 |
| 10 | F.Cu | USB_D+ | GND (85.05, 66.00) | -0.425 | USB_D+ shorted to GND |
| 11 | F.Cu | LCD_DC | GND (109.05, 37.00) | -0.395 | LCD_DC stuck to GND |
| 12 | F.Cu | BTN_DOWN | +3V3 (25.95, 63.00) | -0.375 | BTN_DOWN stuck to +3V3 |
| 13 | F.Cu | BTN_DOWN | +3V3 (32.95, 63.00) | -0.375 | BTN_DOWN stuck to +3V3 |
| 14 | B.Cu | LCD_D0 | GND (134.50, 34.85) | -0.450 | LCD_D0 stuck to GND |
| 15 | B.Cu | SD_CS | GND (153.50, 34.85) | -0.450 | SD_CS stuck to GND — no SD card |
| 16 | B.Cu | LCD_D5 | GND (134.50, 34.85) | -0.350 | LCD_D5 stuck to GND |
| 17 | B.Cu | BTN_B | GND (143.00, 50.25) | -0.275 | BTN_B stuck to GND |
| 18 | F.Cu | BTN_A | GND (76.80, 67.12) | -0.250 | BTN_A also shorted to GND (F.Cu) |
| 19 | B.Cu | LCD_D7 | GND (81.50, 32.96) | -0.145 | LCD_D7 stuck to GND |
| 20 | F.Cu | BTN_SELECT | +3V3 (62.05, 44.60) | -0.075 | BTN_SELECT stuck to +3V3 |
| 21 | F.Cu | BTN_SELECT | +3V3 (67.05, 44.60) | -0.075 | BTN_SELECT stuck to +3V3 |
| 22 | F.Cu | BTN_SELECT | +3V3 (72.05, 44.60) | -0.075 | BTN_SELECT stuck to +3V3 |
| 23 | F.Cu | BTN_R | GND (123.50, 64.50) | -0.075 | BTN_R stuck to GND |
| 24 | B.Cu | BTN_SELECT | +3V3 (72.05, 44.60) | -0.075 | BTN_SELECT (B.Cu segment) |
| 25 | B.Cu | LCD_D4 | GND (134.50, 34.85) | -0.050 | LCD_D4 stuck to GND |
| 26 | F.Cu | LCD_D6 | +3V3 (88.75, 21.01) | -0.040 | LCD_D6 stuck to +3V3 |
| 27 | B.Cu | LCD_D4 | VBUS (110.95, 33.00) | -0.000 | LCD_D4 touching VBUS |

---

## Marginal Clearance (0 < gap < 0.05mm)

These may or may not manifest depending on JLCPCB etching precision.

| # | Layer | Signal | Power Via | Gap (mm) |
|---|-------|--------|-----------|----------|
| 28-32 | B.Cu | LCD_RD | GND vias x=133.45 (4 vias) | +0.025 |
| 33 | B.Cu | LCD_RD | +3V3 via (133.45, 26.25) | +0.025 |
| 34-37 | B.Cu | LCD_RST | GND vias x=133.45 (4 vias) | +0.025 |
| 38 | B.Cu | LCD_RST | +3V3 via (133.45, 26.25) | +0.025 |

---

## Complete Violation Summary

| Severity | Count | Description |
|----------|-------|-------------|
| **CRITICAL** | 3 | Power-to-power bridges (FIX 1-3) |
| **HIGH** | 5 | +3V3-to-GND bridges via buttons/USB (FIX 4-8) |
| **MEDIUM** | 19 | Signal stuck to single power net (#9-27) |
| **MARGINAL** | 11 | Gap 0-0.05mm, may not manifest (#28-38) |
| **BUG 1+2** | 2 | Already fixed by user |
| **Total** | **44** | |

---

## Assessment

This PCB v1 has **too many routing violations for practical rework**. Fixes 1-3 address the power shorts, but even after that:
- 5 button traces bridge +3V3 to GND (each needs cut + wire bridge)
- 6 LCD data lines are shorted to GND or +3V3 (display won't work)
- SD_CS is shorted to GND (no SD card access)
- USB data lines are shorted

**Recommendation:** Fix BUG #3 (LCD_RST bridge) to verify power rails work, then evaluate whether the board is salvageable for basic testing. For full functionality, a new PCB revision with corrected routing is needed.

---

## Measurement Checklist

After each fix, measure with multimeter in continuity mode:

| Test | Pad 1 | Pad 2 | Expected | After FIX |
|------|-------|-------|----------|-----------|
| VBUS-GND | C17 pad+ | C17 pad- | >1MΩ | FIX 3 |
| +5V-GND | C1 pad+ | C1 pad- | >1MΩ | FIX 3 |
| +3V3-GND | C2 pad+ | C2 pad- | >1MΩ | FIX 4-8 |
| BAT+-GND | C18 pad+ | C18 pad- | >1MΩ | FIX 3 |
