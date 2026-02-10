"""Generate the complete KiCad PCB board.

Layout philosophy:
  TOP (F.Cu)  — user-facing: face buttons (D-pad, ABXY, Start, Select, Menu)
                + charging LEDs (bottom-left)
  BOTTOM (B.Cu) — all electronics: ESP32, ICs, connectors, L/R shoulder,
                  speaker, power switch, passives, battery connector

Display module sits on top of PCB but FPC connector is on the back.
"""

import math

from . import primitives as P

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

# ── Display area (ST7796S 4.0" via FPC ribbon cable) ──
# Active area: 86.4 x 64.8mm, centered with 2mm upward offset
DISPLAY_W = 86.4
DISPLAY_H = 64.8
DISPLAY_ENC = (0, 2)   # enclosure offset

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

# Shoulder L/R (near top edge, back side)
SHOULDER_L_ENC = (-65, 35)
SHOULDER_R_ENC = (65, 35)

# FPC display connector (top center, connects to display via ribbon)
FPC_ENC = (0, 32)      # Near top edge for ribbon cable

# USB-C (bottom center edge)
USBC_ENC = (0, -BOARD_H / 2 + 3)   # 3mm from bottom edge

# SD card slot (bottom right, more inward)
SD_ENC = (40, -BOARD_H / 2 + 8)

# Power slide switch (left edge, accessible from enclosure side)
PWR_SWITCH_ENC = (-72, 15)

# Speaker (back side, left area — 22mm diameter)
SPEAKER_ENC = (-50, -15)
SPEAKER_DIAM = 22.0

# IP5306 power management (right area, back)
IP5306_ENC = (45, 8)
# AMS1117 LDO regulator (far right, back)
AMS1117_ENC = (62, 8)
# PAM8403 audio amplifier (left area, back)
PAM8403_ENC = (-50, 8)
# L1 inductor (below IP5306, with clearance)
INDUCTOR_ENC = (45, -3)
# JST PH battery connector (center-bottom, back)
JST_BAT_ENC = (0, -15)


def _board_outline():
    """Generate rounded rectangle board outline on Edge.Cuts."""
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
        "DISPLAY AREA (ST7796S 4.0in)", dx, dy - dh2 - 3,
        "F.SilkS", 1.0,
    ))

    # Board title
    parts.append(P.gr_text(
        "ESP32 Emu Turbo v1.0", CX, CY + 30,
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

    # Shoulder button labels (back side)
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
    """Generate placeholder footprints for component placement."""
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

    # ESP32-S3-WROOM-1 (center, back)
    px, py = enc_to_pcb(*ESP32_ENC)
    placements.append(("U1", "ESP32-S3-WROOM-1-N16R8",
                        px, py, 0, "B.Cu"))

    # Shoulder L/R (SW11-SW12, back side)
    px, py = enc_to_pcb(*SHOULDER_L_ENC)
    placements.append(("SW11", "SW-SMD-5.1x5.1", px, py, 0, "B.Cu"))
    px, py = enc_to_pcb(*SHOULDER_R_ENC)
    placements.append(("SW12", "SW-SMD-5.1x5.1", px, py, 0, "B.Cu"))

    # FPC display connector (top center, back side)
    px, py = enc_to_pcb(*FPC_ENC)
    placements.append(("J4", "FPC-16P-0.5mm", px, py, 0, "B.Cu"))

    # USB-C connector (bottom center edge, back side)
    px, py = enc_to_pcb(*USBC_ENC)
    placements.append(("J1", "USB-C-16P", px, py, 0, "B.Cu"))

    # SD card slot (back side, more inward)
    px, py = enc_to_pcb(*SD_ENC)
    placements.append(("U6", "TF-01A", px, py, 0, "B.Cu"))

    # Power switch (back side, edge-accessible)
    px, py = enc_to_pcb(*PWR_SWITCH_ENC)
    placements.append(("SW_PWR", "SS-12D00G3", px, py, 0, "B.Cu"))

    # Speaker (back side, 22mm)
    px, py = enc_to_pcb(*SPEAKER_ENC)
    placements.append(("SPK1", "Speaker-22mm", px, py, 0, "B.Cu"))

    # IP5306 (right area, back)
    px, py = enc_to_pcb(*IP5306_ENC)
    placements.append(("U2", "ESOP-8", px, py, 0, "B.Cu"))

    # AMS1117 (far right, back)
    px, py = enc_to_pcb(*AMS1117_ENC)
    placements.append(("U3", "SOT-223", px, py, 0, "B.Cu"))

    # PAM8403 (left area, back)
    px, py = enc_to_pcb(*PAM8403_ENC)
    placements.append(("U5", "SOP-16", px, py, 0, "B.Cu"))

    # Inductor (near IP5306, back)
    px, py = enc_to_pcb(*INDUCTOR_ENC)
    placements.append(("L1", "SMD-4x4x2", px, py, 0, "B.Cu"))

    # JST battery connector (center, back)
    px, py = enc_to_pcb(*JST_BAT_ENC)
    placements.append(("J3", "JST-PH-2P", px, py, 0, "B.Cu"))

    # Generate footprint placeholders
    for ref, val, x, y, rot, layer in placements:
        parts.append(
            f'  (footprint "{val}" (at {x} {y} {rot})'
            f' (layer "{layer}")\n'
            f'    (uuid "{P.uid()}")\n'
            f'    (property "Reference" "{ref}"'
            f' (at 0 -3 0) (layer "{layer}")'
            f' (effects (font (size 1 1)'
            f' (thickness 0.15))))\n'
            f'    (property "Value" "{val}"'
            f' (at 0 3 0) (layer "{layer}")'
            f' (effects (font (size 1 1)'
            f' (thickness 0.15))))\n'
            f'  )\n'
        )

    return "".join(parts), placements


def _gnd_zone():
    """GND copper pour on In1.Cu (full board with margin)."""
    m = 0.5
    pts = [
        (m, m), (BOARD_W - m, m),
        (BOARD_W - m, BOARD_H - m), (m, BOARD_H - m),
    ]
    return P.zone_gnd("In1.Cu", pts)


def _traces():
    """Generate representative PCB traces for major signal paths."""
    parts = []

    # Key component positions (PCB coordinates)
    ux, uy = enc_to_pcb(*USBC_ENC)
    ex, ey = enc_to_pcb(*ESP32_ENC)
    ix, iy = enc_to_pcb(*IP5306_ENC)
    amx, amy = enc_to_pcb(*AMS1117_ENC)
    px, py = enc_to_pcb(*PAM8403_ENC)
    fx, fy = enc_to_pcb(*FPC_ENC)
    sx, sy = enc_to_pcb(*SD_ENC)
    lx, ly = enc_to_pcb(*INDUCTOR_ENC)
    jx, jy = enc_to_pcb(*JST_BAT_ENC)
    spx, spy = enc_to_pcb(*SPEAKER_ENC)

    # ── Power traces (B.Cu, 0.5mm) — each with GND return ──

    # VBUS+: USB-C -> IP5306
    parts.append(P.segment(ux + 3, uy, ux + 3, iy + 12, "B.Cu", 0.5))
    parts.append(P.segment(ux + 3, iy + 12, ix, iy + 12, "B.Cu", 0.5))
    parts.append(P.segment(ix, iy + 12, ix, iy + 3, "B.Cu", 0.5))
    # GND return: USB-C -> IP5306
    parts.append(P.segment(ux - 3, uy, ux - 3, iy + 14, "B.Cu", 0.5))
    parts.append(P.segment(ux - 3, iy + 14, ix - 6, iy + 14, "B.Cu", 0.5))
    parts.append(P.segment(ix - 6, iy + 14, ix - 6, iy + 3, "B.Cu", 0.5))

    # 5V+: IP5306 -> L1 -> AMS1117
    parts.append(P.segment(ix + 3, iy, lx, ly, "B.Cu", 0.5))
    parts.append(P.segment(ix + 3, iy, amx - 3, amy, "B.Cu", 0.5))
    # GND return: IP5306 -> AMS1117
    parts.append(P.segment(ix + 3, iy + 2, amx - 3, amy + 2, "B.Cu", 0.5))

    # 3V3+: AMS1117 -> ESP32
    parts.append(P.segment(amx, amy - 2, amx, ey - 5, "B.Cu", 0.4))
    parts.append(P.segment(amx, ey - 5, ex + 10, ey - 5, "B.Cu", 0.4))
    # GND return: AMS1117 -> ESP32
    parts.append(P.segment(amx - 2, amy - 2, amx - 2, ey - 3, "B.Cu", 0.4))
    parts.append(P.segment(amx - 2, ey - 3, ex + 10, ey - 3, "B.Cu", 0.4))

    # BAT+: IP5306 -> JST
    parts.append(P.segment(ix - 3, iy + 3, ix - 3, jy, "B.Cu", 0.5))
    parts.append(P.segment(ix - 3, jy, jx + 3, jy, "B.Cu", 0.5))
    # BAT GND: IP5306 -> JST
    parts.append(P.segment(ix - 5, iy + 3, ix - 5, jy + 2, "B.Cu", 0.5))
    parts.append(P.segment(ix - 5, jy + 2, jx + 3, jy + 2, "B.Cu", 0.5))

    # ── Data traces (B.Cu, 0.2mm) ──

    # 8080 display bus: ESP32 -> FPC (8 parallel lines)
    for i in range(8):
        ox = -7 + i * 2
        parts.append(P.segment(
            ex + ox, ey - 13, ex + ox, ey - 18, "B.Cu", 0.2))
        parts.append(P.segment(
            ex + ox, ey - 18, fx + ox, fy + 2, "B.Cu", 0.2))

    # SPI: ESP32 -> SD card (4 lines)
    for i in range(4):
        oy = -3 + i * 2
        parts.append(P.segment(
            ex + 10, ey + oy, sx - 7, sy + oy, "B.Cu", 0.2))

    # I2S: ESP32 -> PAM8403 (3 lines)
    for i in range(3):
        oy = -2 + i * 2
        parts.append(P.segment(
            ex - 10, ey + oy, px + 6, py + oy, "B.Cu", 0.2))

    # Audio output: PAM8403 -> Speaker (2 lines)
    parts.append(P.segment(px - 5, py, spx + 11, spy, "B.Cu", 0.3))
    parts.append(P.segment(px - 5, py + 2, spx + 11, spy + 2, "B.Cu", 0.3))

    # USB D+/D-: USB-C -> ESP32 (differential pair)
    parts.append(P.segment(ux - 1, uy - 3, ux - 1, ey + 8, "B.Cu", 0.2))
    parts.append(P.segment(ux - 1, ey + 8, ex + 2, ey + 3, "B.Cu", 0.2))
    parts.append(P.segment(ux + 1, uy - 3, ux + 1, ey + 10, "B.Cu", 0.2))
    parts.append(P.segment(ux + 1, ey + 10, ex + 4, ey + 3, "B.Cu", 0.2))

    # ── Button vias (F.Cu -> B.Cu) ──
    for ddx, ddy in DPAD_OFFSETS:
        bx, by = DPAD_ENC
        vx, vy = enc_to_pcb(bx + ddx, by + ddy)
        parts.append(P.via(vx + 4, vy))
        parts.append(P.segment(vx, vy, vx + 4, vy, "F.Cu", 0.2))

    for ddx, ddy in ABXY_OFFSETS:
        bx, by = ABXY_ENC
        vx, vy = enc_to_pcb(bx + ddx, by + ddy)
        parts.append(P.via(vx - 4, vy))
        parts.append(P.segment(vx, vy, vx - 4, vy, "F.Cu", 0.2))

    # Menu button via
    mx, my = enc_to_pcb(*MENU_ENC)
    parts.append(P.via(mx, my - 4))
    parts.append(P.segment(mx, my, mx, my - 4, "F.Cu", 0.2))

    return "".join(parts)


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
    parts.append(_traces())
    parts.append("\n")
    parts.append(_gnd_zone())
    parts.append(P.footer())
    return "".join(parts)
