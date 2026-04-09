#!/usr/bin/env python3
"""Decoupling Capacitor Adequacy Check.

Verifies that each IC has sufficient decoupling capacitance per its
datasheet requirements. Checks:
  1. Total capacitance near each IC (within radius)
  2. High-frequency bypass cap present (100nF within 5mm)
  3. Bulk capacitance meets datasheet minimum
  4. All required power pins have nearby decoupling

Datasheet requirements:
  ESP32-S3:  10uF bulk + 100nF HF within 5mm of VDD pins
  IP5306:    10uF on VIN, 22uF on VOUT, 10uF on BAT
  AMS1117:   10uF input, 22uF output
  PAM8403:   1uF on VDD, 100nF on VREF

Usage:
    python3 scripts/verify_decoupling_adequacy.py
    Exit code 0 = pass, 1 = failure
"""

import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ---- Capacitor value map (from BOM / jlcpcb_export.py) ----
# ref -> capacitance in uF
CAP_VALUES = {
    # AMS1117 support
    "C1":  10.0,     # AMS1117 input (10uF 0805)
    "C2":  22.0,     # AMS1117 output (22uF 1206)
    # ESP32 decoupling
    "C3":  0.1,      # ESP32 EN RC / decoupling (100nF 0805)
    "C4":  0.1,      # ESP32 decoupling (100nF 0805)
    "C26": 0.1,      # ESP32 VDD bypass (100nF 0805)
    "C28": 10.0,     # ESP32 +3V3 bulk (10uF 0805)
    # Button debounce caps (100nF each)
    **{f"C{i}": 0.1 for i in range(5, 17)},
    "C20": 0.1,
    # IP5306 support
    "C17": 10.0,     # IP5306 VIN (10uF 0805)
    "C18": 10.0,     # IP5306 BAT (10uF 0805)
    "C19": 22.0,     # IP5306 VOUT bulk (22uF 1206)
    "C27": 10.0,     # IP5306 VOUT HF (10uF 0805)
    # PAM8403 support
    "C21": 0.1,      # PAM8403 VREF bypass (100nF 0805)
    "C22": 0.47,     # PAM8403 DC-blocking (0.47uF 0805)
    "C23": 1.0,      # PAM8403 VDD decoupling (1uF 0805)
    "C24": 1.0,      # PAM8403 PVDD decoupling (1uF 0805)
    "C25": 1.0,      # PAM8403 PVDD output (1uF 0805)
}

# ---- Capacitor position map (from routing.py / jlcpcb_export.py) ----
# These are populated from PCB cache pad positions at runtime.

# ---- Datasheet decoupling requirements ----
# Each entry: (ic_ref, power_pin, net_name, min_hf_uF, min_bulk_uF,
#              max_hf_dist_mm, max_bulk_dist_mm, description)
DECOUPLING_REQS = [
    # ESP32-S3: 100nF HF within 5mm of VDD + 10uF bulk within 15mm
    ("U1", "2",  "+3V3", 0.1,  10.0, 5.0,  15.0, "ESP32 VDD pin 2 (3V3)"),
    ("U1", "1",  "+3V3", 0.1,  10.0, 5.0,  15.0, "ESP32 VDD pin 1 (3V3)"),

    # IP5306: 10uF on VIN (pin 1), 22uF on VOUT (pin 8), 10uF on BAT (pin 6)
    ("U2", "1",  "VBUS",  10.0, 10.0, 10.0, 30.0, "IP5306 VIN (charger input)"),
    ("U2", "8",  "+5V",   10.0, 22.0, 10.0, 30.0, "IP5306 VOUT (5V boost)"),
    ("U2", "6",  "BAT+",  10.0, 10.0, 10.0, 30.0, "IP5306 BAT (battery terminal)"),

    # AMS1117: 10uF input, 22uF output
    ("U3", "3",  "+5V",   10.0, 10.0, 10.0, 30.0, "AMS1117 VIN (+5V input)"),
    ("U3", "2",  "+3V3",  22.0, 22.0, 10.0, 30.0, "AMS1117 VOUT (+3V3 output)"),
    # Tab is same net as pin 2 (VOUT), but physically offset. Relaxed HF threshold
    # since C2 (22uF) is positioned near pin 2, not the tab.
    ("U3", "4",  "+3V3",  10.0, 22.0, 10.0, 30.0, "AMS1117 tab (VOUT, relaxed HF)"),

    # PAM8403: 1uF on VDD (pin 6), 100nF on VREF (pin 8)
    ("U5", "6",  "+5V",   1.0,  1.0,  10.0, 15.0, "PAM8403 VDD (analog supply)"),
    ("U5", "8",  "PAM_VREF", 0.1, 0.1, 7.0, 15.0, "PAM8403 VREF (reference)"),
]


def _dist(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _get_cap_positions(cache):
    """Build {cap_ref: (x, y)} from PCB cache pads, using pad center."""
    pads = cache["pads"]
    cap_centers = {}
    for p in pads:
        ref = p.get("ref", "")
        if ref.startswith("C") and ref[1:].isdigit():
            if ref not in cap_centers:
                cap_centers[ref] = (p["x"], p["y"])
            else:
                # Average of pad positions = component center
                ox, oy = cap_centers[ref]
                cap_centers[ref] = ((ox + p["x"]) / 2, (oy + p["y"]) / 2)
    return cap_centers


def _get_ic_pin_pos(cache, ic_ref, pin_num):
    """Get IC pin position from PCB cache."""
    for p in cache["pads"]:
        if p["ref"] == ic_ref and str(p["num"]) == str(pin_num):
            return (p["x"], p["y"])
    return None


def _find_caps_near(cap_positions, target_x, target_y, radius_mm):
    """Find all capacitors within radius of target position.

    Returns list of (cap_ref, distance_mm, capacitance_uF).
    """
    nearby = []
    for ref, (cx, cy) in cap_positions.items():
        d = _dist(cx, cy, target_x, target_y)
        if d <= radius_mm and ref in CAP_VALUES:
            nearby.append((ref, d, CAP_VALUES[ref]))
    return sorted(nearby, key=lambda x: x[1])


def test_decoupling_adequacy():
    """Check each IC has adequate decoupling per datasheet."""
    print("\n-- Decoupling Capacitor Adequacy --")
    cache = load_cache(PCB_FILE)
    cap_positions = _get_cap_positions(cache)

    for ic_ref, pin_num, net_name, min_hf_uF, min_bulk_uF, max_hf_dist, max_bulk_dist, desc in DECOUPLING_REQS:
        pin_pos = _get_ic_pin_pos(cache, ic_ref, pin_num)
        if pin_pos is None:
            check(f"{desc}: pin found", False, f"{ic_ref} pin {pin_num} not in PCB cache")
            continue

        px, py = pin_pos

        # Find caps within HF distance (tight radius for bypass)
        hf_caps = _find_caps_near(cap_positions, px, py, max_hf_dist)
        hf_total = sum(c[2] for c in hf_caps)

        # Find caps within bulk distance (relaxed radius)
        bulk_caps = _find_caps_near(cap_positions, px, py, max_bulk_dist)
        bulk_total = sum(c[2] for c in bulk_caps)

        # Check HF: at least min_hf_uF within max_hf_dist
        hf_refs = ", ".join(f"{c[0]}({c[2]}uF@{c[1]:.1f}mm)" for c in hf_caps) or "none"
        check(f"{desc}: HF decoupling >= {min_hf_uF}uF within {max_hf_dist}mm",
              hf_total >= min_hf_uF,
              f"total={hf_total:.2f}uF, caps=[{hf_refs}]")

        # Check bulk: at least min_bulk_uF within max_bulk_dist
        bulk_refs = ", ".join(f"{c[0]}({c[2]}uF@{c[1]:.1f}mm)" for c in bulk_caps) or "none"
        check(f"{desc}: bulk decoupling >= {min_bulk_uF}uF within {max_bulk_dist}mm",
              bulk_total >= min_bulk_uF,
              f"total={bulk_total:.2f}uF, caps=[{bulk_refs}]")


def test_esp32_bypass_proximity():
    """Check ESP32 has at least one 100nF cap within 5mm of a VDD pin."""
    print("\n-- ESP32 100nF Bypass Proximity --")
    cache = load_cache(PCB_FILE)
    cap_positions = _get_cap_positions(cache)

    # ESP32 has VDD on pins 1 and 2
    for pin_num in ("1", "2"):
        pin_pos = _get_ic_pin_pos(cache, "U1", pin_num)
        if not pin_pos:
            continue

        px, py = pin_pos
        nearby = _find_caps_near(cap_positions, px, py, 5.0)
        hf_caps = [c for c in nearby if c[2] <= 0.1]  # 100nF class
        check(f"ESP32 pin {pin_num}: 100nF cap within 5mm",
              len(hf_caps) > 0,
              f"nearest caps: {nearby[:3]}")


def test_ip5306_output_capacitance():
    """IP5306 VOUT needs >= 22uF for boost converter stability."""
    print("\n-- IP5306 VOUT Bulk Capacitance --")
    cache = load_cache(PCB_FILE)
    cap_positions = _get_cap_positions(cache)

    pin_pos = _get_ic_pin_pos(cache, "U2", "8")  # VOUT pin
    if not pin_pos:
        check("IP5306 VOUT pin found", False)
        return

    px, py = pin_pos
    # Look within 30mm (VOUT caps can be on the rail)
    nearby = _find_caps_near(cap_positions, px, py, 30.0)
    total = sum(c[2] for c in nearby)

    # Expected: C19 (22uF) + C27 (10uF) = 32uF
    check(f"IP5306 VOUT: total >= 22uF (boost stability)",
          total >= 22.0,
          f"total={total:.1f}uF, caps={[(c[0], c[2]) for c in nearby[:5]]}")


def test_ams1117_output_capacitance():
    """AMS1117 output needs >= 22uF for LDO stability (ESR requirement)."""
    print("\n-- AMS1117 Output Capacitance --")
    cache = load_cache(PCB_FILE)
    cap_positions = _get_cap_positions(cache)

    pin_pos = _get_ic_pin_pos(cache, "U3", "2")  # VOUT pin
    if not pin_pos:
        check("AMS1117 VOUT pin found", False)
        return

    px, py = pin_pos
    nearby = _find_caps_near(cap_positions, px, py, 30.0)
    total = sum(c[2] for c in nearby)

    # Expected: C2 (22uF) nearby, plus others on +3V3 rail
    check(f"AMS1117 VOUT: total >= 22uF (LDO stability)",
          total >= 22.0,
          f"total={total:.1f}uF, caps={[(c[0], c[2]) for c in nearby[:5]]}")


def test_pam8403_vref_bypass():
    """PAM8403 VREF (pin 8) needs 100nF bypass for clean reference."""
    print("\n-- PAM8403 VREF Bypass --")
    cache = load_cache(PCB_FILE)
    cap_positions = _get_cap_positions(cache)

    pin_pos = _get_ic_pin_pos(cache, "U5", "8")
    if not pin_pos:
        check("PAM8403 VREF pin found", False)
        return

    px, py = pin_pos
    nearby = _find_caps_near(cap_positions, px, py, 7.0)
    hf_caps = [c for c in nearby if c[2] <= 0.1]  # 100nF class

    check(f"PAM8403 VREF: 100nF bypass within 7mm",
          len(hf_caps) > 0,
          f"caps within 7mm: {[(c[0], c[2], f'{c[1]:.1f}mm') for c in nearby]}")


def main():
    global PASS, FAIL
    PASS = FAIL = 0

    test_decoupling_adequacy()
    test_esp32_bypass_proximity()
    test_ip5306_output_capacitance()
    test_ams1117_output_capacitance()
    test_pam8403_vref_bypass()

    print(f"\nResults: {PASS} passed, {FAIL} failed")
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
