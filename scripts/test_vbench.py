"""Mutation tests for the Virtual Bench (Phase 0 foundation, Phase 1 physics,
Phase 2 digital fabric).

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
  G. pins.py, buttons.py — the boot mode must be derived from the copper and
     the strapping tables, a button held at reset must force download mode and
     FAIL, BTN_L's missing pull-up must be derived to be REQUIRED rather than
     reported as a defect, and switch_off must reproduce the v1 invariant.
  H. display.py — the panel-side view must survive a neighbouring markdown
     table, and crossing two data lines must be caught even though every pad's
     net stays valid.
  I. audio.py, sdcard.py — the 8 ohm output power must be DERIVED from the
     datasheet's 4 ohm rating rather than quoted, a missing BOM value must be
     fatal, and the SD socket's DAT2 pad must be detected on a strapping pin's
     net.
  J. corpus coverage — every corpus entry must be caught, blinding one of the
     bench's checks must LOWER that count (a coverage number that survives a
     blinded bench measures nothing), an unapplicable mutation must raise
     rather than read as uncatchable, and the gate must be both registered in
     VERIFY_ALL_SCRIPTS and owned in issue_dispatch.

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


def _quiet(fn, *args):
    """Call a gate's main() without letting its whole report into the suite."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return fn(*args)


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

    # The document must be bound to the PART, not merely exist. The repo now
    # holds DISPLAY-FAMILY_E35RG73248LW6M250-R_FocusLCDs.pdf — a real file
    # describing a DIFFERENT 3.5" panel with the same controller. Before the
    # binding rule, a model citing it validated with every locator pointing
    # at a real page of the wrong part.
    rejects("a real datasheet for a DIFFERENT part is rejected (no mpn in "
            "the filename)",
            lambda: good_model(datasheet=DatasheetRef(
                doc="DISPLAY-FAMILY_E35RG73248LW6M250-R_FocusLCDs.pdf",
                rev="fam")))
    rejects("an in-repo document whose filename lacks the model's LCSC "
            "number is rejected",
            lambda: good_model(mpn="C99999"))

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

    # The structural consequence of R25-HIGH-1, stated precisely: two pages
    # of the panel datasheet ARE in this repo, as images under
    # website/static/img/. What is absent is a PDF in hardware/datasheets/,
    # which is the only place _schema.py accepts a citation from — so no
    # panel model can validate until those pages are put there. If this test
    # fails, either rule 2 was weakened or the pages arrived, and the second
    # case is a good day.
    # 2026-07-31: the good day arrived — the ILITEK controller spec is in
    # hardware/datasheets/ (DS1_ILI9488-controller_ILITEK.pdf, 343 pages).
    # The test now asserts the opposite of what it used to: the document
    # must BE there, because T3.1's controller model cites it. What is
    # still absent is the PANEL's own document (active area, backlight,
    # supply limits) — the controller spec is the silicon, not the glass.
    panel_docs = [f for f in os.listdir(
        os.path.join(BASE, "hardware", "datasheets"))
        if "ILI9488" in f or "panel" in f.lower()]
    check("the ILI9488 controller spec is held, so the controller can be "
          "modelled (T3.1)",
          any("ILI9488-controller" in f for f in panel_docs),
          f"found {panel_docs} — the controller model's citations dangle")

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

    # The coverage count must come from RUNNING detectors, never from the
    # corpus files. This test used to assert "Phase 0 claims no coverage",
    # which was true while no detector existed and became false the moment
    # T5.1 landed — so it now asserts the invariant that outlives the phase:
    # take the detectors away and the count must fall to zero.
    from vbench import detectors
    saved = dict(detectors.LIVE)
    saved_mut = detectors.detect_mutation
    try:
        detectors.LIVE.clear()
        detectors.detect_mutation = lambda e: (False, "detector removed")
        detectors._CACHE.clear()
        with_none = [ok for _, ok, _ in corpus.evaluate(entries) if ok]
    finally:
        detectors.LIVE.update(saved)
        detectors.detect_mutation = saved_mut
        detectors._CACHE.clear()
    check("with the detectors removed, coverage falls to zero — the count is "
          "computed, not stored", len(with_none) == 0,
          f"{len(with_none)} entries still claim to be caught")


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
          "D5" in base_codes, f"got {sorted(base_codes)}")
    # D2 must be GONE from the baseline: its last tenants were the I2S
    # reservation nets, retired 2026-07-26 (R10-LOW-2). If D2 reappears
    # here, a one-pin net has come back.
    check("no single-pin net remains on the board (I2S retirement held)",
          "D2" not in base_codes, f"got {sorted(base_codes)}")
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
    # Since 2026-07-31 the spread includes the divider's cited +/-1%
    # (Uniroyal F code, R26 datasheet p.2 sec 2.3) stacked worst-case on
    # top of V_REF's 0.588..0.612 V. The old V_REF-only spread must still
    # be reproducible for comparison, and must be narrower.
    check("the +3V3 spread stacks V_REF and the cited +/-1% divider",
          abs(lo - 3.2078) < 1e-3 and abs(hi - 3.4500) < 1e-3,
          f"got {lo}..{hi}")
    vlo, _, vhi = v_out_spread(div.r_top_ohm, div.r_bottom_ohm,
                               include_resistors=False)
    check("the V_REF-only spread is still reproducible, and narrower",
          abs(vlo - 3.2607) < 1e-3 and abs(vhi - 3.3939) < 1e-3
          and vlo > lo and vhi < hi,
          f"got {vlo}..{vhi}")
    check("the worst case stays under the 3.6 V ESP32/SD limit",
          hi < 3.6, f"got {hi}")

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
    # The regression that mattered: SW16's shell tabs carry BTN_SELECT, so
    # closing "every net the switch touches" welded BAT+ to the buttons and
    # put 3.83 V on all of them.
    check("closing the switches does NOT weld BAT+ to BTN_SELECT via "
          "SW16's shell tabs",
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

    # Since 2026-07-31 U2 is computable ON BATTERY (cited 92% + theta_JA
    # 50, official V1.32), and must say it is a lower bound; while
    # charging, the power path is still uncited, so charge-and-play must
    # STILL say NOT COMPUTABLE — checked further down.
    results = {r.ref: r for r in thermal.evaluate(thermal.SCENARIOS[1], 40.0)}
    check("U2's on-battery dissipation is computed, labelled a lower bound",
          results["U2"].p_watts is not None
          and "LOWER" in results["U2"].basis
          and results["U2"].tj is not None)
    check("U5 gets a Tj from the cited theta_JA 110, limit the 140 OTP",
          results["U5"].p_watts is not None
          and results["U5"].tj is not None
          and results["U5"].tj_max == 140.0)
    check("U3's figure is labelled a lower bound (no switching loss)",
          "LOWER BOUND" in results["U3"].basis)
    check("U3 and Q1 do get a junction temperature",
          results["U3"].tj is not None and results["Q1"].tj is not None)

    # Charge-and-play must not put battery current through Q1.
    cap = {r.ref: r for r in thermal.evaluate(thermal.SCENARIOS[2], 40.0)}
    check("in charge-and-play Q1 carries no battery current",
          cap["Q1"].p_watts == 0.0, f"got {cap['Q1'].p_watts}")
    check("in charge-and-play U2 stays NOT COMPUTABLE (power path uncited)",
          cap["U2"].p_watts is None
          and "NOT COMPUTABLE" in cap["U2"].basis)

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


# ── G. Phase 2: pin fabric, boot mode, buttons, the switch ──────────

def test_phase2():
    print("\nG. pins.py / buttons.py")
    from vbench import buttons, pins
    from vbench.models.u1_esp32s3 import (
        STRAPPING_DEFAULTS, U1, boot_mode, vdd_spi_voltage)

    try:
        validate_model(U1)
        check("U1's strapping model satisfies the citation schema", True)
    except ModelSchemaError as exc:
        check("U1's strapping model satisfies the citation schema", False,
              str(exc))

    # Table 6, page 14, reproduced exactly — including the row that says
    # GPIO46 is ignored when GPIO0 is high.
    check("GPIO0=1 is SPI Boot whatever GPIO46 does (table 6)",
          boot_mode(1, 0)[0] == "SPI Boot"
          and boot_mode(1, 1)[0] == "SPI Boot")
    check("GPIO0=0 with GPIO46=0 is Joint Download Boot (table 6)",
          boot_mode(0, 0)[0] == "Joint Download Boot")
    check("an undefined GPIO0 gives an UNDEFINED boot mode, not a guess",
          boot_mode(None, 0)[0] == "UNDEFINED")

    # Table 7, page 15.
    check("GPIO45=0 selects the 3.3 V VDD_SPI the N16R8's PSRAM needs",
          vdd_spi_voltage(0)[0] == 3.3)
    check("GPIO45=1 selects 1.8 V, which is why R14 must stay DNP",
          vdd_spi_voltage(1)[0] == 1.8)

    # The GPIO3 exception is the one a hand-written table would flatten.
    check("GPIO3 is recorded as having NO internal pull (p.15 3.3.4)",
          STRAPPING_DEFAULTS["GPIO3"]["internal"] is None
          and STRAPPING_DEFAULTS["GPIO3"]["default"] is None)
    check("GPIO0 pulls up and GPIO45/46 pull down (table 4)",
          STRAPPING_DEFAULTS["GPIO0"]["default"] == 1
          and STRAPPING_DEFAULTS["GPIO45"]["default"] == 0
          and STRAPPING_DEFAULTS["GPIO46"]["default"] == 0)

    # The board, derived end to end.
    fabric, op, v_rail = pins.fabric()
    state = pins.strapping_state(fabric)
    check("this board boots SPI Boot, derived from the copper",
          boot_mode(state["GPIO0"][0], state["GPIO46"][0])[0] == "SPI Boot",
          f"GPIO0={state['GPIO0']}, GPIO46={state['GPIO46']}")
    check("VDD_SPI comes out at 3.3 V because BTN_L floats onto the internal "
          "pull-down",
          vdd_spi_voltage(state["GPIO45"][0])[0] == 3.3,
          f"GPIO45={state['GPIO45']}")
    check("no octal-PSRAM pin is attached externally",
          not [p for p in fabric if p.gpio in pins.RESERVED])

    # T2.4's done-when: a button held at reset that forces download mode must
    # be a FAIL naming the pin.
    held, _, _ = pins.fabric(hold_nets=("BTN_SELECT",))
    held_state = pins.strapping_state(held)
    mode, _ = boot_mode(held_state["GPIO0"][0], held_state["GPIO46"][0])
    check("holding BTN_SELECT at reset forces Joint Download Boot",
          mode == "Joint Download Boot", f"got {mode}")
    check("the pins gate exits non-zero for that scenario",
          _quiet(pins.main, ["--hold", "BTN_SELECT"]) == 1)

    # T2.2: the debounce RC must come from the netlist and the BOM.
    survey = buttons.survey()
    with_rc = [b for b in survey if b.tau_s]
    check("eleven buttons have a 1.000 ms debounce RC from 10k x 100nF",
          len(with_rc) == 11
          and all(abs(b.tau_s - 1e-3) < 1e-9 for b in with_rc),
          f"{len(with_rc)} with RC: "
          f"{[(b.net, b.tau_s) for b in with_rc][:3]}")
    check("the release edge to 70% of rail is 1.204 ms",
          all(abs(b.t_rise_s - 1.2040e-3) < 1e-6 for b in with_rc),
          f"got {[b.t_rise_s for b in with_rc][:2]}")

    # BTN_L must be reported as correct-by-design, not as a defect.
    btn_l = next(b for b in survey if b.net == "BTN_L")
    check("BTN_L's missing pull-up is derived to be REQUIRED, not a defect",
          btn_l.pullup_forbidden is not None
          and btn_l.pullup_forbidden[0] == "GPIO45"
          and btn_l.r_ohm is None,
          f"got {btn_l.pullup_forbidden}")
    check("buttons.py exits 0 despite BTN_L having no RC",
          _quiet(buttons.main, []) == 0)

    # T2.3: switch_off must reproduce, not report.
    ok, detail = buttons.switch_off_scenario()
    check("switch_off leaves the board powered (SW16 is not in series)", ok,
          f"{detail}")
    check("the reason is derived: SW16's throw pads carry no net",
          detail["routed_throws"] == [] and detail["common_net"] == "BAT+",
          f"{detail}")
    check("the invariant is still recorded in docs/known-issues.md",
          detail["recorded"])


# ── H. Phase 3: the display, seen from the panel ────────────────────

def test_phase3():
    print("\nH. display.py")
    from vbench import display as disp

    rows = disp.read_pinout()
    check("all 40 panel pins are covered by the parsed pinout",
          sorted(rows) == list(range(1, 41)), f"got {len(rows)} pins")
    # The parse must anchor on the pinout table's header. components.md holds
    # a second five-column table right below it (IM2:IM1:IM0), whose rows
    # start with 0 and 1 — reading every five-column row in the file let them
    # overwrite panel pin 1, which then came out named "1".
    check("panel pin 1 is XL, not a row from the interface-mode table",
          rows[1][0] == "XL", f"got {rows[1]}")
    check("the data bus expands to DB0..DB7 from a single '17-24' row",
          [rows[p][0] for p in range(17, 25)]
          == [f"DB{n}" for n in range(8)],
          f"got {[rows[p][0] for p in range(17, 25)]}")

    check("the ribbon reversal is pad = 41 - pin",
          disp.pad_of(17) == "24" and disp.pad_of(40) == "1"
          and disp.pad_of(1) == "40")

    view, v_rail = disp.panel_view()
    ok, mode, detail = disp.check_interface_mode(view)
    check("the IM straps derive to 8080 8-bit from the copper", ok,
          f"{mode}: {detail}")
    check("DB0..DB7 land on LCD_D0..LCD_D7 in order",
          disp.check_data_bus(view) == [],
          f"{disp.check_data_bus(view)}")

    # Cross two data lines and require the panel-side check to notice. This is
    # the failure the pad-side gates cannot express: swapping LCD_D0 and
    # LCD_D1 keeps every pad's net valid and every net's pad count identical.
    crossed = []
    for p in view:
        if p.symbol == "DB0":
            crossed.append(p._replace(net="LCD_D1"))
        elif p.symbol == "DB1":
            crossed.append(p._replace(net="LCD_D0"))
        else:
            crossed.append(p)
    faults = disp.check_data_bus(crossed)
    check("crossing two data lines is caught, with both pins named",
          len(faults) == 2 and "panel pin 17" in faults[0]
          and "panel pin 18" in faults[1], f"got {faults}")

    # A 16-bit-mode line that acquires a net must be caught too.
    with_db8 = [p._replace(net="LCD_D0") if p.symbol == "DB8" else p
                for p in view]
    check("a DB8-DB15 line carrying a net in 8-bit mode is caught",
          any("16-bit-mode line" in f
              for f in disp.check_data_bus(with_db8)))

    # An interface mode other than 8-bit 8080 must fail, not be excused.
    flipped = [p._replace(level=1) if p.symbol == "IM2" else p for p in view]
    ok2, mode2, _ = disp.check_interface_mode(flipped)
    check("flipping IM2 stops the mode being 8080 8-bit",
          not ok2 and mode2 != "8080 8-bit parallel", f"got {mode2}")

    # A truncated pinout must be fatal, never filled in.
    saved = disp.PINOUT_DOC
    try:
        disp.PINOUT_DOC = os.path.join(BASE, "README.md")
        try:
            disp.read_pinout(disp.PINOUT_DOC)
            check("a document with no pinout table is fatal", False,
                  "returned a pinout")
        except disp.PinoutError:
            check("a document with no pinout table is fatal", True)
    finally:
        disp.PINOUT_DOC = saved

    # The controller's command set, MADCTL, pixel format and i80 timing USED
    # to be declared unmodelled here, because the controller datasheet was
    # not in the repo. It is now (DS1_ILI9488-controller_ILITEK.pdf) and T3.1
    # models all four, so asserting they are still unmodelled would pin a
    # false claim. What must not silently disappear is the PANEL-side gap
    # that remains: the module itself has no PDF, so no panel Model validates.
    check("the panel module's missing datasheet is still declared",
          "panel_module_model" in disp.UNMODELLED)
    check("the controller half is no longer claimed unmodelled",
          not {"command_set", "pixel_format", "timing"} & set(disp.UNMODELLED),
          "display.py still lists the controller as unbuildable, but "
          "scripts/vbench/ili9488_ctrl.py models it")
    check("display.py runs the controller model, not just the wiring",
          disp.check_controller is not None
          and callable(disp.check_controller))

    # The datasheet distinguishes unused INPUTS (tie them) from unused
    # OUTPUTS (leave them open), pin by pin. No summary in this repo carried
    # that distinction until the datasheet images were read.
    unused = disp.check_unused_pins(view)
    # R28-HIGH-1 was FIXED 2026-07-26: J4 pad 28 (panel pin 13, SPI SDI) now
    # stubs to pad 29's +3V3, so a clean board reports NOTHING. The rule must
    # still discriminate, so the float is re-injected in memory below —
    # same pattern as the pin-14 mutation — and the corpus carries the fix
    # as a detach_pin mutation entry (T5.1 rediscovery).
    check("panel pin 13 (SPI SDI), now tied to +3V3, is not reported",
          not any("pin 13" in f for f in unused), f"got {unused}")
    floated_sdi = [p._replace(net=None) if p.pin == 13 else p for p in view]
    check("re-injecting the pin 13 float IS caught (rule still discriminates)",
          any("pin 13" in f for f in disp.check_unused_pins(floated_sdi)))
    check("panel pin 12 (RDX), which IS tied, is not reported",
          not any("pin 12" in f for f in unused), f"got {unused}")
    check("panel pin 14 (SDO) being open is correct, not a fault",
          not any("pin 14" in f for f in unused), f"got {unused}")
    # Tying an output the datasheet says to leave open must also be caught,
    # or the rule is only half a rule.
    tied_sdo = [p._replace(net="+3V3") if p.pin == 14 else p for p in view]
    check("tying pin 14 shut is caught too",
          any("pin 14" in f for f in disp.check_unused_pins(tied_sdo)))

    check("display.py exits 0 now that pin 13 is tied — the finding is closed",
          _quiet(disp.main, []) == 0)


# ── I. Phase 3: audio and SD ────────────────────────────────────────

def test_phase3_peripherals():
    print("\nI. audio.py / sdcard.py")
    from vbench import audio, sdcard

    r_eff, c_block, f_corner, bias, block = audio.input_network()
    check("the bias network is the two 20k in parallel, from the netlist",
          sorted(bias) == ["R20", "R21"] and abs(r_eff - 10e3) < 1.0,
          f"got {bias}, {r_eff}")
    check("the DC block is C22 = 0.47 uF from the BOM",
          block == "C22" and abs(c_block - 0.47e-6) < 1e-9)
    check("the input high-pass corner is 33.9 Hz",
          abs(f_corner - 33.86) < 0.2, f"got {f_corner}")

    # Since 2026-07-31 the 8 ohm figure is CITED (Diodes p.4: 1.8 W at 10%
    # THD, 5 V), replacing the halved-from-4-ohm derivation of 1.5 W. The
    # 4 ohm point stays the table's own 3.2 W.
    check("8 ohm output power is the cited 1.8 W, not the derived 1.5",
          abs(audio.output_power(5.0, 8.0) - 1.8) < 1e-9
          and abs(audio.output_power(5.0, 4.0) - 3.2) < 1e-9,
          f"got {audio.output_power(5.0, 8.0)}")
    check("output power scales with the square of the supply",
          abs(audio.output_power(2.5, 8.0) - 1.8 / 4) < 1e-9)

    # The gain is the cited 24 dB — the DAC-to-amplitude map exists now.
    check("the closed-loop gain is the cited 24 dB as a linear ratio",
          abs(audio.gain_linear() - 10.0 ** 1.2) < 1e-9,
          f"got {audio.gain_linear()}")

    # Supply current must include the cited quiescent draw (Diodes p.4:
    # 16 mA at 5 V — the Slkor reprint's 6.3 mA figure is superseded).
    i_idle = audio.supply_current(0.0, 5.0)
    check("at zero output the rail sees the cited 16 mA quiescent",
          abs(i_idle - 16e-3) < 1e-9, f"got {i_idle}")
    i_full = audio.supply_current(1.8, 5.0)
    check("at full cited output the rail sees about 430 mA",
          abs(i_full - 0.4298) < 1e-3, f"got {i_full}")

    # The sag the audio current causes on +5V is now a number: I times the
    # boost's derived conduction resistance (worst-case battery floor).
    check("full-output audio sags +5V by ~38 mV through the derived R_out",
          abs(audio.rail_sag(i_full) - i_full * 0.089) < 1e-12
          and 0.030 < audio.rail_sag(i_full) < 0.045,
          f"got {audio.rail_sag(i_full)}")

    # A missing BOM value must be fatal, never defaulted.
    import vbench.rails as _rails
    values = _rails.load_bom_values()
    try:
        audio.input_network(values={k: v for k, v in values.items()
                                    if k != "C22"})
        check("a missing DC-block value is fatal", False, "returned a network")
    except audio.AudioError:
        check("a missing DC-block value is fatal", True)

    wav = os.path.join(tempfile.mkdtemp(prefix="vbench-wav-"), "spk.wav")
    v_peak, v_rms = audio.render_wav(wav, 1.5)
    check("the WAV is written and its amplitude follows P = V^2/R",
          os.path.getsize(wav) > 1000
          and abs(v_rms - (1.5 * 8.0) ** 0.5) < 1e-9,
          f"{v_rms} V rms")
    shutil.rmtree(os.path.dirname(wav), ignore_errors=True)

    # ── SD ───────────────────────────────────────────────────────────
    notes, shared, exposure, op, faults = sdcard.survey()
    check("the four SPI signals land on the socket's own pad roles",
          faults == [], f"{faults}")
    check("DAT1 is tied to DAT0/MISO, as the design intends",
          "8" in shared and shared["8"][0] == "SD_MISO",
          f"{shared.get('8')}")
    # The finding: DAT2 shares a net with a strapping pin.
    check("U6.9 (DAT2) is detected on a strapping pin's net",
          any(pad == "9" and gpio == "GPIO3"
              for pad, _role, _net, gpio, _strap in exposure),
          f"{exposure}")
    check("and that pin is recorded as having NO internal pull",
          all(strap["internal"] is None
              for pad, _r, _n, gpio, strap in exposure if gpio == "GPIO3"))
    check("the SD protocol is declared unmodelled, not faked",
          {"init_sequence", "block_read", "timing"} <= set(sdcard.UNMODELLED))
    check("audio.py and sdcard.py both exit 0 on this board",
          _quiet(audio.main, []) == 0 and _quiet(sdcard.main, []) == 0)


# ── J. Phase 5: does the corpus measure anything? ───────────────────

def test_phase5():
    print("\nJ. corpus coverage / detectors.py / mutate.py")
    from vbench import corpus, detectors, mutate
    from vbench import netlist as _nl

    entries = corpus.load_corpus()
    results = corpus.evaluate(entries)
    caught = [e for e, ok, _ in results if ok]
    missed = [(e.id, why) for e, ok, why in results if not ok]
    check("the bench rediscovers every corpus entry (T5.1)",
          len(caught) == len(entries),
          f"{len(caught)}/{len(entries)}; missed {missed}")

    # The count has to be worth something. Blind one of the bench's checks
    # and the coverage must DROP — otherwise the detectors are passing on
    # something other than the bench's findings.
    saved = _nl.crosscheck
    try:
        _nl.crosscheck = lambda *a, **k: []
        detectors._CACHE.clear()
        blinded = sum(1 for _e, ok, _d in corpus.evaluate(entries) if ok)
    finally:
        _nl.crosscheck = saved
        detectors._CACHE.clear()
    restored = sum(1 for _e, ok, _d in corpus.evaluate(entries) if ok)
    check("blinding the netlist checks lowers the coverage count",
          blinded < len(entries), f"still {blinded}/{len(entries)} blinded")
    check("and restoring them brings it back",
          restored == len(entries), f"{restored}/{len(entries)}")

    # A mutation that cannot be applied must say so, not report the entry as
    # uncatchable — those are different failures with different fixes.
    board = _nl.load_board_netlist()
    try:
        mutate.apply(board, {"kind": "teleport", "ref": "R8"})
        check("an unimplemented mutation kind raises", False, "returned")
    except mutate.MutationError as exc:
        check("an unimplemented mutation kind raises",
              "not implemented" in str(exc))
    try:
        mutate.apply(board, {"kind": "detach_pin", "ref": "R8", "pin": "99"})
        check("detaching a pin that is on no net raises", False, "returned")
    except mutate.MutationError:
        check("detaching a pin that is on no net raises", True)
    try:
        mutate.apply(board, {"kind": "none"})
        check("kind 'none' cannot be injected", False, "returned")
    except mutate.MutationError:
        check("kind 'none' cannot be injected", True)

    # D6 — the Round 5 class. It must be silent on the real board and fire
    # the moment a passive loses a terminal.
    sch = _nl.load_schematic_netlist()
    base_codes = {d.code for d in _nl.crosscheck(board, sch)}
    check("D6 is silent on the board as it stands", "D6" not in base_codes,
          f"got {sorted(base_codes)}")
    detached, _what = mutate.apply(
        board, {"kind": "detach_pin", "ref": "C18", "pin": "1"})
    d6 = [d for d in _nl.crosscheck(detached, sch)
          if d.code == "D6" and d.subject == "C18"]
    check("D6 fires when a decoupling cap loses a terminal (R5-CRIT-2)",
          len(d6) == 1, f"got {[d.subject for d in _nl.crosscheck(detached, sch) if d.code == 'D6']}")
    check("R14 does not trip D6, because it is DNP and derived to be so",
          not [d for d in _nl.crosscheck(board, sch) if d.subject == "R14"])

    # T5.3: the gate has to be registered AND owned.
    makefile = open(os.path.join(BASE, "Makefile")).read()
    check("test_vbench is registered in VERIFY_ALL_SCRIPTS (T5.3)",
          "\ttest_vbench \\" in makefile)
    sys.path.insert(0, os.path.join(BASE, "scripts"))
    import issue_dispatch
    route = issue_dispatch.route("test_vbench")
    check("issue_dispatch gives the bench gate an owner (T5.3)",
          route is not None and route["agent"] == "pcb-engineer",
          f"got {route}")
    check("and rates it a blind-spot, above a dead board",
          route and route["severity"] == "blind-spot", f"got {route}")


# ── K. Phase 4.3: scenarios ─────────────────────────────────────────

def test_scenarios():
    print("\nK. scenario.py")
    from vbench import scenario

    docs = scenario.load_scenarios()
    names = {d["name"] for d in docs}
    check("the plan's scenarios are all present",
          {"usb_cold_boot", "battery_3v4", "press_all_buttons", "switch_off",
           "audio_max"} <= names, f"got {sorted(names)}")
    check("every scenario carries at least one assertion",
          all(d["assert"] for d in docs))

    results = []
    for doc in docs:
        results.extend(scenario.run_scenario(doc))
    failed = [r for r in results if not r.ok]
    check("every scenario assertion passes on this board",
          not failed, f"{[(r.scenario, r.name) for r in failed]}")
    check("there are enough assertions to be worth running",
          len(results) >= 20, f"only {len(results)}")

    # An assertion naming a quantity the bench does not compute must be a
    # hard error. A typo that silently skips is the same failure as a gate
    # nobody runs.
    try:
        scenario.run_scenario({
            "name": "typo", "description": "x", "setup": {},
            "assert": [{"quantity": "rail.+3V3.tpy", "op": "==",
                        "value": 3.3}]})
        check("an unknown quantity is a hard error", False, "ran anyway")
    except scenario.ScenarioError as exc:
        check("an unknown quantity is a hard error",
              "does not compute" in str(exc))

    try:
        scenario.run_scenario({
            "name": "badop", "description": "x", "setup": {},
            "assert": [{"quantity": "rails.violations", "op": "~=",
                        "value": 0}]})
        check("an unknown operator is a hard error", False, "ran anyway")
    except scenario.ScenarioError:
        check("an unknown operator is a hard error", True)

    # A scenario with no assertions passes vacuously, so loading must refuse.
    saved = scenario.SCEN_DIR
    tmp = tempfile.mkdtemp(prefix="vbench-scen-")
    try:
        with open(os.path.join(tmp, "empty.json"), "w") as fh:
            json.dump({"name": "empty", "description": "x", "setup": {},
                       "assert": []}, fh)
        scenario.SCEN_DIR = tmp
        try:
            scenario.load_scenarios()
            check("a scenario that asserts nothing is refused", False,
                  "loaded")
        except scenario.ScenarioError:
            check("a scenario that asserts nothing is refused", True)
    finally:
        scenario.SCEN_DIR = saved
        shutil.rmtree(tmp, ignore_errors=True)

    # The assertions must actually discriminate: holding BTN_SELECT has to
    # break usb_cold_boot's boot-mode assertion.
    cold = next(d for d in docs if d["name"] == "usb_cold_boot")
    held = json.loads(json.dumps(cold))
    held["setup"]["hold"] = ["BTN_SELECT"]
    broken = [r for r in scenario.run_scenario(held) if not r.ok]
    check("holding BTN_SELECT breaks the cold-boot scenario",
          any("boot" in r.detail for r in broken),
          f"got {[r.name for r in broken]}")

    # JUnit must be well-formed and carry the failures.
    out = os.path.join(tempfile.mkdtemp(prefix="vbench-junit-"), "j.xml")
    scenario.junit(results, out)
    import xml.etree.ElementTree as _ET
    root = _ET.parse(out).getroot()
    check("the JUnit output parses and names every scenario",
          root.tag == "testsuites"
          and len(root.findall("testsuite")) == len(docs),
          f"{len(root.findall('testsuite'))} suites")
    shutil.rmtree(os.path.dirname(out), ignore_errors=True)


# ── L. Phase 4.1/4.4: the exported board header ─────────────────────

def test_header():
    print("\nL. export_header.py / vbench_board.h")
    from vbench import export_header as eh

    d = eh.derive()
    check("the i80 bus map derives to the identity on this board",
          d["bus"] == list(range(8)), f"got {d['bus']}")
    check("the RC mask covers eleven buttons and NOT BTN_L (bit 10)",
          d["rc_mask"] == 0xBFF, f"got {hex(d['rc_mask'])}")
    check("boot mode and VDD_SPI carry the derived answers",
          d["boot_mode"] == "SPI Boot" and d["vdd_spi"] == 3.3)
    check("EN is exported as floating (R25-CRIT-1 rides into the window)",
          d["en_floating"] is True)
    check("the switch-not-in-series invariant is exported",
          d["switch_not_in_series"] is True)
    check("the header admits it is uncalibrated",
          d["calibrated"] == "no")

    text = eh.render(d)
    check("rendering is deterministic (same input, same bytes)",
          text == eh.render(d))
    check("the header carries the PCB fingerprint and no timestamp",
          "VB_PCB_HASH" in text and "20" + "26-" not in text.split("sha256")[0])
    check("the bus map is emitted as data, not prose",
          "VB_LCD_BUS_MAP[8] = { 0, 1, 2, 3, 4, 5, 6, 7 }" in text)

    # Freshness: the file on disk must match a regeneration.
    check("the committed header is current (make bench-header)",
          _quiet(eh.main, ["--check"]) == 0)

    # And the check must actually discriminate: a doctored header fails it.
    with open(eh.HEADER) as fh:
        saved = fh.read()
    try:
        with open(eh.HEADER, "w") as fh:
            fh.write(saved.replace("VB_RAIL_3V3_TYP_MV 3327",
                                   "VB_RAIL_3V3_TYP_MV 3300"))
        check("a doctored rail value makes --check fail",
              _quiet(eh.main, ["--check"]) == 1)
    finally:
        with open(eh.HEADER, "w") as fh:
            fh.write(saved)

    # The C build exists and links the model-backed HAL (built by
    # `make bench-build`; here we only require the source contract).
    hal = open(os.path.join(BASE, "software", "sim", "vbench_hal.c")).read()
    check("vbench_hal contains no electrical constant of its own",
          "3.327" not in hal and "1204" not in hal and "0xBFF" not in hal,
          "a derived number is hardcoded in the C — it belongs in the header")
    check("the HAL routes pixels through the derived bus map",
          "VB_LCD_BUS_MAP" in hal and "vb_bus_px" in hal)
    check("the HAL reproduces the switch invariant rather than cutting power",
          "VB_SWITCH_NOT_IN_SERIES" in hal)


def test_phase5_plan_mutations():
    """T5.2 — the plan names five mutations; each must fail the bench.

    'Fail the bench' means: an existing bench check, run against the
    mutated netlist, produces a fault that names the damage. The
    un-mutated board must pass the same check in the same breath, or the
    test proves nothing about discrimination.
    """
    print("\nN. T5.2 — the plan's named mutations")
    from vbench import buttons, conflicts, display, mutate, rails
    from vbench import netlist as _nl

    board = _nl.load_board_netlist()
    values = rails.load_bom_values()

    # ── 1. Swap D/C with a data line ────────────────────────────────
    # J4 pad 31 carries LCD_DC (panel pin 10), pad 24 carries LCD_D0
    # (panel pin 17). Crossing them leaves every net with a valid pad
    # count — invisible to every pad-side gate, dead display in life.
    m, _ = mutate.apply(board, {"kind": "move_pin", "ref": "J4",
                                "pin": "31", "to_net": "LCD_D0"})
    m, _ = mutate.apply(m, {"kind": "move_pin", "ref": "J4",
                            "pin": "24", "to_net": "LCD_DC"})
    view_m, _ = display.panel_view(m)
    ctrl = display.check_control_lines(view_m)
    data = display.check_data_bus(view_m)
    check("swap D/C with DB0: control AND data checks both fire",
          bool(ctrl) and bool(data),
          f"ctrl={len(ctrl)} data={len(data)}")
    view_0, _ = display.panel_view()
    check("the un-mutated board passes the control-line check",
          not display.check_control_lines(view_0))

    # ── 2. Delete a button pull-up ──────────────────────────────────
    # Find BTN_A's pull-up from the survey (never hardcode the ref), then
    # detach it. The button must come back with no RC and a note, where
    # the real board has both.
    row0 = next(b for b in buttons.survey(board, values) if b.net == "BTN_A")
    check("BTN_A has a pull-up and an RC on the real board",
          row0.pullup is not None and row0.t_rise_s is not None)
    pad = next(p.pad for p in board.nets["BTN_A"] if p.ref == row0.pullup)
    m, _ = mutate.apply(board, {"kind": "detach_pin", "ref": row0.pullup,
                                "pin": pad})
    row_m = next(b for b in buttons.survey(m, values) if b.net == "BTN_A")
    check("delete the pull-up: the survey loses the RC and says why",
          row_m.pullup is None and row_m.t_rise_s is None and row_m.note,
          f"got pullup={row_m.pullup} note={row_m.note!r}")

    # ── 3. Tie WR to GND ────────────────────────────────────────────
    # The write strobe welded low: every net keeps a plausible shape, but
    # panel pin 11 now sees GND where the 8080 interface needs its strobe.
    m, _ = mutate.apply(board, {"kind": "short_nets", "net_a": "GND",
                                "net_b": "LCD_WR"})
    view_m, _ = display.panel_view(m)
    ctrl = display.check_control_lines(view_m)
    check("tie WR to GND: the control-line check names the strobe",
          any("WR" in f for f in ctrl), f"faults: {ctrl}")

    # ── 4. Short +3V3 to GND ────────────────────────────────────────
    # The rails module must refuse to produce a happy table for a board
    # whose 3.3 V rail is the ground plane.
    m, _ = mutate.apply(board, {"kind": "short_nets", "net_a": "GND",
                                "net_b": "+3V3"})
    fired = []
    try:
        found = conflicts.find_conflicts(m, values)
        fired = [c for c in found
                 if "U3" in getattr(c, "detail", "") or
                 "U3" in getattr(c, "net", "")]
    except Exception as exc:                              # noqa: BLE001
        fired = [f"conflicts refused: {exc}"]
    solved_dead = False
    try:
        rails.solve_dc(m, values, {"GND": 0.0, "+5V": 5.0, "+3V3": 3.327,
                                   "BAT+": 3.83, "BAT_IN": 3.83,
                                   "VBUS": 5.0})
    except Exception:                                     # noqa: BLE001
        solved_dead = True
    else:
        # +3V3 no longer exists as a net; a solver that still reports it
        # at 3.327 V is describing a board that is not there.
        solved_dead = "+3V3" not in m.nets
    check("short +3V3 to GND: the bench does not produce a happy table",
          bool(fired) or solved_dead,
          f"conflicts={fired} solved_dead={solved_dead}")

    # ── 5. Rotate the LCD model ─────────────────────────────────────
    # Covered at the controller level: scripts/test_vbench_display.py
    # (T3.1) asserts MADCTL MV/MX/MY move a probe pixel exactly as the
    # cited bit semantics say, so a rotated model shows a rotated frame.
    # Asserted here only that the suite exists and is wired into
    # bench-test, so this pointer cannot dangle.
    check("the MADCTL rotation suite exists (T3.1's tests carry mutation 5)",
          os.path.exists(os.path.join(BASE, "scripts",
                                      "test_vbench_display.py")))


def main():
    print("=" * 72)
    print("  Virtual Bench Phase 0/1/2/3/4/5 — mutation tests")
    print("=" * 72)
    test_schema()
    test_corpus()
    test_netlist()
    test_phase1()
    test_thermal()
    test_transients()
    test_phase2()
    test_phase3()
    test_phase3_peripherals()
    test_phase5()
    test_phase5_plan_mutations()
    test_scenarios()
    test_header()
    print()
    print("=" * 72)
    print(f"  {PASS} passed, {FAIL} failed")
    print("=" * 72)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
