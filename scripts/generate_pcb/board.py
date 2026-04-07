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
import re as _re

from . import primitives as P
from . import footprints as FP
from . import routing

# Net ID -> name lookup for pad net injection
_NET_NAME = {nid: name for nid, name in P.NET_LIST}


def _inject_pad_net(pad_str, ref):
    """Replace (net 0 "") in a pad S-expression with the correct net.

    Extracts pad number, looks up (ref, pad_num) in routing.get_pad_nets(),
    and substitutes the correct net ID and name.
    """
    num_m = _re.search(r'\(pad\s+"([^"]*)"', pad_str)
    if not num_m:
        return pad_str
    pad_num = num_m.group(1)
    net_id = routing.get_pad_nets().get((ref, pad_num), 0)
    if net_id == 0:
        return pad_str
    net_name = _NET_NAME.get(net_id, "")
    return _re.sub(
        r'\(net\s+0\s+""\)',
        f'(net {net_id} "{net_name}")',
        pad_str,
    )

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
ABXY_OFFSETS = [(0, 10), (10, 0), (0, -10), (-9, 0)]  # A, B, X, Y — DFM: Y shifted right (enc -9 not -10); SW8 pad left edge at 129.4mm clears FPC slot edge (128.5mm) by 0.9mm >= 0.5mm required

# Start/Select (below D-pad area)
SS_ENC = (-62, -17)
SS_OFFSETS = [(-10, 0), (10, 0)]  # START, SELECT

# Menu button (front, bottom-right — below ABXY, outside display area)
# DFM: was (62,-25.7) → SW13 pads overlapped TF-01A (SD card) pads.
# Moved up 1.5mm: SW13 pad 1 bottom=59.9, TF pad top=61.05, gap=1.15mm ✓
MENU_ENC = (62, -24.2)

# Charging LEDs (front side, bottom-left)
LED_CHARGE_ENC = (-55, -30)    # Red LED — charging
LED_FULL_ENC = (-48, -30)      # Green LED — fully charged

# ── BOTTOM side (B.Cu): everything else ───────────────────────────

# ESP32-S3-WROOM-1 (center, back side)
ESP32_ENC = (0, 10)

# Shoulder L/R (near top edge, BACK side — rotated 90°, aligned to PCB top)
SHOULDER_L_ENC = (-65, 32)
SHOULDER_R_ENC = (65, 32)

# FPC display connector (right of slot, VERTICAL orientation)
# Rotated 90° — connector pads run vertically from y=25.75 to y=45.25 at x=135.
# NOTE: Display FPC pin order is REVERSED vs connector pad order.
# Display Pin N contacts connector pad (41-N) due to landscape CCW + straight-through slot.
# Connector body 3mm wide at x=133.5-136.5, slot right edge at 128.5.
FPC_ENC = (55, 2)      # Next to FPC slot, right side (vertical)

# USB-C (bottom center edge)
USBC_ENC = (0, -BOARD_H / 2 + 3.8)  # 3.8mm from bottom edge (DFM: shield pads clear edge by 0.525mm)

# SD card slot (bottom right)
SD_ENC = (60, -BOARD_H / 2 + 8)

# Power slide switch (bottom edge, left of USB-C — accessible from enclosure)
PWR_SWITCH_ENC = (-40, -BOARD_H / 2 + 3)

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
# JST PH battery connector (center, below passives, back)
JST_BAT_ENC = (0, -25)
# Reset and Boot buttons (back side, right of USB-C — dev kit style)
RESET_ENC = (15, -28)     # EN pin to GND — hardware reset
BOOT_ENC = (25, -28)      # GPIO0 to GND — download mode when held during reset


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

    # Four corner arcs (start, mid, end).
    # The midpoint lies on the minor arc, pointing toward the board corner.
    diag = r * math.sqrt(2) / 2  # offset along 45-degree diagonal

    # Top-left corner (0,0): center (r, r)
    parts.append(P.gr_arc(0, r, r - diag, r - diag, r, 0))
    # Top-right corner (w,0): center (w-r, r)
    parts.append(P.gr_arc(w - r, 0, w - r + diag, r - diag, w, r))
    # Bottom-right corner (w,h): center (w-r, h-r)
    parts.append(P.gr_arc(w, h - r, w - r + diag, h - r + diag, w - r, h))
    # Bottom-left corner (0,h): center (r, h-r)
    parts.append(P.gr_arc(r, h, r - diag, h - r + diag, 0, h - r))

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
    """Add reference labels on Fab layers.

    DFM FIX: ALL text moved from SilkS to Fab layers to eliminate 52
    silkscreen-to-hole JLCDFM violations. Silkscreen text overlapping
    drill holes (vias, THT, NPTH) is a JLCPCB manufacturing error.
    Fab layers are visible in renders but not checked for DFM clearance.
    """
    parts = []

    # ── Front Fab (buttons + LEDs + display outline) ──

    # Display outline label
    dx, dy = enc_to_pcb(*DISPLAY_ENC)
    dw2, dh2 = DISPLAY_W / 2, DISPLAY_H / 2
    parts.append(P.gr_text(
        "DISPLAY AREA (ILI9488 3.95in)", dx, dy - dh2 - 2,
        "F.Fab", 1.0,
    ))

    # Board title on front Fab layer
    parts.append(P.gr_text(
        "ESP32-EMU-TURBO  CPJ & CP", CX, 73.0,
        "F.Fab", 1.5,
    ))

    # Button group labels (front Fab)
    px, py = enc_to_pcb(*DPAD_ENC)
    parts.append(P.gr_text("D-PAD", px, py - 20, "F.Fab"))
    px, py = enc_to_pcb(*ABXY_ENC)
    parts.append(P.gr_text("ABXY", px, py - 20, "F.Fab"))

    # Menu button label (front)
    px, py = enc_to_pcb(*MENU_ENC)
    parts.append(P.gr_text("MENU", px, py - 5, "F.Fab", 0.8))

    # LED labels (front side, bottom-left)
    px, py = enc_to_pcb(*LED_CHARGE_ENC)
    parts.append(P.gr_text("CHG", px, py + 3, "F.Fab", 0.8))
    px, py = enc_to_pcb(*LED_FULL_ENC)
    parts.append(P.gr_text("FULL", px, py + 3, "F.Fab", 0.8))

    # ── Back Fab (IC + connector labels, visible in 3D renders) ──
    px, py = enc_to_pcb(*ESP32_ENC)
    parts.append(P.gr_text("ESP32-S3", px, py - 16, "B.Fab"))
    px, py = enc_to_pcb(*IP5306_ENC)
    parts.append(P.gr_text("IP5306", px, py - 10, "B.Fab", 0.8))
    px, py = enc_to_pcb(*AMS1117_ENC)
    parts.append(P.gr_text("AMS1117", px + 5, py - 3, "B.Fab", 0.8))
    px, py = enc_to_pcb(*PAM8403_ENC)
    parts.append(P.gr_text("PAM8403", px, py - 5, "B.Fab", 0.8))

    # Connector labels (back side)
    px, py = enc_to_pcb(*USBC_ENC)
    parts.append(P.gr_text("USB-C", px, py - 6, "B.Fab", 0.8))
    px, py = enc_to_pcb(*SD_ENC)
    parts.append(P.gr_text("SD", px, py - 8, "B.Fab", 0.8))

    # Battery connector label (back side)
    px, py = enc_to_pcb(*JST_BAT_ENC)
    parts.append(P.gr_text("BATT", px, py - 5, "B.Fab", 0.8))

    # FPC display connector label (back side)
    px, py = enc_to_pcb(*FPC_ENC)
    parts.append(P.gr_text("LCD", px, py - 14, "B.Fab", 0.8))

    # Power switch label (back side)
    px, py = enc_to_pcb(*PWR_SWITCH_ENC)
    parts.append(P.gr_text("PWR", px, py - 5, "B.Fab", 0.8))

    # Speaker label (back side)
    px, py = enc_to_pcb(*SPEAKER_ENC)
    parts.append(P.gr_text("SPEAKER", px, py, "B.Fab", 0.8))

    # Shoulder button labels (back side)
    px, py = enc_to_pcb(*SHOULDER_L_ENC)
    parts.append(P.gr_text("L", px, py + 5, "B.Fab", 0.8))
    px, py = enc_to_pcb(*SHOULDER_R_ENC)
    parts.append(P.gr_text("R", px, py + 5, "B.Fab", 0.8))

    # Board title (back side)
    parts.append(P.gr_text(
        "ESP32-EMU-TURBO  CPJ & CP  2026", CX, 73.0,
        "B.Fab", 1.2,
    ))

    # ── Passive component labels (B.Fab) ────────────────────────
    # Group labels for the pull-up and debounce rows (13 components each)
    # Pull-ups: R4-R15,R19 at y=46, x=43..103 (5mm spacing)
    parts.append(P.gr_text(
        "R4-R15,R19  10k", 73, 43.5, "B.Fab", 0.6,
    ))
    # Debounce caps: C5-C16,C20 at y=50, x=43..103
    parts.append(P.gr_text(
        "C5-C16,C20  100nF", 73, 52.5, "B.Fab", 0.6,
    ))

    # Individual power passives — label offset to clear 0805 body (~2x1.2mm)
    _lbl = 0.5  # text size for individual labels
    _passive_labels = [
        # (ref, value, x, y, label_dx, label_dy)
        # USB CC pull-downs
        ("R1", "5.1k", 74.0, 67.0, 0, -2.0),
        ("R2", "5.1k", 78.0, 67.0, 5.0, -1.0),
        # ESP32 decoupling
        ("R3", "10k", 65.0, 42.0, 0, -2.0),
        ("C3", "100nF", 69.5, 42.0, 0, -2.0),
        ("C4", "100nF", 92.0, 42.0, 0, -2.0),
        # LED resistors
        ("R17", "1k", 25.0, 65.0, 0, -2.0),
        ("R18", "1k", 32.0, 65.0, 0, -2.0),
        # IP5306 area
        ("R16", "100k", 115.0, 52.5, 0, -2.0),
        ("C17", "10uF", 110.0, 35.0, 4.5, 0),
        ("C18", "10uF", 118.0, 55.0, 0, 2.5),
        ("C19", "22uF", 110.0, 58.5, 0, 2.5),
        # AMS1117 caps
        ("C1", "10uF", 121.5, 50.0, 0, -2.0),
        ("C2", "22uF", 125.0, 62.5, 0, -2.0),
        # Inductor
        ("L1", "1uH", 110.0, 52.5, -4.5, 0),
        # PAM8403 passives — right side of U5
        ("C21", "100nF", 38.0, 23.5, 0, -2.0),
        ("C22", "0.47u", 33.175, 20.0, -3.5, 0),
        ("R20", "20k", 38.0, 26.5, 3.5, 0),
        ("C23", "1uF", 38.0, 29.5, 3.5, 0),
        ("R21", "20k", 38.0, 32.5, 3.5, 0),
        # PAM8403 passives — above/below U5
        ("C24", "1uF", 29.365, 22.0, -3.0, 0),
        ("C25", "1uF", 31.5, 37.5, 0, 2.5),
    ]
    for ref, val, cx, cy, dx, dy in _passive_labels:
        parts.append(P.gr_text(
            f"{ref} {val}", cx + dx, cy + dy, "B.Fab", _lbl,
        ))

    return "".join(parts)


def _display_outline():
    """Draw display module outline on F.SilkS."""
    dx, dy = enc_to_pcb(*DISPLAY_ENC)
    dw2, dh2 = DISPLAY_W / 2, DISPLAY_H / 2
    parts = []
    x1, y1 = dx - dw2, dy - dh2
    x2, y2 = dx + dw2, dy + dh2
    for layer in ("F.Fab",):  # DFM: F.Fab avoids silk_over_copper at bottom edge
        parts.append(P.gr_line(x1, y1, x2, y1, layer=layer, width=0.2))
        parts.append(P.gr_line(x2, y1, x2, y2, layer=layer, width=0.2))
        parts.append(P.gr_line(x2, y2, x1, y2, layer=layer, width=0.2))
        parts.append(P.gr_line(x1, y2, x1, y1, layer=layer, width=0.2))
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
    placements.append(("U5", "SOP-16", px, py, 90, "B.Cu"))

    px, py = enc_to_pcb(*INDUCTOR_ENC)
    placements.append(("L1", "SMD-4x4x2", px, py, 0, "B.Cu"))

    px, py = enc_to_pcb(*JST_BAT_ENC)
    placements.append(("J3", "JST-PH-2P", px, py, 0, "B.Cu"))

    # Reset and Boot buttons (B.Cu, right of USB-C — dev kit style)
    px, py = enc_to_pcb(*RESET_ENC)
    placements.append(("SW_RST", "SW-SMD-5.1x5.1", px, py, 0, "B.Cu"))
    px, py = enc_to_pcb(*BOOT_ENC)
    placements.append(("SW_BOOT", "SW-SMD-5.1x5.1", px, py, 0, "B.Cu"))

    # ── Passive components (B.Cu) ──
    # Positions must match jlcpcb_export.py for CPL/Gerber alignment.

    # USB-C CC resistors (positions synced with routing.R1_POS/R2_POS)
    placements.append(("R1", "R_0805", *routing.R1_POS, 0, "B.Cu"))
    placements.append(("R2", "R_0805", *routing.R2_POS, 0, "B.Cu"))

    # ESP32 decoupling (y=42, below ESP32 body edge at 40.25)
    placements.append(("R3", "R_0805", 65, 42, 0, "B.Cu"))
    placements.append(("C3", "C_0805", 69.5, 42, 0, "B.Cu"))  # DFM: was 68 (R3[1]@65.95 to C3[2]@67.05 gap=0.10mm=danger). At 69.5: C3[2]=68.55, R3[1]=65.95, gap=2.60mm clear
    placements.append(("C4", "C_0805", 92, 42, 0, "B.Cu"))  # DFM: moved from 85 (pad1@85.95 hit U1[16]@85.715)
    placements.append(("C26", "C_0805", *routing.C26_POS, 90, "B.Cu"))  # ESP32 VDD bypass (3.6mm from pin 2)

    # LED current-limiting resistors (B.Cu, near LEDs on F.Cu)
    placements.append(("R17", "R_0805", 25, 65, 0, "B.Cu"))
    placements.append(("R18", "R_0805", 32, 65, 0, "B.Cu"))

    # Pull-up resistors (y=46, x=43..103, 5mm spacing)
    pull_up_refs = [f"R{i}" for i in range(4, 16)] + ["R19"]
    for i, ref in enumerate(pull_up_refs):
        placements.append((ref, "R_0805", 43 + i * 5, 46, 0, "B.Cu"))

    # IP5306 KEY pull-down
    ix, iy = enc_to_pcb(*IP5306_ENC)
    placements.append(("R16", "R_0805", ix + 5, iy + 10, 0, "B.Cu"))

    # Debounce caps (y=50, x=43..103, 5mm spacing)
    debounce_refs = [f"C{i}" for i in range(5, 17)] + ["C20"]
    for i, ref in enumerate(debounce_refs):
        placements.append((ref, "C_0805", 43 + i * 5, 50, 0, "B.Cu"))

    # IP5306 support caps
    placements.append(("C17", "C_0805", 110, 35, 0, "B.Cu"))
    placements.append(("C18", "C_0805", 118, 55, 0, "B.Cu"))  # DFM: moved to (118,55) below display trace zone

    # C19 near inductor L1
    lx, ly = enc_to_pcb(*INDUCTOR_ENC)
    placements.append(("C19", "C_1206", lx, ly + 6, 0, "B.Cu"))

    # PAM8403 passive components (B.Cu)
    # PAM8403 passives — spread ~2mm from body for clean layout
    placements.append(("C22", "C_0805", *routing.C22_POS, 90, "B.Cu"))  # DC-blocking
    placements.append(("R20", "R_0805", *routing.R20_POS, 0, "B.Cu"))   # INL bias
    placements.append(("R21", "R_0805", *routing.R21_POS, 0, "B.Cu"))   # INR bias
    placements.append(("C21", "C_0805", *routing.C21_POS, 0, "B.Cu"))   # VREF bypass
    placements.append(("C23", "C_0805", *routing.C23_POS, 90, "B.Cu"))  # VDD decoupling
    placements.append(("C24", "C_0805", *routing.C24_POS, 90, "B.Cu"))  # PVDD top
    placements.append(("C25", "C_0805", *routing.C25_POS, 90, "B.Cu"))  # PVDD bottom

    # AMS1117 support caps (±7mm spacing for DFM clearance from SOT-223 pads)
    # C1 at amx-1 to keep pads outside FPC slot zone (slot starts at x=125.5)
    amx, amy = enc_to_pcb(*AMS1117_ENC)
    placements.append(("C1", "C_0805", amx - 3.5, amy - 7, 0, "B.Cu"))  # DFM: 7.8mm from U3, 2.3mm pad gap to tab
    placements.append(("C2", "C_1206", amx, amy + 7, 0, "B.Cu"))

    # Board-level fiducials at opposite corners for pick-and-place alignment.
    # 1mm copper dot, 2mm mask opening (0.5mm margin), no paste.
    # FID1 at (12, 12): 5.4mm from MH(10,7), copper gap=3.14mm ✓
    # FID2 at (150, 63): moved from (148,63) — old position overlapped via at
    # (148.76, 62.574) with gap=-0.04mm. New position: 5.0mm from MH(150,68),
    # copper gap=2.75mm ✓. No vias nearby ✓.
    placements.append(("FID1", "Fiducial", 12, 12, 0, "F.Cu"))
    placements.append(("FID2", "Fiducial", 150, 63, 0, "F.Cu"))

    # Per-footprint text Y offsets to clear pads (silkscreen-to-pad DFM)
    _text_offsets = {
        "ESP32-S3-WROOM-1-N16R8": (-15, 15),
        "USB-C-16P": (-6, 4),
        "FPC-40P-0.5mm": (-12, 12),
        "TF-01A": (-8, 8),
        "SOP-16": (-7, 7),
        "ESOP-8": (-5, 5),
        "SOT-223": (-5, 5),
        "Speaker-22mm": (-13, 13),
        "JST-PH-2P": (-3, 3),
        "SS-12D00G3": (-4, 4),
        "SMD-4x4x2": (-4, 4),
        "Fiducial": (-2, 2),
    }

    # Passives: text on Fab layer (not silkscreen) to avoid DFM violations
    _passive_fps = {"R_0805", "C_0805", "LED_0805", "C_1206"}

    # Generate footprints with real pad geometries
    # Pads are pre-rotated so the footprint is placed with rotation=0.
    # This ensures gerber apertures have the correct orientation
    # (kicad-cli does not rotate pad aperture shapes for rotated footprints).
    for ref, fp_name, x, y, rot, layer in placements:
        layer_char = "F" if "F." in layer else "B"
        pads = FP.get_pads(fp_name, layer_char, rotation=rot)
        pads = [_inject_pad_net(p, ref) for p in pads]
        pad_str = "".join(pads)
        mirror = " (justify mirror)" if "B." in layer else ""
        ref_y, val_y = _text_offsets.get(fp_name, (-3, 3))

        # ALL refs on Fab layer — SilkS causes silk_over_copper DFM violations.
        # Component labels added as separate gr_text in _silkscreen_labels().
        text_layer = "F.Fab" if layer_char == "F" else "B.Fab"
        ref_layer = text_layer
        text_size = 0.6 if fp_name in _passive_fps else 1

        parts.append(
            f'  (footprint "{fp_name}" (at {x} {y})'
            f' (layer "{layer}")\n'
            f'    (uuid "{P.uid()}")\n'
            f'    (property "Reference" "{ref}"'
            f' (at 0 {ref_y} 0) (layer "{ref_layer}")'
            f' (effects (font (size {text_size} {text_size})'
            f' (thickness 0.2)){mirror}))\n'
            f'    (property "Value" "{fp_name}"'
            f' (at 0 {val_y} 0) (layer "{text_layer}")'
            f' (effects (font (size {text_size} {text_size})'
            f' (thickness 0.2)){mirror}))\n'
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
    # Generate routing FIRST to populate pad-net mapping (_PAD_NETS),
    # then generate footprints with correct net assignments injected.
    routing_str = _all_routing()
    comp_str, _placements = _component_placeholders()
    parts.append(comp_str)
    parts.append("\n")
    parts.append(routing_str)
    parts.append(P.footer())
    return "".join(parts)
