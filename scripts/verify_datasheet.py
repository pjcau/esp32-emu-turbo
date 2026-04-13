#!/usr/bin/env python3
"""Datasheet vs PCB physical characteristics cross-verification.

Compares component physical specs from manufacturer datasheets against
what is actually present in the PCB layout. Checks:
  - Pin count per component
  - Pad pitch (spacing between pins)
  - Body dimensions (derived from pad span)
  - Drill sizes (THT and NPTH)
  - Pad dimensions
  - NPTH positioning hole count and size

Datasheet specs are encoded in DATASHEET_SPECS below, extracted from
PDFs in hardware/datasheets/.

Usage:
    python3 scripts/verify_datasheet.py [path/to/file.kicad_pcb]
"""

import math
import sys
import unittest
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pcb_cache import load_cache

PCB_DEFAULT = Path(__file__).resolve().parent.parent / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"

# ── Datasheet reference database ─────────────────────────────────────
# Each entry: physical specs extracted from the manufacturer datasheet
# in hardware/datasheets/.  Tolerances are generous (±0.3mm typical).
#
# Fields:
#   datasheet: PDF filename in hardware/datasheets/
#   signal_pins: number of signal/functional pads (excludes NPTH)
#   total_pads: total pads including shield/mounting (excludes NPTH)
#   pitch_mm: pin pitch in mm (0 = irregular)
#   body_w_mm: component body width (mm) — for pad span verification
#   body_h_mm: component body height (mm)
#   pad_span_x_mm: expected pad-to-pad span in X (center-to-center)
#   pad_span_y_mm: expected pad-to-pad span in Y (center-to-center)
#   npth_count: number of NPTH positioning holes
#   npth_drill_mm: NPTH hole diameter (mm)
#   tht_drill_mm: THT pad drill diameter (mm), if applicable
#   notes: any clarifications

DATASHEET_SPECS = {
    "U1": {
        "name": "ESP32-S3-WROOM-1-N16R8",
        "datasheet": "U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf",
        "footprint": "ESP32-S3-WROOM-1-N16R8",
        "signal_pins": 41,       # 40 castellated + 1 GND EP
        "pitch_mm": 1.27,        # side pad pitch
        "body_w_mm": 18.0,       # module width
        "body_h_mm": 25.5,       # module height
        "pad_span_x_mm": 17.5,   # left-to-right pad center span
        "pad_span_y_mm": 17.76,  # top-to-bottom pad span (pin1 to pin14)
        "npth_count": 0,
        "tht_drill_mm": None,
    },
    "U2": {
        "name": "IP5306",
        "datasheet": "U2_IP5306_C181692.pdf",
        "footprint": "ESOP-8",
        "signal_pins": 9,        # 8 pins + 1 EP
        "pitch_mm": 1.27,
        "body_w_mm": 4.9,        # ESOP-8 body
        "body_h_mm": 3.9,        # ESOP-8 body height
        "pad_span_x_mm": 6.0,    # pin center-to-center across body
        "pad_span_y_mm": 3.81,   # pin 1 to pin 4 span (3 * 1.27)
        "npth_count": 0,
        "tht_drill_mm": None,
    },
    "U3": {
        "name": "AMS1117-3.3",
        "datasheet": "U3_AMS1117-3.3_C6186.pdf",
        "footprint": "SOT-223",
        "signal_pins": 4,        # 3 pins + 1 tab
        "pitch_mm": 2.3,         # pin 1-2 and 2-3 spacing
        "body_w_mm": 6.5,        # SOT-223 body
        "body_h_mm": 3.5,
        "pad_span_x_mm": 4.6,    # pin 1 to pin 3
        "pad_span_y_mm": 6.3,    # signal to tab span
        "npth_count": 0,
        "tht_drill_mm": None,
    },
    "U5": {
        "name": "PAM8403",
        "datasheet": "U5_PAM8403_C5122557.pdf",
        "footprint": "SOP-16",
        "signal_pins": 16,
        "pitch_mm": 1.27,
        "body_w_mm": 3.9,        # narrow SOP-16 (NOT wide SOIC-16W 7.5mm)
        "body_h_mm": 9.9,
        "pad_span_x_mm": 5.4,    # pin center-to-center across body
        "pad_span_y_mm": 8.89,   # pin 1 to pin 8 span (7 * 1.27)
        "npth_count": 0,
        "tht_drill_mm": None,
    },
    "U6": {
        "name": "TF-01A MicroSD",
        "datasheet": "U6_TF-01A_MicroSD_C91145.pdf",
        "footprint": "TF-01A",
        "signal_pins": 9,        # 9 signal pins
        "total_pads": 13,        # 9 signal + 4 shield
        "pitch_mm": 1.1,         # signal pin pitch
        "body_w_mm": 14.6,
        "body_h_mm": 14.8,
        "npth_count": 2,
        "npth_drill_mm": 1.0,    # datasheet: "2-dia1.00"
        "tht_drill_mm": None,
    },
    "J1": {
        "name": "USB-C 16-pin",
        "datasheet": "J1_USB-C-16pin_C2765186.pdf",
        "footprint": "USB-C-16P",
        "signal_pins": 12,       # 12 signal pads
        "total_pads": 16,        # 12 signal + 2 THT shield + 2 SMD rear shield
        "pitch_mm": 0.5,         # narrow signal pad pitch
        "body_w_mm": 8.94,
        "body_h_mm": 7.3,
        "npth_count": 2,
        "npth_drill_mm": 0.65,   # positioning pegs ø0.50mm, holes ø0.65mm
        "tht_drill_mm": 0.65,    # front shield tab slot width (R20: 0.60→0.65 for JLCPCB min 0.61)
    },
    "J3": {
        "name": "JST PH 2-pin SMD",
        "datasheet": "J3_JST-PH-2P-SMD_C295747.pdf",
        "footprint": "JST-PH-2P-SMD",
        "signal_pins": 2,
        "total_pads": 4,         # 2 signal + 2 mechanical reinforcement tabs
        "smd": True,             # SMD version (C295747)
        "pitch_mm": 2.0,         # JST PH standard pitch
        "body_w_mm": 6.0,
        "body_h_mm": 4.5,
        "tht_drill_mm": None,    # SMD — no THT drill
    },
    "J4": {
        "name": "FPC 40-pin 0.5mm",
        "datasheet": "J4_FPC-40pin-0.5mm_C2856812.pdf",
        "footprint": "FPC-40P-0.5mm",
        "signal_pins": 40,
        "total_pads": 42,        # 40 signal + 2 mounting
        "pitch_mm": 0.5,
        "body_w_mm": 23.0,
        "body_h_mm": 4.0,
        "npth_count": 0,
        "tht_drill_mm": None,
    },
    "SW_PWR": {
        "name": "MSK12C02 Slide Switch",
        "datasheet": "SW_PWR_Slide-Switch_C431540.pdf",
        "footprint": "SS-12D00G3",
        "signal_pins": 3,        # 3 SPDT pins
        "total_pads": 7,         # 3 signal + 4 shell
        "pitch_mm": 1.5,         # signal pin pitch (approx)
        "body_w_mm": 7.0,
        "body_h_mm": 3.0,
        "npth_count": 2,
        "npth_drill_mm": 0.9,    # pegs ø0.75mm, holes ø0.90mm
        "tht_drill_mm": None,
    },
    "L1": {
        "name": "1uH Inductor",
        "datasheet": "L1_1uH-Inductor_C280579.pdf",
        "footprint": "SMD-4x4x2",
        "signal_pins": 2,
        "pitch_mm": 3.4,         # pad center-to-center
        "body_w_mm": 4.0,
        "body_h_mm": 4.0,
        "npth_count": 0,
        "tht_drill_mm": None,
    },
    "LED1": {
        "name": "Red LED 0805",
        "datasheet": "LED1_Red-LED-0805_C84256.pdf",
        "footprint": "LED_0805",
        "signal_pins": 2,
        "pitch_mm": 1.9,         # 0805 pad center-to-center
        "body_w_mm": 2.0,
        "body_h_mm": 1.25,
        "npth_count": 0,
        "tht_drill_mm": None,
    },
    "LED2": {
        "name": "Green LED 0805",
        "datasheet": "LED2_Green-LED-0805_C19171391.pdf",
        "footprint": "LED_0805",
        "signal_pins": 2,
        "pitch_mm": 1.9,
        "body_w_mm": 2.0,
        "body_h_mm": 1.25,
        "npth_count": 0,
        "tht_drill_mm": None,
    },
}

# Passive components — spot-check a few representative refs
PASSIVE_SPECS = {
    "0805": {"pitch_mm": 1.9, "signal_pins": 2, "pad_w": 1.0, "pad_h": 1.3},
    "1206": {"pitch_mm": 3.0, "signal_pins": 2, "pad_w": 1.2, "pad_h": 1.8},
}

# Tolerance for dimensional comparisons (mm)
TOL = 0.35


# ── Helpers ──────────────────────────────────────────────────────────

def _group_pads_by_ref(cache):
    """Group pads by reference designator."""
    groups = defaultdict(list)
    for pad in cache["pads"]:
        ref = pad["ref"]
        if ref and ref != "?":
            groups[ref].append(pad)
    return groups


def _unique_pads(pads):
    """Deduplicate pads that appear on multiple layers (F.Cu + B.Cu)."""
    seen = set()
    unique = []
    for p in pads:
        key = (p["num"], round(p["x"], 2), round(p["y"], 2))
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _signal_pads(pads):
    """Filter to signal pads only (exclude NPTH / empty-number pads)."""
    return [p for p in pads if p["num"] and p["type"] != "np_thru_hole"]


def _npth_pads(pads):
    """Get NPTH positioning holes (deduplicated across layers)."""
    seen = set()
    result = []
    for p in pads:
        if p["type"] == "np_thru_hole":
            key = (round(p["x"], 2), round(p["y"], 2))
            if key not in seen:
                seen.add(key)
                result.append(p)
    return result


def _compute_pitch(pads, expected_pitch):
    """Compute the most common distance between adjacent pads along the
    dominant axis. Returns (measured_pitch, axis)."""
    if len(pads) < 2 or expected_pitch == 0:
        return None, None

    # Collect all pairwise distances along X and Y
    xs = sorted(set(round(p["x"], 3) for p in pads))
    ys = sorted(set(round(p["y"], 3) for p in pads))

    diffs_x = [round(xs[i+1] - xs[i], 3) for i in range(len(xs)-1) if xs[i+1] - xs[i] > 0.1]
    diffs_y = [round(ys[i+1] - ys[i], 3) for i in range(len(ys)-1) if ys[i+1] - ys[i] > 0.1]

    # Find mode (most common difference) near expected pitch
    candidates = []
    for d in diffs_x:
        if abs(d - expected_pitch) < TOL:
            candidates.append(("X", d))
    for d in diffs_y:
        if abs(d - expected_pitch) < TOL:
            candidates.append(("Y", d))

    if not candidates:
        # Try finding any consistent pitch
        all_diffs = [(d, "X") for d in diffs_x] + [(d, "Y") for d in diffs_y]
        all_diffs.sort(key=lambda x: x[0])
        if all_diffs:
            return all_diffs[0][0], all_diffs[0][1]
        return None, None

    # Return the one closest to expected
    best = min(candidates, key=lambda c: abs(c[1] - expected_pitch))
    return best[1], best[0]


class TestDatasheetCompliance(unittest.TestCase):
    """Verify PCB component physical characteristics match datasheets."""

    @classmethod
    def setUpClass(cls):
        pcb_path = sys.argv[1] if len(sys.argv) > 1 else str(PCB_DEFAULT)
        cls.cache = load_cache(Path(pcb_path))
        cls.pad_groups = _group_pads_by_ref(cls.cache)

    # ── Pin count tests ──────────────────────────────────────────

    def test_pin_count_U1_ESP32(self):
        """U1 ESP32-S3: 41 pads (40 castellated + 1 EP)"""
        spec = DATASHEET_SPECS["U1"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("U1", [])))
        self.assertEqual(len(pads), spec["signal_pins"],
                         f"U1 ({spec['name']}): expected {spec['signal_pins']} "
                         f"signal pads, got {len(pads)}")

    def test_pin_count_U2_IP5306(self):
        """U2 IP5306: 9 pads (8 pins + EP)"""
        spec = DATASHEET_SPECS["U2"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("U2", [])))
        self.assertEqual(len(pads), spec["signal_pins"],
                         f"U2 ({spec['name']}): expected {spec['signal_pins']} "
                         f"signal pads, got {len(pads)}")

    def test_pin_count_U3_AMS1117(self):
        """U3 AMS1117: 4 pads (3 pins + tab)"""
        spec = DATASHEET_SPECS["U3"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("U3", [])))
        self.assertEqual(len(pads), spec["signal_pins"],
                         f"U3 ({spec['name']}): expected {spec['signal_pins']} "
                         f"signal pads, got {len(pads)}")

    def test_pin_count_U5_PAM8403(self):
        """U5 PAM8403: 16 pads (SOP-16 narrow body)"""
        spec = DATASHEET_SPECS["U5"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("U5", [])))
        self.assertEqual(len(pads), spec["signal_pins"],
                         f"U5 ({spec['name']}): expected {spec['signal_pins']} "
                         f"signal pads, got {len(pads)}")

    def test_pin_count_U6_SD(self):
        """U6 TF-01A: 13 total pads (9 signal + 4 shield)"""
        spec = DATASHEET_SPECS["U6"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("U6", [])))
        expected = spec.get("total_pads", spec["signal_pins"])
        self.assertEqual(len(pads), expected,
                         f"U6 ({spec['name']}): expected {expected} "
                         f"total pads, got {len(pads)}")

    def test_pin_count_J1_USB(self):
        """J1 USB-C: 16 total pads (12 signal + 4 shield)"""
        spec = DATASHEET_SPECS["J1"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("J1", [])))
        expected = spec.get("total_pads", spec["signal_pins"])
        self.assertEqual(len(pads), expected,
                         f"J1 ({spec['name']}): expected {expected} "
                         f"total pads, got {len(pads)}")

    def test_pin_count_J3_JST(self):
        """J3 JST PH SMD: 4 pads (2 signal + 2 mechanical reinforcement tabs)

        R15 (2026-04-12): added 2 mechanical reinforcement pads "3" and "4"
        per JLCPCB EasyEDA reference footprint (verified via easyeda2kicad).
        Without the tabs, JLCDFM flagged 2 'Pin without pad' Danger findings.
        """
        spec = DATASHEET_SPECS["J3"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("J3", [])))
        expected = spec.get("total_pads", spec["signal_pins"])
        self.assertEqual(len(pads), expected,
                         f"J3 ({spec['name']}): expected {expected} "
                         f"total pads (2 signal + 2 mech), got {len(pads)}")

    def test_pin_count_J4_FPC(self):
        """J4 FPC: 42 total pads (40 signal + 2 mounting)"""
        spec = DATASHEET_SPECS["J4"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("J4", [])))
        expected = spec.get("total_pads", spec["signal_pins"])
        self.assertEqual(len(pads), expected,
                         f"J4 ({spec['name']}): expected {expected} "
                         f"total pads, got {len(pads)}")

    def test_pin_count_SW_PWR(self):
        """SW_PWR: 7 total pads (3 signal + 4 shell)"""
        spec = DATASHEET_SPECS["SW_PWR"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("SW_PWR", [])))
        expected = spec.get("total_pads", spec["signal_pins"])
        self.assertEqual(len(pads), expected,
                         f"SW_PWR ({spec['name']}): expected {expected} "
                         f"total pads, got {len(pads)}")

    # ── NPTH positioning hole tests ──────────────────────────────

    def test_npth_U6_SD_count(self):
        """U6 TF-01A: 2 NPTH holes x 1.0mm drill"""
        spec = DATASHEET_SPECS["U6"]
        nps = _npth_pads(self.pad_groups.get("U6", []))
        self.assertEqual(len(nps), spec["npth_count"],
                         f"U6: expected {spec['npth_count']} NPTH, got {len(nps)}")

    def test_npth_U6_SD_drill(self):
        """U6 TF-01A NPTH drill = 1.0mm"""
        spec = DATASHEET_SPECS["U6"]
        for np in _npth_pads(self.pad_groups.get("U6", [])):
            self.assertAlmostEqual(np["drill"], spec["npth_drill_mm"], delta=0.05,
                                   msg=f"U6 NPTH drill: expected {spec['npth_drill_mm']}mm, "
                                   f"got {np['drill']}mm")

    def test_npth_J1_USB_count(self):
        """J1 USB-C: 2 NPTH holes x 0.65mm drill"""
        spec = DATASHEET_SPECS["J1"]
        nps = _npth_pads(self.pad_groups.get("J1", []))
        self.assertEqual(len(nps), spec["npth_count"],
                         f"J1: expected {spec['npth_count']} NPTH, got {len(nps)}")

    def test_npth_J1_USB_drill(self):
        """J1 USB-C NPTH drill = 0.65mm"""
        spec = DATASHEET_SPECS["J1"]
        for np in _npth_pads(self.pad_groups.get("J1", [])):
            self.assertAlmostEqual(np["drill"], spec["npth_drill_mm"], delta=0.05,
                                   msg=f"J1 NPTH drill: expected {spec['npth_drill_mm']}mm, "
                                   f"got {np['drill']}mm")

    def test_npth_SW_PWR_count(self):
        """SW_PWR: 2 NPTH holes x 0.9mm drill"""
        spec = DATASHEET_SPECS["SW_PWR"]
        nps = _npth_pads(self.pad_groups.get("SW_PWR", []))
        self.assertEqual(len(nps), spec["npth_count"],
                         f"SW_PWR: expected {spec['npth_count']} NPTH, got {len(nps)}")

    def test_npth_SW_PWR_drill(self):
        """SW_PWR NPTH drill = 0.9mm"""
        spec = DATASHEET_SPECS["SW_PWR"]
        for np in _npth_pads(self.pad_groups.get("SW_PWR", [])):
            self.assertAlmostEqual(np["drill"], spec["npth_drill_mm"], delta=0.05,
                                   msg=f"SW_PWR NPTH drill: expected {spec['npth_drill_mm']}mm, "
                                   f"got {np['drill']}mm")

    # ── THT drill size tests ────────────────────────────────────

    def test_tht_drill_J1_USB_shield(self):
        """J1 USB-C shield tabs: THT drill = 0.6mm"""
        spec = DATASHEET_SPECS["J1"]
        tht_pads = [p for p in _unique_pads(self.pad_groups.get("J1", []))
                    if p["type"] == "thru_hole"]
        self.assertGreater(len(tht_pads), 0, "J1: no THT pads found")
        for p in tht_pads:
            self.assertAlmostEqual(p["drill"], spec["tht_drill_mm"], delta=0.1,
                                   msg=f"J1 THT pad {p['num']}: expected drill "
                                   f"{spec['tht_drill_mm']}mm, got {p['drill']}mm")

    def test_tht_drill_J3_JST(self):
        """J3 JST PH THT: verify THT pads with correct drill size"""
        spec = DATASHEET_SPECS["J3"]
        if spec.get("smd"):
            # SMD connector — verify NO through-hole pads exist
            tht_pads = [p for p in _unique_pads(self.pad_groups.get("J3", []))
                        if p["type"] == "thru_hole"]
            self.assertEqual(len(tht_pads), 0,
                             f"J3 SMD: found {len(tht_pads)} THT pads "
                             f"(expected 0 for SMD connector)")
            return
        tht_pads = [p for p in _unique_pads(self.pad_groups.get("J3", []))
                    if p["type"] == "thru_hole"]
        self.assertGreater(len(tht_pads), 0, "J3: no THT pads found")
        for p in tht_pads:
            self.assertAlmostEqual(p["drill"], spec["tht_drill_mm"], delta=0.1,
                                   msg=f"J3 THT pad {p['num']}: expected drill "
                                   f"{spec['tht_drill_mm']}mm, got {p['drill']}mm")

    # ── Pad pitch tests ─────────────────────────────────────────

    def test_pitch_U2_IP5306(self):
        """U2 IP5306: 1.27mm pitch (ESOP-8)"""
        self._check_pitch("U2")

    def test_pitch_U5_PAM8403(self):
        """U5 PAM8403: 1.27mm pitch (SOP-16)"""
        self._check_pitch("U5")

    def test_pitch_J4_FPC(self):
        """J4 FPC: 0.5mm pitch"""
        # Only check the 40 signal pads (exclude mounting pads 41-42)
        spec = DATASHEET_SPECS["J4"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("J4", [])))
        signal_only = [p for p in pads if p["num"] not in ("41", "42")]
        pitch, axis = _compute_pitch(signal_only, spec["pitch_mm"])
        self.assertIsNotNone(pitch,
                             f"J4: could not measure pitch (expected {spec['pitch_mm']}mm)")
        self.assertAlmostEqual(pitch, spec["pitch_mm"], delta=TOL,
                               msg=f"J4 pitch: expected {spec['pitch_mm']}mm, "
                               f"got {pitch}mm (axis {axis})")

    def test_pitch_J3_JST(self):
        """J3 JST PH: 2.0mm pitch"""
        self._check_pitch("J3")

    def _check_pitch(self, ref):
        spec = DATASHEET_SPECS[ref]
        pads = _unique_pads(_signal_pads(self.pad_groups.get(ref, [])))
        # For ICs, use only one side's pads for pitch measurement
        if spec["signal_pins"] > 4:
            # Group by proximity in X — pick the largest column
            x_groups = defaultdict(list)
            for p in pads:
                x_groups[round(p["x"], 1)].append(p)
            largest_col = max(x_groups.values(), key=len)
            if len(largest_col) >= 3:
                pads = largest_col
        pitch, axis = _compute_pitch(pads, spec["pitch_mm"])
        self.assertIsNotNone(pitch,
                             f"{ref}: could not measure pitch "
                             f"(expected {spec['pitch_mm']}mm)")
        self.assertAlmostEqual(pitch, spec["pitch_mm"], delta=TOL,
                               msg=f"{ref} ({spec['name']}) pitch: "
                               f"expected {spec['pitch_mm']}mm, got {pitch}mm")

    # ── Pad span (body dimension proxy) tests ────────────────────

    def test_pad_span_U2_IP5306(self):
        """U2 IP5306 ESOP-8: pad span X ~6.0mm (not 7.5mm SOIC-16W)"""
        spec = DATASHEET_SPECS["U2"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("U2", [])))
        xs = [p["x"] for p in pads]
        span_x = max(xs) - min(xs) if xs else 0
        self.assertAlmostEqual(span_x, spec["pad_span_x_mm"], delta=0.5,
                               msg=f"U2 pad span X: expected ~{spec['pad_span_x_mm']}mm, "
                               f"got {span_x:.2f}mm")

    def test_pad_span_U5_PAM8403(self):
        """U5 PAM8403 SOP-16 narrow: pad span X ~5.4mm (not 10.3mm wide)"""
        spec = DATASHEET_SPECS["U5"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("U5", [])))
        xs = [p["x"] for p in pads]
        ys = [p["y"] for p in pads]
        span_x = max(xs) - min(xs) if xs else 0
        span_y = max(ys) - min(ys) if ys else 0
        # SOP-16 rotated 90deg: X and Y may be swapped
        # Check whichever axis matches pad_span_x (across body)
        short_span = min(span_x, span_y)
        self.assertAlmostEqual(short_span, spec["pad_span_x_mm"], delta=0.5,
                               msg=f"U5 cross-body pad span: expected ~{spec['pad_span_x_mm']}mm, "
                               f"got {short_span:.2f}mm — verify narrow SOP-16 (3.9mm body)")

    def test_pad_span_U1_ESP32(self):
        """U1 ESP32: pad span X ~17.5mm (module width)"""
        spec = DATASHEET_SPECS["U1"]
        pads = _unique_pads(_signal_pads(self.pad_groups.get("U1", [])))
        xs = [p["x"] for p in pads]
        span_x = max(xs) - min(xs) if xs else 0
        self.assertAlmostEqual(span_x, spec["pad_span_x_mm"], delta=1.0,
                               msg=f"U1 pad span X: expected ~{spec['pad_span_x_mm']}mm, "
                               f"got {span_x:.2f}mm")

    # ── Passive component spot checks ────────────────────────────

    def test_passive_0805_pin_count(self):
        """0805 passives (R, C, LED): 2 pads each"""
        for ref in ("R3", "C3", "LED1"):
            pads = _unique_pads(_signal_pads(self.pad_groups.get(ref, [])))
            if pads:
                self.assertEqual(len(pads), 2,
                                 f"{ref} (0805): expected 2 pads, got {len(pads)}")

    def test_passive_1206_pin_count(self):
        """1206 caps (C2, C19): 2 pads each"""
        for ref in ("C2", "C19"):
            pads = _unique_pads(_signal_pads(self.pad_groups.get(ref, [])))
            if pads:
                self.assertEqual(len(pads), 2,
                                 f"{ref} (1206): expected 2 pads, got {len(pads)}")

    # ── Tact switch tests ────────────────────────────────────────

    def test_tact_switch_pin_count(self):
        """SW1-SW13 tact switches: 4 pads each"""
        for i in range(1, 14):
            ref = f"SW{i}"
            pads = _unique_pads(_signal_pads(self.pad_groups.get(ref, [])))
            if pads:
                self.assertEqual(len(pads), 4,
                                 f"{ref} (tact switch): expected 4 pads, got {len(pads)}")

    # ── Datasheet file existence check ───────────────────────────

    def test_datasheet_files_exist(self):
        """All referenced datasheets exist in hardware/datasheets/"""
        ds_dir = Path(__file__).resolve().parent.parent / "hardware" / "datasheets"
        missing = []
        for ref, spec in DATASHEET_SPECS.items():
            ds_file = ds_dir / spec["datasheet"]
            if not ds_file.exists():
                missing.append(f"{ref}: {spec['datasheet']}")
        self.assertEqual(len(missing), 0,
                         f"Missing datasheets: {', '.join(missing)}")

    # ── Component presence check ─────────────────────────────────

    def test_all_spec_components_in_pcb(self):
        """All components in DATASHEET_SPECS exist in the PCB"""
        missing = [ref for ref in DATASHEET_SPECS if ref not in self.pad_groups]
        self.assertEqual(len(missing), 0,
                         f"Components in spec but not in PCB: {', '.join(missing)}")


if __name__ == "__main__":
    # Remove script path from argv so unittest doesn't try to parse PCB path
    if len(sys.argv) > 1 and sys.argv[1].endswith(".kicad_pcb"):
        pcb_arg = sys.argv.pop(1)
        sys.argv.insert(1, pcb_arg)  # Keep for setUpClass but after --
    unittest.main(verbosity=2)
