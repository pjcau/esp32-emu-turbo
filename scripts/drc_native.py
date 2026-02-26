#!/usr/bin/env python3
"""Smart KiCad DRC analysis with violation filtering and fix suggestions.

Wraps kicad-cli DRC JSON output with:
- Known-acceptable violation filtering
- Delta tracking vs saved baseline
- Source file mapping for fix suggestions
- Priority ranking by severity and fixability

Usage:
    python3 scripts/drc_native.py <drc-report.json>
    python3 scripts/drc_native.py <drc-report.json> --update-baseline
"""

import json
import sys
from pathlib import Path
from collections import Counter

BASELINE_PATH = Path("scripts/drc_baseline.json")

# Known-acceptable violations in the generated PCB.
# These are expected because the Python generator doesn't assign nets to pads
# (only traces have net assignments). KiCad sees traces near unnetted pads
# and reports false positives.
KNOWN_ACCEPTABLE = {
    "shorting_items": "Traces near unnetted pads (false positive — nets not assigned in generated PCB)",
    "solder_mask_bridge": "Fine-pitch FPC/USB-C connectors (expected, JLCPCB handles this)",
    "hole_clearance": "Via-in-pad for button footprints (intentional design)",
    "via_dangling": "Zone-connected vias appear dangling before zone fill",
    "track_dangling": "Zone-connected tracks appear dangling before zone fill",
    "courtyardOverlap": "Overlapping courtyards on dense areas (acceptable for PCBA)",
}

# Violation types that indicate REAL issues to fix
REAL_ISSUES = {
    "clearance": {
        "severity": "HIGH",
        "source": "scripts/generate_pcb/routing.py",
        "fix": "Increase trace spacing or move traces apart. Check segment coordinates.",
    },
    "copper_edge_clearance": {
        "severity": "HIGH",
        "source": "scripts/generate_pcb/routing.py",
        "fix": "Move traces away from board edge or FPC slot. Check _crosses_slot() logic.",
    },
    "silk_over_copper": {
        "severity": "MEDIUM",
        "source": "scripts/generate_pcb/board.py",
        "fix": "Move silkscreen text to Fab layer. Check _silkscreen_labels().",
    },
    "silk_overlap": {
        "severity": "LOW",
        "source": "scripts/generate_pcb/board.py",
        "fix": "Reduce text size or reposition overlapping labels.",
    },
    "silk_edge_clearance": {
        "severity": "LOW",
        "source": "scripts/generate_pcb/board.py",
        "fix": "Move silkscreen text away from board edge.",
    },
    "track_width": {
        "severity": "HIGH",
        "source": "scripts/generate_pcb/routing.py",
        "fix": "Increase trace width. Check W_PWR/W_SIG/W_DATA constants.",
    },
    "via_annular_ring": {
        "severity": "HIGH",
        "source": "scripts/generate_pcb/primitives.py",
        "fix": "Increase via size or reduce drill diameter in via() function.",
    },
    "unconnected_items": {
        "severity": "CRITICAL",
        "source": "scripts/generate_pcb/routing.py",
        "fix": "Add missing trace connection. Check routing functions for the affected net.",
    },
    "min_copper_clearance": {
        "severity": "HIGH",
        "source": "scripts/generate_pcb/routing.py",
        "fix": "Increase clearance between copper elements.",
    },
}

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def load_drc_report(path):
    """Load and parse kicad-cli DRC JSON report."""
    with open(path) as f:
        return json.load(f)


def load_baseline():
    """Load saved violation baseline."""
    if BASELINE_PATH.exists():
        with open(BASELINE_PATH) as f:
            return json.load(f)
    return None


def save_baseline(counts):
    """Save current violation counts as new baseline."""
    with open(BASELINE_PATH, "w") as f:
        json.dump(counts, f, indent=2)
    print(f"\nBaseline saved to {BASELINE_PATH}")


def categorize_violations(report):
    """Categorize all violations from the DRC report."""
    counts = Counter()
    details = {}

    # Count violations
    for v in report.get("violations", []):
        vtype = v.get("type", "unknown")
        counts[vtype] += 1
        if vtype not in details:
            details[vtype] = []
        if len(details[vtype]) < 5:  # Keep top 5 examples
            details[vtype].append(v.get("description", ""))

    # Count unconnected items
    unconnected = report.get("unconnected_items", [])
    if unconnected:
        counts["unconnected_items"] = len(unconnected)
        details["unconnected_items"] = [
            u.get("description", "") for u in unconnected[:5]
        ]

    return dict(counts), details


def analyze(report_path, update_baseline=False):
    """Main analysis function."""
    report = load_drc_report(report_path)
    counts, details = categorize_violations(report)
    baseline = load_baseline()

    total = sum(counts.values())

    print("=" * 70)
    print("  NATIVE KiCad DRC — SMART ANALYSIS")
    print(f"  Source: {report_path}")
    print("=" * 70)
    print()

    # -- Known-acceptable violations ------------------------------------------
    known_count = 0
    print("KNOWN-ACCEPTABLE VIOLATIONS (expected, no action needed):")
    print(f"{'Type':<30} {'Count':>6}  Reason")
    print("-" * 70)
    for vtype, reason in KNOWN_ACCEPTABLE.items():
        c = counts.get(vtype, 0)
        known_count += c
        if c > 0:
            delta_str = ""
            if baseline and vtype in baseline:
                diff = c - baseline[vtype]
                if diff != 0:
                    delta_str = f" ({'+' if diff > 0 else ''}{diff})"
            print(f"  {vtype:<28} {c:>6}{delta_str}  {reason}")
    print()

    # -- Real issues ----------------------------------------------------------
    real_count = 0
    real_items = []
    for vtype, info in REAL_ISSUES.items():
        c = counts.get(vtype, 0)
        if c > 0:
            real_count += c
            real_items.append((info["severity"], vtype, c, info))

    # Sort by severity
    real_items.sort(key=lambda x: SEVERITY_ORDER.get(x[0], 99))

    print("REAL ISSUES (need attention):")
    if real_items:
        print(f"{'Sev':<9} {'Type':<28} {'Count':>6}  Source File -> Fix")
        print("-" * 70)
        for sev, vtype, c, info in real_items:
            delta_str = ""
            if baseline and vtype in baseline:
                diff = c - baseline[vtype]
                if diff != 0:
                    delta_str = f" ({'+' if diff > 0 else ''}{diff})"
            print(f"  {sev:<7} {vtype:<28} {c:>5}{delta_str}")
            print(f"          -> {info['source']}")
            print(f"          -> {info['fix']}")
            if vtype in details:
                for d in details[vtype][:2]:
                    print(f"            Example: {d[:60]}")
            print()
    else:
        print("  None! All clear.")
    print()

    # -- Unknown violations ---------------------------------------------------
    known_types = set(KNOWN_ACCEPTABLE.keys()) | set(REAL_ISSUES.keys())
    unknown = {k: v for k, v in counts.items() if k not in known_types and v > 0}
    unknown_count = sum(unknown.values())

    if unknown:
        print("UNCATEGORIZED VIOLATIONS (review manually):")
        print(f"{'Type':<30} {'Count':>6}")
        print("-" * 40)
        for vtype, c in sorted(unknown.items(), key=lambda x: -x[1]):
            print(f"  {vtype:<28} {c:>6}")
            if vtype in details:
                for d in details[vtype][:2]:
                    print(f"    -> {d[:60]}")
        print()

    # -- Delta from baseline --------------------------------------------------
    if baseline:
        print("DELTA FROM BASELINE:")
        new_types = set(counts.keys()) - set(baseline.keys())
        fixed_types = set(baseline.keys()) - set(counts.keys())

        total_baseline = sum(baseline.values())
        total_diff = total - total_baseline

        print(f"  Total: {total} (was {total_baseline}, "
              f"{'+'if total_diff >= 0 else ''}{total_diff})")
        if new_types:
            print(f"  New violation types: {', '.join(new_types)}")
        if fixed_types:
            print(f"  Fixed violation types: {', '.join(fixed_types)}")
        print()

    # -- Summary --------------------------------------------------------------
    print("=" * 70)
    print("SUMMARY:")
    print(f"  Total violations:      {total}")
    print(f"  Known-acceptable:      {known_count}")
    print(f"  Real issues:           {real_count}")
    print(f"  Uncategorized:         {unknown_count}")
    print()

    if real_count == 0 and unknown_count == 0:
        print("  STATUS: CLEAN — No actionable issues found")
    elif real_count > 0:
        print(f"  STATUS: {real_count} ISSUES NEED ATTENTION")
        print(f"  Priority: Fix {real_items[0][1]} first ({real_items[0][0]} severity)")

    print("=" * 70)

    if update_baseline:
        save_baseline(counts)

    return real_count


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/drc_native.py <drc-report.json> [--update-baseline]")
        print()
        print("Run kicad-cli first:")
        print("  kicad-cli pcb drc --output /tmp/drc-report.json --format json \\")
        print("    --severity-all --units mm --all-track-errors \\")
        print("    hardware/kicad/esp32-emu-turbo.kicad_pcb")
        sys.exit(1)

    report_path = sys.argv[1]
    update = "--update-baseline" in sys.argv

    if not Path(report_path).exists():
        print(f"ERROR: {report_path} not found")
        sys.exit(1)

    real_count = analyze(report_path, update_baseline=update)
    sys.exit(0)  # Always exit 0 (advisory)


if __name__ == "__main__":
    main()
