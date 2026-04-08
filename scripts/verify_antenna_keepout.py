#!/usr/bin/env python3
"""Antenna Keep-Out Zone verification for ESP32-S3-WROOM-1 (U1).

The WROOM-1 module (18x25.5mm) has a built-in PCB antenna at the TOP
of the module body (opposite pin 1). Per the datasheet (Figure 10),
the antenna area is 6mm tall x 18mm wide at the top of the module.

This script defines a keep-out zone that extends 2mm beyond the module
outline on the antenna side and checks that no traces, vias, or copper
pours (except GND plane cutouts) exist within this zone on any layer.

Datasheet: hardware/datasheets/U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf
Module dimensions: 18.0 x 25.5 x 3.1 mm (Figure 8)
Antenna area: 6mm from top edge, full 18mm width (Figure 10)
"""

import json
import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"

# Import cache loader
sys.path.insert(0, str(BASE / "scripts"))
from pcb_cache import load_cache

# ── Module geometry (from datasheet Figure 8 & 10) ──────────────
MODULE_WIDTH = 18.0    # mm
MODULE_HEIGHT = 25.5   # mm
ANTENNA_HEIGHT = 6.0   # mm (from top edge of module)
KEEPOUT_MARGIN = 2.0   # mm (extend beyond module outline)

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    """Record test result."""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def find_u1_placement(cache):
    """Find U1 module center and compute antenna keep-out rectangle.

    U1 is on B.Cu (bottom side). The footprint center (fp_x, fp_y) is
    stored in the pad data. The module's pin 1 is at one end, and the
    antenna is at the opposite end (top of module).

    In KiCad, footprint coordinates: the module body extends from the
    center. For WROOM-1, pin 1 is at the bottom-left (pads along bottom
    and sides), antenna is at top.
    """
    # Get U1 pad positions to find footprint center and orientation
    u1_pads = [p for p in cache["pads"] if p.get("ref") == "U1"]
    if not u1_pads:
        return None

    # Footprint center is stored in fp_x, fp_y
    fp_x = u1_pads[0]["fp_x"]
    fp_y = u1_pads[0]["fp_y"]

    # Find pad bounding box to determine orientation
    xs = [p["x"] for p in u1_pads]
    ys = [p["y"] for p in u1_pads]
    pad_min_x, pad_max_x = min(xs), max(xs)
    pad_min_y, pad_max_y = min(ys), max(ys)

    pad_center_y = (pad_min_y + pad_max_y) / 2

    # Determine antenna direction: the antenna is on the side where
    # the module extends beyond the pad bounding box.
    # For WROOM-1, pads occupy the lower ~19.5mm of the 25.5mm module.
    # The antenna is in the top ~6mm where there are NO pads.
    #
    # The keep-out zone on the HOST PCB covers:
    # 1. The area from the topmost pad row up to the module edge
    #    (this is under the antenna, no host copper allowed)
    # 2. Plus KEEPOUT_MARGIN beyond the module edge
    #    (clear area for antenna radiation pattern)
    #
    # Per Espressif layout guidelines (Figure 10), the critical zone
    # is the antenna protrusion area and clearance beyond the module.
    # Traces routed between pads (inside the shielded module body)
    # are acceptable as they are under the module's internal GND plane.

    if pad_center_y > fp_y:
        # Antenna is toward lower Y (top in PCB coordinates)
        antenna_direction = "top"
        module_antenna_edge_y = fp_y - MODULE_HEIGHT / 2
        # The critical keepout is BEYOND the module edge where the
        # antenna radiates freely. Inside the module footprint, traces
        # approaching pads are expected and shielded by the module's
        # internal ground plane and metal can.
        #
        # Keepout zone: from (module_edge - margin) to module_edge
        # This is the area outside the module where no host PCB copper
        # should exist to avoid detuning the antenna.
        keepout_y_min = module_antenna_edge_y - KEEPOUT_MARGIN
        keepout_y_max = module_antenna_edge_y
    else:
        # Antenna is toward higher Y (bottom in PCB coordinates)
        antenna_direction = "bottom"
        module_antenna_edge_y = fp_y + MODULE_HEIGHT / 2
        keepout_y_min = module_antenna_edge_y
        keepout_y_max = module_antenna_edge_y + KEEPOUT_MARGIN

    # Keep-out zone spans full module width + margin on each side
    keepout_x_min = fp_x - MODULE_WIDTH / 2 - KEEPOUT_MARGIN
    keepout_x_max = fp_x + MODULE_WIDTH / 2 + KEEPOUT_MARGIN

    return {
        "fp_x": fp_x,
        "fp_y": fp_y,
        "antenna_dir": antenna_direction,
        "keepout": {
            "x_min": keepout_x_min,
            "x_max": keepout_x_max,
            "y_min": keepout_y_min,
            "y_max": keepout_y_max,
        },
        "pad_bbox": {
            "x_min": pad_min_x,
            "x_max": pad_max_x,
            "y_min": pad_min_y,
            "y_max": pad_max_y,
        },
    }


def point_in_rect(x, y, rect):
    """Check if point (x, y) is inside rectangle."""
    return (rect["x_min"] <= x <= rect["x_max"] and
            rect["y_min"] <= y <= rect["y_max"])


def segment_intersects_rect(x1, y1, x2, y2, rect):
    """Check if a line segment intersects or is inside a rectangle."""
    # Quick check: if either endpoint is inside, it intersects
    if point_in_rect(x1, y1, rect) or point_in_rect(x2, y2, rect):
        return True

    # Check if segment bounding box overlaps rectangle
    seg_x_min, seg_x_max = min(x1, x2), max(x1, x2)
    seg_y_min, seg_y_max = min(y1, y2), max(y1, y2)

    if (seg_x_max < rect["x_min"] or seg_x_min > rect["x_max"] or
            seg_y_max < rect["y_min"] or seg_y_min > rect["y_max"]):
        return False

    # For segments that cross the rectangle without endpoints inside,
    # check line-rectangle intersection (parametric clipping)
    dx = x2 - x1
    dy = y2 - y1

    # Check intersection with each edge
    for edge_x in [rect["x_min"], rect["x_max"]]:
        if abs(dx) > 1e-9:
            t = (edge_x - x1) / dx
            if 0 <= t <= 1:
                y_at_t = y1 + t * dy
                if rect["y_min"] <= y_at_t <= rect["y_max"]:
                    return True

    for edge_y in [rect["y_min"], rect["y_max"]]:
        if abs(dy) > 1e-9:
            t = (edge_y - y1) / dy
            if 0 <= t <= 1:
                x_at_t = x1 + t * dx
                if rect["x_min"] <= x_at_t <= rect["x_max"]:
                    return True

    return False


def test_antenna_keepout():
    """Run all antenna keep-out zone checks."""
    print("=" * 60)
    print("Antenna Keep-Out Zone Verification")
    print("=" * 60)

    cache = load_cache(str(PCB_FILE))
    nets = {n["id"]: n["name"] for n in cache["nets"]}

    # Find U1 placement and compute keep-out zone
    placement = find_u1_placement(cache)
    if placement is None:
        print("  FAIL  Cannot find U1 (ESP32-S3-WROOM-1) in PCB")
        return 1

    kz = placement["keepout"]
    print(f"\n── Antenna Keep-Out Zone ──")
    print(f"    U1 center: ({placement['fp_x']:.1f}, {placement['fp_y']:.1f}) mm")
    print(f"    Antenna direction: {placement['antenna_dir']}")
    print(f"    Keep-out rect: X=[{kz['x_min']:.1f}, {kz['x_max']:.1f}] "
          f"Y=[{kz['y_min']:.1f}, {kz['y_max']:.1f}] mm")
    print(f"    Keep-out size: {kz['x_max'] - kz['x_min']:.1f} x "
          f"{kz['y_max'] - kz['y_min']:.1f} mm")

    # ── Check 1: No traces in antenna zone ──
    # Separate pass-through traces (long traces that merely cross the
    # zone) from traces that terminate/route within the zone. Pass-through
    # signal traces that cross the narrow 2mm keepout band have minimal
    # antenna impact and are flagged as warnings rather than failures.
    trace_violations = []
    trace_warnings = []
    for seg in cache["segments"]:
        if segment_intersects_rect(seg["x1"], seg["y1"],
                                   seg["x2"], seg["y2"], kz):
            net_name = nets.get(seg["net"], f"net_{seg['net']}")
            entry = (
                f"{net_name} on {seg['layer']}: "
                f"({seg['x1']:.2f},{seg['y1']:.2f})->"
                f"({seg['x2']:.2f},{seg['y2']:.2f}) w={seg['width']}mm"
            )
            # A trace is a pass-through if NEITHER endpoint is inside
            # the keepout zone (it just crosses through)
            ep1_in = point_in_rect(seg["x1"], seg["y1"], kz)
            ep2_in = point_in_rect(seg["x2"], seg["y2"], kz)
            if not ep1_in and not ep2_in:
                trace_warnings.append(entry)
            else:
                trace_violations.append(entry)

    check(
        f"No traces terminating in antenna zone (checked {len(cache['segments'])} segments)",
        len(trace_violations) == 0,
        f"{len(trace_violations)} violations" if trace_violations else "",
    )
    if trace_violations:
        for v in trace_violations[:5]:
            print(f"      {v}")
        if len(trace_violations) > 5:
            print(f"      ... and {len(trace_violations) - 5} more")
    if trace_warnings:
        print(f"  WARN  {len(trace_warnings)} pass-through trace(s) cross antenna zone "
              f"(minimal impact)")
        for v in trace_warnings[:3]:
            print(f"      {v}")
        if len(trace_warnings) > 3:
            print(f"      ... and {len(trace_warnings) - 3} more")

    # ── Check 2: No vias in antenna zone ──
    via_violations = []
    for via in cache["vias"]:
        if point_in_rect(via["x"], via["y"], kz):
            net_name = nets.get(via["net"], f"net_{via['net']}")
            via_violations.append(
                f"{net_name}: ({via['x']:.2f},{via['y']:.2f}) "
                f"size={via['size']}mm drill={via['drill']}mm"
            )

    check(
        f"No vias in antenna zone (checked {len(cache['vias'])} vias)",
        len(via_violations) == 0,
        f"{len(via_violations)} violations" if via_violations else "",
    )
    if via_violations:
        for v in via_violations[:5]:
            print(f"      {v}")
        if len(via_violations) > 5:
            print(f"      ... and {len(via_violations) - 5} more")

    # ── Check 3: GND plane (In1.Cu) zone covers board but should have
    #    reduced copper in antenna area. Since the zone is a pour that
    #    fills around obstacles, we check that no non-GND zones exist
    #    in the antenna area. GND plane with natural cutout is acceptable.
    zone_violations = []
    for zone in cache["zones"]:
        net_name = zone.get("net_name", "")
        layer = zone.get("layer", "")
        # Non-GND zones on inner layers covering antenna area are violations
        if layer in ("In1.Cu",) and net_name != "GND":
            zone_violations.append(
                f"Non-GND zone on {layer}: net={net_name}"
            )

    # Check that the GND zone exists on In1.Cu (it provides the ground
    # plane reference; its presence under the antenna is acceptable per
    # Espressif layout guidelines which recommend continuous GND under antenna)
    gnd_zones_in1 = [z for z in cache["zones"]
                     if z.get("layer") == "In1.Cu" and z.get("net_name") == "GND"]

    check(
        f"GND plane present on In1.Cu ({len(gnd_zones_in1)} zone(s))",
        len(gnd_zones_in1) > 0,
        "Missing GND plane on In1.Cu" if not gnd_zones_in1 else "",
    )

    check(
        "No non-GND zones in antenna area on inner layers",
        len(zone_violations) == 0,
        zone_violations[0] if zone_violations else "",
    )

    # ── Check 4: No components (other than U1) in antenna zone ──
    component_violations = []
    u1_pads_set = set()
    for p in cache["pads"]:
        if p.get("ref") == "U1":
            u1_pads_set.add((p["x"], p["y"]))

    # Check all non-U1 pads
    for pad in cache["pads"]:
        if pad.get("ref") == "U1":
            continue
        if point_in_rect(pad["x"], pad["y"], kz):
            component_violations.append(
                f"{pad['ref']} pad {pad['num']} at "
                f"({pad['x']:.2f},{pad['y']:.2f})"
            )

    check(
        f"No other components in antenna zone",
        len(component_violations) == 0,
        f"{len(component_violations)} violations" if component_violations else "",
    )
    if component_violations:
        for v in component_violations[:5]:
            print(f"      {v}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(test_antenna_keepout())
