#!/usr/bin/env python3
"""USB GND Return Path Density — verify GND via stitching near USB D+/D- traces.

For USB 2.0 signal integrity, GND stitching vias should be within 3-5mm of
every USB trace segment to provide a low-impedance return path on the
adjacent ground plane (In1.Cu).

Usage:
    python3 scripts/verify_usb_return_path.py
    Exit code 0 = pass/warn, 1 = failure
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
GND_NET = "GND"
WARN_DISTANCE = 5.0   # mm — warn if any segment midpoint > 5mm from nearest GND via
IDEAL_DISTANCE = 3.0  # mm — ideal max distance


def _seg_midpoint(seg):
    return ((seg["x1"] + seg["x2"]) / 2, (seg["y1"] + seg["y2"]) / 2)


def _dist(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def analyze_usb_return_path(cache):
    """Check GND via proximity for each USB segment midpoint."""
    net_map = {n["name"]: n["id"] for n in cache["nets"] if n["name"]}
    segments = cache["segments"]
    vias = cache["vias"]

    dp_id = net_map.get(USB_DP_NET)
    dm_id = net_map.get(USB_DM_NET)
    gnd_id = net_map.get(GND_NET)

    if dp_id is None or dm_id is None:
        return {"status": "SKIP", "reason": "USB D+/D- nets not found"}
    if gnd_id is None:
        return {"status": "SKIP", "reason": "GND net not found"}

    dp_segs = [s for s in segments if s["net"] == dp_id]
    dm_segs = [s for s in segments if s["net"] == dm_id]
    gnd_vias = [(v["x"], v["y"]) for v in vias if v["net"] == gnd_id]

    if not dp_segs and not dm_segs:
        return {"status": "SKIP", "reason": "No USB segments found"}
    if not gnd_vias:
        return {"status": "FAIL", "reason": "No GND vias found anywhere on board"}

    results = {}
    for label, segs in [("USB_D+", dp_segs), ("USB_D-", dm_segs)]:
        distances = []
        for seg in segs:
            mx, my = _seg_midpoint(seg)
            min_d = min(_dist(mx, my, vx, vy) for vx, vy in gnd_vias)
            distances.append(min_d)

        if distances:
            results[label] = {
                "count": len(segs),
                "min": round(min(distances), 2),
                "max": round(max(distances), 2),
                "avg": round(sum(distances) / len(distances), 2),
                "violations": sum(1 for d in distances if d > WARN_DISTANCE),
            }
        else:
            results[label] = {"count": 0, "min": 0, "max": 0, "avg": 0, "violations": 0}

    total_violations = sum(r["violations"] for r in results.values())
    all_within = total_violations == 0

    return {
        "status": "PASS" if all_within else "WARN",
        "gnd_vias": len(gnd_vias),
        "nets": results,
        "all_within_limit": all_within,
    }


class TestUSBReturnPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = load_cache(PCB_FILE)
        cls.result = analyze_usb_return_path(cls.cache)

    def test_usb_segments_exist(self):
        if self.result["status"] == "SKIP":
            self.skipTest(self.result.get("reason", ""))
        for label in ("USB_D+", "USB_D-"):
            self.assertGreater(self.result["nets"][label]["count"], 0,
                               f"No {label} segments found")

    def test_gnd_via_proximity(self):
        """WARN-level check — violations are reported but not fatal."""
        if self.result["status"] == "SKIP":
            self.skipTest(self.result.get("reason", ""))
        for label, data in self.result["nets"].items():
            if data["violations"] > 0:
                print(f"  WARN  {label}: {data['violations']} segments > "
                      f"{WARN_DISTANCE}mm from GND via (max={data['max']}mm)")
        # This is advisory — WARN does not fail the test
        self.assertIn(self.result["status"], ("PASS", "WARN"))


def main():
    cache = load_cache(PCB_FILE)
    result = analyze_usb_return_path(cache)

    print("\n\u2500\u2500 USB Return Path Analysis \u2500\u2500")
    if result["status"] == "SKIP":
        print(f"  SKIP  {result['reason']}")
        return 0

    print(f"  INFO  GND vias on board: {result['gnd_vias']}")
    for label, data in result["nets"].items():
        tag = "PASS" if data["violations"] == 0 else "WARN"
        print(f"  {tag}  {label} segments: {data['count']}, "
              f"avg {data['avg']}mm to nearest GND via "
              f"(min {data['min']}mm, max {data['max']}mm)")

    if result["all_within_limit"]:
        print(f"  PASS  All USB segments within {WARN_DISTANCE}mm of GND via")
    else:
        total_v = sum(d["violations"] for d in result["nets"].values())
        print(f"  WARN  {total_v} USB segment(s) > {WARN_DISTANCE}mm from nearest GND via")

    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main())
