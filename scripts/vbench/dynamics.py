"""Virtual Bench T1.4b — dynamic corner scenarios (containment layer 3).

Three questions the geometric gates cannot ask, each answered by ngspice
on decks built from the netlist, the BOM's values and cited parameters
(docs/archived/containment-roadmap.md, layer 3):

1. **Buck output across divider corners.** Vout = Vref * (1 + R25/R26) is
   monotone: increasing in Vref and R_top, decreasing in R_bottom. So the
   two deterministic corners (all-high, all-low) BOUND every Monte Carlo
   draw — a corner sweep is the reproducible superset of an MC run, and a
   gate must be reproducible, so corners are what runs here. Each corner
   is simulated as the real L2/C-bulk output filter switching at the
   cited f_sw, and the ripple crest at the high corner / valley at the
   low corner is checked against the ESP32-S3's cited supply window.

2. **EN power-up ramp.** The R3/C31 network (found in the netlist, values
   from the BOM) is driven by the buck's cited soft-start ramp; EN must
   cross V_IH_nRST (0.75 x VDD, cited) only AFTER the rail itself is
   valid. This is the timing check verify_strapping_pins.py deliberately
   defers ("timing is computed by the bench") — the promise is now kept
   here.

3. **Battery brownout under the SNES stress load.** The pack at each OCV
   curve point, behind its family-bound internal resistance and Q1's
   cited R_ds_on, must keep the IP5306 inside its cited operating range;
   and the +5V bulk must ride a stress-load step without crossing the
   cited output UVP. The SoC below which the pack leaves the operating
   window is reported; the gate fails if that happens with more than 10%
   of the pack left — a board that browns out at 10% SoC under load is a
   usability defect, not end-of-charge.

## What is declared, what is cited, what is not establishable

* The SNES stress current (1.5 A on +3V3) is a SCENARIO INPUT from the
  containment roadmap — a question we ask the board, not a datasheet
  claim. It is printed as such.
* MLCC ESR at f_sw is NOT establishable from the held pages: the C12891
  document is Samsung's family catalog, which specifies dissipation
  factor at 120 Hz only. A 120 Hz-derived ESR bound is meaningless three
  decades up in frequency, so the output filter here is ESR-less and the
  simulated ripple is a FLOOR — stated on every corner, the same way
  transients.py states that the control loop is not modelled.
* IP5306 boost efficiency is a single cited "up to 0.92" point, so every
  battery-side current here is a LOWER bound (same status as in
  transients.py section 4).

Exit codes: 0 clean, 1 violation, 2 simulator missing — never a skip.

Usage:
    python3 scripts/vbench/dynamics.py
    python3 scripts/vbench/dynamics.py --keep
"""

import argparse
import os
import shutil
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import netlist as nl                             # noqa: E402
from vbench import rails, sources                            # noqa: E402
from vbench.models import require_valid                      # noqa: E402
from vbench.models.q1_si2301 import Q1, r_ds_on              # noqa: E402
from vbench.models.u1_esp32s3 import U1                      # noqa: E402
from vbench.models.u2_ip5306 import U2                       # noqa: E402
from vbench.models.u3_sy8089 import U3, v_out                # noqa: E402
from vbench.transients import (                              # noqa: E402
    SimulatorMissing, board_values, r_conduction, run_ngspice)

# Scenario input, not a claim: the containment roadmap's SNES stress
# current on +3V3. transients.py's 0.430 A is the measured-class gaming
# estimate; this is the deliberate worst-case question.
I_SNES_STRESS = 1.5
I_SNES_STRESS_SRC = ("docs/archived/containment-roadmap.md layer 3 — scenario "
                     "input, not a datasheet number")

# The board browns out at this much pack remaining => defect. A judgment
# declared here, not hidden in a comparison: end-of-charge cutoff is
# expected at 0% SoC; losing the last 10% to sag under load is accepted;
# more than that is not.
SOC_BROWNOUT_ACCEPTABLE = 0.10


# ── Divider corners ─────────────────────────────────────────────────

def divider_corners():
    """(label, v_corner) for lo/typ/hi — deterministic Monte Carlo bounds.

    Vout = Vref * (1 + Rt/Rb) is monotone in each variable, so the
    extreme output lives at the extreme corners; nothing between them
    can escape the [lo, hi] interval. Resistor identity and values come
    from the netlist + BOM via rails.find_feedback_divider, never from
    this module.
    """
    board = nl.load_board_netlist()
    values = rails.load_bom_values()
    div = rails.find_feedback_divider(board, values)
    r_top, r_bot = div.r_top_ohm, div.r_bottom_ohm
    tol = U3.params["r_divider_tolerance"].value
    v_lo, v_typ, v_hi = U3.params["v_fb_ref"].value
    return [
        ("lo", v_out(r_top * (1 - tol), r_bot * (1 + tol), v_lo)),
        ("typ", v_out(r_top, r_bot, v_typ)),
        ("hi", v_out(r_top * (1 + tol), r_bot * (1 - tol), v_hi)),
    ]


def deck_corner_ripple(c_out, l_buck, v_in, v_corner, i_load):
    """The transients.py ripple deck, retargeted at a corner output.

    Same open-loop LC caveat as deck_ripple: the ring is the deck's, not
    the board's, so ripple is measured in a late window.
    """
    f_sw = U3.params["f_switching"].value
    period = 1.0 / f_sw
    duty = v_corner / v_in
    r_load = max(v_corner / i_load, 1e-3)
    settle = 4e-3
    window = 20 * period
    return f"""* vbench T1.4b - +3V3 ripple at divider corner {v_corner:.4g} V
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


# ── EN ramp ─────────────────────────────────────────────────────────

def find_en_rc():
    """R3/C31 by role, from the netlist: the pull-up is the R on both EN
    and +3V3, the delay cap is the C on both EN and GND. Values from the
    BOM. Raises if either is missing — a deck with an invented RC would
    verify a board that does not exist."""
    board = nl.load_board_netlist()
    values = rails.load_bom_values()
    en_refs = {p.ref for p in board.nets.get("EN", ())}
    v33_refs = {p.ref for p in board.nets.get("+3V3", ())}
    gnd_refs = {p.ref for p in board.nets.get("GND", ())}
    pullups = sorted(r for r in en_refs & v33_refs if r.startswith("R"))
    caps = sorted(c for c in en_refs & gnd_refs if c.startswith("C"))
    if not pullups or not caps:
        raise rails.RailError(
            f"EN RC network not found in the netlist (pull-ups: {pullups}, "
            f"caps: {caps}) — verify_strapping_pins.py owns the topological "
            "verdict; this module only times what exists.")
    r_ref, c_ref = pullups[0], caps[0]
    r_val, c_val = values.get(r_ref), values.get(c_ref)
    if r_val is None or c_val is None:
        raise rails.RailError(
            f"{r_ref}/{c_ref} found on EN but missing a BOM value — DNP "
            "parts cannot delay anything.")
    return r_ref, r_val, c_ref, c_val


def deck_en_ramp(c_3v3, i_load, r_en, c_en, v_rail):
    """Buck soft-start ramp (behavioural, as in transients.py) feeding
    the EN RC. Measures when the rail is valid and when EN releases the
    chip — the whole check is the sign of the difference."""
    t_ss = U3.params["t_soft_start"].value
    r_series = r_conduction()
    r_load = max(v_rail / i_load, 1e-3)
    v_valid = U1.params["v_supply_range"].value[0]
    v_ih = U1.params["v_ih_nrst_ratio"].value * v_rail
    return f"""* vbench T1.4b - EN RC ramp vs rail validity
* Rail: cited soft-start ramp behind the cited conduction resistance.
* EN: the board's own R/C read from netlist + BOM.
Vramp ramp 0 PWL(0 0 {t_ss:.12g} {v_rail:.6g} 1 {v_rail:.6g})
Rss ramp out {r_series:.6g}
C3 out 0 {c_3v3:.12g}
Rload out 0 {r_load:.6g}
Ren out en {r_en:.6g}
Cen en 0 {c_en:.12g}
.tran {t_ss / 2000:.12g} {t_ss * 10:.12g} UIC
.meas tran t_rail_valid WHEN v(out)={v_valid:.6g} RISE=1
.meas tran t_en_release WHEN v(en)={v_ih:.6g} RISE=1
.end
"""


# ── Battery brownout ────────────────────────────────────────────────

def stress_currents(v_bat):
    """Currents for the SNES stress load, each with its epistemic status.

    +5V-side current is derived (buck conduction loss from cited R_ds_on);
    battery-side current uses the cited "up to" boost efficiency, so it
    is a LOWER bound (U2 efficiency curve is UNESTABLISHED).
    """
    v33 = v_out(100e3, 22e3)  # typ target; identity from netlist elsewhere
    p_33 = v33 * I_SNES_STRESS
    p_5 = p_33 + I_SNES_STRESS ** 2 * r_conduction()
    v5 = U2.params["v_out_typ"].value
    i_5 = p_5 / v5
    eta = U2.params["eta_boost_max"].value
    i_bat = p_5 / (v_bat * eta)
    return i_5, i_bat


def deck_bulk_ride_through(c_5v, i_5):
    """Stress-load step on +5V behind the boost's derived output
    resistance: does the bulk keep the rail above the cited UVP?"""
    v5 = U2.params["v_out_typ"].value
    r_out = U2.params["r_out_boost"].value
    t_step = 200e-6
    r_load = v5 / i_5
    return f"""* vbench T1.4b - +5V bulk ride-through of the SNES stress step
Vsrc src 0 DC {v5:.6g}
Rout src v5 {r_out:.6g}
C5 v5 0 {c_5v:.12g}
Sstep v5 0 ctl 0 SW
.model SW SW(ron={r_load:.6g} roff=1e9 vt=0.5)
Vctl ctl 0 PULSE(0 1 {t_step:.12g} 1u)
.tran 1u {t_step * 4:.12g}
.meas tran v5_min MIN v(v5) FROM={t_step:.12g} TO={t_step * 4:.12g}
.end
"""


def brownout_soc():
    """Highest OCV-curve SoC at which the pack leaves the IP5306's cited
    operating window under the stress load, and the terminal voltages.

    Analytic on purpose (V = OCV - I*R needs no simulator); the dynamic
    half of scenario 3 is the ride-through deck. Walks the declared OCV
    points from full to empty and returns the first that fails, or None.
    """
    v_bat_min = U2.params["v_bat_operating_min"].value
    rows = []
    first_fail = None
    for soc in (1.0, 0.5, 0.3, 0.2, 0.1, 0.05, 0.0):
        cell = sources.lipo(soc)
        _, i_bat = stress_currents(cell.v_open)
        drop = i_bat * (cell.r_internal + r_ds_on(-cell.v_open))
        v_term = cell.v_open - drop
        ok = v_term >= v_bat_min
        rows.append((soc, cell.v_open, i_bat, v_term, ok))
        if not ok and first_fail is None:
            first_fail = soc
    return rows, first_fail, v_bat_min


# ── Report ──────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--keep", action="store_true",
                    help="leave the generated decks on disk")
    args = ap.parse_args(argv)

    require_valid(Q1, U1, U2, U3)
    caps, l_buck = board_values()
    c_3v3, _ = caps["+3V3"]
    c_5v, _ = caps["+5V"]
    from vbench.thermal import duty_cycle
    _, v_rail, v_in = duty_cycle()
    v_lo_ok, _, v_hi_ok = U1.params["v_supply_range"].value

    workdir = tempfile.mkdtemp(prefix="vbench-dyn-")
    failures = []
    try:
        print("=" * 72)
        print("  Virtual Bench T1.4b — dynamic corner scenarios (ngspice)")
        print("=" * 72)
        print(f"  SNES stress load: {I_SNES_STRESS} A on +3V3 "
              f"({I_SNES_STRESS_SRC})")
        print("  MLCC ESR at f_sw: NOT establishable from the held pages "
              "(the C12891 doc")
        print("  specifies DF at 120 Hz only) — simulated ripple is a "
              "FLOOR, stated per corner.")

        # ── 1. divider corners ───────────────────────────────────────
        print()
        print("-" * 72)
        print(f"  1. buck output at divider corners vs the ESP32-S3 window "
              f"[{v_lo_ok}, {v_hi_ok}] V")
        corners = divider_corners()
        for label, v_corner in corners:
            vals, _ = run_ngspice(
                deck_corner_ripple(c_3v3, l_buck, v_in, v_corner,
                                   I_SNES_STRESS), workdir)
            ripple = vals["v_max"] - vals["v_min"]
            print(f"     {label:>3}: target {v_corner:.3f} V, simulated "
                  f"mean {vals['v_avg']:.3f} V, ripple {ripple*1e3:.1f} mV "
                  f"pk-pk (ESR-less floor)")
            if label == "hi" and vals["v_max"] > v_hi_ok:
                failures.append(
                    f"high divider corner puts the +3V3 crest at "
                    f"{vals['v_max']:.3f} V, above the module's cited "
                    f"{v_hi_ok} V maximum")
            if label == "lo" and vals["v_min"] < v_lo_ok:
                failures.append(
                    f"low divider corner puts the +3V3 valley at "
                    f"{vals['v_min']:.3f} V, below the module's cited "
                    f"{v_lo_ok} V minimum")

        # ── 2. EN ramp ───────────────────────────────────────────────
        r_ref, r_en, c_ref, c_en = find_en_rc()
        vals, _ = run_ngspice(
            deck_en_ramp(c_3v3, I_SNES_STRESS, r_en, c_en, v_rail), workdir)
        t_rail = vals.get("t_rail_valid")
        t_en = vals.get("t_en_release")
        print()
        print("-" * 72)
        print(f"  2. EN ramp: {r_ref} = {r_en/1e3:.0f} k / {c_ref} = "
              f"{c_en*1e9:.0f} nF from the BOM (tau = {r_en*c_en*1e3:.2f} ms; "
              f"datasheet recommends "
              f"{U1.params['en_rc_r_recommended'].value/1e3:.0f} k / "
              f"{U1.params['en_rc_c_recommended'].value*1e6:.0f} uF)")
        if t_rail is None or t_en is None:
            failures.append("EN ramp deck never crossed one of its "
                            "thresholds — rail or EN stuck low")
        else:
            margin = t_en - t_rail
            print(f"     rail valid at {t_rail*1e3:.3f} ms, EN releases the "
                  f"chip at {t_en*1e3:.3f} ms")
            print(f"     margin: {margin*1e3:+.3f} ms (EN must release "
                  f"AFTER the rail is valid; t_SU min is cited 0)")
            if margin <= 0:
                failures.append(
                    f"EN releases the chip {-margin*1e3:.3f} ms BEFORE the "
                    f"rail is valid — the strap-sampling supply race the RC "
                    "exists to prevent")

        # ── 3. battery brownout ──────────────────────────────────────
        rows, first_fail, v_bat_min = brownout_soc()
        print()
        print("-" * 72)
        print(f"  3. battery vs IP5306 operating minimum {v_bat_min} V "
              f"under the stress load")
        for soc, ocv, i_bat, v_term, ok in rows:
            print(f"     SoC {soc:4.2f}: OCV {ocv:.3f} V, I_bat >= "
                  f"{i_bat:.2f} A (lower bound), terminal {v_term:.3f} V "
                  f"{'ok' if ok else '** below operating minimum'}")
        if first_fail is not None and first_fail > SOC_BROWNOUT_ACCEPTABLE:
            failures.append(
                f"pack leaves the IP5306 operating window at SoC "
                f"{first_fail:.2f} under the stress load — more than the "
                f"declared {SOC_BROWNOUT_ACCEPTABLE:.0%} acceptable loss")
        i_5, _ = stress_currents(sources.lipo(0.5).v_open)
        vals, _ = run_ngspice(deck_bulk_ride_through(c_5v, i_5), workdir)
        uvp = U2.params["v_out_uvp"].value
        print(f"     +5V under the {i_5:.2f} A stress step: min "
              f"{vals['v5_min']:.3f} V vs cited UVP {uvp} V")
        if vals["v5_min"] < uvp:
            failures.append(
                f"+5V sags to {vals['v5_min']:.3f} V under the stress step, "
                f"below the IP5306's cited {uvp} V output UVP — the boost "
                "declares brownout")

        print()
        print("=" * 72)
        if failures:
            print(f"  FAIL — {len(failures)} dynamic violation(s):")
            for f in failures:
                print(f"    {f}")
            print("=" * 72)
            return 1
        print("  No dynamic violation, within what is modelled. ESR and the "
              "boost efficiency")
        print("  curve are not — the corners bound the divider, not the "
              "capacitors.")
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
