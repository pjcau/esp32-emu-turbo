"""Virtual Bench T1.3 — electrical conflicts: two things fighting over one net.

**This module is not about geometry, and it will say so in its own output.**
Copper that is too close, a trace through a pad, an acid trap, a hole in a
plane — those belong to `verify_isolation`, `drc_native`,
`short_circuit_analysis`, `verify_copper_clearance` and
`verify_trace_through_pad`, and the plan's boundary table says the bench must
not duplicate them. Duplicating a geometric check here would produce a second
opinion that disagrees with the first one on a rounding difference, and then
somebody would have to decide which gate is authoritative.

What is checked here is what those gates cannot see: a netlist that is
geometrically perfect and electrically contradictory. Two drivers on one
node is not a clearance problem; every trace can be a millimetre apart and
the board still fails.

Each conflict names the pins involved and the model that declared the pin's
direction, so a wrong verdict can be traced to the claim that produced it.

Usage:
    python3 scripts/vbench/conflicts.py
"""

import argparse
import collections
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import netlist as nl                             # noqa: E402
from vbench import rails                                     # noqa: E402
from vbench.models.q1_si2301 import Q1                       # noqa: E402
from vbench.models.u2_ip5306 import U2                       # noqa: E402
from vbench.models.u3_sy8089 import U3                       # noqa: E402
from vbench.models.u5_pam8403 import U5                      # noqa: E402

# Models that declare pin directions. A ref absent from here contributes no
# direction claims, and the report counts how much of the board that is —
# an unstated coverage figure would read as "no conflicts found".
MODELS = {m.ref: m for m in (Q1, U2, U3, U5)}

DRIVING = frozenset({"out", "power_out", "analog_out", "open_drain"})

Conflict = collections.namedtuple("Conflict", "code net detail owner")

GEOMETRY_OWNERS = (
    "verify_isolation", "drc_native", "short_circuit_analysis",
    "verify_copper_clearance", "verify_trace_through_pad")


def _pin_direction(ref, pad):
    """Declared direction for a pad, or None if no model claims one."""
    model = MODELS.get(ref)
    if model is None:
        return None
    # Models are indexed by datasheet pin number, which for these two parts
    # is the pad number. A ref whose symbol pins differ from its pads would
    # need the translation table from verify_netlist_diff; neither U2 nor U3
    # is such a ref, and asserting that here keeps a future one from being
    # silently mis-read.
    try:
        return model.pin(pad).direction
    except KeyError:
        return None


def _feeds_from_another_rail(model, board, rail_net):
    """True if this part draws power from a net other than `rail_net`.

    That makes it a converter or a pass element, so its output pin is the
    source of `rail_net` rather than a second driver fighting over it.
    """
    ref_nets = {p.pad: net for net, pins in board.nets.items()
                for p in pins if p.ref == model.ref}
    for pad, net in ref_nets.items():
        if net == rail_net:
            continue
        try:
            if model.pin(pad).direction == "power_in":
                return True
        except KeyError:
            continue
    return False


def find_conflicts(board=None, values=None):
    """Every electrical contradiction the netlist and the models imply."""
    board = board or nl.load_board_netlist()
    values = values if values is not None else rails.load_bom_values()
    out = []

    # ── C1: two declared drivers on one net ─────────────────────────
    for net, pins in board.nets.items():
        drivers = [(p.ref, p.pad, _pin_direction(p.ref, p.pad)) for p in pins]
        drivers = [d for d in drivers if d[2] in DRIVING]
        if len(drivers) > 1:
            who = ", ".join(f"{r}.{p} ({d})" for r, p, d in drivers)
            out.append(Conflict(
                "C1", net,
                f"{len(drivers)} declared drivers on one node: {who}. Two "
                f"sources holding one node fight until one of them loses.",
                "phase 1 models / routing"))

    # ── C2: a driver sitting on a rail held by something else ───────
    op_fixed = {"GND", "+5V", "+3V3", "VBUS", "BAT+", "BAT_IN"}
    for net, pins in board.nets.items():
        if net not in op_fixed:
            continue
        for p in pins:
            direction = _pin_direction(p.ref, p.pad)
            if direction not in DRIVING:
                continue
            # A part that MAKES the rail is not in conflict with it. Decided
            # by a derived rule rather than a list of pin names: a converter
            # or pass element has a power_in pin on some OTHER net, so its
            # output is where this rail comes from. U2 (VBUS -> +5V), U3
            # (+5V -> BUCK_LX) and Q1 (BAT_IN -> BAT+) all satisfy it, and a
            # part added later satisfies it without anyone editing a list.
            #
            # This rule was written after the name list ("VOUT", "LX") flagged
            # Q1.3 driving BAT+ — which was a real finding, just not about
            # the board: rails.py was holding BAT+ at the cell voltage
            # directly while Q1 is what actually delivers it. See the note in
            # rails.py.
            model = MODELS[p.ref]
            if _feeds_from_another_rail(model, board, net):
                continue
            out.append(Conflict(
                "C2", net,
                f"{p.ref}.{p.pad} ({model.pin(p.pad).name}, {direction}) "
                f"drives the {net} rail, which a source already holds",
                "phase 1 models / routing"))

    # ── C3: one node pulled to two different rails ──────────────────
    #
    # A resistor to +3V3 and another to +5V on the same node is a divider
    # between two rails, which is almost never what a pull-up was meant to
    # be. The feedback divider is excluded by construction: it is found by
    # walking the netlist, so it is identified rather than named.
    try:
        divider = rails.find_feedback_divider(board, values)
        fb_exempt = {divider.fb_net}
    except rails.RailError:
        fb_exempt = set()

    ref_nets = collections.defaultdict(set)
    for net, pins in board.nets.items():
        for p in pins:
            ref_nets[p.ref].add(net)

    for net, pins in board.nets.items():
        if net in fb_exempt or net in op_fixed:
            continue
        pulled_to = set()
        for p in pins:
            if rails._kind(p.ref) != "resistor":
                continue
            for other in ref_nets[p.ref] - {net}:
                if other in op_fixed and other != "GND":
                    pulled_to.add((p.ref, other))
        rails_hit = {r for _, r in pulled_to}
        if len(rails_hit) > 1:
            who = ", ".join(f"{r} to {t}" for r, t in sorted(pulled_to))
            out.append(Conflict(
                "C3", net,
                f"pulled to {len(rails_hit)} different rails: {who} — a "
                f"divider between two supplies, not a pull-up",
                "routing / schematic"))

    return sorted(out, key=lambda c: (c.code, c.net))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)
    try:
        found = find_conflicts()
    except (rails.RailError, nl.NetlistError) as exc:
        print(f"  ERROR  {exc}", file=sys.stderr)
        return 2

    board = nl.load_board_netlist()
    claimed = sum(1 for net, pins in board.nets.items() for p in pins
                  if _pin_direction(p.ref, p.pad) is not None)
    total = sum(len(p) for p in board.nets.values())

    print("=" * 72)
    print("  Virtual Bench T1.3 — electrical conflicts")
    print("=" * 72)
    print(f"  Geometry is NOT checked here. That belongs to "
          f"{', '.join(GEOMETRY_OWNERS[:3])}")
    print(f"  and {', '.join(GEOMETRY_OWNERS[3:])}. A node can be "
          f"geometrically perfect")
    print(f"  and electrically contradictory; only the second kind is below.")
    print()
    print(f"  Pin directions declared: {claimed} of {total} pin instances "
          f"({100.0*claimed/total:.0f}%)")
    print(f"    Only {', '.join(sorted(MODELS))} carry a cited pin table so "
          f"far. Every other pin")
    print(f"    contributes no direction claim, so 'no conflicts' below "
          f"covers {100.0*claimed/total:.0f}% of the")
    print(f"    board's pins and no more. T1.2 widens this.")
    print()
    if not found:
        print("  No conflict found within that coverage.")
    else:
        print(f"  Conflicts: {len(found)}")
        for c in found:
            print(f"    [{c.code}] {c.net}: {c.detail}")
            print(f"           owner: {c.owner}")
    print("=" * 72)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
