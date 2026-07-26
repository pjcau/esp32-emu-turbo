"""Virtual Bench T1.5 — junction temperatures, and which ones are guesses.

Computes Tj = T_ambient + P * theta_JA for each part, at two ambients, for
three load scenarios. What makes this different from
`scripts/verify_thermal_budget.py` is not the arithmetic — that is the same
formula — but that **every dissipation figure is either derived from a cited
parameter or declared not computable**, and the report separates the two.

Where the numbers come from:

* **U3 (SY8089)** — conduction loss only, from the two cited on-resistances
  and the duty cycle the rails module derives:
  `P = I^2 * (D*Rds_p + (1-D)*Rds_n)`. Switching loss is **not** included,
  because the pages read give no gate charge for the internal FETs and no
  efficiency curve at this board's operating point (figure 2 on page 1 is
  V_OUT = 1.8 V, not 3.33 V). So U3's figure is a **lower bound** and says so.
* **U5 (PAM8403)** — from the cited 90% efficiency and the cited 6.3 mA
  standby current, both on page 1.
* **Q1 (Si2301CDS)** — `I^2 * Rds_on`, on-resistance cited, using the
  steady-state theta_JA of 175 degC/W from note d rather than the 120/145
  pair, which the table qualifies as "<= 5 s". A handheld is steady state.
* **U2 (IP5306)** — **not computable from the cited pages.** Pages 2-4 give
  theta_JA and the absolute maxima but no boost efficiency, so the power lost
  in the converter cannot be derived. Reported as unestablished instead of
  filled in with an assumed 92%, which is what the existing gate does.

Ambient: the plan asks for both 30 degC external air and the 40 degC
in-enclosure figure the existing gate assumes. Both are printed; **40 degC
governs pass/fail** until the enclosure rise is measured on the prototype,
because inside a closed handheld the air around U2 and U3 is warmer than the
room.

theta_JA and copper: each datasheet states the board it measured on — 2" x 2"
FR-4 with 2 oz copper and thermal vias for the SY8089 (page 4, note 2), 1" x
1" FR-4 for the Si2301 (page 1, note b). This board gives both parts less
copper than that, so the real theta_JA is **worse** than the cited figure and
these junction temperatures are optimistic. No correction factor is applied,
because a factor picked without measuring the actual copper area would be a
number with no source. Measuring it from the PCB is the next refinement, and
`COPPER_CAVEAT` below is printed so the gap cannot be forgotten.

Usage:
    python3 scripts/vbench/thermal.py
    python3 scripts/vbench/thermal.py --ambient 25
"""

import argparse
import collections
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench.models import require_valid                      # noqa: E402
from vbench.models.q1_si2301 import Q1, r_ds_on              # noqa: E402
from vbench.models.u2_ip5306 import U2                       # noqa: E402
from vbench.models.u3_sy8089 import U3, v_out_spread         # noqa: E402
from vbench.models.u5_pam8403 import U5                      # noqa: E402

# Plan T1.5: 30 degC is the external air temperature; 40 degC is the existing
# gate's in-enclosure worst case and is the one that governs pass/fail until
# the enclosure rise is measured on the prototype.
AMBIENT_EXTERNAL = 30.0
AMBIENT_IN_ENCLOSURE = 40.0
GOVERNING_AMBIENT = AMBIENT_IN_ENCLOSURE

# Margin below the part's own maximum junction temperature.
SAFE_MARGIN = 25.0

COPPER_CAVEAT = (
    "theta_JA is the datasheet's figure, measured on more copper than this "
    "board gives (SY8089: 2\"x2\" 2oz with thermal vias, page 4 note 2; "
    "Si2301: 1\"x1\", page 1 note b). Real theta_JA is higher, so every Tj "
    "below is optimistic. No correction is applied because a factor chosen "
    "without measuring the board's copper would have no source.")

# Load scenarios. Currents are the same figures scripts/simulate_circuit.py
# and verify_thermal_budget.py use, so the two tools can be compared; they
# are engineering estimates of this design's consumption, not datasheet
# values, and are labelled as such in the report.
Scenario = collections.namedtuple("Scenario", "name desc i_3v3 audio_out_w")
SCENARIOS = (
    Scenario("idle", "menu / standby", 0.150, 0.0),
    Scenario("gaming", "SNES at 60 fps", 0.430, 0.2),
    Scenario("charge-and-play", "gaming while charging over USB", 0.430, 0.2),
)

Result = collections.namedtuple("Result", "ref part p_watts basis tj margin "
                                          "tj_max ok")


def duty_cycle():
    """Buck duty cycle D = Vout/Vin, both from the models, not assumed."""
    v_out = v_out_spread(100e3, 22e3)[1]          # typ, from the real divider
    v_in = U2.params["v_out_typ"].value           # the +5V rail feeds U3
    return v_out / v_in, v_out, v_in


def p_buck_conduction(i_out):
    """Conduction loss in U3's two internal FETs. A LOWER BOUND."""
    d, _, _ = duty_cycle()
    r_p = U3.params["r_ds_on_pfet"].value
    r_n = U3.params["r_ds_on_nfet"].value
    return i_out ** 2 * (d * r_p + (1.0 - d) * r_n)


def p_pam8403(audio_out_w):
    """Class-D loss from the cited efficiency, plus the cited standby draw."""
    eta = U5.params["efficiency_max"].value
    v = U5.params["v_supply_rated"].value
    quiescent = U5.params["i_standby"].value * v
    if audio_out_w <= 0:
        return quiescent
    return audio_out_w * (1.0 / eta - 1.0) + quiescent


def p_q1(i_battery, v_bat):
    """Conduction loss in the reverse-polarity FET. V_GS = -V_BAT."""
    return i_battery ** 2 * r_ds_on(-v_bat, worst_case=True)


def evaluate(scenario, ambient, v_bat=3.83):
    """Per-part results for one scenario at one ambient."""
    out = []

    p3 = p_buck_conduction(scenario.i_3v3)
    theta3 = U3.params["theta_ja"].value
    tj3 = ambient + p3 * theta3
    tjmax3 = U3.params["t_junction_max"].value
    out.append(Result(
        "U3", U3.part, p3,
        "conduction only (cited Rds_on x duty); switching loss NOT included "
        "— LOWER BOUND", tj3, tjmax3 - SAFE_MARGIN - tj3, tjmax3,
        tj3 <= tjmax3 - SAFE_MARGIN))

    p5 = p_pam8403(scenario.audio_out_w)
    # U5 has no cited theta_JA — see u5_pam8403.UNESTABLISHED. Reported as
    # power only; a Tj without a theta_JA would be invention.
    out.append(Result(
        "U5", U5.part, p5,
        "cited 90% efficiency + cited 6.3 mA standby; theta_JA NOT cited "
        "anywhere, so no Tj is computed", None, None, None, None))

    # The battery current in charge-and-play comes from USB, not the cell, so
    # Q1 carries only what the boost draws when running on the battery.
    i_bat = 0.0 if scenario.name == "charge-and-play" else (
        scenario.i_3v3 * 3.327 / v_bat / 0.90)
    pq = p_q1(i_bat, v_bat)
    thetaq = Q1.params["theta_ja_steady_state"].value
    tjq = ambient + pq * thetaq
    tjmaxq = Q1.params["t_junction_max"].value
    out.append(Result(
        "Q1", Q1.part, pq,
        f"I^2 x cited Rds_on at V_GS=-{v_bat:.2f} V; steady-state theta_JA "
        f"175 degC/W (note d), not the <=5 s 120/145 pair",
        tjq, tjmaxq - SAFE_MARGIN - tjq, tjmaxq,
        tjq <= tjmaxq - SAFE_MARGIN))

    out.append(Result(
        "U2", U2.part, None,
        "NOT COMPUTABLE: pages 2-4 give theta_JA 40 degC/W and the absolute "
        "maxima but no boost efficiency, so converter loss cannot be "
        "derived. verify_thermal_budget.py assumes 92% and 80 degC/W, "
        "neither of which is cited.", None, None, None, None))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ambient", type=float, default=None,
                    help="override the governing ambient in degC")
    args = ap.parse_args(argv)

    require_valid(Q1, U2, U3, U5)
    governing = args.ambient if args.ambient is not None else GOVERNING_AMBIENT
    ambients = sorted({AMBIENT_EXTERNAL, AMBIENT_IN_ENCLOSURE, governing})
    d, v_out, v_in = duty_cycle()

    print("=" * 72)
    print("  Virtual Bench T1.5 — junction temperatures")
    print("=" * 72)
    print(f"  Duty cycle    : D = {v_out:.3f}/{v_in:.3f} = {d:.3f} "
          f"(both derived, neither assumed)")
    print(f"  Ambients      : {', '.join(f'{a:.0f}' for a in ambients)} degC "
          f"— {governing:.0f} degC governs pass/fail")
    print(f"  Margin        : Tj must stay {SAFE_MARGIN:.0f} degC below the "
          f"part's own maximum")
    print()
    print(f"  Load currents are engineering estimates of this design's")
    print(f"  consumption, not datasheet values.")
    print()
    print(f"  {COPPER_CAVEAT}")

    failures = []
    for ambient in ambients:
        governs = abs(ambient - governing) < 1e-9
        print()
        print("-" * 72)
        print(f"  Ambient {ambient:.0f} degC"
              f"{'   << governs pass/fail' if governs else '   (reported only)'}")
        print("-" * 72)
        for sc in SCENARIOS:
            print(f"    {sc.name} — {sc.desc}, {sc.i_3v3*1000:.0f} mA on "
                  f"+3V3, {sc.audio_out_w:.1f} W audio")
            for r in evaluate(sc, ambient):
                if r.p_watts is None:
                    print(f"      {r.ref:3} {r.part:<12} P = ?        "
                          f"Tj = ?")
                    print(f"          {r.basis}")
                    continue
                tj = f"{r.tj:6.1f} degC" if r.tj is not None else "     ?    "
                verdict = ""
                if r.ok is not None:
                    limit = r.tj_max - SAFE_MARGIN
                    verdict = (("OK " if r.ok else "FAIL")
                               + f" (margin {r.margin:+.1f} degC to "
                                 f"{limit:.0f})")
                    if not r.ok and governs:
                        failures.append((ambient, sc.name, r))
                print(f"      {r.ref:3} {r.part:<12} "
                      f"P = {r.p_watts*1000:7.1f} mW   Tj = {tj}   {verdict}")
                print(f"          {r.basis}")

    print()
    print("=" * 72)
    if failures:
        print(f"  FAIL — {len(failures)} part/scenario over margin at the "
              f"governing ambient:")
        for ambient, name, r in failures:
            print(f"    {r.ref} in {name} at {ambient:.0f} degC: "
                  f"Tj {r.tj:.1f} degC, margin {r.margin:+.1f} degC")
        print("=" * 72)
        return 1
    print("  No part exceeds its margin at the governing ambient — within "
          "the")
    print("  dissipation figures that are actually derivable. U2's is not, "
          "and")
    print("  U3's excludes switching loss, so this is not a clean bill of "
          "health.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
