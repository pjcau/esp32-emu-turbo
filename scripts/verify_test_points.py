#!/usr/bin/env python3
"""Test 12: Test Point Accessibility.

Advisory check that key signals have accessible probe points for debugging.

For each required signal, checks:
1. At least one pad >= 0.5mm accessible on a copper layer
2. Or a via with >= 0.45mm drill (probeable with standard probe)
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"
sys.path.insert(0, str(BASE / "scripts"))
from pcb_cache import load_cache

PASS = 0
WARN = 0
INFO_COUNT = 0

MIN_PAD_DIM = 0.5       # mm — minimum pad dimension for probing
MIN_VIA_DRILL = 0.45    # mm — minimum via drill for test probe

# Required test points by category
REQUIRED_SIGNALS = {
    "Power rails": ["+3V3", "+5V", "VBUS", "BAT+", "GND"],
    "USB": ["USB_D+", "USB_D-"],
    "SPI (SD card)": ["SD_CLK", "SD_MOSI", "SD_MISO", "SD_CS"],
    "I2S (audio)": ["I2S_DOUT", "I2S_BCLK", "I2S_LRCK"],
    "Display": ["LCD_WR", "LCD_DC", "LCD_CS"],
}


def check_pass(name, detail=""):
    global PASS
    PASS += 1
    print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))


def check_warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  WARN  {name}  {detail}")


def check_info(name, detail=""):
    global INFO_COUNT
    INFO_COUNT += 1
    print(f"  INFO  {name}  {detail}")


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

    for category, signals in REQUIRED_SIGNALS.items():
        print(f"\n  [{category}]")
        for sig in signals:
            net_id = net_id_by_name.get(sig)
            if net_id is None:
                check_warn(f"{sig}: net not found in PCB")
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
                          f"{best['w']:.1f}x{best['h']:.1f}mm")

                if best["w"] >= 1.0 or best["h"] >= 1.0:
                    check_pass(f"{sig}: {detail}")
                else:
                    check_info(f"{sig}: {detail} (fine-pitch, use micro probe)")

            elif probeable_vias:
                best = max(probeable_vias, key=lambda v: v["drill"])
                check_pass(f"{sig}",
                           f"via at ({best['x']:.1f}, {best['y']:.1f}) "
                           f"drill={best['drill']:.2f}mm")

            elif sig_pads:
                # Pads exist but all too small
                best = max(sig_pads, key=lambda p: min(p["w"], p["h"]))
                check_info(f"{sig}: smallest pad {best['w']:.2f}x{best['h']:.2f}mm at {best['ref']}",
                           "(too small for standard probe)")

            elif sig_vias:
                best = max(sig_vias, key=lambda v: v["drill"])
                check_info(f"{sig}: best via drill={best['drill']:.2f}mm",
                           f"(< {MIN_VIA_DRILL}mm, difficult to probe)")

            else:
                check_warn(f"{sig}: no pads or vias found",
                           "(net may be intentionally unrouted)")

    # Summary
    total = PASS + WARN + INFO_COUNT
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} accessible, {INFO_COUNT} limited access, {WARN} no test point")
    if WARN:
        print("  (warnings are advisory — debugging may be harder without test points)")
    print(f"{'=' * 60}")

    # Advisory only — never fail
    return 0


if __name__ == "__main__":
    sys.exit(main())
