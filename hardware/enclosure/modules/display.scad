// ESP32 Emu Turbo — Display cutout and bezel modules
// All dimensions in mm

// ST7796S 4.0" display module dimensions
// Active area: ~86.4 x 64.8 mm (approximate for 4.0" 320x480)
// Module PCB: ~98 x 72 mm (approximate)

// Display viewport cutout (visible area)
module display_cutout(width=86.4, height=64.8, depth=5, corner_r=1.5) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2) {
        offset(r=corner_r)
        offset(r=-corner_r)
        square([width, height], center=true);
    }
}

// Display bezel frame (raised border around display)
module display_bezel(width=86.4, height=64.8, bezel=2, depth=1, corner_r=1.5) {
    outer_w = width + bezel * 2;
    outer_h = height + bezel * 2;

    difference() {
        linear_extrude(height=depth) {
            offset(r=corner_r)
            offset(r=-corner_r)
            square([outer_w, outer_h], center=true);
        }
        translate([0, 0, -0.1])
        linear_extrude(height=depth+0.2) {
            offset(r=corner_r)
            offset(r=-corner_r)
            square([width, height], center=true);
        }
    }
}

// Internal ledge/shelf to hold the display module
module display_shelf(width=98, height=72, shelf_width=2, depth=2) {
    difference() {
        linear_extrude(height=depth)
        square([width + shelf_width*2, height + shelf_width*2], center=true);

        translate([0, 0, -0.1])
        linear_extrude(height=depth+0.2)
        square([width, height], center=true);
    }
}

// Display mounting tabs (snap-fit clips)
module display_mount_tab(tab_width=5, tab_height=2, tab_depth=1.5) {
    cube([tab_width, tab_depth, tab_height], center=true);
}
