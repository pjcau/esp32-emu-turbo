"""Fail when a schematic label does not lie on the wire it is meant to name.

A KiCad label only renames a net if it physically touches that net's copper
on the drawing — a wire, a junction, or a pin endpoint. A label 1.5 mm away
looks identical to a human reader and to every renderer, but names nothing:
the wire stays unnamed, and KiCad drops unnamed nets from the exported
netlist entirely. The pins on that wire then vanish from the netlist rather
than appearing with a wrong net, which is far worse than a mismatch —
`verify_netlist_diff` iterates schematic pins, so a pin that is not there is
compared against nothing and the gate goes green.

This has happened three times in this design, each time discovered by
accident:

1. R24-HIGH-3 — SW15/SW14 wired on the wrong axis, so all four pins
   were absent from the netlist while the sheet looked correct.
2. `BAT_IN` at `q1y - 0.5`, recorded in power_supply.py as floating "1.77mm
   off every wire", fixed to `jst_plus_y - 1.5` — which was still 1.5 mm
   off the same horizontal, so it named nothing either.
3. `BAT+` at `bat_y - 2` and `VBUS` at `vbus_y - 2`, found in 2026-07 by
   scripts/vbench/netlist.py noticing that the board's two main supply
   rails each had exactly ONE node on the schematic. L1's pin numbering was
   reversed underneath that, invisible for as long as the rail was unnamed.

The check is geometric and needs no expectations table: a label is attached
or it is not.

Usage:
    python3 scripts/verify_schematic_label_attach.py
"""

import glob
import math
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCH_GLOB = os.path.join(BASE, "hardware", "kicad", "*.kicad_sch")

# KiCad writes coordinates at 4 decimal places; 1 um of slack absorbs
# formatting, nothing else. A label that misses by 0.01 mm still misses.
TOL = 0.001

_WIRE = re.compile(
    r"\(wire\s*\(pts\s*\(xy\s+([-\d.]+)\s+([-\d.]+)\)\s*"
    r"\(xy\s+([-\d.]+)\s+([-\d.]+)\)\)")
_LABEL = re.compile(
    r"\((label|global_label|hierarchical_label)\s+\"([^\"]+)\""
    r"(?:\s*\(shape\s+\w+\))?\s*\(at\s+([-\d.]+)\s+([-\d.]+)")
_JUNCTION = re.compile(r"\(junction\s*\(at\s+([-\d.]+)\s+([-\d.]+)\)")
# A label may also sit directly on a symbol pin. Pin endpoints are not
# computed here (that needs the symbol library plus the placement
# transform), so instead of guessing, a label that touches no wire and no
# junction is reported with its coordinates and the reader decides. In
# practice every net in this design is named on a wire or a drawn stub:
# sheet_base.link() always draws one.


def _on_segment(px, py, x1, y1, x2, y2):
    """True if (px, py) lies on the segment, endpoints included."""
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) < TOL and abs(dy) < TOL:              # zero-length wire
        return math.hypot(px - x1, py - y1) <= TOL
    # Distance from the point to the infinite line, then a range check.
    length = math.hypot(dx, dy)
    if abs(dy * (px - x1) - dx * (py - y1)) / length > TOL:
        return False
    t = ((px - x1) * dx + (py - y1) * dy) / (length * length)
    return -TOL <= t <= 1 + TOL


def check_sheet(path):
    """Return a list of (name, x, y) labels that touch nothing."""
    src = open(path, errors="replace").read()
    wires = [tuple(float(v) for v in m.groups()) for m in _WIRE.finditer(src)]
    junctions = [(float(m.group(1)), float(m.group(2)))
                 for m in _JUNCTION.finditer(src)]
    orphans = []
    total = 0
    for m in _LABEL.finditer(src):
        kind, name, x, y = m.group(1), m.group(2), float(m.group(3)), float(m.group(4))
        total += 1
        if any(_on_segment(x, y, *w) for w in wires):
            continue
        if any(math.hypot(x - jx, y - jy) <= TOL for jx, jy in junctions):
            continue
        orphans.append((kind, name, x, y))
    return total, orphans


def main():
    sheets = sorted(glob.glob(SCH_GLOB))
    if not sheets:
        print(f"  ERROR  no schematics found at {SCH_GLOB}", file=sys.stderr)
        return 2

    print("=" * 72)
    print("  Schematic labels — every label must lie on the wire it names")
    print("=" * 72)
    grand_total = grand_orphans = 0
    for path in sheets:
        total, orphans = check_sheet(path)
        grand_total += total
        grand_orphans += len(orphans)
        mark = "OK  " if not orphans else "FAIL"
        print(f"  [{mark}] {os.path.basename(path):<32} "
              f"{total:>4} label(s), {len(orphans)} attached to nothing")
        for kind, name, x, y in orphans:
            print(f"           {kind} {name!r} at ({x}, {y}) — names no wire")
    print("-" * 72)
    if grand_orphans:
        print(f"  FAIL — {grand_orphans} of {grand_total} labels name nothing. "
              f"Each one silently removes its pins from the exported netlist.")
        print("  Move the label ONTO the wire (same x for a vertical, same y "
              "for a horizontal).")
        print("=" * 72)
        return 1
    print(f"  PASS — all {grand_total} labels lie on a wire or a junction")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
