"""Complete PCB trace routing with Manhattan (orthogonal) paths.

All traces use only horizontal and vertical segments (L-shaped or
Z-shaped paths).  No diagonal lines.

Trace widths:
  - Power:  0.5mm (VBUS, +5V, +3V3, BAT+, GND returns)
  - Signal: 0.25mm (buttons, passives)
  - Data:   0.2mm  (display bus, SPI, I2S, USB)
  - Audio:  0.3mm  (PAM8403 -> speaker)

Layout notes:
  - FPC slot at enc(47, 2) creates a 3×24mm vertical cutout
  - J4 (FPC-40P) is right of slot at enc(55, 2), rotated 90° (vertical)
  - IP5306/AMS1117/L1 moved left to avoid slot zone
  - L/R shoulder buttons are on B.Cu (back side, rotated 90°)
"""

from . import primitives as P
from .primitives import NET_ID

# ── Trace widths ──────────────────────────────────────────────────
W_PWR = 0.5
W_SIG = 0.25
W_DATA = 0.2
W_AUDIO = 0.3

# ── Board geometry ────────────────────────────────────────────────
BOARD_W = 160.0
BOARD_H = 75.0
CX = BOARD_W / 2   # 80.0
CY = BOARD_H / 2   # 37.5


def enc(ex, ey):
    """Convert enclosure center-origin to PCB top-left origin."""
    return (CX + ex, CY - ey)


# FPC slot zone (PCB coords) — no traces may cross through this cutout
SLOT_X1, SLOT_X2 = 125.5, 128.5
SLOT_Y1, SLOT_Y2 = 23.5, 47.5


def _crosses_slot(x1, y1, x2, y2):
    """Check if a horizontal or vertical segment crosses through the slot."""
    if y1 == y2:  # horizontal
        y = y1
        if SLOT_Y1 <= y <= SLOT_Y2:
            lo, hi = min(x1, x2), max(x1, x2)
            if lo < SLOT_X1 and hi > SLOT_X2:
                return True
    elif x1 == x2:  # vertical
        x = x1
        if SLOT_X1 <= x <= SLOT_X2:
            lo, hi = min(y1, y2), max(y1, y2)
            if lo < SLOT_Y1 and hi > SLOT_Y2:
                return True
    return False


# ── Component positions (PCB coordinates) ────────────────────────
# These must match board.py definitions exactly.

ESP32 = enc(0, 10)        # (80.0, 27.5)
FPC = enc(55, 2)          # (135.0, 35.5)  — right of slot, vertical (90°)
USBC = enc(0, -34.5)      # (80.0, 72.0)
SD = enc(60, -29.5)       # (140.0, 67.0)  — bottom-right
IP5306 = enc(30, -5)      # (110.0, 42.5)  — moved left
AMS1117 = enc(45, -18)    # (125.0, 55.5)  — moved left
PAM8403 = enc(-50, 8)     # (30.0, 29.5)
L1 = enc(30, -15)         # (110.0, 52.5)  — near IP5306
JST = enc(0, -20)         # (80.0, 57.5) — synced with board.py
SPEAKER = enc(-50, -15)   # (30.0, 52.5)
PWR_SW = enc(-40, -34.5)  # (40.0, 72.0) — bottom edge, left of USB-C

# Button positions (PCB coords)
DPAD = [
    ("SW1", enc(-62, 14)),    # UP
    ("SW2", enc(-62, -4)),    # DOWN
    ("SW3", enc(-71, 5)),     # LEFT
    ("SW4", enc(-53, 5)),     # RIGHT
]
ABXY = [
    ("SW5", enc(62, 15)),     # A
    ("SW6", enc(72, 5)),      # B
    ("SW7", enc(62, -5)),     # X
    ("SW8", enc(52, 5)),      # Y
]
SS = [
    ("SW9", enc(-72, -17)),   # START
    ("SW10", enc(-52, -17)),  # SELECT
]
MENU = ("SW13", enc(62, -25))
# Shoulder buttons on B.Cu (back side, rotated 90°, aligned to top edge)
SHOULDER_L = ("SW11", enc(-65, 35))
SHOULDER_R = ("SW12", enc(65, 35))

# LED positions (F.Cu)
LED1 = enc(-55, -30)   # (25.0, 67.5) Red - charging
LED2 = enc(-48, -30)   # (32.0, 67.5) Green - full

# Passive positions (B.Cu) — synced with board.py placements
# Pull-ups at y=46, debounce at y=50, x = 43 + i*5
PULL_UP_REFS = [f"R{i}" for i in range(4, 16)] + ["R19"]
DEBOUNCE_REFS = [f"C{i}" for i in range(5, 17)] + ["C20"]

# Power passives (synced with board.py placements)
R1_POS = (74.0, 67.0)    # USB CC1 pull-down (ux-6, uy-5)
R2_POS = (86.0, 67.0)    # USB CC2 pull-down (ux+6, uy-5)
R3_POS = (65.0, 42.0)    # ESP32 decoupling
R16_POS = (115.0, 52.5)  # IP5306 KEY pull-down
R17_POS = (75.0, 42.0)   # LED1 current limit
R18_POS = (80.0, 42.0)   # LED2 current limit

C1_POS = (125.0, 50.5)   # AMS1117 input cap (amx, amy-5)
C2_POS = (125.0, 60.5)   # AMS1117 output cap (amx, amy+5)
C3_POS = (70.0, 42.0)    # ESP32 decoupling 1
C4_POS = (85.0, 42.0)    # ESP32 decoupling 2
C17_POS = (110.0, 35.0)  # IP5306 cap
C18_POS = (116.0, 37.5)  # IP5306 cap (ix+6, iy-5)
C19_POS = (110.0, 58.5)  # IP5306 bat cap (lx, ly+6)


# ── ESP32 pin positions (approximate, relative to module center) ─
# From config.py ESP_PINS: side (L/R), gpio#, y_offset
# Physical pin pitch on module: 1.27mm
# Module half-width: ~9mm, pins extend ~0.5mm beyond

ESP_HW = 9.0  # half-width

# GPIO -> (side, pin_index) where pin_index gives y position
# Left side: pins at x = ESP32[0] - ESP_HW
# Right side: pins at x = ESP32[0] + ESP_HW

# Map GPIO number to approximate PCB position (absolute)
def _esp_pin(gpio):
    """Return (x, y) PCB coordinate for an ESP32 GPIO pin."""
    ex, ey = ESP32
    # Pin position data: gpio -> (side, y_offset_from_center)
    # Derived from config.py ESP_PINS
    pin_map = {
        # Left side (x = ex - HW)
        4: ("L", -6.35), 5: ("L", -5.08), 6: ("L", -3.81), 7: ("L", -2.54),
        15: ("L", 0), 16: ("L", 1.27), 17: ("L", 2.54), 18: ("L", 3.81),
        8: ("L", 5.08), 19: ("L", 7.62), 20: ("L", 8.89), 3: ("L", 10.16),
        46: ("L", 11.43), 9: ("L", 12.7), 10: ("L", 13.97), 11: ("L", 15.24),
        # Right side (x = ex + HW)
        12: ("R", -6.35), 13: ("R", -5.08), 14: ("R", -3.81),
        21: ("R", -2.54), 47: ("R", -1.27), 48: ("R", 0),
        45: ("R", 1.27), 0: ("R", 2.54), 35: ("R", 3.81),
        36: ("R", 5.08), 37: ("R", 6.35), 38: ("R", 7.62),
        39: ("R", 8.89), 40: ("R", 10.16), 41: ("R", 11.43),
        42: ("R", 12.7), 1: ("R", 15.24), 2: ("R", 16.51),
    }
    if gpio not in pin_map:
        return (ex, ey)
    side, yoff = pin_map[gpio]
    if side == "L":
        return (ex - ESP_HW, ey + yoff)
    else:
        return (ex + ESP_HW, ey + yoff)


# ── Manhattan routing helpers ─────────────────────────────────────

def _seg(x1, y1, x2, y2, layer="B.Cu", width=W_DATA, net=0):
    """Shorthand for segment."""
    return P.segment(x1, y1, x2, y2, layer, width, net)


def _L(x1, y1, x2, y2, layer="B.Cu", width=W_DATA, net=0,
       h_first=True):
    """L-shaped Manhattan route (2 segments).

    h_first=True: horizontal first, then vertical
    h_first=False: vertical first, then horizontal
    """
    parts = []
    if h_first:
        parts.append(_seg(x1, y1, x2, y1, layer, width, net))
        parts.append(_seg(x2, y1, x2, y2, layer, width, net))
    else:
        parts.append(_seg(x1, y1, x1, y2, layer, width, net))
        parts.append(_seg(x1, y2, x2, y2, layer, width, net))
    return parts


def _via_net(x, y, net=0):
    return P.via(x, y, net=net)


# ── Routing functions ─────────────────────────────────────────────

def _power_traces():
    """Power distribution: F.Cu backbone for VBUS/BAT+, vias to inner zones.

    Inner layer power planes handle GND, +3V3, +5V distribution:
      In1.Cu = GND zone (full board)
      In2.Cu = +3V3 zone (full board) + +5V zone (100-140, 35-65)

    Short B.Cu stubs connect IC pads to nearby vias that reach the
    inner zones.  Only VBUS and BAT+ (which have no inner zone) need
    actual traces — routed on F.Cu to avoid crossing B.Cu signal routes.
    """
    parts = []
    ux, uy = USBC
    ix, iy = IP5306
    amx, amy = AMS1117
    ex, ey = ESP32
    lx, ly = L1
    jx, jy = JST
    pwx, pwy = PWR_SW
    n_vbus = NET_ID["VBUS"]
    n_5v = NET_ID["+5V"]
    n_3v3 = NET_ID["+3V3"]
    n_bat = NET_ID["BAT+"]
    n_gnd = NET_ID["GND"]

    # ── VBUS: USB-C → IP5306 (F.Cu backbone) ─────────────────────
    # B.Cu stub from USB-C pad → via
    parts.append(_seg(ux + 3, uy, ux + 3, uy - 2, "B.Cu", W_PWR, n_vbus))
    parts.append(_via_net(ux + 3, uy - 2, n_vbus))
    # F.Cu: horizontal right
    parts.append(_seg(ux + 3, uy - 2, ix - 3, uy - 2, "F.Cu", W_PWR, n_vbus))
    parts.append(_via_net(ix - 3, uy - 2, n_vbus))
    # B.Cu: vertical up to IP5306 (avoids crossing F.Cu button channels)
    parts.append(_seg(ix - 3, uy - 2, ix - 3, iy + 3, "B.Cu", W_PWR, n_vbus))

    # ── GND: vias to In1.Cu GND zone ─────────────────────────────
    gnd_vias = [
        (ux - 3, uy - 2),     # USB-C
        (ix + 3, iy + 3),     # IP5306
        (amx + 2, amy + 2),   # AMS1117
        (ex, ey + 14),        # ESP32
        (jx - 3, jy),         # JST battery
    ]
    for gvx, gvy in gnd_vias:
        parts.append(_via_net(gvx, gvy, n_gnd))
    # Short B.Cu stubs from IC GND pads to vias
    parts.append(_seg(ux - 3, uy, ux - 3, uy - 2, "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(ix + 3, iy, ix + 3, iy + 3, "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(amx + 2, amy, amx + 2, amy + 2, "B.Cu", W_PWR, n_gnd))

    # ── +5V: vias to In2.Cu +5V zone (100-140, 35-65) ────────────
    parts.append(_via_net(ix, iy - 2, n_5v))      # IP5306 output
    parts.append(_via_net(amx - 3, amy, n_5v))     # AMS1117 input
    parts.append(_via_net(lx, ly - 2, n_5v))       # L1 inductor
    # Short B.Cu stubs to +5V vias
    parts.append(_seg(ix, iy, ix, iy - 2, "B.Cu", W_PWR, n_5v))
    parts.append(_seg(amx - 3, amy - 2, amx - 3, amy, "B.Cu", W_PWR, n_5v))
    # IP5306 → L1 on B.Cu (H-V: verticals on B.Cu)
    parts.append(_seg(ix, iy + 3, ix, ly, "B.Cu", W_PWR, n_5v))

    # ── +3V3: AMS1117 output → via outside +5V zone ──────────────
    # AMS1117 at (125, 55.5) is INSIDE +5V zone, so +3V3 via must
    # be routed OUTSIDE (x<100 or y>65) via F.Cu.
    parts.append(_seg(amx, amy - 3, amx - 2, amy - 3, "B.Cu", 0.4, n_3v3))
    # B.Cu: vertical up to y=44 (H-V: verticals on B.Cu)
    parts.append(_seg(amx - 2, amy - 3, amx - 2, 44, "B.Cu", 0.4, n_3v3))
    parts.append(_via_net(amx - 2, 44, n_3v3))
    # F.Cu: horizontal left to x=98
    parts.append(_seg(amx - 2, 44, 98, 44, "F.Cu", 0.4, n_3v3))
    # Via at (98, 44) connects to In2.Cu +3V3 zone (x=98 < 100)
    parts.append(_via_net(98, 44, n_3v3))
    # ESP32 +3V3 via (outside +5V zone, clear of LCD_RST via at 90.5)
    parts.append(_via_net(ex + ESP_HW + 4, ey - 5, n_3v3))

    # ── BAT+: IP5306 → JST battery connector (F.Cu backbone) ─────
    parts.append(_seg(ix - 4, iy, ix - 4, iy + 3, "B.Cu", W_PWR, n_bat))
    parts.append(_via_net(ix - 4, iy + 3, n_bat))
    # F.Cu: horizontal left to JST x
    parts.append(_seg(ix - 4, iy + 3, jx, iy + 3, "F.Cu", W_PWR, n_bat))
    parts.append(_via_net(jx, iy + 3, n_bat))
    # B.Cu: vertical down to JST (H-V: verticals on B.Cu)
    parts.append(_seg(jx, iy + 3, jx, jy, "B.Cu", W_PWR, n_bat))

    # ── Power switch: PWR_SW → BAT+ junction (F.Cu) ──────────────
    # B.Cu: vertical up from power switch (H-V: verticals on B.Cu)
    parts.append(_seg(pwx, pwy, pwx, iy + 3, "B.Cu", W_PWR, n_bat))
    parts.append(_via_net(pwx, iy + 3, n_bat))
    # F.Cu: horizontal right to junction at jx
    parts.append(_seg(pwx, iy + 3, jx, iy + 3, "F.Cu", W_PWR, n_bat))

    # ── USB CC pull-down resistors ────────────────────────────────
    parts.append(_seg(R1_POS[0], R1_POS[1], R1_POS[0], uy - 2, "B.Cu",
                      W_SIG, n_gnd))
    parts.append(_seg(R2_POS[0], R2_POS[1], R2_POS[0], uy - 2, "B.Cu",
                      W_SIG, n_gnd))

    return parts


def _display_traces():
    """8080 display bus: ESP32 -> FPC-40P connector.

    H-V routing: F.Cu for all horizontal segments, B.Cu for all
    vertical segments, vias at each direction change.
    """
    parts = []
    fx, fy = FPC   # (135.0, 35.5)

    def _fpc_pin_y(pin):
        """Absolute Y position of FPC pin (1-indexed), J4 vertical."""
        return fy + (-9.75 + (pin - 1) * 0.5)

    def _approach_x(signal_idx):
        return 129.5 + signal_idx * 0.4

    # 8-bit data bus: GPIO 4-11 -> FPC pins 11-18 (DB0-DB7)
    data_gpios = [4, 5, 6, 7, 8, 9, 10, 11]
    for i, gpio in enumerate(data_gpios):
        net_name = f"LCD_D{i}"
        net = NET_ID[net_name]
        px, py = _esp_pin(gpio)
        pin_y = _fpc_pin_y(11 + i)
        apx = _approach_x(i)

        col_x = 58.0 + i * 1.0       # unique B.Cu vertical column
        bypass_y = 10.0 + i * 0.5     # F.Cu horizontal channel

        # B.Cu stub from ESP32 pin → via (shortened to avoid USB area)
        via_x = px - 1.5
        parts.append(_seg(px, py, via_x, py, "B.Cu", W_DATA, net))
        parts.append(_via_net(via_x, py, net))
        # F.Cu horizontal fan-out to column
        parts.append(_seg(via_x, py, col_x, py, "F.Cu", W_DATA, net))
        parts.append(_via_net(col_x, py, net))
        # B.Cu vertical column to bypass level
        parts.append(_seg(col_x, py, col_x, bypass_y, "B.Cu", W_DATA, net))
        # F.Cu horizontal bypass to approach
        parts.append(_via_net(col_x, bypass_y, net))
        parts.append(_seg(col_x, bypass_y, apx, bypass_y, "F.Cu", W_DATA,
                          net))
        parts.append(_via_net(apx, bypass_y, net))
        # B.Cu vertical approach to FPC pin level
        parts.append(_seg(apx, bypass_y, apx, pin_y, "B.Cu", W_DATA, net))
        # F.Cu horizontal to FPC
        parts.append(_via_net(apx, pin_y, net))
        parts.append(_seg(apx, pin_y, fx, pin_y, "F.Cu", W_DATA, net))

    # Control signals: GPIO -> FPC pin mapping
    ctrl = [
        (13, "LCD_RST", 6),   # RESET (R side)
        (12, "LCD_CS", 7),    # CS (R side)
        (14, "LCD_DC", 8),    # RS/DC (R side)
        (46, "LCD_WR", 9),    # WR (L side)
        (3, "LCD_RD", 10),    # RD (L side)
        (45, "LCD_BL", 3),    # Backlight anode (R side)
    ]
    right_ctrl_idx = 0
    left_ctrl_idx = 0
    for j, (gpio, net_name, fpc_pin) in enumerate(ctrl):
        net = NET_ID[net_name]
        px, py = _esp_pin(gpio)
        pin_y = _fpc_pin_y(fpc_pin)
        apx = _approach_x(8 + j)
        bypass_y = 14.5 + j * 0.5

        if px < CX:  # left side of ESP32
            col_x = 55.0 + left_ctrl_idx * 1.0
            left_ctrl_idx += 1
            via_x = px - 1.5
            parts.append(_seg(px, py, via_x, py, "B.Cu", W_DATA, net))
            parts.append(_via_net(via_x, py, net))
            parts.append(_seg(via_x, py, col_x, py, "F.Cu", W_DATA, net))
            parts.append(_via_net(col_x, py, net))
        else:  # right side
            col_x = 100.0 + right_ctrl_idx * 1.0
            right_ctrl_idx += 1
            via_x = px + 1.5
            parts.append(_seg(px, py, via_x, py, "B.Cu", W_DATA, net))
            parts.append(_via_net(via_x, py, net))
            parts.append(_seg(via_x, py, col_x, py, "F.Cu", W_DATA, net))
            parts.append(_via_net(col_x, py, net))

        # B.Cu vertical column to bypass level
        parts.append(_seg(col_x, py, col_x, bypass_y, "B.Cu", W_DATA, net))
        # F.Cu horizontal bypass to approach
        parts.append(_via_net(col_x, bypass_y, net))
        parts.append(_seg(col_x, bypass_y, apx, bypass_y, "F.Cu", W_DATA,
                          net))
        parts.append(_via_net(apx, bypass_y, net))
        # B.Cu vertical approach to FPC pin level
        parts.append(_seg(apx, bypass_y, apx, pin_y, "B.Cu", W_DATA, net))
        # F.Cu horizontal to FPC
        parts.append(_via_net(apx, pin_y, net))
        parts.append(_seg(apx, pin_y, fx, pin_y, "F.Cu", W_DATA, net))

    # Power to FPC: short stubs
    pin34_y = _fpc_pin_y(34)
    parts.append(_seg(fx, pin34_y, fx + 3, pin34_y, "F.Cu", 0.3,
                      NET_ID["+3V3"]))
    pin1_y = _fpc_pin_y(1)
    parts.append(_seg(fx, pin1_y, fx + 3, pin1_y, "F.Cu", 0.3,
                      NET_ID["GND"]))
    pin2_y = _fpc_pin_y(2)
    parts.append(_seg(fx, pin2_y, fx + 3, pin2_y, "F.Cu", 0.3,
                      NET_ID["GND"]))

    return parts


def _spi_traces():
    """SPI bus: ESP32 -> SD card slot.  H-V routing.

    SD_MOSI and SD_MISO need bypass routing to avoid the FPC approach
    zone (x≈129-135) where LCD_D4/D6 and BTN_Y traces run on F.Cu at
    similar y values.  The bypass drops to B.Cu before the conflict zone,
    runs vertically to the SD pin y level, then continues on F.Cu.
    SD_CLK and SD_CS are at y values that don't conflict, so they use
    the direct route.
    """
    parts = []
    sx, sy = SD
    spi = [
        (36, "SD_MOSI"), (37, "SD_MISO"), (38, "SD_CLK"), (39, "SD_CS"),
    ]
    for i, (gpio, net_name) in enumerate(spi):
        net = NET_ID[net_name]
        px, py = _esp_pin(gpio)
        sd_pin_x = sx - 4.4 + i * 1.1
        sd_pin_y = sy - 6.8

        # B.Cu stub RIGHT from ESP32 pin → via (avoids collinear overlap)
        stub_x = px + 2 + i * 0.5  # unique x per SPI signal
        parts.append(_seg(px, py, stub_x, py, "B.Cu", W_DATA, net))
        parts.append(_via_net(stub_x, py, net))

        # All 4 SPI signals use B.Cu vertical bypass to avoid:
        #   - FPC slot (x=125.5-128.5, y=23.5-47.5)
        #   - LCD data bus / button traces on F.Cu
        # bypass_x must also avoid:
        #   +3V3 B.Cu at x=123, +5V at x=122, C18 stub at x=116
        #   IP5306 GND stub at x=113, R16 GND stub at x=115
        bypass_cols = [120, 118, 114, 112]
        bypass_x = bypass_cols[i]
        approach_y = sd_pin_y - i  # 60.2, 59.2, 58.2, 57.2

        # F.Cu horizontal: ESP32 area to bypass column (stays left of slot)
        parts.append(_seg(stub_x, py, bypass_x, py, "F.Cu", W_DATA, net))
        parts.append(_via_net(bypass_x, py, net))
        # B.Cu vertical: bypass down to SD approach level
        parts.append(_seg(bypass_x, py, bypass_x, approach_y, "B.Cu",
                          W_DATA, net))
        parts.append(_via_net(bypass_x, approach_y, net))
        # F.Cu horizontal: approach to SD pin column (below slot y range)
        parts.append(_seg(bypass_x, approach_y, sd_pin_x, approach_y,
                          "F.Cu", W_DATA, net))
        # Short B.Cu vertical to pin if approach_y != sd_pin_y
        if abs(approach_y - sd_pin_y) > 0.01:
            parts.append(_via_net(sd_pin_x, approach_y, net))
            parts.append(_seg(sd_pin_x, approach_y, sd_pin_x,
                              sd_pin_y, "B.Cu", W_DATA, net))

    return parts


def _i2s_traces():
    """I2S audio: ESP32 -> PAM8403 -> Speaker.  H-V routing."""
    parts = []
    px, py = PAM8403
    spx, spy = SPEAKER

    i2s = [
        (15, "I2S_BCLK"), (16, "I2S_LRCK"), (17, "I2S_DOUT"),
    ]
    for i, (gpio, net_name) in enumerate(i2s):
        net = NET_ID[net_name]
        epx, epy = _esp_pin(gpio)
        pam_x = px - 4.9
        pam_y = py - 2 + i * 1.27

        # B.Cu stub from ESP32 pin → via
        parts.append(_seg(epx, epy, epx - 1.5, epy, "B.Cu", W_DATA, net))
        parts.append(_via_net(epx - 1.5, epy, net))
        # F.Cu horizontal from ESP32 to PAM8403 center
        parts.append(_seg(epx - 1.5, epy, px, epy, "F.Cu", W_DATA, net))
        parts.append(_via_net(px, epy, net))
        # B.Cu vertical from PAM center to pin level
        parts.append(_seg(px, epy, px, pam_y, "B.Cu", W_DATA, net))
        # B.Cu horizontal stub to PAM8403 pin
        parts.append(_seg(px, pam_y, pam_x, pam_y, "B.Cu", W_DATA, net))

    # Audio output: PAM8403 -> Speaker (H-V routed)
    n_spk_p = NET_ID["SPK+"]
    n_spk_m = NET_ID["SPK-"]

    # SPK+: PAM right output → speaker right terminal
    parts.append(_seg(px + 4.9, py - 1, px + 4.9, 28, "B.Cu", W_AUDIO,
                      n_spk_p))
    parts.append(_via_net(px + 4.9, 28, n_spk_p))
    parts.append(_seg(px + 4.9, 28, spx + 9.5, 28, "F.Cu", W_AUDIO,
                      n_spk_p))
    parts.append(_via_net(spx + 9.5, 28, n_spk_p))
    parts.append(_seg(spx + 9.5, 28, spx + 9.5, spy, "B.Cu", W_AUDIO,
                      n_spk_p))

    # SPK-: PAM right output → speaker left terminal
    parts.append(_seg(px + 4.9, py + 1, px + 4.9, 31.5, "B.Cu", W_AUDIO,
                      n_spk_m))
    parts.append(_via_net(px + 4.9, 31.5, n_spk_m))
    parts.append(_seg(px + 4.9, 31.5, spx - 9.5, 31.5, "F.Cu", W_AUDIO,
                      n_spk_m))
    parts.append(_via_net(spx - 9.5, 31.5, n_spk_m))
    parts.append(_seg(spx - 9.5, 31.5, spx - 9.5, spy, "B.Cu", W_AUDIO,
                      n_spk_m))

    return parts


def _usb_traces():
    """USB D+/D- differential pair: USB-C -> ESP32.  H-V routing."""
    parts = []
    ux, uy = USBC
    n_dp = NET_ID["USB_D+"]
    n_dm = NET_ID["USB_D-"]

    dp_x, dp_y = _esp_pin(20)  # (71, 36.39)
    dm_x, dm_y = _esp_pin(19)  # (71, 35.12)

    # D+: USB-C pad → B.Cu vertical → F.Cu horizontal → B.Cu vertical
    # → F.Cu stub to ESP32 pin
    # B.Cu vertical at x=75 avoids LCD stubs (x=69-71) and passives (x=73)
    parts.append(_seg(ux - 0.5, uy - 3, ux - 0.5, 67.5, "B.Cu", W_DATA,
                      n_dp))
    parts.append(_via_net(ux - 0.5, 67.5, n_dp))
    parts.append(_seg(ux - 0.5, 67.5, 75, 67.5, "F.Cu", W_DATA, n_dp))
    parts.append(_via_net(75, 67.5, n_dp))
    parts.append(_seg(75, 67.5, 75, dp_y, "B.Cu", W_DATA, n_dp))
    parts.append(_via_net(75, dp_y, n_dp))
    parts.append(_seg(75, dp_y, dp_x, dp_y, "F.Cu", W_DATA, n_dp))

    # D-: USB-C pad → B.Cu vertical → F.Cu horizontal → B.Cu vertical
    # → F.Cu stub to ESP32 pin
    # B.Cu vertical at x=76.5 avoids passives (x=73/78)
    parts.append(_seg(ux + 0.5, uy - 3, ux + 0.5, 68.5, "B.Cu", W_DATA,
                      n_dm))
    parts.append(_via_net(ux + 0.5, 68.5, n_dm))
    parts.append(_seg(ux + 0.5, 68.5, 76.5, 68.5, "F.Cu", W_DATA, n_dm))
    parts.append(_via_net(76.5, 68.5, n_dm))
    parts.append(_seg(76.5, 68.5, 76.5, dm_y, "B.Cu", W_DATA, n_dm))
    parts.append(_via_net(76.5, dm_y, n_dm))
    parts.append(_seg(76.5, dm_y, dm_x, dm_y, "F.Cu", W_DATA, n_dm))

    # USB CC pull-down resistors (R1, R2 near USB-C) — B.Cu verticals
    n_gnd = NET_ID["GND"]
    parts.append(_seg(R1_POS[0], R1_POS[1], R1_POS[0], uy - 2, "B.Cu",
                      W_SIG, n_gnd))
    parts.append(_seg(R2_POS[0], R2_POS[1], R2_POS[0], uy - 2, "B.Cu",
                      W_SIG, n_gnd))

    return parts


def _button_traces():
    """Button traces with H-V layer assignment.

    F.Cu: horizontal segments only (unique y-channel per button)
    B.Cu: vertical segments + short stubs to ESP32 pads
    Via at every H-V transition.

    Approach columns near ESP32 are ordered by epy (descending):
    highest epy gets nearest approach (x=90.5), lowest gets farthest
    (x=95.5).  This prevents B.Cu horizontal stubs from crossing
    B.Cu vertical approach columns.
    """
    parts = []

    # Button definitions: (ref, net_name, gpio)
    front_btns = [
        ("SW1", "BTN_UP", 40), ("SW2", "BTN_DOWN", 41),
        ("SW3", "BTN_LEFT", 42), ("SW4", "BTN_RIGHT", 1),
        ("SW5", "BTN_A", 2), ("SW6", "BTN_B", 48),
        ("SW7", "BTN_X", 47), ("SW8", "BTN_Y", 21),
        ("SW9", "BTN_START", 18), ("SW10", "BTN_SELECT", 0),
    ]
    all_btns = DPAD + ABXY + SS
    btn_pos = {ref: pos for ref, pos in all_btns}

    # Build button data with ESP32 pin positions
    btn_data = []
    for ref, net_name, gpio in front_btns:
        bx, by = btn_pos[ref]
        epx, epy = _esp_pin(gpio)
        btn_data.append({
            "ref": ref, "net": NET_ID[net_name],
            "bx": bx, "by": by, "epx": epx, "epy": epy,
        })

    # Separate by ESP32 pin side
    right_esp = [b for b in btn_data if b["epx"] > CX]
    left_esp = [b for b in btn_data if b["epx"] <= CX]

    # Sort right-side by epy DESCENDING (highest epy = nearest approach)
    right_esp.sort(key=lambda b: -b["epy"])

    # Assign approach columns at x=90.5+ (1mm apart avoids passive stubs)
    for i, b in enumerate(right_esp):
        b["approach_x"] = 90.5 + i * 1.0

    # Assign left-side approach columns (1mm apart, avoids passive at x=68.95)
    for i, b in enumerate(left_esp):
        b["approach_x"] = 67.5 - i * 1.0

    # Assign unique F.Cu horizontal channels (y=48.0+, 1mm apart)
    # Start at 48.0 to stay below FPC slot y range (23.5-47.5)
    all_ordered = right_esp + left_esp
    for i, b in enumerate(all_ordered):
        b["chan_y"] = 48.0 + i * 1.0

    # Assign unique via offsets to prevent overlapping B.Cu verticals
    # from buttons at the same bx
    via_x_map = {}
    for b in all_ordered:
        bx, by = b["bx"], b["by"]
        if bx < CX:
            base_vx = bx + 3  # +3 avoids I2S stubs at x=23
        else:
            base_vx = bx - 2  # -2 avoids SPI verticals at x=136-139
        # Check slot zone
        slot_margin = 0.6
        if (SLOT_X1 - slot_margin < base_vx < SLOT_X2 + slot_margin and
                SLOT_Y1 - slot_margin < by < SLOT_Y2 + slot_margin):
            base_vx = SLOT_X2 + slot_margin + 0.5
        # Ensure unique vx (offset by 1mm if collision)
        vx = base_vx
        while vx in via_x_map:
            vx += 1.0
        via_x_map[vx] = b["ref"]
        b["vx"] = vx

    # Generate traces for all front buttons
    for b in all_ordered:
        net = b["net"]
        bx, by = b["bx"], b["by"]
        epx, epy = b["epx"], b["epy"]
        vx = b["vx"]
        ax = b["approach_x"]
        cy = b["chan_y"]

        # 1. F.Cu: button pad to via
        parts.append(_seg(bx, by, vx, by, "F.Cu", W_SIG, net))
        parts.append(_via_net(vx, by, net))

        # 2. B.Cu: vertical from button via to F.Cu channel
        parts.append(_seg(vx, by, vx, cy, "B.Cu", W_SIG, net))
        parts.append(_via_net(vx, cy, net))

        # 3. F.Cu: horizontal from via column to approach column
        parts.append(_seg(vx, cy, ax, cy, "F.Cu", W_SIG, net))
        parts.append(_via_net(ax, cy, net))

        # 4. B.Cu: vertical from approach to ESP pin level
        parts.append(_seg(ax, cy, ax, epy, "B.Cu", W_SIG, net))

        # 5. F.Cu: horizontal stub to ESP32 pin (avoids B.Cu approach crossings)
        if abs(ax - epx) > 0.01:
            parts.append(_via_net(ax, epy, net))
            parts.append(_seg(ax, epy, epx, epy, "F.Cu", W_SIG, net))
            parts.append(_via_net(epx, epy, net))

    # Menu button (SW13) — SKIPPED: GPIO 39 conflict with SD_CS
    # TODO: Reassign BTN_MENU to a free GPIO in board_config.h

    # Shoulder button BTN_L only (BTN_R skipped: GPIO 19 = USB_D-)
    net_l = NET_ID["BTN_L"]
    sx_l, sy_l = SHOULDER_L[1]   # (15, 2.5)
    epx_l, epy_l = _esp_pin(35)  # (89, 31.31)
    chan_y_l = 58.0
    # Approach outside other button columns (1mm spacing)
    approach_l = 90.5 + (len(right_esp) + 1) * 1.0

    # B.Cu: vertical from button to channel level
    parts.append(_seg(sx_l, sy_l, sx_l, chan_y_l, "B.Cu", W_SIG, net_l))
    parts.append(_via_net(sx_l, chan_y_l, net_l))
    # F.Cu: horizontal from button to approach near ESP32
    parts.append(_seg(sx_l, chan_y_l, approach_l, chan_y_l, "F.Cu", W_SIG,
                      net_l))
    parts.append(_via_net(approach_l, chan_y_l, net_l))
    # B.Cu: vertical to ESP32 pin level
    parts.append(_seg(approach_l, chan_y_l, approach_l, epy_l, "B.Cu",
                      W_SIG, net_l))
    # F.Cu: horizontal to ESP32 pin
    parts.append(_via_net(approach_l, epy_l, net_l))
    parts.append(_seg(approach_l, epy_l, epx_l, epy_l, "F.Cu", W_SIG,
                      net_l))

    return parts


def _passive_traces():
    """Traces for passive components (pull-ups, debounce, decoupling).

    Power connections (+3V3, GND, +5V) use vias to inner layer zones
    instead of long horizontal traces, avoiding crossings with signal
    routes on B.Cu.
    """
    parts = []
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]
    n_5v = NET_ID["+5V"]

    # Button pull-up resistors: +3V3 via → R → button junction
    # Pull-ups at y=46, x = 43 + i*5 (synced with board.py)
    for i, ref in enumerate(PULL_UP_REFS):
        rx = 43 + i * 5
        ry = 46
        # +3V3 via directly at pull-up pad (connects to In2.Cu zone)
        parts.append(_via_net(rx - 0.95, ry, n_3v3))

    # Debounce caps: junction → C → GND via
    # Caps at y=50, x = 43 + i*5 (synced with board.py)
    for i, ref in enumerate(DEBOUNCE_REFS):
        cx = 43 + i * 5
        cy = 50
        # Left pad to GND via (opposite side from button junction)
        parts.append(_seg(cx - 0.95, cy, cx - 0.95, cy + 2, "B.Cu", W_SIG,
                          n_gnd))
        parts.append(_via_net(cx - 0.95, cy + 2, n_gnd))

    # Connect pull-up outputs to debounce cap inputs (R→C junction)
    btn_nets = [
        NET_ID["BTN_UP"], NET_ID["BTN_DOWN"],
        NET_ID["BTN_LEFT"], NET_ID["BTN_RIGHT"],
        NET_ID["BTN_A"], NET_ID["BTN_B"],
        NET_ID["BTN_X"], NET_ID["BTN_Y"],
        NET_ID["BTN_START"], NET_ID["BTN_SELECT"],
        NET_ID["BTN_L"], NET_ID["BTN_R"],
        NET_ID["BTN_MENU"],
    ]
    for i in range(len(PULL_UP_REFS)):
        x = 43 + i * 5
        net = btn_nets[i] if i < len(btn_nets) else 0
        # R bottom pad (x+0.95, 46) → C right pad (x+0.95, 50)
        # Button net on right side, GND on left side — no overlap
        parts.append(_seg(x + 0.95, 46, x + 0.95, 50, "B.Cu", W_SIG, net))

    # Decoupling caps — short stubs + vias to inner zones
    # C3 near ESP32 → +3V3 via (direct via, no stub avoids LCD/USB crossings)
    parts.append(_via_net(C3_POS[0], C3_POS[1], n_3v3))
    # C4 near ESP32 → GND via
    parts.append(_seg(C4_POS[0], C4_POS[1], C4_POS[0], C4_POS[1] - 2,
                      "B.Cu", W_SIG, n_gnd))
    parts.append(_via_net(C4_POS[0], C4_POS[1] - 2, n_gnd))

    # C1 AMS1117 input → +5V via (inside +5V zone area)
    parts.append(_seg(C1_POS[0], C1_POS[1], C1_POS[0], C1_POS[1] - 2,
                      "B.Cu", W_SIG, n_5v))
    parts.append(_via_net(C1_POS[0], C1_POS[1] - 2, n_5v))
    # C2 AMS1117 output → +3V3 (route to AMS1117 +3V3 via at amx-2)
    parts.append(_seg(C2_POS[0], C2_POS[1], AMS1117[0] - 2, C2_POS[1],
                      "B.Cu", W_SIG, n_3v3))
    parts.append(_seg(AMS1117[0] - 2, C2_POS[1], AMS1117[0] - 2,
                      AMS1117[1] - 3, "B.Cu", W_SIG, n_3v3))

    # C17 near IP5306 → +5V via
    parts.append(_seg(C17_POS[0], C17_POS[1], C17_POS[0], C17_POS[1] - 2,
                      "B.Cu", W_SIG, n_5v))
    parts.append(_via_net(C17_POS[0], C17_POS[1] - 2, n_5v))
    # C18 near IP5306 → +5V via
    parts.append(_seg(C18_POS[0], C18_POS[1], C18_POS[0], C18_POS[1] - 2,
                      "B.Cu", W_SIG, n_5v))
    parts.append(_via_net(C18_POS[0], C18_POS[1] - 2, n_5v))

    # C19 near L1 → BAT+ (short stub to L1)
    parts.append(_seg(C19_POS[0], C19_POS[1], L1[0], C19_POS[1],
                      "B.Cu", W_SIG, NET_ID["BAT+"]))

    # R16 IP5306 KEY pull-down → GND via
    parts.append(_seg(R16_POS[0], R16_POS[1], R16_POS[0], R16_POS[1] + 2,
                      "B.Cu", W_SIG, n_gnd))
    parts.append(_via_net(R16_POS[0], R16_POS[1] + 2, n_gnd))

    return parts


def _led_traces():
    """LED traces: F.Cu pads → via → inner zone connections."""
    parts = []
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]

    # Each LED: anode (+3V3 via) and cathode (GND via)
    for lx, ly in [LED1, LED2]:
        # +3V3 anode
        parts.append(_seg(lx - 1, ly, lx - 1, ly - 2, "F.Cu", W_SIG, n_3v3))
        parts.append(_via_net(lx - 1, ly - 2, n_3v3))
        # GND cathode
        parts.append(_seg(lx + 1, ly, lx + 1, ly - 2, "F.Cu", W_SIG, n_gnd))
        parts.append(_via_net(lx + 1, ly - 2, n_gnd))

    return parts


def _power_zones():
    """Copper pour zones for power distribution."""
    parts = []
    m = 0.5
    board_pts = [
        (m, m), (BOARD_W - m, m),
        (BOARD_W - m, BOARD_H - m), (m, BOARD_H - m),
    ]

    # GND zone on In1.Cu (full board)
    parts.append(P.zone_gnd("In1.Cu", board_pts))

    # +3V3 zone on In2.Cu (full board, will be split by +5V island)
    parts.append(P.zone_fill("In2.Cu", board_pts, NET_ID["+3V3"], "+3V3"))

    # +5V zone on In2.Cu (center-right area near IP5306/AMS1117)
    # Priority 1 = higher than +3V3 (priority 0) so +5V wins in overlap
    v5_pts = [
        (100, 35), (140, 35), (140, 65), (100, 65),
    ]
    parts.append(P.zone_fill("In2.Cu", v5_pts, NET_ID["+5V"], "+5V",
                             priority=1))

    return parts


# ── Main entry point ──────────────────────────────────────────────

def generate_all_traces():
    """Generate all PCB traces and zones.

    Returns a single string of KiCad S-expressions.
    """
    all_parts = []
    all_parts.extend(_power_traces())
    all_parts.extend(_display_traces())
    all_parts.extend(_spi_traces())
    all_parts.extend(_i2s_traces())
    all_parts.extend(_usb_traces())
    all_parts.extend(_button_traces())
    all_parts.extend(_passive_traces())
    all_parts.extend(_led_traces())
    all_parts.extend(_power_zones())
    return "".join(all_parts)
