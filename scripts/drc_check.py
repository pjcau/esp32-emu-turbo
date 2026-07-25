#!/usr/bin/env python3
"""DRC (Design Rule Check) for JLCPCB 4-layer PCB.

Parses the generated .kicad_pcb file and checks compliance with
JLCPCB manufacturing constraints.

Usage:
    python3 scripts/drc_check.py [path/to/file.kicad_pcb]

Exit code 0 = all checks passed, 1 = errors found.
"""

import re
import sys
import math
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── JLCPCB 4-Layer Design Rules ──────────────────────────────────
RULES = {
    "min_trace_width": 0.09,       # mm (practical: 0.2mm)
    "min_trace_spacing": 0.09,     # mm (practical: 0.15mm)
    "min_via_drill": 0.15,         # mm
    "min_via_pad": 0.45,           # mm
    "min_annular_ring": 0.13,      # mm
    "min_board_edge_clearance": 0.3,  # mm
    "min_drill_to_edge": 0.4,      # mm
    "min_drill_spacing": 0.25,     # mm (edge-to-edge, JLCPCB 4-layer: 0.254mm)
    "min_via_copper_spacing": 0.15,  # mm (via copper-to-copper clearance)
    "min_silkscreen_width": 0.15,    # mm (JLCPCB minimum silkscreen line)
    "board_width": 160.0,
    "board_height": 75.0,
}

# FPC slot cutout (internal Edge.Cuts rectangle)
# PCB coordinates: center at (127, 35.5), 3mm wide × 24mm tall
SLOT_X1 = 125.5   # left edge
SLOT_X2 = 128.5   # right edge
SLOT_Y1 = 23.5    # top edge
SLOT_Y2 = 47.5    # bottom edge


def parse_pcb(filepath):
    """Parse KiCad PCB file and extract design elements (via cache)."""
    from pcb_cache import load_cache
    cache = load_cache(Path(filepath))

    # THT pads with drill (deduplicated by position)
    seen = set()
    tht_pads = []
    for p in cache["pads"]:
        if p.get("type") == "thru_hole" and p.get("drill", 0) > 0:
            key = (p["x"], p["y"])
            if key not in seen:
                seen.add(key)
                tht_pads.append({
                    "x": p["x"], "y": p["y"],
                    "size_w": p["w"], "size_h": p["h"],
                    "drill": p["drill"],
                })

    # Filter nets: id > 0 and non-empty name
    nets = [n for n in cache["nets"] if n["id"] > 0 and n["name"]]

    return {
        "segments": cache["segments"],
        "vias": cache["vias"],
        "footprints": [],
        "zones": cache["zones"],
        "nets": nets,
        "pads": tht_pads,
    }


def check_trace_width(data):
    """Check all trace widths meet minimum."""
    errors = []
    min_w = RULES["min_trace_width"]
    for seg in data["segments"]:
        if seg["width"] < min_w:
            errors.append(
                f"Trace width {seg['width']}mm < {min_w}mm at "
                f"({seg['x1']},{seg['y1']})->({seg['x2']},{seg['y2']}) "
                f"on {seg['layer']}"
            )
    return errors


def check_via_dimensions(data):
    """Check via drill and annular ring."""
    errors = []
    min_drill = RULES["min_via_drill"]
    min_ring = RULES["min_annular_ring"]
    for v in data["vias"]:
        if v["drill"] < min_drill:
            errors.append(
                f"Via drill {v['drill']}mm < {min_drill}mm at "
                f"({v['x']},{v['y']})"
            )
        ring = (v["size"] - v["drill"]) / 2
        if ring < min_ring:
            errors.append(
                f"Via annular ring {ring:.3f}mm < {min_ring}mm at "
                f"({v['x']},{v['y']})"
            )
    return errors


def _in_slot(x, y, margin):
    """Check if point (with margin) intrudes into the FPC slot cutout."""
    return (SLOT_X1 - margin < x < SLOT_X2 + margin and
            SLOT_Y1 - margin < y < SLOT_Y2 + margin)


def _segment_crosses_slot(x1, y1, x2, y2, hw):
    """Check if a trace segment physically crosses through the FPC slot.

    A horizontal segment crosses if it spans the slot x-range while within
    the slot y-range. A vertical segment crosses if it spans the slot y-range
    while within the slot x-range. hw = half-width of the trace.
    """
    if abs(y1 - y2) < 0.01:  # horizontal segment
        y = y1
        if SLOT_Y1 - hw <= y <= SLOT_Y2 + hw:
            lo, hi = min(x1, x2), max(x1, x2)
            if lo < SLOT_X1 - hw and hi > SLOT_X2 + hw:
                return True
    elif abs(x1 - x2) < 0.01:  # vertical segment
        x = x1
        if SLOT_X1 - hw <= x <= SLOT_X2 + hw:
            lo, hi = min(y1, y2), max(y1, y2)
            if lo < SLOT_Y1 - hw and hi > SLOT_Y2 + hw:
                return True
    return False


def check_board_edge_clearance(data):
    """Check all elements are inside board boundaries with margin,
    and not intruding into the FPC slot cutout."""
    errors = []
    margin = RULES["min_board_edge_clearance"]
    bw = RULES["board_width"]
    bh = RULES["board_height"]

    for seg in data["segments"]:
        hw = seg["width"] / 2
        for x, y in [(seg["x1"], seg["y1"]), (seg["x2"], seg["y2"])]:
            if (x - hw < margin or x + hw > bw - margin or
                    y - hw < margin or y + hw > bh - margin):
                errors.append(
                    f"Trace at ({x},{y}) too close to board edge "
                    f"(margin={margin}mm)"
                )
            # Check endpoint slot clearance
            if _in_slot(x, y, margin):
                errors.append(
                    f"Trace at ({x},{y}) too close to FPC slot"
                )
        # Check if segment crosses through the slot
        if _segment_crosses_slot(seg["x1"], seg["y1"],
                                 seg["x2"], seg["y2"], hw):
            errors.append(
                f"Trace ({seg['x1']},{seg['y1']})->"
                f"({seg['x2']},{seg['y2']}) crosses FPC slot"
            )

    for v in data["vias"]:
        r = v["size"] / 2
        if (v["x"] - r < margin or v["x"] + r > bw - margin or
                v["y"] - r < margin or v["y"] + r > bh - margin):
            errors.append(
                f"Via at ({v['x']},{v['y']}) too close to board edge"
            )
        if _in_slot(v["x"], v["y"], margin):
            errors.append(
                f"Via at ({v['x']},{v['y']}) too close to FPC slot"
            )

    return errors


def _seg_distance(s1, s2):
    """Approximate minimum distance between two segments on same layer."""
    # Simplified: check endpoint distances
    min_d = float('inf')
    pts1 = [(s1["x1"], s1["y1"]), (s1["x2"], s1["y2"])]
    pts2 = [(s2["x1"], s2["y1"]), (s2["x2"], s2["y2"])]
    for p1 in pts1:
        for p2 in pts2:
            d = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
            min_d = min(min_d, d)
    return min_d


def check_trace_spacing(data):
    """Check minimum spacing between traces on same layer."""
    errors = []
    min_sp = RULES["min_trace_spacing"]

    # Group segments by layer
    by_layer = {}
    for seg in data["segments"]:
        by_layer.setdefault(seg["layer"], []).append(seg)

    for layer, segs in by_layer.items():
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                s1, s2 = segs[i], segs[j]
                # Skip if same net (allowed to overlap)
                if s1["net"] == s2["net"] and s1["net"] != 0:
                    continue
                d = _seg_distance(s1, s2)
                hw = (s1["width"] + s2["width"]) / 2
                clearance = d - hw
                if 0 < clearance < min_sp:
                    errors.append(
                        f"Trace spacing {clearance:.3f}mm < {min_sp}mm "
                        f"on {layer} between nets {s1['net']} and {s2['net']}"
                    )
                    if len(errors) > 20:
                        errors.append(
                            "... (truncated, too many spacing errors)")
                        return errors

    return errors


def check_drill_spacing(data):
    """Check minimum spacing between via drill holes.

    Note: THT pad positions in footprints are relative coordinates,
    not absolute.  We only check via-to-via spacing here since vias
    have absolute board coordinates.
    """
    errors = []
    min_sp = RULES["min_drill_spacing"]

    vias = [(v["x"], v["y"], v["drill"] / 2) for v in data["vias"]]

    for i in range(len(vias)):
        for j in range(i + 1, len(vias)):
            x1, y1, r1 = vias[i]
            x2, y2, r2 = vias[j]
            d = math.hypot(x1 - x2, y1 - y2)
            clearance = d - r1 - r2
            if 0 < clearance < min_sp:
                errors.append(
                    f"Via drill spacing {clearance:.3f}mm < {min_sp}mm "
                    f"between ({x1},{y1}) and ({x2},{y2})"
                )

    return errors


# ── JLCPCB SMD component minimum-spacing matrix ───────────────────
#
# Source: JLCPCB Help Center, "Minimum Spacing Requirements for SMD
# Components"
#   https://jlcpcb.com/help/article/minimum-spacing-for-smd-components
#   (retrieved 2026-07-25)
#
# These are the ONLY component-spacing figures JLCPCB publishes.  Every
# threshold enforced below traces back to a cell in this table; nothing
# here is invented or tuned.  Values are in mm and are a clearance
# (gap) between the copper of two DIFFERENT components on the SAME side
# of the board — not a centre-to-centre distance.
#
# HISTORY — why this replaced a flat 3.0 mm centre-to-centre rule:
# The previous rule required every bottom-side component pair to be
# >= 3.0 mm centre-to-centre.  That metric is not merely over-strict,
# it is *non-monotonic in the quantity that actually matters*: on this
# board R22<->R23 (2.05 mm centres) have 0.780 mm of real copper
# clearance, while R22<->U1 (16.2 mm centres) have only 0.442 mm — the
# tightest pair on the whole board.  The old rule failed the roomy pair
# and passed the tight one, because centre distance conflates package
# size with clearance.  A 0402 is 1.0 x 0.5 mm; a module is 18 x 25.5 mm.
# The fix is to measure pad-edge to pad-edge and to make the threshold
# depend on the package pair, exactly as JLCPCB specifies.
JLCPCB_SMD_SPACING = {
    ("0201", "0201"): 0.15,
    ("0201", "0402"): 0.15,
    ("0201", "0603"): 0.18,
    ("0201", "0805"): 0.18,
    ("0201", "1206"): 0.25,
    ("0201", "QFN"): 1.00,
    ("0201", "QFP"): 0.50,
    ("0201", "SOP"): 0.40,
    ("0201", "SOT"): 0.20,
    ("0201", "BGA"): 1.00,
    ("0402", "0603"): 0.18,
    ("0603", "0805"): 0.25,
    ("QFP", "BGA"): 1.50,
    ("BGA", "BGA"): 2.00,
}

CHIP_CLASSES = ("0201", "0402", "0603", "0805", "1206")


def _package_class(pkg):
    """Map a CPL package string onto a JLCPCB spacing-table class.

    Returns None for package families JLCPCB does not publish a spacing
    figure for (modules, connectors, switches, wirewound inductors,
    speakers).  None means "no published requirement" — see
    _required_spacing().  It deliberately does NOT mean "exempt": such
    pairs are still held to the strictest requirement published for
    whichever package in the pair we do recognise, and to strict
    non-overlap.
    """
    p = pkg.upper()
    for chip in CHIP_CLASSES:
        if re.search(r'(^|[_-])' + chip + r'$', p):
            return chip
    if p.startswith("SOT"):
        return "SOT"
    if p.split("-")[0] in ("SOP", "SOIC", "ESOP", "HSOP", "TSSOP", "MSOP"):
        return "SOP"
    if p.split("-")[0] in ("QFN", "DFN"):
        return "QFN"
    if p.split("-")[0] in ("QFP", "LQFP", "TQFP"):
        return "QFP"
    if p.split("-")[0] in ("BGA", "LFBGA", "WLCSP"):
        return "BGA"
    return None


def _class_demand(cls):
    """Strictest spacing JLCPCB publishes for this package class.

    For chip classes this is taken over chip-to-chip cells only: the
    chip-to-large-package cells (e.g. 0201<->BGA = 1.0) describe a
    requirement imposed by the *large* package, so folding them into a
    chip's own demand would wrongly apply BGA clearance between two
    resistors.  For non-chip classes every published cell counts.
    """
    if cls is None:
        return 0.0
    vals = []
    for (a, b), v in JLCPCB_SMD_SPACING.items():
        if cls not in (a, b):
            continue
        if cls in CHIP_CLASSES and not (a in CHIP_CLASSES and b in CHIP_CLASSES):
            continue
        vals.append(v)
    return max(vals) if vals else 0.0


def _required_spacing(cls_a, cls_b):
    """Required pad-to-pad clearance (mm) for a package pair.

    1. If JLCPCB publishes the exact pair, use that value verbatim.
    2. Otherwise use the strictest value it publishes for either class.
       This never invents a number: it is always some published cell.
    3. A class JLCPCB says nothing about contributes 0, so the pair
       falls back to the other package's published demand (and, in
       check_component_spacing, to strict non-overlap).
    """
    key = (cls_a, cls_b)
    if key in JLCPCB_SMD_SPACING:
        return JLCPCB_SMD_SPACING[key]
    if (cls_b, cls_a) in JLCPCB_SMD_SPACING:
        return JLCPCB_SMD_SPACING[(cls_b, cls_a)]
    return max(_class_demand(cls_a), _class_demand(cls_b))


def _rect_gap(a, b):
    """Signed gap between two axis-aligned rects (x0, y0, x1, y1).

    Positive = clearance, negative = overlap depth.
    """
    dx = max(b[0] - a[2], a[0] - b[2], 0.0)
    dy = max(b[1] - a[3], a[1] - b[3], 0.0)
    if dx == 0.0 and dy == 0.0:
        return -min(min(a[2], b[2]) - max(a[0], b[0]),
                    min(a[3], b[3]) - max(a[1], b[1]))
    return math.hypot(dx, dy)


# Package families that appear in this BOM and for which JLCPCB
# publishes NO spacing figure.  Listing them explicitly is what makes
# their absence auditable: check_spacing_rule_selftest() fails if any
# package in the CPL is neither classified by _package_class() nor
# named here, so a newly added QFN/BGA/etc. can never slip into the
# "no published requirement" path unnoticed.
#
# This is a list of PACKAGE FAMILIES, never of component references.
# Adding a reference here would be an exemption and is not permitted.
UNPUBLISHED_PACKAGE_FAMILIES = {
    "Module_ESP32-S3",    # castellated SMD module
    "USB-C-SMD-16P",      # connector
    "FPC-40P-0.5mm",      # connector
    "JST-PH-2P-SMD",      # connector
    "TF-01A",             # micro-SD socket
    "SS-12D00G3",         # slide switch
    "SW-SMD-5.1x5.1",     # tact switch
    "SMD-4x4x2",          # shielded power inductor (L1)
    "IND-SMD-4.0x4.0",    # shielded power inductor (L2, SY8089 buck output) —
                          # same class as SMD-4x4x2 above, different footprint
                          # name. JLCPCB publishes no spacing cell for
                          # wire-wound power inductors.
    "Speaker-22mm",       # speaker pads
    "Fiducial",           # fiducial mark
}


def _spacing_violations(groups, pkg_of):
    """Pure pairwise engine: find spacing violations in pad geometry.

    ``groups`` maps (reference, side) -> list of pad rects.  Kept free
    of I/O so check_spacing_rule_selftest() can drive it with synthetic
    geometry and prove the detector still fires.
    """
    bounds = {k: (min(r[0] for r in v), min(r[1] for r in v),
                  max(r[2] for r in v), max(r[3] for r in v))
              for k, v in groups.items()}

    keys = sorted(groups)
    errors = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            (ref_a, side_a), (ref_b, side_b) = keys[i], keys[j]
            # Same physical part (e.g. a THT pad appearing on both
            # sides) is not a component-to-component pair.
            if side_a != side_b or ref_a == ref_b:
                continue

            cls_a = _package_class(pkg_of.get(ref_a, ""))
            cls_b = _package_class(pkg_of.get(ref_b, ""))
            required = _required_spacing(cls_a, cls_b)

            # Cheap reject on bounding boxes before the O(n*m) pad scan.
            if _rect_gap(bounds[keys[i]], bounds[keys[j]]) > required:
                continue

            gap = min(_rect_gap(ra, rb)
                      for ra in groups[keys[i]] for rb in groups[keys[j]])

            if gap <= 0.0:
                errors.append(
                    f"{ref_a} <-> {ref_b}: pads OVERLAP by {-gap:.3f}mm "
                    f"on {side_a}.Cu"
                )
            elif gap < required:
                errors.append(
                    f"{ref_a}({cls_a or pkg_of.get(ref_a, '?')}) <-> "
                    f"{ref_b}({cls_b or pkg_of.get(ref_b, '?')}): "
                    f"{gap:.3f}mm pad-to-pad on {side_a}.Cu "
                    f"(JLCPCB min {required:.2f}mm)"
                )
    return errors


def _pad_groups(pcb_path):
    """Group PCB pad rectangles by (reference, board side)."""
    from pcb_cache import load_cache

    cache = load_cache(Path(pcb_path))
    groups = {}
    for p in cache["pads"]:
        side = "F" if p["layer"].startswith("F") else "B"
        groups.setdefault((p["ref"], side), []).append(
            (p["x"] - p["w"] / 2, p["y"] - p["h"] / 2,
             p["x"] + p["w"] / 2, p["y"] + p["h"] / 2))
    return groups


def check_component_spacing(pcb_path):
    """Same-side component clearance against the JLCPCB spacing matrix.

    Measures the true minimum pad-copper-to-pad-copper distance between
    every pair of distinct components sharing a board side, using the
    pad geometry of the generated PCB (not estimated from placement
    coordinates).  Components on opposite sides cannot collide, so
    F.Cu and B.Cu are evaluated independently.

    There is no per-reference exemption list, and there must never be
    one: if a pair is too close the placement gets fixed, and if the
    threshold is wrong the table above gets corrected against JLCPCB's
    published spec.
    """
    from scripts.generate_pcb.jlcpcb_export import _build_placements

    pkg_of = {ref: pkg for ref, _v, pkg, _x, _y, _r, _l in _build_placements()}
    return _spacing_violations(_pad_groups(pcb_path), pkg_of)


def check_spacing_rule_selftest():
    """Prove the spacing rule still asserts something.

    A clearance rule that has quietly stopped matching real geometry
    passes just as loudly as one that works.  This guards three ways
    the rule above could rot into a no-op:

      1. every package in the CPL is classified, or explicitly recorded
         as one JLCPCB publishes no figure for;
      2. _required_spacing() is symmetric and never returns a number
         that is not a published cell — i.e. nobody has slipped an
         interpolation or a hand-tuned constant into the fallback;
      3. the detector fires on synthetic geometry that violates it.
    """
    from scripts.generate_pcb.jlcpcb_export import _build_placements

    errors = []

    # 1. No package may silently fall through to "no requirement".
    for ref, _v, pkg, _x, _y, _r, _l in _build_placements():
        if _package_class(pkg) is None and pkg not in UNPUBLISHED_PACKAGE_FAMILIES:
            errors.append(
                f"package '{pkg}' (e.g. {ref}) is neither classified into "
                f"the JLCPCB spacing matrix nor listed in "
                f"UNPUBLISHED_PACKAGE_FAMILIES — classify it or record why"
            )

    # 2. Every value the rule can demand must be a published cell, and
    #    the rule must be symmetric.  Comparing published cells against
    #    themselves would be tautological, so instead assert the two
    #    properties that a future "improvement" would actually break:
    #    invented numbers, and order-dependent results.
    published_values = set(JLCPCB_SMD_SPACING.values()) | {0.0}
    all_classes = sorted(
        {c for cell in JLCPCB_SMD_SPACING for c in cell}) + [None]
    for a in all_classes:
        for b in all_classes:
            fwd, rev = _required_spacing(a, b), _required_spacing(b, a)
            if abs(fwd - rev) > 1e-9:
                errors.append(
                    f"_required_spacing is asymmetric for ({a},{b}): "
                    f"{fwd} vs {rev}"
                )
            if not any(abs(fwd - v) < 1e-9 for v in published_values):
                errors.append(
                    f"_required_spacing({a},{b}) = {fwd} is not a value "
                    f"JLCPCB publishes — thresholds must never be invented"
                )

    # 3. The detector must still detect.  Two 0402 pads 0.10mm apart
    #    violate the 0.15mm floor; two pads sharing area overlap.
    probe_pkg = {"__A": "R_0402", "__B": "R_0402", "__C": "R_0402"}
    too_close = _spacing_violations(
        {("__A", "B"): [(0.0, 0.0, 1.0, 0.5)],
         ("__B", "B"): [(1.1, 0.0, 2.1, 0.5)]}, probe_pkg)
    if not too_close:
        errors.append(
            "spacing detector did not fire on two 0402 pads 0.10mm apart"
        )
    overlapping = _spacing_violations(
        {("__A", "B"): [(0.0, 0.0, 1.0, 0.5)],
         ("__C", "B"): [(0.5, 0.0, 1.5, 0.5)]}, probe_pkg)
    if not any("OVERLAP" in e for e in overlapping):
        errors.append("spacing detector did not fire on overlapping pads")

    # 4. Opposite sides must never be compared (they cannot collide).
    cross_side = _spacing_violations(
        {("__A", "F"): [(0.0, 0.0, 1.0, 0.5)],
         ("__B", "B"): [(0.5, 0.0, 1.5, 0.5)]}, probe_pkg)
    if cross_side:
        errors.append(
            f"spacing detector wrongly compared F.Cu to B.Cu: {cross_side}"
        )

    return errors


def check_mounting_hole_keepout():
    """Keep components clear of the enclosure mounting-hole bosses.

    This is a MECHANICAL rule, unrelated to SMT assembly spacing: the
    enclosure boss and the M2.5 screw head occupy space above the board,
    so no component body may sit under them.  It is kept as a distance
    from the hole centre to the component origin because that is what
    the enclosure boss geometry in enclosure.scad is specified against.
    """
    from scripts.generate_pcb.jlcpcb_export import _build_placements
    from scripts.generate_pcb.board import MOUNT_HOLES_ENC, enc_to_pcb

    MIN_BOSS_CLEARANCE = 3.0  # mm, hole centre to component origin

    mounts = [enc_to_pcb(ex, ey) for ex, ey in MOUNT_HOLES_ENC]

    errors = []
    for ref, _v, _pkg, x, y, _r, _layer in _build_placements():
        for mx, my in mounts:
            d = math.hypot(x - mx, y - my)
            if d < MIN_BOSS_CLEARANCE:
                errors.append(
                    f"{ref} is {d:.2f}mm from mounting hole "
                    f"({mx:.0f},{my:.0f}) — min {MIN_BOSS_CLEARANCE}mm"
                )
    return errors


def check_text_on_copper(pcb_path):
    """Check that no text (Reference/Value) is placed on copper layers.

    Text on F.Cu/B.Cu causes manufacturing issues — designators and values
    should be on silkscreen (F.SilkS/B.SilkS) or fabrication (F.Fab/B.Fab).
    Handles both single-line and multi-line property blocks.
    """
    errors = []
    text = Path(pcb_path).read_text()
    lines = text.split("\n")
    fp_name = ""

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track current footprint
        fp_match = re.match(r'\(footprint "([^"]*)"', stripped)
        if fp_match:
            fp_name = fp_match.group(1)

        # Match property lines with a layer attribute on the SAME line
        prop_match = re.search(
            r'\(property "(Reference|Value)" "([^"]*)".*'
            r'\(layer "(F\.Cu|B\.Cu)"\)',
            stripped
        )
        if prop_match:
            prop_name = prop_match.group(1)
            prop_value = prop_match.group(2)
            layer = prop_match.group(3)
            errors.append(
                f'{prop_name} "{prop_value}" of {fp_name} on {layer} '
                f"(line {i + 1}) — should be on SilkS or Fab"
            )

    return errors


def check_board_outline_arcs(pcb_path):
    """Check that all Edge.Cuts arcs are minor arcs (≤ 180°).

    A wrong midpoint causes KiCad to draw a major arc (270°) instead
    of a minor arc (90°), creating large circular notches in the
    board outline.  The midpoint must lie on the short (minor) side
    of the arc.
    """
    errors = []
    text = Path(pcb_path).read_text()

    for m in re.finditer(
        r'\(gr_arc\s+'
        r'\(start\s+([\d.-]+)\s+([\d.-]+)\)\s+'
        r'\(mid\s+([\d.-]+)\s+([\d.-]+)\)\s+'
        r'\(end\s+([\d.-]+)\s+([\d.-]+)\)'
        r'.*?\(layer\s+"Edge\.Cuts"\)',
        text, re.DOTALL
    ):
        sx, sy = float(m.group(1)), float(m.group(2))
        mx, my = float(m.group(3)), float(m.group(4))
        ex, ey = float(m.group(5)), float(m.group(6))

        # Compute the arc center from three points (start, mid, end).
        # The center lies at the intersection of perpendicular bisectors.
        ax, ay = mx - sx, my - sy
        bx, by = ex - sx, ey - sy
        D = 2 * (ax * by - ay * bx)
        if abs(D) < 1e-9:
            continue  # Degenerate (collinear points)

        cx = sx + (by * (ax * ax + ay * ay) - ay * (bx * bx + by * by)) / D
        cy = sy + (ax * (bx * bx + by * by) - bx * (ax * ax + ay * ay)) / D

        # Compute angles from center
        a_start = math.atan2(sy - cy, sx - cx)
        a_mid = math.atan2(my - cy, mx - cx)
        a_end = math.atan2(ey - cy, ex - cx)

        # The arc swept angle going start→mid→end.
        # Normalize angles so the sweep direction is consistent.
        def angle_diff(a, b):
            d = (b - a) % (2 * math.pi)
            return d

        sweep_sm = angle_diff(a_start, a_mid)
        sweep_se = angle_diff(a_start, a_end)

        # If mid is between start and end (going one direction),
        # the total sweep is sweep_se.  If mid is on the other side,
        # the sweep is 2π - sweep_se.
        if sweep_sm <= sweep_se:
            total_sweep = sweep_se
        else:
            total_sweep = 2 * math.pi - sweep_se

        # Reject arcs > 180° (π radians) — these are major arcs
        if total_sweep > math.pi + 0.01:  # small tolerance
            errors.append(
                f"Edge.Cuts arc at start=({sx},{sy}) mid=({mx},{my}) "
                f"end=({ex},{ey}) sweeps {math.degrees(total_sweep):.0f}° "
                f"(> 180°) — midpoint selects major arc instead of minor"
            )

    return errors


def check_net_connectivity(data):
    """Check that all declared nets have routing (traces or vias).

    Counts both trace segments AND vias per net.  Nets with a
    stub-to-via pattern (1 segment + ≥1 via) are valid — the via
    connects to an inner-layer zone.
    """
    warnings = []
    seg_count = {}
    via_count = {}

    for seg in data["segments"]:
        net = seg["net"]
        if net > 0:
            seg_count[net] = seg_count.get(net, 0) + 1

    for via in data["vias"]:
        net = via.get("net", 0)
        if net > 0:
            via_count[net] = via_count.get(net, 0) + 1

    # Nets declared for future use but intentionally unrouted
    _UNROUTED_OK = {"I2S_BCLK", "I2S_LRCK"}

    net_names = {n["id"]: n["name"] for n in data["nets"]}
    for nid, name in net_names.items():
        if name in _UNROUTED_OK:
            continue
        total = seg_count.get(nid, 0) + via_count.get(nid, 0)
        if total == 0:
            warnings.append(f"Net {nid} \"{name}\" has no traces or vias")

    return warnings


def check_via_copper_spacing(data):
    """Check minimum copper-to-copper clearance between vias.

    Unlike drill spacing (edge-to-edge of holes), this checks the
    copper annular ring overlap between adjacent vias.
    """
    errors = []
    min_sp = RULES["min_via_copper_spacing"]

    vias = [(v["x"], v["y"], v["size"] / 2) for v in data["vias"]]

    for i in range(len(vias)):
        for j in range(i + 1, len(vias)):
            x1, y1, r1 = vias[i]
            x2, y2, r2 = vias[j]
            d = math.hypot(x1 - x2, y1 - y2)
            clearance = d - r1 - r2
            if -0.01 < clearance < min_sp:
                errors.append(
                    f"Via copper spacing {clearance:.3f}mm < {min_sp}mm "
                    f"between ({x1},{y1}) and ({x2},{y2})"
                )

    return errors


def check_silkscreen_line_width(pcb_path):
    """Check silkscreen lines meet JLCPCB minimum width."""
    errors = []
    min_w = RULES["min_silkscreen_width"]
    text = Path(pcb_path).read_text()

    for m in re.finditer(
        r'\(gr_line[^)]*\).*?\(stroke \(width ([\d.]+)\).*?'
        r'\(layer "([FB]\.SilkS)"\)',
        text,
    ):
        width = float(m.group(1))
        if width < min_w:
            errors.append(
                f"Silkscreen line width {width}mm < {min_w}mm "
                f"on {m.group(2)}"
            )

    return errors


def main():
    pcb_path = sys.argv[1] if len(sys.argv) > 1 else \
        "hardware/kicad/esp32-emu-turbo.kicad_pcb"

    if not Path(pcb_path).exists():
        print(f"ERROR: {pcb_path} not found")
        sys.exit(1)

    print(f"DRC Check: {pcb_path}")
    print(f"Rules: JLCPCB 4-layer")
    print("=" * 60)

    data = parse_pcb(pcb_path)
    print(f"Parsed: {len(data['segments'])} segments, "
          f"{len(data['vias'])} vias, "
          f"{len(data['nets'])} nets, "
          f"{len(data['pads'])} THT pads")
    print()

    all_errors = []
    all_warnings = []

    checks = [
        ("Trace Width", check_trace_width),
        ("Via Dimensions", check_via_dimensions),
        ("Board Edge Clearance", check_board_edge_clearance),
        ("Trace Spacing", check_trace_spacing),
        ("Drill Spacing", check_drill_spacing),
        ("Via Copper Spacing", check_via_copper_spacing),
    ]

    # Self-test of the spacing rule (must run BEFORE the rule itself:
    # a broken detector would otherwise report a clean board)
    selftest_errors = check_spacing_rule_selftest()
    status = "PASS" if not selftest_errors else \
        f"FAIL ({len(selftest_errors)} errors)"
    print(f"  [{status}] Spacing Rule Self-Test")
    for e in selftest_errors[:10]:
        print(f"         {e}")
    all_errors.extend(selftest_errors)

    # Component spacing (true pad geometry, JLCPCB published matrix)
    spacing_errors = check_component_spacing(pcb_path)
    status = "PASS" if not spacing_errors else \
        f"FAIL ({len(spacing_errors)} errors)"
    print(f"  [{status}] Component Spacing (JLCPCB SMD matrix)")
    for e in spacing_errors[:10]:
        print(f"         {e}")
    all_errors.extend(spacing_errors)

    # Mounting hole keepout (mechanical, uses CPL data)
    mh_errors = check_mounting_hole_keepout()
    status = "PASS" if not mh_errors else f"FAIL ({len(mh_errors)} errors)"
    print(f"  [{status}] Mounting Hole Keepout")
    for e in mh_errors[:10]:
        print(f"         {e}")
    all_errors.extend(mh_errors)

    for name, fn in checks:
        errors = fn(data)
        status = "PASS" if not errors else f"FAIL ({len(errors)} errors)"
        print(f"  [{status}] {name}")
        for e in errors[:5]:
            print(f"         {e}")
        if len(errors) > 5:
            print(f"         ... and {len(errors) - 5} more")
        all_errors.extend(errors)

    # Text on copper check (uses raw PCB file, not parsed data)
    copper_text_errors = check_text_on_copper(pcb_path)
    status = "PASS" if not copper_text_errors else \
        f"FAIL ({len(copper_text_errors)} errors)"
    print(f"  [{status}] Text on Copper Layers")
    for e in copper_text_errors[:5]:
        print(f"         {e}")
    if len(copper_text_errors) > 5:
        print(f"         ... and {len(copper_text_errors) - 5} more")
    all_errors.extend(copper_text_errors)

    # Board outline arc check (uses raw PCB file, not parsed data)
    arc_errors = check_board_outline_arcs(pcb_path)
    status = "PASS" if not arc_errors else \
        f"FAIL ({len(arc_errors)} errors)"
    print(f"  [{status}] Board Outline Arcs (no major arcs)")
    for e in arc_errors[:5]:
        print(f"         {e}")
    all_errors.extend(arc_errors)

    # Silkscreen line width check (uses raw PCB file)
    silk_errors = check_silkscreen_line_width(pcb_path)
    status = "PASS" if not silk_errors else \
        f"FAIL ({len(silk_errors)} errors)"
    print(f"  [{status}] Silkscreen Line Width (>= {RULES['min_silkscreen_width']}mm)")
    for e in silk_errors[:5]:
        print(f"         {e}")
    if len(silk_errors) > 5:
        print(f"         ... and {len(silk_errors) - 5} more")
    all_errors.extend(silk_errors)

    # Connectivity is a warning, not a hard error
    print()
    warnings = check_net_connectivity(data)
    if warnings:
        print(f"  [WARN] Net Connectivity ({len(warnings)} warnings)")
        for w in warnings[:10]:
            print(f"         {w}")
        if len(warnings) > 10:
            print(f"         ... and {len(warnings) - 10} more")
        all_warnings.extend(warnings)
    else:
        print("  [PASS] Net Connectivity")

    print()
    print("=" * 60)
    if all_errors:
        print(f"RESULT: FAIL — {len(all_errors)} errors, "
              f"{len(all_warnings)} warnings")
        sys.exit(1)
    else:
        print(f"RESULT: PASS — 0 errors, {len(all_warnings)} warnings")
        sys.exit(0)


if __name__ == "__main__":
    main()
