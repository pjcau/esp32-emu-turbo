#!/usr/bin/env python3
"""Copper queries against the pcb_cache — answers in ~10 lines, not 265k tokens.

Why this exists
---------------
Every "which net is on U2.6?" question used to cost either a hand-written
inline Python snippet over load_cache() (rewritten from scratch each time,
~30 lines of session context per question) or — worse — a Read of the
.kicad_pcb, which .claudeheavy blocks precisely because it costs ~265k
tokens. This is the canonical access path, promoted to a CLI: one Bash line
in, a few lines out.

Usage:
    python3 scripts/pcb_query.py nets                  # every net + pad count
    python3 scripts/pcb_query.py net +3V3              # members of one net
    python3 scripts/pcb_query.py pads U2               # a component's pads
    python3 scripts/pcb_query.py pad U2 6              # one pad's net + position
    python3 scripts/pcb_query.py where U2              # placement + extent
    python3 scripts/pcb_query.py stats                 # board totals

The cache (hardware/kicad/.pcb_cache.json) is SHA-256-keyed to the board,
so answers can never be stale; regeneration is automatic on first query
after the board changes.
"""

import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pcb_cache import load_cache  # noqa: E402


def _nets(c):
    return {n["id"]: n["name"] for n in c["nets"]}


def cmd_nets(c, _args):
    nm = _nets(c)
    count = defaultdict(int)
    for p in c["pads"]:
        n = nm.get(p.get("net"))
        if n:
            count[n] += 1
    for name in sorted(count):
        print(f"{name:16} {count[name]:3} pads")


def cmd_net(c, args):
    name = args[0]
    nm = _nets(c)
    nid = next((i for i, n in nm.items() if n == name), None)
    if nid is None:
        sys.exit(f"no net named {name!r} — try `nets`")
    pads = sorted(f"{p['ref']}.{p.get('num')}" for p in c["pads"]
                  if p.get("net") == nid)
    vias = [v for v in c["vias"] if v.get("net") == nid]
    seg_len = defaultdict(float)
    for s in c["segments"]:
        if s.get("net") == nid:
            w = round(s.get("width") or s.get("w"), 3)
            seg_len[(s.get("layer"), w)] += math.dist(
                (s["x1"], s["y1"]), (s["x2"], s["y2"]))
    print(f"net {name}: {len(pads)} pads, {len(vias)} vias")
    print("  pads:", ", ".join(pads) or "-")
    for (layer, w), L in sorted(seg_len.items()):
        print(f"  {layer} w={w}: {L:.1f} mm")


def cmd_pads(c, args):
    ref = args[0]
    nm = _nets(c)
    rows = [p for p in c["pads"] if p.get("ref") == ref]
    if not rows:
        sys.exit(f"no component {ref!r}")
    for p in sorted(rows, key=lambda p: str(p.get("num"))):
        print(f"{ref}.{p.get('num'):>3}  net={nm.get(p.get('net')) or '-':14} "
              f"({p.get('x'):.2f}, {p.get('y'):.2f})")


def cmd_pad(c, args):
    ref, num = args[0], args[1]
    nm = _nets(c)
    for p in c["pads"]:
        if p.get("ref") == ref and str(p.get("num")) == num:
            print(f"{ref}.{num}: net={nm.get(p.get('net')) or '-'} "
                  f"at ({p.get('x'):.2f}, {p.get('y'):.2f})")
            return
    sys.exit(f"no pad {ref}.{num}")


def cmd_where(c, args):
    ref = args[0]
    rows = [p for p in c["pads"] if p.get("ref") == ref]
    if not rows:
        sys.exit(f"no component {ref!r}")
    xs = [p["x"] for p in rows]
    ys = [p["y"] for p in rows]
    print(f"{ref}: {len(rows)} pads, centre "
          f"({(min(xs)+max(xs))/2:.2f}, {(min(ys)+max(ys))/2:.2f}), "
          f"extent {max(xs)-min(xs):.2f} x {max(ys)-min(ys):.2f} mm")


def cmd_stats(c, _args):
    nm = _nets(c)
    named = [n for n in nm.values() if n]
    print(f"{len(named)} nets, {len(c['pads'])} pads, {len(c['vias'])} vias, "
          f"{len(c['segments'])} segments, {len(c['zones'])} zones")


COMMANDS = {
    "nets": (cmd_nets, 0), "net": (cmd_net, 1), "pads": (cmd_pads, 1),
    "pad": (cmd_pad, 2), "where": (cmd_where, 1), "stats": (cmd_stats, 0),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__.split("Usage:")[1].rsplit("The cache", 1)[0])
    fn, nargs = COMMANDS[sys.argv[1]]
    args = sys.argv[2:]
    if len(args) < nargs:
        sys.exit(f"{sys.argv[1]} needs {nargs} argument(s)")
    fn(load_cache(), args)


if __name__ == "__main__":
    main()
