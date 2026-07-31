# pcb-review — per-script notes (reference)

Moved out of SKILL.md 2026-07-26 (progressive disclosure): the
workflow lives in SKILL.md; what each script CATCHES lives here.
Read the section you need, not the file.

## 1i. System health summary

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


## 1h2. Run per-net copper connectivity check (R5-CRIT gate)


**CRITICAL HARD GATE** (R6): walks the union-find over pads ∪ vias ∪
segments for every net and asserts single connected component. Catches
the R5-CRIT class of bugs where pad-net labels are correct but copper
is fragmented — L1.1 BAT+ inductor isolated (board can't boot on
battery), C17/C18 decoupling caps floating, button pull-ups never
connected, SW14 non-functional, D1 menu diode anodes dangling,
BTN_L missing F.Cu→B.Cu via-in-pad at U1.26 (L shoulder button never
worked on v3.3). Run with `--strict` to bail on technical-debt
accepted fragmentations.


**CRITICAL HARD GATE**: any overlap means a copper trace physically shares
copper with an unnetted (or differently-netted) pad — a real short on the
manufactured board. Checks F.Cu **and** B.Cu. Catches issues that DRC
misses when pads have no net assignment (the v3.3 regression from commit
`775e9fd`, where `_PAD_NETS` entries for U2.3/4, U6.8/9, SW16.4b/4d
were removed and left BTN_SELECT/GND/SD_MISO/BTN_R traces crossing
unnetted pads). Integrated into:
- `make release-prep` (blocking dependency of release)
- `make verify-all` (parallel verification suite)
- `make verify-trace-through-pad` (standalone)
- `/release`, `/release-prep`, `/full-release` skills (hard gate)
- `Stop` hook `.claude/hooks/stop-verify-dfm.sh` (auto-runs after any
  PCB edit and blocks Claude's response with exit 2 on failure)


## 1n. Generate hardware test firmware (Phase 3 prototype)


**Hardware test generator** (20 tests in `software/test/test_hardware.c`):
Auto-generates ESP-IDF Unity test firmware from `board_config.h`:
- 12 button idle-HIGH tests (BTN_L internal pull-up)
- LCD D0-D7 walking-1 short detection
- SD SPI bus init + CMD0 probe
- I2S PDM TX silence test
- USB JTAG verification
- 3.3V power rail ADC check
- PSRAM 1MB pattern verify


## 1m2. Run schematic↔PCB/datasheet_specs sync guard (R4 class)


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


## 1m. Run schematic-to-PCB netlist diff


**Netlist cross-check** (`verify_netlist_diff.py`, 4 checks):
Exports schematic XML netlist via `kicad-cli`, compares against PCB cache:
- [T1] Missing routes (schematic net not in PCB)
- [T2] Orphan PCB nets (PCB net not in schematic)
- [T3] Missing footprints (component in schematic but not PCB)
- [T4] Pin-to-net mismatches between schematic and PCB

**T4 only sees pins that reach the netlist.** `SW15` and `SW14` were
absent from `SCH_PIN_TO_PCB_PADS` for a long time because their schematic
pins were floating — `SW_Push` pins are *horizontal* (x ± 5.08), not
vertical like the R/C symbols, so the generator's wires landed beside the
pins. No pin of theirs ever reached the comparison, so the gate could not
have caught anything about them. Both are now wired and mapped. When adding
a part to that table, remember a tact switch has **two poles, not four
terminals**: pads 1+2 are one pole, 3+4 the other, and the symbol has one
pin per pole (`_TACT_MAP`) — pad 2 belongs to symbol **pin 1**.


## 1k. Run connectivity and signal chain verification


| Script | Tests | What it catches |
|--------|-------|-----------------|
| `verify_component_connectivity.py` | 2 | BOM components with zero electrical connections (phantom parts) |
| `verify_signal_chain_complete.py` | 53 | Nets that only connect to one endpoint (broken signal chains) |


## 1j. Run electrical review scripts


| Script | Tests | What it catches |
|--------|-------|-----------------|
| `verify_strapping_pins.py` | 12 | Wrong boot state, GPIO45 VDD_SPI conflict, EN RC timing, pull-up skip |
| `verify_decoupling_adequacy.py` | 25 | Insufficient capacitance per IC datasheet, missing HF bypass |
| `verify_power_sequence.py` | 26 | Power chain topology, upstream/downstream ordering, GND continuity |


## 1e. Run SPICE power supply simulation


Requires: `ngspice` (`brew install ngspice`)

Simulates IP5306 boost → **SY8089 buck (U3)** → L2 → C30 → ESP32 load:
- +5V rail ripple at 500kHz switching (must be < 150mV)
- +3V3 rail ripple under load steps (must be < 50mV). Note the buck is an
  *averaged closed-loop* model, so 1 MHz switching ripple is NOT represented
- Decoupling cap effectiveness (C17, C27, C1, C19)
- ESP32 WiFi burst response (200mA → 350mA in 10µs)


## 1d. Run ERC (Electrical Rules Check)


Runs KiCad native ERC on the hierarchical schematic. Categorizes 730+ violations:
- **Generator artifacts** (suppressed): grid alignment, wiring stubs, library symbols — inherent to Python-generated schematics
- **Real issues**: pin_not_connected, power_pin_not_driven, pin_to_pin conflicts
- **Critical**: pin_to_pin (output↔output) must be zero for production


## 1g. Run DRC Audit (electrical connectivity)


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


## 1f. Run design intent adversary (cross-source consistency)


**Design intent verification** (`verify_design_intent.py`, 369 checks):
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


## 1c. Run datasheet verification (electrical + physical)


**Datasheet net verification** (`verify_datasheet_nets.py`, 267 checks):
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


## 1b. Run extended verification suite (17 gap-coverage tests)


| Script | Checks | What it catches |
|--------|--------|-----------------|
| `verify_antenna_keepout.py` | 5 | Copper/traces in ESP32 antenna zone (kills WiFi/BLE) |
| `verify_stackup.py` | 5 | Wrong nets on inner plane layers |
| `verify_net_class_widths.py` | 5 | Power traces too narrow (fuse risk) |
| `verify_bom_values.py` | 80 | Schematic value vs BOM mismatch (wrong part assembled) |
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


## 1. Run automated checks


**BOM/CPL/PCB cross-check** (`verify_bom_cpl_pcb.py`, 12 checks):
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


