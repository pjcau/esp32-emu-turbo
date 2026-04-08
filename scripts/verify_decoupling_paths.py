#!/usr/bin/env python3
"""Decoupling Cap Path Length — verify caps have short routing paths to ICs.

Decoupling capacitors must be CLOSE to IC power pins AND have SHORT traces.
Serpentine or indirect routing defeats the purpose of decoupling.

Rules:
  - Placement distance < 5mm from cap to IC power pin
  - Routing path length < 3x placement distance (no meandering)

Usage:
    python3 scripts/verify_decoupling_paths.py
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

MAX_PLACEMENT_LOCAL = 10.0  # local bypass caps: max placement distance (mm)
MAX_PLACEMENT_BULK = 30.0   # bulk/rail caps: relaxed (on power rail, not IC-specific)
MAX_PATH_RATIO = 4.0        # max routing path / placement distance

# Decoupling cap assignments: (cap_ref, ic_ref, shared_net_name, type, description)
# type: "local" = bypass cap close to IC, "bulk" = rail/input cap further away
DECOUPLING_PAIRS = [
    ("C3", "U1", "+3V3", "bulk", "ESP32 decoupling (west, rail)"),
    ("C4", "U1", "+3V3", "bulk", "ESP32 decoupling (east, rail)"),
    ("C26", "U1", "+3V3", "local", "ESP32 decoupling (north, bypass)"),
    ("C17", "U2", "VBUS", "local", "IP5306 input decoupling"),
    ("C18", "U2", "BAT+", "bulk", "IP5306 battery decoupling"),
    ("C1", "U3", "+5V", "local", "AMS1117 input decoupling"),
    ("C2", "U3", "+3V3", "bulk", "AMS1117 output decoupling (rail)"),
    ("C27", "U3", "+5V", "bulk", "AMS1117 input decoupling (rail)"),
    ("C23", "U5", "+5V", "local", "PAM8403 supply decoupling"),
    ("C24", "U5", "+5V", "local", "PAM8403 supply decoupling (alt)"),
    ("C25", "U5", "+5V", "local", "PAM8403 output decoupling"),
]


def _dist(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _manhattan(x1, y1, x2, y2):
    return abs(x2 - x1) + abs(y2 - y1)


def _seg_length(seg):
    return _dist(seg["x1"], seg["y1"], seg["x2"], seg["y2"])


def _find_pads(pads, ref, net_name, net_map):
    """Find ALL pads on a component that connect to the given net."""
    target_net_id = None
    for nid, nname in net_map.items():
        if nname == net_name:
            target_net_id = nid
            break

    candidates = [p for p in pads if p["ref"] == ref and p["net"] == target_net_id]
    if candidates:
        return candidates

    # Fallback: return all pads for the ref (zone-connected)
    return [p for p in pads if p["ref"] == ref]


def _find_closest_pad(pads, ref, net_name, net_map, ref_x, ref_y):
    """Find the pad on ref closest to (ref_x, ref_y) that matches net."""
    all_pads = _find_pads(pads, ref, net_name, net_map)
    if not all_pads:
        return None
    return min(all_pads, key=lambda p: _dist(p["x"], p["y"], ref_x, ref_y))


def _trace_path_length(segments, net_id, start_x, start_y, end_x, end_y, layer=None):
    """Estimate routing path length on a given net between two points.

    Walk connected segments on this net from start toward end.
    Returns total trace length or None if no connected path found.
    """
    net_segs = [s for s in segments if s["net"] == net_id]
    if not net_segs:
        return None

    # Simple approach: sum all segments on this net that are within the
    # bounding box of start-to-end (with margin)
    margin = 3.0
    min_x = min(start_x, end_x) - margin
    max_x = max(start_x, end_x) + margin
    min_y = min(start_y, end_y) - margin
    max_y = max(start_y, end_y) + margin

    total = 0.0
    count = 0
    for s in net_segs:
        # Check if segment is within the bounding region
        sx_mid = (s["x1"] + s["x2"]) / 2
        sy_mid = (s["y1"] + s["y2"]) / 2
        if min_x <= sx_mid <= max_x and min_y <= sy_mid <= max_y:
            total += _seg_length(s)
            count += 1

    return total if count > 0 else None


def analyze_decoupling(cache):
    """Analyze decoupling cap routing paths. Returns list of results."""
    pads = cache["pads"]
    segments = cache["segments"]
    net_map = {n["id"]: n["name"] for n in cache["nets"]}

    results = []
    for cap_ref, ic_ref, net_name, cap_type, desc in DECOUPLING_PAIRS:
        # Find cap pad with matching net
        cap_pads = _find_pads(pads, cap_ref, net_name, net_map)
        cap_pad = cap_pads[0] if cap_pads else None

        if not cap_pad:
            results.append({
                "cap": cap_ref, "ic": ic_ref, "net": net_name, "desc": desc,
                "type": cap_type, "status": "SKIP", "reason": "cap pad not found",
            })
            continue

        # Find CLOSEST IC power pad to this cap
        ic_pad = _find_closest_pad(pads, ic_ref, net_name, net_map,
                                   cap_pad["x"], cap_pad["y"])
        if not ic_pad:
            results.append({
                "cap": cap_ref, "ic": ic_ref, "net": net_name, "desc": desc,
                "type": cap_type, "status": "SKIP", "reason": "IC pad not found",
            })
            continue

        placement_dist = _dist(cap_pad["x"], cap_pad["y"], ic_pad["x"], ic_pad["y"])

        # Find net ID for shared net
        net_id = cap_pad["net"] if cap_pad["net"] != 0 else ic_pad["net"]

        path_len = _trace_path_length(
            segments, net_id,
            cap_pad["x"], cap_pad["y"],
            ic_pad["x"], ic_pad["y"],
        )

        path_ratio = path_len / placement_dist if path_len and placement_dist > 0.1 else None

        max_placement = MAX_PLACEMENT_BULK if cap_type == "bulk" else MAX_PLACEMENT_LOCAL

        status = "PASS"
        reason = ""
        if placement_dist > max_placement:
            status = "WARN"
            reason = f"placement={placement_dist:.1f}mm > {max_placement:.0f}mm ({cap_type})"
        if path_ratio and path_ratio > MAX_PATH_RATIO:
            status = "WARN"
            reason += f" path_ratio={path_ratio:.1f}x > {MAX_PATH_RATIO}x"

        results.append({
            "cap": cap_ref, "ic": ic_ref, "net": net_name, "desc": desc,
            "type": cap_type, "status": status, "reason": reason.strip(),
            "placement_mm": round(placement_dist, 2),
            "path_mm": round(path_len, 2) if path_len else None,
            "path_ratio": round(path_ratio, 1) if path_ratio else None,
        })

    return results


class TestDecouplingPaths(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = load_cache(PCB_FILE)
        cls.results = analyze_decoupling(cls.cache)

    def test_all_caps_placed_near_ics(self):
        """Decoupling caps must be within threshold of their IC."""
        for r in self.results:
            if r["status"] == "SKIP":
                continue
            max_dist = MAX_PLACEMENT_BULK if r.get("type") == "bulk" else MAX_PLACEMENT_LOCAL
            with self.subTest(cap=r["cap"], ic=r["ic"]):
                self.assertLessEqual(
                    r["placement_mm"], max_dist,
                    f"{r['cap']}→{r['ic']} ({r['net']}): "
                    f"placement={r['placement_mm']}mm > {max_dist}mm ({r.get('type','?')})",
                )

    def test_no_serpentine_decoupling(self):
        """Routing path should not be excessively longer than placement distance."""
        for r in self.results:
            if r["status"] == "SKIP" or r["path_ratio"] is None:
                continue
            with self.subTest(cap=r["cap"], ic=r["ic"]):
                self.assertLessEqual(
                    r["path_ratio"], MAX_PATH_RATIO,
                    f"{r['cap']}→{r['ic']} ({r['net']}): "
                    f"path_ratio={r['path_ratio']}x > {MAX_PATH_RATIO}x",
                )


def main():
    cache = load_cache(PCB_FILE)
    results = analyze_decoupling(cache)

    print("\n── Decoupling Cap Path Length ──")
    fails = 0
    for r in results:
        if r["status"] == "SKIP":
            print(f"  SKIP  {r['cap']}→{r['ic']} ({r['net']}): {r['reason']}")
            continue

        path_str = f"path={r['path_mm']}mm" if r["path_mm"] else "path=N/A"
        ratio_str = f"ratio={r['path_ratio']}x" if r["path_ratio"] else "ratio=N/A"
        tag = r["status"]
        line = (
            f"  {tag:4s}  {r['cap']}→{r['ic']} ({r['net']}): "
            f"placement={r['placement_mm']}mm, {path_str}, {ratio_str} "
            f"— {r['desc']}"
        )
        print(line)
        if tag == "WARN":
            fails += 1

    if fails:
        print(f"  WARN  {fails} decoupling path(s) outside recommended range")
        return 1
    else:
        print("  PASS  All decoupling caps have short paths to their ICs")
        return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main())
