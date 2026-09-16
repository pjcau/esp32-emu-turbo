#!/usr/bin/env python3
"""Enclosure interference gate — the shells must not share volume with
anything they enclose.

verify_enclosure_sync compares CONSTANTS (the scad numbers vs the board
numbers). It cannot see a boss standing on a switch, a battery clip
cutting into the cell, or a cap flange touching the display rim — those
are consequences of geometry, not of a constant. This gate asks OpenSCAD
itself: it exports the `collision_check` part of enclosure.scad (the CGAL
intersection of top+bottom shell with PCB model, panel, battery, speaker
and every button cap) and parses the STL. Contacts on faces (a column
neck seated on the PCB, the speaker on the floor) have zero volume and
are fine; any connected component with positive volume is a part of the
printed shell that occupies the same space as a part inside it.

Requires the OpenSCAD Docker service (docker compose run openscad),
exactly like scripts/render-enclosure.sh. If Docker cannot run, that is a
structural error (exit 2), not a pass.

Output contract: every failing component prints a line starting with
FAIL — open_issues_report.py extracts exactly that shape.

Exit codes: 0 no interference · 1 interference · 2 cannot evaluate.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
# docker-compose maps ./website/static/img/renders -> /output
OUT_DIR = BASE / "website" / "static" / "img" / "renders"
STL_REL = "enclosure-collision-check.stl"
MIN_VOLUME = 0.01   # mm^3 — below this is CGAL face-contact noise


class Structural(RuntimeError):
    pass


def export_stl() -> Path:
    out = OUT_DIR / STL_REL
    if out.exists():
        out.unlink()
    cmd = ["docker", "compose", "-f", str(BASE / "docker-compose.yml"),
           "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
           "openscad", "-o", f"/output/{STL_REL}",
           "-D", 'part="collision_check"', "/project/enclosure.scad"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise Structural(f"cannot run the OpenSCAD container: {e}")
    if r.returncode != 0 or not out.exists():
        raise Structural("OpenSCAD export failed:\n"
                         + (r.stderr or r.stdout)[-2000:])
    return out


def components(stl: Path):
    """Connected components of an ASCII STL: (volume, bbox, tris)."""
    tris, cur = [], []
    for line in stl.read_text().splitlines():
        line = line.strip()
        if line.startswith("vertex"):
            cur.append(tuple(round(float(v), 4) for v in line.split()[1:4]))
            if len(cur) == 3:
                tris.append(tuple(cur))
                cur = []
    parent: dict = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    # connectivity through shared EDGES, not single vertices: two slivers
    # that merely touch at a point are two regions, not one
    edge_owner: dict = {}
    for i, (a, b, c) in enumerate(tris):
        for e in ((a, b), (b, c), (c, a)):
            key = tuple(sorted(e))
            j = edge_owner.setdefault(key, i)
            if j != i:
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i, t in enumerate(tris):
        groups[find(i)].append(t)
    out = []
    for ts in groups.values():
        v = 0.0
        for a, b, c in ts:
            v += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6
        pts = [p for t in ts for p in t]
        xs, ys, zs = zip(*pts)
        out.append((abs(v), (min(xs), max(xs), min(ys), max(ys),
                             min(zs), max(zs)), len(ts)))
    return sorted(out, key=lambda c: -c[0])


def main() -> int:
    print("=" * 72)
    print("ENCLOSURE INTERFERENCE (shells vs PCB / panel / battery / caps)")
    print("=" * 72)
    stl = export_stl()
    try:
        comps = components(stl)
    finally:
        stl.unlink(missing_ok=True)
    bad = [c for c in comps if c[0] > MIN_VOLUME]
    contacts = len(comps) - len(bad)
    for vol, (x0, x1, y0, y1, z0, z1), n in bad:
        print(f"  FAIL  {vol:.2f} mm^3 shared at x[{x0:.1f},{x1:.1f}] "
              f"y[{y0:.1f},{y1:.1f}] z[{z0:.1f},{z1:.1f}] ({n} tris)")
    print(f"  {len(comps)} components: {contacts} face contacts (0 volume), "
          f"{len(bad)} interference(s)")
    print("-" * 72)
    if bad:
        print(f"Results: FAIL — {len(bad)} region(s) where the printed shell "
              "occupies the same space as a part it encloses")
        return 1
    print("Results: PASS — shells share no volume with the enclosed parts")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Structural as e:
        print(f"STRUCTURAL ERROR: {e}", file=sys.stderr)
        sys.exit(2)
