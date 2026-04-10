#!/usr/bin/env python3
"""Trace-through-pad overlap check — detect copper traces physically
crossing pads with a different (or no) net.

This is the fabrication-level equivalent of the DRC "shorting_items"
check, but it catches cases where the PCB parser sees a pad with an
empty net assignment (net == 0) that a netted trace physically runs
through. On the manufactured board, the pad metal merges with the
trace net, creating a real short.

Rules:
  - Same-net overlap (trace.net == pad.net):       OK (intentional)
  - Unnetted trace (trace.net == 0):                 skip (no fab short)
  - Different-net overlap (both netted, different): FAIL — real short
  - Netted trace crossing unnetted pad (pad.net=0): FAIL — real short
        This is the class that caused the v3.3 regression: commit 775e9fd
        removed _PAD_NETS assignments for U2.3/4, U6.8/9, SW_PWR.4b/4d
        while BTN_SELECT/GND/SD_MISO/BTN_R tracks still routed through
        those pad positions.

Usage:
    python3 scripts/verify_trace_through_pad.py
    Exit code 0 = pass, 1 = failure

Design note:
    Layer-strict matching — a trace on B.Cu is only checked against pads
    on B.Cu. Through-hole pads appear on each copper layer in the cache,
    so they are covered automatically.
"""

import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache  # noqa: E402

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

COPPER_LAYERS = ("F.Cu", "B.Cu")

# Pad sampling resolution (mm) when walking a segment. 0.05mm catches
# every 0402 pad (smallest in the design is 0.30mm).
SAMPLE_STEP_MM = 0.05


def _seg_pad_gap(sx1, sy1, sx2, sy2, sw, px, py, pw, ph):
    """Signed gap between a segment (rounded rect) and an axis-aligned
    pad bounding box. Negative = physical overlap."""
    half_w = sw / 2.0
    phw = pw / 2.0
    phh = ph / 2.0

    ln = math.hypot(sx2 - sx1, sy2 - sy1)
    if ln < 1e-6:
        # Zero-length segment — sample once at start
        dx = max(0.0, abs(sx1 - px) - phw)
        dy = max(0.0, abs(sy1 - py) - phh)
        return math.hypot(dx, dy) - half_w

    steps = max(2, int(ln / SAMPLE_STEP_MM))
    min_gap = float("inf")
    for i in range(steps + 1):
        t = i / steps
        x = sx1 + t * (sx2 - sx1)
        y = sy1 + t * (sy2 - sy1)
        dx = max(0.0, abs(x - px) - phw)
        dy = max(0.0, abs(y - py) - phh)
        gap = math.hypot(dx, dy) - half_w
        if gap < min_gap:
            min_gap = gap
            if min_gap < -0.01:
                # Early exit — clearly overlapping
                break
    return min_gap


def _pad_bbox(pad):
    """Return (x_min, x_max, y_min, y_max) enlarged by a small margin
    so segments that just graze the pad are caught by the broad phase."""
    half_w = pad["w"] / 2.0 + 0.5
    half_h = pad["h"] / 2.0 + 0.5
    return (
        pad["x"] - half_w, pad["x"] + half_w,
        pad["y"] - half_h, pad["y"] + half_h,
    )


def _seg_bbox(seg):
    hw = seg["width"] / 2.0 + 0.1
    return (
        min(seg["x1"], seg["x2"]) - hw,
        max(seg["x1"], seg["x2"]) + hw,
        min(seg["y1"], seg["y2"]) - hw,
        max(seg["y1"], seg["y2"]) + hw,
    )


def _bbox_overlap(a, b):
    return not (a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2])


def find_overlaps(cache):
    """Return list of (pad, segment, kind) for all different-net or
    trace-through-unnetted-pad overlaps.

    kind: "diff_net"  — both netted, different nets (DRC finds this too)
          "unnetted"  — pad unnetted, trace netted (the v3.3 regression)
    """
    overlaps = []

    # Group pads by layer for O(pads_on_layer * segs_on_layer) pass
    pads_by_layer = {lay: [] for lay in COPPER_LAYERS}
    for p in cache["pads"]:
        if p["layer"] in pads_by_layer:
            pads_by_layer[p["layer"]].append(p)

    segs_by_layer = {lay: [] for lay in COPPER_LAYERS}
    for s in cache["segments"]:
        if s["layer"] in segs_by_layer:
            segs_by_layer[s["layer"]].append(s)

    for layer in COPPER_LAYERS:
        pads = pads_by_layer[layer]
        segs = segs_by_layer[layer]

        # Precompute pad bboxes
        pad_boxes = [(_pad_bbox(p), p) for p in pads]

        for s in segs:
            # Unnetted traces can't create a fab short (they're just
            # isolated copper). DRC already flags these as dangling.
            if s["net"] == 0:
                continue

            sb = _seg_bbox(s)

            for pb, p in pad_boxes:
                # Same-net overlap is intentional (trace into pad)
                if p["net"] == s["net"]:
                    continue

                # Broad-phase bbox reject
                if not _bbox_overlap(sb, pb):
                    continue

                # Narrow-phase geometric gap
                gap = _seg_pad_gap(
                    s["x1"], s["y1"], s["x2"], s["y2"], s["width"],
                    p["x"], p["y"], p["w"], p["h"],
                )
                if gap >= 0:
                    continue

                kind = "unnetted" if p["net"] == 0 else "diff_net"
                overlaps.append((p, s, kind, gap))

    return overlaps


def main():
    cache = load_cache(PCB_FILE)
    net_map = {n["id"]: n["name"] for n in cache["nets"]}

    print()
    print("=" * 60)
    print("Trace-through-pad overlap check")
    print("=" * 60)
    print()

    overlaps = find_overlaps(cache)

    seg_count = sum(
        1 for s in cache["segments"] if s["layer"] in COPPER_LAYERS
    )
    pad_count = sum(
        1 for p in cache["pads"] if p["layer"] in COPPER_LAYERS
    )
    print(f"  Segments checked (F.Cu+B.Cu): {seg_count}")
    print(f"  Pads checked (F.Cu+B.Cu):     {pad_count}")
    print()

    # De-duplicate per (pad_ref, pad_num, seg_net) — a single pad may
    # be crossed by several segments of the same net.
    unique = {}
    for p, s, kind, gap in overlaps:
        key = (p.get("ref"), p.get("num"), p["layer"], s["net"])
        prev = unique.get(key)
        if prev is None or gap < prev[3]:
            unique[key] = (p, s, kind, gap)

    diff_net = [v for v in unique.values() if v[2] == "diff_net"]
    unnetted = [v for v in unique.values() if v[2] == "unnetted"]

    if not overlaps:
        print("  PASS  No trace-through-pad overlaps on any copper layer")
        print()
        print("=" * 60)
        print("Results: 1 passed, 0 failed")
        print("=" * 60)
        return 0

    if diff_net:
        print(
            f"  FAIL  {len(diff_net)} different-net trace-through-pad "
            f"overlap(s) — REAL SHORT on fabricated board:"
        )
        for p, s, _, gap in diff_net:
            snet = net_map.get(s["net"], f"#{s['net']}")
            pnet = net_map.get(p["net"], f"#{p['net']}")
            print(
                f"        {p.get('ref')}.{p.get('num')} [{pnet}] on "
                f"{p['layer']} crossed by [{snet}] track "
                f"({s['x1']:.2f},{s['y1']:.2f})->"
                f"({s['x2']:.2f},{s['y2']:.2f}) "
                f"w={s['width']}mm gap={gap:+.3f}mm"
            )
        print()

    if unnetted:
        print(
            f"  FAIL  {len(unnetted)} netted-trace through unnetted-pad "
            f"overlap(s) — REAL SHORT on fabricated board:"
        )
        print(
            "        (pad has net==0 in PCB, but a netted trace "
            "physically runs through it — the pad metal will merge "
            "with the trace net at fabrication)"
        )
        for p, s, _, gap in unnetted:
            snet = net_map.get(s["net"], f"#{s['net']}")
            print(
                f"        {p.get('ref')}.{p.get('num')} [<no net>] on "
                f"{p['layer']} crossed by [{snet}] track "
                f"({s['x1']:.2f},{s['y1']:.2f})->"
                f"({s['x2']:.2f},{s['y2']:.2f}) "
                f"w={s['width']}mm gap={gap:+.3f}mm"
            )
        print()
        print(
            "        Root cause pattern: missing entry in "
            "scripts/generate_pcb/routing.py::_PAD_NETS, or "
            "_inject_pad_net() not covering a rotated/mirrored footprint."
        )
        print(
            "        Historical reference: commit 775e9fd "
            "(2026-04-09 23:50) removed assignments for U2.3/4, "
            "U6.8/9, SW_PWR.4b/4d thinking they were NC pads — those "
            "assignments were the same-net trick keeping DRC clean."
        )
        print()

    failed = len(diff_net) + len(unnetted)
    print("=" * 60)
    print(f"Results: 0 passed, {failed} failed")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())
