"""Generate the complete KiCad PCB board.

Layout philosophy:
  TOP (F.Cu)  — user-facing: face buttons (D-pad, ABXY, Start, Select, Menu)
                + charging LEDs (bottom-left)
  BOTTOM (B.Cu) — all electronics: ESP32, ICs, connectors,
                  speaker, power switch, passives, battery connector
                  + L/R shoulder buttons (rotated 90°, aligned to top edge)

Display (ILI9488 3.95" bare panel) sits on top of PCB.  FPC ribbon passes
through a vertical slot in the board to reach J4 (FPC-40P) on the back.
"""

import math

from . import primitives as P
from . import footprints as FP
from . import routing

# ── Board dimensions (from enclosure.scad) ──────────────────────
BOARD_W = 160.0   # mm (170mm body - 2x5mm clearance)
BOARD_H = 75.0    # mm (85mm body - 2x5mm clearance)
CORNER_R = 6.0    # Corner radius (slightly less than 8mm body)

# PCB origin = top-left corner (KiCad convention: Y+ = down)
# Enclosure uses center origin, so we convert:
#   pcb_x = enclosure_x + BOARD_W/2
#   pcb_y = BOARD_H/2 - enclosure_y  (Y inverted)
CX = BOARD_W / 2   # 80.0
CY = BOARD_H / 2   # 37.5


def enc_to_pcb(ex, ey):
    """Convert enclosure center-origin coords to PCB top-left origin."""
    return (CX + ex, CY - ey)


# ── Mounting hole positions (from enclosure.scad screw_positions) ──
MOUNT_HOLES_ENC = [
    (-70, 30.5), (70, 30.5),
    (-70, -30.5), (70, -30.5),
    (-25, 0), (25, 0),
]

# ── Display area (ILI9488 3.95" bare LCD panel via FPC ribbon) ──
# Active area: 86.4 x 64.8mm, centered with 2mm upward offset
DISPLAY_W = 86.4
DISPLAY_H = 64.8
DISPLAY_ENC = (0, 2)   # enclosure offset

# ── FPC slot (vertical cutout for 40-pin ribbon cable) ──
# Between display right edge (x=43.2) and ABXY left button (x=52)
FPC_SLOT_ENC = (47, 2)   # slot center in enclosure coords
FPC_SLOT_W = 3.0         # mm wide (enough for 0.3mm ribbon + clearance)
FPC_SLOT_H = 24.0        # mm tall (for ~22mm wide 40-pin FPC ribbon)

# ── TOP side (F.Cu): face buttons + LEDs ────────────────────────────

# D-pad buttons (left cluster)
DPAD_ENC = (-62, 5)
DPAD_OFFSETS = [(0, 9), (0, -9), (-9, 0), (9, 0)]  # UP, DN, LF, RT

# ABXY buttons (right cluster, wider diamond)
ABXY_ENC = (62, 5)
ABXY_OFFSETS = [(0, 10), (10, 0), (0, -10), (-10, 0)]  # A, B, X, Y

# Start/Select (below D-pad area)
SS_ENC = (-62, -17)
SS_OFFSETS = [(-10, 0), (10, 0)]  # START, SELECT

# Menu button (front, bottom-right — below ABXY, outside display area)
MENU_ENC = (62, -25)

# Charging LEDs (front side, bottom-left)
LED_CHARGE_ENC = (-55, -30)    # Red LED — charging
LED_FULL_ENC = (-48, -30)      # Green LED — fully charged

# ── BOTTOM side (B.Cu): everything else ───────────────────────────

# ESP32-S3-WROOM-1 (center, back side)
ESP32_ENC = (0, 10)

# Shoulder L/R (near top edge, BACK side — rotated 90°, aligned to PCB top)
SHOULDER_L_ENC = (-65, 35)
SHOULDER_R_ENC = (65, 35)

# FPC display connector (right of slot, VERTICAL orientation)
# Rotated 90° — pins run vertically from y=25.75 to y=45.25 at x=135.
# Connector body 3mm wide at x=133.5-136.5, slot right edge at 128.5.
FPC_ENC = (55, 2)      # Next to FPC slot, right side (vertical)

# USB-C (bottom center edge)
USBC_ENC = (0, -BOARD_H / 2 + 3)   # 3mm from bottom edge

# SD card slot (bottom right)
SD_ENC = (60, -BOARD_H / 2 + 8)

# Power slide switch (left edge, accessible from enclosure side)
PWR_SWITCH_ENC = (-72, 15)

# Speaker (back side, left area — 22mm diameter)
SPEAKER_ENC = (-50, -15)
SPEAKER_DIAM = 22.0

# IP5306 power management (left-center, back — moved from slot zone)
IP5306_ENC = (30, -5)
# AMS1117 LDO regulator (below center, back — near IP5306)
AMS1117_ENC = (45, -18)
# PAM8403 audio amplifier (left area, back)
PAM8403_ENC = (-50, 8)
# L1 inductor (near IP5306, with clearance)
INDUCTOR_ENC = (30, -15)
# JST PH battery connector (center-bottom, back)
JST_BAT_ENC = (0, -15)


def _board_outline():
    """Generate rounded rectangle board outline + FPC slot on Edge.Cuts."""
    r = CORNER_R
    w, h = BOARD_W, BOARD_H
    parts = []

    # Four straight edges
    parts.append(P.gr_line(r, 0, w - r, 0))          # Top
    parts.append(P.gr_line(w, r, w, h - r))           # Right
    parts.append(P.gr_line(w - r, h, r, h))           # Bottom
    parts.append(P.gr_line(0, h - r, 0, r))           # Left

    # Four corner arcs (start, mid, end)
    a = math.pi * 0.75
    mx = r - r * math.cos(a)
    my = r - r * math.sin(a)
    parts.append(P.gr_arc(0, r, mx, my, r, 0))

    parts.append(P.gr_arc(
        w - r, 0,
        w - r + r * math.cos(math.pi * -0.25),
        r - r * math.sin(math.pi * -0.25),
        w, r,
    ))

    parts.append(P.gr_arc(
        w, h - r,
        w - r + r * math.cos(math.pi * 0.25),
        h - r + r * math.sin(math.pi * 0.25),
        w - r, h,
    ))

    parts.append(P.gr_arc(
        r, h,
        r - r * math.cos(math.pi * 0.25),
        h - r + r * math.sin(math.pi * 0.25),
        0, h - r,
    ))

    # FPC slot — internal rectangular cutout for 40-pin ribbon cable
    sx, sy = enc_to_pcb(*FPC_SLOT_ENC)
    sw2 = FPC_SLOT_W / 2
    sh2 = FPC_SLOT_H / 2
    slot_x1 = sx - sw2   # left
    slot_x2 = sx + sw2   # right
    slot_y1 = sy - sh2   # top
    slot_y2 = sy + sh2   # bottom
    parts.append(P.gr_line(slot_x1, slot_y1, slot_x2, slot_y1))  # top
    parts.append(P.gr_line(slot_x2, slot_y1, slot_x2, slot_y2))  # right
    parts.append(P.gr_line(slot_x2, slot_y2, slot_x1, slot_y2))  # bottom
    parts.append(P.gr_line(slot_x1, slot_y2, slot_x1, slot_y1))  # left

    return "".join(parts)


def _mounting_holes():
    """Generate 6 M2.5 mounting holes."""
    parts = []
    for ex, ey in MOUNT_HOLES_ENC:
        px, py = enc_to_pcb(ex, ey)
        parts.append(P.mounting_hole(px, py))
    return "".join(parts)


def _silkscreen_labels():
    """Add reference labels on silkscreen."""
    parts = []

    # ── Front silkscreen (buttons + LEDs + display outline) ──

    # Display outline on front silkscreen (display module sits here)
    dx, dy = enc_to_pcb(*DISPLAY_ENC)
    dw2, dh2 = DISPLAY_W / 2, DISPLAY_H / 2
    parts.append(P.gr_text(
        "DISPLAY AREA (ILI9488 3.95in)", dx, dy - dh2 - 3,
        "F.SilkS", 1.0,
    ))

    # Board title
    parts.append(P.gr_text(
        "ESP32 EMU Turbo CPJ&CP v1.0", CX, CY + 30,
        "F.SilkS", 1.5,
    ))

    # Button group labels (front)
    px, py = enc_to_pcb(*DPAD_ENC)
    parts.append(P.gr_text("D-PAD", px, py - 15, "F.SilkS"))
    px, py = enc_to_pcb(*ABXY_ENC)
    parts.append(P.gr_text("ABXY", px, py - 16, "F.SilkS"))

    # Menu button label (front)
    px, py = enc_to_pcb(*MENU_ENC)
    parts.append(P.gr_text("MENU", px, py - 5, "F.SilkS", 0.8))

    # LED labels (front side, bottom-left)
    px, py = enc_to_pcb(*LED_CHARGE_ENC)
    parts.append(P.gr_text("CHG", px, py + 3, "F.SilkS", 0.6))
    px, py = enc_to_pcb(*LED_FULL_ENC)
    parts.append(P.gr_text("FULL", px, py + 3, "F.SilkS", 0.6))

    # ── Back silkscreen (everything else) ──
    px, py = enc_to_pcb(*ESP32_ENC)
    parts.append(P.gr_text("ESP32-S3", px, py - 16, "B.SilkS"))
    px, py = enc_to_pcb(*IP5306_ENC)
    parts.append(P.gr_text("IP5306", px, py - 5, "B.SilkS", 0.8))
    px, py = enc_to_pcb(*AMS1117_ENC)
    parts.append(P.gr_text("AMS1117", px, py - 5, "B.SilkS", 0.8))
    px, py = enc_to_pcb(*PAM8403_ENC)
    parts.append(P.gr_text("PAM8403", px, py - 5, "B.SilkS", 0.8))

    # Connector labels (back side)
    px, py = enc_to_pcb(*USBC_ENC)
    parts.append(P.gr_text("USB-C", px, py - 5, "B.SilkS", 0.8))
    px, py = enc_to_pcb(*SD_ENC)
    parts.append(P.gr_text("SD", px, py - 5, "B.SilkS", 0.8))

    # Power switch label (back side)
    px, py = enc_to_pcb(*PWR_SWITCH_ENC)
    parts.append(P.gr_text("PWR", px, py + 5, "B.SilkS", 0.7))

    # Speaker label (back side)
    px, py = enc_to_pcb(*SPEAKER_ENC)
    parts.append(P.gr_text("SPEAKER", px, py, "B.SilkS", 0.8))

    # Shoulder button labels (back side — rotated 90°, aligned to top edge)
    px, py = enc_to_pcb(*SHOULDER_L_ENC)
    parts.append(P.gr_text("L", px, py + 5, "B.SilkS", 0.7))
    px, py = enc_to_pcb(*SHOULDER_R_ENC)
    parts.append(P.gr_text("R", px, py + 5, "B.SilkS", 0.7))

    return "".join(parts)


def _display_outline():
    """Draw display module outline on F.SilkS."""
    dx, dy = enc_to_pcb(*DISPLAY_ENC)
    dw2, dh2 = DISPLAY_W / 2, DISPLAY_H / 2
    parts = []
    x1, y1 = dx - dw2, dy - dh2
    x2, y2 = dx + dw2, dy + dh2
    for layer in ("F.SilkS",):
        parts.append(P.gr_line(x1, y1, x2, y1, layer=layer))
        parts.append(P.gr_line(x2, y1, x2, y2, layer=layer))
        parts.append(P.gr_line(x2, y2, x1, y2, layer=layer))
        parts.append(P.gr_line(x1, y2, x1, y1, layer=layer))
    return "".join(parts)


def _component_placeholders():
    """Generate footprints with real pad definitions."""
    parts = []
    placements = []

    # ── TOP side (F.Cu): face buttons + LEDs + menu ──

    # D-pad switches (SW1-SW4)
    for i, (dx, dy) in enumerate(DPAD_OFFSETS):
        bx, by = DPAD_ENC
        px, py = enc_to_pcb(bx + dx, by + dy)
        placements.append((f"SW{i+1}", "SW-SMD-5.1x5.1",
                            px, py, 0, "F.Cu"))

    # ABXY switches (SW5-SW8)
    for i, (dx, dy) in enumerate(ABXY_OFFSETS):
        bx, by = ABXY_ENC
        px, py = enc_to_pcb(bx + dx, by + dy)
        placements.append((f"SW{i+5}", "SW-SMD-5.1x5.1",
                            px, py, 0, "F.Cu"))

    # Start/Select (SW9-SW10)
    for i, (dx, dy) in enumerate(SS_OFFSETS):
        bx, by = SS_ENC
        px, py = enc_to_pcb(bx + dx, by + dy)
        placements.append((f"SW{i+9}", "SW-SMD-5.1x5.1",
                            px, py, 0, "F.Cu"))

    # Menu button (SW13, front bottom center)
    px, py = enc_to_pcb(*MENU_ENC)
    placements.append(("SW13", "SW-SMD-5.1x5.1", px, py, 0, "F.Cu"))

    # Charging LEDs (front side, bottom-left)
    px, py = enc_to_pcb(*LED_CHARGE_ENC)
    placements.append(("LED1", "LED_0805", px, py, 0, "F.Cu"))
    px, py = enc_to_pcb(*LED_FULL_ENC)
    placements.append(("LED2", "LED_0805", px, py, 0, "F.Cu"))

    # ── BOTTOM side (B.Cu): everything else ──

    px, py = enc_to_pcb(*ESP32_ENC)
    placements.append(("U1", "ESP32-S3-WROOM-1-N16R8",
                        px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*SHOULDER_L_ENC)
    placements.append(("SW11", "SW-SMD-5.1x5.1", px, py, 90, "B.Cu"))
    px, py = enc_to_pcb(*SHOULDER_R_ENC)
    placements.append(("SW12", "SW-SMD-5.1x5.1", px, py, 90, "B.Cu"))

    px, py = enc_to_pcb(*FPC_ENC)
    placements.append(("J4", "FPC-40P-0.5mm", px, py, 90, "B.Cu"))

    px, py = enc_to_pcb(*USBC_ENC)
    placements.append(("J1", "USB-C-16P", px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*SD_ENC)
    placements.append(("U6", "TF-01A", px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*PWR_SWITCH_ENC)
    placements.append(("SW_PWR", "SS-12D00G3", px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*SPEAKER_ENC)
    placements.append(("SPK1", "Speaker-22mm", px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*IP5306_ENC)
    placements.append(("U2", "ESOP-8", px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*AMS1117_ENC)
    placements.append(("U3", "SOT-223", px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*PAM8403_ENC)
    placements.append(("U5", "SOP-16", px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*INDUCTOR_ENC)
    placements.append(("L1", "SMD-4x4x2", px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*JST_BAT_ENC)
    placements.append(("J3", "JST-PH-2P", px, py, 0, "B.Cu"))

    # Generate footprints with real pad geometries
    for ref, fp_name, x, y, rot, layer in placements:
        layer_char = "F" if "F." in layer else "B"
        pads = FP.get_pads(fp_name, layer_char)
        pad_str = "".join(pads)
        parts.append(
            f'  (footprint "{fp_name}" (at {x} {y} {rot})'
            f' (layer "{layer}")\n'
            f'    (uuid "{P.uid()}")\n'
            f'    (property "Reference" "{ref}"'
            f' (at 0 -3 0) (layer "{layer}")'
            f' (effects (font (size 1 1)'
            f' (thickness 0.15))))\n'
            f'    (property "Value" "{fp_name}"'
            f' (at 0 3 0) (layer "{layer}")'
            f' (effects (font (size 1 1)'
            f' (thickness 0.15))))\n'
            f'{pad_str}'
            f'  )\n'
        )

    return "".join(parts), placements


def _all_routing():
    """Generate all traces, vias, and copper zones via routing module."""
    return routing.generate_all_traces()


def generate_board() -> str:
    """Generate the complete .kicad_pcb content."""
    parts = [
        P.header(),
        P.layers_4layer(),
        P.setup_4layer(),
        "\n",
        P.nets(),
        "\n",
        _board_outline(),
        "\n",
        _mounting_holes(),
        "\n",
        _display_outline(),
        "\n",
        _silkscreen_labels(),
        "\n",
    ]
    comp_str, _placements = _component_placeholders()
    parts.append(comp_str)
    parts.append("\n")
    parts.append(_all_routing())
    parts.append(P.footer())
    return "".join(parts)
