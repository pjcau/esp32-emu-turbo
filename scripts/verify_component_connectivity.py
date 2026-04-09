#!/usr/bin/env python3
"""Component connectivity verification — catches phantom components.

Verifies that every component in the BOM has at least one routed trace
connecting it. Catches parts placed on the board and listed in BOM/CPL
but not electrically connected to anything.

Uses the PCB cache (pad net assignments) as the primary data source,
with segment proximity as a fallback check.
"""

import csv
import json
import math
import os
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(BASE, "hardware", "kicad", ".pcb_cache.json")
BOM_FILE = os.path.join(BASE, "hardware", "kicad", "jlcpcb", "bom.csv")

# Components known to connect only via zone fill (no direct traces)
# These get INFO instead of FAIL if all pads have net=0
ZONE_ONLY_REFS: Set[str] = set()
# Note: MH1-MH6 not in this design; SPK1 has direct net assignments

# Components not in BOM but present in PCB (fiducials, test points)
NON_BOM_REFS: Set[str] = {"FID1", "FID2", "FID3", "SPK1"}

# Proximity threshold for segment-to-pad match (mm)
PROXIMITY_MM = 0.2

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


def info(name: str, detail: str = ""):
    """Print informational message (not a pass/fail)."""
    print(f"  INFO  {name}  {detail}")


def read_bom_refs() -> Dict[str, str]:
    """Read BOM and return dict of ref -> footprint."""
    refs = {}
    with open(BOM_FILE) as f:
        for row in csv.DictReader(f):
            designators = [d.strip() for d in row["Designator"].split(",")]
            for des in designators:
                refs[des] = row.get("Footprint", "")
    return refs


def load_cache() -> dict:
    """Load PCB cache JSON."""
    with open(CACHE_FILE) as f:
        return json.load(f)


def build_ref_net_map(pads: list) -> Dict[str, List[int]]:
    """Build ref -> list of net IDs from pad data."""
    ref_nets: Dict[str, List[int]] = defaultdict(list)
    for pad in pads:
        ref_nets[pad["ref"]].append(pad["net"])
    return dict(ref_nets)


def check_segment_proximity(
    ref: str,
    pads: list,
    segments: list,
) -> bool:
    """Check if any F.Cu/B.Cu segment endpoint is within PROXIMITY_MM of a pad.

    Fallback check for components whose pads have net=0 but might still
    be connected via traces that the cache didn't capture.
    """
    ref_pads = [p for p in pads if p["ref"] == ref]
    if not ref_pads:
        return False

    cu_segments = [s for s in segments if s["layer"] in ("F.Cu", "B.Cu")]

    for pad in ref_pads:
        px, py = pad["x"], pad["y"]
        for seg in cu_segments:
            for sx, sy in [(seg["x1"], seg["y1"]), (seg["x2"], seg["y2"])]:
                dist = math.sqrt((px - sx) ** 2 + (py - sy) ** 2)
                if dist <= PROXIMITY_MM:
                    return True
    return False


def test_component_connectivity():
    """Verify every BOM component has at least one connected pad."""
    print("\n── Component Connectivity ──")

    bom_refs = read_bom_refs()
    cache = load_cache()
    pads = cache["pads"]
    segments = cache["segments"]
    net_map = {n["id"]: n["name"] for n in cache["nets"]}

    ref_nets = build_ref_net_map(pads)

    connected = []
    disconnected = []
    zone_only = []

    for ref in sorted(bom_refs.keys()):
        nets = ref_nets.get(ref, [])

        if not nets:
            # Component has no pads in PCB at all
            disconnected.append((ref, "no pads found in PCB"))
            continue

        # Check if any pad has a non-zero net
        nonzero_nets = [n for n in nets if n != 0]

        if nonzero_nets:
            # At least one pad has a net assignment -- connected
            net_names = sorted(set(net_map.get(n, f"net_{n}") for n in nonzero_nets))
            connected.append((ref, net_names))
        else:
            # All pads have net=0 -- check zone-only or segment proximity
            if ref in ZONE_ONLY_REFS:
                zone_only.append(ref)
            elif check_segment_proximity(ref, pads, segments):
                # Connected via segment proximity (edge case)
                connected.append((ref, ["(segment proximity)"]))
            else:
                disconnected.append((ref, "all pads net=0, no segment proximity"))

    # Report zone-only components as INFO
    for ref in zone_only:
        info(f"{ref} zone-only connection", "(expected for this component)")

    # Report results
    for ref, detail in disconnected:
        check(f"{ref} has electrical connection", False, detail)

    if not disconnected:
        check(
            f"All {len(bom_refs)} BOM components connected",
            True,
        )

    # Summary
    print(f"\n    Connected: {len(connected)}/{len(bom_refs)}")
    if disconnected:
        print(f"    Disconnected (FAIL): {len(disconnected)}")
        for ref, detail in disconnected:
            ref_pads = [p for p in pads if p["ref"] == ref]
            pad_info = ", ".join(
                f"pad {p['num']}@({p['x']:.1f},{p['y']:.1f})"
                for p in ref_pads
            )
            print(f"      {ref}: {detail}")
            if ref_pads:
                print(f"        pads: {pad_info}")
    if zone_only:
        print(f"    Zone-only (INFO): {len(zone_only)} — {sorted(zone_only)}")


def test_non_bom_refs():
    """Check PCB-only refs (not in BOM) for awareness."""
    print("\n── Non-BOM PCB Components ──")

    bom_refs = read_bom_refs()
    cache = load_cache()
    pcb_refs = set(p["ref"] for p in cache["pads"])

    extra = sorted(pcb_refs - set(bom_refs.keys()))

    if extra:
        expected = [r for r in extra if r in NON_BOM_REFS]
        unexpected = [r for r in extra if r not in NON_BOM_REFS]

        if expected:
            info(
                f"{len(expected)} non-BOM refs (expected)",
                f"{expected}",
            )

        if unexpected:
            check(
                "No unexpected non-BOM components in PCB",
                False,
                f"unexpected refs: {unexpected}",
            )
        else:
            check("All non-BOM PCB refs are expected", True)
    else:
        check("No non-BOM PCB refs", True)


def main():
    """Run all component connectivity checks."""
    print("=" * 60)
    print("Component Connectivity Verification")
    print("=" * 60)

    if not os.path.exists(CACHE_FILE):
        print(f"  ERROR: PCB cache not found: {CACHE_FILE}")
        print("  Run: python3 scripts/generate_pcb/generate.py")
        return 1

    if not os.path.exists(BOM_FILE):
        print(f"  ERROR: BOM not found: {BOM_FILE}")
        return 1

    test_component_connectivity()
    test_non_bom_refs()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
