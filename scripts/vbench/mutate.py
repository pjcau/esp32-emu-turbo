"""Break the board on purpose, in memory, so the bench can be measured.

The retro corpus describes each historical bug as a mutation. This module
applies one to an **in-memory copy** of the extracted netlist — nothing on
disk is touched — so a detector can ask whether the bench notices.

The rule for "noticed" is deliberately general and is implemented in
`detectors.py`: inject the mutation, re-run the bench's checks, and require a
**new** finding that names the mutated part. Hand-writing "for this entry,
look for this string" per bug would let a detector pass by matching text the
bench happens to print anyway, which measures nothing.

Supported kinds are exactly the ones the corpus uses. An unsupported kind
raises rather than returning an unmutated board — a mutation that silently
did nothing would make its entry look uncatchable when it was never applied.
"""

import copy
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import netlist as nl                              # noqa: E402


class MutationError(RuntimeError):
    """The mutation could not be applied. Never silently skipped."""


def _clone(board):
    """A copy whose nets can be rewritten without touching the original."""
    dup = copy.copy(board)
    dup.nets = {net: tuple(pins) for net, pins in board.nets.items()}
    dup.declared_nets = set(board.declared_nets)
    dup.pads_only_in_datasheet = list(board.pads_only_in_datasheet)
    dup.pads_without_pin = list(board.pads_without_pin)
    return dup


def _find(board, ref, pad):
    for net, pins in board.nets.items():
        for p in pins:
            if p.ref == ref and p.pad == str(pad):
                return net, p
    return None, None


def apply(board, mutation):
    """Return a mutated copy of `board`. Raises on anything it cannot do."""
    kind = mutation.get("kind")
    if kind == "none":
        raise MutationError(
            "kind 'none' describes a defect present in the design as it "
            "stands; there is nothing to inject and the entry needs a live "
            "detector instead")
    dup = _clone(board)

    if kind == "detach_pin" and mutation.get("side") == "schematic":
        # The schematic is a different netlist with the same shape. R24-HIGH-3
        # was a schematic-only defect — the board was always right — so the
        # mutation has to be applied there or the entry tests nothing.
        raise MutationError(
            "schematic-side mutations are applied by apply_schematic(), not "
            "by apply(); the caller passed a board")

    if kind == "detach_pin":
        ref, pad = mutation["ref"], str(mutation.get("pin", ""))
        net, pin = _find(dup, ref, pad)
        if net is None:
            # Try the pin number as a schematic pin rather than a pad.
            for candidate_net, pins in dup.nets.items():
                for p in pins:
                    if p.ref == ref and p.pin == pad:
                        net, pin = candidate_net, p
                        break
                if net:
                    break
        if net is None:
            raise MutationError(
                f"cannot detach {ref}.{pad}: no pad of {ref} carries pin/pad "
                f"{pad} on any net")
        dup.nets[net] = tuple(p for p in dup.nets[net] if p is not pin)
        if not dup.nets[net]:
            del dup.nets[net]
        return dup, f"{ref}.{pad} removed from {net}"

    if kind == "move_pin":
        ref, pad = mutation["ref"], str(mutation.get("pin", ""))
        target = mutation["to_net"]
        net, pin = _find(dup, ref, pad)
        if net is None:
            raise MutationError(f"cannot move {ref}.{pad}: it is on no net")
        dup.nets[net] = tuple(p for p in dup.nets[net] if p is not pin)
        if not dup.nets[net]:
            del dup.nets[net]
        moved = pin._replace()
        dup.nets[target] = tuple(dup.nets.get(target, ())) + (moved,)
        dup.declared_nets.add(target)
        return dup, f"{ref}.{pad} moved from {net} to {target}"

    if kind == "declare_net":
        name = mutation["net"]
        if mutation.get("pads"):
            raise MutationError(
                "declare_net injects a net with NO pads; giving it pads would "
                "not reproduce the phantom-net bug")
        dup.declared_nets.add(name)
        dup.nets.pop(name, None)
        return dup, f"{name} declared with no pad on it"

    if kind == "short_nets":
        a, b = mutation["net_a"], mutation["net_b"]
        if a not in dup.nets or b not in dup.nets:
            raise MutationError(f"cannot short {a} to {b}: one is not on the "
                                f"board")
        dup.nets[a] = tuple(dup.nets[a]) + tuple(dup.nets[b])
        del dup.nets[b]
        return dup, f"{b} merged into {a}"

    raise MutationError(
        f"mutation kind {kind!r} is not implemented. Add it here rather than "
        f"letting the entry report itself uncatchable — it was never applied.")


def apply_schematic(sch, mutation):
    """Apply a schematic-side mutation to a copy of the schematic netlist.

    Only detach_pin, which is what R24-HIGH-3 was: SW_RST and SW_BOOT drawn
    with wires that missed their pins, so the pins left the exported netlist
    entirely rather than appearing with a wrong net.
    """
    if mutation.get("kind") != "detach_pin":
        raise MutationError(
            f"schematic side supports detach_pin only, not "
            f"{mutation.get('kind')!r}")
    ref, pin = mutation["ref"], str(mutation.get("pin", ""))
    pin_nets = dict(sch.pin_nets)
    net = pin_nets.pop((ref, pin), None)
    if net is None:
        raise MutationError(
            f"cannot detach {ref}.{pin} from the schematic: it is on no net "
            f"there, so the mutation would be a no-op")
    nets = {n: tuple(p for p in nodes if p != (ref, pin))
            for n, nodes in sch.nets.items()}
    dup = nl.SchematicNetlist(nets, set(sch.refs), pin_nets)
    return dup, f"{ref}.{pin} removed from the schematic net {net}", {ref, net}


def refs_touched(mutation):
    """Which reference designators / nets a finding must mention to count."""
    out = set()
    for key in ("ref", "net", "net_a", "net_b", "to_net"):
        if mutation.get(key):
            out.add(str(mutation[key]))
    return out
