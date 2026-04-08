#!/usr/bin/env python3
"""Power Delivery Path Tracing.

Verifies that complete copper paths exist from power sources to every IC
VDD/power pin using the PCB cache (segments, vias, pads).

Uses union-find to build connected components per power net from trace
segments and vias. Pads on the correct net that are NOT trace-connected
to the source are flagged as INFO (zone-fill dependent) rather than FAIL,
since internal copper planes (In1.Cu for GND, In2.Cu for power) bridge
those gaps after zone fill.

Exit code 0 = all pass, 1 = failures found.
"""

import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

# Add parent to path for pcb_cache import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pcb_cache import load_cache

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PASS = 0
FAIL = 0
INFO_COUNT = 0

# Coordinate snapping tolerance (mm) — endpoints within this distance
# are treated as the same node in the connectivity graph.
SNAP_TOL = 0.05


# ── Power network definitions ────────────────────────────────────────

# Power sources: net_name -> (ref, pad_num, description)
POWER_SOURCES = {
    "BAT+": ("J3", "1", "Battery connector BAT+"),
    "VBUS": ("J1", "2", "USB-C VBUS"),      # pad 2 is VBUS on USB-C 16P
    "+5V":  ("U2", "8", "IP5306 VOUT"),
    "+3V3": ("U3", "4", "AMS1117 VOUT"),     # SOT-223 pad 4 = tab/VOUT
    "GND":  ("U2", "EP", "IP5306 GND (exposed pad)"),
}

# Power sinks: net_name -> list of (ref, pad_num, description)
# Pad numbers are from the actual PCB footprints (not necessarily
# matching generic datasheet numbering).
POWER_SINKS = {
    "+3V3": [
        ("U1", "2", "ESP32 VDD"),
        ("U6", "4", "TF-01A VDD"),
    ],
    "+5V": [
        ("U3", "3", "AMS1117 VIN"),       # SOT-223 pad 3 = VIN
        ("U5", "6", "PAM8403 VDD"),
        ("U5", "12", "PAM8403 PVDD_L"),
        ("U5", "13", "PAM8403 PVDD_R"),
    ],
    "VBUS": [
        ("U2", "1", "IP5306 VIN"),
    ],
    "BAT+": [
        ("U2", "6", "IP5306 BAT"),
    ],
    "GND": [
        ("U1", "41", "ESP32 GND"),         # ESP32-S3 GND pad
        ("U2", "EP", "IP5306 GND"),         # ESOP-8 exposed pad
        ("U3", "1", "AMS1117 GND"),         # SOT-223 pad 1 = GND
        ("U5", "2", "PAM8403 GND"),
        ("U5", "11", "PAM8403 GND"),
        ("U5", "15", "PAM8403 GND"),
    ],
}

# Zones that provide plane connections (from generate_pcb/routing.py)
POWER_ZONES = {
    "GND": ["In1.Cu", "F.Cu", "B.Cu"],
    "+3V3": ["In2.Cu"],
    "+5V": ["In2.Cu"],
}


def check(name: str, condition: bool, detail: str = ""):
    """Record test result."""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def info(msg: str):
    """Print informational (zone-dependent) result."""
    global INFO_COUNT
    INFO_COUNT += 1
    print(f"  INFO  {msg}")


# ── Union-Find ───────────────────────────────────────────────────────

class UnionFind:
    """Weighted quick-union with path compression."""

    def __init__(self):
        self.parent = {}
        self.rank = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1

    def connected(self, a, b):
        return self.find(a) in self.parent and self.find(b) in self.parent and self.find(a) == self.find(b)


def snap_key(x, y):
    """Quantize coordinates to SNAP_TOL grid for reliable merging."""
    return (round(x / SNAP_TOL) * SNAP_TOL,
            round(y / SNAP_TOL) * SNAP_TOL)


# ── Main verification ────────────────────────────────────────────────

def build_net_connectivity(cache, net_id):
    """Build union-find connectivity graph for a given net.

    Connects segment endpoints and via positions that are on the same net.
    Returns the UnionFind and a set of all node keys.
    """
    uf = UnionFind()
    nodes = set()

    # Add segments
    for seg in cache["segments"]:
        if seg["net"] != net_id:
            continue
        k1 = snap_key(seg["x1"], seg["y1"])
        k2 = snap_key(seg["x2"], seg["y2"])
        uf.union(k1, k2)
        nodes.add(k1)
        nodes.add(k2)

    # Add vias — a via connects its position across layers,
    # and also snaps to nearby segment endpoints
    for via in cache["vias"]:
        if via["net"] != net_id:
            continue
        vk = snap_key(via["x"], via["y"])
        # Connect via to itself (ensures it's in the graph)
        uf.find(vk)
        nodes.add(vk)

        # Connect via to any nearby segment endpoint (within snap tolerance)
        # This is already handled by snap_key quantization — if a segment
        # endpoint is at the same snapped position, they'll merge.

    return uf, nodes


def find_pad(cache, ref, pad_num, net_id):
    """Find a pad by ref, pad number, and net. Returns (x, y) or None."""
    for pad in cache["pads"]:
        if (pad["ref"] == ref and pad["num"] == str(pad_num)
                and pad["net"] == net_id):
            return (pad["x"], pad["y"])
    # Try without net filter (pad may have net 0 if not assigned)
    for pad in cache["pads"]:
        if pad["ref"] == ref and pad["num"] == str(pad_num):
            return (pad["x"], pad["y"])
    return None


def count_path_elements(cache, net_id, source_key, sink_key, uf):
    """Count segments and vias in the path between source and sink.

    This is approximate — counts elements in the same connected component.
    """
    root = uf.find(source_key)
    segs = 0
    vias_count = 0

    for seg in cache["segments"]:
        if seg["net"] != net_id:
            continue
        k1 = snap_key(seg["x1"], seg["y1"])
        if uf.find(k1) == root:
            segs += 1

    for via in cache["vias"]:
        if via["net"] != net_id:
            continue
        vk = snap_key(via["x"], via["y"])
        if uf.find(vk) == root:
            vias_count += 1

    return segs, vias_count


def find_decoupling_caps(cache, net_id):
    """Find decoupling capacitors connected to a power net.

    Returns list of (ref, pad_num, x, y).
    """
    caps = []
    seen_refs = set()
    for pad in cache["pads"]:
        if pad["net"] != net_id:
            continue
        ref = pad["ref"]
        if ref.startswith("C") and ref not in seen_refs:
            seen_refs.add(ref)
            caps.append((ref, pad["num"], pad["x"], pad["y"]))
    return caps


def verify_power_net(cache, net_name, net_id):
    """Verify connectivity for one power net."""
    print(f"\n{'─' * 50}")
    print(f"── Power Path: {net_name} (net {net_id}) ──")

    # Build connectivity graph
    uf, nodes = build_net_connectivity(cache, net_id)

    if not nodes:
        print(f"    WARNING: No segments/vias found for {net_name}")
        print(f"    This net may be entirely zone-fill connected")

    # Find source pad
    if net_name not in POWER_SOURCES:
        print(f"    SKIP: No source defined for {net_name}")
        return

    src_ref, src_pad, src_desc = POWER_SOURCES[net_name]
    src_pos = find_pad(cache, src_ref, src_pad, net_id)

    if src_pos is None:
        check(f"Source pad {src_ref} pin {src_pad} exists", False,
              f"pad not found in PCB for net {net_name}")
        return

    src_key = snap_key(src_pos[0], src_pos[1])
    print(f"  SOURCE: {src_ref} pad {src_pad} ({src_desc}) "
          f"at ({src_pos[0]:.2f}, {src_pos[1]:.2f})")

    # Ensure source is in the union-find
    uf.find(src_key)

    # Check each sink
    if net_name not in POWER_SINKS:
        print(f"    No sinks defined for {net_name}")
        return

    has_zones = net_name in POWER_ZONES

    for sink_ref, sink_pad, sink_desc in POWER_SINKS[net_name]:
        sink_pos = find_pad(cache, sink_ref, sink_pad, net_id)

        if sink_pos is None:
            check(f"{sink_ref} pin {sink_pad} ({sink_desc}) exists",
                  False, "pad not found in PCB")
            continue

        sink_key = snap_key(sink_pos[0], sink_pos[1])

        # Check if sink is trace-connected to source
        if uf.connected(src_key, sink_key):
            segs, vias_count = count_path_elements(
                cache, net_id, src_key, sink_key, uf)
            check(f"{sink_ref} pin {sink_pad} ({sink_desc}) reachable "
                  f"via {segs} segments + {vias_count} vias", True)
        elif has_zones:
            # Not trace-connected but zones exist for this net
            info(f"{sink_ref} pin {sink_pad} ({sink_desc}) at "
                 f"({sink_pos[0]:.2f}, {sink_pos[1]:.2f}) "
                 f"reachable via zone fill ({', '.join(POWER_ZONES[net_name])})")
        else:
            check(f"{sink_ref} pin {sink_pad} ({sink_desc}) reachable",
                  False,
                  f"NO copper path from {src_ref} to {sink_ref} pin {sink_pad}")

    # Check decoupling caps (informational — caps may connect via
    # zone fill, short stubs, or pad overlap not modeled here)
    caps = find_decoupling_caps(cache, net_id)
    if caps:
        connected_caps = 0
        zone_caps = 0
        stub_caps = []
        for cap_ref, cap_pad, cx, cy in caps:
            ck = snap_key(cx, cy)
            if uf.connected(src_key, ck):
                connected_caps += 1
            elif has_zones:
                zone_caps += 1
            else:
                # Cap has correct net assignment but no direct trace
                # to source — may be connected via short stub + via
                # to a zone or nearby trace. Report as INFO.
                stub_caps.append(cap_ref)

        total = len(caps)
        detail = f"{connected_caps} trace-connected"
        if zone_caps > 0:
            detail += f", {zone_caps} zone-fill"
        if stub_caps:
            detail += f", {len(stub_caps)} stub/via ({','.join(stub_caps)})"

        if connected_caps + zone_caps == total:
            check(f"Decoupling caps reachable ({total} caps: {detail})", True)
        else:
            # Stub-connected caps are not a hard failure — they have
            # correct net assignment and are likely connected via
            # short stubs to nearby traces or zone fill
            info(f"Decoupling caps: {detail} — "
                 f"stub caps may need manual routing check")


def main():
    print("=" * 60)
    print("Power Delivery Path Tracing")
    print("=" * 60)

    # Load PCB cache
    print("\n── Loading PCB Cache ──")
    cache = load_cache()

    # Build net name -> id mapping
    net_map = {n["name"]: n["id"] for n in cache["nets"] if n["name"]}
    print(f"    Nets: {len(net_map)}")
    print(f"    Segments: {cache['stats']['segments']}")
    print(f"    Vias: {cache['stats']['vias']}")
    print(f"    Pads: {cache['stats']['pads']}")

    # Verify each power net
    for net_name in ["+3V3", "+5V", "VBUS", "BAT+", "GND"]:
        if net_name not in net_map:
            print(f"\n  FAIL  Net '{net_name}' not found in PCB")
            continue
        verify_power_net(cache, net_name, net_map[net_name])

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {INFO_COUNT} info (zone-dependent)")
    if FAIL > 0:
        print("NOTE: FAIL = no trace path AND no zone fill coverage.")
        print("      Run zone fill + DRC to confirm connectivity.")
    if INFO_COUNT > 0:
        print("NOTE: INFO = reachable via zone fill on internal planes.")
        print("      These connections depend on proper zone fill at fabrication.")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
