#!/usr/bin/env python3
"""USB D+/D- signal-integrity check, calibrated to the link's actual bit rate.

WHY THIS FILE LOOKS THE WAY IT DOES — READ BEFORE "FIXING" THE LAYOUT
====================================================================

This board's USB port is **USB 2.0 Full Speed, 12 Mbit/s**, driven by the
ESP32-S3's native USB-Serial-JTAG peripheral. It is NOT High Speed.

An earlier version of this script applied High Speed (480 Mbit/s) design
rules — a 0.18-0.25 mm width window for a 90 ohm differential target and
a 2.0 mm intra-pair skew limit — and failed the board for a 0.15 mm
segment and 2.5 mm of skew. Both "failures" were artefacts of using the
wrong rate:

  * Controlled impedance only matters once the interconnect is
    electrically long compared with the signal's rise time. USB Full
    Speed drivers have a specified rise/fall time of 4-20 ns (USB 2.0
    spec, table 7-9), so even the fastest 4 ns edge has a critical
    length of ~110 mm on this stackup (see _derive_limits below). The
    D+/D- run here is ~43 mm — roughly 0.13 % of a wavelength at
    12 Mbit/s. Matching it to 90 ohm changes nothing measurable.

  * Likewise for skew. 2.5 mm of FR4 is about 15 ps of delay. At
    12 Mbit/s the unit interval is 83.3 ns, so that is 0.02 % of a bit.
    The 2.0 mm limit is a High Speed number.

So the thresholds below are DERIVED from the configured signalling rate
rather than hard-coded, and the things actually checked at Full Speed
are the ones that can really break a Full Speed link: the pair being
routed at all, the series termination resistors genuinely sitting in the
path, the ESD device sitting on the connector side of them, a sane
return path, and manufacturability of the trace width.

If USB_SPEED is ever changed to "high", the same derivation produces
High Speed limits automatically (critical length drops to ~14 mm, skew
budget to a few tenths of a millimetre) and the impedance-window width
check switches itself on. Nothing here needs re-tuning by hand.

Do NOT move components or re-route traces to satisfy an impedance
target on this board. See also
memory/feedback_usb_impedance_non_issue.md.

Usage:
    python3 scripts/verify_usb_impedance.py
    python3 scripts/verify_usb_impedance.py --test
    Exit code 0 = pass, 1 = failure
"""

import copy
import csv
import math
import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")
BOM_FILE = os.path.join(BASE, "release_jlcpcb", "bom.csv")

# ---------------------------------------------------------------------------
# Design configuration
# ---------------------------------------------------------------------------

# The link this board actually implements. Change this one string if the
# design ever moves to another USB speed — every threshold follows.
USB_SPEED = "full"

# Per-speed signalling parameters.
#   bitrate_bps : line rate, used for the unit interval
#   rise_time_s : fastest specified driver rise/fall time (10-90 %).
#                 USB 2.0 spec: Low Speed 75 ns min, Full Speed 4 ns min,
#                 High Speed 500 ps nominal.
USB_SPEEDS = {
    "low":  {"bitrate_bps": 1.5e6, "rise_time_s": 75e-9},
    "full": {"bitrate_bps": 12e6,  "rise_time_s": 4e-9},
    "high": {"bitrate_bps": 480e6, "rise_time_s": 500e-12},
}

# Propagation delay of a trace on this stackup, seconds per millimetre.
# JLC04161H-7628 4-layer FR4: outer-layer microstrip with an adjacent
# plane gives an effective permittivity around 3.2, i.e. a propagation
# velocity of c/sqrt(3.2) = 168 mm/ns -> 5.96 ps/mm. 6.0 ps/mm is used
# as a round, slightly conservative figure. Inner-layer stripline would
# be ~7.1 ps/mm; using the smaller number makes the derived critical
# length shorter, i.e. the check stricter.
PROP_DELAY_S_PER_MM = 6.0e-12

# An interconnect is treated as a transmission line — and therefore as
# needing a controlled impedance — once its one-way delay exceeds
# rise_time / ELECTRICAL_LENGTH_DIVISOR. 6 is the usual conservative
# choice (some texts use 4, RF practice uses 10 for lambda/10); a larger
# divisor means a shorter critical length, i.e. a stricter check.
ELECTRICAL_LENGTH_DIVISOR = 6.0

# Intra-pair skew budget, expressed as fractions so it scales with rate:
#   - a fraction of the rise time, so the differential crossing point is
#     not displaced appreciably, and
#   - a fraction of the unit interval, so it cannot eat the data eye.
# The tighter of the two applies. At Full Speed the rise-time term binds
# (200 ps -> 33 mm); at High Speed the UI term binds (~21 ps -> 3.5 mm).
SKEW_FRACTION_OF_RISE_TIME = 0.05
SKEW_FRACTION_OF_UI = 0.01

# Differential impedance target and the width window that achieves it on
# this stackup. Only enforced when the pair is electrically long.
ZDIFF_TARGET_OHM = 90
ZDIFF_WIDTH_MIN_MM = 0.18
ZDIFF_WIDTH_MAX_MM = 0.25

# Manufacturability floor, always enforced regardless of rate.
# JLCPCB's documented minimum for 1 oz outer copper is 0.127 mm; this
# project's own net classes never go below 0.15 mm.
MIN_MANUFACTURABLE_WIDTH_MM = 0.127

# Nets and parts that make up the USB data path.
USB_DP_NET = "USB_D+"
USB_DM_NET = "USB_D-"
USB_DP_MCU_NET = "USB_DP_MCU"
USB_DM_MCU_NET = "USB_DM_MCU"

# Series termination: ref -> (connector-side net, MCU-side net).
SERIES_RESISTORS = {
    "R22": (USB_DP_NET, USB_DP_MCU_NET),
    "R23": (USB_DM_NET, USB_DM_MCU_NET),
}
# USB 2.0 source impedance is 28-44 ohm; the ESP32-S3 driver plus a 22
# ohm series resistor lands inside that window.
SERIES_RESISTOR_VALUE_OHM = 22
SERIES_RESISTOR_TOLERANCE_OHM = 5

# ESD device. USBLC6-2SC6: pins 1 and 6 are one internal I/O node, pins
# 3 and 4 the other, pin 2 GND, pin 5 the VBUS clamp reference.
ESD_REF = "U4"
ESD_EXPECTED_PADS = {
    "1": USB_DM_NET, "6": USB_DM_NET,
    "3": USB_DP_NET, "4": USB_DP_NET,
    "2": "GND",
    "5": "VBUS",
}

# Return path: a layer change on a data net needs a ground stitching via
# nearby so the return current has somewhere to go. How near is "near"
# scales with the rate as well. The natural yardstick is the physical
# length of the rising edge, rise_time / propagation_delay: 83 mm at
# High Speed, 667 mm at Full Speed. Requiring the return-path detour to
# stay under 1/30 of that reproduces the customary 2.5-3 mm High Speed
# stitching guideline and relaxes proportionally for slower edges, where
# the detour is electrically invisible.
STITCH_FRACTION_OF_RISE_LENGTH = 1.0 / 30.0

GND_NET = "GND"


# ---------------------------------------------------------------------------
# Derived limits
# ---------------------------------------------------------------------------

def derive_limits(speed=USB_SPEED):
    """Return the geometry limits implied by the signalling rate."""
    if speed not in USB_SPEEDS:
        raise ValueError(f"unknown USB speed {speed!r}")
    p = USB_SPEEDS[speed]
    ui_s = 1.0 / p["bitrate_bps"]
    tr_s = p["rise_time_s"]

    rise_length_mm = tr_s / PROP_DELAY_S_PER_MM
    critical_length_mm = rise_length_mm / ELECTRICAL_LENGTH_DIVISOR
    skew_budget_s = min(SKEW_FRACTION_OF_RISE_TIME * tr_s,
                        SKEW_FRACTION_OF_UI * ui_s)
    skew_budget_mm = skew_budget_s / PROP_DELAY_S_PER_MM

    return {
        "speed": speed,
        "bitrate_bps": p["bitrate_bps"],
        "rise_time_s": tr_s,
        "ui_s": ui_s,
        "rise_length_mm": rise_length_mm,
        "critical_length_mm": critical_length_mm,
        "max_skew_mm": skew_budget_mm,
        "max_skew_s": skew_budget_s,
        "max_stitch_dist_mm": rise_length_mm * STITCH_FRACTION_OF_RISE_LENGTH,
    }


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _seg_length(seg):
    dx = seg["x2"] - seg["x1"]
    dy = seg["y2"] - seg["y1"]
    return math.hypot(dx, dy)


def _seg_midpoint(seg):
    return ((seg["x1"] + seg["x2"]) / 2, (seg["y1"] + seg["y2"]) / 2)


def _point_to_seg_dist(px, py, seg):
    """Minimum distance from a point to a line segment."""
    x1, y1, x2, y2 = seg["x1"], seg["y1"], seg["x2"], seg["y2"]
    dx, dy = x2 - x1, y2 - y1
    len_sq = dx * dx + dy * dy
    if len_sq < 1e-10:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / len_sq))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


# ---------------------------------------------------------------------------
# BOM lookup (series resistor value)
# ---------------------------------------------------------------------------

def _bom_values():
    """ref -> comment string, from the released JLCPCB BOM (may be absent)."""
    values = {}
    if not os.path.exists(BOM_FILE):
        return values
    with open(BOM_FILE, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            comment = (row.get("Comment") or "").strip()
            for ref in (row.get("Designator") or "").split(","):
                ref = ref.strip()
                if ref:
                    values[ref] = comment
    return values


def _parse_ohms(comment):
    """Pull an ohm value out of a BOM comment such as '22R 0402' or '22'."""
    token = comment.split()[0] if comment.split() else ""
    token = token.upper().rstrip("RΩ")
    try:
        return float(token)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze_usb(cache, limits=None):
    """Analyse the USB data path. Returns a result dict with a findings list."""
    limits = limits or derive_limits()

    net_id = {n["name"]: n["id"] for n in cache["nets"] if n["name"]}
    segments = cache["segments"]
    vias = cache.get("vias", [])

    pad_net = {}
    for pad in cache["pads"]:
        key = (pad["ref"], str(pad["num"]))
        if key not in pad_net:
            pad_net[key] = pad["net"]

    dp_id = net_id.get(USB_DP_NET)
    dm_id = net_id.get(USB_DM_NET)
    if dp_id is None or dm_id is None:
        return {"status": "FAIL",
                "findings": [f"USB data nets not present in PCB: "
                             f"{USB_DP_NET}={dp_id} {USB_DM_NET}={dm_id}"],
                "limits": limits}

    dp_segs = [s for s in segments if s["net"] == dp_id]
    dm_segs = [s for s in segments if s["net"] == dm_id]
    # The MCU-side stubs are part of the same physical run; include them
    # in length/width accounting so the check sees the whole path.
    for name, target in ((USB_DP_MCU_NET, dp_segs), (USB_DM_MCU_NET, dm_segs)):
        nid = net_id.get(name)
        if nid is not None:
            target.extend(s for s in segments if s["net"] == nid)

    findings = []

    # ── 1. Continuity: both halves of the pair must actually be routed ──
    if not dp_segs:
        findings.append("D+ has no routed copper")
    if not dm_segs:
        findings.append("D- has no routed copper")
    if not dp_segs or not dm_segs:
        return {"status": "FAIL", "findings": findings, "limits": limits}

    dp_len = sum(_seg_length(s) for s in dp_segs)
    dm_len = sum(_seg_length(s) for s in dm_segs)
    max_len = max(dp_len, dm_len)
    electrically_long = max_len > limits["critical_length_mm"]

    widths = sorted({round(s["width"], 3) for s in dp_segs + dm_segs})

    # ── 2. Width ──
    # Manufacturability always; the impedance window only when the pair
    # is long enough for impedance to mean anything.
    too_thin = [w for w in widths if w < MIN_MANUFACTURABLE_WIDTH_MM]
    if too_thin:
        findings.append(
            f"trace width {too_thin} mm below the {MIN_MANUFACTURABLE_WIDTH_MM} mm "
            f"fabrication minimum")
    if electrically_long:
        off_target = [w for w in widths
                      if not (ZDIFF_WIDTH_MIN_MM <= w <= ZDIFF_WIDTH_MAX_MM)]
        if off_target:
            findings.append(
                f"pair is electrically long ({max_len:.1f} mm > "
                f"{limits['critical_length_mm']:.1f} mm critical length at "
                f"{limits['speed']} speed), so {ZDIFF_TARGET_OHM} ohm differential "
                f"control applies: widths {off_target} mm outside "
                f"{ZDIFF_WIDTH_MIN_MM}-{ZDIFF_WIDTH_MAX_MM} mm")

    # ── 3. Intra-pair skew ──
    skew_mm = abs(dp_len - dm_len)
    if skew_mm > limits["max_skew_mm"]:
        findings.append(
            f"intra-pair skew {skew_mm:.2f} mm "
            f"({skew_mm * PROP_DELAY_S_PER_MM * 1e12:.0f} ps) exceeds the "
            f"{limits['max_skew_mm']:.2f} mm budget derived from a "
            f"{limits['rise_time_s'] * 1e9:.1f} ns rise time and a "
            f"{limits['ui_s'] * 1e9:.1f} ns unit interval")

    # ── 4. Series termination resistors really in the path ──
    for ref, (bus_net, mcu_net) in SERIES_RESISTORS.items():
        pads = {num: net for (r, num), net in pad_net.items() if r == ref}
        if not pads:
            findings.append(f"series resistor {ref} missing from the board")
            continue
        nets_on_part = {n for n in pads.values() if n}
        want = {net_id.get(bus_net), net_id.get(mcu_net)}
        if nets_on_part != want:
            got = sorted(n["name"] for n in cache["nets"]
                         if n["id"] in nets_on_part)
            findings.append(
                f"series resistor {ref} does not bridge {bus_net} and "
                f"{mcu_net}; it sits on {got}")

    bom = _bom_values()
    for ref in SERIES_RESISTORS:
        if ref not in bom:
            continue
        ohms = _parse_ohms(bom[ref])
        if ohms is None:
            findings.append(f"cannot read a resistance for {ref} from the BOM "
                            f"({bom[ref]!r})")
        elif abs(ohms - SERIES_RESISTOR_VALUE_OHM) > SERIES_RESISTOR_TOLERANCE_OHM:
            findings.append(
                f"series resistor {ref} is {ohms:g} ohm; USB 2.0 needs a "
                f"{SERIES_RESISTOR_VALUE_OHM} ohm series element to land inside "
                f"the 28-44 ohm source impedance window")

    # ── 5. ESD device on the connector side ──
    esd_pads = {num: net for (r, num), net in pad_net.items() if r == ESD_REF}
    if not esd_pads:
        findings.append(f"ESD protection device {ESD_REF} missing from the board")
    else:
        for num, expected in ESD_EXPECTED_PADS.items():
            actual_id = esd_pads.get(num)
            expected_id = net_id.get(expected)
            if actual_id != expected_id:
                actual = next((n["name"] for n in cache["nets"]
                               if n["id"] == actual_id), "")
                findings.append(
                    f"ESD device {ESD_REF} pad {num} is on {actual or '<none>'!r}, "
                    f"expected {expected!r} (the TVS must clamp the CONNECTOR "
                    f"side of the series resistors)")

    # ── 6. Return path at layer changes ──
    dp_dm_ids = {dp_id, dm_id,
                 net_id.get(USB_DP_MCU_NET), net_id.get(USB_DM_MCU_NET)}
    data_vias = [v for v in vias if v["net"] in dp_dm_ids]
    gnd_id = net_id.get(GND_NET)
    gnd_vias = [v for v in vias if v["net"] == gnd_id]
    max_stitch = limits["max_stitch_dist_mm"]
    orphan_vias = []
    for v in data_vias:
        nearest = min((math.hypot(v["x"] - g["x"], v["y"] - g["y"])
                       for g in gnd_vias), default=float("inf"))
        if nearest > max_stitch:
            orphan_vias.append((round(v["x"], 2), round(v["y"], 2),
                                round(nearest, 2)))
    if orphan_vias:
        findings.append(
            f"{len(orphan_vias)} USB data via(s) have no ground stitching via "
            f"within {max_stitch:.1f} mm (1/{1 / STITCH_FRACTION_OF_RISE_LENGTH:.0f} "
            f"of the {limits['rise_length_mm']:.0f} mm rising-edge length) — the "
            f"return current has no path across the layer change: "
            f"{orphan_vias[:4]}")

    # ── 7. Pair coupling (informational, plus a gross-split guard) ──
    spacings = []
    for dp_seg in dp_segs:
        mx, my = _seg_midpoint(dp_seg)
        nearest = min((_point_to_seg_dist(mx, my, s) for s in dm_segs),
                      default=float("inf"))
        if nearest < 50:
            spacings.append(nearest)
    avg_spacing = sum(spacings) / len(spacings) if spacings else None

    return {
        "status": "PASS" if not findings else "FAIL",
        "findings": findings,
        "limits": limits,
        "dp_segments": len(dp_segs),
        "dm_segments": len(dm_segs),
        "dp_length_mm": round(dp_len, 2),
        "dm_length_mm": round(dm_len, 2),
        "skew_mm": round(skew_mm, 2),
        "widths": widths,
        "electrically_long": electrically_long,
        "data_vias": len(data_vias),
        "avg_spacing_mm": round(avg_spacing, 2) if avg_spacing else None,
        "dp_layers": sorted({s["layer"] for s in dp_segs}),
        "dm_layers": sorted({s["layer"] for s in dm_segs}),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUSBSignalIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = load_cache(PCB_FILE)
        cls.result = analyze_usb(cls.cache)

    def test_no_findings(self):
        self.assertEqual(self.result["findings"], [],
                         "USB data path findings: "
                         + "; ".join(self.result["findings"]))

    def test_limits_scale_with_rate(self):
        """The thresholds must come from the rate, not be hard-coded."""
        full = derive_limits("full")
        high = derive_limits("high")
        self.assertGreater(full["critical_length_mm"],
                           high["critical_length_mm"] * 5,
                           "Full Speed critical length must be far longer "
                           "than High Speed")
        self.assertGreater(full["max_skew_mm"], high["max_skew_mm"],
                           "Full Speed skew budget must be looser than High Speed")

    def test_high_speed_would_tighten(self):
        """Re-running the analysis as High Speed must engage the strict rules."""
        result = analyze_usb(self.cache, derive_limits("high"))
        self.assertTrue(result["electrically_long"],
                        "at 480 Mbit/s this run length must count as "
                        "electrically long")

    # ── Negative tests: the check must not be a no-op ──────────────
    # Each mutates a copy of the parsed board into a defect that would
    # really break a Full Speed link and asserts the check catches it.

    def _mutated(self, mutate):
        cache = copy.deepcopy(self.cache)
        mutate(cache, {n["name"]: n["id"] for n in cache["nets"] if n["name"]})
        return analyze_usb(cache)

    def _assert_fails(self, mutate, why):
        result = self._mutated(mutate)
        self.assertEqual(result["status"], "FAIL",
                         f"check failed to notice: {why}")

    def test_detects_missing_series_resistor(self):
        self._assert_fails(
            lambda c, n: c["pads"].__setitem__(
                slice(None), [p for p in c["pads"] if p["ref"] != "R22"]),
            "R22 series termination absent from the board")

    def test_detects_shorted_series_resistor(self):
        self._assert_fails(
            lambda c, n: [p.__setitem__("net", n["USB_D+"])
                          for p in c["pads"] if p["ref"] == "R22"],
            "R22 with both pads on the same net (series element bypassed)")

    def test_detects_missing_esd_device(self):
        self._assert_fails(
            lambda c, n: c["pads"].__setitem__(
                slice(None), [p for p in c["pads"] if p["ref"] != ESD_REF]),
            "USB ESD protection removed")

    def test_detects_esd_on_wrong_side_of_series_resistor(self):
        self._assert_fails(
            lambda c, n: [p.__setitem__("net", n["USB_DM_MCU"])
                          for p in c["pads"]
                          if p["ref"] == ESD_REF and str(p["num"]) == "6"],
            "TVS I/O pin moved to the MCU side, shorting R23 out")

    def test_detects_tvs_reference_on_boost_output(self):
        self._assert_fails(
            lambda c, n: [p.__setitem__("net", n["+5V"])
                          for p in c["pads"]
                          if p["ref"] == ESD_REF and str(p["num"]) == "5"],
            "TVS VBUS clamp referenced to the IP5306 boost output")

    def test_detects_unmanufacturable_width(self):
        def mutate(c, n):
            for s in c["segments"]:
                if s["net"] == n[USB_DP_NET]:
                    s["width"] = 0.10
                    return
        self._assert_fails(mutate, "a 0.10 mm USB trace (below fab minimum)")

    def test_detects_gross_skew(self):
        def mutate(c, n):
            detour = dict(c["segments"][0])
            detour.update({"x1": 0.0, "y1": 0.0, "x2": 0.0, "y2": 60.0,
                           "net": n[USB_DP_NET], "width": 0.2,
                           "layer": "B.Cu"})
            c["segments"].append(detour)
        self._assert_fails(mutate, "a 60 mm detour on D+ only")

    def test_detects_missing_return_path(self):
        self._assert_fails(
            lambda c, n: c["vias"].__setitem__(
                slice(None), [v for v in c["vias"] if v["net"] != n[GND_NET]]),
            "every ground stitching via deleted")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    cache = load_cache(PCB_FILE)
    limits = derive_limits()
    result = analyze_usb(cache, limits)

    print("\n-- USB data path check --")
    print(f"  Link            : USB 2.0 {limits['speed']} speed, "
          f"{limits['bitrate_bps'] / 1e6:g} Mbit/s")
    print(f"  Rise time       : {limits['rise_time_s'] * 1e9:g} ns  "
          f"-> critical length {limits['critical_length_mm']:.1f} mm "
          f"(tr / {ELECTRICAL_LENGTH_DIVISOR:g} x {PROP_DELAY_S_PER_MM * 1e12:g} ps/mm)")
    print(f"  Unit interval   : {limits['ui_s'] * 1e9:g} ns  "
          f"-> skew budget {limits['max_skew_mm']:.2f} mm "
          f"({limits['max_skew_s'] * 1e12:.0f} ps)")

    if "dp_length_mm" not in result:
        for f in result["findings"]:
            print(f"  FAIL  {f}")
        return 1

    print(f"  D+              : {result['dp_segments']} segments, "
          f"{result['dp_length_mm']} mm, layers {result['dp_layers']}")
    print(f"  D-              : {result['dm_segments']} segments, "
          f"{result['dm_length_mm']} mm, layers {result['dm_layers']}")
    print(f"  Skew            : {result['skew_mm']} mm "
          f"({result['skew_mm'] * PROP_DELAY_S_PER_MM * 1e12:.0f} ps)")
    print(f"  Widths          : {result['widths']} mm")
    print(f"  Impedance rules : "
          f"{'ENFORCED (electrically long)' if result['electrically_long'] else 'not applicable (electrically short)'}")
    print(f"  Data vias       : {result['data_vias']}, ground stitching required "
          f"within {limits['max_stitch_dist_mm']:.1f} mm")
    if result["avg_spacing_mm"]:
        print(f"  Pair spacing    : {result['avg_spacing_mm']} mm average")

    if result["findings"]:
        for f in result["findings"]:
            print(f"  FAIL  {f}")
        return 1
    print("  PASS  USB data path is sound for this signalling rate")
    return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main())
