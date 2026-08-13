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
         solder_mask_margin=None, roundrect_rratio=None):
    """Generate a single KiCad pad S-expression.

    ``drill`` can be a float for a circular drill or a tuple (w, h) for
    an oval/slot drill.  KiCad syntax: ``(drill 0.6)`` vs
    ``(drill oval 0.6 1.5)``.

    ``roundrect_rratio`` is required when ``shape`` is ``roundrect``: it
    is the corner radius as a fraction of the pad's SHORT side.
    """
    if drill is None:
        d = ""
    elif isinstance(drill, (tuple, list)):
        d = f" (drill oval {drill[0]} {drill[1]})"
    else:
        d = f" (drill {drill})"
    net_s = f' (net {net} "")' if net == 0 else f' (net {net})'
    mask_s = (f" (solder_mask_margin {solder_mask_margin})"
              if solder_mask_margin is not None else "")
    if shape == "roundrect":
        if roundrect_rratio is None:
            raise ValueError("roundrect pad requires roundrect_rratio")
        rr_s = f" (roundrect_rratio {roundrect_rratio})"
    elif roundrect_rratio is not None:
        raise ValueError(f"roundrect_rratio is meaningless on a {shape} pad")
    else:
        rr_s = ""
    return (
        f'    (pad "{num}" {typ} {shape} (at {x} {y})'
        f' (size {w} {h}){d}{rr_s}'
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


# ── GENERIC RULE — Pin-1 Marker Helper ────────────────────────────
#
# Every footprint with ≥ 4 distinguishable pins (pinout matters for
# orientation) MUST call this helper to emit a visible pin-1 marker
# on both the silkscreen AND the fab layer. JLCPCB's SMT assembly
# operator uses the silkscreen marker to verify component orientation
# at pick-and-place time; the fab marker is for 3D-render / review.
#
# Convention: a 0.3mm-radius filled circle placed near pin 1, slightly
# offset outside the body so it remains visible when the component is
# soldered on. The offset direction is footprint-specific (caller
# supplies the marker x,y in footprint-local coordinates).
#
# Generic rule enforcement: scripts/pcb_review.py Check 12
# (JLCDFM pin-1 silk marker) scans every multi-pin reference on the
# finished PCB and fails if no silk element is within 3mm of pin 1.
# This catches any future footprint that forgets to call _pin1_marker().
#
# Historical context: JLCDFM upload on 2026-04-11 flagged 6 multi-pin
# components (U1, U2, U5, U6, J1, J4) for "missing component
# orientation marker". R12 added this helper + back-filled all six
# footprints to close the finding for good.
def _pin1_marker(cx, cy, layer="B"):
    """Emit a pin-1 orientation marker on BOTH silk + fab.

    Args:
        cx, cy: footprint-local coordinates of the marker. Should be
            slightly offset from pin 1 toward the "outside" of the
            body (upper-left for most ICs with pin 1 at top-left) so
            the mark is still legible after placement.
        layer: "B" for bottom-side footprints, "F" for top-side.

    Returns: list of 2 strings (silk circle + fab circle) ready to
    append to a footprint's pads/shapes list.
    """
    silk = "B.SilkS" if layer == "B" else "F.SilkS"
    fab = "B.Fab" if layer == "B" else "F.Fab"
    return [
        _fp_circle(cx, cy, 0.3, silk, width=0.25),
        _fp_circle(cx, cy, 0.3, fab, width=0.2),
    ]


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

    # Pin-1 marker (R12 JLCDFM fix)
    # Pin 1 at (-8.75, -5.26), pad bbox (-9.5..-8.0, -5.71..-4.81).
    # Place marker ABOVE the pad (cy ≤ -6.16 for 0.45mm silk-to-copper
    # clearance). Marker at (-8.75, -6.5) — directly above pin 1,
    # 0.54mm clear of the pad top. This stays within the module body
    # envelope (module top around y=-7) and away from the RF antenna.
    pads.extend(_pin1_marker(-8.75, -6.5, layer))

    return pads


# ── SMT Tact Switch 5.1x5.1mm (TS-1187A-B-A-B, LCSC C318884) ───
# Ref: JLCPCB/EasyEDA official library + brunoeagle KiCad footprint
# 4 pads: pins 1,3 (left pair, terminal A), pins 2,4 (right pair, B)
# Horizontal span: 6.0mm, vertical span: 3.7mm
# DFM: pad width increased 1.0->1.2mm, height 0.75->0.9mm to fully cover
#      JLCPCB 3D model leads and eliminate pin-left/pin-right edge violations
def sw_smd_5_1(layer="F"):
    layers = SMD_F if layer == "F" else SMD_B
    pw, ph = 1.0, 0.7   # Reduced from 1.2x0.9 for JLCPCB pad spacing DFM
    cx, cy = 3.0, 1.85
    return [
        _pad("1", "smd", "rect", -cx, -cy, pw, ph, layers),
        _pad("2", "smd", "rect", cx, -cy, pw, ph, layers),
        _pad("3", "smd", "rect", -cx, cy, pw, ph, layers),
        _pad("4", "smd", "rect", cx, cy, pw, ph, layers),
    ]


# ── 2-pad SMD momentary switch (XUNPU TS-1088-AR02016, LCSC C720477) ──
# SW17, the manual IP5306 KEY wake button. DNP in production.
#
# NOT the 5.1x5.1 tact (C318884) the twelve user buttons use, and the
# reason is measured, not preferred: a 7.0 x 4.4 tact footprint has NO
# clearance-legal site anywhere in the IP5306 quadrant, even with every
# respin part and every piece of respin copper treated as movable. The
# only 5.1x5.1 sites on the whole board sit north of U2, on the far side
# of the BAT+ B.Cu run at y=46.1, in a corridor 0.925 mm wide (between
# U2's pad edge at 113.85 and the gate column's at 114.775) that PWR_SW
# already occupies. Reaching one would mean re-planning the densest
# corner of the board to place a part that is not fitted.
#
# This part is 3.9 x 3.0 mm with just TWO terminals, which is what makes
# it fit: 5.6 x 3.1 mm of envelope, and one pad to KEY, one to GND, with
# no bridged pairs to reason about.
#
# Geometry read from the EasyEDA/LCSC package SW-SMD_L3.9-W3.0-P4.45
# (10 mil grid): pads 4.8425 x 7.3228 units = 1.230 x 1.860 mm, centres
# 17.204 units = 4.370 mm apart.
def sw_smd_2p_ts1088(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pw, ph = 1.23, 1.86
    dx = 4.370 / 2
    return [
        _pad("1", "smd", "rect", -dx, 0.0, pw, ph, layers),
        _pad("2", "smd", "rect", dx, 0.0, pw, ph, layers),
    ]


# ── ESOP-8 (IP5306) ──────────────────────────────────────────────
# 8 pins + exposed pad, 1.27mm pitch
# DFM: EP reduced from 3.4x3.4 to 3.4x2.8mm so corner signal pads
#      (at y=±1.905, half-height=0.3 → edge at y=±1.605) have ≥0.155mm
#      clearance from EP edges (±1.4mm): gap = 1.605-1.45 > 0.15mm threshold.
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

    # Exposed pad — height 2.8mm (reduced from 3.4mm for pad-to-pad clearance)
    # EP edges at y=±1.4mm; corner pin edges at y=±1.605mm; gap=0.205mm > 0.10mm
    pads.append(_pad("EP", "smd", "rect", 0, 0, 3.4, 2.8, layers))

    # Pin-1 marker on both silkscreen + fab (R12 JLCDFM fix)
    # Pin 1 at (-3.0, -1.905), pad bbox (-3.85..-2.15, -2.205..-1.605).
    # Place marker ABOVE the pad (cy ≤ -2.655 for 0.45mm clearance).
    # Marker at (-3.0, -2.8) — 0.60mm clear of pad top, above the
    # body edge (eSOP-8 body y_min ≈ -2.5).
    pads.extend(_pin1_marker(-3.0, -2.8, layer))

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

    # Pin 1 marker — silk + fab (R12 JLCDFM fix)
    # Pin 1 at (-2.7, -4.445), pad bbox (-3.475..-1.925, -4.745..-4.145).
    # Place marker ABOVE the pad (cy ≤ -5.195). Marker at (-2.7, -5.5)
    # — 0.755mm clear of pad top, inside body (body y_min = -5.0) →
    # slightly outside body at y=-5.5 (0.5mm past body edge).
    # Fallback: inside body between pads would collide with adjacent
    # pins 2-8. Going outside body top is the cleanest option.
    pads.extend(_pin1_marker(-2.7, -5.5, layer))

    return pads


# ── USB-C 6-pin SMT (HCTL HC-TYPE-C-16P-01A, LCSC C2765186) ─────
# Ref: JLCPCB/EasyEDA package USB-C-SMD_TYPE-C-6PIN-2MD-073
# 12 signal pads (pins 1-12) at y=-2.375, 4 shield THT pads (pins 13-14),
# 2 NPTH positioning holes.
# Pin mapping (JLCPCB 1-14 scheme).
# R21 CORRECTION (2026-07-25): the previous mapping listed pad 9 as VBUS
# and pad 8 as "SBU". Both were wrong. The datasheet page 1 "RECOMMENDED
# PCB LAYOUT (TOP VIEW)" labels every land with its USB-C contact name;
# read at 600 dpi they are, left to right:
#   A1+B12 | A4+B9 | B8 | A5 | B7 | A6 | A7 | B6 | A8 | B5 | B4+A9 | B1+A12
# The 16-contact receptacle is reduced to 12 lands by merging the two GND
# pairs and the two VBUS pairs; the USB 3 lanes (positions 2,3,10,11) are
# absent. Cross-checked against the "PIN ASSIGNMENTS" table on the same
# sheet. Resulting land -> signal map:
#   1  = A1 + B12 = GND      (wide)
#   2  = A4 + B9  = VBUS     (wide)
#   3  = B8       = SBU2
#   4  = A5       = CC1
#   5  = B7       = USB_D-   (DN2, flipped-orientation D-)
#   6  = A6       = USB_D+   (DP1, normal-orientation D+)
#   7  = A7       = USB_D-   (DN1, normal-orientation D-)
#   8  = B6       = USB_D+   (DP2, flipped-orientation D+)
#   9  = A8       = SBU1
#   10 = B5       = CC2
#   11 = B4 + A9  = VBUS     (wide)
#   12 = B1 + A12 = GND      (wide)
#   13 = SHIELD_FRONT, 14 = SHIELD_REAR
# Consequences, both handled in routing._usb_c_reversibility_traces():
#   - pad 9 must NOT be on VBUS (it is SBU1);
#   - pads 5 and 8 must be shorted to pads 7 and 6 respectively, which
#     is what USB Type-C r2.1 s4.2 requires of a USB 2.0 device
#     (A6<->B6 and A7<->B7 tied on the PCB) for orientation independence.
# ── J1 shield THT geometry — SINGLE SOURCE OF TRUTH ─────────────
# routing.py needs these to keep the BTN_B / BTN_START F.Cu button
# channels clear of the shield pads, and board-level DFM checks quote
# them. They were previously duplicated as magic numbers in routing.py
# ("front shield pad bottom edge = 70.375", "pad 1.4x1.8mm") which had
# already drifted 0.05 mm out of date. Import them, do not retype them.
# Footprint-local coordinates (mm); J1 is placed unrotated on B.Cu, and
# the B-side mirror is in X only, so local Y == board Y offset.
USBC_SHIELD_DX = 4.325          # |x| of all four shield tabs
USBC_SHIELD_FRONT_DY = -1.825   # front (plug-side) tab row
USBC_SHIELD_REAR_DY = 2.375     # rear (body-back) tab row
USBC_SHIELD_FRONT_W = 1.20      # front pad copper, X
USBC_SHIELD_FRONT_H = 2.12      # front pad copper, Y
USBC_SHIELD_REAR_W = 1.20       # rear pad copper, X
USBC_SHIELD_REAR_H = 1.92       # rear pad copper, Y
USBC_SHIELD_SLOT_W = 0.65       # both slots, X (JLCPCB min millable 0.61)
USBC_SHIELD_FRONT_SLOT_H = 1.60 # front slot, Y (datasheet 1.70 — see usb_c_16p)
USBC_SHIELD_REAR_SLOT_H = 1.40  # rear slot, Y (datasheet value)


def usb_c_16p(layer="B"):
    """USB-C 16-pin 2MD(073) — C2765186.

    R19 FIX (2026-04-13): shield tab dimensions corrected to match
    MANUFACTURER DATASHEET instead of EasyEDA community footprint.
    JLCPCB DFM still reported 4 "Danger" pin misalignment after R18
    because their 3D model follows the datasheet, not EasyEDA.

    Datasheet (Shouhan TYPE-C 16PIN 2MD(073)):
      Front shield: pad 1.1x2.10mm, slot 0.60x1.60mm
      Rear shield:  pad 1.2x1.80mm, slot 0.60x1.50mm

    EasyEDA reference had WRONG values:
      Front pad 2.0mm (should be 2.10), front slot 1.50 (should be 1.60)
      Rear slot 1.20 (should be 1.50)

    Prior fixes still in effect:
      - R18: oval slot drills, wide signal pad 1.10mm
      - R16: duplicate "13"/"14" pad names, NPTH drill 0.70mm
    """
    layers = SMD_B if layer == "B" else SMD_F
    pads = []

    # Wide signal pads (pins 1, 2, 11, 12): 0.55 × 1.10 mm at y=-2.375
    # Source: EasyEDA USB-C-SMD_TYPE-C-6PIN-2MD-073 via easyeda2kicad.
    #
    # R18 FIX (2026-04-13): restored to exact JLCPCB reference size
    # 0.55 × 1.10 mm.  R17 had shrunk height to 1.04 mm to satisfy a
    # local DRC hole_clearance rule (0.20 mm to NPTH), but JLCPCB's own
    # reference footprint specifies 1.10 mm, so their manufacturing
    # process handles the 0.171 mm gap.
    #
    # R21 FIX (2026-07-25): rect -> roundrect, corner ratio 0.25.
    # The lower inner corner of lands 1 and 12 was the closest copper to
    # the peg NPTH: 0.5212 mm centre-to-corner, minus the 0.325 mm hole
    # radius = 0.1962 mm, just under the 0.20 mm "NPTH with copper
    # around" rule (0.1712 mm before the peg hole was corrected to the
    # datasheet's 0.65 mm). The land SIZE is JLCPCB reference and must
    # not shrink, but a square corner is not part of that reference —
    # rounding it to the KiCad/IPC-standard 25% ratio pulls the nearest
    # copper back to 0.2172 mm without touching the land's extents,
    # solderable area, or the 3D-model alignment. Applied to all four
    # wide lands so the footprint stays symmetric.
    wide_pads = [
        ("1",  -3.200),   # GND
        ("2",  -2.400),   # VBUS
        ("11",  2.400),   # VBUS
        ("12",  3.200),   # GND
    ]
    for name, x in wide_pads:
        pads.append(_pad(name, "smd", "roundrect", x, -2.375, 0.55, 1.10,
                         layers, solder_mask_margin=0,
                         roundrect_rratio=0.25))

    # Narrow signal pads (pins 3-10): 0.30 × 1.10 mm, 0.5mm pitch at y=-2.375
    # Source: same as wide pads — exact JLCPCB reference dimensions
    narrow_pads = [
        ("3",  -1.750),
        ("4",  -1.250),
        ("5",  -0.750),
        ("6",  -0.250),
        ("7",   0.250),
        ("8",   0.750),
        ("9",   1.250),
        ("10",  1.750),
    ]
    for name, x in narrow_pads:
        pads.append(_pad(name, "smd", "rect", x, -2.375, 0.30, 1.1, layers,
                         solder_mask_margin=0))

    # Shield THT tabs: 4 total, front pair "13"/"14" + rear pair "13"/"14"
    # (duplicate names — matches JLCPCB/EasyEDA reference, see docstring).
    #
    # R19 FIX (2026-04-13): dimensions corrected to match MANUFACTURER
    # DATASHEET (Shouhan TYPE-C 16PIN 2MD(073)), NOT the EasyEDA
    # community footprint which had wrong slot drill heights.
    #
    # Datasheet "RECOMMENDED PCB LAYOUT" specifies:
    #   Front shield: pad 1.1×2.10mm, slot drill 0.60×1.60mm
    #   Rear shield:  pad 1.2×1.80mm, slot drill 0.60×1.50mm
    #
    # EasyEDA had: front drill 0.6×1.5 (wrong), rear drill 0.6×1.2 (wrong),
    # front pad height 2.0 (wrong). JLCPCB 3D model follows the datasheet,
    # causing DFM "pin misalignment" on all 4 shield tabs.
    #
    # R20 FIX (2026-04-13): slot WIDTH increased from 0.60 → 0.65 mm.
    # JLCPCB minimum slot width is 0.61mm; our 0.60mm triggered 4 DFM
    # Danger "slot width check" findings.  Datasheet specifies 0.60mm
    # but JLCPCB can't manufacture below 0.61mm.  0.65mm gives safe
    # margin (component pins ~0.50mm → 0.075mm clearance per side).
    #
    # R21 FIX (2026-07-25): SLOT HEIGHTS corrected + PADS ENLARGED.
    #
    # Two independent problems were found by KiCad DRC (annular_width x4
    # against the JLCPCB "Pad Size" rule, min annular width 0.25 mm):
    #
    # (a) The slot heights carried over from R19 did NOT match the
    #     datasheet after all. Re-reading the "RECOMMENDED PCB LAYOUT
    #     (TOP VIEW)" view on datasheet page 1 (sheet 1 of 1, rev A) at
    #     600 dpi, the shield tabs are dimensioned as OUTER/INNER pairs:
    #         Front tab: "2.10(2X)" outer pad, "1.70(2X)" slot
    #         Rear  tab: "1.80(2X)" outer pad, "1.40(2X)" slot
    #     R19 had front slot 1.60 (should be 1.70) and rear slot 1.50
    #     (should be 1.40). The rear error is what produced the
    #     0.1449 mm annular report: (1.80 - 1.50) / 2 = 0.15 mm.
    #
    # (b) Even the datasheet's own recommended land pattern only gives
    #     (2.10-1.70)/2 = (1.80-1.40)/2 = 0.20 mm annular, which is below
    #     the JLCPCB 0.25 mm minimum annular ring for plated through
    #     holes. The datasheet land pattern is therefore NOT directly
    #     manufacturable at JLCPCB and the pads must be grown.
    #
    # The pads cannot simply be grown, though: J1 is wedged into a
    # 6.4 mm vertical strip with a hard wall on each side.
    #     top    : the BTN_B F.Cu button channel (routing.py channel 5)
    #     bottom : the board edge (min_copper_edge_clearance 0.5 mm)
    # Because the two shield rows are rigidly 4.20 mm apart, moving J1
    # to help one row hurts the other by exactly as much: the sum
    # (front pad height + rear pad height) is a constant set by that
    # strip, and it is ~0.07 mm SHORT of what the datasheet slots plus a
    # 0.25 mm ring would need. See ANNULAR BUDGET below.
    #
    # Resolution, in priority order:
    #   1. Widen both pads in X to 1.20 mm. X is unconstrained (the
    #      neighbours are J1's own GND signal pads) and the X annular is
    #      computed on the straight flanks of the stadium outline, so it
    #      is exact: (1.20 - 0.65)/2 = 0.275 mm. This alone clears the
    #      two 0.2250 mm front reports.
    #   2. Rear slot -> 1.40 mm, the DATASHEET value (it was 1.50 mm,
    #      i.e. 0.10 mm LARGER than the manufacturer asks for). Shrinking
    #      a slot to the manufacturer's own recommendation cannot stop the
    #      tab fitting. This is what clears the 0.1449 mm rear reports.
    #   3. Front slot stays at 1.60 mm, i.e. 0.10 mm under the datasheet's
    #      1.70 mm recommendation. This is the one deliberate deviation
    #      and it is backed by hardware, not by argument: prototype #1 was
    #      fabricated and assembled from this exact footprint revision
    #      (commit caf2b2c, 2026-04-13) and J1 soldered down cleanly —
    #      see the short-circuit test log ("USB-C (J1) ... solder OK";
    #      page removed 2026-08-03, in git history as
    #      website/docs/manufacturing/short-test-multimeter.md).
    #      The front tab therefore physically
    #      passes a 0.65 x 1.60 mm slot. Widening it to the datasheet's
    #      1.70 mm would buy assembly float we have measured we do not
    #      need, at the cost of 0.05 mm of ring we demonstrably do.
    #   4. Free the last ~0.05 mm by narrowing and lifting the BTN_B
    #      channel where it passes the front shield pads, and by nudging
    #      J1 0.05 mm away from the board edge. Both in routing.py /
    #      board.py, keyed off J1_SHIELD_* below.
    #
    # ANNULAR BUDGET (all values mm, board Y increases downward):
    #   BTN_B bypass bottom edge (y=67.975, w=0.15)     68.050
    #   + 0.20 pad-to-track                             ------
    #   front pad top                                   68.250
    #   front pad height                                  2.12   -> ring 0.260
    #   ...                                             ------
    #   rear pad bottom                                 74.485
    #   + 0.50 board setup copper-to-edge               ------
    #   board edge                                      75.000  (0.515 actual)
    # Slack left over: ~0.015 mm at each end. This is at the geometric
    # limit of the current placement. The v2 way out is to move R1 (and
    # with it the CC1 via at (74.95, 67.40), which is what stops the
    # BTN_B bypass rising any further) clear of the channel, then lift
    # channel 5 by ~0.5 mm — after which the datasheet's 1.70 mm front
    # slot fits with a full 0.25 mm ring.
    #
    # Slot WIDTH stays at 0.65 mm (R20): the datasheet says 0.60 mm but
    # JLCPCB cannot mill a plated slot narrower than 0.61 mm. The tab is
    # ~0.50 mm thick, so 0.65 mm still captures it.
    #
    # Front pair: pad 13/14 at y=-1.825 (plug side), 1.20x2.12, slot 0.65x1.60
    # Rear  pair: pad 13/14 at y=+2.375 (body back), 1.20x1.92, slot 0.65x1.40
    for _name, _sx in (("13", -1), ("14", 1)):
        pads.append(_pad(
            _name, "thru_hole", "oval",
            _sx * USBC_SHIELD_DX, USBC_SHIELD_FRONT_DY,
            USBC_SHIELD_FRONT_W, USBC_SHIELD_FRONT_H, THT,
            drill=(USBC_SHIELD_SLOT_W, USBC_SHIELD_FRONT_SLOT_H),
            solder_mask_margin=0))
        pads.append(_pad(
            _name, "thru_hole", "oval",
            _sx * USBC_SHIELD_DX, USBC_SHIELD_REAR_DY,
            USBC_SHIELD_REAR_W, USBC_SHIELD_REAR_H, THT,
            drill=(USBC_SHIELD_SLOT_W, USBC_SHIELD_REAR_SLOT_H),
            solder_mask_margin=0))

    # NPTH positioning holes (no pad, no net)
    # R21 FIX (2026-07-25): 0.70 -> 0.65 mm. The datasheet "RECOMMENDED
    # PCB LAYOUT" explicitly calls out "O0.65(2X)" with a leader to the
    # positioning hole; 0.70 came from the EasyEDA community footprint.
    # Datasheet rule applies (see hardware/datasheets/POLARITY_AUDIT.md
    # and the C2 tantalum lesson: never trust EasyEDA over the datasheet).
    # Component pegs are 00.50 mm (bottom view), so 0.65 mm still gives
    # 0.075 mm clearance per side.
    # Side effect: the 0.025 mm radius reduction also buys back clearance
    # to the J1.1 / J1.12 pad corners, and it is what makes the VBUS
    # escape route past the peg holes geometrically possible at all
    # (see routing._usb_c_reversibility_traces).
    pads.append(
        f'    (pad "" np_thru_hole circle (at -2.89 -1.305)'
        f' (size 0.65 0.65) (drill 0.65)'
        f' (layers "*.Cu" "*.Mask") (uuid "{P.uid()}"))\n'
    )
    pads.append(
        f'    (pad "" np_thru_hole circle (at 2.89 -1.305)'
        f' (size 0.65 0.65) (drill 0.65)'
        f' (layers "*.Cu" "*.Mask") (uuid "{P.uid()}"))\n'
    )

    # Pin-1 marker (R12 JLCDFM fix)
    # Pin 1 (GND) at (-3.2, -2.375), pad bbox (-3.375..-3.025, -2.925..-1.825).
    # Place marker ABOVE the pad (cy ≤ -3.375). Marker at (-3.2, -3.5)
    # — 0.575mm clear of pad top, above the signal pad row. USB-C
    # body extends to roughly y=-4.4 (shield front), so this is
    # still inside the connector housing where it remains legible.
    pads.extend(_pin1_marker(-3.2, -3.5, layer))

    return pads


# ── FPC 40-pin 0.5mm pitch (display connector, LCSC C2856812) ────
# Ref: JLCPCB/EasyEDA package FPC-SMD_40P-P0.50_FPC-05F-40PH20
# Datasheet: J4_FPC-40pin-0.5mm_C2856812.pdf "Recommended FPC/FFC PCB
# Dimension" specifies:
#   Pitch           : 0.50 ± 0.03 mm
#   Contact width   : 0.30 ± 0.03 mm  ← pad width in pitch direction
#   Contact length  : 3.00 mm min
# 2 mounting pads (pins 41-42): 2.000 x 2.500mm at y=+1.288
#
# R13 JLCDFM fix (2026-04-12): pad width was 0.15 mm (50% of datasheet
# value). JLCDFM SMT DFM flagged all 42 J4 pins with "Pin edge past pad"
# 0.02-0.16 mm danger (FPC finger extends ~0.075 mm past each pad edge).
# Raised to 0.30 mm (datasheet nominal) → pad fully captures finger.
# Pitch gap: 0.50 - 0.30 = 0.20 mm ≥ JLCPCB safe 0.15 mm ✓.
def fpc_40p(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []
    pw, ph = 0.30, 1.3  # datasheet: contact width 0.30 ± 0.03
    # R32 (2026-08-03): contact LENGTH was 1.0mm against a 1.5mm JLC
    # reference land (C2856812) — coverage 0.667, the "lead area
    # overlapping pad" class in the 2026-08-03 JLCDFM report. Grown to
    # 1.3mm (coverage 0.867) entirely AWAY from the connector body (pad
    # centre moves from y=-1.288 to y=-1.438): the body side cannot take
    # it, LCD_D5's B.Cu vertical runs at board x=134.50 and the pads'
    # east edge (134.212) already sits 0.188mm off it. The growth stops
    # at 1.3 because every millimetre west also pushes the GND/+3V3
    # escape vias west, and their corridor ends at LCD_D7 (x=131.80).
    _sig_y = -1.438

    # 40 pins at 0.5mm pitch, centered
    # Pin 1 at x = -9.75, pin 40 at x = +9.75
    # solder_mask_margin=0 avoids mask expansion on fine-pitch pads
    for i in range(40):
        x = -9.75 + i * 0.5
        pads.append(_pad(str(i + 1), "smd", "rect", x, _sig_y, pw, ph, layers,
                         solder_mask_margin=0))

    # 2 mounting pads (pins 41-42): 2.000 x 2.500mm
    pads.append(_pad("41", "smd", "rect", 11.44, 1.288, 2.0, 2.5, layers))
    pads.append(_pad("42", "smd", "rect", -11.44, 1.288, 2.0, 2.5, layers))

    # Pin-1 marker (R12 JLCDFM fix)
    # Pin 1 at (-9.75, -1.438), pad bbox (-9.825..-9.675, -2.088..-0.788).
    # Mount pad 42 at (-11.44, 1.288) with 2.0x2.5, bbox (-12.44..-10.44, 0.038..2.538).
    # R32: the marker used to sit at (-9.75, -2.5), i.e. beyond the pad's
    # far end; the 1.3mm contact pad now reaches -2.088 and the 0.3mm
    # circle (0.125 stroke) would touch it. Moved along the pad COLUMN
    # instead, past pin 1 in the pitch direction: (-10.6, -1.438) is
    # 0.275mm clear of pin 1's edge, still 0.8mm clear of mount pad 42,
    # and stays out of the narrow corridor west of the contacts where the
    # GND/+3V3 escape vias live.
    pads.extend(_pin1_marker(-10.6, _sig_y, layer))

    return pads


# ── TF-01A Micro SD card slot (LCSC C91145) ─────────────────────
# Ref: JLCPCB/EasyEDA package TF-SMD_TF-01A
# 9 signal pads (1.1mm pitch) + 4 shield/GND pads + 2 NPTH locating holes
def tf01a(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []

    # Signal pins 1-9 at y=-5.276, 1.1mm pitch, size 0.500 x 1.300mm
    # DFM: was 0.600mm (gap to shield pad 10 = 0.300mm). Now 0.500mm (gap=0.400mm ✓)
    # Pin 1 (DAT2) at x=+2.240, descending to pin 9 (Cd, the socket's own
    # card-detect contact — the datasheet's PCB-pattern view labels the row
    # (1)..(8) then "Cd") at x=-6.560
    signal_x = [2.24, 1.14, 0.04, -1.06, -2.16, -3.26, -4.36, -5.46, -6.56]
    for i, x in enumerate(signal_x):
        pads.append(_pad(str(i + 1), "smd", "rect", x, -5.276, 0.5, 1.3,
                         layers))

    # Shield/GND pads — IMPORTANT: pin 10 at -X, pin 12 at +X (not mirrored)
    shield = [
        ("10", -7.76, -4.426, 1.2, 1.4),   # front-left
        ("13",  6.92, -4.426, 1.2, 1.4),   # front-right
        ("11", -7.76,  5.276, 1.2, 2.0),   # rear-left
        ("12",  7.76,  5.276, 1.2, 2.0),   # rear-right
    ]
    for name, x, y, w, h in shield:
        pads.append(_pad(name, "smd", "rect", x, y, w, h, layers))

    # NPTH locating holes
    # Datasheet: component pegs fit ø1.00mm holes (PCB Layout "2-∅1.00")
    pads.append(
        f'    (pad "" np_thru_hole circle (at -4.95 5.566)'
        f' (size 1.0 1.0) (drill 1.0)'
        f' (layers "*.Cu" "*.Mask") (uuid "{P.uid()}"))\n'
    )
    pads.append(
        f'    (pad "" np_thru_hole circle (at 3.05 5.566)'
        f' (size 1.0 1.0) (drill 1.0)'
        f' (layers "*.Cu" "*.Mask") (uuid "{P.uid()}"))\n'
    )

    # Pin-1 marker (R12 JLCDFM fix)
    # Pin 1 (DAT2) at (2.24, -5.276), pad bbox (1.99..2.49, -5.926..-4.626).
    # Place marker ABOVE the pad (cy ≤ -6.376). Marker at (2.24, -6.6)
    # — 0.674mm clear of pad top, above the slot opening.
    pads.extend(_pin1_marker(2.24, -6.6, layer))

    return pads


# ── JST PH 2-pin SMD (C295747) ──────────────────────────────────
# SMD version avoids inner layer shorts (BAT+ vs GND/+3V3 zones).
# DO NOT change to THT without updating: BOM, CPL, inject-3d-models,
# verify_datasheet, board.py, collision.py, docs, and rendering.
def jst_ph_2p(layer="B"):
    """JST PH 2-pin SMD (S2B-PH-SM4-TB, LCSC C295747).

    SMD version — pads on B.Cu only, no through-hole.

    Per JST datasheet J3_JST-PH-2P-SMD_C295747.pdf (side entry SMT):
    - 2 signal pads: 1.0 × 2.5 mm at pitch 2.0 mm (local ±1, 0)
    - 2 mechanical reinforcement tabs: 1.2 × 2.0 mm at X=±3.075, Y=+2.95
      from the signal row toward the body. These provide mechanical
      strength for the plastic housing and are NOT electrically
      connected to any net — they're just soldered for anchoring.

    R15-FIX (2026-04-12): JLCDFM reported 2 "Pin without pad" Danger
    findings on J3 because the JLCPCB 3D model for C295747 has 4
    pins total (2 signal + 2 reinforcement tabs) but our footprint
    previously defined only the 2 signal pads. Added pads "3" and
    "4" for the mechanical tabs at the typical JST PH SMT side-entry
    reinforcement positions.
    """
    layers = SMD_B if layer == "B" else SMD_F
    return [
        # Signal pads: 1.0 × 3.4 mm — JST's own recommended land for the
        # S2B-PH-SM4-TB. R32 (2026-08-03): was 1.0 × 2.5, coverage 0.658
        # against the EasyEDA 3.8mm reference, one of the JLCDFM "lead
        # area overlapping pad" findings.
        #
        # The blocker recorded here used to be the USB_D- via: at 2.5mm
        # the pads cleared it by 0.514mm, and growing them symmetrically
        # eats 0.45mm of that. It is resolved by J3 moving 0.25mm WEST
        # (routing/_shared.py JST) — that also fixes the F1 body
        # collision, and it centres the 1.0mm inter-pad channel on the
        # via: with J3 at x=79.75 the D- via at (79.75, 64.525) keeps
        # 0.296mm of copper clearance to BOTH pads (nearest approach is
        # pad corner to via circle) instead of 0.514/0.951 lopsided.
        _pad("1", "smd", "rect", -1.0, 0, 1.0, 3.4, layers),
        _pad("2", "smd", "rect", 1.0, 0, 1.0, 3.4, layers),
        # Mechanical reinforcement tabs — no electrical function,
        # soldered for body anchoring.
        #
        # EasyEDA reference (C295747): (±3.35, +5.85) size 1.5×3.4mm.
        # These are on the connector body side (opposite to wire entry).
        # After 180° rotation + B.Cu mirror, board positions:
        #   J3.3 at (76.65, 56.65) and J3.4 at (83.35, 56.65)
        #
        # CONSTRAINT: BTN_R B.Cu vertical at x=76.20 w=0.20. Tab 3 left
        # edge would be 76.65-0.75=75.9, BTN_R right edge 76.30 → gap
        # 75.9-76.30 = -0.4mm OVERLAP. Must route BTN_R around this tab.
        _pad("3", "smd", "rect", -3.35, 5.85, 1.5, 3.4, layers),
        _pad("4", "smd", "rect",  3.35, 5.85, 1.5, 3.4, layers),
    ]


# ── 0402 passive (R) ─────────────────────────────────────────────
# KiCad standard 0402_1005Metric footprint
def passive_0402(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -0.48, 0, 0.56, 0.62, layers),
        _pad("2", "smd", "rect", 0.48, 0, 0.56, 0.62, layers),
    ]


# ── SOT-23-6 (USBLC6-2SC6 ESD protection) ──────────────────────
# 0.95mm pitch, rows at y=±1.10.
#
# Pad LENGTH 1.00mm, up from the 0.70mm the KiCad generic carried. The
# JLC reference land for C7519 (scripts/.easyeda_cache/C7519) is
# 0.532 x 1.072 on ±1.15 rows, and the 2026-08-03 JLCDFM report scored
# our 0.70 pad at coverage 0.653 against it — the gullwing toe sat on
# solder mask. 1.00 covers 0.933 of that land; the remaining 0.07 is not
# worth the extra 0.07mm of outward excursion into U4's neighbourhood.
# Grown symmetrically about the existing row centres so the pad still
# straddles the lead and the package centroid (which
# verify_component_bodies fits bodies from) does not move.
def sot23_6(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -0.95, 1.10, 0.60, 1.00, layers),
        _pad("2", "smd", "rect", 0, 1.10, 0.60, 1.00, layers),
        _pad("3", "smd", "rect", 0.95, 1.10, 0.60, 1.00, layers),
        _pad("4", "smd", "rect", 0.95, -1.10, 0.60, 1.00, layers),
        _pad("5", "smd", "rect", 0, -1.10, 0.60, 1.00, layers),
        _pad("6", "smd", "rect", -0.95, -1.10, 0.60, 1.00, layers),
    ]


# ── SOT-23-5 (SY8089AAAC synchronous buck, LCSC C78988) ─────────
# Pad geometry copied VERBATIM from the JLCPCB/EasyEDA reference
# footprint fetched with easyeda2kicad:
#   scripts/.easyeda_cache/C78988/fp.pretty/
#       SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR.kicad_mod
#   pad 1  (+1.30, +0.95)   pad 4 (-1.30, -0.95)
#   pad 2  (+1.30,  0.00)   pad 5 (-1.30, +0.95)
#   pad 3  (+1.30, -0.95)   all 1.100 x 0.600 rect
# Keeping our library frame identical to EasyEDA's is deliberate:
# verify_easyeda_footprint then reports delta_row = 0 for U3 and NO
# _JLCPCB_ROT_DELTAS entry is required (the CPL default correction
# of 180 deg already preserves the placement rotation).
#
# Pinout — AN_SY8089/A Rev 0.9A page 2 ("Pinout (top view)"):
#   1 = EN, 2 = GND, 3 = LX, 4 = IN, 5 = FB
# Note this footprint is the EasyEDA frame, which is the KiCad-standard
# SOT-23-5 frame rotated -90 deg; that is why "SOT-23-5" needs its own
# entry in _JLCPCB_ROT_CORRECTIONS ahead of the generic "^SOT-23" rule.
def sot23_5(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", 1.30, 0.95, 1.10, 0.60, layers),   # EN
        _pad("2", "smd", "rect", 1.30, 0.00, 1.10, 0.60, layers),   # GND
        _pad("3", "smd", "rect", 1.30, -0.95, 1.10, 0.60, layers),  # LX
        _pad("4", "smd", "rect", -1.30, -0.95, 1.10, 0.60, layers),  # IN
        _pad("5", "smd", "rect", -1.30, 0.95, 1.10, 0.60, layers),   # FB
    ]


# ── SOT-23-3 (BAT54C dual Schottky diode, AO3401A P-MOSFET) ───
# 0.95mm pitch, rows at y=±1.10.
# BAT54C: pin 1=Anode1, pin 2=Anode2, pin 3=Common Cathode
#
# Pad LENGTH 1.00mm, same reasoning as sot23_6 above: the JLC reference
# lands for the two parts on this footprint are 1.070 x 0.600 (D1,
# C37704) and — since the R32 part swap — 1.000 x 0.800 (Q1/Q2,
# AO3401A C15127; the old SI2301CDS C10487 land was 1.037 x 0.532).
# Pad WIDTH is 0.80 for the same reason (R32): at the old 0.60 the
# AO3401A land's short axis was covered 0.75 with a 0.20 mm deficit and
# verify_pad_land flagged all six Q pins. 0.80 covers it fully, leaves
# 1.10 mm between the pin-1/pin-2 pads at the 0.95 pitch (x2 = 1.90 mm
# centres), and over-covers D1's 0.600-wide land, which the gate
# permits. Grown symmetrically about the row centres — the centroid,
# and therefore the fitted body box, is unchanged. Q1's outward edge is
# the binding one: it faces the RPP_GATE corridor at y=51.1 on one side
# and the (R32-widened) BAT+ channel at y=53.0 on the other; the
# channel's 0.20 clearances were derived against the 1.00 mm pad
# HEIGHT, which this growth does not touch.
def sot23_3(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -0.95, 1.10, 0.80, 1.00, layers),
        _pad("2", "smd", "rect", 0.95, 1.10, 0.80, 1.00, layers),
        _pad("3", "smd", "rect", 0, -1.10, 0.80, 1.00, layers),
    ]


# ── 0805 passive (R, C, LED) ─────────────────────────────────────
# Was 1.0 x 1.3 on 1.90 mm centres. The 2026-08-03 JLCDFM report turned
# that into 50 "Pin inner edge 0.08mm" DANGERs: the JLC reference land
# for every 0805 MLCC family on this board (C49678 / C15850 / C28323 /
# C1804 / C13967) is 1.410 x 1.350, so the cap's termination overhung
# copper on both flanks. verify_pad_land.py is the permanent guard.
#
# 1.20 x 1.35 is deliberately NOT the full 1.41-wide reference land.
# This footprint is instantiated ~45 times, most of them inside the
# button matrix where 5 mm-pitch R/C rows are threaded by B.Cu
# verticals with ~0.17 mm of clearance; the full land pushed each pad
# 0.255 mm outward and produced 130 collision-grid violations. At 1.20
# the pad covers 0.851 of the MLCC land and 0.980 of the 0805 RESISTOR
# land (1.133 x 1.377, C17414 etc.) — comfortably past the gate's 0.80
# floor with 0.05 of headroom — while moving each edge only 0.10 mm.
# The height carries the whole 1.35 mm the JLC land asks for, which is
# the axis the "pin inner edge" finding was actually about.
def passive_0805(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -0.95, 0, 1.15, 1.35, layers),
        _pad("2", "smd", "rect", 0.95, 0, 1.15, 1.35, layers),
    ]


# ── 1206 capacitor ───────────────────────────────────────────────
def passive_1206(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -1.5, 0, 1.2, 1.8, layers),
        _pad("2", "smd", "rect", 1.5, 0, 1.2, 1.8, layers),
    ]


# ── 1812 resettable fuse (BHFUSE BSMD1812-200-30V, C960026) ─────
# Body 4.73 x 3.41 mm (datasheet). Land: 1.9 x 3.8 mm pads on 4.4 mm
# centres — generic 1812 chip land (IPC nominal), sized so the pad
# extends ~0.75 mm past each body end for the fuse's wraparound
# terminations.
def fuse_1812(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -2.2, 0, 1.9, 3.8, layers),
        _pad("2", "smd", "rect", 2.2, 0, 1.9, 3.8, layers),
    ]


# ── MSK12C02 slide switch (LCSC C431540) ────────────────────────
# Ref: JLCPCB/EasyEDA package SW-TH_MSK12C02
# 3 signal SMD pads + 4 shell/mounting SMD pads + 2 NPTH holes
# Pin 4 = shell pads (unique names 4a-4d to avoid JLCPCB 0mm spacing)
# Note: shell pad Y positions are ASYMMETRIC (-0.600 top, +1.700 bottom)
def msk12c02(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []

    # Signal pads (3 pins, SPDT): 0.600 x 1.524mm
    pads.append(_pad("1", "smd", "rect", -2.25, -1.7, 0.6, 1.524, layers))
    pads.append(_pad("2", "smd", "rect", 0.75, -1.7, 0.6, 1.524, layers))
    pads.append(_pad("3", "smd", "rect", 2.25, -1.7, 0.6, 1.524, layers))

    # Shell/mounting pads (pin 4): 1.200 x 0.700mm
    # Unique names 4a-4d to prevent JLCPCB 0mm pad-spacing violations
    # Y positions are asymmetric: top=-0.600, bottom=+1.700
    pads.append(_pad("4a", "smd", "rect", -3.6, -0.6, 1.2, 0.7, layers))
    pads.append(_pad("4b", "smd", "rect", 3.6, -0.6, 1.2, 0.7, layers))
    pads.append(_pad("4c", "smd", "rect", -3.6, 1.7, 1.2, 0.7, layers))
    pads.append(_pad("4d", "smd", "rect", 3.6, 1.7, 1.2, 0.7, layers))

    # NPTH mounting holes
    # Datasheet: component pegs are ø0.75mm, PCB holes ø0.90mm (0.15mm clearance)
    pads.append(
        f'    (pad "" np_thru_hole circle (at -1.5 0.55)'
        f' (size 0.9 0.9) (drill 0.9)'
        f' (layers "*.Cu" "*.Mask") (uuid "{P.uid()}"))\n'
    )
    pads.append(
        f'    (pad "" np_thru_hole circle (at 1.5 0.55)'
        f' (size 0.9 0.9) (drill 0.9)'
        f' (layers "*.Cu" "*.Mask") (uuid "{P.uid()}"))\n'
    )

    return pads


# ── PJ-327A 3.5mm headphone jack (HOOYA, LCSC C19712376) ────────
# Dimensions from the HOOYA datasheet "P.C.B LAYOUT TOP VIEW"
# (hardware/datasheets — fetched 2026-08-12; drawing rev A1 2020.6.23):
#   5 SMD pads 2.9 x 1.6 mm on two columns 7.00 mm apart
#   (outer-outer 9.90, inner-inner 4.10), pad centres measured from the
#   body FRONT FACE (= local y=0, where the plug enters):
#     left  column (x=-3.5): pad 3 @ 2.30, pad 2 @ 9.39
#     right column (x=+3.5): pad 4 @ 1.70, pad 5 @ 5.30, pad 6 @ 10.99
#   2 NPTH locating holes Ø1.30 on the centreline at y=3.00 and 9.00.
#   Body 8.8 wide x 11.0 long x 4.4 tall; barrel Ø5.0 protrudes 1.4 mm
#   beyond the front face (overhangs the board edge, like J1's shell).
# Pin roles (plug-travel diagram): 2=TIP, 5=RING, 3=SLEEVE(GND),
# 6=tip NC rest contact (jack detect), 4=ring NC rest contact (unused).
# Place at the board edge with rotation 180 so the front face sits ON
# the edge and the body extends inboard.
def pj327a(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    fab = "B.Fab" if layer == "B" else "F.Fab"
    pads = [
        _pad("2", "smd", "rect", -3.5, 9.39, 2.9, 1.6, layers),
        _pad("3", "smd", "rect", -3.5, 2.30, 2.9, 1.6, layers),
        _pad("4", "smd", "rect", 3.5, 1.70, 2.9, 1.6, layers),
        _pad("5", "smd", "rect", 3.5, 5.30, 2.9, 1.6, layers),
        _pad("6", "smd", "rect", 3.5, 10.99, 2.9, 1.6, layers),
    ]
    for hy in (3.00, 9.00):
        pads.append(
            f'    (pad "" np_thru_hole circle (at 0 {hy})'
            f' (size 1.3 1.3) (drill 1.3)'
            f' (layers "*.Cu" "*.Mask") (uuid "{P.uid()}"))\n'
        )
    # Body outline on Fab (8.8 wide, front face at y=0, 11.0 long)
    bx = 4.4
    pads.append(_fp_line(-bx, 0, bx, 0, fab))
    pads.append(_fp_line(bx, 0, bx, 11.0, fab))
    pads.append(_fp_line(bx, 11.0, -bx, 11.0, fab))
    pads.append(_fp_line(-bx, 11.0, -bx, 0, fab))
    # Barrel stub past the front face
    pads.append(_fp_line(-2.5, 0, -2.5, -1.4, fab))
    pads.append(_fp_line(-2.5, -1.4, 2.5, -1.4, fab))
    pads.append(_fp_line(2.5, -1.4, 2.5, 0, fab))
    # Orientation marker near pad 2 (lowest-numbered pad; the jack has
    # no pad "1"). Outside the body, west of the pad 2 land.
    pads.extend(_pin1_marker(-5.6, 9.39, layer))
    return pads


# ── Speaker wire pads (28mm 8Ω driver, off-board) ────────────────
# Two 2.0x3.0mm solder pads for the speaker leads; the pad geometry is
# independent of the driver diameter. Was named "Speaker-22mm" from an
# early 22mm driver plan; the BOM part has been the 28mm driver all along.
def speaker_28mm(layer="B"):
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


# ── SMD power inductor 4.0x4.0mm (SWPA4030S2R2MT, LCSC C36409) ──
# Pad geometry copied VERBATIM from the JLCPCB/EasyEDA reference
# footprint fetched with easyeda2kicad:
#   scripts/.easyeda_cache/C36409/fp.pretty/
#       IND-SMD_L4.0-W4.0_LQH44PN2R2MP0L.kicad_mod
#   pad 1 (-1.80, 0) and pad 2 (+1.80, 0), both 1.500 x 4.000 rect.
# Wider and taller pads than the legacy SMD-4x4x2 land pattern used by
# L1, so it gets its own footprint name instead of being merged.
# Non-polarized: pad 1 / pad 2 are interchangeable.
def inductor_4x4_c36409(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -1.80, 0, 1.50, 4.00, layers),
        _pad("2", "smd", "rect", 1.80, 0, 1.50, 4.00, layers),
    ]


# ── Fiducial marker (1mm SMD pad, 2mm mask opening) ─────────────
def fiducial(layer="F"):
    layers = SMD_F if layer == "F" else SMD_B
    # No paste layer — remove paste from layers string
    layers_no_paste = layers.replace(' "F.Paste"', '').replace(' "B.Paste"', '')
    return [
        _pad("1", "smd", "circle", 0, 0, 1.0, 1.0, layers_no_paste,
             solder_mask_margin=0.5),
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
    "JST-PH-2P-SMD": (jst_ph_2p, "B"),
    "R_0402": (passive_0402, "B"),
    "SOT-23-6": (sot23_6, "B"),
    "SOT-23-5": (sot23_5, "B"),
    "SOT-23-3": (sot23_3, "B"),
    "R_0805": (passive_0805, "B"),
    "C_0805": (passive_0805, "B"),
    "LED_0805": (passive_0805, "F"),
    "C_1206": (passive_1206, "B"),
    "R_1206": (passive_1206, "B"),
    "F_1812": (fuse_1812, "B"),
    "SS-12D00G3": (msk12c02, "B"),   # C431540 = MSK12C02, not SS-12D00G3
    "SW-SMD-2P-TS1088": (sw_smd_2p_ts1088, "B"),
    "PJ-327A": (pj327a, "B"),
    "Speaker-28mm": (speaker_28mm, "B"),
    "SMD-4x4x2": (inductor_4x4, "B"),
    "IND-SMD-4.0x4.0": (inductor_4x4_c36409, "B"),
    "Fiducial": (fiducial, "F"),
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
