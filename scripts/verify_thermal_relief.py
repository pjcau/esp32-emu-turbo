#!/usr/bin/env python3
"""Test 10: Thermal Relief Verification.

Check that zone fill connections to SMD pads use thermal relief
(not direct connections) on internal planes.

Checks:
1. All internal zones have thermal relief enabled (not solid fill)
2. Thermal gap >= 0.20mm (JLCPCB minimum for reliable assembly)
3. Thermal bridge width >= 0.25mm (structural integrity)
4. connect_pads mode is thermal_relief (not direct/yes)
"""

import re
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"

PASS = 0
FAIL = 0
WARN = 0

MIN_THERMAL_GAP = 0.20      # mm
MIN_BRIDGE_WIDTH = 0.25     # mm
INTERNAL_LAYERS = {"In1.Cu", "In2.Cu"}


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


def parse_zones(text):
    """Extract zone settings from PCB file text."""
    zones = []
    # Find each zone block
    i = 0
    while True:
        idx = text.find("\n  (zone\n", i)
        if idx == -1:
            break
        # Find the zone's polygon start (end of settings, before fill data)
        poly_idx = text.find("(polygon", idx)
        if poly_idx == -1:
            break
        header = text[idx:poly_idx]
        i = poly_idx + 1

        net_m = re.search(r'\(net_name\s+"([^"]+)"\)', header)
        layer_m = re.search(r'\(layer\s+"([^"]+)"\)', header)
        if not net_m or not layer_m:
            continue

        net_name = net_m.group(1)
        layer = layer_m.group(1)

        # Thermal gap and bridge width
        gap_m = re.search(r'\(thermal_gap\s+([\d.]+)\)', header)
        bridge_m = re.search(r'\(thermal_bridge_width\s+([\d.]+)\)', header)
        thermal_gap = float(gap_m.group(1)) if gap_m else None
        bridge_width = float(bridge_m.group(1)) if bridge_m else None

        # Connect pads mode
        connect_m = re.search(r'\(connect_pads\s+(\w+)?\s*\(clearance', header)
        if connect_m and connect_m.group(1):
            connect_mode = connect_m.group(1)
        else:
            # Default (no explicit mode) = thermal_relief in KiCad
            connect_mode = "thermal_relief"

        # Fill type
        has_solid = "(fill (type solid)" in header
        has_fill_yes = "(fill yes" in header

        # Priority
        pri_m = re.search(r'\(priority\s+(\d+)\)', header)
        priority = int(pri_m.group(1)) if pri_m else 0

        zones.append({
            "net_name": net_name,
            "layer": layer,
            "thermal_gap": thermal_gap,
            "bridge_width": bridge_width,
            "connect_mode": connect_mode,
            "solid_fill": has_solid,
            "fill_yes": has_fill_yes,
            "priority": priority,
        })

    return zones


def main():
    print("=" * 60)
    print("Test 10: Thermal Relief Verification")
    print("=" * 60)

    text = PCB_FILE.read_text(encoding="utf-8")
    zones = parse_zones(text)

    if not zones:
        check("Zones found in PCB", False, "no zones parsed")
        print(f"\nResults: {PASS} passed, {FAIL} failed")
        return 1

    internal_zones = [z for z in zones if z["layer"] in INTERNAL_LAYERS]
    print(f"\n── Thermal Relief Verification ──")
    print(f"    Found {len(zones)} zones total, {len(internal_zones)} on internal layers")

    if not internal_zones:
        check("Internal plane zones exist", False, "no zones on In1.Cu/In2.Cu")
        print(f"\nResults: {PASS} passed, {FAIL} failed")
        return 1

    for z in internal_zones:
        label = f"{z['layer']} {z['net_name']} zone (priority={z['priority']})"

        # Check 1: No solid fill type
        if z["solid_fill"]:
            check(f"{label}: thermal relief enabled", False,
                  "uses solid fill (no thermal relief)")
            continue

        # Check 2: Has fill enabled
        if not z["fill_yes"]:
            warn(f"{label}: fill not enabled (empty zone)")
            continue

        # Check 3: Connect pads mode
        if z["connect_mode"] in ("yes", "direct"):
            check(f"{label}: connect mode", False,
                  f"connect_pads={z['connect_mode']} (direct connection, bad for assembly)")
        else:
            # Check 4: Thermal gap
            if z["thermal_gap"] is not None and z["thermal_gap"] < MIN_THERMAL_GAP:
                check(f"{label}: thermal gap", False,
                      f"gap={z['thermal_gap']:.2f}mm < {MIN_THERMAL_GAP}mm minimum")
            elif z["thermal_gap"] is not None:
                # Check 5: Bridge width
                if z["bridge_width"] is not None and z["bridge_width"] < MIN_BRIDGE_WIDTH:
                    check(f"{label}: bridge width", False,
                          f"bridge={z['bridge_width']:.2f}mm < {MIN_BRIDGE_WIDTH}mm minimum")
                else:
                    gap_str = f"gap={z['thermal_gap']:.2f}mm" if z["thermal_gap"] else "gap=default"
                    bridge_str = f"bridge={z['bridge_width']:.2f}mm" if z["bridge_width"] else "bridge=default"
                    check(f"{label}: thermal relief enabled ({gap_str}, {bridge_str})", True)
            else:
                check(f"{label}: thermal relief enabled (default settings)", True)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
