---
id: incident-power-short
title: "Incident: Power Short Circuit (PCB v1)"
sidebar_position: 13
---

# Incident: Power Short Circuit — PCB v1

**Date:** 2026-03-26
**Severity:** Critical (board non-functional)
**Affected boards:** 5/5 (100%) — design bug, not component failure
**Status:** Root cause identified, fix applied in routing.py, boards reworkable
**Update 2026-03-28:** BUG #3 discovered (LCD_RST bridge), full 44-violation map completed

## Symptoms

Six power decoupling capacitors measured 0 ohm (short to GND) on all 5 assembled boards:

| # | Ref | Position (mm) | Package | Net (pad+) | Net (pad-) | Expected | Measured |
|---|-----|---------------|---------|------------|------------|----------|----------|
| 1 | C17 | (110, 35.0) | 0805 | VBUS | GND | >1M ohm | ~0 ohm |
| 2 | C1 | (122, 48.5) | 0805 | +5V | GND | >1M ohm | ~0 ohm |
| 3 | C18 | (118, 55.0) | 0805 | BAT+ | GND | >1M ohm | ~0 ohm |
| 4 | C19 | (110, 58.5) | 1206 | +5V | GND | >1M ohm | ~0 ohm |
| 5 | C2 | (125, 62.5) | 1206 | +3V3 | GND | >1M ohm | ~0 ohm |
| 6 | C3 | (69.5, 42.0) | 0805 | +3V3 | GND | >1M ohm | ~0 ohm |

USB-C connector (J1) was desoldered — short persisted, ruling out connector as cause.

## Root Cause: Via-to-Trace Overlap on F.Cu

Two vias from capacitor C19 overlapped the VBUS power trace on the front copper layer (F.Cu), creating a direct metallurgical short that chained all power rails to GND.

### Bug #1: GND via overlaps VBUS horizontal trace

```
          VBUS horizontal trace (F.Cu, width=0.5mm)
  y=61.25 ─────────────────────────────────────── top edge
  y=61.00 ═══════════════════════════════════════ centerline
  y=60.75 ─────────────────────────────────────── bottom edge
  y=60.95 ·····o····· GND via annular ring top    <-- OVERLAP 0.20mm
  y=60.50     (*)     GND via center
  y=60.05 ·····o····· GND via annular ring bottom

           x=82                    x=108.5    x=111
```

The GND via annular ring (r=0.45mm) extended to y=60.95, but the VBUS trace bottom edge was at y=60.75. **0.20mm copper overlap** = direct short.

### Bug #2: +5V via overlaps VBUS vertical trace

```
        VBUS vertical trace (F.Cu, width=0.5mm)
  x=110.75 |     | x=111.25
           |     |
  x=111.05 |.....|.o  +5V via annular ring left  <-- OVERLAP 0.20mm
           |     |(*) +5V via center @x=111.50
  x=111.95 |     | o  +5V via annular ring right
```

### Short Propagation Chain

The two F.Cu violations created a chain that shorted ALL power rails to GND:

```
                F.Cu Layer Violations
                =====================

  GND via ──────── overlaps ──────── VBUS trace
  @(108.5, 60.5)    -0.20mm         @y=61.0
       |                                |
       |                                | same trace
       |                                |
       |         +5V via ──── overlaps ──── VBUS trace
       |         @(111.5, 56.5) -0.20mm    @x=111.0
       |              |
       v              v
      GND ====== VBUS ====== +5V
                               |
                          AMS1117 (U3)
                               |
                              +3V3
```

**Result:** Every power rail reads 0 ohm to GND through F.Cu copper overlap.

## F.Cu Routing — Problem Area Diagram

```
F.Cu Layer (front copper) — power trace routing

  y=40 --- - - - - - - - - - - - - - - - - - - - -
                          # VBUS vertical @x=111
                          # (width 0.5mm)
  y=48 --- - - - - - - - -#- - - - - - - - - - - -
                          #
                          #
  y=56 --- - - - - - - - -#- - - - - - - - - - - -
                         o#<-- BUG #2: +5V via @(111.5, 56.5)
                          #      overlaps VBUS vert (-0.20mm)
                          #
  y=60 --- - - - - - - - -#- - - - - - - - - - - -
               o          #
               ^          #
  y=61 =======X==========X=== VBUS horizontal @y=61
               |          #      (width 0.5mm, x=82->111)
               |          #
        BUG #1: GND via   #
        @(108.5, 60.5)    #
        overlaps VBUS     #
        horiz (-0.20mm)   #
                          #
  x=82       x=108.5    x=111

  Legend:  === VBUS trace    o via (wrong clearance)
```

## Component Map (B.Cu Bottom Layer)

```
B.Cu viewed from back (X mirrored) — as seen in photos
Board: 160 x 75 mm

     +-------------------------------------------------------------+
     | [btn L]                                        [btn R]      |
     |                                                             |
     |    [FPC J4]          [ESP32-S3 U1]        [PAM8403 U4]     |
     |     ||  ||          +--------------+        +--------+      |
     |     ||  ||     !C17 |              |        |        |      |
     |     ||  ||   (110,35)|  (80,27.5)  |        |(30,30) |      |
     |              *      |              |        |        |      |
     |          U2 IP5306  +--------------+        +--------+      |
     |  !C1    (110,42.5)                                          |
     | (122,49)                              !C3                   |
     |          ##L1##                     (69.5,42)               |
     | !C18   (110,52.5)                                           |
     | (118,55)  U3 AMS1117                                        |
     |          (125,55.5)    R4 R5 R6 ..... R14 R15 R19           |
     |          !C19         C5 C6 C7 ..... C15 C16 C20            |
     | !C2    (110,58.5)                                           |
     | (125,63)                                                    |
     |                                                             |
     | [btn]  [SD]    [JST bat]    [USB-C]   [btn]   [switch]     |
     +-------------------------------------------------------------+

     ! = shorted capacitor     * = IP5306 (NOT the culprit)
```

## Origin of the Bug

Both problematic vias were generated by **C19** (1206 capacitor, +5V/GND, at 110, 58.5 on B.Cu):

```python
# routing.py — C19 via generation (BEFORE fix)
# C19 pad "1" (+5V) at (111.5, 58.5) -> via at (111.5, 56.5)  <-- BUG #2
# C19 pad "2" (GND)  at (108.5, 58.5) -> via at (108.5, 60.5)  <-- BUG #1
```

C19 was added during a DFM fix that moved it to (110, 58.5), but its via offsets (+-2mm vertical) were never checked against the VBUS F.Cu traces at y=61 and x=111. The VBUS route had been changed to y=61 in "SHORT FIX v4" — placing it exactly in the path of C19's vias.

## Why It Wasn't Caught

| Check | Why it missed |
|-------|---------------|
| **Collision grid** (routing.py) | Reported 186 violations total, but power shorts were buried among 180+ FPC/display violations. Not treated as blocking errors. |
| **verify_dfm_v2.py** | Checks pad spacing, drill sizes, silk clearance — does NOT check via-to-trace clearance |
| **verify_dfa.py** | Checks assembly (rotation, BOM, CPL) — not copper routing |
| **KiCad DRC** | Zone fill might mask the overlap if GND zone creates thermal relief |
| **JLCPCB review** | 0.2mm overlap below typical visual inspection threshold |
| **Visual inspection** | F.Cu side is under the display — not visible during testing |

## Fix Applied (routing.py)

### Fix 1: GND via — reduce Y offset

```python
# BEFORE: via at y = pad_y + 2.0 = 60.5 (overlaps VBUS @y=61)
# AFTER:  via at y = pad_y + 1.0 = 59.5 (gap = 0.80mm)
parts.append(_seg(c19_p2[0], c19_p2[1], c19_p2[0], c19_p2[1] + 1.0,
                  "B.Cu", W_SIG, n_gnd))
parts.append(_via_net(c19_p2[0], c19_p2[1] + 1.0, n_gnd))
```

### Fix 2: +5V via — route horizontally to clear VBUS vertical

```python
# BEFORE: via at (111.5, 56.5) — overlaps VBUS vert @x=111
# AFTER:  route B.Cu horizontal to x=113, then via at (113, 56.5)
#         gap to VBUS: 113 - 0.45 - 111.25 = 1.30mm
safe_x = 113.0
parts.append(_seg(c19_p1[0], c19_p1[1], safe_x, c19_p1[1],
                  "B.Cu", W_SIG, NET_ID["+5V"]))
parts.append(_seg(safe_x, c19_p1[1], safe_x, c19_p1[1] - 2,
                  "B.Cu", W_SIG, NET_ID["+5V"]))
parts.append(_via_net(safe_x, c19_p1[1] - 2, NET_ID["+5V"]))
```

### Clearance verification after fix

| Via | Old position | New position | Gap to VBUS | Status |
|-----|-------------|-------------|-------------|--------|
| GND | (108.5, 60.5) | (108.5, 59.5) | 0.80mm | PASS |
| +5V | (111.5, 56.5) | (113.0, 56.5) | 1.30mm | PASS |

All 88 DFM tests and 9 DFA assembly tests pass after regeneration.

## Rework Procedure for Existing Boards

The fix is **surgical but simple**: scrape copper on F.Cu to create clearance around 2 vias. No jumper wires needed — vias still connect to GND (In1.Cu) and +5V (In2.Cu) through inner power planes.

### Tools needed

- Precision knife (X-Acto) or scalpel
- Magnifying glass or loupe (10x)
- Multimeter (continuity mode)
- Isopropyl alcohol + cotton swab
- Optional: clear nail polish or UV solder mask for protection

### Step-by-step

#### Preparation

1. Remove display panel (unclip FPC ribbon)
2. Clean F.Cu (top/display) side with isopropyl alcohol
3. Locate the 2 vias on F.Cu:

```
F.Cu (top/display side) — looking down at the board

                     VBUS vertical trace
                     @x=111, width 0.5mm
                          |#|
                          |#|
    +5V via ----------> --|o|-- y=56.5
    (111.5, 56.5)        |#|    Scrape HERE: isolate via ring
    r=0.45mm             |#|    from VBUS trace on LEFT side
                          |#|
                          |#|
                          |#|
    ======================X#X========  VBUS horizontal @y=61
                       ---|o|---       width 0.5mm
                          | |
    GND via ------------> (108.5, 60.5)
    r=0.45mm                 Scrape HERE: isolate via ring
                             from VBUS trace ABOVE
```

#### Via 1: GND via at (108.5, 60.5) — overlaps VBUS horizontal

4. Find the GND via on F.Cu — ~2.5mm LEFT of the corner where VBUS horizontal meets vertical
5. With a scalpel blade, scrape a **thin line** (0.3mm) of copper between:
   - The TOP edge of the via ring (y ~ 60.95)
   - The BOTTOM edge of the VBUS horizontal trace (y ~ 60.75)
6. Cut direction: **horizontal**, parallel to the VBUS trace
7. Verify with multimeter: via pad vs VBUS trace = **open circuit**

#### Via 2: +5V via at (111.5, 56.5) — overlaps VBUS vertical

8. Find the +5V via — ~4.5mm ABOVE Via 1, ~3mm to the RIGHT
9. Scrape a **thin line** (0.3mm) of copper between:
   - The LEFT edge of the via ring (x ~ 111.05)
   - The RIGHT edge of the VBUS vertical trace (x ~ 111.25)
10. Cut direction: **vertical**, parallel to the VBUS trace
11. Verify with multimeter: via pad vs VBUS trace = **open circuit**

#### Cross-section diagram

```
BEFORE (shorted):

  F.Cu ===VBUS===*GND===   <-- via ring touches trace
  In1.Cu --------GND------  <-- GND zone
  In2.Cu --------+5V------  <-- +5V zone
  B.Cu ====C19=pad=*======  <-- C19 GND pad

AFTER (fixed):

  F.Cu ===VBUS==X...*GND..  <-- scraped gap, via ring isolated
  In1.Cu --------GND------  <-- GND zone still connected to via
  In2.Cu --------+5V------  <-- +5V zone still connected
  B.Cu ====C19=pad=*======  <-- C19 still works through inner layers

  X = scraped copper gap (0.3mm)
  * = via (still connects to inner layers through barrel)
```

#### Verification

12. Test ALL 6 capacitors — each should read **high impedance** (>100k ohm):

| # | Ref | Expected after fix |
|---|-----|--------------------|
| 1 | C17 | >100k ohm (was 0 ohm) |
| 2 | C1  | >100k ohm (was 0 ohm) |
| 3 | C18 | >100k ohm (was 0 ohm) |
| 4 | C19 | >100k ohm (was 0 ohm) |
| 5 | C2  | >100k ohm (was 0 ohm) |
| 6 | C3  | >100k ohm (was 0 ohm) |

#### Power-on test

13. Connect USB-C to a **current-limited supply** (100mA max, 5V)
14. Expected: current draw < 50mA (idle, no battery)
15. If current immediately hits limit — additional short exists, do NOT continue
16. Measure voltages:

| Test point | Expected |
|-----------|----------|
| VBUS (C17 pad+) | 5.0V |
| +5V (C1 pad+) | 4.8-5.2V |
| +3V3 (C2 pad+) | 3.3V |
| BAT+ (C18 pad+) | 0V (no battery) |

#### Protection

17. Apply UV solder mask or clear nail polish over scraped areas
18. Reattach display panel

**Estimated time per board: ~10 minutes**

## BUG #3: LCD_RST Bridges VBUS and GND (discovered 2026-03-28)

After physically fixing BUG #1 and #2, boards still showed a VBUS-to-GND short. A deeper analysis revealed a **third short** that was listed in the original collision report (items #9 and #10 in the "Power vs Signal" category) but not recognized as a power bridge.

### Root cause

A 40mm-long LCD_RST trace on F.Cu at y=33.0 passes over **two different power vias**:

| Via | Net | Position | Overlap |
|-----|-----|----------|---------|
| ESP32 GND via | GND | (81.50, 32.96) | -0.475mm |
| C17 VBUS via | VBUS | (110.95, 33.00) | -0.515mm |

```
F.Cu layer — y = 33mm (under display area)

  x=79.4                    CUT x=95           x=110.95    x=119.6
  ====o==============================X=============o================
      GND via              scrape here          VBUS via
   (81.50, 32.96)                            (110.95, 33.00)

  GND <---- LCD_RST copper ----> VBUS  =  DIRECT BRIDGE
```

### Why it was missed

The original analysis (section 12.B) listed these as two separate "Power vs Signal" violations. The pairwise check found LCD_RST overlapping a VBUS via and LCD_RST overlapping a GND via independently, but did not recognize that **together** they formed a power-to-power bridge through the shared signal copper.

### Rework

On F.Cu (front/display side), cut the LCD_RST trace at **x=95, y=33** (center of board). LCD_RST still functions via B.Cu routing to the FPC connector.

### DFM test added

`test_power_bridge_detection()` now groups violations by trace and flags when a single trace touches vias from 2+ different power nets.

## Complete Violation Map (44 total)

Full analysis of **all 44 routing violations** found on the manufactured PCB (commit `adc073b`), including 8 power bridges, 19 single-net shorts, and rework procedures for each:

**[Complete Short Circuit Map and Rework Guide](https://github.com/pjcau/esp32-emu-turbo/blob/main/hardware/debug/all-shorts-rework.md)**

### Summary

| Severity | Count | Description |
|----------|-------|-------------|
| CRITICAL | 3 | Power-to-power bridges (BUG #1, #2, #3) |
| HIGH | 5 | +3V3-to-GND bridges via button/USB signal traces |
| MEDIUM | 19 | Signal stuck to single power net |
| MARGINAL | 11 | Gap 0-0.05mm, may not manifest |
| **Total** | **44** | |

### Assessment

After fixing BUGs #1-3, power rails should work. However, with 24 additional signal-to-power shorts, the board has limited functionality: display, SD card, several buttons, and USB data lines are affected. A new PCB revision with corrected routing is needed for full functionality.

## New DFM Tests Added (2026-03-28)

Four tests added to `verify_dfm_v2.py` to prevent recurrence:

| Test | What it catches | Old PCB violations |
|------|----------------|--------------------|
| `test_via_annular_ring_trace_clearance` | Via copper (not just drill) overlapping traces | 72 |
| `test_signal_power_via_overlap` | Signal trace touching any power via | 32 |
| `test_trace_crossing_same_layer` | Perpendicular trace crossings | 55 |
| `test_power_bridge_detection` | Signal trace bridging 2+ power nets | 6 |

**Root cause of test gap:** `test_drill_trace_clearance` (test 42) used drill radius (0.175mm) instead of annular ring copper radius (0.45mm) — a 0.275mm blind spot per via.

## Lessons Learned

1. **Via placement must be checked against power traces** — the collision grid reported this, but violations were not treated as blocking errors
2. **Power-net overlaps must be fatal** — any cross-net overlap with gap < 0mm should fail the build
3. **Late component moves need clearance re-verification** — C19 was moved during a DFM fix without rechecking its via paths against existing F.Cu routes
4. **Separate power violations from signal violations** — 2 critical power shorts were hidden among 180+ signal violations in the collision report
5. **Bridge detection requires grouping, not just pairwise checks** — two "signal vs power" violations on the same trace form a power bridge (BUG #3)
6. **Test the right dimension** — drill radius != copper radius; the annular ring extends 0.275mm beyond the drill edge
