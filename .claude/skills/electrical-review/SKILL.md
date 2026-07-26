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

Work through `references/checklist.md` one domain at a time
(A pre-power, B power-up, C boot, D runtime): for each row, read the
named sources, check the PCB cache or routing, give a VERDICT
(OK / CONCERN / RISK). The rows carry as-built warnings — A2 (SW_PWR
not in series), B3 (EN has no RC), D2 (backlight, open R25-HIGH-1) —
do not re-raise those as new findings.

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
