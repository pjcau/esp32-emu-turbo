"""Virtual Bench T3.3 — the SD card's bus, and the pin it shares with a button.

Checks the four SPI signals against the TF-01A socket's pad roles, then asks
the question the socket's own wiring raises: **U6.9 sits on the BTN_R net,
and BTN_R is GPIO3 — a strapping pin.**

That assignment is deliberate. The routing generator
(`generate_pcb/routing/_assemble.py`) records it: the BTN_R track physically
crosses the U6.8/U6.9 pads, so the pads are given the same net to keep the
overlap same-net rather than a fab short.

## What U6.9 is — and what it took three tries to get right

Not DAT2. The socket has **nine pads**; a microSD card has **eight
contacts**. The TF-01A drawing's "PCB Layout (Pattern Side)" view labels the
row (1)(2)(3)(4)(5)(6)(7)(8) and then **Cd**: pad 9 is the socket's own
card-detect contact, and no card contact ever reaches it.

The DAT2 label came from SanDisk's own pin tables, which are the FULL-SIZE
SD tables — the document says so in the sentence above them ("the host uses
a dedicated 9-pin connector to connect to SD cards", p.17 sec 3.1) and every
row is headed "SD Card". On full-size SD, contact 9 IS DAT2. Laying that
nine-row table over this socket's nine pads shifted every name past 8 by one
part that does not exist. The board's own wiring never made that mistake:
pad 2 = CS, 3 = MOSI, 4 = VDD, 5 = CLK, 6 = VSS, 7 = MISO is microSD
numbering, and it is correct.

## So the two shared pads need two different arguments

**U6.8 is DAT1, a real card contact.** The card does not drive it in the
reset window because "the extended DAT lines (DAT1-DAT3) are input on power
up" (SanDisk industrial p.17 sec 3.1, table 3-1 footnote b), and in SPI mode
contacts 8/9 are RSV (table 3-2, p.18). That covers the right window: GPIO3
is latched at reset, before the boot ROM runs, so the older "SAFE as long as
firmware stays in SPI mode" was an argument about the wrong window — and the
"tri-states DAT1/DAT2 once CMD0 arrives" mechanism it rested on was uncited
in the first place (corrected 2026-07-31 by the T3.3 protocol model).

**U6.9 is Cd, and the card cannot reach it at all** — which makes the card
side of the question moot, and opens a different one on the socket side. The
TF-01A datasheet is a mechanical drawing: parts list, dimensions, pattern.
It carries no schematic, no switch symbol and no normally-open /
normally-closed statement, so **whether the Cd blade shorts to the shell
(GND — U6.10/U6.12) when a card is inserted is not determinable from the
document this repo holds**. If it does, BTN_R sits at GND whenever a card is
in the socket and the R shoulder button reads permanently pressed. Tracked
as CLAIM-006 in hardware/CLAIMS.md; one bring-up read of BTN_R with the
socket empty and then loaded settles it, no instruments required.

Boot is a separate question from the button, and the answer there is no for
a reason worth writing down: table 8 on page 15 of the module datasheet
shows GPIO3 is *ignored* unless an eFuse selects it (EFUSE_STRAP_JTAG_SEL),
and the factory default leaves it unselected. So a card that pulls the pad
low cannot change how the board boots — until someone burns that eFuse.

## Where the protocol lives now

Since 2026-07-31 the card protocol IS modelled — in
`scripts/vbench/sdcard_protocol.py`, against the SD Physical Layer
Simplified Specification v3.01 and the SanDisk industrial card datasheet,
both in hardware/datasheets/. CMD0 / CMD8 / ACMD41, R1/R7, CCS and CMD17
block reads from a host directory all replay there with citations
(`make bench-sdcard`, tests in scripts/test_vbench_sdcard.py). This module
keeps the BUS side: pad roles, wiring, and the strapping exposure above.
One half stays unbuildable: the simplified spec's bus-timing section 7.5
is literally "a blank" (p.147), so no setup/hold check exists — that needs
the full specification.

Usage:
    python3 scripts/vbench/sdcard.py
"""

import argparse
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from hardware.datasheet_specs import COMPONENT_SPECS          # noqa: E402
from vbench import netlist as nl                              # noqa: E402
from vbench import pins as pinmod                             # noqa: E402
from vbench import rails                                      # noqa: E402
from vbench.models.u1_esp32s3 import STRAPPING_DEFAULTS       # noqa: E402

# TF-01A pad -> the net this design puts on it. Pad roles come from
# datasheet_specs.py::U6, which quotes the socket datasheet; the expected nets
# are this board's SPI assignment. Numbering is microSD's: pads 1-8 are the
# card's eight contacts, pad 9 is the socket's Cd contact.
EXPECTED = {
    "2": "SD_CS",      # CD/DAT3 -> chip select in SPI mode
    "3": "SD_MOSI",    # CMD
    "4": "+3V3",       # VDD
    "5": "SD_CLK",     # CLK
    "6": "GND",        # VSS
    "7": "SD_MISO",    # DAT0
}

UNMODELLED = {
    "init_sequence": "modelled since 2026-07-31 in sdcard_protocol.py "
                     "(spec v3.01 ch.7, cited per command) — kept here as a "
                     "pointer, not a gap",
    "block_read": "modelled in sdcard_protocol.py: CMD17 streams a host "
                  "file byte-identical through the virtual card "
                  "about this board",
    "timing": "setup/hold at the 20 MHz clock needs a card datasheet — "
              "U6_TF-01A_MicroSD_C91145.pdf is the SOCKET, not the card",
    "current": "card current draw is per-card and not in any document here",
}


def survey():
    """Bus wiring, shared pads, and the strapping exposure."""
    board = nl.load_board_netlist()
    op = rails.operating_point()
    pad_net = {p.pad: net for net, pins in board.nets.items()
               for p in pins if p.ref == "U6"}
    spec = COMPONENT_SPECS.get("U6", {}).get("pins", {})

    faults, notes = [], []
    for pad, want in sorted(EXPECTED.items(), key=lambda kv: int(kv[0])):
        got = pad_net.get(pad)
        role = str(spec.get(pad, {}).get("function", "?"))
        if got != want:
            faults.append(f"U6.{pad} ({role}) carries {got!r}, expected "
                          f"{want!r}")
        notes.append((pad, role, got, want, got == want))

    # Pads the design deliberately ties to another signal.
    shared = {}
    for pad, net in sorted(pad_net.items(), key=lambda kv: (len(kv[0]), kv[0])):
        if pad in EXPECTED or not net:
            continue
        others = sorted({p.ref for p in board.nets.get(net, ())
                         if p.ref != "U6"})
        shared[pad] = (net, str(spec.get(pad, {}).get("function", "?")), others)

    # Does any shared pad land on a strapping pin?
    exposure = []
    for pad, (net, role, others) in shared.items():
        for pin in board.nets.get(net, ()):
            if pin.ref != "U1":
                continue
            gpio = pinmod.gpio_of_pad(pin.pad)
            if gpio in STRAPPING_DEFAULTS:
                exposure.append((pad, role, net, gpio,
                                 STRAPPING_DEFAULTS[gpio]))
    return notes, shared, exposure, op, faults


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.parse_args(argv)

    try:
        notes, shared, exposure, op, faults = survey()
    except (nl.NetlistError, rails.RailError) as exc:
        print(f"  ERROR  {exc}", file=sys.stderr)
        return 2

    print("=" * 72)
    print("  Virtual Bench T3.3 — SD over SPI")
    print("=" * 72)
    print(f"  {'pad':>4}  {'role (socket datasheet)':<44} net")
    print("  " + "-" * 68)
    for pad, role, got, want, ok in notes:
        mark = "" if ok else f"   <- expected {want}"
        print(f"  {pad:>4}  {role[:44]:<44} {got}{mark}")

    print()
    print("  Pads this design ties to another signal:")
    for pad, (net, role, others) in shared.items():
        # A ground pad shares its net with fifty refs; printing them all buries
        # the one line that matters. The count is stated so the cut is visible
        # rather than looking like the whole list.
        shown = ", ".join(others[:6]) or "nothing else"
        if len(others) > 6:
            shown += f", and {len(others) - 6} more"
        print(f"    U6.{pad:<3} {role[:40]:<40} -> {net} (with {shown})")

    v33 = op.voltages.get("+3V3")
    print()
    print(f"  Card supply: U6.4 on +3V3 = {v33:.3f} V")

    print()
    print("-" * 72)
    if exposure:
        print("  A shared pad lands on a STRAPPING pin:")
        for pad, role, net, gpio, strap in exposure:
            print(f"    U6.{pad} ({role[:38]}) shares {net} with {gpio}")
            print(f"      {gpio} is latched at reset "
                  f"({strap['locator']}), internal pull: "
                  f"{strap['internal'] or 'NONE'}")
        print()
        print("    The routing generator keeps these pads same-net on "
              "purpose, and the")
        print("    two of them need different arguments:")
        print()
        print("      U6.8 is DAT1, a card contact. The card does not drive it "
              "in the reset")
        print("      window: 'the extended DAT lines (DAT1-DAT3) are input on "
              "power up' —")
        print("      SanDisk industrial p.17 sec 3.1, table 3-1 footnote b. "
              "(The old")
        print("      'tri-states after CMD0' justification was uncited and "
              "about the wrong")
        print("      window; corrected 2026-07-31.)")
        print()
        print("      U6.9 is Cd, the SOCKET's card-detect contact — no card "
              "contact reaches")
        print("      it, so the card cannot drive it at all. What the socket "
              "does is OPEN:")
        print("      the TF-01A drawing carries no schematic and no NO/NC "
              "statement, so")
        print("      whether the Cd blade shorts to the shell (GND) on "
              "insertion is not")
        print("      determinable from it. If it does, BTN_R reads pressed "
              "with a card in.")
        print("      Tracked as CLAIM-006; one bring-up read settles it.")
        print()
        print("    Boot is inert either way, for a reason worth writing down: "
              "table 8 on")
        print("    page 15 shows GPIO3 is IGNORED unless EFUSE_STRAP_JTAG_SEL "
              "is burned,")
        print("    and the factory default leaves it unselected. It stops "
              "being inert the")
        print("    day somebody burns that eFuse.")
    else:
        print("  No shared pad lands on a strapping pin.")

    print()
    print("  Not modelled, and not silently:")
    for key, why in sorted(UNMODELLED.items()):
        print(f"    {key:<14} {why}")

    print()
    print("=" * 72)
    if faults:
        print(f"  FAIL — {len(faults)} bus wiring fault(s):")
        for f in faults:
            print(f"    {f}")
        print("=" * 72)
        return 1
    print("  The four SPI signals land on the pads the socket datasheet "
          "assigns them.")
    print("  The card protocol itself replays in sdcard_protocol.py "
          "(make bench-sdcard):")
    print("  CMD0/CMD8/ACMD41 init and CMD17 block reads, cited from the "
          "spec in-repo.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
