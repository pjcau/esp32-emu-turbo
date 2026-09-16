#!/usr/bin/env python3
"""Mutation tests for verify_enclosure_requirements.py — every user
requirement must be able to FAIL.

Each case mutates a copy of enclosure.scad (written next to it, so the
OpenSCAD container can still `include` pcb_parts.scad and export the
labels) and demands the requirements gate objects:

    Q1  speaker to the -X side                 R5 speaker      -> exit 1
    Q2  cable riser 3.1 -> 2.5                 R1 stack        -> exit 1
    Q3  ABXY back to o8                        R7 sizes        -> exit 1
    Q4  "A" label engraved beside the D-pad    R9 labels       -> exit 1
    Q5  insert socket oversize (3.1 -> 3.6)    R6 insert       -> exit 1
    Q6  M2.5x25 screw (tip through the roof)   R6 screw        -> exit 1
    Q7  gusset thinned to 0.8                  R6 columns      -> exit 1
    Q8  extension board 100 mm long            R3 extension    -> exit 1
    Q9  Menu pill grown into the LED web       R4 LEDs         -> exit 1
    Q10 battery pocket back to the 80 mm cell  R10 battery     -> exit 1
    Q11 top labels engraved mirrored           R9 chirality    -> exit 1
    Q12 strap thinned to 0.6 mm                R11 hold-down   -> exit 1
    Q13 lever hook tongue back to 3 mm         R8 thin walls   -> exit 1
    Q14 lip groove skin back to 0.7 mm         R8 thin walls   -> exit 1
    Q15 SD slot cut 2 mm into the shelf        R12 measured    -> exit 1
    Q16 unmutated file                         all green       -> exit 0
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_enclosure_sync as ves                 # noqa: E402
import verify_enclosure_requirements as ver         # noqa: E402

ORIGINAL = ves.SCAD.read_text()
MUT = ves.SCAD.with_name("_mutation_under_test.scad")


def run_with(text: str) -> int:
    MUT.write_text(text)
    real = ves.SCAD
    try:
        ves.SCAD = MUT
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                return ver.main()
        except ves.Structural:
            return 2
    finally:
        ves.SCAD = real
        MUT.unlink(missing_ok=True)


def mutate(old: str, new: str) -> str:
    if ORIGINAL.count(old) != 1:
        raise AssertionError(
            f"mutation anchor not unique ({ORIGINAL.count(old)}x): {old!r}")
    return ORIGINAL.replace(old, new)


def main() -> int:
    print("=" * 72)
    print("ENCLOSURE-REQUIREMENTS GATE MUTATION SUITE")
    print("=" * 72)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    cases = [
        ("Q1 speaker on the wrong side", "spk_x = 63.5;", "spk_x = -63.5;", 1),
        ("Q2 cable riser gone", "disp_riser = 3.1;", "disp_riser = 2.5;", 1),
        ("Q3 ABXY shrunk back", "abxy_diam = 9; ", "abxy_diam = 8; ", 1),
        ("Q4 label A beside the D-pad",
         'face_label(abxy_x + abxy_offsets[0][0], abxy_y + abxy_offsets[0][1] + abxy_diam/2 + 2, "A", 2.5);',
         'face_label(dpad_x, dpad_y + dpad_arm_len + 6, "A", 2.5);', 1),
        ("Q5 insert socket oversize", "insert_hole_d = 3.1;", "insert_hole_d = 3.6;", 1),
        ("Q5b insert wall thinned to 1.5", "insert_wall = 2.0;", "insert_wall = 1.5;", 1),
        ("Q6 screw through the roof", "screw_len = 20;", "screw_len = 25;", 1),
        ("Q7 gusset too thin", "boss_gusset_t = 1.5;", "boss_gusset_t = 0.8;", 1),
        ("Q8 extension board past the glass edge", "ext_l = 28;", "ext_l = 100;", 1),
        ("Q9 Menu pill into the LED web", "menu_h = 3.8;", "menu_h = 5.5;", 1),
        ("Q10 pocket back to the 80 mm cell", "bat_w = 90; ", "bat_w = 80; ", 1),
        ("Q11 top labels mirrored",
         "module face_label(x, y, txt, size, mirrored=false) {",
         "module face_label(x, y, txt, size, mirrored=true) {", 1),
        ("Q12 strap too thin", "bat_strap_t = 1.2;", "bat_strap_t = 0.6;", 1),
        ("Q13 lever hook walls thin again", "lever_tongue_w = 5.0;",
         "lever_tongue_w = 3.0;", 1),
        ("Q14 lip skin back to 0.7 mm", "lip_clearance = 0.2;", "lip_clearance = 0.7;", 1),
        ("Q15 SD slot cuts a sliver off the shelf",
         "sd_slot_cutout(sd_cut_w, sd_cut_h, side_wall + 0.2);",
         "sd_slot_cutout(sd_cut_w, sd_cut_h, side_wall + 2);", 1),
    ]
    for name, old, new, want in cases:
        rc = run_with(mutate(old, new))
        check(name, rc == want, f"rc={rc}, want {want}")

    rc = run_with(ORIGINAL)
    check("Q16 unmutated file passes", rc == 0, f"rc={rc}")

    print("-" * 72)
    if failures:
        print(f"Results: FAIL — {len(failures)} case(s): {', '.join(failures)}")
        return 1
    print(f"Results: PASS — {len(cases) + 1}/{len(cases) + 1} scad mutations detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
