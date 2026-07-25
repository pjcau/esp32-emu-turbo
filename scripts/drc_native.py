#!/usr/bin/env python3
"""Smart KiCad DRC analysis with JLCPCB rules and fix suggestions.

Wraps kicad-cli DRC JSON output with:
- JLCPCB manufacturing constraint checking (via .kicad_dru rules)
- Known-acceptable violation filtering
- Delta tracking vs saved baseline
- Source file mapping for fix suggestions
- Priority ranking by severity and fixability

Usage:
    python3 scripts/drc_native.py --run                    # Run DRC + analyze
    python3 scripts/drc_native.py --run --update-baseline  # Run + save baseline
    python3 scripts/drc_native.py <drc-report.json>        # Analyze existing report

Exit code 0 = no real issues, 1 = real issues found.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from collections import Counter

BASELINE_PATH = Path("scripts/drc_baseline.json")
PCB_PATH = Path("hardware/kicad/esp32-emu-turbo.kicad_pcb")
DRU_PATH = Path("hardware/kicad/esp32-emu-turbo.kicad_dru")

# Known-acceptable violations in the generated PCB.
# NOTE: "shorting_items" removed — pad nets are now correctly assigned
# by routing.py auto-capture + board.py injection. Real shorting
# violations will surface as true positives.
KNOWN_ACCEPTABLE = {
    "solder_mask_bridge": "Fine-pitch FPC/USB-C connectors (expected, JLCPCB handles this)",
    "lib_footprint_mismatch": "Generated footprints differ from KiCad library copies (cosmetic)",
    "text_height": "Silkscreen text below 1mm height (cosmetic, does not affect assembly)",
}

# ─── Removed from KNOWN_ACCEPTABLE 2026-07-25 — do not reintroduce ────
#
# Seven entries were promoted to REAL_ISSUES below. At the time of the change
# the DRC reported 0 violations of every type, so this is a no-op on the
# current board and purely a change to what a FUTURE regression is allowed to
# do quietly. Each was justified by a claim that does not hold:
#
#   isolated_copper   "small copper fills isolated from nets, removed during
#                     manufacturing" — this is the exact signature of the v1
#                     dead board. The In2.Cu +3V3 pour was carved into 4
#                     groups and the AMS1117 fed a 4.92 mm² orphan island.
#                     An isolated fill is not swarf, it is an open circuit.
#   via_dangling      "appear dangling before zone fill" — false: --run fills
#   track_dangling    zones and THEN runs DRC, so the report is post-fill.
#                     A dangling via after the fill is a real open.
#   clearance_zone    "JLCPCB adds thermal relief automatically" — an
#                     assumption about the fab, not a property of the design.
#                     Via-to-inner-zone clearance loss is a short.
#   clearance_borderline  "JLCPCB 4-layer manufactures fine at >=0.075mm" —
#                     contradicts the published 4-layer minimum this repo
#                     enforces everywhere else (verify_copper_clearance uses
#                     0.15mm preferred / 0.10mm danger).
#   hole_clearance    "via-in-pad for button footprints (intentional)" — stale:
#                     verify_via_in_pad's KNOWN_INTENTIONAL is empty and the
#                     gate passes, i.e. there is no intentional via-in-pad left.
#   courtyardOverlap  "acceptable for PCBA" — courtyard overlap is how parts
#                     collide on the assembly line; that is DFA's whole job.

# Zone clearance violations (via vs GND zone on inner layers) are expected
# because the generator places vias without thermal relief offsets.
# JLCPCB handles this with automatic thermal relief generation.
ZONE_CLEARANCE_PATTERN = "zone clearance"

# ─── Removed suppressions — do not reintroduce ───────────────────────
#
# ZONE_CONNECTED_NETS and ACCEPTED_UNCONNECTED_NETS used to live here. They
# reclassified real DRC unconnected_items into two invented buckets
# ("unconnected_zone" and "unconnected_accepted") which were then baselined
# away in drc_baseline.json.
#
# The rationale was: "Power/data nets connected through inner-layer zones (not
# direct traces)". That assumption is false when the zone is itself split. On
# PCB v1 the In2.Cu +3V3 pour was carved into 4 separate groups by two
# higher-priority +5V zones; the AMS1117 fed a 4.92 mm² orphan island and the
# board was completely dead. KiCad's DRC WAS reporting those opens — this code
# is what hid them. See website/docs/rework/incident-3v3-split-plane.md.
#
# Unconnected items are now reported as unconnected_items (CRITICAL), full
# stop. Zone-aware connectivity is proven positively, not assumed, by
# scripts/verify_power_net_integrity.py.

# Violation types that indicate REAL issues to fix
REAL_ISSUES = {
    "isolated_copper": {
        "severity": "CRITICAL",
        "source": "scripts/generate_pcb/routing.py + zone priorities",
        "fix": "A fill island isolated from its net is an OPEN, not swarf. "
               "Run verify_power_net_integrity.py to see which net split.",
    },
    "via_dangling": {
        "severity": "CRITICAL",
        "source": "scripts/generate_pcb/routing.py",
        "fix": "Post-fill dangling via = the via never reached the zone. "
               "Check the zone actually pours around it (verify_zone_connectivity.py).",
    },
    "track_dangling": {
        "severity": "CRITICAL",
        "source": "scripts/generate_pcb/routing.py",
        "fix": "Post-fill dangling track = an open segment. Trace it with "
               "verify_net_connectivity.py.",
    },
    "clearance_zone": {
        "severity": "HIGH",
        "source": "scripts/generate_pcb/board.py (zone definitions)",
        "fix": "Via-to-inner-zone clearance loss is a short. Move the via or "
               "add a proper thermal relief — do not assume the fab fixes it.",
    },
    "clearance_borderline": {
        "severity": "HIGH",
        "source": "scripts/generate_pcb/routing.py",
        "fix": "Below the JLCPCB 4-layer minimum enforced elsewhere in this "
               "repo. Widen the gap to >=0.15mm.",
    },
    "hole_clearance": {
        "severity": "HIGH",
        "source": "scripts/generate_pcb/primitives.py",
        "fix": "Drill-to-drill or drill-to-pad spacing below fab minimum. "
               "See the via-to-via >=0.25mm hole-gap rule.",
    },
    "courtyardOverlap": {
        "severity": "MEDIUM",
        "source": "scripts/generate_pcb/board.py (placement)",
        "fix": "Overlapping courtyards are colliding parts at assembly. "
               "Separate the placements or shrink the courtyard to the real body.",
    },
    "clearance_trace": {
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
    # R9-MED-3 (2026-04-11): tracks_crossing must be CRITICAL.
    # KiCad's tracks_crossing rule fires when two segments on the same
    # copper layer intersect without being joined at a node — at the
    # fabricator the copper merges, creating a short between nets.
    # Previously this category was "UNCATEGORIZED" which let R9-CRIT-1
    # (BTN_START crossing LCD_CS/DC/WR) ship past R7/R8 verification.
    "tracks_crossing": {
        "severity": "CRITICAL",
        "source": "scripts/generate_pcb/routing.py",
        "fix": "Reroute one of the two crossing segments. Move it to the opposite copper layer (F.Cu↔B.Cu) or find an alternate corridor.",
    },
    # lib_footprint_issues: missing library entries. Not a fab issue but
    # should still be reported so the project's fp-lib-table stays clean.
    "lib_footprint_issues": {
        "severity": "LOW",
        "source": "hardware/kicad/esp32-emu-turbo.kicad_pro (fp-lib-table)",
        "fix": "Add the referenced library to the project fp-lib-table, or embed its footprints in the project library.",
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

    # Count violations, splitting clearance into zone vs trace vs borderline
    import re as _re
    for v in report.get("violations", []):
        vtype = v.get("type", "unknown")
        desc = v.get("description", "")

        # Split clearance into 3 categories:
        #   zone clearance → known-acceptable (JLCPCB thermal relief)
        #   borderline (0.075-0.09mm) → acceptable (JLCPCB manufactures fine)
        #   real (<0.075mm) → needs fix
        if vtype == "clearance" and ZONE_CLEARANCE_PATTERN in desc:
            vtype = "clearance_zone"
        elif vtype == "clearance":
            # Check if this is a trace-vs-unnetted-pad false positive
            items = v.get("items", [])
            has_no_net = any("<no net>" in i.get("description", "") for i in items)
            if has_no_net:
                vtype = "clearance_zone"  # false positive: trace near unnetted pad
            else:
                actual_match = _re.search(r"actual ([\d.]+)\s*mm", desc)
                if actual_match:
                    actual = float(actual_match.group(1))
                    if actual >= 0.075:
                        vtype = "clearance_borderline"
                    else:
                        vtype = "clearance_trace"
                else:
                    vtype = "clearance_trace"

        counts[vtype] += 1
        if vtype not in details:
            details[vtype] = []
        if len(details[vtype]) < 5:  # Keep top 5 examples
            details[vtype].append(desc)

    # Count unconnected items. Every one of them is a real open circuit —
    # there is no "but a zone will bridge it" exemption (see the note above
    # the removed suppression constants).
    unconnected = report.get("unconnected_items", [])
    for u in unconnected:
        items = u.get("items", [])
        net_names = [i.get("description", "") for i in items]
        vtype = "unconnected_items"
        counts[vtype] += 1
        if vtype not in details:
            details[vtype] = []
        if len(details[vtype]) < 5:
            desc_str = " / ".join(n.split("]")[0] + "]" for n in net_names if "[" in n)
            details[vtype].append(desc_str or u.get("description", ""))

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

    # Uncategorized types count as failures. They used to be printed under
    # "review manually" and then dropped from the return value, so a DRC
    # violation type nobody had classified yet exited 0 — a new failure mode
    # arriving in a KiCad upgrade would have been reported as CLEAN.
    return real_count + unknown_count


def fill_zones():
    """Fill zones via Docker pcbnew API. Works on the PCB file in-place."""
    print("==> Zone fill via Docker (pcbnew API)...")

    project_root = Path(__file__).resolve().parent.parent
    cmd = [
        "docker", "compose", "-f", str(project_root / "docker-compose.yml"),
        "run", "--rm", "--entrypoint", "python3",
        "kicad-pcb",
        "/scripts/kicad_fill_zones.py", f"/project/{PCB_PATH.name}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Zone fill FAILED (exit {result.returncode}):")
        print(result.stderr)
        print(result.stdout)
        return False

    for line in result.stdout.strip().split("\n"):
        print(f"  {line}")
    print()
    return True


def run_drc(skip_zone_fill=False):
    """Fill zones + run kicad-cli DRC with JLCPCB rules. Returns report path."""
    if not PCB_PATH.exists():
        print(f"ERROR: {PCB_PATH} not found")
        sys.exit(1)

    if DRU_PATH.exists():
        print(f"JLCPCB rules: {DRU_PATH}")
    else:
        print("WARNING: No .kicad_dru rules file found — using project defaults only")
    print()

    # Step 1: Zone fill (unless skipped)
    if not skip_zone_fill:
        if not fill_zones():
            print("WARNING: Zone fill failed — running DRC without filled zones")
            print("         (expect false-positive unconnected_items on power nets)")
            print()

    # Step 2: DRC
    report_fd, report_path = tempfile.mkstemp(suffix=".json", prefix="drc-")

    cmd = [
        "kicad-cli", "pcb", "drc",
        "--output", report_path,
        "--format", "json",
        "--severity-all",
        "--units", "mm",
        "--all-track-errors",
        str(PCB_PATH),
    ]

    print(f"==> Running DRC: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode not in (0, 5):  # 5 = violations found (expected)
        print(f"kicad-cli FAILED (exit {result.returncode}):")
        print(result.stderr)
        sys.exit(1)

    return report_path


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 scripts/drc_native.py --run                       # Zone fill + DRC + analyze")
        print("  python3 scripts/drc_native.py --run --no-zone-fill        # DRC only (skip Docker zone fill)")
        print("  python3 scripts/drc_native.py --run --update-baseline     # Run + save baseline")
        print("  python3 scripts/drc_native.py <drc-report.json>           # Analyze existing report")
        sys.exit(1)

    update = "--update-baseline" in sys.argv
    skip_fill = "--no-zone-fill" in sys.argv

    if "--run" in sys.argv:
        report_path = run_drc(skip_zone_fill=skip_fill)
    else:
        report_path = [a for a in sys.argv[1:] if not a.startswith("--")][0]
        if not Path(report_path).exists():
            print(f"ERROR: {report_path} not found")
            sys.exit(1)

    real_count = analyze(report_path, update_baseline=update)
    # Exit non-zero when there are real issues. This used to be a hard
    # "always exit 0 (advisory)" — which meant the CRITICAL unconnected_items
    # count was computed and then thrown away. Combined with the
    # unconnected_zone / unconnected_accepted buckets (removed above), a dead
    # board passed DRC.
    sys.exit(1 if real_count else 0)


if __name__ == "__main__":
    main()
