#!/usr/bin/env python3
"""DRC (Design Rule Check) for JLCPCB 4-layer PCB.

Parses the generated .kicad_pcb file and checks compliance with
JLCPCB manufacturing constraints.

Usage:
    python3 scripts/drc_check.py [path/to/file.kicad_pcb]

Exit code 0 = all checks passed, 1 = errors found.
"""

import re
import sys
import math
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ── JLCPCB 4-Layer Design Rules ──────────────────────────────────
RULES = {
    "min_trace_width": 0.09,       # mm (practical: 0.2mm)
    "min_trace_spacing": 0.09,     # mm (practical: 0.15mm)
    "min_via_drill": 0.15,         # mm
    "min_via_pad": 0.45,           # mm
    "min_annular_ring": 0.13,      # mm
    "min_board_edge_clearance": 0.3,  # mm
    "min_drill_to_edge": 0.4,      # mm
    "min_drill_spacing": 0.5,      # mm (edge-to-edge)
    "board_width": 160.0,
    "board_height": 75.0,
}

# FPC slot cutout (internal Edge.Cuts rectangle)
# PCB coordinates: center at (127, 35.5), 3mm wide × 24mm tall
SLOT_X1 = 125.5   # left edge
SLOT_X2 = 128.5   # right edge
SLOT_Y1 = 23.5    # top edge
SLOT_Y2 = 47.5    # bottom edge


def parse_pcb(filepath):
    """Parse KiCad PCB file and extract design elements."""
    text = Path(filepath).read_text()

    result = {
        "segments": [],
        "vias": [],
        "footprints": [],
        "zones": [],
        "nets": [],
        "pads": [],
    }

    # Extract segments: (segment (start X Y) (end X Y) (width W) (layer L) (net N))
    for m in re.finditer(
        r'\(segment\s+\(start\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(end\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(width\s+([\d.]+)\)\s+'
        r'\(layer\s+"([^"]+)"\)\s+'
        r'\(net\s+(\d+)\)', text
    ):
        result["segments"].append({
            "x1": float(m.group(1)), "y1": float(m.group(2)),
            "x2": float(m.group(3)), "y2": float(m.group(4)),
            "width": float(m.group(5)),
            "layer": m.group(6),
            "net": int(m.group(7)),
        })

    # Extract vias: (via (at X Y) (size S) (drill D))
    for m in re.finditer(
        r'\(via\s+\(at\s+([\d.]+)\s+([\d.]+)\)\s+'
        r'\(size\s+([\d.]+)\)\s+'
        r'\(drill\s+([\d.]+)\)', text
    ):
        result["vias"].append({
            "x": float(m.group(1)), "y": float(m.group(2)),
            "size": float(m.group(3)),
            "drill": float(m.group(4)),
        })

    # Extract net declarations
    for m in re.finditer(r'\(net\s+(\d+)\s+"([^"]*)"\)', text):
        nid = int(m.group(1))
        name = m.group(2)
        if nid > 0 and name:
            result["nets"].append({"id": nid, "name": name})

    # Extract mounting holes / pads with drill
    for m in re.finditer(
        r'\(pad\s+"[^"]*"\s+thru_hole\s+\w+\s+\(at\s+([\d.-]+)\s+([\d.-]+)\)'
        r'\s+\(size\s+([\d.]+)\s+([\d.]+)\)'
        r'\s+\(drill\s+([\d.]+)\)', text
    ):
        result["pads"].append({
            "x": float(m.group(1)), "y": float(m.group(2)),
            "size_w": float(m.group(3)), "size_h": float(m.group(4)),
            "drill": float(m.group(5)),
        })

    return result


def check_trace_width(data):
    """Check all trace widths meet minimum."""
    errors = []
    min_w = RULES["min_trace_width"]
    for seg in data["segments"]:
        if seg["width"] < min_w:
            errors.append(
                f"Trace width {seg['width']}mm < {min_w}mm at "
                f"({seg['x1']},{seg['y1']})->({seg['x2']},{seg['y2']}) "
                f"on {seg['layer']}"
            )
    return errors


def check_via_dimensions(data):
    """Check via drill and annular ring."""
    errors = []
    min_drill = RULES["min_via_drill"]
    min_ring = RULES["min_annular_ring"]
    for v in data["vias"]:
        if v["drill"] < min_drill:
            errors.append(
                f"Via drill {v['drill']}mm < {min_drill}mm at "
                f"({v['x']},{v['y']})"
            )
        ring = (v["size"] - v["drill"]) / 2
        if ring < min_ring:
            errors.append(
                f"Via annular ring {ring:.3f}mm < {min_ring}mm at "
                f"({v['x']},{v['y']})"
            )
    return errors


def _in_slot(x, y, margin):
    """Check if point (with margin) intrudes into the FPC slot cutout."""
    return (SLOT_X1 - margin < x < SLOT_X2 + margin and
            SLOT_Y1 - margin < y < SLOT_Y2 + margin)


def _segment_crosses_slot(x1, y1, x2, y2, hw):
    """Check if a trace segment physically crosses through the FPC slot.

    A horizontal segment crosses if it spans the slot x-range while within
    the slot y-range. A vertical segment crosses if it spans the slot y-range
    while within the slot x-range. hw = half-width of the trace.
    """
    if abs(y1 - y2) < 0.01:  # horizontal segment
        y = y1
        if SLOT_Y1 - hw <= y <= SLOT_Y2 + hw:
            lo, hi = min(x1, x2), max(x1, x2)
            if lo < SLOT_X1 - hw and hi > SLOT_X2 + hw:
                return True
    elif abs(x1 - x2) < 0.01:  # vertical segment
        x = x1
        if SLOT_X1 - hw <= x <= SLOT_X2 + hw:
            lo, hi = min(y1, y2), max(y1, y2)
            if lo < SLOT_Y1 - hw and hi > SLOT_Y2 + hw:
                return True
    return False


def check_board_edge_clearance(data):
    """Check all elements are inside board boundaries with margin,
    and not intruding into the FPC slot cutout."""
    errors = []
    margin = RULES["min_board_edge_clearance"]
    bw = RULES["board_width"]
    bh = RULES["board_height"]

    for seg in data["segments"]:
        hw = seg["width"] / 2
        for x, y in [(seg["x1"], seg["y1"]), (seg["x2"], seg["y2"])]:
            if (x - hw < margin or x + hw > bw - margin or
                    y - hw < margin or y + hw > bh - margin):
                errors.append(
                    f"Trace at ({x},{y}) too close to board edge "
                    f"(margin={margin}mm)"
                )
            # Check endpoint slot clearance
            if _in_slot(x, y, margin):
                errors.append(
                    f"Trace at ({x},{y}) too close to FPC slot"
                )
        # Check if segment crosses through the slot
        if _segment_crosses_slot(seg["x1"], seg["y1"],
                                 seg["x2"], seg["y2"], hw):
            errors.append(
                f"Trace ({seg['x1']},{seg['y1']})->"
                f"({seg['x2']},{seg['y2']}) crosses FPC slot"
            )

    for v in data["vias"]:
        r = v["size"] / 2
        if (v["x"] - r < margin or v["x"] + r > bw - margin or
                v["y"] - r < margin or v["y"] + r > bh - margin):
            errors.append(
                f"Via at ({v['x']},{v['y']}) too close to board edge"
            )
        if _in_slot(v["x"], v["y"], margin):
            errors.append(
                f"Via at ({v['x']},{v['y']}) too close to FPC slot"
            )

    return errors


def _seg_distance(s1, s2):
    """Approximate minimum distance between two segments on same layer."""
    # Simplified: check endpoint distances
    min_d = float('inf')
    pts1 = [(s1["x1"], s1["y1"]), (s1["x2"], s1["y2"])]
    pts2 = [(s2["x1"], s2["y1"]), (s2["x2"], s2["y2"])]
    for p1 in pts1:
        for p2 in pts2:
            d = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
            min_d = min(min_d, d)
    return min_d


def check_trace_spacing(data):
    """Check minimum spacing between traces on same layer."""
    errors = []
    min_sp = RULES["min_trace_spacing"]

    # Group segments by layer
    by_layer = {}
    for seg in data["segments"]:
        by_layer.setdefault(seg["layer"], []).append(seg)

    for layer, segs in by_layer.items():
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                s1, s2 = segs[i], segs[j]
                # Skip if same net (allowed to overlap)
                if s1["net"] == s2["net"] and s1["net"] != 0:
                    continue
                d = _seg_distance(s1, s2)
                hw = (s1["width"] + s2["width"]) / 2
                clearance = d - hw
                if 0 < clearance < min_sp:
                    errors.append(
                        f"Trace spacing {clearance:.3f}mm < {min_sp}mm "
                        f"on {layer} between nets {s1['net']} and {s2['net']}"
                    )
                    if len(errors) > 20:
                        errors.append("... (truncated, too many spacing errors)")
                        return errors

    return errors


def check_drill_spacing(data):
    """Check minimum spacing between via drill holes.

    Note: THT pad positions in footprints are relative coordinates,
    not absolute.  We only check via-to-via spacing here since vias
    have absolute board coordinates.
    """
    errors = []
    min_sp = RULES["min_drill_spacing"]

    vias = [(v["x"], v["y"], v["drill"] / 2) for v in data["vias"]]

    for i in range(len(vias)):
        for j in range(i + 1, len(vias)):
            x1, y1, r1 = vias[i]
            x2, y2, r2 = vias[j]
            d = math.hypot(x1 - x2, y1 - y2)
            clearance = d - r1 - r2
            if 0 < clearance < min_sp:
                errors.append(
                    f"Via drill spacing {clearance:.3f}mm < {min_sp}mm "
                    f"between ({x1},{y1}) and ({x2},{y2})"
                )

    return errors


def check_component_overlap():
    """Check that no two components overlap (< 3mm center-to-center).

    Also verifies no component is placed on a mounting hole.
    Uses the CPL placement data from jlcpcb_export.
    """
    from scripts.generate_pcb.jlcpcb_export import _build_placements
    from scripts.generate_pcb.board import MOUNT_HOLES_ENC, enc_to_pcb

    MIN_DIST = 3.0  # mm minimum center-to-center

    placements = _build_placements()
    mounts = [enc_to_pcb(ex, ey) for ex, ey in MOUNT_HOLES_ENC]

    # Build list of all positioned items
    items = [(ref, x, y) for ref, _, _, x, y, _, layer in placements
             if layer == "bottom"]
    items += [(f"MH@{mx:.0f},{my:.0f}", mx, my) for mx, my in mounts]

    errors = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            r1, x1, y1 = items[i]
            r2, x2, y2 = items[j]
            d = math.hypot(x2 - x1, y2 - y1)
            if d < MIN_DIST:
                errors.append(
                    f"{r1} <-> {r2}: {d:.1f}mm apart (min {MIN_DIST}mm)"
                )
    return errors


def check_net_connectivity(data):
    """Check that all declared nets have at least 2 connections."""
    warnings = []
    net_usage = {}

    for seg in data["segments"]:
        net = seg["net"]
        if net > 0:
            net_usage[net] = net_usage.get(net, 0) + 1

    for via in data["vias"]:
        # Vias parsed without net in our regex — skip
        pass

    net_names = {n["id"]: n["name"] for n in data["nets"]}
    for nid, name in net_names.items():
        count = net_usage.get(nid, 0)
        if count == 0:
            warnings.append(f"Net {nid} \"{name}\" has no traces")
        elif count == 1:
            warnings.append(f"Net {nid} \"{name}\" has only 1 trace segment")

    return warnings


def main():
    pcb_path = sys.argv[1] if len(sys.argv) > 1 else \
        "hardware/kicad/esp32-emu-turbo.kicad_pcb"

    if not Path(pcb_path).exists():
        print(f"ERROR: {pcb_path} not found")
        sys.exit(1)

    print(f"DRC Check: {pcb_path}")
    print(f"Rules: JLCPCB 4-layer")
    print("=" * 60)

    data = parse_pcb(pcb_path)
    print(f"Parsed: {len(data['segments'])} segments, "
          f"{len(data['vias'])} vias, "
          f"{len(data['nets'])} nets, "
          f"{len(data['pads'])} THT pads")
    print()

    all_errors = []
    all_warnings = []

    checks = [
        ("Trace Width", check_trace_width),
        ("Via Dimensions", check_via_dimensions),
        ("Board Edge Clearance", check_board_edge_clearance),
        ("Trace Spacing", check_trace_spacing),
        ("Drill Spacing", check_drill_spacing),
    ]

    # Component overlap check (uses CPL data, not PCB data)
    overlap_errors = check_component_overlap()
    status = "PASS" if not overlap_errors else \
        f"FAIL ({len(overlap_errors)} errors)"
    print(f"  [{status}] Component Overlap")
    for e in overlap_errors[:10]:
        print(f"         {e}")
    all_errors.extend(overlap_errors)

    for name, fn in checks:
        errors = fn(data)
        status = "PASS" if not errors else f"FAIL ({len(errors)} errors)"
        print(f"  [{status}] {name}")
        for e in errors[:5]:
            print(f"         {e}")
        if len(errors) > 5:
            print(f"         ... and {len(errors) - 5} more")
        all_errors.extend(errors)

    # Connectivity is a warning, not a hard error
    print()
    warnings = check_net_connectivity(data)
    if warnings:
        print(f"  [WARN] Net Connectivity ({len(warnings)} warnings)")
        for w in warnings[:10]:
            print(f"         {w}")
        if len(warnings) > 10:
            print(f"         ... and {len(warnings) - 10} more")
        all_warnings.extend(warnings)
    else:
        print("  [PASS] Net Connectivity")

    print()
    print("=" * 60)
    if all_errors:
        print(f"RESULT: FAIL — {len(all_errors)} errors, "
              f"{len(all_warnings)} warnings")
        sys.exit(1)
    else:
        print(f"RESULT: PASS — 0 errors, {len(all_warnings)} warnings")
        sys.exit(0)


if __name__ == "__main__":
    main()
