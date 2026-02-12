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
part = "assembly";  // "assembly", "top", "bottom", "exploded"

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
abxy_spacing = 13;
abxy_diam = 8;
// Y button (leftmost) at x = 62-13 = 49, display edge at 43.2 → 5.8mm clearance

// === Start/Select (below D-pad, left side) ===
ss_x = dpad_x;          // Centered horizontally under D-pad
ss_y = dpad_y - 22;     // Below D-pad
ss_spacing = 16;        // Horizontal distance between Start and Select
ss_w = 10;              // Pill width
ss_h = 4;               // Pill height

// === Shoulder buttons (L/R on back side, near top edge) ===
shoulder_inset_x = 65;  // Distance from center (moved to corners)
shoulder_w = 20;
shoulder_h = 7;

// === USB-C port (bottom center) ===
usbc_x = 0;
usbc_z = bot_d / 2;     // Centered vertically on bottom edge

// === SD card slot (bottom right) ===
sd_x = 60;
sd_z = bot_d / 2;

// === Power switch (bottom edge, left of USB-C) ===
pwr_sw_x = -40;
pwr_sw_z = bot_d / 2;

// === Speaker grille (back panel, left side) ===
spk_x = -50;
spk_y = -15;
spk_diam = 22;

// === Battery compartment (LiPo 105080) ===
bat_w = 82;
bat_h = 52;
bat_d = 11;

// === Screw boss parameters ===
screw_d_outer = 6;
screw_d_inner = 2.5;
screw_boss_h = bot_d - wall;

// === Screw boss positions (4 corners + 2 center) ===
screw_positions = [
    [-body_w/2 + 15, body_h/2 - 12],
    [body_w/2 - 15, body_h/2 - 12],
    [-body_w/2 + 15, -body_h/2 + 12],
    [body_w/2 - 15, -body_h/2 + 12],
    [-25, 0],
    [25, 0]
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

        // Start button cutout (below D-pad, left)
        translate([ss_x - ss_spacing/2, ss_y, 0])
        pill_cutout(ss_w, ss_h, top_d + 1);

        // Select button cutout (below D-pad, right)
        translate([ss_x + ss_spacing/2, ss_y, 0])
        pill_cutout(ss_w, ss_h, top_d + 1);

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
        button_label("SEL", 2, 0.2);
        translate([ss_x + ss_spacing/2, ss_y - ss_h - 2, 0.1])
        button_label("STA", 2, 0.2);

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

        // Battery compartment
        translate([0, 3, wall])
        battery_compartment(bat_w, bat_h, bat_d);

        // Wire channel for battery cable
        translate([bat_w/2 + 2, 3, wall])
        wire_channel(15, 4, 3);

        // L shoulder button cutout (back face, near top edge)
        translate([-shoulder_inset_x, body_h/2 - shoulder_h/2, 0])
        shoulder_button_cutout(shoulder_w, shoulder_h, wall + 1);

        // R shoulder button cutout (back face, near top edge)
        translate([shoulder_inset_x, body_h/2 - shoulder_h/2, 0])
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

    // Shoulder button labels (engraved on back face)
    color([0.3, 0.3, 0.35]) {
        translate([-shoulder_inset_x, body_h/2 - 2, -0.1])
        button_label("L", 2.5, 0.2);
        translate([shoulder_inset_x, body_h/2 - 2, -0.1])
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
// INDIVIDUAL BUTTON CAP MODULES (for per-part STL export)
// ============================================================
cap_h = 1.5;

module cap_dpad() {
    translate([dpad_x, dpad_y, body_d - cap_h])
    linear_extrude(height=cap_h + 0.3) {
        square([dpad_arm_len*2 - 1, dpad_arm_w - 0.5], center=true);
        square([dpad_arm_w - 0.5, dpad_arm_len*2 - 1], center=true);
    }
}

module cap_btn_a() {
    translate([abxy_x + abxy_spacing, abxy_y, body_d - cap_h])
    cylinder(h=cap_h + 0.3, d=abxy_diam - 1, $fn=32);
}

module cap_btn_b() {
    translate([abxy_x, abxy_y - abxy_spacing, body_d - cap_h])
    cylinder(h=cap_h + 0.3, d=abxy_diam - 1, $fn=32);
}

module cap_btn_x() {
    translate([abxy_x, abxy_y + abxy_spacing, body_d - cap_h])
    cylinder(h=cap_h + 0.3, d=abxy_diam - 1, $fn=32);
}

module cap_btn_y() {
    translate([abxy_x - abxy_spacing, abxy_y, body_d - cap_h])
    cylinder(h=cap_h + 0.3, d=abxy_diam - 1, $fn=32);
}

module cap_start() {
    ss_r = (ss_h - 0.5) / 2;
    translate([ss_x - ss_spacing/2, ss_y, body_d - cap_h])
    linear_extrude(height=cap_h + 0.2)
    hull() {
        translate([-(ss_w/2 - ss_r - 0.25), 0]) circle(r=ss_r, $fn=24);
        translate([(ss_w/2 - ss_r - 0.25), 0]) circle(r=ss_r, $fn=24);
    }
}

module cap_select() {
    ss_r = (ss_h - 0.5) / 2;
    translate([ss_x + ss_spacing/2, ss_y, body_d - cap_h])
    linear_extrude(height=cap_h + 0.2)
    hull() {
        translate([-(ss_w/2 - ss_r - 0.25), 0]) circle(r=ss_r, $fn=24);
        translate([(ss_w/2 - ss_r - 0.25), 0]) circle(r=ss_r, $fn=24);
    }
}

module cap_shoulder_l() {
    sh_r = shoulder_h / 2 - 0.5;
    translate([-shoulder_inset_x, body_h/2 - shoulder_h/2, -0.2])
    linear_extrude(height=cap_h + 0.2)
    hull() {
        translate([-(shoulder_w/2 - sh_r - 0.25), 0]) circle(r=sh_r, $fn=24);
        translate([(shoulder_w/2 - sh_r - 0.25), 0]) circle(r=sh_r, $fn=24);
    }
}

module cap_shoulder_r() {
    sh_r = shoulder_h / 2 - 0.5;
    translate([shoulder_inset_x, body_h/2 - shoulder_h/2, -0.2])
    linear_extrude(height=cap_h + 0.2)
    hull() {
        translate([-(shoulder_w/2 - sh_r - 0.25), 0]) circle(r=sh_r, $fn=24);
        translate([(shoulder_w/2 - sh_r - 0.25), 0]) circle(r=sh_r, $fn=24);
    }
}

// Composite: all button caps together
module button_caps() {
    color([0.25, 0.25, 0.28]) cap_dpad();
    color([0.8, 0.2, 0.2])   cap_btn_a();
    color([0.8, 0.8, 0.2])   cap_btn_b();
    color([0.2, 0.4, 0.8])   cap_btn_x();
    color([0.2, 0.7, 0.3])   cap_btn_y();
    color([0.35, 0.35, 0.38]) cap_start();
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

    translate([0, 0, body_d - top_d])
    display_sim();

    button_caps();
}

// ============================================================
// EXPLODED VIEW
// ============================================================
module exploded_view() {
    explode_gap = 35;

    bottom_shell();

    translate([0, 0, body_d + explode_gap])
    mirror([0, 0, 1])
    top_shell();

    translate([0, 0, bot_d + explode_gap * 0.4])
    color([0.1, 0.1, 0.15])
    linear_extrude(height=2)
    square([disp_pcb_w, disp_pcb_h], center=true);

    translate([0, 3, wall + 2])
    color([0.3, 0.3, 0.7, 0.7])
    linear_extrude(height=bat_d - 2)
    rounded_rect(80, 50, 3);

    translate([0, -15, bot_d + explode_gap * 0.15])
    color([0.0, 0.5, 0.2, 0.8])
    linear_extrude(height=1.6)
    square([52, 26], center=true);
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
} else if (part == "part_select") {
    cap_select();
} else if (part == "part_shoulder_l") {
    cap_shoulder_l();
} else if (part == "part_shoulder_r") {
    cap_shoulder_r();
}
