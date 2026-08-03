#!/usr/bin/env python3
"""Fail on signals whose reference plane changes underneath them mid-run.

The gap this closes
-------------------
Every high-speed current on this board travels as a loop: out along the trace,
back along the nearest plane, directly under the trace. Nothing in the repo
checks that the plane under a trace is continuous. `verify_power_net_integrity`
asks whether each plane net is one piece of copper — a question about the
PLANE. This asks a question about the TRACE: does the copper it is referenced
to change identity, or vanish, somewhere along its length.

That matters here specifically because of the stackup:

    F.Cu    signal      -- references In1.Cu
    In1.Cu  solid GND
    In2.Cu  power       -- SPLIT between +3V3 and two +5V zones
    B.Cu    signal      -- references In2.Cu

Most of the LCD and SD routing lives on B.Cu, so most of the fast signals on
this board reference the SPLIT plane. When a B.Cu trace crosses from over the
+3V3 zone to over a +5V zone, its return current arrives at the seam and has
nowhere to go. It detours around the whole split — a loop that can be tens of
millimetres across where the intended loop was 0.2 mm tall. That loop radiates,
picks up, and adds inductance in series with the signal's return, which shows up
as ringing and ground bounce rather than as a broken connection. No continuity
check can see it: the board is perfectly connected and behaves badly.

What is measured
----------------
Sample every signal-net trace centreline at SAMPLE_STEP_MM and ask, for each
sample, which poured zone island sits underneath it on the reference layer.
Two things are then discontinuities:

  (a) SEAM — the last island seen and the current island belong to different
      nets. This is the +3V3 -> +5V case above. It is detected across an
      intervening void, because a seam between two adjacent zones IS a void
      one clearance wide; requiring the two islands to be sample-adjacent
      would miss every real seam.

  (b) VOID — a continuous run of >= VOID_RUN_MIN_MM with no copper underneath
      at all, that is NOT explained by a clearance ring around a via or a
      through-hole.

Why voids need attribution instead of a bigger threshold
--------------------------------------------------------
Zone fill legitimately leaves holes: every via and through-hole pad punches an
antipad through the planes it does not connect to. On this board the zone
clearance is 0.5 mm, so a 0.9 mm via leaves a 1.9 mm hole and a 2.12 mm
through-hole pad leaves a 3.12 mm hole. A pure length threshold therefore
cannot separate "normal antipad" from "the plane is missing here": any
threshold above 3.12 mm would also wave through a real 3 mm plane gap, and
anything below it would fire on ordinary vias.

So the threshold and the attribution do different jobs. VOID_RUN_MIN_MM is a
noise floor; the antipad attribution is what decides whether a void is
expected. A void that no via or hole can account for is a genuine gap in the
reference plane however wide it is.

What this gate does NOT cover
-----------------------------
A trace changing LAYER changes reference plane by definition (F.Cu references
GND, B.Cu references the power plane), which needs a stitching capacitor or a
ground via at the transition. That is a different check and
`verify_usb_impedance.py` already enforces it for the USB pair. Discontinuities
here are measured within one segment, so a seam falling exactly on a corner
between two collinear segments is attributed to whichever segment spans it.

Usage:
    python3 scripts/verify_reference_plane.py
    python3 scripts/verify_reference_plane.py --selftest
    Exit 0 = pass, 1 = failure, 2 = tooling/environment error
"""

import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pcb_cache import load_cache  # noqa: E402
from pcb_copper_graph import DEFAULT_PCB, parse_copper  # noqa: E402

# ── Stackup law ──────────────────────────────────────────────────────

# Which plane carries the return current for a trace on each signal layer.
# JLC04161H-7628: F.Cu / In1.Cu / In2.Cu / B.Cu, with 0.21 mm of prepreg
# between each outer layer and its adjacent inner one and a 1.065 mm core in
# the middle. The adjacent plane is 5x closer than the far one, so the return
# current — which follows the path of least inductance, not least resistance —
# is overwhelmingly on the adjacent layer.
REFERENCE_LAYER = {
    "F.Cu": "In1.Cu",
    "B.Cu": "In2.Cu",
}

# ── Sampling ─────────────────────────────────────────────────────────

# Distance between centreline samples, mm. Must be small enough that (1) a
# void of VOID_RUN_MIN_MM always yields several samples, and (2) a seam is
# never stepped over: the narrowest possible gap between two adjacent zones is
# one zone clearance, 0.5 mm on this board, so 0.25 mm guarantees at least one
# sample lands inside any seam. Halving this doubles runtime and changes no
# verdict on the current board.
SAMPLE_STEP_MM = 0.25

# Void run length below which an unattributed void is treated as fill noise
# rather than a finding. KiCad's zone filler rounds corners and enforces a
# minimum fill thickness, so a sample track clipping the corner of a legitimate
# polygon can register a fraction of a millimetre of "no copper". 1.0 mm is
# four samples wide and comfortably above that, while being far below the
# smallest plane gap anyone would draw on purpose.
VOID_RUN_MIN_MM = 1.0

# Extra slack added to a computed antipad radius before it is allowed to
# excuse a void. Covers the zone filler's min_thickness rounding and the
# polygon approximation of the circular clearance ring.
ANTIPAD_MARGIN_MM = 0.15

# Fallback if the board file does not state a zone clearance. The real value
# is read from the .kicad_pcb at runtime by read_zone_clearance() so this
# constant cannot drift away from the board.
DEFAULT_ZONE_CLEARANCE_MM = 0.5

# Ray-cast acceleration: height of one horizontal edge band, mm. Only affects
# speed, never a verdict.
BAND_MM = 0.5


# ── Net classification ───────────────────────────────────────────────

# Excluded from analysis: these ARE the planes and rails. Asking whether the
# +3V3 plane has a continuous reference under itself is not a question.
QUIET_DC_NETS = {
    "GND":      "the reference plane itself",
    "+3V3":     "plane net — this gate measures signals referenced TO it",
    "+5V":      "plane net — this gate measures signals referenced TO it",
    "VBUS":     "USB input rail, DC — no return-loop area to speak of",
    "VBUS_IN":  "USB input rail upstream of the RPP FET, DC",
    "BAT+":     "battery rail, DC",
    "BAT_IN":   "battery rail upstream of the RPP FET, DC",
    "":         "unassigned copper carries no signal",
}

LOGICAL_NET = {
    "USB_DP_MCU": "USB_D+",
    "USB_DM_MCU": "USB_D-",
}

# Nets for which a broken return path is a FAIL. Same critical set as
# verify_crosstalk.py plus the whole LCD data bus: crosstalk between bus
# members is harmless because they are latched together, but a bus member with
# a broken return path is not — it rings and it radiates, and unlike crosstalk
# that is not cancelled by being sampled on a common edge.
CRITICAL_NETS = {
    "LCD_WR", "SD_CLK", "USB_D+", "USB_D-", "I2S_DOUT",
} | {f"LCD_D{i}" for i in range(8)}

# Documented exceptions: net -> why a discontinuity there is acceptable.
# Empty on purpose. The FPC connector slot cuts every plane, and a critical
# net crossing it is a genuine finding, not a licence to add an entry here.
ALLOWED = {}


def logical(name):
    return LOGICAL_NET.get(name, name)


# ── Zone clearance, read from the board ──────────────────────────────

def read_zone_clearance(pcb_path=None):
    """Widest zone pad clearance declared in the board file, in mm.

    Read rather than hard-coded: the antipad radii this gate uses to excuse
    voids are only correct while they match the clearance the zone filler
    actually used.
    """
    path = str(pcb_path or DEFAULT_PCB)
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            text = open(path, encoding=enc).read()
            break
        except UnicodeDecodeError:
            continue
    else:
        return None
    vals = [float(v) for v in
            re.findall(r"\(connect_pads\s*\(clearance\s+([\d.]+)\)", text)]
    vals += [float(v) for v in
             re.findall(r"\(zone_connect\s+\d+\)\s*\(clearance\s+([\d.]+)\)", text)]
    return max(vals) if vals else None


# ── Island geometry ──────────────────────────────────────────────────

class Island:
    """One poured zone polygon, with a banded edge index for ray casting."""

    __slots__ = ("net", "layer", "priority", "bbox", "bands", "band0", "nbands")

    def __init__(self, net, layer, priority, rings):
        self.net = net
        self.layer = layer
        self.priority = priority

        edges = []
        xs, ys = [], []
        for ring in rings:
            for k in range(len(ring) - 1):
                x1, y1 = ring[k]
                x2, y2 = ring[k + 1]
                if y1 != y2:  # horizontal edges never cross a horizontal ray
                    edges.append((x1, y1, x2, y2))
                xs.append(x1)
                ys.append(y1)
        if not xs:
            self.bbox = (0.0, 0.0, -1.0, -1.0)
            self.bands, self.band0, self.nbands = [], 0.0, 0
            return
        self.bbox = (min(xs), min(ys), max(xs), max(ys))

        self.band0 = self.bbox[1]
        self.nbands = max(1, int((self.bbox[3] - self.band0) / BAND_MM) + 1)
        self.bands = [[] for _ in range(self.nbands)]
        for e in edges:
            lo = int((min(e[1], e[3]) - self.band0) / BAND_MM)
            hi = int((max(e[1], e[3]) - self.band0) / BAND_MM)
            for b in range(max(0, lo), min(self.nbands - 1, hi) + 1):
                self.bands[b].append(e)

    def contains(self, px, py):
        """Even-odd point-in-polygon over exterior and interior rings.

        Even-odd across ALL rings is exactly right for a filled zone: a point
        inside a hole crosses the exterior once and the hole boundary once, an
        even count, so it reads as outside the copper.
        """
        x0, y0, x1, y1 = self.bbox
        if px < x0 or px > x1 or py < y0 or py > y1:
            return False
        b = int((py - self.band0) / BAND_MM)
        if b < 0 or b >= self.nbands:
            return False
        inside = False
        for ex1, ey1, ex2, ey2 in self.bands[b]:
            if (ey1 > py) != (ey2 > py):
                xint = ex1 + (py - ey1) * (ex2 - ex1) / (ey2 - ey1)
                if xint > px:
                    inside = not inside
        return inside


def _rings(poly):
    """Exterior + interior coordinate rings of a shapely polygon."""
    out = [list(poly.exterior.coords)]
    out.extend(list(r.coords) for r in poly.interiors)
    return out


def build_islands(geom):
    """layer -> [Island], for the reference layers only."""
    wanted = set(REFERENCE_LAYER.values())
    by_layer = {layer: [] for layer in wanted}
    for z in geom.zones:
        if z["layer"] not in wanted:
            continue
        for poly in z["polys"]:
            if poly.is_empty:
                continue
            parts = (list(poly.geoms) if poly.geom_type == "MultiPolygon"
                     else [poly])
            for part in parts:
                by_layer[z["layer"]].append(
                    Island(z["net"], z["layer"], z["priority"], _rings(part)))
    return by_layer


def island_at(islands, px, py):
    """The island covering (px, py), highest zone priority first, or None."""
    best = None
    for isl in islands:
        if isl.contains(px, py):
            if best is None or isl.priority > best.priority:
                best = isl
    return best


# ── Antipad keepouts ─────────────────────────────────────────────────

def build_keepouts(cache, clearance):
    """Circles where the planes are legitimately absent: (x, y, radius).

    Every via and every drilled pad punches a clearance ring through the planes
    it does not connect to. A void that lies entirely inside one of these is
    the zone filler doing its job.
    """
    out = []
    for v in cache["vias"]:
        out.append((v["x"], v["y"],
                    v["size"] / 2.0 + clearance + ANTIPAD_MARGIN_MM))
    seen = set()
    for p in cache["pads"]:
        if p["type"] == "smd" or p["drill"] <= 0.0:
            continue
        key = (p["ref"], p["num"])
        if key in seen:
            continue
        seen.add(key)
        # Through-hole pads carve the full pad outline out of the inner
        # layers, not just the drill, so the ring is measured from the pad.
        out.append((p["x"], p["y"],
                    max(p["w"], p["h"]) / 2.0 + clearance + ANTIPAD_MARGIN_MM))
    return out


def index_keepouts(keepouts, cell=5.0):
    """Grid index so the void attribution stays linear in sample count."""
    grid = {}
    for k in keepouts:
        x, y, r = k
        for cx in range(int((x - r) // cell), int((x + r) // cell) + 1):
            for cy in range(int((y - r) // cell), int((y + r) // cell) + 1):
                grid.setdefault((cx, cy), []).append(k)
    return grid, cell


def covered_by_keepout(index, px, py):
    grid, cell = index
    for x, y, r in grid.get((int(px // cell), int(py // cell)), ()):
        if (px - x) ** 2 + (py - y) ** 2 <= r * r:
            return True
    return False


# ── Scan ─────────────────────────────────────────────────────────────

def scan_segment(seg, islands, keepout_index):
    """Reference discontinuities under one segment. Returns a findings list."""
    dx = seg["x2"] - seg["x1"]
    dy = seg["y2"] - seg["y1"]
    length = math.hypot(dx, dy)
    if length < 1e-9:
        return []
    n = max(1, int(length / SAMPLE_STEP_MM))
    ux, uy = dx / length, dy / length

    findings = []
    last_net = None          # last island net actually seen
    void_start = None        # arc position where the current void run began
    void_attributed = True   # every sample of the current void inside a keepout
    void_at = None

    for k in range(n + 1):
        t = min(length, k * length / n)
        px, py = seg["x1"] + ux * t, seg["y1"] + uy * t
        isl = island_at(islands, px, py)

        if isl is None:
            if void_start is None:
                void_start, void_attributed, void_at = t, True, (px, py)
            if not covered_by_keepout(keepout_index, px, py):
                void_attributed = False
            continue

        # Landed on copper — close any void run first.
        if void_start is not None:
            run = t - void_start
            if run >= VOID_RUN_MIN_MM and not void_attributed:
                findings.append({"kind": "void", "run_mm": run,
                                 "at": void_at, "detail": "no reference copper"})
            void_start = None

        if last_net is not None and isl.net != last_net:
            findings.append({
                "kind": "seam", "run_mm": 0.0, "at": (px, py),
                "detail": f"reference changes {last_net} -> {isl.net}"})
        last_net = isl.net

    if void_start is not None:
        run = length - void_start
        if run >= VOID_RUN_MIN_MM and not void_attributed:
            findings.append({"kind": "void", "run_mm": run, "at": void_at,
                             "detail": "no reference copper"})
    return findings


def analyze(cache, geom, clearance):
    """Per-net reference-plane findings. Returns (results, stats)."""
    net_name = {n["id"]: n["name"] for n in cache["nets"]}
    islands = build_islands(geom)
    keepout_index = index_keepouts(build_keepouts(cache, clearance))

    per_net = {}
    scanned = 0
    total_mm = 0.0
    for s in cache["segments"]:
        raw = net_name.get(s["net"], "")
        if raw in QUIET_DC_NETS:
            continue
        ref = REFERENCE_LAYER.get(s["layer"])
        if ref is None:
            continue
        name = logical(raw)
        scanned += 1
        total_mm += math.hypot(s["x2"] - s["x1"], s["y2"] - s["y1"])
        found = scan_segment(s, islands[ref], keepout_index)
        if not found:
            continue
        rec = per_net.setdefault(name, {
            "net": name, "seams": 0, "voids": 0,
            "worst_void_mm": 0.0, "worst_void_at": None,
            "seam_at": None, "seam_detail": "", "layers": set()})
        rec["layers"].add(s["layer"])
        for f in found:
            if f["kind"] == "seam":
                rec["seams"] += 1
                if rec["seam_at"] is None:
                    rec["seam_at"] = f["at"]
                    rec["seam_detail"] = f["detail"]
            else:
                rec["voids"] += 1
                if f["run_mm"] > rec["worst_void_mm"]:
                    rec["worst_void_mm"] = f["run_mm"]
                    rec["worst_void_at"] = f["at"]

    results = []
    for rec in per_net.values():
        rec["critical"] = rec["net"] in CRITICAL_NETS
        rec["allowed"] = ALLOWED.get(rec["net"])
        if rec["allowed"]:
            rec["verdict"] = "NOTE"
        else:
            rec["verdict"] = "FAIL" if rec["critical"] else "WARN"
        results.append(rec)
    results.sort(key=lambda r: (not r["critical"], -r["seams"],
                                -r["worst_void_mm"]))

    return results, {
        "segments_scanned": scanned,
        "trace_mm": total_mm,
        "samples": int(total_mm / SAMPLE_STEP_MM),
        "islands": {k: len(v) for k, v in islands.items()},
        "clearance_mm": clearance,
    }


# ── Self-test ────────────────────────────────────────────────────────

def _square(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def selftest():
    fails = []
    total = 0

    def check(name, got, want):
        nonlocal total
        total += 1
        ok = got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              f"{'' if ok else f'  got {got!r}, want {want!r}'}")
        if not ok:
            fails.append(name)

    # Case 1 — plain square island, even-odd containment.
    sq = Island("A", "In2.Cu", 0, [_square(0, 0, 10, 10)])
    check("case1 point inside the square", sq.contains(5.0, 5.0), True)
    check("case1 point outside the square", sq.contains(15.0, 5.0), False)
    check("case1 point outside in y", sq.contains(5.0, 20.0), False)

    # Case 2 — square with a 4x4 hole in the middle. Even-odd must report the
    # hole as NOT copper: the ray crosses the exterior once and the hole once.
    holed = Island("A", "In2.Cu", 0,
                   [_square(0, 0, 10, 10), _square(3, 3, 7, 7)])
    check("case2 point in the ring is copper", holed.contains(1.5, 5.0), True)
    check("case2 point in the hole is not copper",
          holed.contains(5.0, 5.0), False)

    # Case 3 — seam. Two islands on different nets, 0.5 mm apart, with a trace
    # running from one to the other. Exactly one seam crossing, no void
    # finding (the 0.5 mm gap is below the 1.0 mm void floor).
    a = Island("+3V3", "In2.Cu", 0, [_square(0, 0, 10, 10)])
    b = Island("+5V", "In2.Cu", 1, [_square(10.5, 0, 20, 10)])
    seg = {"x1": 2.0, "y1": 5.0, "x2": 18.0, "y2": 5.0}
    found = scan_segment(seg, [a, b], index_keepouts([]))
    check("case3 one seam crossing", sum(1 for f in found
                                         if f["kind"] == "seam"), 1)
    check("case3 no void finding for a 0.5 mm seam",
          sum(1 for f in found if f["kind"] == "void"), 0)
    check("case3 seam names both nets",
          found[0]["detail"], "reference changes +3V3 -> +5V")

    # Case 4 — a 3 mm gap between two islands of the SAME net is a void, not a
    # seam, and is reported because nothing accounts for it.
    c = Island("+3V3", "In2.Cu", 0, [_square(13.0, 0, 20, 10)])
    found = scan_segment(seg, [a, c], index_keepouts([]))
    check("case4 unexplained 3 mm gap is one void",
          sum(1 for f in found if f["kind"] == "void"), 1)
    check("case4 same-net gap raises no seam",
          sum(1 for f in found if f["kind"] == "seam"), 0)
    void = next(f for f in found if f["kind"] == "void")
    check("case4 void run is measured as 3 mm",
          round(void["run_mm"], 1), 3.0)

    # Case 5 — the same 3 mm gap, now covered by a keepout circle of radius
    # 2 mm at its centre, is an antipad and must be excused.
    found = scan_segment(seg, [a, c], index_keepouts([(11.5, 5.0, 2.0)]))
    check("case5 antipad-covered void is excused",
          sum(1 for f in found if f["kind"] == "void"), 0)

    # Case 6 — a trace entirely over one island has nothing to report.
    found = scan_segment({"x1": 1.0, "y1": 5.0, "x2": 9.0, "y2": 5.0},
                         [a], index_keepouts([]))
    check("case6 continuous reference is clean", found, [])

    print()
    print(f"Results: {total - len(fails)} checks passed, {len(fails)} failed")
    return 1 if fails else 0


# ── Main ─────────────────────────────────────────────────────────────

def main():
    try:
        cache = load_cache()
        geom = parse_copper()
    except Exception as exc:  # noqa: BLE001 — tooling failure, not a verdict
        print(f"  ERROR unable to parse the PCB: {exc}", file=sys.stderr)
        return 2

    clearance = read_zone_clearance()
    if clearance is None:
        print(f"  WARN  no zone clearance found in the board file; assuming "
              f"{DEFAULT_ZONE_CLEARANCE_MM} mm for antipad attribution")
        clearance = DEFAULT_ZONE_CLEARANCE_MM

    results, stats = analyze(cache, geom, clearance)

    print()
    print("── Reference plane continuity (signals crossing plane splits) ──")
    print()
    for sig, ref in sorted(REFERENCE_LAYER.items()):
        n = stats["islands"].get(ref, 0)
        print(f"  {sig} references {ref}  ({n} poured island"
              f"{'' if n == 1 else 's'})")
    print(f"  Segments scanned  : {stats['segments_scanned']} "
          f"({stats['trace_mm']:.0f} mm of trace, ~{stats['samples']} samples "
          f"at {SAMPLE_STEP_MM} mm)")
    print(f"  Zone clearance    : {stats['clearance_mm']} mm (read from the "
          f"board) -> antipads excused up to that plus the feature radius")
    print(f"  Void floor        : {VOID_RUN_MIN_MM} mm of unattributed "
          f"no-copper run")
    print()

    failures = [r for r in results if r["verdict"] == "FAIL"]
    warnings = [r for r in results if r["verdict"] == "WARN"]
    notes = [r for r in results if r["verdict"] == "NOTE"]

    for r in failures + warnings:
        layers = ",".join(sorted(r["layers"]))
        bits = []
        if r["seams"]:
            bits.append(f"{r['seams']} seam crossing"
                        f"{'' if r['seams'] == 1 else 's'} "
                        f"({r['seam_detail']} at "
                        f"({r['seam_at'][0]:.2f}, {r['seam_at'][1]:.2f}))")
        if r["voids"]:
            bits.append(f"{r['voids']} void run"
                        f"{'' if r['voids'] == 1 else 's'}, worst "
                        f"{r['worst_void_mm']:.2f} mm at "
                        f"({r['worst_void_at'][0]:.2f}, "
                        f"{r['worst_void_at'][1]:.2f})")
        print(f"  {r['verdict']}  {r['net']:11s} on {layers:9s} "
              f"{'; '.join(bits)}")

    for r in notes:
        print(f"  NOTE  {r['net']:11s} — allowed: {r['allowed']}")

    if not results:
        print("  PASS  every scanned segment sits over continuous reference "
              "copper")
    elif not failures:
        print("  PASS  no critical net changes reference island or crosses an "
              "unexplained plane void")

    print()
    print(f"Results: {len(failures)} failed, {len(warnings)} warned, "
          f"{len(notes)} allowed")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
