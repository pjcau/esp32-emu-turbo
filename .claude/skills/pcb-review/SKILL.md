---
name: pcb-review
model: claude-opus-5
description: Comprehensive PCB design review — 8 domains, 100-point scoring, JLCPCB DFM rules, datasheet pin verification
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# PCB Design Review

Comprehensive design review of the PCB layout, analyzing 8 key domains like a senior PCB engineer would. Produces a scored report with actionable improvement suggestions.

## Sources

- JLCPCB manufacturing rules: `.claude/skills/pcb-review/references/review-checklist.md`
- JLCPCB blog best practices: trace angles, 3W rule, decoupling, impedance control, stackup
- Component datasheets: `hardware/datasheets/`
- DFM reference: `.claude/skills/dfm-fix/dfm-reference.md`

## Steps

### 1. Run automated checks
```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/pcb_review.py
python3 scripts/verify_dfm_v2.py
python3 scripts/verify_polarity.py
python3 scripts/verify_dfa.py
python3 scripts/validate_jlcpcb.py
python3 scripts/verify_bom_cpl_pcb.py
python3 scripts/verify_jlcpcb_capabilities.py
python3 scripts/verify_stencil_aperture.py
python3 scripts/verify_drill_standards.py
```

What it catches: `references/script-notes.md` → "1. Run automated checks".

### 1b. Run extended verification suite (17 gap-coverage tests)
```bash
# High-risk (5 tests)
python3 scripts/verify_antenna_keepout.py
python3 scripts/verify_stackup.py
python3 scripts/verify_net_class_widths.py
python3 scripts/verify_bom_values.py
python3 scripts/verify_power_paths.py

# Medium-risk (7 tests)
python3 scripts/verify_copper_balance.py
python3 scripts/verify_decoupling_paths.py
python3 scripts/verify_usb_impedance.py
python3 scripts/verify_via_in_pad.py
python3 scripts/verify_thermal_relief.py
python3 scripts/verify_ground_loops.py
python3 scripts/verify_test_points.py
```

What it catches: `references/script-notes.md` → "1b. Run extended verification suite (17 gap-coverage tests)".

### 1c. Run datasheet verification (electrical + physical)
```bash
python3 scripts/verify_datasheet_nets.py
python3 scripts/verify_datasheet.py
```

What it catches: `references/script-notes.md` → "1c. Run datasheet verification (electrical + physical)".

### 1f. Run design intent adversary (cross-source consistency)
```bash
python3 scripts/verify_design_intent.py
```

What it catches: `references/script-notes.md` → "1f. Run design intent adversary (cross-source consistency)".

### 1g. Run DRC Audit (electrical connectivity)
```bash
kicad-cli pcb drc \
  --output /tmp/drc_audit_report.json \
  --format json \
  --severity-all --units mm --all-track-errors \
  hardware/kicad/esp32-emu-turbo.kicad_pcb
```

What it catches: `references/script-notes.md` → "1g. Run DRC Audit (electrical connectivity)".

### 1d. Run ERC (Electrical Rules Check)
```bash
python3 scripts/erc_check.py --run
```

What it catches: `references/script-notes.md` → "1d. Run ERC (Electrical Rules Check)".

### 1e. Run SPICE power supply simulation
```bash
python3 scripts/spice_power_check.py
```

What it catches: `references/script-notes.md` → "1e. Run SPICE power supply simulation".

### 1j. Run electrical review scripts
```bash
# Strapping pin verification (12 tests)
python3 scripts/verify_strapping_pins.py

# Decoupling capacitor adequacy (23 tests)
python3 scripts/verify_decoupling_adequacy.py

# Power sequencing verification (29 tests)
python3 scripts/verify_power_sequence.py
```

What it catches: `references/script-notes.md` → "1j. Run electrical review scripts".

### 1k. Run connectivity and signal chain verification
```bash
# Component connectivity — catches phantom BOM components (2 tests)
python3 scripts/verify_component_connectivity.py

# Signal chain completeness — catches broken copper paths (57 tests)
python3 scripts/verify_signal_chain_complete.py
```

What it catches: `references/script-notes.md` → "1k. Run connectivity and signal chain verification".

### 1l. Run net classification and board config validation

```bash
# Net function classifier — validates GPIO-to-net name consistency
python3 scripts/net_classifier.py --validate

# Board config drift detection — config.py vs board_config.h
python3 scripts/generate_board_config.py --check
```

| Script | What it catches |
|--------|-----------------|
| `net_classifier.py --validate` | Net named "I2S_BCLK" on non-I2S GPIO, USB pins misused |
| `generate_board_config.py --check` | Firmware board_config.h drifted from config.py master |

### 1m. Run schematic-to-PCB netlist diff
```bash
python3 scripts/verify_netlist_diff.py
```

What it catches: `references/script-notes.md` → "1m. Run schematic-to-PCB netlist diff".

### 1m2. Run schematic↔PCB/datasheet_specs sync guard (R4 class)
```bash
python3 scripts/verify_schematic_pcb_sync.py
```

What it catches: `references/script-notes.md` → "1m2. Run schematic↔PCB/datasheet_specs sync guard (R4 class)".

### 1n. Generate hardware test firmware (Phase 3 prototype)
```bash
python3 scripts/generate_hw_tests.py
```

What it catches: `references/script-notes.md` → "1n. Generate hardware test firmware (Phase 3 prototype)".

### 2. Manual review against checklist

Read `references/review-checklist.md` and verify each domain:

| # | Domain (points) | Key checks |
|---|-----------------|------------|
| 1 | Power Integrity (15) | Trace widths for current, decoupling caps near ICs, GND/power planes |
| 2 | Signal Integrity (15) | Bus matching, USB diff pair, 3W rule, 45° traces, impedance |
| 3 | Thermal (10) | Thermal vias, EP pad connections, copper area, IC spacing |
| 4 | JLCPCB DFM (20) | Trace/pad/via spacing, mask bridge, copper-to-edge, fiducials, `validate_jlcpcb.py` |
| 5 | EMI/EMC (10) | GND plane continuity, return paths, decoupling strategy |
| 6 | Component Polarity (15) | Pin-1 vs datasheet, LED polarity, CPL rotation, BOM-CPL match |
| 7 | Mechanical (10) | Mounting holes, connector access, NPTH sizes, board outline |
| 8 | Documentation (5) | LCSC parts, gerbers, silkscreen, assembly variants |

### 3. Datasheet physical verification

```bash
python3 scripts/verify_datasheet.py
```

Automated cross-check of PCB vs datasheets (29 tests):
- Pin count per component (ICs, connectors, passives, switches)
- Pad pitch matches datasheet (0.5mm FPC, 1.27mm SOIC, 2.0mm JST, etc.)
- Pad span / body dimensions (catches wrong package, e.g. SOP-16 vs SOIC-16W)
- NPTH positioning hole count and drill size
- THT drill sizes (JST, USB shield tabs)
- Datasheet PDF presence in `hardware/datasheets/`

### 3b. Manual datasheet verification (Domain 6)

For each IC/connector, read the datasheet from `hardware/datasheets/` and verify:
- Pin 1 location matches footprint orientation
- Net assignments match datasheet pinout
- CPL rotation produces correct JLCPCB placement
- Passive component values match typical application circuit

### 4. Current capacity check (Domain 1)

Verify power trace widths against current requirements:
- VBUS/BAT+: up to 2.1A (IP5306 charger) → need ≥0.76mm (30mil)
- +5V: up to 1A → need ≥0.25mm (10mil)
- +3V3: up to 0.5A → need ≥0.13mm (5mil)
- LX (inductor): up to 2.1A pulsed → need ≥0.76mm (30mil)

### 1h. Run trace-through-pad overlap check

```bash
python3 scripts/verify_trace_through_pad.py
```

### 1h2. Run per-net copper connectivity check (R5-CRIT gate)
```bash
python3 scripts/verify_net_connectivity.py
```

What it catches: `references/script-notes.md` → "1h2. Run per-net copper connectivity check (R5-CRIT gate)".

### 1i. System health summary

What it catches: `references/script-notes.md` → "1i. System health summary".

### 5. Generate report

Format findings as:

```
## PCB Design Review Report

| # | Domain | Score | Key Finding |
|---|--------|-------|-------------|
| 1 | Power Integrity | ?/15 | ... |
| 2 | Signal Integrity | ?/15 | ... |
| 3 | Thermal | ?/10 | ... |
| 4 | JLCPCB DFM | ?/20 | ... |
| 5 | EMI/EMC | ?/10 | ... |
| 6 | Component Polarity | ?/15 | ... |
| 7 | Mechanical | ?/10 | ... |
| 8 | Documentation | ?/5 | ... |
| **TOTAL** | | **?/100** | ... |

### Top 5 Priority Fixes
1. ...
2. ...
```

### 6. Fix and re-verify

After making changes:
```bash
python3 -m scripts.generate_pcb hardware/kicad
python3 scripts/verify_dfm_v2.py
python3 scripts/verify_polarity.py
python3 scripts/validate_jlcpcb.py
```

## Key Files

Per-script index with gate/target and token cost: `docs/REPO_MAP.md`
(generated; `make repo-map` refreshes it). The curated review data
lives in `references/review-checklist.md` and
`references/script-notes.md`.

