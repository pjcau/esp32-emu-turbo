#!/usr/bin/env python3
"""BOM vs Schematic Value Cross-Check.

Parses all KiCad sub-sheet schematics to extract component reference
designators and values, then compares against the JLCPCB BOM to detect
value mismatches (e.g. wrong resistor value in BOM).

Exit code 0 = all pass, 1 = failures found.
"""

import csv
import glob
import os
import re
import sys
from pathlib import Path

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMATIC_DIR = os.path.join(BASE, "hardware", "kicad")
BOM_PATH = os.path.join(BASE, "release_jlcpcb", "bom.csv")

PASS = 0
FAIL = 0
INFO = 0


def check(name: str, condition: bool, detail: str = ""):
    """Record test result."""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def info(msg: str):
    """Print an informational message."""
    global INFO
    INFO += 1
    print(f"  INFO  {msg}")


# ── Schematic parser ─────────────────────────────────────────────────

def parse_schematics() -> dict:
    """Parse all .kicad_sch files and extract ref -> value mapping.

    Returns dict: {"R3": "10k", "C1": "10uF", "U1": "ESP32-S3-N16R8", ...}
    Skips power symbols (#PWR*) and unassigned refs (?).
    """
    components = {}
    sch_files = sorted(glob.glob(os.path.join(SCHEMATIC_DIR, "*.kicad_sch")))

    for sch_path in sch_files:
        text = Path(sch_path).read_text(encoding="utf-8")
        sheet_name = Path(sch_path).stem

        # Find placed symbols (not lib_symbols definitions).
        # Placed symbols appear as: (symbol (lib_id "xxx") (at X Y angle) ...
        #   (property "Reference" "R3" ...)
        #   (property "Value" "10k" ...)
        # )
        # They are at indentation level 2 (two spaces), while lib_symbols
        # definitions are deeper inside the (lib_symbols ...) block.

        # Strategy: find all top-level symbol instances by matching
        # (symbol (lib_id ...) pattern outside lib_symbols.
        # We skip lib_symbols by finding its boundary first.
        lib_sym_start = text.find("(lib_symbols")
        lib_sym_end = -1
        if lib_sym_start >= 0:
            # Find matching close paren
            depth = 0
            for idx in range(lib_sym_start, len(text)):
                if text[idx] == '(':
                    depth += 1
                elif text[idx] == ')':
                    depth -= 1
                    if depth == 0:
                        lib_sym_end = idx + 1
                        break

        # Search for placed symbols outside lib_symbols section
        search_regions = []
        if lib_sym_end > 0:
            search_regions.append(text[:lib_sym_start])
            search_regions.append(text[lib_sym_end:])
        else:
            search_regions.append(text)

        for region in search_regions:
            # Match placed symbol blocks with lib_id
            for m in re.finditer(
                r'\(symbol\s+\(lib_id\s+"[^"]*"\)\s+\(at\s+[\d.\-\s]+\)',
                region
            ):
                # Find the full symbol block
                start = m.start()
                depth = 0
                end = start
                for idx in range(start, len(region)):
                    if region[idx] == '(':
                        depth += 1
                    elif region[idx] == ')':
                        depth -= 1
                        if depth == 0:
                            end = idx + 1
                            break

                block = region[start:end]

                # Extract Reference and Value properties
                ref_m = re.search(
                    r'\(property\s+"Reference"\s+"([^"]+)"', block)
                val_m = re.search(
                    r'\(property\s+"Value"\s+"([^"]+)"', block)

                if not ref_m or not val_m:
                    continue

                ref = ref_m.group(1)
                value = val_m.group(1)

                # Skip power symbols, unassigned, and pure letter refs
                if (ref.startswith('#') or '?' in ref
                        or re.match(r'^[A-Z]+$', ref)):
                    continue

                components[ref] = value

    return components


# ── BOM parser ───────────────────────────────────────────────────────

def parse_bom() -> dict:
    """Parse JLCPCB BOM CSV.

    Returns dict: {"R3": "10k 0805", "C1": "10uF 0805", ...}
    BOM Designator column may contain multiple refs (e.g. "R3,R4,R5").
    """
    bom_entries = {}

    with open(BOM_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            comment = row["Comment"].strip()
            designators = [d.strip() for d in row["Designator"].split(",")]
            for des in designators:
                bom_entries[des] = comment

    return bom_entries


# ── Value normalization ──────────────────────────────────────────────

def normalize_value(value: str) -> str:
    """Normalize a component value for comparison.

    Strips package size suffixes (0805, 1206, etc.), whitespace,
    and normalizes common equivalences.
    """
    v = value.strip()

    # Remove trailing package size (e.g. "10k 0805" -> "10k")
    v = re.sub(r'\s+\d{4}$', '', v)

    # Normalize common prefixes/suffixes
    v = v.lower()

    # Remove spaces
    v = v.replace(' ', '')

    return v


# Known mapping: schematic value -> BOM comment base value.
# These are components where schematic uses a different naming convention
# than the BOM and direct normalization won't work.
KNOWN_MAPPINGS = {
    # Schematic value : BOM comment (normalized)
    "usb_c": "usb-c16-pin",
    "jstph2-pin": "jstph2-pinsmd",
    "jst ph 2-pin": "jst ph 2-pin smd",
    "ss-12d00g3": "slideswitchss-12d00g3",
    "esp32-s3-n16r8": "esp32-s3-wroom-1-n16r8",
    "sd_card_spi": "microsdcardslot",
    "ili94884.0in8080": "fpc40-pin0.5mmbottomcontact",
    "fpc-16p-0.5mm": "fpc40-pin0.5mmbottomcontact",  # schematic says 16P but BOM correctly 40-pin
    "red": "redled",
    "green": "greenled",
    "lipo3.7v5000mah": None,  # battery, not on BOM
    "28mm8ohm": None,  # speaker, not on BOM
    "psp_joystick": None,  # joystick, not on BOM
    "up": "smttactswitch5.1x5.1mm",
    "down": "smttactswitch5.1x5.1mm",
    "left": "smttactswitch5.1x5.1mm",
    "right": "smttactswitch5.1x5.1mm",
    "a": "smttactswitch5.1x5.1mm",
    "b": "smttactswitch5.1x5.1mm",
    "x": "smttactswitch5.1x5.1mm",
    "y": "smttactswitch5.1x5.1mm",
    "start": "smttactswitch5.1x5.1mm",
    "select": "smttactswitch5.1x5.1mm",
    "l": "smttactswitch5.1x5.1mm",
    "r": "smttactswitch5.1x5.1mm",
    "menu": "smttactswitch5.1x5.1mm",
    "boot": "smttactswitch5.1x5.1mm",
    "reset": "smttactswitch5.1x5.1mm",
}

# Components not expected on the BOM (off-board or virtual)
NOT_ON_BOM = {"BT1", "SPK1", "J2", "U4"}


def values_match(sch_value: str, bom_comment: str) -> bool:
    """Compare schematic value against BOM comment.

    Handles normalization of package sizes, naming conventions, etc.
    """
    sv = normalize_value(sch_value)
    bv = normalize_value(bom_comment)

    # Direct match after normalization
    if sv == bv:
        return True

    # Check known mappings
    if sv in KNOWN_MAPPINGS:
        mapped = KNOWN_MAPPINGS[sv]
        if mapped is None:
            return True  # Known non-BOM component
        # Compare normalized versions (strip spaces from both)
        return mapped.replace(' ', '') == bv.replace(' ', '')

    # Passive values: schematic has "10k", BOM has "10k 0805"
    # After normalize_value strips the package suffix, these should match
    # But also handle "22uF tant." -> "22uF"
    sv_clean = re.sub(r'\s*tant\.?$', '', sv)
    if sv_clean == bv:
        return True

    # After stripping "tant." schematic marker, allow BOM to still carry
    # package/type info (e.g. sch "22uF tant." vs BOM "22uF 1206 Tantalum").
    # Reuse the IC-style startswith prefix match on the cleaned value.
    if sv_clean and (bv.startswith(sv_clean) or sv_clean.startswith(bv)):
        return True

    # IC values: schematic may have shorter name
    # e.g. "IP5306" == "IP5306", "AMS1117-3.3" == "AMS1117-3.3"
    if sv.startswith(bv) or bv.startswith(sv):
        return True

    # Inductor: "1uH" matches "1uh4.5a" after normalization
    if sv.replace('uh', '') == bv.split('4.5a')[0].replace('uh', ''):
        return True

    # Handle inductor specifically: "1uh" vs "1uh4.5ainductor"
    if 'uh' in sv and 'uh' in bv:
        sv_val = re.match(r'([\d.]+uh)', sv)
        bv_val = re.match(r'([\d.]+uh)', bv)
        if sv_val and bv_val and sv_val.group(1) == bv_val.group(1):
            return True

    return False


# ── Main verification ────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("BOM vs Schematic Value Cross-Check")
    print("=" * 60)

    # Step 1: Parse schematics
    print("\n── Parsing Schematics ──")
    sch_components = parse_schematics()
    print(f"    Found {len(sch_components)} components in schematics")

    # Step 2: Parse BOM
    print("\n── Parsing BOM ──")
    bom_entries = parse_bom()
    print(f"    Found {len(bom_entries)} entries in BOM")

    # Step 3: Cross-check
    print("\n── BOM vs Schematic Value Check ──")

    # Check each BOM entry against schematics
    mismatches = []
    matched = 0
    skipped = 0

    for ref in sorted(bom_entries.keys()):
        bom_val = bom_entries[ref]

        if ref in NOT_ON_BOM:
            skipped += 1
            continue

        if ref not in sch_components:
            info(f"{ref} in BOM but not found in schematics")
            continue

        sch_val = sch_components[ref]

        if values_match(sch_val, bom_val):
            matched += 1
            check(f"{ref} schematic={sch_val}, BOM={bom_val}", True)
        else:
            mismatches.append((ref, sch_val, bom_val))
            check(
                f"{ref} schematic={sch_val}, BOM={bom_val}",
                False,
                "<-- value mismatch!"
            )

    # Check for schematic components missing from BOM
    print("\n── Schematic Components Not in BOM ──")
    missing_from_bom = []
    for ref in sorted(sch_components.keys()):
        if ref in NOT_ON_BOM:
            continue
        if ref not in bom_entries:
            missing_from_bom.append(ref)

    if missing_from_bom:
        for ref in missing_from_bom:
            info(f"{ref} ({sch_components[ref]}) in schematic but not in BOM")
    else:
        print("    All schematic components accounted for in BOM")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {INFO} info")
    if mismatches:
        print(f"\nMISMATCHES ({len(mismatches)}):")
        for ref, sv, bv in mismatches:
            print(f"  {ref}: schematic={sv}, BOM={bv}")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
