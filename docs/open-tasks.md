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

### 2. SW16 shell-isolation claim — DEADLINE 2026-09-14

`hardware/CLAIMS.md` carries the claim "SW16's shell is internally
isolated from the contacts" (BTN_SELECT on shell tabs, GPIO0 strap) as
`UNVERIFIED`. `verify_claims_ledger` turns red 45 days after filing —
**2026-09-14**. Verify against the switch datasheet (or falsify and fix)
before that date.

## Medium priority — follow-ups from the ampacity gate (2026-08-01)

Left deliberately visible by the gate-coverage expansion (the gate prints
them as "not judged", it does not fail on them):

### 3. ~~BAT+ → L1.1 single-via feed~~ — DONE in v4.4.0 (c7a01bc)

Closed 2026-08-01. The branch was actually behind THREE serial single
barrels (the gate prints only the minimum cut — lesson recorded); the
planned IP5306_KEY re-route would have moved the bottleneck, not
removed it. Fixed by a second BAT+ stitching band (4x 0.90/0.45 at
y=47.55) + barrel-free B.Cu feed to L1.1 + dogleg deletion (5 dead
POWER_HIGH_ALLOWLIST waivers dropped). L1.1 cut: 0.527 A → 5.114 A.
Still open, smaller stakes: +3V3→U1.2 and +5V→U3.1 each sit behind one
0.527 A via, and SW16.2 (no load current by design) tops the printed
"not judged" list.

### 4. Per-load current budgets for `verify_power_via_ampacity`

Declaring per-load budgets would upgrade the gate from min-cut ampacity
to a feasibility max-flow. Until then the single-via feeds above are
printed but not judged.

### 4b. `verify_decoupling_paths` bounding-box metric weakness

Its "path length" sums every same-net segment whose midpoint falls in
the cap↔IC bounding box + 3 mm — not an actual path. C18→U2 sits at
3.8x/4.0 because the v4.4.0 stitching band lands in the box; the next
BAT+ copper near U2 trips the gate for the wrong reason. Fix the gate's
metric (real path walk), not the board.

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

- Waiver audit Part 2: O1 (CPL rotation law, incl. D1/Q1/LED2), O2 (VBUS
  widths), O3 (R20/R21 → PAM_VREF, `ee0ec02`), O4 (phantom nets).
- The containment roadmap's six layers all landed.
- **Error-taxonomy gaps 15–18 all landed 2026-08-01** via the
  gate-coverage expansion merge: `verify_enclosure_sync` (`7b51eda`, also
  fixed a battery pocket that could not hold the 105080 cell),
  `verify_test_points` promoted to blocking (`e68347a`),
  `verify_esd_protection` net-verified via the claims ledger (`21716ec`),
  `verify_power_via_ampacity` (`0d456be`, 5 starved transitions fixed).

See `docs/archived/` and memory `HISTORY.md` for the full records.
