#!/usr/bin/env python3
"""Component BODY collision + board-edge gate (JLC SMT DFM classes).

Born from the 2026-08-03 JLCDFM report: "Component collision 0mm" and
"Component spacing 0mm" DANGERs (F1's 1812 body sat 0.43mm inside J3's
connector housing) plus 3 "clipped by board outline" warnings. Nothing
in the suite modeled a component BODY: collision.py knows segments,
vias, pads, slots and edges; the board file carries no courtyards
(missing_courtyard is ignored in the .kicad_pro), so KiCad's courtyard
DRC structurally cannot fire; and verify_dfa's edge check uses the CPL
centroid only.

Bodies are reconstructed exactly the way JLC's own SMT DFM sees them:
each part's EasyEDA/JLC reference footprint (scripts/.easyeda_cache/,
keyed by the BOM's LCSC number) is rigid-fitted (rot x mirror) onto our
absolute pad positions and its outline pushed through the transform.
No network access — the cache ships in the repo.

Checks (no allowlist for collisions — a hit is fixed by moving a part):
  1. Same-side body-to-body clearance >= MIN_BODY_CLR.
  2. Bodies stay inside the board outline — except the declared
     EDGE_MOUNT parts, which MUST overhang by design (USB-C receptacle
     mouth, microSD card mouth, power-switch actuator); for those the
     gate instead requires every copper pad to stay fully on the board.
"""
import csv
import math
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PCB = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"
BOM = BASE / "hardware" / "kicad" / "jlcpcb" / "bom.csv"
CACHE = BASE / "scripts" / ".easyeda_cache"

MIN_BODY_CLR = 0.25   # mm between same-side bodies (board's tightest
                      # legitimate pair, C27/U2, sits at 0.43)
FIT_ERR_MAX = 0.50    # mm — reject a reference fit worse than this.
                      # 0.5 keeps parts whose land pattern differs
                      # slightly from JLC's (F1: 0.35) while rejecting
                      # fits that landed on the wrong pads entirely.
BOARD_W, BOARD_H = 160.0, 75.0

# Edge-mount parts whose body must overhang the outline (design intent,
# not a defect): value = why. Their pads are still required on-board.
EDGE_MOUNT = {
    "J1": "USB-C receptacle — plug mouth must protrude past the edge",
    "U6": "TF-01A microSD holder — card mouth must protrude past the edge",
    "SW16": "MSK12C02 slide switch — actuator must reach the enclosure wall",
}

failures = []
passes = []


def check(name, ok, detail=""):
    if ok:
        passes.append(name)
        print(f"  PASS  {name}")
    else:
        failures.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def sexp_blocks(s, tag):
    out = []
    for m in re.finditer(r"\(" + tag + r"[\s\"]", s):
        i = m.start()
        depth = 0
        j = i
        instr = False
        while j < len(s):
            c = s[j]
            if instr:
                if c == '"' and s[j - 1] != "\\":
                    instr = False
            else:
                if c == '"':
                    instr = True
                elif c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        out.append((i, j + 1))
                        break
            j += 1
    return out


def parse_board():
    src = PCB.read_text()
    fps = []
    for a, b in sexp_blocks(src, "footprint"):
        blk = src[a:b]
        mlayer = re.search(r'\(layer\s+"([^"]+)"\)', blk)
        mat = re.search(r"\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\s*\)", blk)
        mref = re.search(r'\(property\s+"Reference"\s+"([^"]*)"', blk)
        if not mat:
            continue
        fp = dict(
            ref=mref.group(1) if mref else "",
            layer=mlayer.group(1) if mlayer else "?",
            x=float(mat.group(1)), y=float(mat.group(2)),
            rot=float(mat.group(3)) if mat.group(3) else 0.0,
            pads=[],
        )
        for pa, pb in sexp_blocks(blk, "pad"):
            p = blk[pa:pb]
            mp = re.match(r'\(pad\s+"([^"]*)"\s+(\S+)\s+(\S+)', p)
            mpat = re.search(r"\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\s*\)", p)
            msz = re.search(r"\(size\s+([-\d.]+)\s+([-\d.]+)\)", p)
            if not (mp and mpat and msz):
                continue
            a_ = math.radians(fp["rot"])
            lx, ly = float(mpat.group(1)), float(mpat.group(2))
            ca, sa = math.cos(a_), math.sin(a_)
            X = fp["x"] + lx * ca + ly * sa
            Y = fp["y"] - lx * sa + ly * ca
            prot = float(mpat.group(3)) if mpat.group(3) else 0.0
            w, h = float(msz.group(1)), float(msz.group(2))
            if abs((fp["rot"] + prot) % 180 - 90) < 1e-6:
                w, h = h, w
            fp["pads"].append(dict(num=mp.group(1), type=mp.group(2),
                                   X=X, Y=Y, W=w, H=h))
        fps.append(fp)
    return fps


PAD_RE = re.compile(
    r'\(pad\s+"?([^"\s]*)"?\s+\S+\s+\S+\s*'
    r"\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\s*\)\s*"
    r"\(size\s+([-\d.]+)\s+([-\d.]+)\)")
LINE_RE = re.compile(
    r"\(fp_(?:line|rect)\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+"
    r"\(end\s+([-\d.]+)\s+([-\d.]+)\)\s+\(layer\s+(\S+)\)")


def load_ref_outline(lcsc):
    """Reference pad centres (all occurrences) + body box.

    Body box preference: CrtYd (JLC's own body/courtyard model — what
    their SMT DFM compares against), falling back to the SilkS/Fab
    bounding box for the few refs without a courtyard.
    """
    mods = list((CACHE / lcsc).glob("**/*.kicad_mod"))
    if not mods:
        return None, None, None
    txt = mods[0].read_text()
    pads = [(float(m.group(2)), float(m.group(3)))
            for m in PAD_RE.finditer(txt)]
    named = {}
    for m in PAD_RE.finditer(txt):
        named.setdefault(m.group(1), (float(m.group(2)), float(m.group(3))))

    def box(pred):
        pts = []
        for m in LINE_RE.finditer(txt):
            if not pred(m.group(5)):
                continue
            pts += [(float(m.group(1)), float(m.group(2))),
                    (float(m.group(3)), float(m.group(4)))]
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    crt = box(lambda L: "CrtYd" in L)
    silk = box(lambda L: "SilkS" in L or "Fab" in L)
    return pads, named, (crt or silk)


def xform(p, rot, mirror):
    x, y = p
    if mirror:
        x = -x
    a = math.radians(rot)
    c, s = math.cos(a), math.sin(a)
    return (x * c - y * s, x * s + y * c)


def fit_bodies(fps):
    ref2lcsc = {}
    with open(BOM) as f:
        for row in csv.DictReader(f):
            lcsc = (row.get("LCSC Part #") or row.get("LCSC") or "").strip()
            for d in row["Designator"].replace('"', "").split(","):
                ref2lcsc[d.strip()] = lcsc
    bodies = {}
    unfit = []
    for fp in fps:
        lcsc = ref2lcsc.get(fp["ref"])
        if not lcsc:
            continue
        ref_data = load_ref_outline(lcsc)
        if ref_data is None or not ref_data[0] or ref_data[2] is None:
            unfit.append((fp["ref"], lcsc, "no cached outline"))
            continue
        rpads, rnamed, rbox = ref_data
        ours = [(p["X"], p["Y"]) for p in fp["pads"]
                if p["type"] != "np_thru_hole"]
        ours_named = {p["num"]: (p["X"], p["Y"]) for p in fp["pads"]
                      if p["type"] != "np_thru_hole"}
        if len(ours) < 2 or len(rpads) < 2:
            unfit.append((fp["ref"], lcsc, "fewer than 2 pads to fit"))
            continue
        # Two fit strategies, best wins:
        #  a) name-keyed — exact when pad numbering agrees;
        #  b) name-free centroid + symmetric nearest-neighbour error —
        #     survives duplicate/renamed pad numbers (J3 mech tabs).
        best = None
        common = [n for n in rnamed if n in ours_named]
        for rot in (0, 90, 180, 270):
            for mirror in (False, True):
                if len(common) >= 2:
                    tp = [xform(rnamed[n], rot, mirror) for n in common]
                    dx = sum(ours_named[n][0] - t[0]
                             for n, t in zip(common, tp)) / len(common)
                    dy = sum(ours_named[n][1] - t[1]
                             for n, t in zip(common, tp)) / len(common)
                    err = max(math.hypot(ours_named[n][0] - t[0] - dx,
                                         ours_named[n][1] - t[1] - dy)
                              for n, t in zip(common, tp))
                    if best is None or err < best[0]:
                        best = (err, rot, mirror, dx, dy)
                tp = [xform(p, rot, mirror) for p in rpads]
                tcx = sum(p[0] for p in tp) / len(tp)
                tcy = sum(p[1] for p in tp) / len(tp)
                ocx = sum(p[0] for p in ours) / len(ours)
                ocy = sum(p[1] for p in ours) / len(ours)
                dx, dy = ocx - tcx, ocy - tcy
                moved = [(x + dx, y + dy) for x, y in tp]
                err = max(
                    max(min(math.hypot(mx - ox, my - oy) for ox, oy in ours)
                        for mx, my in moved),
                    max(min(math.hypot(mx - ox, my - oy) for mx, my in moved)
                        for ox, oy in ours),
                )
                if best is None or err < best[0]:
                    best = (err, rot, mirror, dx, dy)
        err, rot, mirror, dx, dy = best
        if err > FIT_ERR_MAX:
            unfit.append((fp["ref"], lcsc, f"fit error {err:.2f}mm"))
            continue
        x0, y0, x1, y1 = rbox
        cs = [xform(c, rot, mirror)
              for c in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
        bodies[fp["ref"]] = dict(
            layer=fp["layer"],
            box=(min(c[0] for c in cs) + dx, min(c[1] for c in cs) + dy,
                 max(c[0] for c in cs) + dx, max(c[1] for c in cs) + dy),
            fp=fp)
    return bodies, unfit


def box_gap(a, b):
    dx = max(a[0] - b[2], b[0] - a[2], 0.0)
    dy = max(a[1] - b[3], b[1] - a[3], 0.0)
    if dx == 0 and dy == 0:
        return -min(min(a[2], b[2]) - max(a[0], b[0]),
                    min(a[3], b[3]) - max(a[1], b[1]))
    return math.hypot(dx, dy)


def main():
    print("=" * 68)
    print("COMPONENT BODY COLLISION + BOARD EDGE (JLC SMT DFM classes)")
    print("=" * 68)
    fps = parse_board()
    bodies, unfit = fit_bodies(fps)
    print(f"\n{len(bodies)} bodies fitted from the JLC reference cache; "
          f"{len(unfit)} parts without a usable reference:")
    for ref, lcsc, why in unfit:
        print(f"        skip {ref} ({lcsc}): {why}")

    # 1. pairwise same-side clearance
    refs = sorted(bodies)
    hits = []
    for i, r1 in enumerate(refs):
        for r2 in refs[i + 1:]:
            b1, b2 = bodies[r1], bodies[r2]
            if b1["layer"] != b2["layer"]:
                continue
            gap = box_gap(b1["box"], b2["box"])
            if gap < MIN_BODY_CLR:
                hits.append((r1, r2, gap, b1["layer"]))
    detail = "; ".join(f"{a}/{b} {g:.3f}mm ({l})" for a, b, g, l in
                       sorted(hits, key=lambda h: h[2])[:6])
    check(f"body-to-body clearance >= {MIN_BODY_CLR}mm (same side)",
          not hits, f"{len(hits)} pairs: {detail}")

    # 2. board edge — bodies from the fit; edge-mount pad containment
    #    from OUR footprints directly (needs no reference fit).
    edge_bad = []
    for ref, b in bodies.items():
        if ref in EDGE_MOUNT:
            continue
        x0, y0, x1, y1 = b["box"]
        overhang = max(0 - x0, 0 - y0, x1 - BOARD_W, y1 - BOARD_H)
        if overhang > 0:
            edge_bad.append((ref, overhang))
    check("non-edge-mount bodies fully inside the outline", not edge_bad,
          "; ".join(f"{r} overhangs {o:.2f}mm" for r, o in edge_bad))

    pad_off = []
    seen_edge_mount = set()
    for fp in fps:
        if fp["ref"] not in EDGE_MOUNT:
            continue
        seen_edge_mount.add(fp["ref"])
        for p in fp["pads"]:
            if p["type"] == "np_thru_hole":
                continue
            if (p["X"] - p["W"] / 2 < 0 or p["Y"] - p["H"] / 2 < 0
                    or p["X"] + p["W"] / 2 > BOARD_W
                    or p["Y"] + p["H"] / 2 > BOARD_H):
                pad_off.append((fp["ref"], p["num"]))
    check("edge-mount parts (declared design intent) keep all pads on-board",
          not pad_off, "; ".join(f"{r}.{n}" for r, n in pad_off))
    check("every declared edge-mount ref exists on the board",
          seen_edge_mount == set(EDGE_MOUNT),
          f"missing: {sorted(set(EDGE_MOUNT) - seen_edge_mount)}")
    for ref, why in sorted(EDGE_MOUNT.items()):
        if ref in bodies:
            x0, y0, x1, y1 = bodies[ref]["box"]
            over = max(0 - x0, 0 - y0, x1 - BOARD_W, y1 - BOARD_H)
            print(f"        edge-mount {ref}: overhang {over:.2f}mm — {why}")

    print("\n" + "=" * 68)
    print(f"Results: {len(passes)} passed, {len(failures)} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
