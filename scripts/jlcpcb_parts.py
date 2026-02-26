#!/usr/bin/env python3
"""JLCPCB BOM parser and parts checker.

Usage:
    python3 scripts/jlcpcb_parts.py check [bom.csv]
    python3 scripts/jlcpcb_parts.py info
"""

import csv
import sys
from pathlib import Path


BOM_PATHS = [
    "release_jlcpcb/bom.csv",
    "hardware/kicad/jlcpcb/bom.csv",
]


def find_bom(explicit_path=None):
    """Find the BOM CSV file."""
    if explicit_path:
        p = Path(explicit_path)
        if p.exists():
            return p
        print(f"ERROR: {explicit_path} not found")
        sys.exit(1)
    for bp in BOM_PATHS:
        p = Path(bp)
        if p.exists():
            return p
    print("ERROR: No BOM file found. Searched:")
    for bp in BOM_PATHS:
        print(f"  - {bp}")
    sys.exit(1)


def parse_bom(bom_path):
    """Parse BOM CSV and return list of component entries."""
    entries = []
    with open(bom_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            comment = row.get("Comment", "")
            designators = row.get("Designator", "")
            footprint = row.get("Footprint", "")
            lcsc = row.get("LCSC Part #", "")
            # Split comma-separated designators
            refs = [d.strip() for d in designators.split(",") if d.strip()]
            entries.append({
                "comment": comment,
                "designators": refs,
                "designator_str": designators,
                "footprint": footprint,
                "lcsc": lcsc,
                "quantity": len(refs),
            })
    return entries


def cmd_check(bom_path):
    """Print BOM summary for stock checking."""
    entries = parse_bom(bom_path)

    print(f"BOM File: {bom_path}")
    print("=" * 80)
    print()

    total_unique = len(entries)
    total_placements = sum(e["quantity"] for e in entries)

    print(f"Unique parts: {total_unique}")
    print(f"Total placements: {total_placements}")
    print()

    # Print table header
    print(f"{'#':<3} {'LCSC':<12} {'Component':<35} {'Footprint':<22} {'Qty':<4}")
    print("-" * 80)

    for i, e in enumerate(entries, 1):
        print(f"{i:<3} {e['lcsc']:<12} {e['comment'][:34]:<35} "
              f"{e['footprint'][:21]:<22} {e['quantity']:<4}")

    print()
    print("=" * 80)
    print()
    print("To check stock/pricing for each part, use WebSearch with:")
    print("  site:jlcpcb.com/partdetail/<LCSC_PART>")
    print()
    print("LCSC Part Numbers to check:")
    for e in entries:
        print(f"  {e['lcsc']}  ({e['comment']})")


def cmd_info():
    """Print BOM statistics."""
    for bp in BOM_PATHS:
        p = Path(bp)
        if p.exists():
            entries = parse_bom(p)
            total = sum(e["quantity"] for e in entries)
            print(f"{bp}: {len(entries)} unique parts, {total} placements")
        else:
            print(f"{bp}: not found")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/jlcpcb_parts.py [check|info] [bom.csv]")
        sys.exit(1)

    cmd = sys.argv[1]
    bom_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "check":
        bom_path = find_bom(bom_arg)
        cmd_check(bom_path)
    elif cmd == "info":
        cmd_info()
    else:
        # Treat as BOM path for check
        bom_path = find_bom(cmd)
        cmd_check(bom_path)


if __name__ == "__main__":
    main()
