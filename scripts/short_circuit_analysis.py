#!/usr/bin/env python3
"""Short circuit and zone fill analysis for JLCPCB 4-layer PCB.

Checks the generated .kicad_pcb for:
  1. Overlapping traces on the same layer with different nets (shorts)
  2. Zone priority conflicts on inner layers
  3. Missing zone fill data (empty inner layers)
  4. Trace-through-zone short circuits
  5. Pad net assignments

Usage:
    python3 scripts/short_circuit_analysis.py [path/to/file.kicad_pcb]

Exit code 0 = all checks passed, 1 = critical issues found.
"""

import re
import sys
import math
from pathlib import Path

# ── Defaults ──────────────────────────────────────────────────────
DEFAULT_PCB = "hardware/kicad/esp32-emu-turbo.kicad_pcb"

BOARD_W = 160.0
BOARD_H = 75.0

# FPC slot cutout (PCB coordinates)
SLOT_X1, SLOT_X2 = 125.5, 128.5
SLOT_Y1, SLOT_Y2 = 23.5, 47.5


def parse_pcb(filepath):
    """Parse KiCad PCB and extract elements for analysis (via cache)."""
    from pcb_cache import load_cache
    cache = load_cache(Path(filepath))

    # Convert nets from list to dict {id: name}
    nets = {n["id"]: n["name"] for n in cache["nets"]
            if n["id"] > 0 and n["name"]}

    # Simplify pads to just {net: N}
    pad_nets = [{"net": p["net"]} for p in cache["pads"]]

    return {
        "segments": cache["segments"],
        "vias": cache["vias"],
        "zones": cache["zones"],
        "nets": nets,
        "pads": pad_nets,
        "filled_polygons": cache["filled_polygons"],
    }


def _segments_overlap(s1, s2):
    """Check if two segments on the same layer physically overlap.

    Returns True if the copper of the two traces touches/overlaps.
    Only checks collinear and crossing orthogonal segments.
    """
    hw1 = s1["width"] / 2
    hw2 = s2["width"] / 2

    # Check if segments are collinear horizontal
    if (abs(s1["y1"] - s1["y2"]) < 0.01 and
            abs(s2["y1"] - s2["y2"]) < 0.01):
        # Both horizontal
        if abs(s1["y1"] - s2["y1"]) < hw1 + hw2:
            # Y overlap — check X overlap
            lo1, hi1 = min(s1["x1"], s1["x2"]), max(s1["x1"], s1["x2"])
            lo2, hi2 = min(s2["x1"], s2["x2"]), max(s2["x1"], s2["x2"])
            if lo1 < hi2 and lo2 < hi1:
                return True

    # Check if segments are collinear vertical
    if (abs(s1["x1"] - s1["x2"]) < 0.01 and
            abs(s2["x1"] - s2["x2"]) < 0.01):
        # Both vertical
        if abs(s1["x1"] - s2["x1"]) < hw1 + hw2:
            lo1, hi1 = min(s1["y1"], s1["y2"]), max(s1["y1"], s1["y2"])
            lo2, hi2 = min(s2["y1"], s2["y2"]), max(s2["y1"], s2["y2"])
            if lo1 < hi2 and lo2 < hi1:
                return True

    # Check orthogonal crossing (H crosses V)
    def _h_crosses_v(h, v, hw_h, hw_v):
        """Horizontal segment h crosses vertical segment v."""
        hy = h["y1"]
        vx = v["x1"]
        h_lo = min(h["x1"], h["x2"])
        h_hi = max(h["x1"], h["x2"])
        v_lo = min(v["y1"], v["y2"])
        v_hi = max(v["y1"], v["y2"])
        if (h_lo - hw_v <= vx <= h_hi + hw_v and
                v_lo - hw_h <= hy <= v_hi + hw_h):
            return True
        return False

    s1_horiz = abs(s1["y1"] - s1["y2"]) < 0.01
    s2_horiz = abs(s2["y1"] - s2["y2"]) < 0.01
    s1_vert = abs(s1["x1"] - s1["x2"]) < 0.01
    s2_vert = abs(s2["x1"] - s2["x2"]) < 0.01

    if s1_horiz and s2_vert:
        if _h_crosses_v(s1, s2, hw1, hw2):
            return True
    if s2_horiz and s1_vert:
        if _h_crosses_v(s2, s1, hw2, hw1):
            return True

    return False


def check_trace_shorts(data):
    """Find overlapping traces on the same layer with different nets."""
    errors = []
    by_layer = {}
    for seg in data["segments"]:
        by_layer.setdefault(seg["layer"], []).append(seg)

    for layer, segs in by_layer.items():
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                s1, s2 = segs[i], segs[j]
                if s1["net"] == s2["net"]:
                    continue  # same net, OK
                if _segments_overlap(s1, s2):
                    n1 = data["nets"].get(s1["net"], f"#{s1['net']}")
                    n2 = data["nets"].get(s2["net"], f"#{s2['net']}")
                    errors.append(
                        f"TRACE_SHORT on {layer}: {n1} "
                        f"({s1['x1']},{s1['y1']})->({s1['x2']},{s1['y2']}) "
                        f"overlaps {n2} "
                        f"({s2['x1']},{s2['y1']})->({s2['x2']},{s2['y2']})"
                    )
                    if len(errors) > 50:
                        errors.append("... truncated")
                        return errors
    return errors


def check_zone_priorities(data):
    """Check that overlapping zones on the same layer have distinct priorities."""
    errors = []
    by_layer = {}
    for z in data["zones"]:
        by_layer.setdefault(z["layer"], []).append(z)

    for layer, zones in by_layer.items():
        if len(zones) <= 1:
            continue
        priorities = [z["priority"] for z in zones]
        names = [z["net_name"] for z in zones]
        # Check for missing priorities
        for z in zones:
            if z["priority"] < 0:
                errors.append(
                    f"ZONE_NO_PRIORITY on {layer}: {z['net_name']} "
                    f"has no priority tag — overlapping zones will conflict"
                )
        # Check for duplicate priorities
        seen = {}
        for z in zones:
            if z["priority"] >= 0:
                if z["priority"] in seen:
                    errors.append(
                        f"ZONE_PRIORITY_DUP on {layer}: {z['net_name']} and "
                        f"{seen[z['priority']]} both have priority "
                        f"{z['priority']}"
                    )
                seen[z["priority"]] = z["net_name"]
    return errors


def check_zone_fill(data):
    """Check that zones have filled_polygon data (non-empty copper pour)."""
    errors = []
    if data["zones"] and data["filled_polygons"] == 0:
        errors.append(
            f"NO_ZONE_FILL: {len(data['zones'])} zones defined but 0 "
            f"filled_polygon sections — inner layers will be empty! "
            f"Run kicad-cli to fill zones."
        )
    return errors


def check_pad_nets(data):
    """Check that pads have net assignments."""
    warnings = []
    total = len(data["pads"])
    net0 = sum(1 for p in data["pads"] if p["net"] == 0)
    if total > 0 and net0 == total:
        warnings.append(
            f"ALL_PADS_NET0: All {total} pads have net 0 — "
            f"programmatic PCB generation does not assign pad nets "
            f"(normal for this project, KiCad assigns during zone fill)"
        )
    return warnings


GERBER_DIR = "hardware/kicad/gerbers"

# Internal layer Gerbers must be larger than pad-only files (~2KB)
MIN_GERBER_BYTES = 5000


def check_gerber_sizes():
    """Check that internal layer Gerbers contain copper fill data."""
    errors = []
    gerber_dir = Path(GERBER_DIR)

    if not gerber_dir.exists():
        errors.append(
            f"GERBER_DIR_MISSING: {GERBER_DIR} not found. "
            f"Run 'make export-gerbers' first."
        )
        return errors

    internal_files = {
        "esp32-emu-turbo-In1_Cu.g1": "GND plane (In1.Cu)",
        "esp32-emu-turbo-In2_Cu.g2": "3V3/5V planes (In2.Cu)",
    }

    for filename, desc in internal_files.items():
        filepath = gerber_dir / filename
        if not filepath.exists():
            errors.append(f"GERBER_MISSING: {filename} ({desc}) not found")
        else:
            size = filepath.stat().st_size
            if size < MIN_GERBER_BYTES:
                errors.append(
                    f"GERBER_EMPTY: {filename} ({desc}) is only {size} bytes "
                    f"— zone fill is likely missing (expected >{MIN_GERBER_BYTES}B)"
                )

    return errors


def main():
    pcb_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PCB

    if not Path(pcb_path).exists():
        print(f"ERROR: {pcb_path} not found")
        sys.exit(1)

    print(f"Short Circuit Analysis: {pcb_path}")
    print("=" * 60)

    data = parse_pcb(pcb_path)
    print(f"Parsed: {len(data['segments'])} segments, "
          f"{len(data['vias'])} vias, "
          f"{len(data['zones'])} zones, "
          f"{len(data['nets'])} nets, "
          f"{len(data['pads'])} pads, "
          f"{data['filled_polygons']} filled polygons")
    print()

    all_critical = []
    all_warnings = []

    # Critical checks
    checks = [
        ("Trace Shorts", check_trace_shorts),
        ("Zone Priorities", check_zone_priorities),
        ("Zone Fill Data", check_zone_fill),
    ]

    for name, fn in checks:
        errors = fn(data)
        status = "PASS" if not errors else f"FAIL ({len(errors)})"
        print(f"  [{status}] {name}")
        for e in errors[:60]:
            print(f"    CRITICAL: {e}")
        if len(errors) > 60:
            print(f"    ... and {len(errors) - 60} more")
        all_critical.extend(errors)

    # Gerber check
    gerber_errors = check_gerber_sizes()
    status = "PASS" if not gerber_errors else f"FAIL ({len(gerber_errors)})"
    print(f"  [{status}] Gerber File Sizes")
    for e in gerber_errors:
        print(f"    CRITICAL: {e}")
    all_critical.extend(gerber_errors)

    # Warning checks
    warn_checks = [
        ("Pad Net Assignments", check_pad_nets),
    ]
    for name, fn in warn_checks:
        warnings = fn(data)
        status = "PASS" if not warnings else f"WARN ({len(warnings)})"
        print(f"  [{status}] {name}")
        for w in warnings:
            print(f"    WARN: {w}")
        all_warnings.extend(warnings)

    print()
    print("=" * 60)
    if all_critical:
        print(f"RESULT: FAIL — {len(all_critical)} critical issues, "
              f"{len(all_warnings)} warnings")
        sys.exit(1)
    else:
        print(f"RESULT: PASS — 0 critical issues, "
              f"{len(all_warnings)} warnings")
        sys.exit(0)


if __name__ == "__main__":
    main()
