"""Mutation tests for the Virtual Bench Phase 0 foundation.

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

    check("the baseline reports the classes Phase 0 is meant to expose",
          {"D1", "D2", "D3", "D5"} <= base_codes,
          f"got {sorted(base_codes)}")

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


def main():
    print("=" * 72)
    print("  Virtual Bench Phase 0 — mutation tests")
    print("=" * 72)
    test_schema()
    test_corpus()
    test_netlist()
    print()
    print("=" * 72)
    print(f"  {PASS} passed, {FAIL} failed")
    print("=" * 72)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
