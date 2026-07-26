#!/usr/bin/env python3
"""Net Class Width Enforcement verification.

Verifies that trace widths match the expected minimums per net class:

  Net Class     | Nets                    | Min Width
  ------------- | ----------------------- | ---------
  Power High    | VBUS, BAT+, LX          | 0.50mm
  Power         | +5V, +3V3               | 0.20mm
  GND           | GND                     | 0.20mm
  Signal        | all others              | 0.15mm

Documented exceptions:
  - +3V3 button pull-up stubs at 0.20mm are acceptable
  - GND short stubs at 0.20mm are acceptable
  - BAT+ corridor bottleneck at 0.30mm — see ALLOWLIST below.
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"

sys.path.insert(0, str(BASE / "scripts"))
from pcb_cache import load_cache

# ── Net class definitions ────────────────────────────────────────
NET_CLASSES = {
    "Power High": {
        "nets": {"VBUS", "BAT+", "LX"},
        "min_width": 0.50,
    },
    "Power": {
        "nets": {"+5V", "+3V3"},
        "min_width": 0.20,
    },
    "GND": {
        "nets": {"GND"},
        "min_width": 0.20,
    },
    "Signal": {
        "nets": None,  # all remaining nets
        "min_width": 0.15,
    },
}

# Nets that are internal/unnamed and should be skipped
SKIP_NETS = {""}

# ── ALLOWLIST: Power High undersized segments with proof ─────────────
#
# Each entry is a tuple (net, layer, x1, y1, x2, y2, width_mm) matched
# with 0.02mm tolerance. An entry MUST be backed by documented proof
# that the segment cannot be widened without a re-layout.
#
# Current entries — BAT+ IP5306 corridor bottleneck
# ---------------------------------------------------
# R8 tech debt: L1.1 → BAT+ main corridor must thread the 0.885mm
# vertical band between the GND Fix1a thermal trace (y=45.3, hw=0.3,
# bottom edge 45.6) and the IP5306_KEY horizontal (y=46.61, hw=0.125,
# top edge 46.485). Widening to 0.50mm at y=46.10 would push the
# bottom edge to 46.35 → gap to KEY top = 0.135mm < 0.20mm Default
# clearance → DRC violation. Shifting y also fails (the GND bound
# constrains the top). Widening requires a v2 re-layout that relaxes
# the GND/KEY neighbors.
# See:
#   scripts/generate_pcb/routing/power.py (BAT+ corridor math, W_BAT_CORRIDOR)
#   memory/project_r8_remaining_todo.md ("BAT+ corridor" section)
#
# Current-carrying check: 0.30mm x 35µm 1oz Cu external → ~1.0A at
# 10°C rise (IPC-2221). BAT+ carries up to 1.0A charging and ~1.5A
# peak boost discharge during ESP32 WiFi TX bursts. Thin section is
# ~21mm total — brief transient bursts (µs-scale) do not drive the
# trace to steady-state temperature. Accepted for prototype; v2 must
# widen to 0.50mm.
POWER_HIGH_ALLOWLIST = [
    # (net, layer, x1, y1, x2, y2, width) — BAT+ corridor
    # R9-HIGH-2 (2026-04-11): L1.1 bridge Y shifted from 48.00 to 47.80
    ("BAT+", "B.Cu", 107.80, 46.10, 114.65, 46.10, 0.30),  # main corridor part 1
    ("BAT+", "B.Cu", 114.65, 46.10, 116.95, 46.10, 0.30),  # main corridor part 2
    ("BAT+", "B.Cu", 111.70, 52.50, 111.70, 47.80, 0.30),  # L1.1 vertical
    ("BAT+", "B.Cu", 111.70, 47.80, 113.45, 47.80, 0.30),  # L1.1 horizontal
    ("BAT+", "B.Cu", 114.65, 47.80, 114.65, 46.10, 0.30),  # L1.1 dogleg down
    ("BAT+", "F.Cu", 105.50, 46.13, 105.50, 46.10, 0.30),  # F.Cu bridge stub
    ("BAT+", "F.Cu", 105.50, 46.10, 107.80, 46.10, 0.30),  # F.Cu bridge over KEY
    ("BAT+", "F.Cu", 113.45, 47.80, 114.65, 47.80, 0.30),  # F.Cu bridge over KEY (L1.1)

    # ── J1 VBUS escape gate ────────────────────────────────────────────
    # The two diagonals that bring USB-C lands 11 and 2 out from under the
    # connector. Unlike the BAT+ corridor above, this is not tech debt
    # awaiting a v2 re-layout: 0.50 mm is UNREACHABLE HERE BY ANY ROUTING.
    #
    # Both features that pin the gap belong to J1 itself — the moulded peg
    # hole and the corner of land 10 — so nothing on the board can move to
    # open it. routing/_shared.py (POWER_HIGH_ALLOWLIST derivation) solves the budget from the connector's
    # own datasheet dimensions rather than typing a width in:
    #     |peg centre -> land 10 corner|      1.1183 mm
    #   - 0.325 peg hole radius
    #   - 0.300 NPTH-to-copper (validate_jlcpcb, stricter than the .kicad_dru)
    #   - 0.200 pad-to-track
    #   = 0.293 mm widest trace that can physically pass
    # confirmed independently by a maximin-clearance path search over an
    # exact B.Cu clearance field: 0.2888 mm at 5 um resolution, pinch at
    # (77.795, 69.485). The alternative escape upward into the board
    # interior measures 0.170 mm and is topologically blocked anyway.
    #
    # IPC-2221 (external, 1 oz, 35 um), which H3 asks for explicitly:
    #   0.273 mm alone           0.93 A at 10 C rise
    #   share of the 2.1 A peak  ~0.7 A  -> ~5 C rise
    # The share is what matters and it is set by resistance, not by wishful
    # splitting: this gate is a PARALLEL bond of ~9.7 mOhm across the two
    # extra connector contacts (~20 mOhm), while land 2 keeps its own
    # 0.60 mm run to the IP5306 as the supply path. Even the pessimistic
    # case of the full 2.1 A crossing one escape is ~13 C on a 1.4 mm
    # segment that sinks into a 0.55 mm land at one end and a 0.76 mm bus
    # at the other.
    #
    # Coordinate-pinned on purpose. routing.py DERIVES this width from the
    # geometry, so if the footprint or the clearance constants ever change,
    # the escape widens by itself, stops matching these rows, and the gate
    # goes red again — which is the point.
    ("VBUS", "B.Cu", 77.54, 69.00, 78.19, 70.24, 0.273),  # land 11 escape
    ("VBUS", "B.Cu", 81.81, 70.24, 82.46, 69.00, 0.273),  # land 2 escape
]


def _matches_allowlist(violation, allowlist):
    """True if the violation matches an allowlisted segment (0.02mm tol)."""
    for net, layer, ax1, ay1, ax2, ay2, aw in allowlist:
        if violation["net"] != net or violation["layer"] != layer:
            continue
        # Match either orientation (start-end or end-start)
        fwd = (
            abs(violation["x1"] - ax1) < 0.02 and abs(violation["y1"] - ay1) < 0.02
            and abs(violation["x2"] - ax2) < 0.02 and abs(violation["y2"] - ay2) < 0.02
        )
        rev = (
            abs(violation["x1"] - ax2) < 0.02 and abs(violation["y1"] - ay2) < 0.02
            and abs(violation["x2"] - ax1) < 0.02 and abs(violation["y2"] - ay1) < 0.02
        )
        if (fwd or rev) and abs(violation["width"] - aw) < 0.02:
            return True
    return False

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


def classify_net(net_name):
    """Return the net class name for a given net."""
    for class_name, spec in NET_CLASSES.items():
        if spec["nets"] is not None and net_name in spec["nets"]:
            return class_name
    return "Signal"


def _pads_by_net_layer(cache, nets):
    """Index pads by (net name, layer) for the burial test below."""
    idx = defaultdict(list)
    for p in cache["pads"]:
        name = nets.get(p["net"], "")
        if not name:
            continue
        idx[(name, p["layer"])].append(p)
    return idx


def _buried_in_own_pad(seg, net_name, pad_idx):
    """True if this segment lies wholly inside a pad of its own net.

    A track drawn from a pad's origin to a point still inside that pad is
    not a neck: the copper there is the PAD, which is far wider than the
    line. Measuring the line's width and calling it undersized flags
    geometry that does not exist — two of the four "undersized VBUS
    traces" were the 0.23mm in-land spines of J1 lands 2 and 11, where
    the real copper is the 0.55mm land.

    The containment test is the pad's INSCRIBED circle, radius
    min(w, h) / 2, not its bounding box. The cache carries no per-pad
    rotation, and a rotated rectangle's axis-aligned box claims copper
    the pad does not have — which would let this exemption swallow a
    real neck. The inscribed circle is true for any rotation, so it can
    only ever exempt less than it should, never more.

    The segment must also be no wider than the pad's narrow dimension,
    so a wide trace clipping a small pad is never called buried.
    """
    for p in pad_idx.get((net_name, seg["layer"]), []):
        r = min(p["w"], p["h"]) / 2.0
        if seg["width"] > min(p["w"], p["h"]) + 1e-9:
            continue
        d1 = ((seg["x1"] - p["x"]) ** 2 + (seg["y1"] - p["y"]) ** 2) ** 0.5
        d2 = ((seg["x2"] - p["x"]) ** 2 + (seg["y2"] - p["y"]) ** 2) ** 0.5
        if d1 <= r and d2 <= r:
            return p
    return None


def test_net_class_widths():
    """Run net class width enforcement checks."""
    print("=" * 60)
    print("Net Class Width Enforcement")
    print("=" * 60)

    cache = load_cache(str(PCB_FILE))
    nets = {n["id"]: n["name"] for n in cache["nets"]}

    # Classify all segments by net class
    class_segments = defaultdict(list)
    class_violations = defaultdict(list)
    class_width_stats = defaultdict(lambda: defaultdict(int))
    pad_idx = _pads_by_net_layer(cache, nets)
    buried = []

    for seg in cache["segments"]:
        net_name = nets.get(seg["net"], "")
        if net_name in SKIP_NETS:
            continue

        net_class = classify_net(net_name)
        min_width = NET_CLASSES[net_class]["min_width"]
        width = seg["width"]

        class_segments[net_class].append(seg)
        class_width_stats[net_class][width] += 1

        # Check minimum width with small tolerance for floating point
        if width < min_width - 0.001:
            pad = _buried_in_own_pad(seg, net_name, pad_idx)
            if pad is not None:
                # Reported, never hidden: this is an exemption with a
                # stated geometric reason, and it stays visible so a
                # sudden jump in the count is noticeable.
                buried.append((net_name, seg["layer"], pad["ref"],
                               pad["num"], width))
                continue
            class_violations[net_class].append({
                "net": net_name,
                "layer": seg["layer"],
                "width": width,
                "min": min_width,
                "x1": seg["x1"],
                "y1": seg["y1"],
                "x2": seg["x2"],
                "y2": seg["y2"],
            })

    # ── Report per net class ──
    print(f"\n── Net Class Width Checks ──")

    if buried:
        print(f"      IN-PAD: {len(buried)} segment(s) lie wholly inside a "
              f"pad of their own net — the copper there is the pad, not "
              f"the line, so its width is not a neck:")
        for net_name, layer, ref, num, w in buried:
            print(f"        {net_name:<12} {layer:<6} inside {ref}.{num} "
                  f"(line {w:.3f}mm)")

    for class_name in ["Power High", "Power", "GND", "Signal"]:
        spec = NET_CLASSES[class_name]
        min_w = spec["min_width"]
        segs = class_segments[class_name]
        violations = class_violations[class_name]
        widths = class_width_stats[class_name]

        # Filter out allowlisted (documented tech-debt) violations
        if class_name == "Power High":
            allowed = [
                v for v in violations
                if _matches_allowlist(v, POWER_HIGH_ALLOWLIST)
            ]
            real_violations = [
                v for v in violations
                if not _matches_allowlist(v, POWER_HIGH_ALLOWLIST)
            ]
            class_violations[class_name] = real_violations
            violations = real_violations
            if allowed:
                # Named per net and width, not summarised as "the BAT+
                # corridor": the allowlist now holds two groups with
                # different reasons — BAT+ is tech debt a v2 re-layout must
                # repay, the J1 VBUS escape is geometrically unreachable —
                # and one label covering both would hide the day a new
                # entry appears under someone else's justification.
                by_key = defaultdict(int)
                for v in allowed:
                    by_key[(v["net"], v["width"])] += 1
                summary = ", ".join(
                    f"{n} x{c} at {w:.3f}mm"
                    for (n, w), c in sorted(by_key.items())
                )
                print(f"      ALLOWED: {summary} "
                      f"(documented — see POWER_HIGH_ALLOWLIST)")

        check(
            f"{class_name} traces >= {min_w:.2f}mm ({len(segs)} segments)",
            len(violations) == 0,
            f"{len(violations)} undersized traces" if violations else "",
        )

        # Show width distribution
        if widths:
            width_str = ", ".join(
                f"{w:.2f}mm x{c}" for w, c in sorted(widths.items())
            )
            print(f"      Widths: {width_str}")

        # Show violations
        if violations:
            for v in violations[:5]:
                print(
                    f"      {v['net']} on {v['layer']}: "
                    f"w={v['width']:.3f}mm < {v['min']:.2f}mm "
                    f"at ({v['x1']:.1f},{v['y1']:.1f})"
                )
            if len(violations) > 5:
                print(f"      ... and {len(violations) - 5} more")

    # ── Summary statistics ──
    print(f"\n── Width Distribution by Net ──")

    net_min_widths = defaultdict(lambda: float("inf"))
    net_max_widths = defaultdict(lambda: 0.0)
    net_seg_counts = defaultdict(int)

    for seg in cache["segments"]:
        net_name = nets.get(seg["net"], "")
        if net_name in SKIP_NETS:
            continue
        w = seg["width"]
        net_min_widths[net_name] = min(net_min_widths[net_name], w)
        net_max_widths[net_name] = max(net_max_widths[net_name], w)
        net_seg_counts[net_name] += 1

    # Show power nets first, then signal
    power_nets = sorted(
        [n for n in net_seg_counts if classify_net(n) != "Signal"],
        key=lambda n: -net_seg_counts[n],
    )
    signal_nets = sorted(
        [n for n in net_seg_counts if classify_net(n) == "Signal"],
        key=lambda n: -net_seg_counts[n],
    )

    for net_name in power_nets:
        nc = classify_net(net_name)
        min_w = net_min_widths[net_name]
        max_w = net_max_widths[net_name]
        count = net_seg_counts[net_name]
        if min_w == max_w:
            print(f"    {net_name:12s} [{nc:12s}]: {min_w:.2f}mm ({count} segs)")
        else:
            print(f"    {net_name:12s} [{nc:12s}]: {min_w:.2f}-{max_w:.2f}mm ({count} segs)")

    print(f"    --- Signal nets ({len(signal_nets)} nets) ---")
    for net_name in signal_nets[:10]:
        min_w = net_min_widths[net_name]
        max_w = net_max_widths[net_name]
        count = net_seg_counts[net_name]
        if min_w == max_w:
            print(f"    {net_name:12s} [Signal      ]: {min_w:.2f}mm ({count} segs)")
        else:
            print(f"    {net_name:12s} [Signal      ]: {min_w:.2f}-{max_w:.2f}mm ({count} segs)")
    if len(signal_nets) > 10:
        print(f"    ... and {len(signal_nets) - 10} more signal nets")

    # ── Final check: overall minimum width ──
    all_widths = [seg["width"] for seg in cache["segments"]
                  if nets.get(seg["net"], "") not in SKIP_NETS]
    if all_widths:
        global_min = min(all_widths)
        check(
            f"Global minimum trace width >= 0.15mm (actual: {global_min:.3f}mm)",
            global_min >= 0.15 - 0.001,
            f"Found {global_min:.3f}mm trace",
        )

    # Summary
    total_segs = sum(len(v) for v in class_segments.values())
    total_violations = sum(len(v) for v in class_violations.values())
    print(f"\n    Total: {total_segs} segments checked, "
          f"{total_violations} violations")

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(test_net_class_widths())
