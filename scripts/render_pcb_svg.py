#!/usr/bin/env python3
"""Generate SVG renders of the PCB layout from component placement data.

Layout:
  TOP (F.Cu)  — face buttons (D-pad, ABXY, Start, Select, Menu)
                + charging LEDs (bottom-left)
                + display outline on silkscreen (module sits on top)
  BOTTOM (B.Cu) — everything else: ESP32, ICs, connectors, L/R shoulder,
                  speaker, power switch, passives, battery connector

No external dependencies — uses only Python standard library.
"""

import os
import sys

# ── Board geometry ────────────────────────────────────────────────────

BOARD_W = 160.0
BOARD_H = 75.0
CORNER_R = 6.0

# Display area (ST7796S 4.0") — 86.4 x 64.8mm centered with 2mm up offset
DISPLAY_W = 86.4
DISPLAY_H = 64.8
DISPLAY_X = 80.0   # center X
DISPLAY_Y = 35.5   # center Y (37.5 - 2mm offset)

SCALE = 4.0
MARGIN = 20
SVG_W = BOARD_W * SCALE + 2 * MARGIN
SVG_H = BOARD_H * SCALE + 2 * MARGIN

# ── Colors ────────────────────────────────────────────────────────────

PCB_GREEN = "#1a5c2a"
PCB_GREEN_LIGHT = "#1f6b31"
COPPER_GOLD = "#c8a83e"
PAD_GOLD = "#d4af37"
SILKSCREEN = "#e8e8e8"
HOLE_DARK = "#1a1a1a"
HOLE_RING = "#c0a030"
EDGE_CUT = "#d4af37"
COMPONENT_IC = "#1a1a1a"
PASSIVE_BODY = "#3a3020"
PASSIVE_CAP = "#8b6914"
SWITCH_BODY = "#555555"
SWITCH_TOP = "#888888"
CONNECTOR_METAL = "#a0a0a0"
TEXT_COLOR = "#ffffff"
BOARD_SHADOW = "rgba(0,0,0,0.3)"
DISPLAY_BG = "#111118"
DISPLAY_BEZEL = "#222222"
LED_RED = "#ff3030"
LED_GREEN = "#30ff30"
TRACE_POWER = "#ff4444"
TRACE_5V = "#ff8844"
TRACE_3V3 = "#ffaa44"
TRACE_DATA = "#4488ff"
TRACE_USB = "#00ccff"
TRACE_AUDIO = "#44cc44"
TRACE_BTN = "#c8a83e"

# ── Component data ────────────────────────────────────────────────────

COMPONENTS_TOP = [
    # (ref, value, package, x, y, width, height)
    # Face buttons on top
    # D-pad (9mm offsets)
    ("SW1", "Up", "SW", 18.0, 23.5, 5.1, 5.1),
    ("SW2", "Dn", "SW", 18.0, 41.5, 5.1, 5.1),
    ("SW3", "Lt", "SW", 9.0, 32.5, 5.1, 5.1),
    ("SW4", "Rt", "SW", 27.0, 32.5, 5.1, 5.1),
    # ABXY (10mm offsets)
    ("SW5", "A", "SW", 142.0, 22.5, 5.1, 5.1),
    ("SW6", "B", "SW", 152.0, 32.5, 5.1, 5.1),
    ("SW7", "X", "SW", 142.0, 42.5, 5.1, 5.1),
    ("SW8", "Y", "SW", 132.0, 32.5, 5.1, 5.1),
    # Start/Select (10mm offsets)
    ("SW9", "St", "SW", 8.0, 54.5, 5.1, 5.1),
    ("SW10", "Se", "SW", 28.0, 54.5, 5.1, 5.1),
    # Menu button (bottom-right, below ABXY)
    ("SW13", "Menu", "SW", 142.0, 62.5, 5.1, 5.1),
    # Charging LEDs (front, bottom-left)
    ("LED1", "CHG", "LED", 25.0, 67.5, 2, 1.25),
    ("LED2", "FULL", "LED", 32.0, 67.5, 2, 1.25),
]

COMPONENTS_BOTTOM = [
    # (ref, value, package, x, y, width, height)
    # Everything else on bottom
    ("U1", "ESP32-S3", "Module", 80.0, 27.5, 18, 25.5),
    # Shoulder buttons (back side)
    ("SW11", "L", "SW", 15.0, 2.5, 5.1, 5.1),
    ("SW12", "R", "SW", 145.0, 2.5, 5.1, 5.1),
    # Connectors (back side)
    ("J4", "FPC-16P", "FPC", 80.0, 5.5, 20, 3),
    ("J1", "USB-C", "USB-C", 80.0, 72.0, 9, 7),
    ("U6", "SD Card", "TF-01A", 120.0, 67.0, 14, 15),
    # Power switch (back side)
    ("SW_PWR", "PWR", "SLIDE_SW", 8.0, 22.5, 4, 8),
    # Speaker (back side, 22mm)
    ("SPK1", "Speaker", "Speaker", 30.0, 52.5, 22, 22),
    # ICs
    ("U2", "IP5306", "ESOP-8", 125.0, 29.5, 6, 5),
    ("U3", "AMS1117", "SOT-223", 142.0, 29.5, 7, 3.5),
    ("U5", "PAM8403", "SOP-16", 30.0, 29.5, 10, 6),
    ("L1", "1uH", "Inductor", 125.0, 40.5, 4, 4),
    ("J3", "Battery", "JST-PH", 80.0, 52.5, 6, 4.5),
]

MOUNTING_HOLES = [
    (10.0, 7.0), (150.0, 7.0),
    (10.0, 68.0), (150.0, 68.0),
    (55.0, 37.5), (105.0, 37.5),
]

# Passive positions from jlcpcb_export.py (all on bottom)
PASSIVES_BACK = [
    ("R1", "5.1k", 74.0, 77.0), ("R2", "5.1k", 86.0, 77.0),
    ("R3", "10k", 65.0, 43.5), ("C3", "100n", 70.0, 43.5),
    ("C4", "100n", 90.0, 43.5),
    ("R17", "1k", 75.0, 43.5), ("R18", "1k", 85.0, 43.5),
    # Button pull-up resistors — centered row below ESP32 (y=44, x=50..110)
    ("R4", "10k", 50.0, 44.0), ("R5", "10k", 55.0, 44.0),
    ("R6", "10k", 60.0, 44.0), ("R7", "10k", 65.0, 44.0),
    ("R8", "10k", 70.0, 44.0), ("R9", "10k", 75.0, 44.0),
    ("R10", "10k", 80.0, 44.0), ("R11", "10k", 85.0, 44.0),
    ("R12", "10k", 90.0, 44.0), ("R13", "10k", 95.0, 44.0),
    ("R14", "10k", 100.0, 44.0), ("R15", "10k", 105.0, 44.0),
    ("R19", "10k", 110.0, 44.0),
    # KEY pull-up (near IP5306)
    ("R16", "100k", 117.0, 35.5),
    # Button debounce caps — centered row below pull-ups (y=48, x=50..110)
    ("C5", "100n", 50.0, 48.0), ("C6", "100n", 55.0, 48.0),
    ("C7", "100n", 60.0, 48.0), ("C8", "100n", 65.0, 48.0),
    ("C9", "100n", 70.0, 48.0), ("C10", "100n", 75.0, 48.0),
    ("C11", "100n", 80.0, 48.0), ("C12", "100n", 85.0, 48.0),
    ("C13", "100n", 90.0, 48.0), ("C14", "100n", 95.0, 48.0),
    ("C15", "100n", 100.0, 48.0), ("C16", "100n", 105.0, 48.0),
    ("C20", "100n", 110.0, 48.0),
    # IP5306 caps
    ("C17", "10u", 119.0, 39.5), ("C18", "10u", 131.0, 39.5),
    ("C19", "22u", 125.0, 46.5),
    # AMS1117 caps
    ("C1", "10u", 142.0, 24.5), ("C2", "22u", 142.0, 34.5),
]

SILKSCREEN_TOP = [
    ("D-PAD", 18.0, 17.5, 1.0),
    ("ABXY", 142.0, 16.5, 1.0),
    ("MENU", 142.0, 57.5, 0.8),
    ("CHG", 25.0, 70.5, 0.6),
    ("FULL", 32.0, 70.5, 0.6),
]

SILKSCREEN_BOTTOM = [
    ("ESP32-S3", 80.0, 11.5, 1.0),
    ("IP5306", 125.0, 24.5, 0.8),
    ("AMS1117", 142.0, 24.5, 0.8),
    ("PAM8403", 30.0, 24.5, 0.8),
    ("USB-C", 80.0, 67.0, 0.8),
    ("SD", 120.0, 62.0, 0.8),
    ("PWR", 8.0, 27.5, 0.7),
    ("SPEAKER", 30.0, 52.5, 0.8),
    ("L", 15.0, 7.5, 0.7),
    ("R", 145.0, 7.5, 0.7),
]

# ── Trace routing data (PCB coords) ──────────────────────────────────
# Each: (x1, y1, x2, y2, color, width_mm)

def _get_bottom_traces():
    """Return trace segments for bottom (B.Cu) layer."""
    # Component positions in PCB coords
    ux, uy = 80.0, 72.0     # USB-C
    ex, ey = 80.0, 27.5     # ESP32
    ix, iy = 125.0, 29.5    # IP5306
    amx, amy = 142.0, 29.5  # AMS1117
    px, py = 30.0, 29.5     # PAM8403
    fx, fy = 80.0, 5.5      # FPC
    sx, sy = 120.0, 67.0    # SD card
    lx, ly = 125.0, 40.5    # Inductor
    jx, jy = 80.0, 52.5     # JST battery
    spx, spy = 30.0, 52.5   # Speaker

    traces = []

    # GND trace color
    gnd = "#666666"

    # Power VBUS+ (red): USB-C -> IP5306
    traces.extend([
        (ux + 3, uy, ux + 3, iy + 12, TRACE_POWER, 1.2),
        (ux + 3, iy + 12, ix, iy + 12, TRACE_POWER, 1.2),
        (ix, iy + 12, ix, iy + 3, TRACE_POWER, 1.2),
    ])
    # GND return: USB-C -> IP5306
    traces.extend([
        (ux - 3, uy, ux - 3, iy + 14, gnd, 1.2),
        (ux - 3, iy + 14, ix - 6, iy + 14, gnd, 1.2),
        (ix - 6, iy + 14, ix - 6, iy + 3, gnd, 1.2),
    ])

    # 5V+ rail (orange): IP5306 -> L1, IP5306 -> AMS1117
    traces.extend([
        (ix + 3, iy, lx, ly, TRACE_5V, 1.0),
        (ix + 3, iy, amx - 3, amy, TRACE_5V, 1.0),
    ])
    # GND return: IP5306 -> AMS1117
    traces.append((ix + 3, iy + 2, amx - 3, amy + 2, gnd, 1.0))

    # 3V3+ rail (yellow-orange): AMS1117 -> ESP32
    traces.extend([
        (amx, amy - 2, amx, ey - 5, TRACE_3V3, 0.8),
        (amx, ey - 5, ex + 10, ey - 5, TRACE_3V3, 0.8),
    ])
    # GND return: AMS1117 -> ESP32
    traces.extend([
        (amx - 2, amy - 2, amx - 2, ey - 3, gnd, 0.8),
        (amx - 2, ey - 3, ex + 10, ey - 3, gnd, 0.8),
    ])

    # Battery+ (red): IP5306 -> JST
    traces.extend([
        (ix - 3, iy + 3, ix - 3, jy, TRACE_POWER, 1.2),
        (ix - 3, jy, jx + 3, jy, TRACE_POWER, 1.2),
    ])
    # Battery GND: IP5306 -> JST
    traces.extend([
        (ix - 5, iy + 3, ix - 5, jy + 2, gnd, 1.2),
        (ix - 5, jy + 2, jx + 3, jy + 2, gnd, 1.2),
    ])

    # 8080 Display bus (blue): ESP32 -> FPC (8 lines)
    for i in range(8):
        ox = -7 + i * 2
        traces.append((ex + ox, ey - 13, fx + ox, fy + 2, TRACE_DATA, 0.5))

    # SPI to SD (blue): ESP32 -> SD card (4 lines)
    for i in range(4):
        oy = -3 + i * 2
        traces.append((ex + 10, ey + oy, sx - 7, sy + oy, TRACE_DATA, 0.5))

    # I2S to PAM8403 (blue): ESP32 -> PAM8403 (3 lines)
    for i in range(3):
        oy = -2 + i * 2
        traces.append((ex - 10, ey + oy, px + 6, py + oy, TRACE_DATA, 0.5))

    # Audio output (green): PAM8403 -> Speaker
    traces.extend([
        (px - 5, py, spx + 11, spy, TRACE_AUDIO, 0.6),
        (px - 5, py + 2, spx + 11, spy + 2, TRACE_AUDIO, 0.6),
    ])

    # USB D+/D- (cyan): USB-C -> ESP32
    traces.extend([
        (ux - 1, uy - 3, ux - 1, ey + 8, TRACE_USB, 0.5),
        (ux - 1, ey + 8, ex + 2, ey + 3, TRACE_USB, 0.5),
        (ux + 1, uy - 3, ux + 1, ey + 10, TRACE_USB, 0.5),
        (ux + 1, ey + 10, ex + 4, ey + 3, TRACE_USB, 0.5),
    ])

    return traces


def _get_top_traces():
    """Return trace segments for top (F.Cu) layer — button to via."""
    traces = []
    # D-pad buttons -> vias (short copper traces)
    dpad_btns = [(18.0, 23.5), (18.0, 41.5), (9.0, 32.5), (27.0, 32.5)]
    for bx, by in dpad_btns:
        traces.append((bx, by, bx + 4, by, TRACE_BTN, 0.5))
        # Via dot will be drawn at the end

    # ABXY buttons -> vias
    abxy_btns = [(142.0, 22.5), (152.0, 32.5), (142.0, 42.5), (132.0, 32.5)]
    for bx, by in abxy_btns:
        traces.append((bx, by, bx - 4, by, TRACE_BTN, 0.5))

    # Menu button -> via (bottom-right)
    traces.append((142.0, 62.5, 142.0, 58.5, TRACE_BTN, 0.5))

    return traces


# ── Helpers ───────────────────────────────────────────────────────────

def _s(mm):
    return mm * SCALE


def _tx(x):
    return MARGIN + x * SCALE


def _ty(y):
    return MARGIN + y * SCALE


def _rounded_rect_path(x, y, w, h, r):
    sx, sy = _tx(x), _ty(y)
    sw, sh = _s(w), _s(h)
    sr = _s(r)
    return (
        f"M {sx + sr},{sy} "
        f"L {sx + sw - sr},{sy} "
        f"A {sr},{sr} 0 0 1 {sx + sw},{sy + sr} "
        f"L {sx + sw},{sy + sh - sr} "
        f"A {sr},{sr} 0 0 1 {sx + sw - sr},{sy + sh} "
        f"L {sx + sr},{sy + sh} "
        f"A {sr},{sr} 0 0 1 {sx},{sy + sh - sr} "
        f"L {sx},{sy + sr} "
        f"A {sr},{sr} 0 0 1 {sx + sr},{sy} Z"
    )


def _svg_header(title, view="top"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {SVG_W} {SVG_H}"
     width="{SVG_W}" height="{SVG_H}">
<title>{title}</title>
<defs>
  <filter id="shadow" x="-5%" y="-5%" width="115%" height="115%">
    <feDropShadow dx="3" dy="3" stdDeviation="4" flood-color="{BOARD_SHADOW}" />
  </filter>
  <pattern id="grid" width="{_s(2.54)}" height="{_s(2.54)}"
           patternUnits="userSpaceOnUse"
           patternTransform="translate({MARGIN},{MARGIN})">
    <rect width="{_s(2.54)}" height="{_s(2.54)}" fill="none"/>
    <path d="M {_s(2.54)} 0 L 0 0 0 {_s(2.54)}"
          fill="none" stroke="{PCB_GREEN_LIGHT}" stroke-width="0.3" opacity="0.3"/>
  </pattern>
</defs>
<rect width="{SVG_W}" height="{SVG_H}" fill="#1a1a2e"/>
"""


def _svg_footer():
    return "</svg>\n"


def _draw_board(view="top"):
    path = _rounded_rect_path(0, 0, BOARD_W, BOARD_H, CORNER_R)
    lines = [
        f'<clipPath id="board-clip"><path d="{path}"/></clipPath>',
        f'<path d="{path}" fill="none" filter="url(#shadow)"/>',
        f'<path d="{path}" fill="{PCB_GREEN}"/>',
        f'<path d="{path}" fill="url(#grid)" clip-path="url(#board-clip)"/>',
        f'<path d="{path}" fill="none" stroke="{EDGE_CUT}" stroke-width="1.5"/>',
    ]
    label = "TOP VIEW (F.Cu)" if view == "top" else "BOTTOM VIEW (B.Cu)"
    lines.append(
        f'<text x="{SVG_W / 2}" y="{SVG_H - 4}" '
        f'text-anchor="middle" font-family="monospace" '
        f'font-size="11" fill="#666">{label}</text>'
    )
    return "\n".join(lines)


def _draw_display_area():
    """Draw the display module outline and screen area on top view."""
    dx, dy = _tx(DISPLAY_X), _ty(DISPLAY_Y)
    dw, dh = _s(DISPLAY_W), _s(DISPLAY_H)
    lines = []
    # Display bezel
    lines.append(
        f'<rect x="{dx - dw/2 - 4}" y="{dy - dh/2 - 4}" '
        f'width="{dw + 8}" height="{dh + 8}" rx="4" '
        f'fill="{DISPLAY_BEZEL}" stroke="#444" stroke-width="1"/>'
    )
    # Screen area (dark)
    lines.append(
        f'<rect x="{dx - dw/2}" y="{dy - dh/2}" '
        f'width="{dw}" height="{dh}" rx="1" '
        f'fill="{DISPLAY_BG}"/>'
    )
    # Screen content hint
    lines.append(
        f'<text x="{dx}" y="{dy - 5}" text-anchor="middle" '
        f'font-family="monospace" font-size="8" fill="#334" '
        f'font-weight="bold">ST7796S 4.0"</text>'
    )
    lines.append(
        f'<text x="{dx}" y="{dy + 5}" text-anchor="middle" '
        f'font-family="monospace" font-size="6" fill="#334">'
        f'320 x 480</text>'
    )
    # FPC ribbon cable indication at top
    lines.append(
        f'<rect x="{dx - 15}" y="{dy - dh/2 - 10}" '
        f'width="30" height="8" rx="1" '
        f'fill="#8b6914" stroke="#a0832a" stroke-width="0.5" opacity="0.7"/>'
    )
    return "\n".join(lines)


def _draw_mounting_holes():
    lines = []
    for hx, hy in MOUNTING_HOLES:
        cx, cy = _tx(hx), _ty(hy)
        r_pad = _s(2.5)
        r_drill = _s(1.25)
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r_pad}" '
            f'fill="{HOLE_RING}" stroke="{EDGE_CUT}" stroke-width="0.5"/>'
        )
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r_drill}" fill="{HOLE_DARK}"/>'
        )
    return "\n".join(lines)


def _draw_component(ref, value, pkg, x, y, w, h):
    """Draw a single component with appropriate style."""
    cx, cy = _tx(x), _ty(y)
    sw, sh = _s(w), _s(h)
    lines = []

    if pkg == "Module":
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="2" '
            f'fill="#555" stroke="#888" stroke-width="1"/>'
        )
        lines.append(
            f'<rect x="{cx - sw/2 + 2}" y="{cy - sh/2 + 2}" '
            f'width="{sw - 4}" height="{sh - 8}" rx="1" '
            f'fill="#777" stroke="#999" stroke-width="0.5"/>'
        )
        lines.append(
            f'<rect x="{cx - sw/2 + 3}" y="{cy + sh/2 - 10}" '
            f'width="{sw - 6}" height="8" rx="1" '
            f'fill="none" stroke="#aaa" stroke-width="0.5" '
            f'stroke-dasharray="2,1"/>'
        )
        lines.append(
            f'<text x="{cx}" y="{cy - 2}" text-anchor="middle" '
            f'font-family="monospace" font-size="5" fill="{TEXT_COLOR}" '
            f'font-weight="bold">{ref}</text>'
        )
        lines.append(
            f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" '
            f'font-family="monospace" font-size="3.5" fill="#ccc">'
            f'{value}</text>'
        )

    elif pkg == "SW":
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="1" '
            f'fill="{SWITCH_BODY}" stroke="#666" stroke-width="0.5"/>'
        )
        r_btn = min(sw, sh) * 0.3
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r_btn}" '
            f'fill="{SWITCH_TOP}" stroke="#999" stroke-width="0.3"/>'
        )
        lines.append(
            f'<text x="{cx}" y="{cy + 1.5}" text-anchor="middle" '
            f'font-family="monospace" font-size="4" fill="{TEXT_COLOR}" '
            f'font-weight="bold">{value}</text>'
        )

    elif pkg == "SLIDE_SW":
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="1.5" '
            f'fill="#444" stroke="#666" stroke-width="0.5"/>'
        )
        lines.append(
            f'<rect x="{cx - sw/3}" y="{cy - sh/4}" '
            f'width="{sw*2/3}" height="{sh/3}" rx="1" '
            f'fill="#888" stroke="#aaa" stroke-width="0.3"/>'
        )
        lines.append(
            f'<text x="{cx}" y="{cy + sh/2 + 5}" text-anchor="middle" '
            f'font-family="monospace" font-size="2.5" fill="{SILKSCREEN}">'
            f'{value}</text>'
        )

    elif pkg == "LED":
        color = LED_RED if "CHG" in value else LED_GREEN
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="0.5" '
            f'fill="{color}" stroke="#fff" stroke-width="0.3" opacity="0.9"/>'
        )
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{_s(2)}" '
            f'fill="{color}" opacity="0.15"/>'
        )

    elif pkg == "Speaker":
        # 22mm speaker — circular with concentric rings
        r = _s(w / 2)
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" '
            f'fill="#2a2a2a" stroke="#555" stroke-width="1"/>'
        )
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.7}" '
            f'fill="#3a3a3a" stroke="#555" stroke-width="0.5"/>'
        )
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.35}" '
            f'fill="#4a4a4a" stroke="#666" stroke-width="0.5"/>'
        )
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r * 0.12}" '
            f'fill="#555" stroke="#777" stroke-width="0.3"/>'
        )

    elif pkg == "USB-C":
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="3" '
            f'fill="{CONNECTOR_METAL}" stroke="#ccc" stroke-width="0.8"/>'
        )
        lines.append(
            f'<rect x="{cx - sw/4}" y="{cy + sh/2 - 3}" '
            f'width="{sw/2}" height="3" rx="1.5" '
            f'fill="#444" stroke="#666" stroke-width="0.3"/>'
        )
        lines.append(
            f'<text x="{cx}" y="{cy}" text-anchor="middle" '
            f'font-family="monospace" font-size="3.5" fill="#333" '
            f'font-weight="bold">{ref}</text>'
        )

    elif pkg == "FPC":
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="0.5" '
            f'fill="#8b6914" stroke="#a0832a" stroke-width="0.5"/>'
        )
        n_pins = 16
        pin_pitch = (sw - 4) / (n_pins - 1)
        for i in range(n_pins):
            px = cx - sw / 2 + 2 + i * pin_pitch
            lines.append(
                f'<rect x="{px - 0.3}" y="{cy - sh/4}" '
                f'width="0.6" height="{sh/2}" fill="{PAD_GOLD}"/>'
            )

    elif pkg == "TF-01A":
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="1" '
            f'fill="{CONNECTOR_METAL}" stroke="#888" stroke-width="0.8"/>'
        )
        lines.append(
            f'<rect x="{cx - sw/3}" y="{cy + sh/2 - 4}" '
            f'width="{sw*2/3}" height="4" rx="0.5" fill="#444"/>'
        )
        lines.append(
            f'<text x="{cx}" y="{cy}" text-anchor="middle" '
            f'font-family="monospace" font-size="3" fill="#333" '
            f'font-weight="bold">SD</text>'
        )

    elif pkg in ("ESOP-8", "SOT-223", "SOP-16"):
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="0.5" '
            f'fill="{COMPONENT_IC}" stroke="#555" stroke-width="0.5"/>'
        )
        lines.append(
            f'<circle cx="{cx - sw/2 + 2}" cy="{cy - sh/2 + 2}" r="0.8" '
            f'fill="#888"/>'
        )
        n_side = 8 if pkg == "SOP-16" else (4 if pkg == "ESOP-8" else 2)
        pin_h = sh / (n_side + 1)
        for i in range(n_side):
            py = cy - sh / 2 + pin_h * (i + 1)
            lines.append(
                f'<rect x="{cx - sw/2 - 2}" y="{py - 0.5}" '
                f'width="2.5" height="1" fill="{PAD_GOLD}"/>'
            )
            lines.append(
                f'<rect x="{cx + sw/2 - 0.5}" y="{py - 0.5}" '
                f'width="2.5" height="1" fill="{PAD_GOLD}"/>'
            )
        lines.append(
            f'<text x="{cx}" y="{cy + 1}" text-anchor="middle" '
            f'font-family="monospace" font-size="3" fill="{TEXT_COLOR}" '
            f'font-weight="bold">{value}</text>'
        )

    elif pkg == "Inductor":
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="1" '
            f'fill="#4a4a4a" stroke="#666" stroke-width="0.5"/>'
        )
        r_coil = min(sw, sh) * 0.25
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r_coil}" '
            f'fill="none" stroke="#888" stroke-width="0.5"/>'
        )
        lines.append(
            f'<text x="{cx}" y="{cy + sh/2 + 4}" text-anchor="middle" '
            f'font-family="monospace" font-size="2.5" fill="{SILKSCREEN}">'
            f'{ref} {value}</text>'
        )

    elif pkg == "JST-PH":
        lines.append(
            f'<rect x="{cx - sw/2}" y="{cy - sh/2}" '
            f'width="{sw}" height="{sh}" rx="0.5" '
            f'fill="#e8e0d0" stroke="#ccc" stroke-width="0.5"/>'
        )
        lines.append(
            f'<circle cx="{cx - 2}" cy="{cy}" r="1" '
            f'fill="{PAD_GOLD}" stroke="#a08020" stroke-width="0.3"/>'
        )
        lines.append(
            f'<circle cx="{cx + 2}" cy="{cy}" r="1" '
            f'fill="{PAD_GOLD}" stroke="#a08020" stroke-width="0.3"/>'
        )
        lines.append(
            f'<text x="{cx}" y="{cy + sh/2 + 4}" text-anchor="middle" '
            f'font-family="monospace" font-size="2.5" fill="{SILKSCREEN}">'
            f'{ref} BAT</text>'
        )

    return "\n".join(lines)


def _draw_passive(ref, value, x, y):
    cx, cy = _tx(x), _ty(y)
    w, h = _s(2.0), _s(1.25)
    is_cap = ref.startswith("C")
    body_color = PASSIVE_CAP if is_cap else PASSIVE_BODY
    return "\n".join([
        f'<rect x="{cx - w/2}" y="{cy - h/2}" '
        f'width="{w}" height="{h}" rx="0.3" '
        f'fill="{body_color}" stroke="#666" stroke-width="0.3"/>',
        f'<rect x="{cx - w/2}" y="{cy - h/2}" '
        f'width="{w * 0.25}" height="{h}" rx="0.2" '
        f'fill="{PAD_GOLD}" opacity="0.8"/>',
        f'<rect x="{cx + w/2 - w * 0.25}" y="{cy - h/2}" '
        f'width="{w * 0.25}" height="{h}" rx="0.2" '
        f'fill="{PAD_GOLD}" opacity="0.8"/>',
    ])


def _draw_silkscreen(text, x, y, size):
    cx, cy = _tx(x), _ty(y)
    fs = size * SCALE * 0.8
    return (
        f'<text x="{cx}" y="{cy}" text-anchor="middle" '
        f'dominant-baseline="middle" '
        f'font-family="monospace" font-size="{fs}" '
        f'fill="{SILKSCREEN}" opacity="0.9">{text}</text>'
    )


def _draw_traces(traces, mirror_x=False):
    """Draw trace segments as colored lines."""
    lines = []
    for x1, y1, x2, y2, color, w_mm in traces:
        if mirror_x:
            x1, x2 = BOARD_W - x1, BOARD_W - x2
        sx1, sy1 = _tx(x1), _ty(y1)
        sx2, sy2 = _tx(x2), _ty(y2)
        sw = _s(w_mm * 0.4)  # visual width (scaled down for clarity)
        lines.append(
            f'<line x1="{sx1}" y1="{sy1}" x2="{sx2}" y2="{sy2}" '
            f'stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="round" opacity="0.7"/>'
        )
    return "\n".join(lines)


def _draw_vias(traces, mirror_x=False):
    """Draw via dots at trace endpoints."""
    lines = []
    for x1, y1, x2, y2, color, _ in traces:
        # Draw via at the end point of each button trace
        vx, vy = x2, y2
        if mirror_x:
            vx = BOARD_W - vx
        cx, cy = _tx(vx), _ty(vy)
        r = _s(0.4)
        lines.append(
            f'<circle cx="{cx}" cy="{cy}" r="{r}" '
            f'fill="{PAD_GOLD}" stroke="{HOLE_DARK}" stroke-width="0.5"/>'
        )
    return "\n".join(lines)


def generate_svg(view="top"):
    """Generate complete SVG for one side of the PCB."""
    title = f"ESP32 Emu Turbo — {'Top' if view == 'top' else 'Bottom'} View"
    parts = [_svg_header(title, view)]
    parts.append(_draw_board(view))
    parts.append(_draw_mounting_holes())

    if view == "top":
        # Display area (the main visual element on top)
        parts.append(_draw_display_area())
        # Traces (button to via)
        top_traces = _get_top_traces()
        parts.append(_draw_traces(top_traces))
        parts.append(_draw_vias(top_traces))
        # Top-side components
        for ref, val, pkg, x, y, w, h in COMPONENTS_TOP:
            parts.append(_draw_component(ref, val, pkg, x, y, w, h))
        # Silkscreen
        for text, x, y, size in SILKSCREEN_TOP:
            parts.append(_draw_silkscreen(text, x, y, size))
        # Board title
        parts.append(_draw_silkscreen(
            "ESP32 Emu Turbo v1.0", 40.0, 72.0, 1.0))

    elif view == "bottom":
        # Copper fill hint
        path = _rounded_rect_path(
            1, 1, BOARD_W - 2, BOARD_H - 2, CORNER_R - 1)
        parts.append(f'<path d="{path}" fill="#1a4a2a" opacity="0.3"/>')
        # Traces (mirrored for bottom view)
        bottom_traces = _get_bottom_traces()
        parts.append(_draw_traces(bottom_traces, mirror_x=True))
        # Bottom components (mirrored X for bottom view)
        for ref, val, pkg, x, y, w, h in COMPONENTS_BOTTOM:
            mx = BOARD_W - x
            parts.append(_draw_component(ref, val, pkg, mx, y, w, h))
        # Passives (mirrored)
        for ref, val, x, y in PASSIVES_BACK:
            mx = BOARD_W - x
            parts.append(_draw_passive(ref, val, mx, y))
        # Silkscreen (mirrored)
        for text, x, y, size in SILKSCREEN_BOTTOM:
            mx = BOARD_W - x
            parts.append(_draw_silkscreen(text, mx, y, size))

    parts.append(_svg_footer())
    return "\n".join(parts)


def generate_combined_svg():
    total_w = SVG_W * 2 + 40
    total_h = SVG_H + 60

    parts = [f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {total_w} {total_h}"
     width="{total_w}" height="{total_h}">
<title>ESP32 Emu Turbo — PCB Layout (Both Sides)</title>
<rect width="{total_w}" height="{total_h}" fill="#1a1a2e"/>
<text x="{total_w/2}" y="22" text-anchor="middle"
      font-family="monospace" font-size="16" fill="#aaa" font-weight="bold">
  ESP32 Emu Turbo — PCB Layout (160x75mm, 4-Layer)
</text>
"""]

    # Top view (left)
    parts.append('<g transform="translate(0, 35)">')
    top_svg = generate_svg("top")
    body_start = top_svg.find("<defs>")
    body_end = top_svg.rfind("</svg>")
    parts.append(top_svg[body_start:body_end])
    parts.append("</g>")

    # Bottom view (right)
    parts.append(f'<g transform="translate({SVG_W + 40}, 35)">')
    bot_svg = generate_svg("bottom")
    body_start = bot_svg.find("<defs>")
    body_end = bot_svg.rfind("</svg>")
    bot_body = bot_svg[body_start:body_end]
    for old, new in [
        ("shadow", "shadow2"), ("grid", "grid2"),
        ("board-clip", "board-clip2"),
    ]:
        bot_body = bot_body.replace(f'id="{old}"', f'id="{new}"')
        bot_body = bot_body.replace(f'url(#{old})', f'url(#{new})')
    parts.append(bot_body)
    parts.append("</g>")

    parts.append("</svg>\n")
    return "\n".join(parts)


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "website/static/img/pcb"
    os.makedirs(output_dir, exist_ok=True)

    for view in ("top", "bottom"):
        svg = generate_svg(view)
        path = os.path.join(output_dir, f"pcb-{view}.svg")
        with open(path, "w") as f:
            f.write(svg)
        print(f"  PCB {view} view: {path}")

    combined = generate_combined_svg()
    path = os.path.join(output_dir, "pcb-combined.svg")
    with open(path, "w") as f:
        f.write(combined)
    print(f"  PCB combined: {path}")

    print(f"\nGenerated 3 SVG renders in {output_dir}/")


if __name__ == "__main__":
    main()
