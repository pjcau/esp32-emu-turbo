#!/usr/bin/env python3
"""The OTHER road: measure the exported STLs, not the scad.

The three enclosure gates read enclosure.scad's constants and trust
OpenSCAD to turn them into geometry. This gate starts from the files that
go to the printer — 3d_case/*.stl (+ hardware/enclosure/reference/) — cuts
them with OpenSCAD `import()` + `projection(cut=true)` at chosen heights,
measures every hole, ring and pocket in the slice, and compares against
sources that are NOT the scad: board.py placements (switches, LEDs, mount
holes, J3), the panel and insert datasheets, the measured cell and the
user's requirements. If a constant, a module or the exporter is wrong,
the numbers here disagree with the design numbers; agreement is the
"does it add up" the user asked for.

Checks (S = STL)
  S0  the viewer shows the print files: each 3d_case/*.stl, moved by
      viewer/placement.json (pure rotation + offset), lands exactly on the
      scad assembly copy in hardware/enclosure/reference/
  S1  shell envelopes: top 170 x 85 x 10.6, bottom 170 x 85 x 18 (with lip)
  S2  front-face cutouts vs board placements: 4 ABXY circles (Ø >= 9),
      D-pad cross (24 x 24, arms >= 6.5), Start/Select/Menu pills, six LED
      light pipes — each centred on its switch/LED within 0.15 mm
  S3  viewport = panel active area + 0.6 (datasheet 83.52 x 55.68), y = 2
  S4  glass pocket (frame walls) = outline 60.88 + 0.6 in Y; equal gaps to
      the Select and Y cap bodies (>= 0.4)
  S5  top bosses at the 4 corner mount holes: socket Ø3.1 (insert OD 3.5
      - 0.4) in the last 4.5 mm (insert L 4.0 + 0.5), relief Ø2.8 above,
      boss Ø7.2 (>= 2 mm wall), front wall closed
  S6  bottom: counterbores Ø5 on the mount holes; columns with a Ø2.8
      bore; contact half-column keeps off SW11/SW12 (x >= 68.55 at Z 15.5)
  S7  battery pocket >= 95 x 50 (measured cell 90 x 50 + 5 leads), not over
      J3 (JST y <= -20.7); strap posts present
  S8  lever face cutouts: >= 1.2 mm floor web to the counterbore
  S9  speaker grille centroid in +X/+Y (top-left seen from the back)
  S10 parts: every cap centred on its switch (viewer STL bbox), height
      7.9; lever nub at SW11/SW12; straps 5 x 1.2 outside the ESP32
      footprint; display part 94.57 x 60.88 x 3.9 with its top at the
      ceiling (Z 24.6)
  S11 thin walls on the STL slices themselves: erode/dilate by 0.6

Exit codes: 0 pass · 1 mismatch · 2 cannot evaluate (Docker, files).
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
OUT_DIR = BASE / "website" / "static" / "img" / "renders"      # docker /output
WORK = OUT_DIR / "_stlcheck"
CASE = BASE / "3d_case"
REF = BASE / "hardware" / "enclosure" / "reference"   # scad assembly copies
PARTS = CASE / "viewer" / "parts"                        # display, pcb

TOL_POS = 0.15
MIN_WALL = 1.2
PANEL_ACTIVE = (83.52, 55.68)       # vendor spec (datasheet image)
PANEL_OUTLINE = (94.57, 60.88, 3.90)
INSERT = (3.5, 4.0)                 # HANGLIFE M2.5 x D3.5 x L4
MEASURED_CELL = (90.0, 50.0, 10.0)


class Structural(RuntimeError):
    pass


# ── geometry helpers ─────────────────────────────────────────────────────

def stl_vertices(path: Path):
    for line in path.read_text().splitlines():
        s = line.strip()
        if s.startswith("vertex"):
            yield tuple(float(v) for v in s.split()[1:4])


def bbox(path: Path):
    xs, ys, zs = zip(*stl_vertices(path))
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def openscad(scad_text: str, out_name: str, **defs) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    scad = WORK / "slice.scad"
    scad.write_text(scad_text)
    out = WORK / out_name
    out.unlink(missing_ok=True)
    cmd = ["docker", "compose", "-f", str(BASE / "docker-compose.yml"), "run",
           "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "openscad",
           "-o", f"/output/_stlcheck/{out_name}"]
    for k, v in defs.items():
        cmd += ["-D", f"{k}={v}"]
    cmd.append("/output/_stlcheck/slice.scad")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Structural(f"cannot run the OpenSCAD container: {e}")
    if r.returncode != 0 or not out.exists():
        raise Structural("OpenSCAD failed:\n" + (r.stderr or r.stdout)[-1500:])
    return out


SLICE_SCAD = """
zc = 0; thin = 0;
module m() { projection(cut=true) translate([0, 0, -zc]) import("/output/_stlcheck/part.stl"); }
if (thin == 0) m();
else intersection() { m(); difference() { m(); offset(r=0.58) offset(r=-0.58) m(); } }
"""


def slice_svg(stl: Path, z: float, thin: bool = False):
    WORK.mkdir(parents=True, exist_ok=True)
    part = WORK / "part.stl"
    if not part.exists() or part.read_bytes() != stl.read_bytes():
        shutil.copy(stl, part)
    svg = openscad(SLICE_SCAD, "slice.svg", zc=z, thin=1 if thin else 0)
    return contours(svg)


def front_view(cs):
    """Print-frame slice of the top shell -> assembly XY.

    The top prints face-down, i.e. the assembly copy turned 180° about X,
    so assembly (x, y) sits at print (x, -y). Measuring the print file
    directly in assembly XY (as this gate did before 2026-09-23) only
    passes on the MIRROR IMAGE of the top — which is what got printed."""
    out = []
    for pts, area, bb, depth in cs:
        out.append(([(x, -y) for x, y in pts], area,
                    (bb[0], bb[1], -bb[3], -bb[2]), depth))
    return out


def contours(svg: Path):
    """[(pts, area, bbox, depth)] — depth odd = hole."""
    txt = svg.read_text()
    polys = []
    for d in re.findall(r'd="([^"]+)"', txt):
        for sub in re.findall(r"M([^Mz]+)z", d):
            pts = [(float(a), -float(b)) for a, b in
                   re.findall(r"(-?[\d.]+),(-?[\d.]+)", sub)]
            if len(pts) < 3:
                continue
            a = 0.0
            for i in range(len(pts)):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % len(pts)]
                a += x1 * y2 - x2 * y1
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            polys.append([pts, abs(a) / 2, (min(xs), max(xs), min(ys), max(ys))])

    def inside(pt, poly):
        x, y = pt
        n = len(poly)
        c = False
        for i in range(n):
            x1, y1 = poly[i]
            x2, y2 = poly[(i + 1) % n]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
        return c

    out = []
    for i, (pts, area, bb) in enumerate(polys):
        depth = sum(1 for j, (p2, a2, b2) in enumerate(polys)
                    if j != i and a2 > area and inside(pts[0], p2))
        out.append((pts, area, bb, depth))
    return out


def holes(cs):
    return [c for c in cs if c[3] % 2 == 1]


def solids(cs):
    return [c for c in cs if c[3] % 2 == 0]


def near(cs, x, y, r=1.5):
    """contours whose bbox centre lies within r of (x, y)"""
    return [c for c in cs
            if math.hypot((c[2][0] + c[2][1]) / 2 - x, (c[2][2] + c[2][3]) / 2 - y) <= r]


def size(c):
    return c[2][1] - c[2][0], c[2][3] - c[2][2]


def centre(c):
    return (c[2][0] + c[2][1]) / 2, (c[2][2] + c[2][3]) / 2


def first_material(cs, x0, y0, dx, dy, maxd, step=0.05):
    """distance from (x0,y0) along (dx,dy) to the first point in material"""
    d = 0.0
    while d <= maxd:
        if point_in_material(cs, x0 + dx * d, y0 + dy * d):
            return d
        d += step
    return float("nan")


def point_in_material(cs, x, y):
    n = 0
    for pts, _a, _b, _d in cs:
        c = False
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                c = not c
        n += c
    return n % 2 == 1


# ── main ─────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 72)
    print("ENCLOSURE STL AUDIT — measured from 3d_case/*.stl, compared with board.py,")
    print("datasheets and the user's requirements (no enclosure.scad constants)")
    print("=" * 72)
    try:
        from scripts.generate_pcb import board as B
        from scripts import generate_enclosure_pcb as GEP
    except Exception as e:
        raise Structural(f"cannot import board sources: {e}")
    parts = GEP.parts()
    P = {r[0]: r for r in parts}
    scad_mtime = max(p.stat().st_mtime for p in
                     (BASE / "hardware" / "enclosure").glob("*.scad"))
    for f in ("case_top.stl", "case_bottom.stl", "lever_r.stl", "lever_l.stl",
              "battery_strap_x2.stl", "viewer/parts/part_display.stl"):
        if not (CASE / f).exists():
            raise Structural(f"3d_case/{f} missing — run make export-enclosure-stl")
        if (CASE / f).stat().st_mtime < scad_mtime:
            raise Structural(f"3d_case/{f} is older than the scad sources — "
                             "run make export-enclosure-stl first")
    results = []

    def check(code, name, ok, detail):
        results.append(ok)
        print(f"  {'PASS' if ok else 'FAIL'}  {code} {name}: {detail}")

    top, bot = CASE / "case_top.stl", CASE / "case_bottom.stl"

    def top_slice(z):
        return front_view(slice_svg(top, z))

    # S0 the viewer shows the print files: every 3d_case/*.stl instance,
    # placed by viewer/placement.json (what viewer.html applies), must be a
    # rotation (det +1) and reproduce the scad assembly reference exactly
    import json
    from scripts import enclosure_placement as EP
    pj = CASE / "viewer" / "placement.json"
    if not pj.exists() or pj.stat().st_mtime < scad_mtime:
        raise Structural("3d_case/viewer/placement.json missing or stale — "
                         "run make export-enclosure-stl")
    shipped = json.loads(pj.read_text())
    bad = [f"{p['file']}: det {EP.det(p['rot'])}" for p in shipped if EP.det(p["rot"]) != 1]
    fresh = EP.compute()
    def norm(ps):
        return [(p["file"], json.dumps(p["rot"]), json.dumps(list(p["t"]))) for p in ps]
    if norm(fresh) != norm(shipped):
        bad.append("placement.json differs from the print files — regenerate it")
    for rf, frac, extra in EP.check([dict(p, t=tuple(p["t"]), ref=f["ref"])
                                     for p, f in zip(shipped, fresh)]):
        if frac < 0.999 or extra:
            bad.append(f"{rf}: {frac:.1%} reproduced, {extra} vertices elsewhere")
    printed = {f.name for f in CASE.glob("*.stl")}
    unplaced = printed - {p["file"] for p in shipped}
    if unplaced:
        bad.append(f"print files the viewer never shows: {sorted(unplaced)}")
    check("S0", "viewer-shows-the-print-files",
          not bad,
          f"{len(shipped)} placed instances of {len(printed)} print files, all pure "
          "rotations, each lands exactly on the design's assembly position"
          + (": " + "; ".join(bad) if bad else ""))

    # S1 envelopes
    bt, bb_ = bbox(top), bbox(bot)
    tw, th, td = bt[1] - bt[0], bt[3] - bt[2], bt[5] - bt[4]
    bw, bh, bd = bb_[1] - bb_[0], bb_[3] - bb_[2], bb_[5] - bb_[4]
    # top: 2 front wall + 7.0 display stack + 1.6 PCB = 10.6, plus the 0.6 mm
    # cosmetic bezel proud of the face; bottom: 16 to the split + 2 mm lip
    check("S1", "shell-envelopes",
          abs(tw - 170) < 0.05 and abs(th - 85) < 0.05 and abs(td - 11.2) < 0.05
          and abs(bw - 170) < 0.05 and abs(bh - 85) < 0.05 and abs(bd - 18) < 0.05,
          f"top {tw:.2f}x{th:.2f}x{td:.2f} (want 170x85x11.2: 2 wall + 7.0 "
          f"stack + 1.6 PCB + 0.6 bezel), bottom {bw:.2f}x{bh:.2f}x{bd:.2f} "
          f"(want 170x85x18: 16 + 2 lip)")

    # S2 front face cutouts (slice through the front wall)
    face = top_slice(1.0)
    fh = holes(face)
    bad = []
    sw_pos = {r: (P[r][1], P[r][2]) for r in P if r.startswith("SW") and P[r][4] == "top"}
    abxy = {"A": "SW5", "B": "SW6", "X": "SW7", "Y": "SW8"}
    for name, ref in abxy.items():
        x, y = sw_pos[ref]
        h = near(fh, x, y, 1.0)
        if len(h) != 1:
            bad.append(f"{name}: {len(h)} holes at {ref}")
            continue
        w, hh = size(h[0])
        cx, cy = centre(h[0])
        if abs(w - hh) > 0.1 or w < 9 - 0.05 or math.hypot(cx - x, cy - y) > TOL_POS:
            bad.append(f"{name}: Ø{w:.2f}x{hh:.2f} at ({cx:.2f},{cy:.2f}) vs {ref} ({x},{y})")
    dx, dy = B.DPAD_ENC
    h = near(fh, dx, dy, 1.0)
    if len(h) != 1:
        bad.append(f"D-pad: {len(h)} holes")
    else:
        w, hh = size(h[0])
        # arm width = the narrow dimension of the cross: sample the contour
        pts = h[0][0]
        arm = max(p[1] for p in pts if abs(p[0] - dx) > 9) - \
            min(p[1] for p in pts if abs(p[0] - dx) > 9)
        cx, cy = centre(h[0])
        if abs(w - 24) > 0.1 or abs(hh - 24) > 0.1 or arm < 6.5 - 0.05 \
                or math.hypot(cx - dx, cy - dy) > TOL_POS:
            bad.append(f"D-pad {w:.2f}x{hh:.2f} arms {arm:.2f} at ({cx:.2f},{cy:.2f})")
    for name, ref, wmin, hmin in (("Start", "SW9", 10, 5), ("Select", "SW10", 10, 5),
                                  ("Menu", "SW13", 12, 3.8)):
        x, y = sw_pos[ref]
        h = near(fh, x, y, 1.0)
        if len(h) != 1:
            bad.append(f"{name}: {len(h)} holes")
            continue
        w, hh = size(h[0])
        cx, cy = centre(h[0])
        if w < wmin - 0.05 or hh < hmin - 0.05 or math.hypot(cx - x, cy - y) > TOL_POS:
            bad.append(f"{name} {w:.2f}x{hh:.2f} at ({cx:.2f},{cy:.2f}) vs ({x},{y})")
    for n in range(1, 7):
        x, y = P[f"LED{n}"][1], P[f"LED{n}"][2]
        h = near(fh, x, y, 1.0)
        if len(h) != 1:
            bad.append(f"LED{n}: {len(h)} holes")
            continue
        w, hh = size(h[0])
        want = 2.0 if n <= 2 else 1.2
        if abs(w - want) > 0.1 or math.hypot(*[a - b for a, b in zip(centre(h[0]), (x, y))]) > TOL_POS:
            bad.append(f"LED{n} Ø{w:.2f} (want {want})")
    check("S2", "front-cutouts-vs-board",
          not bad,
          f"{len(fh)} holes in the front wall; ABXY/D-pad/Start/Select/Menu/LED1-6 "
          "on their placements" + (": " + "; ".join(bad) if bad else ""))

    # S3 viewport
    big = max(fh, key=lambda c: c[1])
    vw, vh = size(big)
    vcx, vcy = centre(big)
    check("S3", "viewport-is-active-area",
          abs(vw - PANEL_ACTIVE[0] - 0.6) < 0.1 and abs(vh - PANEL_ACTIVE[1] - 0.6) < 0.1
          and abs(vcy - B.DISPLAY_ENC[1]) < 0.1,
          f"viewport {vw:.2f}x{vh:.2f} at ({vcx:.2f},{vcy:.2f}) vs active "
          f"{PANEL_ACTIVE[0]}x{PANEL_ACTIVE[1]} + 0.6, y {B.DISPLAY_ENC[1]}")

    # S4 glass pocket: scan from the centre of the viewport to the frame's
    # inner faces (Y both ways at x = 0; +X at y = 20 hits the stub; the
    # tail side is open, so the -X edge follows from the outline length)
    mid = top_slice(6.0)
    up = first_material(mid, 0, 2, 0, 1, 45)
    dn = first_material(mid, 0, 2, 0, -1, 45)
    pocket_h = up + dn
    px1 = first_material(mid, 0, 20, 1, 0, 80)
    sel_hole = near(fh, *sw_pos["SW10"], 1.0)[0]
    y_hole = near(fh, *sw_pos["SW8"], 1.0)[0]
    sel_body_edge = sel_hole[2][1] - 0.3
    y_body_edge = y_hole[2][0] + 0.3
    gap_r = y_body_edge - px1
    px0 = px1 - (PANEL_OUTLINE[0] + 0.6)
    gap_l = px0 - sel_body_edge
    check("S4", "glass-pocket",
          abs(pocket_h - PANEL_OUTLINE[1] - 0.6) < 0.1 and gap_r >= 0.4
          and gap_l >= 0.4 and abs(gap_l - gap_r) < 0.1,
          f"frame inner span Y {pocket_h:.2f} (want {PANEL_OUTLINE[1]} + 0.6); "
          f"pocket x[{px0:.2f}, {px1:.2f}] ({PANEL_OUTLINE[0]} + 0.6); gap to the "
          f"Y cap body {gap_r:.2f}, to the Select cap body {gap_l:.2f} (equal, >= 0.4)")

    # S5 top bosses: slices at 0.4 above the boss end (8.6) and inside the relief (3.0)
    end = top_slice(8.8)      # 0.2 below the boss end (9.0 = PCB top face)
    rel = top_slice(3.0)
    face0 = top_slice(1.0)
    corners = [(x, y) for x, y in B.MOUNT_HOLES_ENC if abs(x) > 50]
    bad = []
    for x, y in corners:
        sock = near(holes(end), x, y, 0.5)
        ring = near(solids(end), x, y, 0.5)
        r_rel = near(holes(rel), x, y, 0.5)
        f = near(holes(face0), x, y, 3.0)
        if len(sock) != 1 or len(ring) != 1 or len(r_rel) != 1 or f:
            bad.append(f"({x},{y}): socket {len(sock)} ring {len(ring)} relief {len(r_rel)} face-holes {len(f)}")
            continue
        ds, dr, dq = size(sock[0])[0], size(ring[0])[0], size(r_rel[0])[0]
        wall = (dr - ds) / 2
        if abs(ds - (INSERT[0] - 0.4)) > 0.08 or wall < 2.0 - 0.05 or abs(dq - 2.8) > 0.08:
            bad.append(f"({x},{y}): socket Ø{ds:.2f} ring Ø{dr:.2f} wall {wall:.2f} relief Ø{dq:.2f}")
    # socket depth: the socket Ø must still be present at 4.4 below the end and gone at 4.6
    d1 = near(holes(top_slice(9.0 - 4.4)), *corners[0], 0.5)
    d2 = near(holes(top_slice(9.0 - 4.6)), *corners[0], 0.5)
    depth_ok = d1 and abs(size(d1[0])[0] - 3.1) < 0.08 and d2 and abs(size(d2[0])[0] - 2.8) < 0.08
    check("S5", "insert-bosses",
          not bad and depth_ok,
          f"4 corner bosses: socket Ø3.1 for OD {INSERT[0]} x L {INSERT[1]} insert, "
          f">= 2 mm wall, Ø2.8 relief, socket depth 4.5 (3.1 at -4.4, 2.8 at -4.6: "
          f"{'ok' if depth_ok else 'WRONG'}), front face closed"
          + (": " + "; ".join(bad) if bad else ""))

    # S6 bottom counterbores, bores, half-columns
    fl = slice_svg(bot, 1.0)
    col = slice_svg(bot, 8.0)
    half = slice_svg(bot, 15.5)
    bad = []
    for x, y in corners:
        cb = near(holes(fl), x, y, 0.5)
        bore = near(holes(col), x, y, 0.5)
        if len(cb) != 1 or abs(size(cb[0])[0] - 5.0) > 0.1:
            bad.append(f"counterbore at ({x},{y}): {[size(c)[0] for c in cb]}")
        if len(bore) != 1 or abs(size(bore[0])[0] - 2.8) > 0.1:
            bad.append(f"bore at ({x},{y}): {[size(c)[0] for c in bore]}")
        inner = x - 1.5 * (1 if x > 0 else -1)
        if point_in_material(half, inner, y) or not point_in_material(half, x + 2.2 * (1 if x > 0 else -1), y):
            bad.append(f"half-column at ({x},{y}): material at x={inner} or none at outer side")
    sw11 = P["SW11"]
    check("S6", "bottom-columns",
          not bad,
          f"counterbores Ø5, bores Ø2.8, contact half-columns open toward the board "
          f"centre (SW11/SW12 body edge {abs(sw11[1]) + 2.55:.2f}, pads to 68.25)"
          + (": " + "; ".join(bad) if bad else ""))

    # S7 pocket: the border ring is open at the lead notch and the hinge
    # corners, so scan from the pocket centre to its inner faces at Z 8
    j3 = P["J3"]
    j3_ymax = j3[2] + 8.6 / 2
    cxp, cyp = -1.5, 5.0                 # anywhere inside the pocket
    xl = first_material(col, cxp, cyp, -1, 0, 60)
    xr = first_material(col, cxp, cyp, 1, 0, 60)
    yd = first_material(col, cxp, cyp, 0, -1, 40)
    yu = first_material(col, cxp, cyp, 0, 1, 40)
    pw, ph = xl + xr, yd + yu
    y0 = cyp - yd
    posts = [c for c in holes(slice_svg(bot, 10.5))
             if 2.5 < size(c)[0] < 2.9 and 2.5 < size(c)[1] < 2.9
             and abs(centre(c)[0]) < 60]          # not the corner screw bores
    check("S7", "battery-pocket",
          pw >= MEASURED_CELL[0] + 5 - 0.1 and ph >= MEASURED_CELL[1] - 0.1
          and y0 >= j3_ymax - 1e-6 and len(posts) == 4,
          f"pocket {pw:.2f}x{ph:.2f} (measured cell {MEASURED_CELL[0]}x{MEASURED_CELL[1]} "
          f"+ 5 leads), bottom edge y={y0:.2f} vs J3 top {j3_ymax:.2f}, "
          f"{len(posts)} strap peg holes")

    # S8 lever webs
    bad = []
    for sgn in (-1, 1):
        ref = "SW12" if sgn > 0 else "SW11"
        sx = P[ref][1]
        lever = [c for c in holes(fl) if 13 < size(c)[0] < 16 and 8 < size(c)[1] < 10
                 and abs(centre(c)[1] - 32) < 2 and centre(c)[0] * sgn > 0]
        cb = near(holes(fl), 70 * sgn, 30.5, 0.5)
        if len(lever) != 1 or len(cb) != 1:
            bad.append(f"{ref}: lever cutouts {len(lever)}")
            continue
        web = (cb[0][2][0] - lever[0][2][1]) if sgn > 0 else (lever[0][2][0] - cb[0][2][1])
        if web < MIN_WALL - 0.02:
            bad.append(f"{ref}: web {web:.2f}")
    check("S8", "lever-webs", not bad,
          f"lever face cutout to counterbore >= {MIN_WALL}" + (": " + "; ".join(bad) if bad else ""))

    # S9 grille
    small = [c for c in holes(fl) if size(c)[0] < 2]
    gx = sum(centre(c)[0] for c in small) / len(small) if small else 0
    gy = sum(centre(c)[1] for c in small) / len(small) if small else 0
    check("S9", "speaker-grille", len(small) >= 20 and gx > 40 and gy > 0,
          f"{len(small)} grille holes, centroid ({gx:.1f},{gy:.1f}) — +X/+Y = top-left from the back")

    # S10 parts
    bad = []
    capmap = {"part_btn_a": "SW5", "part_btn_b": "SW6", "part_btn_x": "SW7",
              "part_btn_y": "SW8", "part_start": "SW9", "part_select": "SW10",
              "part_menu": "SW13"}
    for fn, ref in capmap.items():
        b = bbox(REF / f"{fn}.stl")
        cx, cy = (b[0] + b[1]) / 2, (b[2] + b[3]) / 2
        hgt = b[5] - b[4]
        # flange is asymmetric on Select/Y: use the stem (lowest 1 mm) for the centre
        low = [(x, y) for x, y, z in stl_vertices(REF / f"{fn}.stl") if z < b[4] + 0.5]
        scx = (min(p[0] for p in low) + max(p[0] for p in low)) / 2
        scy = (min(p[1] for p in low) + max(p[1] for p in low)) / 2
        if math.hypot(scx - P[ref][1], scy - P[ref][2]) > TOL_POS or abs(hgt - 7.9) > 0.05:
            bad.append(f"{fn}: stem at ({scx:.2f},{scy:.2f}) vs {ref} ({P[ref][1]},{P[ref][2]}), height {hgt:.2f}")
    for fn, ref in (("part_shoulder_r", "SW12"), ("part_shoulder_l", "SW11")):
        b = bbox(REF / f"{fn}.stl")
        topv = [(x, y) for x, y, z in stl_vertices(REF / f"{fn}.stl") if z > b[5] - 0.3]
        nx = (min(p[0] for p in topv) + max(p[0] for p in topv)) / 2
        ny = (min(p[1] for p in topv) + max(p[1] for p in topv)) / 2
        if math.hypot(nx - P[ref][1], ny - P[ref][2]) > TOL_POS or abs(b[5] - 14.3) > 0.05:
            bad.append(f"{fn}: nub at ({nx:.2f},{ny:.2f}) top Z {b[5]:.2f} vs {ref} ({P[ref][1]},{P[ref][2]}) / 14.3")
    sb = bbox(REF / "part_straps.stl")
    esp = P["U1"]
    strap_ok = abs(sb[5] - 13.2) < 0.05 and abs(sb[4] - 9.0) < 0.05   # pegs 3 mm into the posts
    strap_x = sorted({round(x, 1) for x, y, z in stl_vertices(REF / "part_straps.stl") if z > 13.1})
    inside_esp = [x for x in strap_x if esp[1] - esp[5] / 2 < x < esp[1] + esp[5] / 2]
    if not strap_ok or inside_esp:
        bad.append(f"straps Z {sb[4]:.2f}..{sb[5]:.2f}, x over the ESP32: {inside_esp[:3]}")
    db = bbox(PARTS / "part_display.stl")
    if abs(db[5] - 24.6) > 0.05 or (db[3] - db[2]) < PANEL_OUTLINE[1] - 0.05:
        bad.append(f"display part top Z {db[5]:.2f} (ceiling 24.6), Y span {db[3] - db[2]:.2f}")
    check("S10", "parts-aligned-to-board", not bad,
          "7 caps on their switches (7.9 tall), lever nubs on SW11/SW12 (Z 14.3), "
          "straps at Z 12..13.2 off the module, glass top at the ceiling"
          + (": " + "; ".join(bad) if bad else ""))

    # S11 thin walls measured on the STL slices
    thin = []
    for stl, zs, tag in ((top, (1.0, 3.0, 4.5, 6.0, 8.9), "top"),
                         (bot, (1.0, 5.0, 9.0, 13.0, 15.5, 17.0), "bottom"),
                         (CASE / "lever_r.stl", (0.5, 2.5, 5.0), "lever")):
        for z in zs:
            for c in slice_svg(stl, z, thin=True):
                if c[1] > 0.3:
                    thin.append(f"{tag} z={z} {size(c)[0]:.1f}x{size(c)[1]:.1f} at "
                                f"({centre(c)[0]:.1f},{centre(c)[1]:.1f})")
    check("S11", "thin-walls-on-stl", not thin,
          f"14 STL slices eroded by 0.6: " + ("; ".join(thin[:6]) if thin else "nothing under 1.2 mm"))

    shutil.rmtree(WORK, ignore_errors=True)
    print("-" * 72)
    fails = results.count(False)
    if fails:
        print(f"Results: FAIL — {fails}/{len(results)} STL measurements disagree with the sources")
        return 1
    print(f"Results: PASS — {len(results)}/{len(results)} STL measurements agree with board.py, "
          "the datasheets and the requirements")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Structural as e:
        print(f"STRUCTURAL ERROR: {e}", file=sys.stderr)
        sys.exit(2)
