# Error Taxonomy vs Test Coverage Audit

Date: 2026-08-01 · Method: full error taxonomy for the development of an
electronic device of this class (handheld console: ESP32-S3 + parallel TFT +
LiPo + USB-C + SD + audio), cross-checked against every verification script in
`docs/REPO_MAP.md` and the authoritative gate list `VERIFY_ALL_SCRIPTS` in the
Makefile (100 scripts run by `make verify-all`).

## Verdict

**14 of 19 error categories are covered by blocking gates, 2 are covered in
advisory-only mode (they can never fail), and 3 have real gaps.** The most
concrete gap is PCB ↔ enclosure mechanical synchronization. Coverage of the
classic "dead board" classes (shorts, opens, rotations, release drift) is
exceptional — including a meta-level (mutation tests + fault injection on the
gates themselves) that most hardware projects do not have.

---

## Part 1 — Categories COVERED by blocking gates

### 1. Schematic capture errors
Wires crossing without a junction, floating pins, labels not attached to their
wire, overlapping printable elements, ERC violations.

Covered by: `verify_erc` (zero error-severity findings), `erc_check` +
`test_erc_severity` (mutation-tested verdict), `verify_schematic_pin_connectivity`,
`verify_schematic_crossings`, `verify_schematic_label_attach`,
`verify_schematic_overlaps`.

### 2. Electrical design errors
Wrong component values, missing pull-ups, strapping-pin misconfiguration, wrong
power-on sequencing, inadequate decoupling, two drivers fighting over one net,
missing battery protection.

Covered by: `verify_bom_values` (BOM vs schematic), `verify_strapping_pins` +
`test_strapping_en_rc` (EN RC delay, mutation-tested), `verify_power_sequence`,
`verify_decoupling_adequacy`, `verify_decoupling_paths`, vbench `conflicts.py`
(T1.3 electrical conflicts), `verify_battery_protection` (reverse polarity +
over-voltage), `simulate_circuit`, `spice_power_check`.

### 3. Schematic ↔ PCB ↔ netlist synchronization
The generated schematic and the generated PCB silently disagreeing (the R4
lesson — recorded as a bug class in project memory).

Covered by: `verify_schematic_pcb_sync`, `verify_netlist_diff` (KiCad netlist
export vs PCB cache), `verify_netlist_vs_kicad` (cross-check against KiCad's
own IPC-D-356 export), `verify_schematic_pcb`.

### 4. Short circuits
Covered by **three independent strategies** (deliberate redundancy, recorded in
project memory): KiCad DRC (`drc_check`, `drc_native`), Shapely polygon
analysis (`short_circuit_analysis`), plus `verify_copper_clearance` (catches
what DRC misses at ≥ 0.09 mm), `verify_isolation`, `verify_trace_crossings`,
`verify_trace_through_pad`, and — critically — `verify_gerber_etest`, which
finds shorts in the **shipped artifacts**, not the design files.

### 5. Opens / broken connectivity
The "dead board" class: a power plane split into two pieces of copper, a track
ending in the air, a component pad no copper reaches.

Covered by: `verify_net_connectivity` (walks the per-net copper graph),
`verify_power_net_integrity` + `test_power_net_integrity` (+3V3/+5V/GND/VBUS/BAT+
must each be ONE piece of copper, no allowlist), `verify_signal_chain_complete`,
`verify_dangling_copper`, `verify_component_connectivity` (phantom components),
`verify_zone_connectivity`, `test_pcb_connectivity`, and `verify_gerber_etest`
for opens in the shipped gerbers. This is the direct response to the
"no board ships with unconnected nets — release must HARD BLOCK" lesson.

### 6. Wrong footprints / pad geometry
Covered by: `verify_easyeda_footprint` (reference geometry cache tracked in
git, so gates judge against *reviewed* geometry), `verify_datasheet` (PCB
physical characteristics vs datasheet), `verify_datasheet_nets` (pad-to-net
assignments vs datasheet specs). Backed by the recorded lesson "EasyEDA can be
wrong — cross-check the datasheet" (all three NPTH drills were once wrong).

### 7. Zone fill corruption
Covered by: `verify_zone_fill_sanity` + `test_zone_fill_sanity` (regression
tests for the duplicated-fill bug).

### 8. Fabrication DFM
Drill sizes, annular rings, clearances, stackup, copper balance, gerber
integrity.

Covered by: `validate_jlcpcb`, `verify_jlcpcb_capabilities` (JLCPCB's official
capability table), `verify_jlcpcb_via_rules` (from JLCPCB's own design guide),
`verify_drill_standards`, `verify_dfm_v2`, `verify_via_in_pad`,
`analyze_pad_distances`, `verify_stackup`, `verify_copper_balance`,
`verify_gerber_integrity`.

### 9. Assembly DFA / rotations / polarity
The v4.3.1 disaster class (systemic 90° bottom-side rotation, C2 tantalum
mounted reversed → 0 Ω short on +3V3).

Covered by: `verify_cpl_rotation_law` + `test_cpl_rotation_law` — ONE global
law plus declared exceptions instead of a per-part table, mutation-tested
(recorded principle: "a gate that asks *is this signed off?* cannot catch a
wrong sign-off"); `verify_polarity` (pin-to-net for ALL components — note: it
IS pass/fail via unittest exit code, even though REPO_MAP does not mark it as
a gate); `verify_dfa` (Tier 1 + Tier 2 SMT checks); `verify_stencil_aperture`
(IPC-7525); `verify_bom_cpl_pcb`; `analyze_pin1_marker`; the
`first-article-check` skill (JLC 3D-preview orientation check per package
FAMILY before paying); `hardware/datasheets/POLARITY_AUDIT.md` as polarity
source of truth.

### 10. Release-artifact drift
A fix that lands in the generator but never reaches `release_jlcpcb/` (the U4
lesson — a fix sat unshipped for months while every gate stayed green, because
gates compared generator to board, never release to generator).

Covered by: `order_manifest` (SHA256 fingerprint of exactly what goes to
JLCPCB) + `verify_order_manifest` + `test_order_manifest` (mutation-tested
freshness), `verify_gerber_integrity`, `verify_net_explorer_fresh`,
`docs-bom-check`.

### 11. Firmware ↔ hardware desynchronization
GPIO map in firmware disagreeing with the board.

Covered by: `generate_board_config` (`config.py` → `board_config.h`, single
source), `make firmware-sync-check`, `verify_firmware_retrogo_sync` (retro-go
target ↔ board GPIO), the `pcb-to-firmware` skill, and the bring-up test
firmware (`software/bringup_test/`, generated from `board_config.h` and
freshness-gated by `verify_bringup_fresh`; it validates every
GPIO/bus/peripheral on the physical prototype — the retired
`generate_hw_tests` never compiled and was deleted).

### 12. Functional / electrical behavior (simulated)
Does the board actually work: rail voltages, inrush, brownout, boot straps,
display protocol, SD protocol, audio chain, thermal.

Covered by: the entire Virtual Bench suite — `rails` (DC operating point on
every net), `transients` (cold start, inrush, load steps, brownout), `thermal`
(junction temperatures, 40 °C in-enclosure worst case), `display` +
`ili9488_ctrl` (controller as a state machine), `sdcard` + `sdcard_protocol`
(a microSD that answers), `audio`, `buttons` (debounce RC), `pins` (boot
configuration), `conflicts`, plus `detectors.py` — which proves the bench
**rediscovers the known historical bugs** — and `mutate.py` (break the board
on purpose so the bench can be measured). Component models declare
`UNESTABLISHED` parameters explicitly (e.g. IP5306 charge-path dissipation)
instead of guessing.

### 13. Signal integrity (where it matters at these speeds)
Covered by: USB — `verify_usb_impedance` (calibrated to the link's actual bit
rate), `verify_usb_impedance_stackup`, `verify_usb_return_path` (GND via
stitching); RF — `verify_antenna_keepout` (ESP32-S3-WROOM-1);
`verify_ground_loops`; `verify_power_resonance` (+3V3 plane LC resonance).
Recorded decision: USB Zdiff 130 Ω is a non-issue — do not move parts for it.

### 14. The verification machinery itself (meta-level)
A broken gate is worse than a missing one: it certifies a bad board.

Covered by: `verify_gate_coverage` + `test_gate_coverage` — injects known
faults and demands the gate NETWORK objects; ~15 mutation-test suites
(`test_*`) that break checkers on purpose and require them to notice;
`issue_dispatch` + `test_issue_dispatch` (a failing gate no routing rule
covers is a hard error, severity `blind-spot` ranks highest);
`verify_claims_ledger` + `test_claims_ledger`; `verify_memory` +
`test_verify_memory`; `open_issues_report` at session start (gate state is
derived by running the gates, never written down). This is rare and valuable.

---

## Part 2 — Covered only in ADVISORY mode (can never fail)

### A1. ESD protection
`verify_esd_protection` emits WARN only, by declared choice
("prototype may work without ESD" — `verify_esd_protection.py:10`). It warns
about: no TVS on USB D+/D−, no series resistors, no CC pull-down check, no
bulk cap / TVS on VBUS. **This is the only field-failure class (as opposed to
fabrication-failure) with no blocking gate.** Acceptable for the prototype;
should be promoted to a gate for v2 — a handheld's USB port is touched daily.

### A2. Test-point accessibility
`verify_test_points` is advisory ("debugging may be harder without test
points"). Relevant because the user has **no bench instruments** — debugging
happens via photos, so probeable nets are worth more here than usual.

---

## Part 3 — Real gaps

### G1. PCB ↔ enclosure mechanical synchronization (most concrete gap)
The only mechanical check is the mounting-hole boss keepout in
`drc_check.py:571` (`check_mounting_hole_keepout`) — and it reads constants
from `board.py` (`MOUNT_HOLES_ENC`), **not** from `enclosure.scad`. The
160 × 75 mm outline agreement is a manual convention (`enclosure.scad:105`
`pcb_w = 160` with a comment "from KiCad"). No gate verifies:

- USB-C / SD-slot openings aligned with the shell cutouts
- button and display cutout positions vs actual component placement
- battery pocket vs the 105080 cell (50 × 80 × 10 mm)
- component heights vs interior clearance (3D interference)
- speaker position vs its grille

If `enclosure.scad` changes, **nothing goes red**. This is exactly the
"two sources deriving silently" pattern the project already paid for with the
CPL. Suggested fix: a `verify_enclosure_sync` gate that parses the constants
of `enclosure.scad` and compares them against `board.py` (outline, holes,
connector apertures), with a mutation test.

### G2. Via ampacity on power nets
`verify_net_class_widths` enforces trace widths per net class (which encodes
current), and `verify_power_net_integrity` proves each rail is one piece of
copper — but no check was found on the **number/cross-section of vias**
carrying current between layers on +3V3 / +5V / BAT+. `verify_jlcpcb_via_rules`
is purely geometric. A single 0.3 mm via carrying the full 3.3 V rail current
would pass every current gate. Cheap fix: count parallel vias per power net at
each layer transition and assert a minimum by expected current.

### G3. Not automatable pre-fab (accepted as uncovered)
- **EMC / radiated emissions** — needs a chamber or at least a near-field
  probe; user has no instruments. Layout-level mitigations are partially
  covered (return paths, ground stitching, antenna keepout).
- **Environmental** (drop, vibration, humidity, component temperature
  *ratings* vs the −10…+40 °C usage envelope) — no check; typical for this
  project class.
- **Real-time part availability / EOL** — `jlcpcb_parts` checks the BOM
  statically; live stock lives in the `jlc_stock_check` MCP tool as a
  process step, deliberately not a gate (a network-dependent gate would be
  flaky). Correct trade-off; just remember to run it before ordering.

---

## Part 4 — Coverage matrix (summary)

| # | Category | Status |
|---|----------|--------|
| 1 | Schematic capture | ✅ gated |
| 2 | Electrical design | ✅ gated |
| 3 | Schematic ↔ PCB sync | ✅ gated |
| 4 | Shorts | ✅ gated ×3 strategies |
| 5 | Opens / connectivity | ✅ gated, mutation-tested |
| 6 | Footprint geometry | ✅ gated |
| 7 | Zone fill | ✅ gated |
| 8 | Fabrication DFM | ✅ gated |
| 9 | Rotations / polarity / DFA | ✅ gated, mutation-tested |
| 10 | Release-artifact drift | ✅ gated (SHA256 manifest) |
| 11 | Firmware ↔ HW sync | ✅ gated |
| 12 | Functional behavior | ✅ vbench + fault injection |
| 13 | Signal integrity | ✅ gated (USB, RF, GND) |
| 14 | Verification machinery | ✅ mutation-tested meta-level |
| 15 | ESD protection | ⚠️ advisory only — promote for v2 |
| 16 | Test points | ⚠️ advisory only |
| 17 | PCB ↔ enclosure mechanics | ❌ gap — no sync gate |
| 18 | Power-via ampacity | ❌ gap — geometric checks only |
| 19 | EMC / environmental / live stock | ➖ accepted, not automatable |

## Recommended next steps (best cost/benefit first)

1. **`verify_enclosure_sync`** — parse `enclosure.scad` constants vs
   `board.py` (outline, mounting holes, connector apertures); mutation test
   included, added to `VERIFY_ALL_SCRIPTS` (which auto-enrolls it in
   `issue_dispatch` routing — an unowned gate is already a hard error).
2. **Promote ESD to a blocking gate for v2** — TVS on USB D+/D− and VBUS is
   a one-component-each fix at design time.
3. **Power-via ampacity check** — extend `verify_net_class_widths` or add a
   small dedicated gate.
