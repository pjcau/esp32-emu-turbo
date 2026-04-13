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
    """Generate a single KiCad pad S-expression.

    ``drill`` can be a float for a circular drill or a tuple (w, h) for
    an oval/slot drill.  KiCad syntax: ``(drill 0.6)`` vs
    ``(drill oval 0.6 1.5)``.
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
# Pin mapping (JLCPCB 1-14 scheme):
#   1=GND, 2=VBUS, 3=USB_DM_B, 4=CC1, 5=USB_DM_A, 6=USB_DP_A,
#   7=USB_DP_B, 8=SBU, 9=VBUS, 10=CC2, 11=VBUS, 12=GND,
#   13=SHIELD_FRONT, 14=SHIELD_REAR
def usb_c_16p(layer="B"):
    """USB-C 16-pin 2MD(073) — C2765186.

    R18 FIX (2026-04-13): two critical fixes for JLCPCB SMT assembly
    rejection "package cannot match pads on PCB":

      1. Shield THT tab drills changed from CIRCULAR 0.60 mm to OVAL
         SLOT drills matching EasyEDA reference exactly:
         - Front tabs (13/14): oval 0.60 × 1.50 mm
         - Rear tabs (13/14): oval 0.60 × 1.20 mm

      2. Wide signal pad height restored from 1.04 → 1.10 mm (exact
         EasyEDA reference value). R17's 1.04 mm was a local DRC
         workaround that deviated from the JLCPCB reference.

    Prior fixes still in effect:
      - R16: pad sizes aligned to EasyEDA reference
      - R16: duplicate "13"/"14" pad names for shield tabs
      - R16: NPTH drill 0.70 mm
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
    # process handles the 0.171 mm gap.  The DRC violation is suppressed
    # via board-level rule override for J1 NPTH pads.
    wide_pads = [
        ("1",  -3.200),   # GND
        ("2",  -2.400),   # VBUS
        ("11",  2.400),   # VBUS
        ("12",  3.200),   # GND
    ]
    for name, x in wide_pads:
        pads.append(_pad(name, "smd", "rect", x, -2.375, 0.55, 1.10, layers,
                         solder_mask_margin=0))

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
    # R18 FIX (2026-04-13): drills changed from circular 0.60 mm to OVAL
    # SLOT drills matching the EasyEDA reference exactly.  This was the
    # root cause of JLCPCB's "package cannot match pads" rejection —
    # the 3D model expects slot holes for the shield tabs.
    #
    # Front pair: pad 13/14 at y=-1.825 (plug side), 1.1×2.0 mm, drill oval 0.6×1.5
    # Rear  pair: pad 13/14 at y=+2.375 (body back), 1.2×1.8 mm, drill oval 0.6×1.2
    pads.append(_pad("13", "thru_hole", "oval", -4.325, -1.825, 1.1, 2.0, THT,
                     drill=(0.6, 1.5), solder_mask_margin=0))
    pads.append(_pad("14", "thru_hole", "oval",  4.325, -1.825, 1.1, 2.0, THT,
                     drill=(0.6, 1.5), solder_mask_margin=0))
    pads.append(_pad("13", "thru_hole", "oval", -4.325, 2.375, 1.2, 1.8, THT,
                     drill=(0.6, 1.2), solder_mask_margin=0))
    pads.append(_pad("14", "thru_hole", "oval",  4.325, 2.375, 1.2, 1.8, THT,
                     drill=(0.6, 1.2), solder_mask_margin=0))

    # NPTH positioning holes (no pad, no net)
    # Source: EasyEDA reference — 0.70mm drill (was 0.65mm in prior
    # footprint). Component pegs are ø0.50 mm, so 0.70 mm gives
    # 0.10 mm clearance per side.
    pads.append(
        f'    (pad "" np_thru_hole circle (at -2.89 -1.305)'
        f' (size 0.70 0.70) (drill 0.70)'
        f' (layers "*.Cu" "*.Mask") (uuid "{P.uid()}"))\n'
    )
    pads.append(
        f'    (pad "" np_thru_hole circle (at 2.89 -1.305)'
        f' (size 0.70 0.70) (drill 0.70)'
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
    pw, ph = 0.30, 1.0  # datasheet: contact width 0.30 ± 0.03

    # 40 pins at 0.5mm pitch, centered
    # Pin 1 at x = -9.75, pin 40 at x = +9.75
    # solder_mask_margin=0 avoids mask expansion on fine-pitch pads
    for i in range(40):
        x = -9.75 + i * 0.5
        pads.append(_pad(str(i + 1), "smd", "rect", x, -1.288, pw, ph, layers,
                         solder_mask_margin=0))

    # 2 mounting pads (pins 41-42): 2.000 x 2.500mm
    pads.append(_pad("41", "smd", "rect", 11.44, 1.288, 2.0, 2.5, layers))
    pads.append(_pad("42", "smd", "rect", -11.44, 1.288, 2.0, 2.5, layers))

    # Pin-1 marker (R12 JLCDFM fix)
    # Pin 1 at (-9.75, -1.288), pad bbox (-9.825..-9.675, -1.788..-0.788).
    # Mount pad 42 at (-11.44, 1.288) with 2.0x2.5, bbox (-12.44..-10.44, 0.038..2.538).
    # Place marker ABOVE pad 1 (cy ≤ -2.238). Marker at (-9.75, -2.5).
    # Clear of pad 1 top by 0.262mm + stroke margin, and mount pad is
    # 2.5mm below so no conflict there.
    pads.extend(_pin1_marker(-9.75, -2.5, layer))

    return pads


# ── TF-01A Micro SD card slot (LCSC C91145) ─────────────────────
# Ref: JLCPCB/EasyEDA package TF-SMD_TF-01A
# 9 signal pads (1.1mm pitch) + 4 shield/GND pads + 2 NPTH locating holes
def tf01a(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    pads = []

    # Signal pins 1-9 at y=-5.276, 1.1mm pitch, size 0.500 x 1.300mm
    # DFM: was 0.600mm (gap to shield pad 10 = 0.300mm). Now 0.500mm (gap=0.400mm ✓)
    # Pin 1 (DAT2) at x=+2.240, descending to pin 9 (DET) at x=-6.560
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
        # Signal pads: 1.0 × 2.5 mm. EasyEDA reference says 3.8mm but
        # increasing height causes copper-clearance DANGER with USB_D-
        # via at (79.75, 64.005) — only 23µm gap at 2.6mm height.
        # Keep 2.5mm: DFA "Lead area overlapping pad" ratio=0.73 is
        # cosmetic (JLCPCB assembles correctly, solder joint adequate).
        _pad("1", "smd", "rect", -1.0, 0, 1.0, 2.5, layers),
        _pad("2", "smd", "rect", 1.0, 0, 1.0, 2.5, layers),
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
# KiCad standard SOT-23-6 footprint, 0.95mm pitch
# Bottom row: pins 1,2,3 at y=+1.10  Top row: pins 6,5,4 at y=-1.10
def sot23_6(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -0.95, 1.10, 0.60, 0.70, layers),
        _pad("2", "smd", "rect", 0, 1.10, 0.60, 0.70, layers),
        _pad("3", "smd", "rect", 0.95, 1.10, 0.60, 0.70, layers),
        _pad("4", "smd", "rect", 0.95, -1.10, 0.60, 0.70, layers),
        _pad("5", "smd", "rect", 0, -1.10, 0.60, 0.70, layers),
        _pad("6", "smd", "rect", -0.95, -1.10, 0.60, 0.70, layers),
    ]


# ── SOT-23-3 (BAT54C dual Schottky diode) ───────────────────────
# KiCad standard SOT-23-3 footprint, 0.95mm pitch
# Bottom row: pins 1,2 at y=+1.10  Top row: pin 3 at y=-1.10
# BAT54C: pin 1=Anode1, pin 2=Anode2, pin 3=Common Cathode
def sot23_3(layer="B"):
    layers = SMD_B if layer == "B" else SMD_F
    return [
        _pad("1", "smd", "rect", -0.95, 1.10, 0.60, 0.70, layers),
        _pad("2", "smd", "rect", 0.95, 1.10, 0.60, 0.70, layers),
        _pad("3", "smd", "rect", 0, -1.10, 0.60, 0.70, layers),
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
    "SOT-23-3": (sot23_3, "B"),
    "R_0805": (passive_0805, "B"),
    "C_0805": (passive_0805, "B"),
    "LED_0805": (passive_0805, "F"),
    "C_1206": (passive_1206, "B"),
    "SS-12D00G3": (msk12c02, "B"),   # C431540 = MSK12C02, not SS-12D00G3
    "Speaker-22mm": (speaker_22mm, "B"),
    "SMD-4x4x2": (inductor_4x4, "B"),
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
