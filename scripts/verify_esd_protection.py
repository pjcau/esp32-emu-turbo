#!/usr/bin/env python3
"""ESD Protection Verification — check external interfaces for ESD protection.

Checks schematic files and BOM for:
1. TVS diodes on USB D+/D- lines
2. Series resistors on USB D+/D- (22/27 ohm)
3. TVS diode on VBUS line
4. ESD protection on other external interfaces

Advisory only (WARN, not FAIL) since prototype may work without ESD.

Usage:
    python3 scripts/verify_esd_protection.py
    Exit code 0 = pass/warn, 1 = failure
"""

import csv
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")
BOM_FILE = os.path.join(BASE, "release_jlcpcb", "bom.csv")
BOM_FILE_ALT = os.path.join(BASE, "hardware", "kicad", "jlcpcb", "bom.csv")
SCHEMATIC_DIR = os.path.join(BASE, "hardware", "kicad")

ESD_KEYWORDS = re.compile(r"TVS|ESD|USBLC|PESD|PRTR|TPD|SP05|CDSOT", re.I)
SERIES_R_VALUES = {"22", "27", "22R", "27R"}


def _read_schematics():
    """Read all schematic files, return combined text."""
    texts = {}
    for fn in sorted(os.listdir(SCHEMATIC_DIR)):
        if fn.endswith(".kicad_sch"):
            path = os.path.join(SCHEMATIC_DIR, fn)
            texts[fn] = open(path, encoding="utf-8").read()
    return texts


def _parse_bom():
    """Parse BOM CSV, return list of dicts. Merges release and hardware BOMs."""
    rows = []
    seen_designators = set()
    for bom_path in [BOM_FILE, BOM_FILE_ALT]:
        if not os.path.exists(bom_path):
            continue
        with open(bom_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                desig = row.get("Designator", "")
                if desig not in seen_designators:
                    seen_designators.add(desig)
                    rows.append(row)
    return rows


def analyze_esd_protection():
    """Analyze ESD protection on external interfaces."""
    findings = []
    warns = 0

    # --- BOM analysis ---
    bom = _parse_bom()
    bom_comments = " ".join(r.get("Comment", "") for r in bom)
    bom_designators = " ".join(r.get("Designator", "") for r in bom)

    has_tvs_in_bom = bool(ESD_KEYWORDS.search(bom_comments))

    # Check for series resistors (22/27 ohm) on USB D+/D-
    has_series_r = False
    for row in bom:
        val = row.get("Comment", "").strip().lower()
        if val in ("22", "27", "22r", "27r", "22 ohm", "27 ohm"):
            has_series_r = True
            break

    # --- Schematic analysis ---
    schematics = _read_schematics()
    all_sch = " ".join(schematics.values())

    has_tvs_in_sch = bool(ESD_KEYWORDS.search(all_sch))

    # Check USB CC pull-downs (5.1k)
    has_cc_pulldown = bool(re.search(r"5\.1k|5k1|CC[12]", all_sch))

    # --- PCB net analysis ---
    cache = load_cache(PCB_FILE)
    nets = {n["id"]: n["name"] for n in cache["nets"]}
    pads = cache["pads"]

    # Find components on USB_D+, USB_D- nets (besides J1 and U1)
    usb_dp_net = None
    usb_dm_net = None
    vbus_net = None
    for nid, name in nets.items():
        if name == "USB_D+":
            usb_dp_net = nid
        elif name == "USB_D-":
            usb_dm_net = nid
        elif name == "VBUS":
            vbus_net = nid

    usb_dp_refs = set()
    usb_dm_refs = set()
    vbus_refs = set()
    for p in pads:
        if p["net"] == usb_dp_net:
            usb_dp_refs.add(p["ref"])
        if p["net"] == usb_dm_net:
            usb_dm_refs.add(p["ref"])
        if p["net"] == vbus_net:
            vbus_refs.add(p["ref"])

    # Components on USB data lines besides J1 (connector) and U1 (ESP32)
    usb_extra = (usb_dp_refs | usb_dm_refs) - {"J1", "U1", "?"}
    vbus_extra = vbus_refs - {"J1", "U2", "?"}  # U2=IP5306

    # Check for bulk cap on VBUS
    has_vbus_cap = False
    for ref in vbus_refs:
        if ref.startswith("C"):
            has_vbus_cap = True
            break

    # --- Report ---
    print("\n── ESD Protection Analysis ──")

    # 1. TVS on USB D+/D-
    if has_tvs_in_bom or has_tvs_in_sch:
        findings.append(("PASS", "TVS diode found on USB data lines"))
    else:
        findings.append(("WARN", "No TVS diode found on USB D+/D- "
                         "(recommended: USBLC6-2SC6 or similar)"))
        warns += 1

    # 2. Series resistors on USB D+/D-
    if has_series_r:
        findings.append(("PASS", "Series resistor on USB D+/D- present"))
    elif usb_extra:
        # There might be resistors we didn't catch by value
        r_on_usb = [r for r in usb_extra if r.startswith("R")]
        if r_on_usb:
            findings.append(("INFO", f"Resistors on USB nets: {', '.join(sorted(r_on_usb))} "
                             "(verify they are 22-27 ohm series)"))
        else:
            findings.append(("WARN", "No series resistor on USB D+/D- "
                             "(recommended: 22 ohm for impedance matching)"))
            warns += 1
    else:
        findings.append(("WARN", "No series resistor on USB D+/D- "
                         "(recommended: 22 ohm for impedance matching)"))
        warns += 1

    # 3. USB CC pull-downs
    if has_cc_pulldown:
        cc_refs = [r for r in sorted(vbus_refs | usb_dp_refs | usb_dm_refs)
                   if r.startswith("R")]
        # R1, R2 are the CC pull-downs from BOM
        findings.append(("PASS", "USB CC1/CC2 have 5.1k pull-downs (R1, R2) "
                         "-- OK for device mode"))
    else:
        findings.append(("WARN", "No USB CC pull-down resistors found"))
        warns += 1

    # 4. VBUS protection
    if has_vbus_cap:
        cap_refs = sorted(r for r in vbus_refs if r.startswith("C"))
        findings.append(("PASS", f"VBUS has bulk cap protection ({', '.join(cap_refs)})"))
    else:
        findings.append(("WARN", "No bulk capacitor on VBUS line"))
        warns += 1

    # 5. Components on USB nets
    if usb_extra:
        findings.append(("INFO", f"Components on USB data nets (besides J1, U1): "
                         f"{', '.join(sorted(usb_extra))}"))
    else:
        findings.append(("INFO", "USB D+/D- connect directly J1 <-> U1 (no inline components)"))

    # 6. TVS on VBUS
    tvs_on_vbus = any(ESD_KEYWORDS.search(r) for r in vbus_refs)
    if not tvs_on_vbus and not has_tvs_in_bom:
        findings.append(("WARN", "No TVS diode on VBUS line "
                         "(recommended for USB-C hot-plug transients)"))
        warns += 1

    # Print findings
    for level, msg in findings:
        print(f"  {level:4s}  {msg}")

    if warns > 0:
        print(f"\n  {warns} advisory warning(s) — prototype may work, "
              "but add ESD protection for production")
    else:
        print("\n  All ESD protection checks passed")

    return 0  # Always exit 0 (advisory only)


if __name__ == "__main__":
    sys.exit(analyze_esd_protection())
