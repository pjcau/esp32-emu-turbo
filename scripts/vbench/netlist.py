"""Virtual Bench T0.1 — the netlist the bench stands on, and its disputes.

Builds `{net_name: [PinRef(ref, pin, pad, layer)]}` from the `.kicad_pcb`
(through `pcb_cache.load_cache()`, never by reading the 265k-token board
file) and cross-checks it against the schematic netlist exported by
`kicad-cli`.

Two rules from docs/virtual-bench-plan.md are load-bearing here:

  1. **The PCB netlist is the truth**, because the PCB is what gets
     fabricated. The schematic is the cross-check, and a disagreement is a
     bench-blocking error, not a warning.
  2. The bench runs against **two netlists and reports the delta** — the
     tag of the fabricated revision, so results are comparable to
     prototype #1, and the working tree, so the revision being designed is
     the one under test. `--delta` does that.

## Why this is not a fork of verify_netlist_diff

`verify_netlist_diff` owns the hard part: the table that translates a
logical schematic pin into the footprint pads it actually is
(`SCH_PIN_TO_PCB_PADS`), plus the four evidence-backed allowlists. That
table is imported here, never copied — a second copy would drift the first
time a connector is re-symboled, and the drift would be invisible because
both files would still pass their own checks.

What this module adds is the class of dispute that gate structurally
cannot see. `verify_netlist_diff` compares **names** (T1/T2), **refs**
(T3) and **pins that exist on both sides** (T4). A net that exists by name
in both files while carrying no pin on either is therefore green in all
four tests — and `LCD_BL` and `LCD_RD` are exactly that today. So is a net
with a single pin, which is a label, not a circuit. Those are the checks
here, and they are the reason "every net in the board resolves to a pin
list" is worded the way it is in the plan.

Usage:
    python3 scripts/vbench/netlist.py                # working tree
    python3 scripts/vbench/netlist.py --rev v4.3.1   # a git revision
    python3 scripts/vbench/netlist.py --delta        # tree vs fabricated
    python3 scripts/vbench/netlist.py --json
"""

import argparse
import collections
import json
import os
import pathlib
import re
import subprocess
import sys
import tarfile
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import build_cache, load_cache          # noqa: E402
import verify_netlist_diff as vnd                       # noqa: E402
# DNP_REFS is derived, not listed: verify_bom_cpl_pcb executes
# jlcpcb_export._build_placements() and calls every board footprint absent
# from the CPL a DNP. Imported rather than re-derived so "is this part
# actually assembled?" has one answer in the repo.
from verify_bom_cpl_pcb import DNP_REFS, HAND_ASSEMBLED  # noqa: E402
# The second source that checks a pad's net. verify_datasheet_nets compares
# every pad declared here against its expected net (267 checks today), so a
# pad the schematic symbol does not represent is not automatically a pad
# nobody checks — see the D3 note in crosscheck().
from hardware.datasheet_specs import COMPONENT_SPECS      # noqa: E402

PCB_REL = os.path.join("hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

# The revision prototype #1 was fabricated from. Single source for this
# fact: docs/known-issues.md:294-296 ("the fabricated board = the design
# at the latest release tag, currently v4.3.1 (2026-04-16) — this is what
# prototype #1 is"). Not guessed from `git tag | tail -1`: the newest tag
# is whatever was cut last, which is not the same claim.
#
# If this tag stops existing, `--delta` raises instead of quietly
# comparing the tree against itself.
FABRICATED_REV = "v4.3.1"


class NetlistError(RuntimeError):
    """Raised when the netlist cannot be built at all.

    Distinct from a dispute: a dispute is a finding about the design, this
    is the bench being unable to look. Never downgraded to a warning —
    a bench that cannot read the board must not print a verdict.
    """


PinRef = collections.namedtuple("PinRef", "ref pin pad layer")

# code     — stable identifier, so a dispute can be cited in a commit
# subject  — the thing at fault (net name, ref.pin)
# side     — which source the finding is about: pcb / sch / both
# owner    — the file that has to change; "unknown" is allowed and means
#            the dispute is real but unattributed, never that it is minor
# rank     — ordering *within* a class only. It never suppresses and never
#            downgrades: every dispute prints and every dispute blocks.
Dispute = collections.namedtuple("Dispute", "code subject side owner detail rank")
Dispute.__new__.__defaults__ = (0,)


# ── Board side ──────────────────────────────────────────────────────

def _pad_to_sch_pin(ref):
    """Invert SCH_PIN_TO_PCB_PADS for one ref: {pad: sch_pin}.

    Returns None for refs with no map, meaning pad number == pin number.
    """
    ref_map = vnd.SCH_PIN_TO_PCB_PADS.get(ref)
    if ref_map is None:
        return None
    inverted = {}
    for sch_pin, pads in ref_map.items():
        for pad in pads:
            # A pad claimed by two schematic pins would make the
            # translation ambiguous, which is a bug in the table itself.
            if pad in inverted and inverted[pad] != sch_pin:
                raise NetlistError(
                    f"SCH_PIN_TO_PCB_PADS[{ref!r}] maps pad {pad} to both "
                    f"pin {inverted[pad]} and pin {sch_pin}")
            inverted[pad] = sch_pin
    return inverted


class BoardNetlist:
    """The board's electrical connectivity as pin lists, per net."""

    def __init__(self, cache, origin):
        self.origin = origin                 # "working tree" or a git rev
        self.pcb_hash = cache.get("pcb_hash", "")
        id_to_name = {n["id"]: n["name"] for n in cache.get("nets", [])}
        self.declared_nets = {n for n in id_to_name.values() if n}

        # Pads are emitted once per copper layer, so collect layers per
        # (ref, pad) instead of keeping the first occurrence and losing
        # the fact that a THT pad is on both.
        layers = collections.defaultdict(set)
        pad_net = {}
        for pad in cache.get("pads", []):
            ref, num = pad.get("ref", ""), str(pad.get("num", ""))
            if not ref or not num:
                continue
            key = (ref, num)
            layers[key].add(pad.get("layer", "?"))
            net = id_to_name.get(pad.get("net", 0), "")
            if net:
                pad_net.setdefault(key, net)

        pin_maps = {ref: _pad_to_sch_pin(ref)
                    for ref in {r for r, _ in layers}}

        nets = collections.defaultdict(list)
        self.pads_without_pin = []
        for (ref, pad), net in sorted(pad_net.items()):
            pmap = pin_maps.get(ref)
            if pmap is None:
                pin = pad
            else:
                pin = pmap.get(pad)
                if pin is None:
                    # The ref has a translation table and this pad is not
                    # in it. Recorded, not skipped: on a mapped ref an
                    # unlisted pad is a hole in the table, and a hole is
                    # how a pin escapes every cross-check.
                    self.pads_without_pin.append((ref, pad, net))
            nets[net].append(
                PinRef(ref, pin, pad, " ".join(sorted(layers[(ref, pad)]))))

        self.nets = {k: tuple(v) for k, v in sorted(nets.items())}
        self.refs = set(cache.get("refs", []))
        # Filled by crosscheck(): pads the schematic does not represent but
        # datasheet_specs does. Not disputes — verify_datasheet_nets owns
        # them — but the bench must know they exist, because a model built
        # from the schematic alone would be missing them.
        self.pads_only_in_datasheet = []

        # Copper carried by each net, so "no pins" can be told apart from
        # "no copper either" — a name with neither is a pure phantom.
        self.net_types = dict(cache.get("net_types", {}))
        self.copper_items = collections.Counter()
        for seg in cache.get("segments", []):
            self.copper_items[id_to_name.get(seg.get("net", 0), "")] += 1
        for via in cache.get("vias", []):
            self.copper_items[id_to_name.get(via.get("net", 0), "")] += 1
        self.zone_nets = {z.get("net_name", "") for z in cache.get("zones", [])}

    def pin_nets(self):
        """{(ref, pad): net} — the T4 comparison key, pad-numbered."""
        return {(p.ref, p.pad): net
                for net, pins in self.nets.items() for p in pins}


def load_board_netlist(rev=None):
    """Build the board netlist from the working tree or from a git rev."""
    pcb = os.path.join(BASE, PCB_REL)
    if rev is None:
        if not os.path.exists(pcb):
            raise NetlistError(f"board file missing: {PCB_REL}")
        return BoardNetlist(load_cache(pcb), "working tree")

    _require_rev(rev)
    tmp = tempfile.mkdtemp(prefix="vbench-")
    checked_out = os.path.join(tmp, "esp32-emu-turbo.kicad_pcb")
    with open(checked_out, "wb") as fh:
        proc = subprocess.run(["git", "show", f"{rev}:{PCB_REL}"],
                              cwd=BASE, stdout=fh, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise NetlistError(
            f"cannot read {PCB_REL} at {rev}: {proc.stderr.decode().strip()}")
    # Explicit cache path inside the temp dir: the default would sit next
    # to the checked-out file anyway, but being explicit keeps the
    # revision's cache from ever being mistaken for the tree's.
    cache = build_cache(pathlib.Path(checked_out),
                        pathlib.Path(tmp) / ".pcb_cache.json")
    return BoardNetlist(cache, rev)


def _export_schematic_at_rev(rev):
    """Extract hardware/kicad at `rev` and export its netlist. Returns path.

    The whole directory, not just the root .kicad_sch: the design is a
    sheet set, and a root sheet without its siblings exports an empty
    netlist — which would read as "the schematic has no nets" instead of
    as an error.
    """
    _require_rev(rev)
    tmp = tempfile.mkdtemp(prefix="vbench-sch-")
    tar_path = os.path.join(tmp, "kicad.tar")
    proc = subprocess.run(
        ["git", "archive", "--format=tar", f"--output={tar_path}", rev,
         "hardware/kicad"],
        cwd=BASE, capture_output=True, text=True)
    if proc.returncode != 0:
        raise NetlistError(
            f"cannot extract hardware/kicad at {rev}: {proc.stderr.strip()}")
    with tarfile.open(tar_path) as tar:
        tar.extractall(tmp)
    sch = os.path.join(tmp, "hardware", "kicad", "esp32-emu-turbo.kicad_sch")
    if not os.path.exists(sch):
        raise NetlistError(f"no schematic at {rev}: {sch}")
    out = os.path.join(tmp, "netlist.xml")
    proc = subprocess.run(
        ["kicad-cli", "sch", "export", "netlist", "--format", "kicadxml",
         "--output", out, sch],
        capture_output=True, text=True, timeout=120)
    if proc.returncode != 0 or not os.path.exists(out):
        raise NetlistError(
            f"kicad-cli could not export the schematic at {rev} "
            f"(rc={proc.returncode}): {proc.stderr.strip()}")
    return out


def _require_rev(rev):
    proc = subprocess.run(["git", "rev-parse", "--verify", f"{rev}^{{commit}}"],
                          cwd=BASE, capture_output=True, text=True)
    if proc.returncode != 0:
        raise NetlistError(
            f"git revision {rev!r} does not exist. If this is "
            f"FABRICATED_REV, the tag prototype #1 was built from has been "
            f"renamed or deleted — fix the constant against "
            f"docs/known-issues.md rather than falling back to HEAD.")


# ── Schematic side ──────────────────────────────────────────────────

class SchematicNetlist:
    """The schematic's connectivity, exported by kicad-cli."""

    def __init__(self, nets, comps, pin_nets):
        self.nets = nets            # {net: tuple((ref, pin))}
        self.refs = comps
        self.pin_nets = pin_nets    # {(ref, pin): net}


def load_schematic_netlist(rev=None):
    """Export and parse the schematic netlist for one revision.

    `rev` must match the revision the board came from. Comparing an old
    board against today's schematic manufactures mismatches that belong to
    neither revision — at v4.3.1 that alone invents eleven of them — so the
    two sources are always taken from the same commit.
    """
    if rev is None:
        if not vnd.export_netlist():
            raise NetlistError(
                "kicad-cli could not export the schematic netlist — the bench "
                "has only one of its two sources and cannot cross-check")
        netlist_path = vnd.NETLIST_TMP
    else:
        netlist_path = _export_schematic_at_rev(rev)
    sch_nets, sch_comps, sch_pin_nets = vnd.parse_netlist(netlist_path)
    nets = collections.defaultdict(list)
    for (ref, pin), net in sorted(sch_pin_nets.items()):
        nets[net].append((ref, pin))
    for net in sch_nets:
        nets.setdefault(net, [])
    return SchematicNetlist({k: tuple(v) for k, v in sorted(nets.items())},
                            sch_comps, sch_pin_nets)


# ── Cross-check ─────────────────────────────────────────────────────

def crosscheck(board, sch):
    """Every dispute between the two sources, worst class first.

    Allowlists are imported from verify_netlist_diff, so an exception has
    to be argued once, in the file that already holds the evidence for it.
    No allowlist is defined in this module.
    """
    disputes = []

    # D1 — a net name in the board with no pad on it. Neither T1 nor T2
    # can see this: both files declare the name, so the name comparison
    # matches, and T4 iterates over schematic pins, of which this net has
    # none on the board side.
    for net in sorted(board.declared_nets):
        if net in board.nets:
            continue
        disputes.append(Dispute(
            "D1", net, "pcb", "unknown",
            f"no pad carries it; {board.copper_items[net]} track/via "
            f"item(s), {'in a zone' if net in board.zone_nets else 'no zone'}"))

    # D2 — a net with exactly one pin. Current has to leave somewhere, so
    # a one-pin net is either an unfinished connection or a label that
    # should not be a net. Reported per side, because the two sources
    # disagree about which nets these are.
    for net, pins in board.nets.items():
        if len(pins) != 1 or net in vnd.T1_ALLOW:
            continue
        p = pins[0]
        disputes.append(Dispute(
            "D2", net, "pcb", "unknown",
            f"single pin {p.ref}.{p.pad} — no second pin for current to "
            f"reach; {board.copper_items[net]} track/via item(s)"))

    for net, nodes in sch.nets.items():
        if len(nodes) != 1 or net in vnd.T1_ALLOW or vnd._is_pcb_internal(net):
            continue
        ref, pin = nodes[0]
        why = ""
        if ref in vnd.T3_ALLOW:
            why = (f" — {ref} is a footprint-less logical symbol "
                   f"(T3_ALLOW), so this requirement exists on no copper")
        elif ref in vnd.EXCLUDED_REFS:
            why = f" — {ref} is excluded from cross-checks (EXCLUDED_REFS)"
        disputes.append(Dispute(
            "D2", net, "sch", "schematic generator",
            f"single node {ref}.{pin}{why}"))

    # D3 — a pad that carries a net but that NO source accounts for.
    #
    # The first version of this check reported every pad the schematic
    # translation table does not list, and called them "compared by
    # nothing". That was wrong, and the correction is worth keeping
    # visible: all 17 such pads on this board are declared in
    # `hardware/datasheet_specs.py`, where verify_datasheet_nets compares
    # each one's net against an expected value. The four most suspicious —
    # U6.8/U6.9 on the SD data lines and SW16.4b/4d on BTN_SELECT — turn
    # out to be deliberate same-net fixups with a written safety analysis
    # (routing.py:6055-6085) that a hard gate protects.
    #
    # A check that fires on all seventeen therefore discriminates nothing.
    # The real hole is a pad in NEITHER source: absent from the schematic
    # symbol and undeclared in datasheet_specs, so its net is whatever the
    # copper happened to inject (board._inject_pad_net) and no expectation
    # exists to contradict it. That set is empty today, which is the
    # correct answer, not a missing check — see test_vbench.py, which
    # injects one and requires it to fire.
    board.pads_only_in_datasheet = []
    for ref, pad, net in board.pads_without_pin:
        declared = pad in COMPONENT_SPECS.get(ref, {}).get("pins", {})
        if declared:
            board.pads_only_in_datasheet.append((ref, pad, net))
            continue
        kind = board.net_types.get(net, "signal")
        disputes.append(Dispute(
            "D3", f"{ref} pad {pad}", "pcb", "unknown",
            f"carries {net!r} ({kind}) with no schematic pin and no "
            f"datasheet_specs entry — nothing states what this pad should "
            f"be on", 0 if kind == "signal" else 1))

    # D4 — pin-to-net disagreement. Same comparison verify_netlist_diff's
    # T4 performs, through the same table and the same exception
    # predicate, collected as data instead of printed.
    pcb_pin_nets = board.pin_nets()
    for (ref, pin), sch_net in sorted(sch.pin_nets.items()):
        if ref in vnd.EXCLUDED_REFS:
            continue
        pads, mapped = vnd._mapped_pads(ref, pin)
        if not mapped:
            disputes.append(Dispute(
                "D3", f"{ref}.{pin}", "sch",
                "verify_netlist_diff.SCH_PIN_TO_PCB_PADS",
                "schematic pin on a translated ref with no entry in the "
                "table"))
            continue
        for pad in pads:
            pcb_net = pcb_pin_nets.get((ref, pad))
            if pcb_net is None or pcb_net == sch_net:
                continue
            if vnd._t4_is_allowed(ref, pin, sch_net, pcb_net):
                continue
            via = "" if pads == (pin,) else f" (pad {pad})"
            disputes.append(Dispute(
                "D4", f"{ref}.{pin}{via}", "both", "unknown",
                f"sch={sch_net!r} pcb={pcb_net!r}"))

    # D5 — a part in one source only. verify_netlist_diff's T3 covers
    # schematic-without-footprint; the reverse direction — a footprint no
    # schematic symbol accounts for — is checked by nothing, because
    # verify_bom_cpl_pcb calls exactly that case DNP and moves on.
    #
    # DNP is a real answer, so it is stated rather than suppressed. It is
    # also the more dangerous case for a bench: a DNP land still has pads
    # with nets, so a solver that trusts the netlist will happily model a
    # part that is not on the board. Any model built for a DNP ref in
    # Phase 1 must therefore be an open circuit.
    # DNP_REFS is derived from the working tree's exporter and cache, so it
    # describes today's assembly, not a past revision's. For a --rev run it
    # is therefore not consulted at all rather than applied to the wrong
    # revision: a stale DNP claim is worse than an unattributed part.
    dnp = DNP_REFS if board.origin == "working tree" else frozenset()
    for ref in sorted(board.refs - sch.refs - vnd.EXCLUDED_REFS):
        if ref in dnp:
            disputes.append(Dispute(
                "D5", ref, "pcb", "phase 1 component models",
                "DNP — pads and nets on the board, but not in the BOM, not "
                "in the CPL, not assembled", 0))
        elif ref in HAND_ASSEMBLED:
            continue
        else:
            why = ("no schematic symbol; DNP status not checked for a past "
                   "revision" if not dnp else
                   "no schematic symbol and no DNP record — assembled, but "
                   "unaccounted for by either source")
            disputes.append(Dispute("D5", ref, "pcb",
                                    "schematic generator", why, 0))
    for ref in sorted(sch.refs - board.refs - vnd.EXCLUDED_REFS - vnd.T3_ALLOW):
        disputes.append(Dispute(
            "D5", ref, "sch", "pcb generator",
            "schematic symbol with no footprint on the board", 0))

    # D6 — a two-terminal part with fewer than two pins on any net. It is
    # placed, it is in the BOM, and it is not in the circuit.
    #
    # This is the whole Round 5 class: L1's inductor pin, C17 and C18's
    # decoupling pins, every button's pull-up and debounce cap, SW14 and
    # the menu diode were all physically present with a terminal on an
    # isolated island, and six gates said PASS because every pad still had
    # the *right net name*. A net name is not a connection.
    #
    # The one exception on this board is derived, not listed: R14 has a
    # single pin on a net and is DNP — no BOM value, so it is not fitted, so
    # half-connected is what it should be. Any other part in that state is a
    # finding.
    two_terminal = collections.defaultdict(set)
    for net, pins in board.nets.items():
        for p in pins:
            if re.match(r"^(R|C|L|D|LED)\d", p.ref):
                two_terminal[p.ref].add((p.pad, net))
    for ref, seen in sorted(two_terminal.items()):
        if len({net for _pad, net in seen}) >= 2:
            continue
        if ref in dnp:
            continue
        disputes.append(Dispute(
            "D6", ref, "pcb", "routing",
            f"only {len(seen)} pin(s) on a net "
            f"({', '.join(f'{p}->{n}' for p, n in sorted(seen)) or 'none'}) — "
            f"placed and in the BOM, but not in the circuit", 0))

    order = {"D1": 0, "D6": 1, "D3": 2, "D4": 3, "D5": 4, "D2": 5}
    return sorted(disputes,
                  key=lambda d: (order[d.code], d.rank, d.subject, d.side))


# ── Delta between two revisions ─────────────────────────────────────

def delta(old, new):
    """What changed between two board netlists, pin by pin.

    The plan's headline output: "this changed since the board you are
    holding". Compared by (ref, pad) rather than by net, because a net
    rename with identical copper is not an electrical change and must not
    read as one.
    """
    old_pins, new_pins = old.pin_nets(), new.pin_nets()
    out = {
        "old": old.origin, "new": new.origin,
        "nets_added": sorted(set(new.nets) - set(old.nets)),
        "nets_removed": sorted(set(old.nets) - set(new.nets)),
        "pins_added": sorted(f"{r}.{p}={new_pins[(r, p)]}"
                             for r, p in set(new_pins) - set(old_pins)),
        "pins_removed": sorted(f"{r}.{p}={old_pins[(r, p)]}"
                               for r, p in set(old_pins) - set(new_pins)),
        "pins_moved": sorted(
            f"{r}.{p}: {old_pins[(r, p)]} -> {new_pins[(r, p)]}"
            for r, p in set(old_pins) & set(new_pins)
            if old_pins[(r, p)] != new_pins[(r, p)]),
    }
    out["count"] = sum(len(out[k]) for k in
                       ("nets_added", "nets_removed", "pins_added",
                        "pins_removed", "pins_moved"))
    out["changed"] = out["count"] > 0
    return out


# ── Report ──────────────────────────────────────────────────────────

def print_summary(board):
    pin_count = sum(len(v) for v in board.nets.values())
    print(f"  Netlist source : {board.origin}  ({board.pcb_hash[:19]}...)")
    print(f"  Nets declared  : {len(board.declared_nets)}")
    print(f"  Nets with pins : {len(board.nets)}")
    print(f"  Pin instances  : {pin_count}")
    print(f"  Footprints     : {len(board.refs)}")
    print()
    print("  Largest nets:")
    for net, pins in sorted(board.nets.items(),
                            key=lambda kv: -len(kv[1]))[:6]:
        print(f"    {net:<12} {len(pins):>3} pins")


_CODE_MEANING = {
    "D1": "board net with no pad on it",
    "D2": "net with a single pin — a label, not a circuit",
    "D3": "pad or pin that no source accounts for",
    "D4": "schematic and board disagree about a pin's net",
    "D5": "part present in only one source",
    "D6": "a two-terminal part with a terminal on no net",
}

# Printed once per class, not once per finding: the explanation is a
# property of the class, and repeating it per row is how a long list stops
# being read.
_CODE_NOTE = {
    "D1": "A net with no pin is a name, not a connection. Invisible to "
          "verify_netlist_diff: T1/T2 compare names, which match, and T4 "
          "iterates schematic pins, of which this net has none.",
    "D2": "One pin gives current nowhere to go, so this is either an "
          "unfinished connection or a label that should not be a net.",
    "D3": "Neither the schematic symbol nor datasheet_specs says what this "
          "pad should be on, and pad nets are injected by copper overlap "
          "(board._inject_pad_net) — so its net is an accident nothing can "
          "contradict.",
    "D4": "The two sources describe different circuits. Same comparison as "
          "verify_netlist_diff T4, through the same table.",
    "D5": "A DNP land still has pads with nets, so a solver that trusts the "
          "netlist will model a part the board does not carry.",
    "D6": "It is placed, it is in the BOM, and it is not in the circuit. This "
          "is the Round 5 class: every pad kept the right net NAME while a "
          "terminal sat on an isolated island.",
}


def print_disputes(disputes, board=None):
    if board is not None and board.pads_only_in_datasheet:
        print(f"  Pads the schematic does not represent, but "
              f"datasheet_specs does: {len(board.pads_only_in_datasheet)}")
        print(f"        Not disputes — verify_datasheet_nets compares each "
              f"one's net against a declared expectation. Listed because a "
              f"Phase 1 model built from the schematic alone would miss "
              f"them: "
              f"{', '.join(f'{r}.{p}' for r, p, _ in board.pads_only_in_datasheet[:6])}"
              f"{' ...' if len(board.pads_only_in_datasheet) > 6 else ''}")
        print()
    print(f"  Disputes: {len(disputes)}")
    if not disputes:
        print("    none — the bench has an undisputed netlist to stand on")
        return
    by_code = collections.Counter(d.code for d in disputes)
    for code in sorted(by_code):
        print(f"\n  [{code}] {_CODE_MEANING[code]}  ({by_code[code]})")
        print(f"        {_CODE_NOTE[code]}")
        for d in disputes:
            if d.code == code:
                owner = "" if d.owner == "unknown" else f"   [{d.owner}]"
                print(f"    {d.side:<4} {d.subject:<18} {d.detail}{owner}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rev", help="build from this git revision instead of "
                                  "the working tree")
    ap.add_argument("--delta", nargs="?", const=FABRICATED_REV, metavar="REV",
                    help=f"also report the delta against REV "
                         f"(default: {FABRICATED_REV}, the revision "
                         f"prototype #1 was fabricated from)")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    args = ap.parse_args(argv)

    try:
        board = load_board_netlist(args.rev)
        sch = load_schematic_netlist(args.rev)
        disputes = crosscheck(board, sch)
        the_delta = None
        if args.delta:
            the_delta = delta(load_board_netlist(args.delta), board)
    except NetlistError as exc:
        # A bench that cannot read its own inputs exits 2, not 1: the
        # difference between "the design has disputes" and "the verdict is
        # worthless" has to survive into the exit code.
        print(f"  ERROR  {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "origin": board.origin,
            "pcb_hash": board.pcb_hash,
            "nets": {n: [p._asdict() for p in pins]
                     for n, pins in board.nets.items()},
            "disputes": [d._asdict() for d in disputes],
            "delta": the_delta,
        }, indent=2))
        return 1 if disputes else 0

    print("=" * 72)
    print("  Virtual Bench T0.1 — extracted netlist")
    print("=" * 72)
    print_summary(board)
    print()
    print("-" * 72)
    print_disputes(disputes, board)
    if the_delta:
        print()
        print("-" * 72)
        print(f"  Delta {the_delta['old']} -> {the_delta['new']}")
        if not the_delta["changed"]:
            print("    no electrical change — bench results on this netlist "
                  "are directly comparable to prototype #1")
        else:
            print(f"    {the_delta['count']} electrical difference(s). Any "
                  f"bench result below describes the design, NOT the board "
                  f"on the desk.")
        for key, label in (("nets_added", "net   +"),
                           ("nets_removed", "net   -"),
                           ("pins_added", "pin   +"),
                           ("pins_removed", "pin   -"),
                           ("pins_moved", "pin   ~")):
            for item in the_delta[key]:
                print(f"    {label}  {item}")
    print()
    if disputes:
        print(f"  RESULT: BLOCKED — {len(disputes)} dispute(s). Per the plan, "
              f"the bench may not be built on a netlist in dispute.")
        return 1
    print("  RESULT: OK — netlist undisputed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
