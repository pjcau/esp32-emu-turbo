"""Virtual Bench T1.4 — transients: cold start, inrush, load steps, brownout.

Builds SPICE decks from the extracted netlist, the BOM's real capacitor and
inductor values, and the cited model parameters, then runs them on ngspice
and reports `t_3v3_valid`, `V_min` and ripple per scenario.

## What is modelled, and what cannot be

The SY8089's **control loop is not in the datasheet pages this repo holds** —
no compensation network, no error-amplifier gain, no efficiency curve at this
board's operating point. So a closed-loop transient of the real regulator is
not derivable, and pretending otherwise would produce exactly the confident
wrong answer the plan's boundary table warns about.

What *is* derivable, entirely from cited numbers and BOM values:

* **Ripple.** The switching node is driven at the cited 1 MHz with the duty
  cycle `rails.py` derives (0.665), through the BOM's 2.2 uH inductor into
  the real 22.3 uF of output capacitance. That is a genuine simulation of the
  output filter, and its answer is cross-checked against the closed-form buck
  result below — two independent routes to one number.
* **Soft start.** t_SS = 1.2 ms is cited (page 4), and the current limit
  3.5 A is cited, so the ramp and its clamp are both grounded.
* **Inrush.** The bulk capacitance is read from the BOM, and the source
  impedance is the declared cable resistance from `sources.py`.
* **Sag and brownout.** The cell's internal resistance is uncalibrated (see
  `sources.py`) and Q1's on-resistance is cited, so the sag has one
  calibrated term and one that is not — reported separately rather than
  summed into a single trustworthy-looking number.

**C28 contributes nothing**, and that is correct rather than a bug: it is DNP,
so it has no BOM value, and a capacitor with no value is absent from the
deck. The +3V3 bulk is therefore 22.3 uF, not the 32.3 uF a reader adding up
the schematic would get — which is the same gap
`verify_decoupling_adequacy.py` has not been told about.

## Why ngspice is required, not optional

If the simulator is missing this module exits 2. It does not skip, and it
does not print a partial result: "no transient violations found" from a run
that never simulated anything is the worst output this bench could produce.

Usage:
    python3 scripts/vbench/transients.py
    python3 scripts/vbench/transients.py --keep   # leave the decks on disk
"""

import argparse
import collections
import os
import re
import shutil
import subprocess
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import netlist as nl                             # noqa: E402
from vbench import rails, sources                            # noqa: E402
from vbench.models import require_valid                      # noqa: E402
from vbench.models.q1_ao3401a import Q1, r_ds_on              # noqa: E402
from vbench.models.u2_ip5306 import U2                       # noqa: E402
from vbench.models.u3_sy8089 import U3, v_out_spread         # noqa: E402

# The ESP32-S3's supply minimum. Used as the threshold t_3v3_valid measures
# against, and it is the one number here taken from the module datasheet's
# recommended operating range rather than computed.
V_3V3_VALID = 3.0
V_3V3_VALID_SRC = "ESP32-S3-WROOM-1 recommended supply minimum"


class SimulatorMissing(RuntimeError):
    """ngspice is not installed. Fatal — never downgraded to a skip."""


Scenario = collections.namedtuple("Scenario", "name desc deck measures")
Measured = collections.namedtuple("Measured", "name values notes")


# ── Board values, read not assumed ──────────────────────────────────

def board_values():
    """Capacitance per rail and the buck inductor, from netlist + BOM."""
    board = nl.load_board_netlist()
    values = rails.load_bom_values()
    caps = {}
    for net in ("+3V3", "+5V", "VBUS", "BAT+"):
        total = 0.0
        absent = []
        for pin in board.nets.get(net, ()):
            if not pin.ref.startswith("C"):
                continue
            val = values.get(pin.ref)
            if val is None:
                absent.append(pin.ref)      # DNP: no BOM value, no capacitor
            else:
                total += val
        caps[net] = (total, sorted(set(absent)))
    l_buck = values.get("L2")
    if l_buck is None:
        raise rails.RailError("L2 has no BOM value; the output filter cannot "
                              "be simulated")
    return caps, l_buck


# ── Deck construction ───────────────────────────────────────────────

def r_conduction():
    """The buck's own series resistance: D*Rds_p + (1-D)*Rds_n, both cited.

    The ONLY series resistance either deck is allowed to use. An earlier
    version reached for v_out/i_limit = 0.95 ohm as a stand-in for the current
    limit, in two places, and invented a 0.36-0.50 V steady-state droop that
    made +3V3 look like it was browning out. A current limit clamps during
    startup; it is not a resistance the circuit contains.
    """
    from vbench.thermal import duty_cycle
    duty, _, _ = duty_cycle()
    return (duty * U3.params["r_ds_on_pfet"].value
            + (1.0 - duty) * U3.params["r_ds_on_nfet"].value)


def cap_charge_time(capacitance, v_final, i_limit):
    """How long a current-limited supply takes to charge a bulk capacitance.

    t = C * V / I. This is the answer the unlimited deck cannot give: a real
    supply does not deliver V/R into a discharged capacitor, it delivers its
    limit until the capacitor is charged.
    """
    return capacitance * v_final / i_limit


def deck_ripple(c_out, l_buck, duty, v_in, i_load):
    """Output filter driven at the cited switching frequency."""
    f_sw = U3.params["f_switching"].value
    period = 1.0 / f_sw
    r_load = max(v_out_spread(100e3, 22e3)[1] / i_load, 1e-3)
    # The open-loop LC rings: f0 = 1/(2*pi*sqrt(L*C)) is about 22 kHz here and
    # the load damps it only weakly (Q = R*sqrt(C/L) ~ 25), so it takes
    # milliseconds to settle. The real regulator's feedback loop damps this,
    # and that loop is not modelled — so the ring is an artefact of the deck,
    # not a property of the board. Ripple is therefore measured in a late
    # window, after the artefact has decayed. Measuring early is what made the
    # first version of this deck report 6 V of "ripple".
    settle = 4e-3
    window = 20 * period
    return f"""* vbench T1.4 - +3V3 output ripple
* Switching node driven at the cited f_sw with the derived duty cycle.
* L and C are the BOM's values; nothing here is a round number by choice.
Vlx lx 0 PULSE(0 {v_in} 0 1n 1n {duty * period:.12g} {period:.12g})
L2 lx out {l_buck:.12g}
Cout out 0 {c_out:.12g}
Rload out 0 {r_load:.6g}
.tran {period / 200:.12g} {settle + window:.12g}
.meas tran v_max MAX v(out) FROM={settle:.12g} TO={settle + window:.12g}
.meas tran v_min MIN v(out) FROM={settle:.12g} TO={settle + window:.12g}
.meas tran v_avg AVG v(out) FROM={settle:.12g} TO={settle + window:.12g}
.end
"""


def deck_cold_start(c_5v, c_3v3, i_load, v_psu, r_cable):
    """USB insertion: VBUS step, bulk charge, then the buck's soft start.

    The buck is behavioural: a ramp to the derived output over the cited
    soft-start time, behind a series resistance chosen so the current cannot
    exceed the cited limit. That is not a control loop and does not pretend
    to be one — it bounds the answer with cited numbers.
    """
    v_out = v_out_spread(100e3, 22e3)[1]
    t_ss = U3.params["t_soft_start"].value
    # Series resistance is the buck's own CONDUCTION resistance — the same
    # cited D*Rds_p + (1-D)*Rds_n that thermal.py uses — not the current
    # limit. The first version of this deck used v_out/i_limit = 0.95 ohm as a
    # stand-in for the limit, which is not a resistance the circuit has: it
    # put a permanent 0.36 V droop on the rail and made +3V3 settle at
    # 2.963 V, i.e. it invented a brownout. A current limit clamps during
    # startup; it does not add steady-state droop.
    r_series = r_conduction()
    r_load = max(v_out / i_load, 1e-3)
    t_plug = t_ss * 0.1
    return f"""* vbench T1.4 - USB cold start
* VBUS steps at t={t_plug:.12g}s through the declared cable resistance into
* the BOM's +5V bulk; the buck then ramps over its cited soft-start time.
Vbus vbus 0 PULSE(0 {v_psu} {t_plug:.12g} 1u)
Rcable vbus v5 {r_cable:.6g}
C5 v5 0 {c_5v:.12g}
* Behavioural buck: PWL ramp to the derived output over the cited t_SS,
* behind the cited conduction resistance. Not a control loop.
Vramp ramp 0 PWL(0 0 {t_plug:.12g} 0 {t_plug + t_ss:.12g} {v_out:.6g} 1 {v_out:.6g})
Rss ramp out {r_series:.6g}
C3 out 0 {c_3v3:.12g}
Rload out 0 {r_load:.6g}
.tran {t_ss / 2000:.12g} {t_ss * 4:.12g}
.meas tran t_3v3_valid WHEN v(out)={V_3V3_VALID} RISE=1
.meas tran v_final MAX v(out)
* Branch current is read from the voltage source: ngspice's .meas cannot
* take i() of a resistor, and abs() is not available there either. The
* source sinks current, so this comes out negative and is made positive in
* Python.
.meas tran i_inrush_signed MIN i(Vbus)
.meas tran v5_min MIN v(v5) FROM={t_plug:.12g} TO={t_ss * 4:.12g}
.end
"""


def deck_load_step(c_3v3, i_base, i_step, v_out, r_series):
    """A load step on +3V3 — the backlight has no ballast, so it is a step."""
    t_step = 200e-6
    r_base = v_out / i_base
    r_extra = v_out / i_step
    return f"""* vbench T1.4 - +3V3 load step (backlight, R25-HIGH-1: no ballast)
Vsrc src 0 DC {v_out:.6g}
Rout src out {r_series:.6g}
C3 out 0 {c_3v3:.12g}
Rbase out 0 {r_base:.6g}
* Switch a second load in at t={t_step:.12g}s
Sstep out 0 ctl 0 SW
.model SW SW(ron={r_extra:.6g} roff=1e9 vt=0.5)
Vctl ctl 0 PULSE(0 1 {t_step:.12g} 1u)
.tran 1u {t_step * 4:.12g}
.meas tran v_min MIN v(out) FROM={t_step:.12g} TO={t_step * 4:.12g}
.meas tran v_settled MAX v(out) FROM={t_step * 3:.12g} TO={t_step * 4:.12g}
.end
"""


# ── ngspice ─────────────────────────────────────────────────────────

_MEAS = re.compile(r"^\s*([a-z_0-9]+)\s*=\s*([-\d.eE+]+)", re.MULTILINE)


def run_ngspice(deck, workdir):
    if shutil.which("ngspice") is None:
        raise SimulatorMissing(
            "ngspice is not on PATH. This module exits rather than skipping: "
            "'no transient violations' from a run that never simulated "
            "anything is the worst output this bench could produce. "
            "Install with `brew install ngspice`.")
    path = os.path.join(workdir, "deck.cir")
    with open(path, "w") as fh:
        fh.write(deck)
    proc = subprocess.run(["ngspice", "-b", path], capture_output=True,
                          text=True, timeout=120, cwd=workdir)
    out = proc.stdout + proc.stderr
    values = {}
    for name, raw in _MEAS.findall(out):
        try:
            values[name] = float(raw)
        except ValueError:
            continue
    if not values:
        raise SimulatorMissing(
            f"ngspice produced no .meas results (rc={proc.returncode}). "
            f"Deck at {path}. Output:\n{out[-1500:]}")
    return values, out


# ── Closed-form cross-check ─────────────────────────────────────────

def ripple_closed_form(c_out, l_buck, duty, v_in, v_out):
    """Textbook buck output ripple, as an independent route to the answer.

    dI_L = (v_in - v_out) * D / (L * f_sw);  dV = dI_L / (8 * C * f_sw).
    Derived, not cited — the datasheet gives f_sw, L and C come from the BOM,
    and the formula is standard. It exists to disagree with the simulation if
    either is wrong.
    """
    f_sw = U3.params["f_switching"].value
    d_i = (v_in - v_out) * duty / (l_buck * f_sw)
    return d_i / (8.0 * c_out * f_sw), d_i


# ── Report ──────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--keep", action="store_true",
                    help="leave the generated decks on disk")
    args = ap.parse_args(argv)

    require_valid(Q1, U2, U3)
    caps, l_buck = board_values()
    duty, v_out, v_in = None, None, None
    from vbench.thermal import duty_cycle
    duty, v_out, v_in = duty_cycle()
    psu = sources.psu()
    c_3v3, absent_3v3 = caps["+3V3"]
    c_5v, _ = caps["+5V"]
    i_gaming = 0.430

    workdir = tempfile.mkdtemp(prefix="vbench-tran-")
    failures, results = [], []
    try:
        print("=" * 72)
        print("  Virtual Bench T1.4 — transients (ngspice)")
        print("=" * 72)
        print(f"  +3V3 bulk : {c_3v3*1e6:.1f} uF from the BOM")
        if absent_3v3:
            print(f"              {', '.join(absent_3v3)} contribute nothing "
                  f"(DNP: no BOM value, so no capacitor)")
        print(f"  +5V bulk  : {c_5v*1e6:.1f} uF · L2 = {l_buck*1e6:.1f} uH · "
              f"D = {duty:.3f} · f_sw = "
              f"{U3.params['f_switching'].value/1e6:.0f} MHz (cited)")
        print(f"  Calibration: {sources.CALIBRATION} — the cell's internal "
              f"resistance is not measured")
        print()
        print("  The SY8089 control loop is NOT modelled: no compensation "
              "network is in")
        print("  the pages this repo holds. Soft start, current limit and "
              "f_sw are cited;")
        print("  the buck is behavioural behind them.")

        # ── 1. ripple ────────────────────────────────────────────────
        vals, _ = run_ngspice(
            deck_ripple(c_3v3, l_buck, duty, v_in, i_gaming), workdir)
        sim_ripple = vals["v_max"] - vals["v_min"]
        cf_ripple, d_i = ripple_closed_form(c_3v3, l_buck, duty, v_in, v_out)
        print()
        print("-" * 72)
        print(f"  1. +3V3 ripple at {i_gaming*1000:.0f} mA")
        print(f"     simulated   : {sim_ripple*1e3:.3f} mV pk-pk "
              f"(mean {vals['v_avg']:.3f} V)")
        print(f"     closed form : {cf_ripple*1e3:.3f} mV pk-pk "
              f"(dI_L = {d_i*1e3:.0f} mA)")
        agree = abs(sim_ripple - cf_ripple) <= 0.5 * max(sim_ripple, cf_ripple)
        print(f"     the two routes {'agree' if agree else 'DISAGREE'} within "
              f"a factor of 2 — an independent check on both")
        if not agree:
            failures.append(
                f"simulated ripple {sim_ripple*1e3:.2f} mV and closed form "
                f"{cf_ripple*1e3:.2f} mV disagree by more than 2x; one of "
                f"the two is wrong and the bench cannot say which")
        results.append(Measured("ripple", {"v_pp": sim_ripple,
                                           "v_pp_closed_form": cf_ripple},
                                "output filter only"))

        # ── 2. cold start ────────────────────────────────────────────
        vals, _ = run_ngspice(
            deck_cold_start(c_5v, c_3v3, i_gaming, psu.v_open,
                            psu.r_internal), workdir)
        t_valid = vals.get("t_3v3_valid")
        print()
        print("-" * 72)
        print(f"  2. USB cold start")
        print(f"     t_3v3_valid : "
              f"{t_valid*1e3:.3f} ms to reach {V_3V3_VALID} V "
              f"({V_3V3_VALID_SRC})" if t_valid else
              f"     t_3v3_valid : NEVER reached {V_3V3_VALID} V")
        i_inrush = abs(vals.get("i_inrush_signed", 0.0))
        t_charge = cap_charge_time(c_5v, psu.v_open, psu.i_limit)
        print(f"     V_final     : {vals['v_final']:.3f} V")
        print(f"     inrush      : {i_inrush:.1f} A peak in this deck — an "
              f"UPPER BOUND, not a")
        print(f"                   prediction: the deck steps an ideal "
              f"{psu.v_open} V through")
        print(f"                   {psu.r_internal} ohm and does not model the "
              f"supply's foldback.")
        print(f"                   A {psu.i_limit} A limited supply instead "
              f"charges the {c_5v*1e6:.0f} uF")
        print(f"                   in C*V/I = {t_charge*1e6:.0f} us, which is "
              f"the number to use.")
        print(f"     V(+5V) min  : {vals['v5_min']:.3f} V (before the plug, "
              f"i.e. the rail at rest)")
        t_ss = U3.params["t_soft_start"].value
        if t_valid is None:
            failures.append("+3V3 never reaches 3.0 V in the cold-start deck")
        elif t_valid > 5 * t_ss:
            failures.append(
                f"t_3v3_valid {t_valid*1e3:.2f} ms is more than 5x the cited "
                f"soft-start time {t_ss*1e3:.1f} ms")
        # The deck's inrush peak is deliberately NOT a failure. It exceeds the
        # PSU's limit by construction — an ideal step into a discharged
        # capacitor through 50 mohm is V/R — and treating that as a board
        # defect would be reporting a property of the deck as a property of
        # the hardware. The charge time above is the honest output.
        results.append(Measured("cold_start", dict(vals), ""))

        # ── 3. load step (the unballasted backlight) ─────────────────
        vals, _ = run_ngspice(
            deck_load_step(c_3v3, i_gaming, 0.100, v_out, r_conduction()),
            workdir)
        droop = vals["v_settled"] - vals["v_min"]
        print()
        print("-" * 72)
        print(f"  3. +3V3 load step, +100 mA (backlight, no ballast)")
        print(f"     V_min       : {vals['v_min']:.3f} V "
              f"(droop {droop*1e3:.1f} mV)")
        if vals["v_min"] < V_3V3_VALID:
            failures.append(
                f"a 100 mA step drops +3V3 to {vals['v_min']:.3f} V, below "
                f"the {V_3V3_VALID} V the ESP32-S3 requires")
        results.append(Measured("load_step", dict(vals),
                                "open-loop droop; the real regulator's loop "
                                "would recover faster and is not modelled"))

        # ── 4. battery sag and brownout, from cited resistances ──────
        print()
        print("-" * 72)
        print("  4. battery sag and brownout (analytic, two-term)")
        for soc in (0.50, 0.10, 0.0):
            cell = sources.lipo(soc)
            # Boost input current for the +3V3 load, using the cited boost
            # rating only as a bound; efficiency is UNESTABLISHED for U2, so
            # this is stated as a lower bound on the current.
            i_bat = i_gaming * v_out / cell.v_open
            v_gs = -cell.v_open
            drop_q1 = i_bat * r_ds_on(v_gs)
            drop_cell = i_bat * cell.r_internal
            print(f"     SoC {soc:4.2f}: OCV {cell.v_open:.3f} V "
                  f"- cell {drop_cell*1e3:5.1f} mV (UNCALIBRATED) "
                  f"- Q1 {drop_q1*1e3:5.1f} mV (cited) "
                  f"= {cell.v_open - drop_cell - drop_q1:.3f} V at U2.6")
        uvlo = U3.params["v_uvlo"].value
        print(f"     U3 stops regulating below {uvlo} V on its input "
              f"({U3.params['v_uvlo'].locator}); the boost holds +5V, so the")
        print(f"     brownout threshold is set by the IP5306's own cut-off, "
              f"which is NOT in the")
        print(f"     pages this repo holds — see u2_ip5306.UNESTABLISHED.")

        print()
        print("=" * 72)
        if failures:
            print(f"  FAIL — {len(failures)} transient violation(s):")
            for f in failures:
                print(f"    {f}")
            print("=" * 72)
            return 1
        print("  No transient violation, within what is modelled. The "
              "regulator's control")
        print("  loop and the IP5306's brownout threshold are not — so this "
              "is not a")
        print("  clean bill of health, and T5.5 is where a scope settles it.")
        print("=" * 72)
        return 0
    except SimulatorMissing as exc:
        print(f"  ERROR  {exc}", file=sys.stderr)
        return 2
    finally:
        if args.keep:
            print(f"\n  decks kept in {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
