#!/usr/bin/env python3
"""Netlist Diff — exports KiCad schematic netlist and cross-checks it against PCB cache.

Checks:
  T1  Nets in schematic but NOT in PCB (missing routes)
  T2  Nets in PCB but NOT in schematic (orphan PCB nets)
  T3  Components in schematic but NOT in PCB (missing footprints)
  T4  Pin-to-net mismatches between schematic and PCB

Known exclusions (manual assembly / fiducials / DNP):
  BT1, J2, SPK1 — manual assembly (no PCBA footprint required)
  FID1, FID2, FID3 — fiducials (no electrical nets)
  R14 — DNP (do not populate)

Usage:
    python3 scripts/verify_netlist_diff.py
"""

import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0

SCH_PATH = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_sch")
NETLIST_TMP = "/tmp/esp32_emu_turbo_netlist.xml"

# Components excluded from cross-checks (manual assembly / fiducials / DNP)
EXCLUDED_REFS = {"BT1", "J2", "SPK1", "FID1", "FID2", "FID3", "R14"}

# Net name prefixes/patterns that are PCB-internal (power flags, unconnected stubs)
_PCB_INTERNAL_PREFIXES = ("unconnected-", "Net-(", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check(test_id, name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  [{test_id}] {name}")
    else:
        FAIL += 1
        print(f"  FAIL  [{test_id}] {name}  {detail}")
    return condition


def _is_pcb_internal(net_name):
    """Return True for KiCad auto-generated net names that have no schematic equivalent."""
    return (net_name.startswith("unconnected-")
            or net_name.startswith("Net-(")
            or net_name == "")


# ---------------------------------------------------------------------------
# Step 1 — Export netlist from schematic
# ---------------------------------------------------------------------------

def export_netlist():
    """Run kicad-cli to export KiCadXML netlist. Return True on success."""
    cmd = [
        "kicad-cli", "sch", "export", "netlist",
        "--format", "kicadxml",
        "--output", NETLIST_TMP,
        SCH_PATH,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"  ERROR  kicad-cli failed (rc={result.returncode}): {result.stderr.strip()}")
            return False
        if not os.path.exists(NETLIST_TMP):
            print(f"  ERROR  Netlist not created at {NETLIST_TMP}")
            return False
        return True
    except FileNotFoundError:
        print("  ERROR  kicad-cli not found — install KiCad or add it to PATH")
        return False
    except subprocess.TimeoutExpired:
        print("  ERROR  kicad-cli timed out")
        return False


# ---------------------------------------------------------------------------
# Step 2 — Parse netlist XML
# ---------------------------------------------------------------------------

def parse_netlist(path):
    """Parse KiCadXML netlist. Return (sch_nets, sch_comps, sch_pin_nets).

    sch_nets   : set of net names
    sch_comps  : set of component references
    sch_pin_nets: dict of (ref, pin_number) -> net_name
    """
    tree = ET.parse(path)
    root = tree.getroot()

    sch_nets = set()
    sch_comps = set()
    sch_pin_nets = {}  # (ref, pin) -> net_name

    # <components> section
    components_el = root.find("components")
    if components_el is not None:
        for comp in components_el.findall("comp"):
            ref = comp.get("ref", "")
            if ref and not ref.startswith("#"):
                sch_comps.add(ref)

    # <nets> section
    nets_el = root.find("nets")
    if nets_el is not None:
        for net_el in nets_el.findall("net"):
            net_name = net_el.get("name", "")
            if not net_name:
                continue
            sch_nets.add(net_name)
            for node in net_el.findall("node"):
                ref = node.get("ref", "")
                pin = node.get("pin", "")
                if ref and pin:
                    sch_pin_nets[(ref, pin)] = net_name

    return sch_nets, sch_comps, sch_pin_nets


# ---------------------------------------------------------------------------
# Step 3 — Build PCB net/pad lookup from cache
# ---------------------------------------------------------------------------

def build_pcb_data(cache):
    """Return (pcb_nets, pcb_refs, pcb_pin_nets) from cache.

    pcb_nets    : set of net names in PCB
    pcb_refs    : set of component refs in PCB
    pcb_pin_nets: dict of (ref, pad_num) -> net_name
    """
    net_id_to_name = {n["id"]: n["name"] for n in cache.get("nets", [])}

    pcb_nets = set(net_id_to_name.values()) - {""}
    pcb_refs = set(cache.get("refs", []))

    pcb_pin_nets = {}
    for pad in cache.get("pads", []):
        ref = pad.get("ref", "")
        num = str(pad.get("num", ""))
        net_id = pad.get("net", 0)
        net_name = net_id_to_name.get(net_id, "")
        if ref and num and net_name:
            # Keep first occurrence (pads may be duplicated per copper layer)
            key = (ref, num)
            if key not in pcb_pin_nets:
                pcb_pin_nets[key] = net_name

    return pcb_nets, pcb_refs, pcb_pin_nets


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def t1_missing_routes(sch_nets, pcb_nets):
    """Nets in schematic but not routed in PCB."""
    missing = set()
    for net in sch_nets:
        if _is_pcb_internal(net):
            continue
        if net not in pcb_nets:
            missing.add(net)
    check("T1", "Schematic nets all present in PCB",
          len(missing) == 0,
          f"{len(missing)} missing: {sorted(missing)[:10]}")


def t2_orphan_pcb_nets(sch_nets, pcb_nets):
    """Nets in PCB but not in schematic (excluding auto-generated names)."""
    orphan = set()
    for net in pcb_nets:
        if _is_pcb_internal(net):
            continue
        if net not in sch_nets:
            orphan.add(net)
    check("T2", "PCB nets all present in schematic",
          len(orphan) == 0,
          f"{len(orphan)} orphan: {sorted(orphan)[:10]}")


def t3_missing_footprints(sch_comps, pcb_refs):
    """Components in schematic but without a footprint in PCB."""
    # Filter excluded refs
    expected = sch_comps - EXCLUDED_REFS
    missing = expected - pcb_refs
    check("T3", "All schematic components have PCB footprints",
          len(missing) == 0,
          f"{len(missing)} missing: {sorted(missing)[:10]}")


def t4_pin_net_mismatches(sch_pin_nets, pcb_pin_nets):
    """Pin-to-net mismatches between schematic and PCB (excluding excluded refs)."""
    mismatches = []
    for (ref, pin), sch_net in sch_pin_nets.items():
        if ref in EXCLUDED_REFS:
            continue
        pcb_net = pcb_pin_nets.get((ref, pin))
        if pcb_net is None:
            # Pad not in PCB — already covered by T3
            continue
        if pcb_net != sch_net:
            mismatches.append(f"{ref}.{pin}: sch={sch_net!r} pcb={pcb_net!r}")
    check("T4", "No pin-to-net mismatches between schematic and PCB",
          len(mismatches) == 0,
          f"{len(mismatches)} mismatch(es): {mismatches[:5]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global PASS, FAIL

    print("=" * 60)
    print("Netlist Diff — schematic vs PCB cross-check")
    print("=" * 60)

    # Export netlist
    print("\n[Exporting schematic netlist via kicad-cli...]")
    if not export_netlist():
        print("\n  ABORT  Cannot proceed without netlist export.")
        sys.exit(2)
    print(f"  OK    Netlist written to {NETLIST_TMP}")

    # Parse netlist
    sch_nets, sch_comps, sch_pin_nets = parse_netlist(NETLIST_TMP)
    print(f"  OK    Schematic: {len(sch_comps)} components, "
          f"{len(sch_nets)} nets, {len(sch_pin_nets)} pin-net entries")

    # Load PCB cache
    cache = load_cache()
    pcb_nets, pcb_refs, pcb_pin_nets = build_pcb_data(cache)
    print(f"  OK    PCB cache: {len(pcb_refs)} refs, "
          f"{len(pcb_nets)} nets, {len(pcb_pin_nets)} pad-net entries")
    print(f"  INFO  Excluded refs: {sorted(EXCLUDED_REFS)}")

    # Run tests
    print("\n[Running checks...]")
    t1_missing_routes(sch_nets, pcb_nets)
    t2_orphan_pcb_nets(sch_nets, pcb_nets)
    t3_missing_footprints(sch_comps, pcb_refs)
    t4_pin_net_mismatches(sch_pin_nets, pcb_pin_nets)

    # Summary
    total = PASS + FAIL
    print("\n" + "=" * 60)
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    if FAIL == 0:
        print("STATUS: PASS — schematic and PCB are consistent")
    else:
        print("STATUS: FAIL — fix the issues above before manufacturing")
    print("=" * 60)

    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
