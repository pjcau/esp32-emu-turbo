"""Mutation tests for the Virtual Bench (Phase 0 foundation, Phase 1 physics).

Written in the style of `scripts/test_issue_dispatch.py`: break each
mechanism on purpose and require it to notice. The repo's own lesson is
that an assertion which never fires is not evidence — the schema check that
matters is the one that rejects a plausible model, and the corpus check
that matters is the one that rejects a plausible citation.

Covers:
  A. models/_schema.py — an uncited, weaselly or unlocatable number must
     not validate, and a part whose datasheet is not in the repo must not
     model at all.
  B. corpus.py         — a corpus that hand-writes its own verdict, cites a
     line that moved, or reuses an id must fail to load.
  C. netlist.py        — each dispute class must fire when its condition is
     injected, and must not fire otherwise.
  D. rails.py, conflicts.py — the rails must be DERIVED (the divider found by
     walking the netlist, +3V3 at 3.327 V not 3.300), a floating node must
     stay floating rather than default to 0 V, and the conflict detector must
     fire on an injected driver and fall silent when it is removed.
  E. thermal.py, models Q1/U5 — an on-resistance must come from a table row
     rather than an interpolation, a dissipation that cannot be derived must
     stay unreported, and the margin check must actually fire at a hot
     ambient.
  F. transients.py — a current limit must not be used as a series resistance,
     the decks must carry the BOM's real values, the simulated ripple must
     agree with the closed form, and a missing simulator must raise.

Usage:
    python3 scripts/test_vbench.py
"""

import json
import os
import shutil
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import corpus                                    # noqa: E402
from vbench import netlist as nl                              # noqa: E402
from vbench.models._schema import (                           # noqa: E402
    DatasheetRef, Model, ModelSchemaError, Param, Pin, validate_model)

PASS = FAIL = 0

# A real datasheet in this repo, so the "document exists" rule is satisfied
# by a document that genuinely exists and the other rules are what is being
# tested.
REAL_DOC = "U2_IP5306_C181692.pdf"


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def rejects(name, build):
    """The schema must reject `build()`. Passing is a failure."""
    try:
        validate_model(build())
    except ModelSchemaError:
        check(name, True)
        return
    except Exception as exc:                            # noqa: BLE001
        check(name, False, f"raised {type(exc).__name__} instead: {exc}")
        return
    check(name, False, "validated when it should have been rejected")


def good_model(**over):
    kw = dict(
        ref="U2", part="IP5306", mpn="C181692",
        datasheet=DatasheetRef(doc=REAL_DOC, rev="v1.4"),
        pins=(Pin("1", "VOUT", "power_out", "p.3 table 1"),
              Pin("2", "GND", "gnd", "p.3 table 1")),
        params={"v_out": Param(5.0, "V", locator="p.5 table 3")},
    )
    kw.update(over)
    return Model(**kw)


# ── A. Model schema ─────────────────────────────────────────────────

def test_schema():
    print("\nA. models/_schema.py")
    try:
        validate_model(good_model())
        check("a well-cited model validates", True)
    except ModelSchemaError as exc:
        check("a well-cited model validates", False, str(exc))

    rejects("a parameter with no citation and no derivation is rejected",
            lambda: good_model(params={"v_out": Param(5.0, "V")}))

    rejects("'see datasheet' is not a citation",
            lambda: good_model(
                params={"v_out": Param(5.0, "V", locator="see datasheet")}))

    rejects("'assumed typical' is not a citation",
            lambda: good_model(
                params={"v_out": Param(5.0, "V",
                                       locator="assumed typical value")}))

    rejects("a locator that points nowhere is rejected",
            lambda: good_model(
                params={"v_out": Param(5.0, "V",
                                       locator="near the beginning")}))

    rejects("a document that is not in hardware/datasheets/ is rejected",
            lambda: good_model(datasheet=DatasheetRef(
                doc="ILI9488_panel_that_nobody_added.pdf", rev="v1.0")))

    rejects("an empty datasheet revision is rejected",
            lambda: good_model(datasheet=DatasheetRef(doc=REAL_DOC, rev="")))

    rejects("a value that is both cited and derived is rejected",
            lambda: good_model(params={
                "i": Param(1.0, "A", locator="p.5 table 3",
                           derived_from=("v_out",), formula="v/r")}))

    rejects("a derived value with no formula is rejected",
            lambda: good_model(params={
                "v_out": Param(5.0, "V", locator="p.5 table 3"),
                "i": Param(1.0, "A", derived_from=("v_out",))}))

    rejects("a derived value naming an unknown parameter is rejected",
            lambda: good_model(params={
                "v_out": Param(5.0, "V", locator="p.5 table 3"),
                "i": Param(1.0, "A", derived_from=("r_load",),
                           formula="v/r")}))

    rejects("a pin with no locator is rejected",
            lambda: good_model(pins=(Pin("1", "VOUT", "power_out"),)))

    rejects("an invented pin direction is rejected",
            lambda: good_model(
                pins=(Pin("1", "VOUT", "powerish", "p.3 table 1"),)))

    rejects("a duplicate pin number is rejected",
            lambda: good_model(pins=(
                Pin("1", "VOUT", "power_out", "p.3 table 1"),
                Pin("1", "GND", "gnd", "p.3 table 1"))))

    rejects("a model with no pins is rejected",
            lambda: good_model(pins=()))

    rejects("a model with no parameters is rejected",
            lambda: good_model(params={}))

    # The structural consequence of R25-HIGH-1: the display panel has no
    # datasheet in this repo, so no panel model can validate until one is
    # added. If this test ever fails, someone has weakened rule 2 — or the
    # panel datasheet finally arrived, in which case delete the test.
    panel_docs = [f for f in os.listdir(
        os.path.join(BASE, "hardware", "datasheets"))
        if "ILI9488" in f or "panel" in f.lower()]
    check("the display panel still has no datasheet, so it cannot be "
          "modelled (R25-HIGH-1)", not panel_docs,
          f"found {panel_docs} — update this test and model the panel")

    # A derived parameter is the honest escape hatch, so it must work.
    try:
        validate_model(good_model(params={
            "v_out": Param(5.0, "V", locator="p.5 table 3"),
            "i_load": Param(0.5, "A", derived_from=("v_out",),
                            formula="v_out / r_load, r_load from the "
                                    "measured rail current")}))
        check("a declared-derived parameter validates without a citation",
              True)
    except ModelSchemaError as exc:
        check("a declared-derived parameter validates without a citation",
              False, str(exc))


# ── B. Corpus ───────────────────────────────────────────────────────

def _with_mutated_corpus(mutate):
    """Copy the corpus to a temp dir, mutate it, and try to load it."""
    tmp = tempfile.mkdtemp(prefix="vbench-corpus-")
    shutil.copytree(corpus.RETRO_DIR, os.path.join(tmp, "retro"))
    mutate(os.path.join(tmp, "retro"))
    original = corpus.RETRO_DIR
    corpus.RETRO_DIR = os.path.join(tmp, "retro")
    try:
        corpus.load_corpus()
        return None
    except corpus.CorpusError as exc:
        return str(exc)
    finally:
        corpus.RETRO_DIR = original
        shutil.rmtree(tmp, ignore_errors=True)


def _edit(path, fn):
    with open(path) as fh:
        doc = json.load(fh)
    fn(doc)
    with open(path, "w") as fh:
        json.dump(doc, fh)


def test_corpus():
    print("\nB. corpus.py")
    try:
        entries = corpus.load_corpus()
        check("the shipped corpus loads and every citation resolves",
              len(entries) > 0, "corpus is empty")
    except corpus.CorpusError as exc:
        check("the shipped corpus loads and every citation resolves",
              False, str(exc))
        entries = []

    check("no entry carries a hand-written verdict",
          all(not hasattr(e, "status") for e in entries))

    def add_status(d):
        _edit(os.path.join(d, "invariants.json"),
              lambda doc: doc["entries"][0].update({"status": "caught"}))
    check("a hand-written 'status' is refused",
          _with_mutated_corpus(add_status) is not None)

    def break_line(d):
        _edit(os.path.join(d, "invariants.json"),
              lambda doc: doc["entries"][0].update({"source":
                                                    "docs/known-issues.md:1"}))
    err = _with_mutated_corpus(break_line)
    check("a citation pointing at the wrong line is caught, with the right "
          "line named", err is not None and "it is now at line" in err,
          f"got: {err}")

    def fabricate(d):
        _edit(os.path.join(d, "invariants.json"),
              lambda doc: doc["entries"][0].update(
                  {"source_match": "a sentence nobody ever wrote"}))
    err = _with_mutated_corpus(fabricate)
    check("a citation whose text is nowhere in the file is caught",
          err is not None and "not in" in err, f"got: {err}")

    def dup_id(d):
        _edit(os.path.join(d, "invariants.json"),
              lambda doc: doc["entries"].append(dict(doc["entries"][0])))
    check("a duplicate entry id is caught",
          _with_mutated_corpus(dup_id) is not None)

    def none_without_present(d):
        _edit(os.path.join(d, "invariants.json"),
              lambda doc: doc["entries"][0].pop("present_now"))
    check("mutation kind 'none' without present_now is caught",
          _with_mutated_corpus(none_without_present) is not None)

    def bad_kind(d):
        _edit(os.path.join(d, "invariants.json"),
              lambda doc: doc["entries"][0].update(
                  {"mutation": {"kind": "sabotage"}}))
    check("an unknown mutation kind is caught",
          _with_mutated_corpus(bad_kind) is not None)

    def empty_dir(d):
        for f in os.listdir(d):
            os.remove(os.path.join(d, f))
    check("an empty corpus is caught rather than passing vacuously",
          _with_mutated_corpus(empty_dir) is not None)

    # Phase 0 must report zero caught. A future phase changing this is
    # expected; a future phase changing it *without* writing detectors is
    # what this guards.
    caught = [ok for _, ok, _ in corpus.evaluate(entries) if ok]
    check("Phase 0 claims no coverage", len(caught) == 0,
          f"{len(caught)} entries claim to be caught with no detector")


# ── C. Netlist and disputes ─────────────────────────────────────────

def test_netlist():
    print("\nC. netlist.py")
    board = nl.load_board_netlist()
    sch = nl.load_schematic_netlist()

    check("every net in the extracted netlist has at least one pin",
          all(len(p) >= 1 for p in board.nets.values()))
    check("the board netlist is not trivially small",
          len(board.nets) > 40 and sum(len(v) for v in board.nets.values()) > 200,
          f"{len(board.nets)} nets")

    base = nl.crosscheck(board, sch)
    base_codes = {d.code for d in base}

    # D4 must fire on an injected disagreement, and must name the pin.
    victim = ("U1", "3")
    if victim in sch.pin_nets:
        pin_nets = dict(sch.pin_nets)
        pin_nets[victim] = "GND"
        mutated = nl.SchematicNetlist(sch.nets, sch.refs, pin_nets)
        after = nl.crosscheck(board, mutated)
        d4 = [d for d in after if d.code == "D4" and d.subject.startswith("U1.3")]
        check("D4 fires when a schematic pin is moved to the wrong net",
              len(d4) == 1, f"got {[d.subject for d in after if d.code == 'D4']}")
    else:
        check("D4 fires when a schematic pin is moved to the wrong net",
              False, "U1.3 absent from the schematic netlist — test is stale")

    # D1 must fire on a declared net that no pad carries.
    board.declared_nets.add("PHANTOM_RAIL")
    after = nl.crosscheck(board, sch)
    check("D1 fires on a declared net with no pad",
          any(d.code == "D1" and d.subject == "PHANTOM_RAIL" for d in after))
    board.declared_nets.discard("PHANTOM_RAIL")

    # D2 must fire on a net reduced to one pin, and the reduction must be
    # the only reason it fires.
    two_pin = next((n for n, p in board.nets.items() if len(p) == 2), None)
    if two_pin:
        saved = board.nets[two_pin]
        board.nets[two_pin] = (saved[0],)
        after = nl.crosscheck(board, sch)
        check("D2 fires when a net is reduced to a single pin",
              any(d.code == "D2" and d.subject == two_pin and d.side == "pcb"
                  for d in after))
        board.nets[two_pin] = saved
    else:
        check("D2 fires when a net is reduced to a single pin", False,
              "no two-pin net to reduce")

    # And the baseline must be reproduced exactly after undoing the
    # mutations: a detector with state leaks would pass every test above
    # and still be useless.
    restored = nl.crosscheck(board, sch)
    check("undoing every mutation restores the baseline verdict",
          [d[:5] for d in restored] == [d[:5] for d in base],
          f"{len(restored)} disputes vs {len(base)} before")

    # D3 must fire only for a pad that NEITHER source accounts for, so the
    # injection removes the datasheet_specs entry that currently explains
    # one. Without this the class would be untested: it is empty on the
    # real board, and an empty class proves nothing on its own.
    if board.pads_without_pin:
        ref, pad, _ = board.pads_without_pin[0]
        pins = nl.COMPONENT_SPECS[ref]["pins"]
        saved = pins.pop(pad)
        try:
            after = nl.crosscheck(board, sch)
            check("D3 fires for a pad in neither the schematic nor "
                  "datasheet_specs",
                  any(d.code == "D3" and d.subject == f"{ref} pad {pad}"
                      for d in after),
                  f"injected {ref}.{pad}, got "
                  f"{[d.subject for d in after if d.code == 'D3']}")
        finally:
            pins[pad] = saved
        after = nl.crosscheck(board, sch)
        check("D3 falls silent again once datasheet_specs explains the pad",
              not any(d.code == "D3" for d in after),
              f"still {[d.subject for d in after if d.code == 'D3']}")
    else:
        check("D3 fires for a pad in neither source", False,
              "no pad without a schematic pin — test is stale")

    check("the baseline reports the classes Phase 0 is meant to expose",
          {"D2", "D5"} <= base_codes,
          f"got {sorted(base_codes)}")
    check("every pad the schematic omits is explained by datasheet_specs",
          all(pad in nl.COMPONENT_SPECS.get(ref, {}).get("pins", {})
              for ref, pad, _ in board.pads_without_pin),
          "a pad is accounted for by neither source")

    # An ambiguous translation table must raise rather than pick a winner.
    saved_map = nl.vnd.SCH_PIN_TO_PCB_PADS.get("LED1")
    nl.vnd.SCH_PIN_TO_PCB_PADS["LED1"] = {"1": ("2",), "2": ("2",)}
    try:
        nl._pad_to_sch_pin("LED1")
        check("an ambiguous pin/pad map raises instead of guessing", False,
              "returned a mapping")
    except nl.NetlistError:
        check("an ambiguous pin/pad map raises instead of guessing", True)
    finally:
        nl.vnd.SCH_PIN_TO_PCB_PADS["LED1"] = saved_map

    # A revision that does not exist must be an error, never a fallback.
    try:
        nl.load_board_netlist("definitely-not-a-tag")
        check("a missing git revision raises instead of falling back to HEAD",
              False, "returned a netlist")
    except nl.NetlistError:
        check("a missing git revision raises instead of falling back to HEAD",
              True)


# ── D. Phase 1: models, rails, conflicts ────────────────────────────

def test_phase1():
    print("\nD. rails.py / conflicts.py / the cited models")
    from vbench import conflicts, rails, sources
    from vbench.models.u2_ip5306 import U2
    from vbench.models.u3_sy8089 import U3, v_out, v_out_spread

    for model in (U2, U3):
        try:
            validate_model(model)
            check(f"{model.ref} ({model.part}) satisfies the citation schema",
                  True)
        except ModelSchemaError as exc:
            check(f"{model.ref} ({model.part}) satisfies the citation schema",
                  False, str(exc))

    # T1.2's done-when: each model reproduces its datasheet's own worked
    # example. Figure 1 on page 1 draws R1=200k, R2=100k and labels the
    # output 1.8 V.
    check("SY8089 reproduces its datasheet's worked example (200k/100k -> "
          "1.8 V)", abs(v_out(200e3, 100e3) - 1.8) < 1e-9,
          f"got {v_out(200e3, 100e3)}")

    board = nl.load_board_netlist()
    values = rails.load_bom_values()
    div = rails.find_feedback_divider(board, values)
    check("the feedback divider is found by walking the netlist, not named",
          (div.r_top, div.r_bottom) == ("R25", "R26")
          and div.out_net == "+3V3" and div.fb_net == "BUCK_FB",
          f"got {div}")
    check("the divider's resistor values come from the BOM",
          (div.r_top_ohm, div.r_bottom_ohm) == (100e3, 22e3),
          f"got {div.r_top_ohm}, {div.r_bottom_ohm}")

    lo, typ, hi = v_out_spread(div.r_top_ohm, div.r_bottom_ohm)
    check("+3V3 is 3.327 V, not 3.300 — derived from the real divider",
          abs(typ - 3.3273) < 1e-3, f"got {typ}")
    check("the +3V3 spread comes from V_REF's own tolerance",
          abs(lo - 3.2607) < 1e-3 and abs(hi - 3.3939) < 1e-3,
          f"got {lo}..{hi}")

    op = rails.operating_point()
    # An independent consistency check: the solver knows nothing about
    # V_REF, it only sees two resistors between +3V3 and GND. If FB does not
    # land on 0.600 V then the divider was mis-identified.
    check("the solver puts FB at V_REF without being told (0.600 V)",
          op.voltages["BUCK_FB"] is not None
          and abs(op.voltages["BUCK_FB"] - 0.600) < 1e-3,
          f"got {op.voltages['BUCK_FB']}")

    # R25-CRIT-1, reached from the physics rather than from a comment.
    check("EN has no defined DC level (R25-CRIT-1, no pull-up, no RC)",
          op.voltages.get("EN", "missing") is rails.UNDEFINED,
          f"got {op.voltages.get('EN')}")
    # R14 is DNP, so BTN_L has no external pull-up either.
    check("BTN_L has no defined DC level (R14 is DNP)",
          op.voltages.get("BTN_L", "missing") is rails.UNDEFINED,
          f"got {op.voltages.get('BTN_L')}")
    check("an idle button sits at the +3V3 rail through its pull-up",
          op.voltages["BTN_A"] is not None
          and abs(op.voltages["BTN_A"] - 3.3273) < 1e-3,
          f"got {op.voltages['BTN_A']}")

    pressed = rails.operating_point(buttons_pressed=True)
    check("a pressed button is pulled to 0 V",
          abs(pressed.voltages["BTN_A"]) < 1e-9,
          f"got {pressed.voltages['BTN_A']}")
    # The regression that mattered: SW_PWR's shell tabs carry BTN_SELECT, so
    # closing "every net the switch touches" welded BAT+ to the buttons and
    # put 3.83 V on all of them.
    check("closing the switches does NOT weld BAT+ to BTN_SELECT via "
          "SW_PWR's shell tabs",
          abs(pressed.voltages["BAT+"] - op.voltages["BAT+"]) < 1e-9
          and abs(pressed.voltages["BTN_SELECT"]) < 1e-9,
          f"BAT+={pressed.voltages['BAT+']}, "
          f"BTN_SELECT={pressed.voltages['BTN_SELECT']}")

    # The battery scenario must leave VBUS floating, not at 0 V.
    batt = rails.operating_point(on_battery=True, soc=0.05)
    check("on battery, VBUS is floating rather than 0 V",
          batt.voltages.get("VBUS", "missing") is rails.UNDEFINED)
    check("a low cell drops BAT+ to its OCV, not to a default",
          abs(batt.voltages["BAT+"] - sources.lipo_ocv(0.05)) < 1e-9)
    check("the LiPo model reports itself uncalibrated",
          sources.lipo(0.5).calibrated is False
          and sources.CALIBRATION == "no")

    # A divider resistor with no BOM value must be fatal, not defaulted.
    try:
        rails.find_feedback_divider(board, {k: v for k, v in values.items()
                                            if k != "R26"})
        check("a divider resistor missing from the BOM is fatal", False,
              "returned a divider")
    except rails.RailError:
        check("a divider resistor missing from the BOM is fatal", True)

    # T1.3 must fire on an injected conflict and fall silent afterwards.
    base = conflicts.find_conflicts(board, values)
    check("no electrical conflict on the board as it stands",
          not base, f"got {[c.code + ':' + c.net for c in base]}")

    from vbench.models._schema import Pin
    saved = U3.pins
    try:
        # Declare U3's IN pin an output: now two power outputs (U2.VOUT and
        # U3.IN) hold +5V.
        object.__setattr__(U3, "pins", tuple(
            Pin(p.number, p.name, "power_out", p.locator) if p.number == "4"
            else p for p in saved))
        after = conflicts.find_conflicts(board, values)
        check("C1/C2 fires when a second driver is declared on the +5V rail",
              any(c.net == "+5V" for c in after),
              f"got {[c.code + ':' + c.net for c in after]}")
    finally:
        object.__setattr__(U3, "pins", saved)
    check("the conflict detector falls silent once the injection is undone",
          conflicts.find_conflicts(board, values) == base)


# ── E. Phase 1.5: thermal, and the models it rests on ───────────────

def test_thermal():
    print("\nE. thermal.py / Q1 and U5 models")
    from vbench import thermal
    from vbench.models.q1_si2301 import Q1, r_ds_on
    from vbench.models.u5_pam8403 import U5

    for model in (Q1, U5):
        try:
            validate_model(model)
            check(f"{model.ref} ({model.part}) satisfies the citation schema",
                  True)
        except ModelSchemaError as exc:
            check(f"{model.ref} ({model.part}) satisfies the citation schema",
                  False, str(exc))

    # Q1's on-resistance must come from a table row, never from interpolation
    # between two rows.
    check("Q1 uses the -4.5 V row only when the gate drive reaches it",
          r_ds_on(-4.5) == 0.112 and r_ds_on(-5.0) == 0.112,
          f"got {r_ds_on(-4.5)}, {r_ds_on(-5.0)}")
    check("Q1 falls back to the conservative -2.5 V row in between",
          r_ds_on(-3.83) == 0.142, f"got {r_ds_on(-3.83)}")
    try:
        r_ds_on(-0.5)
        check("Q1 refuses an on-resistance below its threshold", False,
              "returned a value")
    except ValueError:
        check("Q1 refuses an on-resistance below its threshold", True)
    try:
        r_ds_on(3.3)
        check("Q1 rejects a positive V_GS on a P-channel part", False,
              "returned a value")
    except ValueError:
        check("Q1 rejects a positive V_GS on a P-channel part", True)

    # The steady-state figure, not the <=5 s one. A handheld is steady state.
    check("Q1's thermal figure is the steady-state 175 degC/W, not 120/145",
          Q1.params["theta_ja_steady_state"].value == 175.0
          and Q1.params["theta_ja_5s"].value == (0.0, 120.0, 145.0))

    # The duty cycle must come from the derived rail, not from 3.3/5.
    d, v_out, v_in = thermal.duty_cycle()
    check("the buck duty cycle uses the DERIVED 3.327 V, not a nominal 3.3",
          abs(v_out - 3.3273) < 1e-3 and abs(d - 0.6655) < 1e-3,
          f"got Vout={v_out}, D={d}")

    # U2 must be reported as not computable, never filled in.
    results = {r.ref: r for r in thermal.evaluate(thermal.SCENARIOS[1], 40.0)}
    check("U2's dissipation is reported NOT COMPUTABLE, not assumed",
          results["U2"].p_watts is None
          and "NOT COMPUTABLE" in results["U2"].basis)
    check("U5 gets a power figure but no Tj, because theta_JA is uncited",
          results["U5"].p_watts is not None and results["U5"].tj is None)
    check("U3's figure is labelled a lower bound (no switching loss)",
          "LOWER BOUND" in results["U3"].basis)
    check("U3 and Q1 do get a junction temperature",
          results["U3"].tj is not None and results["Q1"].tj is not None)

    # Charge-and-play must not put battery current through Q1.
    cap = {r.ref: r for r in thermal.evaluate(thermal.SCENARIOS[2], 40.0)}
    check("in charge-and-play Q1 carries no battery current",
          cap["Q1"].p_watts == 0.0, f"got {cap['Q1'].p_watts}")

    # Both ambients must be present, and 40 must govern.
    check("30 degC external and 40 degC in-enclosure are both defined, and "
          "40 governs",
          thermal.AMBIENT_EXTERNAL == 30.0
          and thermal.AMBIENT_IN_ENCLOSURE == 40.0
          and thermal.GOVERNING_AMBIENT == 40.0)

    # A hot ambient must actually fail, or the margin check proves nothing.
    hot = thermal.evaluate(thermal.SCENARIOS[1], 200.0)
    check("an absurd ambient drives the margin check to FAIL",
          any(r.ok is False for r in hot),
          "nothing failed at 200 degC — the margin check never fires")

    # The existing gate's ambient must be overridable and default to 40.
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    import importlib
    saved = os.environ.pop("VBENCH_AMBIENT_C", None)
    try:
        vtb = importlib.import_module("verify_thermal_budget")
        importlib.reload(vtb)
        check("verify_thermal_budget still defaults to 40 degC",
              vtb.T_AMBIENT == 40.0, f"got {vtb.T_AMBIENT}")
        os.environ["VBENCH_AMBIENT_C"] = "55"
        importlib.reload(vtb)
        check("verify_thermal_budget's ambient is overridable (T1.5)",
              vtb.T_AMBIENT == 55.0, f"got {vtb.T_AMBIENT}")
    finally:
        os.environ.pop("VBENCH_AMBIENT_C", None)
        if saved is not None:
            os.environ["VBENCH_AMBIENT_C"] = saved


# ── F. Phase 1.4: transients ────────────────────────────────────────

def test_transients():
    print("\nF. transients.py")
    from vbench import transients as tr

    # The regression that mattered twice: a current limit is not a series
    # resistance. v_out/i_limit is 0.95 ohm and invented a 0.36-0.50 V droop
    # in two different decks, once making +3V3 look like it browned out.
    r = tr.r_conduction()
    check("the decks' series resistance is the cited conduction resistance",
          abs(r - 0.100) < 0.005, f"got {r}")
    check("it is NOT v_out/i_limit, the invented 0.95 ohm",
          abs(r - 3.327 / 3.5) > 0.5, f"got {r}")

    # A current-limited supply charges a bulk capacitance in C*V/I.
    t = tr.cap_charge_time(57e-6, 5.0, 3.0)
    check("bulk charge time is C*V/I (57 uF, 5 V, 3 A -> 95 us)",
          abs(t - 95e-6) < 1e-6, f"got {t}")

    caps, l_buck = tr.board_values()
    c_3v3, absent = caps["+3V3"]
    check("the +3V3 bulk is read from the BOM (22.3 uF), not the schematic",
          abs(c_3v3 - 22.3e-6) < 0.1e-6, f"got {c_3v3}")
    check("C28 is excluded because it is DNP and has no BOM value",
          "C28" in absent, f"absent = {absent}")
    check("the buck inductor comes from the BOM (2.2 uH)",
          abs(l_buck - 2.2e-6) < 1e-9, f"got {l_buck}")

    from vbench.thermal import duty_cycle
    duty, v_out, v_in = duty_cycle()
    dv, di = tr.ripple_closed_form(c_3v3, l_buck, duty, v_in, v_out)
    check("the closed-form ripple is about 2.8 mV pk-pk",
          2.0e-3 < dv < 4.0e-3, f"got {dv}")

    # The decks must carry the real values, not round numbers.
    # Parse the deck rather than string-matching it: what matters is that the
    # numbers in the netlist ARE the BOM's and the datasheet's, whatever
    # formatting %g chooses for them.
    deck = tr.deck_ripple(c_3v3, l_buck, duty, v_in, 0.430)
    import re as _re
    def _val(pattern):
        m = _re.search(pattern, deck)
        return float(m.group(1)) if m else None
    deck_l = _val(r"(?m)^L2 \S+ \S+ (\S+)")
    deck_c = _val(r"(?m)^Cout \S+ \S+ (\S+)")
    deck_period = _val(r"PULSE\([^)]*\s(\S+)\)")
    check("the ripple deck carries the BOM's inductor value",
          deck_l is not None and abs(deck_l - l_buck) < 1e-12,
          f"deck L2 = {deck_l}, BOM = {l_buck}")
    check("the ripple deck carries the BOM's output capacitance",
          deck_c is not None and abs(deck_c - c_3v3) < 1e-12,
          f"deck Cout = {deck_c}, BOM = {c_3v3}")
    check("the ripple deck switches at the cited 1 MHz, not a round guess",
          deck_period is not None and abs(deck_period - 1e-6) < 1e-15,
          f"deck period = {deck_period}")

    if shutil.which("ngspice") is None:
        # Not a skip. A transient gate whose simulator is missing has no
        # verdict to give, and saying nothing would read as a pass.
        check("ngspice is installed (required, not optional)", False,
              "install with `brew install ngspice` — transients.py exits 2 "
              "without it and this suite will not pretend otherwise")
        return

    check("ngspice is installed (required, not optional)", True)

    import tempfile as _tf
    work = _tf.mkdtemp(prefix="vbench-test-tran-")
    try:
        vals, _ = tr.run_ngspice(deck, work)
        sim = vals["v_max"] - vals["v_min"]
        check("simulated ripple agrees with the closed form within 2x",
              abs(sim - dv) <= 0.5 * max(sim, dv),
              f"sim {sim*1e3:.3f} mV vs closed form {dv*1e3:.3f} mV")
        check("the ripple is measured after the open-loop LC ring decays",
              abs(vals["v_avg"] - v_out) < 0.05,
              f"mean {vals['v_avg']} is not near the derived {v_out} — the "
              f"measurement window is too early again")

        cold = tr.deck_cold_start(caps["+5V"][0], c_3v3, 0.430, 5.0, 0.05)
        vals, _ = tr.run_ngspice(cold, work)
        t_ss = 1.2e-3
        check("t_3v3_valid lands near the cited 1.2 ms soft-start time",
              vals.get("t_3v3_valid") is not None
              and t_ss <= vals["t_3v3_valid"] <= 2 * t_ss,
              f"got {vals.get('t_3v3_valid')}")
        check("+3V3 settles above the 3.0 V the ESP32-S3 needs",
              vals["v_final"] > 3.0, f"got {vals['v_final']}")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    # A missing simulator must raise, never return a partial result.
    saved = shutil.which
    try:
        shutil.which = lambda *a, **k: None
        try:
            tr.run_ngspice("* empty\n.end\n", work)
            check("a missing simulator raises instead of returning nothing",
                  False, "returned normally")
        except tr.SimulatorMissing:
            check("a missing simulator raises instead of returning nothing",
                  True)
    finally:
        shutil.which = saved


def main():
    print("=" * 72)
    print("  Virtual Bench Phase 0/1 — mutation tests")
    print("=" * 72)
    test_schema()
    test_corpus()
    test_netlist()
    test_phase1()
    test_thermal()
    test_transients()
    print()
    print("=" * 72)
    print(f"  {PASS} passed, {FAIL} failed")
    print("=" * 72)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
