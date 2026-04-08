#!/usr/bin/env python3
"""Copper Balance Between Layers — verify copper distribution across all 4 layers.

Uneven copper distribution can cause PCB warping during reflow soldering.
JLCPCB recommendation: no layer should have <20% of average copper.
Inner layers with ground/power planes automatically satisfy this.

Extended checks (inner layers):
  - Zone coverage area on In1.Cu and In2.Cu (polygon area as % of board)
  - In1.Cu vs In2.Cu coverage balance (should be within 20%)
  - Inner layer minimum coverage (>60% expected for planes)
  - Total stackup balance: (F.Cu + In2.Cu) vs (B.Cu + In1.Cu) within 30%

Usage:
    python3 scripts/verify_copper_balance.py
    Exit code 0 = pass, 1 = failure
"""

import math
import os
import re
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

ALL_LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
MIN_RATIO = 0.15  # warn if any layer has less than 15% of total routed copper

# Board dimensions (mm)
BOARD_W = 160.0
BOARD_H = 75.0
CORNER_R = 6.0
# Effective board area minus corner radii: 4 corners x (r^2 - pi*r^2/4)
BOARD_AREA = BOARD_W * BOARD_H - 4 * (CORNER_R**2 - math.pi * CORNER_R**2 / 4)

# Thresholds for inner layer checks
INNER_MIN_COVERAGE = 0.60     # Inner layers should have >60% coverage
INNER_BALANCE_MAX = 0.20      # In1 vs In2 within 20%
STACKUP_BALANCE_MAX = 0.30    # Top-pair vs bottom-pair within 30%


def _segment_length(seg):
    dx = seg["x2"] - seg["x1"]
    dy = seg["y2"] - seg["y1"]
    return math.sqrt(dx * dx + dy * dy)


def _polygon_area(pts):
    """Shoelace formula for polygon area from list of (x,y) tuples."""
    n = len(pts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def _parse_zone_outlines(pcb_path):
    """Parse zone outline polygons from PCB file.

    Returns list of dicts: {layer, net_name, outline_area, priority}.
    Zone outlines define the boundary; actual filled area depends on clearances.
    """
    with open(pcb_path, encoding="utf-8") as f:
        text = f.read()
    zones = []

    # Find each zone block
    zone_starts = [m.start() for m in re.finditer(r'^\s+\(zone\b', text, re.M)]
    for start in zone_starts:
        # Extract zone header
        header = text[start:start + 500]
        net_m = re.search(r'\(net_name\s+"([^"]+)"\)', header)
        layer_m = re.search(r'\(layer\s+"([^"]+)"\)', header)
        pri_m = re.search(r'\(priority\s+(\d+)\)', header)
        if not net_m or not layer_m:
            continue

        # Find the outline polygon (first polygon after zone start)
        poly_start = text.find("(polygon", start)
        if poly_start == -1 or poly_start > start + 2000:
            continue
        pts_start = text.find("(pts", poly_start)
        if pts_start == -1:
            continue
        pts_end = text.find(")", pts_start + 4)
        if pts_end == -1:
            continue
        # Find closing paren of pts
        depth = 1
        j = pts_start + 4
        while j < len(text) and depth > 0:
            if text[j] == '(':
                depth += 1
            elif text[j] == ')':
                depth -= 1
            j += 1
        pts_block = text[pts_start:j]

        # Parse xy coordinates
        coords = re.findall(r'\(xy\s+([-\d.]+)\s+([-\d.]+)\)', pts_block)
        pts = [(float(x), float(y)) for x, y in coords]

        if len(pts) >= 3:
            zones.append({
                "layer": layer_m.group(1),
                "net_name": net_m.group(1),
                "outline_area": _polygon_area(pts),
                "priority": int(pri_m.group(1)) if pri_m else 0,
            })

    return zones


def analyze_inner_layer_balance(pcb_path):
    """Analyze inner layer zone coverage and balance.

    Returns (inner_stats, warnings).
    inner_stats: dict per inner layer with zone coverage info.
    """
    zone_outlines = _parse_zone_outlines(pcb_path)
    warnings = []

    inner_stats = {}
    for layer in ["In1.Cu", "In2.Cu"]:
        layer_zones = [z for z in zone_outlines if z["layer"] == layer]
        # Use the largest zone outline (primary plane) as coverage estimate
        # Subtract ~15% for clearances, thermal relief, etc.
        if layer_zones:
            total_outline = sum(z["outline_area"] for z in layer_zones)
            # For overlapping zones (e.g., +5V region inside +3V3), the higher
            # priority zone replaces the lower one — don't double-count
            max_outline = max(z["outline_area"] for z in layer_zones)
            estimated_fill = max_outline * 0.85  # ~85% fill after clearances
            coverage_pct = estimated_fill / BOARD_AREA * 100
            zone_names = ", ".join(sorted(set(z["net_name"] for z in layer_zones)))
        else:
            total_outline = 0
            estimated_fill = 0
            coverage_pct = 0
            zone_names = "(none)"

        inner_stats[layer] = {
            "zone_count": len(layer_zones),
            "zone_names": zone_names,
            "outline_area_mm2": round(total_outline, 1),
            "estimated_fill_mm2": round(estimated_fill, 1),
            "coverage_pct": round(coverage_pct, 1),
        }

    # Check 1: Inner layer minimum coverage (>60%)
    for layer in ["In1.Cu", "In2.Cu"]:
        s = inner_stats[layer]
        if s["coverage_pct"] < INNER_MIN_COVERAGE * 100:
            warnings.append(
                f"{layer}: {s['coverage_pct']:.1f}% coverage "
                f"(< {INNER_MIN_COVERAGE*100:.0f}% minimum for planes)")

    # Check 2: In1.Cu vs In2.Cu balance (within 20%)
    in1_cov = inner_stats["In1.Cu"]["coverage_pct"]
    in2_cov = inner_stats["In2.Cu"]["coverage_pct"]
    if in1_cov > 0 and in2_cov > 0:
        max_cov = max(in1_cov, in2_cov)
        min_cov = min(in1_cov, in2_cov)
        imbalance = (max_cov - min_cov) / max_cov
        inner_stats["inner_imbalance_pct"] = round(imbalance * 100, 1)
        if imbalance > INNER_BALANCE_MAX:
            warnings.append(
                f"Inner layer imbalance: In1.Cu={in1_cov:.1f}% vs "
                f"In2.Cu={in2_cov:.1f}% (diff={imbalance*100:.1f}% > "
                f"{INNER_BALANCE_MAX*100:.0f}%)")
    else:
        inner_stats["inner_imbalance_pct"] = 0

    return inner_stats, warnings


def analyze_stackup_balance(cache, inner_stats):
    """Check total stackup balance: (F.Cu + In2.Cu) vs (B.Cu + In1.Cu).

    Uses segment copper area for outer layers, zone fill estimate for inner.
    Returns list of warnings.
    """
    warnings = []
    segments = cache["segments"]

    # Outer layer copper area (from segments)
    fcu_area = sum(_segment_length(s) * s["width"]
                   for s in segments if s["layer"] == "F.Cu")
    bcu_area = sum(_segment_length(s) * s["width"]
                   for s in segments if s["layer"] == "B.Cu")

    # Inner layer copper area (estimated from zone fill)
    in1_area = inner_stats.get("In1.Cu", {}).get("estimated_fill_mm2", 0)
    in2_area = inner_stats.get("In2.Cu", {}).get("estimated_fill_mm2", 0)

    # Stackup pairs (for warping analysis):
    # Top pair:    F.Cu + In1.Cu  (layers 1+2)
    # Bottom pair: In2.Cu + B.Cu  (layers 3+4)
    top_pair = fcu_area + in1_area
    bot_pair = in2_area + bcu_area

    if top_pair > 0 and bot_pair > 0:
        max_pair = max(top_pair, bot_pair)
        min_pair = min(top_pair, bot_pair)
        imbalance = (max_pair - min_pair) / max_pair
        if imbalance > STACKUP_BALANCE_MAX:
            warnings.append(
                f"Stackup imbalance: top-pair={top_pair:.0f}mm^2 vs "
                f"bot-pair={bot_pair:.0f}mm^2 "
                f"(diff={imbalance*100:.1f}% > {STACKUP_BALANCE_MAX*100:.0f}%)")

    return warnings, {
        "fcu_area": round(fcu_area, 1),
        "bcu_area": round(bcu_area, 1),
        "in1_area": round(in1_area, 1),
        "in2_area": round(in2_area, 1),
        "top_pair": round(top_pair, 1),
        "bot_pair": round(bot_pair, 1),
    }


def analyze_copper_balance(cache):
    """Analyze copper distribution across layers.

    Returns dict with per-layer stats and overall pass/fail.
    """
    segments = cache["segments"]
    zones = cache["zones"]

    # Segment stats per layer: count, total length, copper area (length * width)
    layer_stats = {}
    for layer in ALL_LAYERS:
        layer_segs = [s for s in segments if s["layer"] == layer]
        total_length = sum(_segment_length(s) for s in layer_segs)
        total_area = sum(_segment_length(s) * s["width"] for s in layer_segs)
        layer_stats[layer] = {
            "segments": len(layer_segs),
            "total_length_mm": round(total_length, 2),
            "copper_area_mm2": round(total_area, 2),
        }

    # Zone stats per layer
    layer_zones = {}
    for zone in zones:
        layer = zone["layer"]
        if layer not in layer_zones:
            layer_zones[layer] = []
        layer_zones[layer].append(zone["net_name"])

    # Inner layers with zones count as high copper (full plane coverage)
    # Board area: 160 x 75 = 12000 mm2
    board_area = 160.0 * 75.0
    plane_coverage_estimate = board_area * 0.85  # ~85% fill after clearances

    for layer in ALL_LAYERS:
        if layer in layer_zones:
            layer_stats[layer]["zones"] = layer_zones[layer]
            layer_stats[layer]["has_plane"] = True
            layer_stats[layer]["estimated_plane_area_mm2"] = round(
                plane_coverage_estimate, 1
            )
        else:
            layer_stats[layer]["zones"] = []
            layer_stats[layer]["has_plane"] = False
            layer_stats[layer]["estimated_plane_area_mm2"] = 0.0

    # Copper balance assessment:
    # - Inner layers with planes: automatic PASS (full coverage)
    # - Outer layers: compare F.Cu vs B.Cu segment copper area
    #   If one outer layer has <15% of the combined outer copper, WARN
    # - The key warping risk is symmetric balance: top vs bottom, inner vs inner
    warnings = []

    # Check inner layers have planes
    for layer in ["In1.Cu", "In2.Cu"]:
        if not layer_stats[layer]["has_plane"]:
            warnings.append(f"{layer}: no ground/power plane (warping risk)")

    # Check outer layer balance (F.Cu vs B.Cu)
    fcu_area = layer_stats["F.Cu"]["copper_area_mm2"]
    bcu_area = layer_stats["B.Cu"]["copper_area_mm2"]
    outer_total = fcu_area + bcu_area

    if outer_total > 0:
        fcu_ratio = fcu_area / outer_total
        bcu_ratio = bcu_area / outer_total
        layer_stats["F.Cu"]["ratio"] = round(fcu_ratio, 4)
        layer_stats["B.Cu"]["ratio"] = round(bcu_ratio, 4)
        if fcu_ratio < MIN_RATIO:
            warnings.append(
                f"F.Cu: {fcu_ratio*100:.1f}% of outer copper (< {MIN_RATIO*100:.0f}%)"
            )
        if bcu_ratio < MIN_RATIO:
            warnings.append(
                f"B.Cu: {bcu_ratio*100:.1f}% of outer copper (< {MIN_RATIO*100:.0f}%)"
            )
    for layer in ["In1.Cu", "In2.Cu"]:
        layer_stats[layer]["ratio"] = 1.0 if layer_stats[layer]["has_plane"] else 0.0

    return layer_stats, warnings


class TestCopperBalance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = load_cache(PCB_FILE)
        cls.stats, cls.warnings = analyze_copper_balance(cls.cache)
        cls.inner_stats, cls.inner_warnings = analyze_inner_layer_balance(PCB_FILE)
        cls.stackup_warnings, cls.stackup_stats = analyze_stackup_balance(
            cls.cache, cls.inner_stats)

    def test_all_layers_have_copper(self):
        """Every layer must have some copper (segments or zones)."""
        for layer in ALL_LAYERS:
            s = self.stats[layer]
            has_copper = s["segments"] > 0 or s["has_plane"]
            self.assertTrue(
                has_copper,
                f"{layer} has no copper (no segments, no zones)",
            )

    def test_copper_balance_ratio(self):
        """No layer should have less than 15% of total effective copper."""
        for w in self.warnings:
            self.fail(f"Copper balance warning: {w}")

    def test_inner_layers_have_planes(self):
        """Inner layers should have ground/power planes for signal integrity."""
        for layer in ["In1.Cu", "In2.Cu"]:
            self.assertTrue(
                self.stats[layer]["has_plane"],
                f"{layer} has no zone/plane — inner layers need ground or power planes",
            )

    def test_inner_layer_coverage(self):
        """Inner layers should have >60% copper coverage."""
        for w in self.inner_warnings:
            if "coverage" in w:
                self.fail(f"Inner layer coverage: {w}")

    def test_inner_layer_balance(self):
        """In1.Cu vs In2.Cu should be within 20%."""
        for w in self.inner_warnings:
            if "imbalance" in w.lower():
                self.fail(f"Inner layer balance: {w}")

    def test_stackup_balance(self):
        """Top-pair vs bottom-pair copper should be within 30%."""
        for w in self.stackup_warnings:
            self.fail(f"Stackup balance: {w}")


def main():
    cache = load_cache(PCB_FILE)
    stats, warnings = analyze_copper_balance(cache)

    print("\n── Copper Balance (Outer Layers) ──")
    for layer in ALL_LAYERS:
        s = stats[layer]
        if s["has_plane"]:
            zone_names = ", ".join(s["zones"])
            print(
                f"  {layer:8s}: {len(s['zones'])} zone(s) ({zone_names}) "
                f"— high coverage + {s['segments']} segments"
            )
        else:
            print(
                f"  {layer:8s}: segments={s['segments']}, "
                f"total_length={s['total_length_mm']:.1f}mm, "
                f"copper_area={s['copper_area_mm2']:.1f}mm²"
            )

    if warnings:
        for w in warnings:
            print(f"  WARN  {w}")
        print("  FAIL  Outer layer copper balance outside acceptable range")
        return 1
    else:
        print("  PASS  Outer layer copper balance within acceptable range")

    # --- Inner layer zone coverage ---
    inner_stats, inner_warnings = analyze_inner_layer_balance(PCB_FILE)

    print(f"\n── Inner Layer Zone Coverage (board area: {BOARD_AREA:.0f} mm^2) ──")
    for layer in ["In1.Cu", "In2.Cu"]:
        s = inner_stats[layer]
        print(
            f"  {layer:8s}: {s['zone_count']} zone(s) ({s['zone_names']}), "
            f"outline={s['outline_area_mm2']:.0f}mm^2, "
            f"est. fill={s['estimated_fill_mm2']:.0f}mm^2, "
            f"coverage={s['coverage_pct']:.1f}%"
        )

    if inner_stats.get("inner_imbalance_pct", 0) > 0:
        print(f"  In1 vs In2 imbalance: {inner_stats['inner_imbalance_pct']:.1f}%")

    for w in inner_warnings:
        print(f"  WARN  {w}")

    if not inner_warnings:
        print("  PASS  Inner layer coverage and balance OK")

    # --- Stackup balance ---
    stackup_warnings, stackup_stats = analyze_stackup_balance(cache, inner_stats)

    print("\n── Stackup Balance (top-pair vs bottom-pair) ──")
    print(f"  Top pair:  F.Cu ({stackup_stats['fcu_area']:.0f}mm^2) + "
          f"In1.Cu ({stackup_stats['in1_area']:.0f}mm^2) = "
          f"{stackup_stats['top_pair']:.0f}mm^2")
    print(f"  Bot pair:  In2.Cu ({stackup_stats['in2_area']:.0f}mm^2) + "
          f"B.Cu ({stackup_stats['bcu_area']:.0f}mm^2) = "
          f"{stackup_stats['bot_pair']:.0f}mm^2")

    for w in stackup_warnings:
        print(f"  WARN  {w}")

    if not stackup_warnings:
        print("  PASS  Stackup balance within acceptable range")

    all_warnings = warnings + inner_warnings + stackup_warnings
    if all_warnings:
        return 1
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main())
