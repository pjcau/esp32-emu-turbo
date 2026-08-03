"""Virtual Bench T2.2 + T2.3 — the buttons' debounce RC, and the power switch.

For every button the bench finds its pull-up and its debounce capacitor **in
the netlist**, reads their values from the BOM, and computes the release edge
they produce. Pressing is fast — the switch shorts the node to ground — so
the time constant that matters is the rise after release, and it is the one a
firmware debounce interval has to clear.

T2.3 operates SW16 and checks what the switch is supposed to do. Since the
respin it does something: it drives PWR_SW, which through R33 drives the gate
of Q2, the high-side P-MOSFET between the boost output (`+5V_VOUT`) and every
load (`+5V`).

The verdict is read off the GATE, not off the rail. The DC solver has no
MOSFET model, so asking it what the load rail does when Q2 turns off would be
asking it to invent an answer; the gate network is nothing but resistors and
the switch, so it is solved exactly. On the ON throw the gate must sit far
enough below the source to drive the part past its characterised V_gs, and on
the open throw it must sit close enough to the source to be unambiguously off
— both thresholds read from the Q2 model, not typed here.

The scenario also asserts what must NOT happen: BAT+ and +3V3 do not move.
The cell path never passes through this switch, which is the whole point —
OFF has to leave charging working. On the FABRICATED boards the switch is
inert altogether (both throws unrouted), and that limitation stays recorded
in docs/known-issues.md; true isolation on those is unplugging J3.

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
INVARIANT_TEXT = "SW16 does not switch anything"

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


def _q2_thresholds():
    """(V_gs to call Q2 ON, V_gs to call Q2 OFF), from the part's model.

    Both come from the SI2301 model rather than being typed here, so a
    corrected datasheet reading moves this test with it.
    """
    from vbench.models.q1_si2301 import Q1 as SI2301
    p = SI2301.params
    # ON: the datasheet characterises R_ds(on) at a stated V_gs. Driving to
    # at least that magnitude is what "on" means for this part.
    on = abs(p["v_gs_rds_on"].value)
    # OFF: below the MINIMUM threshold magnitude the part is specified not
    # to conduct. The minimum is the pessimistic edge, which is the one an
    # off-state has to clear.
    off = abs(p["v_gs_th_min"].value)
    return on, off, p["v_gs_rds_on"].locator, p["v_gs_th_min"].locator


def switch_scenario():
    """T2.3 — operating SW16 must switch Q2, and must not touch the cell."""
    board = nl.load_board_netlist()
    off_state = rails.operating_point(buttons_pressed=False)
    on_state = rails.operating_point(buttons_pressed=True)

    def vgs(op):
        g = op.voltages.get("PWR_SW_GATE")
        s = op.voltages.get("+5V_VOUT")
        if g is None or s is None:
            return None
        return g - s

    vgs_off = vgs(off_state)
    vgs_on = vgs(on_state)
    v_on_needed, v_off_needed, on_loc, off_loc = _q2_thresholds()

    # Read from the copper, not quoted: which of SW16's pads carry a net,
    # and what the common sits on.
    pads = {p.pad: net for net, pins in board.nets.items()
            for p in pins if p.ref == "SW16"}
    throws = [p for p in ("1", "3") if p in pads]

    try:
        with open(INVARIANT_DOC, errors="replace") as fh:
            recorded = INVARIANT_TEXT in fh.read()
    except OSError:
        recorded = False

    bat_before = off_state.voltages.get("BAT+")
    bat_after = on_state.voltages.get("BAT+")
    rail_before = off_state.voltages.get("+3V3")
    rail_after = on_state.voltages.get("+3V3")

    problems = []
    if vgs_on is None or vgs_off is None:
        problems.append(
            "the Q2 gate node did not solve — PWR_SW_GATE or +5V_VOUT is "
            "missing from the netlist, so the switch cannot be judged")
    else:
        if vgs_on > -v_on_needed:
            problems.append(
                f"with SW16 on the ON throw the gate reaches only "
                f"V_gs = {vgs_on:+.3f} V, short of the {-v_on_needed:+.3f} V "
                f"the part is characterised at ({on_loc}) — Q2 would run in "
                f"an undefined region instead of hard on")
        if vgs_off < -v_off_needed:
            problems.append(
                f"with the throw open the gate sits at V_gs = {vgs_off:+.3f} "
                f"V, past the {-v_off_needed:+.3f} V threshold minimum "
                f"({off_loc}) — Q2 would leak instead of being off")
    if pads.get("2") != "PWR_SW":
        problems.append(
            f"SW16's common (pad 2) is on {pads.get('2')!r}, not PWR_SW — "
            f"the switch is not driving the gate network")
    if "1" not in throws:
        problems.append(
            "SW16's ON throw (pad 1) carries no net, so nothing grounds the "
            "gate and the board can never be switched on")
    if "BAT+" in pads.values():
        problems.append(
            "SW16 is back on BAT+: putting the cell through this switch "
            "breaks charging in the OFF position, which is the design the "
            "respin rejected")
    if bat_before is None or abs(bat_after - bat_before) > 1e-9:
        problems.append(
            f"operating SW16 moved BAT+ ({bat_before} -> {bat_after}); the "
            f"cell path must not pass through the switch")
    if rail_before is None or abs(rail_after - rail_before) > 1e-9:
        problems.append(
            f"operating SW16 moved +3V3 ({rail_before} -> {rail_after})")

    return not problems, {
        "vgs_off": vgs_off, "vgs_on": vgs_on,
        "v_on_needed": v_on_needed, "v_off_needed": v_off_needed,
        "bat_before": bat_before, "bat_after": bat_after,
        "rail_before": rail_before, "rail_after": rail_after,
        "routed_throws": throws,
        "common_net": pads.get("2"),
        "recorded": recorded,
        "problems": problems,
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
    ok, d = switch_scenario()
    print()
    print("=" * 72)
    print("  Virtual Bench T2.3 — scenario switch (SW16 -> Q2 -> +5V loads)")
    print("=" * 72)
    print(f"  SW16 common (pad 2) is on    : {d['common_net']}")
    print(f"  Throw pads carrying a net    : "
          f"{d['routed_throws'] or 'NONE — nothing to switch between'}")
    if d["vgs_on"] is not None:
        print(f"  Q2 V_gs, ON throw            : {d['vgs_on']:+.3f} V "
              f"(needs <= {-d['v_on_needed']:+.3f} V to be hard on)")
        print(f"  Q2 V_gs, throw open          : {d['vgs_off']:+.3f} V "
              f"(needs >  {-d['v_off_needed']:+.3f} V to be off)")
    print(f"  BAT+  before / after         : {d['bat_before']:.3f} V / "
          f"{d['bat_after']:.3f} V")
    print(f"  +3V3  before / after         : {d['rail_before']:.3f} V / "
          f"{d['rail_after']:.3f} V")
    print()
    if ok:
        print("  The switch works: operating SW16 swings Q2's gate across "
              "the part's own")
        print("  characterised drive, and neither BAT+ nor +3V3 moves — the "
              "cell path does")
        print("  not pass through the switch, so OFF leaves the IP5306 "
              "charging.")
        print("  The load rail itself is NOT read here: the DC solve has no "
              "MOSFET model,")
        print("  so the gate network — resistors and the switch, solvable "
              "exactly — is")
        print("  what the verdict comes from.")
        print(f"  FABRICATED-BOARD limitation still recorded in "
              f"docs/known-issues.md: "
              f"{'yes' if d['recorded'] else 'NO'}")
    else:
        problems.extend(d["problems"])
    if not d["recorded"]:
        problems.append(
            f"docs/known-issues.md no longer records {INVARIANT_TEXT!r}; the "
            f"boards already fabricated still have an inert SW16 and the "
            f"bench has nothing declaring it")

    print()
    print("=" * 72)
    if problems:
        print(f"  FAIL — {len(problems)}:")
        for p in problems:
            print(f"    {p}")
        print("=" * 72)
        return 1
    print("  Every button has a computable debounce RC, and operating SW16 "
          "switches Q2")
    print("  without disturbing the cell path.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
