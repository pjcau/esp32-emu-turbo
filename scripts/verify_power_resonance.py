#!/usr/bin/env python3
"""Power Plane Resonance Check — estimate LC resonance of +3V3 plane.

The +3V3 power plane (In2.Cu) forms an LC circuit with decoupling capacitors.
This script estimates the resonance frequency and checks if it falls in
problematic ranges that could couple with ESP32 WiFi or the 8080 display bus.

Physics:
  L_plane ~ mu0 * d / (W * L)  where d=dielectric thickness, W=width, L=length
  f_res = 1 / (2*pi*sqrt(L*C))
  Q = 1/ESR * sqrt(L/C)  — lower Q = better damped

Usage:
    python3 scripts/verify_power_resonance.py
    Exit code 0 = pass/info, 1 = failure
"""

import math
import os
import re
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")
BOM_FILE = os.path.join(BASE, "release_jlcpcb", "bom.csv")

# Board dimensions (mm -> m)
BOARD_W = 160e-3   # 160mm
BOARD_L = 75e-3    # 75mm

# JLCPCB 4-layer 1.6mm stackup (JLC04161H-7628)
# In2.Cu (+3V3) to In1.Cu (GND) dielectric thickness
DIELECTRIC_D = 0.2e-3  # ~0.2mm core between inner layers

MU0 = 4 * math.pi * 1e-7  # H/m

# Capacitor values from BOM — parse designators and values
CAP_VALUES = {
    "100nF": 100e-9,
    "0.47uF": 0.47e-6,
    "1uF": 1e-6,
    "10uF": 10e-6,
    "22uF": 22e-6,
}

# Typical ESR for MLCC (0805/1206)
ESR_TYPICAL = {
    "100nF": 0.015,   # 15 mOhm
    "0.47uF": 0.012,
    "1uF": 0.010,
    "10uF": 0.005,
    "22uF": 0.005,    # 1206
}

# Problematic frequency ranges
WIFI_BAND = (2.4e9, 2.5e9)
DISPLAY_BUS = (10e6, 20e6)  # 8080 parallel bus frequency


def _parse_bom_caps(bom_path):
    """Parse BOM CSV to count capacitors on +3V3 rail.

    We assume all capacitors contribute to +3V3 decoupling (conservative).
    Returns list of (value_str, count) tuples.
    """
    import csv
    caps = []
    try:
        with open(bom_path, "r") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return caps
            for row in reader:
                if len(row) < 5:
                    continue
                comment = row[0].strip()
                designators = row[1].strip()
                quantity = int(row[4].strip()) if row[4].strip().isdigit() else 0

                for val_str, val in CAP_VALUES.items():
                    if val_str in comment:
                        count = quantity if quantity > 0 else (
                            len(designators.split(",")) if designators else 0)
                        caps.append((val_str, count, val))
                        break
    except FileNotFoundError:
        pass

    return caps


def analyze_power_resonance(cache, bom_path=BOM_FILE):
    """Estimate power plane LC resonance and check for problems."""
    caps = _parse_bom_caps(bom_path)

    if not caps:
        return {"status": "SKIP", "reason": "No capacitors found in BOM"}

    # Total capacitance
    total_c = sum(count * val for _, count, val in caps)
    total_count = sum(count for _, count, _ in caps)

    # Plane inductance estimate
    l_plane = MU0 * DIELECTRIC_D / (BOARD_W * BOARD_L)

    # Resonance frequency
    f_res = 1.0 / (2 * math.pi * math.sqrt(l_plane * total_c))

    # Effective parallel ESR (all caps in parallel)
    esr_sum_inv = 0
    for val_str, count, _ in caps:
        esr = ESR_TYPICAL.get(val_str, 0.010)
        if esr > 0 and count > 0:
            esr_sum_inv += count / esr
    esr_parallel = 1.0 / esr_sum_inv if esr_sum_inv > 0 else 0.010

    # Q factor: Q = (1/ESR) * sqrt(L/C) — lower is better (more damped)
    q_factor = (1.0 / esr_parallel) * math.sqrt(l_plane / total_c) if esr_parallel > 0 else 999

    # Check problematic ranges
    in_wifi = WIFI_BAND[0] <= f_res <= WIFI_BAND[1]
    in_display = DISPLAY_BUS[0] <= f_res <= DISPLAY_BUS[1]

    cap_breakdown = [(vs, c) for vs, c, _ in caps]

    return {
        "status": "FAIL" if (in_wifi or in_display) else "PASS",
        "total_capacitance_uF": round(total_c * 1e6, 1),
        "total_caps": total_count,
        "cap_breakdown": cap_breakdown,
        "plane_inductance_nH": round(l_plane * 1e9, 2),
        "resonance_MHz": round(f_res / 1e6, 1),
        "q_factor": round(q_factor, 1),
        "esr_parallel_mOhm": round(esr_parallel * 1000, 2),
        "in_wifi_band": in_wifi,
        "in_display_band": in_display,
    }


class TestPowerResonance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = load_cache(PCB_FILE)
        cls.result = analyze_power_resonance(cls.cache)

    def test_not_in_wifi_band(self):
        if self.result["status"] == "SKIP":
            self.skipTest(self.result["reason"])
        self.assertFalse(self.result["in_wifi_band"],
                         f"Resonance at {self.result['resonance_MHz']}MHz "
                         f"falls in WiFi band (2.4-2.5 GHz)")

    def test_not_in_display_band(self):
        if self.result["status"] == "SKIP":
            self.skipTest(self.result["reason"])
        self.assertFalse(self.result["in_display_band"],
                         f"Resonance at {self.result['resonance_MHz']}MHz "
                         f"falls in display bus band (10-20 MHz)")


def main():
    cache = load_cache(PCB_FILE)
    result = analyze_power_resonance(cache)

    print("\n\u2500\u2500 Power Plane Resonance \u2500\u2500")
    if result["status"] == "SKIP":
        print(f"  SKIP  {result['reason']}")
        return 0

    # Capacitor breakdown
    breakdown = ", ".join(f"{c}x {v}" for v, c in result["cap_breakdown"])
    print(f"  INFO  +3V3 total decoupling: {result['total_capacitance_uF']}uF "
          f"({breakdown})")
    print(f"  INFO  Estimated plane inductance: {result['plane_inductance_nH']} nH")
    print(f"  INFO  Resonance frequency: {result['resonance_MHz']} MHz")

    # WiFi check
    if result["in_wifi_band"]:
        print("  FAIL  Resonance in WiFi band (2.4-2.5 GHz) -- add decoupling")
    else:
        print("  PASS  Resonance outside critical WiFi band (2.4 GHz)")

    # Display bus check
    if result["in_display_band"]:
        print(f"  FAIL  Resonance at {result['resonance_MHz']}MHz overlaps "
              "display bus (10-20 MHz 8080)")
    else:
        print("  PASS  Resonance outside display bus frequency (10-20 MHz 8080)")

    # Q factor
    q = result["q_factor"]
    q_desc = "well damped" if q < 5 else "moderate" if q < 10 else "underdamped"
    print(f"  INFO  Estimated Q factor: {q} ({q_desc}, ESR={result['esr_parallel_mOhm']}mOhm)")

    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main())
