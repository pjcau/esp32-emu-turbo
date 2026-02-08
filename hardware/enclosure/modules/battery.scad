// ESP32 Emu Turbo — Battery compartment modules
// All dimensions in mm

// LiPo 105080: 50mm x 80mm x 10mm, ~5000mAh

// Battery compartment cavity (recessed into bottom shell)
module battery_compartment(width=82, height=52, depth=11, corner_r=3) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.1) {
        offset(r=corner_r)
        offset(r=-corner_r)
        square([width, height], center=true);
    }
}

// Battery retainer clips (friction-fit tabs along edges)
module battery_retainer_clip(width=8, height=1.5, depth=3) {
    // L-shaped clip
    union() {
        // Vertical wall
        cube([width, depth, height], center=true);
        // Horizontal lip
        translate([0, depth/2 - 0.5, -height/2 + 0.5])
        cube([width, 1.0, 1.0], center=true);
    }
}

// Battery compartment with retainer clips on all four sides
module battery_bay(width=82, height=52, depth=11, corner_r=3) {
    difference() {
        // Outer wall (slightly larger)
        linear_extrude(height=depth) {
            offset(r=corner_r)
            offset(r=-corner_r)
            square([width + 3, height + 3], center=true);
        }
        // Inner cavity
        battery_compartment(width, height, depth, corner_r);
    }

    // Retainer clips
    clip_offset_x = width / 2 + 1;
    clip_offset_y = height / 2 + 1;

    // Left and right clips
    for (x = [-1, 1]) {
        translate([x * clip_offset_x, 0, depth - 1.5])
        rotate([0, 0, x > 0 ? 0 : 180])
        battery_retainer_clip();
    }
    // Top and bottom clips
    for (y = [-1, 1]) {
        translate([0, y * clip_offset_y, depth - 1.5])
        rotate([0, 0, y > 0 ? 90 : -90])
        battery_retainer_clip();
    }
}

// Wire channel for battery connector cable
module wire_channel(length=15, width=4, depth=3) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.1) {
        square([length, width], center=true);
    }
}
