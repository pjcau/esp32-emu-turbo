#!/usr/bin/env python3
"""Fail on copper that stops in the air — track ends reaching nothing.

The gap this closes
-------------------
Three checks look adjacent to this and none of them catches it:

- `verify_net_connectivity` asks whether each net is ONE connected copper
  component. A stub hanging off an otherwise-routed net is still part of
  that one component, so the net passes.
- KiCad DRC reports unconnected *pads*. A dangling stub leaves every pad
  connected — the pad is reached by the other end of the trace.
- `verify_trace_through_pad` / `verify_trace_crossings` look for copper
  that touches something it should not. This is the opposite: copper that
  touches nothing at all.

So a track can end 0.8 mm short of the via it was meant to reach and
every gate in the repo stays green. The copper is still there, drawn,
fabricated, and connected to nothing at that end.

What counts as reaching something
---------------------------------
An endpoint is fine when it is a junction with another segment on the
same layer and net, lands on a via or a pad of its own net, or ends
inside its own zone fill on that layer. Anything else is a dead end.

Severity note: a dangling stub on a heavily-meshed net like GND is dead
copper and an unterminated antenna stub rather than a broken connection —
but it is always a routing mistake, and "which stubs are harmless" is not
a judgement this gate should be making silently. Fix them or record the
exception with its reason.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_net_explorer import dangling_ends  # noqa: E402
from pcb_cache import load_cache  # noqa: E402

# (net, layer, x, y) -> why this end is deliberately left in the air.
# Empty on purpose: there is no known-good dangling copper on this board.
ALLOWED = {}


def main():
    cache = load_cache()
    net_name = {n["id"]: n["name"] for n in cache["nets"]}

    ends = dangling_ends(cache, net_name)
    flagged, allowed = [], []
    for e in ends:
        k = (e["net"], e["layer"], round(e["x"], 3), round(e["y"], 3))
        (allowed if k in ALLOWED else flagged).append(e)

    print()
    print("=" * 62)
    print("Dangling copper check (track ends that reach nothing)")
    print("=" * 62)
    print()
    print(f"  Segments checked : {len(cache['segments'])}")
    print(f"  Vias             : {len(cache['vias'])}")
    print(f"  Pads             : {len(cache['pads'])}")
    print()

    if flagged:
        for e in flagged:
            print(f"  FAIL  {e['net']:12s} {e['layer']:7s} "
                  f"({e['x']:8.3f}, {e['y']:8.3f})  "
                  f"— this end touches no pad, via, segment or zone")
    else:
        print("  PASS  Every track end lands on a pad, via, junction "
              "or its own zone fill")

    for e in allowed:
        k = (e["net"], e["layer"], round(e["x"], 3), round(e["y"], 3))
        print(f"  NOTE  {e['net']:12s} {e['layer']:7s} "
              f"({e['x']:8.3f}, {e['y']:8.3f}) — allowed: {ALLOWED[k]}")

    print()
    print("=" * 62)
    print(f"Results: {len(flagged)} dangling, {len(allowed)} documented")
    if flagged:
        print("STATUS: FAIL — copper that ends in the air is a routing "
              "mistake, even when the net is connected elsewhere")
    else:
        print("STATUS: PASS")
    print("=" * 62)
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
