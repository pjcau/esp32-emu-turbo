#!/usr/bin/env python3
"""Schematic legibility gate #2 — no two RENDERED text runs may overlap.

Sister of verify_schematic_overlaps.py, which re-derives KiCad's layout
rules from the .kicad_sch and therefore carries a model of them. That model
missed a whole family of real overlaps for months (pin-number digits under
net labels, field justification mirroring on 180-degree symbols, global
label outlines) because KiCad's actual layout is subtler than any
re-derivation. This gate closes the loop from the other side: it asks
kicad-cli to RENDER each sheet to SVG and reads back the exact geometry of
every text run KiCad drew — anchor, length, font size, rotation. If two
boxes intersect on the rendered page, a reader cannot read them, whatever
any model says.

Ground truth: KiCad's SVG export writes, for every visible text run, an
invisible <text> element (opacity 0) carrying x/y/textLength/font-size/
text-anchor plus an optional rotate() transform, immediately followed by
the stroked glyphs. Those attributes ARE the rendered geometry.

The export occasionally EMITS A FEW SYMBOLS TWICE (identical geometry,
observed on kicad-cli 10.0.x for the last symbols in a sheet); identical
duplicate boxes are collapsed before pairing so the artifact cannot
self-report.

Requires kicad-cli (the same one every DRC/netlist gate uses). A missing
CLI is a hard FAIL, not a skip — a gate that silently passes when its tool
vanishes is a blind spot (see the linux-box note: the flatpak can
disappear on system cleanup).

Exit 0 = no rendered text overlaps any other; 1 = overlaps or export
failure.

Usage:
    python3 scripts/verify_schematic_render_overlaps.py
    python3 scripts/verify_schematic_render_overlaps.py --sheet 01-power-supply
"""

import argparse
import math
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCH_DIR = REPO / "hardware" / "kicad"

SHEETS = [
    "01-power-supply",
    "02-mcu",
    "03-display",
    "04-audio",
    "05-sd-card",
    "06-controls",
]

# Ignore glancing touches below this area (mm^2). 0.10 is ~a tenth of one
# 1.27 mm character cell — below it two runs merely kiss corners.
MIN_AREA = 0.10

# KiCad stroke font vertical metrics relative to font-size: cap height
# above the baseline, descender below.
ASC, DESC = 0.76, 0.18

TEXT_RE = re.compile(
    r'<text x="([\d.\-]+)" y="([\d.\-]+)"\s*'
    r'(?:transform="rotate\(([\d.\-]+)[^"]*"\s*)?'
    r'textLength="([\d.\-]+)" font-size="([\d.\-]+)"[^>]*'
    r'text-anchor="(\w+)"[^>]*>([^<]*)</text>'
)


def text_boxes(svg: str):
    """[(text, (x1, y1, x2, y2))] for every visible text run, in mm."""
    out = []
    for m in TEXT_RE.finditer(svg):
        x, y = float(m.group(1)), float(m.group(2))
        rot = float(m.group(3)) if m.group(3) else 0.0
        w, fs = float(m.group(4)), float(m.group(5))
        anchor, txt = m.group(6), m.group(7)
        if not txt.strip():
            continue
        if anchor == "middle":
            x1, x2 = x - w / 2, x + w / 2
        elif anchor == "end":
            x1, x2 = x - w, x
        else:
            x1, x2 = x, x + w
        y1, y2 = y - ASC * fs, y + DESC * fs
        if abs(rot % 360.0) > 0.01:
            a = math.radians(rot)
            ca, sa = math.cos(a), math.sin(a)
            corners = [
                (x + (px - x) * ca - (py - y) * sa,
                 y + (px - x) * sa + (py - y) * ca)
                for px in (x1, x2) for py in (y1, y2)
            ]
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            box = (min(xs), min(ys), max(xs), max(ys))
        else:
            box = (x1, y1, x2, y2)
        out.append((txt, box))
    return out


def dedup(boxes):
    """Collapse the exporter's duplicate-emission artifact."""
    seen, out = set(), []
    for t, b in boxes:
        key = (t, round(b[0], 2), round(b[1], 2))
        if key in seen:
            continue
        seen.add(key)
        out.append((t, b))
    return out


def overlap_area(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if (w > 0.02 and h > 0.02) else 0.0


def export_svgs(sheets, outdir: Path):
    cli = shutil.which("kicad-cli")
    if not cli:
        print("FAIL: kicad-cli not found on PATH — this gate renders the")
        print("schematics with the same CLI the DRC/netlist gates use.")
        print("(flatpak KiCad + ~/.local/bin shim on this box; reinstall")
        print("user-level if a system cleanup removed it.)")
        return False
    ok = True
    for sheet in sheets:
        src = SCH_DIR / f"{sheet}.kicad_sch"
        r = subprocess.run(
            [cli, "sch", "export", "svg", "--exclude-drawing-sheet",
             "-o", str(outdir), str(src)],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0 or not (outdir / f"{sheet}.svg").exists():
            print(f"FAIL: kicad-cli svg export failed for {sheet}:")
            print((r.stderr or r.stdout).strip()[:500])
            ok = False
    return ok


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", help="check only this sheet (basename)")
    args = ap.parse_args()

    sheets = [s for s in SHEETS
              if not args.sheet or s == args.sheet.removesuffix(".kicad_sch")]
    if not sheets:
        print(f"ERROR: no such sheet: {args.sheet}")
        sys.exit(2)
    missing = [s for s in sheets if not (SCH_DIR / f"{s}.kicad_sch").exists()]
    if missing:
        print(f"FAIL: missing schematics: {missing} — refusing to pass "
              f"vacuously.")
        sys.exit(1)

    print("=" * 72)
    print("Schematic legibility (rendered) — no two DRAWN text runs overlap")
    print("=" * 72)

    total = 0
    with tempfile.TemporaryDirectory(prefix="sch-render-gate.") as td:
        outdir = Path(td)
        if not export_svgs(sheets, outdir):
            sys.exit(1)
        for sheet in sheets:
            svg = (outdir / f"{sheet}.svg").read_text(
                encoding="utf-8", errors="replace")
            boxes = dedup(text_boxes(svg))
            hits = []
            for i in range(len(boxes)):
                for j in range(i + 1, len(boxes)):
                    a = overlap_area(boxes[i][1], boxes[j][1])
                    if a >= MIN_AREA:
                        hits.append((a, boxes[i], boxes[j]))
            hits.sort(reverse=True, key=lambda h: h[0])
            status = "OK  " if not hits else "FAIL"
            print(f"  [{status}] {sheet + '.kicad_sch':28} "
                  f"{len(boxes):3} text runs, {len(hits):3} overlap(s)")
            for a, (t1, b1), (t2, _b2) in hits:
                cx = (b1[0] + b1[2]) / 2
                cy = (b1[1] + b1[3]) / 2
                print(f"           {a:6.2f} mm²  at ({cx:.1f}, {cy:.1f})  "
                      f"'{t1}' × '{t2}'")
            total += len(hits)

    print("-" * 72)
    if total:
        print(f"  FAIL — {total} rendered overlap(s). Fix the sheet "
              f"generator (scripts/generate_schematics/), not the output.")
        print("=" * 72)
        sys.exit(1)
    print(f"  PASS — {len(sheets)} sheet(s) rendered, no text run overlaps "
          f"another")
    print("=" * 72)


if __name__ == "__main__":
    main()
