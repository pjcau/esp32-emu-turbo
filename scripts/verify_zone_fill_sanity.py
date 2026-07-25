#!/usr/bin/env python3
"""Zone-fill sanity gate — catches duplicated / impossible poured copper.

The bug being guarded against: ``scripts/kicad_fill_zones.py`` used to INJECT
its fill just before a zone's closing paren, which lands *after* any fill
already present. Two overlapping runs — ``drc_native.py --run`` racing a
hook-triggered fill — each read the same unfilled original and both injected,
doubling every zone's copper (4 filled islands -> 8, +3V3 9999 -> 19998 mm²).

Why this needs its own gate: a doubled board passes everything else. The
duplicated copper is geometrically identical to the original, so:

  - KiCad DRC is clean (no new clearance or short violations)
  - verify_power_net_integrity still reports ONE connected group per net
  - verify_dfm_v2 / verify_dfa / datasheet checks are all unaffected

It would have gone straight into the gerbers. The only observable symptom is
the poured area, which exceeded the physical board.

Two INDEPENDENT laws, either of which catches the doubling. Both are derived
from physics rather than from a table of known-bad values, so they keep
working as the layout changes:

  Law A — no duplicate islands. Two filled_polygon islands in the same zone
          with an identical vertex set cannot arise from a real pour: the
          filler emits each contiguous region exactly once.

  Law B — poured area fits the board. Zone fills on one layer are clipped
          against each other by priority, so they are disjoint; their total
          area cannot exceed the board outline. Compared against the Edge.Cuts
          BOUNDING BOX, which is a deliberate over-estimate (the real outline
          is a rounded rectangle with a slot) — so a violation is never a
          false positive, it is always real copper that cannot physically fit.

  Law C — every zone pours copper. Duplication's mirror image: a bad
          injection can DELETE fill just as easily as double it. Fixing the
          doubling initially introduced exactly that — three of four zones
          silently lost their fill, and laws A and B both passed it.

Exit code 0 = pass, 1 = fail.

Usage:
    python3 scripts/verify_zone_fill_sanity.py
    python3 scripts/verify_zone_fill_sanity.py --pcb path/to/board.kicad_pcb
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pcb_copper_graph import DEFAULT_PCB, blocks  # noqa: E402

_FAILURES = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        _FAILURES.append(name)
    return ok


def _read(path):
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return Path(path).read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"cannot decode {path}")


def board_bbox_area(text):
    """Bounding-box area of the Edge.Cuts outline, in mm².

    Bounding box, not true outline area: it over-estimates, so Law B can only
    fire on copper that genuinely cannot fit on the board.
    """
    xs, ys = [], []
    for m in re.finditer(
        r'\((?:gr_line|gr_arc)\b.*?\(layer "Edge\.Cuts"\)', text, re.DOTALL
    ):
        for a, b in re.findall(r"\((?:start|mid|end) ([\-0-9.]+) ([\-0-9.]+)\)", m.group(0)):
            xs.append(float(a))
            ys.append(float(b))
    if not xs:
        return None
    return (max(xs) - min(xs)) * (max(ys) - min(ys))


def parse_zone_fills(text):
    """[{net, layer, priority, islands: [[(x,y), ...], ...]}] straight from the file.

    Deliberately re-parses rather than reusing the cache: pcb_cache.py stores
    only a filled_polygon COUNT, and a doubled board has to be caught in the
    geometry itself.
    """
    zones = []
    for z in blocks(text, "(zone"):
        net_m = re.search(r'\(net_name "([^"]*)"\)', z)
        layer_m = re.search(r"\(layers? ([^)]*)\)", z)
        if not (net_m and layer_m):
            continue
        prio = re.search(r"\(priority (\d+)\)", z)
        islands = []
        for f in blocks(z, "(filled_polygon"):
            pts = [(float(a), float(b)) for a, b in
                   re.findall(r"\(xy ([\-0-9.]+) ([\-0-9.]+)\)", f)]
            if len(pts) >= 3:
                islands.append(pts)
        zones.append({
            "net": net_m.group(1),
            "layer": layer_m.group(1).strip('"'),
            "priority": int(prio.group(1)) if prio else 0,
            "islands": islands,
        })
    return zones


def _island_key(pts):
    """Canonical identity of an island, insensitive to vertex rotation.

    The filler may emit the same ring starting at a different vertex; a true
    duplicate is still the same closed loop. Rounded to 1 nm to absorb
    formatting round-trips.
    """
    ring = [(round(x, 6), round(y, 6)) for x, y in pts]
    if ring and ring[0] == ring[-1]:
        ring = ring[:-1]
    if not ring:
        return ()
    # Rotate so the lexicographically smallest vertex comes first.
    i = min(range(len(ring)), key=lambda k: ring[k])
    return tuple(ring[i:] + ring[:i])


def polygon_area(pts):
    """Absolute shoelace area in mm² — no shapely dependency needed."""
    a = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def law_a_no_duplicate_islands(zones):
    """No two islands in one zone may share an identical vertex set."""
    print("\n-- Law A: no duplicate fill islands --")
    ok = True
    for z in zones:
        seen = {}
        dupes = []
        for idx, pts in enumerate(z["islands"]):
            k = _island_key(pts)
            if k in seen:
                dupes.append((seen[k], idx, polygon_area(pts)))
            else:
                seen[k] = idx
        label = f"{z['net']} on {z['layer']} (prio {z['priority']})"
        detail = "; ".join(
            f"island {b} duplicates island {a} ({ar:.2f} mm²)" for a, b, ar in dupes
        )
        ok &= check(
            f"{label}: {len(z['islands'])} island(s) all unique",
            not dupes,
            detail,
        )
    return ok


def law_b_area_fits_board(zones, bbox_area):
    """Total poured copper per layer must fit inside the board outline."""
    print("\n-- Law B: poured area fits the board --")
    if bbox_area is None:
        return check("Board outline found on Edge.Cuts", False,
                     "no Edge.Cuts geometry — cannot bound poured area")

    per_layer = {}
    for z in zones:
        area = sum(polygon_area(p) for p in z["islands"])
        per_layer[z["layer"]] = per_layer.get(z["layer"], 0.0) + area

    ok = True
    for layer, area in sorted(per_layer.items()):
        pct = 100.0 * area / bbox_area
        fits = area <= bbox_area
        ok &= fits
        check(
            f"{layer}: {area:.2f} mm² poured <= {bbox_area:.2f} mm² board bbox",
            fits,
            "" if fits else f"{pct:.0f}% of the board — copper cannot physically fit "
                            f"(duplicated fill?)",
        )
    return ok


def law_c_every_zone_pours_copper(zones):
    """Every defined zone must produce at least one island.

    The mirror image of duplication: a bad injection can also DELETE fill.
    A zone that defines copper but pours nothing is a de-planed board — the
    exact failure mode that ships a dead ground plane. If a zone is ever
    legitimately clipped to nothing by a higher-priority zone, that deserves
    an explicit exception here, not a silent pass.
    """
    print("\n-- Law C: every zone pours copper --")
    ok = True
    for z in zones:
        label = f"{z['net']} on {z['layer']} (prio {z['priority']})"
        n = len(z["islands"])
        ok &= check(
            f"{label}: poured at least one island",
            n > 0,
            "" if n else "zone is defined but poured NOTHING — fill lost?",
        )
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pcb", default=str(DEFAULT_PCB), help="path to .kicad_pcb")
    args = ap.parse_args()

    text = _read(args.pcb)
    zones = parse_zone_fills(text)
    bbox_area = board_bbox_area(text)

    print("=" * 72)
    print("Zone-fill sanity (duplicate islands + poured area vs board outline)")
    print("=" * 72)
    print(f"  PCB          : {args.pcb}")
    print(f"  Zones        : {len(zones)} "
          f"({sum(len(z['islands']) for z in zones)} filled islands)")
    print(f"  Board bbox   : {bbox_area:.2f} mm²" if bbox_area else "  Board bbox   : n/a")

    if not zones:
        print("\nERROR: no zones found — refusing to pass vacuously.")
        sys.exit(1)
    if not any(z["islands"] for z in zones):
        print("\nERROR: zones are defined but nothing is filled — run the zone fill.")
        sys.exit(1)

    law_a_no_duplicate_islands(zones)
    law_b_area_fits_board(zones, bbox_area)
    law_c_every_zone_pours_copper(zones)

    print("\n" + "=" * 72)
    if _FAILURES:
        print(f"Results: FAIL — {len(_FAILURES)} check(s) failed")
        for f in _FAILURES:
            print(f"  - {f}")
        print("=" * 72)
        sys.exit(1)
    print("Results: PASS — fill geometry is sane")
    print("=" * 72)


if __name__ == "__main__":
    main()
