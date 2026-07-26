"""Virtual Bench T3.1 (part) — the display seen from the PANEL, not the pad.

Every existing gate checks J4 by **pad**: datasheet_specs declares 42 pads,
verify_datasheet_nets compares their nets, verify_dfm_v2 checks the 41−N
reversal is applied. Nothing checks what the **panel** sees. Those are not the
same question, because the ribbon reverses the numbering: panel pin N contacts
connector pad 41−N, so a mistake that looks symmetric on the pad side is a
swapped data line on the panel side.

This module builds the panel-side netlist: for each of the 40 panel pins, the
pad it touches, the net on that pad, and the DC level T1.1 computes for it.
Then it checks the things only that view can express — that the interface-mode
straps really select 8-bit 8080, and that DB0..DB7 arrive in order.

## Where the pinout comes from, and what that costs

The 40-pin table is **parsed** out of `website/docs/design/components.md`
(section "FPC 40-Pin Pinout"), which the repo names as the source of truth and
which states it was verified against the panel datasheet shipped by the
seller, with the datasheet images embedded. It is parsed rather than copied so
there is one table, not two.

**The panel's datasheet IS in this repo** — two of its pages, as images, at
`website/static/img/ili9488-fpc40-pinout.png` and `ili9488-datasheet-specs.png`,
referenced from components.md since it was written. An earlier version of this
module said the opposite, which was true of `hardware/datasheets/` and false
of the repo, and the difference is not academic: reading those pages is what
produced R28-HIGH-1 below.

What remains true is narrower. `models/_schema.py` accepts a citation only
from `hardware/datasheets/`, so a panel `Model` still cannot validate and the
panel is handled the way `sources.py` handles the LiPo: declared, provenance
stated, flagged. Putting those two pages in `hardware/datasheets/` is what
would change that.

## What cannot be modelled yet

The ILI9488 **controller** behaviour — command set, MADCTL and rotation, pixel
format, and the setup/hold windows a 20 MHz pclk has to satisfy — needs the
controller datasheet, which this repo does not hold either. T3.1's frame-render
and timing halves stay unbuilt, and this module says so rather than emitting a
framebuffer that would look like proof.

Usage:
    python3 scripts/vbench/display.py
"""

import argparse
import collections
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import netlist as nl                              # noqa: E402
from vbench import rails                                      # noqa: E402

PINOUT_DOC = os.path.join(BASE, "website", "docs", "design", "components.md")
PANEL_PINS = 40

# panel pin N contacts connector pad 41 - N. Documented at the top of
# scripts/generate_schematics/sheets/display.py and in components.md; it is an
# invariant of this board (corpus entry INV-J4-REVERSAL) and must never be
# "fixed".
def pad_of(panel_pin):
    return str(41 - panel_pin)


PanelPin = collections.namedtuple(
    "PanelPin", "pin symbol description expected pad net volts level")

PROVENANCE = (
    "website/docs/design/components.md, section 'FPC 40-Pin Pinout', parsed. "
    "It is transcribed from the panel datasheet's own pages, which are in "
    "this repo as images (website/static/img/ili9488-*.png) — that is where "
    "the unused-pin rules below come from. There is still no PDF in "
    "hardware/datasheets/, which is the only place _schema.py accepts a "
    "citation from, so a panel Model cannot validate yet.")

# What the panel datasheet says to do with the pins this design does not use.
# Source: website/static/img/ili9488-fpc40-pinout.png — the datasheet's own
# pin table, embedded in the repo and referenced from
# website/docs/design/components.md. It draws a distinction no summary in this
# repo had carried: two unused pins must be TIED, and two must be LEFT OPEN.
#
#   pin 12 RDX      "Read enable in MCU parallel interface. If not used,
#                    please fix this pin at VDDI or GND."
#   pin 13 SPI SDI  "SPI interface input pin. If not used, please fix this
#                    pin at VDDI or DGND level."
#   pin 14 SPI SDO  "SPI interface output pin. If not used, let this pin
#                    open."
#   pin  8 FMARK/TE "Tearing effect signal ... (不用时悬空)" — leave floating
#                    when unused.
#
# An input left floating is not the same as an output left open, and the
# datasheet says so pin by pin. This is the check that distinction buys.
TIE_IF_UNUSED = {
    12: "VDDI or GND",
    13: "VDDI or DGND",
}
LEAVE_OPEN_IF_UNUSED = {
    8: "tearing-effect output, unused",
    14: "SPI data output, unused",
}
PIN_RULE_SRC = ("website/static/img/ili9488-fpc40-pinout.png — the panel "
                "datasheet's own pin table")

UNMODELLED = {
    "command_set": "ILI9488 command set, MADCTL and rotation need the "
                   "CONTROLLER datasheet. The two panel pages this repo holds "
                   "are the module's pinout and mechanical specification, not "
                   "the controller's register set.",
    "pixel_format": "RGB565 vs RGB666 selection is a controller register, "
                    "same gap",
    "timing": "setup/hold against the 20 MHz pclk needs the controller's AC "
              "characteristics, same gap — so no timing verdict is given "
              "rather than a reassuring one",
}


class PinoutError(RuntimeError):
    """The pinout table could not be read. Fatal — never guessed around."""


def _expand(cell):
    """'17-24' -> [17..24]; '5' -> [5]."""
    cell = cell.strip().replace("**", "")
    m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", cell)
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    return [int(cell)] if cell.isdigit() else []


def _expand_symbols(symbol, count):
    """'DB0-DB7' -> ['DB0'..'DB7']; 'GND' with count 3 -> ['GND','GND','GND']."""
    symbol = symbol.strip().replace("**", "")
    m = re.match(r"^([A-Za-z_/]+?)(\d+)\s*[-–]\s*[A-Za-z_/]*(\d+)$", symbol)
    if m:
        base, lo, hi = m.group(1), int(m.group(2)), int(m.group(3))
        step = 1 if hi >= lo else -1
        return [f"{base}{n}" for n in range(lo, hi + step, step)]
    return [symbol] * count


def read_pinout(path=PINOUT_DOC):
    """Parse the 40-pin panel table out of components.md."""
    if not os.path.exists(path):
        raise PinoutError(f"pinout source missing: {path}")
    # Only the rows of the table whose header is
    # "| Pin | Symbol | Direction | Description | Connection |", and only
    # until that table ends. components.md holds a SECOND five-column table
    # just below it — the IM2:IM1:IM0 interface-mode table — whose first cells
    # are 0 and 1. Parsing every five-column row in the file let those rows
    # overwrite panel pins 1 and 0, and panel pin 1 came out named "1".
    # Anchoring on the header is what stops a nearby table from being read as
    # this one.
    rows = {}
    inside = False
    with open(path, errors="replace") as fh:
        for line in fh:
            if not line.startswith("|"):
                if inside:
                    break            # the pinout table has ended
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 5:
                if inside:
                    break
                continue
            header = [c.lower() for c in cells]
            if header == ["pin", "symbol", "direction", "description",
                          "connection"]:
                inside = True
                continue
            if not inside or set(cells[0]) <= set("-: "):
                continue
            pins = _expand(cells[0])
            if not pins or max(pins) > PANEL_PINS:
                continue
            symbols = _expand_symbols(cells[1], len(pins))
            if len(symbols) != len(pins):
                symbols = [cells[1].replace("**", "").strip()] * len(pins)
            for pin, sym in zip(pins, symbols):
                rows[pin] = (sym, cells[3], cells[4].replace("**", "").strip())
    missing = [p for p in range(1, PANEL_PINS + 1) if p not in rows]
    if missing:
        raise PinoutError(
            f"the pinout table in {os.path.relpath(path, BASE)} does not cover "
            f"panel pins {missing}. A partial panel pinout is not a pinout — "
            f"fix the table rather than letting the bench fill the gaps.")
    return rows


def panel_view():
    """The 40 panel pins with the board net and DC level each one sees."""
    rows = read_pinout()
    board = nl.load_board_netlist()
    op = rails.operating_point()
    v_rail = op.rail_spread["+3V3"][1]

    pad_net = {}
    for net, pins in board.nets.items():
        for p in pins:
            if p.ref == "J4":
                pad_net[p.pad] = net

    out = []
    for pin in range(1, PANEL_PINS + 1):
        sym, desc, expected = rows[pin]
        pad = pad_of(pin)
        net = pad_net.get(pad)
        volts = op.voltages.get(net) if net else None
        level = None
        if volts is not None:
            level = 1 if volts >= 0.7 * v_rail else (
                0 if volts <= 0.3 * v_rail else "?")
        out.append(PanelPin(pin, sym, desc, expected, pad, net, volts, level))
    return out, v_rail


def check_interface_mode(view):
    """IM2:IM1:IM0 must select 8080 8-bit. Returns (ok, mode, detail)."""
    im = {}
    for p in view:
        if p.symbol in ("IM0", "IM1", "IM2"):
            im[p.symbol] = p.level
    if len(im) != 3:
        return False, "unknown", f"only found {sorted(im)} among the panel pins"
    triple = (im.get("IM2"), im.get("IM1"), im.get("IM0"))
    modes = {
        (0, 1, 0): "8080 16-bit parallel",
        (0, 1, 1): "8080 8-bit parallel",
        (1, 0, 1): "3-line 9-bit SPI",
        (1, 1, 1): "4-line 8-bit SPI",
    }
    mode = modes.get(triple, "not a documented combination")
    detail = (f"IM2={triple[0]}, IM1={triple[1]}, IM0={triple[2]} "
              f"(pins 40/39/38 -> pads 1/2/3)")
    return mode == "8080 8-bit parallel", mode, detail


def check_unused_pins(view):
    """Unused panel pins must be tied or open exactly as the datasheet says."""
    by_pin = {p.pin: p for p in view}
    faults = []
    for pin, where in sorted(TIE_IF_UNUSED.items()):
        p = by_pin.get(pin)
        if p is None:
            faults.append(f"panel pin {pin} is missing from the pinout")
            continue
        if p.net is None:
            faults.append(
                f"panel pin {pin} ({p.symbol}) is FLOATING on pad {p.pad}; the "
                f"panel datasheet says to fix it at {where} when unused. A "
                f"floating input sits near threshold and can oscillate — this "
                f"is an input, not an output, and the datasheet distinguishes "
                f"the two pin by pin.")
    for pin, why in sorted(LEAVE_OPEN_IF_UNUSED.items()):
        p = by_pin.get(pin)
        if p is not None and p.net is not None:
            faults.append(
                f"panel pin {pin} ({p.symbol}, {why}) carries {p.net!r}; the "
                f"datasheet says to leave this one open")
    return faults


def check_data_bus(view):
    """DB0..DB7 must land on LCD_D0..LCD_D7 in order. Returns list of faults."""
    faults = []
    for p in view:
        m = re.match(r"^DB(\d+)$", p.symbol)
        if not m:
            continue
        n = int(m.group(1))
        if n > 7:
            if p.net:
                faults.append(
                    f"panel pin {p.pin} ({p.symbol}) is a 16-bit-mode line "
                    f"and must be unconnected in 8-bit mode, but pad {p.pad} "
                    f"carries {p.net!r}")
            continue
        want = f"LCD_D{n}"
        if p.net != want:
            faults.append(
                f"panel pin {p.pin} ({p.symbol}) reaches pad {p.pad} carrying "
                f"{p.net!r}, but 8-bit mode needs {want!r} there — a data line "
                f"is crossed")
    return faults


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)

    try:
        view, v_rail = panel_view()
    except (PinoutError, nl.NetlistError, rails.RailError) as exc:
        print(f"  ERROR  {exc}", file=sys.stderr)
        return 2

    print("=" * 72)
    print("  Virtual Bench T3.1 — the display, seen from the panel")
    print("=" * 72)
    print(f"  Panel  : 40-pin FPC, pin N contacts J4 pad 41-N (board "
          f"invariant)")
    print(f"  Pinout : {PROVENANCE}")
    print()
    print(f"  {'pin':>3} {'symbol':<8} {'pad':>4} {'net':<12} {'V':>7} lvl")
    print("  " + "-" * 60)
    for p in view:
        volts = f"{p.volts:7.3f}" if p.volts is not None else "      -"
        lvl = " - " if p.level is None else f" {p.level} "
        print(f"  {p.pin:>3} {p.symbol:<8} {p.pad:>4} {p.net or '(none)':<12} "
              f"{volts} {lvl}")

    problems = []
    ok, mode, detail = check_interface_mode(view)
    print()
    print("-" * 72)
    print(f"  Interface mode : {mode}")
    print(f"                   {detail}")
    if not ok:
        problems.append(
            f"the IM straps select {mode!r}, not 8080 8-bit — the firmware "
            f"drives an 8-bit parallel bus, so the panel would not respond")
    else:
        print(f"  Which is what the firmware drives. The straps are read from "
              f"the copper,")
        print(f"  not from the mode table: pads 1/2/3 carry GND/+3V3/+3V3.")

    faults = check_data_bus(view)
    print()
    print(f"  Data bus : {'DB0-DB7 land on LCD_D0-LCD_D7 in order' if not faults else f'{len(faults)} fault(s)'}")
    for f in faults:
        print(f"    {f}")
    problems.extend(faults)

    unused = check_unused_pins(view)
    print()
    print(f"  Unused pins, per {PIN_RULE_SRC}:")
    print(f"    tie when unused : "
          f"{', '.join(f'pin {p} -> {w}' for p, w in sorted(TIE_IF_UNUSED.items()))}")
    print(f"    leave open      : "
          f"{', '.join(f'pin {p}' for p in sorted(LEAVE_OPEN_IF_UNUSED))}")
    if not unused:
        print("    all of them obey it")
    for f in unused:
        print(f"    {f}")
    problems.extend(unused)

    print()
    print("-" * 72)
    print("  Not modelled, and not silently:")
    for key, why in sorted(UNMODELLED.items()):
        print(f"    {key:<14} {why}")

    print()
    print("=" * 72)
    if problems:
        print(f"  FAIL — {len(problems)} panel-side problem(s)")
        print("=" * 72)
        return 1
    print("  The panel sees an 8-bit 8080 bus with its data lines in order.")
    print("  That is the whole verdict — no frame was rendered and no timing")
    print("  was checked, because the controller datasheet is not in this "
          "repo.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
