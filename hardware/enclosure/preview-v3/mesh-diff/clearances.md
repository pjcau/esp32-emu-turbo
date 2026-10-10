# Top-boss gusset clearances — mesh-measured audit (2026-10-10)

Verification task from team-lead: measure clearance between the new top-boss
gusset ribs (`hardware/enclosure/enclosure.scad`, `top_boss_gusset_*`, 4 bosses
x 8 ribs each) and every mounted part, by mesh-to-mesh distance (trimesh
`proximity.closest_point`, both directions — same method as the existing
`top_boss_gusset_overrides` comment), not boolean volume overlap. Required
minimum: 0.5 mm, at rest AND through full travel/lateral slop for every
moving part.

**Result: one real violation found and fixed.** A second rib at the
back-right boss — (70,−30.5) at angle 90° (true north), which the original
design comment did not analyze — came out at 0.344 mm worst-case against the
Menu cap, under the 0.5 mm bar. Fixed by adding
`[70, -30.5, 90, 5.2]` to `top_boss_gusset_overrides` (height only, 6.5→5.2;
reach left at the default 6.6). Re-measured worst-case after the fix:
0.561 mm (now the already-known 135° rib is the tighter of the two, at the
same value its own commit comment recorded). All other parts and all other
31 ribs were already ≥0.5 mm and were left unchanged.

## Method

- Ribs isolated into their own mesh (32 disjoint triangular wedges, one
  OpenSCAD render of just the `top_boss_gusset_*` geometry, not the rest of
  the shell), so "nearest rib" attribution is to the rib itself, not the
  boss cylinder or ceiling.
- Static parts: existing assembly-coordinate reference STLs
  (`hardware/enclosure/reference/*.stl`, `3d_case/viewer/parts/*.stl`) — all
  current for commit `26c42daf` (checked: last touching commits are older
  than the gusset geometry, confirmed by git history + a `verify_enclosure_*`
  gate run).
- Moving parts: travel/slop applied as rigid transforms on the rest-pose
  mesh (translation for straight-line travel, rotation about the real pivot
  axis for the L/R levers) — these reproduce the scad's own kinematics
  (`lr_press`, `_face_cap_body` stem travel, etc.), not a separate
  approximation.
- `trimesh.proximity.closest_point(B, A.vertices)` and the reverse, minimum
  of both directions — exact distance from vertices to the opposing
  surface, not vertex-to-vertex.
- Full computation: `/private/tmp/.../scratchpad/gusset_clearance.py`
  (session-local scratch, not in the repo).

## Table — minimum clearance to the nearest rib

"Rest rib" / "worst rib" = `(boss_x,boss_y)@angle`. "Worst" = rest position
perturbed by the part's own full travel and/or lateral guide slop, in the
direction that reduces clearance.

| Part | Modelled? | Rest clearance | Worst-case clearance |
|---|---|---|---|
| **1. PCB + top-side components** | | | |
| Bare PCB sheet (board material under the boss, not a component) | from pcb_outline (fixed) | 0.500 mm @ every unoverridden rib | 0.500 mm (static — design floor, see note) |
| SW13 (Menu switch body) | from board.py (fixed) | 3.398 mm @ (70,−30)@180 | 3.398 mm |
| LED5 | from board.py (fixed) | 6.19 mm @ (70,−30)@90 | 6.19 mm |
| LED6 | from board.py (fixed) | 5.77 mm @ (70,−30)@90 | 5.77 mm |
| R29/R30/R31 | from board.py (fixed) | 9.1–12.3 mm | same |
| LED1–4, R28, SW1–SW10 (all other top-side) | from board.py (fixed) | ≥5.3 mm (worst: LED6) | same |
| Whole PCB mesh (board + every part, sanity cross-check) | `part_pcb.stl` (fixed) | 0.500 mm | 0.500 mm |
| **2. Insert + screw (not modelled as a print/assembly part in the repo — built as primitives for this check)** | | | |
| M2.5 heat-set insert (OD3.5×L4, seated in the boss socket) | **NOT modelled** — only `inserts_sim()` for the collision-gate render; same geometry reused here | 1.35 mm (every boss) | 1.35 mm (static, concentric with the boss axis, radius 1.75 < rib's own inner radius 3.6 — geometrically can never reach a rib) |
| M2.5×20 screw (shank + pan head, through the bottom column into the insert) | **NOT modelled anywhere in the repo** — no scad module draws it; built as a Ø2.5 shank + Ø5.0×1.8 head primitive for this check only | 1.35 mm (every boss) | 1.35 mm (same reasoning — radius ≤1.25, always inside the rib-free bore) |
| **3. Face caps — rest, fully pressed (−0.45 mm Z), + lateral guide slop (btn_clear/2 = 0.3 mm toward the nearest rib)** | | | |
| D-pad (rocks on its centre pivot; worst = tilt lifting the side nearest a boss) | `part_dpad.stl` (existing) | 7.27 mm | 6.996 mm |
| Button A | `part_btn_a.stl` | 6.22 mm | 6.155 mm |
| Button B | `part_btn_b.stl` | 13.82 mm | 13.62 mm |
| Button X | `part_btn_x.stl` | 15.09 mm | 14.89 mm |
| Button Y | `part_btn_y.stl` | 18.84 mm | 18.61 mm |
| Start | `part_start.stl` | 4.36 mm | 4.31 mm |
| Select | `part_select.stl` | 10.86 mm | 10.70 mm |
| **Menu** | `part_menu.stl` | 0.667 mm @ (70,−30)@90 (pre-fix: 0.563 mm) | **0.561 mm** @ (70,−30)@135 (pre-fix: **0.344 mm — FIXED**) |
| **4. L/R levers + caps, full swing (press 0→1) + lateral slop (lr_cap_clear/2 = 0.15 mm)** | | | |
| L/R caps (both) | `part_lr_caps.stl` rest + a `lr_press=1` re-render | 6.99 mm (rest) | 6.58 mm (pressed + lateral) |
| Lever L | `part_lr_lever_l.stl` rest + `lr_press=1` re-render | 3.88 mm | 3.88 mm (press barely moves it in Z; it sits well below the split, 4.3+ mm under the lowest rib tip regardless) |
| Lever R | `part_lr_lever_r.stl` + `lr_press=1` re-render | 3.88 mm | 3.88 mm |
| Power slider, full ON↔OFF travel (±0.8 mm X) | `part_power_slider.stl` + translated copies | 21.63 mm | 20.96 mm |
| **5. Display / speaker / battery** | | | |
| Display panel, glass, FPC tail fold | `part_display.stl` (existing, fixed) | 15.37 mm | 15.37 mm |
| Speaker (28 mm driver) | **not pre-exported as a reference STL** — built as a cylinder primitive from `speaker_sim()`'s own constants (spk_x/y/driver_d/t) | 12.91 mm | 12.91 mm (static) |
| Battery cell | **not pre-exported as a reference STL** — built as a box primitive from `battery_sim()`'s own constants | 19.89 mm | 19.89 mm (static) |
| Battery straps (both) | `part_straps.stl` (existing, fixed) | 32.94 mm | 32.94 mm |
| **6. Bottom shell assembled** (lip, columns, column gussets, all in one mesh) | `case_bottom.stl` (existing, fixed) | 2.10 mm | 2.10 mm (static — separated from every top rib by the full PCB thickness + the 0.5 mm tip clearance; see closing-path note) |
| **7. Closing path** (top shell descending the last 5 mm) | — analytical, see note | **= the rest-position numbers above** | — |

All numbers ≥ 0.5 mm after the fix. No clearance is silently skipped: every
category the team-lead listed has an entry, and every entry not backed by an
existing reference STL says so explicitly in the "Modelled?" column.

## Notes

- **PCB bare-sheet clearance sits exactly at the 0.5 mm floor, by design**
  (`top_boss_gusset_tip_clear = 0.5`, used verbatim) for all 31 ribs that
  were not individually overridden. This is not a violation (0.500 is not
  "under 0.5"), but it has zero margin against float/manufacturing noise —
  worth a deliberate decision, not a surprise, if anyone tightens that
  constant later.
- **Insert + screw**: geometrically, no rib can ever reach either, by
  construction — ribs start at radius `top_boss_d/2 = 3.6` mm from the boss
  axis outward, while the insert (radius 1.75) and screw (radius 1.25) are
  concentric with that same axis, strictly inside it. Confirmed numerically
  (1.35 mm at every boss) rather than assumed.
- **Closing path**: the top shell's descent onto the bottom shell is a pure
  vertical (−Z) rigid motion; everything the ribs could approach (PCB,
  bottom shell, battery, straps, speaker) is fixed to the bottom shell and
  does not move during that motion. Since the ribs are rigidly attached to
  the top shell, any position above the final seated position moves every
  rib further from those fixed parts, never closer (no XY motion occurs
  during the descent). The minimum distance during the whole closing motion
  therefore equals the final/rest clearance already measured above; this
  was confirmed by the Z-ranges (ribs lowest point ≥17.6mm i.e. flush with
  the PCB top at most, rising from there as the shell lifts), not
  re-simulated as a separate motion.
- **Fix applied**: `hardware/enclosure/enclosure.scad`
  `top_boss_gusset_overrides` gained `[70, -30.5, 90, 5.2]` (height-only
  change, reach left at the 6.6 mm default). STLs re-exported
  (`scripts/export-enclosure-stl.sh`); gates run one at a time, all PASS:
  `verify_enclosure_sync.py`, `test_enclosure_sync.py`,
  `verify_enclosure_requirements.py`, `test_enclosure_requirements.py`,
  `test_enclosure_stl_solidity.py`, `verify_enclosure_collision.py`,
  `verify_enclosure_stl.py`. Changes are left uncommitted, per instructions:
  `hardware/enclosure/enclosure.scad`, `hardware/enclosure/reference/case_top.stl`,
  `3d_case/case_top.stl`.
