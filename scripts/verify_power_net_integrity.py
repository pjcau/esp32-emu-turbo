#!/usr/bin/env python3
"""Power-net integrity gate — every power net must be ONE piece of copper.

FAILS (exit 1) when any of +3V3 / +5V / GND / VBUS / BAT+ resolves to more
than one geometric group on the fabricated board.

Why this gate exists
--------------------
PCB v1 shipped completely dead. The AMS1117 produced a clean 3.3 V into a
4.92 mm² orphan island while the ESP32, the display connector and the SD card
sat at 0 V. ``In2.Cu`` is a split plane: a ``+3V3`` zone at priority 0 covering
the whole board, and two ``+5V`` zones at priority 1 and 2 that carve it up.
The priority-1 ``+5V`` rectangle swallowed the regulator output.

Two independent checks failed to catch it, for the SAME reason — both assumed
"an inner-layer zone stitches the net together", which is false when the zone
is itself split:

  1. ``scripts/drc_baseline.json`` carried ``"unconnected_zone": 7``. KiCad's
     DRC WAS reporting the real opens; they were baselined as
     "Power/data nets connected through inner-layer zones".
  2. ``scripts/verify_net_connectivity.py`` skipped GND / +3V3 / +5V by
     default, because it does not parse zone ``filled_polygon`` blocks.

Both suppressions were removed in the same commit that added this file. See
``website/docs/rework/incident-3v3-split-plane.md``.

There is no allowlist here, by design. A power net split in two is an open
circuit; there is no rationale under which that is acceptable, and the project
rule is: never silence an error.

Method
------
``scripts/pcb_copper_graph.py`` — union-find over zone filled_polygon islands,
vias, track segments and pads that share a copper layer and overlap. Copper is
modelled with an over-approximation, so a reported split is never a geometric
false positive (see that module's docstring).

Usage:
    python3 scripts/verify_power_net_integrity.py            # the 5 power nets
    python3 scripts/verify_power_net_integrity.py +3V3 GND   # named nets only
    python3 scripts/verify_power_net_integrity.py --pcb path/to/board.kicad_pcb

Exit code 0 = every power net is a single connected group, 1 = at least one
net is fragmented (or missing from the board entirely).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pcb_copper_graph import (  # noqa: E402
    DEFAULT_PCB,
    group_area,
    group_distance,
    group_island_distance,
    group_islands,
    group_pads,
    groups_for,
    parse_copper,
)

# Nets that carry supply current. Every one of these must be a single piece of
# copper — a second group means some part of the circuit has no source.
POWER_NETS = ("+3V3", "+5V", "GND", "VBUS", "BAT+")

WIDTH = 72


def describe_group(group, main, index):
    """Human-readable, actionable description of one orphan group."""
    pads = group_pads(group)
    islands = group_islands(group)
    area = group_area(group)

    lines = [f"    Group {index}: {len(group)} copper item(s)"]
    lines.append(f"      pads          : "
                 f"{', '.join(pads) if pads else '(no pads — orphan copper)'}")
    if not pads:
        # No pad to name the group by — list the raw copper so the offending
        # item can still be found in the layout.
        for n in group[:4]:
            lines.append(f"        {n.label}")
        if len(group) > 4:
            lines.append(f"        ... and {len(group) - 4} more")
    if islands:
        areas = ", ".join(f"{g.area:.2f}" for g in
                          sorted(islands, key=lambda g: -g.area))
        lines.append(f"      zone islands  : {len(islands)} "
                     f"({areas} mm²; total {area:.2f} mm²)")
    else:
        lines.append("      zone islands  : none (traces/vias/pads only)")
    pts = [n.geom.centroid for n in group if not n.geom.is_empty]
    if pts:
        cx = sum(p.x for p in pts) / len(pts)
        cy = sum(p.y for p in pts) / len(pts)
        lines.append(f"      location      : ~({cx:.2f}, {cy:.2f}) mm")
    dist = group_distance(group, main)
    if dist == dist:  # not NaN
        lines.append(f"      nearest copper of main group : {dist:.2f} mm")
    else:
        lines.append("      nearest copper of main group : not measurable "
                     "— the copper above is degenerate (zero extent)")
    island_gap = group_island_distance(group, main)
    if island_gap == island_gap:  # not NaN
        lines.append(f"      pour gap to main plane       : "
                     f"{island_gap:.2f} mm")
    return lines


def check_net(net, geom):
    """Return (ok, groups, message_lines) for one net."""
    groups = groups_for(net, geom)

    if not groups:
        return False, groups, [
            f"  FAIL  {net}: net carries NO copper at all.",
            "        Either the net was renamed in the generator or this gate",
            "        is checking a name the board does not have. Both are bugs.",
        ]

    if len(groups) == 1:
        pads = group_pads(groups[0])
        return True, groups, [
            f"  PASS  {net}: 1 group, {len(groups[0])} copper item(s), "
            f"{len(pads)} pad(s), {group_area(groups[0]):.2f} mm² poured"
        ]

    main = groups[0]
    lines = [
        f"  FAIL  {net}: {len(groups)} electrically separate groups "
        f"— OPEN CIRCUIT on the fabricated board.",
        f"    Group 0 (main): {len(main)} copper item(s), "
        f"{group_area(main):.2f} mm² poured, "
        f"{len(group_pads(main))} pad(s)",
    ]
    for i, g in enumerate(groups[1:], 1):
        lines.extend(describe_group(g, main, i))
    return False, groups, lines


def main():
    ap = argparse.ArgumentParser(
        description="Fail when a power net is split into multiple groups.")
    ap.add_argument("nets", nargs="*", default=None,
                    help=f"nets to check (default: {' '.join(POWER_NETS)})")
    ap.add_argument("--pcb", default=str(DEFAULT_PCB),
                    help="path to the .kicad_pcb to check")
    args = ap.parse_args()

    nets = args.nets or list(POWER_NETS)

    print()
    print("=" * WIDTH)
    print("Power-net integrity (zone-aware union-find on real copper)")
    print("=" * WIDTH)
    print()

    geom = parse_copper(args.pcb)
    zone_islands = sum(len(z["polys"]) for z in geom.zones)
    print(f"  PCB              : {args.pcb}")
    print(f"  Zones            : {len(geom.zones)} "
          f"({zone_islands} filled islands)")
    print(f"  Vias / segments  : {len(geom.vias)} / {len(geom.segments)}")
    print(f"  Footprints       : {len(geom.footprints)}")
    print(f"  Nets checked     : {', '.join(nets)}")
    print()

    failures = []
    for net in nets:
        ok, _groups, lines = check_net(net, geom)
        for ln in lines:
            print(ln)
        if not ok:
            failures.append(net)
        print()

    print("=" * WIDTH)
    if not failures:
        print(f"Results: PASS — all {len(nets)} power net(s) are a single "
              f"connected copper group")
        print("=" * WIDTH)
        return 0

    print(f"Results: FAIL — {len(failures)} of {len(nets)} power net(s) "
          f"fragmented: {', '.join(failures)}")
    print("=" * WIDTH)
    print()
    print("REMEDIATION:")
    print("  A power net in more than one group means part of the circuit has")
    print("  no source. This is an open, not a short — a thermal camera shows")
    print("  nothing and there is no measurable current anywhere.")
    print()
    print("  Most common cause: a higher-priority pour zone on an inner layer")
    print("  carves the lower-priority zone into islands. Fix in")
    print("  scripts/generate_pcb/routing.py::_power_zones() by raising the")
    print("  starved net's zone priority, reshaping the overlapping zone so it")
    print("  does not enclose the source, or routing explicit copper from the")
    print("  source to the load instead of relying on the plane.")
    print()
    print("  Do NOT allowlist a net here to make this pass.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
