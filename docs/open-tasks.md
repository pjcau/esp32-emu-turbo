# Open tasks — the condensed to-do list for protection, testing and coverage

Condensed 2026-08-01 from the four audit documents now in `docs/archived/`
(`containment-roadmap.md`, `waiver-audit-recovery.md`,
`error-taxonomy-coverage-audit.md`, `virtual-bench-plan.md`). Everything in
those files that was DONE stays there; everything still actionable is here.

Two standing rules from those audits apply to every item below:

- A new gate goes into `VERIFY_ALL_SCRIPTS` **and** gets an owner rule in
  `scripts/issue_dispatch.py`, plus a mutation test. No soft-passes.
- `docs/known-issues.md` is the living record of what is broken on the
  board itself and is parsed by gates at that path — items here that
  overlap its section C point back to it rather than replacing it.

## High priority — real defect classes

### 1. `collision.py` is default-open on pad nets

`_KNOWN_PAD_NETS` (`collision.py:215`) has 4 hardcoded entries; every other
pad registers with `net=0`, and net=0 pads are *skipped* in collision
queries, so a pad the router never targets is invisible to collision
detection forever and a trace can be routed straight over it. Contained
today only by post-hoc gates (`verify_trace_through_pad`,
`short_circuit_analysis`, `analyze_pad_distances`) — all green, but this
class has bitten before.

**Fix:** seed pad nets from `routing._PAD_NETS` / the datasheet spec map
before routing begins, so the router is default-closed.
Source: waiver audit O5 = `docs/known-issues.md` §C.

### 2. `verify_enclosure_sync` — the one ungated hardware contract

Error-taxonomy gap #17: nothing syncs `enclosure.scad` constants against
`board.py` (board outline 160×75 mm, mounting holes, USB-C / SD apertures).
The same drift class that bit GPIO before `firmware-sync-check` existed.

**Fix:** parse both files, compare the shared constants, mutation-test it,
add to `VERIFY_ALL_SCRIPTS`. Best cost/benefit of the three gaps.

### 3. SW16 shell-isolation claim — DEADLINE 2026-09-14

`hardware/CLAIMS.md` carries the claim "SW16's shell is internally
isolated from the contacts" (BTN_SELECT on shell tabs, GPIO0 strap) as
`UNVERIFIED`. `verify_claims_ledger` turns red 45 days after filing —
**2026-09-14**. Verify against the switch datasheet (or falsify and fix)
before that date.

## Medium priority — coverage gaps for v2

### 4. Promote ESD to a blocking gate for v2

Error-taxonomy gap #15: TVS on USB D+/D− and VBUS is advisory only. One
component per line, but the decision must be made at design time for v2.

### 5. Power-via ampacity check

Error-taxonomy gap #18: net-class width checks are trace-only; no gate
computes current through the +5V / BAT+ / +3V3 via stitching. Extend
`verify_net_class_widths` or add a small dedicated gate.

### 6. Test points — advisory only

Error-taxonomy gap #16, minor. Decide whether v2 gets probeable test
points (the bring-up firmware is the current substitute for instruments).

## Small cleanups — known fix, known reason they are open

Detail for each lives in `docs/known-issues.md` §C; this is the index.

- **R14 in `verify_netlist_diff.EXCLUDED_REFS`** — documented as DNP but
  never independently verified. Confirm before trusting the exclusion.
- **`verify_bom_values.KNOWN_MAPPINGS`** maps `"fpc-16p-0.5mm" → 40-pin`,
  papering over a real schematic/BOM inconsistency. Fix the schematic
  symbol value, then delete the mapping.
- **`verify_copper_clearance`** reports `loc = (0,0,0,0)` on the
  `nearest_points` fallback. Does not hide violations, only misplaces
  them.
- **`verify_easyeda_footprint._GEOMETRIC_MISMATCH_ALLOWLIST`** still holds
  U2 (90°) and LED2 (180°). Both angles are now *explained* (H4/H6 closed)
  but the allowlist is a tolerance, not a proof — replace with a derived
  check if it ever grows.

## Blocked — waiting on bench instruments

- **vbench T5.4 / T5.5** (calibrate models against a live board; close the
  loop with measured rails). The user has no bench instruments — photos
  only. Unblocks if instruments ever arrive; until then the bring-up
  firmware (`software/bringup_test/`) is the measuring device.

## Already closed — do not redo

The waiver audit's Part 2 items O1 (CPL rotation law, incl. D1/Q1/LED2),
O2 (VBUS widths), O3 (R20/R21 → PAM_VREF, fixed in `ee0ec02`) and O4
(phantom nets) are closed; the containment roadmap's six layers all
landed. See `docs/archived/` for the full record.
