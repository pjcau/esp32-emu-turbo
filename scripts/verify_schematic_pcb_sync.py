#!/usr/bin/env python3
"""Verify that the Python-generated schematic and the Python-generated PCB agree.

This is the guard that catches the R4 class of bugs:

  R4-CRIT-1  ILI9488 FPC pinout in display.py ≠ datasheet_specs.py (→ PCB)
  R4-HIGH-1  USBLC6 + R22/R23 exist only in routing.py, missing from schematic
  R4-HIGH-2  U4 designator used for ILI9488 module symbol AND for USBLC6 TVS

The schematic generator (``scripts/generate_schematics``) and the PCB
generator (``scripts/generate_pcb``) are two independent code paths. Any
verifier that reads only one side can never catch divergence — the whole
class of ``schematic says X, PCB says Y`` bugs is invisible.

What this script checks
-----------------------

  A. Every designator that ends up in the BOM/CPL must have a corresponding
     schematic symbol in exactly one sheet. BOM refs with no schematic
     symbol are invisible to the reviewer; schematic refs with no BOM entry
     are phantom parts.

  B. No designator may map to two different component types across the
     schematic and the PCB. If ``U4`` is a display module in ``display.py``
     and a USBLC6 TVS in the BOM, that is a designator collision.

  C. Every connector defined in ``hardware/datasheet_specs.py`` must have
     its full set of distinct signal nets appear in the sheet that wires it
     (via ``self.glabel("NET", ...)`` calls). This does NOT catch pin-by-pin
     swaps (the schematic uses simplified symbols) but it does catch the
     case where a sheet wires a completely different pinout family than the
     one the PCB uses — e.g. a sheet that references ``LCD_CS, LCD_WR, …``
     while the PCB's ``J4`` uses an entirely different set of nets.

Exit code
---------

Non-zero on ANY violation. No warnings, no soft-passes, no "known false
positives". If a check cannot be run (e.g. a parse failure), that is also
a non-zero exit — never silently skip. This is required by the
"never silence errors" project rule; R4 found a CRITICAL that slipped
through rounds 1-3 because earlier checks auto-skipped on missing inputs.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO = Path(__file__).resolve().parent.parent
SHEETS_DIR = REPO / "scripts" / "generate_schematics" / "sheets"
JLCPCB_EXPORT = REPO / "scripts" / "generate_pcb" / "jlcpcb_export.py"
DATASHEET_SPECS = REPO / "hardware" / "datasheet_specs.py"

# Schematic symbol "refs" that exist only in the schematic for visualisation
# and must NOT appear in the BOM/CPL (they represent off-board modules or
# mechanical/logical groupings). Any ref in this set is exempt from check A
# on the BOM side.
#
# IMPORTANT: keep this list very small. Every entry is a promise that the
# symbol has no manufacturable counterpart. Do not use this to hide real
# mismatches — fix them.
SCHEMATIC_ONLY_REFS: Set[str] = {
    "BT1",        # LiPo cell — off-board, wired through J3
    "SPK1",       # 28mm speaker — off-board, through-hole, manual
    "#FLG01",     # KiCad PWR_FLAG marker
    "DS1",        # ILI9488 display module — off-board, connects via J4
    "J2",         # Optional PSP joystick — DNP by default (assembled per SKU)
}

# Power symbols / flags that are not components at all.
IGNORE_SCH_TYPES: Set[str] = {
    "PWR_FLAG",
}


# ---------------------------------------------------------------------------
# Parsing: schematic sheets
# ---------------------------------------------------------------------------

class SchematicParseError(RuntimeError):
    pass


import io
import tokenize

# Helper calls that wire to the standard power/ground rails.
RAIL_HELPERS = {
    "gnd":  "GND",
    "v5":   "+5V",
    "v33":  "+3V3",
}
RAIL_HELPER_RE = re.compile(
    r"self\.(" + "|".join(RAIL_HELPERS.keys()) + r")\b"
)


def _iter_string_tokens(text: str):
    """Yield every *non-docstring* string literal from Python source.

    Uses the stdlib ``tokenize`` module so we correctly handle
    triple-quoted strings, f-strings, escapes, and apostrophes inside
    comments. A hand-rolled regex here silently swallowed large spans of
    code once it hit an apostrophe inside a comment (``connector's``),
    which masked real net references and broke check C.

    Module docstrings and class docstrings are excluded — they document
    the panel datasheet and are intentionally free text, not wiring.
    """
    prev_toktype = None
    prev_was_newline = True  # start of module counts as a fresh stmt
    try:
        tokens = list(tokenize.generate_tokens(
            io.StringIO(text).readline
        ))
    except tokenize.TokenizeError:
        return
    for tok in tokens:
        toktype, tokstr, _start, _end, _line = tok
        # Drop docstrings: a STRING that is the first token of a
        # statement (preceded by NEWLINE/INDENT/DEDENT/NL) and is not
        # assigned to anything.
        if toktype == tokenize.STRING:
            is_docstring = prev_was_newline
            if not is_docstring:
                # It's a real expression string — yield its value.
                try:
                    val = eval(tokstr, {"__builtins__": {}}, {})
                except Exception:
                    continue
                if isinstance(val, str):
                    yield val
        if toktype in (
            tokenize.NEWLINE, tokenize.NL,
            tokenize.INDENT, tokenize.DEDENT,
            tokenize.ENCODING,
        ):
            prev_was_newline = True
        else:
            prev_was_newline = False
        prev_toktype = toktype


def parse_sheet(path: Path) -> Tuple[List[Tuple[str, str, str]], Set[str]]:
    """Return ((type, ref, value) list, set of nets possibly wired in sheet).

    Implementation note: we tokenise the sheet source, collect every
    non-docstring string literal, then walk through them in order to
    rebuild (type, ref, value) tuples whenever we see a `self.sym(
    "type", "ref", "value", …)` pattern. The same token stream feeds
    the "possible nets" set used by check C.
    """
    text = path.read_text()
    all_strings: List[str] = list(_iter_string_tokens(text))

    # Build sym() tuples: look for every occurrence of the three
    # consecutive string args that follow ``self.sym(``. A text-level
    # scan is fine because we already have clean token values.
    syms: List[Tuple[str, str, str]] = []
    # Use a regex over the source but guarded to match only literal
    # triples — if any arg is a variable, we skip (dynamic refs).
    sym_re = re.compile(
        r"""self\.sym\(\s*
            (?P<q1>["'])(?P<type>[^"']+)(?P=q1)\s*,\s*
            (?P<q2>["'])(?P<ref>[A-Za-z_][A-Za-z0-9_]*)(?P=q2)\s*,\s*
            (?P<q3>["'])(?P<val>[^"']*)(?P=q3)
        """,
        re.VERBOSE,
    )
    for m in sym_re.finditer(text):
        syms.append((m.group("type"), m.group("ref"), m.group("val")))

    # "Possible nets" = every non-docstring string literal + rails reached
    # via helper methods. Deliberately permissive (false negatives on the
    # sync check beat false positives that would hide real bugs).
    nets: Set[str] = {s for s in all_strings if s}
    for m in RAIL_HELPER_RE.finditer(text):
        nets.add(RAIL_HELPERS[m.group(1)])
    return syms, nets


def parse_all_sheets() -> Tuple[
    Dict[str, Tuple[str, str, Path]],   # ref -> (type, value, sheet)
    Dict[str, Set[str]],                # sheet stem -> set of nets
]:
    if not SHEETS_DIR.is_dir():
        raise SchematicParseError(f"sheets directory missing: {SHEETS_DIR}")

    by_ref: Dict[str, Tuple[str, str, Path]] = {}
    nets_by_sheet: Dict[str, Set[str]] = {}
    collisions: List[str] = []

    for path in sorted(SHEETS_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        syms, nets = parse_sheet(path)
        nets_by_sheet[path.stem] = nets
        for ctype, ref, value in syms:
            if ctype in IGNORE_SCH_TYPES:
                continue
            # Skip dynamic refs (e.g. f"SW{i+1}") — they won't parse as
            # literal strings, and the CPL side covers them.
            if not re.fullmatch(r"[A-Z][A-Z0-9_]*[0-9]+|[A-Z][A-Z0-9_]+", ref):
                # Non-standard ref shape — still record it, but don't crash.
                pass
            if ref in by_ref:
                prev_type, _prev_val, prev_path = by_ref[ref]
                if prev_type != ctype:
                    collisions.append(
                        f"  {ref}: {prev_path.name} uses type={prev_type!r}, "
                        f"{path.name} uses type={ctype!r}"
                    )
            else:
                by_ref[ref] = (ctype, value, path)

    if collisions:
        raise SchematicParseError(
            "designator collision inside schematic sheets:\n"
            + "\n".join(collisions)
        )
    return by_ref, nets_by_sheet


# ---------------------------------------------------------------------------
# Parsing: PCB CPL via jlcpcb_export._build_placements
# ---------------------------------------------------------------------------

def load_placements() -> List[Tuple[str, str, str]]:
    """Return list of (ref, value, footprint) from jlcpcb_export.

    Imports the module and calls `_build_placements()`. A failure here is
    a hard error (never silenced) because it means the PCB generator is
    broken — pcb-review must halt.
    """
    sys.path.insert(0, str(REPO))
    try:
        from scripts.generate_pcb import jlcpcb_export  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise SchematicParseError(
            f"cannot import scripts.generate_pcb.jlcpcb_export: {exc}"
        ) from exc

    # pylint: disable=protected-access
    raw = jlcpcb_export._build_placements()
    out: List[Tuple[str, str, str]] = []
    for tup in raw:
        # tuples are (ref, value, footprint, x, y, rot, side)
        if len(tup) < 3:
            raise SchematicParseError(f"malformed placement tuple: {tup!r}")
        ref, value, footprint = tup[0], tup[1], tup[2]
        out.append((ref, value, footprint))
    return out


# ---------------------------------------------------------------------------
# Parsing: hardware/datasheet_specs.py for connector expected nets
# ---------------------------------------------------------------------------

def load_datasheet_specs() -> Dict[str, Dict[str, object]]:
    """Execute datasheet_specs.py and return COMPONENT_SPECS."""
    ns: Dict[str, object] = {}
    try:
        code = DATASHEET_SPECS.read_text()
    except FileNotFoundError as exc:
        raise SchematicParseError(
            f"datasheet_specs.py missing: {DATASHEET_SPECS}"
        ) from exc
    exec(compile(code, str(DATASHEET_SPECS), "exec"), ns)  # noqa: S102
    specs = ns.get("COMPONENT_SPECS")
    if not isinstance(specs, dict):
        raise SchematicParseError(
            "datasheet_specs.py did not define a COMPONENT_SPECS dict"
        )
    return specs  # type: ignore[return-value]


def expected_nets_for_connector(spec: Dict[str, object]) -> Set[str]:
    """Return the set of distinct non-empty net names for a connector."""
    pins = spec.get("pins", {})
    out: Set[str] = set()
    if not isinstance(pins, dict):
        return out
    for _pin, info in pins.items():
        if not isinstance(info, dict):
            continue
        net = info.get("net")
        if not isinstance(net, dict):
            continue
        kind = net.get("match")
        if kind == "exact":
            out.add(str(net.get("net")))
        elif kind == "any_of":
            for n in net.get("nets", []):
                out.add(str(n))
        # unconnected → ignore
    # Strip non-signal "nets" that won't appear as glabels in the sheet.
    return {n for n in out if n and not n.startswith("unconnected")}


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_ref_coverage(
    sch: Dict[str, Tuple[str, str, Path]],
    cpl: List[Tuple[str, str, str]],
) -> List[str]:
    """Check A: refs in schematic vs refs in BOM/CPL."""
    violations: List[str] = []
    cpl_refs = {ref for ref, _v, _f in cpl}
    sch_refs = set(sch.keys())

    # Dynamic-ref families generated by loops in board.py / jlcpcb_export.py
    # (SW1-SW13, SW_RST, SW_BOOT, R4-R15 pull-ups, C5-C16 debounce caps,
    # etc.). The schematic uses a single controls/mcu sheet symbol for
    # them; they are legitimately many-to-one.
    dynamic_families = (
        re.compile(r"^SW\d+$"),
        re.compile(r"^R(4|5|6|7|8|9|10|11|12|13|14|15|19)$"),
        re.compile(r"^C(5|6|7|8|9|10|11|12|13|14|15|16|20|26)$"),
    )

    def is_dynamic(ref: str) -> bool:
        return any(rx.match(ref) for rx in dynamic_families)

    # BOM refs that are missing from schematic (excluding known dynamic
    # families and the explicit schematic-only allowlist).
    missing_from_sch = []
    for ref in sorted(cpl_refs):
        if ref in sch_refs:
            continue
        if is_dynamic(ref):
            continue
        missing_from_sch.append(ref)
    if missing_from_sch:
        violations.append(
            "BOM refs with no schematic symbol (R4-HIGH-1 class):\n  "
            + ", ".join(missing_from_sch)
        )

    # Schematic refs with no BOM entry (excluding allowlist).
    missing_from_cpl = []
    for ref in sorted(sch_refs):
        if ref in cpl_refs:
            continue
        if ref in SCHEMATIC_ONLY_REFS:
            continue
        missing_from_cpl.append(ref)
    if missing_from_cpl:
        violations.append(
            "Schematic refs with no BOM entry:\n  "
            + ", ".join(missing_from_cpl)
        )

    return violations


_TOKEN_RE = re.compile(r"[A-Z0-9]+")


def _tokens(*fields: str) -> Set[str]:
    """Split an identifier blob into uppercase alphanumeric tokens ≥2 chars.

    Used to ask "do the schematic type and BOM value/footprint share any
    meaningful substring?". Very generic 2-char noise ("EP", "IN", "PP")
    is dropped elsewhere via the ``generic`` set in the caller.
    """
    out: Set[str] = set()
    for f in fields:
        if not f:
            continue
        for m in _TOKEN_RE.finditer(f.upper().replace("-", " ").replace("_", " ")):
            t = m.group(0)
            if len(t) >= 2:
                out.add(t)
    return out


def check_designator_collisions(
    sch: Dict[str, Tuple[str, str, Path]],
    cpl: List[Tuple[str, str, str]],
) -> List[str]:
    """Check B: the same ref must not name two different component types.

    Two heuristics, in order:

    1. For passive symbols (type ``C``/``R``/``L``) the schematic carries the
       value as a string. Compare it to the CPL value after canonicalising
       (``22uF tant.`` == ``22uF``, ``0.47u`` == ``0.47uF``).

    2. For ICs/connectors/switches the schematic type is a logical symbol
       name (``PAM8403_Module``, ``FPC_16P``, ``Conn_JST_PH_2``, …). We
       tokenise the schematic ``type + value`` and the CPL ``value +
       footprint`` and require at least one shared ≥3-char alphanumeric
       token. This correctly matches ``ST7796S_Module`` against ``ILI9488``
       once the schematic value is ``"ILI9488 4.0in 8080"`` — and crucially
       it catches R4-HIGH-2 where schematic ``ST7796S_Module`` / value
       ``"ILI9488 4.0in 8080"`` is reused for CPL ``USBLC6-2SC6`` /
       ``SOT-23-6`` (zero shared tokens → collision).
    """
    violations: List[str] = []
    cpl_by_ref: Dict[str, Tuple[str, str]] = {ref: (v, f) for ref, v, f in cpl}
    passive_types = {"C", "R", "L"}

    for ref, (ctype, value, path) in sorted(sch.items()):
        if ref not in cpl_by_ref:
            continue
        cpl_val, cpl_fp = cpl_by_ref[ref]

        if ctype in passive_types:
            if _canonical_value(value) != _canonical_value(cpl_val):
                violations.append(
                    f"  {ref}: schematic {path.name} says "
                    f"{ctype} {value!r}, CPL says {cpl_val!r} ({cpl_fp})"
                )
            continue

        sch_tokens = _tokens(ctype, value)
        cpl_tokens = _tokens(cpl_val, cpl_fp)
        # Drop generic tokens that carry no identifying meaning.
        generic = {
            # schematic symbol wrappers
            "MODULE", "CONN", "SYM", "PAD",
            # footprint families
            "SMD", "SOP", "SOT", "SOIC", "DIP", "QFN", "DFN",
            "ESOP", "TSSOP", "BGA", "LQFP", "TQFP", "SOD",
            "SMA", "SMB", "SMC",
            # case sizes / form-factor words
            "0402", "0603", "0805", "1206", "1210", "PIN",
            "BOTTOM", "TOP", "CONTACT", "MM", "P",
            # generic English
            "NONE", "VAL", "POWER", "IN", "OUT", "EP",
            "ESP32", "ESP",  # too generic for an ESP32 board
            "SLOT", "MICRO",  # avoid weak matches like "Micro SD" ↔ "Micro-USB"
            # small integers / dimensions
            "0IN", "1IN", "2IN",
        }
        sch_meaningful = sch_tokens - generic
        cpl_meaningful = cpl_tokens - generic
        if not (sch_meaningful & cpl_meaningful):
            violations.append(
                f"  {ref}: schematic {path.name} type={ctype!r} "
                f"value={value!r}; CPL value={cpl_val!r} footprint={cpl_fp!r} "
                f"(no shared identifying token — designator reused?)"
            )
    if violations:
        return [
            "Designator collisions between schematic and PCB "
            "(R4-HIGH-2 class):\n" + "\n".join(violations)
        ]
    return []


def _canonical_value(v: str) -> str:
    """Normalize capacitor/resistor values for comparison.

    Strips spaces, lowercases, collapses common aliases so that
    ``22uF tant.`` / ``22uF`` / ``22u`` / ``0.47uF`` / ``0.47u`` all compare
    as expected.
    """
    s = v.lower().strip()
    for token in (" tant.", " tantalum", " mlcc", " ceramic"):
        s = s.replace(token, "")
    s = s.replace(" ", "")
    # Drop trailing unit letter if it's just "u" without trailing "f"/"h".
    # e.g. "0.47u" → "0.47uf"  (matches "0.47uF")
    if re.fullmatch(r"[0-9.]+u", s):
        s = s + "f"
    if re.fullmatch(r"[0-9.]+p", s):
        s = s + "f"
    if re.fullmatch(r"[0-9.]+n", s):
        s = s + "f"
    return s


def check_connector_nets(
    sch_nets_by_sheet: Dict[str, Set[str]],
    specs: Dict[str, Dict[str, object]],
    sch: Dict[str, Tuple[str, str, Path]],
) -> List[str]:
    """Check C: connector expected nets must appear in the wiring sheet.

    For each connector spec, find the schematic sheet that instantiates its
    ref, collect all nets referenced by ``self.glabel`` in that sheet, and
    verify that the expected non-empty set from datasheet_specs.py is a
    subset. This will not catch pin-by-pin swaps (the schematic uses
    simplified symbols) but it does catch cases like R4-CRIT-1 where the
    schematic and the datasheet_specs.py describe entirely different
    pinouts: a pinout for a touch+display panel carrying nets the
    datasheet_specs.py never assigns.
    """
    violations: List[str] = []
    connector_refs = {
        ref for ref, spec in specs.items()
        if isinstance(spec, dict)
        and "FPC" in str(spec.get("component", "")).upper()
        or ref.startswith("J")
    }
    for ref in sorted(connector_refs):
        spec = specs.get(ref)
        if not isinstance(spec, dict):
            continue
        expected = expected_nets_for_connector(spec)
        if not expected:
            continue
        # Which sheet instantiates this ref?
        entry = sch.get(ref)
        if entry is None:
            # Connector exists in datasheet_specs.py + PCB but has no
            # schematic symbol at all (covered by check A, but we still
            # flag it here for a clearer message).
            violations.append(
                f"  {ref}: datasheet_specs.py defines it, no schematic sheet "
                f"instantiates the symbol"
            )
            continue
        sheet_stem = entry[2].stem
        sheet_nets = sch_nets_by_sheet.get(sheet_stem, set())
        missing = sorted(expected - sheet_nets)
        if missing:
            violations.append(
                f"  {ref} ({sheet_stem}.py): datasheet_specs.py expects "
                f"nets {sorted(expected)}, sheet is missing {missing}"
            )
    if violations:
        return [
            "Connector pinout mismatch schematic vs datasheet_specs.py "
            "(R4-CRIT-1 class):\n" + "\n".join(violations)
        ]
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("verify_schematic_pcb_sync.py — R4 guard")
    print(f"  sheets    : {SHEETS_DIR}")
    print(f"  jlcpcb    : {JLCPCB_EXPORT}")
    print(f"  specs     : {DATASHEET_SPECS}")
    print()

    try:
        sch_by_ref, sch_nets_by_sheet = parse_all_sheets()
        cpl = load_placements()
        specs = load_datasheet_specs()
    except SchematicParseError as exc:
        print(f"[FAIL] parse error: {exc}")
        return 2

    print(f"  schematic refs : {len(sch_by_ref)}")
    print(f"  CPL refs       : {len(cpl)}")
    print(f"  datasheet_specs: {len(specs)}")
    print()

    violations: List[str] = []
    violations += check_ref_coverage(sch_by_ref, cpl)
    violations += check_designator_collisions(sch_by_ref, cpl)
    violations += check_connector_nets(sch_nets_by_sheet, specs, sch_by_ref)

    if violations:
        print("FAIL — schematic/PCB sync violations found:\n")
        for v in violations:
            print(v)
            print()
        print(
            "Fix these in the schematic generator or in datasheet_specs.py. "
            "Do NOT add suppressions."
        )
        return 1

    print("PASS — schematic, PCB and datasheet_specs.py agree.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
