// ESP32 Emu Turbo — Button cutout modules
// All dimensions in mm
//
// V2: every cutout is built from a 2D SHAPE module so the same outline
// can be reused for the through-wall cutout, the guide well under the
// ceiling, the countersunk flange seat and the cap body (offset inward
// by the print clearance). Keep the 2D shapes and the 3D cutouts in sync.

// ---- 2D shapes (nominal cutout outline, centered) ----

// Cross-shaped D-pad outline
module dpad_shape(arm_length=12, arm_width=5) {
    square([arm_length*2, arm_width], center=true);
    square([arm_width, arm_length*2], center=true);
}

// Circular face button outline
module face_button_shape(diameter=8) {
    circle(d=diameter, $fn=40);
}

// Pill (stadium) outline — Start/Select/Menu and shoulder levers
module pill_shape(width=10, height=4) {
    r = height / 2;
    hull() {
        translate([-(width/2 - r), 0]) circle(r=r, $fn=32);
        translate([(width/2 - r), 0]) circle(r=r, $fn=32);
    }
}

// ---- 3D cutouts (extruded shapes, +0.1 overshoot each end) ----

module dpad_cutout(arm_length=12, arm_width=5, depth=5) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2)
    dpad_shape(arm_length, arm_width);
}

module face_button_cutout(diameter=8, depth=5) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2)
    face_button_shape(diameter);
}

module pill_cutout(width=10, height=4, depth=5) {
    translate([0, 0, -0.1])
    linear_extrude(height=depth+0.2)
    pill_shape(width, height);
}

// Shoulder button cutout — same stadium outline as a pill
module shoulder_button_cutout(width=20, height=8, depth=5) {
    pill_cutout(width, height, depth);
}

// ---- Guide well + countersunk flange seat ----
//
// A ring hanging from the ceiling around a cutout. Its bore continues the
// cutout so the cap body is guided over wall + well_h instead of the wall
// alone; its far end is countersunk at 45° (stepped, printable) so the
// cap's conical flange self-centres and the flange plane stays outside
// the bore. children(0) = the 2D nominal cutout shape.
//   well_h   ring height below the ceiling
//   ring_t   ring wall thickness around the bore
//   sink_h   countersink height (== cap flange cone height)
//   sink_extra radial growth of the countersink at the far end
module guide_well(well_h=3, ring_t=1.5, sink_h=1.5, sink_extra=1.8) {
    steps = 5;
    difference() {
        linear_extrude(height=well_h)
        offset(r=ring_t + sink_extra) children(0);
        // bore
        translate([0, 0, -0.1])
        linear_extrude(height=well_h + 0.2) children(0);
        // stepped countersink at the far end (z = well_h)
        for (i = [0 : steps - 1])
            translate([0, 0, well_h - sink_h + i * sink_h / steps - 0.01])
            linear_extrude(height=sink_h / steps + 0.02)
            offset(delta=sink_extra * (i + 1) / steps) children(0);
    }
}

// Conical (stepped) flange for a cap: grows from the body outline to
// body + flange_extra over cone_h, then a flat flange plate of flat_h.
// children(0) = cap BODY 2D outline. z=0 is the flange's outer (well end
// face) plane; the cone rises toward +z (into the countersink), the flat
// plate lies below z=0.
module cap_flange(flange_extra=1.5, cone_h=1.5, flat_h=0.8) {
    steps = 5;
    // flat plate (outside the bore)
    translate([0, 0, -flat_h])
    linear_extrude(height=flat_h)
    offset(delta=flange_extra) children(0);
    // stepped cone inside the countersink
    for (i = [0 : steps - 1])
        translate([0, 0, i * cone_h / steps])
        linear_extrude(height=cone_h / steps + 0.01)
        offset(delta=flange_extra * (steps - i) / steps) children(0);
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
