"""Virtual Bench T3.3 — the SD card's bus, and the pads it shares with signals.

Checks the four SPI signals against the TF-01A socket's pad roles, then asks
which socket pads carry a net they are not a card contact for, and whether
any of those lands on a strapping pin. Today the answer is none. Getting to
none took three passes and the last one is the interesting one.

**U6.8 (DAT1) shares SD_MISO, and that is fine.** The routing generator
(`generate_pcb/routing/_assemble.py`) records why: the SD_MISO track
physically crosses the pad, so the pad is given the same net to keep the
overlap same-net rather than a fab short. The card does not drive it,
because "the extended DAT lines (DAT1-DAT3) are input on power up"
(SanDisk industrial p.17 sec 3.1, table 3-1 footnote b) and in SPI mode
contact 8 is RSV (table 3-2, p.18). Note the shape of that argument: it is
about the power-up window, because the original justification ("the card
tri-states DAT1/DAT2 once CMD0 selects SPI mode") was both uncited and
about the wrong window — the GPIO3 strap is latched at reset, before any
CMD0. Corrected 2026-07-31 by the T3.3 protocol model.

**U6.9 had the same entry, and it should never have had one.** It carried
BTN_R (= GPIO3, a strapping pin) on the same reasoning, and this module
used to open by calling that exposure real-but-inert, citing table 8 on
page 15 of the module datasheet: GPIO3 is ignored unless an eFuse selects
it (EFUSE_STRAP_JTAG_SEL) and the factory default leaves it unselected.

All of that analysis was about the wrong object. A microSD card has EIGHT
contacts. The ninth pad on this socket is the card-DETECT spring, which
mates with the grounded shell — a switch to GND, not an idle data line,
so no statement about what a card drives applies to it and no eFuse
argument makes it inert. In one card state (most plausibly card-inserted,
i.e. throughout gameplay) it grounded BTN_R outright. Fixed as R31-HIGH-2
by rerouting the BTN_R riser east of the pad row; the pad is off-net and
`exposure` is now expected to be empty.

Worth keeping in view: every layer agreed with itself for three passes
(9709bea removed the pad, 775e9fd restored it, eff85e6 re-justified it)
because they all inherited one wrong pin identity from the pad above it.
The socket's datasheet is mechanical-only, so no gate could have known.

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
# are this board's SPI assignment.
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
              "purpose. Why the")
        print("    card does not drive them in the reset window: 'the "
              "extended DAT lines")
        print("    (DAT1-DAT3) are input on power up' — SanDisk industrial "
              "p.17 sec 3.1,")
        print("    table 3-1 footnote b. (The old 'tri-states after CMD0' "
              "justification")
        print("    was uncited and about the wrong window; corrected "
              "2026-07-31.)")
        print()
        print("    Currently inert, for a reason worth writing down: table 8 "
              "on page 15")
        print("    shows GPIO3 is IGNORED unless EFUSE_STRAP_JTAG_SEL is "
              "burned, and the")
        print("    factory default leaves it unselected. It stops being inert "
              "the day")
        print("    somebody burns that eFuse.")
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
