#!/usr/bin/env python3
"""Zone-aware copper graph — what the fabricated board is actually connected to.

Provides:
  parse_copper(pcb_path)      — zones (with filled_polygon islands), vias,
                                track segments and pads, as raw geometry
  groups_for(net, geom)       — union-find over every piece of copper on a
                                net; returns the ELECTRICAL groups, largest
                                first
  group_pads / group_islands / group_area / group_distance — reporting
                                helpers for describing an orphan group

Why this exists
---------------
Every other connectivity check in this repo assumed "the net has a pour zone,
therefore the zone stitches it together". That assumption is false when the
zone is itself split. On PCB v1 the ``In2.Cu`` ``+3V3`` zone (priority 0,
whole board) was carved up by two higher-priority ``+5V`` zones; ``+3V3``
resolved into 4 electrically separate groups, the AMS1117 fed a 4.92 mm²
orphan island, and the board was dead. Both the DRC baseline and
``verify_net_connectivity.py`` skipped exactly this case.

See ``website/docs/rework/incident-3v3-split-plane.md``.

This module is the single implementation of the detector. It is imported by:
  scripts/verify_power_net_integrity.py   — the gate
  scripts/verify_net_connectivity.py      — zone-filled nets
  scripts/render_3v3_rework_figures.py    — the incident figures

Method
------
Nodes = zone filled_polygon islands ∪ vias ∪ track segments ∪ pads.
Two nodes are joined when they share at least one copper layer AND their
geometries intersect. Connected components of that graph are the electrical
groups.

Conservative by construction
----------------------------
Pads are modelled as a circle of radius ``max(w, h) / 2`` — an
OVER-approximation of the real pad rectangle, and vias/through-hole pads span
all four copper layers. Over-approximating copper can only MERGE groups that
are really separate; it can never split a group that is really joined.
Therefore "more than one group" is never a geometric false positive: a
reported split is a real open circuit.

Validated by control: on the unfixed PCB v1 this returns GND → 1 group,
+5V → 1 group, +3V3 → 4 groups.
"""

import math
import re
from collections import defaultdict, namedtuple
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree

DEFAULT_PCB = (Path(__file__).resolve().parent.parent
               / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb")

#: Every copper layer of the 4-layer stackup. Vias and through-hole pads are
#: treated as present on all of them.
LAYERS = frozenset({"F.Cu", "In1.Cu", "In2.Cu", "B.Cu"})

#: One piece of copper on a net.
#:   label  — "ISLAND<k>" | "VIA(x,y)" | "SEG<i>" | "PAD <ref>.<num>"
#:   layers — set of copper layers the piece lives on
#:   geom   — shapely geometry in board mm
#:   meta   — source dict (via / pad), or None
CopperNode = namedtuple("CopperNode", "label layers geom meta")

#: Raw copper geometry of a board. Unpacks as (zones, vias, segments, pads).
CopperGeometry = namedtuple("CopperGeometry", "zones vias segments footprints")


# ── S-expression helpers ────────────────────────────────────────────

def blocks(src, tok):
    """Return every balanced-paren block starting with `tok`."""
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


# ── Parsing ─────────────────────────────────────────────────────────

def parse_copper(pcb_path=None):
    """Parse a .kicad_pcb into a CopperGeometry.

    Unlike scripts/pcb_cache.py this parses zone ``filled_polygon`` blocks —
    the actual poured copper, island by island. That is the whole point: the
    zone OUTLINE says "the whole board"; the FILL says which parts of the
    board the higher-priority zones left behind.
    """
    path = Path(pcb_path) if pcb_path else DEFAULT_PCB
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            s = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise UnicodeDecodeError("utf-8", b"", 0, 1, f"cannot decode {path}")

    netmap = {int(a): b for a, b in
              re.findall(r'^\s*\(net (\d+) "([^"]*)"\)', s, re.M)}

    zones = []
    for z in blocks(s, "(zone"):
        net_m = re.search(r'\(net_name "([^"]*)"\)', z)
        layer_m = re.search(r"\(layers? ([^)]*)\)", z)
        if not (net_m and layer_m):
            continue
        prio = re.search(r"\(priority (\d+)\)", z)
        polys = []
        for f in blocks(z, "(filled_polygon"):
            pts = [(float(a), float(b)) for a, b in
                   re.findall(r"\(xy ([\-0-9.]+) ([\-0-9.]+)\)", f)]
            if len(pts) >= 3:
                polys.append(Polygon(pts).buffer(0))
        zones.append({"net": net_m.group(1),
                      "layer": layer_m.group(1).strip('"'),
                      "priority": int(prio.group(1)) if prio else 0,
                      "polys": polys})

    vias = []
    for v in blocks(s, "(via"):
        nm = re.search(r"\(net (\d+)\)", v)
        at = re.search(r"\(at ([\-0-9.]+) ([\-0-9.]+)\)", v)
        sz = re.search(r"\(size ([\-0-9.]+)\)", v)
        if not (nm and at):
            continue
        vias.append({"net": netmap.get(int(nm.group(1)), ""),
                     "x": float(at.group(1)), "y": float(at.group(2)),
                     "size": float(sz.group(1)) if sz else 0.6})

    segs = []
    for t in blocks(s, "(segment"):
        nm = re.search(r"\(net (\d+)\)", t)
        st = re.search(r"\(start ([\-0-9.]+) ([\-0-9.]+)\)", t)
        en = re.search(r"\(end ([\-0-9.]+) ([\-0-9.]+)\)", t)
        w = re.search(r"\(width ([\-0-9.]+)\)", t)
        ly = re.search(r'\(layer "([^"]+)"\)', t)
        if not (nm and st and en):
            continue
        segs.append({"net": netmap.get(int(nm.group(1)), ""),
                     "x1": float(st.group(1)), "y1": float(st.group(2)),
                     "x2": float(en.group(1)), "y2": float(en.group(2)),
                     "w": float(w.group(1)) if w else 0.25,
                     "layer": ly.group(1) if ly else "F.Cu"})

    fps = []
    for f in blocks(s, "(footprint "):
        rm = re.search(r'"Reference" "([^"]+)"', f)
        if not rm:
            continue
        hdr = f[:f.find("(property")] if "(property" in f else f[:300]
        at = re.search(r"\(at ([\-0-9.]+) ([\-0-9.]+)(?:\s+([\-0-9.]+))?\)", hdr)
        ly = re.search(r'\(layer "([^"]+)"\)', hdr)
        if not at:
            continue
        fx, fy = float(at.group(1)), float(at.group(2))
        ang = float(at.group(3) or 0)
        pads = []
        for p in blocks(f, '(pad "'):
            # mounting holes / shield pads can carry an empty pad number
            num = re.match(r'\(pad "([^"]*)"', p).group(1)
            pa = re.search(r"\(at ([\-0-9.]+) ([\-0-9.]+)", p)
            sz = re.search(r"\(size ([\-0-9.]+) ([\-0-9.]+)\)", p)
            nm = re.search(r'\(net (\d+) "([^"]*)"\)', p)
            if not pa:
                continue
            # Pads in the .kicad_pcb are already pre-rotated and mirrored
            # (footprints.get_pads: generate -> pre-rotate -> mirror), so
            # only the footprint header angle (usually 0) still applies.
            lx, ly_ = float(pa.group(1)), float(pa.group(2))
            if ang % 360:
                r = math.radians(ang)
                lx, ly_ = (lx * math.cos(r) - ly_ * math.sin(r),
                           lx * math.sin(r) + ly_ * math.cos(r))
            w, h = ((float(sz.group(1)), float(sz.group(2)))
                    if sz else (0.5, 0.5))
            thru = "thru_hole" in p[:60] or "np_thru" in p[:60]
            pads.append({"num": num, "x": fx + lx, "y": fy + ly_,
                         "w": w, "h": h,
                         "net": nm.group(2) if nm else "", "thru": thru})
        fps.append({"ref": rm.group(1), "x": fx, "y": fy,
                    "layer": ly.group(1) if ly else "F.Cu", "pads": pads})

    return CopperGeometry(zones, vias, segs, fps)


# ── Node construction ───────────────────────────────────────────────

def nodes_for(net, geom):
    """Every piece of copper carrying `net`, as CopperNode objects."""
    zones, vias, segs, fps = geom
    nodes = []
    for z in zones:
        if z["net"] != net:
            continue
        for k, g in enumerate(z["polys"]):
            nodes.append(CopperNode(f"ISLAND{k}", {z["layer"]}, g, None))
    for v in vias:
        if v["net"] != net:
            continue
        nodes.append(CopperNode(f"VIA({v['x']:.2f},{v['y']:.2f})", set(LAYERS),
                                Point(v["x"], v["y"]).buffer(v["size"] / 2), v))
    for i, t in enumerate(segs):
        if t["net"] != net:
            continue
        g = (LineString([(t["x1"], t["y1"]), (t["x2"], t["y2"])])
             .buffer(t["w"] / 2, cap_style=2))
        nodes.append(CopperNode(
            f"SEG{i} {t['layer']}({t['x1']:.2f},{t['y1']:.2f})-"
            f"({t['x2']:.2f},{t['y2']:.2f})", {t["layer"]}, g, t))
    for f in fps:
        for p in f["pads"]:
            if p["net"] != net:
                continue
            layers = set(LAYERS) if p["thru"] else {f["layer"]}
            g = Point(p["x"], p["y"]).buffer(max(p["w"], p["h"]) / 2)
            nodes.append(CopperNode(f"PAD {f['ref']}.{p['num']}", layers, g,
                                    {"ref": f["ref"], **p}))
    return nodes


# ── Union-find grouping ─────────────────────────────────────────────

def group_nodes(nodes):
    """Union-find over overlapping copper that shares a layer.

    Returns the connected components, largest (most members) first.
    """
    if not nodes:
        return []

    parent = list(range(len(nodes)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # STRtree prunes the O(n^2) pair sweep down to bbox-overlapping candidates.
    # The exact intersects() test still decides every edge, so the result is
    # identical to the naive double loop — just orders of magnitude faster on
    # a full-board GND pour.
    geoms = [n.geom for n in nodes]
    tree = STRtree(geoms)
    for i, node in enumerate(nodes):
        for j in tree.query(node.geom):
            j = int(j)
            if j <= i:
                continue
            if not (node.layers & nodes[j].layers):
                continue
            if node.geom.intersects(nodes[j].geom):
                union(i, j)

    comp = defaultdict(list)
    for i, n in enumerate(nodes):
        comp[find(i)].append(n)
    return sorted(comp.values(), key=len, reverse=True)


def groups_for(net, geom):
    """Electrical groups of `net` on the board, largest first.

    len(groups) > 1  ⇒  the net is an OPEN CIRCUIT on the fabricated board.
    """
    return group_nodes(nodes_for(net, geom))


# ── Reporting helpers ───────────────────────────────────────────────

def group_pads(group):
    """Sorted "REF.PAD" strings for every pad in the group."""
    return sorted(n.label[4:] for n in group if n.label.startswith("PAD "))


def group_islands(group):
    """The zone filled_polygon islands in the group."""
    return [n.geom for n in group if n.label.startswith("ISLAND")]


def group_area(group):
    """Total poured-copper area of the group's zone islands, in mm²."""
    return sum(g.area for g in group_islands(group))


def _min_distance(geoms_a, geoms_b):
    """Minimum edge-to-edge distance in mm between two geometry sets.

    Degenerate (empty) geometries are skipped — a zero-length segment has no
    position to measure from. Returns NaN when either side has nothing
    measurable, so callers never print a fabricated number.
    """
    ga = [g for g in geoms_a if g is not None and not g.is_empty]
    gb = [g for g in geoms_b if g is not None and not g.is_empty]
    if not ga or not gb:
        return float("nan")
    tree = STRtree(gb)
    best = float("inf")
    for g in ga:
        # nearest() is exact, and cheap after the tree is built
        best = min(best, g.distance(gb[int(tree.nearest(g))]))
    return best


def group_distance(a, b):
    """Minimum edge-to-edge distance in mm between two groups' copper."""
    return _min_distance([n.geom for n in a], [n.geom for n in b])


def group_island_distance(a, b):
    """Minimum distance in mm between two groups' poured zone islands.

    Reported alongside group_distance because the two answer different
    questions: group_distance is "how far is the nearest copper of any kind"
    (how long a rework jumper would have to be if you could solder anywhere),
    while this is "how wide is the gap the pour failed to bridge".
    """
    return _min_distance(group_islands(a), group_islands(b))


# ── CLI ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    geom = parse_copper()
    nets = sys.argv[1:] or ["GND", "+5V", "+3V3"]
    for net in nets:
        grps = groups_for(net, geom)
        print(f"{net:>8} -> {len(grps)} group(s)")
        for k, g in enumerate(grps):
            pads = group_pads(g)
            print(f"           [{k}] {len(g):4d} item(s), "
                  f"{group_area(g):8.2f} mm² poured, "
                  f"pads: {', '.join(pads) if pads else '(none)'}")
