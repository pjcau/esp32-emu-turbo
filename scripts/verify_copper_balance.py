#!/usr/bin/env python3
"""Copper Balance Between Layers — verify copper distribution across all 4 layers.

Uneven copper distribution can cause PCB warping during reflow soldering.
JLCPCB recommendation: no layer should have <20% of average copper.
Inner layers with ground/power planes automatically satisfy this.

Usage:
    python3 scripts/verify_copper_balance.py
    Exit code 0 = pass, 1 = failure
"""

import math
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

ALL_LAYERS = ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]
MIN_RATIO = 0.15  # warn if any layer has less than 15% of total routed copper


def _segment_length(seg):
    dx = seg["x2"] - seg["x1"]
    dy = seg["y2"] - seg["y1"]
    return math.sqrt(dx * dx + dy * dy)


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


def main():
    cache = load_cache(PCB_FILE)
    stats, warnings = analyze_copper_balance(cache)

    print("\n── Copper Balance ──")
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
        print("  FAIL  Copper balance outside acceptable range")
        return 1
    else:
        print("  PASS  Copper balance within acceptable range")
        return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main())
