// ESP32 Emu Turbo — Button cutout modules
// All dimensions in mm

// Cross-shaped D-pad cutout
module dpad_cutout(arm_length=12, arm_width=5, depth=5) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2) {
        // Horizontal arm
        square([arm_length*2, arm_width], center=true);
        // Vertical arm
        square([arm_width, arm_length*2], center=true);
    }
}

// Circular face button cutout
module face_button_cutout(diameter=8, depth=5) {
    translate([0, 0, -0.1])
    cylinder(h=depth+0.2, d=diameter, $fn=32);
}

// Pill-shaped (stadium) cutout for Start/Select
module pill_cutout(width=10, height=4, depth=5) {
    r = height / 2;
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2) {
        hull() {
            translate([-(width/2 - r), 0]) circle(r=r, $fn=24);
            translate([(width/2 - r), 0]) circle(r=r, $fn=24);
        }
    }
}

// Shoulder button cutout (rectangular with rounded ends)
module shoulder_button_cutout(width=20, height=8, depth=5) {
    r = height / 2;
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2) {
        hull() {
            translate([-(width/2 - r), 0]) circle(r=r, $fn=24);
            translate([(width/2 - r), 0]) circle(r=r, $fn=24);
        }
    }
}

// ABXY diamond layout (4 face buttons in diamond pattern)
module abxy_diamond(spacing=13, diameter=8, depth=5) {
    // A = right
    translate([spacing, 0, 0]) face_button_cutout(diameter, depth);
    // B = bottom
    translate([0, -spacing, 0]) face_button_cutout(diameter, depth);
    // X = top
    translate([0, spacing, 0]) face_button_cutout(diameter, depth);
    // Y = left
    translate([-spacing, 0, 0]) face_button_cutout(diameter, depth);
}

// Internal button support post (cylinder on the inner wall)
module button_support_post(outer_d=5, inner_d=2.5, height=4) {
    difference() {
        cylinder(h=height, d=outer_d, $fn=24);
        translate([0, 0, -0.1])
        cylinder(h=height+0.2, d=inner_d, $fn=24);
    }
}

// Button labels (for visual reference in renders)
module button_label(text_str, size=3, depth=0.3) {
    linear_extrude(height=depth)
    text(text_str, size=size, halign="center", valign="center", font="Liberation Sans:style=Bold");
}
