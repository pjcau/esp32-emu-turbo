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
| 4 | Dynamic behavior — power-up sequencing, strap pins at boot (GPIO0=SELECT, GPIO3=BTN_R + SD card-detect, GPIO45=BTN_L), buck stability, brownout under SNES load, LX noise, USB SI | Partially covered by strapping/resonance/sequence/vbench gates, but the models are only as good as their datasheet parameters |
| 5 | Hardware↔firmware↔mechanics contract — enclosure tolerances, FPC bend radius, button travel, battery fit | GPIO sync is gated; the mechanical side is not |
| 6 | Sourcing — wrong package variant, EOL/substitutions, stock | PAM8403 narrow SOP-16 vs wide SOIC-16W |

## Containment layers — TODO, in order of yield

### 1. Pre-order gate (closes class 3) — TODO

`make order-manifest`: print SHA256 of `gerbers.zip` / `bom.csv` / `cpl.csv`
from `release_jlcpcb/` and write a dated manifest; at upload time the hashes
are compared against what the JLC site received. Minimal cost, kills the
"the fix never reached the order" bug class by construction.

### 2. Unverified-claims ledger (closes class 1) — TODO

Every load-bearing claim of the kind "the shell is internally isolated"
(SW16↔BTN_SELECT, parked) or "the module has the pull-up" must live in a
claims file with status `VERIFIED-ON-DATASHEET` / `UNVERIFIED`, gated: an
`UNVERIFIED` claim older than N days goes red. Turns the most dangerous text
in the repo — the justification comment — into a work queue.

### 3. Dynamic SPICE gates (closes class 4) — TODO

The ngspice MCP is already installed. Scenarios to hook into vbench:

- buck transient with real MLCC ESR + Monte Carlo on R25/R26 tolerances
  (worst-case Vout);
- power-up ramp with strap-threshold verification at t=0;
- brownout at 3.0 V battery under 1.5 A SNES load.

### 4. First-article photographic protocol (closes class 2) — TODO

Formalize the v4.3.1 lesson as a skill: checklist per package *family* (not
per component), orientation check on the JLC 3D viewer before paying,
photo-vs-render comparison for each side.

### 5. Bring-up test firmware at first power-on — TODO

The `hardware-test-gen` skill exists: a Unity firmware that verifies every
GPIO/bus/rail at boot and reports over serial turns the "no bench
instruments, photos only" constraint into telemetry. It is the multimeter.

### 6. ERC warning burn-down — TODO

636 ERC warnings remain (481 off-grid endpoints). Noise that can hide a real
warning tomorrow; already parked in memory
(`project_schematic_deferred_deepdives`).

---

Conventions that apply to every item: a new gate goes into
`VERIFY_ALL_SCRIPTS` **and** gets an owner rule in
`scripts/issue_dispatch.py` (an unrouted gate is a hard error, exit 2);
gates get mutation tests; no soft-passes. Update the item's heading from
TODO to DONE (with commit hash) as layers land.
