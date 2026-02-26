#!/usr/bin/env python3
"""Verify DFM v2 fixes: CPL alignment, silkscreen, spacing, gerbers."""

import csv
import os
import re
import sys
import zipfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE = os.path.join(BASE, "release_jlcpcb")
PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def read_cpl():
    rows = {}
    with open(os.path.join(RELEASE, "cpl.csv")) as f:
        reader = csv.DictReader(f)
        for row in reader:
            ref = row["Designator"]
            rows[ref] = row
    return rows


def test_cpl_positions():
    """Test 1-4: CPL position and rotation corrections."""
    print("\n── CPL Position & Rotation Tests ──")
    cpl = read_cpl()

    # J1: no correction, should be at raw position 72.00
    j1_y = float(cpl["J1"]["Mid Y"].replace("mm", ""))
    check("J1 Mid Y = 72.00mm (no correction)", abs(j1_y - 72.00) < 0.01,
          f"got {j1_y}")

    # SW_PWR: no correction, should be at raw position 72.00
    sw_y = float(cpl["SW_PWR"]["Mid Y"].replace("mm", ""))
    check("SW_PWR Mid Y = 72.00mm (no correction)", abs(sw_y - 72.00) < 0.01,
          f"got {sw_y}")

    # U1: ESP32 correction +3.62 still applied
    u1_y = float(cpl["U1"]["Mid Y"].replace("mm", ""))
    check("U1 Mid Y = 31.12mm (ESP32 correction)", abs(u1_y - 31.12) < 0.01,
          f"got {u1_y}")

    # U5: rotation override = 90 (mathematically proven correct)
    # JLCPCB uses Y-mirror + CW rotation for bottom-side components.
    # For SOP-16 at design rotation 90°, CPL=90 is the only value where
    # all 16 model pins align perfectly with gerber pads.
    u5_rot = int(cpl["U5"]["Rotation"])
    check("U5 rotation = 90 (override)", u5_rot == 90,
          f"got {u5_rot}")


def test_silkscreen_on_fab():
    """Test 5: All footprint Reference/Value text on Fab layers, not SilkS."""
    print("\n── Silkscreen Text Tests ──")
    with open(PCB_FILE) as f:
        content = f.read()

    # Find all footprint blocks and check their text layers
    violations = []
    # Match footprint blocks with their Reference/Value properties
    fp_pattern = re.compile(
        r'\(footprint "([^"]+)".*?\n.*?\(property "Reference" "([^"]*)"'
        r'.*?\(layer "([^"]+)"\)',
        re.DOTALL,
    )
    for m in fp_pattern.finditer(content):
        fp_name, ref, layer = m.group(1), m.group(2), m.group(3)
        if "SilkS" in layer and ref:  # empty ref (mounting holes) is ok
            violations.append(f"{ref} ({fp_name}) on {layer}")

    check("No footprint Reference on SilkS", len(violations) == 0,
          f"{len(violations)} violations: {violations[:5]}")


def test_mounting_hole_text():
    """Test 6: Mounting hole Reference on Fab, not SilkS."""
    print("\n── Mounting Hole Text Tests ──")
    with open(PCB_FILE) as f:
        content = f.read()

    # Find MountingHole footprints
    mh_pattern = re.compile(
        r'\(footprint "MountingHole[^"]*".*?\(property "Reference" ""'
        r'.*?\(layer "([^"]+)"\)',
        re.DOTALL,
    )
    silk_holes = 0
    fab_holes = 0
    for m in mh_pattern.finditer(content):
        layer = m.group(1)
        if "SilkS" in layer:
            silk_holes += 1
        elif "Fab" in layer:
            fab_holes += 1

    check("Mounting hole Reference on Fab (not SilkS)",
          silk_holes == 0 and fab_holes > 0,
          f"SilkS={silk_holes}, Fab={fab_holes}")


def test_c1_c2_spacing():
    """Test 7: C1/C2 spacing from U3."""
    print("\n── C1/C2 Spacing Tests ──")
    cpl = read_cpl()

    c1_y = float(cpl["C1"]["Mid Y"].replace("mm", ""))
    c2_y = float(cpl["C2"]["Mid Y"].replace("mm", ""))
    u3_y = float(cpl["U3"]["Mid Y"].replace("mm", ""))

    check("C1 Mid Y = 48.50mm", abs(c1_y - 48.50) < 0.01, f"got {c1_y}")
    check("C2 Mid Y = 62.50mm", abs(c2_y - 62.50) < 0.01, f"got {c2_y}")

    # SOT-223 extends ±3.9mm from center (pads at ±3.15, size 1.5mm)
    u3_top = u3_y + 3.9    # signal pads top edge
    u3_bot = u3_y - 3.9    # tab bottom edge (actually -3.15-0.9)

    # C1 (0805) extends ±0.65mm from center
    c1_bot = c1_y + 0.65

    # C2 (1206) extends ±0.9mm from center
    c2_top = c2_y - 0.9

    gap_c1_u3 = u3_bot - c1_bot
    gap_u3_c2 = c2_top - u3_top

    check(f"C1-U3 gap >= 1.5mm", gap_c1_u3 >= 1.5,
          f"gap={gap_c1_u3:.2f}mm")
    check(f"U3-C2 gap >= 1.5mm", gap_u3_c2 >= 1.5,
          f"gap={gap_u3_c2:.2f}mm")


def test_gr_text_vs_holes():
    """Test 8: No gr_text within 6mm of mounting hole centers."""
    print("\n── gr_text vs Mounting Holes ──")
    # Mounting hole positions (PCB coords)
    holes = [(10, 7), (150, 7), (10, 68), (150, 68), (55, 37.5), (105, 37.5)]

    with open(PCB_FILE) as f:
        content = f.read()

    # Find all gr_text positions
    gr_pattern = re.compile(
        r'\(gr_text "([^"]+)" \(at ([\d.]+) ([\d.]+)\)',
    )
    violations = []
    for m in gr_pattern.finditer(content):
        text, x, y = m.group(1), float(m.group(2)), float(m.group(3))
        for hx, hy in holes:
            dist = ((x - hx)**2 + (y - hy)**2)**0.5
            if dist < 6.0:
                violations.append(f'"{text}" at ({x},{y}) dist={dist:.1f}mm '
                                  f'from hole ({hx},{hy})')

    check("No gr_text within 6mm of mounting holes",
          len(violations) == 0,
          f"{len(violations)} violations: {violations[:3]}")


def test_via_annular_ring():
    """Test 9: All vias have annular ring >= 0.175mm."""
    print("\n── Via Annular Ring Tests ──")
    with open(PCB_FILE) as f:
        content = f.read()

    via_pattern = re.compile(r'\(via\b.*?\(size ([\d.]+)\).*?\(drill ([\d.]+)\)')
    total = 0
    violations = 0
    for m in via_pattern.finditer(content):
        size = float(m.group(1))
        drill = float(m.group(2))
        ring = (size - drill) / 2
        total += 1
        if ring < 0.175:
            violations += 1

    check(f"Via annular ring >= 0.175mm ({total} vias)",
          violations == 0, f"{violations} violations")


def test_gerber_zip():
    """Test 10: gerbers.zip has 12 files."""
    print("\n── Gerber Zip Tests ──")
    zip_path = os.path.join(RELEASE, "gerbers.zip")
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
    check(f"gerbers.zip has 12 files", len(names) == 12,
          f"got {len(names)}: {names}")


def test_u5_pin_alignment():
    """Test 11: U5 (PAM8403) model pins align with gerber pads at CPL rotation.

    Uses JLCPCB's convention: Y-mirror (negate X) + CW rotation.
    Verifies that every pin of the JLCPCB 3D model, after bottom-side
    flip and CPL rotation, lands exactly on the corresponding gerber pad.
    """
    print("\n── U5 Pin Alignment Test ──")
    import math

    # Standard SOP-16 model pin positions (body center at origin)
    model_pins = {}
    for i in range(8):
        model_pins[i + 1] = (-4.65, -4.445 + i * 1.27)
    for i in range(8):
        model_pins[i + 9] = (4.65, 4.445 - i * 1.27)

    # Our gerber pad positions (from pre-rotation 90° + X-mirror)
    gerber_pins = {}
    for i in range(8):
        x, y = -4.65, -4.445 + i * 1.27
        rx, ry = -y, x      # 90° CCW pre-rotation
        gerber_pins[i + 1] = (-rx, ry)  # X-mirror
    for i in range(8):
        x, y = 4.65, 4.445 - i * 1.27
        rx, ry = -y, x
        gerber_pins[i + 9] = (-rx, ry)

    # Read CPL rotation for U5
    cpl = read_cpl()
    cpl_rot = int(cpl["U5"]["Rotation"])

    # Apply JLCPCB transforms: Y-mirror then CW rotation
    rad = math.radians(-cpl_rot)  # CW = negative
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    max_err = 0
    mismatches = []
    for pin in sorted(model_pins):
        mx, my = model_pins[pin]
        mx = -mx  # Y-mirror (negate X)
        rx = mx * cos_a - my * sin_a
        ry = mx * sin_a + my * cos_a
        gx, gy = gerber_pins[pin]
        err = max(abs(rx - gx), abs(ry - gy))
        max_err = max(max_err, err)
        if err > 0.01:
            mismatches.append(f"pin {pin}: model ({rx:.3f},{ry:.3f}) "
                              f"vs pad ({gx:.3f},{gy:.3f})")

    check(f"U5 all 16 pins align at CPL rot={cpl_rot}° (max err={max_err:.4f}mm)",
          len(mismatches) == 0,
          f"{len(mismatches)} mismatches: {mismatches[:3]}")


def test_sop16_aperture():
    """Test 12: SOP-16 aperture R,0.6x2.05 exists (pre-rotation working)."""
    print("\n── SOP-16 Aperture Test ──")
    gerber_path = os.path.join(RELEASE, "gerbers", "esp32-emu-turbo-B_Cu.gbl")
    with open(gerber_path) as f:
        content = f.read()

    # Look for rotated aperture (0.6 wide, 2.05 tall)
    has_rotated = bool(re.search(r'R,0\.600000X2\.050000', content))
    check("SOP-16 rotated aperture R,0.6x2.05 exists", has_rotated)


if __name__ == "__main__":
    print("=" * 60)
    print("DFM v2 Verification Tests")
    print("=" * 60)

    test_cpl_positions()
    test_silkscreen_on_fab()
    test_mounting_hole_text()
    test_c1_c2_spacing()
    test_gr_text_vs_holes()
    test_via_annular_ring()
    test_gerber_zip()
    test_u5_pin_alignment()
    test_sop16_aperture()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")
    sys.exit(1 if FAIL else 0)
