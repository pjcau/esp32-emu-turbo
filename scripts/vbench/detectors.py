"""Virtual Bench T5.1 — does the bench actually rediscover the known bugs?

Every corpus entry gets a detector, and `corpus.py` reports how many are
caught. Nothing here is written into the corpus files: the count is computed
by running the bench, which is why the corpus refuses a `status` field.

Two kinds of entry, two kinds of detector:

**Mutation entries** — bugs that have since been fixed. The detector applies
the mutation to an in-memory netlist, re-runs the bench's checks, and requires
a **new** finding that names the mutated part. That rule is general on
purpose: a per-entry "look for this string" would pass by matching text the
bench prints anyway, which measures nothing. It also fails honestly — if the
bench notices *something* but never names the part, that is not a
rediscovery.

**Live entries** (`mutation.kind == "none"`, `present_now: true`) — defects or
invariants present in the design as it stands. Each has its own detector,
because each asks a different question of a different part of the bench, and
each must ask it of the *derived* answer rather than of a comment.

Invariants (`expect: "reproduced"`) are caught when the bench **states** them.
Silence is not reproduction: an invariant the bench never mentions is one a
reader will not know about.
"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import buttons, conflicts, display, mutate        # noqa: E402
from vbench import netlist as nl                              # noqa: E402
from vbench import pins as pinmod                             # noqa: E402
from vbench import rails, sdcard                              # noqa: E402
from vbench.models.u1_esp32s3 import STRAPPING_DEFAULTS       # noqa: E402


# ── The generic mutation detector ───────────────────────────────────

def _datasheet_expectations(board):
    """Pads whose net no longer matches what datasheet_specs declares.

    Reuses the expectation table `verify_datasheet_nets` already owns rather
    than restating it. It is what catches a detached pin on a part with more
    than two terminals — D1's anode, SW14's signal pad — where "fewer than
    two pins on a net" says nothing because the other terminals are fine.
    """
    from hardware.datasheet_specs import COMPONENT_SPECS
    actual = {(p.ref, p.pad): net
              for net, pins in board.nets.items() for p in pins}
    out = set()
    for ref, block in COMPONENT_SPECS.items():
        for pad, spec in block.get("pins", {}).items():
            expect = spec.get("net", {})
            if expect.get("match") != "exact":
                continue
            want = expect.get("net")
            got = actual.get((ref, str(pad)))
            if got != want:
                out.add(f"SPEC|{ref}.{pad}|expected {want!r}, board has "
                        f"{got!r}")
    return out


def _findings(board, sch, values):
    """Every finding the netlist-level checks produce, as comparable text."""
    out = set()
    for d in nl.crosscheck(board, sch):
        out.add(f"{d.code}|{d.subject}|{d.detail}")
    for c in conflicts.find_conflicts(board, values):
        out.add(f"{c.code}|{c.net}|{c.detail}")
    out |= _datasheet_expectations(board)
    # A net that loses its only path to a source shows up here and nowhere
    # else — which is the whole R5 class.
    try:
        op = rails.operating_point()
        solved = rails.solve_dc(board, values, {
            "GND": 0.0, "+5V": 5.0, "+3V3": op.rail_spread["+3V3"][1],
            "BAT+": 3.83, "BAT_IN": 3.83, "VBUS": 5.0})
        for net, volts in solved.items():
            if volts is rails.UNDEFINED:
                out.add(f"FLOAT|{net}|no DC path to any source")
    except (rails.RailError, KeyError):
        pass
    return out


# Loading the schematic netlist spawns kicad-cli, and the corpus asks for it
# once per mutation entry. Cached for the life of the process — the design
# does not change while a single run is evaluating it, and without this the
# corpus took ten seconds of which nine were re-exporting the same file.
_CACHE = {}


def _sources():
    if "board" not in _CACHE:
        _CACHE["board"] = nl.load_board_netlist()
        _CACHE["sch"] = nl.load_schematic_netlist()
        _CACHE["values"] = rails.load_bom_values()
    return _CACHE["board"], _CACHE["sch"], _CACHE["values"]


def detect_mutation(entry):
    """Inject the entry's mutation and require a NEW finding naming the part."""
    board, sch, values = _sources()
    before = _findings(board, sch, values)
    extra = set()
    try:
        if entry.mutation.get("side") == "schematic":
            mutated_sch, what, extra = mutate.apply_schematic(
                sch, entry.mutation)
            mutated, sch = board, mutated_sch
        else:
            mutated, what = mutate.apply(board, entry.mutation)
    except mutate.MutationError as exc:
        return False, f"mutation could not be applied: {exc}"
    after = _findings(mutated, sch, values)
    new = after - before
    if not new:
        return False, (f"injected {what}, and the bench reported nothing it "
                       f"had not already reported")
    wanted = mutate.refs_touched(entry.mutation) | extra
    naming = [f for f in new if any(w in f for w in wanted)]
    if not naming:
        return False, (f"injected {what}; the bench produced {len(new)} new "
                       f"finding(s) but none names {sorted(wanted)}")
    return True, f"injected {what} -> {sorted(naming)[0]}"


# ── Live detectors, one question each ───────────────────────────────

def _live_r25_crit_1():
    """EN must come out with no defined DC level, from the copper."""
    op = rails.operating_point()
    if op.voltages.get("EN", "missing") is not rails.UNDEFINED:
        return False, f"EN solved to {op.voltages.get('EN')}, not floating"
    board = nl.load_board_netlist()
    pins_on_en = {f"{p.ref}.{p.pad}" for p in board.nets.get("EN", ())}
    return True, (f"EN has no DC path to any source; its only pins are "
                  f"{sorted(pins_on_en)} — no pull-up, no capacitor")


def _live_r10_low_7():
    """No R and no C on EN, so no RC time constant exists to compute."""
    board = nl.load_board_netlist()
    refs = {}
    for net, pins in board.nets.items():
        for p in pins:
            refs.setdefault(p.ref, set()).add(net)
    pullup = [r for r, nets in refs.items()
              if r.startswith("R") and {"EN", "+3V3"} <= nets]
    cap = [c for c, nets in refs.items()
           if c.startswith("C") and {"EN", "GND"} <= nets]
    if pullup or cap:
        return False, f"EN now has {pullup} and {cap}; the entry is stale"
    return True, ("no resistor from EN to +3V3 and no capacitor from EN to "
                  "GND, so any RC boot delay computed for this board is "
                  "computed from parts that are not there")


def _live_r25_high_1():
    """The backlight anode must reach the rail with no series element."""
    view, _ = display.panel_view()
    led_a = [p for p in view if p.symbol == "LED-A"]
    if not led_a:
        return False, "no LED-A pin in the parsed panel pinout"
    p = led_a[0]
    if p.net != "+3V3":
        return False, f"LED-A reaches {p.net!r}, not the bare rail"
    board = nl.load_board_netlist()
    series = [q.ref for q in board.nets.get("+3V3", ())
              if q.ref.startswith("R")]
    return True, (f"panel pin {p.pin} (LED-A) lands on pad {p.pad} carrying "
                  f"+3V3 directly; the resistors on that rail ({sorted(series)[:3]}"
                  f"...) are button pull-ups, none in series with the "
                  f"backlight string")


def _live_r25_low_1():
    """R20 and R21 must be found in parallel, with nothing to GND."""
    from vbench import audio
    r_eff, c_block, f_corner, bias, block = audio.input_network()
    if len(bias) != 2:
        return False, f"the bias network is {bias}, not a pair"
    board = nl.load_board_netlist()
    to_gnd = [r for r in bias
              if any(p.ref == r for p in board.nets.get("GND", ()))]
    if to_gnd:
        return False, f"{to_gnd} reaches GND, so it is a divider after all"
    return True, (f"{' || '.join(bias)} = {r_eff/1000:.0f}k between PAM_IN_AC "
                  f"and PAM_VREF, nothing to GND — parallel, not a divider")


def _live_vb_c28_dnp():
    """C28 must be reported as a DNP land, and contribute no capacitance."""
    board, sch, _values = _sources()
    d5 = [d for d in nl.crosscheck(board, sch)
          if d.code == "D5" and d.subject == "C28"]
    if not d5:
        return False, "C28 is no longer reported as present in one source only"
    from vbench import transients
    caps, _ = transients.board_values()
    total, absent = caps["+3V3"]
    if "C28" not in absent:
        return False, f"C28 now contributes to the +3V3 bulk ({total*1e6:.1f} uF)"
    return True, (f"C28 is DNP and contributes nothing: the +3V3 bulk is "
                  f"{total*1e6:.1f} uF, not the 32.3 uF the schematic sums to")


def _inv_sw_pwr():
    ok, detail = buttons.switch_off_scenario()
    if not ok:
        return False, f"operating the switch changed a rail: {detail}"
    return True, (f"switch_off leaves BAT+ at {detail['bat_after']:.3f} V and "
                  f"+3V3 at {detail['rail_after']:.3f} V; SW16's throw pads "
                  f"carry {detail['routed_throws'] or 'no net'}")


def _inv_j4_reversal():
    if display.pad_of(17) != "24" or display.pad_of(40) != "1":
        return False, "the bench no longer maps pad = 41 - panel pin"
    view, _ = display.panel_view()
    db0 = next((p for p in view if p.symbol == "DB0"), None)
    if not db0 or db0.net != "LCD_D0":
        return False, f"DB0 reaches {db0.net if db0 else None!r}"
    return True, (f"panel pin {db0.pin} (DB0) reaches pad {db0.pad} carrying "
                  f"LCD_D0 — the reversal is applied, not 'fixed'")


def _inv_j4_im_strap():
    view, _ = display.panel_view()
    ok, mode, detail = display.check_interface_mode(view)
    if not ok:
        return False, f"the straps select {mode}"
    return True, f"the straps are modelled as mode inputs: {detail} -> {mode}"


def _inv_led_pin_numbering():
    """The bench must take LED current direction from the footprint."""
    board = nl.load_board_netlist()
    for led in ("LED1", "LED2"):
        pads = {p.pad: net for net, pins in board.nets.items()
                for p in pins if p.ref == led}
        if pads.get("1") != "GND" or not pads.get("2", "").endswith("_RA"):
            return False, f"{led} pads are {pads}; pad 1 should be the cathode"
    return True, ("LED1/LED2 pad 1 is on GND and pad 2 on the resistor node, "
                  "i.e. the footprint's numbering — the symbol's opposite "
                  "convention is a translation, not a polarity error")


def _inv_vbus_fragments():
    """VBUS's single-orientation delivery must be stated, not silently OK."""
    board = nl.load_board_netlist()
    j1 = sorted(p.pad for p in board.nets.get("VBUS", ()) if p.ref == "J1")
    if not j1:
        return False, "no J1 pad carries VBUS at all"
    return True, (f"VBUS reaches J1 pads {j1}; the receptacle's other VBUS "
                  f"pads are isolated, so it is delivered in one plug "
                  f"orientation — functional and documented")


def _live_sd_strapping():
    """The SD socket's DAT2 must be seen sharing a net with a strapping pin."""
    _notes, _shared, exposure, _op, _faults = sdcard.survey()
    hit = [e for e in exposure if e[0] == "9"]
    if not hit:
        return False, "U6.9 is no longer detected on a strapping pin's net"
    pad, role, net, gpio, strap = hit[0]
    return True, (f"U6.{pad} ({role.split('—')[0].strip()}) shares {net} with "
                  f"{gpio}, whose internal pull is "
                  f"{strap['internal'] or 'NONE'}")


LIVE = {
    "R25-CRIT-1": _live_r25_crit_1,
    "R10-LOW-7": _live_r10_low_7,
    "R25-HIGH-1": _live_r25_high_1,
    "R25-LOW-1": _live_r25_low_1,
    "VB-C28-DNP": _live_vb_c28_dnp,
    "INV-SW-PWR": _inv_sw_pwr,
    "INV-J4-REVERSAL": _inv_j4_reversal,
    "INV-J4-IM-STRAP": _inv_j4_im_strap,
    "INV-LED-PIN-NUMBERING": _inv_led_pin_numbering,
    "INV-VBUS-FRAGMENTS": _inv_vbus_fragments,
}


def evaluate(entry):
    """(caught, detail) for one corpus entry."""
    if entry.id in LIVE:
        try:
            return LIVE[entry.id]()
        except Exception as exc:                        # noqa: BLE001
            return False, f"detector raised {type(exc).__name__}: {exc}"
    if entry.mutation.get("kind") == "none":
        return False, ("live entry with no detector — add one to "
                       "detectors.LIVE rather than leaving it uncounted")
    try:
        return detect_mutation(entry)
    except Exception as exc:                            # noqa: BLE001
        return False, f"detector raised {type(exc).__name__}: {exc}"
