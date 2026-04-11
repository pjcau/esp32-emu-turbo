#!/usr/bin/env python3
"""Trace-crossings check — detect pairs of copper segments on the same
layer belonging to different nets whose copper regions physically touch.

This is the fabrication-level equivalent of the KiCad DRC "tracks_crossing"
rule, but runs against the parsed PCB cache so it can be part of the
Layer 1 gate suite (no live KiCad needed).

Why this gate exists:
  R9-CRIT-1 (2026-04-11) — the R7/R8 BTN_START bridge added a 10.5mm
  horizontal on F.Cu at y≈43 that crossed LCD_CS / LCD_DC / LCD_WR
  (three different nets on the same layer). `verify_trace_through_pad.py`
  only checks trace-vs-pad; `verify_net_connectivity.py` only detects
  under-connectivity (net fragmented). Nothing caught the trace-vs-trace
  short class. This script closes that gap.

Physics model:
  Each copper segment is a capsule (two half-disks + rectangle) of radius
  width/2 along its centerline. Two segments on the same layer overlap
  iff the closest distance between their centerlines is smaller than
  (width1 + width2) / 2. Different-net overlap == fab short.

Complexity:
  O(n log n) via bounding-box sweep on the x-axis. With 560 segments in
  this project it runs in < 20 ms.

Usage:
    python3 scripts/verify_trace_crossings.py
    Exit code 0 = pass, 1 = failure
"""

import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache  # noqa: E402

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

COPPER_LAYERS = ("F.Cu", "B.Cu", "In1.Cu", "In2.Cu")

# Touch tolerance — if centerlines are closer than (w1+w2)/2 - EPS, treat
# as overlap. Small negative EPS lets us flag "barely-touching" cases too
# since manufacturing tolerance will merge them.
EPS_MM = 1e-4


def _seg_seg_min_dist(ax1, ay1, ax2, ay2, bx1, by1, bx2, by2):
    """Minimum Euclidean distance between two line segments in 2D.

    Standard closest-point-between-segments algorithm. Handles parallel
    and degenerate (point) cases.
    """
    dax = ax2 - ax1
    day = ay2 - ay1
    dbx = bx2 - bx1
    dby = by2 - by1
    rx = ax1 - bx1
    ry = ay1 - by1

    a = dax * dax + day * day  # |A|^2
    e = dbx * dbx + dby * dby  # |B|^2
    f = dbx * rx + dby * ry    # B . r

    # Both segments degenerate to points
    if a <= 1e-12 and e <= 1e-12:
        return math.hypot(rx, ry)

    if a <= 1e-12:
        s = 0.0
        t = max(0.0, min(1.0, f / e))
    else:
        c = dax * rx + day * ry  # A . r
        if e <= 1e-12:
            t = 0.0
            s = max(0.0, min(1.0, -c / a))
        else:
            # Non-degenerate: solve the 2x2 system
            b = dax * dbx + day * dby  # A . B
            denom = a * e - b * b
            if denom != 0.0:
                s = max(0.0, min(1.0, (b * f - c * e) / denom))
            else:
                # Parallel segments
                s = 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0
                s = max(0.0, min(1.0, -c / a))
            elif t > 1.0:
                t = 1.0
                s = max(0.0, min(1.0, (b - c) / a))

    cpx = ax1 + dax * s - (bx1 + dbx * t)
    cpy = ay1 + day * s - (by1 + dby * t)
    return math.hypot(cpx, cpy)


def _seg_bbox(seg):
    """Bounding box enlarged by the segment half-width."""
    hw = seg["width"] / 2.0
    return (
        min(seg["x1"], seg["x2"]) - hw,
        max(seg["x1"], seg["x2"]) + hw,
        min(seg["y1"], seg["y2"]) - hw,
        max(seg["y1"], seg["y2"]) + hw,
    )


def find_crossings(cache):
    """Return list of (seg_a, seg_b, min_dist, needed) for every pair of
    same-layer, different-net segments whose capsules overlap."""
    crossings = []

    segs_by_layer = {lay: [] for lay in COPPER_LAYERS}
    for s in cache["segments"]:
        if s["layer"] in segs_by_layer:
            segs_by_layer[s["layer"]].append(s)

    for layer, segs in segs_by_layer.items():
        n = len(segs)
        if n < 2:
            continue

        # Sweep on x-axis: sort by x_min of bbox, then sweep active set
        annotated = [(s, _seg_bbox(s)) for s in segs]
        annotated.sort(key=lambda item: item[1][0])

        active = []  # list of (x_max, item)
        for s, bb in annotated:
            xmin, xmax, ymin, ymax = bb
            # Drop items whose x_max < current x_min
            active = [(xm, it) for xm, it in active if xm >= xmin]

            for _, (o, obb) in active:
                # Skip same net (including both == 0 which is "no net")
                if o["net"] == s["net"]:
                    continue
                # y-axis bbox reject
                _, _, oymin, oymax = obb
                if oymax < ymin or ymax < oymin:
                    continue

                needed = (s["width"] + o["width"]) / 2.0
                dist = _seg_seg_min_dist(
                    s["x1"], s["y1"], s["x2"], s["y2"],
                    o["x1"], o["y1"], o["x2"], o["y2"],
                )
                if dist < needed - EPS_MM:
                    crossings.append((o, s, dist, needed))

            active.append((xmax, (s, bb)))

    return crossings


def main():
    cache = load_cache(PCB_FILE)
    net_map = {n["id"]: n["name"] for n in cache["nets"]}

    print()
    print("=" * 60)
    print("Trace-crossings check (same-layer, different-net copper)")
    print("=" * 60)
    print()

    seg_total = sum(
        1 for s in cache["segments"] if s["layer"] in COPPER_LAYERS
    )
    print(f"  Segments checked: {seg_total} on {COPPER_LAYERS}")

    crossings = find_crossings(cache)

    if not crossings:
        print("  PASS  No trace-crossings on any copper layer")
        print()
        print("=" * 60)
        print("Results: 1 passed, 0 failed")
        print("=" * 60)
        return 0

    # De-duplicate by (net_a, net_b, layer) — one line per net pair per layer.
    unique = {}
    for a, b, dist, needed in crossings:
        na, nb = a["net"], b["net"]
        key = (min(na, nb), max(na, nb), a["layer"])
        prev = unique.get(key)
        if prev is None or dist < prev[2]:
            unique[key] = (a, b, dist, needed)

    print(
        f"  FAIL  {len(unique)} different-net trace-crossing pair(s) — "
        "REAL SHORT on fabricated board:"
    )
    print()
    for a, b, dist, needed in sorted(
        unique.values(), key=lambda v: (v[0]["layer"], v[2])
    ):
        na = net_map.get(a["net"], f"#{a['net']}")
        nb = net_map.get(b["net"], f"#{b['net']}")
        gap = dist - needed
        print(
            f"    {a['layer']}: [{na}] "
            f"({a['x1']:.2f},{a['y1']:.2f})->({a['x2']:.2f},{a['y2']:.2f}) "
            f"w={a['width']}mm"
        )
        print(
            f"           × [{nb}] "
            f"({b['x1']:.2f},{b['y1']:.2f})->({b['x2']:.2f},{b['y2']:.2f}) "
            f"w={b['width']}mm"
        )
        print(
            f"           dist={dist:.3f}mm need={needed:.3f}mm "
            f"gap={gap:+.3f}mm"
        )
        print()

    print(
        "    Root cause pattern: routing.py added a segment whose bounding "
        "corridor was already occupied by a different-net segment on the "
        "same copper layer. Either reroute to the opposite layer (F.Cu↔B.Cu) "
        "or avoid the corridor."
    )
    print()
    print("=" * 60)
    print(f"Results: 0 passed, {len(unique)} failed")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
