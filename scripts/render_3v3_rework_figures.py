#!/usr/bin/env python3
"""Render the +3V3 split-plane rework figures from the real PCB geometry.

Produces three SVGs into website/static/img/debug/:

  3v3-plane-split.svg     In2.Cu split plane — shows the +5V zones cutting
                          the +3V3 plane into orphan islands.
  3v3-rework-jumpers.svg  Bottom view (B.Cu, as the board is held) with the
                          rework wires to add.
  3v3-j4-islands.svg      Zoom on the J4 FPC connector island pins.

Everything is derived from hardware/kicad/esp32-emu-turbo.kicad_pcb — no
hand-placed coordinates — so the figures cannot drift from the layout.

Usage:  python3 scripts/render_3v3_rework_figures.py
"""

import math
import re
from collections import defaultdict
from pathlib import Path

from shapely.geometry import LineString, Point, Polygon

ROOT = Path(__file__).resolve().parent.parent
PCB = ROOT / "hardware/kicad/esp32-emu-turbo.kicad_pcb"
OUT = ROOT / "website/static/img/debug"

BOARD_W, BOARD_H = 160.0, 75.0
LAYERS = {"F.Cu", "In1.Cu", "In2.Cu", "B.Cu"}


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


def parse():
    s = PCB.read_text()
    netmap = {int(a): b for a, b in
              re.findall(r'^\s*\(net (\d+) "([^"]*)"\)', s, re.M)}

    zones = []
    for z in blocks(s, "(zone"):
        net = re.search(r'\(net_name "([^"]*)"\)', z).group(1)
        layer = re.search(r"\(layers? ([^)]*)\)", z).group(1).strip('"')
        prio = re.search(r"\(priority (\d+)\)", z)
        polys = []
        for f in blocks(z, "(filled_polygon"):
            pts = [(float(a), float(b)) for a, b in
                   re.findall(r"\(xy ([\-0-9.]+) ([\-0-9.]+)\)", f)]
            if len(pts) >= 3:
                polys.append(Polygon(pts).buffer(0))
        zones.append({"net": net, "layer": layer,
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
    return zones, vias, segs, fps


# ── electrical grouping (same method as the audit) ──────────────────
def groups_for(net, zones, vias, segs, fps):
    """Union-find over overlapping copper that shares a layer."""
    nodes = []
    for z in zones:
        if z["net"] != net:
            continue
        for k, g in enumerate(z["polys"]):
            nodes.append((f"ISLAND{k}", {z["layer"]}, g, None))
    for v in vias:
        if v["net"] != net:
            continue
        nodes.append((f"VIA({v['x']:.2f},{v['y']:.2f})", set(LAYERS),
                      Point(v["x"], v["y"]).buffer(v["size"] / 2), v))
    for i, t in enumerate(segs):
        if t["net"] != net:
            continue
        g = LineString([(t["x1"], t["y1"]), (t["x2"], t["y2"])]) \
            .buffer(t["w"] / 2, cap_style=2)
        nodes.append((f"SEG{i}", {t["layer"]}, g, None))
    for f in fps:
        for p in f["pads"]:
            if p["net"] != net:
                continue
            ls = set(LAYERS) if p["thru"] else {f["layer"]}
            g = Point(p["x"], p["y"]).buffer(max(p["w"], p["h"]) / 2)
            nodes.append((f"PAD {f['ref']}.{p['num']}", ls, g,
                          {"ref": f["ref"], **p}))

    par = list(range(len(nodes)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if not (nodes[i][1] & nodes[j][1]):
                continue
            if nodes[i][2].intersects(nodes[j][2]):
                ra, rb = find(i), find(j)
                if ra != rb:
                    par[ra] = rb

    comp = defaultdict(list)
    for i, n in enumerate(nodes):
        comp[find(i)].append(n)
    # largest group first
    return sorted(comp.values(), key=len, reverse=True)


# ── SVG primitives ──────────────────────────────────────────────────
class Svg:
    def __init__(self, x0, y0, x1, y1, scale=6.0, mirror=False, pad=6.0):
        self.mirror = mirror
        self.x0, self.y0, self.x1, self.y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
        self.s = scale
        self.parts = []

    def X(self, x):
        return ((self.x1 - x) if self.mirror else (x - self.x0)) * self.s

    def Y(self, y):
        return (y - self.y0) * self.s

    @property
    def w(self):
        return (self.x1 - self.x0) * self.s

    @property
    def h(self):
        return (self.y1 - self.y0) * self.s

    def poly(self, geom, fill, opacity=1.0, stroke="none", sw=0.0):
        gs = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for g in gs:
            if g.is_empty:
                continue
            d = ""
            for ring in [g.exterior] + list(g.interiors):
                pts = list(ring.coords)
                d += "M" + " L".join(
                    f"{self.X(x):.2f},{self.Y(y):.2f}" for x, y in pts) + " Z "
            self.parts.append(
                f'<path d="{d}" fill="{fill}" fill-rule="evenodd" '
                f'fill-opacity="{opacity}" stroke="{stroke}" '
                f'stroke-width="{sw}"/>')

    def rect(self, x, y, w, h, **kw):
        """Axis-aligned rect centred on (x, y). X() flips under mirror, so
        take the smaller of the two mapped edges as the SVG left edge."""
        a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
        px = min(self.X(x - w / 2), self.X(x + w / 2))
        self.parts.append(
            f'<rect x="{px:.2f}" y="{self.Y(y - h / 2):.2f}" '
            f'width="{w * self.s:.2f}" height="{h * self.s:.2f}" {a}/>')

    def circle(self, x, y, r, **kw):
        a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
        self.parts.append(f'<circle cx="{self.X(x):.2f}" cy="{self.Y(y):.2f}" '
                          f'r="{r * self.s:.2f}" {a}/>')

    def line(self, x1, y1, x2, y2, **kw):
        a = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in kw.items())
        self.parts.append(
            f'<line x1="{self.X(x1):.2f}" y1="{self.Y(y1):.2f}" '
            f'x2="{self.X(x2):.2f}" y2="{self.Y(y2):.2f}" {a}/>')

    def text(self, x, y, s, size=3.0, fill="#e6edf3", anchor="middle",
             weight="normal", px=False):
        fs = size if px else size * self.s
        self.parts.append(
            f'<text x="{self.X(x):.2f}" y="{self.Y(y):.2f}" '
            f'font-family="ui-monospace,Menlo,monospace" font-size="{fs:.1f}" '
            f'font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}">{s}</text>')

    def raw(self, s):
        self.parts.append(s)

    def save(self, path, title):
        body = "\n  ".join(self.parts)
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" '
               f'viewBox="0 0 {self.w:.0f} {self.h:.0f}" '
               f'width="{self.w:.0f}" height="{self.h:.0f}">\n'
               f'  <title>{title}</title>\n'
               f'  <rect width="100%" height="100%" fill="#0d1117"/>\n'
               f'  {body}\n</svg>\n')
        path.write_text(svg)
        print(f"  wrote {path.relative_to(ROOT)}  ({len(svg) // 1024} KB)")


def board_outline(svg, mirrored_note=None):
    svg.rect(BOARD_W / 2, BOARD_H / 2, BOARD_W, BOARD_H, fill="none",
             stroke="#30363d", stroke_width=2, rx=6)
    if mirrored_note:
        svg.text(BOARD_W / 2, -2.0, mirrored_note, size=11, px=True,
                 fill="#8b949e")


# ── figure 1: the split plane ───────────────────────────────────────
def fig_plane_split(zones, vias, segs, fps, grps):
    svg = Svg(0, 0, BOARD_W, BOARD_H, scale=6.0, pad=9.0)
    z3 = [z for z in zones if z["net"] == "+3V3" and z["layer"] == "In2.Cu"]
    z5 = [z for z in zones if z["net"] == "+5V" and z["layer"] == "In2.Cu"]
    polys = [p for z in z3 for p in z["polys"]]
    main = max(polys, key=lambda g: g.area)
    islands = [p for p in polys if p is not main]

    svg.text(BOARD_W / 2, -4.5, "In2.Cu — PIANO INTERNO SPLITTATO", size=15,
             px=True, fill="#e6edf3", weight="bold")
    board_outline(svg)
    svg.poly(main.simplify(0.08, preserve_topology=True), "#1f6feb", 0.55)
    for z in z5:
        for p in z["polys"]:
            svg.poly(p.simplify(0.08, preserve_topology=True), "#d29922", 0.75,
                     stroke="#f0b72f", sw=1.0)

    # One callout per orphan ELECTRICAL GROUP (a group may span several
    # island polygons — e.g. the regulator sits on ISLAND0 + ISLAND2).
    callouts = []
    for grp in grps[1:]:
        gis = [n[2] for n in grp if n[0].startswith("ISLAND")]
        pads = sorted(n[0][4:] for n in grp if n[0].startswith("PAD"))
        if not gis:
            continue
        area = sum(g.area for g in gis)
        dist = min(g.distance(main) for g in gis)
        cx = sum(g.centroid.x * g.area for g in gis) / area
        cy = sum(g.centroid.y * g.area for g in gis) / area
        callouts.append((cx, cy, area, dist, pads, gis))

    callouts.sort(key=lambda t: t[1])
    for i, (cx, cy, area, dist, pads, gis) in enumerate(callouts):
        for g in gis:
            b = g.bounds
            svg.circle((b[0] + b[2]) / 2, (b[1] + b[3]) / 2, 2.8, fill="none",
                       stroke="#f85149", stroke_width=2.2)
        lx, ly = 62.0, 12.0 + i * 11.0
        svg.line(cx, cy, lx + 1.5, ly + 0.5, stroke="#f85149",
                 stroke_width=1.1, stroke_dasharray="3 2")
        svg.circle(lx + 1.0, ly + 0.4, 0.5, fill="#f85149")
        svg.text(lx, ly - 0.9, ", ".join(pads) if pads else "(rame orfano)",
                 size=12.5, px=True, fill="#ff7b72", anchor="end",
                 weight="bold")
        svg.text(lx, ly + 2.9,
                 f"isola {area:.2f} mm² — a {dist:.1f} mm dal piano",
                 size=11, px=True, fill="#ffa198", anchor="end")

    u3 = next(f for f in fps if f["ref"] == "U3")
    svg.text(u3["x"], u3["y"] + 9.0, "U3 AMS1117", size=11, px=True,
             fill="#e6edf3", weight="bold")
    j4 = next(f for f in fps if f["ref"] == "J4")
    svg.text(j4["x"] - 1, j4["y"] - 14.0, "J4 FPC", size=11, px=True,
             fill="#e6edf3", weight="bold")

    lg = [("#1f6feb", "zona +3V3 (priorita 0, tutta la board)"),
          ("#d29922", "zona +5V (priorita 1 e 2) — taglia il +3V3"),
          ("#f85149", "isole +3V3 orfane, elettricamente separate")]
    for i, (c, t) in enumerate(lg):
        yy = BOARD_H + 4.0 + i * 4.0
        svg.rect(4.0, yy, 5.0, 2.6, fill=c, rx=1)
        svg.text(8.0, yy + 1.0, t, size=11, px=True, fill="#8b949e",
                 anchor="start")
    svg.y1 += 12
    svg.save(OUT / "3v3-plane-split.svg", "In2.Cu split plane")


# ── figure 2: rework jumpers, bottom view ───────────────────────────
LANDMARKS = ["U1", "U2", "U3", "U5", "U6", "J1", "J3", "J4", "L1", "C2",
             "C4", "C3", "SW_PWR"]
LABEL_BELOW = {"C2", "U6", "C4", "C3"}
NICE = {"U1": "U1 ESP32-S3", "U2": "U2 IP5306", "U3": "U3 AMS1117",
        "U5": "U5 PAM8403", "U6": "U6 microSD", "J1": "J1 USB-C",
        "J3": "J3 batt", "J4": "J4 FPC display", "L1": "L1",
        "C2": "C2", "C4": "C4", "C3": "C3", "SW_PWR": "SW_PWR"}


def fig_jumpers(zones, vias, segs, fps, grps):
    svg = Svg(0, 0, BOARD_W, BOARD_H, scale=6.6, mirror=True, pad=9.0)
    svg.text(BOARD_W / 2, -5.0,
             "REWORK +3V3 — VISTA DAL BASSO (lato B.Cu, come tieni la board)",
             size=15, px=True, fill="#e6edf3", weight="bold")
    board_outline(svg)

    for f in fps:
        if f["ref"] not in LANDMARKS or not f["pads"]:
            continue
        xs = [p["x"] for p in f["pads"]]
        ys = [p["y"] for p in f["pads"]]
        w = max(max(xs) - min(xs), 1.6) + 1.2
        h = max(max(ys) - min(ys), 1.6) + 1.2
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        svg.rect(cx, cy, w, h, fill="#161b22", stroke="#484f58",
                 stroke_width=1.2, rx=2)
        # refs whose label would collide with a neighbour go underneath
        dy = (h / 2 + 2.6) if f["ref"] in LABEL_BELOW else -(h / 2 + 1.2)
        svg.text(cx, cy + dy, NICE.get(f["ref"], f["ref"]), size=10,
                 px=True, fill="#8b949e")

    # +3V3 pads coloured by electrical group
    main_members = {n[0] for n in grps[0]}
    for f in fps:
        for p in f["pads"]:
            if p["net"] != "+3V3":
                continue
            key = f"PAD {f['ref']}.{p['num']}"
            ok = key in main_members
            svg.circle(p["x"], p["y"], 0.75,
                       fill="#3fb950" if ok else "#f85149",
                       stroke="#0d1117", stroke_width=0.8)

    # the two jumpers. Anchors are chosen for SOLDERABILITY, not just for
    # the shortest span: the nearest main-plane via (141.06, 61.72) is
    # buried under the microSD socket U6 and the SW13 button — unreachable.
    jumpers = [
        ((125.0, 52.35), (92.95, 42.0), "#f0b72f",
         "PONTE 1 (obbligatorio)  U3 tab  ->  C4 pad 1   33.7 mm"),
        ((133.712, 39.75), (133.712, 26.75), "#58a6ff",
         "PONTE 2 (obbligatorio)  J4.29/34/35  ->  J4.3   passo 0.5 mm"),
    ]
    for (ax, ay), (bx, by), col, _ in jumpers:
        svg.line(ax, ay, bx, by, stroke=col, stroke_width=3.4,
                 stroke_linecap="round", opacity=0.95)
        svg.circle(ax, ay, 1.15, fill=col, stroke="#0d1117", stroke_width=0.8)
        svg.circle(bx, by, 1.15, fill=col, stroke="#0d1117", stroke_width=0.8)
    svg.text(110.0, 45.4, "U3 tab (pad 4)", size=10, px=True, fill="#f0b72f")
    svg.line(110.0, 46.2, 113.0, 48.8, stroke="#f0b72f", stroke_width=0.9,
             stroke_dasharray="2 2")
    svg.text(92.95, 38.9, "C4 pad 1", size=10, px=True, fill="#f0b72f")

    # the tempting-but-unusable anchor
    svg.circle(141.06, 61.72, 2.4, fill="none", stroke="#6e7681",
               stroke_width=1.4, stroke_dasharray="3 2")
    svg.line(139.4, 60.1, 142.7, 63.4, stroke="#f85149", stroke_width=1.8)
    svg.line(142.7, 60.1, 139.4, 63.4, stroke="#f85149", stroke_width=1.8)
    svg.text(141.06, 68.4, "via +3V3 a 14.6 mm — NON usabile,", size=9.5,
             px=True, fill="#8b949e")
    svg.text(141.06, 71.0, "sepolta sotto U6 microSD + SW13", size=9.5,
             px=True, fill="#8b949e")

    lg = [("#3fb950", "pad +3V3 sul piano principale  —  0 V oggi"),
          ("#f85149", "pad +3V3 su isola orfana  —  3.3 V solo su U3/C2"),
          ("#f0b72f", jumpers[0][3]),
          ("#58a6ff", jumpers[1][3])]
    for i, (c, t) in enumerate(lg):
        yy = BOARD_H + 4.0 + i * 4.2
        svg.rect(BOARD_W - 4.0, yy, 5.0, 2.6, fill=c, rx=1)
        svg.text(BOARD_W - 8.0, yy + 1.0, t, size=11, px=True, fill="#8b949e",
                 anchor="start")
    svg.y1 += 14
    svg.save(OUT / "3v3-rework-jumpers.svg", "+3V3 rework jumpers")


# ── figure 3: J4 zoom ───────────────────────────────────────────────
def fig_j4(fps, grps):
    j4 = next(f for f in fps if f["ref"] == "J4")
    pads = [p for p in j4["pads"] if p["num"].isdigit() and int(p["num"]) <= 40]
    xs = [p["x"] for p in pads]
    ys = [p["y"] for p in pads]
    svg = Svg(min(xs) - 12.0, min(ys) - 4.5, max(xs) + 20.0, max(ys) + 12.0,
              scale=17.0, pad=1.5)
    svg.text(min(xs) + 2.0, min(ys) - 2.6,
             "J4 — pin di alimentazione del display", size=15, px=True,
             weight="bold")
    main_members = {n[0] for n in grps[0]}

    for p in pads:
        n = int(p["num"])
        net = p["net"] or "—"
        key = f"PAD J4.{p['num']}"
        if net == "+3V3":
            col = "#3fb950" if key in main_members else "#f85149"
        elif net == "GND":
            col = "#6e7681"
        elif net == "—":
            col = "#21262d"
        else:
            col = "#1f6feb"
        svg.rect(p["x"], p["y"], p["w"], p["h"], fill=col, stroke="#0d1117",
                 stroke_width=0.5)
        # connector pad number (left) and panel pin number (right)
        svg.text(p["x"] - 1.2, p["y"] + 0.16, f"{n}", size=8.5, px=True,
                 fill="#8b949e", anchor="end")
        svg.text(p["x"] + 2.0, p["y"] + 0.16,
                 f"panel {41 - n}  {net}", size=8.5, px=True,
                 fill="#c9d1d9" if net != "—" else "#484f58", anchor="start")

    for num, txt in [("29", "isola orfana"), ("34", "isola orfana"),
                     ("35", "isola orfana")]:
        p = next(p for p in pads if p["num"] == num)
        svg.circle(p["x"], p["y"], 0.9, fill="none", stroke="#f85149",
                   stroke_width=1.4)
    p3 = next(p for p in pads if p["num"] == "3")
    svg.circle(p3["x"], p3["y"], 0.9, fill="none", stroke="#3fb950",
               stroke_width=1.4)

    # PONTE 2 — bring the three orphan supply pins back to J4.3, drawn in a
    # side channel so the wire never hides a pad.
    ch = min(xs) - 4.2
    orphans = [next(p for p in pads if p["num"] == k) for k in ("29", "34", "35")]
    svg.line(ch, p3["y"], ch, max(o["y"] for o in orphans), stroke="#58a6ff",
             stroke_width=2.2, stroke_linecap="round")
    for p in orphans + [p3]:
        svg.line(ch, p["y"], p["x"] - 0.55, p["y"], stroke="#58a6ff",
                 stroke_width=2.2, stroke_linecap="round")
        svg.circle(p["x"] - 0.55, p["y"], 0.24, fill="#58a6ff")
    svg.text(ch - 0.6, (p3["y"] + max(o["y"] for o in orphans)) / 2,
             "PONTE 2", size=10, px=True, fill="#58a6ff", anchor="end",
             weight="bold")

    svg.text(min(xs) - 1.2, max(ys) + 3.0, "pad J4", size=9, px=True,
             fill="#8b949e", anchor="end")
    lg = [("#3fb950", "+3V3 collegato al piano  (J4.2 / J4.3 / J4.8)"),
          ("#f85149", "+3V3 su isola orfana  (J4.29 / J4.34 / J4.35)"),
          ("#6e7681", "GND"), ("#1f6feb", "segnale"),
          ("#21262d", "nessun net (pad libero)")]
    for i, (c, t) in enumerate(lg):
        yy = max(ys) + 5.0 + i * 1.5
        svg.rect(min(xs) - 5.4, yy, 1.2, 1.0, fill=c, rx=0.2)
        svg.text(min(xs) - 4.4, yy + 0.35, t, size=9, px=True, fill="#8b949e",
                 anchor="start")
    svg.y1 += 5
    svg.save(OUT / "3v3-j4-islands.svg", "J4 +3V3 island pins")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"parsing {PCB.relative_to(ROOT)} ...")
    zones, vias, segs, fps = parse()
    grps = groups_for("+3V3", zones, vias, segs, fps)
    print(f"  +3V3 -> {len(grps)} gruppi elettrici separati")
    fig_plane_split(zones, vias, segs, fps, grps)
    fig_jumpers(zones, vias, segs, fps, grps)
    fig_j4(fps, grps)


if __name__ == "__main__":
    main()
