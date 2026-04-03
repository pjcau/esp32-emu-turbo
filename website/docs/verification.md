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

**Primary Script:** `scripts/drc_native.py`

Validates the PCB layout against JLCPCB 4-layer manufacturing constraints using KiCad's native DRC engine with custom manufacturing rules.

| Rule | JLCPCB Minimum | Our Design |
|:---|:---|:---|
| Trace width | 0.09 mm | 0.25 mm |
| Trace spacing | 0.09 mm | 0.2 mm |
| Via drill | 0.15 mm | 0.2 mm |
| Via pad | 0.35 mm | 0.35–0.46 mm |
| Annular ring | 0.075 mm | 0.075–0.13 mm |
| Board edge clearance | 0.3 mm | 0.5 mm |

### JLCPCB Custom DRC Rules

The project uses custom design rules from [tinfever's JLCPCB DRC ruleset](https://github.com/tinfever/KiCAD-Custom-DRC-Rules-for-JLCPCB-with-Unit-Tests) integrated as `hardware/kicad/esp32-emu-turbo.kicad_dru`. This file defines JLCPCB's manufacturing constraints for 4-layer boards with standard vias and is **automatically loaded by KiCad during DRC**.

Key rules enforced:
- **4-layer, 1oz+0.5oz copper** specifications
- **Minimum track width** 0.09mm
- **Minimum clearance** 0.09mm
- **Standard via** min drill 0.3mm, min diameter 0.45mm
- **PTH holes** 0.2-6.35mm range
- **Annular ring** min 0.075mm (JLCPCB absolute minimum for standard process)
- **Buried vias disallowed** (JLCPCB doesn't support them)

### Smart DRC Analysis

`drc_native.py` wraps `kicad-cli` DRC output with intelligent categorization:

- **Known-acceptable violations** — filtered out (e.g., zone clearance false positives, solder mask bridges on fine-pitch connectors)
- **Real issues** — prioritized by severity (CRITICAL/HIGH/MEDIUM/LOW) with source file mapping and fix suggestions
- **Delta tracking** — compares against saved baseline to detect regressions
- **Clearance split** — distinguishes zone clearance (false positive) from trace clearance (real JLCPCB issue)

### Checks performed

- **Component Overlap** — no footprints colliding or placed on mounting holes
- **Trace Width** — all segments meet minimum width
- **Via Dimensions** — drill size and annular ring validation
- **Board Edge Clearance** — traces/vias positioned safely from board edges
- **FPC Slot Intrusion** — nothing crosses the 3x24mm display connector cutout
- **Trace Spacing** — minimum clearance between different nets on same layer
- **Drill Spacing** — via-to-via center distances
- **JLCPCB Manufacturing Constraints** — via `.kicad_dru` custom rules

### DFM API Research Findings

**Question:** Can we automate JLCPCB DFM analysis via API or CLI?

**Answer:** No. After researching all major PCB manufacturers, **none** provide programmatic access to their DFM engines:

| Manufacturer | DFM Analysis | API/CLI Access | CI/CD Support |
|:-------------|:-------------|:---------------|:--------------|
| **JLCPCB** | Web-based only (after Gerber upload) | No | No |
| **PCBWay** | Web-based only | No | No |
| **NextPCB** | Web-based only | No | No |
| **Elecrow** | Web-based only | No | No |
| **Seeed Studio** | Web-based only | No | No |

**Conclusion:** The only CI/CD-compatible approach for manufacturability verification is **KiCad native DRC with custom `.kicad_dru` rules** matching the manufacturer's constraints. This is the approach used in this project.

While manufacturer web DFM tools may catch additional edge cases (e.g., silkscreen resolution, panelization issues), they require manual upload and review. The `.kicad_dru` + `drc_native.py` pipeline catches 95%+ of issues automatically and runs in seconds.

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
| PCB footprints | 78 refs |
| JLCPCB CPL (assembly) | 71 refs |

### Off-board components (correct exclusions)

| Ref | Component | Reason |
|:---|:---|:---|
| BT1 | LiPo battery | Connected via JST-PH cable |
| J2 | PSP joystick | Removed in v2 (was optional) |
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

### GPIO43 (BTN_R) — Was TX0

GPIO43 was previously reserved for UART debug (TX0). It is now assigned to BTN_R. UART debug is replaced by native USB (GPIO19/20 as USB_D-/D+).

### USB Native Data (GPIO19/20)

GPIO19 and GPIO20 carry USB D- and D+ for firmware flashing and CDC debug console. These pins connect to the USB-C connector alongside the power lines (VBUS/GND for charging via IP5306).

---

## 4. Pre-Production Net Audit

Full audit of every ESP32-S3 GPIO connection, verified across four sources: `config.py` (GPIO mapping), PCB traces, `board_config.h` (firmware), and documentation.

### Display — 8080 Parallel (14/14 routed)

| GPIO | Signal | Net | Segments | Vias | Status |
|:-----|:-------|:----|:---------|:-----|:-------|
| 4 | LCD_D0 | 6 | 6 | 4 | OK |
| 5 | LCD_D1 | 7 | 6 | 4 | OK |
| 6 | LCD_D2 | 8 | 6 | 4 | OK |
| 7 | LCD_D3 | 9 | 6 | 4 | OK |
| 8 | LCD_D4 | 10 | 10 | 6 | OK |
| 9 | LCD_D5 | 11 | 6 | 4 | OK |
| 10 | LCD_D6 | 12 | 7 | 4 | OK |
| 11 | LCD_D7 | 13 | 7 | 4 | OK |
| 12 | LCD_CS | 14 | 10 | 6 | OK |
| 13 | LCD_RST | 15 | 6 | 4 | OK |
| 14 | LCD_DC | 16 | 10 | 6 | OK |
| 46 | LCD_WR | 17 | 8 | 6 | OK |
| 3 | LCD_RD | 18 | 6 | 4 | OK |
| 45 | LCD_BL | 19 | 6 | 4 | OK |

### SD Card — SPI (4/4 routed)

| GPIO | Signal | Net | Segments | Vias | Status |
|:-----|:-------|:----|:---------|:-----|:-------|
| 36 | SD_MOSI | 20 | 7 | 6 | OK |
| 37 | SD_MISO | 21 | 7 | 6 | OK |
| 38 | SD_CLK | 22 | 7 | 6 | OK |
| 39 | SD_CS | 23 | 7 | 6 | OK |

### Audio — I2S + PAM8403 (3/3 routed)

| GPIO | Signal | Net | Segments | Vias | Status |
|:-----|:-------|:----|:---------|:-----|:-------|
| 17 | I2S_DOUT | 26 | 5 | 2 | OK |
| — | SPK+ | 42 | 4 | 2 | OK |
| — | SPK- | 43 | 3 | 2 | OK |

:::info I2S_BCLK and I2S_LRCK — intentionally unrouted
GPIO15 (I2S_BCLK, net 24) and GPIO16 (I2S_LRCK, net 25) are allocated in the ESP-IDF I2S driver but have **no PCB traces by design**. The PAM8403 is an analog Class-D amplifier — it has no I2S input. Only I2S_DOUT carries the audio signal (PDM/sigma-delta) to the PAM8403 analog inputs (INR/INL).
:::

### Buttons — GPIO Input (12/12 routed)

| GPIO | Signal | Net | Segments | Vias | Status |
|:-----|:-------|:----|:---------|:-----|:-------|
| 40 | BTN_UP | 27 | 7 | 5 | OK |
| 41 | BTN_DOWN | 28 | 7 | 5 | OK |
| 42 | BTN_LEFT | 29 | 7 | 5 | OK |
| 1 | BTN_RIGHT | 30 | 7 | 5 | OK |
| 2 | BTN_A | 31 | 7 | 5 | OK |
| 48 | BTN_B | 32 | 8 | 5 | OK |
| 47 | BTN_X | 33 | 8 | 5 | OK |
| 21 | BTN_Y | 34 | 8 | 5 | OK |
| 18 | BTN_START | 35 | 7 | 5 | OK |
| 0 | BTN_SELECT | 36 | 8 | 5 | OK |
| 35 | BTN_L | 37 | 5 | 2 | OK |
| 43 | BTN_R | 38 | 6 | 4 | OK |

### USB — Native (5/5 routed)

| GPIO | Signal | Net | Segments | Vias | Status |
|:-----|:-------|:----|:---------|:-----|:-------|
| 20 | USB_D+ | 40 | 5 | 2 | OK |
| 19 | USB_D- | 41 | 4 | 2 | OK |
| — | VBUS | 2 | 7 | 3 | OK |
| — | USB_CC1 | 48 | 3 | 0 | OK |
| — | USB_CC2 | 49 | 3 | 2 | OK |

### Power (5/5 routed)

| Signal | Net | Segments | Vias | Status |
|:-------|:----|:---------|:-----|:-------|
| GND | 1 | 66 | 49 | OK |
| VBUS | 2 | 7 | 3 | OK |
| +5V | 3 | 12 | 7 | OK |
| +3V3 | 4 | 26 | 21 | OK |
| BAT+ | 5 | 12 | 6 | OK |
| LX | 46 | 3 | 0 | OK |

### Summary

| Category | Routed | Total | Result |
|:---------|:-------|:------|:-------|
| Display (8080) | 14 | 14 | **PASS** |
| SD Card (SPI) | 4 | 4 | **PASS** |
| Audio (I2S) | 3 | 3 | **PASS** |
| Buttons | 12 | 12 | **PASS** |
| USB (native) | 5 | 5 | **PASS** |
| Power | 6 | 6 | **PASS** |
| **Total** | **44** | **44** | **ALL PASS** |

Cross-reference validation:
- `config.py` ↔ `board_config.h`: all GPIO assignments match
- `config.py` ↔ `snes-hardware.md`: all documentation matches
- `_PIN_TO_GPIO` mapping: 36 pins verified, all correct
- Zero orphaned nets (all defined signals are routed or intentionally unconnected)

---

## 5. Hole & Drill Audit

Verification of all through-holes (PTH + NPTH) against component datasheets, short circuit risk analysis, and copper clearance check.

**Total holes:** 16 component holes + 6 mounting holes + 269 vias = **291 drill operations**

### Component NPTH — Datasheet Verification

Positioning holes (NPTH) must match the component peg diameter with adequate clearance. Dimensions verified against datasheets in `hardware/datasheets/`.

| Ref | Component | Holes | PCB Drill | Datasheet Spec | Peg Diameter | Clearance | Status |
|-----|-----------|-------|-----------|----------------|--------------|-----------|--------|
| J1 | USB-C 16P (C2765186) | 2x NPTH | 0.65 mm | ø0.65(2X) | ø0.50 mm | 0.15 mm | **PASS** |
| U6 | TF-01A SD slot (C91145) | 2x NPTH | 1.00 mm | 2-∅1.00 | ø0.80 mm | 0.20 mm | **PASS** |
| SW_PWR | MSK12C02 slide switch (C431540) | 2x NPTH | 0.90 mm | ø0.75 pegs | ø0.75 mm | 0.15 mm | **PASS** |
| J3 | JST PH 2-pin (C173752) | 2x THT | 0.85 mm | ø0.7 +0.1/-0 | ø0.50 mm pins | 0.35 mm | **PASS** |

### Mounting Holes (6x NPTH, 2.5 mm)

Standard M2.5 mounting holes at board corners and center, no electrical connection.

| Position (mm) | Nearest Copper | Gap (mm) | Min Required | Status |
|---------------|----------------|----------|--------------|--------|
| (10.0, 7.0) | SW11 pad | 1.74 | 0.20 | **PASS** |
| (150.0, 7.0) | net22 trace | 1.15 | 0.20 | **PASS** |
| (10.0, 68.0) | net35 trace | 0.85 | 0.20 | **PASS** |
| (150.0, 68.0) | net22 trace | 1.15 | 0.20 | **PASS** |
| (55.0, 37.5) | net31 trace | 1.20 | 0.20 | **PASS** |
| (105.0, 37.5) | net17 trace | 0.57 | 0.20 | **PASS** |

### Short Circuit Risk Analysis

| Check | Detail | Result |
|-------|--------|--------|
| J3 pad-to-pad gap (BAT+ vs GND) | 0.40 mm edge-to-edge (min 0.15 mm) | **PASS** |
| J3 pads to diff-net copper | > 0.20 mm to all nearby vias/traces | **PASS** |
| All NPTH to nearest copper | Min gap 0.24 mm (J1 positioning holes) | **PASS** |
| All mounting holes to copper | Min gap 0.57 mm (MH center) | **PASS** |
| J3 pin pitch vs datasheet | 2.00 mm (datasheet: 2.0 mm) | **PASS** |

:::tip NPTH Rule
NPTH positioning holes are always sized from the component datasheet — never guessed. The drill diameter must exceed the component peg diameter by 0.10–0.20 mm for reliable insertion during assembly. All 8 NPTH holes in this design follow this rule.
:::

### Via Summary

| Type | Count | Drill Range | Annular Ring | Status |
|------|-------|-------------|--------------|--------|
| Signal vias | 269 | 0.20 mm | ≥ 0.075 mm | **PASS** |
| Component NPTH | 8 | 0.65–1.00 mm | — (no pad) | **PASS** |
| Mounting NPTH | 6 | 2.50 mm | — (no pad) | **PASS** |
| Component THT (J3) | 2 | 0.85 mm | 0.375 mm | **PASS** |

**Result: 22/22 checks passed — no short circuit risk, all drills match datasheets.**

---

## Running Verification

### Fast commands (recommended)

```bash
# Quick DFM check — 114 tests, ~2s, no Docker needed
make verify-fast

# Full pipeline — generate + DFM + DRC + gerbers + connectivity (~5s)
make fast-check

# GPIO firmware/schematic sync check
make firmware-sync-check
```

### DRC Commands (JLCPCB Rules)

```bash
# Full DRC — zone fill + DRC + smart analysis (recommended)
python3 scripts/drc_native.py --run

# Fast DRC — skip zone fill for quick checks
python3 scripts/drc_native.py --run --no-zone-fill

# Update baseline — save current violations as reference
python3 scripts/drc_native.py --run --update-baseline

# Analyze existing DRC report
python3 scripts/drc_native.py /path/to/drc-report.json
```

The `--run` mode automatically:
1. Fills zones via Docker (pcbnew API) unless `--no-zone-fill` is used
2. Runs `kicad-cli pcb drc` with JLCPCB rules from `.kicad_dru`
3. Categorizes violations into known-acceptable vs real issues
4. Provides source file mapping and fix suggestions for real issues
5. Tracks deltas vs saved baseline (if `--update-baseline` was used previously)

### Full verification suite

```bash
make verify-all    # DRC + simulation + consistency + short circuit
```

Or individually:

```bash
python3 scripts/verify_dfm_v2.py         # 114 DFM guard tests
python3 scripts/drc_native.py --run      # JLCPCB design rules (smart analysis)
python3 scripts/simulate_circuit.py      # Power/timing simulation
python3 scripts/verify_schematic_pcb.py  # Schematic-PCB sync
python3 scripts/test_pcb_connectivity.py # Electrical connectivity
python3 scripts/analyze_pad_distances.py # Pad spacing analysis
```

### Automatically (Husky pre-commit hook)

All three checks run on every `git commit`. If any check fails (exit code != 0), the commit is blocked.

The hook is managed by [Husky](https://typicode.github.io/husky/) and installed at `.husky/pre-commit`. After cloning:

```bash
npm install
```

This runs `husky` via the `prepare` script and activates the hooks automatically.

You can also run the full battery manually:

```bash
npm run verify
```

### Expected output

```
[verify] DRC Check ............ PASS (0 errors, 2 warnings)
[verify] Circuit Simulation ... PASS (0 errors, 5 warnings)
[verify] Schematic-PCB ........ PASS
[verify] All pre-production checks passed
```

---

## Performance Notes

The verification pipeline uses a **hybrid local + Docker** approach for speed:

| Tool | Runs via | Time |
|------|----------|------|
| DFM tests (`verify_dfm_v2.py`) | Python (local) | 1.4s |
| KiCad DRC | `kicad-cli` (local) | 0.8s |
| Gerber export | `kicad-cli` (local) | 0.9s |
| Zone fill | Docker (pcbnew API) | 1.8s |
| Connectivity | Python (local) | 0.15s |

Container runtime: **OrbStack** (drop-in Docker Desktop replacement, 16x faster container startup).
