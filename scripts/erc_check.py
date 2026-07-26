#!/usr/bin/env python3
"""ERC (Electrical Rules Check) automation for KiCad schematics.

Runs KiCad native ERC, parses JSON output, categorizes violations
by severity, and separates generator artifacts from real electrical issues.

Usage:
    python3 scripts/erc_check.py [--run]

    --run   Force a re-run of kicad-cli ERC even if the report is current.

The report is regenerated automatically whenever it is missing or older than
the schematic, so this gate always reports on the schematic as it is now.

The report used to live at a machine-global /tmp/erc-report.json with no
freshness check, which made this gate wrong in three ways at once: it failed
on any machine that had never generated the file, it kept reporting yesterday's
answer once the file existed, and every worktree and every other KiCad project
on the machine wrote the same path — one project's ERC could sign off another's.
The report is now project-scoped and stamped with a hash of every schematic
sheet, the way scripts/pcb_cache.py stamps the board.
"""

import glob
import hashlib
import json
import os
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KICAD_DIR = os.path.join(PROJECT_DIR, "hardware/kicad")
SCH_PATH = os.path.join(KICAD_DIR, "esp32-emu-turbo.kicad_sch")
ERC_JSON = os.path.join(KICAD_DIR, ".erc-report.json")
ERC_STAMP = os.path.join(KICAD_DIR, ".erc-report.stamp")


def schematic_fingerprint():
    """SHA-256 over every sheet, so editing any one of them invalidates."""
    h = hashlib.sha256()
    for path in sorted(glob.glob(os.path.join(KICAD_DIR, "*.kicad_sch"))):
        h.update(os.path.basename(path).encode())
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 16), b""):
                h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def report_is_current():
    if not (os.path.exists(ERC_JSON) and os.path.exists(ERC_STAMP)):
        return False
    with open(ERC_STAMP) as f:
        return f.read().strip() == schematic_fingerprint()

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

# ── Error-severity waivers (R27-LOW-1) ───────────────────────────────────
#
# Until 2026-07-26 the verdict was `len(criticals) == 0` over CRITICAL_TYPES
# alone, and KiCad's own `severity` field was never read. Every type in
# GENERATOR_ARTIFACTS was dropped wholesale — including `wire_dangling`, which
# KiCad raises at severity=error. The gate therefore printed
# "PASS — 0 critical" while the raw report held a dozen errors, and it kept
# printing it when a D-pad button's ground pin was deliberately detached: the
# planted defect took SW3.2 off GND in the netlist and the verdict did not move.
#
# Now: any error-severity violation fails unless its exact identity is waived
# here, so a NEW error can never hide behind an old one's type.
#
# Each key is (type, sheet, item description) verbatim from the report. That is
# deliberately brittle — the same reasoning as POWER_HIGH_ALLOWLIST's
# coordinate pinning. If the generator's output shifts, the key stops matching,
# the gate goes red, and somebody looks at it again.
ERROR_WAIVERS = {
    # KiCad's hierarchy bookkeeping on a programmatically generated schematic,
    # not board defects. The evidence that these are artifacts, not findings:
    #
    #   * the items describe geometry that does not exist. There are 317 wires
    #     across the seven sheets and NONE is shorter than 0.3 mm, yet these
    #     report wires of 0.0508 mm and 0.0038 mm;
    #   * the sheet attribution is wrong. These are filed under "/" — the root
    #     sheet, which contains zero wires and zero symbols — and the R4 items
    #     under "/Display/" when R4 exists only in 06-controls.kicad_sch;
    #   * all twelve button columns are emitted by the same four lines
    #     (controls.py:77-101), and only this one is flagged;
    #   * the netlist those sheets actually export is complete and correct:
    #     verify_netlist_diff T1-T4 pass, verify_schematic_pin_connectivity
    #     reports 338 pins with 0 floating, and all 15 switches reach GND.
    #
    # So the drawing is sound where it can be measured, and these are removed
    # from the verdict rather than from the report — they still print.
    ("wire_dangling", "/", "Symbol SW4 [SW_Push]"): "generated-hierarchy artifact",
    ("wire_dangling", "/", "Symbol SW4 Pin 2 [2, Passive, Line]"): "generated-hierarchy artifact",
    ("wire_dangling", "/", "Horizontal Wire, length 0.0508 mm"): "phantom geometry — no wire this short exists",
    ("wire_dangling", "/", "Symbol #PWR013 [+3V3]"): "generated-hierarchy artifact",
    ("wire_dangling", "/", "Symbol #PWR013 Pin 1 [+3V3, Power input, Line]"): "generated-hierarchy artifact",
    ("wire_dangling", "/", "Horizontal Wire, length 0.1800 mm"): "phantom geometry — no wire this short exists",
    ("wire_dangling", "/", "Vertical Wire, length 0.0038 mm"): "phantom geometry — no wire this short exists",
    ("wire_dangling", "/", "Symbol R7 [R]"): "generated-hierarchy artifact",
    ("pin_not_connected", "/Power Supply/", "Symbol #PWR030 [GND]"):
        "power-flag symbol; GND is a plane and every GND pin is on it",
    ("pin_not_connected", "/Mcu/", "Global Label 'BTN_LEFT'"):
        "BTN_LEFT is complete on both sides — C7.1 + R6.1 + SW3 + U1.35 on "
        "copper, and present in the exported netlist",
    ("power_pin_not_driven", "/Display/", "Symbol R4 Pin 1 [Passive, Line]"):
        "R4 is a passive pull-up in 06-controls, not a power input, and not "
        "in the Display sheet at all",
    ("power_pin_not_driven", "/Display/", "Symbol R4 Pin 2 [Passive, Line]"):
        "R4 is a passive pull-up in 06-controls, not a power input, and not "
        "in the Display sheet at all",
}


def waiver_for(vtype, sheet, item):
    """Reason this exact error-severity item is waived, or None."""
    return ERROR_WAIVERS.get((vtype, sheet, item))

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
    # Stamp with the fingerprint taken BEFORE the run: if a sheet is edited
    # while ERC is running, the stamp will not match on the next call and the
    # report is regenerated rather than trusted.
    stamp = schematic_fingerprint()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode not in (0, 1):  # 1 = violations found (expected)
        print(f"ERROR: kicad-cli failed: {result.stderr}")
        sys.exit(2)
    with open(ERC_STAMP, "w") as f:
        f.write(stamp + "\n")
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
    errors_waived = []
    errors_unwaived = []

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

            # Severity-driven pass, independent of the type classification
            # below. This is what makes a NEW error impossible to hide behind
            # a suppressed type — see ERROR_WAIVERS.
            if v.get("severity") == "error":
                for item in v.get("items", []):
                    desc = item.get("description", "?")
                    row = {"type": vtype, "sheet": sheet_path, "item": desc}
                    reason = waiver_for(vtype, sheet_path, desc)
                    if reason:
                        errors_waived.append({**row, "reason": reason})
                    else:
                        errors_unwaived.append(row)

            # Suppress pin_to_pin between passive component and power symbol
            # (KiCad ERC false positive: cap pad to GND symbol is not output↔output)
            _is_passive_power_pp = False
            if vtype == "pin_to_pin":
                item_descs = [it.get("description", "") for it in v.get("items", [])]
                if any("Passive" in d for d in item_descs) and any("Power" in d for d in item_descs):
                    _is_passive_power_pp = True

            # Classify
            if vtype not in GENERATOR_ARTIFACTS and not _is_passive_power_pp:
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
        # Every error-severity item KiCad reported, split by whether this repo
        # has an explicit waiver for that exact item. Collected independently of
        # GENERATOR_ARTIFACTS so a suppressed TYPE can no longer hide an error.
        "errors_waived": errors_waived,
        "errors_unwaived": errors_unwaived,
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

    # ── Error-severity accounting (R27-LOW-1) ────────────────────────────
    # Printed every run, waived or not: a waiver removes an item from the
    # verdict, never from the report.
    waived = result.get("errors_waived", [])
    unwaived = result.get("errors_unwaived", [])

    if waived:
        print(f"\n── KiCad error-severity, waived ({len(waived)}) ──")
        for e in waived:
            print(f"    [{e['type']}] {e['sheet']} {e['item']}")
            print(f"        waived: {e['reason']}")

    if unwaived:
        print(f"\n── KiCad error-severity, NOT waived ({len(unwaived)}) ──")
        for e in unwaived:
            print(f"    [{e['type']}] {e['sheet']} {e['item']}")

    # Verdict
    criticals = [i for i in result["real_issues"]
                 if i["type"] in CRITICAL_TYPES]
    print(f"\n{'=' * 60}")
    if criticals or unwaived:
        if criticals:
            print(f"  FAIL  {len(criticals)} critical ERC violations")
        if unwaived:
            print(f"  FAIL  {len(unwaived)} KiCad error-severity violation(s) "
                  f"with no waiver in ERROR_WAIVERS")
            print("        Fix the schematic, or add the exact "
                  "(type, sheet, item) with a reason.")
    else:
        print(f"  PASS  ERC — 0 critical, {real} warnings "
              f"({gen} generator artifacts suppressed, "
              f"{len(waived)} error-severity waived)")
    print(f"{'=' * 60}")

    return not criticals and not unwaived


def main():
    if "--run" in sys.argv or not report_is_current():
        run_erc()

    if not os.path.exists(ERC_JSON):
        print("ERC report missing after the run — is kicad-cli on PATH?")
        sys.exit(2)

    result = parse_report(ERC_JSON)
    passed = print_report(result)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
