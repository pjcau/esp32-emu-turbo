"""Virtual Bench T3.3 — the SD card's bus, and the pin it shares with a button.

Checks the four SPI signals against the TF-01A socket's pad roles, then asks
the question the socket's own wiring raises: **U6.9 (DAT2) sits on the BTN_R
net, and BTN_R is GPIO3 — a strapping pin.**

That assignment is deliberate and analysed. The routing generator
(`generate_pcb/routing/_assemble.py`) records it: the BTN_R track physically
crosses the U6.8/U6.9 pads, so the pads are given the same net to keep the
overlap same-net rather than a fab short. The original analysis said "SAFE
as long as firmware stays in SPI mode", because an SD card tri-states
DAT1/DAT2 once CMD0 has put it in SPI mode.

**The strapping sample happens before any of that.** GPIO3 is latched at
reset, before the boot ROM runs — so "the firmware keeps the card in SPI
mode" is an argument about the wrong window. In the reset window the card
has received no CMD0.

**And the tri-state claim itself was uncited** — corrected 2026-07-31 by
the T3.3 protocol model: no held document says CMD0 tri-states anything.
What the card datasheet actually says is "the extended DAT lines
(DAT1-DAT3) are input on power up" (SanDisk industrial p.17 sec 3.1,
table 3-1 footnote b) and that in SPI mode contacts 8/9 are RSV (table
3-2, p.18). The power-up input state — which covers the reset window — is
the citable reason U6.9 does not drive BTN_R. Right conclusion, wrong
mechanism, in two places; both now corrected.

Whether that matters is a second question, and the answer today is no, for a
reason worth writing down: table 8 on page 15 of the module datasheet shows
GPIO3 is *ignored* unless an eFuse selects it (EFUSE_STRAP_JTAG_SEL), and the
factory default leaves it unselected. So the exposure is real but currently
inert — and it stops being inert the day someone burns that eFuse.

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
