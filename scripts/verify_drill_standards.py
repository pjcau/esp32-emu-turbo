#!/usr/bin/env python3
"""Standard Drill Size Audit.

Maps all drill holes to nearest standard PCB drill sizes and flags
non-standard drills that may cause manufacturing issues or cost increases.
Based on KiPadCheck methodology (HiGregSmith/KiPadCheck).

Standard drill sets:
- ISO metric preferred: 0.20, 0.25, 0.30, ..., 6.00mm
- PCB industry standard: common via/PTH drills used by JLCPCB
- JLCPCB 0.05mm increment rule (validated separately in validate_jlcpcb.py)

Also checks:
- Drill-to-pad ratio (IPC recommendation: hole = 60-80% of pad)
- Drill inventory summary (unique sizes → cost optimization)
- Via vs PTH drill size appropriateness

Run: python3 scripts/verify_drill_standards.py
"""

import math
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from pcb_cache import load_cache

PASS = 0
FAIL = 0
WARN = 0

# ── Standard Drill Sets ───────────────────────────────────────────────

# ISO metric preferred drill sizes (mm) — common in PCB manufacturing
ISO_METRIC_PREFERRED = [
    0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55,
    0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95,
    1.00, 1.05, 1.10, 1.15, 1.20, 1.30, 1.40, 1.50,
    1.60, 1.70, 1.80, 1.90, 2.00, 2.10, 2.20, 2.30,
    2.40, 2.50, 2.60, 2.80, 3.00, 3.20, 3.50, 4.00,
    4.50, 5.00, 5.50, 6.00, 6.30,
]

# JLCPCB common drill sizes (most frequently used, lowest cost)
JLCPCB_COMMON = [
    0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55,
    0.60, 0.65, 0.70, 0.80, 0.85, 0.90, 1.00, 1.10,
    1.20, 1.50, 2.00, 2.50, 3.00, 3.20, 3.50,
]

# Maximum number of unique drill sizes before cost warning
MAX_UNIQUE_DRILLS_CHEAP = 8  # JLCPCB: 8 drill sizes included, extra cost after

# Drill-to-pad ratio (IPC-2222)
MIN_DRILL_PAD_RATIO = 0.50   # Hole too small relative to pad
MAX_DRILL_PAD_RATIO = 0.85   # Hole too large (thin annular ring)
IDEAL_DRILL_PAD_RATIO = (0.60, 0.75)  # Optimal range


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


def _nearest_standard(drill, standard_set):
    """Find nearest standard drill size and distance."""
    if not standard_set:
        return drill, 0
    nearest = min(standard_set, key=lambda s: abs(s - drill))
    return nearest, abs(drill - nearest)


def test_iso_metric_compliance():
    """Check all drills against ISO metric preferred sizes."""
    print("\n── ISO Metric Preferred Drill Sizes ──")
    cache = load_cache()

    non_standard = []
    all_drills = []

    # Vias
    for v in cache["vias"]:
        drill = v["drill"]
        all_drills.append(("via", v["x"], v["y"], drill))
        nearest, delta = _nearest_standard(drill, ISO_METRIC_PREFERRED)
        if delta > 0.001:
            non_standard.append(
                f"via@({v['x']:.2f},{v['y']:.2f}) drill={drill:.3f}mm "
                f"→ nearest ISO={nearest:.3f}mm (Δ={delta:.3f}mm)")

    # PTH pads
    for p in cache["pads"]:
        drill = p.get("drill", 0)
        if drill <= 0:
            continue
        all_drills.append(("pad", p["x"], p["y"], drill))
        nearest, delta = _nearest_standard(drill, ISO_METRIC_PREFERRED)
        if delta > 0.001:
            non_standard.append(
                f"{p['ref']}[{p['num']}] drill={drill:.3f}mm "
                f"→ nearest ISO={nearest:.3f}mm (Δ={delta:.3f}mm)")

    check(f"All drills ISO metric ({len(all_drills)} holes)",
          len(non_standard) == 0,
          f"{len(non_standard)} non-standard")

    if non_standard:
        print("    NON-STANDARD DRILLS:")
        for ns in non_standard[:10]:
            print(f"      {ns}")
        if len(non_standard) > 10:
            print(f"      ... and {len(non_standard) - 10} more")


def test_jlcpcb_common_drills():
    """Check drills against JLCPCB commonly-stocked sizes."""
    print("\n── JLCPCB Common Drill Sizes ──")
    cache = load_cache()

    uncommon = []

    # Vias
    for v in cache["vias"]:
        drill = v["drill"]
        nearest, delta = _nearest_standard(drill, JLCPCB_COMMON)
        if delta > 0.001:
            uncommon.append(
                f"via@({v['x']:.2f},{v['y']:.2f}) drill={drill:.3f}mm "
                f"(nearest common={nearest:.3f}mm)")

    # PTH pads
    for p in cache["pads"]:
        drill = p.get("drill", 0)
        if drill <= 0:
            continue
        nearest, delta = _nearest_standard(drill, JLCPCB_COMMON)
        if delta > 0.001:
            uncommon.append(
                f"{p['ref']}[{p['num']}] drill={drill:.3f}mm "
                f"(nearest common={nearest:.3f}mm)")

    if uncommon:
        warn(f"{len(uncommon)} holes use uncommon JLCPCB drill sizes",
             f"may increase cost/lead time")
        for u in uncommon[:5]:
            print(f"      {u}")
    else:
        check("All drills match JLCPCB common sizes", True)


def test_drill_inventory():
    """Count unique drill sizes and warn if exceeding JLCPCB included count."""
    print("\n── Drill Inventory ──")
    cache = load_cache()

    drill_counts = Counter()

    for v in cache["vias"]:
        drill_counts[f"via {v['drill']:.3f}mm"] += 1

    for p in cache["pads"]:
        drill = p.get("drill", 0)
        if drill > 0:
            drill_counts[f"pad {drill:.3f}mm"] += 1

    # Count unique sizes
    unique_sizes = set()
    for v in cache["vias"]:
        unique_sizes.add(round(v["drill"], 3))
    for p in cache["pads"]:
        drill = p.get("drill", 0)
        if drill > 0:
            unique_sizes.add(round(drill, 3))

    print(f"    Unique drill sizes: {len(unique_sizes)}")
    print(f"    Total holes: {sum(drill_counts.values())}")
    print(f"\n    {'Size (mm)':<12} {'Type':<8} {'Count':<8}")
    print(f"    {'─' * 30}")

    for size in sorted(unique_sizes):
        via_count = sum(1 for v in cache["vias"] if abs(v["drill"] - size) < 0.001)
        pad_count = sum(1 for p in cache["pads"]
                       if abs(p.get("drill", 0) - size) < 0.001)
        types = []
        if via_count > 0:
            types.append(f"via×{via_count}")
        if pad_count > 0:
            types.append(f"pad×{pad_count}")
        print(f"    {size:>8.3f}     {' + '.join(types)}")

    check(f"Drill count <= {MAX_UNIQUE_DRILLS_CHEAP} (JLCPCB included)",
          len(unique_sizes) <= MAX_UNIQUE_DRILLS_CHEAP,
          f"{len(unique_sizes)} unique sizes (extra cost above {MAX_UNIQUE_DRILLS_CHEAP})")


def test_drill_pad_ratio():
    """Check drill-to-pad ratio for THT components (IPC-2222)."""
    print("\n── Drill-to-Pad Ratio (IPC-2222) ──")
    cache = load_cache()

    violations = []
    warnings = []

    for p in cache["pads"]:
        drill = p.get("drill", 0)
        if drill <= 0:
            continue
        # Skip NPTH pads — drill == pad is by design (no copper ring)
        if p.get("type") == "np_thru_hole":
            continue

        pw = p.get("w", 0)
        ph = p.get("h", 0)
        if pw == 0 or ph == 0:
            continue

        min_pad = min(pw, ph)
        ratio = drill / min_pad

        if ratio > MAX_DRILL_PAD_RATIO:
            violations.append(
                f"{p['ref']}[{p['num']}] drill={drill:.2f}mm pad={min_pad:.2f}mm "
                f"ratio={ratio:.2f} > {MAX_DRILL_PAD_RATIO} (thin annular ring)")
        elif ratio < MIN_DRILL_PAD_RATIO:
            warnings.append(
                f"{p['ref']}[{p['num']}] drill={drill:.2f}mm pad={min_pad:.2f}mm "
                f"ratio={ratio:.2f} < {MIN_DRILL_PAD_RATIO} (hole very small vs pad)")
        elif not (IDEAL_DRILL_PAD_RATIO[0] <= ratio <= IDEAL_DRILL_PAD_RATIO[1]):
            warnings.append(
                f"{p['ref']}[{p['num']}] drill={drill:.2f}mm pad={min_pad:.2f}mm "
                f"ratio={ratio:.2f} (outside ideal {IDEAL_DRILL_PAD_RATIO[0]}-{IDEAL_DRILL_PAD_RATIO[1]})")

    check(f"Drill-to-pad ratio within IPC limits",
          len(violations) == 0,
          f"{len(violations)} violations")

    if violations:
        print("    VIOLATIONS:")
        for v in violations[:10]:
            print(f"      {v}")

    if warnings:
        warn(f"{len(warnings)} pads outside ideal drill-to-pad ratio",
             f"first: {warnings[0]}")


def test_via_vs_pth_appropriateness():
    """Verify via drills are appropriate for vias and PTH drills for components."""
    print("\n── Via vs PTH Drill Appropriateness ──")
    cache = load_cache()

    issues = []

    # Vias should typically be 0.20-0.60mm drill
    for v in cache["vias"]:
        drill = v["drill"]
        if drill > 0.80:
            issues.append(
                f"via@({v['x']:.2f},{v['y']:.2f}) drill={drill:.2f}mm "
                f"(unusually large for via — should this be a PTH pad?)")
        elif drill < 0.15:
            issues.append(
                f"via@({v['x']:.2f},{v['y']:.2f}) drill={drill:.2f}mm "
                f"(micro-via on 2-layer board — not supported by JLCPCB)")

    # PTH component pads should typically be >= 0.50mm drill
    for p in cache["pads"]:
        drill = p.get("drill", 0)
        if drill <= 0:
            continue
        # Small PTH drills are usually fine for test points, but flag very small ones
        if drill < 0.30 and p["ref"] not in ("TP1", "TP2", "TP3"):
            issues.append(
                f"{p['ref']}[{p['num']}] drill={drill:.2f}mm "
                f"(very small PTH — verify lead fits)")

    check("Via/PTH drill sizes appropriate",
          len(issues) == 0,
          f"{len(issues)} concerns")

    if issues:
        for i in issues[:5]:
            print(f"      {i}")


def main():
    print("=" * 70)
    print("  Standard Drill Size Audit")
    print("  Source: ISO metric + JLCPCB + IPC-2222 + KiPadCheck")
    print("=" * 70)

    test_iso_metric_compliance()
    test_jlcpcb_common_drills()
    test_drill_inventory()
    test_drill_pad_ratio()
    test_via_vs_pth_appropriateness()

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  RESULTS: {PASS} PASS / {FAIL} FAIL / {WARN} WARN")
    if FAIL == 0:
        print("  STATUS: ALL DRILL CHECKS PASSED")
    else:
        print(f"  STATUS: {FAIL} ISSUE(S) — review drill sizes")
    print("=" * 70)
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
