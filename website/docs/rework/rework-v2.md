---
id: rework-v2
title: PCB v2 Rework Guide
sidebar_position: 1
---

# PCB v2 Rework Guide

Three issues found during datasheet-vs-PCB audit require physical rework on existing v2 boards. All fixes use standard soldering tools and 0805 SMD components.

**Tools needed:** soldering iron (fine tip), flux, 30AWG kynar/bodge wire, solder wick, magnifying glass/microscope.

---

## Fix 1: SD Card Power (CRITICAL)

**Problem:** SD card slot (U6) pins 4 (VDD) and 6 (GND) have no copper connection. The card receives no power.

**U6 is on the BACK side (B.Cu).** All work done on the back of the board.

### Pin locations (back side, looking at component)

```
         Signal pads (top edge of slot)
    ┌──────────────────────────────────┐
    │  1  2  3  4  5  6  7  8  9      │
    │         CS    VDD    GND   MISO  │
    │              ^^^    ^^^          │  ← FIX THESE
    │          SD CARD SLOT            │
    │                                  │
    └──────────────────────────────────┘
     Pin 13                      Pin 10
     (shield)                  (shield)
```

### Rework steps

1. **+3V3 to Pin 4 (VDD):**
   - Locate pin 4 on the TF-01A slot (4th pad from left on the signal row)
   - Find the nearest +3V3 source: the AMS1117 output cap (C2) or any pad/via labeled +3V3
   - Solder a 30AWG wire from **pin 4** to the nearest **+3V3 via or pad**
   - Alternative: drill a 0.3mm hole next to pin 4 and insert a via wire to reach the In2.Cu +3V3 plane

2. **GND to Pin 6 (VSS):**
   - Locate pin 6 (6th pad from left)
   - Find the nearest GND source: any via, mounting hole pad, or ground pour
   - Solder a 30AWG wire from **pin 6** to nearest **GND point**
   - The shield pads (pins 10-13) have large exposed copper — if any connects to GND, use that

3. **GND to Shield pads (pins 10, 12) — optional but recommended:**
   - Solder wires from 2 opposite shield pads to GND for EMI shielding

### Verification

- Multimeter continuity: pin 4 to any +3V3 pad → should beep
- Multimeter continuity: pin 6 to any GND pad → should beep
- Insert SD card, power on → SD should be detected by firmware

---

## Fix 2: PAM8403 Audio Passives (CRITICAL)

**Problem:** The PAM8403 Class-D amplifier is missing all passive components from the datasheet application circuit. No DC-blocking, no decoupling, no bias resistors.

**U5 is on the BACK side (B.Cu).** All work done on the back of the board.

### U5 pin layout (back side view, rotated 90°)

```
        Top row (y≈26.8)              Bottom row (y≈32.2)
    Pin 1  +OUT_L  ┐   ┌ Pin 16 +OUT_R
    Pin 2  PGND    │   │ Pin 15 PGND
    Pin 3  -OUT_L  │   │ Pin 14 -OUT_R
    Pin 4  PVDD    │ U5│ Pin 13 PVDD
    Pin 5  MUTE    │   │ Pin 12 SHDN
    Pin 6  VDD     │   │ Pin 11 GND
    Pin 7  INL     │   │ Pin 10 INR
    Pin 8  VREF    ┘   └ Pin 9  NC
```

### Components to add (all 0805 SMD)

| # | Value | Purpose | Connect between |
|---|-------|---------|-----------------|
| C_a | **0.47uF** | DC-blocking | I2S_DOUT trace → INR (pin 10) |
| R_a | **20k** | INL bias | Pin 7 (INL) → GND |
| R_b | **20k** | INR bias | Pin 10 (INR) → GND |
| C_b | **100nF** | VREF bypass | Pin 8 (VREF) → GND |
| C_c | **1uF** | VDD decoupling | Pin 6 (VDD) → GND |
| C_d | **1uF** | PVDD decoupling | Pin 4 (PVDD) → GND |
| C_e | **1uF** | PVDD decoupling | Pin 13 (PVDD) → GND |

### Rework steps (priority order)

**Step A — DC-blocking cap (most important):**
1. Locate the I2S_DOUT trace arriving at pin 10 (INR) — it's a vertical B.Cu trace at x≈33.2mm
2. **Cut the trace** between the via and pin 10 using a hobby knife
3. Solder a 0.47uF 0805 cap across the cut (one pad to via side, other to pin 10 side)
4. This blocks DC offset from the ESP32 DAC

**Step B — Bias resistors:**
1. Solder a 20k 0805 resistor from **pin 7 (INL)** to nearest GND point
2. Solder a 20k 0805 resistor from **pin 10 (INR)** to nearest GND point
3. These set the audio input bias point

**Step C — VREF bypass:**
1. Solder a 100nF 0805 cap from **pin 8 (VREF)** to **pin 2 (PGND)** — same row, 7.6mm apart
2. Use a short bodge wire if the cap can't bridge the distance

**Step D — Decoupling caps:**
1. Solder a 1uF 0805 cap from **pin 6 (VDD)** to **pin 11 (GND)** — opposite rows, bridging across
2. Solder a 1uF 0805 cap from **pin 4 (PVDD)** to **pin 2 (PGND)** — same row, 2.54mm apart (1 cap can bridge)
3. Solder a 1uF 0805 cap from **pin 13 (PVDD)** to **pin 15 (PGND)** — same row, 2.54mm apart

### Verification

- Power on without SD card
- Connect speaker to SPK+/SPK- pads
- Play a test tone from firmware → should hear clean audio without buzzing
- No DC offset: measure DC voltage across speaker terminals → should be < 20mV

---

## Fix 3: USB-C Shield Pads (HIGH)

**Problem:** Front shield pads are 1.1mm wide instead of datasheet 1.7mm. Reduces mechanical retention.

### Rework steps

1. **Add extra solder** to all 4 shield THT pads (pins 13, 14 front; 13b, 14b rear)
2. Build up a **generous solder fillet** around each tab to increase contact area
3. Optionally apply **UV-cure adhesive** (Bondic or similar) at the connector base for extra mechanical strength
4. Test: firmly pull/push USB-C cable — connector should not move

This is the simplest fix — just add more solder to compensate for the undersized pads.

---

## Fix Priority

| Fix | Effort | Impact | Required? |
|-----|--------|--------|-----------|
| 1. SD Card power | 10 min | **Board-breaking** — SD won't work at all | **YES** — mandatory |
| 2. PAM8403 passives | 35 min | Audio damage risk + noise | **Only if using speaker** |
| 3. USB-C pads | 5 min | Mechanical durability | Optional, recommended |

**Minimum rework: ~10 minutes** (fix #1 only, no audio).
**Full rework: ~50 minutes** (all fixes).

:::tip No speaker? Skip fix #2 entirely
If you are not connecting a speaker, the PAM8403 rework is unnecessary. Without a load, the Class-D amp draws ~10mA quiescent but causes no harm. All missing passives (DC-blocking, decoupling, bias) only matter when driving a speaker. You can do fix #2 later when you want audio.
:::

---

## Parts Shopping List (for rework)

| Qty | Value | Package | Use |
|-----|-------|---------|-----|
| 1 | 0.47uF ceramic | 0805 | PAM8403 DC-blocking |
| 3 | 1uF ceramic | 0805 | PAM8403 decoupling (VDD + 2x PVDD) |
| 1 | 100nF ceramic | 0805 | PAM8403 VREF bypass |
| 2 | 20k resistor | 0805 | PAM8403 input bias |
| 1m | 30AWG kynar wire | — | Bodge wires for all fixes |
