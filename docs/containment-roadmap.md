# Containment roadmap — residual risk when every geometric gate is green

Written 2026-07-31. Driving question: **when DRC/DFM/shorts/annular/polarity
are all green, what can still go wrong — and what containment layers reduce
it?** Every real incident in this project's history passed the geometric
gates; none was a "construction" problem.

## Residual risk classes (anchored to incidents that already happened)

| # | Class | Evidence from this repo |
|---|-------|------------------------|
| 1 | Right copper, wrong decision — gates check the board against what we *declared*, so a wrong declaration makes everything green and wrong together | R25 (all 24 gates agreed with a wrong decision encoded in `datasheet_specs.py`); EN RC network missing for 4 releases behind a false "module has internal pull-up" comment; C28 counted as bulk while DNP |
| 2 | Assembly conventions — rotation reference frames, tape orientation, polarity markings | v4.3.1: 8 parts placed 90° off with a syntactically perfect CPL; JLC placed exactly what the file said |
| 3 | Drift between what was verified and what was uploaded — no gate can see what is on JLC's website | U4 fix sat months outside `release_jlcpcb/`; C2 polarity fix never reached the uploaded order |
| 4 | Dynamic behavior — power-up sequencing, strap pins at boot (GPIO0=SELECT, GPIO3=BTN_R — no SD card-detect exists on this board, GPIO45=BTN_L, GPIO46=LCD_WR), buck stability, brownout under SNES load, LX noise, USB SI | Partially covered by strapping/resonance/sequence/vbench gates, but the models are only as good as their datasheet parameters |
| 5 | Hardware↔firmware↔mechanics contract — enclosure tolerances, FPC bend radius, button travel, battery fit | GPIO sync is gated; the mechanical side is not |
| 6 | Sourcing — wrong package variant, EOL/substitutions, stock | PAM8403 narrow SOP-16 vs wide SOIC-16W |

## Containment layers — TODO, in order of yield

### 1. Pre-order gate (closes class 3) — DONE (d6de9e3)

`make order-manifest`: print SHA256 of `gerbers.zip` / `bom.csv` / `cpl.csv`
from `release_jlcpcb/` and write a dated manifest; at upload time the hashes
are compared against what the JLC site received. Minimal cost, kills the
"the fix never reached the order" bug class by construction.

Landed as `scripts/order_manifest.py` (writer) + `verify_order_manifest`
(freshness gate in `VERIFY_ALL_SCRIPTS` and the session-start subset) +
`test_order_manifest` (mutation suite). The `/release` skill regenerates
the manifest immediately after the `release_jlcpcb/` copy and records the
hashes in the release notes.

### 2. Unverified-claims ledger (closes class 1) — DONE (d6de9e3)

Every load-bearing claim of the kind "the shell is internally isolated"
(SW16↔BTN_SELECT, parked) or "the module has the pull-up" must live in a
claims file with status `VERIFIED-ON-DATASHEET` / `UNVERIFIED`, gated: an
`UNVERIFIED` claim older than N days goes red. Turns the most dangerous text
in the repo — the justification comment — into a work queue.

Landed as `hardware/CLAIMS.md` (seeded with the SW16 shell-isolation claim
UNVERIFIED — red on 2026-09-14 unless verified — the falsified EN pull-up
claim and the bench-verified USB-C 1.60 slot) + `verify_claims_ledger`
(N = 45 days, evidence required for any verdict) + `test_claims_ledger`.

### 3. Dynamic SPICE gates (closes class 4) — DONE (3a08f07)

The ngspice MCP is already installed. Scenarios to hook into vbench:

- buck transient with real MLCC ESR + Monte Carlo on R25/R26 tolerances
  (worst-case Vout);
- power-up ramp with strap-threshold verification at t=0;
- brownout at 3.0 V battery under 1.5 A SNES load.

Landed as `scripts/vbench/dynamics.py` (T1.4b, `make bench-dynamics`) +
`test_vbench_dynamics` (mutation-paired, in `VERIFY_ALL_SCRIPTS`). Two
deliberate substitutions, both argued in the module docstring: Monte
Carlo became a deterministic corner sweep (Vout is monotone in each
variable, so corners bound every MC draw and a gate must be
reproducible); MLCC ESR at f_sw is declared NOT establishable from the
held pages (the C12891 doc is a catalog citing DF at 120 Hz only), so
the simulated ripple is stated as a floor rather than decorated with an
invented ESR. First run: all three scenarios pass on the current design
(corners 3.213–3.455 V, EN margin +1.06 ms, brownout only at SoC 0).

### 4. First-article photographic protocol (closes class 2) — DONE (d6de9e3)

Formalize the v4.3.1 lesson as a skill: checklist per package *family* (not
per component), orientation check on the JLC 3D viewer before paying,
photo-vs-render comparison for each side.

Landed as `/first-article-check` (`.claude/skills/first-article-check/`):
phase A pre-payment on the JLC preview (referenced from the `/release`
skill), phase B on arrival, photos only. No gate — the checklist is human
work by nature; the machine-checkable halves live in layers 1 and 2.

### 5. Bring-up test firmware at first power-on — TODO

The `hardware-test-gen` skill exists: a Unity firmware that verifies every
GPIO/bus/rail at boot and reports over serial turns the "no bench
instruments, photos only" constraint into telemetry. It is the multimeter.

### 6. ERC warning burn-down — DONE (3c3d749)

636 ERC warnings remain (481 off-grid endpoints). Noise that can hide a real
warning tomorrow; already parked in memory
(`project_schematic_deferred_deepdives`).

Landed: 676 warnings (as measured at burn-down time) → ZERO. Grid snap
at emission in `generate_schematics/kicad_primitives.py`, on-grid pin
offsets for the three off-grid symbols (BAT54C/USBLC6/Speaker) with
their sheet wiring, and the `emu:` symbol library (generated
`emu.kicad_sym` + `sym-lib-table`) for the 169 bare-lib_id warnings.
`verify_erc` now gates `--severity-all` against a zero baseline — a
ratchet with nothing left to ratchet.

---

Conventions that apply to every item: a new gate goes into
`VERIFY_ALL_SCRIPTS` **and** gets an owner rule in
`scripts/issue_dispatch.py` (an unrouted gate is a hard error, exit 2);
gates get mutation tests; no soft-passes. Update the item's heading from
TODO to DONE (with commit hash) as layers land.
