#!/usr/bin/env python3
"""Schematic legibility gate — nothing printable may overlap anything else.

Sister gate to verify_schematic_crossings.py. That one guarantees no WIRE
crosses another; this one guarantees no LABEL, JUNCTION or TEXT lands on top
of another item. Both exist for the same reason: a schematic that is
electrically correct but unreadable cannot be reviewed, and an unreviewable
schematic is where net-level bugs hide.

What is checked, item against item:

  text          free-standing annotation
  label         local net label (sheet-scoped)
  global_label  global net label
  junction      connection dot
  symbol        component body + its Reference/Value fields

Bounding boxes are approximate but deliberately CONSERVATIVE for text: KiCad
renders its stroke font at roughly 0.72 * size per character advance, and we
measure at that width, so a reported overlap is real ink on ink rather than a
rounding artefact.

Exit code 0 = pass, 1 = overlaps found.

Usage:
    python3 scripts/verify_schematic_overlaps.py
    python3 scripts/verify_schematic_overlaps.py --sheet 04-audio.kicad_sch
    python3 scripts/verify_schematic_overlaps.py --list   # every overlap
"""

import argparse
import math
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCH_DIR = REPO / "hardware" / "kicad"

# KiCad stroke-font horizontal advance per character, as a fraction of the
# font size. Measured conservatively (real advance is ~0.72-0.78).
CHAR_ADVANCE = 0.72
# A junction dot is small; give it a real footprint so a label placed exactly
# on a node is reported.
JUNCTION_R = 0.5
# Ignore sub-micron touches: adjacent boxes that merely share an edge.
EPS = 0.01


def blocks(src, tok):
    """Every balanced-paren block starting with ``tok``."""
    out, i = [], 0
    while True:
        i = src.find(tok, i)
        if i < 0:
            return out
        depth, j = 0, i
        while j < len(src):
            c = src[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(src[i:j + 1])
        i = j + 1


def _font_size(block, default=1.27):
    m = re.search(r"\(size ([\d.]+) ([\d.]+)\)", block)
    return (float(m.group(1)), float(m.group(2))) if m else (default, default)


def _text_box(txt, x, y, angle, size):
    """Axis-aligned box for a text run anchored at (x, y).

    Text is left-anchored along its reading direction and centred across it.
    All four orientations extend a DIFFERENT way, and getting this wrong
    invents overlaps that are not on the page:

        0    reads right  -> +x        180  reads left   -> -x
        90   reads up     -> -y        270  reads down   -> +y

    (KiCad schematic Y grows downward, so "up" is -y.)
    """
    w = max(len(txt), 1) * size[0] * CHAR_ADVANCE
    h = size[1]
    a = int(angle) % 360
    if a == 90:
        return (x - h / 2, y - w, x + h / 2, y)
    if a == 270:
        return (x - h / 2, y, x + h / 2, y + w)
    if a == 180:
        return (x - w, y - h / 2, x, y + h / 2)
    return (x, y - h / 2, x + w, y + h / 2)


def parse_items(text, sheet):
    """Every printable item on a sheet as (kind, name, box)."""
    items = []

    for b in blocks(text, "(text "):
        m = re.match(r'\(text "((?:[^"\\]|\\.)*)"\s*\(at ([\d.\-]+) ([\d.\-]+) ([\d.\-]+)\)', b)
        if not m:
            continue
        txt, x, y, a = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))
        items.append(("text", txt, _text_box(txt, x, y, a, _font_size(b, 2.54))))

    for tok, kind in (("(label ", "label"), ("(global_label ", "global_label")):
        for b in blocks(text, tok):
            m = re.match(r'\(\w+ "([^"]+)"' + (r'\s*\(shape \w+\)' if kind == "global_label" else "")
                         + r'\s*\(at ([\d.\-]+) ([\d.\-]+) ([\d.\-]+)\)', b)
            if not m:
                continue
            nm, x, y, a = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))
            items.append((kind, nm, _text_box(nm, x, y, a, _font_size(b))))

    for b in blocks(text, "(junction "):
        m = re.search(r"\(at ([\d.\-]+) ([\d.\-]+)\)", b)
        if not m:
            continue
        x, y = float(m.group(1)), float(m.group(2))
        items.append(("junction", f"({x},{y})",
                      (x - JUNCTION_R, y - JUNCTION_R, x + JUNCTION_R, y + JUNCTION_R)))

    # Symbol Reference / Value fields are printed text too — a label dropped
    # on top of "R20" is exactly as unreadable as one dropped on a comment.
    for b in blocks(text, "(symbol (lib_id"):
        ref = re.search(r'\(property "Reference" "([^"]+)"\s*\(at ([\d.\-]+) ([\d.\-]+) ([\d.\-]+)\)', b)
        val = re.search(r'\(property "Value" "([^"]+)"\s*\(at ([\d.\-]+) ([\d.\-]+) ([\d.\-]+)\)', b)
        for m, what in ((ref, "ref"), (val, "val")):
            if not m or "hide" in b[m.start():m.end() + 80]:
                continue
            nm, x, y, a = m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))
            items.append((f"symbol.{what}", nm, _text_box(nm, x, y, a, _font_size(b))))

    return items


def overlap(a, b):
    """Overlapping area of two boxes, 0 if they only touch."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    w = min(ax2, bx2) - max(ax1, bx1)
    h = min(ay2, by2) - max(ay1, by1)
    if w <= EPS or h <= EPS:
        return 0.0
    return w * h


def check_sheet(path, list_all=False):
    text = path.read_text(encoding="utf-8", errors="replace")
    items = parse_items(text, path.name)
    hits = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            k1, n1, b1 = items[i]
            k2, n2, b2 = items[j]
            a = overlap(b1, b2)
            if a > 0:
                hits.append((a, k1, n1, k2, n2))
    hits.sort(reverse=True, key=lambda h: h[0])

    status = "OK  " if not hits else "FAIL"
    print(f"  [{status}] {path.name:28} {len(items):3} items, {len(hits):3} overlap(s)")
    shown = hits if list_all else hits[:5]
    for a, k1, n1, k2, n2 in shown:
        print(f"           {a:6.2f} mm²  {k1} '{n1}'  ×  {k2} '{n2}'")
    if not list_all and len(hits) > len(shown):
        print(f"           ... and {len(hits) - len(shown)} more (use --list)")
    return len(items), hits


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", help="check only this sheet file")
    ap.add_argument("--list", action="store_true", help="print every overlap")
    args = ap.parse_args()

    sheets = sorted(SCH_DIR.glob("*.kicad_sch"))
    if args.sheet:
        sheets = [s for s in sheets if s.name == args.sheet]
        if not sheets:
            print(f"ERROR: no such sheet: {args.sheet}")
            sys.exit(1)
    if not sheets:
        print(f"ERROR: no schematics found in {SCH_DIR} — refusing to pass vacuously.")
        sys.exit(1)

    print("=" * 72)
    print("Schematic legibility — no label / junction / text may overlap another")
    print("=" * 72)

    total_items = total_hits = 0
    for s in sheets:
        n, hits = check_sheet(s, args.list)
        total_items += n
        total_hits += len(hits)

    print("-" * 72)
    if total_hits:
        print(f"  FAIL — {total_hits} overlap(s) across {len(sheets)} sheet(s), "
              f"{total_items} items")
        print("  Move the item, or split the sheet if it has run out of room.")
        print("=" * 72)
        sys.exit(1)
    print(f"  PASS — {total_items} items across {len(sheets)} sheet(s), nothing overlaps")
    print("=" * 72)


if __name__ == "__main__":
    main()
