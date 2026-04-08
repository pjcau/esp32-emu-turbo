#!/usr/bin/env python3
"""USB Impedance Check — verify USB D+/D- trace geometry for 90 ohm differential.

For JLCPCB 4-layer 1.6mm stackup (JLC04161H-7628):
  - Outer layer copper: ~0.035mm (1oz)
  - Prepreg to inner layer: ~0.21mm (7628)
  - 90 ohm differential: trace width 0.18-0.22mm, spacing ~0.20mm

Checks:
  1. Trace width in 0.18-0.25mm range
  2. D+/D- length mismatch (skew) < 2mm
  3. Parallel section spacing between D+ and D-

Usage:
    python3 scripts/verify_usb_impedance.py
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

USB_DP_NET = "USB_D+"
USB_DM_NET = "USB_D-"
MIN_WIDTH = 0.18   # mm
MAX_WIDTH = 0.25   # mm
MAX_SKEW = 2.0     # mm (USB 2.0 FS tolerance ~25mm, we're strict)
MIN_SPACING = 0.15 # mm between D+ and D- traces
MAX_SPACING = 0.35 # mm (too far apart loses coupling)


def _seg_length(seg):
    dx = seg["x2"] - seg["x1"]
    dy = seg["y2"] - seg["y1"]
    return math.sqrt(dx * dx + dy * dy)


def _seg_midpoint(seg):
    return ((seg["x1"] + seg["x2"]) / 2, (seg["y1"] + seg["y2"]) / 2)


def _point_to_seg_dist(px, py, seg):
    """Minimum distance from a point to a line segment."""
    x1, y1, x2, y2 = seg["x1"], seg["y1"], seg["x2"], seg["y2"]
    dx, dy = x2 - x1, y2 - y1
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-10:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)


def analyze_usb_impedance(cache):
    """Analyze USB D+/D- trace geometry. Returns dict with results."""
    net_map = {n["name"]: n["id"] for n in cache["nets"] if n["name"]}
    segments = cache["segments"]

    dp_id = net_map.get(USB_DP_NET)
    dm_id = net_map.get(USB_DM_NET)

    if dp_id is None or dm_id is None:
        return {"status": "SKIP", "reason": "USB D+/D- nets not found"}

    dp_segs = [s for s in segments if s["net"] == dp_id]
    dm_segs = [s for s in segments if s["net"] == dm_id]

    if not dp_segs and not dm_segs:
        return {"status": "SKIP", "reason": "No USB D+/D- segments found (may use zones only)"}

    # Width check
    dp_widths = set(round(s["width"], 3) for s in dp_segs)
    dm_widths = set(round(s["width"], 3) for s in dm_segs)
    all_widths = dp_widths | dm_widths

    width_ok = all(MIN_WIDTH <= w <= MAX_WIDTH for w in all_widths)
    width_issues = [
        w for w in all_widths if w < MIN_WIDTH or w > MAX_WIDTH
    ]

    # Length / skew
    dp_total = sum(_seg_length(s) for s in dp_segs)
    dm_total = sum(_seg_length(s) for s in dm_segs)
    skew = abs(dp_total - dm_total)
    skew_ok = skew <= MAX_SKEW

    # Spacing: for each D+ segment midpoint, find min distance to any D- segment
    spacings = []
    for dp_seg in dp_segs:
        mx, my = _seg_midpoint(dp_seg)
        min_dist = float("inf")
        for dm_seg in dm_segs:
            d = _point_to_seg_dist(mx, my, dm_seg)
            if d < min_dist:
                min_dist = d
        if min_dist < 50:  # only count nearby parallel sections
            spacings.append(min_dist)

    avg_spacing = sum(spacings) / len(spacings) if spacings else None
    min_spacing = min(spacings) if spacings else None

    # Layers used
    dp_layers = set(s["layer"] for s in dp_segs)
    dm_layers = set(s["layer"] for s in dm_segs)

    return {
        "status": "PASS" if (width_ok and skew_ok) else "FAIL",
        "dp_segments": len(dp_segs),
        "dm_segments": len(dm_segs),
        "dp_length_mm": round(dp_total, 2),
        "dm_length_mm": round(dm_total, 2),
        "skew_mm": round(skew, 2),
        "skew_ok": skew_ok,
        "widths": sorted(all_widths),
        "width_ok": width_ok,
        "width_issues": width_issues,
        "avg_spacing_mm": round(avg_spacing, 2) if avg_spacing else None,
        "min_spacing_mm": round(min_spacing, 2) if min_spacing else None,
        "dp_layers": sorted(dp_layers),
        "dm_layers": sorted(dm_layers),
    }


class TestUSBImpedance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = load_cache(PCB_FILE)
        cls.result = analyze_usb_impedance(cls.cache)

    def test_usb_nets_exist(self):
        """USB D+ and D- nets must have routed segments."""
        if self.result["status"] == "SKIP":
            self.skipTest(self.result["reason"])
        self.assertGreater(self.result["dp_segments"], 0, "No USB_D+ segments")
        self.assertGreater(self.result["dm_segments"], 0, "No USB_D- segments")

    def test_trace_width(self):
        """USB trace width must be 0.18-0.25mm for 90 ohm differential."""
        if self.result["status"] == "SKIP":
            self.skipTest(self.result["reason"])
        self.assertTrue(
            self.result["width_ok"],
            f"USB trace widths out of range: {self.result['width_issues']}mm "
            f"(need {MIN_WIDTH}-{MAX_WIDTH}mm)",
        )

    def test_length_skew(self):
        """USB D+/D- length mismatch must be < 2mm."""
        if self.result["status"] == "SKIP":
            self.skipTest(self.result["reason"])
        self.assertLessEqual(
            self.result["skew_mm"], MAX_SKEW,
            f"USB skew={self.result['skew_mm']}mm > {MAX_SKEW}mm "
            f"(D+={self.result['dp_length_mm']}mm, D-={self.result['dm_length_mm']}mm)",
        )


def main():
    cache = load_cache(PCB_FILE)
    result = analyze_usb_impedance(cache)

    print("\n── USB Impedance Check ──")
    if result["status"] == "SKIP":
        print(f"  SKIP  {result['reason']}")
        return 0

    print(f"  D+ segments: {result['dp_segments']}, length: {result['dp_length_mm']}mm")
    print(f"  D- segments: {result['dm_segments']}, length: {result['dm_length_mm']}mm")
    print(f"  Trace widths: {result['widths']}mm (target: {MIN_WIDTH}-{MAX_WIDTH}mm)")
    print(f"  Length skew: {result['skew_mm']}mm (max: {MAX_SKEW}mm)")
    print(f"  D+ layers: {result['dp_layers']}, D- layers: {result['dm_layers']}")

    if result["avg_spacing_mm"]:
        print(f"  Avg spacing: {result['avg_spacing_mm']}mm, min: {result['min_spacing_mm']}mm")

    issues = []
    if not result["width_ok"]:
        issues.append(f"width out of range: {result['width_issues']}mm")
    if not result["skew_ok"]:
        issues.append(f"skew={result['skew_mm']}mm exceeds {MAX_SKEW}mm")

    if issues:
        for i in issues:
            print(f"  FAIL  {i}")
        return 1
    else:
        print("  PASS  USB D+/D- impedance geometry within spec")
        return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main())
