---
name: design-intent
model: claude-opus-4-7
description: Design intent adversary — cross-checks GPIO, nets, power chains, signal paths across firmware/schematic/PCB/datasheet sources to find lost connections and inconsistencies
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# Design Intent Adversary

Acts as a "devil's advocate" — maps every GPIO, device, net, and connection, then hunts for inconsistencies, orphan nets, missing signal paths, and logic errors across ALL design sources.

## What it checks (18 tests, 300+ checks)

| Test | Category | What it catches |
|------|----------|-----------------|
| T1 | GPIO consistency | `board_config.h` vs `config.py` GPIO mismatch |
| T2 | GPIO consistency | `config.py` vs `datasheet_specs.py` U1 pin mapping |
| T3 | Duplicate GPIO | Same GPIO# assigned to multiple signals |
| T4 | Signal endpoints | GPIO signal doesn't reach its destination component |
| T5 | Orphan nets | Nets connected to 0-1 pads (lost connections) |
| T6 | Power chain | VBUS→IP5306→+5V→AMS1117→+3V3→all VDD pins |
| T7 | GND completeness | Component missing ground connection |
| T8 | Button circuits | Button GPIO missing switch or ESP32 connection |
| T9 | Pin capability | GPIO used for unsupported function (reserved for PSRAM, etc.) |
| T10 | Strapping pins | GPIO0/3/45/46 boot conflict risk |
| T11 | Unused GPIOs | Available pins not in any signal group |
| T12 | Cross-component | Expected component-to-component nets actually connected |
| T13 | Display chain | LCD_D0-D7 + control: ESP32 ↔ FPC connector |
| T14 | Audio chain | I2S + speaker: ESP32 ↔ PAM8403 ↔ SPK |
| T15 | SD card chain | SPI signals: ESP32 ↔ SD slot |
| T16 | USB chain | Full path: USB-C → ESD → series R → ESP32 |
| T17 | Button pull-ups | Discrete pull-up resistor presence |
| T18 | Net naming | Typos, case conflicts, suspicious auto-names |

## Sources cross-checked

1. `software/main/board_config.h` — firmware GPIO definitions
2. `scripts/generate_schematics/config.py` — schematic generator GPIO mapping
3. `hardware/datasheet_specs.py` — pin-to-net specs from datasheets
4. PCB cache (parsed from `.kicad_pcb`) — actual routed nets/pads
5. BOM/CPL — manufacturing files

## Usage

### Quick run (all tests)
```bash
python3 scripts/verify_design_intent.py
```

### Verbose (show INFO for known patterns)
```bash
python3 scripts/verify_design_intent.py --verbose
```

### Single test
```bash
python3 scripts/verify_design_intent.py --test T5    # orphan nets only
python3 scripts/verify_design_intent.py --test T6    # power chain only
python3 scripts/verify_design_intent.py --test T16   # USB chain only
```

## Integration with /pcb-review

Run this as Step 1f after existing verification steps:

```bash
python3 scripts/verify_design_intent.py
```

Any FAIL indicates a real design inconsistency that must be investigated. WARNs are known patterns (strapping pins, direct-routed nets) that should be verified visually.

## When to run

- After changing GPIO assignments in `board_config.h` or `config.py`
- After modifying `datasheet_specs.py` pin mappings
- After PCB regeneration (`/generate`)
- Before manufacturing release (`/release`)
- As part of `/pcb-review` comprehensive review

## Key files

- `scripts/verify_design_intent.py` — the adversary script (18 tests)
- `software/main/board_config.h` — firmware GPIO source of truth
- `scripts/generate_schematics/config.py` — schematic GPIO source of truth
- `hardware/datasheet_specs.py` — datasheet pin-to-net source of truth
- `scripts/pcb_cache.py` — PCB data parser (shared cache infrastructure)
