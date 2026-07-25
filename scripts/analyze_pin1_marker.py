#!/usr/bin/env python3
"""Locate the PHYSICAL pin-1 / polarity marker of an LCSC part, analytically.

Why this exists
---------------
`_JLCPCB_ROT_OVERRIDES` in scripts/generate_pcb/jlcpcb_export.py is a
hand-maintained table. Every entry in it was originally chosen by trying a
value, looking at the JLCPCB 3D preview, and trying again (see git history:
`39e350c` D1 "90 -> 180", then `c7514e7` D1 "180 -> 270" the same day).
`verify_easyeda_footprint.py` then checks that a *sign-off exists* for each
mismatch — via `_JLCPCB_ROT_OVERRIDES`, `_GEOMETRIC_MISMATCH_ALLOWLIST` or
`_PENDING_VALIDATION` — not that the emitted angle is *geometrically right*.
A gate that asks "did somebody sign this off?" cannot catch a wrong sign-off.

This module answers the one question those tables encode by hand:

    In the EasyEDA/JLCPCB footprint frame, at CPL rotation 0, WHERE IS THE
    PHYSICAL POLARITY MARKER OF THE PART?

Once that is known, the required CPL rotation is arithmetic, not judgement.

Two INDEPENDENT extractors
--------------------------
Both read only files already in `scripts/.easyeda_cache/` (the EasyEDA API
now returns HTTP 403, so the archived cache is the only source).

  silk : mirror-asymmetry of the F.SilkS body outline. Reflect the silk
         vertices about the perpendicular bisector of the pad axis; vertices
         with no mirror partner are the asymmetric feature (cathode chamfer,
         polarity bar, bevel). Their weighted centroid gives the direction.

  mesh : per-Shape colour groups of the manufacturer 3D model (.wrl). The
         polarity mark is a small LOCALISED colour patch on the body's top
         face, offset to one end. Symmetric groups (terminals, body) are
         rejected; the localised off-centre patch is the marker.

They share no input beyond the part identity: one reads 2D silkscreen drawn
by the footprint author, the other reads a 3D mesh from the manufacturer.
Agreement between them is strong evidence; disagreement is a hard FAIL,
never a silent pass.

WHAT THIS DELIBERATELY DOES NOT USE
-----------------------------------
The pin-1 *dot* (small F.SilkS circle) is present on 30/30 cached parts and
looks like an ideal anchor. It is NOT one: it is drawn next to whichever pad
the footprint author numbered "1", so it reproduces a wrong numbering instead
of exposing it. Verified on the two 0805 LEDs -- the dot sits beside pad 1 in
both, including the one whose numbering is inverted. Pad numbers and the dot
are the hypothesis under test; they can never be the reference.

Usage:
    python3 scripts/analyze_pin1_marker.py                 # every cached part
    python3 scripts/analyze_pin1_marker.py C84256 C19171391
"""

from __future__ import annotations

import glob
import math
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CACHE = BASE / "scripts" / ".easyeda_cache"

# A silk circle at or below this radius is a pin-1 dot: excluded from the
# outline (see module docstring -- it tracks pad numbering, not physics).
PIN1_DOT_MAX_R = 0.35

# A reflected silk vertex further than this from any real vertex has no
# mirror partner and therefore belongs to an asymmetric feature.
MIRROR_TOL_MM = 0.12

# A 3D colour group whose X-extent is below this fraction of the body's
# total X-extent is "localised" -- a printed mark rather than body or
# terminal geometry.
MESH_LOCALISED_FRAC = 0.35

# A localised group must sit at least this far off-centre (as a fraction of
# the body half-width) to count as a polarity marker rather than a centred
# logo or part number.
MESH_OFFCENTRE_FRAC = 0.30

_PAD_RE = re.compile(
    r'\(pad\s+"?([^\s")]+)"?\s+\S+\s+\S+\s+\(at\s+([-\d.]+)\s+([-\d.]+)'
)
_LINE_RE = re.compile(
    r'\(fp_line\s+\(start\s+([-\d.]+)\s+([-\d.]+)\)\s+'
    r'\(end\s+([-\d.]+)\s+([-\d.]+)\)[^)]*\(layer\s+"?([\w.]+)"?'
)
_CIRCLE_RE = re.compile(
    r'\(fp_circle\s+\(center\s+([-\d.]+)\s+([-\d.]+)\)\s+'
    r'\(end\s+([-\d.]+)\s+([-\d.]+)\)[^)]*\(layer\s+"?([\w.]+)"?'
)
_SHAPE_RE = re.compile(
    r"diffuseColor\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(.*?)point\s*\[(.*?)\]",
    re.S,
)
_XYZ_RE = re.compile(r"([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s*,")


def _angle(dx: float, dy: float) -> float:
    return math.degrees(math.atan2(dy, dx)) % 360.0


def _ang_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings, in degrees."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


# ── silk extractor ───────────────────────────────────────────────────

def read_footprint(lcsc: str) -> dict | None:
    """Parse the cached EasyEDA .kicad_mod. Returns pads + silk outline."""
    mods = glob.glob(str(CACHE / lcsc / "fp.pretty" / "*.kicad_mod"))
    if not mods:
        return None
    text = Path(mods[0]).read_text(errors="replace")

    pads = [
        (m.group(1), float(m.group(2)), float(m.group(3)))
        for m in _PAD_RE.finditer(text)
    ]
    outline: list[tuple[float, float]] = []
    for m in _LINE_RE.finditer(text):
        if "Silk" not in m.group(5):
            continue
        outline.append((float(m.group(1)), float(m.group(2))))
        outline.append((float(m.group(3)), float(m.group(4))))
    for m in _CIRCLE_RE.finditer(text):
        if "Silk" not in m.group(5):
            continue
        cx, cy, ex, ey = (float(m.group(i)) for i in (1, 2, 3, 4))
        if math.hypot(ex - cx, ey - cy) > PIN1_DOT_MAX_R:
            outline.append((cx, cy))  # a large circle is real body outline
    return {"path": mods[0], "pads": pads, "outline": outline}


def marker_from_silk(fp: dict) -> tuple[float, int] | None:
    """Bearing of the asymmetric silk feature, measured from pad centroid."""
    pads, outline = fp["pads"], fp["outline"]
    if len(pads) < 2 or len(outline) < 4:
        return None

    cx = sum(p[1] for p in pads) / len(pads)
    cy = sum(p[2] for p in pads) / len(pads)

    # Pad-array principal axis = the widest-separated pad pair.
    far = max(
        ((i, j) for i in range(len(pads)) for j in range(i + 1, len(pads))),
        key=lambda ij: math.hypot(
            pads[ij[0]][1] - pads[ij[1]][1], pads[ij[0]][2] - pads[ij[1]][2]
        ),
    )
    pa, pb = pads[far[0]], pads[far[1]]
    ux, uy = pa[1] - pb[1], pa[2] - pb[2]
    norm = math.hypot(ux, uy)
    if norm < 1e-9:
        return None
    ux, uy = ux / norm, uy / norm

    def reflect(px: float, py: float) -> tuple[float, float]:
        dx, dy = px - cx, py - cy
        t = dx * ux + dy * uy
        return (cx + dx - 2 * t * ux, cy + dy - 2 * t * uy)

    residual = []
    for px, py in outline:
        rx, ry = reflect(px, py)
        nearest = min(math.hypot(rx - qx, ry - qy) for qx, qy in outline)
        if nearest > MIRROR_TOL_MM:
            residual.append(((px, py), nearest))
    if not residual:
        return None

    wsum = sum(w for _, w in residual)
    mx = sum(p[0] * w for p, w in residual) / wsum
    my = sum(p[1] * w for p, w in residual) / wsum
    return (_angle(mx - cx, my - cy), len(residual))


# ── mesh extractor ───────────────────────────────────────────────────

def marker_from_mesh(lcsc: str) -> tuple[float, tuple] | None:
    """Bearing of the localised off-centre colour patch in the 3D model.

    The .wrl shares the footprint's frame (KiCad records `rotate (xyz 0 0 0)`
    for these parts), so a bearing computed here is directly comparable to
    the silk bearing.
    """
    wrls = glob.glob(str(CACHE / lcsc / "fp.3dshapes" / "*.wrl"))
    if not wrls:
        return None
    text = Path(wrls[0]).read_text(errors="replace")

    groups = []
    for m in _SHAPE_RE.finditer(text):
        colour = tuple(round(float(m.group(i)), 2) for i in (1, 2, 3))
        pts = [
            (float(t.group(1)), float(t.group(2)), float(t.group(3)))
            for t in _XYZ_RE.finditer(m.group(5))
        ]
        if pts:
            groups.append((colour, pts))
    if not groups:
        return None

    xs_all = [p[0] for _, pts in groups for p in pts]
    ys_all = [p[1] for _, pts in groups for p in pts]
    span_x = max(xs_all) - min(xs_all)
    cx = (max(xs_all) + min(xs_all)) / 2
    cy = (max(ys_all) + min(ys_all)) / 2
    if span_x < 1e-9:
        return None

    # Candidate markers are evaluated PER SHAPE, not aggregated per colour:
    # a body and its polarity mark are often authored in the same colour
    # (verified on C19171391, where the mark and a side face share the LED's
    # own green), and merging them destroys the localisation that identifies
    # the mark.
    cands = []
    for colour, pts in groups:
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        if (max(xs) - min(xs)) > MESH_LOCALISED_FRAC * span_x:
            continue
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        offset = math.hypot(mx - cx, my - cy)
        if offset < MESH_OFFCENTRE_FRAC * (span_x / 2):
            continue
        cands.append((colour, mx, my, offset, len(pts)))
    if not cands:
        return None

    # Drop anything with a mirror twin of the same colour on the far side:
    # that is a symmetric feature (the two terminals), not a polarity mark.
    tol = 0.08 * span_x
    asym = [
        c for c in cands
        if not any(
            o[0] == c[0]
            and abs((o[1] - cx) + (c[1] - cx)) < tol
            and abs((o[2] - cy) - (c[2] - cy)) < tol
            for o in cands if o is not c
        )
    ]
    if not asym:
        return None

    # Every surviving patch marks the same end; average them by point count
    # so a single noisy sliver cannot swing the bearing.
    wsum = sum(c[4] for c in asym)
    mx = sum(c[1] * c[4] for c in asym) / wsum
    my = sum(c[2] * c[4] for c in asym) / wsum
    return (_angle(mx - cx, my - cy), tuple(sorted({c[0] for c in asym})))


# ── report ───────────────────────────────────────────────────────────

def analyse(lcsc: str) -> dict:
    out = {"lcsc": lcsc, "pad1": None, "silk": None, "mesh": None,
           "verdict": "NO DATA"}
    fp = read_footprint(lcsc)
    if fp is None:
        return out

    pads = fp["pads"]
    if len(pads) >= 2:
        cx = sum(p[1] for p in pads) / len(pads)
        cy = sum(p[2] for p in pads) / len(pads)
        p1 = next((p for p in pads if p[0] in ("1", "A1")), None)
        if p1:
            out["pad1"] = _angle(p1[1] - cx, p1[2] - cy)

    silk = marker_from_silk(fp)
    if silk:
        out["silk"] = silk[0]
    mesh = marker_from_mesh(lcsc)
    if mesh:
        out["mesh"] = mesh[0]

    if out["silk"] is not None and out["mesh"] is not None:
        out["verdict"] = (
            "AGREE" if _ang_diff(out["silk"], out["mesh"]) <= 45 else "CONFLICT"
        )
    elif out["silk"] is not None or out["mesh"] is not None:
        out["verdict"] = "ONE SOURCE"
    return out


def main(argv: list[str]) -> int:
    parts = argv[1:] or sorted(p.name for p in CACHE.iterdir() if p.is_dir())
    print(f"{'LCSC':<11} {'pad1':>7} {'silk':>7} {'mesh':>7}  "
          f"{'sources':<10} pad1-vs-marker")
    print("-" * 72)
    conflicts = 0
    for lcsc in parts:
        r = analyse(lcsc)
        marker = r["mesh"] if r["mesh"] is not None else r["silk"]
        rel = ""
        if marker is not None and r["pad1"] is not None:
            d = _ang_diff(marker, r["pad1"])
            rel = f"delta={d:5.1f}deg  " + (
                "OPPOSITE -- pad numbering contradicts the physical marker"
                if d > 90 else "aligned"
            )
        if r["verdict"] == "CONFLICT":
            conflicts += 1
        fmt = lambda v: "  --  " if v is None else f"{v:6.1f}"  # noqa: E731
        print(f"{lcsc:<11} {fmt(r['pad1'])} {fmt(r['silk'])} {fmt(r['mesh'])}"
              f"  {r['verdict']:<10} {rel}")
    if conflicts:
        print(f"\n{conflicts} part(s) where silk and mesh disagree "
              f"-- resolve before trusting either.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
