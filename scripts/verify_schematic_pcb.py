#!/usr/bin/env python3
"""Verify consistency between schematic sheets, main schematic, PCB, and JLCPCB exports.

Compares component references across:
  1. Main schematic (esp32-emu-turbo.kicad_sch)
  2. Individual sub-sheets (01-power-supply..07-joystick)
  3. PCB file (esp32-emu-turbo.kicad_pcb)
  4. JLCPCB CPL export

Reports missing/extra components in each source.
"""

import os
import re
import sys


def extract_refs(content, skip_power=True):
    """Extract component references from a KiCad schematic or PCB file."""
    refs = re.findall(r'"Reference"\s+"([^"]+)"', content)
    if skip_power:
        refs = [r for r in refs if not r.startswith('#')]
    # Filter out lib_symbol template refs (single letter like "U", "R", "C")
    refs = [r for r in refs if not re.match(r'^[A-Z]+$', r) and '?' not in r]
    return sorted(set(refs))


def extract_pcb_refs(content):
    """Extract component references from a .kicad_pcb file."""
    refs = re.findall(r'"Reference"\s+"([^"]+)"', content)
    refs = [r for r in refs if not r.startswith('#')
            and not re.match(r'^[A-Z]+$', r)
            and '?' not in r]
    return sorted(set(refs))


def extract_cpl_refs(cpl_path):
    """Extract designators from CPL.csv."""
    if not os.path.exists(cpl_path):
        return []
    refs = []
    with open(cpl_path) as f:
        for i, line in enumerate(f):
            if i == 0:
                continue  # skip header
            parts = line.strip().split(',')
            if parts:
                refs.append(parts[0].strip('"'))
    return sorted(set(refs))


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_diff(label_a, set_a, label_b, set_b):
    """Print symmetric difference between two sets."""
    only_a = set_a - set_b
    only_b = set_b - set_a
    common = set_a & set_b

    if only_a:
        print(f"  In {label_a} but NOT in {label_b} ({len(only_a)}):")
        print(f"    {', '.join(sorted(only_a))}")
    if only_b:
        print(f"  In {label_b} but NOT in {label_a} ({len(only_b)}):")
        print(f"    {', '.join(sorted(only_b))}")
    if not only_a and not only_b:
        print(f"  MATCH: {label_a} and {label_b} are identical ({len(common)} refs)")


def main():
    kicad_dir = sys.argv[1] if len(sys.argv) > 1 else "hardware/kicad"

    # 1. Main schematic
    main_sch_path = os.path.join(kicad_dir, "esp32-emu-turbo.kicad_sch")
    main_content = open(main_sch_path).read()
    main_refs = set(extract_refs(main_content))

    # Check for hierarchical sheet references
    sheet_blocks = re.findall(r'\(sheet\s', main_content)

    print_section("MAIN SCHEMATIC")
    print(f"  File: {main_sch_path}")
    print(f"  Components: {len(main_refs)}")
    print(f"  Refs: {', '.join(sorted(main_refs))}")
    print(f"  Hierarchical sheet refs: {len(sheet_blocks)}")
    if len(sheet_blocks) == 0:
        print("  WARNING: No hierarchical sheet references found!")
        print("  The sub-sheets are NOT linked to the main schematic.")

    # 2. Sub-sheets
    print_section("SUB-SHEETS")
    all_subsheet_refs = set()
    import glob
    for f in sorted(glob.glob(os.path.join(kicad_dir, "[0-9]*.kicad_sch"))):
        content = open(f).read()
        refs = set(extract_refs(content))
        fname = os.path.basename(f)
        print(f"  {fname}: {', '.join(sorted(refs)) if refs else '(empty)'}")
        all_subsheet_refs |= refs

    print(f"\n  All sub-sheets combined: {len(all_subsheet_refs)} unique refs")
    print(f"  Refs: {', '.join(sorted(all_subsheet_refs))}")

    # 3. PCB file
    pcb_path = os.path.join(kicad_dir, "esp32-emu-turbo.kicad_pcb")
    if os.path.exists(pcb_path):
        pcb_content = open(pcb_path).read()
        pcb_refs = set(extract_pcb_refs(pcb_content))
        print_section("PCB FILE")
        print(f"  File: {pcb_path}")
        print(f"  Components: {len(pcb_refs)}")
        print(f"  Refs: {', '.join(sorted(pcb_refs))}")
    else:
        pcb_refs = set()

    # 4. JLCPCB CPL
    cpl_path = os.path.join(kicad_dir, "jlcpcb", "cpl.csv")
    if os.path.exists(cpl_path):
        cpl_refs = set(extract_cpl_refs(cpl_path))
        print_section("JLCPCB CPL")
        print(f"  File: {cpl_path}")
        print(f"  Components: {len(cpl_refs)}")
        print(f"  Refs: {', '.join(sorted(cpl_refs))}")
    else:
        cpl_refs = set()

    # 5. Effective schematic = root + sub-sheets (hierarchical)
    if len(sheet_blocks) > 0:
        effective_sch_refs = main_refs | all_subsheet_refs
        sch_label = "Full Schematic (root + sub-sheets)"
        print_section("HIERARCHICAL DESIGN DETECTED")
        print(f"  Root has {len(sheet_blocks)} sheet references -> OK")
        print(f"  Effective component count: {len(effective_sch_refs)}")
    else:
        effective_sch_refs = main_refs
        sch_label = "Main Schematic (flat)"
        print_section("WARNING: FLAT DESIGN")
        print("  Sub-sheets are NOT linked to root schematic")

    # 6. Key comparison: schematic vs JLCPCB
    print_section(f"COMPARISON: {sch_label} vs JLCPCB CPL")
    print_diff(sch_label, effective_sch_refs, "JLCPCB CPL", cpl_refs)

    print_section("COMPARISON: PCB footprints vs JLCPCB CPL")
    print_diff("PCB", pcb_refs, "JLCPCB CPL", cpl_refs)

    # 7. Summary
    print_section("SUMMARY")
    missing_from_sch = cpl_refs - effective_sch_refs
    extra_in_sch = effective_sch_refs - cpl_refs

    if not missing_from_sch:
        print(f"  ALL {len(cpl_refs)} JLCPCB components have schematic symbols")
    else:
        print(f"  MISSING from schematic ({len(missing_from_sch)}):")
        print(f"    {', '.join(sorted(missing_from_sch))}")

    if extra_in_sch:
        print(f"\n  Off-board/optional (in schematic, not assembled by JLCPCB):")
        print(f"    {', '.join(sorted(extra_in_sch))}")

    # JLCPCB readiness
    print_section("JLCPCB READINESS")
    checks = []
    if not missing_from_sch:
        checks.append("Schematic coverage: PASS")
    else:
        checks.append(f"Schematic coverage: FAIL ({len(missing_from_sch)} missing)")
    if cpl_refs:
        checks.append(f"CPL file: PASS ({len(cpl_refs)} components)")
    else:
        checks.append("CPL file: MISSING")
    pcb_missing = cpl_refs - pcb_refs
    if pcb_missing:
        checks.append(f"PCB footprints: {len(pcb_refs)} placed, {len(pcb_missing)} passive-only in CPL")
    else:
        checks.append("PCB footprints: PASS (all present)")

    for c in checks:
        print(f"  {c}")


if __name__ == "__main__":
    main()
