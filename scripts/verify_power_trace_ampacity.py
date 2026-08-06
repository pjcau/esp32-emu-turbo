#!/usr/bin/env python3
"""Power-TRACE ampacity — can the copper itself carry the declared rail?

Sibling of verify_power_via_ampacity.py, closing the half of R31-MED-3
that gate deliberately left open: its min-cut treats an in-layer copper
island as an INFINITE conductor ("an island does not restrict a
current"), so a rail whose barrels are sized to the derived worst case
could still be starved by the traces BETWEEN the barrels. That is
exactly what R31-MED-3 found: BAT+/LX barrels sized to 4.348 A while
every trace on the same path is 0.76 mm, justified in a comment at
2.1 A. Two design currents for one net, and no gate compared trace
copper to either.

This gate ends the two-current story by measuring the copper against
THE SAME declared currents the barrel gate uses (_rail_declarations —
every number cited from the component models; nothing typed by hand).

Model
-----
Feature-level max-flow. Where the via gate collapses each layer into
islands (nodes) and capacitates only barrels, this gate keeps every
copper feature as its own capacitated node:

  segment  : IPC-2221B conductor curve, I = k * dT^0.44 * A^0.725
             k = 0.048 (outer layers) / 0.024 (inner layers)
             A from the trace width x the stackup's copper weight:
             35 um outer (1 oz), 17.5 um inner (0.5 oz) — the JLCPCB
             4-layer standard declared in esp32-emu-turbo.kicad_dru.
             EXCEPTION — the land-pattern neck: a segment whose entire
             copper lies within PAD_HALO_MM of a same-net pad is part
             of the land pattern, not a trace. The IPC curve is the
             asymptote for a long, thermally isolated conductor; a
             sub-mm neck bounded by a pad on one end and fat copper on
             the other is dominated by conduction into both (IPC-2152's
             own length sections show >2x capacity for short traces),
             and the component's continuous rating covers its own land:
             the AO3401A carries -4 A through a 0.6 mm-wide lead land.
             Such necks get INF here; anything longer binds normally.
  zone     : INF — a pour is judged by verify_power_net_integrity /
             the zone-fill gates, not here.
  pad      : INF — pad copper is wide and short. THT component pads
             are INF on every layer: a SOLDERED pin fills the barrel,
             so the plating-annulus model (which the barrel gate
             rightly applies to empty vias) does not describe the
             joint. Layer transitions through bare vias still pay
             via_ampacity().
  via      : via_ampacity() imported from the barrel gate, so the two
             gates can never disagree about a barrel.

Arcs join features that physically intersect on a shared layer (vias
span all four). Max-flow from the rail's declared source pads to its
consumer pads is then the current the copper can deliver at the model
dT — parallel bands add up, series bottlenecks bind, and stubs to
bypass capacitors contribute nothing, all for free.

Acceptance
----------
A rail passes when the copper delivers its declared current within
DELTA_T_LIMIT_C of temperature rise. Capacity scales as dT^0.44, so
the gate reports the rise the copper actually needs for the declared
current — one number that makes the trade visible:

    dT_needed = dT_model * (I_required / I_capacity@dT_model)^(1/0.44)

The limit is 20 degC. The barrel gate designs its vias to 10 degC, but
a via can always be duplicated; a trace is bounded by the corridor it
runs in, and the corridors on this board were hand-verified against
their neighbours. 20 degC on the deliberately-low IPC-2221 curve (the
repo keeps it over IPC-2152 for headroom; 2152 measured roughly twice
the capacity for short traces) is a materially conservative bar.

Per-net exceptions live in TRACE_DT_EXCEPTIONS below, the same shape
as issue_dispatch's ROUTING_EXCEPTIONS: an entry must say what is
geometrically non-standard about that net, carries the measured
ceiling, and prints on every run. Do not add an entry to make a red
net pass — widen the copper, parallel it on another layer, or correct
the declared current AT ITS CITATION in _rail_declarations if the
electrical argument is genuinely about the current. An entry whose
ceiling the copper no longer needs (because a respin widened it) is
flagged so it gets deleted.

Usage:
    python3 scripts/verify_power_trace_ampacity.py            # gate
    python3 scripts/verify_power_trace_ampacity.py --report   # measure only
    python3 scripts/verify_power_trace_ampacity.py BAT+ LX    # subset

Output contract: every failing check prints a line starting with FAIL.
Exit codes: 0 pass · 1 starved copper · 2 structural.
"""

from __future__ import annotations

import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

from pcb_cache import load_cache                      # noqa: E402
from pcb_copper_graph import parse_copper             # noqa: E402
from shapely.geometry import LineString, Point        # noqa: E402
from shapely.strtree import STRtree                   # noqa: E402

from verify_power_via_ampacity import (               # noqa: E402
    COPPER_LAYERS,
    INF,
    FlowNetwork,
    Structural,
    _placement_values,
    _rail_declarations,
    classify,
    resistance_ohms,
    via_ampacity,
)

WIDTH = 76

# ── Trace ampacity ──────────────────────────────────────────────────
# IPC-2221B figure 6-4 closed form, same as the barrel gate, but with
# the conductor curve matched to the layer: external traces cool into
# air, internal ones are buried. Copper weights are the JLCPCB 4-layer
# standard the .kicad_dru header declares: 1 oz (35 um) outer, 0.5 oz
# (17.5 um) inner. dT is the barrel gate's 10 degC, and IPC-2221 is
# kept over IPC-2152 for the same reason it is kept there: headroom.
_MM2_PER_MIL2 = 0.0254 ** 2
_DELTA_T_C = 10.0
_DELTA_T_LIMIT_C = 20.0

# Per-net dT ceilings for nets whose corridors are at their geometric
# maximum (see the module docstring). Every entry: (ceiling_degC, why).
# The R32 widening sweep took all three of these to the widest copper
# their corridors admit at the 0.2 mm netclass clearance — the numbers
# below are the measured residual, not a choice:
#
#   BAT+   2.034 A @10 -> 56 degC at the 4.348 A corner
#   BAT_IN 2.563 A @10 -> 33 degC
#   LX     2.216 A @10 -> 46 degC
#
# The 4.348 A figure is itself a stacked corner: the boost at its full
# rated 2.4 A output WITH the cell at its 3.0 V operating floor — an
# end-of-discharge transient, not a sustained state (at a nominal 3.7 V
# cell the same load draws 3.52 A -> BAT+ 36 degC). A first-article
# thermal probe on the Q1 corridor at forced full load is OWED before
# these entries can be called validated; they are declared limits, not
# blessings.
TRACE_DT_EXCEPTIONS = {
    "BAT+": (60.0,
             "Q1-quadrant corridor at its maximum: the channel into Q1.2 "
             "is capped at 0.80 mm by the gate pad (0.20 above) and the "
             "drain pad (0.20 below); the fence of button-RC lands, the "
             "J3.4 tab, RPP_GATE and the PWR_SW F.Cu wall blocks every "
             "wider or parallel path short of moving components"),
    "BAT_IN": (36.0,
               "same quadrant: the J3.1 riser and the y=54.20 horizontal "
               "are at 1.10 mm, the widest the J3 tab / BAT+ channel "
               "corridor admits"),
    "LX": (50.0,
           "boost switch node: the column is capped at 0.90 mm by the "
           "0.25 mm LX-vs-BAT+ spacing rule (verify_dfm_v2); an F.Cu "
           "parallel band was deliberately rejected — it would double "
           "the 1 MHz switch-node copper against datasheet rule 3"),
}
_THICKNESS_MM = {"F.Cu": 0.035, "B.Cu": 0.035,
                 "In1.Cu": 0.0175, "In2.Cu": 0.0175}
_K = {"F.Cu": 0.048, "B.Cu": 0.048, "In1.Cu": 0.024, "In2.Cu": 0.024}
# Land-pattern neck halo (see the module docstring). 0.75 mm covers the
# last-mile stub a hand route needs to land on a SOT-23 / 0805-class pad
# without covering any real inter-component trace: the shortest genuine
# trace on this board's power nets is several mm.
PAD_HALO_MM = 0.75


def trace_ampacity(width_mm: float, layer: str,
                   delta_t: float = _DELTA_T_C) -> float:
    """Continuous current a trace of this width on this layer may carry."""
    if width_mm <= 0:
        raise Structural(f"trace with non-positive width {width_mm}")
    if layer not in _THICKNESS_MM:
        raise Structural(f"trace on unknown layer {layer!r}")
    area_mil2 = width_mm * _THICKNESS_MM[layer] / _MM2_PER_MIL2
    return _K[layer] * (delta_t ** 0.44) * (area_mil2 ** 0.725)


# ── Feature-level flow model ────────────────────────────────────────

class Feature:
    __slots__ = ("label", "geom", "layers", "capacity")

    def __init__(self, label, geom, layers, capacity):
        self.label = label
        self.geom = geom
        self.layers = layers
        self.capacity = capacity


def build_features(net: str, cache: dict, zones: list):
    """Every copper feature of `net`, individually capacitated."""
    net_id = next((n["id"] for n in cache["nets"] if n["name"] == net), None)
    if net_id is None:
        raise Structural(f"net {net!r} does not exist on the board")

    features: list[Feature] = []
    pads_by_name: dict[str, Feature] = {}

    for z in zones:
        if z["net"] != net:
            continue
        for poly in z["polys"]:
            features.append(Feature(f"zone@{z['layer']}", poly,
                                    (z["layer"],), INF))

    # Pads first: segment capacities depend on the pad halos.
    seen = set()
    pad_halos = []          # buffered pad geoms, for the neck exemption
    for pad in cache["pads"]:
        if pad["net"] != net_id:
            continue
        name = f"{pad['ref']}.{pad['num']}"
        geom = Point(pad["x"], pad["y"]).buffer(max(pad["w"], pad["h"]) / 2)
        if pad["type"] == "thru_hole":
            if name in seen:
                continue
            seen.add(name)
            # Soldered pin fills the barrel — INF on every layer (see
            # the module docstring; bare vias still pay via_ampacity).
            feat = Feature(f"pth {name}", geom, COPPER_LAYERS, INF)
        else:
            feat = Feature(f"pad {name}", geom, (pad["layer"],), INF)
        features.append(feat)
        pads_by_name[name] = feat
        pad_halos.append(geom.buffer(PAD_HALO_MM))

    halo_tree = STRtree(pad_halos) if pad_halos else None

    for seg in cache["segments"]:
        if seg["net"] != net_id:
            continue
        geom = LineString([(seg["x1"], seg["y1"]), (seg["x2"], seg["y2"])]) \
            .buffer(seg["width"] / 2, cap_style=2)
        # Land-pattern neck exemption: entirely inside a same-net pad's
        # halo -> part of the land, not a trace.
        neck = False
        if halo_tree is not None:
            for h in halo_tree.query(geom):
                if pad_halos[int(h)].contains(geom):
                    neck = True
                    break
        features.append(Feature(
            f"{seg['width']:.2f}mm@{seg['layer']}"
            f"({seg['x1']:.1f},{seg['y1']:.1f})"
            + ("[neck]" if neck else ""),
            geom, (seg["layer"],),
            INF if neck else trace_ampacity(seg["width"], seg["layer"])))

    for via in cache["vias"]:
        if via["net"] != net_id:
            continue
        geom = Point(via["x"], via["y"]).buffer(via["size"] / 2)
        features.append(Feature(f"via@({via['x']:.2f},{via['y']:.2f})",
                                geom, COPPER_LAYERS,
                                via_ampacity(via["drill"])))

    if not pads_by_name:
        raise Structural(f"net {net!r} carries no pads")
    return features, pads_by_name


# Stand-in for "does not restrict the flow". A true float INF poisons
# Edmonds-Karp the moment an augmenting path is all-uncapacitated
# (INF - INF = NaN in the residual update); 1e6 A is finite, orders of
# magnitude above any real capacity, and survives the arithmetic. A
# computed max-flow at or above BIG/2 means no trace bound the path.
BIG = 1e6


def copper_max_flow(features, sources, sinks) -> float:
    """Max deliverable current from source features to sink features.

    Returns INF when no capacitated feature binds the path at all.
    """
    net = FlowNetwork()
    for i, f in enumerate(features):
        net.arc(("f-", i), ("f+", i), min(f.capacity, BIG))

    # Arc features that share copper on a shared layer. STRtree per
    # layer keeps this O(n log n) instead of all-pairs.
    by_layer: dict[str, list[int]] = {}
    for i, f in enumerate(features):
        for layer in f.layers:
            by_layer.setdefault(layer, []).append(i)
    linked = set()
    for layer, idxs in by_layer.items():
        geoms = [features[i].geom for i in idxs]
        tree = STRtree(geoms)
        for a, g in enumerate(geoms):
            for b in tree.query(g):
                b = int(b)
                if b <= a:
                    continue
                i, j = idxs[a], idxs[b]
                key = (min(i, j), max(i, j))
                if key in linked or not g.intersects(geoms[b]):
                    continue
                linked.add(key)
                net.arc(("f+", i), ("f-", j), BIG)
                net.arc(("f+", j), ("f-", i), BIG)

    for i in sources:
        net.arc("SOURCE", ("f-", i), BIG)
    for i in sinks:
        net.arc(("f+", i), "SINK", BIG)
    flow = net.max_flow("SOURCE", "SINK")
    return INF if flow >= BIG / 2 else flow


# ── The check ───────────────────────────────────────────────────────

def check_net(net: str, rail, cache: dict, zones: list, values: dict):
    features, pads_by_name = build_features(net, cache, zones)
    idx_of = {id(f): i for i, f in enumerate(features)}

    missing = [s for s in rail.sources if s not in pads_by_name]
    if missing:
        raise Structural(
            f"{net}: declared source pad(s) {', '.join(missing)} are not "
            "on the net — the part moved or the rail is fed elsewhere")

    sources, sinks, consumers, bypass_demand, n_bypass = [], [], [], 0.0, 0
    for name, feat in pads_by_name.items():
        if name in rail.sources:
            sources.append(idx_of[id(feat)])
            continue
        kind = classify(name.split(".")[0])
        if kind == "capacitor":
            n_bypass += 1
        elif kind == "resistor":
            ref = name.split(".")[0]
            bypass_demand += rail.volts / resistance_ohms(
                ref, values.get(ref, ""))
            n_bypass += 1
        else:
            consumers.append(name)
            sinks.append(idx_of[id(feat)])

    if not consumers:
        raise Structural(f"{net}: no consumer pads — dead net or "
                         "misdeclared source")

    need = rail.current - bypass_demand
    capacity = copper_max_flow(features, sources, sinks)
    n_segs = sum(1 for f in features if f.label[0].isdigit())

    lines = [
        f"  {net}",
        f"      required   : {need:.3f} A "
        f"(declared {rail.current:.3f} A - {bypass_demand * 1000:.1f} mA "
        "in bypass R)",
        f"      citation   : {rail.why}",
        f"      copper     : {n_segs} trace segment(s), "
        f"{n_bypass} non-load pad(s) excluded from the sinks",
    ]

    if capacity == INF:
        lines.append(
            f"  PASS  {net}/copper: source and consumers share "
            "uncapacitated copper (zone/pad only) — no trace binds")
        return True, lines

    dt_needed = _DELTA_T_C * (need / capacity) ** (1 / 0.44)
    lines.append(
        f"      deliverable: {capacity:.3f} A at dT {_DELTA_T_C:.0f} degC "
        f"-> the declared {need:.3f} A needs dT {dt_needed:.1f} degC")
    limit = _DELTA_T_LIMIT_C
    if net in TRACE_DT_EXCEPTIONS:
        ceiling, why = TRACE_DT_EXCEPTIONS[net]
        if dt_needed <= _DELTA_T_LIMIT_C + 1e-9:
            lines.append(
                f"  STALE-EXCEPTION  {net}: the copper now meets the "
                f"global {_DELTA_T_LIMIT_C:.0f} degC limit — delete this "
                "net's TRACE_DT_EXCEPTIONS entry")
            return False, lines
        limit = ceiling
        lines.append(f"      exception  : dT ceiling {ceiling:.0f} degC — "
                     f"{why}")
    ok = dt_needed <= limit + 1e-9
    verdict = "PASS" if ok else "FAIL"
    lines.append(
        f"  {verdict}  {net}/copper: "
        + (f"the declared {need:.3f} A within dT {limit:.0f} degC "
           f"({dt_needed:.1f} degC needed)" if ok else
           f"copper delivers {capacity:.3f} A at "
           f"dT {limit:.0f} degC-equivalent but the rail declares "
           f"{need:.3f} A — that current runs this copper at "
           f"dT {dt_needed:.0f} degC"))
    return ok, lines


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    report_only = "--report" in argv
    argv = [a for a in argv if a != "--report"]

    print()
    print("=" * WIDTH)
    print("POWER-TRACE AMPACITY — can the copper itself carry the rail?")
    print("=" * WIDTH)

    rails = _rail_declarations()
    cache = load_cache()
    zones = parse_copper().zones
    values = _placement_values()

    selected = argv or list(rails)
    unknown = [n for n in selected if n not in rails]
    if unknown:
        raise Structural(f"no declaration for {', '.join(unknown)}")

    print(f"  Ampacity model : IPC-2221B conductor curves, "
          f"dT {_DELTA_T_C:.0f} degC, limit {_DELTA_T_LIMIT_C:.0f} degC")
    print(f"                   outer 1 oz: 0.76 mm -> "
          f"{trace_ampacity(0.76, 'B.Cu'):.3f} A, 0.60 mm -> "
          f"{trace_ampacity(0.60, 'B.Cu'):.3f} A, 0.30 mm -> "
          f"{trace_ampacity(0.30, 'B.Cu'):.3f} A")
    print(f"  Nets checked   : {', '.join(selected)}")
    print()

    failed, total = [], 0
    for net in selected:
        ok, lines = check_net(net, rails[net], cache, zones, values)
        for line in lines:
            print(line)
        print()
        total += 1
        if not ok:
            failed.append(net)

    print("=" * WIDTH)
    if report_only:
        print(f"REPORT ONLY — {total - len(failed)}/{total} net(s) within "
              f"dT {_DELTA_T_LIMIT_C:.0f} degC"
              + (f"; over: {', '.join(failed)}" if failed else ""))
        print("=" * WIDTH)
        return 0
    if not failed:
        print(f"Results: PASS — {total}/{total} power net(s), copper "
              f"carries the declared current within "
              f"dT {_DELTA_T_LIMIT_C:.0f} degC")
        print("=" * WIDTH)
        return 0
    print(f"Results: FAIL — {len(failed)}/{total} net(s): "
          f"{', '.join(failed)}")
    print("=" * WIDTH)
    print()
    print("REMEDIATION:")
    print("  Starved copper is invisible on the bench at idle current and")
    print("  shows up as a hot trace at rated load. Widen the binding run,")
    print("  parallel it on another layer (stitch both ends with vias the")
    print("  barrel gate will then judge), or — only if the electrical")
    print("  argument is genuinely about the current — correct the declared")
    print("  current AT ITS CITATION in _rail_declarations(). Do not touch")
    print("  the ampacity constants.")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Structural as e:
        print(f"STRUCTURAL ERROR: {e}", file=sys.stderr)
        sys.exit(2)
