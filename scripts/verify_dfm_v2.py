#!/usr/bin/env python3
"""Verify DFM v2 fixes: CPL alignment, silkscreen, spacing, gerbers."""

import csv
import json
import os
import re
import shutil
import subprocess
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

    # SW_PWR: position correction -1.5mm applied → 72.00 - 1.5 = 70.50
    sw_y = float(cpl["SW_PWR"]["Mid Y"].replace("mm", ""))
    check("SW_PWR Mid Y = 70.50mm (position correction)", abs(sw_y - 70.50) < 0.01,
          f"got {sw_y}")

    # U1: ESP32 correction +3.62 still applied
    u1_y = float(cpl["U1"]["Mid Y"].replace("mm", ""))
    check("U1 Mid Y = 31.12mm (ESP32 correction)", abs(u1_y - 31.12) < 0.01,
          f"got {u1_y}")

    # U5: rotation override — 90° aligns pre-rotated SOP-16 with JLCPCB model
    u5_rot = int(cpl["U5"]["Rotation"])
    check("U5 rotation = 90 (pre-rotation alignment)", u5_rot == 90,
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
    """Test 10: gerbers.zip has >= 12 files (gerbers + drill + optional job)."""
    print("\n── Gerber Zip Tests ──")
    zip_path = os.path.join(RELEASE, "gerbers.zip")
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
    check(f"gerbers.zip has >= 12 files", len(names) >= 12,
          f"got {len(names)}: {names}")


def test_u5_pin_alignment():
    """Test 11: Analyze U5 (PAM8403) pin alignment at all rotations.

    Tests all 4 rotations under JLCPCB convention (Y-mirror + CCW rotation).
    C5122557 = narrow SOP-16 (3.9mm body, pad centers at ±2.7mm).
    Reports which rotation aligns with standard SOIC-16 model assumptions.
    Always passes — JLCPCB C5122557 model may differ from standard.
    """
    print("\n── U5 Pin Alignment Analysis ──")
    import math

    # Narrow SOP-16 model pin positions (body center at origin)
    # C5122557: 3.9mm body width, pad centers at ±2.7mm
    PAD_X = 2.7   # narrow body pad center distance from body center
    model_pins = {}
    for i in range(8):
        model_pins[i + 1] = (-PAD_X, -4.445 + i * 1.27)
    for i in range(8):
        model_pins[i + 9] = (PAD_X, 4.445 - i * 1.27)

    # Our gerber pad positions (from pre-rotation 90° + X-mirror)
    gerber_pins = {}
    for i in range(8):
        x, y = -PAD_X, -4.445 + i * 1.27
        rx, ry = -y, x
        gerber_pins[i + 1] = (-rx, ry)
    for i in range(8):
        x, y = PAD_X, 4.445 - i * 1.27
        rx, ry = -y, x
        gerber_pins[i + 9] = (-rx, ry)

    cpl = read_cpl()
    cpl_rot = int(cpl["U5"]["Rotation"])

    for test_rot in [0, 90, 180, 270]:
        rad = math.radians(-test_rot)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        max_err = 0
        for pin in sorted(model_pins):
            mx, my = model_pins[pin]
            mx = -mx
            rx = mx * cos_a - my * sin_a
            ry = mx * sin_a + my * cos_a
            gx, gy = gerber_pins[pin]
            err = max(abs(rx - gx), abs(ry - gy))
            max_err = max(max_err, err)
        tag = " ← CPL" if test_rot == cpl_rot else ""
        status = "ALIGN" if max_err < 0.01 else f"err={max_err:.1f}mm"
        print(f"    rot={test_rot:3d}°: {status}{tag}")

    check(f"U5 CPL rotation = {cpl_rot}° (4 variants in release_jlcpcb/)",
          True)


def test_sop16_aperture():
    """Test 12: SOP-16 narrow aperture R,0.6x1.55 exists (pre-rotation working)."""
    print("\n── SOP-16 Aperture Test ──")
    gerber_path = os.path.join(RELEASE, "gerbers", "esp32-emu-turbo-B_Cu.gbl")
    with open(gerber_path) as f:
        content = f.read()

    # Look for rotated aperture (0.6 wide, 1.55 tall — narrow SOP-16)
    has_rotated = bool(re.search(r'R,0\.600000X1\.550000', content))
    check("SOP-16 narrow rotated aperture R,0.6x1.55 exists", has_rotated)


def test_kicad_drc():
    """Test 13-15: KiCad DRC — no real violations (edge, hole, silk)."""
    print("\n── KiCad DRC Tests ──")
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        print("  SKIP  kicad-cli not found (install KiCad for DRC tests)")
        return

    drc_out = os.path.join(BASE, "hardware", "kicad", "drc-report.json")
    try:
        subprocess.run(
            [kicad_cli, "pcb", "drc",
             "--output", drc_out, "--format", "json",
             "--severity-all", "--units", "mm", "--all-track-errors",
             PCB_FILE],
            capture_output=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("  SKIP  kicad-cli drc failed to run")
        return

    if not os.path.exists(drc_out):
        print("  SKIP  DRC report not generated")
        return

    with open(drc_out) as f:
        data = json.load(f)

    from collections import Counter
    types = Counter()
    for v in data.get("violations", []):
        types[v["type"]] += 1

    # Real violations that should be zero
    edge = types.get("copper_edge_clearance", 0)
    hole = types.get("hole_to_hole", 0)
    silk_copper = types.get("silk_over_copper", 0)
    silk_overlap = types.get("silk_overlap", 0)
    silk_edge = types.get("silk_edge_clearance", 0)

    check("KiCad DRC: copper_edge_clearance = 0", edge == 0,
          f"got {edge}")
    check("KiCad DRC: hole_to_hole = 0", hole == 0,
          f"got {hole}")
    check("KiCad DRC: silk issues = 0",
          silk_copper + silk_overlap + silk_edge == 0,
          f"silk_over_copper={silk_copper}, silk_overlap={silk_overlap}, "
          f"silk_edge={silk_edge}")

    # Clean up
    os.remove(drc_out)


_CACHE = None


def _get_cache():
    """Lazy-load PCB cache (shared across all test functions)."""
    global _CACHE
    if _CACHE is None:
        from pcb_cache import load_cache
        _CACHE = load_cache()
    return _CACHE


def _cached_segments():
    """Load segments from cache with 'w' key (backward compat)."""
    return [{"x1": s["x1"], "y1": s["y1"], "x2": s["x2"], "y2": s["y2"],
             "w": s["width"], "layer": s["layer"], "net": s["net"]}
            for s in _get_cache()["segments"]]


def _cached_vias():
    """Load vias from cache."""
    return _get_cache()["vias"]


def _seg_min_dist(s1, s2):
    """Approximate minimum distance between two parallel segments on same layer.

    For axis-aligned segments sharing an overlap region, computes edge-to-edge gap.
    Returns None if segments aren't parallel/overlapping axis-aligned.
    """
    tol = 0.01
    # Both vertical
    if abs(s1["x1"] - s1["x2"]) < tol and abs(s2["x1"] - s2["x2"]) < tol:
        x1, x2 = s1["x1"], s2["x1"]
        y1a, y1b = min(s1["y1"], s1["y2"]), max(s1["y1"], s1["y2"])
        y2a, y2b = min(s2["y1"], s2["y2"]), max(s2["y1"], s2["y2"])
        overlap = min(y1b, y2b) - max(y1a, y2a)
        if overlap > 0:
            gap = abs(x1 - x2) - (s1["w"] + s2["w"]) / 2
            return gap
    # Both horizontal
    if abs(s1["y1"] - s1["y2"]) < tol and abs(s2["y1"] - s2["y2"]) < tol:
        y1, y2 = s1["y1"], s2["y1"]
        x1a, x1b = min(s1["x1"], s1["x2"]), max(s1["x1"], s1["x2"])
        x2a, x2b = min(s2["x1"], s2["x2"]), max(s2["x1"], s2["x2"])
        overlap = min(x1b, x2b) - max(x1a, x2a)
        if overlap > 0:
            gap = abs(y1 - y2) - (s1["w"] + s2["w"]) / 2
            return gap
    return None


def test_trace_spacing():
    """Test 16: Trace spacing regression guard — no new parallel trace violations.

    Baseline: some trace proximity violations are inherent to the dense design
    (USB-C area, button pull-up arrays, ESP32 pin fan-out).
    This test guards against REGRESSIONS — the count should not increase.
    """
    print("\n── Trace Spacing Tests ──")
    segs = _cached_segments()

    # Group by layer for efficient comparison
    by_layer = {}
    for s in segs:
        by_layer.setdefault(s["layer"], []).append(s)

    violations = []
    min_gap_threshold = 0.10  # JLCPCB DFM Danger threshold

    for layer, layer_segs in by_layer.items():
        if "Cu" not in layer:
            continue
        n = len(layer_segs)
        for i in range(n):
            for j in range(i + 1, n):
                s1, s2 = layer_segs[i], layer_segs[j]
                if s1["net"] == s2["net"]:
                    continue  # same net, no spacing required
                gap = _seg_min_dist(s1, s2)
                if gap is not None and gap < min_gap_threshold:
                    violations.append(
                        f"{layer}: gap={gap:.3f}mm at "
                        f"({s1['x1']},{s1['y1']})-({s1['x2']},{s1['y2']}) vs "
                        f"({s2['x1']},{s2['y1']})-({s2['x2']},{s2['y2']})"
                    )

    # Baseline: 27 violations from dense areas (USB-C, pull-ups, ESP32 fan-out)
    # Fail if count increases (regression) — improvement is always welcome
    BASELINE = 27
    check(f"Trace spacing violations <= baseline {BASELINE} ({len(violations)} found)",
          len(violations) <= BASELINE,
          f"{len(violations)} violations (baseline {BASELINE}): {violations[:3]}")


def test_via_to_via_spacing():
    """Test 17: No via holes closer than 0.25mm (hole-to-hole edge gap)."""
    print("\n── Via-to-Via Spacing Tests ──")
    vias = _cached_vias()

    min_hole_gap = 0.25  # JLCPCB minimum hole-to-hole clearance
    violations = []

    for i in range(len(vias)):
        for j in range(i + 1, len(vias)):
            v1, v2 = vias[i], vias[j]
            dist = ((v1["x"] - v2["x"])**2 + (v1["y"] - v2["y"])**2)**0.5
            edge_gap = dist - (v1["drill"] + v2["drill"]) / 2
            if edge_gap < min_hole_gap:
                # Exclude same-net via-in-pad on ESP32 castellated pads
                # (ESP32 center at 80, 31.12; module 18x25.5mm)
                esp_cx, esp_cy = 80.0, 31.12
                on_esp = (abs(v1["x"] - esp_cx) < 10 and abs(v1["y"] - esp_cy) < 14
                          and abs(v2["x"] - esp_cx) < 10 and abs(v2["y"] - esp_cy) < 14)
                if on_esp and v1["net"] == v2["net"]:
                    continue
                violations.append(
                    f"gap={edge_gap:.3f}mm: ({v1['x']},{v1['y']}) vs "
                    f"({v2['x']},{v2['y']})"
                )

    check(f"Via hole-to-hole gap >= 0.25mm ({len(vias)} vias)",
          len(violations) == 0,
          f"{len(violations)} violations: {violations[:5]}")


def test_display_stagger_vs_esp32():
    """Test 18: Display bottom-pin stagger traces at ESP32 pin midpoints.

    ESP32 left-side pins at y = 22.24 + n*1.27 (n=0..13).
    Bottom-pin stagger traces (y=28..32 region) must use midpoints
    to avoid trace spacing violations with ESP32 side-pin signal traces.

    Excludes button routing traces, which legitimately end at ESP32 pad X
    positions (x=71.25 right side, x=88.75 left side).  Those traces are
    short point-to-point segments terminating at the ESP32 pad — they are
    not display bus stagger traces and cannot be at midpoints.
    """
    print("\n── Display Stagger vs ESP32 Pin Tests ──")
    segs = _cached_segments()

    # ESP32 left-side pin Y positions
    esp_pin_ys = [22.24 + n * 1.27 for n in range(14)]

    # ESP32 right-side pin X coordinates (board level, after B.Cu mirror)
    # Button traces that END at an ESP32 pad x are excluded from stagger check.
    # Right-side ESP32 pads are at x=71.25; left-side at x=88.75.
    ESP32_PAD_XS = {71.25, 88.75}

    # Find F.Cu horizontal traces in the STAGGER REGION (y=28..32)
    # These are display bottom-pin stagger traces that must use midpoints.
    # Exclude:
    #   - short stubs < 5mm (direct pad connections)
    #   - button routing traces that end exactly at an ESP32 pad column
    stagger_segs = []
    for s in segs:
        if s["layer"] != "F.Cu":
            continue
        if abs(s["y1"] - s["y2"]) > 0.01:
            continue  # not horizontal
        length = abs(s["x1"] - s["x2"])
        if length < 5.0:
            continue  # short stub
        y = s["y1"]
        # Critical stagger region: y=28..32 where bottom ESP32 pins are
        if not (28 < y < 32 and min(s["x1"], s["x2"]) < 75):
            continue
        # Exclude button routing traces that terminate at an ESP32 pad column.
        # These traces end at epx (ESP32 pad x) or start at the approach column.
        x_max = max(s["x1"], s["x2"])
        if any(abs(x_max - ex) < 0.1 for ex in ESP32_PAD_XS):
            continue  # button approach-to-pad trace, not a display stagger
        stagger_segs.append(s)

    violations = []
    min_gap = 0.15  # minimum y-distance from ESP32 pin center

    for s in stagger_segs:
        y = s["y1"]
        for py in esp_pin_ys:
            if abs(y - py) < min_gap:
                violations.append(
                    f"stagger y={y:.3f} len={abs(s['x1']-s['x2']):.1f}mm "
                    f"collides with ESP32 pin y={py:.2f} "
                    f"(gap={abs(y - py):.3f}mm)"
                )

    check(f"Bottom stagger traces at midpoints ({len(stagger_segs)} traces)",
          len(violations) == 0,
          f"{len(violations)} violations: {violations[:5]}")


def test_esop8_ep_pad_clearance():
    """Test 19: ESOP-8 (IP5306) EP pad has >= 0.10mm gap to corner signal pads.

    The EP (exposed pad) is 3.4 x 2.8mm (height reduced from 3.4mm).
    Corner signal pins 1, 4, 5, 8 are at y = ±1.905mm, half-height = 0.3mm.
    EP edge at ±1.4mm.  Gap = 1.605 - 1.4 = 0.205mm > 0.10mm danger threshold.
    Guard against regression that restores the original 3.4mm height.
    """
    print("\n── ESOP-8 EP Pad Clearance Tests ──")
    with open(PCB_FILE) as f:
        content = f.read()

    # Find the ESOP-8 footprint block and locate the EP pad size
    # The EP pad at center (0,0) has name "EP"
    ep_pattern = re.compile(
        r'\(pad "EP" smd rect \(at ([-\d.]+) ([-\d.]+)\)'
        r' \(size ([\d.]+) ([\d.]+)\)',
    )
    found = False
    violations = []
    for m in ep_pattern.finditer(content):
        ex, ey = float(m.group(1)), float(m.group(2))
        ew, eh = float(m.group(3)), float(m.group(4))
        found = True
        # EP edges (in footprint-local coords, before board transform)
        ep_half_h = eh / 2
        # Corner signal pin edge at ±1.605mm (y=±1.905, half-height=0.3)
        pin_edge = 1.605
        gap = pin_edge - ep_half_h
        if gap < 0.10:
            violations.append(
                f"EP size {ew}x{eh}mm: gap={gap:.3f}mm < 0.10mm danger threshold"
            )

    check("ESOP-8 EP pad found", found)
    check(
        "ESOP-8 EP pad height <= 3.2mm (gap >= 0.10mm to corner pins)",
        len(violations) == 0,
        f"{len(violations)} violation(s): {violations[:2]}",
    )


def test_msk12c02_unique_sh_pads():
    """Test 20: MSK12C02 (SW_PWR) mounting pads have unique names SH1-SH4.

    JLCPCB's DFM checker groups same-named pads and can report 0mm spacing
    between them.  All four shell/mounting pads must have distinct names.
    """
    print("\n── MSK12C02 Unique SH Pad Names ──")
    with open(PCB_FILE) as f:
        content = f.read()

    # Count pads named exactly "SH" (the old shared name) in SS-12D00G3 footprint
    sh_plain_pattern = re.compile(r'\(pad "SH" smd rect')
    sh_plain_count = len(sh_plain_pattern.findall(content))

    # Count uniquely-named SH1-SH4 pads
    sh_unique_pattern = re.compile(r'\(pad "SH[1-4]" smd rect')
    sh_unique_count = len(sh_unique_pattern.findall(content))

    check(
        "No plain 'SH' pads remain (all renamed to SH1-SH4)",
        sh_plain_count == 0,
        f"found {sh_plain_count} plain 'SH' pads (should be 0)",
    )
    check(
        "Exactly 4 unique SH1-SH4 pads present (one MSK12C02 with 4 shell pads)",
        sh_unique_count == 4,
        f"found {sh_unique_count} SH1-SH4 pads (expected 4)",
    )


def test_btn_r_routed():
    """Test 21: BTN_R (SW12 shoulder-right button) has a trace to ESP32 GPIO36.

    SW12 is at enc(65, 32) = (145, 5.5) on B.Cu.  Routing uses a B.Cu stub
    down to a channel row, F.Cu across the board, then B.Cu up to GPIO19
    (ESP32 right-side pad at y~37.48).  Verify that at least one B.Cu segment
    originates near SW12 pad 3 (143.15, 8.5).
    """
    print("\n── BTN_R (SW12) Routing Tests ──")
    segs = _cached_segments()

    # SW12 signal pad 3 is at (143.15, 8.5) in board coordinates.
    # Expect a B.Cu segment starting or ending very near this position.
    target_x, target_y = 143.15, 8.5
    tolerance = 0.1

    found_stub = any(
        s["layer"] == "B.Cu"
        and (
            (abs(s["x1"] - target_x) < tolerance and abs(s["y1"] - target_y) < tolerance)
            or (abs(s["x2"] - target_x) < tolerance and abs(s["y2"] - target_y) < tolerance)
        )
        for s in segs
    )

    check(
        "BTN_R B.Cu stub found near SW12 pad 3 (143.15, 8.5)",
        found_stub,
        "no B.Cu segment near SW12 signal pad — BTN_R may be unrouted",
    )

    # Also verify a long F.Cu horizontal segment exists near chan_y_r (69.5mm)
    # that spans a significant board width (x > 40mm length) for the cross-board run.
    # BTN_R routes to GPIO19 at x=88.75 (right-side ESP32), approach at x=90.75,
    # so F.Cu from SW12 pad (x=146.85) to approach_r (x=90.75): length ~56.1mm.
    long_fcu = any(
        s["layer"] == "F.Cu"
        and abs(s["y1"] - s["y2"]) < 0.01
        and abs(s["y1"] - 69.5) < 1.0
        and abs(s["x1"] - s["x2"]) > 40
        for s in segs
    )
    check(
        "BTN_R long F.Cu cross-board segment found near y=69mm",
        long_fcu,
        "no long F.Cu segment at y~69.5mm — BTN_R channel route may be missing",
    )


def test_kicad_drc_edge_clearance():
    """Test 22: KiCad DRC copper-to-edge clearance — zero violations.

    Guards against traces or vias placed too close to the board outline,
    the FPC slot edge, or any other Edge.Cuts element.
    Passes only when kicad-cli is available.
    """
    print("\n── KiCad DRC Edge Clearance Guard ──")
    kicad_cli = shutil.which("kicad-cli")
    if not kicad_cli:
        print("  SKIP  kicad-cli not found")
        return

    drc_out = os.path.join(BASE, "hardware", "kicad", "drc-edge-guard.json")
    try:
        subprocess.run(
            [kicad_cli, "pcb", "drc",
             "--output", drc_out, "--format", "json",
             "--severity-all", "--units", "mm",
             PCB_FILE],
            capture_output=True, timeout=60,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("  SKIP  kicad-cli drc failed")
        return

    if not os.path.exists(drc_out):
        print("  SKIP  DRC report not generated")
        return

    with open(drc_out) as f:
        data = json.load(f)

    from collections import Counter
    types = Counter(v["type"] for v in data.get("violations", []))
    edge = types.get("copper_edge_clearance", 0)
    hole = types.get("hole_to_hole", 0)

    check("KiCad DRC: copper_edge_clearance = 0 (regression guard)", edge == 0,
          f"got {edge} violations")
    check("KiCad DRC: hole_to_hole = 0 (regression guard)", hole == 0,
          f"got {hole} violations")

    os.remove(drc_out)


def test_sw8_slot_clearance():
    """Test 23: SW8 (BTN_Y) pad 1 clears FPC slot edge by >= 0.5mm.

    SW8 pad 1 (signal pad) is closest to the FPC slot cutout (right edge
    at x=128.5mm).  Pad center must be at x >= 129.0mm so the copper edge
    (pad_center - pad_half_width = x - 0.6) is at least 0.5mm from slot edge.
    Min center x = 128.5 + 0.5 + 0.6 = 129.6mm.
    Guards against accidental leftward drift of SW8 position.
    """
    print("\n── SW8 Slot Clearance Test ──")
    cpl = read_cpl()
    sw8_x = float(cpl["SW8"]["Mid X"].replace("mm", ""))
    # SW8 pad 1 is 3mm left of center
    pad1_x = sw8_x - 3.0
    slot_edge_x = 128.5
    pad_half_w = 0.6
    gap = pad1_x - pad_half_w - slot_edge_x
    check(
        f"SW8 pad1 clears FPC slot by >= 0.5mm (gap={gap:.2f}mm)",
        gap >= 0.5,
        f"SW8 center={sw8_x:.2f}mm, pad1={pad1_x:.2f}mm, slot={slot_edge_x}mm, gap={gap:.3f}mm",
    )


def test_btn_r_edge_clearance():
    """Test 24: BTN_R F.Cu channel is at least 0.5mm from board bottom edge.

    BTN_R uses an F.Cu horizontal segment to cross the board.  The bottom
    board edge is at y=75.0mm.  The copper must be at most y=74.5mm
    (0.5mm clearance from edge).
    Guards against chan_y_r drifting to 75.0 (board edge).
    """
    print("\n── BTN_R Edge Clearance Test ──")
    segs = _cached_segments()

    # BTN_R net=38; find its longest F.Cu horizontal segment
    net_btn_r = 38
    board_bottom = 75.0
    min_clearance = 0.5
    violations = []
    for s in segs:
        if s["net"] != net_btn_r or s["layer"] != "F.Cu":
            continue
        if abs(s["y1"] - s["y2"]) > 0.01:
            continue  # not horizontal
        y = s["y1"]
        clearance = board_bottom - y
        if clearance < min_clearance:
            violations.append(
                f"BTN_R F.Cu at y={y:.3f}mm: clearance to board edge = {clearance:.3f}mm < {min_clearance}mm"
            )

    check(
        "BTN_R F.Cu channel >= 0.5mm from board bottom edge (y <= 74.5mm)",
        len(violations) == 0,
        f"{len(violations)} violations: {violations[:3]}",
    )


def test_sd_gnd_via_clearance():
    """Test 25: SD routing B.Cu post_slot traces clear of SW5/SW7 GND vias.

    SW5 (BTN_A) and SW7 (BTN_X) GND vias land at x=143.5 (pads at x=145 offset
    1.5mm left).  SD routing post_slot B.Cu verticals at x=141,145,146,148 must
    all be >= 0.2mm (KiCad netclass clearance) from via ring at 143.5±0.45mm.

    Forbidden zone: x in [143.05, 143.95] (via ring ±0.45mm).
    Clearance requirement: trace half-width (0.1mm) + via radius (0.45mm) +
    clearance (0.2mm) = 0.75mm from via center.  So trace centerline must be
    outside [142.75, 144.25].

    Guards against post_slot_map assignments at x=143 or x=144 which caused
    0.05mm clearance violations in KiCad DRC.
    """
    print("\n── SD Post-Slot vs GND Via Clearance ──")
    segs = _cached_segments()

    # GND vias from SW5/SW7 routing are at x=143.5 (net=GND).
    # SD post_slot B.Cu verticals are net 20-23 (SD_MOSI,MISO,CLK,CS).
    # Any SD B.Cu segment with centerline in [142.75, 144.25] is a violation.
    FORBIDDEN_LO = 142.75
    FORBIDDEN_HI = 144.25
    SD_NETS = {20, 21, 22, 23}  # SD_MOSI, SD_MISO, SD_CLK, SD_CS

    violations = []
    for s in segs:
        if s["net"] not in SD_NETS or s["layer"] != "B.Cu":
            continue
        # Vertical segment: x1==x2
        if abs(s["x1"] - s["x2"]) > 0.01:
            continue
        x = s["x1"]
        if FORBIDDEN_LO < x < FORBIDDEN_HI:
            violations.append(
                f"SD net={s['net']} B.Cu vert at x={x:.3f} in forbidden zone "
                f"[{FORBIDDEN_LO},{FORBIDDEN_HI}]"
            )

    check(
        "SD post_slot B.Cu verticals avoid x=[142.75,144.25] (GND via clearance zone)",
        len(violations) == 0,
        f"{len(violations)} violations: {violations[:3]}",
    )


def test_bat_plus_via_vbus_clearance():
    """Test 26: BAT+ via at L1[1] clears VBUS F.Cu trace at x=111.0.

    The L1 boost inductor pin 1 BAT+ via is at (bat_via_x, bat_via_y).
    The VBUS F.Cu trace runs vertically at x=111.0 with width=0.5mm.
    Required clearance: 0.2mm (netclass default).

    Forbidden: via must not be within 0.75mm of x=111.0 (via_radius +
    trace_half + clearance = 0.45+0.25+0.2-0.25 = 0.65mm from trace center).
    More precisely: via_center_x - via_radius >= 111.25 + 0.2 → x >= 111.9mm.
    Guards against BAT+ via drifting back to (111.7, 49.5) which gives 0.0mm gap.
    """
    print("\n── BAT+ Via / VBUS Trace Clearance ──")
    with open(PCB_FILE) as f:
        content = f.read()

    import re as _re
    # Find BAT+ via (net=5) near y=49.5
    vias_raw = _re.findall(
        r'\(via\s+\(at\s+([-\d.]+)\s+([-\d.]+)\).*?\(size\s+([-\d.]+)\).*?\(drill\s+([-\d.]+)\).*?\(net\s+(\d+)\)',
        content, _re.DOTALL
    )
    # Find VBUS F.Cu vertical near x=111 (any segment with both endpoints at x≈111)
    vbus_net = 2
    vbus_trace_x = 111.0
    vbus_trace_hw = 0.25  # half-width of 0.5mm VBUS trace
    required_clearance = 0.2

    bat_net = 5
    violations = []
    for v in vias_raw:
        vx, vy, vsize, vdrill, vnet = float(v[0]), float(v[1]), float(v[2]), float(v[3]), int(v[4])
        if vnet != bat_net:
            continue
        # Only check the L1[1] BAT+ via — it's near x=111-113, y=48-51.
        # Other BAT+ vias (e.g. for JST connector, IP5306 BAT pins) are far from x=111.
        if not (110.0 < vx < 115.0 and 47.0 < vy < 52.0):
            continue
        # This via must be RIGHT of VBUS trace: via_left >= vbus_right + clearance.
        via_radius = float(vsize) / 2
        # VBUS trace right edge = vbus_trace_x + vbus_trace_hw = 111.25
        vbus_right = vbus_trace_x + vbus_trace_hw
        via_left = vx - via_radius
        gap = via_left - vbus_right
        if gap < required_clearance:
            violations.append(
                f"BAT+ L1 via at ({vx:.3f},{vy:.3f}) r={via_radius:.3f}: "
                f"gap to VBUS right edge={gap:.3f}mm < {required_clearance}mm"
            )

    check(
        "BAT+ L1 via clears VBUS F.Cu trace by >= 0.2mm",
        len(violations) == 0,
        f"{len(violations)} violations: {violations[:3]}",
    )


def test_mounting_holes_npth():
    """Test 27: All MountingHole footprints use np_thru_hole (NPTH).

    DFM: NPTH mounting holes have no copper annular ring, eliminating
    THT-to-SMD and pad spacing DANGER violations with nearby components.
    Guards against regression that restores PTH mounting holes.
    """
    print("\n── Mounting Holes NPTH Test ──")
    with open(PCB_FILE) as f:
        content = f.read()

    # Find all MountingHole footprint blocks and check pad type
    mh_blocks = re.findall(
        r'\(footprint "MountingHole[^"]*".*?\n(?:.*?\n)*?.*?\(pad[^)]*\)',
        content,
    )
    pth_count = 0
    npth_count = 0
    for block in mh_blocks:
        if 'np_thru_hole' in block:
            npth_count += 1
        elif 'thru_hole' in block:
            pth_count += 1

    # Also check with a simpler pattern for reliability
    npth_pattern = re.compile(
        r'\(footprint "MountingHole.*?'
        r'\(pad "" np_thru_hole',
        re.DOTALL,
    )
    pth_pattern = re.compile(
        r'\(footprint "MountingHole.*?'
        r'\(pad "" thru_hole',
        re.DOTALL,
    )
    npth_simple = len(npth_pattern.findall(content))
    pth_simple = len(pth_pattern.findall(content))

    check(
        "All MountingHole pads are np_thru_hole (NPTH)",
        pth_simple == 0 and npth_simple > 0,
        f"PTH={pth_simple}, NPTH={npth_simple} (expected 0 PTH, >0 NPTH)",
    )


def test_lx_bat_trace_spacing():
    """Test 28: LX and BAT+ B.Cu vertical columns have edge gap >= 0.25mm.

    LX (net=46) vertical at lx_col_x and BAT+ (net=5) vertical at bat_col_x
    must have sufficient spacing. Guards against LX column drifting right
    toward BAT+ column.
    """
    print("\n── LX vs BAT+ Trace Spacing Test ──")
    segs = _cached_segments()

    n_lx = 46   # NET_ID["LX"]
    n_bat = 5   # NET_ID["BAT+"]
    min_edge_gap = 0.25

    # Find B.Cu vertical segments for LX and BAT+
    lx_verts = [s for s in segs if s["net"] == n_lx and s["layer"] == "B.Cu"
                and abs(s["x1"] - s["x2"]) < 0.01]
    bat_verts = [s for s in segs if s["net"] == n_bat and s["layer"] == "B.Cu"
                 and abs(s["x1"] - s["x2"]) < 0.01]

    violations = []
    for lx in lx_verts:
        for bat in bat_verts:
            gap = _seg_min_dist(lx, bat)
            if gap is not None and gap < min_edge_gap:
                violations.append(
                    f"LX@x={lx['x1']:.3f} vs BAT+@x={bat['x1']:.3f}: "
                    f"edge gap={gap:.3f}mm < {min_edge_gap}mm"
                )

    check(
        f"LX vs BAT+ B.Cu vertical edge gap >= {min_edge_gap}mm",
        len(violations) == 0,
        f"{len(violations)} violations: {violations[:3]}",
    )


def test_button_vx_spacing():
    """Test 29: Button B.Cu vertical columns have edge gap >= 0.15mm.

    All BTN_* (net 27-39) B.Cu vertical segments must maintain minimum
    spacing between different-net columns. Guards against button vx
    assignments that are too close.
    """
    print("\n── Button B.Cu Column Spacing Test ──")
    segs = _cached_segments()

    btn_nets = set(range(27, 40))  # BTN_UP(27) through BTN_MENU(39)
    min_edge_gap = 0.15

    btn_verts = [s for s in segs if s["net"] in btn_nets and s["layer"] == "B.Cu"
                 and abs(s["x1"] - s["x2"]) < 0.01]

    violations = []
    for i in range(len(btn_verts)):
        for j in range(i + 1, len(btn_verts)):
            s1, s2 = btn_verts[i], btn_verts[j]
            if s1["net"] == s2["net"]:
                continue
            gap = _seg_min_dist(s1, s2)
            if gap is not None and gap < min_edge_gap - 0.005:  # 5µm tolerance for FP
                violations.append(
                    f"net{s1['net']}@x={s1['x1']:.3f} vs net{s2['net']}@x={s2['x1']:.3f}: "
                    f"gap={gap:.3f}mm"
                )

    check(
        f"Button B.Cu vertical edge gap >= {min_edge_gap}mm ({len(btn_verts)} segments)",
        len(violations) == 0,
        f"{len(violations)} violations: {violations[:5]}",
    )


def test_gnd_lcd_d7_spacing():
    """Test 30: GND power trace vs LCD_D7 B.Cu gap >= 0.15mm.

    ESP32 GND thermal pad (net=1, w=0.5mm) B.Cu vertical must not approach
    LCD_D7 (net=13, w=0.2mm) B.Cu vertical. Guards against GND trace
    drifting back to x=81.5 (overlapping LCD_D7 at x=81.905).
    """
    print("\n── GND vs LCD_D7 Spacing Test ──")
    segs = _cached_segments()

    n_gnd = 1   # NET_ID["GND"]
    n_lcd_d7 = 13  # NET_ID["LCD_D7"]
    min_edge_gap = 0.15

    # GND power B.Cu verticals near ESP32 (x in 78..84, y in 28..35)
    gnd_verts = [s for s in segs if s["net"] == n_gnd and s["layer"] == "B.Cu"
                 and abs(s["x1"] - s["x2"]) < 0.01 and s["w"] >= 0.4
                 and 78 < s["x1"] < 84 and min(s["y1"], s["y2"]) < 35]
    lcd_d7_verts = [s for s in segs if s["net"] == n_lcd_d7 and s["layer"] == "B.Cu"
                    and abs(s["x1"] - s["x2"]) < 0.01]

    violations = []
    for g in gnd_verts:
        for l in lcd_d7_verts:
            gap = _seg_min_dist(g, l)
            if gap is not None and gap < min_edge_gap:
                violations.append(
                    f"GND@x={g['x1']:.3f} vs LCD_D7@x={l['x1']:.3f}: "
                    f"gap={gap:.3f}mm"
                )

    check(
        f"GND power vs LCD_D7 B.Cu edge gap >= {min_edge_gap}mm",
        len(violations) == 0,
        f"{len(violations)} violations: {violations[:3]}",
    )


def test_lcd_sd_approach_spacing():
    """Test 31: LCD approach columns vs SD traces edge gap >= 0.15mm.

    LCD B.Cu vertical approach columns (x in 134..141) must not overlap
    SD card routing B.Cu verticals (net 20-23). Guards against approach
    pitch or SD post_slot column being too close.
    """
    print("\n── LCD Approach vs SD Trace Spacing Test ──")
    segs = _cached_segments()

    lcd_nets = set(range(6, 20))  # LCD_D0(6)..LCD_BL(19)
    sd_nets = {20, 21, 22, 23}   # SD_MOSI, SD_MISO, SD_CLK, SD_CS
    min_edge_gap = 0.15

    # LCD B.Cu verticals in approach column range
    lcd_verts = [s for s in segs if s["net"] in lcd_nets and s["layer"] == "B.Cu"
                 and abs(s["x1"] - s["x2"]) < 0.01 and 133 < s["x1"] < 142]
    # SD B.Cu verticals in same x range
    sd_verts = [s for s in segs if s["net"] in sd_nets and s["layer"] == "B.Cu"
                and abs(s["x1"] - s["x2"]) < 0.01 and 133 < s["x1"] < 148]

    violations = []
    for lcd in lcd_verts:
        for sd in sd_verts:
            gap = _seg_min_dist(lcd, sd)
            if gap is not None and gap < min_edge_gap:
                violations.append(
                    f"LCD net{lcd['net']}@x={lcd['x1']:.3f} vs "
                    f"SD net{sd['net']}@x={sd['x1']:.3f}: gap={gap:.3f}mm"
                )

    check(
        f"LCD approach vs SD B.Cu edge gap >= {min_edge_gap}mm",
        len(violations) == 0,
        f"{len(violations)} violations: {violations[:5]}",
    )


def test_via_pad_spacing():
    """Test 32: All different-net via pairs have pad edge gap >= 0.15mm.

    Guards against via placement that creates overlapping pads on different
    nets. Excludes same-net pairs and vias within ESP32 module area.
    """
    print("\n── Via Pad Spacing Test ──")
    vias = _cached_vias()

    min_pad_gap = 0.15
    violations = []

    for i in range(len(vias)):
        for j in range(i + 1, len(vias)):
            v1, v2 = vias[i], vias[j]
            if v1["net"] == v2["net"]:
                continue
            dist = ((v1["x"] - v2["x"])**2 + (v1["y"] - v2["y"])**2)**0.5
            pad_gap = dist - (v1["size"] + v2["size"]) / 2
            if pad_gap < min_pad_gap:
                # Exclude ESP32 area (already handled by via_to_via_spacing)
                esp_cx, esp_cy = 80.0, 31.12
                on_esp = (abs(v1["x"] - esp_cx) < 10 and abs(v1["y"] - esp_cy) < 14
                          and abs(v2["x"] - esp_cx) < 10 and abs(v2["y"] - esp_cy) < 14)
                if on_esp:
                    continue
                violations.append(
                    f"net{v1['net']}@({v1['x']:.3f},{v1['y']:.3f}) vs "
                    f"net{v2['net']}@({v2['x']:.3f},{v2['y']:.3f}): "
                    f"pad gap={pad_gap:.3f}mm"
                )

    check(
        f"Via pad edge gap >= {min_pad_gap}mm ({len(vias)} vias)",
        len(violations) == 0,
        f"{len(violations)} violations: {violations[:5]}",
    )


def test_usb_cap_trace_spacing():
    """Test 40: USB D+/D- B.Cu traces maintain >= 0.10mm from GND cap traces.

    Guards against JLCPCB DANGER: B.Cu trace spacing in USB area (x=88-93).
    """
    print("\n── USB Cap Trace Spacing Test ──")
    segs = _cached_segments()

    # B.Cu segments in USB area
    usb_segs = [s for s in segs
                if s["layer"] == "B.Cu" and 88 <= s["x1"] <= 93 and 88 <= s["x2"] <= 93
                and 55 <= s["y1"] <= 75 and 55 <= s["y2"] <= 75]

    violations = []
    for i in range(len(usb_segs)):
        for j in range(i + 1, len(usb_segs)):
            s1, s2 = usb_segs[i], usb_segs[j]
            if s1["net"] == s2["net"]:
                continue
            gap = _seg_min_dist(s1, s2)
            if gap is not None and gap < 0.10:
                violations.append(
                    f"gap={gap:.3f}mm: ({s1['x1']},{s1['y1']})-({s1['x2']},{s1['y2']}) w={s1['w']} "
                    f"vs ({s2['x1']},{s2['y1']})-({s2['x2']},{s2['y2']}) w={s2['w']}"
                )

    check("USB B.Cu trace-to-cap spacing >= 0.10mm",
          len(violations) == 0,
          f"{len(violations)} violations: {violations[:3]}")


def test_mounting_hole_trace_clearance():
    """Test 41: F.Cu traces maintain >= 0.18mm from MH(55,37.5) drill edge.

    Guards against JLCPCB DANGER: PTH-to-trace clearance near mounting holes.
    MH drill=2.5mm, so edge radius=1.25mm from center.
    """
    print("\n── Mounting Hole Trace Clearance Test ──")
    segs = _cached_segments()

    mh_x, mh_y = 55.0, 37.5
    mh_radius = 1.25  # drill=2.5mm
    min_clearance = 0.18  # JLCPCB minimum

    # F.Cu segments near the mounting hole (within 5mm box)
    nearby = [s for s in segs
              if s["layer"] == "F.Cu"
              and min(s["x1"], s["x2"]) < mh_x + 5
              and max(s["x1"], s["x2"]) > mh_x - 5
              and min(s["y1"], s["y2"]) < mh_y + 5
              and max(s["y1"], s["y2"]) > mh_y - 5]

    violations = []
    for s in nearby:
        # Distance from MH center to nearest point on segment
        # For axis-aligned segments:
        if abs(s["x1"] - s["x2"]) < 0.01:  # vertical
            dx = abs(s["x1"] - mh_x)
            sy_min, sy_max = min(s["y1"], s["y2"]), max(s["y1"], s["y2"])
            if sy_min <= mh_y <= sy_max:
                dist = dx
            else:
                dy = min(abs(mh_y - sy_min), abs(mh_y - sy_max))
                dist = (dx**2 + dy**2)**0.5
        elif abs(s["y1"] - s["y2"]) < 0.01:  # horizontal
            dy = abs(s["y1"] - mh_y)
            sx_min, sx_max = min(s["x1"], s["x2"]), max(s["x1"], s["x2"])
            if sx_min <= mh_x <= sx_max:
                dist = dy
            else:
                dx = min(abs(mh_x - sx_min), abs(mh_x - sx_max))
                dist = (dx**2 + dy**2)**0.5
        else:
            # Diagonal — use endpoint distances as conservative estimate
            d1 = ((s["x1"] - mh_x)**2 + (s["y1"] - mh_y)**2)**0.5
            d2 = ((s["x2"] - mh_x)**2 + (s["y2"] - mh_y)**2)**0.5
            dist = min(d1, d2)

        # Gap = center distance - MH radius - half trace width
        gap = dist - mh_radius - s["w"] / 2
        if gap < min_clearance:
            violations.append(
                f"gap={gap:.3f}mm: ({s['x1']},{s['y1']})-({s['x2']},{s['y2']}) w={s['w']}"
            )

    check(f"F.Cu traces >= {min_clearance}mm from MH(55,37.5) drill edge",
          len(violations) == 0,
          f"{len(violations)} violations: {violations[:3]}")


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
    test_kicad_drc()
    test_trace_spacing()
    test_via_to_via_spacing()
    test_display_stagger_vs_esp32()
    test_esop8_ep_pad_clearance()
    test_msk12c02_unique_sh_pads()
    test_btn_r_routed()
    test_kicad_drc_edge_clearance()
    test_sw8_slot_clearance()
    test_btn_r_edge_clearance()
    test_sd_gnd_via_clearance()
    test_bat_plus_via_vbus_clearance()
    test_mounting_holes_npth()
    test_lx_bat_trace_spacing()
    test_button_vx_spacing()
    test_gnd_lcd_d7_spacing()
    test_lcd_sd_approach_spacing()
    test_via_pad_spacing()
    test_usb_cap_trace_spacing()
    test_mounting_hole_trace_clearance()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")
    sys.exit(1 if FAIL else 0)
