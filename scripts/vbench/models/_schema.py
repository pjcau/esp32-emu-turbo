"""Virtual Bench T0.2 — what a component model must prove before it counts.

Phase 1 will fill `scripts/vbench/models/` with models of the IP5306, the
SY8089 buck, the PAM8403, the ILI9488 and the rest. Every number in them is
a claim about a physical part, and the boundary table in
docs/virtual-bench-plan.md admits the one failure this bench cannot detect
by simulating harder: **a model that misreads its datasheet**. A wrong
model does not produce a wrong-looking answer. It produces a confident one.

So the schema's job is not to describe data, it is to make an
uncited number impossible to write down. Three rules do the work:

1. **A citation names a place, not a document.** `page 28, figure 7` is a
   claim someone can check in a minute; "per the datasheet" is not. The
   locator must match a page / figure / table / section pattern.
2. **The cited document must exist in `hardware/datasheets/`.** This is
   deliberately strict, and it has a known consequence: the display panel
   is the one part in this design with no datasheet in the repo
   (hardware-audit-bugs.md, R25-HIGH-1, "the panel is the only component
   in the design with no datasheet"), so a panel model cannot validate
   until someone adds the PDF. That is the intended outcome. R25-HIGH-1 —
   a backlight wired across the rail with no ballast — survived every gate
   precisely because the requirement lived in a Markdown table instead of
   a document.
3. **A computed value must say so instead of borrowing a citation.**
   `Param(derived_from=...)` exists so that nobody is ever cornered into
   attributing arithmetic to a page number. Removing this escape hatch
   would not raise honesty, it would manufacture fake citations.

And one prohibition, from the Round 25 post-mortem (see
memory/feedback_comment_outranked_datasheet.md — "a justification comment
outranks the datasheet"): a citation may not contain reassuring language.
`R3 is redundant, the module integrates the pull-up` was believed for four
releases, propagated into three other files, and was never true. Text like
"assumed", "should be", "per the reference design" is rejected here, in the
field whose entire purpose is to be checkable.

Usage:
    from vbench.models._schema import (
        DatasheetRef, Param, Pin, Model, require_valid)

    U2 = Model(
        ref="U2", part="IP5306", mpn="C181692",
        datasheet=DatasheetRef(doc="U2_IP5306_C181692.pdf", rev="v1.4"),
        pins=(Pin("1", "VOUT", "power_out", "p.3 table 1"), ...),
        params={"v_out_typ": Param(5.0, "V", locator="p.5 table 3")},
    )
    require_valid(U2)      # raises ModelSchemaError on any violation
"""

import dataclasses
import os
import re
import typing

BASE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
DATASHEET_DIR = os.path.join(BASE, "hardware", "datasheets")


class ModelSchemaError(ValueError):
    """A model failed its own schema check. Never caught to continue."""


# A locator has to point somewhere a reader can turn to. One atom is a
# page, figure, table or section reference; a locator is one or more atoms,
# because a real citation reads "p.28 figure 7" — the page alone does not
# distinguish the figure from the paragraph beside it.
_ATOM = r"""(?:
      (?:p{1,2}\.?|page[s]?)\s*\d+(?:\s*[-–]\s*\d+)?
    | (?:fig\.?|figure|图)\s*\d+[a-z]?
    | (?:table|tab\.?|表)\s*\d+[a-z]?
    | (?:sec\.?|section|§)\s*\d+(?:\.\d+)*
    )"""
_LOCATOR_PART = re.compile(
    rf"^\s*{_ATOM}(?:\s+{_ATOM})*\s*$", re.IGNORECASE | re.VERBOSE)

# Phrases that turn a citation into an assertion. The list is short on
# purpose: each entry is a phrase that has actually preceded a wrong
# number in this repo's history, or its direct synonym.
_WEASEL = (
    "assume", "assumed", "presumably", "should be", "must be redundant",
    "redundant", "reference design", "as designed", "obviously",
    "typical value", "see datasheet", "per datasheet", "datasheet says",
    "standard practice", "common practice", "known good", "trust me",
    "tbd", "todo", "fixme", "n/a", "unknown",
)

_DIRECTIONS = frozenset({
    "in", "out", "inout", "power_in", "power_out", "gnd", "passive",
    "nc", "analog_in", "analog_out", "open_drain",
})


def _reject_weasel(text, where):
    low = text.lower()
    for phrase in _WEASEL:
        if phrase in low:
            raise ModelSchemaError(
                f"{where}: citation contains {phrase!r}. A citation must "
                f"say where the claim is written, not why it is believed — "
                f"see the Round 25 note at the top of _schema.py.")


@dataclasses.dataclass(frozen=True)
class DatasheetRef:
    """Which document, which revision. Where inside it is per-field."""

    doc: str            # filename under hardware/datasheets/
    rev: str            # revision or date as printed ON the document
    note: str = ""      # optional verbatim quote

    def validate(self, where):
        if not self.doc.strip():
            raise ModelSchemaError(f"{where}: datasheet doc is empty")
        path = os.path.join(DATASHEET_DIR, self.doc)
        if not os.path.exists(path):
            raise ModelSchemaError(
                f"{where}: cited document {self.doc!r} is not in "
                f"hardware/datasheets/. A model may not cite a document the "
                f"repo does not hold — add the PDF first (this is what "
                f"R25-HIGH-1 turned on).")
        if not self.rev.strip():
            raise ModelSchemaError(
                f"{where}: datasheet revision is empty. Two revisions of "
                f"the same part disagree often enough that an uncited "
                f"revision is an uncited number.")
        _reject_weasel(self.rev, f"{where} rev")
        if self.note:
            # The note is a quote, so weasel words inside it may be the
            # datasheet's own. Only its emptiness is checked.
            pass


@dataclasses.dataclass(frozen=True)
class Param:
    """One electrical parameter: a number, its unit, and its provenance.

    Exactly one of `locator` (cited) or `derived_from` (computed) must be
    given. A parameter that is neither cited nor declared derived is the
    thing this schema exists to reject.
    """

    value: typing.Any                       # float, or (min, typ, max)
    unit: str
    locator: str = ""                       # "p.5 table 3"
    doc: str = ""                           # overrides the model's document
    derived_from: typing.Tuple[str, ...] = ()
    formula: str = ""

    def validate(self, where, model_ref):
        if not self.unit.strip():
            raise ModelSchemaError(
                f"{where}: unit is empty (use '1' for dimensionless)")
        if isinstance(self.value, tuple):
            if len(self.value) != 3:
                raise ModelSchemaError(
                    f"{where}: a tuple value must be (min, typ, max)")
            if any(v is None for v in self.value):
                raise ModelSchemaError(
                    f"{where}: (min, typ, max) has a missing entry — omit "
                    f"the parameter rather than padding it")
        elif not isinstance(self.value, (int, float, str)):
            raise ModelSchemaError(
                f"{where}: value must be a number, a string, or "
                f"(min, typ, max)")

        cited = bool(self.locator.strip())
        derived = bool(self.derived_from)
        if cited and derived:
            raise ModelSchemaError(
                f"{where}: both cited and derived. Pick one — a computed "
                f"value that also carries a page number is how a "
                f"calculation acquires false authority.")
        if not cited and not derived:
            raise ModelSchemaError(
                f"{where}: no citation and not declared derived. Give "
                f"locator='p.N table M', or derived_from=(...) with a "
                f"formula.")
        if derived:
            if not self.formula.strip():
                raise ModelSchemaError(
                    f"{where}: derived_from without a formula")
            if self.doc:
                raise ModelSchemaError(
                    f"{where}: a derived parameter must not cite a document")
            return

        validate_locator(self.locator, where)
        if self.doc:
            # A parameter may cite a different document from the model's
            # (an app note, a second part), but it must still be in-repo.
            DatasheetRef(doc=self.doc, rev=model_ref.rev).validate(where)


def validate_locator(locator, where):
    """A locator must point at a page, figure, table or section."""
    _reject_weasel(locator, where)
    for part in re.split(r"[,;]", locator):
        if not part.strip():
            continue
        if not _LOCATOR_PART.match(part):
            raise ModelSchemaError(
                f"{where}: {part.strip()!r} is not a page/figure/table/"
                f"section reference. Write 'p.28', 'figure 7', 'table 3' or "
                f"'§7.2' — a locator that cannot be turned to is not a "
                f"citation.")


@dataclasses.dataclass(frozen=True)
class Pin:
    """One pin, its electrical role, and where that role is written."""

    number: str
    name: str
    direction: str
    locator: str = ""
    doc: str = ""

    def validate(self, where, model_ref):
        if not str(self.number).strip():
            raise ModelSchemaError(f"{where}: pin number is empty")
        if not self.name.strip():
            raise ModelSchemaError(f"{where}: pin name is empty")
        if self.direction not in _DIRECTIONS:
            raise ModelSchemaError(
                f"{where}: direction {self.direction!r} is not one of "
                f"{sorted(_DIRECTIONS)}")
        if not self.locator.strip():
            raise ModelSchemaError(
                f"{where}: no locator for the pin's role. The pin table is "
                f"exactly what R10-LOW-5 got wrong (J4 pins 15 and 16 "
                f"carried the wrong function text for four rounds).")
        validate_locator(self.locator, where)
        if self.doc:
            DatasheetRef(doc=self.doc, rev=model_ref.rev).validate(where)


@dataclasses.dataclass(frozen=True)
class Model:
    """A component model: pins, parameters, and one cited document."""

    ref: str                                # board reference, e.g. "U2"
    part: str                               # part name, e.g. "IP5306"
    mpn: str                                # LCSC/manufacturer number
    datasheet: DatasheetRef
    pins: typing.Tuple[Pin, ...]
    params: typing.Dict[str, Param] = dataclasses.field(default_factory=dict)
    # A model of a part the board does not assemble must be an open
    # circuit, not a component — see netlist.py's D5 class and C28.
    dnp: bool = False

    def pin(self, number):
        for p in self.pins:
            if str(p.number) == str(number):
                return p
        raise KeyError(f"{self.ref} has no pin {number!r}")


def validate_model(model):
    """Raise ModelSchemaError on the first violation found."""
    if not isinstance(model, Model):
        raise ModelSchemaError(f"not a Model: {type(model).__name__}")
    where = f"model {model.ref}"
    for field in ("ref", "part", "mpn"):
        if not str(getattr(model, field)).strip():
            raise ModelSchemaError(f"{where}: {field} is empty")

    model.datasheet.validate(where)

    if not model.pins:
        raise ModelSchemaError(
            f"{where}: no pins. A part with no pins cannot be connected to "
            f"a netlist, so it cannot be checked against one.")
    seen = set()
    for p in model.pins:
        if str(p.number) in seen:
            raise ModelSchemaError(
                f"{where}: pin {p.number!r} declared twice")
        seen.add(str(p.number))
        p.validate(f"{where} pin {p.number}", model.datasheet)

    if not model.params:
        raise ModelSchemaError(
            f"{where}: no electrical parameters. A model with no parameters "
            f"cannot be wrong, which means it cannot be right either.")
    for name, prm in sorted(model.params.items()):
        if not isinstance(prm, Param):
            raise ModelSchemaError(
                f"{where} param {name!r}: not a Param instance")
        prm.validate(f"{where} param {name}", model.datasheet)

    # Derived parameters must resolve inside this model, or the dependency
    # is a name nobody checks.
    for name, prm in sorted(model.params.items()):
        for dep in prm.derived_from:
            if dep not in model.params:
                raise ModelSchemaError(
                    f"{where} param {name}: derived_from names {dep!r}, "
                    f"which is not a parameter of this model")
            if dep == name:
                raise ModelSchemaError(
                    f"{where} param {name}: derived from itself")
    return True


def require_valid(*models):
    """Validate every model, or raise. Returns the models unchanged."""
    for m in models:
        validate_model(m)
    return models if len(models) > 1 else models[0]
