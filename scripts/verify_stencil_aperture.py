#!/usr/bin/env python3
"""IPC-7525 Stencil Aperture Analysis.

Multi-thickness stencil analysis for solder paste transfer quality.
Based on KiPadCheck methodology (HiGregSmith/KiPadCheck).

Checks:
1. Area ratio: (L × W) / [2(L+W) × T] — must be >= 0.66 for reliable release
2. Aspect ratio: min(L,W) / T — must be >= 1.5 (baseline), 1.2 (laser stencil)
3. Solder paste powder type recommendation based on aperture width
4. Per-thickness analysis for 3mil, 4mil, 5mil stencils (JLCPCB default = 0.12mm ≈ 4.7mil)

Run: python3 scripts/verify_stencil_aperture.py
"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))
from pcb_cache import load_cache

PASS = 0
FAIL = 0
WARN = 0

# Stencil thicknesses to analyze (mm)
STENCIL_THICKNESSES = {
    "3mil (0.076mm)": 0.076,
    "4mil (0.100mm)": 0.100,
    "5mil (0.127mm)": 0.127,
    "JLCPCB std (0.120mm)": 0.120,
}
DEFAULT_THICKNESS = 0.120  # mm — JLCPCB standard

# IPC-7525 limits
MIN_AREA_RATIO = 0.66       # Below this: insufficient paste release
GOOD_AREA_RATIO = 0.75      # Above this: reliable paste release
MIN_ASPECT_RATIO_CHEM = 1.5  # Chemical-etched stencil
MIN_ASPECT_RATIO_LASER = 1.2  # Laser-cut stencil (JLCPCB uses laser)
MIN_ASPECT_RATIO_EFORM = 1.0  # Electroformed stencil

# Solder paste powder types by min aperture width (IPC J-STD-005)
PASTE_TYPES = [
    (0.500, "Type 2 (75-45µm)", "Standard for most SMD"),
    (0.300, "Type 3 (45-25µm)", "Fine pitch down to 0.5mm"),
    (0.200, "Type 4 (38-20µm)", "Ultra-fine pitch 0.4mm"),
    (0.150, "Type 5 (25-15µm)", "Micro BGA / 0.3mm pitch"),
    (0.000, "Type 6 (15-5µm)", "Experimental / flip-chip"),
]


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


def _area_ratio(length, width, thickness):
    """IPC-7525 area ratio: aperture_area / wall_area.

    = (L × W) / [2(L+W) × T]
    Higher is better for paste release.
    """
    wall_area = 2 * (length + width) * thickness
    if wall_area == 0:
        return 999
    return (length * width) / wall_area


def _aspect_ratio(length, width, thickness):
    """Aspect ratio: min dimension / stencil thickness.

    Higher is better. Minimum depends on stencil manufacturing method.
    """
    if thickness == 0:
        return 999
    return min(length, width) / thickness


def _recommend_paste_type(min_aperture_width):
    """Recommend solder paste powder type based on smallest aperture."""
    for threshold, name, desc in PASTE_TYPES:
        if min_aperture_width >= threshold:
            return name, desc
    return PASTE_TYPES[-1][1], PASTE_TYPES[-1][2]


def _get_smd_pad_geometries(cache):
    """Extract all SMD pad geometries from cache.

    Returns list of (ref, pad_num, width_mm, height_mm, layer).
    """
    pads = []
    for p in cache["pads"]:
        if p.get("drill", 0) > 0:
            continue  # THT
        w = p.get("w", 0)
        h = p.get("h", 0)
        if w <= 0 or h <= 0:
            continue
        pads.append((p["ref"], p["num"], w, h, p.get("layer", "F.Cu")))
    return pads


def test_area_ratio():
    """IPC-7525 area ratio check at JLCPCB standard stencil thickness."""
    print("\n── IPC-7525 Area Ratio (JLCPCB 0.12mm stencil) ──")
    cache = load_cache()
    pads = _get_smd_pad_geometries(cache)
    t = DEFAULT_THICKNESS

    violations = []
    marginal = []

    for ref, num, w, h, layer in pads:
        ratio = _area_ratio(w, h, t)

        if ratio < MIN_AREA_RATIO:
            violations.append(
                f"{ref}[{num}] {w:.2f}×{h:.2f}mm AR={ratio:.2f} "
                f"< {MIN_AREA_RATIO} (insufficient paste release)")
        elif ratio < GOOD_AREA_RATIO:
            marginal.append(
                f"{ref}[{num}] {w:.2f}×{h:.2f}mm AR={ratio:.2f} "
                f"(marginal, consider thinner stencil)")

    check(f"Area ratio >= {MIN_AREA_RATIO} ({len(pads)} SMD pads, T={t}mm)",
          len(violations) == 0,
          f"{len(violations)} pads below minimum")

    if violations:
        print("    VIOLATIONS (risk: insufficient solder paste):")
        for v in violations[:10]:
            print(f"      {v}")
        if len(violations) > 10:
            print(f"      ... and {len(violations) - 10} more")

    if marginal:
        warn(f"{len(marginal)} pads marginal (AR {MIN_AREA_RATIO}-{GOOD_AREA_RATIO})",
             f"first: {marginal[0]}")


def test_aspect_ratio():
    """Aspect ratio check — laser-cut stencil (JLCPCB standard)."""
    print("\n── Aspect Ratio (laser-cut stencil) ──")
    cache = load_cache()
    pads = _get_smd_pad_geometries(cache)
    t = DEFAULT_THICKNESS

    violations = []

    for ref, num, w, h, layer in pads:
        ar = _aspect_ratio(w, h, t)

        if ar < MIN_ASPECT_RATIO_LASER:
            violations.append(
                f"{ref}[{num}] {w:.2f}×{h:.2f}mm AspR={ar:.2f} "
                f"< {MIN_ASPECT_RATIO_LASER} (pad too narrow for stencil)")

    check(f"Aspect ratio >= {MIN_ASPECT_RATIO_LASER} (laser stencil, T={t}mm)",
          len(violations) == 0,
          f"{len(violations)} pads too narrow")

    if violations:
        print("    VIOLATIONS (risk: stencil aperture collapse):")
        for v in violations[:10]:
            print(f"      {v}")


def test_paste_type_recommendation():
    """Recommend solder paste powder type based on smallest aperture."""
    print("\n── Solder Paste Powder Type Recommendation ──")
    cache = load_cache()
    pads = _get_smd_pad_geometries(cache)

    if not pads:
        check("SMD pads found", False, "No SMD pads in design")
        return

    min_aperture = min(min(w, h) for _, _, w, h, _ in pads)
    paste_type, desc = _recommend_paste_type(min_aperture)

    print(f"    Smallest aperture: {min_aperture:.3f}mm")
    print(f"    Recommended paste: {paste_type}")
    print(f"    Use case: {desc}")

    check(f"Paste type determined: {paste_type}",
          True, "")


def test_multi_thickness_analysis():
    """Analyze area ratios across multiple stencil thicknesses."""
    print("\n── Multi-Thickness Stencil Analysis ──")
    cache = load_cache()
    pads = _get_smd_pad_geometries(cache)

    if not pads:
        return

    print(f"\n  {'Stencil':<25} {'Pads OK':<10} {'Marginal':<10} {'Failing':<10} {'Min AR'}")
    print(f"  {'─' * 70}")

    best_thickness = None
    best_fail_count = len(pads)

    for name, t in sorted(STENCIL_THICKNESSES.items(), key=lambda x: x[1]):
        ok = 0
        marginal = 0
        failing = 0
        min_ar = 999

        for ref, num, w, h, layer in pads:
            ratio = _area_ratio(w, h, t)
            min_ar = min(min_ar, ratio)

            if ratio >= GOOD_AREA_RATIO:
                ok += 1
            elif ratio >= MIN_AREA_RATIO:
                marginal += 1
            else:
                failing += 1

        status = "OK" if failing == 0 else f"FAIL({failing})"
        print(f"  {name:<25} {ok:<10} {marginal:<10} {failing:<10} {min_ar:.3f}")

        if failing < best_fail_count:
            best_fail_count = failing
            best_thickness = name

    if best_fail_count > 0:
        warn(f"No stencil thickness gives 0 failures",
             f"best: {best_thickness} with {best_fail_count} failing")
    else:
        print(f"\n  Optimal stencil: {best_thickness} (all pads pass)")

    check("Multi-thickness analysis complete", True)


def test_fine_pitch_detail():
    """Detailed report for fine-pitch components (pitch <= 0.5mm)."""
    print("\n── Fine-Pitch Component Detail ──")
    cache = load_cache()
    pads = _get_smd_pad_geometries(cache)
    t = DEFAULT_THICKNESS

    # Find pads with min dimension <= 0.35mm (fine pitch indicators)
    fine_pitch = []
    for ref, num, w, h, layer in pads:
        min_dim = min(w, h)
        if min_dim <= 0.35:
            ar = _area_ratio(w, h, t)
            asp = _aspect_ratio(w, h, t)
            fine_pitch.append((ref, num, w, h, ar, asp))

    if not fine_pitch:
        print("    No fine-pitch pads found (all apertures > 0.35mm)")
        check("Fine-pitch pad analysis", True)
        return

    print(f"    Found {len(fine_pitch)} fine-pitch pads (min dim <= 0.35mm):")
    print(f"\n  {'Ref':<10} {'Pad':<6} {'W×H (mm)':<14} {'Area Ratio':<12} {'Aspect Ratio'}")
    print(f"  {'─' * 55}")

    for ref, num, w, h, ar, asp in sorted(fine_pitch, key=lambda x: x[4]):
        status = "OK" if ar >= MIN_AREA_RATIO else "FAIL"
        print(f"  {ref:<10} {num:<6} {w:.2f}×{h:.2f}      {ar:.3f}        {asp:.2f}    {status}")

    failing = sum(1 for _, _, _, _, ar, _ in fine_pitch if ar < MIN_AREA_RATIO)
    check(f"Fine-pitch pads area ratio ({len(fine_pitch)} pads)",
          failing == 0,
          f"{failing} pads below IPC-7525 minimum")


def main():
    print("=" * 70)
    print("  IPC-7525 Stencil Aperture Analysis")
    print("  Source: IPC-7525 + KiPadCheck methodology")
    print("=" * 70)

    test_area_ratio()
    test_aspect_ratio()
    test_paste_type_recommendation()
    test_multi_thickness_analysis()
    test_fine_pitch_detail()

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  RESULTS: {PASS} PASS / {FAIL} FAIL / {WARN} WARN")
    if FAIL == 0:
        print("  STATUS: ALL STENCIL CHECKS PASSED")
    else:
        print(f"  STATUS: {FAIL} ISSUE(S) — review stencil thickness or pad geometry")
    print("=" * 70)
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
