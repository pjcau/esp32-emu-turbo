---
name: electrical-review
model: claude-opus-5
description: Comprehensive electrical verification — strapping pins, decoupling adequacy, power sequencing, SPICE simulation, and 30-question manual checklist
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# Electrical Review

Covers the gap between DFM/DRC (manufacturing checks) and actual electrical functionality. Verifies that the board will boot, power up correctly, and operate reliably.

## Steps

### 1. Run automated electrical checks

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo

# 1a. Strapping pin verification (12 tests)
python3 scripts/verify_strapping_pins.py

# 1b. Decoupling capacitor adequacy (23 tests)
python3 scripts/verify_decoupling_adequacy.py

# 1c. Power sequencing verification (29 tests)
python3 scripts/verify_power_sequence.py

# 1d. SPICE power supply simulation (requires ngspice)
python3 scripts/spice_power_check.py
```

| Script | Tests | What it catches |
|--------|-------|-----------------|
| `verify_strapping_pins.py` | 12 | Wrong boot state, GPIO45 VDD_SPI conflict. **Its "EN RC delay" block is not evidence** — it matches a comment string in the schematic and computes τ from a WROOM-1 internal pull-up that does not exist (see B3) |
| `verify_decoupling_adequacy.py` | 23 | Insufficient capacitance per IC datasheet, missing HF bypass |
| `verify_power_sequence.py` | 29 | Power chain topology, upstream/downstream ordering, GND continuity |
| `spice_power_check.py` | — | Ripple on +5V/+3V3 rails, transient response, decoupling effectiveness |
| `verify_component_connectivity.py` | 2 | BOM components with zero electrical connections (phantom parts) |
| `verify_signal_chain_complete.py` | 57 | Nets that only connect to one endpoint (broken signal chains) |

```bash
# 1e. Component connectivity + signal chain completeness
python3 scripts/verify_component_connectivity.py
python3 scripts/verify_signal_chain_complete.py
```

### 2. Manual 30-question electrical review

Walk through each question. For each, read the relevant source files, check the PCB cache or routing.py, and give a VERDICT: OK, CONCERN, or RISK.

#### A. Pre-Power (4 questions)

| # | Question | What to check |
|---|----------|---------------|
| A1 | Are all power rails isolated from each other (no shorts)? | Run `python3 scripts/verify_power_paths.py`, check net isolation |
| A2 | Is the power switch between battery and IP5306? | **No, and this is a known as-built limitation — do not re-raise it as a new bug.** Only SW_PWR's common pin (pad 2) is routed, as a stub tap on BAT+ at (39.25, 70.3); throw pins 1/3 carry no net. J3 → Q1 → BAT+ → IP5306 pin 6 is continuous copper that never passes through the switch, so **the switch cannot power the board down**; true isolation = unplug J3. Respin: route the battery through switch pins 1–2. See RESPIN in `docs/known-issues.md` |
| A3 | Are USB CC1/CC2 pull-downs correct (5.1k to GND)? | Check R1, R2 values (5.1k) and nets (USB_CC1/CC2 to GND) |
| A4 | Is reverse polarity protection adequate? | Check BAT54C diode D1, JST connector polarity |

#### B. Power-Up Sequence (5 questions)

| # | Question | What to check |
|---|----------|---------------|
| B1 | Does IP5306 boost start cleanly from 3.7V battery? | Check C17 (VIN), L1 (inductor), C19/C27 (VOUT) values |
| B2 | Does the U3 buck regulate correctly? | **U3 is a SY8089AAAC 2A synchronous buck (SOT-23-5, C78988) — not an LDO, so there is no dropout budget.** Vout = 0.6 × (1 + R25/R26) = 0.6 × (1 + 100k/22k) = **3.327 V** (measured 3.327 V, vbench Phase 1). EN (pin 1) is hard-tied to +5V; abs-max is Vin + 0.6 V, so the tie is in spec. Check the divider R25=100k / R26=22k and the C29 feed-forward |
| B3 | Does EN have an RC delay? | **No — and that is the as-built answer, not a finding to re-raise.** The board has no pull-up and no cap on EN: `R3` is absent from the BOM and the PCB, and `C3` is a plain +3V3 decoupling cap (twin of C4). `EN` carries exactly two pads, `U1.3` and `SW_RST` pad 1. The WROOM-1 does **not** integrate an EN pull-up — that claim was retired from `mcu.py` in `74c196e`. Datasheet p.28 requires the RC; this is a RESPIN item (10 kΩ +3V3→EN, 100 nF EN→GND). Margin defect, not a dead board. See RESPIN in `docs/known-issues.md` |
| B4 | Is IP5306 KEY pin properly configured? | R16=100k pull-down, check KEY net routing |
| B5 | Can charge-and-play work? (USB + battery simultaneously) | IP5306 supports charge-and-play natively |

#### C. ESP32 Boot (6 questions)

| # | Question | What to check |
|---|----------|---------------|
| C1 | Is GPIO0 HIGH at boot? (normal boot vs download mode) | BTN_SELECT pull-up R9=10k to +3V3, button not pressed = HIGH |
| C2 | Is GPIO45 LOW at boot? (VDD_SPI=3.3V for PSRAM) | R14 DNP + i=10 skip in routing.py, no external pull-up |
| C3 | Is GPIO46 LOW at boot? (ROM log output) | LCD_WR has internal pull-down, no external pull-up |
| C4 | Does GPIO3 state matter? | Any state OK (USB JTAG select), pull-up is acceptable |
| C5 | Is PSRAM accessible at boot? (Octal SPI, needs VDD_SPI=3.3V) | Depends on C2 (GPIO45=LOW), verified by strapping check |
| C6 | Is flash accessible? (16MB SPI flash on module) | Module has internal flash connection, no external routing needed |

#### D. Runtime (9 questions)

| # | Question | What to check |
|---|----------|---------------|
| D1 | Can the +3V3 rail source enough current for all peripherals? | Total: ~350mA max (WiFi burst); U3 (SY8089) is rated 2A |
| D2 | Is display bus functional? (8-bit 8080 parallel) | Check LCD_D0-D7, CS, RST, DC, WR traces. **`LCD_RD` and `LCD_BL` are not nets** — ids 18/19 are retired gaps in `primitives.NET_LIST`. FPC pin 12 (RD, read strobe disabled — write-only) and pin 33 (LED-A backlight) are hard-tied to +3V3, so their pads live on the +3V3 net. **The backlight has no current-limiting element at all, and that is OPEN finding R25-HIGH-1** — `J4` pad 8 (panel pin 33, LED-A) sits directly on +3V3 while the cathodes (pads 7/6/5) are GND, so 8 chip white LEDs (Vf 2.9–3.3 V) sit straight across the 3.3 V rail. `components.md` quotes the panel datasheet as "+3V3 (**via resistor**, always-on)"; the resistor was documented and never placed. Do not accept `routing.py`'s "panels have internal limiting" as settled — it is an unverified justification comment, which is the exact pattern that produced R25-CRIT-1 |
| D3 | Is SD card SPI functional? | Check SD_MOSI, SD_MISO, SD_CLK, SD_CS routing to TF-01A |
| D4 | Is I2S audio path clean? | Check I2S_BCLK, I2S_LRCK, I2S_DOUT to PAM8403; DC-blocking cap C22 |
| D5 | Are all buttons readable? | 12 buttons + menu combo via BAT54C D1 |
| D6 | Is USB data path functional? | D+/D- through USBLC6-2SC6 (U4), 22ohm series (R22/R23), to ESP32 |
| D7 | Is speaker output adequate? | PAM8403 3W per channel, SPK+/SPK- to 28mm speaker |
| D8 | Are LEDs functional? | LED1/LED2 through R17/R18 (1k), connected to IP5306 LED outputs |
| D9 | Is thermal dissipation adequate? | **The LDO thermal problem is gone** — a switching buck at ~90% efficiency dissipates ~0.04 W at 350 mA where the AMS1117 burned 1.7 V × I as heat (0.85 W at 500 mA). What matters instead is the 1 MHz hot loop: C1 (C_IN) tight to U3 IN/GND, C30 (C_OUT) tight to L2's output pad, LX node kept small. Checked by `verify_dfm_v2.test_c1_c2_spacing` |

#### E. Edge Cases (6 questions)

| # | Question | What to check |
|---|----------|---------------|
| E1 | What happens if USB is plugged in while battery is low? | IP5306 handles charge-and-play, VBUS powers via VIN |
| E2 | What happens if battery is removed while USB powers the board? | IP5306 VOUT continues from VBUS, check C19 bulk cap for transient |
| E3 | Can EMI from boost converter affect ESP32? | Check L1-to-ESP32 distance, GND plane shielding on In1.Cu |
| E4 | Is antenna keepout zone clear? | Run verify_antenna_keepout.py, check no copper within 5mm |
| E5 | Can button bounce cause false triggers? | 100nF debounce caps + firmware debounce (typically 20ms) |
| E6 | Is ESD protection adequate on exposed connectors? | USB: USBLC6-2SC6 TVS, SD card: internal to TF-01A module |

### 3. Generate verdict report

```
## Electrical Review Report

**Board**: ESP32 Emu Turbo v3.x
**Date**: [date]

### Automated Checks
| Script | Result | Tests |
|--------|--------|-------|
| verify_strapping_pins.py | PASS/FAIL | X/Y |
| verify_decoupling_adequacy.py | PASS/FAIL | X/Y |
| verify_power_sequence.py | PASS/FAIL | X/Y |
| spice_power_check.py | PASS/FAIL | X/Y |

### Manual Review
| Section | OK | CONCERN | RISK |
|---------|----|---------|----- |
| A. Pre-Power (4) | X | X | X |
| B. Power-Up (5) | X | X | X |
| C. ESP32 Boot (6) | X | X | X |
| D. Runtime (9) | X | X | X |
| E. Edge Cases (6) | X | X | X |

### Critical Issues (RISK)
[List any RISK verdicts with evidence]

### Concerns (CONCERN)
[List any CONCERN verdicts with evidence]

### Overall Verdict: PASS / CONDITIONAL PASS / FAIL
```

## Key Files

| File | Purpose |
|------|---------|
| `scripts/verify_strapping_pins.py` | ESP32-S3 boot pin configuration (12 tests) |
| `scripts/verify_decoupling_adequacy.py` | IC decoupling per datasheet (25 tests) |
| `scripts/verify_power_sequence.py` | Power chain and sequencing (26 tests) |
| `scripts/spice_power_check.py` | SPICE simulation of power rails |
| `scripts/generate_schematics/config.py` | GPIO mapping (source of truth) |
| `scripts/generate_pcb/routing.py` | PULL_UP_REFS, NET_ID, pad nets |
| `software/main/board_config.h` | Firmware pin definitions |
| `hardware/datasheet_specs.py` | Component pin-to-net specs |
