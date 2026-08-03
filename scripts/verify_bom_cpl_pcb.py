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
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

BOM_PATH = os.path.join(BASE, "hardware", "kicad", "jlcpcb", "bom.csv")
CPL_PATH = os.path.join(BASE, "hardware", "kicad", "jlcpcb", "cpl.csv")

# Components that are hand-assembled (not in BOM, OK to be in PCB only)
HAND_ASSEMBLED = {"SPK1"}


def _load_dnp_refs() -> set:
    """Return refs that are DNP (footprint on PCB but intentionally
    excluded from BOM/CPL assembly).

    The authoritative list lives in ``scripts/generate_pcb/jlcpcb_export.py``
    as comments + the actual exclusions applied to ``_build_placements``.
    Rather than duplicate, we execute ``_build_placements`` and compare
    to the PCB placements list — any PCB ref not in the CPL output is
    DNP by definition. This gives us a single source of truth and
    automatically picks up future DNPs without edits.

    Fail-loud: if the import breaks, we raise, because a BOM/CPL check
    that cannot see the DNP list must NOT silently pass.
    """
    try:
        from scripts.generate_pcb import jlcpcb_export  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            f"cannot import scripts.generate_pcb.jlcpcb_export to "
            f"discover DNP refs: {exc}"
        ) from exc

    cpl_refs = {tup[0] for tup in jlcpcb_export._build_placements()}
    # The full PCB footprint list comes from the parse cache. The cache
    # exposes ``refs`` (mapping of ref → layer) and individual pad
    # records; either works to enumerate every footprint on the board.
    cache = load_cache()
    refs_map = cache.get("refs")
    if isinstance(refs_map, dict):
        pcb_all = set(refs_map.keys())
    else:
        pcb_all = {p["ref"] for p in cache.get("pads", []) if "ref" in p}
    dnp = pcb_all - cpl_refs - HAND_ASSEMBLED
    return dnp


DNP_REFS = _load_dnp_refs()

# Known CPL position corrections (intentional offsets from PCB pad centers)
# These components have JLCPCB-specific position corrections in jlcpcb_export.py
KNOWN_CPL_CORRECTIONS = {"J1", "J3", "J4", "U1", "U2", "U3", "U5", "U6"}

# JLCPCB-compatible footprint names (reject internal project names)
JLCPCB_FOOTPRINTS = {
    "Module_ESP32-S3-WROOM-1", "ESOP-8", "SOT-223", "SOP-16",
    "USB-C-SMD-16P", "TF-01A", "JST-PH-2P-SMD", "LED_0805",
    "SMD-4x4x2mm", "R_0805", "R_0402", "R_1206", "C_0805", "C_1206",
    "SW-SMD-5.1x5.1", "FPC-40P-0.5mm", "SS-12D00G3",
    "SOT-23-6", "SOT-23",
    # U3 SY8089AAAC (C78988) and L2 SWPA4030S2R2MT (C36409): both land
    # patterns are verbatim copies of the JLCPCB/EasyEDA reference
    # footprints fetched with easyeda2kicad, so they are by construction
    # JLCPCB-compatible (verify_easyeda_footprint reports delta_row = 0).
    "SOT-23-5", "IND-SMD-4.0x4.0",
    # F1 VBUS PTC fuse (C960026): generic 1812 chip land (body 4.73x3.41
    # per the BHFUSE datasheet), same naming convention as R_/C_ chips.
    "F_1812",
    # SW17 manual KEY wake (C720477, XUNPU TS-1088-AR02016): two-terminal
    # SMD momentary, land drawn from the EasyEDA package
    # SW-SMD_L3.9-W3.0-P4.45 (pads 1.230 x 1.860 mm at 4.370 mm pitch,
    # read off the 10-mil grid). DNP, so JLCPCB never places it — but the
    # land still has to be a real one, because the whole point is that it
    # CAN be fitted later.
    "SW-SMD-2P-TS1088",
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
    # A part whose BOM comment says DO NOT PLACE is SUPPOSED to be missing
    # from the CPL — that is the mechanism, not an oversight. The CPL is
    # the file JLCPCB places from, so "in the BOM, out of the CPL" is
    # exactly how you say "here is the part, do not fit it". Keeping the
    # line in the BOM is what makes it sourceable later; dropping it would
    # lose the LCSC number and leave a bare land nobody can identify.
    #
    # The marker is the literal phrase DO NOT PLACE, and NOT the word
    # "DNP", because this board already uses "DNP" to mean something
    # different: the diagnostic LEDs and their resistors are commented
    # "DNP in production", which is a note about a FUTURE build — they are
    # placed in this one, on purpose, because they are the bring-up
    # instrumentation. Keying on "DNP" would have declared all eight of
    # them do-not-place and quietly stopped them being assembled.
    #
    # Derived from the comment, not from a ref list: a new do-not-place
    # part gets this behaviour by saying so, and a part that stops being
    # do-not-place starts being required in the CPL again on the same edit.
    dnp_refs = {r for r, e in bom.items()
                if "DO NOT PLACE" in e["comment"].upper()}
    diff_bom_cpl = bom_refs - cpl_refs - dnp_refs
    check("All BOM refs in CPL (except DO NOT PLACE)", not diff_bom_cpl,
          f"missing from CPL: {sorted(diff_bom_cpl)}")
    # The other direction of the same rule: a do-not-place part appearing
    # in the CPL would be populated by JLCPCB regardless of the comment.
    dnp_in_cpl = dnp_refs & cpl_refs
    check("No DO-NOT-PLACE part is in the CPL", not dnp_in_cpl,
          f"marked do-not-place but in the CPL: {sorted(dnp_in_cpl)}")

    diff_cpl_bom = cpl_refs - bom_refs
    check("All CPL refs in BOM", not diff_cpl_bom,
          f"missing from BOM: {sorted(diff_cpl_bom)}")

    # ── 2. BOM ↔ PCB consistency ──
    print("\n── BOM ↔ PCB Consistency ──")
    diff_bom_pcb = bom_refs - pcb_refs
    check("All BOM refs in PCB", not diff_bom_pcb,
          f"in BOM but not PCB: {sorted(diff_bom_pcb)}")

    # PCB refs that are intentionally not assembled:
    #   - HAND_ASSEMBLED: through-hole or post-assembly (SPK1)
    #   - DNP_REFS:       footprint present but excluded from CPL
    #                     (auto-discovered from jlcpcb_export._build_placements)
    # Anything ELSE that is on the PCB but not in the BOM is a genuine
    # mismatch and must fail the check.
    diff_pcb_bom = pcb_refs - bom_refs - HAND_ASSEMBLED - DNP_REFS
    check("All PCB refs in BOM (excl hand-assembled + DNP)",
          not diff_pcb_bom,
          f"in PCB but not BOM: {sorted(diff_pcb_bom)}")

    if pcb_refs & HAND_ASSEMBLED:
        print(f"  INFO  Hand-assembled components: "
              f"{sorted(pcb_refs & HAND_ASSEMBLED)}")
    if pcb_refs & DNP_REFS:
        print(f"  INFO  DNP (PCB footprint only, excluded from CPL): "
              f"{sorted(pcb_refs & DNP_REFS)}")

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

    # ── 8. Schematic field completeness (KiBot-inspired) ──
    print("\n── Schematic Field Completeness ──")
    missing_value = []
    missing_fp = []
    for ref, info in sorted(bom.items()):
        if not info["comment"] or info["comment"].strip() == "":
            missing_value.append(ref)
        if not info["footprint"] or info["footprint"].strip() == "":
            missing_fp.append(ref)

    check("All BOM entries have value/comment field", not missing_value,
          f"missing value: {sorted(missing_value)}")
    check("All BOM entries have footprint field", not missing_fp,
          f"missing footprint: {sorted(missing_fp)}")

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
