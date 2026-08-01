#!/usr/bin/env python3
"""Test 12: Test Point Accessibility — blocking gate.

Every required signal must expose probeable copper for a multimeter: the
user debugs with photos and a probe only (the C2-reversed short was
diagnosed by continuity on exposed copper), so a signal nothing can reach
is a finding, not a footnote.

For each required signal:
1. a pad >= 0.5mm on a copper layer, or a via with >= 0.45mm drill
   -> PASS (0.5-1.0mm pads PASS as INFO "fine-pitch, use micro probe" —
   inherent to connector footprints like USB-C, deliberately not a
   failure; adding a probe stub to a 90-ohm pair would cost more than
   the access is worth)
2. copper exists but none of it is probeable (all pads under MIN_PAD_DIM,
   or only sub-MIN_VIA_DRILL vias), or no copper at all -> FAIL (exit 1)

Structurally NOT negotiable: a net named in REQUIRED_SIGNALS that does not
exist on the board exits 2 — the law would be describing a different
board, which makes every verdict above it untrustworthy. To retire a
signal, move it to DEMOTED_SIGNALS with the finding written down; never
delete it silently.
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"
sys.path.insert(0, str(BASE / "scripts"))
from pcb_cache import load_cache

PASS = 0
FAIL = 0
INFO_COUNT = 0
ERROR = 0

MIN_PAD_DIM = 0.5       # mm — minimum pad dimension for probing
MIN_VIA_DRILL = 0.45    # mm — minimum via drill for test probe

# Required test points by category.
# Every entry carries one line of WHY it earns a probe point — which bring-up
# failure it lets you diagnose with a multimeter. No line, no entry.
REQUIRED_SIGNALS = {
    "Power rails": ["+3V3", "+5V", "VBUS", "BAT+", "GND"],
    "USB": ["USB_D+", "USB_D-"],
    "SPI (SD card)": ["SD_CLK", "SD_MOSI", "SD_MISO", "SD_CS"],
    "I2S (audio)": ["I2S_DOUT"],  # BCLK/LRCK retired 2026-07-26 (R10-LOW-2)
    "Display": ["LCD_WR", "LCD_DC", "LCD_CS"],
    "Bring-up (first power-on)": [
        # EN — is the chip being held in reset? A dead board with a good +3V3
        # rail is EN stuck low (R3/C31 RC wrong, SW15 shorted, pull-up open).
        "EN",
        # BTN_SELECT — which boot mode did it strap into? This IS the GPIO0
        # strap net (config.py: GPIO 0 -> BTN_SELECT); SW14/BOOT pulls it low.
        # Low at reset = ROM download mode, high = run the flashed app, so its
        # DC level at power-on says whether the board even tried to boot.
        "BTN_SELECT",
        # BUCK_FB — is the regulator regulating, or is the divider wrong? U3
        # servos this node to 0.600 V; measuring it separates "buck is dead"
        # from "buck is fine, R25/R26 set the wrong Vout" (the R25 bug class).
        "BUCK_FB",
    ],
}

# Signals the law names but deliberately does NOT require, each with the
# finding that demoted it. Printed on every run — a demotion stays visible.
DEMOTED_SIGNALS = {
    "TXD0/RXD0 (UART0)": (
        "no dedicated net on this board — config.py assigns GPIO43/GPIO44 "
        "(the ESP32-S3 ROM bootloader's U0TXD/U0RXD) to SD_MISO/SD_MOSI, so "
        "the bootloader banner comes out on the SD_MISO copper already "
        "required above under 'SPI (SD card)'. Requiring it twice would "
        "double-count the same pad, not buy a second probe point."
    ),
}


def check_pass(name, detail=""):
    global PASS
    PASS += 1
    print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))


def check_fail(name, detail=""):
    global FAIL
    FAIL += 1
    print(f"  FAIL  {name}  {detail}")


def check_info(name, detail=""):
    global INFO_COUNT
    INFO_COUNT += 1
    print(f"  INFO  {name}  {detail}")


def check_error(name, detail=""):
    global ERROR
    ERROR += 1
    print(f"  ERROR {name}  {detail}")


def main():
    print("=" * 60)
    print("Test 12: Test Point Accessibility")
    print("=" * 60)

    cache = load_cache(PCB_FILE)
    pads = cache["pads"]
    vias = cache["vias"]

    # Build net name -> id mapping
    net_id_by_name = {n["name"]: n["id"] for n in cache["nets"]}

    print(f"\n── Test Point Accessibility ──")

    deficit = []

    for category, signals in REQUIRED_SIGNALS.items():
        print(f"\n  [{category}]")
        for sig in signals:
            net_id = net_id_by_name.get(sig)
            if net_id is None:
                # Structural: the law names copper this board does not have.
                # Not a finding about the board — a broken law. See module
                # docstring: demote it in DEMOTED_SIGNALS or fix the name.
                check_error(f"{sig}: net does not exist on this board",
                            "(REQUIRED_SIGNALS names a net the PCB never "
                            "declares — rename it or move it to "
                            "DEMOTED_SIGNALS with the finding)")
                deficit.append((category, sig, "net absent"))
                continue

            # Find accessible pads for this net
            sig_pads = [p for p in pads if p["net"] == net_id]
            probeable_pads = [p for p in sig_pads
                              if min(p["w"], p["h"]) >= MIN_PAD_DIM]

            # Find probeable vias
            sig_vias = [v for v in vias if v["net"] == net_id]
            probeable_vias = [v for v in sig_vias
                              if v["drill"] >= MIN_VIA_DRILL]

            if probeable_pads:
                # Pick the largest pad as best probe point
                best = max(probeable_pads, key=lambda p: p["w"] * p["h"])
                detail = (f"accessible via {best['ref']} pad "
                          f"({best['x']:.1f}, {best['y']:.1f}) "
                          f"{best['w']:.1f}x{best['h']:.1f}mm "
                          f"on {best['layer']}")

                if best["w"] >= 1.0 or best["h"] >= 1.0:
                    check_pass(f"{sig}: {detail}")
                else:
                    check_info(f"{sig}: {detail} (fine-pitch, use micro probe)")
                    deficit.append((category, sig,
                                    f"only fine-pitch copper "
                                    f"({best['w']:.2f}x{best['h']:.2f}mm at "
                                    f"{best['ref']})"))

            elif probeable_vias:
                best = max(probeable_vias, key=lambda v: v["drill"])
                check_pass(f"{sig}",
                           f"via at ({best['x']:.1f}, {best['y']:.1f}) "
                           f"drill={best['drill']:.2f}mm")

            elif sig_pads:
                # Pads exist but all too small — nothing a probe can reach
                best = max(sig_pads, key=lambda p: min(p["w"], p["h"]))
                check_fail(f"{sig}: largest pad {best['w']:.2f}x{best['h']:.2f}mm at {best['ref']}",
                           f"(no pad reaches MIN_PAD_DIM={MIN_PAD_DIM}mm)")
                deficit.append((category, sig,
                                f"no pad reaches MIN_PAD_DIM={MIN_PAD_DIM}mm "
                                f"(best {best['ref']} "
                                f"{best['w']:.2f}x{best['h']:.2f}mm)"))

            elif sig_vias:
                best = max(sig_vias, key=lambda v: v["drill"])
                check_fail(f"{sig}: vias only, best drill={best['drill']:.2f}mm",
                           f"(< {MIN_VIA_DRILL}mm — not probeable)")
                deficit.append((category, sig,
                                f"vias only, best drill {best['drill']:.2f}mm "
                                f"< MIN_VIA_DRILL={MIN_VIA_DRILL}mm"))

            else:
                check_fail(f"{sig}: no pads or vias found",
                           "(no copper a probe can reach)")
                deficit.append((category, sig, "no copper at all"))

    # Demotions — printed every run so a retired signal never goes quiet
    print(f"\n  [Demoted — named by the law, not required]")
    for sig, finding in DEMOTED_SIGNALS.items():
        check_info(f"{sig}:", finding)

    # Deficit — which required signals a multimeter cannot reach today
    print(f"\n── Probe deficit ──")
    if deficit:
        for category, sig, why in deficit:
            print(f"  {sig:<12} [{category}]  {why}")
    else:
        print("  none — every required signal has probeable copper")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} accessible, {INFO_COUNT} limited access, "
          f"{FAIL} no test point, {ERROR} structural")
    if FAIL:
        print("  FAIL: a required signal has no copper a probe can reach — "
              "add a test point or demote the signal with its finding")
    if ERROR:
        print("  STRUCTURAL ERROR: the law describes a board that is not this "
              "one — no verdict above is trustworthy")
    print(f"{'=' * 60}")

    if ERROR:
        return 2
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
