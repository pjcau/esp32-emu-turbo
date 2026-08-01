# Gate Coverage Expansion Plan — categories 15–18 (rev 2)

Date: 2026-08-01 · Source: `docs/error-taxonomy-coverage-audit.md`
(Part 4 matrix) · Reviewed by plan-reviewer (26 findings, all folded
in; verdicts on record below).

Scope: promote the two advisory-only checks (15 ESD, 16 test points)
to blocking gates and close the two real gaps (17 PCB ↔ enclosure
sync, 18 power-via ampacity), wiring every new gate into the existing
hook/dispatch machinery so that **nothing can go silently red and
every session ends with all gates passing**.

## Findings that reshaped this plan (from the review)

- **F1 — the enclosure battery pocket cannot hold the specified
  cell.** `enclosure.scad:98-101` + `battery_compartment(bat_w+5,
  bat_h, bat_d)` at `:283` give a **70 × 55 × 9.5 mm** pocket; the
  spec cell (105080) is **50 × 80 × 10 mm**. 80 mm exceeds both pocket
  axes; 10 > 9.5 depth. Verified: no orientation fits. Live bug of
  exactly the class gap 17 predicts.
- **F2 — Workstream C's original premise was false.** The board
  ALREADY carries a USBLC6-2SC6 on USB D+/D− (**U4**,
  `release_jlcpcb/bom.csv:28`) and `verify_esd_protection` exits 0
  today with zero WARN. But that green is **vacuous**: at
  `verify_esd_protection.py:214-215` the VBUS-TVS check greps
  `ESD_KEYWORDS` against *reference designators* (`C17`, `F1`…), which
  can never match — dead code — and then falls back to
  `has_tvs_in_bom`, a global OR over the whole BOM, so **U4 (a
  data-line part) silences the VBUS check**. A false-green gate
  promoted to blocking would be worse than the advisory it replaces.
  C is therefore detector-repair first, parts second (maybe never).
- **F3 — the gate-coverage framework cannot yet prove a NEW gate
  works.** `verify_gate_coverage.py:308-313` declares a fault CAUGHT
  if *any* gate objects. Deleting a part trips the BOM/CPL/netlist
  family regardless, so `f_esd_removed`-style faults would "pass"
  even if the new gate were broken. Only a fault nothing else sees
  (the scad) discriminates today. Fixing this is prerequisite **A0**.

---

## Iron rules — how a new gate self-corrects (applies to ALL four)

This is the machinery satisfying the requirement: *any change to these
tests must trip hooks so the system converges to all-green by end of
session.*

1. **Add the gate to `VERIFY_ALL_SCRIPTS` in the Makefile.** That one
   edit auto-enrolls it in `make verify-all` and in `issue_dispatch`
   (verified: `gates_from_makefile` parses that variable and
   `SystemExit`s if missing or empty — never a copied list).
2. **Routing ownership must exist in the SAME commit.** Precision (per
   review): `issue_dispatch` exits 2 only when an unrouted gate is
   also *failing*; what catches a *passing* unrouted gate is
   `test_issue_dispatch::test_every_shipped_gate_is_routed`, already
   in verify-all. Empirically verified routing for the planned names:
   - `verify_esd_protection` → `law:esd` (pcb-engineer,
     `/electrical-review`, degraded) ✓ nothing to add
   - `verify_test_points` → `law:test_point` (pcb-engineer,
     `/pcb-review`, degraded) ✓ nothing to add
   - `verify_power_via_ampacity` → `law:power` (dead-board) — wrong
     severity; see Decision D2 (declared exception → degraded)
   - `verify_enclosure_sync` → **no keyword matches; would
     hard-error.** Add to `ROUTING_LAW`: `("enclosure",
     "mechanical fit", "cad-engineer", "/enclosure-design",
     "degraded", "a shell that does not fit the board is discovered
     after printing, not before")`
   - **The two new mutation suites need routing exceptions too**
     (review finding 18): `test_enclosure_sync` would inherit
     `law:enclosure`/degraded and `test_power_via_ampacity`
     `law:power`/dead-board — both wrong. A red mutation suite means
     the *gate* can no longer be trusted: **blind-spot**. Add two
     `ROUTING_EXCEPTIONS` entries with that rationale (precedent:
     `test_order_manifest`, `issue_dispatch.py:246-257`). The
     exceptions table then has THREE entries — also fix the live doc
     rot in CLAUDE.md, which still claims "`ROUTING_EXCEPTIONS` is
     empty on purpose".
3. **Every new gate ships with its mutation test** (`test_<gate>.py`),
   itself added to `VERIFY_ALL_SCRIPTS` (with its routing exception,
   above). Each suite must include the "renamed source constant /
   unknown input = hard error, not skip" cases (pattern:
   `test_issue_dispatch`).
4. **Gate-network proof via `verify_gate_coverage` — AFTER A0.** Each
   workstream adds one injected fault, with an `expect` field naming
   the gate that must fire (see A0). Faults land **only in the commit
   that makes their mutation applicable** (review finding 10): a
   `mutate()` whose regex matches nothing raises `Fatal` on every
   `verify-all` run, because `test_gate_coverage` T5 executes all
   mutations unconditionally.
5. **Regenerate the repo map** (`make repo-map`) in the same commit.
   Honest caveat (review finding 25): `repo-map-check` exists as a
   target but is **not** in `VERIFY_ALL_SCRIPTS`, so a stale index
   does not fail the suite today. Optional side-decision D4: enroll
   it (needs a routing keyword, e.g. `repo_map` → software-dev,
   cosmetic).
6. **SessionStart fast list**: add `verify_enclosure_sync` to
   `open_issues_report.GATES`. Justification: measured, not assumed —
   its imports (`board.py`, `_build_placements()`) run in ~0.15 s
   against the 30 s/gate budget. Contract: the gate's failure lines
   must start with `FAIL` (that is what `run_gate` extracts), and its
   GATES entry needs the one-line "meaning when it fails" string:
   *"the printed shell no longer matches the board (outline, holes,
   cutouts, battery, or Z-stack)"*.
7. **Extend the Stop hook** (`.claude/hooks/stop-verify-dfm.sh`) the
   way it already handles `EE_CHANGED` (`:108-116`), NOT by widening
   the PCB pattern: a separate `SCAD_CHANGED` flag
   (`hardware/enclosure/.*\.scad`), its own fail-count block and
   report line, top guard becomes `PCB_CHANGED || SCAD_CHANGED …`.
   `verify_enclosure_sync` runs when **either** side moves
   (`generate_pcb/` is already in the PCB pattern). Budget verified:
   current hook body ~7.2 s serial vs 30 s timeout.
   **Honest limitation** (review finding 16): the hook diffs against
   HEAD, so it guards *uncommitted* work only; once committed, the
   loop is closed by SessionStart + `verify-all`, not by this hook.
8. **A gate lands GREEN in the same commit as the design change it
   requires** (a red gate stops being read). Prove the gate CAN fail
   with its mutation test + injected fault, never by leaving the repo
   red. If gate and fix cannot land together, `make dispatch` turns
   the red into an owned work order — but same-commit is the default.
9. **Board-touching commits (C1-if-parts, D) follow the six-file
   chain** (footprint, BOM, CPL, schematic, routing, docs) **plus
   vbench models**, then `python3 scripts/verify_dfa.py` (mandatory),
   `release_jlcpcb/` sync (check `git diff --stat`) **and
   `make order-manifest` in the same commit** (review finding 17:
   `verify_order_manifest` is in verify-all AND in the SessionStart
   fast list — regenerated release files without a fresh fingerprint
   end the session red). Re-fingerprinting is a release-integrity
   action and is explicitly NOT a release: no tag is cut (Decision
   D1, R25 precedent).
10. **Rollback unit** (review finding 24): each workstream's gate +
    Makefile entry + routing entry + fault revert **together**; after
    any post-commit red that cannot be fixed forward immediately, run
    `make dispatch` so the red is owned before the session ends.

---

## Workstream A0 — make the coverage auditor able to vouch for a new gate (prerequisite)

- Extend the `FAULTS` tuple in `verify_gate_coverage.py` with an
  optional `expect` field: gate name(s) that MUST be among the gates
  that fired; the audit fails if the expected gate stays green even
  though others objected. Without this, three of the four planned
  faults measure network noise, not the new gate (F3).
- Backfill `expect` on the existing nine faults where unambiguous.
- Extend `test_gate_coverage.py` with mutation cases: an `expect`ed
  gate that never fires must fail the audit; an unknown `expect` name
  must hard-error.
- Doc-rot in the same commit (review finding 22): `Makefile:317` help
  text says "9 historical fault classes" — parameterize or update as
  faults are added; the docstring claim "every fault reproduces a
  REAL bug this project already had" must admit two categories
  (historical + predicted) — of the new faults only
  `f_enclosure_drift` is historical (F1).

## Workstream A — Gap 17: `verify_enclosure_sync` (priority 1)

**Why first**: live bug waiting (F1), no board change, same
"two sources deriving silently" pattern already paid for with the CPL.

**A1. The gate** (`scripts/verify_enclosure_sync.py`):
- **Two parsers, stated now** (review finding 9 — the original
  single-regex rule would hard-error on `screw_positions` and the
  gate could never go green):
  1. scalar constants: **column-0-anchored** `^name = value;` regex —
     anchoring verified necessary: a `^\s*`-tolerant regex picks up
     module-local duplicates (`cy`, `fl_r`, `fl_span`); column-0
     yields 75 constants, zero duplicates;
  2. `screw_positions`: a small bracket-balanced vector reader
     (multi-line, arithmetic elements, trailing comma), evaluating
     elements through the same expression evaluator used for derived
     scalars (`bot_d = body_d - top_d`).
  A constant the gate expects but cannot parse (renamed, restructured)
  is a **hard error, not a skip**; the constants block becomes a
  contract. Mutation test includes: indent a constant → the gate must
  notice, not silently bind a module-local of the same name.
- Comparisons (source of truth on the right):
  | scad | source of truth |
  |---|---|
  | `pcb_w/pcb_h/pcb_d/pcb_corner_r` | board outline in `generate_pcb/board.py` |
  | `screw_positions` | `MOUNT_HOLES_ENC` via `enc_to_pcb` (already used by `drc_check.check_mounting_hole_keepout`) — closes the triangle: today components are checked against `MOUNT_HOLES_ENC`, but nothing checks the scad's bosses EQUAL it |
  | `usbc_x`, `sd_x`, `pwr_sw_x` (+ z vs `pcb_z`) | J1 / SD / SW16 from `jlcpcb_export._build_placements()` |
  | `dpad_*`, ABXY, start/select, `shoulder_*` | SW* button placements |
  | `esp_x/esp_y/esp_w/esp_h/esp_d` | U1 placement + module dims |
  | `bat_w/bat_h/bat_d` (+5 margin) | **the existing vbench model `scripts/vbench/models/bt1_lp105080.py`** (cited family datasheet, "10 × 50 × 80 mm") — add a mechanical `dims` field there if absent; do NOT create a second declaration in `datasheet_specs` (review finding 13). The gate **declares the axis mapping** (cell dim ↔ scad X/Y/Z) explicitly. |
  | `disp_*` viewport | ILI9488 active area + panel placement |
  | `spk_x/spk_y/spk_diam` | speaker position |
  | interior Z (`top_d/bot_d/pcb_z/wall`) | tallest component per side from a package-height table |
- Tolerances: exact (±0.1 mm) outline/holes; window semantics for
  cutouts; ≥-margins for pockets and Z clearance.
- Output contract: failure lines start with `FAIL` (Iron Rule 6).

**A2. Fix F1** (cad-engineer, `/enclosure-design`) — the review
quantified the cascade; hand the cad-engineer the real numbers:
- Z is the binding constraint, not just XY: pocket floor at `wall=2`,
  battery top today `2+9.5 = 11.5` against the ESP32 module occupying
  z 12→15 (`esp_d=3` below `pcb_z=15`). A 10 mm cell reaches 12.0 —
  zero clearance; a real 10.5 mm cell interferes.
- XY: the 80 mm axis fits only in X (interior 166 mm); Y interior is
  `body_h − 2·wall = 81` mm — 0.5 mm/side, not viable. So: rotate the
  pocket (80 in X, 50 in Y) **and** either grow `body_d` (~25 →
  ≥26.5, cascading to `bot_d`, `usbc_z`, `sd_z`, `pwr_sw_z`, `pcb_z`,
  `screw_boss_h`, `z_inner`) or move the pocket out from under U1
  (module spans y 1→19).
- Checklist items, same commit: update the hand-written Z-stack
  comment block (`enclosure.scad:120-131`), the "9.5 × 55 × 65"
  comments at `:98` and `modules/battery.scad:4` (a stale
  justification comment is the highest-risk text class in this repo),
  re-render `make render-enclosure`, and confirm the new pocket does
  not break `drc_check.check_mounting_hole_keepout`.

**A3. Wiring**: Iron Rules 1–8; fault `f_enclosure_drift`
(`pcb_w = 159` in the sandbox scad — verified expressible: the
sandbox already copies `hardware/`, and `_sub` matches `:105`),
`expect="verify_enclosure_sync"` — the one fault that already
discriminates today, since nothing else reads the scad.

## Workstream B — Gap 18: `verify_power_via_ampacity` (priority 2)

Scoped honestly (review finding 19): **no existing helper answers
"which vias form this transition"** — `pcb_copper_graph.nodes_for`
deliberately erases per-layer structure (vias span all layers, then
union-find), and `networkx` is not installed.

- **v1 law (this plan)**: per power net (+3V3, +5V, VBUS, VBUS_IN,
  BAT+), for each source-pad → load-pad pair, compute the **minimum
  via cut** with a hand-rolled BFS over per-layer copper islands
  (from `load_cache()` segments/zones) with vias as inter-layer
  edges. Capacity of a cut = Σ per-via ampacity; conservative
  IPC-2152-derived table per drill size, cited in-file (e.g. 0.3 mm
  drill ≈ 1 A at ΔT 10 °C). No magic numbers without a citation.
- Required current per net from `datasheet_specs` with datasheet
  citations (SY8089 2 A, IP5306 boost limit, PAM8403 peak, backlight
  per the R27 sizing). A power net with no declared expected current
  is a **hard error** — never-silence.
- GND: checked as the sum of return currents of the rails it serves.
- If min-cut proves too heavy for v1, the documented fallback is the
  coarser "aggregate via count per net ≥ required current / per-via
  ampacity", with the weaker guarantee stated in-file — the choice is
  recorded in the script header, not silently.
- Wiring: mutation test on synthetic mini-cache fixtures (pattern:
  `test_power_net_integrity`) — starved cut → fail;
  missing-current-entry → hard error. Fault `f_via_starvation`
  (delete all but one of the 26 +3V3 vias; helpers `_net_number`/
  `_sub` exist) with `expect="verify_power_via_ampacity"` — NOTE:
  this fault will also fragment the In2 pour and fire
  `verify_power_net_integrity`; only A0's `expect` makes it meaningful.
  Routing: Decision D2 exception (degraded). Repo map.

## Workstream C — Cat. 15: ESD — repair the detector, then promote (priority 3)

Rewritten after F2. The board already has U4 (USBLC6-2SC6 on D+/D−)
and CC pull-downs (R1/R2); the gate's current all-green is partly
vacuous.

**C1. Repair `verify_esd_protection` detection** (no board change):
- `tvs_on_vbus` must be computed from the **net membership of parts
  whose BOM description matches `ESD_KEYWORDS`** (which nets do the
  part's pads land on), not from designator string-matching
  (`:214-215` dead code).
- Remove the `has_tvs_in_bom` global-OR escape from the VBUS check
  (`:159`, `:215`) — a data-line TVS must not silence a VBUS finding.
- Re-run: the honest result is expected to be **red on VBUS TVS**
  (nothing protects VBUS today beyond C17 bulk + F1 fuse). That red
  is the input to C2, not a problem to suppress.
**C2. Decide the VBUS TVS** (product decision, Decision D5): add an
SMF5.0A-class TVS downstream of F1 (six-file chain + vbench model +
order manifest, Iron Rule 9), or file the deliberate absence as a
claim in `hardware/CLAIMS.md` (format enforced by the ledger gate;
note the mechanism: an `UNVERIFIED` claim goes red in 45 days — the
waiver is time-boxed by design, not permanent).
**C3. Flip the gate** to exit non-zero, with **no internal waiver
list** — deliberate absences live in CLAIMS.md, read by the script.
Wiring: already in `VERIFY_ALL_SCRIPTS`, already routed (`law:esd`).
Fault `f_esd_removed` (strip U4 from sandbox BOM+board,
`expect="verify_esd_protection"`) lands only with C3, after A0.
If D5 chooses the claim path, C touches **no board files at all** —
no six-file chain, no DFA run, no manifest churn.

## Workstream D — Cat. 16: test points — expand the law, measure, then flip (priority 4)

Reframed (review finding 20): `verify_test_points.py:28-29` already
requires the power rails and passes today (13 accessible, 0 WARN) —
"flip WARN→FAIL" alone is a no-op. The value is in the new entries.

**D1. Expand `REQUIRED_SIGNALS`**: add bring-up signals — EN,
GPIO0/BOOT strap, TXD0/RXD0 — each entry carrying one line of *why it
earns a TP*, so the list never grows by inertia.
**D2. Measure the deficit** in report mode. The gate counts probeable
copper (pads/vias ≥ `MIN_PAD_DIM`), so connector pins and exposed
vias may already satisfy much of D1.
**D3. Close the deficit and flip in the same commit** (Iron Rule 8):
TPxx pads (1.2 mm SMD, bottom side, via `board.py`) only where
measured short — that commit is board-touching → Iron Rule 9 (six-file
chain, `verify_dfa`, `release_jlcpcb/` sync, `make order-manifest`).
If the measured deficit is zero, D3 is just the exit-code flip.
**Fault**: `f_test_point_removed` is **conditional** (review finding
10): today there are zero TP refs on the board, so the planned
mutation matches nothing and would `Fatal` every verify-all run. Land
it only if D3 adds pads; otherwise the fault targets existing
probeable copper (shrink the largest probeable +3V3 pad below
`MIN_PAD_DIM = 0.5`) or is dropped — decided by D2's measurement.
Routing already exists (`law:test_point`).
- Rationale: the user debugs with photos and a multimeter at most —
  the C2-reversed incident was diagnosed by continuity on exposed
  copper. TPs cost zero BOM lines.

---

## Sequencing and landing checklist

Order: **A0 → A → B → C → D**. A0 is the framework fix everything
else's proof depends on (review finding 26). C and D each ride at
most one board-change commit — and possibly none (C via claim, D via
zero deficit).

Per workstream:
1. Gate + mutation test; prove failure on fixtures/faults only.
2. Design fix if required (A2, C2-if-TVS, D3-if-deficit) in the same
   commit.
3. Board touched → `verify_dfa` + six-file chain + vbench models +
   `release_jlcpcb/` sync + `make order-manifest` (Iron Rule 9).
4. Makefile (`VERIFY_ALL_SCRIPTS`: gate + test) · routing (keyword or
   exception) · `verify_gate_coverage` fault with `expect` · Stop-hook
   `SCAD_CHANGED` block (A only) · fast GATES entry (A only).
5. `make repo-map` · `make verify-all` — **everything green**.
6. One commit per workstream; push. Revert unit = the whole
   workstream (Iron Rule 10).

End state: matrix rows 15–18 flip to ✅ gated; the only remaining ➖
is row 19 (EMC / environmental / live stock — accepted).

## Decisions for the user

- **D1 (scope)**: C/D may add parts/pads. Per the R25 precedent this
  lands in design only — **no release tag, no fabrication implied**
  (none exists after v4.3.1, deliberately). Confirm.
- **D2 (severity honesty)**: `verify_power_via_ampacity` under
  `law:power` would rank **dead-board**; an undersized via transition
  is really **degraded** (runs hot, same class as `law:width`).
  Recommendation: declared `ROUTING_EXCEPTIONS` entry — severity
  ranks dispatch order, and the exceptions table exists exactly for
  this (it already has one entry; with finding 18's two suite
  exceptions it grows to four — update CLAUDE.md's "empty on purpose"
  line).
- **D3 (F1 fix direction)**: confirm the 105080 (50 × 80 × 10) cell
  is still the chosen battery before reworking the shell — the
  alternative is a smaller pack fitting the current ~70 × 55 × 9.5
  pocket, which is a product decision (capacity loss), not a CAD one.
- **D4 (optional)**: enroll `repo-map-check` in `VERIFY_ALL_SCRIPTS`
  (today a stale index fails nothing; needs a routing keyword).
- **D5 (VBUS TVS)**: part vs time-boxed CLAIMS.md entry, after C1
  shows the honest red.
