# Datasheet Net Verification

Verifies that every PCB pad-to-net assignment matches the manufacturer datasheet pin specifications. This is the automated guard against wiring errors like unconnected VBUS, wrong pin assignments, or missing GND connections.

## When to Use

- After any change to `board.py`, `routing.py`, `footprints.py`, or `jlcpcb_export.py`
- After modifying GPIO mapping in `config.py`
- Before manufacturing release (part of full verification pipeline)
- When adding a new component to the design
- After fixing any net connectivity issue

## Quick Run

```bash
python3 scripts/verify_datasheet_nets.py
```

## Options

```bash
# Verbose mode -- show INFO lines for intentionally unconnected pins
python3 scripts/verify_datasheet_nets.py --verbose

# Verify a single component
python3 scripts/verify_datasheet_nets.py --component J1
python3 scripts/verify_datasheet_nets.py -c U5
```

## What It Checks

For each of the 30 defined components (246 total pin checks):

1. **Net assignment** -- pad has the correct net name per datasheet
2. **Pad type** -- SMD vs THT matches the component package
3. **Drill size** -- THT pads meet minimum drill requirements
4. **Signal pair validation** -- for tact switches, verifies both signal and GND appear

## Output Codes

| Code | Meaning |
|------|---------|
| PASS | Pad has correct net |
| FAIL | Pad has wrong net or is unconnected when it should be connected |
| WARN | Net is correct but pad type or drill size is wrong |
| INFO | Pad is intentionally unconnected (documented in spec) |

## Architecture

### Spec File: `hardware/datasheet_specs.py`

The single source of truth for pin-to-net mappings. Each component defines:
- Reference designator and LCSC part number
- Datasheet filename and page reference
- Pin-by-pin expected net (exact match, any-of, or unconnected)
- Pin function description
- Required pad type and minimum drill size

### Verification Script: `scripts/verify_datasheet_nets.py`

Loads the PCB cache and compares actual pad-net assignments against the spec file. Auto-rebuilds cache if stale.

## Adding a New Component

1. Read the component's datasheet from `hardware/datasheets/`
2. Add entry to `COMPONENT_SPECS` dict in `hardware/datasheet_specs.py`
3. Run `python3 scripts/verify_datasheet_nets.py -c NEW_REF` to verify
4. Run full suite to ensure no regressions

## Key Files

| File | Purpose |
|------|---------|
| `hardware/datasheet_specs.py` | Pin-to-net specifications (source of truth) |
| `scripts/verify_datasheet_nets.py` | Verification script |
| `hardware/datasheets/` | Manufacturer PDF datasheets |
| `hardware/kicad/.pcb_cache.json` | Parsed PCB data (auto-generated) |

## Components Covered (30)

| Ref | Component | Pins |
|-----|-----------|------|
| J1 | USB-C 16-Pin Connector | 16 signal + shield |
| J3 | JST PH 2-Pin Battery | 2 |
| J4 | FPC 40-Pin Display | 42 (40 + 2 shell) |
| U1 | ESP32-S3-WROOM-1-N16R8 | 41 |
| U2 | IP5306 Power Bank SoC | 9 (8 + EP) |
| U3 | AMS1117-3.3 LDO | 4 (3 + tab) |
| U5 | PAM8403 Audio Amp | 16 |
| U6 | TF-01A MicroSD Slot | 13 + NPTH |
| SW1-SW12 | Tact Switches (buttons) | 4 each |
| SW13 | Menu Button (placeholder) | 4 |
| SW_PWR | Slide Switch | 7 |
| SW_RST | Reset Switch | 4 |
| SW_BOOT | Boot/Select Switch | 4 |
| R1, R2 | CC Pull-Down Resistors | 2 each |
| L1 | Power Inductor | 2 |
| LED1, LED2 | Status LEDs | 2 each |
| SPK1 | Speaker | 2 |
