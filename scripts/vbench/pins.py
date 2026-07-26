"""Virtual Bench T2.1 + T2.4 — the pin fabric, and what this board boots into.

Joins three sources that have never been joined: the netlist (what is
attached to each ESP32 pin), the DC operating point from T1.1 (what voltage
that attachment produces at reset), and the strapping tables from the module
datasheet (what the chip does with those levels).

The result answers a question no existing gate asks end to end: **given the
copper, which boot mode does this board enter, and can a button change it?**

The interesting part is that the answer is derived rather than asserted.
`verify_strapping_pins.py` reaches the same conclusions today, but it reaches
them by grepping the schematic for phrases like "R3 DNP" and by consulting a
hand-written table of pin roles. Here the level comes out of the resistive
solve in `rails.py`, and the consequence comes out of table 6 on page 14.
When the two disagree, one of them is wrong about the board, and that is worth
knowing.

Usage:
    python3 scripts/vbench/pins.py
    python3 scripts/vbench/pins.py --hold BTN_SELECT
"""

import argparse
import collections
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from hardware.datasheet_specs import COMPONENT_SPECS          # noqa: E402
from vbench import netlist as nl                              # noqa: E402
from vbench import rails                                      # noqa: E402
from vbench.models import require_valid                       # noqa: E402
from vbench.models.u1_esp32s3 import (                        # noqa: E402
    STRAPPING_DEFAULTS, STRAPPING_ROLES, U1, boot_mode, vdd_spi_voltage)

# Pins the module keeps for its own octal PSRAM and must stay externally
# unconnected. Same evidence verify_netlist_diff.T1_ALLOW cites.
RESERVED = {"GPIO35", "GPIO36", "GPIO37"}

# The board net each strapping GPIO lands on. Derived, not written: the pin's
# function text in datasheet_specs names the GPIO, and the netlist says which
# net that pad carries.
Pin = collections.namedtuple("Pin", "pad gpio net volts level role locator")


def gpio_of_pad(pad):
    """The GPIO number datasheet_specs assigns to a U1 pad, or None."""
    spec = COMPONENT_SPECS.get("U1", {}).get("pins", {}).get(str(pad))
    if not spec:
        return None
    m = re.search(r"\b(?:GPIO|IO)\s*(\d+)\b", str(spec.get("function", "")))
    return f"GPIO{m.group(1)}" if m else None


def _level(volts, v_rail):
    """Digital level from a DC voltage, or None when the node is floating.

    Thresholds are the usual CMOS 30%/70% of rail. They are DERIVED, not
    cited: the module datasheet's V_IH/V_IL are on a page this model has not
    read, so anything between the two bands is reported as indeterminate
    rather than rounded to the nearer rail.
    """
    if volts is None:
        return None
    if volts >= 0.7 * v_rail:
        return 1
    if volts <= 0.3 * v_rail:
        return 0
    return "?"


def fabric(hold_nets=()):
    """Every U1 pad with its net, DC voltage, level and strapping role."""
    board = nl.load_board_netlist()
    op = rails.operating_point(buttons_pressed=False)
    v_rail = op.rail_spread["+3V3"][1]

    # A held button shorts its net to GND — the reset-time question T2.4 asks.
    forced = {}
    for net in hold_nets:
        if net not in board.nets:
            raise SystemExit(f"no net named {net!r} on this board")
        forced[net] = 0.0

    pad_net = {}
    for net, pins in board.nets.items():
        for p in pins:
            if p.ref == "U1":
                pad_net[p.pad] = net

    out = []
    for pad in sorted(pad_net, key=lambda s: (len(s), s)):
        net = pad_net[pad]
        gpio = gpio_of_pad(pad)
        volts = forced.get(net, op.voltages.get(net))
        role, locator = STRAPPING_ROLES.get(gpio, ("", ""))
        out.append(Pin(pad, gpio, net, volts, _level(volts, v_rail),
                       role, locator))
    return out, op, v_rail


def strapping_state(pins):
    """{GPIO: level} for the four strapping pins, with the board's evidence."""
    state = {}
    for gpio in STRAPPING_DEFAULTS:
        found = [p for p in pins if p.gpio == gpio]
        if not found:
            # Not on a U1 pad we can see: fall back to the datasheet default,
            # which is exactly what the chip does with an unconnected pin.
            d = STRAPPING_DEFAULTS[gpio]
            state[gpio] = (d["default"], f"not attached; internal "
                                         f"{d['internal'] or 'no pull'} "
                                         f"({d['locator']})")
            continue
        p = found[0]
        if p.level is None:
            # Floating on the board: the chip's own internal pull decides,
            # and for GPIO3 there is none — which is a real hole, not a 0.
            d = STRAPPING_DEFAULTS[gpio]
            if d["internal"] is None:
                state[gpio] = (None, f"{p.net} floats and {gpio} has NO "
                                     f"internal pull ({d['locator']}) — the "
                                     f"datasheet requires an external "
                                     f"non-high-Z driver")
            else:
                state[gpio] = (d["default"],
                               f"{p.net} floats; the chip's internal "
                               f"{d['internal']} decides ({d['locator']})")
            continue
        state[gpio] = (p.level, f"{p.net} at {p.volts:.3f} V from the board")
    return state


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--hold", action="append", default=[], metavar="NET",
                   help="hold this net low at reset (repeatable), e.g. "
                        "--hold BTN_SELECT")
    args = ap.parse_args(argv)

    require_valid(U1)
    pins, op, v_rail = fabric(args.hold)

    print("=" * 72)
    print("  Virtual Bench T2.1 — ESP32-S3 pin fabric")
    print("=" * 72)
    print(f"  Rail      : +3V3 = {v_rail:.3f} V (derived by T1.1, not assumed)")
    print(f"  Held low  : {', '.join(args.hold) if args.hold else 'nothing'}")
    print(f"  Levels use 30%/70% of rail. Those thresholds are DERIVED — the")
    print(f"  module's V_IH/V_IL are on a page this model has not read — so a")
    print(f"  node between the bands prints '?' rather than the nearer rail.")
    print()
    print(f"  {'pad':>4}  {'GPIO':<8} {'net':<12} {'V':>7}  lvl  role")
    print("  " + "-" * 68)
    floating = []
    for p in pins:
        volts = f"{p.volts:7.3f}" if p.volts is not None else "  float"
        lvl = " - " if p.level is None else f" {p.level} "
        role = f"  <- {p.role}" if p.role else ""
        print(f"  {p.pad:>4}  {p.gpio or '':<8} {p.net:<12} {volts}  {lvl}"
              f"{role}")
        if p.volts is None:
            floating.append(p)

    print()
    print(f"  {len(pins)} U1 pads carry a net; {len(floating)} float at DC.")
    print(f"  Floating is normal for a driven digital line (the LCD bus, SD, "
          f"USB); it is")
    print(f"  NOT normal for a strapping pin, which is what the next section "
          f"is about.")
    attached_reserved = [p for p in pins if p.gpio in RESERVED]
    print(f"  Reserved octal-PSRAM pins {sorted(RESERVED)} attached "
          f"externally: {len(attached_reserved)}"
          f"{' — must be zero' if attached_reserved else ' (correct)'}")

    # ── T2.4 boot mode ───────────────────────────────────────────────
    state = strapping_state(pins)
    print()
    print("=" * 72)
    print("  Virtual Bench T2.4 — strapping pins and the resulting boot mode")
    print("=" * 72)
    for gpio in ("GPIO0", "GPIO3", "GPIO45", "GPIO46"):
        level, why = state[gpio]
        role, locator = STRAPPING_ROLES[gpio]
        shown = "undefined" if level is None else str(level)
        print(f"  {gpio:<7} = {shown:<9} {why}")
        print(f"          decides: {role}  [{locator}]")

    mode, why = boot_mode(state["GPIO0"][0], state["GPIO46"][0])
    vdd_spi, vdd_why = vdd_spi_voltage(state["GPIO45"][0])
    print()
    print(f"  BOOT MODE : {mode}")
    print(f"              {why}")
    print(f"  VDD_SPI   : {vdd_spi if vdd_spi else 'undetermined'} V")
    print(f"              {vdd_why}")

    problems = []
    if mode != "SPI Boot":
        problems.append(
            f"the board enters {mode} instead of SPI Boot"
            + (f" because {', '.join(args.hold)} is held at reset"
               if args.hold else "")
            + f" — GPIO0={state['GPIO0'][0]}, GPIO46={state['GPIO46'][0]}")
    if vdd_spi != 3.3:
        problems.append(
            f"VDD_SPI is {vdd_spi} V, not the 3.3 V the N16R8's PSRAM needs "
            f"(GPIO45={state['GPIO45'][0]})")
    if state["GPIO3"][0] is None:
        problems.append(
            "GPIO3 has no defined level at reset and no internal pull to fall "
            "back on (p.15 section 3.3.4)")
    if attached_reserved:
        problems.append(
            f"octal-PSRAM pins are attached externally: "
            f"{[p.gpio for p in attached_reserved]}")

    print()
    print("=" * 72)
    if problems:
        print(f"  FAIL — {len(problems)} boot-time problem(s):")
        for p in problems:
            print(f"    {p}")
        print("=" * 72)
        return 1
    print("  Boot is SPI Boot with VDD_SPI at 3.3 V, decided by the copper "
          "and by")
    print("  tables 4, 6 and 7 — not by a comment.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
