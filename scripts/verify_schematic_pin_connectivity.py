#!/usr/bin/env python3
"""Fail when a placed schematic symbol has a pin that nothing lands on.

Why this exists
---------------
The schematic is emitted by a generator, so a pin is "wired" only if the
generator happened to draw a wire endpoint at the pin's exact connection
point. When the generator wires a symbol using the wrong pin geometry —
e.g. wiring `SW_Push` vertically at (x, y +/- 3.81) when its pins are
horizontal at (x +/- 5.08, y) — the wires miss the pins entirely. The
symbol still renders, the sheet still looks correct to a human, and the
netlist silently drops the component.

KiCad's own ERC does report this as `pin_not_connected`, but two things
hid it for four audit rounds:

  1. `erc_check.py` classes `pin_not_connected` as a warning, not a
     critical, so the ERC gate prints PASS.
  2. Every sheet file reuses the same low-numbered UUIDs, so KiCad
     attributes the violation to whichever symbol elsewhere in the
     hierarchy shares the colliding UUID. The R24 report showed SW3
     (a Controls-sheet button) blamed for SW_RST/SW_BOOT floating in
     the Mcu sheet — chasing SW3 found nothing wrong, and the finding
     was dismissed.

This check is independent of both: it reads the .kicad_sch geometry
directly and never consults a UUID.

The law
-------
Every pin of every placed symbol must have an electrical anchor at its
connection point: a wire endpoint, a junction, a label of any kind, or a
no-connect flag. Deliberate no-connects are declared in ALLOWED below,
each with the reason it is intentional — a bare floating pin is a bug.
"""
import glob
import math
import os
import re
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCH_GLOB = os.path.join(PROJECT_DIR, "hardware/kicad/*.kicad_sch")

# (reference, pin number) -> why this pin is intentionally unterminated.
# An entry here is a claim that the open circuit is the design. Anything
# not listed is a failure.
ALLOWED = {
    ("SW_PWR", "1"): (
        "v1 as-built: the slide switch is NOT in series with the battery. "
        "Only the common pin (2) taps BAT+; the throw pins are unrouted. "
        "See power_supply.py and hardware/datasheet_specs.py::SW_PWR. "
        "v2 respin wires pins 1-2 in series."
    ),
    ("SW_PWR", "2"): (
        "Same as SW_PWR.1 — v1 leaves the throw side open. The wired "
        "terminal is the one carrying the BAT+ glabel."
    ),
}

ANCHOR_ELEMENTS = ("junction", "label", "global_label",
                   "hierarchical_label", "no_connect")


# ── minimal s-expression reader ──────────────────────────────────────

def parse_sexp(text):
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack, cur = [], []
    for tok in tokens:
        if tok == "(":
            stack.append(cur)
            cur = []
        elif tok == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
        else:
            cur.append(tok[1:-1] if tok.startswith('"') else tok)
    return cur


def iter_nodes(node, head):
    if isinstance(node, list):
        if node and node[0] == head:
            yield node
        for child in node:
            yield from iter_nodes(child, head)


def field(node, head):
    for child in node:
        if isinstance(child, list) and child and child[0] == head:
            return child
    return None


def position(node):
    at = field(node, "at")
    if not at:
        return None
    angle = float(at[3]) if len(at) >= 4 else 0.0
    return float(at[1]), float(at[2]), angle


def point(x, y):
    # 3 decimals: KiCad writes mm at 4dp, pin/wire coincidence is exact.
    return round(x, 3), round(y, 3)


# ── geometry ─────────────────────────────────────────────────────────

def library_pins(root):
    """lib_id -> [(pin number, x, y)] in library coordinates (Y-up)."""
    out = {}
    for libs in iter_nodes(root, "lib_symbols"):
        for sym in libs[1:]:
            if not (isinstance(sym, list) and sym and sym[0] == "symbol"):
                continue
            pins = []
            for pin in iter_nodes(sym, "pin"):
                pos = position(pin)
                num = field(pin, "number")
                if pos and num:
                    pins.append((num[1], pos[0], pos[1]))
            if pins:
                out[sym[1]] = pins
    return out


def anchor_points(root):
    """Every point where a wire, junction, label or no-connect terminates."""
    anchors = set()
    for wire in iter_nodes(root, "wire"):
        for pts in iter_nodes(wire, "pts"):
            for xy in iter_nodes(pts, "xy"):
                anchors.add(point(float(xy[1]), float(xy[2])))
    for head in ANCHOR_ELEMENTS:
        for node in iter_nodes(root, head):
            pos = position(node)
            if pos:
                anchors.add(point(pos[0], pos[1]))
    return anchors


def placed_pin_points(sym, libpins):
    """Absolute connection point of every pin of one placed symbol.

    Library symbols are drawn Y-up; the sheet is Y-down, so the library
    Y is negated before the instance mirror and rotation are applied.
    """
    lib_id = field(sym, "lib_id")
    pos = position(sym)
    if not lib_id or not pos or lib_id[1] not in libpins:
        return
    mirror = field(sym, "mirror")
    mirror = mirror[1] if mirror else None
    ox, oy, angle = pos
    theta = math.radians(angle)
    for num, px, py in libpins[lib_id[1]]:
        x, y = px, -py
        if mirror == "x":
            y = -y
        elif mirror == "y":
            x = -x
        rx = x * math.cos(theta) - y * math.sin(theta)
        ry = x * math.sin(theta) + y * math.cos(theta)
        yield num, point(ox + rx, oy + ry)


def reference_of(sym):
    for prop in iter_nodes(sym, "property"):
        if len(prop) >= 3 and prop[1] == "Reference":
            return prop[2]
    return "?"


# ── check ────────────────────────────────────────────────────────────

def check_sheet(path):
    root = parse_sexp(open(path).read())[0]
    libpins = library_pins(root)
    anchors = anchor_points(root)

    floating, allowed, total = [], [], 0
    for sym in root:
        if not (isinstance(sym, list) and sym and sym[0] == "symbol"):
            continue
        ref = reference_of(sym)
        for num, pt in placed_pin_points(sym, libpins):
            total += 1
            if pt in anchors:
                continue
            if (ref, num) in ALLOWED:
                allowed.append((ref, num, pt))
            else:
                floating.append((ref, num, pt))
    return total, floating, allowed


def main():
    print()
    print("=" * 62)
    print("Schematic pin-connectivity check")
    print("=" * 62)
    print()

    sheets = sorted(glob.glob(SCH_GLOB))
    if not sheets:
        print(f"  FAIL  No schematic found at {SCH_GLOB}")
        return 1

    total_pins = total_floating = total_allowed = 0
    for path in sheets:
        pins, floating, allowed = check_sheet(path)
        total_pins += pins
        total_floating += len(floating)
        total_allowed += len(allowed)

        status = "FAIL" if floating else "PASS"
        note = f"  ({len(allowed)} documented N.C.)" if allowed else ""
        print(f"  {status}  {os.path.basename(path):28s} "
              f"{pins:4d} pins, {len(floating)} floating{note}")
        for ref, num, pt in floating:
            print(f"          {ref:10s} pin {num:4s} @ {pt} "
                  f"— nothing lands on this pin")
        for ref, num, pt in allowed:
            print(f"          {ref:10s} pin {num:4s} @ {pt} "
                  f"— N.C.: {ALLOWED[(ref, num)][:60]}...")

    print()
    print("=" * 62)
    print(f"Results: {total_pins} pins checked, "
          f"{total_floating} floating, {total_allowed} documented N.C.")
    if total_floating:
        print("STATUS: FAIL — a floating pin means the component is absent "
              "from the netlist")
    else:
        print("STATUS: PASS — every pin is wired or declared N.C.")
    print("=" * 62)
    return 1 if total_floating else 0


if __name__ == "__main__":
    sys.exit(main())
