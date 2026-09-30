#!/usr/bin/env python3
"""Draw the power / system SVG figures that replaced the ASCII diagrams.

Same kit as the other doc figures (svgfig.py): hand-placed, vector, one
palette, readable in both site themes.
Run: python3 website/scripts/gen_svgs_power.py
Output: website/static/img/diagrams/*.svg

  system-block.svg  design/schematics.md (system block diagram),
                    overview/feasibility.md (hardware schematic)
  power-path.svg    design/schematics.md (power path architecture)
  power-chain.svg   design/components.md (power architecture note)
  power-tree.svg    manufacturing/verification.md (power tree + budget)
"""
import os

from svgfig import C, INK, MUTED, Svg

OUT = os.path.join(os.path.dirname(__file__), "..", "static", "img", "diagrams")

Svg.out_dir = OUT

WIRE = "#475569"


def tbox(s, x, y, w, h, title, color="gray", rows=(), size=13.5, row_size=11.5):
    """A box whose text block is centred by hand (title-only boxes included)."""
    s.box(x, y, w, h, None, [], color)
    n = len(rows)
    total = size + n * (row_size + 5)
    ty = y + (h - total) / 2 + size - 1
    s.text(x + w / 2, ty, title, size, 650, C[color][2])
    for i, r in enumerate(rows):
        s.text(x + w / 2, ty + (i + 1) * (row_size + 5) + 1, r, row_size, color=C[color][2])


def wire(s, pts, color=WIRE, dashed=False, width=1.6):
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    s.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}"{dash}/>')


def dot(s, x, y, color=WIRE):
    s.add(f'<circle cx="{x}" cy="{y}" r="3.6" fill="{color}"/>')


def net(s, x, y, label, color=MUTED, anchor="middle", weight=600, size=11.5):
    s.text(x, y, label, size, weight, color, anchor=anchor)


def gnd(s, x, y):
    wire(s, [(x, y), (x, y + 10)])
    for i, hw in enumerate((10, 6, 2.5)):
        wire(s, [(x - hw, y + 10 + i * 4), (x + hw, y + 10 + i * 4)], width=1.6)


# ---------------------------------------------------------------------------
def system_block():
    s = Svg(1000, 760, "System block diagram")
    # power section
    s.group(20, 20, 960, 400, "power", "orange")
    tbox(s, 40, 70, 110, 56, "USB-C", "gray", ["5 V in"])
    tbox(s, 220, 60, 220, 76, "IP5306 (U2)", "orange", ["charge + boost", "5 V out on +5V_VOUT"])
    s.arrow([(150, 98), (218, 98)], "VBUS", lx=184, ly=86)
    tbox(s, 220, 188, 220, 56, "Q1 AO3401A", "red", ["reverse-polarity protection"])
    tbox(s, 220, 290, 220, 76, "LiPo 3.7 V 5000 mAh", "amber", ["105080 cell", "on J3"])
    s.arrow([(330, 138), (330, 186)], "BAT+", lx=362, ly=162, both=True)
    s.arrow([(330, 246), (330, 288)], None, both=True)

    tbox(s, 530, 60, 200, 76, "Q2 AO3401A", "red", ["high-side P-MOSFET", "cuts the +5V load rail"])
    s.arrow([(440, 98), (528, 98)], "+5V_VOUT", lx=484, ly=86)
    tbox(s, 530, 206, 200, 96, "SW16 power switch", "blue",
         ["gate net R32 · R33 · C32", "C33 wake pulse", "into IP5306 KEY"])
    s.arrow([(630, 204), (630, 138)], "gate", lx=652, ly=172)
    s.arrow([(530, 280), (480, 280), (480, 118), (442, 118)], "KEY\n(wake)", lx=480, ly=236, dashed=True,
            color=C["blue"][0])

    # +5V bus and its loads
    wire(s, [(730, 98), (790, 98), (790, 390)], color=C["red"][0], width=2.2)
    net(s, 760, 90, "+5V", C["red"][0])
    net(s, 800, 400, "+5V (loads)", C["red"][0], anchor="start")
    tbox(s, 820, 60, 150, 64, "PAM8403 (U5)", "purple", ["+ speaker"])
    tbox(s, 820, 150, 150, 64, "R27 20 Ω", "gray", ["LCD backlight"])
    tbox(s, 820, 240, 150, 64, "SY8089 (U3)", "teal", ["buck 5 V to 3.3 V"])
    for y in (92, 182, 272):
        s.arrow([(790, y), (818, y)])
        dot(s, 790, y)

    # 3.3 V to the MCU
    s.arrow([(895, 306), (895, 450), (722, 450)], "+3V3", lx=895, ly=380, color=C["teal"][0])
    tbox(s, 280, 430, 440, 76, "ESP32-S3-WROOM-1 N16R8", "blue",
         ["2 × LX7 240 MHz · 16 MB flash · 8 MB Octal PSRAM"], size=15, row_size=12)

    # peripherals
    per = [("Display", "teal", ["ILI9488 3.95\" 320×480", "8-bit 8080 parallel"]),
           ("SD card", "green", ["module on SPI", "ROMs"]),
           ("USB data", "gray", ["native D- / D+"]),
           ("Audio", "purple", ["PDM on GPIO17", "to PAM8403 + speaker"]),
           ("Controls", "amber", ["12 buttons: D-pad", "A B X Y · Start · Select · L R"])]
    w, gap, x0, y = 178, 17, 24, 590
    for i, (t, c, r) in enumerate(per):
        x = x0 + i * (w + gap)
        tbox(s, x, y, w, 84, t, c, r, row_size=11)
        s.arrow([(360 + i * 70, 508), (x + w / 2, y - 2)])
    s.text(500, 712, "SW16 OFF: Q2 open, all +5V loads dead, USB still charges the cell.", 12.5, color=INK)
    s.text(500, 734, "SW16 ON: C33 couples a wake pulse into IP5306 KEY, Q2 closes.", 12.5, color=INK)
    s.save("system-block.svg")


# ---------------------------------------------------------------------------
def power_path():
    s = Svg(1000, 790, "Power path and SW16 gate network")
    # --- main path ------------------------------------------------------
    s.group(20, 20, 960, 330, "main path · the switch cuts the load rail only, never the charge path", "orange")
    ix, iy, iw, ih = 300, 70, 170, 210
    s.box(ix, iy, iw, ih, None, [], "orange")
    s.text(ix + iw / 2, iy + 100, "IP5306", 16, 700, C["orange"][2])
    s.text(ix + iw / 2, iy + 120, "(U2)", 12, color=C["orange"][2])
    pin = dict(size=11, color=C["orange"][2], weight=600)
    s.text(ix + 8, 104, "pin 1 VIN", anchor="start", **pin)
    s.text(ix + 8, 204, "pin 6 BAT", anchor="start", **pin)
    s.text(ix + iw - 8, 124, "pin 8 VOUT", anchor="end", **pin)
    s.text(ix + iw - 8, 234, "pin 7 LX", anchor="end", **pin)
    s.text(ix + 40, iy + ih - 10, "pin 5 KEY", **pin)
    s.text(ix + 130, iy + ih - 10, "GND", **pin)

    tbox(s, 36, 80, 90, 46, "USB-C", "gray", ["5 V"])
    tbox(s, 180, 80, 80, 46, "F1", "gray", ["PTC"])
    s.arrow([(126, 100), (178, 100)], "VBUS_IN", lx=152, ly=72)
    s.arrow([(260, 100), (298, 100)])
    tbox(s, 36, 176, 90, 50, "Battery", "amber", ["3.7 V · J3"])
    tbox(s, 180, 180, 80, 46, "Q1", "red", ["RPP"])
    s.arrow([(126, 200), (178, 200)], "BAT_IN", lx=152, ly=172)
    s.arrow([(260, 200), (298, 200)])
    net(s, 279, 192, "BAT+", C["amber"][0], size=10.5)

    # VOUT -> C27 -> Q2 -> +5V bus
    s.arrow([(470, 120), (578, 120)])
    dot(s, 520, 120)
    net(s, 525, 112, "+5V_VOUT", C["orange"][0])
    wire(s, [(520, 120), (520, 150)])
    s.text(532, 162, "C27", 11.5, 600, MUTED, anchor="start")
    wire(s, [(510, 150), (530, 150)], width=2)
    wire(s, [(510, 156), (530, 156)], width=2)
    gnd(s, 520, 156)
    tbox(s, 580, 96, 90, 48, "Q2", "red", ["PMOS"])
    wire(s, [(670, 120), (720, 120), (720, 245)], color=C["red"][0], width=2.2)
    net(s, 695, 112, "+5V", C["red"][0])
    tbox(s, 750, 70, 100, 46, "SY8089", "teal", ["(U3)"])
    tbox(s, 870, 64, 96, 58, "+3V3", "blue", ["ESP32 · LCD", "SD"])
    s.arrow([(720, 93), (748, 93)])
    s.arrow([(850, 93), (868, 93)])
    tbox(s, 750, 150, 216, 46, "PAM8403 (U5)", "purple")
    tbox(s, 750, 222, 90, 46, "R27", "gray")
    tbox(s, 868, 222, 98, 46, "backlight", "gray")
    s.arrow([(720, 173), (748, 173)])
    s.arrow([(720, 245), (748, 245)])
    s.arrow([(840, 245), (866, 245)])
    for y in (93, 173, 245):
        dot(s, 720, y)
    # LX -> L1 -> BAT+
    s.arrow([(470, 230), (518, 230)])
    tbox(s, 520, 210, 70, 40, "L1", "gray")
    s.arrow([(590, 230), (640, 230)])
    net(s, 645, 234, "BAT+", C["amber"][0], anchor="start")
    # KEY and GND out of the bottom
    wire(s, [(ix + 40, iy + ih), (ix + 40, 322)], color=C["blue"][0])
    net(s, ix + 48, 318, "IP5306_KEY (from C33 below)", C["blue"][0], anchor="start")
    gnd(s, ix + 130, iy + ih)

    # --- gate network ---------------------------------------------------
    gy = 370
    s.group(20, gy, 960, 400, "gate network · SW16 does nothing but pull PWR_SW to GND", "blue")
    net(s, 250, gy + 52, "+5V_VOUT", C["orange"][0])
    wire(s, [(250, gy + 58), (250, gy + 74)])
    wire(s, [(170, gy + 74), (330, gy + 74)])
    wire(s, [(170, gy + 74), (170, gy + 92)])
    wire(s, [(330, gy + 74), (330, gy + 92)])
    dot(s, 250, gy + 74)
    tbox(s, 120, gy + 92, 100, 40, "R32 22k", "gray")
    tbox(s, 280, gy + 92, 100, 40, "C32 1 µF", "gray")
    wire(s, [(170, gy + 132), (170, gy + 150), (330, gy + 150), (330, gy + 132)])
    dot(s, 250, gy + 150)
    s.text(400, gy + 108, "default = OFF", 11.5, color=MUTED, anchor="start")
    s.text(400, gy + 124, "C32 = soft start", 11.5, color=MUTED, anchor="start")
    wire(s, [(250, gy + 150), (250, gy + 196)])
    dot(s, 250, gy + 176)
    net(s, 240, gy + 172, "PWR_SW_GATE", C["red"][0], anchor="end")
    s.arrow([(250, gy + 176), (598, gy + 176)], None, color=C["red"][0])
    tbox(s, 600, gy + 158, 110, 36, "Q2 gate", "red")
    tbox(s, 200, gy + 196, 100, 38, "R33 1k", "gray")
    s.text(340, gy + 220, "τ = (R32 || R33) · C32 = 957 µs", 12, 600, INK, anchor="start")
    wire(s, [(250, gy + 234), (250, gy + 262)])
    dot(s, 250, gy + 262)
    net(s, 260, gy + 256, "PWR_SW", C["blue"][0], anchor="start")
    wire(s, [(130, gy + 262), (780, gy + 262)])
    wire(s, [(130, gy + 262), (130, gy + 280)])
    wire(s, [(520, gy + 262), (520, gy + 280)])
    wire(s, [(780, gy + 262), (780, gy + 280)])
    dot(s, 520, gy + 262)
    tbox(s, 40, gy + 280, 260, 104, "SW16", "blue",
         ["pad 2 (common) = PWR_SW", "pad 1 = GND (ON position)", "pad 3 = OPEN",
          "tabs 4a–4d mechanical (4b/4d on BTN_SELECT)"], row_size=11)
    tbox(s, 450, gy + 280, 140, 40, "R34 1M", "gray")
    s.arrow([(520, gy + 320), (520, gy + 336)])
    net(s, 520, gy + 350, "BAT+", C["amber"][0])
    s.text(520, gy + 368, "defines the node when", 11, color=MUTED)
    s.text(520, gy + 382, "the throw is open", 11, color=MUTED)
    tbox(s, 710, gy + 280, 140, 40, "C33 4.7 µF", "gray")
    s.arrow([(780, gy + 320), (780, gy + 336)], color=C["blue"][0])
    net(s, 780, gy + 350, "IP5306_KEY", C["blue"][0])
    s.text(780, gy + 368, "wake pulse on the", 11, color=MUTED)
    s.text(780, gy + 382, "ON transition", 11, color=MUTED)
    s.save("power-path.svg")


# ---------------------------------------------------------------------------
def power_chain():
    s = Svg(1000, 230, "Power architecture")
    boxes = [("USB-C", "gray", ["5 V in"]), ("IP5306", "orange", ["charge + boost"]),
             ("Q2 PMOS", "red", ["high-side switch"]), ("SY8089", "teal", ["buck"]),
             ("ESP32-S3", "blue", ["+ LCD · SD"])]
    labels = ["", "+5V_VOUT", "+5V", "3.3 V"]
    w, gap, x0, y = 140, 75, 20, 30
    for i, (t, c, r) in enumerate(boxes):
        x = x0 + i * (w + gap)
        tbox(s, x, y, w, 60, t, c, r)
        if i < len(boxes) - 1:
            s.arrow([(x + w, y + 30), (x + w + gap - 2, y + 30)], labels[i] or None, lx=x + w + gap / 2,
                    ly=y + 16)
    ipx = x0 + (w + gap) + w / 2
    q2x = x0 + 2 * (w + gap) + w / 2
    tbox(s, ipx - 80, 150, 160, 50, "LiPo battery", "amber", ["3.7 V 5000 mAh"])
    s.arrow([(ipx, 148), (ipx, 92)], None, both=True)
    tbox(s, q2x - 70, 150, 140, 50, "SW16", "blue", ["power switch"])
    s.arrow([(q2x, 148), (q2x, 92)], "gate", lx=q2x + 26, ly=120)
    s.save("power-chain.svg")


# ---------------------------------------------------------------------------
def power_tree():
    s = Svg(1000, 520, "Power tree and current budget")
    tbox(s, 20, 150, 130, 70, "LiPo 3.7 V", "amber", ["5000 mAh"])
    tbox(s, 190, 150, 150, 70, "IP5306", "orange", ["boost"])
    s.arrow([(150, 185), (188, 185)], None, both=True)
    tbox(s, 190, 30, 150, 60, "USB-C VBUS", "gray", ["charge input · 1 A max"])
    s.arrow([(265, 92), (265, 148)], "charges with\nSW16 OFF", lx=312, ly=120)
    tbox(s, 420, 150, 120, 70, "Q2", "red", ["PMOS"])
    s.arrow([(340, 185), (418, 185)], "+5V_VOUT", lx=379, ly=172)

    # +5V bus
    wire(s, [(540, 185), (600, 185), (600, 435)], color=C["red"][0], width=2.2)
    s.badge(612, 250, "+5V · 387 mA max", "red")
    tbox(s, 640, 150, 150, 70, "SY8089", "teal", ["buck"])
    s.arrow([(600, 185), (638, 185)])
    tbox(s, 640, 330, 150, 50, "PAM8403", "purple", ["50 mA"])
    tbox(s, 640, 410, 150, 50, "LEDs", "green", ["2.4 mA"])
    for y in (355, 435):
        s.arrow([(600, y), (638, y)])
        dot(s, 600, y)
    dot(s, 600, 185)
    # +3V3 bus
    wire(s, [(790, 185), (820, 185), (820, 110), (820, 290)], color=C["teal"][0], width=2.2)
    s.badge(700, 116, "+3V3 · 2 A max", "teal")
    for y, (t, r) in zip((60, 150, 240), [("ESP32-S3", "200 mA"), ("Display", "100 mA"), ("SD card", "30 mA")]):
        tbox(s, 850, y, 130, 50, t, "blue", [r])
        s.arrow([(820, y + 25), (848, y + 25)])
        dot(s, 820, y + 25)
    wire(s, [(820, 85), (820, 110)], color=C["teal"][0], width=2.2)

    # gate path
    tbox(s, 20, 300, 130, 56, "SW16", "blue", ["drives PWR_SW"])
    tbox(s, 190, 300, 150, 56, "R33", "gray", ["to PWR_SW_GATE"])
    s.arrow([(150, 328), (188, 328)])
    s.arrow([(340, 328), (480, 328), (480, 222)], "gate", lx=480, ly=276, color=C["blue"][0])
    s.text(20, 396, "PWR_SW_GATE: R32 / C32 to +5V_VOUT", 12, color=MUTED, anchor="start")
    s.text(20, 414, "C33 wake pulse into IP5306_KEY", 12, color=MUTED, anchor="start")
    s.text(20, 452, "USB charging is upstream of Q2:", 12, 600, INK, anchor="start")
    s.text(20, 470, "the cell charges with SW16 OFF.", 12, 600, INK, anchor="start")
    s.save("power-tree.svg")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (system_block, power_path, power_chain, power_tree):
        fn()
    print("written:", sorted(os.listdir(OUT)))
