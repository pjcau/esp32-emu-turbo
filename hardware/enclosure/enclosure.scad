// ============================================================
// ESP32 Emu Turbo — Handheld Console Enclosure — V3.0
// Parametric design — all dimensions in mm
// Form factor: landscape (similar to GBA / Switch Lite)
//
// V3 (2026-10-08) — the user's review of the V2.1 shell:
//   * face caps stand 2 mm proud of the front (were 0.6) so they can be
//     found by touch, with a 1.5 mm rounded head edge — no sharp caps.
//   * L/R caps on the +Y edge, at the shell split, 2.5 mm proud —
//     Switch-Lite style shoulder buttons. They press the ON-BOARD
//     SW11/SW12 (TS-1187A on the PCB bottom, actuator facing -Z; the
//     user keeps them soldered, 2026-10-08) through a printed BELL-CRANK
//     LEVER per side: the cap pushes the lever's lower arm toward -Y, the
//     lever turns on two pins (axis along X) seated in U-slot blocks on
//     the floor, and its flat upper arm lifts the switch actuator +Z.
//     Arms 5.6 / 5.6: cap travel = switch travel, cap force = switch
//     force (160 gf), like the face buttons.
//   * speaker on the player's LEFT (D-pad side, -X): the battery pocket
//     slides +2.6 in X to make room for the Ø32 seat.
//   * shells are rounded like the Switch Lite: 11 mm corners, an 8 mm
//     fillet all round the back, a 2 mm fillet round the front; the
//     bodies are hulls of fillet slices (convex, so hull() is exact).
//   * the -Y edge openings are RECESSED into the face: USB-C in a 2 mm
//     pocket (the plug overmold seats inside the shell), and SW16's
//     1.6 mm knob — 5.1 mm inside the face, out of any finger's reach —
//     is driven by a printed SLIDER captive in the wall (flange inside,
//     tab in the lip groove). The SD card keeps the V2.1 16 x 3.5 slit
//     (the V3 finger window was reverted by the user, 2026-10-08).
//
// V2 (2026-09-16) — lessons from the first printed shell (April 2026):
//   * real panel: 94.57 x 60.88 x 3.90 mm outline, 83.52 x 55.68 active
//     (ILI9488 3.95" with resistive touch). The 8-9 mm driver-ledge
//     border (FPC tail) is on the D-PAD side; the tail U-folds under the
//     glass into the 40P extension board, whose type-B FFC crosses under
//     the panel to the PCB slot at x=47 and J4 on the back. The GLASS is
//     centred between the D-pad and the Y button cutouts (not the active
//     area), and may overhang the slot. That cable stack needs
//     disp_riser = 3.1 mm, so the top interior is exactly 7.0 mm above
//     the PCB.
//   * the top shell grows a display FRAME: rim walls from the ceiling to
//     the PCB on +Y/-Y, two stubs on +X beside the FFC opening, open on
//     -X for the tail fold. The panel is taped to the bezel from inside;
//     the frame contains it and lands on the PCB when screwed shut.
//   * top-shell bosses at the 4 PCB corner holes with sockets for M2.5
//     heat-set inserts (OD 3.5, L 3) at the PCB end — the boss is the
//     spacer to the PCB; M2.5 x 20 from the back, through the bottom
//     column and the PCB hole, into the insert.
//   * L/R are HINGED LEVERS: the corner column at (70, 30.5) is 5 mm from
//     switch SW11/SW12 at (65, 32) — no plunger can be centred there.
//   * bottom columns carry four gussets from the floor.
//   * button caps computed from the real stack (switch 1.5 mm, ceiling
//     7.0 mm above the PCB): 3 mm guide well, countersunk conical
//     flange, 1.5 mm stem — 7.9 mm total. ABXY o9, D-pad 24 x 6.5,
//     Start/Select 10 x 5, Menu 12 x 4 (LED3-6 sit 3.7 mm above it).
//     The glass (94.57) sits between the Select cap and the Y cap with
//     0.47 mm per side: those two caps have their flange clipped on the
//     glass side, and no cap can grow in X without moving a switch.
//   * PCB model GENERATED from board.py (pcb_parts.scad: all 98 fitted
//     parts with body sizes/heights) — nothing about the board is drawn
//     by hand any more.
//
// Constants contract: every `name = value;` at column 0 is parsed by
// scripts/verify_enclosure_sync.py and verify_enclosure_requirements.py
// (numbers, names, + - * / and parentheses only — no booleans, no
// function calls, no indexing at column 0). Keep it that way.
// ============================================================

use <modules/buttons.scad>
use <modules/display.scad>
use <modules/ports.scad>
use <modules/battery.scad>
include <pcb_parts.scad>   // GENERATED: pcb_outline, pcb_slot, pcb_holes, pcb_parts

// === Render control (override with -D on CLI) ===
part = "assembly";  // see RENDER SELECTOR at the bottom

// === Main enclosure parameters ===
body_w = 170;           // Width (landscape, X axis) = PCB 160 + 2x5
body_h = 85;            // Height (Y axis) = PCB 75 + 2x5
wall = 2.0;             // floor / front-face thickness
side_wall = 2.6;        // perimeter walls of both shells: 1.2 skin outside
                        // the lip groove + 1.2 lip + 0.2 clearance (Weerg
                        // flagged the old 0.7 mm skin as thin material)
min_wall = 1.2;         // print-service "thin material" threshold — every
                        // printed wall/ring/strap is >= this (gate R8)
corner_r = 11;          // plan-view corner radius (V3: 8 -> 11, Switch Lite look)
back_r = 8;             // V3: fillet all round the back face (bottom shell, Z 0..8)
front_r = 2;            // V3: fillet round the front face (top shell)
fillet_steps = 12;      // slices per quarter circle in the shell hulls

// === PCB (KiCad: 160 x 75 mm, 4-layer 1.6mm, 6mm corner radius) ===
pcb_w = 160;
pcb_h = 75;
pcb_d = 1.6;
pcb_corner_r = 6;

// === Tactile switch — C318884 = XKB TS-1187A-B-A-B (height code A) ===
sw_h = 1.5;             // body height incl. actuator (datasheet table, code A)
sw_travel = 0.25;       // datasheet "Travel 0.25mm"
sw_pretravel = 0.2;     // stem-to-actuator gap at rest (no preload)
sw_body = 5.1;          // 5.1 x 5.1 body

btn_clear = 0.6;        // diametral clearance cap body vs cutout (used by the glass rule)

// === D-pad (left) — board DPAD_ENC / DPAD_OFFSETS ===
dpad_x = -62;
dpad_y = 5;
dpad_arm_len = 12;      // stems at arm_len - 3 = 9 = board offsets
dpad_arm_w = 6.5;       // V2.1: 5 -> 6.5 (wider arms)

// === ABXY (right, diamond) — board ABXY_ENC / ABXY_OFFSETS ===
abxy_x = 62;
abxy_y = 5;
abxy_spacing = 10;      // nominal diamond radius (labels only)
abxy_diam = 9;          // V2.1: 8 -> 9. Bounded by the glass: see disp_ref_right
abxy_offsets = [
    [0, 10],     // A
    [10, 0],     // B
    [0, -10],    // X
    [-9, 0],     // Y — DFM: shifted 1mm toward centre on the board
];

// === Start/Select (below D-pad) — board SS_ENC / SS_OFFSETS ===
ss_x = dpad_x;
ss_y = dpad_y - 22;
ss_spacing = 20;
ss_w = 10;              // width bounded by the glass (Select is 5.2 mm from its edge)
ss_h = 5;               // V2.1: 4 -> 5 (taller)

// === Menu (below ABXY) — board MENU_ENC. Height stays 4: LED4/LED5 sit
// 3.7 mm above its centre and the light-pipe holes need a 0.9 mm web ===
menu_x = 62;
menu_y = -24.2;
menu_w = 12;
menu_h = 3.8;           // 3.8 (not 4): keeps a min_wall web to the LED4/LED5 pipes

// === LEDs on the PCB top — board LED_*_ENC + the 4 diagnostic LEDs ===
// (one constant per line: the gates parse column-0 `name = value;`)
led1_x = -55;           // LED1 charge
led1_y = -30;
led2_x = -48;           // LED2 full
led2_y = -30;
led3_x = 54;            // LED3..LED6 bring-up diagnostics (right of Menu)
// y -20.5 + 0.03: the Menu guide well's stepped countersink (guide_well())
// widens the bore by delta 1.2 at local z 4.4 (step i=3 of 5: sink_extra
// 1.5 * 4/5), landing its horizontal step face at y = menu_y + menu_h/2 +
// 1.2 = -21.1 -- EXACTLY the bottom of a led_diag_d/2 = 0.6 radius light-
// pipe hole centred on -20.5 (-20.5 - 0.6 = -21.1). A cylinder exactly
// tangent to another cut's flat boundary, rather than crossing it, is
// what left zero-volume two-triangle sheets in case_top.stl at that y,
// each side of LED4/LED5's x (caught by the solidity check,
// verify_enclosure_stl S12/meshcheck). +0.03 keeps the LED well inside
// its sync tolerance (0.1 mm, verify_enclosure_sync) and the S2 placement
// tolerance (0.15 mm) while clearing the tangency.
led3_y = -20.47;
led4_x = 60;
led4_y = -20.47;
led5_x = 66;
led5_y = -20.47;
led6_x = 72;
led6_y = -20.47;
led_d = 2.0;            // LED1/2 light pipe hole
led_diag_d = 1.2;       // LED3-6 (between the Menu pill and the column)

// === Brand engravings (user 2026-10-08): "GAME BRO!" above the screen on
// the top cover, "CPJ & CP 2026" low on the back face, both engraved
// brand_depth into the 2 mm walls ===
brand_front_y = 36.3;   // between the bezel top (32.1) and the front fillet (40.5)
brand_front_size = 4.5;
brand_back_y = -27;     // under the battery pocket's -Y border, between the counterbores
brand_back_size = 3;    // user 2026-10-08: "la metà" of the first 6 mm try
brand_depth = 0.6;

// === Display — ILI9488 3.95" bare panel WITH resistive touch ===
// Vendor spec (website/static/img/ili9488-datasheet-specs.png):
//   outline 60.88(W) x 94.57(H) x 3.90(T) with touch (2.60 without)
//   active   55.68(W) x 83.52(H), 40P FPC not included
disp_w = 83.52;         // ACTIVE area along X — this is the viewport
disp_h = 55.68;         // ACTIVE area along Y
disp_t = 3.9;           // panel thickness (touch version)
disp_outline_l = 94.57; // outline along X
disp_outline_w = 60.88; // outline along Y
disp_border_side = 2.6; // (60.88 - 55.68) / 2, both long sides
disp_border_tail = 8.5; // driver-ledge border at the FPC end (user: 8-9 mm)
disp_border_end = 2.55; // = 94.57 - 83.52 - disp_border_tail
disp_tail_side = -1;    // -1: tail (wide border) on the D-pad side (user 2026-09-16)
disp_clear = 0.3;       // pocket clearance per side (3D-print)
disp_riser = 3.1;       // cable space under the panel: folded tail +
                        // extension board + type-B FFC
disp_stack = 7.0;       // PCB top face -> glass top = disp_t + disp_riser
disp_rim_t = 1.5;       // frame rim wall thickness (>= min_wall)
disp_tail_w = 26;       // tail fold opening width (Y) — 40P tail ~22 mm
disp_tail_ext = 1.8;    // fold zone beyond the glass edge (toward SW4)
disp_bezel = 2.0;       // cosmetic raised bezel width on the outer face
disp_offset_y = 2;      // active-area centre Y = board DISPLAY_ENC[1]
// Glass centred between the two nearest cap BODIES — Select (right edge)
// and Y (left edge, board offset -9) — the user's rule: "well spaced from
// D-pad and ABXY, centring not required". Equal gaps of disp_gap each.
disp_ref_left = ss_x + ss_spacing/2 + ss_w/2 - btn_clear/2;   // -47.3: Select cap body edge
disp_ref_right = abxy_x - 9 - abxy_diam/2 + btn_clear/2;      // 48.8: Y cap body edge
disp_glass_cx = (disp_ref_left + disp_ref_right) / 2;         // 0.75
disp_gap = (disp_ref_right - disp_ref_left - disp_outline_l - 2*disp_clear) / 2;  // 0.465
disp_rim_inset = 1.5;   // long rim walls start this far in from the tail edge (LED2 is there)
disp_x = disp_glass_cx - disp_tail_side * (disp_border_tail - disp_border_end) / 2;  // active centre
// 40P extension board (R37 workaround) under the panel, BEFORE the slot
// — sizes are placeholders until measured; the requirements gate keeps
// the box inside the glass footprint, left of the slot, under the riser.
ext_l = 28;
ext_w = 24;
ext_t = 3.0;
ext_gap = 1.0;          // gap between the board and the slot edge

// === Shell split / Z stack ===
top_int = disp_stack;             // top shell interior above the PCB top
bot_d = 16;                       // bottom shell depth: PCB bottom face
top_d = pcb_d + top_int + wall;   // 10.6
body_d = bot_d + top_d;           // 26.6
pcb_z = bot_d;                    // PCB bottom face sits on the columns
z_pcb_top = pcb_z + pcb_d;        // 17.6
z_ceiling = z_pcb_top + top_int;  // 24.6 = inner face of the front wall
z_sw_top = z_pcb_top + sw_h;      // 19.1

// === Z-axis stack (closed assembly, Z=0 = back face) ===
// Z=0        back face             Z=16    PCB bottom = split = column tops
// Z=2        floor                 Z=17.6  PCB top; switches to 19.1
// Z=2-12     battery (10)          Z=17.6-20.7 cable riser (3.1)
// Z=10.5-16  J3 JST (5.5)          Z=20.7-24.6 panel glass (3.9)
// Z=12.9-16  ESP32 module (3.1)    Z=24.6  ceiling;  Z=26.6 front face

// === Face button caps (computed from the Z stack) ===
btn_face_h = 2.0;       // cap face proud of the front surface (V3: 0.6 -> 2.0,
                        // "devono fuoriuscire circa 2 mm" — found by touch)
btn_face_r = 1.5;       // rounded head edge (V3: "smussati, non spigolosi")
btn_guide_h = 3.0;      // guide well under the ceiling
btn_flange_extra = 1.2; // flange radial growth beyond the body
btn_flange_cone_h = 1.5;// conical part (in the countersink)
btn_flange_h = 1.2;     // flat flange plate (>= min_wall)
btn_stem_d = 3.0;       // actuator stem (switch plunger is 2.0)
btn_stem_h = top_int - btn_guide_h - btn_flange_h - sw_h - sw_pretravel; // 1.1
btn_cap_h = btn_face_h + wall + btn_guide_h + btn_flange_h + btn_stem_h;  // 7.9 (flange grew, stem shrank)
btn_well_t = 1.5;       // guide well ring thickness
dpad_pivot_d = 3.0;     // D-pad rocks on a centre pivot resting on the PCB
dpad_pivot_h = top_int - btn_guide_h - btn_flange_h;                      // 3.2

// === Screws — M2.5 through the PCB's 4 corner holes (drill 2.5, NPTH) ===
screw_d_outer = 6;      // bottom column OD, 1.6 mm wall around the bore
screw_d_inner = 2.8;    // M2.5 clearance through the bottom column
screw_boss_h = bot_d - wall;   // 13.4: column top = PCB seat
boss_half_h = 2.0;      // the last 2 mm under the PCB are the OUTER half
                        // of the column only (cut through the axis): the
                        // contact face keeps clear of the SW11/SW12 body
                        // and pads and of the TF-01A housing next to the
                        // holes, with no thin sliver (the old o4.4 neck had
                        // a 0.8 mm wall)
boss_gusset_n = 4;      // V2.1: gussets from the floor around each column
boss_gusset_t = 1.5;
boss_gusset_r = 6.0;    // reach from the column axis at the floor
boss_gusset_h = 8.0;    // height on the column
m25_head_d = 5.0;       // pan head o4.5 + clearance (counterbore)
m25_head_depth = 1.8;
screw_len = 20;         // M2.5 x 20: tip at Z = 1.8 + 20 = 21.8, inside the relief
// === Top bosses with M2.5 heat-set inserts — the user's part is HANGLIFE
// "M2.5 x D3.5 x L4" (amazon B0CS6YVJYD): OD 3.5, length 4.0; "2 mm of
// plastic around it for robustness" ===
insert_od = 3.5;        // knurled OD
insert_l = 4.0;         // length (listing: "larghezza 3.5 mm e lunghezza 4.0 mm")
insert_hole_d = 3.1;    // socket (OD - 0.4, PLA/PETG heat-set)
insert_hole_depth = insert_l + 0.5;   // 4.5: flush insert + 0.5
insert_relief_d = 2.8;  // bore above the insert for the screw tip
insert_relief_h = 2.0;  // socket + relief = 6.5 of the 7 mm boss; 0.5 boss
                        // + 2.0 front wall stay closed. M2.5x20 tip at Z 21.8
                        // = 0.2 past the insert end (21.6): full 4 mm engagement
insert_wall = 2.0;      // plastic around the socket (user's request)
top_boss_d = insert_hole_d + 2 * insert_wall + 0.1;   // 7.2

// === Top-boss gussets (user 2026-10-10): "the 4 cylinders of the top
// cover must be reinforced with flanges that attach them to the layer" —
// "layer" clarified as the INNER SURFACE of the top shell, the ceiling
// top_internals' own root (z=0 in its frame) where the boss cylinders
// are rooted. Triangular fillet, same gusset() module and thickness
// class as the existing bottom-column gussets, own reach/height
// parameters (own name too) because the top boss is a different size
// (Ø7.2) inside a shorter shell (top_int = 7.0 total, vs the bottom
// column's much taller screw_boss_h).
// Height: NOT bounded by the insert socket -- the heat-set insert sits
// INSIDE the bore (radius insert_hole_d/2 = 1.55); a gusset on the
// OUTSIDE of the boss wall (from top_boss_d/2 = 3.6 outward) can never
// narrow that socket's mouth, however tall it is. The real limit is the
// boss's own FAR END (the free "tip", at local z = top_int, flush with
// the PCB-side insert flange and the soldering-iron clearance): the rib
// stops top_boss_gusset_tip_clear short of it. Within that bound, h is
// set to the LARGEST value that keeps >= 0.5 mm clear of every FIXED PCB
// top-side component near each boss -- checked, not assumed: the
// nearest top-side part to ANY of the 4 bosses is >= 10 mm away centre
// to centre (SW13/Menu and LED5/6 near the back-right boss; nothing
// closer at the other 3), well outside this rib's own XY reach
// (top_boss_gusset_r = 6.6 from the axis), so every boss gets the same,
// maximum height against FIXED parts -- verify_enclosure_collision (0
// interferences) plus a per-rib mesh clearance sweep are the actual
// proof, not this comment.
//
// Fixed parts are not the whole story: the team-lead's 2026-10-10 full-
// parts clearance audit (hardware/enclosure/preview-v3/mesh-diff/
// clearances.md) mesh-measured every one of the 32 ribs against every
// MOVING part too (caps at full travel + lateral guide slop) and found
// a second rib the "nearest fixed component" argument above does not
// cover: back-right boss (70,-30.5), angle 90 (truly north, NOT the 135
// NW rib below) reaches to within 2.9 mm of the Menu cap's flange
// corner at full h/r -- closer than the already-overridden 135 rib --
// because the Menu cap's flange is a far bigger target than any PCB
// component near that boss. Overridden below (r kept at the default
// 6.6, h alone lowered to 5.2; a reach cut was not needed here because,
// unlike the 135 rib, this rib's closest approach is at its TAPERED
// outer tip, not at its full-height root, so h alone moves it).
top_boss_gusset_t = 1.5;        // == boss_gusset_t (bottom columns): same
                                // style and thickness, both >= min_wall
top_boss_gusset_r = top_boss_d/2 + 3.0;   // 6.6: reach from the AXIS (same
                                // convention as boss_gusset_r), i.e. 3.0 mm
                                // beyond the boss surface — the nearest
                                // obstacle (ABXY-A well, front-right boss)
                                // is >= 17 mm away centre to centre;
                                // verified by verify_enclosure_collision,
                                // not assumed
top_boss_gusset_tip_clear = 0.5; // the user's minimum, to the boss's own
                                // free end (tip), not the insert socket
top_boss_gusset_h = top_int - top_boss_gusset_tip_clear; // 6.5
top_boss_gusset_n = 8;          // ribs per boss (R16, >= 3): ALL AROUND
                                // the cylinder ("le vorrei tutte attorno
                                // dei cilindri", user 2026-10-10), evenly
                                // spaced every 360/n deg from +X -- no
                                // longer limited to the outward quadrant.
                                // Any rib found to reach a PCB component,
                                // the frame or a guide well is shortened
                                // or lowered INDIVIDUALLY (see the
                                // per-boss override below), never
                                // dropped silently.
top_boss_gusset_overrides = [
    // [boss_x, boss_y, angle_deg, h, r] -- one entry per rib that cannot
    // take the full top_boss_gusset_h/_r; angle_deg must match 360*i/n
    // exactly; r defaults to top_boss_gusset_r when omitted.
    //
    // The back-right boss (70,-30.5), angle 135 (NW, toward the Menu
    // cap): at the full height/reach it reaches into part_menu.stl's
    // flange. "No volume overlap" alone is NOT the user's bar -- the
    // Menu cap is a MOVING part (switch travel 0.45, lateral guide slop
    // btn_clear/2 = 0.3) and the requirement is >= 0.5 mm clear in every
    // position, mesh-measured (trimesh closest_point, both directions,
    // not just the boolean intersection volume):
    //   at full h=6.5, r=6.6:            rest clearance   0.230 mm
    //   lowering h alone to 4.0 (r=6.6):  rest clearance   0.230 mm too
    //     -- the rib's WIDEST cross-section sits at its ROOT (z=0, the
    //     ceiling), which does not move with h; height alone cannot fix
    //     a root-level clash, only a reach (r) change can.
    //   shortening r alone to 5.0 (h=6.5): rest clearance  0.392 mm -- still short
    //   r=5.0 AND h=4.0: rest 0.779 mm; worst case (lateral rattle
    //     toward the rib, no press) 0.543 mm; pressed + lateral 0.561 mm
    //     -- pressing moves the flange DOWN away from the ceiling-rooted
    //     rib, so it only helps; lateral rattle is the real risk and
    //     0.543 mm clears the 0.5 mm bar with margin. Kept.
    [70, -30.5, 135, 4.0, 5.0],
    //
    // Same boss, angle 90 (true north -- the full-parts sweep, not the
    // comment above, is what found this one; it is CLOSER to the Menu
    // cap than the 135 rib just above, despite pointing further away
    // from it on paper, because its full r=6.6 outer tip lands almost
    // under the flange's top-right corner):
    //   at full h=6.5, r=6.6:  rest 0.563 mm; worst (press 0.45 +
    //     lateral 0.3 toward the rib, both at once -- a pressed cap can
    //     sit at either edge of its own guide slop) 0.344 mm -- UNDER
    //     the 0.5 mm bar.
    //   r alone to 6.0 (h=6.5): worst only 0.517 mm -- margin too thin.
    //   h alone to 5.5 (r=6.6):  worst 0.492 mm -- still short.
    //   h alone to 5.2 (r=6.6):  rest 0.667 mm; worst 0.562 mm -- clears
    //     with a margin similar to the 135 rib above. r is left at the
    //     default: unlike the 135 rib (whose clash is at the full-height
    //     ROOT, which h cannot move), this rib's closest point to the
    //     cap sits on the sloped outer face near the tapered tip, where
    //     the gusset() triangle's hypotenuse runs from (r1, ceiling) to
    //     (r0, h deep) -- lowering h alone raises that whole sloped face
    //     toward the ceiling (away from the cap, which sits well below
    //     it), so h alone is enough; no reach cut needed. Kept.
    [70, -30.5, 90, 5.2],
];

// === Screw positions = PCB corner holes (board MOUNT_HOLES_ENC) ===
screw_positions = [
    [-body_w/2 + 15, body_h/2 - 12],    // Front-left  (-70,  30.5)
    [body_w/2 - 15, body_h/2 - 12],     // Front-right ( 70,  30.5)
    [-body_w/2 + 15, -body_h/2 + 12],   // Back-left   (-70, -30.5)
    [body_w/2 - 15, -body_h/2 + 12],    // Back-right  ( 70, -30.5)
];

// === PCB edge support ribs (bottom shell) ===
rib_w = 6;
rib_reach = 1.5;        // under the PCB edge
rib_clear = 0.3;
rib_positions = [
    [-40, 1], [40, 1],          // top edge (y > 0)
    [-25, -1], [25, -1],        // bottom edge, between the ports
];
rib_side_y = 0;         // one rib per short side at y = 0

// === USB-C port (bottom edge, centre) — opening sized for the PLUG
// overmold: the receptacle mouth is at the PCB edge, 5 mm inside ===
// V3: the opening sits in a RECESS pocket in the face (user: ">= 2 mm")
// so the overmold seats inside the shell; a pad on the inner wall face
// keeps >= min_wall of plastic under the pocket floor (J1 body front is
// at y -37.3, the pad ends at -38.9).
usbc_x = 0;
usbc_z = bot_d - 1.6;
usbc_cut_w = 13;
usbc_cut_h = 6.5;
usbc_recess_d = 2.0;    // pocket depth into the face
usbc_recess_w = 17;
usbc_recess_h = 9;
usbc_pad_t = usbc_recess_d + min_wall - side_wall + 1.0;   // 1.6 inward of the wall:
                        // in the lip-groove zone the pad stands alone (the
                        // skin outside the groove is cut by the recess), so
                        // it must be >= min_wall by itself

// === SD card slot (bottom edge, right) — TF-01A at board SD_ENC ===
// The V2.1 card SLIT, cut through the bottom-shell wall only. V3 tried a
// 20 mm finger window up into the top shell; the user reverted it to
// this slit on 2026-10-08 (gate R13 pins the revert). Housing front =
// SD_ENC y - 7.5 (14.5 x 15 body); latched card protrudes sd_card_out.
sd_x = 60;
sd_z = bot_d - 1.8;
sd_cut_w = 16;
sd_cut_h = 3.5;
sd_shelf_top = 13.3;
sd_card_out = 1.3;      // latched card beyond the housing front (typical push-push)
sd_housing_front = 37.0;// |y| of the TF-01A housing front = SD_ENC 29.5 + 15/2 (sync gate)
sd_card_reach = body_h/2 - (sd_housing_front + sd_card_out);   // 4.2: face -> card end

// === Power switch (bottom edge, left of USB-C) — MSK12C02 at board
// PWR_SWITCH_ENC, bottom side. Datasheet SW16_Slide-Switch_C431540.pdf:
// body 8 x 2.8 x 1.4 (3.7 with feet), knob 1.6 wide, 1.5 long, travel
// 1.6. Knob tip = -34.5 - 1.4 - 1.5 = -37.4: 5.1 mm inside the face,
// 1 mm tall — unreachable by a finger (user: "da calcolare di modo che si
// possa realmente switchare"). V3: a printed SLIDER captive in the wall
// (flange inside, tab in the lip groove) carries the knob out to a nub
// on the face; its slot is open to the split and bridged by the lip.
pwr_sw_x = -40;
pwr_sw_z = bot_d - 2.0;
pwr_cut_w = 8;          // (kept for the sync gate)
pwr_cut_h = 3.2;
pwr_knob_w = 1.6;       // MSK12C02 knob width (X)
pwr_knob_tip_y = -37.4; // knob tip (assembly Y)
pwr_knob_root_y = -35.9;// knob root = body face
pwr_knob_z = 15.3;      // knob centre height (bottom-side part, 1 mm knob)
pwr_travel = 1.6;       // datasheet full travel
pwr_nub_w = 4;          // slider nub on the face (X)
pwr_nub_h = 3.0;        // nub height (Z)
pwr_nub_proud = 1.0;    // nub above the face
pwr_slot_w = pwr_nub_w + pwr_travel + 0.4;   // 6.0
pwr_slot_z0 = 12.4;     // slot bottom; the slot is open to the split (bot_d)
pwr_trough_w = 10;      // shallow finger trough round the slot
pwr_trough_d = 0.6;
pwr_trough_z0 = 12.0;
pwr_fl_w = 10;          // slider flange (X): covers the slot at both ends of travel
pwr_fl_z0 = 11.2;       // flange bottom (>= 1.2 below the slot)
pwr_fl_t = 1.2;         // flange thickness (Y), against the inner wall face
pwr_fork_t = 1.2;       // fork arm thickness (X)
pwr_fork_z0 = 14.3;     // fork arms Z 14.3 .. 15.8 (PCB bottom at 16)
pwr_fork_z1 = 15.8;
pwr_tab_w = 4;          // tab up into the lip groove (X)
pwr_tab_h = 1.4;        // tab height above the split (groove is 2 deep)
pwr_notch_w = 6;        // tongue notch for the tab (travel + 2 x 1.2 clearance)
// Horizontal GUIDE for the slider (user 2026-10-08): a block on the inner
// wall face with a channel the flange runs in — the lip in front holds
// the flange against the wall, the channel ends are the stops. Open at
// the top: the slider drops in from above (nub down the slot, tab into
// the tongue notch), then the PCB brings the SW16 knob down between the
// fork arms. Travel to switch ON<->OFF = the datasheet's 1.6 mm, the
// switch's own detents are the real stops; the channel gives +0.3 each way.
pwr_guide_w = 16;       // guide block (X)
pwr_guide_z0 = 10.0;    // guide block bottom
pwr_guide_z1 = 13.8;    // guide block top: under the SW16 body (Z 14) and the fork arms
pwr_guide_d = 2.9;      // block depth inward from the wall face (to y -37.0, under the PCB edge)
pwr_chan_d = pwr_fl_t + 0.1;                           // 1.3: channel depth, flange + play
pwr_chan_half = pwr_fl_w/2 + pwr_travel/2 + 0.3;       // 6.1: channel half-length = stops
pwr_guide_lip = pwr_guide_d - pwr_chan_d;              // 1.6: lip in front of the flange
pwr_guide_stop = pwr_guide_w/2 - pwr_chan_half;        // 1.9: end stop thickness

// === L/R shoulder buttons — cap on the +Y edge + bell-crank lever ===
// SW11/SW12 stay on the board (TS-1187A code A, actuator o2 facing -Z,
// tip sw_h below the PCB, cover sw_cover_h below it). The cap slides in
// -Y through a window at the split; behind its flange a printed lever per
// side turns on pins along X:
//   lower arm  — a bump on its +Y face touches the flange back at Z
//                lr_bump_z (5.6 below the pivot): the cap pushes it -Y
//   upper arm  — flat, its top lr_arm_top = actuator tip - pretravel,
//                runs -Y under the actuator (5.6 from the pivot) and
//                lifts it +Z when the lever turns
//   pins       — o2 at the beam ends, dropped into U-slot blocks fused to
//                the inner wall; the lever top is one plane (Z 14.3), so
//                it prints upside down with no support
// The PCB above and the actuator itself keep the lever in its slots.
lr_x = 57.5;            // cap centre |X| (pads at 65, column at 70)
lr_axis_z = 12.0;       // cap centre Z: cap Z 8 .. 16, top edge AT the split
lr_sw_x = 65;           // SW11/SW12 centre |X| (board SHOULDER_*_ENC)
lr_sw_y = 32;           // SW11/SW12 centre Y
sw_cover_h = 1.2;       // TS-1187A cover face below the PCB (datasheet: 1.2)
lr_cap_w = 14;          // cap face (X)
lr_cap_h = 8;           // cap face (Z) — Z 8 .. 16, top edge AT the split
lr_cap_proud = 2.5;     // beyond the wall face (user: "2-3 mm")
lr_cap_r = 1.5;         // rounded outer edges
lr_cap_clear = 0.3;     // diametral, cap body vs window
lr_fl_t = 1.2;          // inner flange thickness (Y)
lr_fl_extra = 1.2;      // flange beyond the body on 3 sides (not the top)
lr_fl_gap = 0.05;       // flange face to the inner wall face (no coplanar contact)
lr_fl_back_y = body_h/2 - side_wall - lr_fl_gap - lr_fl_t;     // 38.65: flange back face
lr_arm_top = pcb_z - sw_h - sw_pretravel;      // 14.3: lever top plane (rest)
lr_piv_y = 37.6;        // pivot axis Y (under the PCB edge, behind the flange)
lr_piv_z = lr_arm_top - 1.0;                   // 13.3: pin top on the top plane
lr_pin_d = 2.0;
lr_slot_w = 2.3;        // U-slot width (pin + 0.3)
lr_beam_y0 = 35.5;      // beam along X joining the pins and both arms
lr_beam_y1 = 37.9;      // 0.3 short of the flange at full travel
lr_beam_z0 = 11.6;
lr_beam_x0 = 49.3;      // beam |X| span between the two blocks (0.4 end float)
lr_beam_x1 = 66.9;
lr_arm_w = 3.0;         // upper arm width (X), centred on the switch
lr_arm_y_end = lr_sw_y; // upper arm end edge ON the actuator centre line: a
                        // tilted flat arm touches first at its end edge, so the
                        // push is centred and the arm is exactly lr_r_out long;
                        // nothing of the arm lies beyond the actuator, so at full
                        // travel no point of it rises above the actuator tip
                        // (still 0.05 proud of the cover: 1.5 - 1.2 - 0.25)
lr_arm_z0 = 12.6;
lr_in_w = 4.0;          // lower arm width (X), centred on the cap
lr_in_y0 = 36.4;
lr_in_y1 = 38.0;
lr_in_z0 = 7.0;
lr_bump_r = 0.6;        // half-round bump along X on the lower arm's +Y face
lr_bump_z = lr_piv_z - (lr_piv_y - lr_sw_y);   // 7.7: equal arms (5.6 / 5.6)
lr_bump_gap = lr_fl_back_y - (lr_in_y1 + lr_bump_r);   // 0.05 to the flange at rest
lr_blk_t = 2.0;         // pivot block thickness (X)
lr_blk_gap = 0.4;       // beam end to block face (end float)
lr_blk_wall = 1.4;      // slot wall on the -Y side (the +Y side is fused to the shell wall)
lr_blk_top = pcb_z - 0.6;                      // 15.4: 0.6 under the PCB (off the 15.5 audit slice)
lr_label_y = 30;        // "L"/"R" engraved on the flat back face beside the lever
// derived: lever ratio and the swing at full switch travel
lr_r_out = lr_piv_y - lr_sw_y;                 // 5.6: pivot -> actuator
lr_r_in = lr_piv_z - lr_bump_z;                // 5.6: pivot -> cap contact
lr_theta = (sw_pretravel + sw_travel) / lr_r_out;          // rad at full travel
lr_cap_travel = lr_theta * lr_r_in;                        // 0.45
lr_press = 0;           // RENDER ONLY: 0 = rest, 1 = switch fully pressed

// === Speaker (28 mm driver, off-board, seats on the floor) ===
// User 2026-10-07: "la cassa a sinistra" = the player's LEFT = the D-pad
// side (-X), where board.py's SPEAKER_ENC silk marker also sits. Seat
// r16 at x -62.5 clears the pocket border (x -46.5 after the +2.6 pocket
// shift), the column (-70, 30.5) and the back fillet: the driver edge
// (x -76.5) stays inside the inner floor outline (inset back_r = 8 ->
// x -77).
spk_x = -62.5;
spk_y = 8;
spk_diam = 22;          // grille pattern over the radiating cone
spk_driver_d = 28;
spk_driver_t = 5;
spk_seat_t = 1.5;
spk_seat_od = 32;       // 1.7 mm ring wall around the o28.6 seat

// === Battery pocket — the FITTED cell, measured by the user 2026-09-16:
// 90 x 50 x 10 mm (length incl. the tab/PCM end; the 105080 family
// datasheet says 80 for the bare cell). Pocket = bat_w + 5 x bat_h x bat_d.
bat_w = 90;             // length (X) — measured
bat_h = 50;             // width (Y) — measured
bat_d = 10;             // thickness (Z) — measured
bat_offset_x = 2.6;     // pocket x -45 .. 50 (border to -46.5 / 51.5): the
                        // speaker seat starts at -46.5, the R switch cradle
                        // at x >= 52 (V3: was -1.5 with the speaker on +X)
bat_offset_y = 5;       // pocket y -20 .. 30: clear of J3 (y <= -20.7)
bat_border_w = 1.5;
bat_border_h = 8;       // < 8.5 so J3 (Z 10.5..16) never meets the border
bat_lead_notch_w = 8;
bat_lead_notch_y = -14;
bat_corner_notch = 2.5; // +Y corners of the border cut back (lead routing)
// Battery hold-down (user 2026-09-16: "vincolare la batteria per non
// andare contro il bottom del PCB"). The cell top (Z 12) is 0.9 mm from
// the ESP32 underside (12.9), so only a 1 mm strap fits: two printed
// straps (bat_strap_w x bat_strap_t) at X positions outside the module
// footprint, pegged into four posts on the pocket border; the PCB above
// captures them. The sync gate checks straps and posts against every
// bottom-side part.
bat_strap_x1 = -30;     // strap 1 (X) — clear of the ESP32 (x ±12.75)
bat_strap_x2 = 26;      // strap 2 (X)
bat_strap_w = 5;
bat_strap_t = 1.2;      // Z 12 .. 13.2: parts above are >= 13.7 (gate)
bat_post_w = 8;         // post along X
bat_post_t = 5.2;       // post along Y (outside the border wall): 1.25 mm
                        // walls beside the o2.7 peg hole
bat_post_h = bat_d;     // post top = cell top plane (Z 12)
bat_peg_d = 2.4;        // strap pegs into Ø(peg + 0.3) holes in the posts
bat_peg_h = 3;

// === Tall bottom-side parts kept as named constants for the sync gate
// (cross-checked against pcb_parts.scad / board.py) ===
esp_w = 25.5;           // ESP32-S3-WROOM-1 (datasheet 25.5 x 18.0 x 3.1)
esp_h = 18.0;
esp_d = 3.1;
esp_x = 0;              // board ESP32_ENC
esp_y = 10;
jst_x = -0.25;          // board JST_BAT_ENC — S2B-PH-SM4-TB
jst_y = -25;
jst_w = 7.9;            // JST p.4: B = 7.9 (2 circuits)
jst_h = 8.6;            // 6.0 body + 2.6 mouth
jst_d = 5.5;            // JST p.4: side entry height 5.5

// === Alignment lip (tongue on bottom shell -> inside top shell) ===
lip_h = 2.0;
lip_t = 1.2;            // tongue thickness (>= min_wall)
lip_clearance = 0.2;    // wall - lip_t - clearance = 1.2 skin outside the groove

echo(str("V3.0 stack: body_d=", body_d, " top_int=", top_int,
         " btn_stem_h=", btn_stem_h, " btn_cap_h=", btn_cap_h,
         " glass_cx=", disp_glass_cx, " disp_x=", disp_x,
         " lr_axis_z=", lr_axis_z, " lr_ratio=", lr_r_out / lr_r_in,
         " lr_cap_travel=", lr_cap_travel,
         " sd_card_reach=", sd_card_reach));

// ============================================================
// Primitives / geometry helpers
// ============================================================
module rounded_rect(w, h, r) {
    offset(r=r) offset(r=-r) square([w, h], center=true);
}

// V3 shell bodies: a rounded-rect prism whose z=0 edge is filleted with
// radius rf — the hull of fillet_steps thin slices (every slice is a
// convex rounded rect, so the hull IS the filleted solid). Plan size w x
// h, corner radius rc, total height ht. rf = 0 -> plain prism.
module filleted_prism(w, h, rc, ht, rf, steps=fillet_steps) {
    hull() {
        if (rf > 0)
            for (i = [0 : steps]) {
                t = 90 * i / steps;
                z = rf - rf * cos(t);
                inset = rf - rf * sin(t);
                translate([0, 0, z])
                linear_extrude(height=0.01)
                rounded_rect(w - 2 * inset, h - 2 * inset, max(0.5, rc - inset));
            }
        else
            linear_extrude(height=0.01) rounded_rect(w, h, rc);
        translate([0, 0, ht - 0.01]) linear_extrude(height=0.01) rounded_rect(w, h, rc);
    }
}

// The cavity of a filleted shell: inset side_wall at the sides, floor
// thickness `floor`, inner fillet radius rf - side_wall about the same
// corner centre (wall >= floor everywhere, = side_wall on the flanks).
module filleted_cavity(w, h, rc, floor, ht, rf) {
    ri = rf - side_wall;
    if (ri > 0.2)
        hull() {
            for (i = [0 : fillet_steps]) {
                t = 90 * i / fillet_steps;
                z = floor + ri - ri * cos(t);
                inset = side_wall + ri - ri * sin(t);
                translate([0, 0, z])
                linear_extrude(height=0.01)
                rounded_rect(w - 2 * inset, h - 2 * inset, max(0.5, rc - inset));
            }
            translate([0, 0, ht]) linear_extrude(height=0.01)
            rounded_rect(w - 2 * side_wall, h - 2 * side_wall, max(0.5, rc - side_wall));
        }
    else
        translate([0, 0, floor])
        linear_extrude(height=ht - floor + 0.01)
        rounded_rect(w - 2 * side_wall, h - 2 * side_wall, max(0.5, rc - side_wall));
}

// 2D rounded rectangle for the edge caps / slider nub
module rrect2d(w, h, r) { rounded_rect(w, h, min(r, w/2 - 0.01, h/2 - 0.01)); }

// Extrude a 2D shape to height ht and round its TOP edge with radius r
// (stacked inward offsets following a quarter circle): the "smussato"
// head of every V3 cap. children(0) = the outline.
module rounded_top_extrude(ht, r, steps=8) {
    linear_extrude(height=ht - r + 0.01) children(0);
    for (i = [0 : steps - 1]) {
        z0 = ht - r + r * sin(90 * i / steps);
        z1 = ht - r + r * sin(90 * (i + 1) / steps);
        translate([0, 0, z0])
        linear_extrude(height=z1 - z0 + 0.01)
        offset(r=-(r - r * cos(90 * (i + 1) / steps))) children(0);
    }
}

// Panel outline pocket (glass + clearance), 2D. Glass is centred at
// disp_glass_cx; the active area sits disp_x.
function panel_x0() = disp_glass_cx - disp_outline_l/2 - disp_clear;
function panel_x1() = disp_glass_cx + disp_outline_l/2 + disp_clear;
function panel_y0() = disp_offset_y - disp_outline_w/2 - disp_clear;
function panel_y1() = disp_offset_y + disp_outline_w/2 + disp_clear;
function slot_y0() = pcb_slot[1] - pcb_slot[3]/2;
function slot_y1() = pcb_slot[1] + pcb_slot[3]/2;
function slot_x0() = pcb_slot[0] - pcb_slot[2]/2;
// extension board box (assembly coords): left of the slot, under the glass
function ext_x1() = slot_x0() - ext_gap;
function ext_x0() = ext_x1() - ext_l;

module panel_pocket_shape() {
    translate([panel_x0(), panel_y0()])
    square([panel_x1() - panel_x0(), panel_y1() - panel_y0()]);
}

// USB-C plug opening, ASSEMBLY coords (crosses the shell split); through
// the wall AND the V3 recess pad behind it
module usbc_opening() {
    translate([usbc_x, -body_h/2 - 0.1, usbc_z])
    rotate([-90, 0, 0])
    usbc_cutout(usbc_cut_w, usbc_cut_h, side_wall + usbc_pad_t + 0.2);
}

// ---- V3 -Y edge features, ASSEMBLY coords (they cross the shell split) ----
// extrude a 2D profile drawn in the XZ plane (local x = X, local y = Z)
// from y0 to y1
module xz_extrude(y0, y1) {
    translate([0, y1, 0]) rotate([90, 0, 0]) linear_extrude(height=y1 - y0) children();
}
// USB-C: a pad thickening the wall inside (added), the recess pocket in
// the face and the plug opening (subtracted)
module usbc_pad() {
    translate([usbc_x - (usbc_recess_w + 2*min_wall)/2, -body_h/2 + side_wall - 0.01,
               usbc_z - (usbc_recess_h + 2*min_wall)/2])
    cube([usbc_recess_w + 2*min_wall, usbc_pad_t + 0.01, usbc_recess_h + 2*min_wall]);
}
// (the lip tongue is notched over the recess width: the recess removes
// the skin outside the groove there, so a tongue would stand alone)
module usbc_recess() {
    translate([usbc_x, 0, usbc_z]) xz_extrude(-body_h/2 - 0.1, -body_h/2 + usbc_recess_d)
    rrect2d(usbc_recess_w, usbc_recess_h, 2);
    translate([usbc_x - usbc_recess_w/2 - 0.2, -body_h/2 - 0.1, bot_d - 0.01])
    cube([usbc_recess_w + 0.4, side_wall + 0.2, lip_h + 0.1]);
}
// Power slider: trough in the face, slot through the wall (open to the
// split), notch in the lip tongue for the slider's tab
module pwr_cuts() {
    translate([pwr_sw_x - pwr_trough_w/2, -body_h/2 - 0.1, pwr_trough_z0])
    cube([pwr_trough_w, pwr_trough_d + 0.1, bot_d - pwr_trough_z0 + 0.1]);
    translate([pwr_sw_x - pwr_slot_w/2, -body_h/2 - 0.1, pwr_slot_z0])
    cube([pwr_slot_w, side_wall + 0.2, bot_d - pwr_slot_z0 + 0.1]);
    translate([pwr_sw_x - pwr_notch_w/2, -body_h/2 - 0.1, bot_d - 0.01])
    cube([pwr_notch_w, side_wall + 0.2, lip_h + 0.1]);
}
// L/R cap windows in the +Y wall: rounded below, open to the split above
// (the lip tongue and the top shell bridge them)
module lr_windows() {
    for (sx = [-1, 1])
        translate([sx * lr_x, 0, lr_axis_z])
        xz_extrude(body_h/2 - side_wall - 0.1, body_h/2 + 0.1) {
            rrect2d(lr_cap_w + lr_cap_clear, lr_cap_h + lr_cap_clear, 2 + lr_cap_clear/2);
            translate([-(lr_cap_w + lr_cap_clear)/2, 0])
            square([lr_cap_w + lr_cap_clear, bot_d - lr_axis_z + 0.01]);
        }
}

// Engraved label at (x, y). Readability depends only on the glyph's XY
// orientation and which side the reader stands on: the TOP shell's face
// is read from +Z (assembly) and its local XY == assembly XY, so the
// glyph is engraved as-is; the BOTTOM shell's face is read from -Z, so
// each glyph is mirrored about its OWN centre (never the whole group —
// V2.0 put A/B/X/Y on the D-pad that way; V2.1 mirrored the top and
// printed a backwards B). Gate R9 checks position AND chirality.
module face_label(x, y, txt, size, mirrored=false) {
    translate([x, y, -0.1])
    mirror([mirrored ? 1 : 0, 0, 0])
    button_label(txt, size, 0.4);
}

// Brand text engraved brand_depth deep at (x, y); the back one is mirrored
// about its own centre (read from -Z), like the bottom labels
module brand_text(x, y, txt, size, mirrored=false) {
    translate([x, y, -0.1])
    mirror([mirrored ? 1 : 0, 0, 0])
    linear_extrude(height=brand_depth + 0.1)
    text(txt, size=size, halign="center", valign="center", font="Liberation Sans:style=Bold");
}

// Stepped 45° gusset (wedge) from a column: full height at radius r0,
// zero at radius r1, thickness t, pointing along +x before rotation.
module gusset(r0, r1, h, t) {
    rotate([90, 0, 0]) translate([0, 0, -t/2])
    linear_extrude(height=t)
    polygon([[r0 - 0.5, 0], [r1, 0], [r0 - 0.5, h]]);
}

// ============================================================
// TOP SHELL (display side) — LOCAL coords: z=0 front face, +z inward
// ============================================================
module top_shell() {
    color([0.15, 0.15, 0.18])
    difference() {
        union() {
            difference() {
                filleted_prism(body_w, body_h, corner_r, top_d, front_r);
                filleted_cavity(body_w, body_h, corner_r, wall, top_d + 1, front_r);
            }
            top_internals();
            // USB-C recess pad (assembly coords -> local)
            translate([0, 0, body_d]) mirror([0, 0, 1])
            intersection() { usbc_pad(); translate([-body_w/2, -body_h/2, bot_d]) cube([body_w, body_h, top_d]); }
        }

        // Display viewport = active area + clearance
        translate([disp_x, disp_offset_y, 0])
        display_cutout(disp_w + 2*disp_clear, disp_h + 2*disp_clear, wall, 1.0);

        // Button cutouts through wall + guide wells
        top_button_cutouts(wall + btn_guide_h + 0.2);

        // LED light pipes — through the wall AND any well ring under them
        for (p = [[led1_x, led1_y, led_d], [led2_x, led2_y, led_d],
                  [led3_x, led3_y, led_diag_d], [led4_x, led4_y, led_diag_d],
                  [led5_x, led5_y, led_diag_d], [led6_x, led6_y, led_diag_d]])
            translate([p[0], p[1], -0.1])
            cylinder(h=wall + btn_guide_h + 0.2, d=p[2], $fn=16);

        // Display keep-out: glass pocket down to the PCB + tail fold zone.
        // offset(delta=-0.03): this cutter's own footprint is a STRICT
        // SUBSET of the frame wall's hole (top_internals' inner square is
        // the same panel_pocket_shape() rectangle, extended +1mm on the
        // tail side only) everywhere, so shrinking it 0.03 mm inward keeps
        // it clear of the frame's inner wall FACE without changing what
        // actually bounds the pocket (the frame hole, untouched) — unlike
        // growing it, which fixed the same defect but grew the MEASURED
        // pocket past S3/S4's tolerance. Two CSG operands sharing an exact
        // coincident face — this cutter's nominal edge sitting exactly on
        // the frame's inner wall face — is what left zero-volume
        // two-triangle sheets in case_top.stl at x = panel_x1(), caught by
        // the solidity check (verify_enclosure_stl S12/meshcheck).
        translate([0, 0, wall - 0.01])
        linear_extrude(height=top_int + 0.02)
        offset(delta=-0.03) panel_pocket_shape();
        translate([disp_tail_side > 0 ? panel_x1() - 0.01 : panel_x0() - disp_tail_ext,
                   disp_offset_y - disp_tail_w/2, wall + disp_t])
        cube([disp_tail_ext + 0.01, disp_tail_w, top_int - disp_t + 0.01]);
        // FFC passage through the +X rim at the PCB slot (full height:
        // the Y cap flange lives above the glass there)
        translate([panel_x1() - 0.01, slot_y0() - 1.5, wall - 0.01])
        cube([disp_rim_t + 0.02, slot_y1() - slot_y0() + 3, top_int + 0.02]);

        // Heat-set insert sockets at the boss free end + screw-tip relief
        for (pos = screw_positions) translate([pos[0], pos[1], 0]) {
            translate([0, 0, wall + top_int - insert_hole_depth])
            cylinder(h=insert_hole_depth + 0.1, d=insert_hole_d, $fn=24);
            translate([0, 0, wall + top_int - insert_hole_depth - insert_relief_h])
            cylinder(h=insert_relief_h + 0.1, d=insert_relief_d, $fn=20);
        }

        // Groove for the alignment lip of the bottom shell — a RING between
        // the outer skin and the interior. (V2.1 subtracted a full slab
        // here and silently chopped the last 0.4 mm off every boss and
        // frame wall; caught by verify_enclosure_stl S5.)
        translate([0, 0, top_d - lip_h])
        linear_extrude(height=lip_h + 0.1)
        difference() {
            rounded_rect(body_w - 2*(side_wall - lip_t - lip_clearance),
                          body_h - 2*(side_wall - lip_t - lip_clearance),
                          max(1, corner_r - side_wall + lip_t + lip_clearance));
            rounded_rect(body_w - 2*side_wall, body_h - 2*side_wall,
                          max(1, corner_r - side_wall));
        }

        // -Y edge features crossing the split: USB-C opening + recess
        translate([0, 0, body_d]) mirror([0, 0, 1]) { usbc_opening(); usbc_recess(); }

        top_labels();
    }

    // Cosmetic raised bezel around the viewport (proud of the front face)
    color([0.1, 0.1, 0.12])
    translate([disp_x, disp_offset_y, -0.6])
    display_bezel(disp_w + 2*disp_clear, disp_h + 2*disp_clear, disp_bezel, 0.6, 1.0);
}

// Engraved labels, each beside ITS OWN button (board net mapping:
// SW5=A top, SW6=B right, SW7=X bottom, SW8=Y left). The D-pad carries an
// arrow beyond each of its four arms. Y is engraved ABOVE its cap, not on
// its left: x = 46.5 there is under the raised display bezel (it ends at
// 47.8), which swallowed the glyph (user 2026-10-08; R9 now rejects any
// label under the bezel).
module top_labels() {
    face_label(dpad_x, dpad_y + dpad_arm_len + 3, "^", 2.5);
    face_label(dpad_x, dpad_y - dpad_arm_len - 3, "v", 2.5);
    face_label(dpad_x - dpad_arm_len - 3, dpad_y, "<", 2.5);
    face_label(dpad_x + dpad_arm_len + 3, dpad_y, ">", 2.5);
    face_label(abxy_x + abxy_offsets[0][0], abxy_y + abxy_offsets[0][1] + abxy_diam/2 + 2, "A", 2.5);
    face_label(abxy_x + abxy_offsets[1][0] + abxy_diam/2 + 2, abxy_y + abxy_offsets[1][1], "B", 2.5);
    face_label(abxy_x + abxy_offsets[2][0], abxy_y + abxy_offsets[2][1] - abxy_diam/2 - 2, "X", 2.5);
    face_label(abxy_x + abxy_offsets[3][0], abxy_y + abxy_offsets[3][1] + abxy_diam/2 + 2, "Y", 2.5);
    face_label(ss_x - ss_spacing/2, ss_y - ss_h/2 - 2.5, "START", 2);
    face_label(ss_x + ss_spacing/2, ss_y - ss_h/2 - 2.5, "SEL", 2);
    face_label(menu_x, menu_y - menu_h/2 - 2.5, "MENU", 2);
    brand_text(disp_x, brand_front_y, "GAME BRO!", brand_front_size);
}

// Everything that hangs from the ceiling (local z = wall .. wall+top_int)
module top_internals() {
    translate([0, 0, wall]) {
        // Display frame: +Y and -Y walls (inset from the tail edge, where
        // LED2 sits), +X wall = two stubs beside the FFC passage (cut in
        // top_shell), tail side (-X) open for the fold.
        linear_extrude(height=top_int)
        difference() {
            translate([panel_x0() + disp_rim_inset, panel_y0() - disp_rim_t])
            square([panel_x1() - panel_x0() - disp_rim_inset + disp_rim_t,
                    panel_y1() - panel_y0() + 2*disp_rim_t]);
            translate([panel_x0() - 1, panel_y0()])
            square([panel_x1() - panel_x0() + 1, panel_y1() - panel_y0()]);
        }

        // Insert bosses: plain o7 cylinders from the ceiling to the PCB
        // (the heat-set insert socket is cut in top_shell at the PCB
        // end), each tied to the ceiling by top_boss_gusset_n triangular
        // gussets (same gusset() module as the bottom screw columns),
        // spaced EVENLY ALL AROUND the cylinder (every 360/n deg from
        // +X) -- not limited to an outward quadrant. Any rib found too
        // close to a moving part in ANY of its real positions (cap
        // travel + lateral guide slop, not just "no volume overlap") is
        // shortened and/or pulled in to its own (h, r) in
        // top_boss_gusset_overrides for THAT one (bx, by, angle) entry,
        // never silently dropped; verify_enclosure_collision (0
        // interferences) plus the mesh-measured clearances recorded in
        // that list's own comments are the actual proof, not this one.
        color([0.45, 0.45, 0.5])
        for (pos = screw_positions) translate([pos[0], pos[1], 0]) {
            cylinder(h=top_int, d=top_boss_d, $fn=32);
            for (i = [0 : top_boss_gusset_n - 1]) {
                ang = 360 * i / top_boss_gusset_n;
                ov = [for (o = top_boss_gusset_overrides)
                        if (o[0] == pos[0] && o[1] == pos[1] && o[2] == ang) o];
                h = len(ov) > 0 ? ov[0][3] : top_boss_gusset_h;
                r = (len(ov) > 0 && len(ov[0]) > 4) ? ov[0][4] : top_boss_gusset_r;
                rotate([0, 0, ang])
                gusset(top_boss_d/2, r, h, top_boss_gusset_t);
            }
        }

        // Guide wells around every face button. A well next to the glass
        // is trimmed by the pocket grown by min_wall: what would remain
        // between its bore and the pocket edge would be a sliver, so it is
        // removed outright and the ring becomes a thick-ended C.
        difference() {
            union() {
                translate([dpad_x, dpad_y, 0])
                guide_well(btn_guide_h, btn_well_t, btn_flange_cone_h, btn_flange_extra + 0.3)
                    dpad_shape(dpad_arm_len, dpad_arm_w);
                for (off = abxy_offsets)
                    translate([abxy_x + off[0], abxy_y + off[1], 0])
                    guide_well(btn_guide_h, btn_well_t, btn_flange_cone_h, btn_flange_extra + 0.3)
                        face_button_shape(abxy_diam);
                for (p = [[ss_x - ss_spacing/2, ss_y], [ss_x + ss_spacing/2, ss_y]])
                    translate([p[0], p[1], 0])
                    guide_well(btn_guide_h, btn_well_t, btn_flange_cone_h, btn_flange_extra + 0.3)
                        pill_shape(ss_w, ss_h);
                translate([menu_x, menu_y, 0])
                guide_well(btn_guide_h, btn_well_t, btn_flange_cone_h, btn_flange_extra + 0.3)
                    pill_shape(menu_w, menu_h);
            }
            // trim = the ring's full radial extent + 0.3: a ring closer
            // than that to the pocket is cut THROUGH its bore, so the two
            // ends of the remaining C are full-thickness radial walls and
            // no tangent sliver is left at any countersink height
            translate([0, 0, -1])
            linear_extrude(height=top_int + 2)
            offset(delta=btn_well_t + btn_flange_extra + 0.3 + 0.3) panel_pocket_shape();
            // LED3-6 light pipes cross the Menu well ring: open the ring
            // outward (away from the Menu) instead of leaving a <1.2 web
            for (p = [[led3_x, led3_y], [led4_x, led4_y], [led5_x, led5_y], [led6_x, led6_y]])
                translate([p[0] - led_diag_d/2, p[1] - led_diag_d/2, -1])
                cube([led_diag_d, menu_y + menu_h/2 + 6 - p[1] + 4, top_int + 2]);
        }
    }
}

// All face-button cutouts, nominal outline, depth d from the front face
module top_button_cutouts(d) {
    translate([dpad_x, dpad_y, 0]) dpad_cutout(dpad_arm_len, dpad_arm_w, d);
    for (off = abxy_offsets)
        translate([abxy_x + off[0], abxy_y + off[1], 0])
        face_button_cutout(abxy_diam, d);
    translate([ss_x - ss_spacing/2, ss_y, 0]) pill_cutout(ss_w, ss_h, d);
    translate([ss_x + ss_spacing/2, ss_y, 0]) pill_cutout(ss_w, ss_h, d);
    translate([menu_x, menu_y, 0]) pill_cutout(menu_w, menu_h, d);
}

// ============================================================
// BOTTOM SHELL (battery side) — z=0 back face
// ============================================================
module bottom_shell() {
    color([0.18, 0.18, 0.22])
    difference() {
        union() {
            difference() {
                filleted_prism(body_w, body_h, corner_r, bot_d, back_r);
                filleted_cavity(body_w, body_h, corner_r, wall, bot_d + 1, back_r);
            }
            bottom_internals();
            intersection() { usbc_pad(); translate([-body_w/2, -body_h/2, 0]) cube([body_w, body_h, bot_d]); }

            // Alignment lip (tongue into the top shell)
            translate([0, 0, bot_d])
            linear_extrude(height=lip_h)
            difference() {
                rounded_rect(body_w - 2*(side_wall - lip_t), body_h - 2*(side_wall - lip_t),
                             max(1, corner_r - side_wall + lip_t));
                rounded_rect(body_w - 2*side_wall, body_h - 2*side_wall,
                             max(1, corner_r - side_wall));
            }
        }

        // -Y edge: USB-C opening in its recess, SD card slit, power slider cuts
        usbc_opening();
        usbc_recess();
        translate([sd_x, -body_h/2 - 0.1, sd_z])
        rotate([-90, 0, 0])
        sd_slot_cutout(sd_cut_w, sd_cut_h, side_wall + 0.2);
        pwr_cuts();
        // +Y edge: L/R cap windows
        lr_windows();

        // Speaker grille (back face)
        translate([spk_x, spk_y, 0])
        speaker_grille(spk_diam, 1.5, 3.5, wall + 1);

        // M2.5 counterbores + clearance holes through floor and column
        for (pos = screw_positions)
            translate([pos[0], pos[1], -0.1]) {
                cylinder(h=m25_head_depth + 0.1, d=m25_head_d, $fn=24);
                cylinder(h=bot_d + 0.2, d=screw_d_inner, $fn=24);
            }

        bottom_labels();
    }
}

// L is the cap at -X (wired to SW11), R at +X — each label on the flat
// back face under its own cradle, read from the back (mirrored glyph)
module bottom_labels() {
    face_label(-lr_x, lr_label_y, "L", 2.5, true);
    face_label(lr_x, lr_label_y, "R", 2.5, true);
    brand_text(0, brand_back_y, "CPJ & CP 2026", brand_back_size, true);
}

// Everything standing on the floor (z = wall ..)
module bottom_internals() {
    // Screw columns: full OD, outer half only for the last boss_half_h,
    // four gussets
    for (pos = screw_positions)
        translate([pos[0], pos[1], wall]) {
            cylinder(h=screw_boss_h - boss_half_h, d=screw_d_outer, $fn=32);
            intersection() {
                cylinder(h=screw_boss_h, d=screw_d_outer, $fn=32);
                translate([pos[0] > 0 ? 0 : -screw_d_outer, -screw_d_outer/2, 0])
                cube([screw_d_outer, screw_d_outer, screw_boss_h + 1]);
            }
            // gussets point outward in X (±45°) and along ±Y: nothing
            // toward the board centre (battery pocket, L/R cradles)
            for (a = (pos[0] > 0 ? [45, 315, 90, 270] : [135, 225, 90, 270]))
                rotate([0, 0, a])
                gusset(screw_d_outer/2, boss_gusset_r, boss_gusset_h, boss_gusset_t);
        }

    // PCB edge support ribs
    for (r = rib_positions) {
        y_in = body_h/2 - side_wall;
        y0 = r[1] > 0 ? pcb_h/2 - rib_reach : -y_in;
        y1 = r[1] > 0 ? y_in : -pcb_h/2 + rib_reach;
        translate([r[0] - rib_w/2, y0, wall])
        cube([rib_w, y1 - y0, screw_boss_h]);
    }
    for (sx = [-1, 1]) {
        x_in = body_w/2 - side_wall;
        x0 = sx > 0 ? pcb_w/2 - rib_reach : -x_in;
        x1 = sx > 0 ? x_in : -pcb_w/2 + rib_reach;
        translate([x0, rib_side_y - rib_w/2, wall])
        cube([x1 - x0, rib_w, screw_boss_h]);
    }

    // Battery pocket border: locates the cell (held down by a foam pad
    // under the PCB, never pinched by clips). Lead notch on +X; +Y
    // corners cut away for lead routing.
    translate([bat_offset_x, bat_offset_y, wall])
    difference() {
        linear_extrude(height=bat_border_h)
        difference() {
            offset(r=3) offset(r=-3)
            square([bat_w + 5 + bat_border_w*2, bat_h + bat_border_w*2], center=true);
            offset(r=3) offset(r=-3)
            square([bat_w + 5, bat_h], center=true);
        }
        translate([(bat_w + 5)/2 - 0.1, bat_lead_notch_y - bat_lead_notch_w/2, -0.1])
        cube([bat_border_w + 0.3, bat_lead_notch_w, bat_border_h + 0.2]);
        for (sx = [-1, 1])
            translate([sx * ((bat_w + 5)/2 - bat_corner_notch) - (sx > 0 ? 0 : 10),
                       bat_h/2 - bat_corner_notch, -0.1])
            cube([10, bat_border_w + bat_corner_notch + 1, bat_border_h + 0.2]);
    }

    // Battery strap posts: on the outer face of the ±Y border walls, top
    // at the cell plane, with a peg hole each
    for (px = [bat_strap_x1, bat_strap_x2])
        for (sy = [-1, 1]) {
            py = bat_offset_y + sy * (bat_h/2 + bat_border_w + bat_post_t/2);
            translate([px, py, wall])
            difference() {
                translate([-bat_post_w/2, -bat_post_t/2, 0])
                cube([bat_post_w, bat_post_t, bat_post_h]);
                translate([0, 0, bat_post_h - bat_peg_h - 0.2])
                cylinder(h=bat_peg_h + 0.3, d=bat_peg_d + 0.3, $fn=16);
            }
        }

    // Speaker seat ring
    translate([spk_x, spk_y, wall])
    difference() {
        cylinder(h=spk_seat_t, d=spk_seat_od, $fn=64);
        translate([0, 0, -0.1]) cylinder(h=spk_seat_t + 0.2, d=spk_driver_d + 0.6, $fn=64);
    }

    // SD card guide shelf (inner wall -> PCB edge)
    translate([sd_x - (sd_cut_w + 2)/2, -body_h/2 + side_wall - 0.01, wall])
    cube([sd_cut_w + 2, body_h/2 - side_wall - pcb_h/2 - rib_clear, sd_shelf_top - wall]);

    // L/R switch cradles
    for (sx = [-1, 1]) lr_bearings(sx);

    // Power slider guide: block on the -Y inner wall face, channel cut
    // for the flange (open at the top)
    translate([pwr_sw_x, 0, 0])
    difference() {
        translate([-pwr_guide_w/2, -body_h/2 + side_wall - 0.01, pwr_guide_z0])
        cube([pwr_guide_w, pwr_guide_d + 0.01, pwr_guide_z1 - pwr_guide_z0]);
        translate([-pwr_chan_half, -body_h/2 + side_wall - 0.02, pwr_fl_z0 - 0.1])
        cube([2 * pwr_chan_half, pwr_chan_d + 0.02, pwr_guide_z1 - pwr_fl_z0 + 0.3]);
    }
}

// L/R lever pivot blocks (bottom shell): one each side of the lever's
// beam, from the floor to 0.5 under the PCB, fused to the +Y inner wall.
// A U-slot open upward takes the lever pin; its -Y wall is lr_blk_wall.
// The lever drops in from above before the PCB goes on.
module lr_bearings(sx) {
    y_in = body_h/2 - side_wall;
    for (bx = [lr_beam_x0 - lr_blk_gap - lr_blk_t, lr_beam_x1 + lr_blk_gap])
        translate([sx > 0 ? bx : -bx - lr_blk_t, 0, 0])
        difference() {
            translate([0, lr_piv_y - lr_slot_w/2 - lr_blk_wall, wall - 0.01])
            cube([lr_blk_t, y_in + 0.5 - (lr_piv_y - lr_slot_w/2 - lr_blk_wall),
                  lr_blk_top - wall + 0.01]);
            translate([-0.1, lr_piv_y, lr_piv_z]) rotate([0, 90, 0])
            cylinder(h=lr_blk_t + 0.2, d=lr_slot_w, $fn=24);
            translate([-0.1, lr_piv_y - lr_slot_w/2, lr_piv_z])
            cube([lr_blk_t + 0.2, lr_slot_w, lr_blk_top]);
        }
}

// L/R bell-crank lever (printed), assembly coords; sx = +1 R, -1 L.
// rot = turn about the pin axis in degrees (render only: + lifts the
// upper arm toward the switch).
module lr_lever(sx, rot=0) {
    pz = lr_piv_z; py = lr_piv_y;
    module body() {
        // beam
        translate([lr_beam_x0, lr_beam_y0, lr_beam_z0])
        cube([lr_beam_x1 - lr_beam_x0, lr_beam_y1 - lr_beam_y0, lr_arm_top - lr_beam_z0]);
        // pins, flush with the top plane
        for (xs = [[lr_beam_x0 - lr_blk_gap - lr_blk_t + 0.3, lr_beam_x0 + 0.01],
                   [lr_beam_x1 - 0.01, lr_beam_x1 + lr_blk_gap + lr_blk_t - 0.3]])
            translate([xs[0], py, pz]) rotate([0, 90, 0])
            cylinder(h=xs[1] - xs[0], d=lr_pin_d, $fn=24);
        // upper arm, flat top under the actuator
        translate([lr_sw_x - lr_arm_w/2, lr_arm_y_end, lr_arm_z0])
        cube([lr_arm_w, lr_beam_y0 - lr_arm_y_end + 0.01, lr_arm_top - lr_arm_z0]);
        // lower arm + bump toward the cap flange
        translate([lr_x - lr_in_w/2, lr_in_y0, lr_in_z0])
        cube([lr_in_w, lr_in_y1 - lr_in_y0, lr_beam_z0 - lr_in_z0 + 0.01]);
        translate([lr_x - lr_in_w/2, lr_in_y1, lr_bump_z]) rotate([0, 90, 0])
        cylinder(h=lr_in_w, r=lr_bump_r, $fn=16);
    }
    mirror([sx > 0 ? 0 : 1, 0, 0])
    translate([0, py, pz]) rotate([-rot, 0, 0]) translate([0, -py, -pz])
    body();
}
module lr_levers(press=lr_press) {
    a = press * lr_theta * 180 / PI;
    lr_lever(-1, a); lr_lever(1, a);
}

// ============================================================
// SIMULATED DISPLAY + CABLE STACK (assembly coords)
// ============================================================
module display_sim() {
    z0 = z_ceiling - disp_t;
    // glass
    color([0.12, 0.12, 0.14])
    translate([panel_x0() + disp_clear, panel_y0() + disp_clear, z0])
    cube([disp_outline_l, disp_outline_w, disp_t]);
    // active area (flush with the ceiling)
    color([0.03, 0.03, 0.08])
    translate([disp_x - disp_w/2, disp_offset_y - disp_h/2, z_ceiling - 0.1])
    cube([disp_w, disp_h, 0.1]);
    // tail U-fold at the tail-side glass edge
    color([0.85, 0.6, 0.2])
    translate([disp_tail_side < 0 ? panel_x0() + disp_clear - disp_tail_ext + 0.3
                                  : panel_x1() - disp_clear - 0.3,
               disp_offset_y - 11, z_pcb_top + 0.3])
    cube([disp_tail_ext, 22, z0 - z_pcb_top - 0.3]);
    // 40P extension board under the glass, before the slot
    color([0.0, 0.35, 0.15])
    translate([ext_x0(), disp_offset_y - ext_w/2, z_pcb_top + 0.1])
    cube([ext_l, ext_w, ext_t]);
}

// ============================================================
// PCB MODEL — generated data (pcb_parts.scad), z=0 = PCB bottom face
// ============================================================
module pcb_model(alpha=0.8) {
    color([0.0, 0.5, 0.2, alpha])
    difference() {
        linear_extrude(height=pcb_d)
        rounded_rect(pcb_outline[0], pcb_outline[1], pcb_outline[2]);
        translate([pcb_slot[0], pcb_slot[1], -0.1])
        linear_extrude(height=pcb_d + 0.2) square([pcb_slot[2], pcb_slot[3]], center=true);
        for (h = pcb_holes)
            translate([h[0], h[1], -0.1]) cylinder(h=pcb_d + 0.2, d=h[2], $fn=16);
    }
    for (p = pcb_parts) {
        ref = p[0]; side = p[4]; L = p[5]; W = p[6]; H = p[7];
        is_led = search("LED", ref) == [0];
        is_sw = search("SW", ref) == [0];
        col = is_led ? [0.9, 0.1, 0.1] : is_sw ? [0.75, 0.75, 0.75]
            : ref == "U1" ? [0.1, 0.1, 0.1] : [0.35, 0.35, 0.3];
        color(col)
        translate([p[1], p[2], side == "top" ? pcb_d : -H])
        rotate([0, 0, p[3]])
        translate([-L/2, -W/2, 0]) cube([L, W, H]);
    }
}

// ============================================================
// BUTTON CAPS (assembly coords)
// ============================================================
z_flange = z_ceiling - btn_guide_h;   // 21.6: well end face / flange plane

// glass_side: 0 = full flange; +1/-1 = the glass is on that side of the
// cap, so the flange (and its cone) is clipped flush with the cap body
// there — retention comes from the other three sides. clip_x = the body
// extreme on that side, in the cap's local frame.
module _face_cap_body(glass_side=0, clip_x=0) {   // children(0) = nominal outline
    translate([0, 0, z_flange])
    rounded_top_extrude(btn_guide_h + wall + btn_face_h, btn_face_r)
    offset(delta=-btn_clear/2) children(0);
    intersection() {
        translate([0, 0, z_flange])
        cap_flange(btn_flange_extra, btn_flange_cone_h, btn_flange_h)
            offset(delta=-btn_clear/2) children(0);
        translate([glass_side == 0 ? 0 : clip_x - glass_side * 50, 0, z_flange])
        cube([100, 100, 20], center=true);
    }
}

module _stem(x=0, y=0) {
    translate([x, y, z_flange - btn_flange_h - btn_stem_h])
    cylinder(h=btn_stem_h + 0.01, d=btn_stem_d, $fn=20);
}

module cap_dpad() {
    translate([dpad_x, dpad_y, 0]) {
        _face_cap_body() dpad_shape(dpad_arm_len, dpad_arm_w);
        r = dpad_arm_len - 3;   // = board DPAD_OFFSETS radius (9)
        for (p = [[r, 0], [-r, 0], [0, r], [0, -r]]) _stem(p[0], p[1]);
        translate([0, 0, z_pcb_top + dpad_pivot_d/2])
        cylinder(h=dpad_pivot_h - dpad_pivot_d/2 + 0.01, d=dpad_pivot_d, $fn=20);
        translate([0, 0, z_pcb_top + dpad_pivot_d/2])
        sphere(d=dpad_pivot_d, $fn=20);
    }
}

module _abxy_cap(cx, cy, glass_side=0) {
    translate([cx, cy, 0]) {
        _face_cap_body(glass_side, glass_side * (abxy_diam/2 - btn_clear/2))
            face_button_shape(abxy_diam);
        _stem();
    }
}
module cap_btn_a() { _abxy_cap(abxy_x + abxy_offsets[0][0], abxy_y + abxy_offsets[0][1]); }
module cap_btn_b() { _abxy_cap(abxy_x + abxy_offsets[1][0], abxy_y + abxy_offsets[1][1]); }
module cap_btn_x() { _abxy_cap(abxy_x + abxy_offsets[2][0], abxy_y + abxy_offsets[2][1]); }
module cap_btn_y() { _abxy_cap(abxy_x + abxy_offsets[3][0], abxy_y + abxy_offsets[3][1], -1); }  // glass on -X

module _pill_cap(cx, cy, w, h, glass_side=0) {
    translate([cx, cy, 0]) {
        _face_cap_body(glass_side, glass_side * (w/2 - btn_clear/2)) pill_shape(w, h);
        _stem();
    }
}
module cap_start()  { _pill_cap(ss_x - ss_spacing/2, ss_y, ss_w, ss_h); }
module cap_select() { _pill_cap(ss_x + ss_spacing/2, ss_y, ss_w, ss_h, 1); }  // glass on +X
module cap_menu()   { _pill_cap(menu_x, menu_y, menu_w, menu_h); }

// ---- L/R edge caps (assembly coords); sx = +1 R, -1 L ----
// Body through the +Y wall window and lr_cap_proud beyond it, outer edges
// rounded; inner flange 1.2 wider on the two sides and the bottom (flush
// on top: the cap's top edge is at the split, the top shell wall above
// it keeps it down). The lever's bump rests on the flange's back.
module cap_lr(sx) {
    y_in = body_h/2 - side_wall;
    translate([sx * lr_x, -lr_press * lr_cap_travel, lr_axis_z]) {
        translate([0, y_in - lr_fl_gap - 0.01, 0]) rotate([-90, 0, 0])
        rounded_top_extrude(side_wall + lr_cap_proud + lr_fl_gap + 0.01, lr_cap_r)
        rrect2d(lr_cap_w - lr_cap_clear, lr_cap_h - lr_cap_clear, 2);
        translate([0, y_in - lr_fl_gap - lr_fl_t, 0]) rotate([-90, 0, 0])
        linear_extrude(height=lr_fl_t)
        translate([0, lr_fl_extra/2])      // local +y = -Z: extra at the bottom
        rrect2d(lr_cap_w - lr_cap_clear + 2 * lr_fl_extra,
                lr_cap_h - lr_cap_clear + lr_fl_extra, 2);
    }
}
module cap_lr_l() { cap_lr(-1); }
module cap_lr_r() { cap_lr(1); }

// ---- Power slider (assembly coords) ----
// Flange against the inner wall face, tab up into the lip groove
// (through the tongue notch), nub out through the slot to pwr_nub_proud
// above the face, and a fork that straddles the MSK12C02 knob.
module cap_power_slider() {
    y_in = -body_h/2 + side_wall;
    y_out = -body_h/2;
    translate([pwr_sw_x, 0, 0]) {
        translate([-pwr_fl_w/2, y_in, pwr_fl_z0])
        cube([pwr_fl_w, pwr_fl_t, bot_d - pwr_fl_z0]);
        translate([-pwr_tab_w/2, y_out + side_wall - lip_t + lip_clearance/2, bot_d - 0.01])
        cube([pwr_tab_w, lip_t - lip_clearance/2 + pwr_fl_t, pwr_tab_h + 0.01]);
        translate([0, y_in + 0.01, pwr_slot_z0 + 0.2 + pwr_nub_h/2]) rotate([90, 0, 0])
        rounded_top_extrude(side_wall + pwr_nub_proud + 0.01, 0.8)
        rrect2d(pwr_nub_w, pwr_nub_h, 0.8);
        for (sg = [-1, 1])
            translate([sg * (pwr_knob_w/2 + 0.2 + pwr_fork_t/2) - pwr_fork_t/2,
                       y_in + pwr_fl_t - 0.01, pwr_fork_z0])
            cube([pwr_fork_t, (pwr_knob_root_y - 0.6) - (y_in + pwr_fl_t) + 0.01,
                  pwr_fork_z1 - pwr_fork_z0]);
    }
}

module face_caps() {
    color([0.25, 0.25, 0.28]) cap_dpad();
    color([0.8, 0.2, 0.2])   cap_btn_a();
    color([0.8, 0.8, 0.2])   cap_btn_b();
    color([0.2, 0.4, 0.8])   cap_btn_x();
    color([0.2, 0.7, 0.3])   cap_btn_y();
    color([0.35, 0.35, 0.38]) cap_start();
    color([0.35, 0.35, 0.38]) cap_menu();
    color([0.35, 0.35, 0.38]) cap_select();
}
module edge_caps() {
    color([0.25, 0.25, 0.28]) cap_lr_l();
    color([0.25, 0.25, 0.28]) cap_lr_r();
    color([0.35, 0.35, 0.38]) cap_power_slider();
}
module button_caps() {
    face_caps();
    edge_caps();
}

// ============================================================
// VIEWS
// ============================================================
module battery_sim() {
    translate([bat_offset_x, bat_offset_y, wall])
    color([0.3, 0.3, 0.7, 0.7])
    linear_extrude(height=bat_d)
    rounded_rect(bat_w, bat_h, 3);
}
module speaker_sim() {
    color([0.2, 0.2, 0.2])
    translate([spk_x, spk_y, wall])
    cylinder(h=spk_driver_t, d=spk_driver_d, $fn=64);
}
// Battery hold-down strap at X = px (assembly coords): a 1 mm bar over
// the cell between the two posts, pegs down into the post holes
module bat_strap(px) {
    y_out = bat_h/2 + bat_border_w + bat_post_t;
    translate([px, bat_offset_y, 0]) {
        translate([-bat_strap_w/2, -y_out, wall + bat_post_h])
        cube([bat_strap_w, 2 * y_out, bat_strap_t]);
        for (sy = [-1, 1])
            translate([0, sy * (bat_h/2 + bat_border_w + bat_post_t/2), wall + bat_post_h - bat_peg_h])
            cylinder(h=bat_peg_h + 0.01, d=bat_peg_d, $fn=16);
    }
}
module bat_straps() {
    color([0.55, 0.55, 0.6]) { bat_strap(bat_strap_x1); bat_strap(bat_strap_x2); }
}

// The four M2.5 heat-set inserts seated in the top bosses (assembly coords)
module inserts_sim() {
    color([0.85, 0.65, 0.25])
    for (pos = screw_positions)
        translate([pos[0], pos[1], z_pcb_top])
        difference() {
            cylinder(h=insert_l, d=insert_od, $fn=24);
            translate([0, 0, -0.1]) cylinder(h=insert_l + 0.2, d=2.5, $fn=16);
        }
}

module assembly() {
    bottom_shell();
    translate([0, 0, body_d]) mirror([0, 0, 1]) top_shell();
    translate([0, 0, pcb_z]) pcb_model();
    display_sim();
    button_caps();
    lever_parts();
}
module lever_parts() { color([0.9, 0.55, 0.15]) lr_levers(); }
module assembly_internal() {
    assembly();
    battery_sim();
    bat_straps();
    speaker_sim();
    inserts_sim();
}

module exploded_view() {
    explode_gap = 35;
    bottom_shell();
    translate([0, 0, body_d + explode_gap]) mirror([0, 0, 1]) top_shell();
    battery_sim();
    speaker_sim();
    translate([0, 0, explode_gap * 0.1]) bat_straps();
    translate([0, 0, explode_gap * 0.2]) translate([0, 0, pcb_z]) pcb_model();
    translate([0, 0, explode_gap * 0.5]) display_sim();
    translate([0, 0, explode_gap * 1.35]) face_caps();
    translate([0, 0, explode_gap * 0.1]) lever_parts();
    translate([0, 0, explode_gap * 0.15]) edge_caps();
}

module cross_section() {
    difference() {
        assembly_internal();
        translate([0, -body_h/4 - 0.5, body_d/2])
        cube([body_w + 10, body_h/2 + 1, body_d + 20], center=true);
    }
}
module cross_section_yz() {
    difference() {
        assembly_internal();
        translate([abxy_x + abxy_offsets[3][0] + body_w/2, 0, body_d/2])
        cube([body_w, body_h + 10, body_d + 20], center=true);
    }
}
module fit_check() {
    bottom_shell();
    translate([0, 0, pcb_z]) pcb_model(alpha=0.35);
    battery_sim();
    bat_straps();
    lever_parts();
    edge_caps();
}
module top_inside() {
    top_shell();
    translate([0, 0, body_d]) mirror([0, 0, 1]) { display_sim(); face_caps(); inserts_sim(); }
}
module top_inside_bare() {
    top_shell();
    translate([0, 0, body_d]) mirror([0, 0, 1]) inserts_sim();
}
// no speaker body here: the seat ring shows where the driver drops in
module bottom_inside() {
    bottom_shell();
    battery_sim();
    bat_straps();
    lever_parts();
    edge_caps();
}
// Every printed part laid out flat, as it comes off the bed (viewer / docs)
module parts_layout() {
    translate([0, 0, 0]) rotate([180, 0, 0]) mirror([0, 0, 1]) top_shell();
    translate([0, -100, 0]) bottom_shell();
    translate([-20, 70, -z_flange + btn_flange_h + btn_stem_h]) face_caps();
    translate([0, 170, 0]) {
        color([0.25, 0.25, 0.28]) translate([-30, 0, 0]) rotate([90, 0, 0]) translate([lr_x, -(body_h/2 - side_wall - lr_fl_t), -lr_axis_z]) cap_lr_l();
        color([0.25, 0.25, 0.28]) translate([0, 0, 0]) rotate([90, 0, 0]) translate([-lr_x, -(body_h/2 - side_wall - lr_fl_t), -lr_axis_z]) cap_lr_r();
        color([0.35, 0.35, 0.38]) translate([30, 0, 0]) rotate([-90, 0, 0]) translate([-pwr_sw_x, body_h/2 - side_wall, 0]) cap_power_slider();
        color([0.9, 0.55, 0.15]) translate([-65, 0, 0]) rotate([180, 0, 0]) translate([lr_x, -lr_piv_y, -lr_arm_top]) lr_lever(-1);
        color([0.9, 0.55, 0.15]) translate([-95, 0, 0]) rotate([180, 0, 0]) translate([-lr_x, -lr_piv_y, -lr_arm_top]) lr_lever(1);
        color([0.55, 0.55, 0.6]) translate([60, -10, wall + bat_post_h + bat_strap_t]) rotate([180, 0, 0]) translate([-bat_strap_x1, -bat_offset_y, 0]) bat_strap(bat_strap_x1);
    }
}
module battery_fit() { bottom_shell(); battery_sim(); bat_straps(); }

// One top boss cut open through its axis: insert socket, relief, wall
module boss_section() {
    bx = screw_positions[1][0]; by = screw_positions[1][1];
    // the socket is shown EMPTY on purpose: this is the print geometry
    intersection() {
        translate([0, 0, body_d]) mirror([0, 0, 1]) top_shell();
        translate([bx - 8, by, body_d - top_d - 1]) cube([16, 12, top_d + 2]);
    }
}

// Interference audit — exported to STL by verify_enclosure_collision.py:
// shells vs everything inside, caps vs the panel stack, panel stack vs
// the PCB parts. A component with volume is a collision.
module collision_check() {
    intersection() {
        union() {
            bottom_shell();
            translate([0, 0, body_d]) mirror([0, 0, 1]) top_shell();
        }
        union() {
            translate([0, 0, pcb_z]) pcb_model();
            display_sim();
            battery_sim();
            speaker_sim();
            button_caps();
            bat_straps();
            lr_levers();
        }
    }
    intersection() { lr_levers(); translate([0, 0, pcb_z]) pcb_model(); }
    intersection() { lr_levers(); edge_caps(); }
    intersection() { edge_caps(); translate([0, 0, pcb_z]) pcb_model(); }
    intersection() { bat_straps(); translate([0, 0, pcb_z]) pcb_model(); }
    intersection() { bat_straps(); battery_sim(); }
    intersection() { face_caps(); display_sim(); }
    intersection() { display_sim(); translate([0, 0, pcb_z]) pcb_model(); }
    intersection() { inserts_sim(); translate([0, 0, pcb_z]) pcb_model(); }
}

// Thin-wall audit (vertical walls) — exported to STL by
// verify_enclosure_requirements.py. Each horizontal slice of the part is
// eroded and re-dilated by min_wall/2: whatever the erosion deleted is
// material thinner than min_wall. The slices are stacked as 0.1 mm slabs
// at their own z, so a hit reports where it is. Horizontal plates (cap
// flange, straps, floor) are checked by R8's table, not here.
module thin_slice(z) {
    translate([0, 0, z])
    linear_extrude(height=0.1)
    intersection() {
        // the slice itself: keeps the audit inside real material (CGAL
        // can leave phantom slivers inside holes otherwise)
        projection(cut=true) translate([0, 0, -z]) children(0);
        difference() {
            projection(cut=true) translate([0, 0, -z]) children(0);
            offset(r=min_wall/2 - 0.02) offset(r=-min_wall/2 + 0.02)
                projection(cut=true) translate([0, 0, -z]) children(0);
        }
    }
}
module thin_check_top()    { for (z = [1, 3, 4.5, 6, 7.5, 8.9, 9.8]) thin_slice(z) top_shell(); }
module thin_check_bottom() { for (z = [1, 3, 5, 7, 9, 11, 13, 15, 17]) thin_slice(z) bottom_shell(); }
// edge caps + slider + L/R levers, sliced in assembly Z (their flanges
// and arms are vertical plates)
module thin_check_edge() {
    for (z = [7.5, 8.5, 10, 12, 13.3, 14, 15.5, 16.5])
        thin_slice(z) union() { edge_caps(); lr_levers(); }
}
module thin_check() {
    thin_check_top();
    translate([0, 0, 40]) thin_check_bottom();
    translate([0, 0, 80]) thin_check_edge();
}

// Label audit — exported to STL by verify_enclosure_requirements.py: the
// engraved glyphs alone, in ASSEMBLY coords, so each one can be located
// next to its own button.
module labels_check() {
    translate([0, 0, body_d]) mirror([0, 0, 1]) top_labels();
    bottom_labels();
}

// L/R lever explainers (renders only), R side: the bottom shell cut on
// the YZ plane through the switch (x = lr_sw_x) or through the cap
// (x = lr_x), with the PCB, the cap and the lever; lr_press poses them.
module lr_lever_detail(cut_x) {
    // each piece cut separately with a cutter of ITS OWN colour: in the
    // preview a cut face takes the cutter's colour
    module cut(c) {
        difference() {
            color(c) children();
            color(c) translate([cut_x, -200, -1]) cube([400, 400, 60]);
        }
    }
    cut([0.32, 0.32, 0.36]) bottom_shell();
    cut([0.1, 0.55, 0.3]) translate([0, 0, pcb_z]) pcb_model(alpha=1);
    cut([0.62, 0.62, 0.66]) cap_lr_r();
    cut([0.95, 0.55, 0.1]) lr_lever(1, lr_press * lr_theta * 180 / PI);
}

// ============================================================
// RENDER SELECTOR
// ============================================================
if (part == "assembly") {
    assembly();
} else if (part == "top") {
    top_shell();
} else if (part == "bottom") {
    bottom_shell();
} else if (part == "exploded") {
    exploded_view();
} else if (part == "cross_section") {
    cross_section();
} else if (part == "cross_section_yz") {
    cross_section_yz();
} else if (part == "fit_check") {
    fit_check();
} else if (part == "top_inside") {
    top_inside();
} else if (part == "top_inside_bare") {
    top_inside_bare();
} else if (part == "bottom_inside") {
    bottom_inside();
} else if (part == "collision_check") {
    collision_check();
} else if (part == "labels_check") {
    labels_check();
} else if (part == "thin_check") {
    thin_check();
} else if (part == "pcb") {
    pcb_model();
} else if (part == "battery_fit") {
    battery_fit();
// --- Individual part exports (STL viewer + printing) ---
} else if (part == "case_top") {
    translate([0, 0, body_d]) mirror([0, 0, 1]) top_shell();
} else if (part == "case_top_print") {
    // Front face down on the bed = the ASSEMBLY copy turned over 180° about
    // X. Never top_shell() alone: its local frame is the assembly MIRRORED
    // in Z, and a mirror is not a motion you can do to a printed part — the
    // 2026-09 print came out as the mirror image, ABXY holes on the D-pad
    // side. Every print part must be a pure rotation of its viewer part
    // (gate S0 in verify_enclosure_stl.py).
    rotate([180, 0, 0]) mirror([0, 0, 1]) top_shell();
} else if (part == "case_bottom") {
    bottom_shell();
} else if (part == "part_display") {
    display_sim();
} else if (part == "part_dpad") {
    cap_dpad();
} else if (part == "part_btn_a") {
    cap_btn_a();
} else if (part == "part_btn_b") {
    cap_btn_b();
} else if (part == "part_btn_x") {
    cap_btn_x();
} else if (part == "part_btn_y") {
    cap_btn_y();
} else if (part == "part_start") {
    cap_start();
} else if (part == "part_menu") {
    cap_menu();
} else if (part == "part_select") {
    cap_select();
} else if (part == "part_lr_cap_l") {
    cap_lr_l();
} else if (part == "part_lr_cap_r") {
    cap_lr_r();
} else if (part == "part_lr_caps") {
    cap_lr_l(); cap_lr_r();
} else if (part == "part_lr_cap_print") {
    // one cap (R), flange flat on the bed, face up: a pure rotation
    rotate([90, 0, 0]) translate([-lr_x, -(body_h/2 - side_wall - lr_fl_t), -lr_axis_z]) cap_lr_r();
} else if (part == "part_power_slider") {
    cap_power_slider();
} else if (part == "part_power_slider_print") {
    // flange flat on the bed, nub up (rotation only)
    rotate([-90, 0, 0]) translate([-pwr_sw_x, body_h/2 - side_wall, 0]) cap_power_slider();
} else if (part == "part_lr_levers") {
    lr_levers();
} else if (part == "part_lr_lever_l") {
    lr_lever(-1);
} else if (part == "part_lr_lever_r") {
    lr_lever(1);
} else if (part == "part_lr_lever_l_print") {
    // top plane (Z lr_arm_top) flat on the bed: a pure rotation
    rotate([180, 0, 0]) translate([lr_x, -lr_piv_y, -lr_arm_top]) lr_lever(-1);
} else if (part == "part_lr_lever_r_print") {
    rotate([180, 0, 0]) translate([-lr_x, -lr_piv_y, -lr_arm_top]) lr_lever(1);
} else if (part == "parts_layout") {
    parts_layout();
} else if (part == "lr_cut_switch") {
    lr_lever_detail(lr_sw_x);
} else if (part == "lr_cut_cap") {
    lr_lever_detail(lr_x);
} else if (part == "part_pcb") {
    translate([0, 0, pcb_z]) pcb_model();
} else if (part == "part_straps") {
    bat_straps();
} else if (part == "part_strap_print") {
    // one strap, pegs up, flat on the bed (turned over: rotate, never mirror)
    translate([0, 0, wall + bat_post_h + bat_strap_t]) rotate([180, 0, 0])
    translate([-bat_strap_x1, -bat_offset_y, 0]) bat_strap(bat_strap_x1);
} else if (part == "boss_section") {
    boss_section();
}
