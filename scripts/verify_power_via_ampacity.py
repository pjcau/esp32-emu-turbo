#!/usr/bin/env python3
"""Power-via ampacity gate — the layer transitions must carry the rail.

`verify_power_net_integrity` proves a power net is ONE piece of copper.
It says nothing about how WIDE that piece is where it changes layer. A
single 0.2 mm via carrying the whole +3V3 rail is one connected group,
draws no DRC violation, passes every other gate in this repo, and burns
open the first time the ESP32 transmits. This gate is the missing half:
copper that is connected must also be big enough.

Nothing here duplicates the trace-width question. Track width has its own
constraints; this file judges only the INTER-LAYER transitions — vias and
plated through-hole barrels — because those are where a power net on this
board narrows by an order of magnitude without anything noticing.

The law
-------
For every net in the power path, with a declared worst-case current
``I_net``:

  T1  SOURCE CUT.  Take the pad(s) that inject current into the net and
      the pads that consume it. The minimum via cut separating them
      carries 100% of the rail current by definition, so its aggregate
      ampacity must be >= I_net. Computed as a real min cut: a
      hand-rolled max-flow (Edmonds-Karp, networkx is not installed) over
      per-layer copper islands, with vias and plated barrels as
      capacitated inter-layer nodes.

  T2  SOLE-CONSUMER CUT.  When a net has exactly one consuming pad
      besides the source, that pad takes the entire rail current, so the
      cut to it alone must also be >= I_net. This is the series-element
      case: J1 -> F1, Q1 -> BAT+, U2 -> L1.

Both tiers are sound: they never demand more current from a transition
than physics can push through it. A FAIL is a real finding.

Which pads consume
------------------
T1's sink set is every pad on the net except the source and except pads
that provably cannot carry DC:

  * a capacitor pad conducts no DC current — structural, not a datasheet
    number; ``C*`` by reference designator (the repo enforces IPC
    designators, see the SW_PWR -> SW16 rename)
  * a resistor pad conducts ``V_rail / R``, taken from the generator's
    own BOM value; an upper bound, since whatever is in series with it
    only reduces the current

Their (tiny, derived) demands are subtracted from the current the cut
must carry. Everything else — ICs, connectors, inductors, switches,
transistors, fuses — is a consumer with an undeclared budget.

Deviation from the plan, stated on purpose
------------------------------------------
docs/gate-coverage-expansion-plan.md Workstream B specifies the law as
"for each source-pad -> load-pad pair, compute the minimum via cut" and
compare each against I_net. That was implemented and measured first, and
it is degenerate on this board: the routing style is one drop via per
pad, so of the 52 source/load pairs on the plan's five nets, 44 return
0.527 A, 5 return 0.791 A and 3 are unbounded. 49 of 52 red, two
distinct numbers, no signal about which transition is actually starved.
It is also unsound in the false-positive direction — it demands that the
path to a 100 nF decoupling capacitor carry the entire 2 A rail.

The repo declares no per-load current budget anywhere (the vbench models
carry supply-side limits only; there is no ESP32 or panel supply-current
Param to read), and inventing one would be exactly the magic number this
project forbids. So v1 judges the two cuts that are sound without one.
The known consequence: a single starved transition to ONE consumer among
several is not caught. The narrowest single-consumer transition per net
is printed as measured data so the gap is visible rather than silent.
When per-load budgets are declared, replace T1/T2 with a feasibility
flow (per-load sink capacities, feasible iff maxflow == total demand)
and this limitation disappears.

Conservatism direction
----------------------
The copper model is the repo's standard over-approximation (see
pcb_copper_graph): pads are circles of radius max(w,h)/2 and via pads
exist on every layer. Over-approximating copper can only ADD paths, so
the computed cut is an UPPER bound on the real capacity. A FAIL is
therefore definitive; a PASS may hide a marginal case.

Usage:
    python3 scripts/verify_power_via_ampacity.py
    python3 scripts/verify_power_via_ampacity.py +3V3 BAT+

Output contract: every failing check prints a line starting with FAIL.
Exit codes: 0 pass · 1 at least one starved transition · 2 structural
(a declared net absent from the board, a source pad that does not exist,
a power net on the board with no declared current, an unparseable BOM
value).
"""

from __future__ import annotations

import collections
import math
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

from pcb_cache import load_cache                      # noqa: E402
from pcb_copper_graph import parse_copper             # noqa: E402
from shapely.geometry import LineString, Point        # noqa: E402
from shapely.strtree import STRtree                   # noqa: E402

COPPER_LAYERS = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
INF = float("inf")
WIDTH = 76


class Structural(RuntimeError):
    """A source of truth is missing, renamed or unparseable."""


# ── Via ampacity ────────────────────────────────────────────────────
#
# IPC-2221B section 6.2 figure 6-4, the conductor-current nomograph, in
# its usual closed form:
#
#     I = k * dT^0.44 * A^0.725        A in mil^2, dT in degC, I in A
#
# k = 0.024 for INTERNAL conductors and 0.048 for external. A plated via
# barrel is buried in laminate on every side, so the internal curve is
# both the correct one and the lower one.
#
# The barrel is modelled as a conductor whose cross-section is the
# annulus of plated copper, A = pi * d_drill * t_plating. No copper from
# the annular ring, the pad or the surrounding pour is counted.
#
# All three inputs are deliberately the pessimistic end:
#
#   t_plating 18 um — IPC-6012E table 3-2 gives Class 2 plated copper in
#                     the hole as 20 um average with an 18 um thin-area
#                     minimum. This takes the thin area, i.e. the worst
#                     legal point of a compliant barrel.
#   dT 10 degC      — the conventional design rise for a power conductor
#                     that shares a board with a battery.
#   IPC-2221 curve  — superseded by IPC-2152, which measured higher
#                     allowable currents for the same geometry. Staying
#                     on the older, lower curve is intentional headroom.
#
# Sanity check against the rule of thumb: this returns 0.707 A for a
# 0.3 mm drill, against the commonly quoted "about 1 A". Conservative by
# roughly 30%, as intended.
_IPC2221_K_INTERNAL = 0.024
_PLATING_MM = 0.018
_DELTA_T_C = 10.0
_MM2_PER_MIL2 = 0.0254 ** 2


def via_ampacity(drill_mm: float) -> float:
    """Continuous current one plated barrel of this drill may carry, in A."""
    if drill_mm <= 0:
        raise Structural(f"via/barrel with a non-positive drill {drill_mm} — "
                         "an unplated hole cannot carry current and must not "
                         "appear on a net")
    area_mil2 = math.pi * drill_mm * _PLATING_MM / _MM2_PER_MIL2
    return _IPC2221_K_INTERNAL * (_DELTA_T_C ** 0.44) * (area_mil2 ** 0.725)


# ── Declared currents ───────────────────────────────────────────────
#
# Every number below is read live from the component models under
# scripts/vbench/models/, whose schema refuses an uncited Param. Nothing
# here is a constant typed by hand: if a datasheet reading is corrected
# in a model, this gate follows it in the same commit.

def _rail_declarations():
    """Return {net: Rail} built from the cited component models."""
    try:
        from scripts.vbench.models.bt1_lp105080 import BT1
        from scripts.vbench.models.u2_ip5306 import U2
        from scripts.vbench.models.u3_sy8089 import U3
    except Exception as e:
        raise Structural(f"cannot import a component model: {e}")

    def p(model, key):
        try:
            return model.params[key]
        except KeyError:
            raise Structural(f"{model.ref} model has no Param {key!r} — "
                             "renamed or removed; this gate's citation is "
                             "now dangling")

    # +3V3 — the buck's rated continuous output.
    i_3v3 = p(U3, "i_out_continuous")
    # +5V — the IP5306 boost's rated maximum output.
    i_5v = p(U2, "i_boost_max")
    # BAT+ — derived, not read: the current the boost pulls OUT of the
    # cell to sustain its rated output at the LOWEST battery voltage it
    # will still run at (worst case), capped by what the cell is rated to
    # deliver continuously.
    #     I_bat = I_boost * V_out / (V_bat_min * eta)
    v_out = p(U2, "v_out_typ")
    v_bat_min = p(U2, "v_bat_operating_min")
    eta = p(U2, "eta_boost_max")
    i_bat_cell = p(BT1, "i_discharge_max_cont")
    i_bat = min(i_5v.value * v_out.value / (v_bat_min.value * eta.value),
                i_bat_cell.value)
    bat_cite = (f"derived: {i_5v.value} A x {v_out.value} V / "
                f"({v_bat_min.value} V x {eta.value}) capped at the cell's "
                f"{i_bat_cell.value} A continuous discharge "
                f"[{U2.datasheet.doc} {i_5v.locator}, {v_out.locator}, "
                f"{v_bat_min.locator}, {eta.locator}; "
                f"{BT1.datasheet.doc} {i_bat_cell.locator}]")

    def cite(model, param):
        return f"{model.part} {model.datasheet.doc} {param.locator}"

    # VBUS / VBUS_IN — bounded by the PTC in series with them, not by the
    # cable. Its hold current is read live from the generator's own
    # placement value so the two cannot drift apart.
    i_fuse = _fuse_hold_current("F1")
    fuse_cite = ("F1 PTC hold current, value from "
                 "scripts/generate_pcb/jlcpcb_export.py::_build_placements "
                 "(LCSC C960026, BOM 'PTC Resettable Fuse 2A 1812'); no "
                 "datasheet PDF for this part is in hardware/datasheets")

    v_3v3 = _buck_output_voltage(U3)
    v_5v = v_out.value
    v_bat = p(BT1, "v_charge_max").value

    R = collections.namedtuple("Rail", "current volts sources why")
    return {
        "+3V3": R(i_3v3.value, v_3v3, ("L2.1",),
                  cite(U3, i_3v3) + " (buck output through L2)"),
        "+5V": R(i_5v.value, v_5v, ("U2.8",),
                 cite(U2, i_5v) + " (boost output)"),
        "VBUS": R(i_fuse, v_5v, ("F1.2",), fuse_cite),
        "VBUS_IN": R(i_fuse, v_5v, ("J1.2", "J1.11"), fuse_cite),
        "BAT+": R(i_bat, v_bat, ("Q1.3",), bat_cite),
        "BAT_IN": R(i_bat, v_bat, ("J3.1",),
                    bat_cite + " — same path, upstream of Q1"),
        "LX": R(i_bat, v_bat, ("U2.7",),
                bat_cite + " — boost switch node, carries the cell current"),
        "BUCK_LX": R(i_3v3.value, v_5v, ("U3.3",),
                     cite(U3, i_3v3) + " — buck switch node, inductor DC "
                     "current equals the rated output"),
        # GND is the return. Every rail's current comes back through it,
        # so its requirement is the largest of the rails it serves. The
        # sources are the two converters' return pads, where the return
        # current has to arrive.
        "GND": R(max(i_3v3.value, i_5v.value, i_fuse, i_bat), v_5v,
                 ("U2.EP", "U3.2"),
                 "return path: max of the rails it serves"),
    }


def _placement_values() -> dict:
    """{ref: value} from the generator, the same source the BOM is cut from."""
    try:
        from scripts.generate_pcb.jlcpcb_export import _build_placements
    except Exception as e:
        raise Structural(f"cannot import the placement source of truth: {e}")
    return {row[0]: row[1] for row in _build_placements()}


_R_VALUE = re.compile(r"^([0-9]*\.?[0-9]+)\s*([kKmMrR]?)$")
_R_MULT = {"": 1.0, "r": 1.0, "R": 1.0, "k": 1e3, "K": 1e3,
           "m": 1e6, "M": 1e6}


def resistance_ohms(ref: str, value: str) -> float:
    m = _R_VALUE.match(value.strip())
    if not m:
        raise Structural(f"{ref} has BOM value {value!r}, which this gate "
                         "cannot read as a resistance — a resistor on a "
                         "power net with an unreadable value is a hole in "
                         "the demand model, not a pass")
    return float(m.group(1)) * _R_MULT[m.group(2)]


def _fuse_hold_current(ref: str) -> float:
    """PTC hold current from the placement value, e.g. '2A'."""
    value = _placement_values().get(ref)
    if value is None:
        raise Structural(f"{ref} is not in _build_placements() — the fuse "
                         "that bounds VBUS was renamed or removed")
    m = re.match(r"^([0-9]*\.?[0-9]+)\s*[aA]$", value.strip())
    if not m:
        raise Structural(f"{ref} placement value {value!r} is not a current "
                         "rating; VBUS's declared current would be a guess")
    return float(m.group(1))


def _buck_output_voltage(U3) -> float:
    """+3V3 from the FB reference and the divider actually in the BOM.

    Vout = V_FB * (1 + R25/R26). Read rather than assumed, because the
    R25 respin exists precisely because a hand-written 3.3 outlived the
    divider that produced it.
    """
    vals = _placement_values()
    r_top = resistance_ohms("R25", vals.get("R25", ""))
    r_bot = resistance_ohms("R26", vals.get("R26", ""))
    v_fb = U3.params["v_fb_ref"].value
    v_fb_typ = v_fb[1] if isinstance(v_fb, tuple) else v_fb
    return v_fb_typ * (1.0 + r_top / r_bot)


# ── Copper model: per-layer islands + capacitated barrels ───────────

Island = collections.namedtuple("Island", "layer geoms")
Barrel = collections.namedtuple("Barrel", "label geom capacity")
PadNode = collections.namedtuple("PadNode", "name geom layers is_barrel")

Model = collections.namedtuple("Model", "islands barrels pads index")


def build_model(net: str, cache: dict, zones: list) -> Model:
    """Per-layer copper islands of `net`, with vias/barrels as edges.

    pcb_copper_graph deliberately gives vias every layer and then
    union-finds the lot, which answers "is it connected" and erases the
    per-layer structure a cut needs. This rebuilds that structure:
    union-find is run INSIDE each layer, and the only way between layers
    is a barrel with a finite capacity.
    """
    net_id = next((n["id"] for n in cache["nets"] if n["name"] == net), None)
    if net_id is None:
        raise Structural(f"net {net!r} is declared here but does not exist "
                         "on the board — renamed in the generator, or this "
                         "gate is checking a name the board never had")

    pieces = {layer: [] for layer in COPPER_LAYERS}
    barrels: list[Barrel] = []
    pads: list[PadNode] = []

    for z in zones:
        if z["net"] != net:
            continue
        if z["layer"] not in pieces:
            raise Structural(f"zone on {net} sits on unknown layer "
                             f"{z['layer']!r}")
        for poly in z["polys"]:
            pieces[z["layer"]].append(poly)

    for seg in cache["segments"]:
        if seg["net"] != net_id:
            continue
        if seg["layer"] not in pieces:
            raise Structural(f"track on {net} sits on unknown layer "
                             f"{seg['layer']!r}")
        pieces[seg["layer"]].append(
            LineString([(seg["x1"], seg["y1"]), (seg["x2"], seg["y2"])])
            .buffer(seg["width"] / 2, cap_style=2))

    for i, via in enumerate(cache["vias"]):
        if via["net"] != net_id:
            continue
        geom = Point(via["x"], via["y"]).buffer(via["size"] / 2)
        barrels.append(Barrel(f"via@({via['x']:.2f},{via['y']:.2f})", geom,
                              via_ampacity(via["drill"])))
        for layer in COPPER_LAYERS:
            pieces[layer].append(geom)

    seen = set()
    for pad in cache["pads"]:
        if pad["net"] != net_id:
            continue
        name = f"{pad['ref']}.{pad['num']}"
        geom = Point(pad["x"], pad["y"]).buffer(max(pad["w"], pad["h"]) / 2)
        if pad["type"] == "thru_hole":
            # A plated barrel is a via that happens to be a pad: it is
            # both copper on every layer and a capacitated transition.
            if name in seen:
                continue
            seen.add(name)
            barrels.append(Barrel(f"barrel {name}", geom,
                                  via_ampacity(pad["drill"])))
            for layer in COPPER_LAYERS:
                pieces[layer].append(geom)
            pads.append(PadNode(name, geom, COPPER_LAYERS, True))
        else:
            if pad["layer"] not in pieces:
                raise Structural(f"pad {name} on {net} sits on unknown "
                                 f"layer {pad['layer']!r}")
            pieces[pad["layer"]].append(geom)
            pads.append(PadNode(name, geom, (pad["layer"],), False))

    if not pads:
        raise Structural(f"net {net!r} carries no pads — nothing sources it "
                         "and nothing consumes it")

    islands: list[Island] = []
    index: dict = {layer: [] for layer in COPPER_LAYERS}
    for layer in COPPER_LAYERS:
        geoms = pieces[layer]
        if not geoms:
            continue
        for members in _connected_components(geoms):
            island_id = len(islands)
            islands.append(Island(layer, [geoms[m] for m in members]))
            for m in members:
                index[layer].append((geoms[m], island_id))

    return Model(islands, barrels, pads, index)


def _connected_components(geoms: list) -> list:
    """Union-find over geometries that intersect, within one layer."""
    parent = list(range(len(geoms)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    tree = STRtree(geoms)
    for i, g in enumerate(geoms):
        for j in tree.query(g):
            j = int(j)
            if j <= i or not g.intersects(geoms[j]):
                continue
            ra, rb = find(i), find(j)
            if ra != rb:
                parent[ra] = rb

    comp = collections.defaultdict(list)
    for i in range(len(geoms)):
        comp[find(i)].append(i)
    return list(comp.values())


def islands_touching(model: Model, geom, layers) -> set:
    """Island ids this geometry lands on, per layer."""
    hit = set()
    for layer in layers:
        for other, island_id in model.index.get(layer, ()):
            if island_id not in hit and geom.intersects(other):
                hit.add(island_id)
    return hit


# ── Min cut (hand-rolled max-flow, node capacities) ─────────────────

class FlowNetwork:
    """Edmonds-Karp on a residual adjacency dict. networkx is not installed.

    Capacity lives on NODES here (a barrel carries a current, an island
    does not restrict one), so every node is split in two and the node's
    capacity becomes the arc between the halves — the standard reduction
    for undirected node-capacitated cuts.
    """

    def __init__(self):
        self.adj = collections.defaultdict(dict)

    def arc(self, u, v, capacity):
        self.adj[u][v] = self.adj[u].get(v, 0.0) + capacity
        self.adj[v].setdefault(u, 0.0)

    def max_flow(self, source, sink) -> float:
        total = 0.0
        while True:
            prev = {source: None}
            queue = collections.deque([source])
            while queue and sink not in prev:
                u = queue.popleft()
                for v, capacity in self.adj[u].items():
                    if capacity > 1e-12 and v not in prev:
                        prev[v] = u
                        queue.append(v)
            if sink not in prev:
                return total
            bottleneck, v = INF, sink
            while prev[v] is not None:
                bottleneck = min(bottleneck, self.adj[prev[v]][v])
                v = prev[v]
            v = sink
            while prev[v] is not None:
                self.adj[prev[v]][v] -= bottleneck
                self.adj[v][prev[v]] += bottleneck
                v = prev[v]
            total += bottleneck

    def reachable(self, source) -> set:
        """Residual-reachable nodes — the source side of the min cut."""
        seen, queue = {source}, collections.deque([source])
        while queue:
            u = queue.popleft()
            for v, capacity in self.adj[u].items():
                if capacity > 1e-12 and v not in seen:
                    seen.add(v)
                    queue.append(v)
        return seen


Cut = collections.namedtuple("Cut", "capacity barrels")


def min_via_cut(model: Model, source_islands: set, sink_islands: set) -> Cut:
    """The narrowest set of barrels separating the two island sets.

    An INF capacity means no barrel separates them at all: they are the
    same copper, or a chain of copper with no layer change. That is not a
    vacuous pass — it is the statement that no layer transition is
    involved, and the trace-width gates own what happens next.
    """
    if source_islands & sink_islands:
        return Cut(INF, [])
    if not source_islands or not sink_islands:
        raise Structural("a cut was requested against an empty side — the "
                         "pad geometry landed on no copper at all")

    net = FlowNetwork()
    for island_id in range(len(model.islands)):
        net.arc(("i-", island_id), ("i+", island_id), INF)
    for barrel in model.barrels:
        net.arc(("b-", barrel.label), ("b+", barrel.label), barrel.capacity)
        for island_id in islands_touching(model, barrel.geom, COPPER_LAYERS):
            net.arc(("i+", island_id), ("b-", barrel.label), INF)
            net.arc(("b+", barrel.label), ("i-", island_id), INF)
    for island_id in source_islands:
        net.arc("SOURCE", ("i-", island_id), INF)
    for island_id in sink_islands:
        net.arc(("i+", island_id), "SINK", INF)

    capacity = net.max_flow("SOURCE", "SINK")
    side = net.reachable("SOURCE")
    crossing = [b.label for b in model.barrels
                if ("b-", b.label) in side and ("b+", b.label) not in side]
    return Cut(capacity, crossing)


# ── The checks ──────────────────────────────────────────────────────

def classify(ref: str) -> str:
    """capacitor · resistor · consumer, from the reference designator."""
    if re.match(r"^C\d", ref):
        return "capacitor"
    if re.match(r"^R\d", ref):
        return "resistor"
    return "consumer"


def check_net(net: str, rail, cache: dict, zones: list, values: dict) -> list:
    model = build_model(net, cache, zones)
    by_name = {pad.name: pad for pad in model.pads}

    missing = [s for s in rail.sources if s not in by_name]
    if missing:
        raise Structural(
            f"{net}: declared source pad(s) {', '.join(missing)} are not on "
            "the net — the part moved, was renamed, or the rail is now fed "
            "from somewhere else. A gate measuring from the wrong source "
            "measures nothing.")

    source_islands = set()
    for name in rail.sources:
        pad = by_name[name]
        source_islands |= islands_touching(model, pad.geom, pad.layers)

    consumers, bypass, bypass_demand = [], [], 0.0
    for pad in model.pads:
        if pad.name in rail.sources:
            continue
        kind = classify(pad.name.split(".")[0])
        if kind == "capacitor":
            bypass.append(pad)
        elif kind == "resistor":
            ref = pad.name.split(".")[0]
            ohms = resistance_ohms(ref, values.get(ref, ""))
            bypass.append(pad)
            bypass_demand += rail.volts / ohms
        else:
            consumers.append(pad)

    if not consumers:
        raise Structural(
            f"{net}: every pad besides the source is a capacitor or a "
            "resistor. A rail that powers nothing is either a dead net or a "
            "misdeclared source.")

    sizes = sorted({round(b.capacity, 3) for b in model.barrels})
    lines = [
        f"  {net}",
        f"      required     : {rail.current:.3f} A",
        f"      citation     : {rail.why}",
        f"      source pad(s): {', '.join(rail.sources)}",
        f"      consumers    : {', '.join(p.name for p in consumers)}",
        f"      not DC loads : {len(bypass)} pad(s), a derived "
        f"{bypass_demand * 1000:.3f} mA in total",
        f"      barrels      : {len(model.barrels)} "
        f"({', '.join(f'{c:.3f} A' for c in sizes) if sizes else 'none'})",
    ]
    results = []

    # T1 — the cut every amp of this rail has to cross.
    sink_islands = set()
    for pad in consumers:
        sink_islands |= islands_touching(model, pad.geom, pad.layers)
    cut = min_via_cut(model, source_islands, sink_islands)
    need = rail.current - bypass_demand
    if cut.capacity == INF:
        shared = [p.name for p in consumers
                  if islands_touching(model, p.geom, p.layers)
                  & source_islands]
        lines.append(
            f"  PASS  {net}/source-cut: no barrel separates the source from "
            f"its consumers — {', '.join(shared)} sits on the same copper, "
            "so the rail changes no layer between them")
        results.append(True)
    elif cut.capacity + 1e-9 < need:
        lines.append(
            f"  FAIL  {net}/source-cut: every amp of this rail crosses "
            f"{len(cut.barrels)} barrel(s) worth {cut.capacity:.3f} A, "
            f"against {need:.3f} A required "
            f"({cut.capacity / need * 100:.0f}% of what it must carry)")
        lines.append(f"            the cut: {_name_cut(cut)}")
        results.append(False)
    else:
        lines.append(f"  PASS  {net}/source-cut: {cut.capacity:.3f} A across "
                     f"the narrowest transition ({len(cut.barrels)} barrel"
                     f"(s)), {need:.3f} A required")
        results.append(True)

    # T2 — a lone consumer takes everything the source puts out.
    if len(consumers) == 1:
        only = consumers[0]
        solo = min_via_cut(model, source_islands,
                           islands_touching(model, only.geom, only.layers))
        if solo.capacity == INF:
            lines.append(f"  PASS  {net}/sole-consumer: {only.name} sits on "
                         "the source's own copper, no transition involved")
            results.append(True)
        elif solo.capacity + 1e-9 < rail.current:
            lines.append(
                f"  FAIL  {net}/sole-consumer: {only.name} is the only load "
                f"on this net, so it takes all {rail.current:.3f} A, and it "
                f"is reached through {solo.capacity:.3f} A of barrel")
            lines.append(f"            the cut: {_name_cut(solo)}")
            results.append(False)
        else:
            lines.append(f"  PASS  {net}/sole-consumer: {only.name} reached "
                         f"through {solo.capacity:.3f} A of barrel")
            results.append(True)

    # Measured, not judged — see the module docstring. This is the
    # transition a per-load budget would judge; printing it keeps the hole
    # in the law visible instead of silent.
    narrowest = None
    for pad in consumers:
        solo = min_via_cut(model, source_islands,
                           islands_touching(model, pad.geom, pad.layers))
        if narrowest is None or solo.capacity < narrowest[1]:
            narrowest = (pad.name, solo.capacity)
    if narrowest and narrowest[1] != INF:
        lines.append(f"      narrowest single-consumer transition: "
                     f"{narrowest[0]} behind {narrowest[1]:.3f} A "
                     "(not judged — no per-load budget is declared)")

    return results, lines


def _name_cut(cut: Cut, limit: int = 6) -> str:
    shown = ", ".join(cut.barrels[:limit])
    if len(cut.barrels) > limit:
        shown += f", ... and {len(cut.barrels) - limit} more"
    return shown or "(none)"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    print()
    print("=" * WIDTH)
    print("POWER-VIA AMPACITY — can the layer transitions carry the rail?")
    print("=" * WIDTH)

    rails = _rail_declarations()
    cache = load_cache()
    zones = parse_copper().zones
    values = _placement_values()

    # A power net on the board that nobody declared a current for is a
    # hole in this gate, and a hole is worse than a red light: it reads
    # as green. Classification comes from the repo's own net_classifier
    # rule, embedded in pcb_cache.
    on_board = {name for name, kind in cache["net_types"].items()
                if kind in ("power", "gnd")}
    undeclared = sorted(on_board - set(rails))
    if undeclared:
        raise Structural(
            "power net(s) on the board with no declared current: "
            + ", ".join(undeclared)
            + " — declare the worst-case current with a citation in "
              "_rail_declarations(), or this gate silently ignores them")

    selected = argv or list(rails)
    unknown = [n for n in selected if n not in rails]
    if unknown:
        raise Structural(f"no declaration for {', '.join(unknown)}")

    print(f"  Vias / pads      : {len(cache['vias'])} / {len(cache['pads'])}")
    print(f"  Ampacity model   : IPC-2221B internal curve, "
          f"{_PLATING_MM * 1000:.0f} um barrel plating, "
          f"dT {_DELTA_T_C:.0f} degC")
    print(f"                     0.20 mm drill -> "
          f"{via_ampacity(0.20):.3f} A, 0.35 mm -> {via_ampacity(0.35):.3f} A")
    print(f"  Nets checked     : {', '.join(selected)}")
    print()

    failed_nets, total, bad = [], 0, 0
    for net in selected:
        results, lines = check_net(net, rails[net], cache, zones, values)
        for line in lines:
            print(line)
        print()
        total += len(results)
        net_bad = results.count(False)
        bad += net_bad
        if net_bad:
            failed_nets.append(net)

    print("=" * WIDTH)
    if not bad:
        print(f"Results: PASS — {total}/{total} transition check(s) across "
              f"{len(selected)} power net(s)")
        print("=" * WIDTH)
        return 0

    print(f"Results: FAIL — {bad}/{total} transition check(s) on "
          f"{len(failed_nets)} net(s): {', '.join(failed_nets)}")
    print("=" * WIDTH)
    print()
    print("REMEDIATION:")
    print("  A starved transition does not show up as an open. It works on")
    print("  the bench at 200 mA and fails the first time the rail is asked")
    print("  for its rated current — the barrel is the fuse.")
    print()
    print("  Fix in scripts/generate_pcb/routing/: stitch the transition with")
    print("  several vias in parallel, use the larger drill already in the")
    print("  stackup, or keep the current on one layer so it never has to")
    print("  cross. Do not raise the ampacity constants to make this pass:")
    print("  they are already the optimistic reading of a pessimistic curve.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Structural as e:
        print(f"STRUCTURAL ERROR: {e}", file=sys.stderr)
        sys.exit(2)
