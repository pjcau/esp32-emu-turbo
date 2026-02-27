"""Analytical pad distance checker for KiCad PCB files.

Parses esp32-emu-turbo.kicad_pcb, extracts ALL pads and vias with their
absolute positions/sizes/layers, then computes edge-to-edge distances
for every same-layer pair.  Reports all pairs with gap < THRESHOLD.

Usage:
    python3 scripts/analyze_pad_distances.py
    python3 scripts/analyze_pad_distances.py --threshold 0.20
"""

import math
import re
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

PCB_FILE = Path(__file__).parent.parent / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"

# ── Data classes ─────────────────────────────────────────────────

@dataclass
class Pad:
    ref: str          # footprint reference (e.g. "U1")
    num: str          # pad number string (e.g. "1", "A4", "EP")
    layer: str        # "F.Cu" or "B.Cu" (copper layer only)
    x: float          # absolute board X
    y: float          # absolute board Y
    w: float          # pad width (after rotation)
    h: float          # pad height (after rotation)
    shape: str        # "rect", "circle", "oval"
    fp_x: float = 0   # footprint center X
    fp_y: float = 0   # footprint center Y
    net: int = 0      # net number (0 = unconnected)

@dataclass
class Via:
    x: float
    y: float
    size: float       # annular ring outer diameter
    drill: float      # drill diameter
    annular: float    # (size - drill) / 2
    net: int = 0      # net number

@dataclass
class Segment:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    layer: str        # "F.Cu" or "B.Cu"
    net: int = 0


# ── Parser ───────────────────────────────────────────────────────

def _re_float(s: str, key: str) -> Optional[float]:
    m = re.search(rf'\({key}\s+([-\d.]+)\)', s)
    return float(m.group(1)) if m else None

def _re_pair(s: str, key: str):
    m = re.search(rf'\({key}\s+([-\d.]+)\s+([-\d.]+)\)', s)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None

def _rotate(x, y, angle_deg):
    rad = math.radians(angle_deg)
    c, s = math.cos(rad), math.sin(rad)
    return (x * c - y * s, x * s + y * c)


def parse_pcb(path: Path):
    """Parse .kicad_pcb and return (pads, vias, segments) via cache."""
    from pcb_cache import load_cache
    cache = load_cache(path)

    pads: list[Pad] = [
        Pad(ref=p["ref"], num=p["num"], layer=p["layer"],
            x=p["x"], y=p["y"], w=p["w"], h=p["h"], shape=p["shape"],
            fp_x=p["fp_x"], fp_y=p["fp_y"], net=p["net"])
        for p in cache["pads"]
    ]

    vias: list[Via] = [
        Via(x=v["x"], y=v["y"], size=v["size"], drill=v["drill"],
            annular=(v["size"] - v["drill"]) / 2, net=v["net"])
        for v in cache["vias"]
    ]

    # Only F.Cu and B.Cu segments (matches original behavior)
    segments: list[Segment] = [
        Segment(x1=s["x1"], y1=s["y1"], x2=s["x2"], y2=s["y2"],
                width=s["width"], layer=s["layer"], net=s["net"])
        for s in cache["segments"]
        if s["layer"] in ("F.Cu", "B.Cu")
    ]

    return pads, vias, segments


# ── Distance calculations ─────────────────────────────────────────

def pad_bbox(p: Pad):
    """Return (x_min, y_min, x_max, y_max) for a pad's copper extents."""
    hw = p.w / 2
    hh = p.h / 2
    return (p.x - hw, p.y - hh, p.x + hw, p.y + hh)


def pad_edge_distance(a: Pad, b: Pad) -> float:
    """Compute edge-to-edge (gap) distance between two rectangular pads.

    Returns negative value if pads overlap (negative gap = overlap amount).
    """
    # For circular pads, treat as square inscribed = use radius
    # For oval/rect we use bounding box (conservative)
    ax1, ay1, ax2, ay2 = pad_bbox(a)
    bx1, by1, bx2, by2 = pad_bbox(b)

    # Overlap in X and Y
    dx = max(0, max(ax1, bx1) - min(ax2, bx2))
    dy = max(0, max(ay1, by1) - min(ay2, by2))

    if dx == 0 and dy == 0:
        # Overlapping or touching
        # Return overlap amount as negative
        ox = min(ax2, bx2) - max(ax1, bx1)
        oy = min(ay2, by2) - max(ay1, by1)
        return -min(ox, oy)

    if dx == 0:
        return dy  # vertically separated, no X gap
    if dy == 0:
        return dx  # horizontally separated, no Y gap

    # Diagonally separated — nearest corner distance
    return math.sqrt(dx*dx + dy*dy)


def via_to_pad_distance(v: Via, p: Pad) -> float:
    """Edge-to-edge distance from via annular ring to pad."""
    ax1, ay1, ax2, ay2 = pad_bbox(p)
    # Via outer radius
    vr = v.size / 2
    # Distance from via center to nearest point on pad bbox
    cx = max(ax1, min(v.x, ax2))
    cy = max(ay1, min(v.y, ay2))
    dist_center = math.sqrt((v.x - cx)**2 + (v.y - cy)**2)
    return dist_center - vr


def segment_to_pad_distance(s: Segment, p: Pad) -> float:
    """Approximate edge-to-edge distance from segment to pad."""
    ax1, ay1, ax2, ay2 = pad_bbox(p)
    sw = s.width / 2

    # Nearest point on segment to pad center
    def point_to_seg(px, py):
        dx = s.x2 - s.x1
        dy = s.y2 - s.y1
        if dx == 0 and dy == 0:
            return math.sqrt((px - s.x1)**2 + (py - s.y1)**2)
        t = ((px - s.x1) * dx + (py - s.y1) * dy) / (dx*dx + dy*dy)
        t = max(0, min(1, t))
        nx = s.x1 + t * dx
        ny = s.y1 + t * dy
        return math.sqrt((px - nx)**2 + (py - ny)**2)

    # Check distance from segment axis to each pad corner
    corners = [(ax1, ay1), (ax2, ay1), (ax1, ay2), (ax2, ay2),
               (p.x, p.y)]
    min_d = min(point_to_seg(cx, cy) for cx, cy in corners)
    return min_d - sw


def segment_to_segment_distance(a: Segment, b: Segment) -> float:
    """Minimum edge-to-edge distance between two trace segments."""
    # Axis-aligned only (Manhattan routing) — much simpler
    # Check if bboxes overlap with half-widths included
    aw = a.width / 2
    bw = b.width / 2

    # Segment bboxes (center-line)
    ax1, ax2 = min(a.x1, a.x2), max(a.x1, a.x2)
    ay1, ay2 = min(a.y1, a.y2), max(a.y1, a.y2)
    bx1, bx2 = min(b.x1, b.x2), max(b.x1, b.x2)
    by1, by2 = min(b.y1, b.y2), max(b.y1, b.y2)

    # Expand by half-widths
    ax1 -= aw; ax2 += aw; ay1 -= aw; ay2 += aw
    bx1 -= bw; bx2 += bw; by1 -= bw; by2 += bw

    dx = max(0, max(ax1, bx1) - min(ax2, bx2))
    dy = max(0, max(ay1, by1) - min(ay2, by2))

    if dx == 0 and dy == 0:
        return 0.0
    return math.sqrt(dx*dx + dy*dy)


# ── Main analysis ─────────────────────────────────────────────────

def analyze(threshold: float = 0.15, verbose: bool = True):
    if verbose:
        print(f"Parsing: {PCB_FILE}")
    pads, vias, segments = parse_pcb(PCB_FILE)

    if verbose:
        print(f"Found: {len(pads)} pad copper entries, {len(vias)} vias, "
              f"{len(segments)} trace segments\n")

    violations = []

    # ── Pad-to-pad ───────────────────────────────────────────────
    # Group pads by layer for efficiency
    from collections import defaultdict
    by_layer: dict[str, list[Pad]] = defaultdict(list)
    for p in pads:
        by_layer[p.layer].append(p)

    checked_pairs = 0
    for layer, layer_pads in by_layer.items():
        n = len(layer_pads)
        for i in range(n):
            a = layer_pads[i]
            for j in range(i + 1, n):
                b = layer_pads[j]

                # Skip same-net pads (e.g. power rail pads that are intentionally
                # adjacent, or multi-pin components with bridged nets)
                if a.net != 0 and b.net != 0 and a.net == b.net:
                    continue

                # Fast reject: bounding box pre-filter
                if abs(a.x - b.x) > (a.w + b.w) / 2 + threshold + 1.0:
                    continue
                if abs(a.y - b.y) > (a.h + b.h) / 2 + threshold + 1.0:
                    continue

                dist = pad_edge_distance(a, b)
                checked_pairs += 1

                if dist < threshold:
                    violations.append({
                        "type": "pad-pad",
                        "layer": layer,
                        "dist": dist,
                        "a": f"{a.ref}[{a.num}]",
                        "b": f"{b.ref}[{b.num}]",
                        "a_pos": (round(a.x, 4), round(a.y, 4)),
                        "b_pos": (round(b.x, 4), round(b.y, 4)),
                        "a_size": (round(a.w, 4), round(a.h, 4)),
                        "b_size": (round(b.w, 4), round(b.h, 4)),
                        "a_shape": a.shape,
                        "b_shape": b.shape,
                    })

    if verbose:
        print(f"Pad-to-pad pairs checked: {checked_pairs}")

    # ── Via-to-pad ───────────────────────────────────────────────
    # Vias appear on both F.Cu and B.Cu.
    # Skip same-net pairs (when net info available) and skip vias that land
    # exactly at a pad center (connected via-in-pad, intentional).
    via_violations = 0
    for v in vias:
        for layer in ("F.Cu", "B.Cu"):
            for p in by_layer[layer]:
                # Skip same-net (valid connection)
                if v.net != 0 and p.net != 0 and v.net == p.net:
                    continue
                # Skip via that sits exactly at pad center (intentional connection)
                ax1, ay1, ax2, ay2 = pad_bbox(p)
                if ax1 <= v.x <= ax2 and ay1 <= v.y <= ay2:
                    continue
                if abs(v.x - p.x) > (p.w / 2 + v.size / 2 + threshold + 1.0):
                    continue
                if abs(v.y - p.y) > (p.h / 2 + v.size / 2 + threshold + 1.0):
                    continue
                dist = via_to_pad_distance(v, p)
                if dist < threshold:
                    violations.append({
                        "type": "via-pad",
                        "layer": layer,
                        "dist": dist,
                        "a": f"VIA@({v.x:.3f},{v.y:.3f}) size={v.size}",
                        "b": f"{p.ref}[{p.num}]",
                        "a_pos": (round(v.x, 4), round(v.y, 4)),
                        "b_pos": (round(p.x, 4), round(p.y, 4)),
                        "a_size": (round(v.size, 4), round(v.size, 4)),
                        "b_size": (round(p.w, 4), round(p.h, 4)),
                        "a_shape": "circle",
                        "b_shape": p.shape,
                    })
                    via_violations += 1

    if verbose:
        print(f"Via-to-pad violations found: {via_violations}")

    # ── Trace-to-pad ─────────────────────────────────────────────
    # Skip connected pairs: a trace endpoint that terminates at a pad center
    # (within a tight tolerance) is a valid connection, not a spacing violation.
    # Also skip same-net pairs when net info is available on both objects.
    def _endpoint_on_pad(s: "Segment", p: "Pad") -> bool:
        """Return True if either trace endpoint falls inside the pad bounding box."""
        ax1, ay1, ax2, ay2 = pad_bbox(p)
        # Expand pad bbox by half trace-width for endpoint-overlap check
        hw = s.width / 2
        ax1 -= hw; ax2 += hw; ay1 -= hw; ay2 += hw
        for ex, ey in [(s.x1, s.y1), (s.x2, s.y2)]:
            if ax1 <= ex <= ax2 and ay1 <= ey <= ay2:
                return True
        return False

    trace_pad_violations = 0
    for s in segments:
        for p in by_layer[s.layer]:
            # Skip same-net (valid connection, not a spacing violation)
            if s.net != 0 and p.net != 0 and s.net == p.net:
                continue
            # Skip if a trace endpoint terminates at this pad (connected trace)
            if _endpoint_on_pad(s, p):
                continue
            # Fast reject
            sx1, sx2 = min(s.x1, s.x2), max(s.x1, s.x2)
            sy1, sy2 = min(s.y1, s.y2), max(s.y1, s.y2)
            if p.x < sx1 - p.w/2 - s.width/2 - threshold - 1.0:
                continue
            if p.x > sx2 + p.w/2 + s.width/2 + threshold + 1.0:
                continue
            if p.y < sy1 - p.h/2 - s.width/2 - threshold - 1.0:
                continue
            if p.y > sy2 + p.h/2 + s.width/2 + threshold + 1.0:
                continue
            dist = segment_to_pad_distance(s, p)
            if dist < threshold:
                violations.append({
                    "type": "trace-pad",
                    "layer": s.layer,
                    "dist": dist,
                    "a": f"TRACE({s.x1:.3f},{s.y1:.3f})->({s.x2:.3f},{s.y2:.3f}) w={s.width} net={s.net}",
                    "b": f"{p.ref}[{p.num}]",
                    "a_pos": (round((s.x1+s.x2)/2, 4), round((s.y1+s.y2)/2, 4)),
                    "b_pos": (round(p.x, 4), round(p.y, 4)),
                    "a_size": (round(s.width, 4), round(s.width, 4)),
                    "b_size": (round(p.w, 4), round(p.h, 4)),
                    "a_shape": "segment",
                    "b_shape": p.shape,
                })
                trace_pad_violations += 1

    if verbose:
        print(f"Trace-to-pad violations found: {trace_pad_violations}")

    # ── Trace-to-trace ───────────────────────────────────────────
    trace_trace_violations = 0
    by_seg_layer: dict[str, list[Segment]] = defaultdict(list)
    for s in segments:
        by_seg_layer[s.layer].append(s)

    for layer, segs in by_seg_layer.items():
        n = len(segs)
        for i in range(n):
            a = segs[i]
            for j in range(i + 1, n):
                b = segs[j]
                # Same net — skip (not a spacing violation)
                if a.net != 0 and a.net == b.net:
                    continue
                dist = segment_to_segment_distance(a, b)
                if dist < threshold:
                    violations.append({
                        "type": "trace-trace",
                        "layer": layer,
                        "dist": dist,
                        "a": f"TRACE({a.x1:.3f},{a.y1:.3f})->({a.x2:.3f},{a.y2:.3f}) w={a.width} net={a.net}",
                        "b": f"TRACE({b.x1:.3f},{b.y1:.3f})->({b.x2:.3f},{b.y2:.3f}) w={b.width} net={b.net}",
                        "a_pos": (round((a.x1+a.x2)/2, 4), round((a.y1+a.y2)/2, 4)),
                        "b_pos": (round((b.x1+b.x2)/2, 4), round((b.y1+b.y2)/2, 4)),
                        "a_size": (round(a.width, 4), round(a.width, 4)),
                        "b_size": (round(b.width, 4), round(b.width, 4)),
                        "a_shape": "segment",
                        "b_shape": "segment",
                    })
                    trace_trace_violations += 1

    if verbose:
        print(f"Trace-to-trace violations found: {trace_trace_violations}\n")

    # Sort by distance (worst first)
    violations.sort(key=lambda v: v["dist"])

    return violations, pads, vias, segments


def print_report(violations, threshold: float = 0.15):
    DANGER = 0.10  # JLCPCB danger threshold

    danger = [v for v in violations if v["dist"] < DANGER]
    warning = [v for v in violations if DANGER <= v["dist"] < threshold]

    print("=" * 80)
    print(f"PAD DISTANCE ANALYSIS REPORT  (threshold={threshold}mm)")
    print("=" * 80)
    print(f"DANGER  (<{DANGER}mm):  {len(danger)}")
    print(f"WARNING (<{threshold}mm): {len(warning)}")
    print()

    if danger:
        print(f"{'─'*80}")
        print(f"DANGER VIOLATIONS ({len(danger)} pairs, gap < {DANGER}mm):")
        print(f"{'─'*80}")
        by_type: dict[str, list] = {}
        for v in danger:
            by_type.setdefault(v["type"], []).append(v)

        for vtype, items in by_type.items():
            print(f"\n  [{vtype.upper()}] — {len(items)} violations")
            for v in items:
                gap = v["dist"]
                overlap = " *** OVERLAP ***" if gap < 0 else ""
                print(f"    gap={gap:+.4f}mm{overlap}")
                print(f"      A: {v['a']}")
                print(f"         pos={v['a_pos']}  size={v['a_size']}  shape={v['a_shape']}")
                print(f"      B: {v['b']}")
                print(f"         pos={v['b_pos']}  size={v['b_size']}  shape={v['b_shape']}")
                print(f"      layer={v['layer']}")

    if warning:
        print(f"\n{'─'*80}")
        print(f"WARNING VIOLATIONS ({len(warning)} pairs, {DANGER}mm <= gap < {threshold}mm):")
        print(f"{'─'*80}")
        for v in warning:
            print(f"    gap={v['dist']:+.4f}mm  [{v['type']}]  layer={v['layer']}")
            print(f"      A: {v['a']}  pos={v['a_pos']}")
            print(f"      B: {v['b']}  pos={v['b_pos']}")

    print()
    if len(danger) == 0:
        print("RESULT: PASS — No danger violations found.")
    else:
        print(f"RESULT: FAIL — {len(danger)} danger violations must be fixed.")

    # ── Summary by component ─────────────────────────────────────
    if danger:
        print()
        print("COMPONENT SUMMARY (danger violations):")
        comp_count: dict[str, int] = {}
        for v in danger:
            for key in ("a", "b"):
                # Extract component ref
                name = v[key].split("[")[0].split("@")[0]
                comp_count[name] = comp_count.get(name, 0) + 1
        for comp, cnt in sorted(comp_count.items(), key=lambda x: -x[1]):
            print(f"  {comp}: {cnt} violation(s)")

    return len(danger)


def main():
    parser = argparse.ArgumentParser(description="Analyze PCB pad distances")
    parser.add_argument("--threshold", type=float, default=0.15,
                        help="Report pairs with gap < threshold (default: 0.15mm)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress progress messages")
    args = parser.parse_args()

    violations, pads, vias, segments = analyze(
        threshold=args.threshold, verbose=not args.quiet
    )
    n_danger = print_report(violations, threshold=args.threshold)
    sys.exit(1 if n_danger > 0 else 0)


if __name__ == "__main__":
    main()
