#!/usr/bin/env python3
"""Fail when two schematic wires cross without being connected.

A wire that passes over another wire is ambiguous to a human reader: at a
glance there is no way to tell a crossing from a connection, and the reader
has to hunt for the junction dot to find out. KiCad will not complain -- the
netlist is fine either way -- so nothing catches it except reading the sheet.

The remedy is not to reroute the wire but to stop drawing it: connect the two
points with a NET LABEL at each end instead (`SheetBase.link()`). A labelled
connection cannot cross anything, and it scales -- a sheet with 40 signals
stays readable, while 40 routed wires do not.

What counts as a crossing:
  * two wire segments that intersect at a point, AND
  * that point is not an endpoint of either segment (a shared endpoint is a
    corner or a T, which is a real connection), AND
  * there is no junction at that point (a junction dot IS a real connection)

Exit 0 when every sheet is clean, 1 otherwise.

Usage:
    python3 scripts/verify_schematic_crossings.py
    python3 scripts/verify_schematic_crossings.py --verbose
"""

from __future__ import annotations

import glob
import math
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SHEETS = str(BASE / "hardware" / "kicad" / "0*.kicad_sch")

EPS = 1e-9
# Snap coordinates before comparing: KiCad writes them at 0.01 mm precision
# and float arithmetic on the intersection must land on the same grid.
ROUND = 2
# How far from a wire end a label may sit and still be considered its name.
LABEL_RADIUS_MM = 15.0

_WIRE_RE = re.compile(
    r"\(wire\s*\(pts\s*\(xy ([-\d.]+) ([-\d.]+)\)\s*\(xy ([-\d.]+) ([-\d.]+)\)"
)
_JUNCTION_RE = re.compile(r"\(junction\s*\(at ([-\d.]+) ([-\d.]+)\)")
_LABEL_RE = re.compile(
    r'\((?:global_|hierarchical_)?label "([^"]+)"\s*\(at ([-\d.]+) ([-\d.]+)'
)


def _intersection(a: tuple, b: tuple) -> tuple | None:
    """Point where segments a and b cross, or None if they do not."""
    x1, y1, x2, y2 = a
    x3, y3, x4, y4 = b
    denom = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(denom) < EPS:
        return None  # parallel or collinear
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / denom
    u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / denom
    if not (-EPS <= t <= 1 + EPS and -EPS <= u <= 1 + EPS):
        return None
    return (round(x1 + t * (x2 - x1), ROUND), round(y1 + t * (y2 - y1), ROUND))


def _analyse(path: Path) -> list[dict]:
    text = path.read_text(errors="replace")
    wires = [tuple(float(m.group(i)) for i in (1, 2, 3, 4))
             for m in _WIRE_RE.finditer(text)]
    junctions = {
        (round(float(m.group(1)), ROUND), round(float(m.group(2)), ROUND))
        for m in _JUNCTION_RE.finditer(text)
    }
    labels = [(m.group(1), float(m.group(2)), float(m.group(3)))
              for m in _LABEL_RE.finditer(text)]

    def nearest_label(x: float, y: float) -> str:
        near = [(math.hypot(lx - x, ly - y), n) for n, lx, ly in labels]
        near = [t for t in near if t[0] < LABEL_RADIUS_MM]
        return min(near)[1] if near else "?"

    found = []
    for i in range(len(wires)):
        for k in range(i + 1, len(wires)):
            point = _intersection(wires[i], wires[k])
            if point is None:
                continue
            ends = {
                (round(w[j], ROUND), round(w[j + 1], ROUND))
                for w in (wires[i], wires[k]) for j in (0, 2)
            }
            if point in ends or point in junctions:
                continue
            found.append({
                "at": point,
                "a": wires[i], "b": wires[k],
                "a_net": nearest_label(wires[i][0], wires[i][1]),
                "b_net": nearest_label(wires[k][0], wires[k][1]),
            })
    return found


def main(argv: list[str]) -> int:
    verbose = "--verbose" in argv or "-v" in argv
    sheets = sorted(glob.glob(SHEETS))
    if not sheets:
        print(f"ERROR: no sheets matched {SHEETS}")
        return 1

    total = 0
    print("=" * 70)
    print("  SCHEMATIC WIRE CROSSINGS — a crossing must be a label, not a wire")
    print("=" * 70)
    for s in sheets:
        path = Path(s)
        hits = _analyse(path)
        total += len(hits)
        mark = "OK  " if not hits else "FAIL"
        print(f"  [{mark}] {path.name:<28} {len(hits)} crossing(s)")
        for h in hits if (hits and (verbose or True)) else []:
            ax, ay, ax2, ay2 = h["a"]
            bx, by, bx2, by2 = h["b"]
            print(f"          at ({h['at'][0]:.2f}, {h['at'][1]:.2f})")
            print(f"            ({ax:.2f},{ay:.2f})->({ax2:.2f},{ay2:.2f})"
                  f"  near '{h['a_net']}'")
            print(f"            ({bx:.2f},{by:.2f})->({bx2:.2f},{by2:.2f})"
                  f"  near '{h['b_net']}'")
    print("-" * 70)
    if total:
        print(f"  {total} crossing(s). Replace the offending wire with a "
              f"labelled link:")
        print(f"      self.link(\"NET_NAME\", x, y, angle)   "
              f"# scripts/generate_schematics/sheet_base.py")
        print(f"  A label at each end connects the same net with nothing "
              f"drawn in between.")
        return 1
    print("  No wire crosses another. Every connection is a corner, a "
          "junction, or a label.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
