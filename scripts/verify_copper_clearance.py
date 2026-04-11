#!/usr/bin/env python3
"""Copper-to-copper clearance gate — catches what DRC misses at ≥ 0.09mm.

Motivation (R13, 2026-04-11):
  JLCDFM flagged a 0.05mm "Trace spacing" Danger on Bottom copper that
  our verify_dfm_v2.py (115/115 PASS) and KiCad native DRC (0 errors
  at 0.09mm rule) did not detect. Multi-strategy investigation proved
  the actual physical gap was 0.100-0.145mm — above the 0.09mm KiCad
  rule but BELOW JLCPCB's preferred 0.15mm manufacturing minimum.
  JLCDFM likely computes mask-aperture-to-mask-aperture distance
  (subtracting ~2×0.05mm mask margin from the copper gap), which
  pushes 0.10mm copper gap down to 0.00-0.05mm apparent gap.

  The existing DFM pipeline was tuned to JLCPCB's *absolute* minimum
  (0.09mm) which is the physical fab capability; this gate enforces
  the *preferred* minimum (0.15mm) which is the yield-safe target
  and what JLCDFM uses as its Warning/Good threshold.

Strategy:
  1. For each copper layer (F.Cu, B.Cu, In1.Cu, In2.Cu), build a
     Shapely polygon for every feature (trace, pad, via).
  2. Group features by net and merge per-net polygons into a single
     MultiPolygon via unary_union.
  3. Compute pairwise polygon distance between every different-net
     pair (broad-phase pruned by bounding box).
  4. Report any gap < GAP_WARN (0.15mm) as WARN and < GAP_DANGER
     (0.10mm) as FAIL. Exit code 1 if any FAIL.

Why not use KiCad DRC?
  KiCad DRC uses the `clearance` rule in .kicad_dru which is set to
  0.09mm (JLCPCB absolute minimum). Raising it to 0.15mm would
  produce 100+ violations from existing routed areas that are fine
  per JLCPCB absolute spec. This gate keeps the .kicad_dru at 0.09mm
  (so fab-accept checks remain correct) and adds a separate
  yield-safe check at 0.15mm, reporting each violation with net names,
  coordinates, and nearest points for easy fix.

Usage:
    python3 scripts/verify_copper_clearance.py
    python3 scripts/verify_copper_clearance.py --layer B.Cu
    python3 scripts/verify_copper_clearance.py --warn-only
"""

import argparse
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache  # noqa: E402

try:
    from shapely.geometry import Point, LineString, box  # noqa: E402
    from shapely.ops import unary_union, nearest_points  # noqa: E402
except ImportError as e:
    print("ERROR: shapely is required for this check.", file=sys.stderr)
    print("Install with: pip3 install --break-system-packages shapely", file=sys.stderr)
    sys.exit(2)

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

# Thresholds (mm, edge-to-edge)
GAP_DANGER = 0.10   # Below this = FAIL (JLCDFM Danger band)
GAP_WARN = 0.15     # Below this = WARN (JLCPCB preferred minimum, JLCDFM Warning)

# Broad-phase pruning distance (skip pairs whose bboxes are >= this apart)
BROAD_PHASE = 0.5


def seg_to_capsule(seg):
    """Convert a trace segment to a Shapely capsule polygon."""
    line = LineString([(seg["x1"], seg["y1"]), (seg["x2"], seg["y2"])])
    return line.buffer(seg["width"] / 2, resolution=8)


def pad_to_polygon(pad):
    """Convert a pad to a Shapely polygon (rect or oval/circle)."""
    x, y, w, h = pad["x"], pad["y"], pad["w"], pad["h"]
    shape = pad.get("shape", "rect")
    if shape in ("oval", "circle"):
        if abs(w - h) < 0.01:
            return Point(x, y).buffer(w / 2, resolution=16)
        if w > h:
            return LineString(
                [(x - (w - h) / 2, y), (x + (w - h) / 2, y)]
            ).buffer(h / 2, resolution=16)
        return LineString(
            [(x, y - (h - w) / 2), (x, y + (h - w) / 2)]
        ).buffer(w / 2, resolution=16)
    return box(x - w / 2, y - h / 2, x + w / 2, y + h / 2)


def via_to_polygon(via):
    return Point(via["x"], via["y"]).buffer(via["size"] / 2, resolution=16)


def build_layer_features(cache, layer):
    """Build list of (net_id, ref_label, polygon) for all copper features
    on the given layer."""
    features = []
    for s in cache["segments"]:
        if s["layer"] == layer:
            features.append((s["net"], "track", seg_to_capsule(s)))
    for p in cache["pads"]:
        # SMD pads are layer-specific; THT pads appear on all copper layers
        if p.get("type") == "smd" and p["layer"] != layer:
            continue
        ref = f"{p.get('ref', '?')}.{p.get('num', '?')}"
        features.append((p.get("net", 0), ref, pad_to_polygon(p)))
    # Vias span all copper layers
    for v in cache["vias"]:
        features.append((v["net"], "via", via_to_polygon(v)))
    return features


def merge_by_net(features):
    """Merge all features per net into a single Shapely geometry.

    Netted features → merged per net.
    Unnetted features (net_id == 0) → all merged into ONE "<no net>" group
    so self-vs-self comparisons don't show up as 0mm gaps (NPTH mounting
    holes, USB-C shield tabs, etc. are all unnetted copper that the fab
    treats as a single non-conductive group).
    """
    by_net = {}
    nonet_polys = []
    for net_id, label, poly in features:
        if net_id == 0:
            nonet_polys.append(poly)
        else:
            by_net.setdefault(net_id, []).append(poly)

    merged = {}
    for net_id, polys in by_net.items():
        try:
            merged[net_id] = (unary_union(polys), [])
        except Exception:
            continue
    if nonet_polys:
        try:
            merged["<no net>"] = (unary_union(nonet_polys), [])
        except Exception:
            pass
    return merged


def find_gaps(merged, nets, threshold=GAP_WARN):
    """Return list of (gap_mm, net_a, net_b, pt_a, pt_b) for every
    different-net pair with polygon distance < threshold."""
    violations = []
    items = list(merged.items())
    for i in range(len(items)):
        ka, (pa, _) = items[i]
        pa_bounds = pa.bounds
        for j in range(i + 1, len(items)):
            kb, (pb, _) = items[j]
            pb_bounds = pb.bounds
            # Broad-phase reject
            if (pa_bounds[2] + BROAD_PHASE < pb_bounds[0]
                    or pb_bounds[2] + BROAD_PHASE < pa_bounds[0]
                    or pa_bounds[3] + BROAD_PHASE < pb_bounds[1]
                    or pb_bounds[3] + BROAD_PHASE < pa_bounds[1]):
                continue
            try:
                d = pa.distance(pb)
            except Exception:
                continue
            if d < threshold:
                na = nets.get(ka, str(ka)) if isinstance(ka, int) else ka
                nb = nets.get(kb, str(kb)) if isinstance(kb, int) else kb
                # Skip no-net vs no-net (same group, meaningless)
                if na == "<no net>" and nb == "<no net>":
                    continue
                try:
                    pt_a, pt_b = nearest_points(pa, pb)
                    loc = (pt_a.x, pt_a.y, pt_b.x, pt_b.y)
                except Exception:
                    loc = (0, 0, 0, 0)
                violations.append((d, na, nb) + loc)
    return violations


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--layer", default=None,
        help="Check only one layer (default: all 4 copper layers)",
    )
    ap.add_argument(
        "--warn-only", action="store_true",
        help="Exit 0 even if DANGER violations found (advisory mode)",
    )
    ap.add_argument(
        "--quiet", "-q", action="store_true",
        help="Only show totals, not per-violation details",
    )
    args = ap.parse_args()

    cache = load_cache(PCB_FILE)
    nets = {n["id"]: n["name"] for n in cache["nets"]}

    layers = (
        [args.layer] if args.layer
        else ["F.Cu", "B.Cu", "In1.Cu", "In2.Cu"]
    )

    print("=" * 70)
    print("Copper-to-copper clearance check (JLCPCB 4-layer preferred ≥0.15mm)")
    print("=" * 70)

    total_danger = 0
    total_warn = 0

    for layer in layers:
        features = build_layer_features(cache, layer)
        if not features:
            print(f"\n{layer}: no features, skipped")
            continue

        merged = merge_by_net(features)
        violations = find_gaps(merged, nets, threshold=GAP_WARN)
        violations.sort(key=lambda v: v[0])

        danger = [v for v in violations if v[0] < GAP_DANGER]
        warn = [v for v in violations if GAP_DANGER <= v[0] < GAP_WARN]

        total_danger += len(danger)
        total_warn += len(warn)

        status = "PASS" if not danger else "FAIL"
        print(f"\n{layer}: {len(features)} features, {len(merged)} nets")
        print(f"  DANGER (< {GAP_DANGER}mm): {len(danger)}  "
              f"WARN (< {GAP_WARN}mm): {len(warn)}  [{status}]")

        if not args.quiet:
            if danger:
                print(f"\n  DANGER violations ({layer}) — manufacturing short risk:")
                for d, na, nb, ax, ay, bx, by in danger[:10]:
                    print(f"    {d*1000:5.1f}µm  [{na}] ({ax:.2f},{ay:.2f}) "
                          f"vs [{nb}] ({bx:.2f},{by:.2f})")
            if warn and len(warn) <= 20:
                print(f"\n  WARN violations ({layer}) — below 0.15mm preferred minimum:")
                for d, na, nb, ax, ay, bx, by in warn:
                    print(f"    {d*1000:5.1f}µm  [{na}] ({ax:.2f},{ay:.2f}) "
                          f"vs [{nb}] ({bx:.2f},{by:.2f})")
            elif warn:
                print(f"\n  WARN violations ({layer}) — below 0.15mm (top 15 of {len(warn)}):")
                for d, na, nb, ax, ay, bx, by in warn[:15]:
                    print(f"    {d*1000:5.1f}µm  [{na}] ({ax:.2f},{ay:.2f}) "
                          f"vs [{nb}] ({bx:.2f},{by:.2f})")

    print()
    print("=" * 70)
    print(f"TOTAL: {total_danger} DANGER (<{GAP_DANGER}mm), "
          f"{total_warn} WARN (<{GAP_WARN}mm)")
    print("=" * 70)

    if total_danger > 0 and not args.warn_only:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
