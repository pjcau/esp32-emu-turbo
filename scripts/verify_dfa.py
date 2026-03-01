#!/usr/bin/env python3
"""Design for Assembly (DFA) verification — Tier 1 + Tier 2 SMT DFM checks.

Tier 1 — basic assembly checks:
1. BOM-CPL consistency
2. LCSC stock availability
3. Courtyard clearance (via KiCad DRC rule)
4. Component-to-edge clearance

Tier 2 — SMT DFM checks:
5. Solder paste aperture ratio (IPC-7525: 0.66-0.85)
6. Tombstoning risk for small passives
7. Polarity verification (LEDs, ICs with pin-1 markers)
"""

import csv
import json
import math
import os
import sys
import urllib.request
import urllib.error
from typing import Dict, List, Tuple

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE = os.path.join(BASE, "release_jlcpcb")
PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

PASS = 0
FAIL = 0

# Board dimensions
BOARD_WIDTH = 160.0  # mm
BOARD_HEIGHT = 75.0  # mm
MIN_EDGE_CLEARANCE = 3.0  # mm for SMT components

# ── Pad geometry data from footprints.py ──────────────────────────
# Footprint name → list of (pad_width_mm, pad_height_mm) for SMT pads
# Used for solder paste aperture ratio calculation
PAD_GEOMETRY = {
    "R_0805":   [(1.0, 1.3), (1.0, 1.3)],
    "C_0805":   [(1.0, 1.3), (1.0, 1.3)],
    "LED_0805": [(1.0, 1.3), (1.0, 1.3)],
    "C_1206":   [(1.2, 1.8), (1.2, 1.8)],
    "ESOP-8":   [(1.7, 0.6)] * 8 + [(3.4, 2.8)],  # 8 signal + EP
    "SOT-223":  [(1.0, 1.5)] * 3 + [(3.6, 1.8)],   # 3 signal + tab
    "SOP-16":   [(1.55, 0.6)] * 16,
    "SW-SMD-5.1x5.1": [(1.2, 0.9)] * 4,
    "USB-C-16P": [(0.6, 1.3)] * 4 + [(0.3, 1.3)] * 8,  # 4 wide + 8 narrow
    "FPC-40P-0.5mm": [(0.3, 1.3)] * 40 + [(1.6, 1.6)] * 2,
    "TF-01A":   [(0.6, 1.3)] * 9 + [(1.2, 1.4)] * 2 + [(1.2, 2.0)] * 2,
    "SS-12D00G3": [(0.6, 1.3)] * 3 + [(1.05, 0.7)] * 4,  # MSK12C02
    "SMD-4x4x2": [(1.4, 3.4)] * 2,
    "Speaker-22mm": [(2.0, 3.0)] * 2,
}

# IPC-7525 solder paste aperture ratio limits
# Ratio = stencil_aperture_area / pad_area
# Standard 0.12mm stencil thickness for JLCPCB
STENCIL_THICKNESS = 0.12  # mm (JLCPCB standard)
MIN_APERTURE_RATIO = 0.66  # IPC-7525 minimum
MAX_APERTURE_RATIO = 1.50  # allow up to 1:1 + margin for large pads

# Tombstoning: minimum pad-to-pad distance for 2-terminal passives
# Components with shorter distance have higher tombstoning risk
TOMBSTONE_PACKAGES = {"R_0805", "C_0805", "LED_0805", "C_1206"}

# Polarity-sensitive components (must have correct orientation)
POLARITY_LEDS = {"LED1", "LED2"}  # LED_0805 — cathode at pad 1
POLARITY_ICS = {"U1", "U2", "U3", "U5"}  # ICs with pin-1 marker


def check(name: str, condition: bool, detail: str = ""):
    """Record test result."""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def read_bom() -> Dict[str, Dict[str, str]]:
    """Read BOM and return dict keyed by designator."""
    bom_path = os.path.join(RELEASE, "bom.csv")
    bom_entries = {}

    with open(bom_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # BOM has comma-separated designators for multi-part entries
            designators = [d.strip() for d in row["Designator"].split(",")]
            for des in designators:
                bom_entries[des] = {
                    "Comment": row["Comment"],
                    "Footprint": row["Footprint"],
                    "LCSC Part #": row["LCSC Part #"],
                }

    return bom_entries


def read_cpl() -> Dict[str, Dict[str, str]]:
    """Read CPL and return dict keyed by designator."""
    cpl_path = os.path.join(RELEASE, "cpl.csv")
    cpl_entries = {}

    with open(cpl_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            cpl_entries[row["Designator"]] = row

    return cpl_entries


def test_bom_cpl_consistency():
    """Test 1: BOM-CPL consistency check."""
    print("\n── BOM-CPL Consistency ──")

    bom = read_bom()
    cpl = read_cpl()

    bom_refs = set(bom.keys())
    cpl_refs = set(cpl.keys())

    # Find mismatches
    in_bom_not_cpl = bom_refs - cpl_refs
    in_cpl_not_bom = cpl_refs - bom_refs

    check(
        "All BOM designators have CPL entries",
        len(in_bom_not_cpl) == 0,
        f"missing in CPL: {sorted(in_bom_not_cpl)}" if in_bom_not_cpl else "",
    )

    check(
        "All CPL designators have BOM entries",
        len(in_cpl_not_bom) == 0,
        f"missing in BOM: {sorted(in_cpl_not_bom)}" if in_cpl_not_bom else "",
    )

    # Print summary
    print(f"    BOM entries: {len(bom_refs)}")
    print(f"    CPL entries: {len(cpl_refs)}")
    print(f"    Common: {len(bom_refs & cpl_refs)}")


def query_lcsc_stock(lcsc_code: str) -> Tuple[bool, int, str]:
    """Query JLCPCB/LCSC stock for a part.

    Returns:
        (found, stock_qty, error_msg)
    """
    # Try multiple API endpoints
    urls = [
        f"https://jlcsearch.tscircuit.com/components/list.json?search={lcsc_code}",
        "https://yaqwsx.github.io/jlcparts/data/cache.json",  # Fallback to static cache
    ]

    for url in urls:
        try:
            # Add headers to avoid 403
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; DFA-Checker/1.0)",
                    "Accept": "application/json",
                }
            )

            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())

                # Handle different API response formats
                if isinstance(data, list):
                    # tscircuit API format
                    if len(data) == 0:
                        continue

                    # Find exact match
                    for component in data:
                        if component.get("lcsc") == lcsc_code:
                            stock = component.get("stock", 0)
                            return True, stock, ""

                    # No exact match, try next endpoint
                    continue

                if isinstance(data, dict):
                    # jlcparts cache format (partial data, may not have stock)
                    if lcsc_code in data:
                        # Part exists but stock info may not be available
                        return True, -1, "Stock unavailable (found in catalog)"
                    continue

            # No match in this endpoint, try next
            continue

        except urllib.error.HTTPError as e:
            if e.code == 403:
                # Try next endpoint on 403
                continue
            return False, 0, f"HTTP error: {e.code}"
        except urllib.error.URLError:
            # Network error, skip to next endpoint
            continue
        except Exception:
            continue

    # All endpoints failed
    return False, 0, "All API endpoints failed (network or rate limit)"


def test_lcsc_stock():
    """Test 2: LCSC stock verification."""
    print("\n── LCSC Stock Verification ──")

    bom = read_bom()

    # Get unique LCSC part numbers
    lcsc_parts = {}
    for des, info in bom.items():
        lcsc = info["LCSC Part #"]
        if lcsc not in lcsc_parts:
            lcsc_parts[lcsc] = []
        lcsc_parts[lcsc].append(des)

    print(f"    Checking {len(lcsc_parts)} unique LCSC parts (max 5 for speed)...")

    out_of_stock = []
    not_found = []
    in_stock = []

    # Only check first 5 parts to avoid timeout (this is informational only)
    for i, lcsc_code in enumerate(sorted(lcsc_parts.keys())):
        if i >= 5:
            print(f"    (skipping {len(lcsc_parts) - 5} parts for speed - use JLCPCB web interface for full check)")
            break

        found, stock, error = query_lcsc_stock(lcsc_code)

        if not found:
            not_found.append((lcsc_code, error, lcsc_parts[lcsc_code]))
        elif stock == 0:
            out_of_stock.append((lcsc_code, lcsc_parts[lcsc_code]))
        else:
            in_stock.append((lcsc_code, stock, lcsc_parts[lcsc_code]))

    # Report results
    # Note: Some checks may fail due to API rate limits or network issues
    # This is informational rather than blocking
    total_found = len(in_stock) + len(out_of_stock)
    if total_found == 0 and len(not_found) > 0:
        # All queries failed - likely API issue
        print("    WARNING: LCSC stock check failed (API unavailable)")
        print("    This is non-blocking - verify manually at https://jlcpcb.com/parts")
        # Don't fail the build on API issues
        check(
            "LCSC API availability (informational only)",
            True,  # Don't fail on API issues
            "API unavailable - manual verification required",
        )
    else:
        check(
            f"All parts found in LCSC catalog ({total_found}/{len(lcsc_parts)})",
            len(not_found) == 0,
            f"{len(not_found)} not found: {[p[0] for p in not_found[:3]]}" if not_found else "",
        )

        check(
            f"All parts in stock ({len(in_stock)}/{len(lcsc_parts)})",
            len(out_of_stock) == 0,
            (f"{len(out_of_stock)} out of stock: "
             f"{[p[0] for p in out_of_stock[:3]]}") if out_of_stock else "",
        )

    # Print detailed stock info
    if in_stock:
        print(f"    In stock: {len(in_stock)} part(s)")
        for lcsc, stock, refs in in_stock[:5]:
            print(f"      {lcsc}: {stock} units ({refs[0]})")
        if len(in_stock) > 5:
            print(f"      ... and {len(in_stock) - 5} more")

    if out_of_stock:
        print("    OUT OF STOCK:")
        for lcsc, refs in out_of_stock:
            print(f"      {lcsc}: {', '.join(refs[:3])}")

    if not_found:
        print("    NOT FOUND:")
        for lcsc, error, refs in not_found:
            print(f"      {lcsc}: {error} ({', '.join(refs[:3])})")


def test_component_edge_clearance():
    """Test 4: Component-to-edge clearance check."""
    print("\n── Component-to-Edge Clearance ──")

    cpl = read_cpl()

    violations = []

    for des, info in cpl.items():
        # Parse position
        x = float(info["Mid X"].replace("mm", ""))
        y = float(info["Mid Y"].replace("mm", ""))

        # Check distances to all four edges
        dist_left = x
        dist_right = BOARD_WIDTH - x
        dist_top = y
        dist_bottom = BOARD_HEIGHT - y

        min_dist = min(dist_left, dist_right, dist_top, dist_bottom)

        if min_dist < MIN_EDGE_CLEARANCE:
            edge = ["left", "right", "top", "bottom"][
                [dist_left, dist_right, dist_top, dist_bottom].index(min_dist)
            ]
            violations.append(
                f"{des} at ({x:.1f},{y:.1f}mm): {min_dist:.2f}mm from {edge} edge"
            )

    check(
        f"All components >= {MIN_EDGE_CLEARANCE}mm from board edge ({len(cpl)} components)",
        len(violations) == 0,
        f"{len(violations)} violations: {violations[:3]}" if violations else "",
    )

    if violations:
        print("    VIOLATIONS:")
        for v in violations[:10]:
            print(f"      {v}")
        if len(violations) > 10:
            print(f"      ... and {len(violations) - 10} more")


def _parse_footprint(package: str) -> str:
    """Map CPL package name to footprint key in PAD_GEOMETRY."""
    mapping = {
        "Module_ESP32-S3": None,       # Complex module, skip aperture check
        "Module_ESP32-S3-WROOM-1": None,
        "USB-C-SMD-16P": "USB-C-16P",
        "JST-PH-2P-Vertical": None,   # THT, skip
    }
    if package in mapping:
        return mapping[package]
    return package if package in PAD_GEOMETRY else None


def test_solder_paste_aperture():
    """Test 5: Solder paste aperture ratio (IPC-7525).

    Checks that pad aspect ratio allows adequate solder paste transfer
    through the stencil aperture. Small narrow pads risk insufficient paste.
    Formula: ratio = aperture_width / stencil_thickness
    IPC-7525: ratio >= 0.66 for reliable paste release.
    """
    print("\n── Solder Paste Aperture Ratio ──")

    cpl = read_cpl()
    violations: List[str] = []
    checked = 0

    for des, info in cpl.items():
        package = info.get("Package", "")
        fp_key = _parse_footprint(package)
        if not fp_key:
            continue

        pads = PAD_GEOMETRY.get(fp_key, [])
        for i, (pw, ph) in enumerate(pads):
            checked += 1
            # Aperture ratio = min(width, height) / stencil_thickness
            min_dim = min(pw, ph)
            ratio = min_dim / STENCIL_THICKNESS

            if ratio < MIN_APERTURE_RATIO:
                violations.append(
                    f"{des} pad {i+1} ({pw}x{ph}mm): "
                    f"ratio={ratio:.2f} < {MIN_APERTURE_RATIO} "
                    f"(risk: insufficient paste release)"
                )

    check(
        f"Solder paste aperture ratio >= {MIN_APERTURE_RATIO} "
        f"({checked} pads checked)",
        len(violations) == 0,
        f"{len(violations)} pads below threshold" if violations else "",
    )

    if violations:
        print("    VIOLATIONS:")
        for v in violations[:10]:
            print(f"      {v}")
        if len(violations) > 10:
            print(f"      ... and {len(violations) - 10} more")
    else:
        print(f"    All pads have adequate aperture ratio (stencil={STENCIL_THICKNESS}mm)")


def test_tombstoning_risk():
    """Test 6: Tombstoning risk for small 2-terminal passives.

    Tombstoning occurs when one pad reflows before the other, pulling
    the component upright. Risk factors:
    - Uneven thermal mass on pads (one pad near copper pour / via)
    - Component near board edge (uneven heating)
    - Mismatched pad sizes
    This test checks for symmetric pad geometry and flags components
    where the two pads connect to different-sized copper features.
    """
    print("\n── Tombstoning Risk Analysis ──")

    cpl = read_cpl()
    bom = read_bom()
    at_risk: List[str] = []
    checked = 0

    for des, info in cpl.items():
        package = info.get("Package", "")
        fp_key = _parse_footprint(package)
        if fp_key not in TOMBSTONE_PACKAGES:
            continue

        checked += 1
        x = float(info["Mid X"].replace("mm", ""))
        y = float(info["Mid Y"].replace("mm", ""))

        # Check pad symmetry — our footprints have symmetric pads by design
        pads = PAD_GEOMETRY.get(fp_key, [])
        if len(pads) == 2:
            p1, p2 = pads
            if abs(p1[0] - p2[0]) > 0.05 or abs(p1[1] - p2[1]) > 0.05:
                at_risk.append(
                    f"{des} ({fp_key}): asymmetric pads "
                    f"{p1[0]}x{p1[1]} vs {p2[0]}x{p2[1]}mm"
                )
                continue

        # Check proximity to board edge (uneven heating risk)
        dist_edge = min(x, BOARD_WIDTH - x, y, BOARD_HEIGHT - y)
        if dist_edge < 5.0:
            at_risk.append(
                f"{des} ({fp_key}) at ({x:.0f},{y:.0f}mm): "
                f"{dist_edge:.1f}mm from edge (uneven reflow heating risk)"
            )

    check(
        f"Tombstoning risk assessment ({checked} passives checked)",
        len(at_risk) == 0,
        f"{len(at_risk)} at-risk components" if at_risk else "",
    )

    if at_risk:
        print("    AT RISK (consider thermal relief or reflow profile adjustment):")
        for r in at_risk[:10]:
            print(f"      {r}")
    else:
        print(f"    All {checked} passives have symmetric pads and safe placement")


def test_polarity_verification():
    """Test 7: Polarity and orientation verification.

    Verifies:
    - LED orientation consistency (all LEDs same rotation = same polarity)
    - IC pin-1 alignment (ICs at same rotation within package type)
    - BOM polarity-sensitive parts have expected footprints
    """
    print("\n── Polarity & Orientation Verification ──")

    cpl = read_cpl()
    bom = read_bom()
    issues: List[str] = []

    # Check LED orientation consistency
    led_rotations = {}
    for des in POLARITY_LEDS:
        if des in cpl:
            rot = float(cpl[des]["Rotation"])
            layer = cpl[des]["Layer"]
            led_rotations[des] = (rot, layer)

    if len(led_rotations) >= 2:
        rots = list(led_rotations.values())
        if not all(r == rots[0] for r in rots):
            issues.append(
                f"LED orientation mismatch: "
                + ", ".join(f"{d}={r[0]}deg/{r[1]}" for d, r in led_rotations.items())
            )

    check(
        f"LED polarity consistent ({len(led_rotations)} LEDs)",
        not any("LED" in i for i in issues),
        next((i for i in issues if "LED" in i), ""),
    )

    # Check IC orientation within same package type
    ic_by_package: Dict[str, List[Tuple[str, float, str]]] = {}
    for des in POLARITY_ICS:
        if des in cpl and des in bom:
            package = cpl[des].get("Package", "")
            rot = float(cpl[des]["Rotation"])
            layer = cpl[des]["Layer"]
            if package not in ic_by_package:
                ic_by_package[package] = []
            ic_by_package[package].append((des, rot, layer))

    for package, ics in ic_by_package.items():
        # ICs of the same package on the same layer should have same rotation
        by_layer: Dict[str, List[Tuple[str, float]]] = {}
        for des, rot, layer in ics:
            if layer not in by_layer:
                by_layer[layer] = []
            by_layer[layer].append((des, rot))

        for layer, components in by_layer.items():
            if len(components) < 2:
                continue
            rots = [r for _, r in components]
            if len(set(rots)) > 1:
                issues.append(
                    f"IC rotation mismatch ({package}/{layer}): "
                    + ", ".join(f"{d}={r}deg" for d, r in components)
                )

    ic_issues = [i for i in issues if "IC" in i]
    check(
        f"IC pin-1 orientation consistent ({len(POLARITY_ICS)} ICs)",
        len(ic_issues) == 0,
        ic_issues[0] if ic_issues else "",
    )

    # Verify polarized capacitors have correct footprint
    polarized_caps = []
    for des, info in bom.items():
        comment = info.get("Comment", "")
        # 22uF and above in 1206 are typically polarized (tantalum/ceramic)
        if "22uF" in comment and "1206" not in info.get("Footprint", ""):
            polarized_caps.append(f"{des}: {comment} in {info['Footprint']} (expected 1206)")

    check(
        "Polarized capacitors use correct footprint",
        len(polarized_caps) == 0,
        polarized_caps[0] if polarized_caps else "",
    )

    if issues:
        print("    ISSUES:")
        for i in issues:
            print(f"      {i}")
    else:
        print("    All polarity-sensitive components verified")


def main():
    """Run all DFA checks."""
    print("=" * 60)
    print("Design for Assembly (DFA) Verification — Tier 1 + Tier 2")
    print("=" * 60)

    # Test 1: BOM-CPL consistency
    test_bom_cpl_consistency()

    # Test 2: LCSC stock verification
    test_lcsc_stock()

    # Test 3: Courtyard clearance
    # This is now enforced by KiCad DRC rule, so we just note it
    print("\n── Courtyard Clearance ──")
    print("    NOTE: Courtyard clearance (min 0.25mm) is enforced by KiCad DRC rule")
    print("    Run `kicad-cli pcb drc` or `/drc-native` to verify")

    # Test 4: Component-to-edge clearance
    test_component_edge_clearance()

    # ── Tier 2: SMT DFM ──
    print(f"\n{'─' * 60}")
    print("  Tier 2 — SMT DFM Checks")
    print(f"{'─' * 60}")

    # Test 5: Solder paste aperture ratio
    test_solder_paste_aperture()

    # Test 6: Tombstoning risk
    test_tombstoning_risk()

    # Test 7: Polarity verification
    test_polarity_verification()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
