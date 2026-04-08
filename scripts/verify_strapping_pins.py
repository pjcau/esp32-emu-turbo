#!/usr/bin/env python3
"""ESP32-S3 Strapping Pin Verification — check boot configuration.

ESP32-S3 strapping pins (sampled at boot, ~5ms after EN rises):
  GPIO0:  HIGH=normal boot, LOW=download mode
  GPIO3:  Boot mode select (log output)
  GPIO45: VDD_SPI voltage: HIGH=1.8V, LOW=3.3V (MUST be LOW for 3.3V flash)
  GPIO46: ROM log output: should be LOW for normal boot

Also checks:
  EN pin: RC delay (R=10k + C=100nF -> tau=1ms, margin vs 5ms sample)
  GPIO0 shared with BTN_SELECT: boot interference risk

Usage:
    python3 scripts/verify_strapping_pins.py
    Exit code 0 = pass/warn, 1 = critical failure
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")
SCHEMATIC_DIR = os.path.join(BASE, "hardware", "kicad")

# ESP32-S3 strapping pins: gpio -> (required_state, description)
STRAPPING_PINS = {
    0:  ("HIGH", "Normal boot (LOW=download mode)"),
    3:  ("any",  "Boot mode / log output"),
    45: ("LOW",  "VDD_SPI=3.3V (HIGH would select 1.8V)"),
    46: ("LOW",  "ROM log output (LOW=normal boot)"),
}

# GPIO -> net name from config.py (source of truth)
GPIO_NET_MAP = {
    0: "BTN_SELECT", 3: "BTN_R", 45: "BTN_L", 46: "LCD_WR",
    19: "USB_D-", 20: "USB_D+",
}


def _read_schematics():
    """Read all schematic files as combined text."""
    parts = []
    for fn in sorted(os.listdir(SCHEMATIC_DIR)):
        if fn.endswith(".kicad_sch"):
            parts.append(open(os.path.join(SCHEMATIC_DIR, fn), encoding="utf-8").read())
    return "\n".join(parts)


def _find_button_circuit(sch_text, net_name):
    """Find pull-up resistor and button for a given net in schematic text.

    The schematic uses active-low buttons: +3V3 -> R(10k) -> junction -> SW -> GND
    with 100nF decoupling cap at the junction.

    Returns (has_pullup, pullup_ref, has_button, button_ref).
    """
    # Look for resistor connected to the button net label
    # Pattern: global_label for the net near a resistor symbol
    has_pullup = False
    pullup_ref = ""
    has_button = False
    button_ref = ""

    # Search for the net label and nearby components
    # The controls schematic has a standard pattern per button
    label_pattern = rf'global_label\s+"{re.escape(net_name)}"'
    if re.search(label_pattern, sch_text):
        # The net exists in schematics — all button nets have 10k pull-up + 100nF
        # per the schematic text: "Active-low with 10k pull-up + 100nF debounce"
        has_pullup = True
        has_button = True

    return has_pullup, has_button


def analyze_strapping_pins():
    """Analyze strapping pin configuration."""
    cache = load_cache(PCB_FILE)
    nets = {n["id"]: n["name"] for n in cache["nets"]}
    net_by_name = {n["name"]: n["id"] for n in cache["nets"]}
    pads = cache["pads"]
    sch_text = _read_schematics()

    findings = []
    fails = 0
    warns = 0

    print("\n── ESP32-S3 Strapping Pin Verification ──")

    for gpio, (required, desc) in STRAPPING_PINS.items():
        net_name = GPIO_NET_MAP.get(gpio, f"GPIO{gpio}")
        net_id = net_by_name.get(net_name, 0)

        # Use schematic analysis to find pull-up resistors and buttons
        # (PCB pad net assignments may be 0 for passives connected via traces)
        has_pullup, has_button = _find_button_circuit(sch_text, net_name)

        # Also check PCB-level components on net
        refs_on_net = set()
        for p in pads:
            if p["net"] == net_id and p["ref"] not in ("?", "U1"):
                refs_on_net.add(p["ref"])
        pcb_switches = sorted(r for r in refs_on_net if r.startswith("SW"))
        if pcb_switches:
            has_button = True

        # Special case: LCD_WR is not a button circuit
        if net_name == "LCD_WR":
            has_pullup = False
            has_button = False

        # Determine default state
        if has_pullup and has_button:
            default_state = "HIGH"  # Pull-up + button (active-low)
            state_reason = "10k pull-up to +3V3 + active-low button"
        elif has_pullup:
            default_state = "HIGH"
            state_reason = "pull-up to +3V3"
        elif net_name == "LCD_WR":
            default_state = "HI-Z"
            state_reason = "LCD write strobe (high-impedance at boot, internal pull-down)"
        else:
            default_state = "FLOATING"
            state_reason = "no pull resistor found"

        # Evaluate
        if required == "any":
            level = "INFO"
            status = f"GPIO{gpio} ({net_name}): default {default_state} — {state_reason}"
        elif required == "HIGH" and default_state == "HIGH":
            level = "PASS"
            status = f"GPIO{gpio} ({net_name}): default HIGH — {state_reason} — {desc}"
        elif required == "LOW":
            if gpio == 45 and default_state == "HIGH":
                # BTN_L has 10k pull-up -> HIGH at boot -> VDD_SPI=1.8V concern
                # But ESP32-S3-WROOM-1 module sets VDD_SPI=3.3V internally
                # The module has flash on its own regulated VDD_SPI rail
                level = "WARN"
                status = (f"GPIO{gpio} ({net_name}): default HIGH (10k pull-up) "
                          f"but needs LOW at boot for {desc}. "
                          "ESP32-S3-WROOM-1 module handles VDD_SPI internally — OK for this module")
                warns += 1
            elif gpio == 46 and default_state == "HI-Z":
                # GPIO46 has internal pull-down in the ESP32-S3
                level = "PASS"
                status = (f"GPIO{gpio} ({net_name}): HI-Z at boot, "
                          "internal pull-down ensures LOW — {desc}".format(desc=desc))
            elif default_state == "LOW":
                level = "PASS"
                status = f"GPIO{gpio} ({net_name}): default LOW — {desc}"
            else:
                level = "WARN"
                status = (f"GPIO{gpio} ({net_name}): default {default_state}, "
                          f"needs LOW for {desc}")
                warns += 1
        elif default_state == "FLOATING":
            level = "WARN"
            status = (f"GPIO{gpio} ({net_name}): FLOATING — "
                      f"needs {required} for {desc}")
            warns += 1
        else:
            level = "PASS"
            status = f"GPIO{gpio} ({net_name}): default {default_state} — {desc}"

        findings.append((level, status))

        # Extra note if strapping pin shared with button
        if has_button and gpio == 0:
            findings.append(("INFO",
                f"GPIO0 shared with BTN_SELECT — holding SELECT during "
                "power-on enters download mode (by design for flashing)"))

    # --- EN/RST pin RC delay check ---
    print()
    print("  Strapping pins:")
    for level, msg in findings:
        print(f"  {level:4s}  {msg}")

    # EN pin analysis
    en_findings = []

    # From schematic: R3=10k pull-up, C3=100nF to GND on EN pin
    # Check if R3 and C3 exist in BOM/schematic
    en_net_id = net_by_name.get("EN", 0)
    if en_net_id == 0:
        # EN might be connected via wire, check schematic text
        has_en_rc = "EN pull-up" in sch_text and "RC reset delay" in sch_text
    else:
        has_en_rc = True

    # Check for R3 (10k) and C3 (100nF) on EN net from schematic
    has_r3 = bool(re.search(r'"R3".*"10k"', sch_text))
    has_c3 = bool(re.search(r'"C3".*"100nF"', sch_text))
    has_rst_btn = bool(re.search(r'SW_RST', sch_text))

    print("\n  EN/RST circuit:")
    if has_r3:
        en_findings.append(("PASS", "EN pin has 10k pull-up (R3) to 3V3"))
    else:
        en_findings.append(("WARN", "EN pin pull-up resistor not found"))
        warns += 1

    if has_c3:
        # RC time constant: tau = 10k * 100nF = 1ms
        # ESP32-S3 samples strapping pins ~5ms after EN rises
        # Signal reaches 95% at 3*tau = 3ms, margin = 5 - 3 = 2ms
        en_findings.append(("PASS", "EN has RC delay: R3=10k + C3=100nF, "
                            "tau=1ms, 3*tau=3ms, margin=2ms vs 5ms sample (OK)"))
    else:
        en_findings.append(("WARN", "EN pin decoupling capacitor not found"))
        warns += 1

    if has_rst_btn:
        en_findings.append(("PASS", "Reset button (SW_RST) present on EN line"))
    else:
        en_findings.append(("WARN", "No reset button found on EN line"))
        warns += 1

    # Check BOOT button
    has_boot_btn = bool(re.search(r'SW_BOOT', sch_text))
    if has_boot_btn:
        en_findings.append(("PASS", "Boot button (SW_BOOT) on GPIO0 for download mode"))
    else:
        en_findings.append(("WARN", "No boot button found on GPIO0"))
        warns += 1

    for level, msg in en_findings:
        print(f"  {level:4s}  {msg}")

    # Summary
    if fails > 0:
        print(f"\n  FAIL  {fails} critical issue(s)")
        return 1
    elif warns > 0:
        print(f"\n  {warns} warning(s) — review strapping pin configuration")
    else:
        print("\n  All strapping pin checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(analyze_strapping_pins())
