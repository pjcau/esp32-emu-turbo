#!/usr/bin/env python3
"""Zone Connectivity Verification — verify vias/pads on zone nets are covered by fill.

Checks that every via and pad on zone-filled nets (GND, +5V, +3V3) is
actually covered by the zone fill polygon on the corresponding inner plane.

Zone net -> layer mapping:
  GND  -> In1.Cu (priority 0)
  +3V3 -> In2.Cu (priority 0)
  +5V  -> In2.Cu (priority 1, 2)

Items within 0.6mm of zone fill copper -> PASS (thermal relief connected).
Items 0.6-1.0mm -> WARN.
Items >1.0mm -> FAIL (truly isolated).

If no filled_polygon data exists, prints WARNING and exits 0.
"""

import os
import re
import sys
from pathlib import Path

BASE = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"

sys.path.insert(0, str(BASE / "scripts"))
from pcb_cache import load_cache

# Thresholds
THERMAL_THRESHOLD = 0.6    # thermal_gap 0.5mm + 0.1mm tolerance
WARN_THRESHOLD = 1.0       # between 0.6-1.0 -> WARN, above -> FAIL

# Zone net -> inner layer mapping
ZONE_NET_LAYERS = {
    "GND": ["In1.Cu"],
    "+3V3": ["In2.Cu"],
    "+5V": ["In2.Cu"],
}

PASS = 0
FAIL = 0
WARN = 0


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


def parse_filled_polygons(pcb_text):
    """Parse filled_polygon blocks from zone definitions.

    Returns dict: (layer, net_name) -> list of polygon coordinate lists.
    Each polygon is a list of (x, y) tuples.
    """
    polygons = {}  # (layer, net_name) -> [[(x,y), ...], ...]

    # Find zone blocks and their filled_polygon children
    zone_starts = list(re.finditer(r'^\s+\(zone\b', pcb_text, re.M))

    for zi, zone_m in enumerate(zone_starts):
        zone_start = zone_m.start()
        # Zone header is within the first ~500 chars
        header_end = min(zone_start + 500, len(pcb_text))
        header = pcb_text[zone_start:header_end]

        net_m = re.search(r'\(net_name\s+"([^"]+)"\)', header)
        if not net_m:
            continue
        net_name = net_m.group(1)

        if net_name not in ZONE_NET_LAYERS:
            continue

        # Determine zone boundary (up to next zone or end)
        if zi + 1 < len(zone_starts):
            zone_end = zone_starts[zi + 1].start()
        else:
            zone_end = len(pcb_text)

        zone_block = pcb_text[zone_start:zone_end]

        # Find all filled_polygon blocks within this zone
        for fp_m in re.finditer(r'\(filled_polygon\s*\n\s*\(layer\s+"([^"]+)"\)\s*\n\s*\(pts\b', zone_block):
            layer = fp_m.group(1)
            pts_start = fp_m.end()

            # Find closing of pts block using depth tracking
            depth = 1
            j = pts_start
            while j < len(zone_block) and depth > 0:
                if zone_block[j] == '(':
                    depth += 1
                elif zone_block[j] == ')':
                    depth -= 1
                j += 1
            pts_block = zone_block[pts_start:j]

            coords = re.findall(r'\(xy\s+([-\d.]+)\s+([-\d.]+)\)', pts_block)
            if len(coords) >= 3:
                pts = [(float(x), float(y)) for x, y in coords]
                key = (layer, net_name)
                if key not in polygons:
                    polygons[key] = []
                polygons[key].append(pts)

    return polygons


def point_to_polygon_distance(px, py, polygon):
    """Compute minimum distance from point (px, py) to polygon boundary/interior.

    Returns 0.0 if point is inside polygon, otherwise minimum distance to edge.
    Uses ray-casting for containment and point-to-segment distance.
    """
    n = len(polygon)
    if n < 3:
        return float('inf')

    # Ray-casting test for containment
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    if inside:
        return 0.0

    # Minimum distance to any edge
    import math
    min_dist = float('inf')
    j = n - 1
    for i in range(n):
        x1, y1 = polygon[j]
        x2, y2 = polygon[i]
        dx, dy = x2 - x1, y2 - y1
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq == 0:
            dist = math.sqrt((px - x1) ** 2 + (py - y1) ** 2)
        else:
            t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
            proj_x = x1 + t * dx
            proj_y = y1 + t * dy
            dist = math.sqrt((px - proj_x) ** 2 + (py - proj_y) ** 2)
        if dist < min_dist:
            min_dist = dist
        j = i

    return min_dist


def min_distance_to_zone(px, py, polygon_list):
    """Minimum distance from point to any polygon in the zone fill."""
    min_d = float('inf')
    for poly in polygon_list:
        d = point_to_polygon_distance(px, py, poly)
        if d == 0.0:
            return 0.0
        if d < min_d:
            min_d = d
    return min_d


def main():
    print("=" * 60)
    print("Zone Connectivity Verification")
    print("=" * 60)

    pcb_text = PCB_FILE.read_text(encoding="utf-8")

    # Check if filled_polygon data exists
    fp_count = len(re.findall(r'\(filled_polygon\b', pcb_text))
    if fp_count == 0:
        print("\n  WARN  No filled_polygon data found in PCB file.")
        print("         Zones not yet filled. Run:")
        print("         docker compose run --rm -T --entrypoint python3 "
              "kicad-pcb /scripts/kicad_fill_zones.py "
              "/project/esp32-emu-turbo.kicad_pcb")
        print(f"\nResults: 0 passed, 0 failed, 1 warning")
        return 0

    print(f"\n  Found {fp_count} filled_polygon block(s) in PCB file")

    # Parse filled polygons by (layer, net)
    polygons = parse_filled_polygons(pcb_text)
    print(f"  Parsed zone fills for {len(polygons)} (layer, net) combinations:")
    for (layer, net), polys in sorted(polygons.items()):
        total_pts = sum(len(p) for p in polys)
        print(f"    {layer} / {net}: {len(polys)} polygon(s), {total_pts} vertices")

    # Load cache for via/pad data
    cache = load_cache(str(PCB_FILE))
    nets = {n["id"]: n["name"] for n in cache["nets"]}

    # Check vias on zone nets
    print(f"\n-- Via Connectivity --")
    via_isolated = []
    via_warned = []
    via_ok = 0

    for via in cache["vias"]:
        net_name = nets.get(via["net"], "")
        if net_name not in ZONE_NET_LAYERS:
            continue

        expected_layers = ZONE_NET_LAYERS[net_name]
        for layer in expected_layers:
            key = (layer, net_name)
            if key not in polygons:
                via_isolated.append((via, layer, net_name, float('inf')))
                continue

            dist = min_distance_to_zone(via["x"], via["y"], polygons[key])
            if dist <= THERMAL_THRESHOLD:
                via_ok += 1
            elif dist <= WARN_THRESHOLD:
                via_warned.append((via, layer, net_name, dist))
            else:
                via_isolated.append((via, layer, net_name, dist))

    check(f"Vias connected to zone fill ({via_ok} OK)",
          len(via_isolated) == 0,
          f"{len(via_isolated)} via(s) isolated from zone fill")

    for v, layer, net, dist in via_warned:
        warn(f"Via at ({v['x']:.2f}, {v['y']:.2f}) {net}/{layer}",
             f"distance={dist:.3f}mm (marginal)")

    for v, layer, net, dist in via_isolated[:10]:
        dist_str = f"{dist:.3f}mm" if dist < 1000 else "no zone fill"
        print(f"    ISOLATED: via ({v['x']:.2f}, {v['y']:.2f}) "
              f"{net}/{layer} distance={dist_str}")

    # Check SMD pads on zone nets
    print(f"\n-- Pad Connectivity --")
    pad_isolated = []
    pad_warned = []
    pad_ok = 0

    for pad in cache["pads"]:
        net_name = nets.get(pad["net"], "")
        if net_name not in ZONE_NET_LAYERS:
            continue
        # Only check pads on layers where the zone exists
        # SMD pads are on F.Cu/B.Cu but connect to inner zones via vias
        # THT pads span all layers and should be checked against inner zones
        if pad["type"] == "thru_hole":
            expected_layers = ZONE_NET_LAYERS[net_name]
        else:
            # SMD pads only exist on their copper layer, not inner layers
            # They connect to inner planes via vias, not direct zone fill
            # Skip SMD pad check — they wouldn't be in the zone fill polygon
            continue

        for layer in expected_layers:
            key = (layer, net_name)
            if key not in polygons:
                pad_isolated.append((pad, layer, net_name, float('inf')))
                continue

            dist = min_distance_to_zone(pad["x"], pad["y"], polygons[key])
            if dist <= THERMAL_THRESHOLD:
                pad_ok += 1
            elif dist <= WARN_THRESHOLD:
                pad_warned.append((pad, layer, net_name, dist))
            else:
                pad_isolated.append((pad, layer, net_name, dist))

    check(f"THT pads connected to zone fill ({pad_ok} OK)",
          len(pad_isolated) == 0,
          f"{pad_isolated} pad(s) isolated from zone fill")

    for p, layer, net, dist in pad_warned:
        warn(f"Pad {p['ref']}.{p['num']} at ({p['x']:.2f}, {p['y']:.2f}) "
             f"{net}/{layer}",
             f"distance={dist:.3f}mm (marginal)")

    for p, layer, net, dist in pad_isolated[:10]:
        dist_str = f"{dist:.3f}mm" if dist < 1000 else "no zone fill"
        print(f"    ISOLATED: pad {p['ref']}.{p['num']} "
              f"({p['x']:.2f}, {p['y']:.2f}) {net}/{layer} "
              f"distance={dist_str}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
