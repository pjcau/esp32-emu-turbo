// ============================================================
// ESP32 Emu Turbo — Handheld Console Enclosure — V2.1
// Parametric design — all dimensions in mm
// Form factor: landscape (similar to GBA / Switch Lite)
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
corner_r = 8;           // Corner radius

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
led3_y = -20.5;
led4_x = 60;
led4_y = -20.5;
led5_x = 66;
led5_y = -20.5;
led6_x = 72;
led6_y = -20.5;
led_d = 2.0;            // LED1/2 light pipe hole
led_diag_d = 1.2;       // LED3-6 (between the Menu pill and the column)

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
btn_face_h = 0.6;       // cap face proud of the front surface
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

// === Shoulder buttons (L/R on the back face) — board SHOULDER_*_ENC ===
shoulder_inset_x = 65;  // switch centre |X|
shoulder_y = 32;        // switch centre Y
lever_len = 14;         // visible face length (X) — the hinge must stay
                        // outside the 95 mm battery pocket (|x| >= 49.5)
lever_w = 8.5;          // visible face width (Y)
lever_tip_over = 0.8;   // face tip beyond the switch centre: the floor web
                        // between the face cutout and the o5 counterbore
                        // must stay >= min_wall (1.3 here); the nub (to
                        // x 66.7) rides on the flange, which runs 1 mm past
                        // the face tip
lever_face_h = 1.0;     // face proud of the back surface
lever_flange_t = 1.2;   // retention flange inside the floor (>= 1.2: slicer min wall)
lever_flange_extra = 1.2;
lever_nub_d = 3.4;
lever_rod_d = 2.0;      // hinge rod printed with the shell
lever_rod_z = 4.0;      // rod axis above the back face (floor top = 2)
lever_tongue_w = 5.0;   // hinge tongue width (Y): 1.35 mm walls beside the o2.3 bore
lever_tongue_top = lever_rod_z + 2.5;   // 1.35 mm of hook above the bore
lever_tongue_front = 2.4;               // tongue end beyond the rod axis: 1.25 mm in front of the bore
lever_min_wall = min_wall;
lever_block_t = 2.0;    // hinge block thickness (Y)
lever_block_gap = 4.5;  // block inner face from the lever centre line
lever_tip_x = shoulder_inset_x + lever_tip_over;      // 65.8
lever_x0 = lever_tip_x - lever_len;                   // 51.8
lever_cx = lever_tip_x - lever_len / 2;               // 58.8
lever_hinge_x = lever_x0 - 1.4;                       // 50.4
lever_nub_top = pcb_z - sw_h - sw_pretravel;          // 14.3
lever_cut_clear = 0.8;  // diametral clearance face vs floor cutout

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
// === Top bosses with M2.5 heat-set inserts — user 2026-09-16: ID M2.5,
// L 2.5, OD 3.5, "2 mm of plastic around it for robustness" ===
insert_od = 3.5;        // knurled OD
insert_l = 2.5;         // length
insert_hole_d = 3.1;    // socket (OD - 0.4, PLA/PETG heat-set)
insert_hole_depth = insert_l + 0.5;   // 3.0: flush insert + 0.5
insert_relief_d = 2.8;  // bore above the insert for the screw tip
insert_relief_h = 2.5;  // Z 20.6..23.1 — the M2.5x20 tip stops at 21.8
insert_wall = 2.0;      // plastic around the socket (user's request)
top_boss_d = insert_hole_d + 2 * insert_wall + 0.1;   // 7.2

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
usbc_x = 0;
usbc_z = bot_d - 1.6;
usbc_cut_w = 13;
usbc_cut_h = 6.5;

// === SD card slot (bottom edge, right) ===
sd_x = 60;
sd_z = bot_d - 1.8;
sd_cut_w = 16;
sd_cut_h = 3.5;
sd_shelf_top = 13.3;

// === Power switch (bottom edge, left of USB-C) — MSK12C02 ===
pwr_sw_x = -40;
pwr_sw_z = bot_d - 2.0;
pwr_cut_w = 8;
pwr_cut_h = 3.2;

// === Speaker (28 mm driver, off-board, seats on the floor) ===
// User 2026-09-16: grille top-LEFT when looking at the back = ABXY side,
// toward the top edge in enclosure coords. Seat r15 clears the pocket
// border (x 47.5), the R lever hinge (y >= 26.5), the side rib (x 78.5)
// and the column (23.6 mm).
spk_x = 63.5;
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
bat_offset_x = -1.5;    // pocket x -49 .. 46: the speaker seat starts at 48,
                        // the L/R lever hinges at |x| >= 49.5
bat_offset_y = 5;       // pocket y -20 .. 30: clear of J3 (y <= -20.7)
bat_border_w = 1.5;
bat_border_h = 8;       // < 8.5 so J3 (Z 10.5..16) never meets the border
bat_lead_notch_w = 8;
bat_lead_notch_y = -14;
bat_corner_notch = 2.5; // +Y corners of the border cut back (lever hinges)
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

echo(str("V2.1 stack: body_d=", body_d, " top_int=", top_int,
         " btn_stem_h=", btn_stem_h, " btn_cap_h=", btn_cap_h,
         " glass_cx=", disp_glass_cx, " disp_x=", disp_x,
         " lever_nub_h=", lever_nub_top - wall - lever_flange_t));

// ============================================================
// Primitives / geometry helpers
// ============================================================
module rounded_rect(w, h, r) {
    offset(r=r) offset(r=-r) square([w, h], center=true);
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

// USB-C plug opening, ASSEMBLY coords (crosses the shell split)
module usbc_opening() {
    translate([usbc_x, -body_h/2 - 0.1, usbc_z])
    rotate([-90, 0, 0])
    usbc_cutout(usbc_cut_w, usbc_cut_h, side_wall + 0.2);
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
                linear_extrude(height=top_d)
                rounded_rect(body_w, body_h, corner_r);
                translate([0, 0, wall])
                linear_extrude(height=top_d)
                rounded_rect(body_w - side_wall*2, body_h - side_wall*2, corner_r - side_wall);
            }
            top_internals();
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

        // Display keep-out: glass pocket down to the PCB + tail fold zone
        translate([0, 0, wall - 0.01])
        linear_extrude(height=top_int + 0.02)
        panel_pocket_shape();
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

        // Groove for the alignment lip of the bottom shell
        translate([0, 0, top_d - lip_h])
        linear_extrude(height=lip_h + 0.1)
        rounded_rect(body_w - 2*(side_wall - lip_t - lip_clearance),
                      body_h - 2*(side_wall - lip_t - lip_clearance),
                      max(1, corner_r - side_wall + lip_t + lip_clearance));

        // USB-C plug opening crosses the split: notch the rim end
        translate([0, 0, body_d]) mirror([0, 0, 1]) usbc_opening();

        top_labels();
    }

    // Cosmetic raised bezel around the viewport (proud of the front face)
    color([0.1, 0.1, 0.12])
    translate([disp_x, disp_offset_y, -0.6])
    display_bezel(disp_w + 2*disp_clear, disp_h + 2*disp_clear, disp_bezel, 0.6, 1.0);
}

// Engraved labels, each beside ITS OWN button (board net mapping:
// SW5=A top, SW6=B right, SW7=X bottom, SW8=Y left)
module top_labels() {
    face_label(dpad_x, dpad_y + dpad_arm_len + 3, "^", 2.5);
    face_label(dpad_x, dpad_y - dpad_arm_len - 3, "v", 2.5);
    face_label(abxy_x + abxy_offsets[0][0], abxy_y + abxy_offsets[0][1] + abxy_diam/2 + 2, "A", 2.5);
    face_label(abxy_x + abxy_offsets[1][0] + abxy_diam/2 + 2, abxy_y + abxy_offsets[1][1], "B", 2.5);
    face_label(abxy_x + abxy_offsets[2][0], abxy_y + abxy_offsets[2][1] - abxy_diam/2 - 2, "X", 2.5);
    face_label(abxy_x + abxy_offsets[3][0] - abxy_diam/2 - 2, abxy_y + abxy_offsets[3][1], "Y", 2.5);
    face_label(ss_x - ss_spacing/2, ss_y - ss_h/2 - 2.5, "START", 2);
    face_label(ss_x + ss_spacing/2, ss_y - ss_h/2 - 2.5, "SEL", 2);
    face_label(menu_x, menu_y - menu_h/2 - 2.5, "MENU", 2);
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
        // (the heat-set insert socket is cut in top_shell at the PCB end)
        color([0.45, 0.45, 0.5])
        for (pos = screw_positions) translate([pos[0], pos[1], 0])
            cylinder(h=top_int, d=top_boss_d, $fn=32);

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
                linear_extrude(height=bot_d)
                rounded_rect(body_w, body_h, corner_r);
                translate([0, 0, wall])
                linear_extrude(height=bot_d)
                rounded_rect(body_w - side_wall*2, body_h - side_wall*2, corner_r - side_wall);
            }
            bottom_internals();

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

        usbc_opening();

        translate([sd_x, -body_h/2 - 0.1, sd_z])
        rotate([-90, 0, 0])
        sd_slot_cutout(sd_cut_w, sd_cut_h, side_wall + 0.2);

        translate([pwr_sw_x, -body_h/2 - 0.1, pwr_sw_z])
        rotate([-90, 0, 0])
        power_switch_cutout(pwr_cut_w, pwr_cut_h, side_wall + 0.2);

        // Speaker grille (back face)
        translate([spk_x, spk_y, 0])
        speaker_grille(spk_diam, 1.5, 3.5, wall + 1);

        // M2.5 counterbores + clearance holes through floor and column
        for (pos = screw_positions)
            translate([pos[0], pos[1], -0.1]) {
                cylinder(h=m25_head_depth + 0.1, d=m25_head_d, $fn=24);
                cylinder(h=bot_d + 0.2, d=screw_d_inner, $fn=24);
            }

        // Shoulder lever face cutouts
        for (sx = [-1, 1])
            translate([sx * lever_cx, shoulder_y, 0])
            pill_cutout(lever_len + lever_cut_clear, lever_w + lever_cut_clear, wall);

        bottom_labels();
    }
}

// L is the lever at -X (SW11 at (-65, 32)), R at +X — each label beside its lever
module bottom_labels() {
    face_label(-lever_cx, shoulder_y + lever_w/2 + 3, "L", 2.5, true);
    face_label(lever_cx, shoulder_y + lever_w/2 + 3, "R", 2.5, true);
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
            // toward the board centre, where the L/R lever flanges lie
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
    // corners cut away where the L/R lever hinges stand.
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

    // Shoulder lever hinges: two blocks + a printed rod (bridged)
    for (sx = [-1, 1]) {
        for (sy = [-1, 1])
            translate([sx * lever_hinge_x - 1.5,
                       shoulder_y + sy * lever_block_gap - (sy > 0 ? 0 : lever_block_t),
                       wall])
            cube([3, lever_block_t, lever_rod_z - wall + 2]);
        translate([sx * lever_hinge_x, shoulder_y - lever_block_gap - lever_block_t, lever_rod_z])
        rotate([-90, 0, 0])
        cylinder(h=2 * (lever_block_gap + lever_block_t), d=lever_rod_d, $fn=20);
    }
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
    linear_extrude(height=btn_guide_h + wall + btn_face_h)
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

// ---- Shoulder levers (bottom shell, hinged); sx = +1 R, -1 L ----
module _shoulder_lever(sx) {
    mirror([sx < 0 ? 1 : 0, 0, 0])
    translate([0, shoulder_y, 0]) {
        translate([lever_cx, 0, -lever_face_h])
        linear_extrude(height=lever_face_h + wall)
        pill_shape(lever_len, lever_w);
        translate([0, 0, wall])
        linear_extrude(height=lever_flange_t)
        intersection() {
            translate([lever_cx, 0])
            offset(delta=lever_flange_extra) pill_shape(lever_len, lever_w);
            translate([lever_x0 + 1.2, -20]) square([lever_len - 1.2 + 1.0, 40]);
        }
        translate([shoulder_inset_x, 0, wall + lever_flange_t - 0.01])
        cylinder(h=lever_nub_top - wall - lever_flange_t, d=lever_nub_d, $fn=20);
        difference() {
            union() {
                // tongue over the floor (0.3 above it, so it can pivot)
                translate([lever_hinge_x - lever_tongue_front, -lever_tongue_w/2, wall + 0.3])
                cube([lever_x0 + 4 - (lever_hinge_x - lever_tongue_front), lever_tongue_w,
                      lever_tongue_top - wall - 0.3]);
                // ...and sunk into the face plate where it overlaps it —
                // a solid 4 mm join, no thin bridge
                translate([lever_x0 + 0.3, -lever_tongue_w/2, wall - 1.0])
                cube([3.7, lever_tongue_w, lever_tongue_top - wall + 1.0]);
            }
            translate([lever_hinge_x, -lever_tongue_w/2 - 0.1, lever_rod_z])
            rotate([-90, 0, 0])
            cylinder(h=lever_tongue_w + 0.2, d=lever_rod_d + 0.3, $fn=20);
            translate([lever_hinge_x - (lever_rod_d - 0.3)/2, -lever_tongue_w/2 - 0.1, wall])
            cube([lever_rod_d - 0.3, lever_tongue_w + 0.2, lever_rod_z - wall + 0.01]);
        }
    }
}
module cap_shoulder_l() { _shoulder_lever(-1); }
module cap_shoulder_r() { _shoulder_lever(1); }

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
module button_caps() {
    face_caps();
    color([0.25, 0.25, 0.28]) cap_shoulder_l();
    color([0.25, 0.25, 0.28]) cap_shoulder_r();
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
}
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
    translate([0, 0, -explode_gap * 0.3]) {
        color([0.25, 0.25, 0.28]) cap_shoulder_l();
        color([0.25, 0.25, 0.28]) cap_shoulder_r();
    }
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
    color([0.25, 0.25, 0.28]) { cap_shoulder_l(); cap_shoulder_r(); }
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
    color([0.25, 0.25, 0.28]) { cap_shoulder_l(); cap_shoulder_r(); }
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
        }
    }
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
module thin_check_levers() { for (z = [0.5, 2.5, 3.5, 5, 6]) thin_slice(z) { cap_shoulder_l(); cap_shoulder_r(); } }
module thin_check() {
    thin_check_top();
    translate([0, 0, 40]) thin_check_bottom();
    translate([0, 0, 80]) thin_check_levers();
}

// Label audit — exported to STL by verify_enclosure_requirements.py: the
// engraved glyphs alone, in ASSEMBLY coords, so each one can be located
// next to its own button.
module labels_check() {
    translate([0, 0, body_d]) mirror([0, 0, 1]) top_labels();
    bottom_labels();
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
    top_shell();                       // front face down on the bed
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
} else if (part == "part_shoulder_l") {
    cap_shoulder_l();
} else if (part == "part_shoulder_r") {
    cap_shoulder_r();
} else if (part == "part_pcb") {
    translate([0, 0, pcb_z]) pcb_model();
} else if (part == "part_straps") {
    bat_straps();
} else if (part == "part_strap_print") {
    // one strap, pegs up, flat on the bed
    translate([0, 0, wall + bat_post_h + bat_strap_t]) mirror([0, 0, 1])
    translate([-bat_strap_x1, -bat_offset_y, 0]) bat_strap(bat_strap_x1);
} else if (part == "boss_section") {
    boss_section();
}
