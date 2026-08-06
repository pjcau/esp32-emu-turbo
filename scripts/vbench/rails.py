"""Virtual Bench T1.1 — the DC operating point: what voltage sits on every net.

Reads the netlist from Phase 0, the passive values from the BOM, and the
regulator behaviour from the cited models, then solves the resistive network
for a DC voltage on every net.

Three decisions shape what this can and cannot say.

**The rails are derived, not declared.** +3V3 is not "3.3 V because the net
is called +3V3". It is `V_REF * (1 + R_top/R_bottom)` with V_REF from the
SY8089's page 4 and the two resistors identified *by walking the netlist*
from the FB pin. On this board that gives 3.327 V, not 3.30 — and the answer
moves if someone changes R25 or R26, which is the entire point. A net name
is not a measurement.

**A net with no resistive path to a source is UNDEFINED, and that is
reported, not defaulted.** A solver that quietly assigns 0 V to a floating
node produces a plausible table with a lie in it. This is what makes the
EN net visible: its only pins are U1.3 and SW15.1, the switch is open at
DC, and there is no pull-up — so EN has no defined level, which is
R25-CRIT-1 arrived at from the physics instead of from reading a comment.

**Capacitors are open, inductors are short, switches are open.** That is
what DC means. It also means this module says nothing about ripple, rise
time or inrush; those are T1.4, and the report says so rather than leaving
the reader to assume the silence is a pass.

Usage:
    python3 scripts/vbench/rails.py
    python3 scripts/vbench/rails.py --buttons-pressed
    python3 scripts/vbench/rails.py --source battery --soc 0.2
"""

import argparse
import collections
import csv
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import netlist as nl                             # noqa: E402
from vbench import sources                                   # noqa: E402
from vbench.models import require_valid                      # noqa: E402
from vbench.models.u2_ip5306 import U2, UNESTABLISHED        # noqa: E402
from vbench.models.u3_sy8089 import U3, v_out_spread         # noqa: E402

# The GENERATED BOM, not the release copy. The bench solves the netlist
# parsed out of hardware/kicad/esp32-emu-turbo.kicad_pcb, so it has to read
# the passive values that belong to THAT board; release_jlcpcb/ is a
# snapshot of the last order and lags every change until a release is cut.
# This is the repo's own split — verify_gate_coverage.py states it: "the
# content gates read THESE, while the release_jlcpcb/ copies are owned by
# the order-manifest integrity gate".
#
# The mismatch was invisible while the two files agreed. It stopped being
# invisible when the SW16 respin added R32/R33/R34: solve_dc found a
# resistor spanning two nets with no value and refused to guess, which is
# the correct behaviour and was pointing at the wrong BOM.
BOM = os.path.join(BASE, "hardware", "kicad", "jlcpcb", "bom.csv")

UNDEFINED = None        # a net with no DC path to any source


class RailError(RuntimeError):
    """The operating point cannot be computed. Never a warning."""


# ── BOM values ──────────────────────────────────────────────────────

_MULT = {"": 1.0, "R": 1.0, "K": 1e3, "M": 1e6, "G": 1e9,
         "U": 1e-6, "N": 1e-9, "P": 1e-12}


def _parse_value(comment):
    """'100k 0805' -> 100000.0 ; '0.47uF 0805' -> 4.7e-07 ; else None."""
    m = re.match(r"^\s*([\d.]+)\s*([kKmMuUnNpPrR]?)", comment)
    if not m:
        return None
    try:
        num = float(m.group(1))
    except ValueError:
        return None
    return num * _MULT.get(m.group(2).upper(), 1.0)


def load_bom_values(path=BOM):
    """{designator: numeric value} from the BOM's Comment column."""
    if not os.path.exists(path):
        raise RailError(f"BOM not found at {path} — the operating point "
                        f"cannot be computed without passive values")
    values = {}
    with open(path) as fh:
        for row in csv.DictReader(fh):
            val = _parse_value(row.get("Comment", ""))
            if val is None:
                continue
            for des in row.get("Designator", "").split(","):
                des = des.strip()
                if des:
                    values[des] = val
    return values


# ── Element classification ──────────────────────────────────────────

_MECHANICAL = ("mechanical", "anchor", "shell")


def _is_switch_terminal(ref, pad):
    """True if this pad is an electrical pole of the switch, not a solder tab.

    Decided by datasheet_specs' own `function` text, which says
    "Shell/anchor (mechanical)" for SW16's four tabs. A pad the spec does
    not describe is treated as a terminal, so an undeclared pad fails loudly
    in the scenario rather than being silently ignored.
    """
    spec = nl.COMPONENT_SPECS.get(ref, {}).get("pins", {}).get(pad)
    if spec is None:
        return True
    fn = str(spec.get("function", "")).lower()
    return not any(word in fn for word in _MECHANICAL)


def _kind(ref):
    """What a reference designator is, for DC purposes."""
    if re.match(r"^R\d", ref):
        return "resistor"
    if re.match(r"^C\d", ref):
        return "capacitor"       # open at DC
    if re.match(r"^L\d", ref):
        return "inductor"        # short at DC
    if re.match(r"^D\d", ref):
        return "diode"
    if re.match(r"^Q\d", ref):
        return "mosfet"
    if ref.startswith("SW"):
        return "switch"          # open unless the scenario closes it
    if re.match(r"^LED\d", ref):
        return "led"
    return "device"              # U*, J*, BT*, SPK*, FID*


# ── The regulated rails, derived from the netlist ────────────────────

FeedbackDivider = collections.namedtuple(
    "FeedbackDivider", "fb_net out_net r_top r_top_ohm r_bottom r_bottom_ohm")


def find_feedback_divider(board, values, reg_ref="U3", fb_pin="5",
                          gnd_net="GND"):
    """Walk the netlist from the regulator's FB pin to its divider.

    Nothing about which resistor is R_top is assumed: the one whose other
    end is GND is the bottom, the one whose other end is a rail with the
    regulator's own inductor on it is the top.
    """
    fb_net = None
    for net, pins in board.nets.items():
        if any(p.ref == reg_ref and p.pad == fb_pin for p in pins):
            fb_net = net
            break
    if fb_net is None:
        raise RailError(
            f"{reg_ref} pin {fb_pin} (FB) is on no net — the output voltage "
            f"is not programmed by anything the netlist can see")

    resistors = [p.ref for p in board.nets[fb_net]
                 if _kind(p.ref) == "resistor"]
    if len(resistors) != 2:
        raise RailError(
            f"the {fb_net} node carries {len(resistors)} resistor(s) "
            f"({resistors}) — the SY8089 programs its output with exactly "
            f"two (page 2, FB pin description), so this is not a divider")

    top = bottom = None
    for ref in resistors:
        others = {net for net, pins in board.nets.items()
                  if net != fb_net and any(p.ref == ref for p in pins)}
        if gnd_net in others:
            bottom = (ref, others)
        else:
            top = (ref, others)
    if top is None or bottom is None:
        raise RailError(
            f"cannot tell the {fb_net} divider apart: neither or both of "
            f"{resistors} reach {gnd_net}")

    out_nets = top[1] - {fb_net}
    if len(out_nets) != 1:
        raise RailError(
            f"{top[0]} reaches {sorted(out_nets)} besides {fb_net}; the top "
            f"of the divider must sit on exactly one output rail")
    out_net = out_nets.pop()

    for ref in (top[0], bottom[0]):
        if ref not in values:
            raise RailError(
                f"{ref} has no value in the BOM, so the output voltage "
                f"cannot be computed. A divider with an unknown resistor is "
                f"not a divider.")
    return FeedbackDivider(fb_net, out_net, top[0], values[top[0]],
                           bottom[0], values[bottom[0]])


# ── DC solve of the resistive network ───────────────────────────────

def _solve(matrix, rhs):
    """Gaussian elimination with partial pivoting. stdlib only."""
    n = len(rhs)
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(matrix[r][col]))
        if abs(matrix[piv][col]) < 1e-15:
            raise RailError(
                "the conductance matrix is singular — a node group has no "
                "path to any source and was not classified as floating")
        matrix[col], matrix[piv] = matrix[piv], matrix[col]
        rhs[col], rhs[piv] = rhs[piv], rhs[col]
        for row in range(col + 1, n):
            f = matrix[row][col] / matrix[col][col]
            if f == 0.0:
                continue
            for k in range(col, n):
                matrix[row][k] -= f * matrix[col][k]
            rhs[row] -= f * rhs[col]
    out = [0.0] * n
    for row in reversed(range(n)):
        acc = rhs[row] - sum(matrix[row][k] * out[k] for k in range(row + 1, n))
        out[row] = acc / matrix[row][row]
    return out


def solve_dc(board, values, fixed, buttons_pressed=False):
    """Return {net: volts or UNDEFINED} for every net carrying a pin.

    `fixed` maps net -> volts for nodes the sources and regulators hold.
    Everything else is solved through the resistors; inductors merge their
    two nets; capacitors, open switches and device pins contribute nothing.
    """
    # Inductors are 0 ohm at DC: merge their nets so the matrix stays
    # non-singular instead of carrying a 1e9-siemens edge.
    parent = {net: net for net in board.nets}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            # Keep a fixed net as the representative so its voltage sticks.
            if rb in fixed:
                ra, rb = rb, ra
            parent[rb] = ra

    two_terminal = collections.defaultdict(list)
    ref_pad_nets = collections.defaultdict(dict)
    for net, pins in board.nets.items():
        for p in pins:
            two_terminal[p.ref].append(net)
            ref_pad_nets[p.ref][p.pad] = net

    for ref, nets in two_terminal.items():
        if _kind(ref) == "inductor" and len(set(nets)) == 2:
            union(*sorted(set(nets)))
        if _kind(ref) == "switch" and buttons_pressed:
            # Only the pads that are electrical terminals. SW16's four
            # shell tabs carry BTN_SELECT on this board — a deliberate
            # same-net fixup for a trace that grazes them
            # (routing.py:6055-6085) — and they are mechanically isolated
            # from the slide contacts inside the component body. Closing the
            # switch across "every net this ref touches" therefore welded
            # BAT+ to BTN_SELECT and put 3.83 V on every button. The
            # terminal/mechanical split is read from datasheet_specs, which
            # is where it is declared, not guessed from pad names.
            terminals = {net for pad, net in ref_pad_nets[ref].items()
                         if _is_switch_terminal(ref, pad)}
            if len(terminals) == 2:
                union(*sorted(terminals))

    # Resistive edges between (merged) nodes.
    edges = []
    for ref, nets in two_terminal.items():
        if _kind(ref) != "resistor":
            continue
        distinct = sorted(set(find(n) for n in nets))
        if len(distinct) != 2:
            continue        # both ends on one node: carries no current
        if ref not in values:
            raise RailError(
                f"{ref} spans {distinct} but has no BOM value — an unknown "
                f"resistor changes the answer, so this is fatal, not skipped")
        edges.append((distinct[0], distinct[1], 1.0 / values[ref]))

    roots_fixed = {find(n): v for n, v in fixed.items() if n in parent}

    # Only nodes with a resistive path to a fixed node are solvable. The
    # rest are floating, and are reported as such.
    adj = collections.defaultdict(set)
    for a, b, _ in edges:
        adj[a].add(b)
        adj[b].add(a)
    reachable = set(roots_fixed)
    stack = list(roots_fixed)
    while stack:
        node = stack.pop()
        for nb in adj[node]:
            if nb not in reachable:
                reachable.add(nb)
                stack.append(nb)

    unknowns = sorted(n for n in reachable if n not in roots_fixed)
    solved = dict(roots_fixed)
    if unknowns:
        index = {n: i for i, n in enumerate(unknowns)}
        size = len(unknowns)
        mat = [[0.0] * size for _ in range(size)]
        rhs = [0.0] * size
        for a, b, g in edges:
            for x, y in ((a, b), (b, a)):
                if x not in index:
                    continue
                i = index[x]
                mat[i][i] += g
                if y in index:
                    mat[i][index[y]] -= g
                elif y in roots_fixed:
                    rhs[i] += g * roots_fixed[y]
        for n, v in zip(unknowns, _solve(mat, rhs)):
            solved[n] = v

    return {net: solved.get(find(net), UNDEFINED) for net in board.nets}


# ── Operating point ─────────────────────────────────────────────────

OperatingPoint = collections.namedtuple(
    "OperatingPoint", "voltages divider rail_spread source notes violations")


def operating_point(on_battery=False, soc=0.5, buttons_pressed=False):
    require_valid(U2, U3)
    board = nl.load_board_netlist()
    values = load_bom_values()
    divider = find_feedback_divider(board, values)

    src = sources.lipo(soc) if on_battery else sources.psu()
    notes, violations = [], []

    # The +5V rail comes out of the IP5306 boost in both cases: on USB it is
    # the VIN pass-through, on battery it is the boost. Both land on pin 8.
    v5 = U2.params["v_out_typ"].value
    notes.append(
        f"+5V taken as {v5} V from {U2.mpn} pin 8 "
        f"({U2.params['v_out_typ'].locator}); tolerance NOT established — "
        f"{UNESTABLISHED['v_out_tolerance']}")

    lo, typ, hi = v_out_spread(divider.r_top_ohm, divider.r_bottom_ohm)
    rail_spread = {divider.out_net: (lo, typ, hi)}

    # The cell is on the board in both scenarios: this is a charge-and-play
    # design, so BAT+ is held by the battery whether or not USB is plugged
    # in. Only VBUS differs.
    cell = sources.lipo(soc)
    fixed = {"GND": 0.0, "+5V_VOUT": v5, "+5V": v5, divider.out_net: typ,
             "BAT+": cell.v_open, "BAT_IN": cell.v_open}
    if on_battery:
        notes.append("VBUS left floating: no cable in this scenario")
    else:
        fixed["VBUS"] = src.v_open
    notes.append(
        f"BAT+ held at {cell.v_open:.3f} V by the cell at SoC {soc:.2f} "
        f"(charge-and-play: the battery is present on USB too)")
    # BAT+ is really BAT_IN *through Q1*, not a second source. Holding both
    # at the cell voltage is exact only at zero load current, which is what
    # this DC solve has: every consumer is a high-impedance pin, so no
    # current flows and Q1's I*Rds_on drop is zero. It stops being exact the
    # moment load currents enter the model, which is T1.4's job — Q1's
    # on-resistance is already cited in models/q1_ao3401a.py, and at the
    # gaming current it is worth about 70 mV. conflicts.py found this by
    # flagging Q1.3 as a second driver on BAT+, which it is not; the model
    # was wrong, not the board.
    notes.append(
        "BAT+ = BAT_IN through Q1; the drop is zero here ONLY because a DC "
        "solve with high-impedance loads carries no current. Load currents "
        "(T1.4) must add I x Rds_on — about 70 mV at the gaming current.")
    # The same argument, one rail up: +5V is +5V_VOUT *through Q2*, the
    # SW16 high-side switch, and both are held at the boost output because
    # a zero-current solve puts no drop across the MOSFET either.
    #
    # This does NOT mean the bench thinks the switch does nothing. The
    # solver has no MOSFET model, so asking it what the load rail does when
    # Q2 turns off would be asking it to invent an answer. What it CAN do
    # exactly is solve the gate network, which is nothing but resistors and
    # the switch itself — and the gate is where the switch's behaviour is
    # decided. That is what T2.3 reads (see buttons.py::switch_scenario).
    notes.append(
        "+5V = +5V_VOUT through Q2 (the SW16 high-side switch); like Q1 "
        "above, the drop is zero only because this solve carries no "
        "current. Q2's ON/OFF state is judged from the GATE network, "
        "which is resistive and exactly solvable, not from this rail.")
    fixed = {n: v for n, v in fixed.items() if n in board.nets}

    voltages = solve_dc(board, values, fixed, buttons_pressed)

    # Checks against the parts' own cited limits.
    if v5 > U3.params["v_in_abs_max"].value:
        violations.append(
            f"+5V = {v5} V exceeds U3's absolute maximum input "
            f"{U3.params['v_in_abs_max'].value} V "
            f"({U3.params['v_in_abs_max'].locator})")
    in_lo, _, in_hi = U3.params["v_in_range"].value
    if not in_lo <= v5 <= in_hi:
        violations.append(
            f"+5V = {v5} V is outside U3's recommended input range "
            f"{in_lo}-{in_hi} V ({U3.params['v_in_range'].locator})")
    if hi > 3.6:
        violations.append(
            f"{divider.out_net} worst case {hi:.3f} V exceeds the 3.6 V "
            f"absolute maximum of the ESP32-S3 and the SD card")

    return OperatingPoint(voltages, divider, rail_spread, src, notes,
                          violations)


# ── Report ──────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", choices=("usb", "battery"), default="usb")
    ap.add_argument("--soc", type=float, default=0.5,
                    help="battery state of charge, 0..1 (default 0.5)")
    ap.add_argument("--buttons-pressed", action="store_true",
                    help="close every switch (worst-case button scenario)")
    args = ap.parse_args(argv)

    try:
        op = operating_point(args.source == "battery", args.soc,
                            args.buttons_pressed)
    except (RailError, nl.NetlistError) as exc:
        print(f"  ERROR  {exc}", file=sys.stderr)
        return 2

    d = op.divider
    print("=" * 72)
    print("  Virtual Bench T1.1 — DC operating point")
    print("=" * 72)
    print(f"  Source        : {op.source.name} at {op.source.v_open:.3f} V "
          f"open circuit, r_int {op.source.r_internal} ohm")
    print(f"  Calibration   : {sources.CALIBRATION} "
          f"({sources.CALIBRATION_WHY})")
    print(f"  Switches      : {'all closed' if args.buttons_pressed else 'open'}")
    print()
    print(f"  {d.out_net} is DERIVED, not assumed:")
    print(f"    V_REF * (1 + {d.r_top}/{d.r_bottom}) = "
          f"0.600 * (1 + {d.r_top_ohm/1000:.0f}k/{d.r_bottom_ohm/1000:.0f}k)")
    lo, typ, hi = op.rail_spread[d.out_net]
    print(f"    = {typ:.3f} V typ, {lo:.3f} .. {hi:.3f} V from V_REF's own "
          f"tolerance alone")
    print(f"    (resistor tolerance NOT included: the BOM does not state it)")
    print()
    for note in op.notes:
        print(f"  note: {note}")

    print()
    print("-" * 72)
    print("  Per-net DC voltage")
    print("-" * 72)
    defined = {n: v for n, v in op.voltages.items() if v is not UNDEFINED}
    floating = sorted(n for n, v in op.voltages.items() if v is UNDEFINED)
    pin_counts = {n: len(p) for n, p in nl.load_board_netlist().nets.items()}
    for net, volts in sorted(defined.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {net:<12} {volts:7.3f} V   ({pin_counts.get(net, 0)} pins)")
    print()
    print(f"  Floating at DC — no resistive path to any source ({len(floating)}):")
    for net in floating:
        print(f"    {net}")
    print("    A floating node has no voltage, so none is printed. Assigning "
          "0 V here")
    print("    would be a plausible table with a lie in it.")

    print()
    print("-" * 72)
    if op.violations:
        print(f"  VIOLATIONS ({len(op.violations)}):")
        for v in op.violations:
            print(f"    {v}")
    else:
        print("  No cited limit is exceeded at DC.")
    print()
    print("  Not covered here: ripple, rise time, inrush, brownout — T1.4. "
          "Silence above")
    print("  is not a pass on any of them.")
    print("=" * 72)
    return 1 if op.violations else 0


if __name__ == "__main__":
    sys.exit(main())
