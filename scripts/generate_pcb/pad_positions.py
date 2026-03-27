"""Compute absolute PCB-level pad positions for all components.

This module resolves the correct absolute (x, y) position for every pad
on the board, accounting for:
  - Footprint-local pad coordinates
  - B.Cu X-mirroring (KiCad convention: negate pad X for back-side)
  - Footprint rotation (90°, 180°, etc.)
  - Footprint placement position on the board

Usage:
    pads = get_all_pad_positions()
    # Returns {ref: {pad_num: (abs_x, abs_y, width, height), ...}, ...}

    pos = get_pad(pads, "U1", "4")  # ESP32 pin 4
    pos = get_pad(pads, "J4", "11") # FPC pin 11
"""

import math
import re

from . import footprints as FP
from .board import _component_placeholders


def get_all_pad_positions():
    """Compute absolute pad positions for all placed footprints.

    Returns:
        dict: {ref: {pad_num: (abs_x, abs_y, w, h), ...}, ...}
    """
    _comp_str, placements = _component_placeholders()
    result = {}

    for ref, fp_name, fx, fy, rot, layer in placements:
        layer_char = "F" if "F." in layer else "B"

        if fp_name not in FP.FOOTPRINTS:
            continue

        gen, _default_layer = FP.FOOTPRINTS[fp_name]
        # Raw pads: x/y are footprint-local, NOT yet mirrored
        raw_pads = gen(layer_char)

        ref_pads = {}
        for pad_str in raw_pads:
            at_match = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\)', pad_str)
            sz_match = re.search(r'\(size\s+([\d.]+)\s+([\d.]+)\)', pad_str)
            num_match = re.search(r'\(pad\s+"([^"]*)"', pad_str)

            if not at_match or not sz_match:
                continue

            px = float(at_match.group(1))
            py = float(at_match.group(2))
            pw = float(sz_match.group(1))
            ph = float(sz_match.group(2))
            pad_num = num_match.group(1) if num_match else "?"

            # Transform order: rotate → mirror_X → translate
            # (matches _compute_pads in routing.py and KiCad convention)

            # Step 1: Apply rotation
            rot_rad = math.radians(rot)
            cos_r = math.cos(rot_rad)
            sin_r = math.sin(rot_rad)
            rx = px * cos_r - py * sin_r
            ry = px * sin_r + py * cos_r

            # Step 2: B.Cu mirroring: negate X (after rotation)
            if layer_char == "B":
                rx = -rx

            # Step 3: Translate to board coordinates
            abs_x = fx + rx
            abs_y = fy + ry

            # Rotate pad dimensions
            if abs(rot % 360) in (90, 270):
                pw, ph = ph, pw

            ref_pads[pad_num] = (abs_x, abs_y, pw, ph)

        result[ref] = ref_pads

    return result


def get_pad(pads, ref, pad_num):
    """Return (x, y) for a specific pad, or None if not found."""
    if ref in pads and pad_num in pads[ref]:
        x, y, _w, _h = pads[ref][pad_num]
        return (x, y)
    return None


# ── ESP32 GPIO-to-pin mapping ────────────────────────────────────
# ESP32-S3-WROOM-1 module: physical pin number -> GPIO number
# From Espressif datasheet Table 1 (Pin Description)
# Left side (pins 1-14), Bottom (pins 15-26), Right (pins 27-40), GND=41
PIN_TO_GPIO = {
    # Left side: pins 1-14
    1: None,   # GND
    2: None,   # 3V3
    3: None,   # EN
    4: 4, 5: 5, 6: 6, 7: 7,
    8: 15, 9: 16, 10: 17, 11: 18,
    12: 8, 13: 19, 14: 20,
    # Bottom side: pins 15-26
    15: 3, 16: 46, 17: 9, 18: 10, 19: 11,
    20: 12, 21: 13, 22: 14,
    23: 21, 24: 47, 25: 48, 26: 45,
    # Right side: pins 27-40
    27: 0, 28: 35, 29: 36, 30: 37,
    31: 38, 32: 39, 33: 40, 34: 41,
    35: 42, 36: 1, 37: 2,
    38: None, 39: None, 40: None,  # NC or power
    # Thermal pad
    41: None,  # GND
}

GPIO_TO_PIN = {gpio: pin for pin, gpio in PIN_TO_GPIO.items()
               if gpio is not None}


def esp32_gpio_pos(pads, gpio):
    """Return absolute (x, y) for an ESP32 GPIO pin.

    Args:
        pads: result from get_all_pad_positions()
        gpio: GPIO number (e.g. 4, 15, 36)

    Returns:
        (x, y) tuple or None
    """
    if gpio not in GPIO_TO_PIN:
        return None
    pin = str(GPIO_TO_PIN[gpio])
    return get_pad(pads, "U1", pin)


def fpc_pin_pos(pads, pin):
    """Return absolute (x, y) for FPC connector pin.

    Args:
        pads: result from get_all_pad_positions()
        pin: pin number 1-40

    Returns:
        (x, y) tuple or None
    """
    return get_pad(pads, "J4", str(pin))
