---
name: pcb-review
model: claude-opus-4-7
description: Comprehensive PCB design review — 8 domains, 100-point scoring, JLCPCB DFM rules, datasheet pin verification
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob, Agent
---

# PCB Design Review

Comprehensive design review of the PCB layout, analyzing 8 key domains like a senior PCB engineer would. Produces a scored report with actionable improvement suggestions.

## Sources

- JLCPCB manufacturing rules: `.claude/skills/pcb-review/review-checklist.md`
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

**BOM/CPL/PCB cross-check** (`verify_bom_cpl_pcb.py`, 13 checks):
Verifies all designators match across BOM, CPL, and PCB. Checks footprint names
are JLCPCB-compatible, CPL rotations valid, positions match (with known correction
allowances), all LCSC part numbers present, and schematic field completeness.

**JLCPCB capabilities** (`verify_jlcpcb_capabilities.py`, 12 checks):
Two-tier cross-check against JLCPCB published manufacturing limits. FAIL = board
rejected, WARN = below recommended. Covers trace, via, THT, clearance rules.

**Stencil aperture** (`verify_stencil_aperture.py`, 6 checks):
IPC-7525 area ratio + aspect ratio for multiple stencil thicknesses (3-5mil),
paste powder type recommendation, fine-pitch component detail report.

**Drill standards** (`verify_drill_standards.py`, 6 checks):
ISO metric + JLCPCB common drill mapping, drill inventory count, IPC-2222
drill-to-pad ratio, via vs PTH appropriateness.

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

| Script | Checks | What it catches |
|--------|--------|-----------------|
| `verify_antenna_keepout.py` | 5 | Copper/traces in ESP32 antenna zone (kills WiFi/BLE) |
| `verify_stackup.py` | 5 | Wrong nets on inner plane layers |
| `verify_net_class_widths.py` | 5 | Power traces too narrow (fuse risk) |
| `verify_bom_values.py` | 75 | Schematic value vs BOM mismatch (wrong part assembled) |
| `verify_power_paths.py` | 19 | Missing copper path from source to IC VDD pin |
| `verify_copper_balance.py` | 3 | Layer imbalance causing PCB warping |
| `verify_decoupling_paths.py` | 11 | Cap too far or poorly routed to IC |
| `verify_usb_impedance.py` | 4 | USB trace geometry wrong for 90ohm differential |
| `verify_via_in_pad.py` | 3 | Vias inside SMD pads (solder wicking) |
| `verify_thermal_relief.py` | 4 | Missing thermal relief on zone connections |
| `verify_ground_loops.py` | 3 | Audio-digital ground coupling |
| `verify_test_points.py` | 18 | Missing debug probe points |
| `verify_esd_protection.py` | 6 | Missing TVS/series resistors on USB |
| `verify_strapping_pins.py` | 6 | ESP32 boot pin conflicts |
| `verify_usb_return_path.py` | 3 | GND via density near USB traces |
| `verify_sd_interface.py` | 7 | SD card SPI completeness + card detect |
| `verify_power_resonance.py` | 4 | Power plane LC resonance frequency |

### 1c. Run datasheet verification (electrical + physical)

```bash
python3 scripts/verify_datasheet_nets.py
python3 scripts/verify_datasheet.py
```

**Datasheet net verification** (`verify_datasheet_nets.py`, 246 checks):
Compares EVERY pad of EVERY component against the expected net from the datasheet.
Uses `hardware/datasheet_specs.py` as single source of truth (pin→net mapping).
- Catches: unconnected pads that should be connected, wrong net on a pad
- Example: USB-C pad 1 should be GND, shield pads should be GND, VBUS on all 3 pins

**Datasheet physical verification** (`verify_datasheet.py`, 29 tests):
Compares PCB footprint dimensions against datasheet mechanical drawings.
- Pin count per component (ICs, connectors, passives, switches)
- Pad pitch (0.5mm FPC, 1.27mm SOIC, 2.0mm JST, etc.)
- Pad span / body dimensions (catches wrong package, e.g. SOP-16 vs SOIC-16W)
- NPTH positioning hole count and drill sizes
- THT drill sizes (JST, USB shield tabs)
- Datasheet PDF presence in `hardware/datasheets/`

### 1f. Run design intent adversary (cross-source consistency)

```bash
python3 scripts/verify_design_intent.py
```

**Design intent verification** (`verify_design_intent.py`, 362 checks):
Cross-checks GPIO assignments, net connections, and signal paths across ALL sources:
firmware (`board_config.h`), schematic config (`config.py`), datasheet specs, and actual PCB layout.

| Test | What it catches |
|------|-----------------|
| T1-T3 | GPIO mismatch across sources, duplicate GPIO assignments |
| T4-T5 | Missing signal endpoints, orphan nets (0-1 pad connections) |
| T6-T7 | Broken power chain (VBUS→+5V→+3V3), missing GND connections |
| T8 | Button circuit incomplete (no switch or no MCU connection) |
| T9-T11 | Reserved/invalid GPIO usage, strapping pin conflicts |
| T12-T16 | Signal chain breaks: display, audio, SD, USB paths |
| T17-T18 | Missing pull-ups, net naming issues |
| T19 | Pin electrical type conflicts (multi-output on same net) |
| T20 | ESP32-S3 IO MUX validation (GPIO range, PSRAM/flash reserved) |
| T21 | I2C bus completeness (pull-ups, address conflicts) |
| T22 | Power rail decoupling completeness (8 caps on correct rails) |

### 1g. Run DRC Audit (electrical connectivity)

```bash
kicad-cli pcb drc \
  --output /tmp/drc_audit_report.json \
  --format json \
  --severity-all --units mm --all-track-errors \
  hardware/kicad/esp32-emu-turbo.kicad_pcb
```

**CRITICAL step** — catches issues that ALL custom scripts miss:
- `shorting_items`: traces touching pads with wrong/no net (board malfunction)
- `unconnected_items`: broken signal paths (components not connected)
- `via_dangling`: orphan vias (wasted manufacturing, DFM warnings)
- `clearance`: real spacing violations below JLCPCB minimums

Our `verify_dfm_v2.py` runs KiCad DRC but only checks 3 of 9 violation types.
Test 43 (trace-pad clearance) auto-skips when pads lack net assignments.
This step fills that gap. See `.claude/skills/drc-audit/SKILL.md` for full methodology.

Classify `shorting_items` as:
- **Real shorts** (`"nets X and Y)"`) — CRITICAL, board will fail
- **Pad-net bugs** (`"nets X and )"`) — generator fix needed in `_init_pads()`

### 1d. Run ERC (Electrical Rules Check)

```bash
python3 scripts/erc_check.py --run
```

Runs KiCad native ERC on the hierarchical schematic. Categorizes 730+ violations:
- **Generator artifacts** (suppressed): grid alignment, wiring stubs, library symbols — inherent to Python-generated schematics
- **Real issues**: pin_not_connected, power_pin_not_driven, pin_to_pin conflicts
- **Critical**: pin_to_pin (output↔output) must be zero for production

### 1e. Run SPICE power supply simulation

```bash
python3 scripts/spice_power_check.py
```

Requires: `ngspice` (`brew install ngspice`)

Simulates IP5306 boost → AMS1117 LDO → ESP32 load:
- +5V rail ripple at 500kHz switching (must be < 150mV)
- +3V3 rail ripple under load steps (must be < 50mV)
- Decoupling cap effectiveness (C17, C27, C1, C19)
- ESP32 WiFi burst response (200mA → 350mA in 10µs)

### 1j. Run electrical review scripts

```bash
# Strapping pin verification (12 tests)
python3 scripts/verify_strapping_pins.py

# Decoupling capacitor adequacy (25 tests)
python3 scripts/verify_decoupling_adequacy.py

# Power sequencing verification (26 tests)
python3 scripts/verify_power_sequence.py
```

| Script | Tests | What it catches |
|--------|-------|-----------------|
| `verify_strapping_pins.py` | 12 | Wrong boot state, GPIO45 VDD_SPI conflict, EN RC timing, pull-up skip |
| `verify_decoupling_adequacy.py` | 25 | Insufficient capacitance per IC datasheet, missing HF bypass |
| `verify_power_sequence.py` | 26 | Power chain topology, upstream/downstream ordering, GND continuity |

### 1k. Run connectivity and signal chain verification

```bash
# Component connectivity — catches phantom BOM components (2 tests)
python3 scripts/verify_component_connectivity.py

# Signal chain completeness — catches broken copper paths (53 tests)
python3 scripts/verify_signal_chain_complete.py
```

| Script | Tests | What it catches |
|--------|-------|-----------------|
| `verify_component_connectivity.py` | 2 | BOM components with zero electrical connections (phantom parts) |
| `verify_signal_chain_complete.py` | 53 | Nets that only connect to one endpoint (broken signal chains) |

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

**Netlist cross-check** (`verify_netlist_diff.py`, 4 checks):
Exports schematic XML netlist via `kicad-cli`, compares against PCB cache:
- Missing routes (schematic net not in PCB)
- Orphan PCB nets (PCB net not in schematic)
- Missing footprints (component in schematic but not PCB)
- Pin-to-net mismatches between schematic and PCB

### 1m2. Run schematic↔PCB/datasheet_specs sync guard (R4 class)

```bash
python3 scripts/verify_schematic_pcb_sync.py
```

**Schematic/PCB/datasheet_specs.py sync** (`verify_schematic_pcb_sync.py`):
Guards against the R4 class of bugs — schematic generator and PCB
generator are two independent Python code paths and can drift silently.
Three checks, all fail-loud (no soft-passes, no auto-skip):

| Check | Catches | R4 bug |
|-------|---------|--------|
| A — ref coverage | BOM refs with no schematic symbol; schematic refs with no BOM entry | R4-HIGH-1 (USBLC6/R22/R23 in PCB but missing from schematic) |
| B — designator collision | Same ref used for two different component families across schematic and BOM (token-overlap heuristic) | R4-HIGH-2 (U4 was both ILI9488 module and USBLC6 TVS) |
| C — connector net coverage | Each connector in `datasheet_specs.py` must have its full expected net set appear in the sheet that wires it | R4-CRIT-1 (display.py docstring described a completely different FPC pinout than the PCB used) |

**CRITICAL** — this script must exit 0 before any PCB release. It is
the only guard that catches schematic↔PCB drift on the Python
generators. Never add suppressions; never edit the allowlist in the
script to make a real bug disappear. Fix the design side instead.

### 1n. Generate hardware test firmware (Phase 3 prototype)

```bash
python3 scripts/generate_hw_tests.py
```

**Hardware test generator** (20 tests in `software/test/test_hardware.c`):
Auto-generates ESP-IDF Unity test firmware from `board_config.h`:
- 12 button idle-HIGH tests (BTN_L internal pull-up)
- LCD D0-D7 walking-1 short detection
- SD SPI bus init + CMD0 probe
- I2S PDM TX silence test
- USB JTAG verification
- 3.3V power rail ADC check
- PSRAM 1MB pattern verify

### 2. Manual review against checklist

Read `review-checklist.md` and verify each domain:

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

**CRITICAL HARD GATE** (R6): walks the union-find over pads ∪ vias ∪
segments for every net and asserts single connected component. Catches
the R5-CRIT class of bugs where pad-net labels are correct but copper
is fragmented — L1.1 BAT+ inductor isolated (board can't boot on
battery), C17/C18 decoupling caps floating, button pull-ups never
connected, SW_BOOT non-functional, D1 menu diode anodes dangling,
BTN_L missing F.Cu→B.Cu via-in-pad at U1.26 (L shoulder button never
worked on v3.3). Run with `--strict` to bail on technical-debt
accepted fragmentations.


**CRITICAL HARD GATE**: any overlap means a copper trace physically shares
copper with an unnetted (or differently-netted) pad — a real short on the
manufactured board. Checks F.Cu **and** B.Cu. Catches issues that DRC
misses when pads have no net assignment (the v3.3 regression from commit
`775e9fd`, where `_PAD_NETS` entries for U2.3/4, U6.8/9, SW_PWR.4b/4d
were removed and left BTN_SELECT/GND/SD_MISO/BTN_R traces crossing
unnetted pads). Integrated into:
- `make release-prep` (blocking dependency of release)
- `make verify-all` (parallel verification suite)
- `make verify-trace-through-pad` (standalone)
- `/release`, `/release-prep`, `/full-release` skills (hard gate)
- `Stop` hook `.claude/hooks/stop-verify-dfm.sh` (auto-runs after any
  PCB edit and blocks Claude's response with exit 2 on failure)

### 1i. System health summary

Answer these 5 questions with data:

| Question | Check | Must be |
|----------|-------|---------|
| Components positioned correctly? | `verify_datasheet.py` + `verify_polarity.py` | ALL PASS |
| No shorts or signal overlaps? | DFM 115/115 + DRC 0 real shorts + 0 trace-through-pad | ALL ZERO |
| Power stable? | `spice_power_check.py` | +5V ripple <150mV, +3V3 <50mV |
| Pinout matches datasheet? | `verify_datasheet_nets.py` | ALL PASS |
| All signals reach destination? | `verify_design_intent.py` | ALL PASS |
| Schematic ↔ PCB ↔ datasheet_specs agree? | `verify_schematic_pcb_sync.py` | PASS (R4 guard) |

If ANY check fails, stop and fix before generating the report.

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

- `.claude/skills/pcb-review/review-checklist.md` — Full scoring criteria + JLCPCB rules reference
- `hardware/datasheets/` — Component datasheets for pin verification
- `scripts/pcb_review.py` — Automated review script
- `scripts/verify_dfm_v2.py` — DFM verification (115 tests)
- `scripts/verify_polarity.py` — Polarity/pin assignment tests
- `scripts/verify_dfa.py` — Assembly verification (9 tests)
- `scripts/verify_bom_cpl_pcb.py` — BOM/CPL/PCB cross-check (10 tests)
- `scripts/verify_datasheet.py` — Datasheet vs PCB physical verification (29 tests)
- `scripts/verify_datasheet_nets.py` — Datasheet vs PCB net/pinout verification (259 checks)
- `hardware/datasheet_specs.py` — Single source of truth: pin→net mapping for all 30 components
- `scripts/validate_jlcpcb.py` — JLCPCB manufacturing validation (26 tests)
- `scripts/verify_antenna_keepout.py` — ESP32 antenna zone clearance (5 checks)
- `scripts/verify_stackup.py` — 4-layer stackup net verification (5 checks)
- `scripts/verify_net_class_widths.py` — Power/signal trace width enforcement (5 checks)
- `scripts/verify_bom_values.py` — BOM vs schematic value cross-check (75 checks)
- `scripts/verify_power_paths.py` — Power delivery path tracing (19 checks)
- `scripts/verify_copper_balance.py` — Layer copper distribution (3 checks)
- `scripts/verify_decoupling_paths.py` — Cap-to-IC path quality (11 checks)
- `scripts/verify_usb_impedance.py` — USB D+/D- impedance geometry (4 checks)
- `scripts/verify_via_in_pad.py` — Via-in-pad detection all SMD pads (3 checks)
- `scripts/verify_thermal_relief.py` — Zone thermal relief settings (4 checks)
- `scripts/verify_ground_loops.py` — Audio-digital ground coupling (3 checks)
- `scripts/verify_test_points.py` — Debug probe accessibility (18 checks)
- `scripts/erc_check.py` — ERC automation (KiCad native, artifact filtering)
- `scripts/spice_power_check.py` — ngspice power supply simulation (+5V/+3V3 ripple, load transient)
- `scripts/verify_design_intent.py` — Cross-source adversary (362 checks, T1-T22)
- `scripts/verify_netlist_diff.py` — Schematic-to-PCB netlist cross-check (4 checks)
- `scripts/verify_schematic_pcb_sync.py` — R4 sync guard: ref coverage, designator collisions, connector net coverage (schematic vs datasheet_specs.py vs CPL)
- `scripts/net_classifier.py` — Net function classifier with GPIO validation
- `scripts/generate_board_config.py` — Board config drift detection (config.py vs board_config.h)
- `scripts/generate_hw_tests.py` — ESP-IDF Unity test generator (20 tests)
- `scripts/generate_pcb/routing.py` — Trace routing
- `scripts/generate_pcb/board.py` — Component placement
- `scripts/generate_pcb/jlcpcb_export.py` — CPL/BOM export
