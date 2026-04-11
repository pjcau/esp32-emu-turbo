#!/usr/bin/env python3
"""Signal chain completeness verification — catches broken copper paths.

Verifies that critical signal chains have pads on BOTH the source and
destination components. A net that only appears on one component means
the chain is broken — the copper path is incomplete.

This goes beyond "net exists" to verify "net connects the right endpoints."
"""

import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Set, Tuple

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_FILE = os.path.join(BASE, "hardware", "kicad", ".pcb_cache.json")

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    """Record test result."""
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def load_cache() -> dict:
    """Load PCB cache JSON."""
    with open(CACHE_FILE) as f:
        return json.load(f)


def build_net_ref_map(pads: list) -> Dict[int, Set[str]]:
    """Build net_id -> set of component refs."""
    net_refs: Dict[int, Set[str]] = defaultdict(set)
    for pad in pads:
        if pad["net"] != 0:
            net_refs[pad["net"]].add(pad["ref"])
    return dict(net_refs)


def build_net_name_map(nets: list) -> Tuple[Dict[int, str], Dict[str, int]]:
    """Build bidirectional net ID <-> name maps."""
    id_to_name = {n["id"]: n["name"] for n in nets}
    name_to_id = {n["name"]: n["id"] for n in nets if n["name"]}
    return id_to_name, name_to_id


def verify_chain(
    chain_name: str,
    net_name: str,
    required_refs: List[str],
    net_refs: Dict[int, Set[str]],
    name_to_id: Dict[str, int],
    id_to_name: Dict[int, str],
) -> bool:
    """Verify that a net connects all required component refs.

    Returns True if all refs are present on the net.
    """
    net_id = name_to_id.get(net_name)

    if net_id is None:
        check(
            f"{chain_name}: {net_name} net exists",
            False,
            f"net '{net_name}' not found in PCB",
        )
        return False

    connected_refs = net_refs.get(net_id, set())

    missing = [r for r in required_refs if r not in connected_refs]

    if missing:
        check(
            f"{chain_name}: {net_name} connects {' + '.join(required_refs)}",
            False,
            f"missing: {missing}, found on: {sorted(connected_refs)}",
        )
        return False

    check(
        f"{chain_name}: {net_name} connects {' + '.join(required_refs)}",
        True,
    )
    return True


def test_en_reset_chain(net_refs, name_to_id, id_to_name):
    """1. EN reset chain: SW_RST -> EN net -> ESP32 pin 3 (EN)."""
    print("\n── EN Reset Chain ──")

    # Full chain check: EN net must connect BOTH SW_RST and U1.
    # Currently FAILS because SW_RST→U1 route is incomplete (no trace from
    # via at 98,60 to U1 pin 3 at 88.75,24.78 — F.Cu path crosses 16+ traces).
    # ESP32 boots via internal pull-up, but reset button does not work.
    verify_chain("EN reset", "EN", ["SW_RST", "U1"], net_refs, name_to_id, id_to_name)


def test_audio_chain(net_refs, name_to_id, id_to_name):
    """2. Audio chain: ESP32 I2S_DOUT -> C22 -> PAM8403 -> SPK1."""
    print("\n── Audio Chain ──")

    # I2S signals from U1 to PAM8403 (U5)
    verify_chain("Audio", "I2S_DOUT", ["U1", "U5"], net_refs, name_to_id, id_to_name)
    verify_chain("Audio", "I2S_BCLK", ["U1"], net_refs, name_to_id, id_to_name)
    verify_chain("Audio", "I2S_LRCK", ["U1"], net_refs, name_to_id, id_to_name)

    # DC-blocking cap in audio path
    verify_chain("Audio DC-block", "I2S_DOUT", ["C22", "U5"], net_refs, name_to_id, id_to_name)

    # Speaker output
    verify_chain("Speaker", "SPK+", ["U5", "SPK1"], net_refs, name_to_id, id_to_name)
    verify_chain("Speaker", "SPK-", ["U5", "SPK1"], net_refs, name_to_id, id_to_name)


def test_power_chain(net_refs, name_to_id, id_to_name):
    """3. Power chain: BAT+ -> SW_PWR -> IP5306 -> AMS1117 -> 3V3."""
    print("\n── Power Chain ──")

    # Battery to switch to IP5306
    verify_chain("Battery", "BAT+", ["J3", "SW_PWR", "U2"], net_refs, name_to_id, id_to_name)

    # IP5306 inductor
    verify_chain("Boost", "LX", ["L1", "U2"], net_refs, name_to_id, id_to_name)

    # IP5306 output (+5V) to AMS1117 input
    verify_chain("5V rail", "+5V", ["U2", "U3"], net_refs, name_to_id, id_to_name)

    # AMS1117 output (+3V3) to ESP32
    verify_chain("3V3 rail", "+3V3", ["U3", "U1"], net_refs, name_to_id, id_to_name)

    # VBUS from USB connector to IP5306
    verify_chain("USB power", "VBUS", ["J1", "U2"], net_refs, name_to_id, id_to_name)


def test_display_chain(net_refs, name_to_id, id_to_name):
    """4. Display chain: U1 LCD_D0-D7 -> J4 pads."""
    print("\n── Display Chain ──")

    lcd_data = [f"LCD_D{i}" for i in range(8)]
    lcd_ctrl = ["LCD_CS", "LCD_RST", "LCD_DC", "LCD_WR"]

    for net_name in lcd_data + lcd_ctrl:
        verify_chain("Display", net_name, ["U1", "J4"], net_refs, name_to_id, id_to_name)

    # LCD_RD and LCD_BL are hardwired to +3V3 at J4 (see routing.py DFM v3
    # fix at _fpc_power_traces). The "LCD_RD"/"LCD_BL" logical nets are
    # intentionally fully merged into +3V3 — the panel pads J4.29 (RD) and
    # J4.16/33 (BL) sit directly on the +3V3 copper.
    #
    # Accept either:
    #   (a) the logical net reaches J4, OR
    #   (b) the logical net is fully merged (0 refs) AND J4 has pads on +3V3.
    v3v3_id = name_to_id.get("+3V3")
    v3v3_refs = net_refs.get(v3v3_id, set()) if v3v3_id else set()
    for net_name in ["LCD_RD", "LCD_BL"]:
        net_id = name_to_id.get(net_name)
        refs = net_refs.get(net_id, set()) if net_id else set()
        merged_into_3v3 = (len(refs) == 0) and ("J4" in v3v3_refs)
        ok = ("J4" in refs) or merged_into_3v3
        detail = ""
        if not ok:
            detail = f"found on: {sorted(refs)}; +3V3 on J4={'J4' in v3v3_refs}"
        elif merged_into_3v3:
            detail = "(merged into +3V3 at J4 by design)"
        check(
            f"Display: {net_name} reaches J4 (hardwired)",
            ok,
            detail,
        )


def test_sd_chain(net_refs, name_to_id, id_to_name):
    """5. SD chain: U1 SD_MOSI/MISO/CLK/CS -> U6."""
    print("\n── SD Card Chain ──")

    for net_name in ["SD_MOSI", "SD_MISO", "SD_CLK", "SD_CS"]:
        verify_chain("SD card", net_name, ["U1", "U6"], net_refs, name_to_id, id_to_name)


def test_usb_chain(net_refs, name_to_id, id_to_name):
    """6. USB chain: J1 D+/D- -> R22/R23 -> U4 TVS -> U1."""
    print("\n── USB Chain ──")

    # USB connector to TVS and series resistors
    verify_chain("USB D+", "USB_D+", ["J1", "R22", "U4"], net_refs, name_to_id, id_to_name)
    verify_chain("USB D-", "USB_D-", ["J1", "R23", "U4"], net_refs, name_to_id, id_to_name)

    # Series resistors to ESP32
    verify_chain("USB D+ MCU", "USB_DP_MCU", ["R22", "U1"], net_refs, name_to_id, id_to_name)
    verify_chain("USB D- MCU", "USB_DM_MCU", ["R23", "U1"], net_refs, name_to_id, id_to_name)


def test_button_chain(net_refs, name_to_id, id_to_name):
    """7. Button chain: each SW -> pull-up R -> debounce C -> U1 GPIO."""
    print("\n── Button Chain ──")

    # Button name -> (switch ref, expected components on the net)
    buttons = {
        "BTN_UP":     ("SW1",  ["SW1", "U1"]),
        "BTN_DOWN":   ("SW2",  ["SW2", "U1"]),
        "BTN_LEFT":   ("SW3",  ["SW3", "U1"]),
        "BTN_RIGHT":  ("SW4",  ["SW4", "U1"]),
        "BTN_A":      ("SW5",  ["SW5", "U1"]),
        "BTN_B":      ("SW6",  ["SW6", "U1"]),
        "BTN_X":      ("SW7",  ["SW7", "U1"]),
        "BTN_Y":      ("SW8",  ["SW8", "U1"]),
        "BTN_START":  ("SW9",  ["SW9", "U1"]),
        "BTN_SELECT": ("SW10", ["SW10", "U1"]),
        "BTN_L":      ("SW11", ["SW11", "U1"]),
        "BTN_R":      ("SW12", ["SW12", "U1"]),
    }

    for net_name, (sw_ref, required) in buttons.items():
        verify_chain("Button", net_name, required, net_refs, name_to_id, id_to_name)

    # Menu button combo (BTN_MENU net should connect R19 pull-up)
    verify_chain("Menu combo", "BTN_MENU", ["R19"], net_refs, name_to_id, id_to_name)
    verify_chain("Menu combo", "MENU_K", ["D1", "SW13"], net_refs, name_to_id, id_to_name)


def test_dedicated_pins(net_refs, name_to_id, id_to_name):
    """8. Dedicated pins: EN, USB CC1/CC2, IP5306_KEY, LEDs."""
    print("\n── Dedicated Pins ──")

    # USB CC pull-downs (5.1k to GND)
    verify_chain("USB CC1", "USB_CC1", ["J1", "R1"], net_refs, name_to_id, id_to_name)
    verify_chain("USB CC2", "USB_CC2", ["J1", "R2"], net_refs, name_to_id, id_to_name)

    # IP5306 KEY pin (pull-down via R16)
    verify_chain("IP5306 KEY", "IP5306_KEY", ["U2", "R16"], net_refs, name_to_id, id_to_name)

    # LED indicator chains
    verify_chain("LED1", "LED1_RA", ["LED1", "R17"], net_refs, name_to_id, id_to_name)
    verify_chain("LED2", "LED2_RA", ["LED2", "R18"], net_refs, name_to_id, id_to_name)

    # PAM8403 VREF
    verify_chain("PAM VREF", "PAM_VREF", ["U5", "C21"], net_refs, name_to_id, id_to_name)


def main():
    """Run all signal chain verification checks."""
    print("=" * 60)
    print("Signal Chain Completeness Verification")
    print("=" * 60)

    if not os.path.exists(CACHE_FILE):
        print(f"  ERROR: PCB cache not found: {CACHE_FILE}")
        print("  Run: python3 scripts/generate_pcb/generate.py")
        return 1

    cache = load_cache()
    pads = cache["pads"]
    nets = cache["nets"]

    net_refs = build_net_ref_map(pads)
    id_to_name, name_to_id = build_net_name_map(nets)

    # Run all chain verifications
    test_en_reset_chain(net_refs, name_to_id, id_to_name)
    test_audio_chain(net_refs, name_to_id, id_to_name)
    test_power_chain(net_refs, name_to_id, id_to_name)
    test_display_chain(net_refs, name_to_id, id_to_name)
    test_sd_chain(net_refs, name_to_id, id_to_name)
    test_usb_chain(net_refs, name_to_id, id_to_name)
    test_button_chain(net_refs, name_to_id, id_to_name)
    test_dedicated_pins(net_refs, name_to_id, id_to_name)

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
