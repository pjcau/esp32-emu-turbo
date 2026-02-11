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
  - J4 (FPC-40P) is right of slot at enc(55, 2)
  - IP5306/AMS1117/L1 moved left to avoid slot zone
  - L/R shoulder buttons are on F.Cu (front side)
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
FPC = enc(59, 2)          # (139.0, 35.5)  — right of slot
USBC = enc(0, -34.5)      # (80.0, 72.0)
SD = enc(60, -29.5)       # (140.0, 67.0)  — bottom-right
IP5306 = enc(30, -5)      # (110.0, 42.5)  — moved left
AMS1117 = enc(45, -18)    # (125.0, 55.5)  — moved left
PAM8403 = enc(-50, 8)     # (30.0, 29.5)
L1 = enc(30, -15)         # (110.0, 52.5)  — near IP5306
JST = enc(0, -15)         # (80.0, 52.5)
SPEAKER = enc(-50, -15)   # (30.0, 52.5)
PWR_SW = enc(-72, 15)     # (8.0, 22.5)

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
# Shoulder buttons now on F.Cu (front side)
SHOULDER_L = ("SW11", enc(-65, 35))
SHOULDER_R = ("SW12", enc(65, 35))

# LED positions (F.Cu)
LED1 = enc(-55, -30)   # (25.0, 67.5) Red - charging
LED2 = enc(-48, -30)   # (32.0, 67.5) Green - full

# Passive positions (B.Cu) — pull-ups and debounce in centered rows
# R4-R15,R19 at y=44, C5-C16,C20 at y=48, x=50..110 with 5mm pitch
PULL_UP_REFS = [f"R{i}" for i in range(4, 16)] + ["R19"]
DEBOUNCE_REFS = [f"C{i}" for i in range(5, 17)] + ["C20"]

# Power passives (updated for new IP5306/AMS1117 positions)
R1_POS = (73.0, 67.0)    # USB CC1 pull-down
R2_POS = (87.0, 67.0)    # USB CC2 pull-down
R3_POS = (110.0, 37.0)   # IP5306 decoupling (near new IP5306)
R16_POS = (115.0, 52.5)  # IP5306 KEY pull-down (near new L1)
R17_POS = (25.0, 64.0)   # LED1 current limit
R18_POS = (32.0, 64.0)   # LED2 current limit

C1_POS = (110.0, 38.0)   # IP5306 input cap (near new IP5306)
C2_POS = (115.0, 38.0)   # IP5306 output cap (22uF)
C3_POS = (80.0, 18.0)    # ESP32 decoupling 1
C4_POS = (85.0, 18.0)    # ESP32 decoupling 2
C17_POS = (125.0, 50.0)  # AMS1117 input cap (near new AMS1117)
C18_POS = (125.0, 60.0)  # AMS1117 output cap
C19_POS = (110.0, 57.0)  # IP5306 bat cap (22uF, near L1)


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
    """Power distribution: USB-C -> IP5306 -> AMS1117 -> ESP32."""
    parts = []
    ux, uy = USBC
    ix, iy = IP5306
    amx, amy = AMS1117
    ex, ey = ESP32
    lx, ly = L1
    jx, jy = JST
    n_vbus = NET_ID["VBUS"]
    n_5v = NET_ID["+5V"]
    n_3v3 = NET_ID["+3V3"]
    n_bat = NET_ID["BAT+"]
    n_gnd = NET_ID["GND"]

    # VBUS: USB-C -> IP5306 (L-shape: right then up)
    mid_y = iy + 5
    parts.append(_seg(ux + 3, uy, ux + 3, mid_y, "B.Cu", W_PWR, n_vbus))
    parts.append(_seg(ux + 3, mid_y, ix - 3, mid_y, "B.Cu", W_PWR, n_vbus))
    parts.append(_seg(ix - 3, mid_y, ix - 3, iy + 3, "B.Cu", W_PWR, n_vbus))

    # GND return: USB-C -> IP5306
    parts.append(_seg(ux - 3, uy, ux - 3, mid_y + 2, "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(ux - 3, mid_y + 2, ix + 3, mid_y + 2, "B.Cu", W_PWR,
                      n_gnd))
    parts.append(_seg(ix + 3, mid_y + 2, ix + 3, iy + 3, "B.Cu", W_PWR,
                      n_gnd))

    # 5V: IP5306 -> L1 (vertical, both near x=110)
    parts.append(_seg(ix, iy + 3, ix, ly, "B.Cu", W_PWR, n_5v))
    parts.append(_seg(ix, ly, lx, ly, "B.Cu", W_PWR, n_5v))

    # 5V: IP5306 -> AMS1117 (L-shape: right then down)
    parts.append(_seg(ix + 3, iy, ix + 3, amy, "B.Cu", W_PWR, n_5v))
    parts.append(_seg(ix + 3, amy, amx - 3, amy, "B.Cu", W_PWR, n_5v))

    # GND: IP5306 -> AMS1117
    parts.append(_seg(ix + 5, iy, ix + 5, amy + 2, "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(ix + 5, amy + 2, amx - 3, amy + 2, "B.Cu", W_PWR,
                      n_gnd))

    # 3V3: AMS1117 -> ESP32 (route left of FPC slot for clearance)
    v3_x = amx - 2  # 123.0 — safe clearance from slot left edge at 125.5
    parts.append(_seg(amx, amy - 3, v3_x, amy - 3, "B.Cu", 0.4, n_3v3))
    parts.append(_seg(v3_x, amy - 3, v3_x, ey - 5, "B.Cu", 0.4, n_3v3))
    parts.append(_seg(v3_x, ey - 5, ex + ESP_HW + 2, ey - 5, "B.Cu", 0.4,
                      n_3v3))

    # BAT+: IP5306 -> JST (L-shape: left then down)
    parts.append(_seg(ix - 4, iy + 3, ix - 4, jy, "B.Cu", W_PWR, n_bat))
    parts.append(_seg(ix - 4, jy, jx + 2, jy, "B.Cu", W_PWR, n_bat))

    # BAT GND: IP5306 -> JST
    parts.append(_seg(ix - 6, iy + 3, ix - 6, jy + 2, "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(ix - 6, jy + 2, jx - 2, jy + 2, "B.Cu", W_PWR, n_gnd))

    # Power switch: BAT+ rail connection
    pwx, pwy = PWR_SW
    parts.append(_seg(pwx, pwy, pwx, jy - 5, "B.Cu", W_PWR, n_bat))
    parts.append(_seg(pwx, jy - 5, jx - 5, jy - 5, "B.Cu", W_PWR, n_bat))

    return parts


def _display_traces():
    """8080 display bus: ESP32 -> FPC-40P connector (ILI9488 40-pin pinout).

    ILI9488 40-pin FPC pinout (typical):
      Pin 1: GND, Pin 2: LEDK (GND), Pin 3: LEDA (+3V3 backlight)
      Pin 6: RESET, Pin 7: CS, Pin 8: RS/DC, Pin 9: WR, Pin 10: RD
      Pins 11-18: DB0-DB7 (8-bit data bus)
      Pins 34-35: VCC (+3V3), Pins 27-28,32-33,40: GND

    FPC-40P connector: 40 pins at 0.5mm pitch, centered at J4 position.
    Pin 1 at relative x = -9.75, pin 40 at x = +9.75.
    """
    parts = []
    fx, fy = FPC

    def _fpc_pin_x(pin):
        """Absolute X position of FPC pin (1-indexed)."""
        return fx - 9.75 + (pin - 1) * 0.5

    # 8-bit data bus: GPIO 4-11 -> FPC pins 11-18 (DB0-DB7)
    # Route ABOVE the FPC slot: ESP32 -> column -> up to bypass -> right -> down to FPC
    data_gpios = [4, 5, 6, 7, 8, 9, 10, 11]
    for i, gpio in enumerate(data_gpios):
        net_name = f"LCD_D{i}"
        net = NET_ID[net_name]
        px, py = _esp_pin(gpio)
        fpc_x = _fpc_pin_x(11 + i)

        col_x = 58.0 + i * 1.0       # unique vertical column (58-65)
        bypass_y = 10.0 + i * 0.5     # horizontal channel above slot (10-13.5)

        parts.append(_seg(px, py, col_x, py, "B.Cu", W_DATA, net))
        parts.append(_seg(col_x, py, col_x, bypass_y, "B.Cu", W_DATA, net))
        parts.append(_seg(col_x, bypass_y, fpc_x, bypass_y, "B.Cu", W_DATA, net))
        parts.append(_seg(fpc_x, bypass_y, fpc_x, fy, "B.Cu", W_DATA, net))

    # Control signals: GPIO -> FPC pin mapping per ILI9488 pinout
    # Route above slot, using columns right of data bus columns
    ctrl = [
        (13, "LCD_RST", 6),   # RESET (R side)
        (12, "LCD_CS", 7),    # CS (R side)
        (14, "LCD_DC", 8),    # RS/DC (R side)
        (46, "LCD_WR", 9),    # WR (L side)
        (3, "LCD_RD", 10),    # RD (L side)
        (45, "LCD_BL", 3),    # Backlight anode (R side)
    ]
    for j, (gpio, net_name, fpc_pin) in enumerate(ctrl):
        net = NET_ID[net_name]
        px, py = _esp_pin(gpio)
        fpc_x = _fpc_pin_x(fpc_pin)

        bypass_y = 14.5 + j * 0.5     # after data bus channel (14.5-17.0)
        if px < CX:  # left side of ESP32
            col_x = 67.0 + j * 1.0
        else:  # right side of ESP32
            col_x = px + 2 + j * 0.5

        parts.append(_seg(px, py, col_x, py, "B.Cu", W_DATA, net))
        parts.append(_seg(col_x, py, col_x, bypass_y, "B.Cu", W_DATA, net))
        parts.append(_seg(col_x, bypass_y, fpc_x, bypass_y, "B.Cu", W_DATA, net))
        parts.append(_seg(fpc_x, bypass_y, fpc_x, fy, "B.Cu", W_DATA, net))

    # Power to FPC: +3V3 on pins 34-35 (VCC) and GND on pin 1
    fpc_vcc_x = _fpc_pin_x(34)
    fpc_gnd_x = _fpc_pin_x(1)
    parts.append(_seg(fpc_vcc_x, fy, fpc_vcc_x, fy + 3, "B.Cu", 0.3,
                      NET_ID["+3V3"]))
    parts.append(_seg(fpc_gnd_x, fy, fpc_gnd_x, fy + 3, "B.Cu", 0.3,
                      NET_ID["GND"]))
    # LEDK (pin 2) to GND
    fpc_ledk_x = _fpc_pin_x(2)
    parts.append(_seg(fpc_ledk_x, fy, fpc_ledk_x, fy + 3, "B.Cu", 0.3,
                      NET_ID["GND"]))

    return parts


def _spi_traces():
    """SPI bus: ESP32 -> SD card slot."""
    parts = []
    sx, sy = SD
    spi = [
        (36, "SD_MOSI"), (37, "SD_MISO"), (38, "SD_CLK"), (39, "SD_CS"),
    ]
    for i, (gpio, net_name) in enumerate(spi):
        net = NET_ID[net_name]
        px, py = _esp_pin(gpio)
        # SD card signal pin offset (1.1mm pitch)
        sd_pin_x = sx - 4.4 + i * 1.1
        sd_pin_y = sy - 6.8

        # Route BELOW the FPC slot: ESP32 right -> down past slot -> right to SD
        bypass_y = SLOT_Y2 + 2.0 + i * 0.5   # 49.5, 50.0, 50.5, 51.0
        col_x = px + 3 + i * 1.0              # fan-out columns (92-95)
        parts.append(_seg(px, py, col_x, py, "B.Cu", W_DATA, net))
        parts.append(_seg(col_x, py, col_x, bypass_y, "B.Cu", W_DATA, net))
        parts.append(_seg(col_x, bypass_y, sd_pin_x, bypass_y, "B.Cu",
                          W_DATA, net))
        parts.append(_seg(sd_pin_x, bypass_y, sd_pin_x, sd_pin_y, "B.Cu",
                          W_DATA, net))

    return parts


def _i2s_traces():
    """I2S audio: ESP32 -> PAM8403 -> Speaker."""
    parts = []
    px, py = PAM8403
    spx, spy = SPEAKER

    i2s = [
        (15, "I2S_BCLK"), (16, "I2S_LRCK"), (17, "I2S_DOUT"),
    ]
    for i, (gpio, net_name) in enumerate(i2s):
        net = NET_ID[net_name]
        epx, epy = _esp_pin(gpio)
        # PAM8403 left-side pin (input pins 5-7 area)
        pam_x = px - 4.9
        pam_y = py - 2 + i * 1.27

        # Manhattan: horizontal left from ESP32, then vertical to PAM
        parts.append(_seg(epx, epy, epx - 3, epy, "B.Cu", W_DATA, net))
        parts.append(_seg(epx - 3, epy, pam_x - 2, epy, "B.Cu", W_DATA, net))
        parts.append(_seg(pam_x - 2, epy, pam_x - 2, pam_y, "B.Cu", W_DATA,
                          net))
        parts.append(_seg(pam_x - 2, pam_y, pam_x, pam_y, "B.Cu", W_DATA,
                          net))

    # Audio output: PAM8403 right-side -> Speaker
    n_spk_p = NET_ID["SPK+"]
    n_spk_m = NET_ID["SPK-"]
    parts.append(_seg(px + 4.9, py - 1, spx + 9.5, py - 1, "B.Cu", W_AUDIO,
                      n_spk_p))
    parts.append(_seg(spx + 9.5, py - 1, spx + 9.5, spy, "B.Cu", W_AUDIO,
                      n_spk_p))
    parts.append(_seg(px + 4.9, py + 1, spx - 9.5, py + 1, "B.Cu", W_AUDIO,
                      n_spk_m))
    parts.append(_seg(spx - 9.5, py + 1, spx - 9.5, spy, "B.Cu", W_AUDIO,
                      n_spk_m))

    return parts


def _usb_traces():
    """USB D+/D- differential pair: USB-C -> ESP32."""
    parts = []
    ux, uy = USBC
    n_dp = NET_ID["USB_D+"]
    n_dm = NET_ID["USB_D-"]

    # ESP32 USB pins (GPIO 19 D-, GPIO 20 D+)
    dp_x, dp_y = _esp_pin(20)
    dm_x, dm_y = _esp_pin(19)

    # Route from USB-C up to ESP32 left side
    # Keep D+ and D- parallel with 0.15mm gap
    mid_y = ey_mid = (uy + dp_y) / 2

    # D+ trace (left of center)
    parts.append(_seg(ux - 0.5, uy - 3, ux - 0.5, mid_y, "B.Cu", W_DATA,
                      n_dp))
    parts.append(_seg(ux - 0.5, mid_y, dp_x - 2, mid_y, "B.Cu", W_DATA,
                      n_dp))
    parts.append(_seg(dp_x - 2, mid_y, dp_x - 2, dp_y, "B.Cu", W_DATA,
                      n_dp))
    parts.append(_seg(dp_x - 2, dp_y, dp_x, dp_y, "B.Cu", W_DATA, n_dp))

    # D- trace (right of center)
    parts.append(_seg(ux + 0.5, uy - 3, ux + 0.5, mid_y + 0.5, "B.Cu",
                      W_DATA, n_dm))
    parts.append(_seg(ux + 0.5, mid_y + 0.5, dm_x - 2.5, mid_y + 0.5,
                      "B.Cu", W_DATA, n_dm))
    parts.append(_seg(dm_x - 2.5, mid_y + 0.5, dm_x - 2.5, dm_y, "B.Cu",
                      W_DATA, n_dm))
    parts.append(_seg(dm_x - 2.5, dm_y, dm_x, dm_y, "B.Cu", W_DATA, n_dm))

    # USB CC pull-down resistors (R1, R2 near USB-C)
    n_gnd = NET_ID["GND"]
    # R1: CC1 to GND
    parts.append(_seg(R1_POS[0], R1_POS[1], R1_POS[0], uy - 2, "B.Cu",
                      W_SIG, n_gnd))
    # R2: CC2 to GND
    parts.append(_seg(R2_POS[0], R2_POS[1], R2_POS[0], uy - 2, "B.Cu",
                      W_SIG, n_gnd))

    return parts


def _button_traces():
    """Button traces: F.Cu pad -> via -> B.Cu -> ESP32 GPIO."""
    parts = []

    # Button -> (net_name, gpio)
    btn_map = [
        # D-pad
        ("SW1", "BTN_UP", 40), ("SW2", "BTN_DOWN", 41),
        ("SW3", "BTN_LEFT", 42), ("SW4", "BTN_RIGHT", 1),
        # ABXY
        ("SW5", "BTN_A", 2), ("SW6", "BTN_B", 48),
        ("SW7", "BTN_X", 47), ("SW8", "BTN_Y", 21),
        # Start/Select
        ("SW9", "BTN_START", 18), ("SW10", "BTN_SELECT", 0),
    ]

    # Front-side buttons: short F.Cu trace -> via -> B.Cu trace -> ESP32
    all_btns = DPAD + ABXY + SS
    btn_positions = {ref: pos for ref, pos in all_btns}

    crossing_idx = 0
    for ref, net_name, gpio in btn_map:
        net = NET_ID[net_name]
        bx, by = btn_positions[ref]
        epx, epy = _esp_pin(gpio)

        # Via position: offset toward ESP32 side
        if bx < CX:  # left-side button, via goes right
            vx, vy = bx + 4, by
        else:  # right-side button, via goes left
            vx, vy = bx - 4, by

        # Ensure via is not inside FPC slot zone
        slot_margin = 0.6  # via radius + clearance
        if (SLOT_X1 - slot_margin < vx < SLOT_X2 + slot_margin and
                SLOT_Y1 - slot_margin < vy < SLOT_Y2 + slot_margin):
            vx = SLOT_X2 + slot_margin + 0.5  # push right of slot

        # F.Cu: button pad to via
        parts.append(_seg(bx, by, vx, vy, "F.Cu", W_SIG, net))
        parts.append(_via_net(vx, vy, net))

        # Check if B.Cu L-route would cross through the FPC slot
        h_would_cross = (SLOT_Y1 <= vy <= SLOT_Y2 and
                         min(vx, epx) < SLOT_X1 and
                         max(vx, epx) > SLOT_X2)

        if h_would_cross:
            # Z-route above slot: via -> up -> left past slot -> down to ESP
            bypass_y = 7.0 - crossing_idx * 1.0   # 7, 6, 5 (above all)
            approach_x = 53.0 - crossing_idx * 1.5  # 53, 51.5, 50
            crossing_idx += 1
            parts.append(_seg(vx, vy, vx, bypass_y,
                              "B.Cu", W_SIG, net))
            parts.append(_seg(vx, bypass_y, approach_x, bypass_y,
                              "B.Cu", W_SIG, net))
            parts.append(_seg(approach_x, bypass_y, approach_x, epy,
                              "B.Cu", W_SIG, net))
            parts.append(_seg(approach_x, epy, epx, epy,
                              "B.Cu", W_SIG, net))
        else:
            # Normal L-shape route
            parts.extend(_L(vx, vy, epx, epy, "B.Cu", W_SIG, net,
                            h_first=(abs(vx - epx) > abs(vy - epy))))

    # Menu button (SW13)
    net_menu = NET_ID["BTN_MENU"]
    mx, my = MENU[1]
    mvx, mvy = mx, my - 4
    parts.append(_seg(mx, my, mvx, mvy, "F.Cu", W_SIG, net_menu))
    parts.append(_via_net(mvx, mvy, net_menu))
    # Route to nearest ESP32 GPIO (could use GPIO44 or another free pin)
    parts.extend(_L(mvx, mvy, ESP32[0] + ESP_HW, ESP32[1] + 5,
                    "B.Cu", W_SIG, net_menu, h_first=True))

    # Shoulder buttons (now on F.Cu — same pattern as face buttons)
    shoulder_map = [
        ("SW11", "BTN_L", 35), ("SW12", "BTN_R", 19),
    ]
    shoulder_positions = {
        "SW11": SHOULDER_L[1], "SW12": SHOULDER_R[1],
    }
    for ref, net_name, gpio in shoulder_map:
        net = NET_ID[net_name]
        sx, sy = shoulder_positions[ref]
        epx, epy = _esp_pin(gpio)

        # Via position: offset toward ESP32 side
        if sx < CX:
            vx, vy = sx + 4, sy
        else:
            vx, vy = sx - 4, sy

        # F.Cu: button pad to via
        parts.append(_seg(sx, sy, vx, vy, "F.Cu", W_SIG, net))
        parts.append(_via_net(vx, vy, net))

        # B.Cu: route avoiding FPC slot.
        # SW11 (left): v_first — vertical at x=via, then horizontal.
        # SW12 (right): h_first at y=2.5 (above slot), then vertical.
        if ref == "SW11":
            # v_first: vertical far left, then horizontal (no slot crossing)
            parts.extend(_L(vx, vy, epx, epy, "B.Cu", W_SIG, net,
                            h_first=False))
        else:
            # h_first: horizontal at y≈2.5 (above slot top at 23.5)
            parts.extend(_L(vx, vy, epx, epy, "B.Cu", W_SIG, net,
                            h_first=True))

    return parts


def _passive_traces():
    """Traces for passive components (pull-ups, debounce, decoupling)."""
    parts = []
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]

    # Button pull-up resistors: +3V3 -> R -> button junction
    # Pull-ups are at y=44, x=50..110 with 5mm pitch (B.Cu)
    # They connect to +3V3 on one side and button GPIO on the other
    # The +3V3 rail runs horizontally above the resistor row
    parts.append(_seg(48, 42, 112, 42, "B.Cu", 0.3, n_3v3))  # 3V3 rail

    for i, ref in enumerate(PULL_UP_REFS):
        rx = 50 + i * 5
        ry = 44
        # Top pad to +3V3 rail
        parts.append(_seg(rx - 0.95, ry, rx - 0.95, 42, "B.Cu", W_SIG,
                          n_3v3))

    # Debounce caps: junction -> C -> GND
    # Caps are at y=48, GND rail runs below at y=50
    parts.append(_seg(48, 50, 112, 50, "B.Cu", 0.3, n_gnd))  # GND rail

    for i, ref in enumerate(DEBOUNCE_REFS):
        cx = 50 + i * 5
        cy = 48
        # Bottom pad to GND rail
        parts.append(_seg(cx + 0.95, cy, cx + 0.95, 50, "B.Cu", W_SIG,
                          n_gnd))

    # Connect pull-up outputs to debounce cap inputs (vertical)
    for i in range(len(PULL_UP_REFS)):
        x = 50 + i * 5
        parts.append(_seg(x + 0.95, 44, x - 0.95, 48, "B.Cu", W_SIG, 0))

    # Decoupling caps near ICs
    # C3, C4 near ESP32
    parts.append(_seg(C3_POS[0], C3_POS[1], C3_POS[0], ESP32[1] - 5,
                      "B.Cu", W_SIG, n_3v3))
    parts.append(_seg(C4_POS[0], C4_POS[1], C4_POS[0], ESP32[1] - 5,
                      "B.Cu", W_SIG, n_gnd))

    # C1 near IP5306 input (new position)
    parts.append(_seg(C1_POS[0], C1_POS[1], IP5306[0], C1_POS[1],
                      "B.Cu", W_SIG, n_3v3))
    # C2 near IP5306 output
    parts.append(_seg(C2_POS[0], C2_POS[1], IP5306[0] + 3, C2_POS[1],
                      "B.Cu", W_SIG, NET_ID["+5V"]))

    # C17, C18 near AMS1117 (new position)
    parts.append(_seg(C17_POS[0], C17_POS[1], AMS1117[0], C17_POS[1],
                      "B.Cu", W_SIG, NET_ID["+5V"]))
    parts.append(_seg(C18_POS[0], C18_POS[1], AMS1117[0], C18_POS[1],
                      "B.Cu", W_SIG, n_3v3))

    # C19 near L1 / IP5306 bat cap
    parts.append(_seg(C19_POS[0], C19_POS[1], L1[0], C19_POS[1],
                      "B.Cu", W_SIG, NET_ID["BAT+"]))

    # R16 IP5306 KEY pull-down
    parts.append(_seg(R16_POS[0], R16_POS[1], R16_POS[0], L1[1],
                      "B.Cu", W_SIG, n_gnd))

    return parts


def _led_traces():
    """LED traces: F.Cu pads -> via -> B.Cu power."""
    parts = []
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]

    # LED1 (Red, charging) at (25, 67.5)
    lx1, ly1 = LED1
    # Via for 3V3 connection
    parts.append(_seg(lx1 - 1, ly1, lx1 - 1, ly1 - 2, "F.Cu", W_SIG, n_3v3))
    parts.append(_via_net(lx1 - 1, ly1 - 2, n_3v3))
    # R17 connects on B.Cu
    parts.append(_seg(lx1 - 1, ly1 - 2, R17_POS[0], R17_POS[1],
                      "B.Cu", W_SIG, n_3v3))
    # GND via
    parts.append(_seg(lx1 + 1, ly1, lx1 + 1, ly1 - 2, "F.Cu", W_SIG, n_gnd))
    parts.append(_via_net(lx1 + 1, ly1 - 2, n_gnd))

    # LED2 (Green, full) at (32, 67.5)
    lx2, ly2 = LED2
    parts.append(_seg(lx2 - 1, ly2, lx2 - 1, ly2 - 2, "F.Cu", W_SIG, n_3v3))
    parts.append(_via_net(lx2 - 1, ly2 - 2, n_3v3))
    parts.append(_seg(lx2 - 1, ly2 - 2, R18_POS[0], R18_POS[1],
                      "B.Cu", W_SIG, n_3v3))
    parts.append(_seg(lx2 + 1, ly2, lx2 + 1, ly2 - 2, "F.Cu", W_SIG, n_gnd))
    parts.append(_via_net(lx2 + 1, ly2 - 2, n_gnd))

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
    v5_pts = [
        (100, 35), (140, 35), (140, 65), (100, 65),
    ]
    parts.append(P.zone_fill("In2.Cu", v5_pts, NET_ID["+5V"], "+5V"))

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
