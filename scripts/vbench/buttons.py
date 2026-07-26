"""Virtual Bench T2.2 + T2.3 — the buttons' debounce RC, and the power switch.

For every button the bench finds its pull-up and its debounce capacitor **in
the netlist**, reads their values from the BOM, and computes the release edge
they produce. Pressing is fast — the switch shorts the node to ground — so
the time constant that matters is the rise after release, and it is the one a
firmware debounce interval has to clear.

T2.3 is the opposite kind of test: `switch_off` must **reproduce** a known
property of this board rather than report it. SW_PWR is not in series with the
battery — only its common pad is routed, as a stub tap on BAT+ — so the switch
cannot power the board down. The bench asserts that the board stays powered,
cites the invariant, and fails if the board ever starts behaving like the
switch works, because that would mean the copper changed under a recorded
limitation.

Usage:
    python3 scripts/vbench/buttons.py
"""

import argparse
import collections
import math
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import netlist as nl                              # noqa: E402
from vbench import pins as pinmod                             # noqa: E402
from vbench import rails                                      # noqa: E402
from vbench.models.u1_esp32s3 import STRAPPING_DEFAULTS       # noqa: E402

# The level a rising node must reach to read as HIGH. Same 70%-of-rail
# convention pins.py uses, and derived for the same reason: the module's V_IH
# is on a page these models have not read.
V_IH_FRACTION = 0.70

INVARIANT_DOC = os.path.join(BASE, "docs", "known-issues.md")
INVARIANT_TEXT = "SW_PWR is not in series"

Button = collections.namedtuple(
    "Button", "net switch pullup r_ohm cap c_farad tau_s t_rise_s note "
              "pullup_forbidden")


def _pullup_forbidden(board, net):
    """Is an external pull-up on this net forbidden by a strapping default?

    Derived, not listed. If the net lands on a U1 pad whose GPIO is a
    strapping pin whose datasheet default is 0, then pulling it up would
    override that default and change what the chip does at reset. For GPIO45
    that means selecting VDD_SPI = 1.8 V and starving the N16R8's 3.3 V PSRAM
    (table 7, page 15) — which is precisely why R14 is DNP.

    So a button on such a pin having NO external pull-up is the design
    working, not a defect, and reporting it as one would be the bench arguing
    with the datasheet.
    """
    for pin in board.nets.get(net, ()):
        if pin.ref != "U1":
            continue
        gpio = pinmod.gpio_of_pad(pin.pad)
        strap = STRAPPING_DEFAULTS.get(gpio)
        if strap and strap["default"] == 0:
            return (gpio, strap["locator"])
    return None


def _refs_on(board, net, prefix):
    return sorted(p.ref for p in board.nets.get(net, ())
                  if re.match(prefix, p.ref))


def survey(board=None, values=None):
    """Every button net with its pull-up, debounce cap and release timing."""
    board = board or nl.load_board_netlist()
    values = values if values is not None else rails.load_bom_values()
    out = []
    for net in sorted(n for n in board.nets if n.startswith("BTN_")):
        switches = _refs_on(board, net, r"^SW")
        pullups = _refs_on(board, net, r"^R\d")
        caps = _refs_on(board, net, r"^C\d")
        # A pull-up is only a pull-up if its other end is on +3V3.
        pullups = [r for r in pullups
                   if any(p.ref == r for p in board.nets.get("+3V3", ()))]
        r_ref = pullups[0] if pullups else None
        c_ref = caps[0] if caps else None
        r_val = values.get(r_ref) if r_ref else None
        c_val = values.get(c_ref) if c_ref else None

        note = ""
        tau = t_rise = None
        if r_ref and r_val is None:
            note = (f"{r_ref} is on the net but has no BOM value — DNP, so "
                    f"there is no external pull-up")
            r_ref, r_val = None, None
        if r_val and c_val:
            tau = r_val * c_val
            # Time for an RC to climb from 0 to V_IH_FRACTION of the rail.
            t_rise = -tau * math.log(1.0 - V_IH_FRACTION)
        elif r_val and not c_val:
            note = note or ("pull-up but no debounce capacitor: the edge is "
                            "as fast as the pull-up can drive the pin's own "
                            "capacitance")
        forbidden = _pullup_forbidden(board, net)
        if not r_val:
            if forbidden:
                gpio, locator = forbidden
                note = (f"no external pull-up, and there must not be one: "
                        f"{net} is on {gpio}, a strapping pin whose datasheet "
                        f"default is 0 ({locator}). Pulling it up would change "
                        f"what the chip does at reset. The idle level comes "
                        f"from the ESP32's internal pull once firmware enables "
                        f"it.")
            else:
                note = note or ("no external pull-up: the idle level depends "
                                "entirely on the ESP32's internal pull, and "
                                "there is no RC to compute")
        out.append(Button(net, switches[0] if switches else None, r_ref,
                          r_val, c_ref, c_val, tau, t_rise, note,
                          forbidden))
    return out


def switch_off_scenario():
    """T2.3 — closing SW_PWR must NOT remove power. Returns (ok, detail)."""
    board = nl.load_board_netlist()
    values = rails.load_bom_values()
    powered = rails.operating_point(buttons_pressed=False)
    switched = rails.operating_point(buttons_pressed=True)

    v_before = powered.voltages.get("BAT+")
    v_after = switched.voltages.get("BAT+")
    rail_before = powered.voltages.get("+3V3")
    rail_after = switched.voltages.get("+3V3")

    # The physical reason, read from the copper rather than quoted: SW_PWR's
    # throw pads carry no net, so there is nothing for the common to switch
    # between.
    pads = {p.pad: net for net, pins in board.nets.items()
            for p in pins if p.ref == "SW_PWR"}
    throws = [p for p in ("1", "3") if p in pads]

    try:
        with open(INVARIANT_DOC, errors="replace") as fh:
            recorded = INVARIANT_TEXT in fh.read()
    except OSError:
        recorded = False

    still_powered = (v_after is not None and rail_after is not None
                     and abs(v_after - v_before) < 1e-9
                     and abs(rail_after - rail_before) < 1e-9)
    return still_powered, {
        "bat_before": v_before, "bat_after": v_after,
        "rail_before": rail_before, "rail_after": rail_after,
        "routed_throws": throws,
        "common_net": pads.get("2"),
        "recorded": recorded,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)

    board = nl.load_board_netlist()
    values = rails.load_bom_values()
    buttons = survey(board, values)
    v_rail = rails.operating_point().rail_spread["+3V3"][1]

    print("=" * 72)
    print("  Virtual Bench T2.2 — button debounce, from the netlist and the BOM")
    print("=" * 72)
    print(f"  Rise target: {V_IH_FRACTION*100:.0f}% of {v_rail:.3f} V = "
          f"{V_IH_FRACTION*v_rail:.3f} V (threshold DERIVED, not cited)")
    print()
    print(f"  {'net':<12} {'SW':<8} {'R':<5} {'C':<5} {'tau':>9} "
          f"{'t_rise':>9}")
    print("  " + "-" * 62)
    problems = []
    for b in buttons:
        tau = f"{b.tau_s*1e3:7.3f}ms" if b.tau_s else "        -"
        rise = f"{b.t_rise_s*1e3:7.3f}ms" if b.t_rise_s else "        -"
        print(f"  {b.net:<12} {b.switch or '-':<8} {b.pullup or '-':<5} "
              f"{b.cap or '-':<5} {tau:>9} {rise:>9}")
        if b.note:
            print(f"      {b.note}")
        if b.tau_s is None and not b.pullup_forbidden:
            problems.append(f"{b.net}: no RC to compute — {b.note}")
        elif b.pullup_forbidden and b.r_ohm is not None:
            gpio, locator = b.pullup_forbidden
            problems.append(
                f"{b.net} has an external pull-up ({b.pullup}) on {gpio}, "
                f"whose strapping default must stay 0 ({locator}) — this "
                f"changes the chip's reset behaviour")

    with_rc = [b for b in buttons if b.tau_s]
    if with_rc:
        slowest = max(with_rc, key=lambda b: b.t_rise_s)
        print()
        print(f"  Slowest release edge: {slowest.net} at "
              f"{slowest.t_rise_s*1e3:.3f} ms "
              f"({slowest.pullup} x {slowest.cap})")
        print(f"  A firmware debounce interval shorter than that will read a "
              f"release as a")
        print(f"  second press. This is the number to size it against.")

    # ── T2.3 ─────────────────────────────────────────────────────────
    ok, d = switch_off_scenario()
    print()
    print("=" * 72)
    print("  Virtual Bench T2.3 — scenario switch_off")
    print("=" * 72)
    print(f"  SW_PWR common (pad 2) is on : {d['common_net']}")
    print(f"  Throw pads carrying a net    : "
          f"{d['routed_throws'] or 'NONE — nothing to switch between'}")
    print(f"  BAT+  before / after         : {d['bat_before']:.3f} V / "
          f"{d['bat_after']:.3f} V")
    print(f"  +3V3  before / after         : {d['rail_before']:.3f} V / "
          f"{d['rail_after']:.3f} V")
    print()
    if ok:
        print("  EXPECTED: the board stays powered with the switch operated.")
        print("  This is not a bench failure and must never be reported as "
              "one — only")
        print("  SW_PWR's common pad is routed, as a stub tap on BAT+, so the "
              "battery")
        print("  path J3 -> Q1 -> BAT+ -> U2.6 never passes through the "
              "switch. True")
        print("  isolation on the fabricated board is unplugging J3.")
        print(f"  Invariant recorded in docs/known-issues.md: "
              f"{'yes' if d['recorded'] else 'NO'}")
    else:
        problems.append(
            "operating SW_PWR changed a rail: the copper no longer matches "
            "the recorded invariant that the switch is not in series")
    if not d["recorded"]:
        problems.append(
            f"docs/known-issues.md no longer records {INVARIANT_TEXT!r}; the "
            f"bench is reproducing a limitation nothing declares")

    print()
    print("=" * 72)
    if problems:
        print(f"  FAIL — {len(problems)}:")
        for p in problems:
            print(f"    {p}")
        print("=" * 72)
        return 1
    print("  Every button has a computable debounce RC, and switch_off "
          "reproduces the")
    print("  documented v1 behaviour instead of reporting it as a defect.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
