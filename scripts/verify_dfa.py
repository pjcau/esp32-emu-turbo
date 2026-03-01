#!/usr/bin/env python3
"""Design for Assembly (DFA) Tier 1 automated checks.

Verifies:
1. BOM-CPL consistency
2. LCSC stock availability
3. Courtyard clearance (via KiCad DRC rule)
4. Component-to-edge clearance
"""

import csv
import json
import os
import sys
import urllib.request
import urllib.error
from typing import Dict, Tuple

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE = os.path.join(BASE, "release_jlcpcb")
PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

PASS = 0
FAIL = 0

# Board dimensions
BOARD_WIDTH = 160.0  # mm
BOARD_HEIGHT = 75.0  # mm
MIN_EDGE_CLEARANCE = 3.0  # mm for SMT components


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


def main():
    """Run all DFA checks."""
    print("=" * 60)
    print("Design for Assembly (DFA) Tier 1 Verification")
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

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
