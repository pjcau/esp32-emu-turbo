#!/usr/bin/env python3
"""Draw the hardware SVG figures that replaced the text diagrams of the docs.

Same kit as the other doc figures (svgfig.py): hand-placed, vector, one
palette, readable in both site themes. Run: python3 website/scripts/gen_svgs_hw.py
Output: website/static/img/diagrams/*.svg

  circuit-button-pullup.svg    design/schematics.md            (button circuit)
  circuit-button-breadboard.svg manufacturing/prototyping.md   (step 6, buttons)
  circuit-gpio0-select.svg     manufacturing/verification.md   (GPIO0 / SELECT)
  wiring-breadboard-power.svg  manufacturing/prototyping.md    (step 1, power rail)
  wiring-devkit-power.svg      manufacturing/prototyping.md    (step 2, DevKit)
  wiring-audio-chain.svg       overview/snes-hardware.md       (audio architecture)
  wiring-lcd-8080.svg          software/overview.md            (ESP32 -> ILI9488)
  display-rotation.svg         design/components.md            (display orientation)
  enclosure-layout.svg         design/enclosure.md             (physical layout)

The enclosure figure is drawn to scale from the constants of
hardware/enclosure/enclosure.scad (copied below, keep them in step).
"""
import os

from svgfig import C, INK, MUTED, MONO, Svg

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "img", "diagrams")

Svg.out_dir = OUT

WIRE = "#334155"


# ---- schematic symbols -----------------------------------------------------
def wire(s, pts, color=WIRE, width=1.8):
    s.add('<path d="M' + " L".join(f"{x},{y}" for x, y in pts) +
          f'" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"/>')


def dot(s, x, y, color=WIRE):
    s.add(f'<circle cx="{x}" cy="{y}" r="4" fill="{color}"/>')


def resistor_h(s, x1, x2, y, color=WIRE):
    """Zigzag resistor between x1 and x2 (leads included)."""
    lead = (x2 - x1) * 0.2
    a, b = x1 + lead, x2 - lead
    n = 6
    pts = [(x1, y), (a, y)]
    for i in range(n):
        pts.append((a + (b - a) * (i + 0.5) / n, y + (-8 if i % 2 == 0 else 8)))
    pts += [(b, y), (x2, y)]
    wire(s, pts, color, 2)


def capacitor_v(s, x, y1, y2, color=WIRE):
    m = (y1 + y2) / 2
    wire(s, [(x, y1), (x, m - 5)])
    wire(s, [(x, m + 5), (x, y2)])
    s.add(f'<path d="M{x - 16},{m - 5} L{x + 16},{m - 5} M{x - 16},{m + 5} L{x + 16},{m + 5}" '
          f'stroke="{color}" stroke-width="2.6"/>')


def switch_v(s, x, y1, y2, color=WIRE):
    """Normally-open push button between y1 (top) and y2 (bottom)."""
    a, b = y1 + (y2 - y1) * 0.3, y2 - (y2 - y1) * 0.3
    wire(s, [(x, y1), (x, a)])
    wire(s, [(x, b), (x, y2)])
    for yy in (a, b):
        s.add(f'<circle cx="{x}" cy="{yy}" r="3.2" fill="#ffffff" stroke="{color}" stroke-width="1.8"/>')
    # contact bar held open, with its plunger
    bx = x - 14
    s.add(f'<path d="M{bx},{a - 4} L{bx},{b + 4}" stroke="{color}" stroke-width="2.4"/>')
    s.add(f'<path d="M{bx},{(a + b) / 2} L{bx - 16},{(a + b) / 2} M{bx - 16},{(a + b) / 2 - 6} '
          f'L{bx - 16},{(a + b) / 2 + 6}" stroke="{color}" stroke-width="1.8" fill="none"/>')


def gnd(s, x, y, color=WIRE):
    s.add(f'<path d="M{x - 14},{y} L{x + 14},{y} M{x - 9},{y + 6} L{x + 9},{y + 6} M{x - 4},{y + 12} '
          f'L{x + 4},{y + 12}" stroke="{color}" stroke-width="2"/>')
    s.text(x, y + 30, "GND", 12, 600, MUTED)


def rail(s, x, y, label, color="red"):
    """Supply rail: a short bar with its name above."""
    stroke = C[color][0]
    s.add(f'<path d="M{x - 18},{y} L{x + 18},{y}" stroke="{stroke}" stroke-width="3"/>')
    s.text(x, y - 10, label, 13, 700, stroke)


def net_label(s, x, y, label, color="blue"):
    """Global label: a flag pointing back at the wire."""
    stroke, bg, tx = C[color]
    w = len(label) * 7.6 + 26
    s.add(f'<path d="M{x},{y} L{x + 12},{y - 13} L{x + w},{y - 13} L{x + w},{y + 13} L{x + 12},{y + 13} Z" '
          f'fill="{bg}" stroke="{stroke}" stroke-width="1.6"/>')
    s.text(x + 12 + (w - 12) / 2, y + 4.5, label, 12.5, 650, tx)


def part_label(s, x, y, ref, value, anchor="start"):
    if ref:
        s.text(x, y, ref, 12.5, 700, INK, anchor=anchor)
        s.text(x, y + 17, value, 12.5, 400, MUTED, anchor=anchor)
    else:
        s.text(x, y + 8, value, 12.5, 600, INK, anchor=anchor)


# ---- button pull-up circuits -----------------------------------------------
def button_circuit(name, title, rail_name, r_ref, r_val, net, sw_ref, sw_val="", cap=None, note=None):
    has_cap = cap is not None
    s = Svg(760, 330, title)
    y = 90
    rail(s, 70, y - 22, rail_name)
    wire(s, [(70, y - 22), (70, y), (150, y)])
    resistor_h(s, 150, 280, y)
    part_label(s, 215, y - 42, r_ref, r_val, anchor="middle")
    nx = 380
    wire(s, [(280, y), (nx, y), (500, y)])
    dot(s, nx, y)
    net_label(s, 500, y, net)
    gy = 250
    if has_cap:
        cx, sx = nx - 70, nx + 70
        wire(s, [(nx, y), (nx, 130)])
        dot(s, nx, 130)
        wire(s, [(cx, 130), (sx, 130)])
        capacitor_v(s, cx, 130, gy)
        part_label(s, cx - 28, (130 + gy) / 2 - 4, cap[0], cap[1], anchor="end")
    else:
        sx = nx
    switch_v(s, sx, y if not has_cap else 130, gy)
    part_label(s, sx + 18, (y + gy) / 2 + (10 if has_cap else 0), sw_ref, sw_val)
    if has_cap:
        gnd(s, cx, gy)
    gnd(s, sx, gy)
    if note:
        s.box(560, 170, 176, 110, None, [], "gray", shadow=False)
        s.lines(648, 200, note, size=12, color=INK)
    s.save(name)


def buttons():
    button_circuit("circuit-button-pullup.svg", "Button circuit", "+3V3", "R", "10 kΩ", "GPIO_x",
                   "SW", "tact switch", cap=("C", "100 nF"),
                   note=["idle: HIGH", "(pulled up to 3.3 V)", "pressed: LOW", "(grounded by the switch)"])
    button_circuit("circuit-button-breadboard.svg", "Breadboard button wiring", "3.3V", None, "10 kΩ", "GPIO pin",
                   None, "switch",
                   note=["one per button:", "6 × 6 mm tact switch", "+ 10 kΩ pull-up", "to 3.3 V"])
    button_circuit("circuit-gpio0-select.svg", "GPIO0 and the SELECT button", "+3.3V", "R9", "10 k",
                   "GPIO0 (ESP32)", "SW10", "SELECT",
                   note=["at boot:", "HIGH = normal boot", "LOW = download mode", "(SELECT held)"])


# ---- breadboard power wiring -----------------------------------------------
def pin_row(s, x, y, name, side="right"):
    """A pin stub leaving a module box; returns the wire start point."""
    d = 1 if side == "right" else -1
    s.add(f'<path d="M{x},{y} L{x + 14 * d},{y}" stroke="{WIRE}" stroke-width="2"/>')
    s.text(x - 10 * d, y + 4.5, name, 12, 600, INK, anchor="end" if d == 1 else "start", font=MONO)
    return x + 14 * d, y


def breadboard_power():
    s = Svg(1000, 450, "Breadboard power rail")
    rails = [("5V rail", 800, "red"), ("GND rail", 870, "gray"), ("3.3V rail", 940, "amber")]
    for label, x, col in rails:
        stroke, bg, _ = C[col]
        s.add(f'<rect x="{x - 9}" y="56" width="18" height="350" rx="9" fill="{bg}" stroke="{stroke}" '
              'stroke-width="2"/>')
        s.text(x, 40, label, 12.5, 700, stroke)
    rx = {r[0]: r[1] for r in rails}

    # IP5306 module
    s.box(330, 60, 190, 170, None, [], "blue")
    s.text(425, 86, "IP5306 Module", 14, 650, C["blue"][2])
    s.text(425, 104, "USB-C charge + boost", 12, 400, C["blue"][2])
    for y, name, dest in ((140, "OUT+", "5V rail"), (170, "OUT-", "GND rail")):
        x0, y0 = pin_row(s, 520, y, name)
        wire(s, [(x0, y0), (rx[dest] - 9, y0)])
        dot(s, rx[dest], y0, C["red" if dest == "5V rail" else "gray"][0])
    for y, name in ((180, "BAT+"), (206, "BAT-")):
        pin_row(s, 330, y, name, side="left")
    pin_row(s, 330, 140, "USB", side="left")
    s.box(40, 110, 170, 60, "USB-C cable", ["charging + power"], "gray", title_size=13)
    wire(s, [(210, 140), (316, 140)])
    s.box(40, 178, 170, 60, "LiPo battery", ["(+) and (-)"], "green", title_size=13)
    wire(s, [(210, 196), (260, 196), (260, 180), (316, 180)])
    wire(s, [(210, 220), (260, 220), (260, 206), (316, 206)])
    s.text(226, 190, "+", 12, 700, MUTED)
    s.text(226, 234, "-", 12, 700, MUTED)

    # buck module
    s.box(300, 262, 220, 140, None, [], "orange")
    s.text(410, 288, "Buck 5V to 3.3V", 14, 650, C["orange"][2])
    s.text(410, 306, "MP1584 stand-in for the SY8089 (U3)", 11.5, 400, C["orange"][2])
    for y, name, dest, badge in ((330, "VIN", "5V rail", "10 µF cap"), (356, "GND", "GND rail", None),
                                 (382, "VOUT", "3.3V rail", "22 µF cap")):
        x0, y0 = pin_row(s, 520, y, name)
        wire(s, [(x0, y0), (rx[dest] - 9, y0)])
        col = {"5V rail": "red", "GND rail": "gray", "3.3V rail": "amber"}[dest]
        dot(s, rx[dest], y0, C[col][0])
        if badge:
            s.add(f'<rect x="590" y="{y0 - 11}" width="120" height="22" rx="11" fill="#ffffff" '
                  f'stroke="{C["purple"][0]}" stroke-width="1.4"/>')
            s.text(650, y0 + 4.5, "through " + badge, 11.5, 600, C["purple"][2])
    s.text(40, 434, "a dot is a connection; wires that cross without a dot do not connect", 11.5, color=MUTED,
           anchor="start")
    s.save("wiring-breadboard-power.svg")


def devkit_power():
    s = Svg(1000, 250, "DevKit power")
    s.box(40, 50, 220, 150, "ESP32-S3 DevKitC-1", ["N16R8"], "blue", title_size=14)
    for label, x, col in (("5V rail", 800, "red"), ("GND rail", 900, "gray")):
        stroke, bg, _ = C[col]
        s.add(f'<rect x="{x - 9}" y="40" width="18" height="180" rx="9" fill="{bg}" stroke="{stroke}" '
              'stroke-width="2"/>')
        s.text(x, 28, label, 12.5, 700, stroke)
    x0, y0 = pin_row(s, 260, 80, "VIN")
    wire(s, [(x0, y0), (791, y0)])
    dot(s, 800, y0, C["red"][0])
    s.text(530, 72, "if USB is not connected directly", 11.5, color=MUTED)
    x0, y0 = pin_row(s, 260, 130, "USB")
    wire(s, [(x0, y0), (470, y0)])
    s.arrow([(470, y0), (498, y0)])
    s.box(500, 110, 230, 40, "Direct USB-C", [], "gray", title_size=13)
    s.text(615, 170, "programming / debug", 11.5, color=MUTED)
    s.add(f'<rect x="340" y="94" width="64" height="20" rx="10" fill="{C["amber"][0]}"/>')
    s.text(372, 108, "— OR —", 11, 700, "#ffffff")
    x0, y0 = pin_row(s, 260, 180, "GND")
    wire(s, [(x0, y0), (891, y0)])
    dot(s, 900, y0, C["gray"][0])
    wire(s, [(800, 80), (800, 80)])
    s.save("wiring-devkit-power.svg")


# ---- audio chain -------------------------------------------------------------
def audio_chain():
    s = Svg(1000, 250, "Audio chain")
    steps = [("ESP32-S3", ["PDM TX + DMA"], "blue", 190),
             ("C22", ["DC block"], "gray", 150),
             ("PAM8403", ["class-D amp"], "orange", 190),
             ("speaker", ["28 mm · 8 Ω"], "green", 170)]
    x, y, h = 30, 50, 76
    xs = []
    gap = (1000 - 60 - sum(w for *_, w in steps)) / (len(steps) - 1)
    for i, (t, r, c, w) in enumerate(steps):
        s.box(x, y, w, h, t, r, c)
        xs.append((x, w))
        if i < len(steps) - 1:
            s.arrow([(x + w, y + h / 2), (x + w + gap - 2, y + h / 2)])
        x += w + gap
    ex, ew = xs[0]
    s.arrow([(ex + ew / 2, y + h + 2), (ex + ew / 2, 186)], head=False, color=C["blue"][0])
    s.chip(ex + ew / 2 - s.chip_w("GPIO17 (I2S_DOUT)") / 2, 186, "GPIO17 (I2S_DOUT)", "blue")
    s.text(ex + ew + gap / 2, y + h / 2 - 10, "PDM", 11.5, 600, MUTED)
    px, pw = xs[2]
    s.arrow([(px + pw / 2, 184), (px + pw / 2, y + h + 4)], color=C["orange"][0])
    s.chip(px + pw / 2 - s.chip_w("R20/R21 bias to VREF (pin 8)") / 2, 186, "R20/R21 bias to VREF (pin 8)",
           "orange")
    s.save("wiring-audio-chain.svg")


# ---- ESP32 -> ILI9488 8080 bus -------------------------------------------------
def lcd_8080():
    rows = [("GPIO 4-11", "D0-D7", "DB0-DB7", "8-bit data bus", True),
            ("GPIO 12", "CS", "CS", "chip select", False),
            ("GPIO 14", "DC", "DC", "data / command", False),
            ("GPIO 46", "WR", "WR", "write strobe", False),
            ("+3V3", "RD", "RD", "tied HIGH, no read-back", False),
            ("GPIO 13", "RST", "RST", "reset", False),
            ("+5V via R27 (20 Ω)", "", "LED-A", "always-on backlight, net LED_BLA", False)]
    top, rh = 96, 44
    s = Svg(1000, top + len(rows) * rh + 30, "ESP32-S3 to ILI9488 wiring")
    s.box(30, 24, 300, top + len(rows) * rh - 30, None, [], "blue", shadow=True)
    s.text(180, 52, "ESP32-S3", 15, 700, C["blue"][2])
    s.box(640, 24, 330, top + len(rows) * rh - 30, None, [], "purple", shadow=True)
    s.text(805, 52, "ILI9488  (3.95\"  320 × 480)", 15, 700, C["purple"][2])
    for i, (src, sig, dst, what, bus) in enumerate(rows):
        y = top + i * rh
        power = src.startswith("+")
        col = "red" if power else "blue"
        s.text(50, y + 4.5, src, 13, 650, C[col][2] if not power else C["red"][0], anchor="start",
               font=MONO)
        if sig:
            s.text(310, y + 4.5, sig, 12.5, 700, MUTED, anchor="end", font=MONO)
        s.arrow([(332, y), (636, y)], width=1.8, color=C["red"][0] if power else "#64748b")
        if bus:
            s.add(f'<path d="M476,{y + 8} L488,{y - 8}" stroke="#64748b" stroke-width="2"/>')
            s.text(482, y - 12, "8", 12, 700, MUTED)
        s.text(660, y + 4.5, dst, 13, 700, C["purple"][2], anchor="start", font=MONO)
        s.text(740, y + 4.5, what, 12, 400, MUTED, anchor="start")
    s.save("wiring-lcd-8080.svg")


# ---- display orientation ----------------------------------------------------------
def display_rotation():
    s = Svg(1000, 360, "Display orientation")
    k = 0.52
    pw, ph = 320 * k, 480 * k
    px, py = 150, 60

    def panel(x, y, w, h, l1, l2, fpc):
        s.add(f'<rect x="{x - 8}" y="{y - 8}" width="{w + 16}" height="{h + 16}" rx="12" fill="#1e293b"/>')
        s.add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{C["blue"][1]}" '
              f'stroke="{C["blue"][0]}" stroke-width="1.6"/>')
        s.text(x + w / 2, y + h / 2 - 4, l1, 16, 700, C["blue"][2])
        s.text(x + w / 2, y + h / 2 + 16, l2, 13, 400, C["blue"][2])
        fx, fy, fw, fh = fpc
        s.add(f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="3" fill="{C["amber"][0]}"/>')

    panel(px, py, pw, ph, "320 × 480", "portrait", (px + pw / 2 - 30, py + ph + 8, 60, 22))
    s.text(px + pw / 2, 30, "Portrait (native)", 14, 700, INK)
    s.text(px + pw / 2 + 44, py + ph + 24, "FPC", 12, 700, C["amber"][2], anchor="start")

    lw, lh = 480 * k, 320 * k
    lx, ly = 560, 60 + (ph - lh) / 2
    panel(lx, ly, lw, lh, "480 × 320", "landscape", (lx - 30, ly + lh / 2 - 30, 22, 60))
    s.text(lx + lw / 2, 30, "Landscape (gaming mode)", 14, 700, INK)
    s.text(lx - 36, ly + lh / 2 + 48, "FPC", 12, 700, C["amber"][2], anchor="end")
    s.arrow([(360, 180), (500, 180)], width=2.4)
    s.text(430, 168, "rotate", 13, 600, INK)
    s.text(430, 202, "90° CW", 13, 600, INK)
    s.text(lx + lw / 2, ly + lh + 36, "the FPC tail ends up on the left: the D-pad side of the console", 12,
           color=MUTED)
    s.save("display-rotation.svg")


# ---- enclosure layout (to scale, from enclosure.scad) ------------------------------
BODY_W, BODY_H, CORNER_R = 170, 85, 8
SCREWS = [(-70, 30.5), (70, 30.5), (-70, -30.5), (70, -30.5)]
DPAD = (-62, 5, 24, 6.5)
ABXY = [("A", 62, 15), ("B", 72, 5), ("X", 62, -5), ("Y", 53, 5)]      # abxy_x/y + abxy_offsets
ABXY_D = 9
SS = [("START", -72, -17), ("SELECT", -52, -17)]                        # ss_x -/+ 10, ss_y
SS_W, SS_H = 10, 5
MENU = (62, -24.2, 12, 3.8)
LEDS_BIG = [(-55, -30), (-48, -30)]                                     # LED1 charge, LED2 full, o2
LEDS_DIAG = [(54, -20.5), (60, -20.5), (66, -20.5), (72, -20.5)]        # LED3..6, o1.2
GLASS = (0.75, 2, 94.57, 60.88)                                         # disp_glass_cx, outline
ACTIVE = (3.725, 2, 83.52, 55.68)                                       # disp_x, active area
TAIL_BORDER = 8.5                                                       # on the D-pad side (-X)
PORTS = [("PWR", -40, 8), ("USB-C", 0, 13), ("SD card", 60, 16)]        # x, cut width, bottom edge
LEVERS = [("L", -59.4), ("R", 59.4)]                                    # face cutout 14.8 x 9.3 at y 32
LEVER_W, LEVER_H, LEVER_Y = 14.8, 9.3, 32
SPK = (63.5, 8, 22)


def enclosure():
    k = 4.6
    vw, vh = BODY_W * k, BODY_H * k
    ox = (1000 - vw) / 2
    oy_front, oy_back = 70, 70 + vh + 130
    s = Svg(1000, oy_back + vh + 90, "Enclosure physical layout")

    def P(x, y, oy, back=False):
        return (ox + (BODY_W / 2 + (-x if back else x)) * k, oy + (BODY_H / 2 - y) * k)

    def rect_mm(cx, cy, w, h, oy, back=False, **kw):
        x, y = P(cx, cy, oy, back)
        attrs = " ".join(f'{a.replace("_", "-")}="{v}"' for a, v in kw.items())
        s.add(f'<rect x="{x - w * k / 2}" y="{y - h * k / 2}" width="{w * k}" height="{h * k}" {attrs}/>')

    def circle_mm(cx, cy, d, oy, back=False, **kw):
        x, y = P(cx, cy, oy, back)
        attrs = " ".join(f'{a.replace("_", "-")}="{v}"' for a, v in kw.items())
        s.add(f'<circle cx="{x}" cy="{y}" r="{d * k / 2}" {attrs}/>')

    def body(oy):
        s.add(f'<rect x="{ox}" y="{oy}" width="{vw}" height="{vh}" rx="{CORNER_R * k}" fill="#f1f5f9" '
              f'stroke="#64748b" stroke-width="2" filter="url(#sh)"/>')

    def ports(oy, back):
        for name, x, w in PORTS:
            rect_mm(x, -BODY_H / 2 + 1, w, 2.4, oy, back, fill=C["gray"][0], rx=3)
            px, py = P(x, -BODY_H / 2, oy, back)
            s.text(px, py + 22, name, 12, 650, C["gray"][2])

    # ---- FRONT
    s.text(ox, oy_front - 22, "FRONT  ·  display side, as the player sees it", 14, 700, INK, anchor="start")
    body(oy_front)
    for x, y in SCREWS:
        circle_mm(x, y, 7.2, oy_front, fill="none", stroke="#94a3b8", stroke_width=1.6,
                  stroke_dasharray="3 3")
    gx, gy, gw, gh = GLASS
    rect_mm(gx, gy, gw, gh, oy_front, fill="#1e293b", rx=6)
    ax, ay, aw, ah = ACTIVE
    rect_mm(ax, ay, aw, ah, oy_front, fill=C["blue"][1], stroke=C["blue"][0], stroke_width=1.4, rx=2)
    tx0 = gx - gw / 2
    rect_mm(tx0 + TAIL_BORDER / 2, gy, TAIL_BORDER - 1, gh - 6, oy_front, fill=C["amber"][0], opacity=0.85, rx=2)
    cx, cy = P(ax, ay, oy_front)
    s.text(cx, cy - 16, "active area 83.5 × 55.7", 15, 700, C["blue"][2])
    s.text(cx, cy + 6, "panel 94.6 × 60.9", 12.5, 400, C["blue"][2])
    s.text(cx, cy + 26, "glass centred between Select and Y", 12, 400, MUTED)
    tx, ty = P(tx0 + TAIL_BORDER / 2, gy, oy_front)
    s.add(f'<text x="{tx}" y="{ty}" font-family="Inter, \'Segoe UI\', system-ui, sans-serif" font-size="11.5" '
          f'font-weight="700" fill="#ffffff" text-anchor="middle" dominant-baseline="middle" '
          f'transform="rotate(-90 {tx} {ty})">FPC tail · U-folds under</text>')
    # D-pad
    dx, dy, dl, dw = DPAD
    for w, h in ((dl, dw), (dw, dl)):
        rect_mm(dx, dy, w, h, oy_front, fill="#ffffff", stroke=INK, stroke_width=1.6, rx=3)
    px_, py_ = P(dx, dy - dl / 2, oy_front)
    s.text(px_, py_ + 18, "D-pad", 12, 650, INK)
    for name, x, y in ABXY:
        circle_mm(x, y, ABXY_D, oy_front, fill="#ffffff", stroke=INK, stroke_width=1.6)
        px_, py_ = P(x, y, oy_front)
        s.text(px_, py_ + 5, name, 14, 700, INK)
    for name, x, y in SS:
        rect_mm(x, y, SS_W, SS_H, oy_front, fill="#ffffff", stroke=INK, stroke_width=1.6, rx=SS_H * k / 2)
        px_, py_ = P(x, y - SS_H / 2, oy_front)
        s.text(px_, py_ + 16, name, 11, 650, INK)
    mx, my, mw, mh = MENU
    rect_mm(mx, my, mw, mh, oy_front, fill="#ffffff", stroke=INK, stroke_width=1.6, rx=mh * k / 2)
    px_, py_ = P(mx - 4, my - mh / 2, oy_front)
    s.text(px_, py_ + 16, "MENU", 11, 650, INK)
    for (x, y), col in zip(LEDS_BIG, ("amber", "green")):
        circle_mm(x, y, 2.6, oy_front, fill=C[col][0])
    px_, py_ = P(-51.5, -30, oy_front)
    s.text(px_, py_ + 20, "LED1 · LED2", 11, 600, MUTED)
    for x, y in LEDS_DIAG:
        circle_mm(x, y, 1.8, oy_front, fill=C["teal"][0])
    px_, py_ = P(72, -20.5, oy_front)
    s.text(px_ + 10, py_ + 4, "LED3–6", 11, 600, MUTED, anchor="start")
    ports(oy_front, False)
    s.text(500, oy_front + vh + 44, "dashed circles: screw bosses at (±70, ±30.5)", 11.5, color=MUTED)
    s.text(ox + 8, oy_front + vh + 44, "D-pad side", 12, 700, C["gray"][0], anchor="start")
    s.text(ox + vw - 8, oy_front + vh + 44, "ABXY side", 12, 700, C["gray"][0], anchor="end")

    # ---- BACK (mirrored)
    s.text(ox, oy_back - 22, "BACK  ·  as seen from behind: left and right are MIRRORED", 14, 700, INK,
           anchor="start")
    body(oy_back)
    for x, y in SCREWS:
        circle_mm(x, y, 5, oy_back, True, fill="#334155")
    lx, ly = P(70, -30.5, oy_back, True)
    s.text(lx + 22, ly + 4, "M2.5 counterbore Ø5", 11, 600, MUTED, anchor="start")
    for name, x in LEVERS:
        rect_mm(x, LEVER_Y, LEVER_W, LEVER_H, oy_back, True, fill=C["purple"][1], stroke=C["purple"][0],
                stroke_width=1.8, rx=4)
        px_, py_ = P(x, LEVER_Y, oy_back, True)
        s.text(px_, py_ + 5, f"{name} lever", 12, 700, C["purple"][2])
    sx, sy, sd = SPK
    circle_mm(sx, sy, 30, oy_back, True, fill="none", stroke="#94a3b8", stroke_width=1.4, stroke_dasharray="4 4")
    circle_mm(sx, sy, sd, oy_back, True, fill=C["green"][1], stroke=C["green"][0], stroke_width=1.8)
    cx, cy = P(sx, sy, oy_back, True)
    step = 3.2
    for i in range(-3, 4):
        for j in range(-3, 4):
            if (i * step) ** 2 + (j * step) ** 2 <= (sd / 2 - 1.8) ** 2:
                s.add(f'<circle cx="{cx + i * step * k}" cy="{cy + j * step * k}" r="3" fill="{C["green"][0]}"/>')
    s.text(cx, cy + sd * k / 2 + 40, "speaker grille Ø22", 12, 650, C["green"][2])
    s.text(cx, cy + sd * k / 2 + 56, "seat for the 28 mm driver", 11, 400, MUTED)
    ports(oy_back, True)
    s.text(ox + 8, oy_back + vh + 44, "ABXY side", 12, 700, C["gray"][0], anchor="start")
    s.text(ox + vw - 8, oy_back + vh + 44, "D-pad side", 12, 700, C["gray"][0], anchor="end")
    s.text(500, oy_back + vh + 72, "to scale, 170 × 85 mm, positions from hardware/enclosure/enclosure.scad",
           11.5, color=MUTED)
    s.save("enclosure-layout.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (buttons, breadboard_power, devkit_power, audio_chain, lcd_8080, display_rotation, enclosure):
        fn()
    print("written:", sorted(f for f in os.listdir(OUT)
                             if f.startswith(("circuit-", "wiring-", "display-", "enclosure-"))))
