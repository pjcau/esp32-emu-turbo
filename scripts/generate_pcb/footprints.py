"""KiCad PCB footprint definitions with real pad geometries.

Each function returns a list of pad S-expression strings for embedding
inside a (footprint ...) block.  Coordinates are relative to the
footprint origin (center).

Pad dimensions sourced from:
  - KiCad 10 standard library footprints (RF_Module, Package_SO, etc.)
  - JLCPCB/EasyEDA official component library (C91145, C318884, etc.)
  - Manufacturer datasheets (Espressif, HCTL, Korean Hroparts Elec)
"""

import math
import re

from . import primitives as P


# ── Helper ────────────────────────────────────────────────────────
def _pad(num, typ, shape, x, y, w, h, layers, net=0, drill=None,
         solder_mask_margin=None):
    """Generate a single KiCad pad S-expression."""
    d = f" (drill {drill})" if drill else ""
    net_s = f' (net {net} "")' if net == 0 else f' (net {net})'
    mask_s = (f" (solder_mask_margin {solder_mask_margin})"
              if solder_mask_margin is not None else "")
    return (
        f'    (pad "{num}" {typ} {shape} (at {x} {y})'
        f' (size {w} {h}){d}'
        f' (layers {layers}){net_s}{mask_s}'
        f' (uuid "{P.uid()}"))\n'
    )


SMD_F = '"F.Cu" "F.Paste" "F.Mask"'
SMD_B = '"B.Cu" "B.Paste" "B.Mask"'
THT = '"*.Cu" "*.Mask"'


def _fp_line(x1, y1, x2, y2, layer="B.SilkS", width=0.2):
    """Footprint-local silkscreen/fab line."""
    return (
        f'    (fp_line (start {x1} {y1}) (end {x2} {y2})'
        f' (stroke (width {width}) (type default))'
        f' (layer "{layer}") (uuid "{P.uid()}"))\n'
    )


def _fp_circle(cx, cy, r, layer="B.SilkS", width=0.2):
    """Footprint-local circle (pin 1 marker etc.)."""
    return (
        f'    (fp_circle (center {cx} {cy}) (end {cx + r} {cy})'
        f' (stroke (width {width}) (type default))'
        f' (layer "{layer}") (uuid "{P.uid()}"))\n'
    )


def _smd(num, x, y, w, h, layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return _pad(num, "smd", "rect", x, y, w, h, layers)


def _tht(num, x, y, w, h, drill):
    return _pad(num, "thru_hole", "circle", x, y, w, h, THT, drill=drill)


# ── ESP32-S3-WROOM-1-N16R8 ───────────────────────────────────────
# Module: 18mm x 25.5mm, 40 castellated pads on 3 sides + exposed GND
# Ref: KiCad RF_Module.pretty/ESP32-S3-WROOM-1.kicad_mod
# Left (1-14), Bottom (15-26), Right (27-40), GND pad #41
def esp32_s3_wroom1(layer="B"):
    pads = []
    layers = SMD_B if layer == "B" else SMD_F
    pw, ph = 1.5, 0.9   # pad size for side pads

    # Left side: pins 1-14, x=-8.75, pitch 1.27mm
    # Pin 1 at y=-5.26, pin 14 at y=11.25
    for i in range(14):
        pin = i + 1
        y = -5.26 + i * 1.27
        pads.append(_pad(str(pin), "smd", "rect", -8.75, y, pw, ph, layers))

    # Bottom side: pins 15-26, y=12.5, pitch 1.27mm
    # Pin 15 at x=-6.985, pin 26 at x=6.985
    # Pads rotated 270° → effectively size 0.9 x 1.5 (swap w/h)
    for i in range(12):
        pin = i + 15
        x = -6.985 + i * 1.27
        pads.append(_pad(str(pin), "smd", "rect", x, 12.5, ph, pw, layers))

    # Right side: pins 27-40, x=8.75, pitch 1.27mm
    # Pin 27 at y=11.25 (bottom), pin 40 at y=-5.26 (top)
    for i in range(14):
        pin = 27 + i
        y = 11.25 - i * 1.27
        pads.append(_pad(str(pin), "smd", "rect", 8.75, y, pw, ph, layers))

    # Exposed GND pad #41 (thermal pad)
    # Position: (-1.5, 2.46), size 3.9 x 3.9mm
    pads.append(_pad(
        "41", "smd", "rect", -1.5, 2.46, 3.9, 3.9, layers,
    ))

    return pads


# ── SMT Tact Switch 5.1x5.1mm (TS-1187A-B-A-B, LCSC C318884) ───
# Ref: JLCPCB/EasyEDA official library + brunoeagle KiCad footprint
# 4 pads: pins 1,3 (left pair, terminal A), pins 2,4 (right pair, B)
# Horizontal span: 6.0mm, vertical span: 3.7mm
def sw_smd_5_1(layer="F"):
    layers = SMD_F if layer == "F" else SMD_B
    pw, ph = 1.0, 0.75
    cx, cy = 3.0, 1.85
    return [
        _pad("1", "smd", "rect", -cx, -cy, pw, ph, layers),
        _pad("2", "smd", "rect", cx, -cy, pw, ph, layers),
        _pad("3", "smd", "rect", -cx, cy, pw, ph, layers),
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


# ── SOP-16 narrow body (PAM8403 C5122557) ──────────────────────
# Ref: KiCad Package_SO.pretty/SOIC-16_3.9x9.9mm_P1.27mm.kicad_mod
# C5122557 (Slkor PAM8403) = SOP-16 150mil (3.9mm body, 6.0mm lead span)
# NOT the wide body SOIC-16W (7.5mm). Confirmed from LCSC datasheet:
#   body 3.9mm (E=3.8-4.0), lead span 6.0mm (E1=5.8-6.3)
# 16 pins, 1.27mm pitch, pad centers at x=±2.7 (lead midpoint)
# PAM8403 pinout: 1=+OUT_L, 2=PGND, 3=-OUT_L, 4=PVDD, 5=MUTE,
#   6=VDD, 7=INL, 8=VREF, 9=NC, 10=INR, 11=GND, 12=SHDN,
#   13=PVDD, 14=-OUT_R, 15=PGND, 16=+OUT_R
def sop16(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    fab = "B.Fab" if layer == "B" else "F.Fab"
    pads = []
    pw, ph = 1.55, 0.6   # narrow body: 1.55mm pad (lead 1.05mm + extension)

    # Left: pins 1-8 (top to bottom)
    for i in range(8):
        y = -4.445 + i * 1.27
        pads.append(_pad(str(i + 1), "smd", "rect", -2.7, y, pw, ph, layers))

    # Right: pins 9-16 (bottom to top)
    for i in range(8):
        y = 4.445 - i * 1.27
        pads.append(_pad(str(i + 9), "smd", "rect", 2.7, y, pw, ph, layers))

    # Body outline on Fab layer (3.9mm body width)
    bx = 2.0    # body half-width (3.9mm / 2 ≈ 2.0mm)
    by = 5.0    # body half-height (9.9mm / 2 ≈ 5.0mm)
    pads.append(_fp_line(-bx, -by, bx, -by, fab))   # top
    pads.append(_fp_line(bx, -by, bx, by, fab))      # right
    pads.append(_fp_line(bx, by, -bx, by, fab))      # bottom
    pads.append(_fp_line(-bx, by, -bx, -by, fab))    # left

    # Pin 1 marker (dot inside body near pin 1)
    pads.append(_fp_circle(-1.0, -4.0, 0.3, fab))

    return pads


# ── USB-C 16-pin SMT (HCTL HC-TYPE-C-16P-01A, LCSC C2765186) ────
# Ref: KiCad Connector_USB.pretty/USB_C_Receptacle_HCTL_HC-TYPE-C-16P-01A
# Single row of 16 signal pads at y=-3.745 (some overlap: A1/B12, etc.)
# 4 shield THT pads
def usb_c_16p(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []

    # Merged wide pads — A-side and B-side share identical positions:
    #   A1/B12 (GND), A4/B9 (VBUS), A9/B4 (VBUS), A12/B1 (GND)
    # Only emit ONE pad per position to eliminate "pad spacing 0mm" DFM error.
    # Keep A-side names (routing.py references A4, A12, etc.)
    merged_wide = [
        ("A1",  -3.2,  0.6, 1.3),   # A1+B12 (GND)
        ("A4",  -2.4,  0.6, 1.3),   # A4+B9 (VBUS)
        ("A9",   2.4,  0.6, 1.3),   # A9+B4 (VBUS)
        ("A12",  3.2,  0.6, 1.3),   # A12+B1 (GND)
    ]
    for name, x, w, h in merged_wide:
        pads.append(_pad(name, "smd", "rect", x, -3.745, w, h, layers))

    # A-side unique narrow pads (no B-side overlap)
    a_narrow = [
        ("A5",  -1.25, 0.3, 1.3),
        ("A6",  -0.25, 0.3, 1.3),
        ("A7",   0.25, 0.3, 1.3),
        ("A8",   1.25, 0.3, 1.3),
    ]
    for name, x, w, h in a_narrow:
        pads.append(_pad(name, "smd", "rect", x, -3.745, w, h, layers,
                         solder_mask_margin=0))

    # B-side unique narrow pads (no A-side overlap)
    b_narrow = [
        ("B8",  -1.75, 0.3, 1.3),
        ("B7",  -0.75, 0.3, 1.3),
        ("B6",   0.75, 0.3, 1.3),
        ("B5",   1.75, 0.3, 1.3),
    ]
    for name, x, w, h in b_narrow:
        pads.append(_pad(name, "smd", "rect", x, -3.745, w, h, layers,
                         solder_mask_margin=0))

    # Shield / mounting legs (4 THT oval pads)
    # Front shields: size 1.3x2.1, rear shields: size 1.3x1.6
    # Drill 0.80mm (was 0.65 — increased for JLCPCB DFM "missing hole for pin")
    # Annular ring: (1.3-0.8)/2 = 0.25mm > 0.175mm minimum
    for sx in [-4.32, 4.32]:
        pads.append(_pad("S", "thru_hole", "oval", sx, -3.105, 1.3, 2.1, THT,
                         drill=0.80))
    for sx in [-4.32, 4.32]:
        pads.append(_pad("S", "thru_hole", "oval", sx, 1.075, 1.3, 1.6, THT,
                         drill=0.80))

    return pads


# ── FPC 40-pin 0.5mm pitch (display connector) ──────────────────
# Ref: KiCad Hirose FH12 series / generic FPC-40P bottom contact
# Signal pads at y=-1.85, size 0.3x1.3, 0.5mm pitch
def fpc_40p(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []
    pw, ph = 0.3, 1.3

    # 40 pins at 0.5mm pitch, centered
    # Pin 1 at x = -9.75, pin 40 at x = +9.75
    # solder_mask_margin=0 avoids mask expansion on fine-pitch pads
    for i in range(40):
        x = -9.75 + i * 0.5
        pads.append(_pad(str(i + 1), "smd", "rect", x, -1.85, pw, ph, layers,
                         solder_mask_margin=0))

    # 2 mounting pads
    pads.append(_pad("MP1", "smd", "rect", -11.5, -1.85, 1.6, 1.6, layers))
    pads.append(_pad("MP2", "smd", "rect", 11.5, -1.85, 1.6, 1.6, layers))

    return pads


# ── TF-01A Micro SD card slot (LCSC C91145) ─────────────────────
# Ref: JLCPCB/EasyEDA official library for Korean Hroparts Elec TF-01A
# 9 signal pads (1.1mm pitch) + 4 shield/GND pads
def tf01a(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []

    # Signal pins 1-9 at y=-5.45, 1.1mm pitch, size 0.6x1.3
    # Pin 1 (DAT2) at x=2.24, descending to pin 9 (DET) at x=-6.56
    signal_x = [2.24, 1.14, 0.04, -1.06, -2.16, -3.26, -4.36, -5.46, -6.56]
    for i, x in enumerate(signal_x):
        pads.append(_pad(str(i + 1), "smd", "rect", x, -5.45, 0.6, 1.3,
                         layers))

    # Shield/GND pads
    shield = [
        ("10", -7.76, -4.60, 1.2, 1.4),   # front-left
        ("13",  6.92, -4.60, 1.2, 1.4),   # front-right
        ("11", -7.76,  5.10, 1.2, 2.0),   # rear-left
        ("12",  7.76,  5.10, 1.2, 2.0),   # rear-right
    ]
    for name, x, y, w, h in shield:
        pads.append(_pad(name, "smd", "rect", x, y, w, h, layers))

    return pads


# ── JST PH 2-pin (through-hole, C173752) ────────────────────────
# Standard JST PH pin diameter: 0.64mm → hole = 0.85mm (0.21mm clearance)
# JLCPCB DFM requires ≥0.80mm for standard JST PH press-fit
def jst_ph_2p(layer="B"):
    return [
        _tht("1", -1.0, 0, 1.6, 1.6, 0.85),
        _tht("2", 1.0, 0, 1.6, 1.6, 0.85),
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


# ── MSK12C02 slide switch (LCSC C431540) ────────────────────────
# Ref: KiCad Button_Switch_SMD.pretty/SW_SPDT_Shouhan_MSK12C02.kicad_mod
# 3 signal SMD pads + 4 shell/mounting SMD pads
# Replaces old SS-12D00G3 THT footprint (wrong component type)
def msk12c02(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []

    # Signal pads (3 pins, SPDT)
    pads.append(_pad("1", "smd", "rect", -2.25, -1.95, 0.6, 1.3, layers))
    pads.append(_pad("2", "smd", "rect", 0.75, -1.95, 0.6, 1.3, layers))
    pads.append(_pad("3", "smd", "rect", 2.25, -1.95, 0.6, 1.3, layers))

    # Shell/mounting pads (4 corners)
    for sx, sy in [(-3.675, -1.1), (-3.675, 1.1),
                   (3.675, -1.1), (3.675, 1.1)]:
        pads.append(_pad("SH", "smd", "rect", sx, sy, 1.05, 0.7, layers))

    return pads


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
    "SS-12D00G3": (msk12c02, "B"),   # C431540 = MSK12C02, not SS-12D00G3
    "Speaker-22mm": (speaker_22mm, "B"),
    "SMD-4x4x2": (inductor_4x4, "B"),
}


def _pre_rotate_element(elem_str, angle_deg):
    """Pre-rotate a pad/line/circle element by angle (degrees).

    Rotates positions (at, start, end, center) and swaps pad (size w h)
    for 90°/270° rotations so gerber apertures have correct orientation.
    """
    if angle_deg % 360 == 0:
        return elem_str

    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)

    def _rotate_point(m):
        kw = m.group(1)
        x, y = float(m.group(2)), float(m.group(3))
        nx = round(x * cos_a - y * sin_a, 6)
        ny = round(x * sin_a + y * cos_a, 6)
        if nx == 0:
            nx = 0.0
        if ny == 0:
            ny = 0.0
        return f'({kw} {nx:g} {ny:g})'

    result = re.sub(
        r'\((at|start|end|center) ([-\d.]+) ([-\d.]+)\)',
        _rotate_point, elem_str,
    )

    # Swap (size w h) for 90° / 270° rotations
    if angle_deg % 180 != 0:
        result = re.sub(
            r'\(size ([\d.]+) ([\d.]+)\)',
            lambda m: f'(size {m.group(2)} {m.group(1)})',
            result,
        )

    return result


def _mirror_pad_x(pad_str):
    """Negate X coordinates in a pad/line S-expression for B.Cu mirroring.

    In KiCad, footprints on B.Cu must have their X coordinates
    pre-mirrored (negated) so the Gerber copper matches the physical
    component placement from the pick-and-place (CPL) file.
    Handles pad (at), fp_line (start/end), and fp_circle (center/end).
    """
    def _negate(match):
        keyword = match.group(1)
        x = -float(match.group(2))
        if x == 0:
            x = 0.0  # avoid -0.0
        y = match.group(3)
        return f'({keyword} {x} {y})'
    return re.sub(r'\((at|start|end|center) ([-\d.]+) ([-\d.]+)\)',
                  _negate, pad_str)


def get_pads(footprint_name, layer=None, rotation=0):
    """Return pad S-expression list for a given footprint.

    If rotation is non-zero, pads are pre-rotated so the footprint
    can be placed with rotation=0 in the .kicad_pcb file.  This ensures
    pad apertures in the gerber export have the correct orientation.

    Order: generate → pre-rotate → mirror (B.Cu).
    """
    if footprint_name not in FOOTPRINTS:
        return []
    gen, default_layer = FOOTPRINTS[footprint_name]
    actual_layer = layer or default_layer
    pads = gen(actual_layer)
    if rotation % 360 != 0:
        pads = [_pre_rotate_element(p, rotation) for p in pads]
    if actual_layer == "B":
        pads = [_mirror_pad_x(p) for p in pads]
    return pads
