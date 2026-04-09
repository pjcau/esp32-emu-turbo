#!/usr/bin/env python3
"""Net Function Classifier — infers signal function from net names.

Reusable utility that classifies PCB nets into functional categories
based on naming patterns. Tailored to the ESP32 Emu Turbo project.

Usage:
    from net_classifier import classify_net, classify_all_nets, validate_net_function_match
    category = classify_net("I2S_BCLK")  # -> "i2s"
    grouped = classify_all_nets()         # -> {"i2s": ["I2S_BCLK", ...], ...}
    issues = validate_net_function_match() # -> ["GPIO15 (I2S_BCLK): ..."]

CLI:
    python3 scripts/net_classifier.py
    python3 scripts/net_classifier.py --validate
"""

import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

# ---------------------------------------------------------------------------
# Pattern database — order matters (first match wins)
# ---------------------------------------------------------------------------

NET_PATTERNS: dict[str, list[str]] = {
    "power": [r"^\+[35]V", r"^VCC", r"^VBUS", r"^BAT\+", r"^LX$"],
    "gnd": [r"^GND$"],
    "i2c": [r"I2C", r"SDA", r"SCL"],
    "spi": [r"SPI", r"MOSI", r"MISO", r"SD_CLK", r"SD_CS"],
    "i2s": [r"I2S", r"BCLK", r"LRCK", r"DOUT"],
    "uart": [r"UART", r"^TX$", r"^RX$", r"^TXD", r"^RXD"],
    "usb": [r"USB", r"^D[+-]$", r"CC[12]"],
    "lcd_data": [r"LCD_D[0-7]"],
    "lcd_ctrl": [r"LCD_CS", r"LCD_RST", r"LCD_DC", r"LCD_WR", r"LCD_RD", r"LCD_BL"],
    "button": [r"BTN_"],
    "led": [r"LED"],
}

# Compiled patterns (built once)
_COMPILED: dict[str, list[re.Pattern]] = {
    cat: [re.compile(p) for p in pats]
    for cat, pats in NET_PATTERNS.items()
}

# ESP32-S3 GPIO function capabilities (signal prefix -> required capability)
# All GPIOs 0-21, 38-48 support any peripheral via GPIO Matrix,
# so validation focuses on USB-dedicated pins and reserved ranges.
_SIGNAL_REQUIREMENTS: dict[str, str] = {
    "USB_D": "usb",
    "I2S_": "gpio",
    "SD_": "gpio",
    "LCD_": "gpio",
    "BTN_": "gpio",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_net(net_name: str) -> str:
    """Classify a single net name into a functional category.

    Returns one of: "power", "gnd", "i2c", "spi", "i2s", "uart", "usb",
    "lcd_data", "lcd_ctrl", "button", "led", "unknown".
    """
    if not net_name or net_name.startswith("unconnected-"):
        return "unknown"
    for category, patterns in _COMPILED.items():
        for pat in patterns:
            if pat.search(net_name):
                return category
    return "unknown"


def classify_all_nets() -> dict[str, list[str]]:
    """Classify all nets from pcb_cache into functional categories.

    Returns dict of category -> [net_names], sorted alphabetically.
    """
    cache = load_cache()
    result: dict[str, list[str]] = {}
    for net in cache["nets"]:
        name = net["name"]
        if not name:
            continue
        cat = classify_net(name)
        result.setdefault(cat, []).append(name)
    # Sort each category
    for cat in result:
        result[cat].sort()
    return result


def validate_net_function_match() -> list[str]:
    """Cross-check net names against GPIO functions in config.py.

    Verifies that signal names match expected GPIO capabilities.
    Example: net "USB_D+" should be on GPIO20 (dedicated USB pin).

    Returns list of issue strings (empty = all OK).
    """
    # Import config.py GPIO_NETS
    sys.path.insert(0, os.path.join(BASE, "scripts", "generate_schematics"))
    try:
        from config import GPIO_NETS
    except ImportError:
        return ["Cannot import config.GPIO_NETS"]

    # USB dedicated pins
    USB_PINS = {19: "USB_D-", 20: "USB_D+"}
    issues = []

    for gpio, signal in GPIO_NETS.items():
        cat = classify_net(signal)

        # USB signals must be on dedicated USB pins
        if cat == "usb" and signal.startswith("USB_D"):
            if gpio not in USB_PINS:
                issues.append(
                    f"GPIO{gpio} ({signal}): USB data signal on non-USB pin"
                )
            elif USB_PINS[gpio] != signal:
                issues.append(
                    f"GPIO{gpio} ({signal}): wrong USB pin assignment "
                    f"(expected {USB_PINS[gpio]})"
                )

        # Non-USB signals must NOT be on USB-dedicated pins
        if cat != "usb" and gpio in USB_PINS:
            issues.append(
                f"GPIO{gpio} ({signal}): non-USB signal on USB-dedicated pin"
            )

    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Net Function Classifier")
    parser.add_argument("--validate", action="store_true",
                        help="Cross-check nets vs GPIO functions")
    args = parser.parse_args()

    grouped = classify_all_nets()

    print("=" * 50)
    print("  NET FUNCTION CLASSIFICATION")
    print("=" * 50)

    total = 0
    for cat in list(NET_PATTERNS.keys()) + ["unknown"]:
        nets = grouped.get(cat, [])
        if not nets:
            continue
        total += len(nets)
        print(f"\n  {cat.upper()} ({len(nets)}):")
        for n in nets:
            print(f"    {n}")

    print(f"\n  Total: {total} nets classified")

    if args.validate:
        print("\n" + "=" * 50)
        print("  NET vs GPIO VALIDATION")
        print("=" * 50)
        issues = validate_net_function_match()
        if issues:
            for issue in issues:
                print(f"  FAIL  {issue}")
            print(f"\n  {len(issues)} issue(s) found")
        else:
            print("  PASS  All net-to-GPIO assignments valid")

    return 0


if __name__ == "__main__":
    sys.exit(main())
