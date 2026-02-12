// ESP32 Emu Turbo — Port cutout modules
// All dimensions in mm

// USB-C port cutout (rounded rectangle)
module usbc_cutout(width=9.0, height=3.2, depth=5) {
    r = height / 2;
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2) {
        hull() {
            translate([-(width/2 - r), 0]) circle(r=r, $fn=24);
            translate([(width/2 - r), 0]) circle(r=r, $fn=24);
        }
    }
}

// SD card slot cutout
module sd_slot_cutout(width=12, height=2.5, depth=5) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2) {
        square([width, height], center=true);
    }
}

// Speaker grille — array of small holes in a circular pattern
module speaker_grille(outer_diameter=22, hole_diameter=1.5, hole_spacing=3.5, depth=5) {
    r_max = outer_diameter / 2 - hole_diameter;

    translate([0, 0, -0.1])
    for (x = [-r_max : hole_spacing : r_max]) {
        for (y = [-r_max : hole_spacing : r_max]) {
            if (sqrt(x*x + y*y) <= r_max) {
                translate([x, y, 0])
                cylinder(h=depth+0.2, d=hole_diameter, $fn=16);
            }
        }
    }
}

// Power slide switch cutout (SS-12D00G3)
module power_switch_cutout(width=8, height=4, depth=5) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2) {
        square([width, height], center=true);
    }
}

// Headphone jack cutout (3.5mm, optional)
module headphone_jack_cutout(diameter=6.5, depth=5) {
    translate([0, 0, -0.1])
    cylinder(h=depth+0.2, d=diameter, $fn=24);
}

// Ventilation slot (single slot)
module vent_slot(width=15, height=1.2, depth=5) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2) {
        hull() {
            translate([-(width/2 - height/2), 0]) circle(r=height/2, $fn=16);
            translate([(width/2 - height/2), 0]) circle(r=height/2, $fn=16);
        }
    }
}

// Multiple ventilation slots
module vent_slots(count=3, width=15, height=1.2, spacing=3, depth=5) {
    total_h = (count - 1) * spacing;
    for (i = [0 : count-1]) {
        translate([0, -total_h/2 + i * spacing, 0])
        vent_slot(width, height, depth);
    }
}
