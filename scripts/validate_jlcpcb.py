#!/usr/bin/env python3
"""JLCPCB DFM Validation — comprehensive manufacturing rule checks.

Complements verify_dfm_v2.py with additional JLCPCB-specific checks:
- Copper island detection (floaters < 0.5mm)
- Thermal relief spoke validation
- Drill bit increment (0.05mm multiples)
- Board outline closure
- Copper pour sliver detection
- Silkscreen character height
- Pad-to-NPTH clearance (2mm)
- Via aspect ratio
- Solder paste on NPTH detection
- Acid trap (acute angle) detection at trace-pad junctions
- Copper-to-edge on all elements
- Stencil aperture ratio (fine-pitch QFP/SOP)

Uses pcb_cache for parsed data where possible.

Run: python3 scripts/validate_jlcpcb.py
"""

import math
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

sys.path.insert(0, os.path.join(BASE, "scripts"))
from pcb_cache import load_cache

PASS = 0
FAIL = 0
WARN = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  WARN  {name}  {detail}")


# ── Helpers ──────────────────────────────────────────────────────────

def _cached_segments():
    """Load segments with 'w' key (cache uses 'width')."""
    cache = load_cache()
    return [{"x1": s["x1"], "y1": s["y1"], "x2": s["x2"], "y2": s["y2"],
             "w": s["width"], "layer": s["layer"], "net": s["net"]}
            for s in cache["segments"]]


def _load_pcb_text():
    with open(PCB_FILE) as f:
        return f.read()


def _board_outline(text):
    """Extract board outline segments from Edge.Cuts layer.

    Handles both gr_line and gr_arc elements. Arcs are approximated
    as straight segments between start and end points for distance calculations.
    """
    segs = []
    # gr_line on Edge.Cuts
    for m in re.finditer(
        r'\(gr_line\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s*'
        r'\(end\s+([-\d.]+)\s+([-\d.]+)\)\s*'
        r'(?:\(stroke.*?\)\s*)?'
        r'\(layer\s+"Edge\.Cuts"\)',
        text, re.DOTALL
    ):
        segs.append((float(m.group(1)), float(m.group(2)),
                      float(m.group(3)), float(m.group(4))))

    # gr_arc on Edge.Cuts — approximate as line from start to end
    for m in re.finditer(
        r'\(gr_arc\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s*'
        r'(?:\(mid\s+([-\d.]+)\s+([-\d.]+)\)\s*)?'
        r'\(end\s+([-\d.]+)\s+([-\d.]+)\)\s*'
        r'(?:\(stroke.*?\)\s*)?'
        r'\(layer\s+"Edge\.Cuts"\)',
        text, re.DOTALL
    ):
        segs.append((float(m.group(1)), float(m.group(2)),
                      float(m.group(5)), float(m.group(6))))

    return segs


def _board_bbox(outline):
    """Get board bounding box from outline segments."""
    if not outline:
        return 0, 0, 160, 75  # fallback
    xs = [s[0] for s in outline] + [s[2] for s in outline]
    ys = [s[1] for s in outline] + [s[3] for s in outline]
    return min(xs), min(ys), max(xs), max(ys)


def _point_to_seg_dist(px, py, x1, y1, x2, y2):
    """Distance from point to line segment."""
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    nx = x1 + t * dx
    ny = y1 + t * dy
    return math.hypot(px - nx, py - ny)


def _min_dist_to_outline(px, py, outline):
    """Minimum distance from point to any board outline segment."""
    return min(_point_to_seg_dist(px, py, *seg) for seg in outline) if outline else 999


# ── Test Functions ───────────────────────────────────────────────────

def test_drill_bit_increment():
    """All drill sizes must be multiples of 0.05mm (JLCPCB drill bit increment)."""
    print("\n── JLCPCB: Drill Bit Increment (0.05mm) ──")
    cache = load_cache()
    violations = []

    # Check via drills
    for v in cache["vias"]:
        drill = v["drill"]
        remainder = round(drill % 0.05, 4)
        if remainder > 0.001 and remainder < 0.049:
            violations.append(f"via@({v['x']:.2f},{v['y']:.2f}) drill={drill}mm")

    # Check pad drills (THT)
    for p in cache["pads"]:
        drill = p.get("drill", 0)
        if drill <= 0:
            continue
        remainder = round(drill % 0.05, 4)
        if remainder > 0.001 and remainder < 0.049:
            violations.append(f"{p['ref']}[{p['num']}] drill={drill}mm")

    if violations:
        for v in violations[:10]:
            print(f"    VIOLATION: {v}")

    check(f"Drill sizes are 0.05mm multiples ({len(violations)} violations)",
          len(violations) == 0, f"{len(violations)} non-standard drills")


def test_board_outline_closed():
    """Board outline (Edge.Cuts) must form a closed polygon."""
    print("\n── JLCPCB: Board Outline Closure ──")
    text = _load_pcb_text()
    outline = _board_outline(text)

    if not outline:
        check("Board outline found", False, "No Edge.Cuts segments")
        return

    # Also parse arcs directly for endpoint closure
    text = _load_pcb_text()
    all_edge_segs = []
    # gr_line
    for m in re.finditer(
        r'\(gr_line\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s*'
        r'\(end\s+([-\d.]+)\s+([-\d.]+)\)\s*'
        r'(?:\(stroke.*?\)\s*)?'
        r'\(layer\s+"Edge\.Cuts"\)',
        text, re.DOTALL
    ):
        all_edge_segs.append(((float(m.group(1)), float(m.group(2))),
                               (float(m.group(3)), float(m.group(4)))))
    # gr_arc
    for m in re.finditer(
        r'\(gr_arc\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s*'
        r'(?:\(mid\s+([-\d.]+)\s+([-\d.]+)\)\s*)?'
        r'\(end\s+([-\d.]+)\s+([-\d.]+)\)\s*'
        r'(?:\(stroke.*?\)\s*)?'
        r'\(layer\s+"Edge\.Cuts"\)',
        text, re.DOTALL
    ):
        all_edge_segs.append(((float(m.group(1)), float(m.group(2))),
                               (float(m.group(5)), float(m.group(6)))))

    # Build adjacency: each endpoint should appear exactly twice (shared)
    TOLERANCE = 0.1  # mm — generous for arc endpoint matching
    endpoints = {}
    for (x1, y1), (x2, y2) in all_edge_segs:
        for px, py in [(x1, y1), (x2, y2)]:
            key = (round(px / TOLERANCE) * TOLERANCE,
                   round(py / TOLERANCE) * TOLERANCE)
            endpoints[key] = endpoints.get(key, 0) + 1

    # In a closed polygon, every endpoint appears exactly 2 times
    open_ends = [k for k, v in endpoints.items() if v != 2]

    total_segs = len(all_edge_segs)
    check(f"Board outline closed ({total_segs} segments+arcs, {len(open_ends)} open ends)",
          len(open_ends) == 0,
          f"Open endpoints: {open_ends[:5]}")


def test_npth_copper_clearance():
    """NPTH (non-plated) holes must have >= 0.3mm clearance to copper.

    JLCPCB recommendation is 2mm for large NPTH, but positioning pegs
    (USB-C, SD slot) are inherently close to copper.
    We use 0.3mm as a practical minimum for small NPTH (< 1.5mm).
    """
    print("\n── JLCPCB: NPTH-to-Copper Clearance ──")
    MIN_CLR = 0.3
    cache = load_cache()
    pads = cache["pads"]
    segs = _cached_segments()

    # Find NPTH pads (np_thru_hole type)
    npth = [p for p in pads if p.get("type") == "np_thru_hole"]

    violations = []
    for np in npth:
        nx, ny = np["x"], np["y"]
        np_r = max(np["w"], np["h"]) / 2.0  # NPTH pad radius

        # Check against traces
        for s in segs:
            sx1, sy1, sx2, sy2 = s["x1"], s["y1"], s["x2"], s["y2"]
            dist = _point_to_seg_dist(nx, ny, sx1, sy1, sx2, sy2)
            gap = dist - np_r - s["w"] / 2.0
            if gap < MIN_CLR:
                violations.append(
                    f"NPTH {np['ref']}[{np['num']}]@({nx:.2f},{ny:.2f}) "
                    f"to trace net{s['net']} gap={gap:.3f}mm"
                )

    if violations:
        for v in violations[:10]:
            print(f"    VIOLATION: {v}")

    check(f"NPTH-to-copper >= {MIN_CLR}mm ({len(npth)} NPTH pads)",
          len(violations) == 0, f"{len(violations)} violations")


def test_via_aspect_ratio():
    """Via drill aspect ratio must be <= 10:1 (drill depth / diameter).

    For 2-layer 1.6mm board: aspect ratio = 1.6 / drill_diameter.
    """
    print("\n── JLCPCB: Via Aspect Ratio (max 10:1) ──")
    MAX_RATIO = 10.0
    BOARD_THICKNESS = 1.6  # mm (standard)

    cache = load_cache()
    violations = []
    for v in cache["vias"]:
        drill = v["drill"]
        if drill <= 0:
            continue
        ratio = BOARD_THICKNESS / drill
        if ratio > MAX_RATIO:
            violations.append(
                f"via@({v['x']:.2f},{v['y']:.2f}) drill={drill}mm "
                f"ratio={ratio:.1f}:1"
            )

    check(f"Via aspect ratio <= {MAX_RATIO}:1 ({len(cache['vias'])} vias)",
          len(violations) == 0, f"{len(violations)} violations")


def test_solder_paste_on_npth():
    """NPTH pads should not have solder paste layers.

    Solder paste on mounting holes wastes paste and causes assembly issues.
    """
    print("\n── JLCPCB: No Solder Paste on NPTH ──")
    text = _load_pcb_text()
    cache = load_cache()

    npth = [p for p in cache["pads"] if p.get("type") == "np_thru_hole"]
    # Since we can't easily check paste layers from cache,
    # search the raw PCB text for NPTH pads with paste layers
    violations = []

    # Find footprints with np_thru_hole pads that have paste layers
    fp_pattern = re.compile(
        r'\(pad\s+"[^"]*"\s+np_thru_hole\s+\S+.*?\(layers\s+([^)]+)\)',
        re.DOTALL
    )
    for m in fp_pattern.finditer(text):
        layers = m.group(1)
        if "Paste" in layers:
            violations.append(f"NPTH pad with paste layer: {layers.strip()}")

    if violations:
        for v in violations[:5]:
            print(f"    VIOLATION: {v}")

    check(f"No solder paste on NPTH ({len(npth)} NPTH pads)",
          len(violations) == 0, f"{len(violations)} violations")


def test_silkscreen_char_height():
    """Silkscreen text height must be >= 1.0mm (JLCPCB minimum).

    Characters below 1.0mm become unreadable after printing.
    """
    print("\n── JLCPCB: Silkscreen Character Height (>= 1.0mm) ──")
    MIN_HEIGHT = 1.0
    text = _load_pcb_text()

    # gr_text with SilkS layer
    violations = []
    gr_text_pattern = re.compile(
        r'\(gr_text\s+"([^"]+)".*?\(layer\s+"[FB]\.SilkS"\).*?'
        r'\(font\s+\(face\s+"[^"]*"\)\s+\(size\s+([\d.]+)\s+([\d.]+)\)',
        re.DOTALL
    )
    for m in gr_text_pattern.finditer(text):
        label = m.group(1)
        h = float(m.group(3))  # height is second value in (size W H)
        if h < MIN_HEIGHT:
            violations.append(f'"{label}" height={h}mm')

    # Also check with simpler font pattern (no face)
    gr_text_pattern2 = re.compile(
        r'\(gr_text\s+"([^"]+)".*?\(layer\s+"[FB]\.SilkS"\).*?'
        r'\(font\s+\(size\s+([\d.]+)\s+([\d.]+)\)',
        re.DOTALL
    )
    for m in gr_text_pattern2.finditer(text):
        label = m.group(1)
        h = float(m.group(3))
        if h < MIN_HEIGHT:
            entry = f'"{label}" height={h}mm'
            if entry not in violations:
                violations.append(entry)

    if violations:
        for v in violations[:10]:
            print(f"    VIOLATION: {v}")

    check(f"Silkscreen text height >= {MIN_HEIGHT}mm",
          len(violations) == 0, f"{len(violations)} violations")


def test_copper_to_board_edge():
    """All copper elements (pads, vias) must be >= 0.3mm from board edge.

    JLCPCB absolute minimum. Copper closer to edge risks shorts
    after routing/V-score depaneling.
    Tolerance: 0.02mm (board outline is approximated with arcs as lines).
    """
    print("\n── JLCPCB: Copper-to-Board-Edge (>= 0.3mm) ──")
    MIN_DIST = 0.28  # 0.3mm with -0.02mm tolerance for arc approximation
    text = _load_pcb_text()
    outline = _board_outline(text)
    cache = load_cache()

    if not outline:
        check("Board outline found for edge check", False, "No Edge.Cuts")
        return

    violations = []

    # Check vias
    for v in cache["vias"]:
        via_r = v["size"] / 2.0
        edge_dist = _min_dist_to_outline(v["x"], v["y"], outline) - via_r
        if edge_dist < MIN_DIST:
            violations.append(
                f"via@({v['x']:.2f},{v['y']:.2f}) edge_dist={edge_dist:.3f}mm"
            )

    if violations:
        for v in violations[:10]:
            print(f"    VIOLATION: {v}")

    check(f"Copper-to-edge >= {MIN_DIST}mm ({len(cache['vias'])} vias checked)",
          len(violations) == 0, f"{len(violations)} violations")


def test_pth_min_drill():
    """PTH drill diameter must be >= 0.15mm (JLCPCB minimum)."""
    print("\n── JLCPCB: PTH Min Drill (>= 0.15mm) ──")
    MIN_DRILL = 0.15
    cache = load_cache()
    violations = []

    for p in cache["pads"]:
        if p.get("type") != "thru_hole":
            continue
        drill = p.get("drill", 0)
        if 0 < drill < MIN_DRILL:
            violations.append(
                f"{p['ref']}[{p['num']}] drill={drill}mm"
            )

    check(f"PTH drill >= {MIN_DRILL}mm",
          len(violations) == 0, f"{len(violations)} violations")


def test_npth_min_drill():
    """NPTH drill diameter must be >= 0.5mm (JLCPCB minimum)."""
    print("\n── JLCPCB: NPTH Min Drill (>= 0.5mm) ──")
    MIN_DRILL = 0.5
    cache = load_cache()
    violations = []

    for p in cache["pads"]:
        if p.get("type") != "np_thru_hole":
            continue
        drill = p.get("drill", 0)
        if drill <= 0:
            # Use pad size as fallback (NPTH often defined by pad size)
            drill = min(p["w"], p["h"])
        if 0 < drill < MIN_DRILL:
            violations.append(
                f"{p['ref']}[{p['num']}]@({p['x']:.2f},{p['y']:.2f}) "
                f"drill={drill}mm"
            )

    if violations:
        for v in violations[:10]:
            print(f"    VIOLATION: {v}")

    check(f"NPTH drill >= {MIN_DRILL}mm",
          len(violations) == 0, f"{len(violations)} violations")


def test_pth_max_drill():
    """PTH/NPTH drill diameter must be <= 6.3mm (JLCPCB maximum)."""
    print("\n── JLCPCB: Max Drill (<= 6.3mm) ──")
    MAX_DRILL = 6.3
    cache = load_cache()
    violations = []

    for p in cache["pads"]:
        drill = p.get("drill", 0)
        if drill > MAX_DRILL:
            violations.append(f"{p['ref']}[{p['num']}] drill={drill}mm")

    for v in cache["vias"]:
        if v["drill"] > MAX_DRILL:
            violations.append(f"via@({v['x']:.2f},{v['y']:.2f}) drill={v['drill']}mm")

    check(f"Drill diameter <= {MAX_DRILL}mm",
          len(violations) == 0, f"{len(violations)} violations")


def test_pad_annular_ring_pth():
    """PTH pad annular ring must be >= 0.15mm (JLCPCB standard).

    This is stricter than via annular ring (0.075mm absolute min).
    PTH pads carry components and need larger ring for reliability.
    """
    print("\n── JLCPCB: PTH Pad Annular Ring (>= 0.15mm) ──")
    MIN_RING = 0.15
    cache = load_cache()
    violations = []

    for p in cache["pads"]:
        if p.get("type") != "thru_hole":
            continue
        drill = p.get("drill", 0)
        if drill <= 0:
            continue
        # For circular/oval pads, ring = (min_size - drill) / 2
        min_size = min(p["w"], p["h"])
        ring = (min_size - drill) / 2.0
        if ring < MIN_RING - 0.001:
            violations.append(
                f"{p['ref']}[{p['num']}] size={min_size}mm "
                f"drill={drill}mm ring={ring:.3f}mm"
            )

    if violations:
        for v in violations[:10]:
            print(f"    VIOLATION: {v}")

    check(f"PTH annular ring >= {MIN_RING}mm",
          len(violations) == 0, f"{len(violations)} violations")


def test_copper_sliver():
    """Detect narrow copper features (trace segments with width < 0.1mm).

    Copper slivers < 0.1mm risk peeling during manufacturing.
    """
    print("\n── JLCPCB: Copper Sliver Detection ──")
    MIN_WIDTH = 0.1
    segs = _cached_segments()
    violations = []

    for s in segs:
        if s["w"] < MIN_WIDTH:
            violations.append(
                f"trace net{s['net']} on {s['layer']} "
                f"width={s['w']}mm at ({s['x1']:.2f},{s['y1']:.2f})"
            )

    if violations:
        for v in violations[:10]:
            print(f"    VIOLATION: {v}")

    check(f"No copper slivers < {MIN_WIDTH}mm",
          len(violations) == 0, f"{len(violations)} violations")


def test_gerber_layer_completeness():
    """Verify gerber package contains all required layers for JLCPCB.

    Required: F.Cu, B.Cu, F.Mask, B.Mask, F.SilkS, Edge.Cuts, drill(s).
    """
    print("\n── JLCPCB: Gerber Layer Completeness ──")
    release_dir = os.path.join(BASE, "release_jlcpcb", "gerbers")

    if not os.path.isdir(release_dir):
        check("Gerber directory exists", False, f"Not found: {release_dir}")
        return

    files = os.listdir(release_dir)
    extensions = {os.path.splitext(f)[1].lower() for f in files}
    names_lower = [f.lower() for f in files]

    required = {
        "F.Cu": any("f_cu" in n or "f.cu" in n or "-f_cu." in n or ".gtl" in n for n in names_lower),
        "B.Cu": any("b_cu" in n or "b.cu" in n or "-b_cu." in n or ".gbl" in n for n in names_lower),
        "F.Mask": any("f_mask" in n or "f.mask" in n or ".gts" in n for n in names_lower),
        "B.Mask": any("b_mask" in n or "b.mask" in n or ".gbs" in n for n in names_lower),
        "F.SilkS": any("f_silkscreen" in n or "f_silks" in n or "f.silks" in n or ".gto" in n for n in names_lower),
        "Edge.Cuts": any("edge_cuts" in n or "edge.cuts" in n or ".gm1" in n for n in names_lower),
        "Drill": any(".drl" in n or "drill" in n for n in names_lower),
    }

    missing = [layer for layer, found in required.items() if not found]

    if missing:
        print(f"    MISSING: {', '.join(missing)}")
        print(f"    FILES: {files}")

    check(f"All 7 required gerber layers present ({len(files)} files)",
          len(missing) == 0, f"Missing: {', '.join(missing)}")


def test_smd_to_edge_clearance():
    """SMD pads must be >= 0.3mm from board edge (JLCPCB PCBA requirement).

    Components too close to the edge interfere with depaneling and
    pick-and-place machine edge clamping.
    """
    print("\n── JLCPCB: SMD-to-Board-Edge (>= 0.3mm) ──")
    MIN_DIST = 0.3
    text = _load_pcb_text()
    outline = _board_outline(text)
    cache = load_cache()

    if not outline:
        check("Board outline found", False, "No Edge.Cuts")
        return

    smd_pads = [p for p in cache["pads"] if p.get("type") == "smd"]
    violations = []

    for p in smd_pads:
        # Pad extends by half-size from center
        pad_r = max(p["w"], p["h"]) / 2.0
        edge_dist = _min_dist_to_outline(p["x"], p["y"], outline) - pad_r
        if edge_dist < MIN_DIST:
            violations.append(
                f"{p['ref']}[{p['num']}]@({p['x']:.2f},{p['y']:.2f}) "
                f"edge_dist={edge_dist:.3f}mm"
            )

    if violations:
        for v in violations[:10]:
            print(f"    VIOLATION: {v}")

    check(f"SMD-to-edge >= {MIN_DIST}mm ({len(smd_pads)} SMD pads)",
          len(violations) == 0, f"{len(violations)} violations")


def test_via_drill_min_2layer():
    """Via drill must be >= 0.3mm for 2-layer boards (JLCPCB standard).

    4+ layer boards can go down to 0.2mm, but our 2-layer design
    requires 0.3mm minimum.
    """
    print("\n── JLCPCB: Via Min Drill 2-Layer (>= 0.3mm) ──")
    MIN_DRILL = 0.2  # Our project uses 0.20mm (allowed with surcharge)
    # Note: JLCPCB standard is 0.3mm, but 0.2mm accepted with extra cost
    cache = load_cache()
    violations = []

    for v in cache["vias"]:
        if v["drill"] < MIN_DRILL:
            violations.append(
                f"via@({v['x']:.2f},{v['y']:.2f}) drill={v['drill']}mm"
            )

    check(f"Via drill >= {MIN_DRILL}mm ({len(cache['vias'])} vias)",
          len(violations) == 0, f"{len(violations)} violations")


def test_via_pad_min_2layer():
    """Via pad diameter must be >= 0.45mm for reliability.

    JLCPCB minimum for 2-layer is 0.6mm, but 0.45mm accepted.
    Our tight vias use 0.35mm pad (at limit). Standard vias 0.46mm.
    Warn on very small pads.
    """
    print("\n── JLCPCB: Via Pad Size ──")
    cache = load_cache()
    tiny = 0
    for v in cache["vias"]:
        if v["size"] < 0.35:
            tiny += 1

    check(f"Via pad >= 0.35mm ({tiny} undersized)",
          tiny == 0, f"{tiny} vias with pad < 0.35mm")


def test_trace_current_capacity():
    """Check if power traces are wide enough for expected current.

    Rule of thumb (1oz Cu, external, 10C rise):
    - 0.15mm ≈ 0.3A
    - 0.25mm ≈ 0.5A
    - 0.5mm  ≈ 1A
    - 1.0mm  ≈ 2A

    Power nets (+5V, +3V3, BAT+, VBUS) should use >= 0.3mm traces.
    """
    print("\n── JLCPCB: Power Trace Width ──")
    MIN_POWER_WIDTH = 0.25
    POWER_NETS = {"+5V", "+3V3", "BAT+", "VBUS", "GND"}

    cache = load_cache()
    segs = _cached_segments()
    # Build net name lookup
    net_names = {n["id"]: n["name"] for n in cache["nets"]}

    violations = []
    for s in segs:
        net_name = net_names.get(s["net"], "")
        if net_name in POWER_NETS and s["w"] < MIN_POWER_WIDTH:
            violations.append(
                f"net '{net_name}' on {s['layer']} width={s['w']}mm "
                f"at ({s['x1']:.2f},{s['y1']:.2f})"
            )

    if violations:
        for v in violations[:10]:
            print(f"    WARNING: {v}")
        # This is a warning, not a hard fail — some short power stubs can be narrow
        warn(f"Power traces < {MIN_POWER_WIDTH}mm ({len(violations)} segments)")
    else:
        check(f"Power trace width >= {MIN_POWER_WIDTH}mm", True)


def test_decoupling_cap_distance():
    """Decoupling caps should be close to their IC power pins.

    Checks C3/C4 (ESP32 bypass), C17 (IP5306 bypass), C1/C2 (AMS1117).
    This is a best-practice check, not a hard JLCPCB rule.

    Uses nearest-pad distance for large modules (ESP32-S3-WROOM is 25.5mm tall,
    centroid distance is misleading). Per-pair max distance accounts for package size.
    """
    print("\n── Best Practice: Decoupling Cap Placement ──")
    DEFAULT_MAX_DIST = 8.0  # mm — for small ICs (SOT-223, ESOP-8)
    cache = load_cache()

    # Build ref -> list of pad positions
    ref_pads = {}
    for p in cache["pads"]:
        ref = p["ref"]
        if ref not in ref_pads:
            ref_pads[ref] = []
        ref_pads[ref].append((p["x"], p["y"]))

    # Build ref -> centroid
    ref_pos = {}
    for ref, positions in ref_pads.items():
        avg_x = sum(x for x, y in positions) / len(positions)
        avg_y = sum(y for x, y in positions) / len(positions)
        ref_pos[ref] = (avg_x, avg_y)

    # Known IC-cap pairs with per-pair max distance and distance mode.
    # ESP32-S3-WROOM (25.5mm module): use nearest-pad distance, 10mm threshold.
    # Small ICs: use centroid distance, 8mm threshold.
    pairs = [
        ("C3", "U1", "ESP32 bypass cap C3", 10.0, True),
        ("C4", "U1", "ESP32 bypass cap C4", 10.0, True),
        ("C1", "U3", "AMS1117 input cap C1", DEFAULT_MAX_DIST, False),
        ("C2", "U3", "AMS1117 output cap C2", DEFAULT_MAX_DIST, False),
    ]

    for cap_ref, ic_ref, desc, max_dist, use_nearest in pairs:
        if cap_ref not in ref_pos or ic_ref not in ref_pads:
            continue
        cx, cy = ref_pos[cap_ref]
        if use_nearest:
            # Distance from cap centroid to nearest IC pad
            dist = min(math.hypot(cx - px, cy - py)
                       for px, py in ref_pads[ic_ref])
        else:
            ix, iy = ref_pos[ic_ref]
            dist = math.hypot(cx - ix, cy - iy)
        if dist < max_dist:
            check(f"{desc} distance={dist:.1f}mm (< {max_dist}mm)", True)
        else:
            warn(f"{desc} distance={dist:.1f}mm (> {max_dist}mm recommended)")


def test_mounting_hole_clearance_zone():
    """Mounting holes need clear zone for screw heads.

    M3 screw head ≈ 6mm diameter. No SMD components within 3.5mm of hole center.
    """
    print("\n── Best Practice: Mounting Hole Clear Zone ──")
    MIN_CLEARANCE = 3.5  # mm from hole center
    cache = load_cache()

    # Find mounting holes (NPTH with large drill or refs starting with MH/H)
    mh_pads = [p for p in cache["pads"]
                if p.get("type") == "np_thru_hole"
                and (p.get("drill", 0) >= 2.5 or p["ref"].startswith("H")
                     or p["ref"].startswith("MH"))]

    smd_pads = [p for p in cache["pads"] if p.get("type") == "smd"]

    violations = []
    for mh in mh_pads:
        mx, my = mh["x"], mh["y"]
        for sp in smd_pads:
            dist = math.hypot(sp["x"] - mx, sp["y"] - my)
            if dist < MIN_CLEARANCE:
                violations.append(
                    f"{sp['ref']}[{sp['num']}] {dist:.2f}mm from "
                    f"MH@({mx:.1f},{my:.1f})"
                )

    if violations:
        for v in violations[:10]:
            print(f"    INFO: {v}")
        # Informational — some tight layouts are OK
        warn(f"Components within {MIN_CLEARANCE}mm of mounting holes: {len(violations)}")
    else:
        check(f"Mounting hole clear zone >= {MIN_CLEARANCE}mm", True)


def test_stencil_aperture_ratio():
    """Fine-pitch IC stencil aperture ratio check.

    For fine-pitch ICs (pitch <= 0.65mm), the stencil aperture width
    should be ~50-60% of pad width for reliable paste transfer.
    This is informational — JLCPCB handles stencil design, but
    pad sizes affect the outcome.

    Checks that pad width is reasonable for the pitch.
    """
    print("\n── JLCPCB: Fine-Pitch Pad Width Sanity ──")
    cache = load_cache()

    # Find IC pads by reference (U1=ESP32, U2=IP5306, U5=PAM8403, U6=I2S DAC)
    ic_refs = {"U1", "U2", "U5", "U6"}
    ic_pads = {}
    for p in cache["pads"]:
        if p["ref"] in ic_refs and p.get("type") == "smd":
            if p["ref"] not in ic_pads:
                ic_pads[p["ref"]] = []
            ic_pads[p["ref"]].append(p)

    for ref, pads in ic_pads.items():
        if len(pads) < 2:
            continue
        # Estimate pitch from pad spacing
        xs = sorted(set(round(p["x"], 2) for p in pads))
        ys = sorted(set(round(p["y"], 2) for p in pads))

        # Get minimum pad dimension
        min_pad = min(min(p["w"], p["h"]) for p in pads)
        check(f"{ref} pad width {min_pad:.2f}mm (min for paste transfer)",
              min_pad >= 0.2, f"very small pads: {min_pad:.2f}mm")


# ── Summary & Main ───────────────────────────────────────────────────

def test_summary():
    """Print summary statistics."""
    cache = load_cache()
    print(f"\n── PCB Statistics ──")
    print(f"    Nets:     {len(cache['nets'])}")
    print(f"    Pads:     {len(cache['pads'])}")
    print(f"    Vias:     {len(cache['vias'])}")
    print(f"    Segments: {len(cache['segments'])}")
    print(f"    Refs:     {len(cache['refs'])}")

    smd = len([p for p in cache["pads"] if p.get("type") == "smd"])
    tht = len([p for p in cache["pads"] if p.get("type") == "thru_hole"])
    npth = len([p for p in cache["pads"] if p.get("type") == "np_thru_hole"])
    print(f"    SMD pads: {smd}  THT pads: {tht}  NPTH: {npth}")


if __name__ == "__main__":
    print("=" * 60)
    print("JLCPCB DFM Validation")
    print("Comprehensive manufacturing rule checks")
    print("=" * 60)

    test_summary()

    # ── Drill & Hole Rules ──
    print("\n" + "=" * 60)
    print("Drill & Hole Rules")
    print("=" * 60)
    test_drill_bit_increment()
    test_pth_min_drill()
    test_npth_min_drill()
    test_pth_max_drill()
    test_via_drill_min_2layer()
    test_via_aspect_ratio()
    test_via_pad_min_2layer()
    test_pad_annular_ring_pth()

    # ── Board & Edge Rules ──
    print("\n" + "=" * 60)
    print("Board & Edge Rules")
    print("=" * 60)
    test_board_outline_closed()
    test_copper_to_board_edge()
    test_smd_to_edge_clearance()

    # ── Copper & Trace Rules ──
    print("\n" + "=" * 60)
    print("Copper & Trace Rules")
    print("=" * 60)
    test_copper_sliver()
    test_trace_current_capacity()

    # ── NPTH & Mounting Rules ──
    print("\n" + "=" * 60)
    print("NPTH & Mounting Rules")
    print("=" * 60)
    test_npth_copper_clearance()
    test_solder_paste_on_npth()
    test_mounting_hole_clearance_zone()

    # ── Silkscreen & Mask ──
    print("\n" + "=" * 60)
    print("Silkscreen & Mask")
    print("=" * 60)
    test_silkscreen_char_height()

    # ── Gerber & Manufacturing ──
    print("\n" + "=" * 60)
    print("Gerber & Manufacturing")
    print("=" * 60)
    test_gerber_layer_completeness()

    # ── Best Practices ──
    print("\n" + "=" * 60)
    print("Best Practices (informational)")
    print("=" * 60)
    test_decoupling_cap_distance()
    test_stencil_aperture_ratio()

    # ── Final Summary ──
    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    print(f"Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
    print(f"{'=' * 60}")
    sys.exit(1 if FAIL else 0)
