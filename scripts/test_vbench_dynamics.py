#!/usr/bin/env python3
"""Mutation-paired gate for vbench/dynamics.py — the dynamic scenarios
must be able to fail (containment roadmap layer 3).

Every assertion here is paired with a mutation that must flip it: a
dynamic gate that would pass a 10x-wrong divider tolerance, a 10x-small
EN cap or a quadrupled load is measuring nothing.

    T1  the real board passes all three scenarios (this IS the gate:
        a red here is a real dynamic violation on the current design)
    T2  a 10% divider tolerance pushes the high corner's crest past the
        module's 3.6 V ceiling — the corner measurement discriminates
    T3  a 10 nF EN cap releases the chip BEFORE the rail is valid — the
        ramp measurement discriminates
    T4  a 6 A stress load browns the pack out above 10% SoC — the
        brownout walk discriminates
    T5  main()'s failure path is real: a poisoned corner turns the whole
        run red (rc 1), not just a printed number
    T6  a missing simulator is rc 2, never a silent pass
    T7  registration: this gate is in VERIFY_ALL_SCRIPTS, the dispatch
        law routes it, and `make bench-dynamics` exists
    T8  the EN RC the deck times is the board's own R3/C31 with the
        BOM's 10k/100nF — netlist drift cannot silently retime the ramp
"""
from __future__ import annotations

import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from issue_dispatch import gates_from_makefile, route      # noqa: E402
from vbench import dynamics, transients                    # noqa: E402
from vbench.models.u1_esp32s3 import U1                    # noqa: E402
from vbench.models.u3_sy8089 import U3, v_out              # noqa: E402

BASE = Path(__file__).resolve().parent.parent


def main() -> int:
    print("=" * 72)
    print("VBENCH DYNAMICS MUTATION SUITE")
    print("=" * 72)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    workdir = tempfile.mkdtemp(prefix="vbench-dyn-test-")

    # T1 — the actual gate: the board as designed passes
    rc = dynamics.main([])
    check("T1 real board passes the dynamic scenarios", rc == 0,
          f"rc={rc}: a red here is a real finding, see the report above")

    # T2 — corner measurement discriminates: 10% tolerance escapes 3.6 V
    caps, l_buck = transients.board_values()
    c_3v3, _ = caps["+3V3"]
    from vbench.thermal import duty_cycle
    _, _, v_in = duty_cycle()
    v_hi_ok = U1.params["v_supply_range"].value[2]
    bad_corner = v_out(100e3 * 1.10, 22e3 * 0.90, U3.params["v_fb_ref"].value[2])
    vals, _ = transients.run_ngspice(
        dynamics.deck_corner_ripple(c_3v3, l_buck, v_in, bad_corner,
                                    dynamics.I_SNES_STRESS), workdir)
    check("T2 10% divider tolerance is caught at the corner",
          vals["v_max"] > v_hi_ok,
          f"crest {vals['v_max']:.3f} V vs ceiling {v_hi_ok} V")

    # T3 — EN ramp discriminates: a 10 nF cap races the rail
    _, r_en, _, _ = dynamics.find_en_rc()
    from vbench.thermal import duty_cycle as _dc
    _, v_rail, _ = _dc()
    vals, _ = transients.run_ngspice(
        dynamics.deck_en_ramp(c_3v3, dynamics.I_SNES_STRESS,
                              r_en, 10e-9, v_rail), workdir)
    t_rail, t_en = vals.get("t_rail_valid"), vals.get("t_en_release")
    check("T3 10 nF EN cap loses the race and is caught",
          t_rail is not None and t_en is not None and t_en < t_rail,
          f"t_en {t_en} vs t_rail {t_rail}")

    # T4 — brownout walk discriminates: 6 A kills the pack early
    saved = dynamics.I_SNES_STRESS
    try:
        dynamics.I_SNES_STRESS = 6.0
        _rows, first_fail, _ = dynamics.brownout_soc()
    finally:
        dynamics.I_SNES_STRESS = saved
    check("T4 a 6 A load browns out above the 10% threshold",
          first_fail is not None
          and first_fail > dynamics.SOC_BROWNOUT_ACCEPTABLE,
          f"first failing SoC = {first_fail}")

    # T5 — main()'s failure path: a poisoned corner reddens the run
    saved_corners = dynamics.divider_corners
    try:
        dynamics.divider_corners = lambda: [("hi", 4.2)]
        rc = dynamics.main([])
    finally:
        dynamics.divider_corners = saved_corners
    check("T5 a poisoned corner turns main() red", rc == 1, f"rc={rc}")

    # T6 — missing simulator is rc 2, never a pass
    saved_which = transients.shutil.which
    try:
        transients.shutil.which = lambda _name: None
        rc = dynamics.main([])
    finally:
        transients.shutil.which = saved_which
    check("T6 missing ngspice is rc 2, not a pass", rc == 2, f"rc={rc}")

    # T7 — registration: run by the suite, owned by an agent, on the bench
    gates = gates_from_makefile()
    check("T7a test_vbench_dynamics in VERIFY_ALL_SCRIPTS",
          "test_vbench_dynamics" in gates)
    rt = route("test_vbench_dynamics")
    check("T7b dispatch routes test_vbench_dynamics",
          rt is not None and rt["severity"] == "blind-spot",
          f"routed {rt}")
    mk = (BASE / "Makefile").read_text()
    check("T7c make bench-dynamics exists",
          re.search(r"^bench-dynamics:", mk, re.M) is not None)

    # T8 — the RC in the deck is the board's own R3/C31
    r_ref, r_val, c_ref, c_val = dynamics.find_en_rc()
    check("T8 EN RC is R3=10k / C31=100nF from netlist+BOM",
          (r_ref, c_ref) == ("R3", "C31")
          and abs(r_val - 10e3) < 1 and abs(c_val - 100e-9) < 1e-12,
          f"{r_ref}={r_val}, {c_ref}={c_val}")

    print("=" * 72)
    if failures:
        print(f"FAIL — {len(failures)} test(s): {', '.join(failures)}")
        return 1
    print("PASS — the dynamic scenarios can fail, and do so for the right "
          "reasons")
    return 0


if __name__ == "__main__":
    sys.exit(main())
