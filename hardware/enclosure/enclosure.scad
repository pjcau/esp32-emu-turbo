// ============================================================
// ESP32 Emu Turbo — Handheld Console Enclosure
// Parametric design — all dimensions in mm
// Form factor: landscape (similar to GBA / Switch Lite)
// ============================================================

use <modules/buttons.scad>
use <modules/display.scad>
use <modules/ports.scad>
use <modules/battery.scad>

// === Render control (override with -D on CLI) ===
part = "assembly";  // "assembly", "top", "bottom", "exploded", "cross_section", "fit_check", "pcb"

// === Main enclosure parameters ===
body_w = 170;           // Width (landscape, X axis)
body_h = 85;            // Height (Y axis)
body_d = 25;            // Depth/thickness (Z axis)
wall = 2.0;             // Wall thickness
corner_r = 8;           // Corner radius

// Shell split
top_d = 10;             // Top shell depth (display side)
bot_d = body_d - top_d; // Bottom shell depth (battery side)

// === Display parameters (ILI9488 3.95" bare panel + 40P FPC) ===
disp_w = 86.4;          // Active area width
disp_h = 64.8;          // Active area height
disp_bezel = 2.0;       // Bezel width around viewport
disp_pcb_w = 98;        // Display module PCB width
disp_pcb_h = 72;        // Display module PCB height
disp_offset_y = 2;      // Slight upward offset

// === D-pad parameters (left side) ===
dpad_x = -62;           // X offset from center
dpad_y = 5;             // Y offset from center
dpad_arm_len = 12;
dpad_arm_w = 5;

// === ABXY parameters (right side, diamond layout) ===
abxy_x = 62;            // X offset from center (moved right, symmetric with D-pad)
abxy_y = 5;             // Y offset from center
abxy_spacing = 10;      // KiCad: switches at 10mm from diamond center
abxy_diam = 8;

// === Start/Select (below D-pad, left side) ===
ss_x = dpad_x;          // Centered horizontally under D-pad
ss_y = dpad_y - 22;     // Below D-pad
ss_spacing = 20;        // Horizontal distance Start↔Select (KiCad: 8→28 = 20mm)
ss_w = 10;              // Pill width
ss_h = 4;               // Pill height

// === Menu button (below ABXY, right side) — KiCad SW13 BTN_MENU (142,62.5) ===
menu_x = 62;            // Same X as ABXY center
menu_y = -25;           // KiCad Y=62.5 → enc -25

// === LED indicators (below Start/Menu, left side) ===
led1_x = -55;           // KiCad (25, 67.5) → enc (-55, -30)
led1_y = -30;
led2_x = -48;           // KiCad (32, 67.5) → enc (-48, -30)
led2_y = -30;
led_d = 2.0;            // Light pipe hole diameter

// === Shoulder buttons (L/R on back side, near top edge) ===
shoulder_inset_x = 65;  // Distance from center
shoulder_y = 35;        // Y position from KiCad (15, 2.5) → enc_y=35
shoulder_w = 28;
shoulder_h = 10;

// === M3 screw dimensions (countersunk from back) ===
m3_head_d = 6.5;        // M3 button head + clearance
m3_head_depth = 1.8;    // Head recess depth
m3_clear_d = 3.2;       // M3 shaft clearance hole

// === Button cap design (retention flange + actuator stem) ===
btn_flange_extra = 3;    // Flange wider than cutout (mm total)
btn_flange_h = 0.8;      // Flange thickness
btn_stem_d = 2.0;        // Actuator stem diameter
btn_stem_h = 2.0;        // Stem length toward PCB tactile switch

// === USB-C port (bottom center) ===
usbc_x = 0;
usbc_z = bot_d - 1.5;   // Aligned with connector center just below PCB (pcb_z=bot_d)

// === SD card slot (bottom right) ===
sd_x = 60;
sd_z = bot_d - 1.5;     // Aligned with SD module center below PCB

// === Power switch (bottom edge, left of USB-C) ===
pwr_sw_x = -40;
pwr_sw_z = bot_d - 2.0; // Aligned with switch body center below PCB

// === Speaker grille (back panel, left side) ===
spk_x = -50;
spk_y = -15;
spk_diam = 22;

// === Battery (9.5 × 55 × 65 mm LiPo) ===
bat_w = 65;             // Width (X)
bat_h = 55;             // Height (Y)
bat_d = 9.5;            // Thickness (Z)
bat_offset_y = 3;       // Y offset from center

// === PCB (from KiCad: 160 × 75 mm, 4-layer 1.6mm, 6mm corner radius) ===
pcb_w = 160;
pcb_h = 75;
pcb_d = 1.6;
pcb_corner_r = 6;
pcb_z = bot_d;          // PCB bottom sits on screw boss tops at shell split

// === ESP32-S3-WROOM-1-N16R8 (bottom-mount on PCB) ===
esp_w = 25.5;
esp_h = 18.0;
esp_d = 3.0;            // Protrusion below PCB
esp_x = 0;              // KiCad (80, 27.5) → enc (0, 10)
esp_y = 10;

// === Alignment lip (tongue on bottom shell → inside top shell) ===
lip_h = 2.0;
lip_t = 1.0;
lip_clearance = 0.3;    // 3D-print tolerance

// === Z-axis stack (closed assembly) ===
// Z=0:      Bottom shell outer face
// Z=2:      Bottom shell floor (wall=2)
// Z=2-11.5: Battery (9.5mm)
// Z=12-15:  ESP32 module zone (3mm below PCB)
// Z=15:     PCB bottom face / shell split line
// Z=16.6:   PCB top face (1.6mm board)
// Z=15-23:  Top shell interior (8mm)
// Z=23:     Top shell ceiling
// Z=25:     Top shell outer face

// === Screw boss parameters ===
screw_d_outer = 6;
screw_d_inner = 2.5;
screw_boss_h = bot_d - wall;

// === Screw boss positions (4 corners + 2 center) ===
// 4 corner positions only (center 2 removed — they interfered with battery)
screw_positions = [
    [-body_w/2 + 15, body_h/2 - 12],    // Front-left
    [body_w/2 - 15, body_h/2 - 12],     // Front-right
    [-body_w/2 + 15, -body_h/2 + 12],   // Back-left
    [body_w/2 - 15, -body_h/2 + 12],    // Back-right
];

// ============================================================
// Rounded rectangle primitive
// ============================================================
module rounded_rect(w, h, r) {
    offset(r=r)
    offset(r=-r)
    square([w, h], center=true);
}

// ============================================================
// TOP SHELL (display side)
// ============================================================
module top_shell() {
    color([0.15, 0.15, 0.18])
    difference() {
        // Outer shell
        linear_extrude(height=top_d)
        rounded_rect(body_w, body_h, corner_r);

        // Hollow interior
        translate([0, 0, wall])
        linear_extrude(height=top_d)
        rounded_rect(body_w - wall*2, body_h - wall*2, corner_r - wall);

        // Display viewport cutout
        translate([0, disp_offset_y, 0])
        display_cutout(disp_w, disp_h, top_d + 1);

        // D-pad cutout
        translate([dpad_x, dpad_y, 0])
        dpad_cutout(dpad_arm_len, dpad_arm_w, top_d + 1);

        // ABXY button cutouts (diamond layout: A, B, X, Y)
        translate([abxy_x, abxy_y, 0])
        abxy_diamond(abxy_spacing, abxy_diam, top_d + 1);

        // Start button cutout (below D-pad, left) — KiCad SW9 BTN_START
        translate([ss_x - ss_spacing/2, ss_y, 0])
        pill_cutout(ss_w, ss_h, top_d + 1);

        // Select button cutout (below D-pad, right) — KiCad SW10 BTN_SELECT
        translate([ss_x + ss_spacing/2, ss_y, 0])
        pill_cutout(ss_w, ss_h, top_d + 1);

        // Menu button cutout (below ABXY, right side) — KiCad SW13 BTN_MENU
        translate([menu_x, menu_y, 0])
        pill_cutout(ss_w, ss_h, top_d + 1);

        // LED light pipe holes (below Start/Menu)
        translate([led1_x, led1_y, 0])
        cylinder(h=top_d + 1, d=led_d, $fn=16);
        translate([led2_x, led2_y, 0])
        cylinder(h=top_d + 1, d=led_d, $fn=16);

        // Groove for alignment lip from bottom shell
        translate([0, 0, top_d - lip_h])
        linear_extrude(height=lip_h + 0.1)
        rounded_rect(body_w - 2*(wall - lip_t - lip_clearance),
                      body_h - 2*(wall - lip_t - lip_clearance),
                      max(1, corner_r - wall + lip_t + lip_clearance));

    }

    // Display bezel (raised frame)
    color([0.1, 0.1, 0.12])
    translate([0, disp_offset_y, 0])
    display_bezel(disp_w, disp_h, disp_bezel, 0.8);

    // Button labels (engraved into surface)
    color([0.3, 0.3, 0.35]) {
        // D-pad arrows
        translate([dpad_x, dpad_y + dpad_arm_len + 3, 0.1])
        button_label("^", 2.5, 0.2);
        translate([dpad_x, dpad_y - dpad_arm_len - 3, 0.1])
        button_label("v", 2.5, 0.2);

        // ABXY labels
        translate([abxy_x + abxy_spacing + 5, abxy_y, 0.1])
        button_label("A", 2.5, 0.2);
        translate([abxy_x, abxy_y - abxy_spacing - 5, 0.1])
        button_label("B", 2.5, 0.2);
        translate([abxy_x, abxy_y + abxy_spacing + 5, 0.1])
        button_label("X", 2.5, 0.2);
        translate([abxy_x - abxy_spacing - 5, abxy_y, 0.1])
        button_label("Y", 2.5, 0.2);

        // Start/Select labels (below D-pad)
        translate([ss_x - ss_spacing/2, ss_y - ss_h - 2, 0.1])
        button_label("STA", 2, 0.2);
        translate([ss_x + ss_spacing/2, ss_y - ss_h - 2, 0.1])
        button_label("SEL", 2, 0.2);

        // Menu label (below ABXY)
        translate([menu_x, menu_y - ss_h - 2, 0.1])
        button_label("M", 2, 0.2);

    }
}

// ============================================================
// BOTTOM SHELL (battery side)
// ============================================================
module bottom_shell() {
    color([0.18, 0.18, 0.22])
    difference() {
        // Outer shell
        linear_extrude(height=bot_d)
        rounded_rect(body_w, body_h, corner_r);

        // Hollow interior
        translate([0, 0, wall])
        linear_extrude(height=bot_d)
        rounded_rect(body_w - wall*2, body_h - wall*2, corner_r - wall);

        // USB-C port cutout (bottom edge, centered)
        translate([usbc_x, -body_h/2, usbc_z])
        rotate([90, 0, 0])
        usbc_cutout(9.0, 3.2, wall + 2);

        // SD card slot cutout (bottom edge, right)
        translate([sd_x, -body_h/2, sd_z])
        rotate([90, 0, 0])
        sd_slot_cutout(12, 2.5, wall + 2);

        // Power switch cutout (bottom edge, left of USB-C)
        translate([pwr_sw_x, -body_h/2, pwr_sw_z])
        rotate([90, 0, 0])
        power_switch_cutout(8, 4, wall + 2);

        // Speaker grille (back face, z=0)
        translate([spk_x, spk_y, 0])
        speaker_grille(spk_diam, 1.5, 3.5, wall + 1);

        // Battery compartment (5mm length tolerance)
        translate([0, bat_offset_y, wall])
        battery_compartment(bat_w + 5, bat_h, bat_d);

        // M3 screw counterbores on 4 corner positions (flush with exterior)
        for (i = [0:3]) {
            translate([screw_positions[i][0], screw_positions[i][1], 0]) {
                // Counterbore recess for screw head
                translate([0, 0, -0.1])
                cylinder(h=m3_head_depth + 0.1, d=m3_head_d, $fn=24);
                // Clearance hole through floor
                translate([0, 0, -0.1])
                cylinder(h=wall + 0.2, d=m3_clear_d, $fn=24);
            }
        }

        // Wire channel for battery cable
        translate([bat_w/2 + 2, 3, wall])
        wire_channel(15, 4, 3);

        // L shoulder button cutout (back face) — KiCad SW11 at enc (-65, 35)
        translate([-shoulder_inset_x, shoulder_y, 0])
        shoulder_button_cutout(shoulder_w, shoulder_h, wall + 1);

        // R shoulder button cutout (back face) — KiCad SW12 at enc (65, 35)
        translate([shoulder_inset_x, shoulder_y, 0])
        shoulder_button_cutout(shoulder_w, shoulder_h, wall + 1);
    }

    // Screw bosses
    color([0.18, 0.18, 0.22])
    for (pos = screw_positions) {
        translate([pos[0], pos[1], wall]) {
            difference() {
                cylinder(h=screw_boss_h, d=screw_d_outer, $fn=24);
                translate([0, 0, -0.1])
                cylinder(h=screw_boss_h + 0.2, d=screw_d_inner, $fn=24);
            }
        }
    }

    // Battery retaining clips (4 overhanging lips to hold battery down)
    bat_clip_w = 8;
    bat_clip_overhang = 1.5;
    bat_clip_h = 2;
    color([0.18, 0.18, 0.22])
    for (side = [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
        cx = side[0] * ((bat_w + 5) / 2 + 0.5);
        cy = bat_offset_y + side[1] * (bat_h / 2 + 0.5);
        translate([cx, cy, wall + bat_d - bat_clip_h]) {
            if (abs(side[0]) > 0) {
                // Left/right clips: extend inward
                translate([-side[0] * bat_clip_overhang/2, 0, 0])
                cube([bat_clip_overhang, bat_clip_w, bat_clip_h], center=true);
            } else {
                // Top/bottom clips: extend inward
                translate([0, -side[1] * bat_clip_overhang/2, 0])
                cube([bat_clip_w, bat_clip_overhang, bat_clip_h], center=true);
            }
        }
    }

    // Battery compartment border wall (raised edge around bay)
    bat_border_w = 1.5;    // Border wall thickness
    bat_border_h = bat_d;  // Same height as battery
    color([0.18, 0.18, 0.22])
    translate([0, bat_offset_y, wall])
    linear_extrude(height=bat_border_h)
    difference() {
        offset(r=3) offset(r=-3)
        square([bat_w + 5 + bat_border_w*2, bat_h + bat_border_w*2], center=true);
        offset(r=3) offset(r=-3)
        square([bat_w + 5, bat_h], center=true);
    }

    // Alignment lip (tongue extending upward into top shell)
    color([0.18, 0.18, 0.22])
    translate([0, 0, bot_d])
    linear_extrude(height=lip_h)
    difference() {
        rounded_rect(body_w - 2*(wall - lip_t),
                      body_h - 2*(wall - lip_t),
                      max(1, corner_r - wall + lip_t));
        rounded_rect(body_w - 2*wall,
                      body_h - 2*wall,
                      max(1, corner_r - wall));
    }

    // Shoulder button labels (engraved on back face)
    color([0.3, 0.3, 0.35]) {
        translate([-shoulder_inset_x, shoulder_y + shoulder_h/2 + 2, -0.1])
        button_label("L", 2.5, 0.2);
        translate([shoulder_inset_x, shoulder_y + shoulder_h/2 + 2, -0.1])
        button_label("R", 2.5, 0.2);
    }
}

// ============================================================
// SIMULATED DISPLAY (for assembly renders)
// ============================================================
module display_sim() {
    color([0.05, 0.05, 0.1])
    translate([0, disp_offset_y, 1])
    linear_extrude(height=0.5)
    square([disp_w - 1, disp_h - 1], center=true);
}

// ============================================================
// PCB MODEL (from KiCad: 160x75mm, 6mm corners, 1.6mm thick)
// ============================================================
module pcb_model() {
    // PCB board outline
    color([0.0, 0.5, 0.2, 0.8])
    linear_extrude(height=pcb_d)
    rounded_rect(pcb_w, pcb_h, pcb_corner_r);

    // ESP32-S3-WROOM-1-N16R8 (bottom-mounted, hangs below PCB)
    color([0.1, 0.1, 0.1])
    translate([esp_x, esp_y, -esp_d])
    translate([-esp_w/2, -esp_h/2, 0])
    cube([esp_w, esp_h, esp_d]);

    // LCD FPC connector (top-mounted) — KiCad (135,35.5) → enc (55, 2)
    color([0.8, 0.8, 0.7])
    translate([55, 2, pcb_d])
    linear_extrude(height=1.0)
    square([6, 30], center=true);

    // USB-C connector — KiCad (80,72) → enc (0, -34.5)
    color([0.7, 0.7, 0.7])
    translate([usbc_x, -pcb_h/2 + 3.5, -1.5])
    cube([9, 7, pcb_d + 3], center=true);

    // SD card module — KiCad (140,67) → enc (60, -29.5)
    color([0.6, 0.6, 0.6])
    translate([sd_x, -pcb_h/2 + 7.5, -2])
    cube([15, 15, 2], center=true);

    // Power switch — KiCad (40,72) → enc (-40, -34.5)
    color([0.5, 0.5, 0.5])
    translate([pwr_sw_x, -pcb_h/2 + 3, pcb_d])
    cube([8, 4, 2], center=true);

    // IP5306 power management IC — KiCad (110, 42.5) → enc (30, -5)
    color([0.15, 0.15, 0.15])
    translate([30, -5, pcb_d])
    cube([5, 5, 1], center=true);

    // Mounting holes (visual)
    color([0.8, 0.8, 0.0, 0.5])
    for (pos = screw_positions) {
        translate([pos[0], pos[1], -0.1])
        cylinder(h=pcb_d + 0.2, d=2.5, $fn=16);
    }
}

// ============================================================
// INDIVIDUAL BUTTON CAP MODULES (flange + stem design)
// Each cap has 3 parts:
//   1. Cap body — visible, fills the cutout with clearance
//   2. Retention flange — wider, rests on inner shell surface
//   3. Actuator stem — thin post pressing the PCB tactile switch
// ============================================================

// Z reference: inner ceiling of top shell in assembly coordinates
z_inner = body_d - wall;  // =23mm

// ---- D-pad cap (cross shape + 4 stems at arm tips) ----
module cap_dpad() {
    translate([dpad_x, dpad_y, 0]) {
        // Cap body (visible cross, in cutout)
        translate([0, 0, z_inner])
        linear_extrude(height=wall + 0.3) {
            square([dpad_arm_len*2 - 1, dpad_arm_w - 0.5], center=true);
            square([dpad_arm_w - 0.5, dpad_arm_len*2 - 1], center=true);
        }
        // Retention flange (wider cross, rests on inner ceiling)
        translate([0, 0, z_inner - btn_flange_h])
        linear_extrude(height=btn_flange_h) {
            square([dpad_arm_len*2 + btn_flange_extra, dpad_arm_w + btn_flange_extra], center=true);
            square([dpad_arm_w + btn_flange_extra, dpad_arm_len*2 + btn_flange_extra], center=true);
        }
        // Actuator stems at 4 arm tips (press D-pad switches)
        for (pos = [[dpad_arm_len - 3, 0], [-(dpad_arm_len - 3), 0],
                     [0, dpad_arm_len - 3], [0, -(dpad_arm_len - 3)]])
            translate([pos[0], pos[1], z_inner - btn_flange_h - btn_stem_h])
            cylinder(h=btn_stem_h, d=btn_stem_d, $fn=16);
    }
}

// ---- ABXY circular button caps (flange + center stem) ----
module _abxy_cap(cx, cy) {
    // Cap body (visible circle, in cutout)
    translate([cx, cy, z_inner])
    cylinder(h=wall + 0.3, d=abxy_diam - 1, $fn=32);
    // Retention flange
    translate([cx, cy, z_inner - btn_flange_h])
    cylinder(h=btn_flange_h, d=abxy_diam + btn_flange_extra, $fn=32);
    // Actuator stem
    translate([cx, cy, z_inner - btn_flange_h - btn_stem_h])
    cylinder(h=btn_stem_h, d=btn_stem_d, $fn=16);
}

module cap_btn_a() { _abxy_cap(abxy_x + abxy_spacing, abxy_y); }
module cap_btn_b() { _abxy_cap(abxy_x, abxy_y - abxy_spacing); }
module cap_btn_x() { _abxy_cap(abxy_x, abxy_y + abxy_spacing); }
module cap_btn_y() { _abxy_cap(abxy_x - abxy_spacing, abxy_y); }

// ---- Pill-shaped caps (Start, Menu, Select) ----
module _pill_cap(cx, cy) {
    ss_r = (ss_h - 0.5) / 2;           // Cap body radius (with clearance)
    fl_r = (ss_h + btn_flange_extra) / 2;  // Flange radius
    fl_span = (ss_w + btn_flange_extra) / 2 - fl_r;
    // Cap body (visible pill, in cutout)
    translate([cx, cy, z_inner])
    linear_extrude(height=wall + 0.2)
    hull() {
        translate([-(ss_w/2 - ss_r - 0.25), 0]) circle(r=ss_r, $fn=24);
        translate([(ss_w/2 - ss_r - 0.25), 0]) circle(r=ss_r, $fn=24);
    }
    // Retention flange (wider pill)
    translate([cx, cy, z_inner - btn_flange_h])
    linear_extrude(height=btn_flange_h)
    hull() {
        translate([-fl_span, 0]) circle(r=fl_r, $fn=24);
        translate([fl_span, 0]) circle(r=fl_r, $fn=24);
    }
    // Actuator stem
    translate([cx, cy, z_inner - btn_flange_h - btn_stem_h])
    cylinder(h=btn_stem_h, d=btn_stem_d, $fn=16);
}

module cap_start()  { _pill_cap(ss_x - ss_spacing/2, ss_y); }
module cap_select() { _pill_cap(ss_x + ss_spacing/2, ss_y); }
module cap_menu()   { _pill_cap(menu_x, menu_y); }

// ---- Shoulder button caps (on bottom shell back face) ----
module _shoulder_cap(cx) {
    cy = shoulder_y;
    sh_r = shoulder_h / 2 - 0.5;
    fl_r = (shoulder_h + btn_flange_extra) / 2;
    fl_span = (shoulder_w + btn_flange_extra) / 2 - fl_r;
    // Cap body (protrudes through back face cutout)
    translate([cx, cy, -0.2])
    linear_extrude(height=wall + 0.2)
    hull() {
        translate([-(shoulder_w/2 - sh_r - 0.25), 0]) circle(r=sh_r, $fn=24);
        translate([(shoulder_w/2 - sh_r - 0.25), 0]) circle(r=sh_r, $fn=24);
    }
    // Retention flange (on inner surface of bottom shell wall)
    translate([cx, cy, wall])
    linear_extrude(height=btn_flange_h)
    hull() {
        translate([-fl_span, 0]) circle(r=fl_r, $fn=24);
        translate([fl_span, 0]) circle(r=fl_r, $fn=24);
    }
    // Actuator stem (toward PCB)
    translate([cx, cy, wall + btn_flange_h])
    cylinder(h=btn_stem_h, d=btn_stem_d, $fn=16);
}

module cap_shoulder_l() { _shoulder_cap(-shoulder_inset_x); }
module cap_shoulder_r() { _shoulder_cap(shoulder_inset_x); }

// Composite: all button caps together
module button_caps() {
    color([0.25, 0.25, 0.28]) cap_dpad();
    color([0.8, 0.2, 0.2])   cap_btn_a();
    color([0.8, 0.8, 0.2])   cap_btn_b();
    color([0.2, 0.4, 0.8])   cap_btn_x();
    color([0.2, 0.7, 0.3])   cap_btn_y();
    color([0.35, 0.35, 0.38]) cap_start();
    color([0.35, 0.35, 0.38]) cap_menu();
    color([0.35, 0.35, 0.38]) cap_select();
    color([0.25, 0.25, 0.28]) cap_shoulder_l();
    color([0.25, 0.25, 0.28]) cap_shoulder_r();
}

// ============================================================
// ASSEMBLY (top + bottom shells together)
// ============================================================
module assembly() {
    bottom_shell();

    translate([0, 0, body_d])
    mirror([0, 0, 1])
    top_shell();

    // PCB at shell split line
    translate([0, 0, pcb_z])
    pcb_model();

    translate([0, 0, body_d - top_d])
    display_sim();

    button_caps();
}

// ============================================================
// EXPLODED VIEW
// ============================================================
module exploded_view() {
    explode_gap = 35;

    // Bottom shell (in place)
    bottom_shell();

    // Top shell (lifted)
    translate([0, 0, body_d + explode_gap])
    mirror([0, 0, 1])
    top_shell();

    // Battery (in bottom shell area)
    translate([0, bat_offset_y, wall + 1])
    color([0.3, 0.3, 0.7, 0.7])
    linear_extrude(height=bat_d)
    rounded_rect(bat_w, bat_h, 3);

    // PCB with components (lifted above bottom shell)
    translate([0, 0, bot_d + explode_gap * 0.2])
    pcb_model();

    // Display module (above PCB, below top shell)
    translate([0, disp_offset_y, bot_d + explode_gap * 0.5])
    color([0.1, 0.1, 0.15])
    linear_extrude(height=2)
    square([disp_pcb_w, disp_pcb_h], center=true);

    // Button caps (near top shell)
    translate([0, 0, explode_gap * 0.7])
    button_caps();
}

// ============================================================
// ASSEMBLY WITH INTERNALS (for cross-section and fit-check)
// ============================================================
module assembly_internal() {
    bottom_shell();

    translate([0, 0, body_d])
    mirror([0, 0, 1])
    top_shell();

    // PCB
    translate([0, 0, pcb_z])
    pcb_model();

    // Battery
    translate([0, bat_offset_y, wall])
    color([0.3, 0.3, 0.7, 0.7])
    linear_extrude(height=bat_d)
    rounded_rect(bat_w, bat_h, 3);

    // Display module (on top of PCB)
    translate([0, disp_offset_y, pcb_z + pcb_d + 0.5])
    color([0.1, 0.1, 0.15])
    linear_extrude(height=2)
    square([disp_pcb_w, disp_pcb_h], center=true);

    button_caps();
}

// ============================================================
// CROSS-SECTION VIEW (XZ plane, cut at Y=0, front removed)
// ============================================================
module cross_section() {
    difference() {
        assembly_internal();
        // Cut away front half (Y < 0) to expose Z-stack from front
        translate([0, -body_h/4 - 0.5, body_d/2])
        cube([body_w + 10, body_h/2 + 1, body_d + 10], center=true);
    }
}

// ============================================================
// FIT-CHECK VIEW (transparent shells, solid internals)
// ============================================================
module fit_check() {
    // Bottom shell only (open-top view to verify internal fit)
    bottom_shell();

    // PCB on screw bosses
    translate([0, 0, pcb_z])
    pcb_model();

    // Battery in compartment
    translate([0, bat_offset_y, wall])
    color([0.3, 0.3, 0.7, 0.7])
    linear_extrude(height=bat_d)
    rounded_rect(bat_w, bat_h, 3);

    // Display module on PCB
    translate([0, disp_offset_y, pcb_z + pcb_d + 0.5])
    color([0.1, 0.1, 0.15])
    linear_extrude(height=2)
    square([disp_pcb_w, disp_pcb_h], center=true);
}

// ============================================================
// BATTERY FIT VIEW (bottom shell + battery only)
// ============================================================
module battery_fit() {
    bottom_shell();

    // Battery in compartment (exact dimensions)
    translate([0, bat_offset_y, wall])
    color([0.3, 0.3, 0.7, 0.85])
    linear_extrude(height=bat_d)
    rounded_rect(bat_w, bat_h, 3);
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
} else if (part == "fit_check") {
    fit_check();
} else if (part == "pcb") {
    pcb_model();
} else if (part == "battery_fit") {
    battery_fit();
// --- Individual part exports for colored 3D viewer ---
} else if (part == "case_top") {
    translate([0, 0, body_d]) mirror([0, 0, 1]) top_shell();
} else if (part == "case_bottom") {
    bottom_shell();
} else if (part == "part_display") {
    translate([0, 0, body_d - top_d]) display_sim();
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
}
