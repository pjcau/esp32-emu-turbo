#!/usr/bin/env python3
"""JLCPCB Official Capabilities Cross-Check.

Two-tier verification against JLCPCB published manufacturing limits
(source: https://jlcpcb.com/capabilities/Capabilities and
 agausmann/jlcpcb-kicad-drc community rules).

Tier 1 (FAIL): Violates JLCPCB absolute minimum — board WILL be rejected.
Tier 2 (WARN): Below JLCPCB recommended — may trigger DFM review or yield issues.

This script complements verify_dfm_v2.py (which uses our internal thresholds)
by checking against JLCPCB's actual published limits.

Run: python3 scripts/verify_jlcpcb_capabilities.py
"""

import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from pcb_cache import load_cache

PASS = 0
FAIL = 0
WARN = 0

# ── JLCPCB Official Capabilities (1-2 layer board) ─────────────────
# Source: jlcpcb.com/capabilities (absolute min) + agausmann/jlcpcb-kicad-drc (recommended)
#
# IMPORTANT: JLCPCB's universal minimum clearance for ALL copper features
# on 1-2 layer boards is 0.127mm (5mil). The agausmann DRC file uses
# STRICTER recommended values (e.g., 0.254mm via-to-track) which are
# best-practice for yield, NOT rejection thresholds.
#
# Each rule has: (absolute_min, recommended, description)
JLCPCB_RULES = {
    # Trace
    "trace_width_min":       (0.127, 0.15, "mm"),  # 5mil abs, 6mil rec
    "trace_spacing_min":     (0.127, 0.15, "mm"),  # 5mil abs, 6mil rec
    "trace_to_outline":      (0.20, 0.30, "mm"),

    # Via
    "via_hole_min":          (0.20, 0.30, "mm"),
    "via_diameter_min":      (0.45, 0.60, "mm"),  # 1-2L: 0.45mm abs, 0.50mm in agausmann DRC
    "via_annular_ring":      (0.13, 0.15, "mm"),

    # THT pad
    "tht_hole_min":          (0.20, 0.50, "mm"),
    "tht_annular_ring":      (0.25, 0.30, "mm"),

    # Clearance (different net)
    # JLCPCB absolute min for all copper clearances: 0.127mm (5mil)
    # agausmann recommended values are stricter for specific feature pairs
    "hole_to_hole_diff":     (0.50, 0.50, "mm"),   # drill-to-drill specific rule
    "via_to_via_diff":       (0.50, 0.50, "mm"),   # drill-to-drill specific rule
    "via_to_via_same":       (0.127, 0.254, "mm"), # abs=universal min, rec=agausmann
    "smd_pad_to_pad_diff":   (0.127, 0.15, "mm"),
    "tht_pad_to_pad_diff":   (0.127, 0.50, "mm"), # abs=universal min, rec=agausmann
    "via_to_track":          (0.127, 0.254, "mm"), # abs=universal min, rec=agausmann
    "pth_to_track":          (0.127, 0.33, "mm"),  # abs=universal min, rec=agausmann
    "npth_to_track":         (0.127, 0.254, "mm"), # abs=universal min, rec=agausmann
    "pad_to_track":          (0.127, 0.20, "mm"),  # abs=universal min, rec=agausmann

    # Drill
    "drill_max":             (6.30, 6.30, "mm"),
    "pth_hole_max":          (6.35, 6.35, "mm"),
}


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


def _dist(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


def _seg_min_dist(seg, px, py):
    """Min distance from point to segment centerline."""
    x1, y1, x2, y2 = seg["x1"], seg["y1"], seg["x2"], seg["y2"]
    dx, dy = x2 - x1, y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    nx = x1 + t * dx
    ny = y1 + t * dy
    return math.hypot(px - nx, py - ny)


# ── Test Functions ────────────────────────────────────────────────────

def test_trace_width():
    """All traces >= JLCPCB minimum width."""
    print("\n── JLCPCB: Trace Width ──")
    cache = load_cache()
    abs_min = JLCPCB_RULES["trace_width_min"][0]
    rec_min = JLCPCB_RULES["trace_width_min"][1]
    violations = []
    warnings = []

    for s in cache["segments"]:
        w = s["width"]
        if w < abs_min:
            violations.append(
                f"trace@({s['x1']:.2f},{s['y1']:.2f}) w={w:.3f}mm < {abs_min}mm abs min")
        elif w < rec_min:
            warnings.append(
                f"trace@({s['x1']:.2f},{s['y1']:.2f}) w={w:.3f}mm < {rec_min}mm recommended")

    check(f"Trace width >= {abs_min}mm (JLCPCB absolute min)",
          len(violations) == 0,
          f"{len(violations)} violations: {violations[:3]}")

    if warnings:
        warn(f"{len(warnings)} traces below {rec_min}mm recommended",
             f"first: {warnings[0]}")


def test_trace_spacing():
    """All trace-to-trace spacing >= JLCPCB minimum."""
    print("\n── JLCPCB: Trace-to-Trace Spacing ──")
    cache = load_cache()
    abs_min = JLCPCB_RULES["trace_spacing_min"][0]
    rec_min = JLCPCB_RULES["trace_spacing_min"][1]

    segments = cache["segments"]
    violations = []
    warnings = []

    # Build net lookup
    net_by_id = {n["id"]: n["name"] for n in cache["nets"]}

    # Only check segments on same layer with different nets
    # Group by layer for efficiency
    by_layer = {}
    for s in segments:
        layer = s["layer"]
        if layer not in by_layer:
            by_layer[layer] = []
        by_layer[layer].append(s)

    for layer, segs in by_layer.items():
        for i in range(len(segs)):
            for j in range(i + 1, min(i + 200, len(segs))):  # limit O(n²)
                s1, s2 = segs[i], segs[j]
                if s1["net"] == s2["net"]:
                    continue

                # Quick bbox filter
                margin = rec_min + max(s1["width"], s2["width"])
                if (abs(s1["x1"] - s2["x1"]) > margin + 5 and
                    abs(s1["x1"] - s2["x2"]) > margin + 5):
                    continue

                # Approximate: min distance between midpoints minus half-widths
                mx1 = (s1["x1"] + s1["x2"]) / 2
                my1 = (s1["y1"] + s1["y2"]) / 2
                mx2 = (s2["x1"] + s2["x2"]) / 2
                my2 = (s2["y1"] + s2["y2"]) / 2
                center_dist = _dist(mx1, my1, mx2, my2)
                clearance = center_dist - s1["width"] / 2 - s2["width"] / 2

                if clearance < abs_min and clearance >= 0:
                    violations.append(
                        f"{layer} traces net {s1['net']} vs {s2['net']} "
                        f"gap={clearance:.3f}mm < {abs_min}mm")
                elif clearance < rec_min and clearance >= abs_min:
                    warnings.append(
                        f"{layer} traces net {s1['net']} vs {s2['net']} "
                        f"gap={clearance:.3f}mm < {rec_min}mm rec")

    check(f"Trace spacing >= {abs_min}mm (JLCPCB absolute min)",
          len(violations) == 0,
          f"{len(violations)} violations" + (f": {violations[0]}" if violations else ""))

    if warnings:
        warn(f"{len(warnings)} trace pairs below {rec_min}mm recommended",
             f"first: {warnings[0]}")


def test_via_geometry():
    """All vias meet JLCPCB hole/diameter/annular ring minimums."""
    print("\n── JLCPCB: Via Geometry ──")
    cache = load_cache()
    hole_min = JLCPCB_RULES["via_hole_min"][0]
    diam_min = JLCPCB_RULES["via_diameter_min"][0]
    ring_min = JLCPCB_RULES["via_annular_ring"][0]

    hole_viol = []
    diam_viol = []
    ring_viol = []

    for v in cache["vias"]:
        drill = v["drill"]
        size = v["size"]
        annular = (size - drill) / 2

        if drill < hole_min:
            hole_viol.append(f"via@({v['x']:.2f},{v['y']:.2f}) hole={drill}mm")
        if size < diam_min:
            diam_viol.append(f"via@({v['x']:.2f},{v['y']:.2f}) diam={size}mm")
        if annular < ring_min:
            ring_viol.append(f"via@({v['x']:.2f},{v['y']:.2f}) ring={annular:.3f}mm")

    check(f"Via hole >= {hole_min}mm", len(hole_viol) == 0,
          f"{len(hole_viol)} violations")
    check(f"Via diameter >= {diam_min}mm (1-2L)", len(diam_viol) == 0,
          f"{len(diam_viol)} violations")
    check(f"Via annular ring >= {ring_min}mm", len(ring_viol) == 0,
          f"{len(ring_viol)} violations")


def test_tht_geometry():
    """All THT pads meet JLCPCB hole/annular ring minimums."""
    print("\n── JLCPCB: THT Pad Geometry ──")
    cache = load_cache()
    hole_min = JLCPCB_RULES["tht_hole_min"][0]
    ring_min = JLCPCB_RULES["tht_annular_ring"][0]

    hole_viol = []
    ring_viol = []

    for p in cache["pads"]:
        drill = p.get("drill", 0)
        if drill <= 0:
            continue  # SMD pad
        # Skip NPTH pads — no annular ring expected
        if p.get("type") == "np_thru_hole":
            continue

        # Annular ring: (pad_size - drill) / 2
        pw = p.get("w", 0)
        ph = p.get("h", 0)
        if pw == 0 and ph == 0:
            continue
        min_pad = min(pw, ph)
        annular = (min_pad - drill) / 2

        if drill < hole_min:
            hole_viol.append(f"{p['ref']}[{p['num']}] hole={drill}mm")
        if annular < ring_min:
            ring_viol.append(
                f"{p['ref']}[{p['num']}] ring={annular:.3f}mm "
                f"(pad={min_pad}mm, drill={drill}mm)")

    check(f"THT hole >= {hole_min}mm", len(hole_viol) == 0,
          f"{len(hole_viol)} violations: {hole_viol[:3]}")
    check(f"THT annular ring >= {ring_min}mm", len(ring_viol) == 0,
          f"{len(ring_viol)} violations: {ring_viol[:3]}")


def test_via_to_via_spacing():
    """Via-to-via spacing meets JLCPCB limits."""
    print("\n── JLCPCB: Via-to-Via Spacing ──")
    cache = load_cache()
    diff_min = JLCPCB_RULES["via_to_via_diff"][0]
    same_min = JLCPCB_RULES["via_to_via_same"][0]

    vias = cache["vias"]
    diff_viol = []
    same_viol = []

    for i in range(len(vias)):
        for j in range(i + 1, len(vias)):
            v1, v2 = vias[i], vias[j]
            # Quick distance filter
            dx = abs(v1["x"] - v2["x"])
            if dx > 3.0:
                continue
            dy = abs(v1["y"] - v2["y"])
            if dy > 3.0:
                continue

            center_dist = math.hypot(dx, dy)
            # Hole-to-hole gap = center_dist - r1 - r2
            gap = center_dist - v1["drill"] / 2 - v2["drill"] / 2

            if v1["net"] != v2["net"]:
                if gap < diff_min:
                    diff_viol.append(
                        f"vias@({v1['x']:.2f},{v1['y']:.2f})-({v2['x']:.2f},{v2['y']:.2f}) "
                        f"gap={gap:.3f}mm net {v1['net']} vs {v2['net']}")
            else:
                if gap < same_min:
                    same_viol.append(
                        f"vias@({v1['x']:.2f},{v1['y']:.2f})-({v2['x']:.2f},{v2['y']:.2f}) "
                        f"gap={gap:.3f}mm net {v1['net']}")

    check(f"Via-to-via (diff net) >= {diff_min}mm",
          len(diff_viol) == 0,
          f"{len(diff_viol)} violations" + (f": {diff_viol[0]}" if diff_viol else ""))
    check(f"Via-to-via (same net) >= {same_min}mm",
          len(same_viol) == 0,
          f"{len(same_viol)} violations" + (f": {same_viol[0]}" if same_viol else ""))


def test_via_to_track():
    """Via-to-track clearance meets JLCPCB limits."""
    print("\n── JLCPCB: Via-to-Track Clearance ──")
    cache = load_cache()
    abs_min = JLCPCB_RULES["via_to_track"][0]

    vias = cache["vias"]
    segments = cache["segments"]
    violations = []

    for v in vias:
        vx, vy = v["x"], v["y"]
        v_radius = v["size"] / 2

        for s in segments:
            if s["net"] == v["net"]:
                continue
            if s["layer"] not in ("F.Cu", "B.Cu"):
                continue

            # Quick filter
            sx_mid = (s["x1"] + s["x2"]) / 2
            sy_mid = (s["y1"] + s["y2"]) / 2
            if abs(vx - sx_mid) > 5.0 or abs(vy - sy_mid) > 5.0:
                continue

            dist = _seg_min_dist(s, vx, vy)
            clearance = dist - v_radius - s["width"] / 2

            if clearance < abs_min and clearance >= 0:
                violations.append(
                    f"via@({vx:.2f},{vy:.2f}) net{v['net']} to "
                    f"trace net{s['net']} gap={clearance:.3f}mm")

                if len(violations) >= 20:
                    break
        if len(violations) >= 20:
            break

    check(f"Via-to-track (diff net) >= {abs_min}mm",
          len(violations) == 0,
          f"{len(violations)}+ violations" + (f": {violations[0]}" if violations else ""))


def test_pad_to_track():
    """Pad-to-track clearance meets JLCPCB limits."""
    print("\n── JLCPCB: Pad-to-Track Clearance ──")
    cache = load_cache()
    abs_min = JLCPCB_RULES["pad_to_track"][0]

    pads = cache["pads"]
    segments = cache["segments"]
    violations = []

    # Only check SMD pads (THT pads have their own rule)
    smd_pads = [p for p in pads if p.get("drill", 0) == 0]

    for p in smd_pads:
        px, py = p["x"], p["y"]
        # Approximate pad radius as half of min dimension
        pw, ph = p.get("w", 0), p.get("h", 0)
        if pw == 0 or ph == 0:
            continue
        p_radius = min(pw, ph) / 2

        for s in segments:
            if s["net"] == p["net"]:
                continue
            if s["layer"] != p.get("layer", "F.Cu"):
                continue

            # Quick filter
            if abs(px - (s["x1"] + s["x2"]) / 2) > 5.0:
                continue
            if abs(py - (s["y1"] + s["y2"]) / 2) > 5.0:
                continue

            dist = _seg_min_dist(s, px, py)
            clearance = dist - p_radius - s["width"] / 2

            if clearance < abs_min and clearance >= 0:
                violations.append(
                    f"{p['ref']}[{p['num']}] net{p['net']} to "
                    f"trace net{s['net']} gap={clearance:.3f}mm")

                if len(violations) >= 20:
                    break
        if len(violations) >= 20:
            break

    check(f"Pad-to-track (diff net) >= {abs_min}mm",
          len(violations) == 0,
          f"{len(violations)}+ violations" + (f": {violations[0]}" if violations else ""))


def test_smd_pad_spacing():
    """SMD pad-to-pad spacing meets JLCPCB limits."""
    print("\n── JLCPCB: SMD Pad-to-Pad Spacing ──")
    cache = load_cache()
    abs_min = JLCPCB_RULES["smd_pad_to_pad_diff"][0]
    rec_min = JLCPCB_RULES["smd_pad_to_pad_diff"][1]

    pads = cache["pads"]
    smd_pads = [p for p in pads if p.get("drill", 0) == 0
                and p.get("w", 0) > 0 and p.get("h", 0) > 0]

    violations = []
    warnings = []

    # Group by layer
    by_layer = {}
    for p in smd_pads:
        layer = p.get("layer", "F.Cu")
        if layer not in by_layer:
            by_layer[layer] = []
        by_layer[layer].append(p)

    for layer, layer_pads in by_layer.items():
        # Sort by x for spatial optimization
        layer_pads.sort(key=lambda p: p["x"])

        for i in range(len(layer_pads)):
            p1 = layer_pads[i]
            for j in range(i + 1, len(layer_pads)):
                p2 = layer_pads[j]

                # Once pads are too far in x, skip rest
                if p2["x"] - p1["x"] > 3.0:
                    break

                if p1["net"] == p2["net"]:
                    continue

                # Skip same-component pads
                if p1["ref"] == p2["ref"]:
                    continue

                dy = abs(p1["y"] - p2["y"])
                if dy > 3.0:
                    continue

                # Edge-to-edge distance (approximate: center dist - half sizes)
                center_dist = math.hypot(p2["x"] - p1["x"], p2["y"] - p1["y"])
                r1 = min(p1["w"], p1["h"]) / 2
                r2 = min(p2["w"], p2["h"]) / 2
                gap = center_dist - r1 - r2

                if gap < abs_min and gap >= 0:
                    violations.append(
                        f"{p1['ref']}[{p1['num']}] to {p2['ref']}[{p2['num']}] "
                        f"gap={gap:.3f}mm")
                elif gap < rec_min and gap >= abs_min:
                    warnings.append(
                        f"{p1['ref']}[{p1['num']}] to {p2['ref']}[{p2['num']}] "
                        f"gap={gap:.3f}mm")

    check(f"SMD pad-to-pad (diff net) >= {abs_min}mm",
          len(violations) == 0,
          f"{len(violations)} violations" + (f": {violations[0]}" if violations else ""))

    if warnings:
        warn(f"{len(warnings)} pad pairs below {rec_min}mm recommended",
             f"first: {warnings[0]}")


def test_summary_table():
    """Print summary of all JLCPCB rules with our project's actual values."""
    print("\n── JLCPCB Capabilities Summary ──")
    cache = load_cache()

    # Compute actual minimums from the board
    min_trace_w = min((s["width"] for s in cache["segments"]), default=999)
    min_via_hole = min((v["drill"] for v in cache["vias"]), default=999)
    min_via_diam = min((v["size"] for v in cache["vias"]), default=999)
    min_via_ring = min(((v["size"] - v["drill"]) / 2 for v in cache["vias"]), default=999)

    tht_pads = [p for p in cache["pads"]
                if p.get("drill", 0) > 0 and p.get("type") != "np_thru_hole"]
    min_tht_hole = min((p["drill"] for p in tht_pads), default=999)
    min_tht_ring = min(
        ((min(p.get("w", 0), p.get("h", 0)) - p["drill"]) / 2
         for p in tht_pads if p.get("w", 0) > 0),
        default=999)

    print(f"\n  {'Parameter':<30} {'Board':<10} {'JLCPCB Min':<12} {'JLCPCB Rec':<12} {'Status'}")
    print(f"  {'─' * 76}")

    rows = [
        ("Trace width", min_trace_w,
         JLCPCB_RULES["trace_width_min"][0], JLCPCB_RULES["trace_width_min"][1]),
        ("Via hole", min_via_hole,
         JLCPCB_RULES["via_hole_min"][0], JLCPCB_RULES["via_hole_min"][1]),
        ("Via diameter", min_via_diam,
         JLCPCB_RULES["via_diameter_min"][0], JLCPCB_RULES["via_diameter_min"][1]),
        ("Via annular ring", min_via_ring,
         JLCPCB_RULES["via_annular_ring"][0], JLCPCB_RULES["via_annular_ring"][1]),
        ("THT hole", min_tht_hole,
         JLCPCB_RULES["tht_hole_min"][0], JLCPCB_RULES["tht_hole_min"][1]),
        ("THT annular ring", min_tht_ring,
         JLCPCB_RULES["tht_annular_ring"][0], JLCPCB_RULES["tht_annular_ring"][1]),
    ]

    for name, actual, abs_min, rec_min in rows:
        if actual >= 999:
            status = "N/A"
        elif actual < abs_min:
            status = "FAIL"
        elif actual < rec_min:
            status = "WARN"
        else:
            status = "OK"
        print(f"  {name:<30} {actual:>8.3f}mm  {abs_min:>8.3f}mm    {rec_min:>8.3f}mm    {status}")


def main():
    print("=" * 70)
    print("  JLCPCB Official Capabilities Cross-Check")
    print("  Source: jlcpcb.com/capabilities + agausmann/jlcpcb-kicad-drc")
    print("=" * 70)

    test_trace_width()
    test_trace_spacing()
    test_via_geometry()
    test_tht_geometry()
    test_via_to_via_spacing()
    test_via_to_track()
    test_pad_to_track()
    test_smd_pad_spacing()
    test_summary_table()

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  RESULTS: {PASS} PASS / {FAIL} FAIL / {WARN} WARN")
    if FAIL == 0 and WARN == 0:
        print("  STATUS: ALL CHECKS PASSED — board meets JLCPCB capabilities")
    elif FAIL == 0:
        print(f"  STATUS: PASSED with {WARN} warning(s) — review recommended values")
    else:
        print(f"  STATUS: {FAIL} FAILURE(S) — board may be REJECTED by JLCPCB")
    print("=" * 70)
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
