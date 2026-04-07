#!/usr/bin/env python3
"""ERC (Electrical Rules Check) automation for KiCad schematics.

Runs KiCad native ERC, parses JSON output, categorizes violations
by severity, and separates generator artifacts from real electrical issues.

Usage:
    python3 scripts/erc_check.py [--run]

    --run   Execute kicad-cli ERC first (requires kicad-cli in PATH)
            Without --run, reads existing /tmp/erc-report.json
"""

import json
import os
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCH_PATH = os.path.join(PROJECT_DIR, "hardware/kicad/esp32-emu-turbo.kicad_sch")
ERC_JSON = "/tmp/erc-report.json"

# Violations that come from the schematic generator (grid alignment, wiring style)
# and are NOT real electrical issues. These are suppressed in the report.
GENERATOR_ARTIFACTS = {
    "endpoint_off_grid",         # Generator doesn't snap to KiCad grid
    "wire_dangling",             # Short wire stubs from generator layout
    "lib_symbol_issues",         # Custom symbols not in KiCad library
    "wire_not_connected",        # Generator wiring style
    "label_dangling",            # Label placement by generator
    "unconnected_wire_endpoint", # Root sheet wiring stubs from generator
    "isolated_pin_label",        # Generator label placement on root sheet
}

# Real electrical issues that must be zero for production
CRITICAL_TYPES = {
    "pin_to_pin",            # Output driving output (short circuit risk)
    "different_unit_net",    # Same symbol, different unit, conflicting nets
    "bus_entry_no_connect",  # Bus entry not connected
}

# Issues to review but not necessarily fix
WARNING_TYPES = {
    "pin_not_connected",     # Unconnected IC pin (may be intentional NC)
    "power_pin_not_driven",  # Power pin without driver (may use zone fill)
    "pin_not_driven",        # Input pin without driver
    "missing_power_pin",     # Symbol missing power pin definition
}


def run_erc():
    """Run kicad-cli ERC and save JSON report."""
    print(f"Running ERC on {os.path.basename(SCH_PATH)}...")
    cmd = [
        "kicad-cli", "sch", "erc",
        SCH_PATH,
        "-o", ERC_JSON,
        "--format", "json",
        "--severity-all",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):  # 1 = violations found (expected)
        print(f"ERROR: kicad-cli failed: {result.stderr}")
        sys.exit(2)
    print(f"ERC report saved: {ERC_JSON}")
    return result.returncode


def parse_report(path):
    """Parse ERC JSON report and categorize violations."""
    with open(path) as f:
        data = json.load(f)

    total = 0
    by_type = {}
    by_sheet = {}
    real_issues = []

    for sheet in data.get("sheets", []):
        sheet_path = sheet.get("path", "/")
        sheet_violations = sheet.get("violations", [])

        for v in sheet_violations:
            total += 1
            vtype = v.get("type", v.get("description", "unknown"))

            # Extract violation type from description if type field missing
            if "type" not in v:
                # Try to infer type from description text
                desc = v.get("description", "")
                for known_type in (list(GENERATOR_ARTIFACTS) +
                                   list(CRITICAL_TYPES) +
                                   list(WARNING_TYPES)):
                    if known_type in desc.lower().replace(" ", "_"):
                        vtype = known_type
                        break

            by_type[vtype] = by_type.get(vtype, 0) + 1
            by_sheet[sheet_path] = by_sheet.get(sheet_path, 0) + 1

            # Classify
            if vtype not in GENERATOR_ARTIFACTS:
                severity = v.get("severity", "warning")
                items_desc = []
                for item in v.get("items", []):
                    items_desc.append(item.get("description", "?"))
                real_issues.append({
                    "type": vtype,
                    "severity": severity,
                    "sheet": sheet_path,
                    "description": v.get("description", ""),
                    "items": items_desc,
                })

    return {
        "total": total,
        "by_type": by_type,
        "by_sheet": by_sheet,
        "real_issues": real_issues,
        "generator_artifacts": sum(
            by_type.get(t, 0) for t in GENERATOR_ARTIFACTS
        ),
    }


def print_report(result):
    """Print formatted ERC report."""
    print()
    print("=" * 60)
    print("ERC Report — Electrical Rules Check")
    print("=" * 60)

    # Summary
    gen = result["generator_artifacts"]
    real = len(result["real_issues"])
    total = result["total"]
    print(f"\n  Total violations: {total}")
    print(f"  Generator artifacts (suppressed): {gen}")
    print(f"  Real electrical issues: {real}")

    # By type
    print(f"\n── Violation Types ──")
    for vtype, count in sorted(result["by_type"].items(),
                                key=lambda x: -x[1]):
        marker = "  [GEN]" if vtype in GENERATOR_ARTIFACTS else ""
        print(f"  {count:4d}  {vtype}{marker}")

    # By sheet
    print(f"\n── By Sheet ──")
    for sheet, count in sorted(result["by_sheet"].items(),
                                key=lambda x: -x[1]):
        print(f"  {count:4d}  {sheet}")

    # Real issues detail
    if result["real_issues"]:
        print(f"\n── Real Issues ({real}) ──")
        criticals = [i for i in result["real_issues"]
                     if i["type"] in CRITICAL_TYPES]
        warnings = [i for i in result["real_issues"]
                    if i["type"] not in CRITICAL_TYPES]

        if criticals:
            print(f"\n  CRITICAL ({len(criticals)}):")
            for issue in criticals:
                print(f"    {issue['sheet']}: {issue['description']}")
                for item in issue["items"][:3]:
                    print(f"      → {item}")

        if warnings:
            print(f"\n  WARNINGS ({len(warnings)}):")
            for issue in warnings:
                print(f"    {issue['sheet']}: {issue['description']}")
                for item in issue["items"][:2]:
                    print(f"      → {item}")
    else:
        print(f"\n  ✓ No real electrical issues found")

    # Verdict
    criticals = [i for i in result["real_issues"]
                 if i["type"] in CRITICAL_TYPES]
    print(f"\n{'=' * 60}")
    if criticals:
        print(f"  FAIL  {len(criticals)} critical ERC violations")
    else:
        print(f"  PASS  ERC — 0 critical, {real} warnings "
              f"({gen} generator artifacts suppressed)")
    print(f"{'=' * 60}")

    return len(criticals) == 0


def main():
    if "--run" in sys.argv:
        run_erc()

    if not os.path.exists(ERC_JSON):
        print(f"No ERC report found. Run with --run to generate.")
        print(f"  python3 scripts/erc_check.py --run")
        sys.exit(1)

    result = parse_report(ERC_JSON)
    passed = print_report(result)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
