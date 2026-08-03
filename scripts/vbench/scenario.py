"""Virtual Bench T4.3 — scenarios with assertions, headless, for CI.

Everything the earlier phases compute is a number or a state. This runner
turns those into **named scenarios with pass/fail assertions**, so the bench
stops being a set of reports somebody has to read and becomes a thing that
says yes or no.

A scenario declares a setup (which source, what state of charge, which
buttons are held, what ambient) and a list of assertions against *derived*
quantities. The quantity names are deliberately not free text — each maps to
something a Phase 1-3 module computes, and an unknown name is a hard error
rather than a silently-skipped assertion. An assertion nobody evaluates is
the same failure as a gate nobody runs.

Output is a text log plus JUnit XML, so CI can consume it.

Usage:
    python3 scripts/vbench/scenario.py
    python3 scripts/vbench/scenario.py --junit /tmp/vbench.xml
    python3 scripts/vbench/scenario.py --only usb_cold_boot
"""

import argparse
import collections
import glob
import json
import os
import sys
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import audio, buttons, display, rails, sdcard, thermal  # noqa: E402
from vbench import pins as pinmod                                   # noqa: E402
from vbench.models.u1_esp32s3 import boot_mode, vdd_spi_voltage     # noqa: E402

SCEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")

Result = collections.namedtuple("Result", "scenario name ok detail")


class ScenarioError(RuntimeError):
    """The scenario itself is malformed, or asks for something unknown."""


# ── Quantities a scenario may assert on ─────────────────────────────
#
# Each entry is a function of the evaluated setup. Adding a scenario that
# names something absent from this table fails loudly: a typo in an
# assertion must not become an assertion that never runs.

def _quantities(setup):
    """Evaluate the bench under `setup` and return every assertable value."""
    on_battery = setup.get("source", "usb") == "battery"
    soc = float(setup.get("soc", 0.5))
    held = tuple(setup.get("hold", ()))
    pressed = bool(setup.get("buttons_pressed", False))
    ambient = float(setup.get("ambient_c", thermal.GOVERNING_AMBIENT))

    op = rails.operating_point(on_battery=on_battery, soc=soc,
                               buttons_pressed=pressed)
    q = {}
    for net, volts in op.voltages.items():
        q[f"net.{net}"] = volts               # None means floating
    for net, (lo, typ, hi) in op.rail_spread.items():
        q[f"rail.{net}.min"] = lo
        q[f"rail.{net}.typ"] = typ
        q[f"rail.{net}.max"] = hi
    q["rails.violations"] = len(op.violations)
    q["source.calibrated"] = op.source.calibrated
    q["source.v_open"] = op.source.v_open

    fabric, _op2, _v = pinmod.fabric(hold_nets=held)
    state = pinmod.strapping_state(fabric)
    q["boot.mode"] = boot_mode(state["GPIO0"][0], state["GPIO46"][0])[0]
    q["boot.vdd_spi"] = vdd_spi_voltage(state["GPIO45"][0])[0]
    for gpio, (level, _why) in state.items():
        q[f"strap.{gpio}"] = level

    survey = buttons.survey()
    with_rc = [b for b in survey if b.tau_s]
    q["buttons.with_rc"] = len(with_rc)
    q["buttons.slowest_release_s"] = (
        max((b.t_rise_s for b in with_rc), default=None))
    # SW16 respin: the switch does something now, so the quantities are
    # about what it does. The gate V_gs is the measurable — the DC solve
    # has no MOSFET model, so the load rail itself would be an invented
    # answer, while the gate network is resistors and the switch and is
    # solved exactly.
    ok_sw, sw = buttons.switch_scenario()
    q["switch.ok"] = ok_sw
    q["switch.throws_routed"] = len(sw["routed_throws"])
    q["switch.common_net"] = sw["common_net"]
    q["switch.vgs_on"] = sw["vgs_on"]
    q["switch.vgs_off"] = sw["vgs_off"]
    # The cell path must not run through the switch: OFF has to leave the
    # IP5306 charging.
    q["switch.bat_unchanged"] = (sw["bat_before"] == sw["bat_after"])

    view, _rail = display.panel_view()
    ok_mode, mode, _detail = display.check_interface_mode(view)
    q["display.interface_mode"] = mode
    q["display.data_bus_faults"] = len(display.check_data_bus(view))
    q["display.unused_pin_faults"] = len(display.check_unused_pins(view))

    v5 = op.voltages.get("+5V")
    if v5 is not None:
        p_full = audio.output_power(v5)
        q["audio.p_out_max_w"] = p_full
        level = float(setup.get("audio_level", 0.0))
        p_out = p_full * max(0.0, level) ** 2
        q["audio.p_out_w"] = p_out
        q["audio.rail_current_a"] = audio.supply_current(p_out, v5)
    q["audio.hp_corner_hz"] = audio.input_network()[2]

    _notes, _shared, exposure, _op3, faults = sdcard.survey()
    q["sd.bus_faults"] = len(faults)
    q["sd.strapping_exposure"] = len(exposure)

    hot = []
    for sc in thermal.SCENARIOS:
        for r in thermal.evaluate(sc, ambient):
            if r.ok is False:
                hot.append(f"{r.ref}/{sc.name}")
    q["thermal.over_margin"] = len(hot)
    q["thermal.ambient_c"] = ambient
    return q


_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
    "between": lambda a, b: a is not None and b[0] <= a <= b[1],
    "is_floating": lambda a, b: (a is None) == bool(b),
}


def run_scenario(doc):
    """Evaluate one scenario's assertions. Returns a list of Result."""
    name = doc["name"]
    quantities = _quantities(doc.get("setup", {}))
    out = []
    for a in doc["assert"]:
        want_q = a["quantity"]
        if want_q not in quantities:
            raise ScenarioError(
                f"{name}: assertion names {want_q!r}, which the bench does "
                f"not compute. Known quantities include "
                f"{sorted(k for k in quantities if k.startswith(want_q.split('.')[0]))[:6]}. "
                f"An assertion nobody evaluates is the same failure as a gate "
                f"nobody runs.")
        op = a["op"]
        if op not in _OPS:
            raise ScenarioError(f"{name}: unknown operator {op!r}")
        got = quantities[want_q]
        ok = _OPS[op](got, a.get("value"))
        detail = f"{want_q} = {got!r} {op} {a.get('value')!r}"
        if a.get("because"):
            detail += f"  — {a['because']}"
        out.append(Result(name, a.get("name", want_q), bool(ok), detail))
    return out


def load_scenarios(only=None):
    files = sorted(glob.glob(os.path.join(SCEN_DIR, "*.json")))
    if not files:
        raise ScenarioError(f"no scenarios in {SCEN_DIR}")
    docs = []
    for path in files:
        with open(path) as fh:
            doc = json.load(fh)
        for key in ("name", "description", "setup", "assert"):
            if key not in doc:
                raise ScenarioError(
                    f"{os.path.basename(path)}: missing {key!r}")
        if not doc["assert"]:
            raise ScenarioError(
                f"{doc['name']}: no assertions. A scenario that asserts "
                f"nothing passes always and measures nothing.")
        if only and doc["name"] != only:
            continue
        docs.append(doc)
    if only and not docs:
        raise ScenarioError(f"no scenario named {only!r}")
    return docs


def junit(results, path):
    suites = ET.Element("testsuites")
    by_scenario = collections.defaultdict(list)
    for r in results:
        by_scenario[r.scenario].append(r)
    for scenario, rs in by_scenario.items():
        suite = ET.SubElement(
            suites, "testsuite", name=f"vbench.{scenario}",
            tests=str(len(rs)),
            failures=str(sum(1 for r in rs if not r.ok)))
        for r in rs:
            case = ET.SubElement(suite, "testcase",
                                 classname=f"vbench.{scenario}", name=r.name)
            if not r.ok:
                fail = ET.SubElement(case, "failure", message=r.detail)
                fail.text = r.detail
    ET.ElementTree(suites).write(path, encoding="utf-8",
                                 xml_declaration=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="run one scenario by name")
    ap.add_argument("--junit", help="write JUnit XML here")
    args = ap.parse_args(argv)

    try:
        docs = load_scenarios(args.only)
        results = []
        print("=" * 72)
        print("  Virtual Bench T4.3 — scenarios")
        print("=" * 72)
        for doc in docs:
            rs = run_scenario(doc)
            results.extend(rs)
            failed = [r for r in rs if not r.ok]
            mark = "OK  " if not failed else "FAIL"
            print(f"\n  [{mark}] {doc['name']} — {doc['description']}")
            for r in rs:
                print(f"      {'pass' if r.ok else 'FAIL'}  {r.name}")
                print(f"            {r.detail}")
    except (ScenarioError, rails.RailError) as exc:
        print(f"  ERROR  {exc}", file=sys.stderr)
        return 2

    if args.junit:
        junit(results, args.junit)
        print(f"\n  JUnit written: {args.junit}")

    failed = [r for r in results if not r.ok]
    print()
    print("=" * 72)
    print(f"  {len(results) - len(failed)} passed, {len(failed)} failed, "
          f"across {len(docs)} scenario(s)")
    print(f"  Calibration: {rails.sources.CALIBRATION} — every number above "
          f"is self-consistent")
    print(f"  and uncalibrated until prototype #1 measurements land (T5.4).")
    print("=" * 72)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
