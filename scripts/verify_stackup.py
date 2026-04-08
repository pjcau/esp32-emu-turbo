#!/usr/bin/env python3
"""Stackup Layer-Net Verification for 4-layer PCB.

Verifies the 4-layer stackup follows JLCPCB conventions:
  F.Cu  (Layer 1): Signal + components — no power/GND zones
  In1.Cu (Layer 2): GND plane — all zones must be GND only
  In2.Cu (Layer 3): Power plane — zones must be +3V3, +5V, or VBUS only
  B.Cu  (Layer 4): Signal + components — no power/GND zones

Also checks that no signal traces exist on inner layers (In1.Cu, In2.Cu).
"""

import json
import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"

sys.path.insert(0, str(BASE / "scripts"))
from pcb_cache import load_cache

# ── Expected stackup assignments ────────────────────────────────
# Inner layer zone net assignments
IN1_ALLOWED_NETS = {"GND"}
IN2_ALLOWED_NETS = {"+3V3", "+5V", "VBUS"}

# Power/GND nets that should NOT have large zones on signal layers
POWER_GND_NETS = {"GND", "+3V3", "+5V", "VBUS", "BAT+"}

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


def parse_zones_from_pcb():
    """Parse zone definitions directly from the PCB file.

    Returns list of dicts with net, net_name, layer, priority.
    """
    pcb_text = PCB_FILE.read_text()
    zones = []

    # Match zone blocks: (zone\n  (net N)\n  (net_name "XXX")\n  (layer "YYY")
    # Zones in KiCad s-expression format
    zone_pattern = re.compile(
        r'\(zone\s*\n'
        r'\s*\(net\s+(\d+)\)\s*\n'
        r'\s*\(net_name\s+"([^"]+)"\)\s*\n'
        r'\s*\(layer\s+"([^"]+)"\)',
        re.MULTILINE,
    )

    for m in zone_pattern.finditer(pcb_text):
        zones.append({
            "net_id": int(m.group(1)),
            "net_name": m.group(2),
            "layer": m.group(3),
        })

    return zones


def test_stackup():
    """Run all stackup layer-net verification checks."""
    print("=" * 60)
    print("Stackup Layer-Net Verification")
    print("=" * 60)

    cache = load_cache(str(PCB_FILE))
    nets = {n["id"]: n["name"] for n in cache["nets"]}

    # Parse zones from both cache and PCB file for completeness
    cache_zones = cache.get("zones", [])
    pcb_zones = parse_zones_from_pcb()

    # Use PCB file zones as primary (more detailed)
    zones = pcb_zones if pcb_zones else cache_zones

    print(f"\n── Zone Assignments ──")
    for z in zones:
        net_name = z.get("net_name", "?")
        layer = z.get("layer", "?")
        print(f"    {layer}: {net_name}")

    # ── Check 1: All In1.Cu zones are GND ──
    print(f"\n── In1.Cu (GND Plane) ──")
    in1_zones = [z for z in zones if z["layer"] == "In1.Cu"]
    in1_violations = [z for z in in1_zones
                      if z["net_name"] not in IN1_ALLOWED_NETS]

    check(
        f"All In1.Cu zones are GND ({len(in1_zones)} zone(s))",
        len(in1_violations) == 0 and len(in1_zones) > 0,
        (f"Non-GND zones: {[z['net_name'] for z in in1_violations]}"
         if in1_violations else "No GND zone found on In1.Cu"),
    )

    # ── Check 2: All In2.Cu zones are power nets ──
    print(f"\n── In2.Cu (Power Plane) ──")
    in2_zones = [z for z in zones if z["layer"] == "In2.Cu"]
    in2_violations = [z for z in in2_zones
                      if z["net_name"] not in IN2_ALLOWED_NETS]

    check(
        f"All In2.Cu zones are power nets ({len(in2_zones)} zone(s))",
        len(in2_violations) == 0 and len(in2_zones) > 0,
        (f"Non-power zones: {[z['net_name'] for z in in2_violations]}"
         if in2_violations else "No power zone found on In2.Cu"),
    )

    # List In2.Cu zone nets
    for z in in2_zones:
        print(f"    {z['net_name']}")

    # ── Check 3: No signal traces on inner layers ──
    print(f"\n── Inner Layer Trace Check ──")
    inner_segments = []
    for seg in cache["segments"]:
        if seg["layer"] in ("In1.Cu", "In2.Cu"):
            net_name = nets.get(seg["net"], f"net_{seg['net']}")
            inner_segments.append(
                f"{net_name} on {seg['layer']}: "
                f"({seg['x1']:.2f},{seg['y1']:.2f})->"
                f"({seg['x2']:.2f},{seg['y2']:.2f})"
            )

    check(
        f"No traces on inner layers (checked {len(cache['segments'])} segments)",
        len(inner_segments) == 0,
        f"{len(inner_segments)} inner-layer traces found" if inner_segments else "",
    )
    if inner_segments:
        for s in inner_segments[:5]:
            print(f"      {s}")
        if len(inner_segments) > 5:
            print(f"      ... and {len(inner_segments) - 5} more")

    # ── Check 4: No large power/GND zones on signal layers (F.Cu, B.Cu) ──
    print(f"\n── Signal Layer Zone Check ──")
    signal_layer_power_zones = [
        z for z in zones
        if z["layer"] in ("F.Cu", "B.Cu")
        and z["net_name"] in POWER_GND_NETS
    ]

    check(
        "No power/GND zones on signal layers (F.Cu, B.Cu)",
        len(signal_layer_power_zones) == 0,
        (f"Power zones found: "
         f"{[(z['net_name'], z['layer']) for z in signal_layer_power_zones]}"
         if signal_layer_power_zones else ""),
    )

    # ── Check 5: Layer usage summary ──
    print(f"\n── Layer Usage Summary ──")
    from collections import Counter
    layer_seg_count = Counter(s["layer"] for s in cache["segments"])
    layer_via_count = len(cache["vias"])  # vias span all layers
    layer_zone_count = Counter(z["layer"] for z in zones)

    for layer in ["F.Cu", "In1.Cu", "In2.Cu", "B.Cu"]:
        segs = layer_seg_count.get(layer, 0)
        zone_count = layer_zone_count.get(layer, 0)
        role = {
            "F.Cu": "Signal+Components",
            "In1.Cu": "GND Plane",
            "In2.Cu": "Power Plane",
            "B.Cu": "Signal+Components",
        }[layer]
        print(f"    {layer:8s}: {segs:3d} traces, {zone_count} zone(s) — {role}")
    print(f"    Vias:     {layer_via_count} (span all layers)")

    check(
        "Layer usage matches 4-layer stackup convention",
        (layer_seg_count.get("In1.Cu", 0) == 0 and
         layer_seg_count.get("In2.Cu", 0) == 0),
        "Traces found on plane layers",
    )

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(test_stackup())
