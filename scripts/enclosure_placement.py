#!/usr/bin/env python3
"""Place the PRINT files in the assembly — the viewer shows what you print.

The website 3D viewer loads 3d_case/*.stl, the very files that go to the
printer, and only MOVES them: each instance is a proper rotation (det +1,
multiples of 90°) plus a translation. No separate "preview" geometry
exists, so the preview cannot show a part the print file does not contain
(the 2026-09 top was printed mirror-imaged while the preview, loaded from a
second export, looked right).

The rotation of each print part is declared here; the translation is
derived by matching the rotated print file onto the scad assembly copy in
hardware/enclosure/reference/. verify_enclosure_stl.py S0 then requires
every placed instance to reproduce that reference vertex for vertex.

Writes 3d_case/viewer/placement.json, read by website/static/viewer.html.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CASE = BASE / "3d_case"
REF = BASE / "hardware" / "enclosure" / "reference"
OUT = CASE / "viewer" / "placement.json"

I3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
RX180 = ((1, 0, 0), (0, -1, 0), (0, 0, -1))     # turned over about X

# print file -> [(rotation, reference part in assembly coords, group)]
# group drives the viewer's exploded offsets and colours. The two straps
# are the same printed file placed twice; the reference holds both.
PLACEMENT = {
    "case_top.stl":         [(RX180, "case_top.stl", "top")],
    "case_bottom.stl":      [(I3, "case_bottom.stl", "bottom")],
    "dpad.stl":             [(I3, "part_dpad.stl", "dpad")],
    "btn_a.stl":            [(I3, "part_btn_a.stl", "btn_a")],
    "btn_b.stl":            [(I3, "part_btn_b.stl", "btn_b")],
    "btn_x.stl":            [(I3, "part_btn_x.stl", "btn_x")],
    "btn_y.stl":            [(I3, "part_btn_y.stl", "btn_y")],
    "start.stl":            [(I3, "part_start.stl", "pill")],
    "select.stl":           [(I3, "part_select.stl", "pill")],
    "menu.stl":             [(I3, "part_menu.stl", "pill")],
    "lever_l.stl":          [(I3, "part_shoulder_l.stl", "lever")],
    "lever_r.stl":          [(I3, "part_shoulder_r.stl", "lever")],
    "battery_strap_x2.stl": [(RX180, "part_straps.stl", "strap"),
                             (RX180, "part_straps.stl", "strap")],
}


def stl_vertices(path: Path):
    for line in path.read_text().splitlines():
        s = line.strip()
        if s.startswith("vertex"):
            yield tuple(float(v) for v in s.split()[1:4])


def det(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def apply(m, t, v):
    return tuple(sum(m[i][j] * v[j] for j in range(3)) + t[i] for i in range(3))


def vset(verts):
    return {tuple(round(c, 2) for c in v) for v in verts}


def _bbox(vs):
    return [min(v[i] for v in vs) for i in range(3)], [max(v[i] for v in vs) for i in range(3)]


def compute():
    """[{file, group, rot, t}] — translation by bbox match, per instance"""
    out = []
    for pf, instances in PLACEMENT.items():
        pv = list(stl_vertices(CASE / pf))
        rotated = [apply(instances[0][0], (0, 0, 0), v) for v in pv]
        rmin, rmax = _bbox(rotated)
        ref = list(stl_vertices(REF / instances[0][1]))
        if len(instances) == 1:
            fmin, _ = _bbox(ref)
            targets = [fmin]
        else:
            # N copies side by side along X in the reference: split by the
            # gaps in X and match each cluster's bbox
            span = rmax[0] - rmin[0]
            xs = sorted({round(v[0], 2) for v in ref})
            starts = [xs[0]] + [b for a, b in zip(xs, xs[1:]) if b - a > span * 0.5]
            if len(starts) != len(instances):
                raise RuntimeError(f"{instances[0][1]}: {len(starts)} copies, "
                                   f"placement declares {len(instances)}")
            targets = []
            for x0 in starts:
                cl = [v for v in ref if x0 - 1e-6 <= v[0] <= x0 + span + 1e-3]
                targets.append(_bbox(cl)[0])
        for (rot, rf, group), tmin in zip(instances, targets):
            if det(rot) != 1:
                raise RuntimeError(f"{pf}: placement is not a rotation (det {det(rot)})")
            t = tuple(round(tmin[i] - rmin[i], 4) for i in range(3))
            out.append({"file": pf, "group": group, "rot": rot, "t": t, "ref": rf})
    return out


def check(placements):
    """[(ref, fraction of the reference reproduced by its placed instances)]"""
    by_ref = {}
    for p in placements:
        vs = [apply(p["rot"], p["t"], v) for v in stl_vertices(CASE / p["file"])]
        by_ref.setdefault(p["ref"], set()).update(vset(vs))
    res = []
    for rf, got in by_ref.items():
        want = vset(stl_vertices(REF / rf))
        res.append((rf, len(want & got) / max(len(want), 1), len(got - want)))
    return res


def main() -> int:
    placements = compute()
    bad = [r for r in check(placements) if r[1] < 0.999 or r[2]]
    if bad:
        for rf, frac, extra in bad:
            print(f"FAIL  {rf}: {frac:.1%} reproduced, {extra} extra vertices")
        return 1
    OUT.write_text(json.dumps([{k: p[k] for k in ("file", "group", "rot", "t")}
                               for p in placements], indent=1) + "\n")
    print(f"placement.json: {len(placements)} print-file instances, all rotations, "
          "each reproduces its assembly reference")
    return 0


if __name__ == "__main__":
    sys.exit(main())
