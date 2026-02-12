"""KiCad PCB footprint definitions with real pad geometries.

Each function returns a list of pad S-expression strings for embedding
inside a (footprint ...) block.  Coordinates are relative to the
footprint origin (center).
"""

import re

from . import primitives as P


# ── Helper ────────────────────────────────────────────────────────
def _pad(num, typ, shape, x, y, w, h, layers, net=0, drill=None):
    """Generate a single KiCad pad S-expression."""
    d = f" (drill {drill})" if drill else ""
    net_s = f' (net {net} "")' if net == 0 else f' (net {net})'
    return (
        f'    (pad "{num}" {typ} {shape} (at {x} {y})'
        f' (size {w} {h}){d}'
        f' (layers {layers}){net_s}'
        f' (uuid "{P.uid()}"))\n'
    )


SMD_F = '"F.Cu" "F.Paste" "F.Mask"'
SMD_B = '"B.Cu" "B.Paste" "B.Mask"'
THT = '"*.Cu" "*.Mask"'


def _smd(num, x, y, w, h, layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return _pad(num, "smd", "rect", x, y, w, h, layers)


def _tht(num, x, y, w, h, drill):
    return _pad(num, "thru_hole", "circle", x, y, w, h, THT, drill=drill)


# ── ESP32-S3-WROOM-1-N16R8 ───────────────────────────────────────
# Module: 25.5mm x 18mm, 39 castellated pads + GND pad
# Left pins 1-19, Right pins 20-39, Bottom GND pad
def esp32_s3_wroom1(layer="B"):
    pads = []
    layers = SMD_B if layer == "B" else SMD_F
    hw = 9.0      # half-width of module
    pin_w = 1.8   # pad length (extends outward)
    pin_h = 0.9   # pad width

    # Left side: pins 1-19 (top to bottom)
    for i in range(19):
        pin = i + 1
        y = -11.43 + i * 1.27
        pads.append(_pad(
            str(pin), "smd", "rect",
            -hw + pin_w / 2 - 0.5, y, pin_w, pin_h, layers,
        ))

    # Right side: pins 20-39 (top to bottom, but numbered bottom-up)
    for i in range(20):
        pin = 39 - i
        y = -11.43 + i * 1.27
        pads.append(_pad(
            str(pin), "smd", "rect",
            hw - pin_w / 2 + 0.5, y, pin_w, pin_h, layers,
        ))

    # Bottom GND pads (pins 40-41)
    pads.append(_pad("40", "smd", "rect", -1.27, 13.0, 1.0, 1.8, layers))
    pads.append(_pad("41", "smd", "rect", 1.27, 13.0, 1.0, 1.8, layers))

    # Exposed GND pad (large thermal pad)
    pads.append(_pad(
        "GND", "smd", "rect", 0, 5.0, 10.0, 10.0, layers,
    ))

    return pads


# ── SMT Tact Switch 5.1x5.1mm ────────────────────────────────────
# 4 pads: pin 1,2 (left pair), pin 3,4 (right pair)
# Pins 1-2 are connected internally, pins 3-4 connected internally
def sw_smd_5_1(layer="F"):
    layers = SMD_F if layer == "F" else SMD_B
    pw, ph = 1.6, 1.0
    cx, cy = 2.75, 1.85
    return [
        _pad("1", "smd", "rect", -cx, -cy, pw, ph, layers),
        _pad("2", "smd", "rect", -cx, cy, pw, ph, layers),
        _pad("3", "smd", "rect", cx, -cy, pw, ph, layers),
        _pad("4", "smd", "rect", cx, cy, pw, ph, layers),
    ]


# ── ESOP-8 (IP5306) ──────────────────────────────────────────────
# 8 pins + exposed pad, 1.27mm pitch
def esop8(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []
    pw, ph = 1.7, 0.6

    # Left side: pins 1-4 (top to bottom)
    for i in range(4):
        y = -1.905 + i * 1.27
        pads.append(_pad(str(i + 1), "smd", "rect", -3.0, y, pw, ph, layers))

    # Right side: pins 5-8 (bottom to top)
    for i in range(4):
        y = 1.905 - i * 1.27
        pads.append(_pad(str(i + 5), "smd", "rect", 3.0, y, pw, ph, layers))

    # Exposed pad
    pads.append(_pad("EP", "smd", "rect", 0, 0, 3.4, 3.4, layers))

    return pads


# ── SOT-223 (AMS1117-3.3) ────────────────────────────────────────
# 4 pads: 3 small on one side + 1 tab on other
def sot223(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = [
        _pad("1", "smd", "rect", -2.3, 3.15, 1.0, 1.5, layers),
        _pad("2", "smd", "rect", 0, 3.15, 1.0, 1.5, layers),
        _pad("3", "smd", "rect", 2.3, 3.15, 1.0, 1.5, layers),
        _pad("4", "smd", "rect", 0, -3.15, 3.6, 1.8, layers),  # tab
    ]
    return pads


# ── SOP-16 (PAM8403) ─────────────────────────────────────────────
# 16 pins, 1.27mm pitch
def sop16(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []
    pw, ph = 1.7, 0.6

    # Left: pins 1-8 (top to bottom)
    for i in range(8):
        y = -4.445 + i * 1.27
        pads.append(_pad(str(i + 1), "smd", "rect", -4.9, y, pw, ph, layers))

    # Right: pins 9-16 (bottom to top)
    for i in range(8):
        y = 4.445 - i * 1.27
        pads.append(_pad(str(i + 9), "smd", "rect", 4.9, y, pw, ph, layers))

    return pads


# ── USB-C 16-pin SMT ─────────────────────────────────────────────
# Simplified: 16 signal pads + 4 shield legs
def usb_c_16p(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []
    # 2 rows of 6 pads (A-side and B-side), 0.5mm pitch
    names_top = ["A1", "A4", "A5", "A6", "A7", "A8", "A9", "A12"]
    names_bot = ["B12", "B9", "B8", "B7", "B6", "B5", "B4", "B1"]

    for i, name in enumerate(names_top):
        x = -1.75 + i * 0.5
        pads.append(_pad(name, "smd", "rect", x, -3.2, 0.3, 1.0, layers))

    for i, name in enumerate(names_bot):
        x = -1.75 + i * 0.5
        pads.append(_pad(name, "smd", "rect", x, -2.2, 0.3, 1.0, layers))

    # Shield / mounting legs (4 corners, THT)
    for sx, sy in [(-4.32, -1.5), (4.32, -1.5), (-4.32, 1.5), (4.32, 1.5)]:
        pads.append(_pad("S", "thru_hole", "oval", sx, sy, 1.0, 1.8, THT,
                         drill=0.65))

    return pads


# ── FPC 40-pin 0.5mm pitch (ILI9488 display) ────────────────────
def fpc_40p(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []
    pw, ph = 0.3, 1.2

    # 40 pins at 0.5mm pitch, centered at origin
    # Pin 1 at x = -9.75, pin 40 at x = +9.75
    for i in range(40):
        x = -9.75 + i * 0.5
        pads.append(_pad(str(i + 1), "smd", "rect", x, 0, pw, ph, layers))

    # 2 mounting pads (wider for 40-pin connector)
    pads.append(_pad("MP1", "smd", "rect", -12.0, 0, 1.2, 2.0, layers))
    pads.append(_pad("MP2", "smd", "rect", 12.0, 0, 1.2, 2.0, layers))

    return pads


# ── TF-01A Micro SD card slot ─────────────────────────────────────
# 9 signal pads + 4 shield/detect pads
def tf01a(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []
    # Signal pins (1-9), 1.1mm pitch
    names = ["DAT2", "CD/DAT3", "CMD", "VDD", "CLK", "VSS", "DAT0",
             "DAT1", "DET"]
    for i in range(9):
        x = -4.4 + i * 1.1
        pads.append(_pad(str(i + 1), "smd", "rect", x, -6.8, 0.7, 1.8,
                         layers))

    # Shield/mounting (4 pads)
    for sx, sy in [(-7.0, -1.0), (7.0, -1.0), (-7.0, 6.5), (7.0, 6.5)]:
        pads.append(_pad("S", "smd", "rect", sx, sy, 1.2, 1.5, layers))

    return pads


# ── JST PH 2-pin (through-hole) ──────────────────────────────────
def jst_ph_2p(layer="B"):
    return [
        _tht("1", -1.0, 0, 1.5, 1.5, 0.75),
        _tht("2", 1.0, 0, 1.5, 1.5, 0.75),
    ]


# ── 0805 passive (R, C, LED) ─────────────────────────────────────
def passive_0805(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -0.95, 0, 1.0, 1.3, layers),
        _pad("2", "smd", "rect", 0.95, 0, 1.0, 1.3, layers),
    ]


# ── 1206 capacitor ───────────────────────────────────────────────
def passive_1206(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -1.5, 0, 1.2, 1.8, layers),
        _pad("2", "smd", "rect", 1.5, 0, 1.2, 1.8, layers),
    ]


# ── SS-12D00G3 slide switch ──────────────────────────────────────
# 3 THT pins, SPDT
def ss12d00g3(layer="B"):
    return [
        _tht("1", -2.5, 0, 1.5, 1.5, 0.8),
        _tht("2", 0, 0, 1.5, 1.5, 0.8),
        _tht("3", 2.5, 0, 1.5, 1.5, 0.8),
    ]


# ── Speaker 22mm ─────────────────────────────────────────────────
def speaker_22mm(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -9.5, 0, 2.0, 3.0, layers),
        _pad("2", "smd", "rect", 9.5, 0, 2.0, 3.0, layers),
    ]


# ── SMD inductor 4x4mm ───────────────────────────────────────────
def inductor_4x4(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -1.7, 0, 1.4, 3.4, layers),
        _pad("2", "smd", "rect", 1.7, 0, 1.4, 3.4, layers),
    ]


# ── Footprint registry ───────────────────────────────────────────
# Maps footprint name -> (pad_generator, default_layer)
FOOTPRINTS = {
    "ESP32-S3-WROOM-1-N16R8": (esp32_s3_wroom1, "B"),
    "SW-SMD-5.1x5.1": (sw_smd_5_1, "F"),
    "ESOP-8": (esop8, "B"),
    "SOT-223": (sot223, "B"),
    "SOP-16": (sop16, "B"),
    "USB-C-16P": (usb_c_16p, "B"),
    "FPC-40P-0.5mm": (fpc_40p, "B"),
    "TF-01A": (tf01a, "B"),
    "JST-PH-2P": (jst_ph_2p, "B"),
    "R_0805": (passive_0805, "B"),
    "C_0805": (passive_0805, "B"),
    "LED_0805": (passive_0805, "F"),
    "C_1206": (passive_1206, "B"),
    "SS-12D00G3": (ss12d00g3, "B"),
    "Speaker-22mm": (speaker_22mm, "B"),
    "SMD-4x4x2": (inductor_4x4, "B"),
}


def _mirror_pad_x(pad_str):
    """Negate the X coordinate in a pad S-expression for B.Cu mirroring.

    In KiCad, footprints on B.Cu must have their pad X coordinates
    pre-mirrored (negated) so the Gerber copper matches the physical
    component placement from the pick-and-place (CPL) file.
    """
    def _negate(match):
        x = -float(match.group(1))
        if x == 0:
            x = 0.0  # avoid -0.0
        y = match.group(2)
        return f'(at {x} {y})'
    return re.sub(r'\(at ([-\d.]+) ([-\d.]+)\)', _negate, pad_str, count=1)


def get_pads(footprint_name, layer=None):
    """Return pad S-expression list for a given footprint.

    If layer is None, uses the default layer for that footprint.
    For B.Cu footprints, pad X coordinates are negated (mirrored)
    to match KiCad's convention for bottom-side components.
    """
    if footprint_name not in FOOTPRINTS:
        return []
    gen, default_layer = FOOTPRINTS[footprint_name]
    actual_layer = layer or default_layer
    pads = gen(actual_layer)
    if actual_layer == "B":
        pads = [_mirror_pad_x(p) for p in pads]
    return pads
