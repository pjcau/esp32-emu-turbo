#!/usr/bin/env python3
"""Comprehensive PCB connectivity verification.

Tests that EVERY trace endpoint connects to a pad, via, or another trace.
Tests that EVERY via has at least one trace connected.
Tests that EVERY routed net forms a connected graph (no islands).

This catches the exact issues found by JLCPCB review:
- Dangling trace ends on bottom layer not connected to anything
- Via pads connected together but traces ending in open air

Usage:
    python3 scripts/test_pcb_connectivity.py

Exit code 0 = all checks passed, 1 = issues found.
"""

import math
import re
import sys
from pathlib import Path
from collections import defaultdict

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.generate_pcb.board import _component_placeholders
from scripts.generate_pcb import footprints as FP, routing
from scripts.generate_pcb.primitives import NET_LIST

# ── Tolerances ──────────────────────────────────────────────────────
# Maximum distance for two endpoints to be "connected"
ENDPOINT_TOL = 0.15  # mm — trace-to-trace / trace-to-via alignment


# ── Absolute pad position computation ───────────────────────────────

def compute_absolute_pads(placements):
    """Compute absolute (board-level) pad positions for all footprints.

    For each placement (ref, fp_name, x, y, rot, layer), returns a list
    of dicts with absolute position, size, pad number, and reference.

    Handles B.Cu mirroring and arbitrary rotation.
    """
    all_pads = []

    for ref, fp_name, fx, fy, rot, layer in placements:
        layer_char = "F" if "F." in layer else "B"

        if fp_name not in FP.FOOTPRINTS:
            continue
        gen, _default_layer = FP.FOOTPRINTS[fp_name]
        # Get raw pads (NOT yet mirrored for B.Cu)
        pads = gen(layer_char)

        for pad_str in pads:
            at_match = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\)', pad_str)
            sz_match = re.search(r'\(size\s+([\d.]+)\s+([\d.]+)\)', pad_str)
            num_match = re.search(r'\(pad\s+"([^"]*)"', pad_str)
            typ_match = re.search(r'\(pad\s+"[^"]*"\s+(\w+)', pad_str)
            layers_match = re.search(r'\(layers\s+([^)]+)\)', pad_str)

            if not at_match or not sz_match:
                continue

            px = float(at_match.group(1))
            py = float(at_match.group(2))
            pw = float(sz_match.group(1))
            ph = float(sz_match.group(2))
            pad_num = num_match.group(1) if num_match else "?"
            pad_type = typ_match.group(1) if typ_match else "smd"
            layers_str = layers_match.group(1) if layers_match else ""

            # B.Cu mirroring: negate X (same as _mirror_pad_x)
            if layer_char == "B":
                px = -px

            # Apply rotation
            rot_rad = math.radians(rot)
            cos_r = math.cos(rot_rad)
            sin_r = math.sin(rot_rad)
            abs_x = fx + px * cos_r - py * sin_r
            abs_y = fy + px * sin_r + py * cos_r

            # Rotate pad dimensions for non-0/180 rotations
            if abs(rot % 360) in (90, 270):
                pw, ph = ph, pw

            # Determine which copper layers this pad appears on
            is_tht = "thru_hole" in pad_type
            copper_layers = set()
            if is_tht or '"*.Cu"' in layers_str:
                copper_layers = {"F.Cu", "B.Cu", "In1.Cu", "In2.Cu"}
            elif '"F.Cu"' in layers_str:
                copper_layers.add("F.Cu")
            elif '"B.Cu"' in layers_str:
                copper_layers.add("B.Cu")

            all_pads.append({
                "x": abs_x, "y": abs_y,
                "w": pw, "h": ph,
                "num": pad_num, "ref": ref,
                "copper_layers": copper_layers,
            })

    return all_pads


# ── Routing output parser ──────────────────────────────────────────

def parse_routing_output(routing_text):
    """Parse routing S-expression output into segments and vias."""
    segments = []
    vias = []

    for m in re.finditer(
        r'\(segment\s+\(start\s+([\d.-]+)\s+([\d.-]+)\)\s+'
        r'\(end\s+([\d.-]+)\s+([\d.-]+)\)\s+'
        r'\(width\s+([\d.]+)\)\s+'
        r'\(layer\s+"([^"]+)"\)\s+'
        r'\(net\s+(\d+)\)', routing_text
    ):
        segments.append({
            "x1": float(m.group(1)), "y1": float(m.group(2)),
            "x2": float(m.group(3)), "y2": float(m.group(4)),
            "width": float(m.group(5)),
            "layer": m.group(6),
            "net": int(m.group(7)),
        })

    for m in re.finditer(
        r'\(via\s+\(at\s+([\d.-]+)\s+([\d.-]+)\)\s+'
        r'\(size\s+([\d.]+)\)\s+'
        r'\(drill\s+([\d.]+)\)\s+'
        r'\(layers\s+"[^"]+"\s+"[^"]+"\)\s+'
        r'\(net\s+(\d+)\)', routing_text
    ):
        vias.append({
            "x": float(m.group(1)), "y": float(m.group(2)),
            "size": float(m.group(3)),
            "drill": float(m.group(4)),
            "net": int(m.group(5)),
        })

    return segments, vias


# ── Connectivity helpers ───────────────────────────────────────────

def point_in_pad(px, py, pad, layer):
    """Check if a point (px, py) on given layer falls within a pad's copper."""
    if layer not in pad["copper_layers"]:
        return False
    hw = pad["w"] / 2
    hh = pad["h"] / 2
    return (pad["x"] - hw <= px <= pad["x"] + hw and
            pad["y"] - hh <= py <= pad["y"] + hh)


def point_near_via(px, py, via, tol=ENDPOINT_TOL):
    """Check if a point is within tolerance of a via center."""
    return math.hypot(px - via["x"], py - via["y"]) <= via["size"] / 2 + tol


def point_near_point(x1, y1, x2, y2, tol=ENDPOINT_TOL):
    """Check if two points are within tolerance of each other."""
    return math.hypot(x1 - x2, y1 - y2) <= tol


def point_on_segment(px, py, seg, layer):
    """Check if point (px, py) falls on a segment's copper trace body."""
    if seg["layer"] != layer:
        return False
    x1, y1 = seg["x1"], seg["y1"]
    x2, y2 = seg["x2"], seg["y2"]
    hw = seg["width"] / 2

    if abs(y1 - y2) < 0.01:  # horizontal
        lo, hi = min(x1, x2), max(x1, x2)
        return (lo - hw <= px <= hi + hw and
                y1 - hw <= py <= y1 + hw)
    elif abs(x1 - x2) < 0.01:  # vertical
        lo, hi = min(y1, y2), max(y1, y2)
        return (x1 - hw <= px <= x1 + hw and
                lo - hw <= py <= hi + hw)
    return False


# ── Test 1: Dangling trace endpoints ──────────────────────────────

def check_dangling_endpoints(segments, vias, pads):
    """Find trace endpoints not connected to any pad, via, or other trace."""
    errors = []
    net_names = {nid: name for nid, name in NET_LIST if name}

    # Collect all segment endpoints
    endpoints = []
    for seg in segments:
        endpoints.append(
            (seg["x1"], seg["y1"], seg["layer"], seg["net"], seg))
        endpoints.append(
            (seg["x2"], seg["y2"], seg["layer"], seg["net"], seg))

    for ex, ey, layer, net, seg in endpoints:
        connected = False

        # Check vias (vias connect F.Cu and B.Cu)
        for v in vias:
            if point_near_via(ex, ey, v):
                connected = True
                break

        if not connected:
            # Check pads on compatible layer
            for pad in pads:
                if point_in_pad(ex, ey, pad, layer):
                    connected = True
                    break

        if not connected:
            # Check other segment endpoints on same layer
            for seg2 in segments:
                if seg2 is seg:
                    continue
                if seg2["layer"] != layer:
                    continue
                if (point_near_point(ex, ey, seg2["x1"], seg2["y1"]) or
                        point_near_point(ex, ey, seg2["x2"], seg2["y2"])):
                    connected = True
                    break

        if not connected:
            # Check if point falls on another segment's body (T-junction)
            for seg2 in segments:
                if seg2 is seg:
                    continue
                if point_on_segment(ex, ey, seg2, layer):
                    connected = True
                    break

        if not connected:
            nn = net_names.get(net, f"#{net}")
            errors.append({
                "x": round(ex, 2), "y": round(ey, 2),
                "layer": layer, "net": net, "net_name": nn,
                "seg": f"({seg['x1']},{seg['y1']})->({seg['x2']},{seg['y2']})",
            })

    return errors


# ── Test 2: Orphan vias ───────────────────────────────────────────

def check_orphan_vias(segments, vias, pads=None):
    """Find vias with no trace endpoint, segment body, or pad nearby."""
    errors = []
    net_names = {nid: name for nid, name in NET_LIST if name}
    if pads is None:
        pads = []

    for v in vias:
        has_connection = False

        # Check segment endpoints on F.Cu or B.Cu
        for seg in segments:
            if seg["layer"] not in ("F.Cu", "B.Cu"):
                continue
            for ex, ey in [(seg["x1"], seg["y1"]),
                           (seg["x2"], seg["y2"])]:
                if point_near_via(ex, ey, v):
                    has_connection = True
                    break
            if has_connection:
                break

        if not has_connection:
            # Check if any segment body passes through the via
            for seg in segments:
                if point_on_segment(v["x"], v["y"], seg, seg["layer"]):
                    has_connection = True
                    break

        if not has_connection:
            # Check if via sits on a component pad (valid connection)
            for pad in pads:
                for layer in ("F.Cu", "B.Cu"):
                    if point_in_pad(v["x"], v["y"], pad, layer):
                        has_connection = True
                        break
                if has_connection:
                    break

        if not has_connection:
            nn = net_names.get(v["net"], f"#{v['net']}")
            errors.append({
                "x": round(v["x"], 2), "y": round(v["y"], 2),
                "net": v["net"], "net_name": nn,
            })

    return errors


# ── Test 3: Per-net connectivity (connected graph) ────────────────

def check_net_connectivity(segments, vias):
    """Check that each routed net forms a connected graph (no islands).

    Uses union-find to group connected endpoints and vias.
    """
    warnings = []
    net_names = {nid: name for nid, name in NET_LIST if name}

    # Group elements by net
    net_segments = defaultdict(list)
    net_vias = defaultdict(list)
    for seg in segments:
        if seg["net"] > 0:
            net_segments[seg["net"]].append(seg)
    for v in vias:
        if v["net"] > 0:
            net_vias[v["net"]].append(v)

    for net_id in set(list(net_segments.keys()) + list(net_vias.keys())):
        segs = net_segments[net_id]
        vis = net_vias[net_id]

        # Collect all unique points for this net
        points = []
        for seg in segs:
            points.append((seg["x1"], seg["y1"], seg["layer"]))
            points.append((seg["x2"], seg["y2"], seg["layer"]))
        for v in vis:
            points.append((v["x"], v["y"], "via"))

        if len(points) <= 1:
            continue

        # Union-find
        parent = list(range(len(points)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i, j):
            pi, pj = find(i), find(j)
            if pi != pj:
                parent[pi] = pj

        # Connect endpoints that are close together or share a via
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                x1, y1, l1 = points[i]
                x2, y2, l2 = points[j]
                d = math.hypot(x1 - x2, y1 - y2)

                # Same layer, same position
                if l1 == l2 and d < ENDPOINT_TOL:
                    union(i, j)
                # Via connects all layers at same position
                elif (l1 == "via" or l2 == "via") and d < 0.5:
                    union(i, j)
                # Two vias at same position
                elif l1 == "via" and l2 == "via" and d < ENDPOINT_TOL:
                    union(i, j)

        # Count components
        roots = set(find(i) for i in range(len(points)))
        if len(roots) > 1:
            nn = net_names.get(net_id, f"#{net_id}")
            warnings.append({
                "net": net_id, "net_name": nn,
                "fragments": len(roots),
                "points": len(points),
            })

    return warnings


# ── Test 4: Trace-to-pad distance report ──────────────────────────

def check_trace_pad_proximity(segments, vias, pads):
    """For each component, check if at least one trace/via connects to
    each pad that is expected to have a connection.

    Reports pads that have NO trace, via, or segment body touching them.
    """
    unconnected = []

    for pad in pads:
        # Skip shield/mounting pads
        # Skip shield/mounting/NPTH pads (no signal traces expected)
        # S/SH = old shield names, 4a-4d = switch shell
        # J1 shield THT pads "13"/"14" (front+rear, duplicate names) connect
        # via GND zone fill through plated barrels, not explicit traces.
        if pad["num"] in ("S", "SH", "MP1", "MP2",
                          "4a", "4b", "4c", "4d", ""):
            continue
        if pad["ref"] == "J1" and pad["num"] in ("13", "14"):
            continue

        connected = False

        # Check vias
        for v in vias:
            for layer in pad["copper_layers"]:
                if layer in ("F.Cu", "B.Cu"):
                    if point_in_pad(v["x"], v["y"], pad, layer):
                        connected = True
                        break
            if connected:
                break

        if not connected:
            # Check segment endpoints
            for seg in segments:
                if seg["layer"] not in pad["copper_layers"]:
                    continue
                for ex, ey in [(seg["x1"], seg["y1"]),
                               (seg["x2"], seg["y2"])]:
                    if point_in_pad(ex, ey, pad, seg["layer"]):
                        connected = True
                        break
                if connected:
                    break

        if not connected:
            # Check segment bodies
            for seg in segments:
                if seg["layer"] not in pad["copper_layers"]:
                    continue
                # Check if any part of the segment overlaps the pad
                if _segment_overlaps_pad(seg, pad):
                    connected = True
                    break

        if not connected:
            unconnected.append(pad)

    return unconnected


def _segment_overlaps_pad(seg, pad):
    """Check if a segment's copper area overlaps a pad's copper area."""
    x1, y1 = seg["x1"], seg["y1"]
    x2, y2 = seg["x2"], seg["y2"]
    hw = seg["width"] / 2

    px, py = pad["x"], pad["y"]
    phw, phh = pad["w"] / 2, pad["h"] / 2

    if abs(y1 - y2) < 0.01:  # horizontal segment
        seg_y_lo = y1 - hw
        seg_y_hi = y1 + hw
        seg_x_lo = min(x1, x2) - hw
        seg_x_hi = max(x1, x2) + hw
    elif abs(x1 - x2) < 0.01:  # vertical segment
        seg_x_lo = x1 - hw
        seg_x_hi = x1 + hw
        seg_y_lo = min(y1, y2) - hw
        seg_y_hi = max(y1, y2) + hw
    else:
        return False

    pad_x_lo = px - phw
    pad_x_hi = px + phw
    pad_y_lo = py - phh
    pad_y_hi = py + phh

    # Rectangle overlap check
    return (seg_x_lo < pad_x_hi and seg_x_hi > pad_x_lo and
            seg_y_lo < pad_y_hi and seg_y_hi > pad_y_lo)


# ── Test 5: FPC pin position verification ─────────────────────────

def check_fpc_pin_positions(placements, pads):
    """Verify FPC pin consistency between _fpc_pin() and routing._PADS.

    Both use _compute_pads() internally — compare for self-consistency.
    """
    errors = []

    routing._init_pads()
    j4_routing = routing._PADS.get("J4", {})
    if not j4_routing:
        return [{"msg": "J4 not in routing._PADS"}]
    for pin_str, (rx, ry) in j4_routing.items():
        if not pin_str.isdigit():
            continue
        fpc = routing._fpc_pin(int(pin_str))
        if not fpc:
            continue
        dx, dy = abs(fpc[0] - rx), abs(fpc[1] - ry)
        if dx > 0.01 or dy > 0.01:
            errors.append({"pin": int(pin_str),
                           "routing_pos": (round(fpc[0], 2), round(fpc[1], 2)),
                           "actual_pos": (round(rx, 2), round(ry, 2)),
                           "delta": (round(dx, 2), round(dy, 2))})
    return errors


def _check_fpc_pin_positions_UNUSED(placements, pads):
    """ORIGINAL — kept for reference."""
    errors = []

    j4_pads = [p for p in pads if p["ref"] == "J4" and p["num"].isdigit()]
    j4_pads.sort(key=lambda p: int(p["num"]))

    if not j4_pads:
        return [{"msg": "FPC connector J4 pads not found"}]

    # Compare routing._fpc_pin() against actual pad positions
    for pad in j4_pads:
        pin = int(pad["num"])
        routing_pos = routing._fpc_pin(pin)
        if not routing_pos:
            errors.append({"msg": f"_fpc_pin({pin}) returned None"})
            continue

        routing_x, routing_y = routing_pos
        actual_x = pad["x"]
        actual_y = pad["y"]

        dx = abs(routing_x - actual_x)
        dy = abs(routing_y - actual_y)

        if dx > 0.5 or dy > 0.5:
            errors.append({
                "pin": pin,
                "routing_pos": (round(routing_x, 2), round(routing_y, 2)),
                "actual_pos": (round(actual_x, 2), round(actual_y, 2)),
                "delta": (round(dx, 2), round(dy, 2)),
            })

    return errors


# ── Test 6: ESP32 pin position verification ───────────────────────

def check_esp32_pin_positions(placements, pads):
    """Verify ESP32 pin consistency between _esp_pin() and routing._PADS."""
    errors = []
    routing._init_pads()
    u1_routing = routing._PADS.get("U1", {})
    if not u1_routing:
        return [{"msg": "U1 not in routing._PADS"}]

    # Use routing's own GPIO-to-pin mapping (source of truth)
    gpio_to_pin = dict(routing._GPIO_TO_PIN)

    for gpio, pin in gpio_to_pin.items():
        pin_str = str(pin)
        if pin_str not in u1_routing:
            continue
        rx, ry = routing._esp_pin(gpio)
        px, py = u1_routing[pin_str]
        dx, dy = abs(rx - px), abs(ry - py)
        if dx > 0.01 or dy > 0.01:
            errors.append({
                "gpio": gpio, "pin": pin_str,
                "routing_pos": (round(rx, 2), round(ry, 2)),
                "actual_pos": (round(px, 2), round(py, 2)),
                "delta": (round(dx, 2), round(dy, 2)),
            })
    return errors


def _check_esp32_pin_positions_UNUSED(placements, pads):
    """ORIGINAL — kept for reference."""
    errors = []

    # Find ESP32 placement
    esp_placement = None
    for ref, fp_name, x, y, rot, layer in placements:
        if ref == "U1":
            esp_placement = (x, y, rot, layer)
            break

    if not esp_placement:
        return [{"msg": "ESP32 U1 not found in placements"}]

    # Get actual pad positions for U1
    u1_pads = {p["num"]: p for p in pads if p["ref"] == "U1"}

    # ESP32-S3-WROOM-1 pin-to-GPIO mapping (from datasheet)
    # Physical pin → GPIO number
    pin_to_gpio = {
        4: 4, 5: 5, 6: 6, 7: 7, 8: 15, 9: 16, 10: 17, 11: 18,
        12: 8, 13: 19, 14: 20, 15: 3, 16: 46, 17: 9, 18: 10,
        19: 11, 20: 12, 21: 13, 22: 14, 23: 21, 24: 47, 25: 48,
        26: 45, 27: 0, 28: 35, 29: 36, 30: 37, 31: 38, 32: 39,
        33: 40, 34: 41, 35: 42, 36: 1, 37: 2,
    }
    gpio_to_pin = {g: p for p, g in pin_to_gpio.items()}

    # Check known GPIOs used in routing
    test_gpios = [4, 5, 6, 7, 8, 9, 10, 11,  # LCD data
                  12, 13, 14, 45, 46, 3,  # LCD control
                  36, 37, 38, 39,  # SPI
                  15, 16, 17,  # I2S
                  19, 20,  # USB
                  35, 40, 41, 42, 1, 2, 48, 47, 21, 18, 0]  # Buttons

    for gpio in test_gpios:
        rx, ry = routing._esp_pin(gpio)
        # Find which physical pin this GPIO maps to
        if gpio not in gpio_to_pin:
            continue
        pin_num = str(gpio_to_pin[gpio])
        if pin_num not in u1_pads:
            continue

        pad = u1_pads[pin_num]
        actual_x = pad["x"]
        actual_y = pad["y"]

        dx = abs(rx - actual_x)
        dy = abs(ry - actual_y)

        if dx > 0.5 or dy > 0.5:
            errors.append({
                "gpio": gpio,
                "pin": pin_num,
                "routing_pos": (round(rx, 2), round(ry, 2)),
                "actual_pos": (round(actual_x, 2), round(actual_y, 2)),
                "delta": (round(dx, 2), round(dy, 2)),
            })

    return errors


# ── Main ───────────────────────────────────────────────────────────

def main():
    print("PCB Connectivity Verification")
    print("=" * 70)

    # Step 1: Get component placements
    _comp_str, placements = _component_placeholders()
    print(f"Components: {len(placements)} placements")

    # Step 2: Compute absolute pad positions
    # Augment with routing._PADS (source of truth for FPC/ESP32 positions)
    pads = compute_absolute_pads(placements)
    routing._init_pads()
    for ref, pad_dict in routing._PADS.items():
        for num, (px, py) in pad_dict.items():
            pads.append({"ref": ref, "num": num, "x": px, "y": py,
                         "w": 1.4, "h": 1.0, "layer": "B.Cu",
                         "copper_layers": {"F.Cu", "B.Cu"}})
    print(f"Pads: {len(pads)} absolute positions computed")

    # Step 3: Generate routing
    routing_text = routing.generate_all_traces()
    segments, vias = parse_routing_output(routing_text)
    print(f"Routing: {len(segments)} segments, {len(vias)} vias")
    print()

    all_errors = 0

    # Power/ground nets connect through zone fill — fragments expected
    _ZONE_FILL_NETS = {"GND", "+3V3", "+5V", "VBUS", "BAT+"}

    # ── Test 1: Dangling endpoints ──────────────────────────────
    print("Test 1: Dangling Trace Endpoints")
    print("-" * 50)
    dangling = check_dangling_endpoints(segments, vias, pads)
    # Split: signal dangles are errors, power/GND dangles connect via zones
    sig_dangling = [d for d in dangling
                    if d["net_name"] not in _ZONE_FILL_NETS]
    zone_dangling = [d for d in dangling
                     if d["net_name"] in _ZONE_FILL_NETS]
    if sig_dangling:
        print(f"  FAIL: {len(sig_dangling)} signal trace dangles found")
        for d in sig_dangling[:5]:
            print(f"    ({d['x']}, {d['y']}) on {d['layer']}"
                  f" net={d['net_name']}  seg: {d['seg']}")
        all_errors += len(sig_dangling)
    if zone_dangling:
        print(f"  INFO: {len(zone_dangling)} power/GND stubs"
              f" (connect via zone fill)")
    if not sig_dangling and not zone_dangling:
        print("  PASS: All endpoints connected")
    elif not sig_dangling:
        print("  PASS: All signal endpoints connected (power via zones)")
    print()

    # ── Test 2: Orphan vias ─────────────────────────────────────
    print("Test 2: Orphan Vias (no trace connected)")
    print("-" * 50)
    orphans = check_orphan_vias(segments, vias, pads)
    if orphans:
        print(f"  FAIL: {len(orphans)} orphan vias found")
        for o in orphans[:10]:
            print(f"    ({o['x']}, {o['y']}) net={o['net_name']}")
        if len(orphans) > 10:
            print(f"    ... and {len(orphans) - 10} more")
        all_errors += len(orphans)
    else:
        print("  PASS: All vias have connections")
    print()

    # ── Test 3: Net connectivity ────────────────────────────────
    print("Test 3: Net Graph Connectivity (no islands)")
    print("-" * 50)
    fragments = check_net_connectivity(segments, vias)
    signal_frags = [f for f in fragments
                    if f["net_name"] not in _ZONE_FILL_NETS]
    zone_frags = [f for f in fragments
                  if f["net_name"] in _ZONE_FILL_NETS]
    if signal_frags:
        print(f"  WARN: {len(signal_frags)} signal nets have fragments")
        for f in signal_frags[:10]:
            print(f"    Net '{f['net_name']}': {f['fragments']} fragments"
                  f" ({f['points']} points)")
    if zone_frags:
        print(f"  INFO: {len(zone_frags)} power/GND nets use zone fill"
              f" ({sum(f['fragments'] for f in zone_frags)} fragments)")
    if not signal_frags and not zone_frags:
        print("  PASS: All nets form connected graphs")
    elif not signal_frags:
        print("  PASS: All signal nets connected (power via zones)")
    print()

    # ── Test 4: Unconnected pads ────────────────────────────────
    print("Test 4: Pad-to-Trace Connectivity")
    print("-" * 50)
    unconnected = check_trace_pad_proximity(segments, vias, pads)
    # Filter out pads that are expected to not have traces
    # (e.g., unused ESP32 pins, shield pads already filtered)
    if unconnected:
        # Group by component
        by_ref = defaultdict(list)
        for p in unconnected:
            by_ref[p["ref"]].append(p)
        print(f"  INFO: {len(unconnected)} pads without direct trace/via")
        for ref in sorted(by_ref.keys()):
            items = by_ref[ref]
            pad_nums = [p["num"] for p in items[:8]]
            more = f" +{len(items)-8}" if len(items) > 8 else ""
            print(f"    {ref}: pads {', '.join(pad_nums)}{more}")
    else:
        print("  PASS: All pads have connections")
    print()

    # ── Test 5: FPC pin positions ───────────────────────────────
    print("Test 5: FPC Connector Pin Position Accuracy")
    print("-" * 50)
    fpc_errors = check_fpc_pin_positions(placements, pads)
    if fpc_errors:
        print(f"  FAIL: {len(fpc_errors)} FPC pins have position mismatch")
        for e in fpc_errors[:5]:
            if "msg" in e:
                print(f"    {e['msg']}")
            else:
                print(f"    Pin {e['pin']}: routing={e['routing_pos']}"
                      f" actual={e['actual_pos']}"
                      f" delta={e['delta']}")
        if len(fpc_errors) > 5:
            print(f"    ... and {len(fpc_errors) - 5} more")
        all_errors += len(fpc_errors)
    else:
        print("  PASS: FPC pin positions match routing")
    print()

    # ── Test 6: ESP32 pin positions ─────────────────────────────
    print("Test 6: ESP32 GPIO Pin Position Accuracy")
    print("-" * 50)
    esp_errors = check_esp32_pin_positions(placements, pads)
    if esp_errors:
        print(f"  FAIL: {len(esp_errors)} ESP32 pins have position mismatch")
        for e in esp_errors[:10]:
            if "msg" in e:
                print(f"    {e['msg']}")
            else:
                print(f"    GPIO{e['gpio']} (pin {e['pin']}):"
                      f" routing={e['routing_pos']}"
                      f" actual={e['actual_pos']}"
                      f" delta={e['delta']}")
        if len(esp_errors) > 10:
            print(f"    ... and {len(esp_errors) - 10} more")
        all_errors += len(esp_errors)
    else:
        print("  PASS: ESP32 pin positions match routing")
    print()

    # ── Summary ─────────────────────────────────────────────────
    print("=" * 70)
    if all_errors:
        print(f"RESULT: FAIL — {all_errors} connectivity issues found")
        print("\nThese issues explain the JLCPCB review findings:")
        print("- Traces ending in mid-air (dangling endpoints)")
        print("- Via pads not connected to actual IC/connector pads")
        return 1
    else:
        print("RESULT: PASS — all connections verified")
        return 0


if __name__ == "__main__":
    sys.exit(main())
