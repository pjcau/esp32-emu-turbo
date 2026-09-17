---
name: enclosure-design
model: claude-sonnet-5
description: Design and modify the OpenSCAD parametric enclosure (V2) — constants contract, Z stack, button/lever geometry, display frame, and the two gates that must stay green
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: <component-or-feature> (e.g. "display", "battery", "usb-c", "levers", "caps", "bosses")
---

# OpenSCAD Enclosure Design (V2)

Design and modify the parametric 3D enclosure for the ESP32 Emu Turbo handheld.

**Argument** (optional): feature to modify (`display`, `battery`, `usb-c`, `levers`, `caps`, `bosses`, `speaker`, `ports`).

## The three rules

1. **Every dimension comes from a source, never from a guess.** V1 was printed
   from guessed numbers (a 4.0" active area, 2 mm stems, bosses that hit the
   L/R switches). Sources, in order: `scripts/generate_pcb/board.py`
   (positions, `PANEL_*` panel spec), `hardware/datasheets/` +
   `website/static/datasheets/` (component heights), `scripts/vbench/models/`
   (battery cell). Write the source next to the constant.
2. **Four gates green before you stop** (all in `make verify-all`):
   ```bash
   python3 scripts/verify_enclosure_sync.py          # constants vs board.py / datasheets / generated PCB model
   python3 scripts/verify_enclosure_requirements.py  # the USER's constraints R1-R12 (Docker: label + thin-wall export)
   python3 scripts/verify_enclosure_collision.py     # CGAL: shells vs parts, caps vs panel, panel vs PCB
   python3 scripts/verify_enclosure_stl.py           # the OTHER road: measures 3d_case/*.stl (needs a fresh export)
   python3 scripts/test_enclosure_sync.py            # mutation suites — every check must be able to fail
   python3 scripts/test_enclosure_requirements.py
   ```
   Then `make render-enclosure` and LOOK at `enclosure-top-inside.png`,
   `enclosure-top-inside-bare.png`, `enclosure-bottom-inside.png`, both
   cross-sections. A render is evidence only after the gates pass.
3. **Nothing printed is thinner than `min_wall` (1.2 mm).** Weerg rejected
   V2.1 for 0.35-1.0 mm walls (groove skin, column necks, speaker ring,
   cap flanges, straps, lever hook). R8 tabulates the named walls; R12
   slices the shells and levers in OpenSCAD (`thin_check`), erodes by
   0.6 and fails on anything left. Side walls are 2.6 (`side_wall`: 1.2
   skin + 1.2 tongue + 0.2), floor/front stay 2.0 (`wall`). Where two
   features would leave a sliver, remove one (well rings are cut through
   their bore beside the glass; LED pipes open the Menu ring outward;
   column contact faces are outer half-columns, not necks).
4. **The PCB model is generated, never drawn.** `pcb_parts.scad` comes
   from `scripts/generate_enclosure_pcb.py` (board.py placements +
   `BODY_BY_PACKAGE` heights). A new package on the board = one row in
   that table, or the generator refuses. `make generate-pcb` refreshes it;
   a stale file is a red sync gate.

## Constants contract (parsed by the sync gate)

Every `name = value;` at **column 0** of `enclosure.scad` is parsed. Values
may be numbers, earlier names, and `+ - * /` only — **no booleans, no
function calls, no `?:` at column 0** (a `true` there is a structural
error, exit 2). Vectors are read only for `screw_positions` and
`abxy_offsets` (lists of `[x, y]`). Anything else lives inside modules.

One constant per line (`a = 1;  b = 2;` on one line loses `b`). Names the
gates require (do not rename): everything in the sync gate's `need()`
calls plus the requirements gate's — in short every constant in the
blocks *body, PCB, switch, D-pad, ABXY, Start/Select, Menu, LEDs 1-6,
display (incl. `disp_ref_left/right`, `disp_glass_cx`, `disp_gap`,
`disp_tail_side`, `ext_*`), Z stack, caps, levers, screws/inserts, gussets,
ribs, ports, speaker, battery, ESP/JST, lip*. Grep `need(` in both gates
before renaming anything.

## Architecture

- **Coordinates**: enclosure origin at the body centre; Z = 0 at the back
  face. KiCad → enclosure: `enc_x = kicad_x - 80`, `enc_y = 37.5 - kicad_y`.
- **Top shell is modelled in LOCAL coords** (z = 0 front face, +z inward)
  and placed with `translate([0,0,body_d]) mirror([0,0,1])`. Text on its
  face needs `mirror([1,0,0])`. Anything in assembly coords (USB opening,
  display sim, caps) is brought into local coords with the same transform.
- **Bottom shell** is in assembly coords (z = 0 back face).

### Z stack (all from `disp_stack = disp_t + disp_riser = 7.0`)

```
Z=0     back face            Z=16    PCB bottom = split = column tops (pcb_z)
Z=2     floor                Z=17.6  PCB top; switches to 19.1 (sw_h 1.5)
Z=2-12  battery (bat_d 10)   Z=17.6-20.7 cable riser (disp_riser 3.1)
Z=10.5  J3 underside (5.5)   Z=20.7-24.6 panel (disp_t 3.9)
Z=12.9  ESP32 underside      Z=24.6  ceiling = glass top;  Z=26.6 front face
```
`top_d = pcb_d + top_int + wall`, `body_d = bot_d + top_d`. Change the
riser or the panel thickness and everything (caps, columns, frame) follows.

### Display (ILI9488 3.95" with touch — board.py `PANEL_*`)
- Panel outline 94.57 × 60.88 × 3.90; borders 2.6 sides, `disp_border_tail`
  8.5 (user measured 8-9) on the **D-pad side** (`disp_tail_side = -1`),
  `disp_border_end` 2.55. Tail U-folds under the glass (fold zone
  `disp_tail_ext` 1.8 toward SW4) into the extension board (`ext_*`, placed
  left of the FPC slot); the type-B FFC goes through the slot to J4.
- **The glass is placed, not the active area**: `disp_glass_cx` = midpoint
  between the Select cap body edge (`disp_ref_left`) and the Y cap body
  edge (`disp_ref_right`); `disp_gap` (0.47) is what is left per side. The
  active area follows (`disp_x`). Select and Y have their flange clipped
  on the glass side (`_face_cap_body(glass_side, clip_x)`). Any wider cap
  or a rim on those sides collides with the glass — the collision gate
  and R2 say so.
- **Frame**: `top_internals()` extrudes rim walls (`disp_rim_t` 1.2) from
  the ceiling to the PCB along ±Y (inset `disp_rim_inset` from the tail
  edge, clear of LED2) and two stubs on +X beside the FFC passage (cut in
  `top_shell()`); −X open for the fold.
- A **display keep-out** (glass pocket + tail zone) is subtracted from every
  internal feature, so a guide well next to the glass becomes a C-ring
  automatically (Y button, Select).

### Buttons (face) — `_face_cap_body()` + `guide_well()` + `cap_flange()`
- Cutout = nominal 2D shape (`dpad_shape`, `face_button_shape`,
  `pill_shape` in `modules/buttons.scad`); cap body = shape − `btn_clear`.
- Guide well `btn_guide_h` 3 mm under the ceiling; its end is a stepped 45°
  countersink; the cap flange is the matching stepped cone + 0.8 plate —
  both printable face-down without supports.
- `btn_stem_h = top_int − btn_guide_h − btn_flange_h − sw_h − sw_pretravel`
  (= 1.5). The gate fails if it drops below 1.0.
- D-pad: 4 stems at r = `dpad_arm_len − 3` (= board 9) + a Ø3 centre pivot
  on the PCB.

### L/R shoulder — hinged levers (`_shoulder_lever(sx)`)
The corner hole (70, 30.5) is 5 mm from SW11/SW12 (65, 32): no plunger can
be centred on the switch. Lever: face `lever_len × lever_w` (14 × 8.5)
through the floor, flange along the long sides only, nub Ø3.4 to Z = 14.3
(switch actuator at 14.5), hinge tongue (`lever_tongue_w` 5) with a snap
hook over a Ø2 rod printed between two blocks at |x| = `lever_hinge_x`
(51 — outside the battery pocket; a longer lever puts the hinge into the
cell). Every hook wall ≥ `lever_min_wall` 1.2 (R8): the print service
rejected the 3 mm tongue as thin material. Gate checks the face cutout
stays ≥ 0.3 from the counterbore and the column neck clears the switch body.

### Screws — M2.5 through the PCB holes, heat-set inserts in the top
Top boss Ø7.2 × 7 mm (`top_boss_d` = socket + 2 × `insert_wall` 2.0), a plain
cylinder, with a socket Ø3.1 × 4.5 (`insert_hole_d/depth`) for the user's M2.5 insert (HANGLIFE M2.5 x D3.5 x L4: OD 3.5, L 4.0) at
the PCB end and a Ø2.8 relief above it (`inserts_sim()` draws the four
inserts in the inside views). Bottom column Ø6,
outer HALF-column for the last 2 mm (`boss_half_h`: the contact face keeps
off the SW11/12 pads with radial, full-thickness ends — a Ø4.4 neck had a
0.8 mm wall) and 4 gussets 1.5 from the floor (`boss_gusset_*`, pointing outward and ±Y —
never toward the L/R lever flanges). M2.5 × 20 (`screw_len`): R6 checks
the tip lands in the relief.

### Battery
The fitted cell is the one the USER MEASURED: 90 × 50 × 10 (R10,
`MEASURED_CELL`), not the 80 mm family datasheet. Pocket `bat_w + 5` ×
`bat_h` × `bat_d` (95 × 50 × 10), border 8 mm (< J3's 10.5 mm underside),
corners notched at +Y for the lever hinges, lead notch on +X. The pocket
spans x −49…46: that is why the speaker seat starts at x = 48 and the L/R
hinges sit at |x| = 51 (lever face 14 mm). The sync gate checks the pocket
against EVERY bottom-side part (77) for Z clearance. No clips — the cell
is held down by two printed 1 mm straps (`bat_strap_*`) on posts at the
cell plane, outside the ESP32 footprint (0.9 mm under the module is all
there is); the PCB captures them. Gate: `z-battery-straps` + R11.

### Ports, speaker, LEDs
USB-C opening is sized for the plug **overmold** (13 × 6.5) because the
receptacle mouth is 5 mm inside the wall; it crosses the split, so the
same `usbc_opening()` is subtracted from both shells. SD has a guide shelf.
Speaker at (`spk_x`, `spk_y`) = (63, 8): top-left when looking at the
back (R5 enforces the +X/+Y quadrant and the clearances). Six LED light
pipes (`led1..6_*`), cut through the wall AND the guide-well rings.

### Labels — the rule that took three tries
Readability depends only on the glyph's XY orientation and which side the
reader stands on; a `mirror([0,0,1])` of the whole shell does NOT flip
it. The top shell's local XY == assembly XY and its face is read from +Z:
engrave glyphs **as-is**. The bottom shell's face is read from −Z:
`face_label(..., mirrored=true)` mirrors each glyph about its OWN centre.
Never mirror a group (V2.0: A/B/X/Y on the D-pad); never mirror the top
(V2.1: backwards B). R9 exports `labels_check`, counts glyphs beside every
button AND checks chirality (stem side of "B" and "L"). Judge labels from
that gate or from a `labels_check` render, never from a dark thumbnail.

## File map

| File | Purpose |
|------|---------|
| `hardware/enclosure/enclosure.scad` | constants contract, shells, caps, levers, views, `collision_check` |
| `hardware/enclosure/modules/buttons.scad` | 2D shapes, `guide_well`, `cap_flange`, cutouts |
| `hardware/enclosure/modules/display.scad` | viewport cutout, bezel |
| `hardware/enclosure/modules/ports.scad` | USB-C / SD / power / grille cutouts |
| `hardware/enclosure/modules/battery.scad` | pocket primitives |
| `hardware/enclosure/pcb_parts.scad` | GENERATED PCB model (do not edit) |
| `scripts/generate_enclosure_pcb.py` | its generator (`BODY_BY_PACKAGE` = package → L × W × H) |
| `scripts/verify_enclosure_sync.py` (+ `test_enclosure_sync.py`) | constants gate + mutation suite |
| `scripts/verify_enclosure_requirements.py` (+ `test_enclosure_requirements.py`) | user-requirements gate R1-R9 + mutation suite (Docker) |
| `scripts/verify_enclosure_collision.py` | CGAL interference gate (Docker) |
| `scripts/verify_enclosure_stl.py` | STL audit S1-S11 — slices the exported files and measures them against board.py/datasheets; caught the groove chopping 0.4 mm off the bosses, which no constant gate could see |
| `scripts/render-enclosure.sh`, `scripts/export-enclosure-stl.sh` | renders / STLs (print set → `3d_case/`) |
| `website/docs/design/enclosure.md` | the documentation — update the V1→V2 table and the dimension tables when constants change |

## Render selectors (`-D 'part="..."'`)

`assembly top bottom exploded cross_section cross_section_yz fit_check
top_inside top_inside_bare bottom_inside battery_fit boss_section pcb
collision_check labels_check case_top case_top_print case_bottom
part_display part_dpad part_btn_{a,b,x,y} part_start part_menu part_select
part_shoulder_{l,r} part_pcb part_straps part_strap_print`

## Workflow for a change

1. Find the source of the number (board.py / datasheet / vbench). Add or
   update the constant with the citation in its comment.
2. If it is a new load-bearing number, add a check to
   `verify_enclosure_sync.py` (board/datasheet truth) or a requirement to
   `verify_enclosure_requirements.py` (what the user asked for), and a
   mutation to the matching test suite. A user constraint that no gate
   enforces will be lost at the next edit.
3. Run the three gates + both mutation suites.
4. `make render-enclosure`; inspect the inside views and cross-sections.
5. `make export-enclosure-stl` (regenerates the viewer STLs and the print
   set, ends with the collision gate).
6. Update `website/docs/design/enclosure.md` tables.
