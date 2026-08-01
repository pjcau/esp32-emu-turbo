#!/usr/bin/env python3
"""Mutation tests for verify_power_via_ampacity.py — the gate must object.

The bug being guarded against is the one no other gate in this repo can
see: a power net that is perfectly connected (verify_power_net_integrity
green, DRC green, netlist green) and yet crosses between layers through a
single 0.2 mm barrel rated half an amp. Connectivity checks answer "is
it joined"; nothing answered "is the joint big enough".

Every case here is built on SYNTHETIC copper — an in-memory cache-shaped
dict and a hand-drawn zone — so it stays valid whatever the real layout
does next. The real board is never mutated; it appears once, as a control
whose verdict is recorded rather than asserted.

    M1  one 0.2 mm barrel for a 2 A rail        starved     -> exit 1
    M2  eight barrels in parallel, same rail    adequate    -> exit 0
    M3  M1's geometry, rail rated 0.4 A         discriminates-> exit 0
    M4  a power net on the board, undeclared    blind spot  -> exit 2
    M5  a declared net absent from the board    contract    -> exit 2
    M6  the declared source pad is not on the net           -> exit 2
    M7  the rail's only loads are C and R       dead rail   -> exit 2
    M8  an unplated (zero-drill) barrel on a net            -> exit 2
    M9  a vbench Param renamed under the citation           -> exit 2
    M10 the IPC-2221 ampacity numbers themselves            (unit check)
    M11 the min cut is the NARROW side, not the sum         (unit check)
    C   the real board at HEAD                  recorded, not asserted

Usage:
    python3 scripts/test_power_via_ampacity.py
"""

from __future__ import annotations

import collections
import contextlib
import io
import math
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shapely.geometry import Polygon  # noqa: E402

import verify_power_via_ampacity as vpa  # noqa: E402

Rail = collections.namedtuple("Rail", "current volts sources why")
Geom = collections.namedtuple("Geom", "zones")

NET = "+3V3"
NET_ID = 4


# ── Synthetic copper ────────────────────────────────────────────────
#
# One inner plane, two B.Cu landing pads 50 mm apart, and a chosen number
# of barrels dropping each pad into the plane. All the current between
# the pads has to cross both barrel groups, so the min cut is whichever
# group is smaller — which is exactly what the gate must report.
#
#     B.Cu   [U9.1]===o o o                    o o o===[U8.1]
#                      |||                      |||
#     In2.Cu  ==========================================

def pad(ref, num, x, y, net_id=NET_ID, layer="B.Cu", kind="smd", drill=0.0):
    return {"ref": ref, "num": num, "x": x, "y": y, "w": 1.0, "h": 1.0,
            "shape": "rect", "layer": layer, "net": net_id,
            "type": kind, "drill": drill}


def via(x, y, drill=0.2, net_id=NET_ID):
    return {"x": x, "y": y, "size": drill + 0.3, "drill": drill,
            "net": net_id}


def seg(x1, y1, x2, y2, layer="B.Cu", width=1.0, net_id=NET_ID):
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "width": width,
            "layer": layer, "net": net_id}


def drop(x, y, count, drill=0.2):
    """`count` barrels in a row at x, plus the B.Cu copper joining them."""
    vias = [via(x + 0.6 * i, y, drill) for i in range(count)]
    span = seg(x - 0.6, y, x + 0.6 * count, y)
    return vias, span


def fixture(source_barrels, load_barrels, extra_pads=(), drill=0.2):
    src_vias, src_seg = drop(5.0, 10.0, source_barrels, drill)
    load_vias, load_seg = drop(50.0, 10.0, load_barrels, drill)
    cache = {
        "nets": [{"id": NET_ID, "name": NET}],
        "net_types": {NET: "power"},
        "pads": [pad("U9", "1", 5.0, 10.0), pad("U8", "1", 50.0, 10.0)]
                + list(extra_pads),
        "vias": src_vias + load_vias,
        "segments": [src_seg, load_seg],
    }
    zones = [{"net": NET, "layer": "In2.Cu", "priority": 0,
              "polys": [Polygon([(0, 0), (60, 0), (60, 20), (0, 20)])]}]
    return cache, zones


def rails_for(current=2.0, sources=("U9.1",), nets=(NET,)):
    return {n: Rail(current, 3.3, sources, "synthetic fixture")
            for n in nets}


# ── Harness ─────────────────────────────────────────────────────────

def run(cache, zones, rails, values=None):
    """Run the gate against synthetic sources of truth; return its rc."""
    saved = (vpa.load_cache, vpa.parse_copper, vpa._rail_declarations,
             vpa._placement_values)
    vpa.load_cache = lambda *a, **k: cache
    vpa.parse_copper = lambda *a, **k: Geom(zones)
    vpa._rail_declarations = lambda: rails
    vpa._placement_values = lambda: dict(values or {})
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            return vpa.main(argv=[])
    except vpa.Structural:
        return 2
    finally:
        (vpa.load_cache, vpa.parse_copper, vpa._rail_declarations,
         vpa._placement_values) = saved


def run_real():
    """The real board, untouched. Returns (exit code, captured report)."""
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = vpa.main(argv=[])
    except vpa.Structural as e:
        return 2, f"STRUCTURAL: {e}"
    return code, buf.getvalue()


def main() -> int:
    print("=" * 76)
    print("POWER-VIA AMPACITY GATE MUTATION SUITE")
    print("=" * 76)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {why}" if why
                                                         else ""))
        if not ok:
            failures.append(name)

    # M1 — the regression. One barrel, 2 A rail.
    cache, zones = fixture(source_barrels=1, load_barrels=8)
    rc = run(cache, zones, rails_for(current=2.0))
    check("M1 one 0.2mm barrel for a 2 A rail", rc == 1, f"rc={rc}, want 1")

    # M2 — the same rail, stitched properly.
    cache, zones = fixture(source_barrels=8, load_barrels=8)
    rc = run(cache, zones, rails_for(current=2.0))
    check("M2 eight parallel barrels pass", rc == 0, f"rc={rc}, want 0")

    # M3 — M1's geometry under a rail it CAN carry. Without this, M1
    # would also be satisfied by a gate that always fails.
    cache, zones = fixture(source_barrels=1, load_barrels=8)
    rc = run(cache, zones, rails_for(current=0.4))
    check("M3 the same starved geometry passes a 0.4 A rail", rc == 0,
          f"rc={rc}, want 0")

    # M4 — a power net exists on the board and nobody declared a current
    # for it. Silence here reads as green, which is worse than red.
    cache, zones = fixture(source_barrels=8, load_barrels=8)
    cache["net_types"] = {NET: "power", "+12V": "power"}
    rc = run(cache, zones, rails_for(current=2.0))
    check("M4 undeclared power net is a hard error", rc == 2,
          f"rc={rc}, want 2")

    # M5 — the gate names a net the board does not have (renamed in the
    # generator). It must not quietly check nothing.
    cache, zones = fixture(source_barrels=8, load_barrels=8)
    rails = rails_for(current=2.0)
    rails["+3V4"] = Rail(2.0, 3.3, ("U9.1",), "renamed rail")
    rc = run(cache, zones, rails)
    check("M5 declared net absent from the board", rc == 2,
          f"rc={rc}, want 2")

    # M6 — the source moved. Measuring from the wrong end measures nothing.
    cache, zones = fixture(source_barrels=8, load_barrels=8)
    rc = run(cache, zones, rails_for(current=2.0, sources=("L9.1",)))
    check("M6 source pad not on the net", rc == 2, f"rc={rc}, want 2")

    # M7 — a rail whose only loads are a capacitor and a resistor powers
    # nothing; the source declaration must be wrong.
    cache, zones = fixture(source_barrels=8, load_barrels=8)
    cache["pads"] = [p for p in cache["pads"] if p["ref"] != "U8"]
    cache["pads"].append(pad("C9", "1", 50.0, 10.0))
    rc = run(cache, zones, rails_for(current=2.0), values={"C9": "100nF"})
    check("M7 rail with no consumer", rc == 2, f"rc={rc}, want 2")

    # M8 — a hole with no plating cannot carry current, and must not be
    # silently scored as if it could.
    cache, zones = fixture(source_barrels=8, load_barrels=8)
    cache["vias"][0]["drill"] = 0.0
    rc = run(cache, zones, rails_for(current=2.0))
    check("M8 unplated barrel on a net", rc == 2, f"rc={rc}, want 2")

    # M9 — the citations are live reads from the vbench models. If a
    # Param is renamed the citation dangles, and a dangling citation must
    # stop the gate, not fall back to a number typed here.
    real_before = vpa._rail_declarations()[NET].current
    stub = types.ModuleType("scripts.vbench.models.u3_sy8089")
    stub.U3 = types.SimpleNamespace(
        ref="U3", part="SY8089AAAC",
        datasheet=types.SimpleNamespace(doc="U3_SY8089AAAC_C78988.pdf"),
        params={})            # i_out_continuous renamed away
    saved = sys.modules.get("scripts.vbench.models.u3_sy8089")
    sys.modules["scripts.vbench.models.u3_sy8089"] = stub
    try:
        vpa._rail_declarations()
        broke = False
    except vpa.Structural:
        broke = True
    finally:
        if saved is None:
            del sys.modules["scripts.vbench.models.u3_sy8089"]
        else:
            sys.modules["scripts.vbench.models.u3_sy8089"] = saved
    check("M9 renamed vbench Param breaks the citation",
          broke and vpa._rail_declarations()[NET].current == real_before,
          f"raised={broke}, restored={real_before} A")

    # M10 — the ampacity numbers are the whole verdict. Recompute them
    # here from the same published formula so a silent edit to k, the
    # plating thickness or the temperature rise cannot pass unnoticed.
    def ipc2221(drill_mm, k=0.024, plating_mm=0.018, dt=10.0):
        area_mil2 = math.pi * drill_mm * plating_mm / (0.0254 ** 2)
        return k * dt ** 0.44 * area_mil2 ** 0.725

    same = all(abs(vpa.via_ampacity(d) - ipc2221(d)) < 1e-9
               for d in (0.2, 0.3, 0.35, 0.5))
    conservative = vpa.via_ampacity(0.3) < 1.0   # vs the "1 A" rule of thumb
    check("M10 ampacity follows IPC-2221B and stays under the rule of thumb",
          same and conservative,
          f"0.3mm -> {vpa.via_ampacity(0.3):.3f} A")

    # M11 — a min cut is the narrow side, never the total. A gate that
    # summed every barrel on the net would call M1 adequate (9 barrels,
    # 4.7 A) and miss the single one that carries everything.
    cache, zones = fixture(source_barrels=1, load_barrels=8)
    model = vpa.build_model(NET, cache, zones)
    src = vpa.islands_touching(model, model.pads[0].geom,
                               model.pads[0].layers)
    dst = vpa.islands_touching(model, model.pads[1].geom,
                               model.pads[1].layers)
    cut = vpa.min_via_cut(model, src, dst)
    check("M11 the cut is the narrow side, not the sum",
          len(model.barrels) == 9 and len(cut.barrels) == 1
          and abs(cut.capacity - vpa.via_ampacity(0.2)) < 1e-9,
          f"{len(model.barrels)} barrels on the net, cut = "
          f"{len(cut.barrels)} worth {cut.capacity:.3f} A")

    # C — the real board. Recorded, never asserted: this suite must stay
    # green both before and after the layout is fixed.
    rc, report = run_real()
    verdict = {0: "PASS", 1: "FAIL", 2: "STRUCTURAL"}.get(rc, f"rc={rc}")
    check("C real board runs without crashing", rc in (0, 1),
          f"HEAD verdict: {verdict}")
    for line in report.splitlines():
        if line.strip().startswith(("FAIL", "Results:")):
            print(f"        | {line.strip()}")

    print("-" * 76)
    if failures:
        print(f"Results: FAIL — {len(failures)} case(s): "
              f"{', '.join(failures)}")
        return 1
    print("Results: PASS — 12/12 mutations detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
