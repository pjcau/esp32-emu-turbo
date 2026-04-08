#!/usr/bin/env python3
"""Cross-check BOM, CPL, and PCB for consistency.

Verifies:
  1. All BOM designators exist in CPL (and vice versa)
  2. All BOM designators exist in PCB (and vice versa, minus hand-assembled)
  3. CPL positions match PCB pad centers (within tolerance, accounting for JLCPCB corrections)
  4. CPL rotation is a valid multiple of 90°
  5. BOM footprint names are JLCPCB-compatible (no internal names)
  6. No duplicate designators in BOM or CPL

Usage:
    python3 scripts/verify_bom_cpl_pcb.py
"""

import csv
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

BOM_PATH = os.path.join(BASE, "hardware", "kicad", "jlcpcb", "bom.csv")
CPL_PATH = os.path.join(BASE, "hardware", "kicad", "jlcpcb", "cpl.csv")

# Components that are hand-assembled (not in BOM, OK to be in PCB only)
HAND_ASSEMBLED = {"SPK1"}

# Known CPL position corrections (intentional offsets from PCB pad centers)
# These components have JLCPCB-specific position corrections in jlcpcb_export.py
KNOWN_CPL_CORRECTIONS = {"J1", "J3", "J4", "U1", "U2", "U3", "U5", "U6"}

# JLCPCB-compatible footprint names (reject internal project names)
JLCPCB_FOOTPRINTS = {
    "Module_ESP32-S3-WROOM-1", "ESOP-8", "SOT-223", "SOP-16",
    "USB-C-SMD-16P", "TF-01A", "JST-PH-2P-SMD", "LED_0805",
    "SMD-4x4x2mm", "R_0805", "R_0402", "C_0805", "C_1206",
    "SW-SMD-5.1x5.1", "FPC-40P-0.5mm", "SS-12D00G3",
    "SOT-23-6", "SOT-23",
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
    return condition


def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  WARN  {name}  {detail}")


def parse_bom():
    """Parse BOM → {ref: {comment, footprint, lcsc, qty}}."""
    entries = {}
    all_refs = []
    with open(BOM_PATH) as f:
        for row in csv.DictReader(f):
            fps = row.get("Footprint", "")
            lcsc = row.get("LCSC Part #", "")
            comment = row.get("Comment", "")
            for ref in row["Designator"].split(","):
                ref = ref.strip()
                all_refs.append(ref)
                entries[ref] = {
                    "comment": comment,
                    "footprint": fps,
                    "lcsc": lcsc,
                }
    return entries, all_refs


def parse_cpl():
    """Parse CPL → {ref: {val, package, x, y, rot, layer}}."""
    entries = {}
    all_refs = []
    with open(CPL_PATH) as f:
        for row in csv.DictReader(f):
            ref = row["Designator"].strip()
            all_refs.append(ref)
            entries[ref] = {
                "val": row.get("Val", ""),
                "package": row.get("Package", ""),
                "x": float(row["Mid X"].replace("mm", "")),
                "y": float(row["Mid Y"].replace("mm", "")),
                "rot": float(row["Rotation"]),
                "layer": row["Layer"],
            }
    return entries, all_refs


def get_pcb_refs(cache):
    """Get component refs from PCB, excluding mounting holes and fiducials."""
    refs = set()
    for p in cache["pads"]:
        ref = p["ref"]
        if ref and ref != "?" and not ref.startswith("MH") and not ref.startswith("FID"):
            refs.add(ref)
    return refs


def get_pad_centers(cache):
    """Get center of each component's pads."""
    pad_groups = {}
    for p in cache["pads"]:
        ref = p["ref"]
        if ref not in pad_groups:
            pad_groups[ref] = {"xs": [], "ys": []}
        pad_groups[ref]["xs"].append(p["x"])
        pad_groups[ref]["ys"].append(p["y"])

    centers = {}
    for ref, data in pad_groups.items():
        centers[ref] = (
            sum(data["xs"]) / len(data["xs"]),
            sum(data["ys"]) / len(data["ys"]),
        )
    return centers


def main():
    print("=" * 60)
    print("  BOM / CPL / PCB Cross-Check")
    print("=" * 60)

    bom, bom_all_refs = parse_bom()
    cpl, cpl_all_refs = parse_cpl()
    cache = load_cache()
    pcb_refs = get_pcb_refs(cache)
    pad_centers = get_pad_centers(cache)

    bom_refs = set(bom.keys())
    cpl_refs = set(cpl.keys())

    print(f"\n  BOM: {len(bom_refs)} refs, CPL: {len(cpl_refs)} refs, PCB: {len(pcb_refs)} refs")

    # ── 1. BOM ↔ CPL consistency ──
    print("\n── BOM ↔ CPL Consistency ──")
    diff_bom_cpl = bom_refs - cpl_refs
    check("All BOM refs in CPL", not diff_bom_cpl,
          f"missing from CPL: {sorted(diff_bom_cpl)}")

    diff_cpl_bom = cpl_refs - bom_refs
    check("All CPL refs in BOM", not diff_cpl_bom,
          f"missing from BOM: {sorted(diff_cpl_bom)}")

    # ── 2. BOM ↔ PCB consistency ──
    print("\n── BOM ↔ PCB Consistency ──")
    diff_bom_pcb = bom_refs - pcb_refs
    check("All BOM refs in PCB", not diff_bom_pcb,
          f"in BOM but not PCB: {sorted(diff_bom_pcb)}")

    diff_pcb_bom = pcb_refs - bom_refs - HAND_ASSEMBLED
    check("All PCB refs in BOM (excl hand-assembled)", not diff_pcb_bom,
          f"in PCB but not BOM: {sorted(diff_pcb_bom)}")

    if pcb_refs & HAND_ASSEMBLED:
        print(f"  INFO  Hand-assembled components: {sorted(pcb_refs & HAND_ASSEMBLED)}")

    # ── 3. Duplicate designators ──
    print("\n── Duplicate Designator Check ──")
    bom_dupes = [r for r in bom_all_refs if bom_all_refs.count(r) > 1]
    check("No duplicate BOM designators", not bom_dupes,
          f"duplicates: {sorted(set(bom_dupes))}")

    cpl_dupes = [r for r in cpl_all_refs if cpl_all_refs.count(r) > 1]
    check("No duplicate CPL designators", not cpl_dupes,
          f"duplicates: {sorted(set(cpl_dupes))}")

    # ── 4. BOM footprint names ──
    print("\n── BOM Footprint Compatibility ──")
    bad_fps = []
    for ref, info in sorted(bom.items()):
        fp = info["footprint"]
        if fp not in JLCPCB_FOOTPRINTS:
            bad_fps.append(f"{ref}={fp}")
    check("All BOM footprints JLCPCB-compatible", not bad_fps,
          f"unknown: {bad_fps[:5]}")

    # ── 5. CPL rotation validity ──
    print("\n── CPL Rotation Check ──")
    bad_rot = []
    for ref, info in sorted(cpl.items()):
        rot = info["rot"]
        if rot % 90 != 0 and rot % 45 != 0:
            bad_rot.append(f"{ref}={rot}")
    check("All CPL rotations valid (multiples of 45°)", not bad_rot,
          f"bad rotations: {bad_rot}")

    # ── 6. CPL position vs PCB ──
    print("\n── CPL Position vs PCB Pads ──")
    pos_errors = []
    for ref in sorted(cpl_refs):
        if ref not in pad_centers:
            pos_errors.append(f"{ref}: NOT in PCB!")
            continue
        pcb_cx, pcb_cy = pad_centers[ref]
        cpl_x, cpl_y = cpl[ref]["x"], cpl[ref]["y"]
        dx, dy = abs(cpl_x - pcb_cx), abs(cpl_y - pcb_cy)
        if dx > 1.0 or dy > 1.0:
            if ref in KNOWN_CPL_CORRECTIONS:
                print(f"  INFO  {ref}: CPL correction Δ=({dx:.1f},{dy:.1f})mm (expected)")
            else:
                pos_errors.append(
                    f"{ref}: CPL=({cpl_x:.1f},{cpl_y:.1f}) PCB=({pcb_cx:.1f},{pcb_cy:.1f}) Δ=({dx:.1f},{dy:.1f})")

    check("CPL positions match PCB (excl known corrections)", not pos_errors,
          f"{len(pos_errors)} unexpected offset(s): {pos_errors}")

    # ── 7. LCSC part numbers present ──
    print("\n── LCSC Part Number Check ──")
    missing_lcsc = []
    for ref, info in sorted(bom.items()):
        if not info["lcsc"] or info["lcsc"].strip() == "":
            missing_lcsc.append(ref)
    check("All BOM entries have LCSC part number", not missing_lcsc,
          f"missing LCSC: {sorted(missing_lcsc)}")

    # ── Summary ──
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"  RESULTS: {PASS} PASS / {FAIL} FAIL / {WARN} WARN  ({total} checks)")
    if FAIL == 0:
        print("  STATUS: ALL CHECKS PASSED")
    else:
        print(f"  STATUS: {FAIL} ISSUE(S) FOUND")
    print("=" * 60)
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
