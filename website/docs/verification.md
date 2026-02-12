---
id: verification
title: Pre-Production Verification
sidebar_position: 10
---

# Pre-Production Verification

Automated test battery that validates the entire design before PCB manufacturing. These checks run automatically on every commit via a git pre-commit hook.

```bash
python3 scripts/drc_check.py
python3 scripts/simulate_circuit.py
python3 scripts/verify_schematic_pcb.py
```

---

## 1. DRC — Design Rules Check

**Script:** `scripts/drc_check.py`

Validates the PCB layout against JLCPCB 4-layer manufacturing constraints.

| Rule | JLCPCB Minimum | Our Design |
|:---|:---|:---|
| Trace width | 0.09 mm | 0.25 mm |
| Trace spacing | 0.09 mm | 0.2 mm |
| Via drill | 0.15 mm | 0.3 mm |
| Via pad | 0.45 mm | 0.6 mm |
| Annular ring | 0.13 mm | 0.15 mm |
| Board edge clearance | 0.3 mm | 0.5 mm |

### Checks performed

- **Component Overlap** — no footprints colliding or placed on mounting holes
- **Trace Width** — all segments meet minimum width
- **Via Dimensions** — drill size and annular ring validation
- **Board Edge Clearance** — traces/vias positioned safely from board edges
- **FPC Slot Intrusion** — nothing crosses the 3x24mm display connector cutout
- **Trace Spacing** — minimum clearance between different nets on same layer
- **Drill Spacing** — via-to-via center distances

---

## 2. Circuit Simulation

**Script:** `scripts/simulate_circuit.py`

Static electrical analysis — verifies power budget, signal timing, component values, and GPIO assignments.

### Power Budget

| Rail | Typical | Maximum | Regulator | Headroom |
|:---|---:|---:|:---|:---|
| +3V3 | 250 mA | 335 mA | AMS1117 (800 mA) | 58% |
| +5V | 283 mA | 387 mA | IP5306 (2.4 A) | 84% |

**AMS1117 thermal:** P = (5.0 - 3.3) x 335mA = 0.57W, Tj = 91°C (below 125°C max)

**Battery life:** 11.8h typical, 8.6h heavy use (5000mAh LiPo)

```
LiPo 3.7V 5000mAh
  |
  +--[IP5306 boost]--> +5V (387mA max)
  |    |
  |    +--[AMS1117 LDO]--> +3V3 (335mA max)
  |    |    |-- ESP32-S3 (200mA)
  |    |    |-- Display (100mA)
  |    |    +-- SD card (30mA)
  |    |
  |    +-- PAM8403 (50mA)
  |    +-- LEDs (2.4mA)
  |
  +--[USB-C VBUS]--> charge input (1A max)
```

### Signal Timing

| Signal | Requirement | Actual | Margin |
|:---|:---|:---|:---|
| Button debounce (RC) | > 1 ms | 1.0 ms (10k x 100nF) | OK |
| Display 8080 bus | 18.4 MB/s (60fps) | 20.0 MB/s (8-bit @ 20MHz) | 7.8% |
| SPI SD card | — | 5.0 MB/s @ 40MHz | 1.3s load |
| I2S audio | — | BCLK 1.024 MHz / 8 MHz max | OK |
| ESP32 EN reset | > 0.05 ms | 1.39 ms (10k x 100nF) | OK |

### Component Values

| Component | Value | Purpose | Validation |
|:---|:---|:---|:---|
| R1, R2 | 5.1k | USB-C CC pull-down | USB spec: 4.7k–5.6k |
| R3 | 10k | ESP32 EN pull-up | RC = 1ms with C3 |
| R4–R15, R19 | 10k | Button pull-ups | Logic HIGH = 3.3V > 2.475V (Vih) |
| R16 | 100k | IP5306 KEY pull-down | Keeps KEY low when idle |
| R17, R18 | 1k | LED current limiting | 1.3mA red, 1.1mA green |
| C1 | 10uF | AMS1117 input | Datasheet requirement |
| C2 | 22uF | AMS1117 output | Datasheet: >= 22uF |
| C3, C4 | 100nF | ESP32 decoupling | Standard practice |
| C5–C16, C20 | 100nF | Button debounce | RC = 1ms with 10k pull-ups |
| C17, C18 | 10uF | IP5306 decoupling | Datasheet requirement |
| C19 | 22uF | IP5306 output bulk | Datasheet requirement |
| L1 | 1uH / 4.5A | IP5306 boost inductor | 4.5A >> 387mA load |

---

## 3. Schematic-PCB Consistency

**Script:** `scripts/verify_schematic_pcb.py`

Cross-checks three sources of truth to ensure nothing is missing or mismatched.

| Source | Components |
|:---|:---|
| Schematic (7 sub-sheets) | 68 unique refs |
| PCB footprints | 65 refs |
| JLCPCB CPL (assembly) | 64 refs |

### Off-board components (correct exclusions)

| Ref | Component | Reason |
|:---|:---|:---|
| BT1 | LiPo battery | Connected via JST-PH cable |
| J2 | PSP joystick | Optional, not assembled |
| SPK1 | 28mm speaker | Soldered manually to pads |
| U4 | ILI9488 display | Connected via FPC cable |

---

## Known Warnings (accepted)

These warnings appear in every test run and are **expected behavior**, not defects.

### GPIO0 — SELECT button / Download Mode

```
+3.3V ──[10k R9]──┬── GPIO0 (ESP32)
                   │
              [SW10 SELECT]
                   │
                  GND
```

ESP32-S3 reads GPIO0 at boot: HIGH = normal boot, LOW = download mode. If SELECT is pressed during power-on, the ESP32 enters USB programming mode instead of running the game.

**Why it's OK:** This is a **feature** — it provides a way to flash firmware without a separate BOOT button. Normal usage (power on, then play) never triggers it.

### GPIO45 (LCD_BL) / GPIO46 (LCD_WR) — Strapping pins

| Pin | Function | Boot requirement | Our circuit |
|:---|:---|:---|:---|
| GPIO45 | LCD backlight | Must be LOW (3.3V VDD_SPI) | Backlight OFF at boot = LOW |
| GPIO46 | LCD write strobe | Must be LOW (normal boot) | Bus inactive at boot = LOW |

**Why it's OK:** Both pins are naturally LOW at power-on because the display is not yet initialized. The firmware enables them after boot completes.

:::caution What would happen if wrong
If GPIO45 were HIGH at boot, the ESP32 would set VDD_SPI to 1.8V instead of 3.3V, causing the PSRAM and flash to malfunction. Our circuit prevents this because the backlight starts OFF.
:::

### GPIO44 (JOY_Y) — No ADC

GPIO44 has no analog-to-digital converter. The joystick is **optional** (SNES games use only D-pad). If needed in the future, reassign JOY_Y to an ADC-capable GPIO (GPIO1–10).

### JOY_X / JOY_Y nets — No traces

The joystick nets have no PCB traces because the joystick is optional and not part of the v1.0 PCBA. These nets are reserved for a future revision.

---

## Running Verification

### Manually

```bash
python3 scripts/drc_check.py
python3 scripts/simulate_circuit.py
python3 scripts/verify_schematic_pcb.py
```

### Automatically (pre-commit hook)

All three checks run on every `git commit`. If any check fails (exit code != 0), the commit is blocked.

The hook is installed at `.githooks/pre-commit` and activated via:

```bash
git config core.hooksPath .githooks
```

### Expected output

```
[verify] DRC Check ............ PASS (0 errors, 2 warnings)
[verify] Circuit Simulation ... PASS (0 errors, 5 warnings)
[verify] Schematic-PCB ........ PASS
[verify] All pre-production checks passed
```
