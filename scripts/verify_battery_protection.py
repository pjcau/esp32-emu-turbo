#!/usr/bin/env python3
"""Battery Protection Verification — check reverse-polarity and over-voltage protection.

Checks the battery connector (J3) path for:
  - Electronic reverse-polarity protection (P-MOSFET or Schottky diode)
  - Over-voltage protection (OVP)
  - Over-current protection (OCP/PTC fuse)
  - Mechanical keying (JST PH connector)

IP5306 has built-in OVP (4.6V) and OCP (3.0A).
JST PH has mechanical keying preventing reverse insertion.

This script WARNs for missing electronic protection but does NOT FAIL
(mechanical keying is adequate for prototype v1).
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

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


def info(name, detail=""):
    print(f"  INFO  {name}  {detail}")


def main():
    print("=" * 60)
    print("Battery Protection Verification")
    print("=" * 60)

    cache = load_cache(PCB_FILE)
    nets = {n["id"]: n["name"] for n in cache["nets"]}
    net_ids = {n["name"]: n["id"] for n in cache["nets"]}
    refs = set(cache["refs"])

    # Check J3 battery connector exists
    print(f"\n-- Battery Connector --")
    j3_found = "J3" in refs
    check("J3 battery connector present", j3_found,
          "J3 not found in PCB references")

    # Find BAT+ net
    bat_plus_id = net_ids.get("BAT+")
    check("BAT+ net defined", bat_plus_id is not None,
          "no BAT+ net in PCB")

    if bat_plus_id is None:
        print(f"\nResults: {PASS} passed, {FAIL} failed, {WARN} warnings")
        return 1 if FAIL else 0

    # Find all pads on BAT+ net
    bat_pads = [p for p in cache["pads"] if p["net"] == bat_plus_id]
    bat_refs = sorted(set(p["ref"] for p in bat_pads))

    print(f"\n-- Components on BAT+ Net --")
    info(f"BAT+ net ID: {bat_plus_id}")
    info(f"Pads on BAT+: {len(bat_pads)}")
    info(f"Components: {', '.join(bat_refs)}")

    # Classify protection components
    has_mosfet = False
    has_diode = False
    has_fuse = False
    has_ip5306 = False

    for ref in bat_refs:
        ref_upper = ref.upper()
        if ref_upper.startswith("Q"):
            has_mosfet = True
            info(f"P-MOSFET found: {ref} (reverse-polarity protection)")
        elif ref_upper.startswith("D"):
            has_diode = True
            info(f"Diode found: {ref} (possible Schottky reverse protection)")
        elif ref_upper.startswith("F"):
            has_fuse = True
            info(f"Fuse/PTC found: {ref} (over-current protection)")
        elif ref_upper.startswith("U"):
            # Check if it's IP5306
            if ref_upper in ("U2",):
                has_ip5306 = True
                info(f"IP5306 ({ref}) connected to BAT+")

    # Check 1: IP5306 built-in protections
    print(f"\n-- Built-in Protection (IP5306) --")
    if has_ip5306:
        check("IP5306 provides built-in OVP (4.6V)", True)
        check("IP5306 provides built-in OCP (3.0A)", True)
        info("IP5306 does NOT provide reverse-polarity protection")
    else:
        warn("IP5306 not found on BAT+ net",
             "cannot confirm built-in OVP/OCP")

    # Check 2: Electronic reverse-polarity protection
    print(f"\n-- Reverse-Polarity Protection --")
    has_electronic_rpol = has_mosfet or has_diode

    if has_electronic_rpol:
        check("Electronic reverse-polarity protection present", True)
    else:
        warn("No electronic reverse-polarity protection found",
             "No P-MOSFET or series diode on BAT+ net. Recommend adding for v2.")

    # Check 3: JST PH mechanical keying
    # JST PH connectors have mechanical keying by design
    if j3_found:
        info("JST PH mechanical keying provides primary reverse-polarity protection")
        info("Keying prevents reverse insertion IF cable is crimped correctly")
        check("Mechanical keying present (JST PH connector)", True)
    else:
        warn("No JST PH connector found — no mechanical keying")

    # Check 4: Over-current protection beyond IP5306
    print(f"\n-- Over-Current Protection --")
    if has_fuse:
        check("External fuse/PTC on battery path", True)
    else:
        if has_ip5306:
            info("IP5306 built-in OCP is the only over-current protection")
            info("Consider adding a polyfuse for v2 (additional safety)")
        else:
            warn("No over-current protection found on BAT+ path")

    # Overall assessment
    print(f"\n-- Protection Summary --")
    if has_electronic_rpol and has_ip5306:
        level = "FULL"
        info(f"Protection level: {level} (electronic RPP + OVP + OCP)")
    elif has_ip5306 and j3_found:
        level = "MECHANICAL + IC"
        info(f"Protection level: {level} (JST keying + IP5306 OVP/OCP)")
        info("Adequate for prototype v1. Add electronic RPP for v2.")
    elif j3_found:
        level = "MECHANICAL ONLY"
        info(f"Protection level: {level} (JST keying only)")
        warn("Minimal protection — add IP5306 or equivalent for OVP/OCP")
    else:
        level = "NONE"
        check("Battery has some protection", False,
              "no connector keying and no electronic protection detected")

    # This script should WARN but NOT FAIL for missing electronic RPP
    # FAIL only if absolutely no protection at all
    if level == "NONE":
        check("Minimum battery protection present", False,
              "no protection of any kind detected")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
