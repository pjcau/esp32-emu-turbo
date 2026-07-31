#!/usr/bin/env python3
"""Gerber-level electrical test — opens and shorts from the SHIPPED artifacts.

Why this gate exists
--------------------
Every other connectivity check in this repo reads the `.kicad_pcb` — either
through our own parser (`pcb_cache`, `verify_net_connectivity`,
`verify_power_net_integrity`) or through KiCad itself
(`verify_netlist_vs_kicad`, DRC). They all judge the *design model*. None of
them reads the copper JLCPCB actually fabricates: the gerbers.

If gerber export is broken, stale, or the zone fill misbehaves (the
concurrent-fill bug silently doubled every zone's copper), every model-side
gate stays green while the shipped board is wrong. This script closes that
gap by doing what the fab's flying-probe e-test does, before ordering:

    1. rasterize the four copper gerbers,
    2. connect layers through the plated holes in the drill file,
    3. locate every pad and via from the IPC-D-356 e-test netlist,
    4. assert  OPENS:  each net is ONE piece of copper,
               SHORTS: no piece of copper carries two nets.

All three inputs (gerbers, drill, .d356) come from `release_jlcpcb/` — the
directory that goes to the fab — so this also catches the "release dir is
stale while gates are green" failure class. It already has: on its first run
it found `release_jlcpcb/esp32-emu-turbo.d356` still describing the AMS1117
board (U3 as SOT-223, the deleted C2) while the gerbers had the SY8089A.

Validated against a known-bad fixture: the v4.3.1 release gerbers (the
fabricated prototype #1) FAIL with +3V3 in 4 pieces and VBUS in 3 — the
dead board, seen from the copper the fab actually etched. HEAD passes.
`scripts/test_gerber_etest.py` mutation-tests both directions.

Usage:
    python3 scripts/verify_gerber_etest.py
    python3 scripts/verify_gerber_etest.py --gerbers DIR --d356 FILE [--dpmm 40]

Exit codes: 0 PASS · 1 opens/shorts found · 2 structural error (inputs
unreadable, coordinate mapping broken, suspiciously empty netlist — never
silently skipped).
"""

from __future__ import annotations

import argparse
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent
DEF_GERBERS = BASE / "release_jlcpcb" / "gerbers"
DEF_D356 = BASE / "release_jlcpcb" / "esp32-emu-turbo.d356"

COPPER_SUFFIXES = [  # outer → inner → outer, index = layer id
    ("F.Cu", "-F_Cu.gtl"),
    ("In1.Cu", "-In1_Cu.g1"),
    ("In2.Cu", "-In2_Cu.g2"),
    ("B.Cu", "-B_Cu.gbl"),
]
IN_TO_MM = 25.4 / 10000.0  # d356 CUST 0 units: 1/10000 inch

# margin added to a hole/pad radius when sampling copper labels: reaches the
# annular ring without jumping the 0.1 mm minimum clearance to foreign copper
SAMPLE_MARGIN_MM = 0.05


class Fatal(RuntimeError):
    """Structural error — the verdict would be meaningless, refuse to guess."""


# ---------------------------------------------------------------- d356 parse

D356_RE = re.compile(
    r"^(317|327)(?P<net>.{14})(?P<ref>.{6})"  # record type, net, refdes
    r".*?"
    r"(?:D(?P<drill>\d{4})(?P<plating>[PN]))?"  # 317 only: drill dia + plating
    r"A(?P<access>\d{2})"
    r"X(?P<x>[+-]\d+)Y(?P<y>[+-]\d+)"
)


def parse_d356(path: Path):
    """Return e-test records: dicts with net, ref, x/y in mm, access, drill."""
    records = []
    for line in path.read_text().splitlines():
        if not line.startswith(("317", "327")):
            continue
        m = D356_RE.match(line)
        if not m:
            raise Fatal(f"unparseable d356 record: {line!r}")
        net = m.group("net").strip()
        if net in ("", "N/C"):
            continue  # intentionally unconnected (fiducials, punch-outs)
        drill = m.group("drill")
        records.append(
            {
                "net": net,
                "ref": m.group("ref").strip(),
                "x": int(m.group("x")) * IN_TO_MM,
                "y": int(m.group("y")) * IN_TO_MM,
                "access": m.group("access"),  # 00 through, else layer number
                "drill": (int(drill) * IN_TO_MM) if drill else None,
                "plated": m.group("plating") == "P" if drill else False,
            }
        )
    if len(records) < 100:
        raise Fatal(
            f"only {len(records)} e-test records in {path.name} — the board "
            "has hundreds of pads; the netlist export is broken or truncated"
        )
    return records


# --------------------------------------------------------------- drill parse

def parse_drill(path: Path):
    """Return plated hole positions [(x, y, dia_mm)]; G85 slots contribute
    both endpoints (the plated slot connects layers along its full length)."""
    holes = []
    tools: dict[str, float] = {}
    plated_tools: set[str] = set()
    pending_plated = None
    current: str | None = None
    header = True
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line.startswith("; #@! TA.AperFunction"):
            pending_plated = "NonPlated" not in line
            continue
        tm = re.match(r"^T(\d+)C([\d.]+)", line)
        if tm:
            tools[tm.group(1)] = float(tm.group(2))
            if pending_plated is None or pending_plated:
                plated_tools.add(tm.group(1))
            pending_plated = None
            continue
        if line == "%" or line.startswith("G90") or line.startswith("M95"):
            header = False
            continue
        if header:
            continue
        sm = re.match(r"^T(\d+)$", line)
        if sm:
            current = sm.group(1)
            continue
        cm = re.match(
            r"^X(?P<x>-?[\d.]+)Y(?P<y>-?[\d.]+)"
            r"(?:G85X(?P<x2>-?[\d.]+)Y(?P<y2>-?[\d.]+))?$",
            line,
        )
        if cm and current is not None:
            if current not in plated_tools:
                continue
            dia = tools[current]
            holes.append((float(cm.group("x")), float(cm.group("y")), dia))
            if cm.group("x2") is not None:
                holes.append((float(cm.group("x2")), float(cm.group("y2")), dia))
    if not holes:
        raise Fatal(f"no plated holes parsed from {path.name}")
    return holes


# ------------------------------------------------------------------- raster

def _mono_scheme():
    from pygerber.backend.rasterized_2d.color_scheme import ColorScheme
    from pygerber.common.rgba import RGBA

    black = RGBA(r=0, g=0, b=0, a=255)
    white = RGBA(r=255, g=255, b=255, a=255)
    return ColorScheme(
        background_color=black,
        clear_color=black,
        solid_color=white,
        clear_region_color=black,
        solid_region_color=white,
        debug_1_color=black,
        debug_2_color=black,
    )


def rasterize_layers(gerber_dir: Path, dpmm: int):
    """Render the 4 copper gerbers onto one common canvas.

    Returns (masks, minx_mm, maxy_mm): masks[i] is a bool array, and
    pixel (row, col) covers board point
    (minx + col/dpmm, maxy - row/dpmm)."""
    from PIL import Image
    from pygerber.gerberx3.api.v2 import GerberFile, ImageFormatEnum

    stem = None
    for f in gerber_dir.iterdir():
        if f.name.endswith("-F_Cu.gtl"):
            stem = f.name[: -len("-F_Cu.gtl")]
    if stem is None:
        raise Fatal(f"no *-F_Cu.gtl in {gerber_dir}")

    parsed, boxes = [], []
    for _, suffix in COPPER_SUFFIXES:
        path = gerber_dir / (stem + suffix)
        if not path.exists():
            raise Fatal(f"missing copper gerber {path.name}")
        p = GerberFile.from_file(path).parse()
        info = p.get_info()
        boxes.append(
            (float(info.min_x_mm), float(info.min_y_mm),
             float(info.max_x_mm), float(info.max_y_mm))
        )
        parsed.append(p)

    minx = min(b[0] for b in boxes)
    miny = min(b[1] for b in boxes)
    maxx = max(b[2] for b in boxes)
    maxy = max(b[3] for b in boxes)
    height = int(round((maxy - miny) * dpmm)) + 2
    width = int(round((maxx - minx) * dpmm)) + 2

    scheme = _mono_scheme()
    masks = []
    for p, box in zip(parsed, boxes):
        buf = io.BytesIO()
        p.render_raster(buf, dpmm=dpmm, color_scheme=scheme,
                        image_format=ImageFormatEnum.PNG)
        buf.seek(0)
        img = np.asarray(Image.open(buf).convert("L")) > 127
        canvas = np.zeros((height, width), dtype=bool)
        r0 = int(round((maxy - box[3]) * dpmm))
        c0 = int(round((box[0] - minx) * dpmm))
        h = min(img.shape[0], height - r0)
        w = min(img.shape[1], width - c0)
        canvas[r0 : r0 + h, c0 : c0 + w] = img[:h, :w]
        masks.append(canvas)
    return masks, minx, maxy


# --------------------------------------------------------------- connectivity

class UnionFind:
    def __init__(self):
        self.parent: dict = {}

    def find(self, a):
        p = self.parent.setdefault(a, a)
        if p != a:
            self.parent[a] = p = self.find(p)
        return p

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def labels_near(labelled, minx, maxy, dpmm, x, y, radius_mm):
    """Set of copper labels within radius of board point (x, y) on one layer."""
    row = (maxy - y) * dpmm
    col = (x - minx) * dpmm
    r = max(1, int(np.ceil(radius_mm * dpmm)))
    h, w = labelled.shape
    r0, r1 = max(0, int(row) - r), min(h, int(row) + r + 1)
    c0, c1 = max(0, int(col) - r), min(w, int(col) + r + 1)
    if r0 >= r1 or c0 >= c1:
        return set()
    window = labelled[r0:r1, c0:c1]
    rr, cc = np.ogrid[r0:r1, c0:c1]
    disk = (rr - row) ** 2 + (cc - col) ** 2 <= r * r
    return set(np.unique(window[disk])) - {0}


def analyze(records, holes, masks, minx, maxy, dpmm):
    """Weld layers through plated holes, place every e-test record, and
    return (failures, stats). failures is a list of (headline, detail_lines);
    empty means electrically sound."""
    from scipy import ndimage

    eight = np.ones((3, 3), dtype=int)
    labelled = []
    islands = []
    for m in masks:
        lab, n = ndimage.label(m, structure=eight)
        labelled.append(lab)
        islands.append(n)

    uf = UnionFind()

    # plated holes weld the layers together
    missed_holes = 0
    for x, y, dia in holes:
        touched = []
        for li, lab in enumerate(labelled):
            for lid in labels_near(lab, minx, maxy, dpmm, x, y,
                                   dia / 2 + SAMPLE_MARGIN_MM):
                touched.append((li, int(lid)))
        if not touched:
            missed_holes += 1
            continue
        first = touched[0]
        for t in touched[1:]:
            uf.union(first, t)
    if missed_holes > len(holes) * 0.5:
        raise Fatal(
            f"{missed_holes}/{len(holes)} plated holes landed on bare board — "
            "the drill/gerber coordinate mapping is broken, not the copper"
        )

    # cross-check the two coordinate sources before trusting either: every
    # drilled d356 record must sit on a hole from the drill file. A systematic
    # offset between netlist and gerbers would otherwise place hundreds of
    # points on the wrong copper and report fiction with a straight face.
    drilled = [r for r in records if r["drill"] and r["plated"]]
    if drilled:
        hx = np.array([h[0] for h in holes])
        hy = np.array([h[1] for h in holes])
        unmatched = sum(
            1 for r in drilled
            if np.min((hx - r["x"]) ** 2 + (hy - r["y"]) ** 2) > 0.3**2
        )
        if unmatched > len(drilled) * 0.5:
            raise Fatal(
                f"{unmatched}/{len(drilled)} drilled e-test points have no "
                "matching hole in the drill file — the d356 and the gerbers "
                "describe different boards"
            )

    # locate every e-test record on the welded copper.
    # IPC-D-356 access codes as KiCad writes them are LAYER NUMBERS:
    # A00 = through-hole (all layers), A01 = top, A0<n_layers> = bottom.
    def layers_for(rec):
        if rec["drill"] and rec["plated"]:
            return range(len(labelled))
        acc = int(rec["access"])
        if acc == 0:
            return range(len(labelled))
        return [min(acc - 1, len(labelled) - 1)]

    bare, rec_comp = [], []
    for rec in records:
        radius = (rec["drill"] / 2 if rec["drill"] else 0.15) + SAMPLE_MARGIN_MM
        touched = []
        for li in layers_for(rec):
            # exact centre first: a wider probe near a foreign trace must
            # never win over the record's own pad copper
            for r_mm in (0.03, radius):
                found = labels_near(labelled[li], minx, maxy, dpmm,
                                    rec["x"], rec["y"], r_mm)
                if found:
                    touched.extend((li, int(lid)) for lid in found)
                    break
        if not touched:
            bare.append(rec)
            continue
        first = touched[0]
        if rec["drill"] and rec["plated"]:  # its own barrel welds these too
            for t in touched[1:]:
                uf.union(first, t)
        rec_comp.append((rec, first))
    if len(bare) > len(records) * 0.5:
        raise Fatal(
            f"{len(bare)}/{len(records)} e-test points landed on bare board — "
            "the d356/gerber coordinate mapping is broken, not the copper"
        )

    # verdicts — component ids canonicalized only after ALL unions are done
    net_comps: dict[str, dict] = defaultdict(dict)
    comp_nets: dict = defaultdict(dict)
    for rec, comp in rec_comp:
        comp = uf.find(comp)
        net_comps[rec["net"]].setdefault(comp, []).append(rec)
        comp_nets[comp].setdefault(rec["net"], rec)

    failures = []
    for net in sorted(net_comps):
        groups = net_comps[net]
        if len(groups) > 1:
            sizes = sorted((len(v) for v in groups.values()), reverse=True)
            detail = []
            for comp, recs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
                r = recs[0]
                detail.append(
                    f"      group of {len(recs):3d} point(s), e.g. "
                    f"{r['ref'] or 'VIA'} at ({r['x']:.2f}, {r['y']:.2f}) mm"
                )
            failures.append(
                (f"OPEN   {net}: {len(groups)} disconnected copper groups "
                 f"(sizes {sizes})", detail)
            )
    for comp, nets in comp_nets.items():
        if len(nets) > 1:
            detail = [
                f"      {net} e.g. {r['ref'] or 'VIA'} at "
                f"({r['x']:.2f}, {r['y']:.2f}) mm"
                for net, r in sorted(nets.items())
            ]
            failures.append(
                (f"SHORT  one piece of copper carries {len(nets)} nets: "
                 f"{', '.join(sorted(nets))}", detail)
            )
    for rec in bare:
        failures.append(
            (f"BARE   {rec['net']} point {rec['ref'] or 'VIA'} at "
             f"({rec['x']:.2f}, {rec['y']:.2f}) mm has no copper under it", [])
        )

    stats = {
        "records": len(records),
        "nets": len(net_comps),
        "holes": len(holes),
        "islands": islands,
    }
    return failures, stats


def find_drill(gerber_dir: Path) -> Path:
    for f in gerber_dir.iterdir():
        if f.suffix == ".drl" and "NPTH" not in f.name:
            return f
    raise Fatal(f"no .drl drill file in {gerber_dir}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--gerbers", type=Path, default=DEF_GERBERS)
    ap.add_argument("--d356", type=Path, default=DEF_D356)
    ap.add_argument("--dpmm", type=int, default=40,
                    help="raster resolution (default 40 px/mm = 25 µm)")
    args = ap.parse_args()

    print("=" * 72)
    print("GERBER ELECTRICAL TEST — opens & shorts from the shipped artifacts")
    print("=" * 72)
    print(f"  gerbers : {args.gerbers}")
    print(f"  netlist : {args.d356}")

    records = parse_d356(args.d356)
    holes = parse_drill(find_drill(args.gerbers))
    masks, minx, maxy = rasterize_layers(args.gerbers, args.dpmm)
    failures, stats = analyze(records, holes, masks, minx, maxy, args.dpmm)

    for (name, _), n in zip(COPPER_SUFFIXES, stats["islands"]):
        print(f"  {name:<7}: {n} copper islands")
    print(f"  e-test points: {stats['records']} on {stats['nets']} nets, "
          f"{stats['holes']} plated holes")
    print("-" * 72)
    if failures:
        for head, detail in failures:
            print(f"  FAIL {head}")
            for d in detail:
                print(d)
        print("-" * 72)
        print(f"Results: FAIL — {len(failures)} electrical fault(s) in the "
              "shipped gerbers")
        print()
        print("This is what the fab's flying-probe test would report AFTER")
        print("you paid for the boards. Fix the design, regenerate, re-export")
        print("and re-sync release_jlcpcb/ — do NOT edit the gerbers.")
        print("A BARE/mapping error with green model-side gates usually means")
        print("release_jlcpcb/ files are stale relative to each other:")
        print("re-run the release pipeline so gerbers and .d356 are exported")
        print("from the same board.")
        return 1
    print("Results: PASS — every net is one piece of copper, no net touches "
          "another")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fatal as e:
        print(f"STRUCTURAL ERROR: {e}", file=sys.stderr)
        sys.exit(2)
