#!/usr/bin/env python3
"""JLCPCB BOM parser and parts checker.

Usage:
    python3 scripts/jlcpcb_parts.py check [bom.csv]
    python3 scripts/jlcpcb_parts.py info
    python3 scripts/jlcpcb_parts.py footprint <LCSC_PART> [LCSC_PART ...]
"""

import csv
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None


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


EASYEDA_USER_AGENT = (
    "JLC2KiCadLib/esp32-emu-turbo "
    "(https://github.com/TousstNicolas/JLC2KiCad_lib)"
)


def _easyeda_get(url):
    """GET request to EasyEDA API. Returns parsed JSON or None on failure."""
    if requests is not None:
        resp = requests.get(url, headers={"User-Agent": EASYEDA_USER_AGENT}, timeout=15)
        if resp.status_code != 200:
            return None
        return json.loads(resp.content.decode())
    # Fallback to urllib (no external dependency)
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": EASYEDA_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def fetch_footprint_info(lcsc_part):
    """Fetch footprint info for an LCSC part number via EasyEDA API.

    Returns a dict with keys: name, pad_count, width_mm, height_mm,
    has_3d_model, datasheet, description, component_uuid, or None on error.
    """
    # Step 1: get component UUIDs from LCSC part number
    data = _easyeda_get(
        f"https://easyeda.com/api/products/{lcsc_part}/svgs"
    )
    if not data or not data.get("success"):
        return None

    results = data.get("result", [])
    if not results:
        return None

    footprint_uuid = results[-1]["component_uuid"]

    # Step 2: get footprint detail from component UUID
    comp_data = _easyeda_get(
        f"https://easyeda.com/api/components/{footprint_uuid}"
    )
    if not comp_data or not comp_data.get("result"):
        return None

    result = comp_data["result"]
    data_str = result.get("dataStr", {})
    head = data_str.get("head", {})
    shape = data_str.get("shape", [])

    # Extract footprint name
    fp_name = (
        result.get("title", "unknown")
        .replace(" ", "_")
        .replace("/", "_")
        .replace("(", "_")
        .replace(")", "_")
    )

    # Count pads (lines starting with "PAD~")
    pad_count = sum(1 for s in shape if s.startswith("PAD~"))

    # Extract bounding box from pad coordinates (mil to mm)
    MIL2MM = 0.0254
    xs, ys = [], []
    for s in shape:
        if s.startswith("PAD~"):
            parts = s.split("~")
            try:
                xs.append(float(parts[2]) * MIL2MM)
                ys.append(float(parts[3]) * MIL2MM)
            except (IndexError, ValueError):
                pass

    width_mm = round(max(xs) - min(xs), 2) if xs else 0.0
    height_mm = round(max(ys) - min(ys), 2) if ys else 0.0

    # Datasheet link
    c_para = head.get("c_para", {})
    datasheet = c_para.get("link", "")
    description = c_para.get("name", result.get("title", ""))

    # 3D model: check if any SVGNODE or model3D references exist
    has_3d = any(s.startswith("SVGNODE~") for s in shape)

    return {
        "name": fp_name,
        "pad_count": pad_count,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "has_3d_model": has_3d,
        "datasheet": datasheet,
        "description": description,
        "component_uuid": footprint_uuid,
    }


def cmd_footprint(lcsc_parts):
    """Fetch and display footprint info for LCSC part numbers."""
    for part in lcsc_parts:
        part = part.strip().upper()
        if not part.startswith("C") or not part[1:].isdigit():
            print(f"WARNING: '{part}' does not look like an LCSC part number (Cxxxxx)")

        print(f"\nLooking up {part} ...")
        info = fetch_footprint_info(part)

        if info is None:
            print(f"  ERROR: Could not fetch footprint for {part}")
            print(f"  Check that the part exists: https://jlcpcb.com/partdetail/{part}")
            continue

        print(f"  Footprint:  {info['name']}")
        print(f"  Pads:       {info['pad_count']}")
        print(f"  Size (pads): {info['width_mm']} x {info['height_mm']} mm")
        print(f"  3D Model:   {'Yes' if info['has_3d_model'] else 'No'}")
        print(f"  Description: {info['description']}")
        if info["datasheet"]:
            print(f"  Datasheet:  {info['datasheet']}")
        print(f"  EasyEDA UUID: {info['component_uuid']}")
        print()
        print(f"  To generate KiCad library files:")
        print(f"    pip install JLC2KiCadLib")
        print(f"    JLC2KiCadLib {part} -dir hardware/kicad/jlcpcb_lib")


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
        print("Usage: python3 scripts/jlcpcb_parts.py [check|info|footprint] [args]")
        print()
        print("Commands:")
        print("  check [bom.csv]              Check BOM component availability")
        print("  info                          Print BOM statistics")
        print("  footprint <LCSC> [LCSC ...]   Fetch footprint info from EasyEDA")
        sys.exit(1)

    cmd = sys.argv[1]
    bom_arg = sys.argv[2] if len(sys.argv) > 2 else None

    if cmd == "check":
        bom_path = find_bom(bom_arg)
        cmd_check(bom_path)
    elif cmd == "info":
        cmd_info()
    elif cmd == "footprint":
        if len(sys.argv) < 3:
            print("Usage: python3 scripts/jlcpcb_parts.py footprint <LCSC_PART> [...]")
            sys.exit(1)
        cmd_footprint(sys.argv[2:])
    else:
        # Treat as BOM path for check
        bom_path = find_bom(cmd)
        cmd_check(bom_path)


if __name__ == "__main__":
    main()
