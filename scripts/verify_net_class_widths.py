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

    for class_name in ["Power High", "Power", "GND", "Signal"]:
        spec = NET_CLASSES[class_name]
        min_w = spec["min_width"]
        segs = class_segments[class_name]
        violations = class_violations[class_name]
        widths = class_width_stats[class_name]

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
