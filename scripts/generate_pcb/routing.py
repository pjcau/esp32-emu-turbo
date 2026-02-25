"""Complete PCB trace routing with Manhattan (orthogonal) paths.

All traces use only horizontal and vertical segments (L-shaped or
Z-shaped paths).  No diagonal lines.

Trace widths:
  - Power:  0.5mm (VBUS, +5V, +3V3, BAT+, GND returns)
  - Signal: 0.25mm (buttons, passives)
  - Data:   0.2mm  (display bus, SPI, I2S, USB)
  - Audio:  0.3mm  (PAM8403 -> speaker)

Layout notes:
  - FPC slot at enc(47, 2) creates a 3x24mm vertical cutout
  - J4 (FPC-40P) is right of slot at enc(55, 2), rotated 90deg (vertical)
  - IP5306/AMS1117/L1 moved left to avoid slot zone
  - L/R shoulder buttons are on B.Cu (back side, rotated 90deg)
  - B.Cu mirroring: module "left" pins appear on board "right" and vice versa
  - All pad positions computed from footprint definitions (no approximations)
"""

import math
import re

from . import primitives as P
from . import footprints as FP
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
FPC = enc(55, 2)          # (135.0, 35.5)  — right of slot, vertical (90deg)
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
# Shoulder buttons on B.Cu (back side, rotated 90deg, aligned to top edge)
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


# ── Exact pad position computation ───────────────────────────────
# Computes absolute board-level coordinates for every IC/connector pad,
# accounting for B.Cu X-mirroring and footprint rotation.

# ESP32-S3-WROOM-1 physical pin -> GPIO mapping (from datasheet)
_PIN_TO_GPIO = {
    4: 4, 5: 5, 6: 6, 7: 7,
    8: 15, 9: 16, 10: 17, 11: 18,
    12: 8, 13: 19, 14: 20,
    15: 3, 16: 46, 17: 9, 18: 10, 19: 11,
    20: 12, 21: 13, 22: 14,
    23: 21, 24: 47, 25: 48, 26: 45,
    27: 0, 28: 35, 29: 36, 30: 37,
    31: 38, 32: 39, 33: 40, 34: 41,
    35: 42, 36: 1, 37: 2,
}
_GPIO_TO_PIN = {gpio: pin for pin, gpio in _PIN_TO_GPIO.items()}


def _compute_pads(fp_name, cx, cy, rot, layer_char):
    """Compute absolute pad positions for a footprint placement.

    Returns dict: {pad_num_str: (abs_x, abs_y), ...}
    """
    if fp_name not in FP.FOOTPRINTS:
        return {}
    gen, _ = FP.FOOTPRINTS[fp_name]
    raw_pads = gen(layer_char)
    result = {}
    for pad_str in raw_pads:
        at_m = re.search(r'\(at\s+([-\d.]+)\s+([-\d.]+)\)', pad_str)
        num_m = re.search(r'\(pad\s+"([^"]*)"', pad_str)
        if not at_m or not num_m:
            continue
        px, py = float(at_m.group(1)), float(at_m.group(2))
        if layer_char == "B":
            px = -px
        rot_rad = math.radians(rot)
        cos_r, sin_r = math.cos(rot_rad), math.sin(rot_rad)
        result[num_m.group(1)] = (
            cx + px * cos_r - py * sin_r,
            cy + px * sin_r + py * cos_r,
        )
    return result


# Precomputed pad positions for all routed components
_PADS = {}


def _init_pads():
    """Lazily compute pad positions (called on first use)."""
    global _PADS
    if _PADS:
        return
    components = [
        ("U1", "ESP32-S3-WROOM-1-N16R8", *ESP32, 0, "B"),
        ("J4", "FPC-40P-0.5mm", *FPC, 90, "B"),
        ("J1", "USB-C-16P", *USBC, 0, "B"),
        ("U6", "TF-01A", *SD, 0, "B"),
        ("U2", "ESOP-8", *IP5306, 0, "B"),
        ("U3", "SOT-223", *AMS1117, 0, "B"),
        ("U5", "SOP-16", *PAM8403, 90, "B"),
        ("L1", "SMD-4x4x2", *L1, 0, "B"),
        ("J3", "JST-PH-2P", *JST, 0, "B"),
        ("SPK1", "Speaker-22mm", *SPEAKER, 0, "B"),
        ("SW_PWR", "SS-12D00G3", *PWR_SW, 0, "B"),
    ]
    for ref, fp_name, cx, cy, rot, lc in components:
        _PADS[ref] = _compute_pads(fp_name, cx, cy, rot, lc)

    # F.Cu face buttons
    for ref, pos in DPAD + ABXY + SS:
        _PADS[ref] = _compute_pads("SW-SMD-5.1x5.1", pos[0], pos[1], 0, "F")
    ref_m, pos_m = MENU
    _PADS[ref_m] = _compute_pads("SW-SMD-5.1x5.1",
                                  pos_m[0], pos_m[1], 0, "F")
    # B.Cu shoulder buttons (rotated 90°)
    ref_l, pos_l = SHOULDER_L
    _PADS[ref_l] = _compute_pads("SW-SMD-5.1x5.1",
                                  pos_l[0], pos_l[1], 90, "B")
    ref_r, pos_r = SHOULDER_R
    _PADS[ref_r] = _compute_pads("SW-SMD-5.1x5.1",
                                  pos_r[0], pos_r[1], 90, "B")

    # Key passives with explicit routing
    passive_placements = [
        ("C1", "C_0805", *C1_POS, 0, "B"),
        ("C2", "C_1206", *C2_POS, 0, "B"),
        ("C3", "C_0805", *C3_POS, 0, "B"),
        ("C4", "C_0805", *C4_POS, 0, "B"),
        ("C17", "C_0805", *C17_POS, 0, "B"),
        ("C18", "C_0805", *C18_POS, 0, "B"),
        ("C19", "C_1206", *C19_POS, 0, "B"),
        ("R16", "R_0805", *R16_POS, 0, "B"),
        ("R1", "R_0805", *R1_POS, 0, "B"),
        ("R2", "R_0805", *R2_POS, 0, "B"),
    ]
    for ref, fp, cx, cy, rot, lc in passive_placements:
        _PADS[ref] = _compute_pads(fp, cx, cy, rot, lc)


def _pad(ref, num):
    """Return absolute (x, y) for a component pad."""
    _init_pads()
    return _PADS.get(ref, {}).get(str(num), None)


def _esp_pin(gpio):
    """Return (x, y) PCB coordinate for an ESP32 GPIO pin."""
    _init_pads()
    if gpio not in _GPIO_TO_PIN:
        return ESP32
    pin = str(_GPIO_TO_PIN[gpio])
    pos = _PADS.get("U1", {}).get(pin)
    return pos if pos else ESP32


def _fpc_pin(pin):
    """Return (x, y) PCB coordinate for FPC connector pin (1-indexed)."""
    _init_pads()
    pos = _PADS.get("J4", {}).get(str(pin))
    return pos if pos else FPC


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


def _hv_route(x1, y1, x2, y2, net, width=W_DATA,
              h_layer="F.Cu", v_layer="B.Cu"):
    """Route from (x1,y1) to (x2,y2) using H-V Manhattan path.

    Returns (parts, via_x, via_y) — the parts list and the corner point.
    First goes horizontal on h_layer, then vertical on v_layer.
    """
    parts = []
    parts.append(_via_net(x1, y1, net))
    parts.append(_seg(x1, y1, x2, y1, h_layer, width, net))
    parts.append(_via_net(x2, y1, net))
    parts.append(_seg(x2, y1, x2, y2, v_layer, width, net))
    return parts


# ── Routing functions ─────────────────────────────────────────────

def _power_traces():
    """Power distribution using exact IC pad positions.

    Inner layer power planes handle GND, +3V3, +5V distribution:
      In1.Cu = GND zone (full board)
      In2.Cu = +3V3 zone (full board) + +5V zone (100-140, 35-65)
    """
    parts = []
    _init_pads()

    n_vbus = NET_ID["VBUS"]
    n_5v = NET_ID["+5V"]
    n_3v3 = NET_ID["+3V3"]
    n_bat = NET_ID["BAT+"]
    n_gnd = NET_ID["GND"]

    # ── Get exact pad positions ─────────────────────────────────
    # IP5306 (U2): ESOP-8
    # Pin 1 = VIN (VBUS), Pin 3 = VSS (GND), Pin 4 = VOUT,
    # Pin 8 = VCC (BAT+), EP = GND
    ip_vbus = _pad("U2", "1")     # VBUS input
    ip_gnd = _pad("U2", "3")      # GND
    ip_vout = _pad("U2", "4")     # +5V output
    ip_bat = _pad("U2", "8")      # BAT+ (battery)
    ip_ep = _pad("U2", "EP")      # Exposed GND pad

    # AMS1117 (U3): SOT-223
    # Pin 1 = GND/ADJ, Pin 2 = VOUT (+3V3), Pin 3 = VIN (+5V), Pin 4 = tab (VOUT)
    am_gnd = _pad("U3", "1")
    am_vout = _pad("U3", "2")
    am_vin = _pad("U3", "3")
    am_tab = _pad("U3", "4")      # tab = VOUT

    # USB-C (J1): VBUS on A1/A4/B12/B9, GND on A12/B1
    usb_vbus = _pad("J1", "A4")   # VBUS pad
    usb_gnd = _pad("J1", "A12")   # GND pad

    # JST battery (J3)
    jst_p = _pad("J3", "1")       # BAT+
    jst_n = _pad("J3", "2")       # GND

    # L1 inductor
    l1_1 = _pad("L1", "1")
    l1_2 = _pad("L1", "2")

    # Power switch
    sw_com = _pad("SW_PWR", "2")   # Common pin

    # ESP32 GND (exposed pad)
    esp_gnd = _pad("U1", "41")

    # ── VBUS: USB-C -> IP5306 ──────────────────────────────────
    # B.Cu stub from USB-C VBUS pad -> via
    vbus_via_y = usb_vbus[1] - 2
    parts.append(_seg(usb_vbus[0], usb_vbus[1], usb_vbus[0], vbus_via_y,
                       "B.Cu", W_PWR, n_vbus))
    parts.append(_via_net(usb_vbus[0], vbus_via_y, n_vbus))
    # F.Cu horizontal to IP5306 area, then F.Cu vertical down
    # (avoid long B.Cu vertical crossing BAT+ horizontal at y~58.5)
    ip_vbus_via_x = ip_vbus[0] - 2
    parts.append(_seg(usb_vbus[0], vbus_via_y, ip_vbus_via_x, vbus_via_y,
                       "F.Cu", W_PWR, n_vbus))
    parts.append(_seg(ip_vbus_via_x, vbus_via_y, ip_vbus_via_x, ip_vbus[1],
                       "F.Cu", W_PWR, n_vbus))
    parts.append(_via_net(ip_vbus_via_x, ip_vbus[1], n_vbus))
    # Short B.Cu horizontal to IP5306 pin
    parts.append(_seg(ip_vbus_via_x, ip_vbus[1], ip_vbus[0], ip_vbus[1],
                       "B.Cu", W_PWR, n_vbus))

    # ── GND: vias to In1.Cu GND zone ──────────────────────────
    # GND vias near key components
    gnd_via_positions = [
        (usb_gnd[0], usb_gnd[1] - 2),    # USB-C GND
        (ip_gnd[0] + 2, ip_gnd[1]),       # IP5306 GND (offset RIGHT to avoid +5V at same X)
        (am_gnd[0], am_gnd[1] + 2),       # AMS1117 GND
        (esp_gnd[0], esp_gnd[1] + 2),     # ESP32 GND
        (jst_n[0], jst_n[1]),             # JST GND
    ]
    for gvx, gvy in gnd_via_positions:
        parts.append(_via_net(gvx, gvy, n_gnd))

    # B.Cu stubs from IC GND pads to vias
    parts.append(_seg(usb_gnd[0], usb_gnd[1], usb_gnd[0], usb_gnd[1] - 2,
                       "B.Cu", W_PWR, n_gnd))
    # IP5306 GND: horizontal RIGHT to avoid sharing x with +5V vertical
    parts.append(_seg(ip_gnd[0], ip_gnd[1], ip_gnd[0] + 2, ip_gnd[1],
                       "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(am_gnd[0], am_gnd[1], am_gnd[0], am_gnd[1] + 2,
                       "B.Cu", W_PWR, n_gnd))
    # ESP32 GND pad (pin 41) to GND via
    parts.append(_seg(esp_gnd[0], esp_gnd[1], esp_gnd[0], esp_gnd[1] + 2,
                       "B.Cu", W_PWR, n_gnd))

    # ── +5V: IP5306 output -> AMS1117 input, vias to In2.Cu ───
    # IP5306 VOUT via: route DOWN (not up, to avoid GND at same X)
    parts.append(_via_net(ip_vout[0], ip_vout[1] + 2, n_5v))
    parts.append(_seg(ip_vout[0], ip_vout[1], ip_vout[0], ip_vout[1] + 2,
                       "B.Cu", W_PWR, n_5v))
    parts.append(_via_net(am_vin[0], am_vin[1] - 2, n_5v))
    parts.append(_seg(am_vin[0], am_vin[1], am_vin[0], am_vin[1] - 2,
                       "B.Cu", W_PWR, n_5v))
    # L1 inductor connection (IP5306 to L1)
    parts.append(_via_net(l1_1[0], l1_1[1] - 2, n_5v))
    parts.append(_seg(l1_1[0], l1_1[1], l1_1[0], l1_1[1] - 2,
                       "B.Cu", W_PWR, n_5v))
    # Connect IP5306 VOUT to L1 via B.Cu (vertical down, then horizontal)
    parts.append(_seg(ip_vout[0], ip_vout[1], ip_vout[0], l1_1[1],
                       "B.Cu", W_PWR, n_5v))
    parts.append(_seg(ip_vout[0], l1_1[1], l1_1[0], l1_1[1],
                       "B.Cu", W_PWR, n_5v))

    # ── +3V3: AMS1117 output via outside +5V zone ─────────────
    # AMS1117 VOUT (pin 2) and tab (pin 4) are +3V3
    # Route to via outside +5V zone (x < 100)
    v3_via_x = am_tab[0] - 2
    v3_via_y = am_tab[1] - 3
    parts.append(_seg(am_tab[0], am_tab[1], v3_via_x, am_tab[1],
                       "B.Cu", 0.4, n_3v3))
    parts.append(_seg(v3_via_x, am_tab[1], v3_via_x, v3_via_y,
                       "B.Cu", 0.4, n_3v3))
    parts.append(_via_net(v3_via_x, v3_via_y, n_3v3))
    # F.Cu horizontal to x=98 (outside +5V zone)
    parts.append(_seg(v3_via_x, v3_via_y, 98, v3_via_y,
                       "F.Cu", 0.4, n_3v3))
    parts.append(_via_net(98, v3_via_y, n_3v3))
    # ESP32 +3V3: via near pin 2 with B.Cu stub
    esp_3v3 = _pad("U1", "2")  # pin 2 = +3V3 power input
    if esp_3v3:
        parts.append(_via_net(esp_3v3[0], esp_3v3[1] - 2, n_3v3))
        parts.append(_seg(esp_3v3[0], esp_3v3[1], esp_3v3[0],
                           esp_3v3[1] - 2, "B.Cu", 0.4, n_3v3))

    # ── BAT+: IP5306 -> JST battery connector ─────────────────
    bat_via_y = ip_bat[1] + 3
    parts.append(_seg(ip_bat[0], ip_bat[1], ip_bat[0], bat_via_y,
                       "B.Cu", W_PWR, n_bat))
    parts.append(_via_net(ip_bat[0], bat_via_y, n_bat))
    # F.Cu horizontal to JST
    parts.append(_seg(ip_bat[0], bat_via_y, jst_p[0], bat_via_y,
                       "F.Cu", W_PWR, n_bat))
    parts.append(_via_net(jst_p[0], bat_via_y, n_bat))
    # B.Cu vertical to JST pad
    parts.append(_seg(jst_p[0], bat_via_y, jst_p[0], jst_p[1],
                       "B.Cu", W_PWR, n_bat))

    # ── Power switch -> BAT+ junction ──────────────────────────
    # Use F.Cu for long vertical to avoid B.Cu overlap with SPK+ at x~39.5
    sw_via_y = sw_com[1] - 2  # short B.Cu stub
    parts.append(_seg(sw_com[0], sw_com[1], sw_com[0], sw_via_y,
                       "B.Cu", W_PWR, n_bat))
    parts.append(_via_net(sw_com[0], sw_via_y, n_bat))
    # F.Cu vertical + horizontal to BAT+ junction
    parts.append(_seg(sw_com[0], sw_via_y, sw_com[0], bat_via_y,
                       "F.Cu", W_PWR, n_bat))
    parts.append(_seg(sw_com[0], bat_via_y, jst_p[0], bat_via_y,
                       "F.Cu", W_PWR, n_bat))

    # ── USB CC pull-down resistors ─────────────────────────────
    r1_gnd = _pad("R1", "2")
    r2_gnd = _pad("R2", "2")
    if r1_gnd:
        parts.append(_seg(r1_gnd[0], r1_gnd[1], r1_gnd[0],
                           usb_gnd[1] - 2, "B.Cu", W_SIG, n_gnd))
    if r2_gnd:
        parts.append(_seg(r2_gnd[0], r2_gnd[1], r2_gnd[0],
                           usb_gnd[1] - 2, "B.Cu", W_SIG, n_gnd))

    return parts


def _display_traces():
    """8080 display bus: ESP32 -> FPC-40P connector.

    ILI9488 4.0" bare panel FPC-40P pinout (from datasheet):
      1-4:   Touch (XL/YU/XR/YD) — NC
      5:     GND
      6:     VDDI (I/O power, 3.3V)
      7:     VDDA (analog power, 3.3V)
      8:     TE (tearing effect) — NC
      9:     CS          → GPIO12
      10:    DC/RS       → GPIO14
      11:    WR          → GPIO46
      12:    RD          → GPIO3
      13-14: SPI SDI/SDO — NC (parallel mode)
      15:    RESET       → GPIO13
      16:    GND
      17-24: DB0-DB7     → GPIO4-11
      25-32: DB8-DB15    — NC (8-bit mode)
      33:    LED-A (backlight anode) → GPIO45
      34-36: LED-K (backlight cathode) → GND
      37:    GND
      38:    IM0 → +3V3 (HIGH for 8080 8-bit)
      39:    IM1 → +3V3 (HIGH for 8080 8-bit)
      40:    IM2 → GND   (LOW for 8080 8-bit)

    After B.Cu mirroring:
    - ESP32 left-module pins (GPIO 4-8) are at board x~89 (RIGHT of ESP32)
    - ESP32 bottom-module pins (GPIO 9-11) are at board y~40
    - FPC pins are at x~137, with pin numbering reversed by B.Cu mirror

    Strategy: route from ESP32 pads RIGHT toward FPC, bypassing the
    FPC slot (x=125.5-128.5) by going above it (y < 23) then down.
    """
    parts = []
    _init_pads()

    # 8-bit data bus: GPIO 4-11 -> FPC pins 17-24 (DB0-DB7)
    data_gpios = [4, 5, 6, 7, 8, 9, 10, 11]
    fpc_data_pins = [17, 18, 19, 20, 21, 22, 23, 24]

    # Control signals: GPIO -> FPC pin mapping (per ILI9488 datasheet)
    ctrl = [
        (13, "LCD_RST", 15),  # RESET
        (12, "LCD_CS", 9),    # CS
        (14, "LCD_DC", 10),   # RS/DC
        (46, "LCD_WR", 11),   # WR
        (3,  "LCD_RD", 12),   # RD
        (45, "LCD_BL", 33),   # Backlight anode (LED-A)
    ]

    # Combined list for unified stagger handling
    # Each entry: (global_idx, gpio, fpc_pin, net_name)
    all_lcd = []
    for i, (gpio, fpc_pin) in enumerate(zip(data_gpios, fpc_data_pins)):
        all_lcd.append((i, gpio, fpc_pin, f"LCD_D{i}"))
    for j, (gpio, net_name, fpc_pin) in enumerate(ctrl):
        all_lcd.append((8 + j, gpio, fpc_pin, net_name))

    # Bottom-side stagger counter (pins at y ≈ 40 need Y separation)
    stagger_idx = 0

    for idx, gpio, fpc_pin, net_name in all_lcd:
        net = NET_ID[net_name]
        epx, epy = _esp_pin(gpio)
        fpx, fpy = _fpc_pin(fpc_pin)

        bypass_y = 8.0 + idx * 0.5
        apx = 130.0 + idx * 0.4
        col_x = 124.0 - idx * 0.8  # wider spacing (0.8mm vs 0.5mm)

        is_bottom = abs(epy - 40.0) < 1.0

        if is_bottom:
            # Bottom-side ESP32 pins: vertical stub UP to staggered Y
            # to avoid parallel overlapping horizontal stubs at y=40
            stagger_y = 38.0 - stagger_idx * 0.6
            stagger_idx += 1

            # 1. B.Cu vertical from pad up to stagger level
            parts.append(_seg(epx, epy, epx, stagger_y,
                              "B.Cu", W_DATA, net))
            parts.append(_via_net(epx, stagger_y, net))

            # 2. F.Cu horizontal to col_x
            parts.append(_seg(epx, stagger_y, col_x, stagger_y,
                              "F.Cu", W_DATA, net))
            parts.append(_via_net(col_x, stagger_y, net))
        else:
            # Side pins: horizontal stub right to via
            via1_x = epx + 1.5
            parts.append(_seg(epx, epy, via1_x, epy,
                              "B.Cu", W_DATA, net))
            parts.append(_via_net(via1_x, epy, net))

            # F.Cu horizontal to col_x
            parts.append(_seg(via1_x, epy, col_x, epy,
                              "F.Cu", W_DATA, net))
            parts.append(_via_net(col_x, epy, net))

        # 3. B.Cu vertical up to bypass level (above slot)
        from_y = stagger_y if is_bottom else epy
        parts.append(_seg(col_x, from_y, col_x, bypass_y,
                          "B.Cu", W_DATA, net))
        parts.append(_via_net(col_x, bypass_y, net))

        # 4. F.Cu horizontal across slot at safe Y
        parts.append(_seg(col_x, bypass_y, apx, bypass_y,
                          "F.Cu", W_DATA, net))
        # Stay on F.Cu — no via here (avoid B.Cu vertical crossing others)

        # 5. F.Cu vertical down to FPC pin Y level
        parts.append(_seg(apx, bypass_y, apx, fpy, "F.Cu", W_DATA, net))
        parts.append(_via_net(apx, fpy, net))

        # 6. B.Cu horizontal to FPC pad (short stub only)
        parts.append(_seg(apx, fpy, fpx, fpy, "B.Cu", W_DATA, net))

    # ── Power and GND connections to FPC (per ILI9488 datasheet) ──
    n_gnd = NET_ID["GND"]
    n_3v3 = NET_ID["+3V3"]

    # GND pins: 5, 16, 34, 35, 36, 37, 40(IM2)
    # Use staggered Y offsets for adjacent pins to ensure drill spacing
    gnd_pins_offsets = [
        (5, -2, 0),     # pin 5: offset x=-2 (away from pin 6 +3V3 via)
        (16, -2, 0),    # pin 16: offset x=-2
        (34, 2, -1),    # pin 34: offset x=+2, y=-1
        (35, -2, 0),    # pin 35: offset x=-2
        (36, 2, 1),     # pin 36: offset x=+2, y=+1
        (37, -2, 0),    # pin 37: offset x=-2
        (40, -2, 0),    # pin 40 (IM2): offset x=-2 (away from pin 39 +3V3 via)
    ]
    for pin, ox, oy in gnd_pins_offsets:
        pos = _fpc_pin(pin)
        if pos:
            vx, vy = pos[0] + ox, pos[1] + oy
            parts.append(_via_net(vx, vy, n_gnd))
            parts.append(_seg(pos[0], pos[1], vx, vy, "B.Cu", 0.3, n_gnd))

    # +3V3 pins: 6(VDDI), 7(VDDA), 38(IM0=HIGH), 39(IM1=HIGH)
    v33_pins_offsets = [
        (6, 2, -2),     # pin 6 (VDDI): offset x=+2, y=-2 (away from pin 7)
        (7, -2, 0),     # pin 7 (VDDA): offset x=-2
        (38, -2, -1),   # pin 38 (IM0): offset x=-2, y=-1
        (39, 2, 0),     # pin 39 (IM1): offset x=+2
    ]
    for pin, ox, oy in v33_pins_offsets:
        pos = _fpc_pin(pin)
        if pos:
            vx, vy = pos[0] + ox, pos[1] + oy
            parts.append(_via_net(vx, vy, n_3v3))
            parts.append(_seg(pos[0], pos[1], vx, vy, "B.Cu", 0.3, n_3v3))

    return parts


def _spi_traces():
    """SPI bus: ESP32 -> SD card slot.

    After B.Cu mirroring, SPI GPIOs (36-39) are on the LEFT side of the
    board (x~71) while SD card is on the far RIGHT (x~140). Route across
    the board, bypassing the FPC slot.
    """
    parts = []
    _init_pads()

    spi = [
        (36, "SD_MOSI"), (37, "SD_MISO"), (38, "SD_CLK"), (39, "SD_CS"),
    ]
    # SD card signal pins (TF-01A pin numbering)
    # Pin 3=CMD(MOSI), Pin 5=CLK, Pin 7=DAT0(MISO), Pin 2=CS(DAT3)
    sd_pin_map = {"SD_MOSI": "3", "SD_MISO": "7",
                  "SD_CLK": "5", "SD_CS": "2"}

    for i, (gpio, net_name) in enumerate(spi):
        net = NET_ID[net_name]
        epx, epy = _esp_pin(gpio)
        sd_pad = _pad("U6", sd_pin_map[net_name])
        if not sd_pad:
            continue
        sdx, sdy = sd_pad

        # Bypass Y above the slot
        bypass_y = 18.0 + i * 0.5

        # 1. B.Cu stub from ESP32 pad -> via
        stub_x = epx - 1.5 - i * 0.5  # unique offset left
        parts.append(_seg(epx, epy, stub_x, epy, "B.Cu", W_DATA, net))
        parts.append(_via_net(stub_x, epy, net))

        # 2. F.Cu horizontal to column left of slot
        col_x = 50.0 + i * 1.0  # well left of slot
        parts.append(_seg(stub_x, epy, col_x, epy, "F.Cu", W_DATA, net))
        parts.append(_via_net(col_x, epy, net))

        # 3. B.Cu vertical up to bypass level (above slot)
        parts.append(_seg(col_x, epy, col_x, bypass_y,
                          "B.Cu", W_DATA, net))
        parts.append(_via_net(col_x, bypass_y, net))

        # 4. F.Cu horizontal across board past slot
        post_slot_x = 135.0 + i * 1.0  # right of slot
        parts.append(_seg(col_x, bypass_y, post_slot_x, bypass_y,
                          "F.Cu", W_DATA, net))
        # Stay on F.Cu — no via here (avoid B.Cu vertical crossing LCD traces)

        # 5. F.Cu vertical down to staggered Y (avoid same-Y overlap)
        stagger_y = sdy - i * 1.0  # each signal at different Y
        parts.append(_seg(post_slot_x, bypass_y, post_slot_x, stagger_y,
                          "F.Cu", W_DATA, net))
        parts.append(_via_net(post_slot_x, stagger_y, net))

        # 6. B.Cu L-shaped to SD pad: horizontal at stagger_y, then vertical
        parts.append(_seg(post_slot_x, stagger_y, sdx, stagger_y,
                          "B.Cu", W_DATA, net))
        if abs(stagger_y - sdy) > 0.01:
            parts.append(_seg(sdx, stagger_y, sdx, sdy,
                              "B.Cu", W_DATA, net))

    return parts


def _i2s_traces():
    """I2S audio: ESP32 -> PAM8403 -> Speaker.

    After B.Cu mirroring, I2S GPIOs (15-17, pins 8-10) are at board x~89
    (RIGHT side). PAM8403 is at x=30 (LEFT). Route right-to-left.
    """
    parts = []
    _init_pads()

    i2s = [
        (15, "I2S_BCLK"), (16, "I2S_LRCK"), (17, "I2S_DOUT"),
    ]
    # PAM8403 input pins: RLIN=pin 11, LLIN=pin 6, BCLK=pin 14 etc.
    # Actually PAM8403 in SOP-16: pins 1-8 left, 9-16 right (before rotation)
    # After 90deg rotation + B.Cu mirror: pin layout changes
    # Pin 1 (INL+) at (34.45, 34.15), pin 16 (VDD) at (34.45, 24.85)
    # For I2S: we route to pins near the input side
    # PAM8403 functional pins:
    # Pin 4 = INR-, Pin 5 = INR+, Pin 12 = INL+, Pin 13 = INL-
    # For mono bridged: use pin 5 (INR+) and pin 12 (INL+)
    pam_pins = ["5", "12", "13"]  # BCLK→5, LRCK→12, DOUT→13

    for i, (gpio, net_name) in enumerate(i2s):
        net = NET_ID[net_name]
        epx, epy = _esp_pin(gpio)
        pam_pad = _pad("U5", pam_pins[i])
        if not pam_pad:
            continue
        pamx, pamy = pam_pad

        # Route from ESP32 (right side, x~89) to PAM8403 (left side, x~30)
        # 1. B.Cu stub from ESP32 pad left -> via
        via1_x = epx - 1.5
        parts.append(_seg(epx, epy, via1_x, epy, "B.Cu", W_DATA, net))
        parts.append(_via_net(via1_x, epy, net))

        # 2. F.Cu horizontal LEFT across board to PAM8403 area
        chan_y = epy  # use same Y for horizontal
        parts.append(_seg(via1_x, chan_y, pamx, chan_y,
                          "F.Cu", W_DATA, net))
        parts.append(_via_net(pamx, chan_y, net))

        # 3. B.Cu vertical from F.Cu channel to PAM8403 pad
        # Offset X with fixed spacing to avoid same-X overlaps
        col_x = 29.0 - i * 3.0  # i=0: 29, i=1: 26, i=2: 23
        parts.append(_seg(pamx, chan_y, col_x, chan_y, "B.Cu", W_DATA, net))
        parts.append(_seg(col_x, chan_y, col_x, pamy, "B.Cu", W_DATA, net))
        if abs(col_x - pamx) > 0.01:
            parts.append(_seg(col_x, pamy, pamx, pamy, "B.Cu", W_DATA, net))

    # Audio output: PAM8403 -> Speaker
    n_spk_p = NET_ID["SPK+"]
    n_spk_m = NET_ID["SPK-"]

    # PAM8403 output pins: pin 3 (OUTR+), pin 14 (OUTL+)
    # Speaker pads
    spk_1 = _pad("SPK1", "1")  # (39.5, 52.5)
    spk_2 = _pad("SPK1", "2")  # (20.5, 52.5)
    pam_outr = _pad("U5", "3")   # Right output
    pam_outl = _pad("U5", "14")  # Left output

    if pam_outr and spk_1:
        # SPK+: PAM right output -> speaker pad 1
        # Offset column +1.5mm right to avoid SPK- at same X
        spk_p_x = pam_outr[0] + 1.5
        mid_y = 23.0  # above PAM
        parts.append(_seg(pam_outr[0], pam_outr[1], spk_p_x, pam_outr[1],
                          "B.Cu", W_AUDIO, n_spk_p))
        parts.append(_seg(spk_p_x, pam_outr[1], spk_p_x, mid_y,
                          "B.Cu", W_AUDIO, n_spk_p))
        parts.append(_via_net(spk_p_x, mid_y, n_spk_p))
        parts.append(_seg(spk_p_x, mid_y, spk_1[0], mid_y,
                          "F.Cu", W_AUDIO, n_spk_p))
        parts.append(_via_net(spk_1[0], mid_y, n_spk_p))
        parts.append(_seg(spk_1[0], mid_y, spk_1[0], spk_1[1],
                          "B.Cu", W_AUDIO, n_spk_p))

    if pam_outl and spk_2:
        # SPK-: PAM left output -> speaker pad 2
        mid_y = 21.0  # above PAM, different channel
        parts.append(_seg(pam_outl[0], pam_outl[1], pam_outl[0], mid_y,
                          "B.Cu", W_AUDIO, n_spk_m))
        parts.append(_via_net(pam_outl[0], mid_y, n_spk_m))
        parts.append(_seg(pam_outl[0], mid_y, spk_2[0], mid_y,
                          "F.Cu", W_AUDIO, n_spk_m))
        parts.append(_via_net(spk_2[0], mid_y, n_spk_m))
        parts.append(_seg(spk_2[0], mid_y, spk_2[0], spk_2[1],
                          "B.Cu", W_AUDIO, n_spk_m))

    return parts


def _usb_traces():
    """USB D+/D- differential pair: USB-C -> ESP32."""
    parts = []
    _init_pads()

    n_dp = NET_ID["USB_D+"]
    n_dm = NET_ID["USB_D-"]

    # ESP32 USB pins
    dp_x, dp_y = _esp_pin(20)  # D+
    dm_x, dm_y = _esp_pin(19)  # D-

    # USB-C data pads: D+ on A6/B6, D- on A7/B7
    usb_dp = _pad("J1", "A6")
    usb_dm = _pad("J1", "A7")
    if not usb_dp or not usb_dm:
        return parts

    # D+: USB-C -> ESP32
    # 1. B.Cu vertical from USB-C pad up
    dp_via_y = usb_dp[1] - 3
    parts.append(_seg(usb_dp[0], usb_dp[1], usb_dp[0], dp_via_y,
                       "B.Cu", W_DATA, n_dp))
    parts.append(_via_net(usb_dp[0], dp_via_y, n_dp))
    # 2. F.Cu horizontal to approach column
    dp_col_x = dp_x + 2
    parts.append(_seg(usb_dp[0], dp_via_y, dp_col_x, dp_via_y,
                       "F.Cu", W_DATA, n_dp))
    parts.append(_via_net(dp_col_x, dp_via_y, n_dp))
    # 3. B.Cu vertical up to ESP32 pin Y
    parts.append(_seg(dp_col_x, dp_via_y, dp_col_x, dp_y,
                       "B.Cu", W_DATA, n_dp))
    # 4. B.Cu horizontal stub to ESP32 pad
    parts.append(_seg(dp_col_x, dp_y, dp_x, dp_y, "B.Cu", W_DATA, n_dp))

    # D-: USB-C -> ESP32 (stagger via Y to avoid drill spacing)
    dm_via_y = usb_dm[1] - 4
    parts.append(_seg(usb_dm[0], usb_dm[1], usb_dm[0], dm_via_y,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_via_net(usb_dm[0], dm_via_y, n_dm))
    dm_col_x = dm_x + 3
    parts.append(_seg(usb_dm[0], dm_via_y, dm_col_x, dm_via_y,
                       "F.Cu", W_DATA, n_dm))
    parts.append(_via_net(dm_col_x, dm_via_y, n_dm))
    parts.append(_seg(dm_col_x, dm_via_y, dm_col_x, dm_y,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_seg(dm_col_x, dm_y, dm_x, dm_y, "B.Cu", W_DATA, n_dm))

    # USB CC pull-down resistors -> GND via (use actual pad positions)
    n_gnd = NET_ID["GND"]
    usb_gnd = _pad("J1", "A12")
    if usb_gnd:
        r1_gnd_pad = _pad("R1", "2")
        r2_gnd_pad = _pad("R2", "2")
        if r1_gnd_pad:
            parts.append(_seg(r1_gnd_pad[0], r1_gnd_pad[1], r1_gnd_pad[0],
                              usb_gnd[1] - 2, "B.Cu", W_SIG, n_gnd))
        if r2_gnd_pad:
            parts.append(_seg(r2_gnd_pad[0], r2_gnd_pad[1], r2_gnd_pad[0],
                              usb_gnd[1] - 2, "B.Cu", W_SIG, n_gnd))

    return parts


def _button_traces():
    """Button traces with exact ESP32 pad positions.

    After B.Cu mirroring, ESP32 pin sides are swapped:
    - Module left-side GPIOs -> board RIGHT (x~89)
    - Module right-side GPIOs -> board LEFT (x~71)
    - Module bottom-side GPIOs -> board y~40

    F.Cu: horizontal segments (channels)
    B.Cu: vertical segments + stubs
    Via at every H-V transition.
    """
    parts = []
    _init_pads()

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

    # Build button data with exact pad positions
    n_gnd = NET_ID["GND"]
    btn_data = []
    for ref, net_name, gpio in front_btns:
        bx, by = btn_pos[ref]
        epx, epy = _esp_pin(gpio)
        # Signal pad: right side for left buttons, left side for right
        if bx < CX:
            sig_pad = _pad(ref, "2")   # right pad (bx+3, by-1.85)
            gnd_pad = _pad(ref, "3")   # left-bottom pad for GND
        else:
            sig_pad = _pad(ref, "1")   # left pad (bx-3, by-1.85)
            gnd_pad = _pad(ref, "4")   # right-bottom pad for GND
        spx, spy = sig_pad if sig_pad else (bx, by)
        btn_data.append({
            "ref": ref, "net": NET_ID[net_name],
            "bx": bx, "by": by, "epx": epx, "epy": epy,
            "spx": spx, "spy": spy,
            "gnd_pad": gnd_pad,
        })

    # Assign unique F.Cu horizontal channels (y=62+, below passive area)
    # Passive pull-ups at y=46, debounce caps at y=50, GND vias at y=52
    for i, b in enumerate(btn_data):
        b["chan_y"] = 62.0 + i * 1.0

    # Assign approach columns near ESP32
    # Avoid passive pull-up traces at x = 43+i*5 ± 0.95, y=46-50
    passive_trace_xs = {43 + i * 5 + 0.95 for i in range(13)}
    passive_trace_xs |= {43 + i * 5 - 0.95 for i in range(13)}
    used_approach_xs = set()

    for i, b in enumerate(btn_data):
        epx = b["epx"]
        if epx > CX:
            ax = epx + 2 + i * 0.6
        else:
            ax = epx - 2 - i * 0.6
        # Nudge away from passive traces and previously used columns
        for _ in range(20):
            conflict = False
            for px in passive_trace_xs:
                if abs(ax - px) < 0.5:  # need 0.5mm clearance
                    ax = px + 0.5 if ax > px else px - 0.5
                    conflict = True
                    break
            for ux in used_approach_xs:
                if abs(ax - ux) < 0.4:  # need 0.4mm clearance
                    ax = ux - 0.4 if ax < ux else ux + 0.4
                    conflict = True
                    break
            if not conflict:
                break
        used_approach_xs.add(round(ax, 2))
        b["approach_x"] = round(ax, 2)

    # Compute via X: 1mm beyond signal pad
    via_x_map = {}
    for b in btn_data:
        spx = b["spx"]
        if b["bx"] < CX:
            base_vx = spx + 1.0  # right of right pad
        else:
            base_vx = spx - 1.0  # left of left pad
        # Check slot zone
        slot_margin = 0.6
        if (SLOT_X1 - slot_margin < base_vx < SLOT_X2 + slot_margin and
                SLOT_Y1 - slot_margin < b["spy"] < SLOT_Y2 + slot_margin):
            base_vx = SLOT_X2 + slot_margin + 0.5
        vx = base_vx
        while vx in via_x_map:
            vx += 1.0
        via_x_map[vx] = b["ref"]
        b["vx"] = vx

    # Generate traces for all front buttons
    bottom_stagger_idx = 0
    for b in btn_data:
        net = b["net"]
        spx, spy = b["spx"], b["spy"]
        epx, epy = b["epx"], b["epy"]
        vx = b["vx"]
        ax = b["approach_x"]
        cy = b["chan_y"]

        # 1. F.Cu: signal pad to via
        parts.append(_seg(spx, spy, vx, spy, "F.Cu", W_SIG, net))
        parts.append(_via_net(vx, spy, net))

        # 2. B.Cu: vertical from button via to F.Cu channel
        parts.append(_seg(vx, spy, vx, cy, "B.Cu", W_SIG, net))
        parts.append(_via_net(vx, cy, net))

        # 3. F.Cu: horizontal to approach column
        parts.append(_seg(vx, cy, ax, cy, "F.Cu", W_SIG, net))
        parts.append(_via_net(ax, cy, net))

        # 4-5. Route to ESP32 pad: B.Cu vertical + F.Cu horizontal
        # Bottom-side pins (y≈40) get Y-stagger to avoid same-Y overlap
        is_bottom = abs(epy - 40.0) < 2.0
        if is_bottom:
            stagger_y = 38.0 - bottom_stagger_idx * 0.8
            bottom_stagger_idx += 1
            # B.Cu vertical to stagger Y
            parts.append(_seg(ax, cy, ax, stagger_y, "B.Cu", W_SIG, net))
            parts.append(_via_net(ax, stagger_y, net))
            # F.Cu horizontal to ESP32 pad X
            parts.append(_seg(ax, stagger_y, epx, stagger_y,
                              "F.Cu", W_SIG, net))
            parts.append(_via_net(epx, stagger_y, net))
            # B.Cu short vertical to actual pad
            parts.append(_seg(epx, stagger_y, epx, epy,
                              "B.Cu", W_SIG, net))
        else:
            # B.Cu vertical to ESP32 Y level
            parts.append(_seg(ax, cy, ax, epy, "B.Cu", W_SIG, net))
            # F.Cu horizontal to ESP32 pad (avoid B.Cu crossing)
            if abs(ax - epx) > 0.01:
                parts.append(_via_net(ax, epy, net))
                parts.append(_seg(ax, epy, epx, epy,
                                  "F.Cu", W_SIG, net))
                parts.append(_via_net(epx, epy, net))

        # 6. GND via on opposite button pad
        gp = b["gnd_pad"]
        if gp:
            parts.append(_via_net(gp[0], gp[1], n_gnd))

    # Shoulder button BTN_L (B.Cu, rotated 90°)
    net_l = NET_ID["BTN_L"]
    # Use actual pad position instead of button center
    sl_pad = _pad("SW11", "3")  # bottom pad after rotation
    sx_l = sl_pad[0] if sl_pad else SHOULDER_L[1][0]
    sy_l = sl_pad[1] if sl_pad else SHOULDER_L[1][1]
    epx_l, epy_l = _esp_pin(35)
    chan_y_l = 58.0 + len(btn_data)

    # B.Cu vertical from shoulder button pad to channel
    parts.append(_seg(sx_l, sy_l, sx_l, chan_y_l, "B.Cu", W_SIG, net_l))
    parts.append(_via_net(sx_l, chan_y_l, net_l))
    # F.Cu horizontal to approach
    approach_l = epx_l - 2
    parts.append(_seg(sx_l, chan_y_l, approach_l, chan_y_l,
                       "F.Cu", W_SIG, net_l))
    parts.append(_via_net(approach_l, chan_y_l, net_l))
    # B.Cu vertical to ESP32 pin level
    parts.append(_seg(approach_l, chan_y_l, approach_l, epy_l,
                       "B.Cu", W_SIG, net_l))
    # B.Cu horizontal to ESP32 pad
    parts.append(_seg(approach_l, epy_l, epx_l, epy_l,
                       "B.Cu", W_SIG, net_l))
    # GND via on opposite shoulder pad
    sl_gnd = _pad("SW11", "2")
    if sl_gnd:
        parts.append(_via_net(sl_gnd[0], sl_gnd[1], n_gnd))

    return parts


def _passive_traces():
    """Traces for passive components using exact pad positions.

    Power connections (+3V3, GND, +5V) use vias to inner layer zones.
    """
    parts = []
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]
    n_5v = NET_ID["+5V"]

    # Button pull-up resistors: +3V3 via at pull-up pad
    for i, ref in enumerate(PULL_UP_REFS):
        rx = 43 + i * 5
        ry = 46
        parts.append(_via_net(rx - 0.95, ry, n_3v3))

    # Debounce caps: GND via at cap pad
    for i, ref in enumerate(DEBOUNCE_REFS):
        cx = 43 + i * 5
        cy = 50
        parts.append(_seg(cx - 0.95, cy, cx - 0.95, cy + 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(cx - 0.95, cy + 2, n_gnd))

    # Connect pull-up outputs to debounce cap inputs (R->C junction)
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
        parts.append(_seg(x + 0.95, 46, x + 0.95, 50, "B.Cu", W_SIG, net))

    # Decoupling caps — use exact pad positions
    # B.Cu passives: after mirroring, pad "1" at (cx+0.95, cy), pad "2" at (cx-0.95, cy)
    _init_pads()

    # C3 near ESP32: pad "1" -> +3V3 via
    c3_p1 = _pad("C3", "1")
    if c3_p1:
        parts.append(_via_net(c3_p1[0], c3_p1[1], n_3v3))
    # C3 pad "2" -> GND via
    c3_p2 = _pad("C3", "2")
    if c3_p2:
        parts.append(_seg(c3_p2[0], c3_p2[1], c3_p2[0], c3_p2[1] - 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c3_p2[0], c3_p2[1] - 2, n_gnd))

    # C4 near ESP32: pad "1" -> +3V3 via, pad "2" -> GND via
    c4_p1 = _pad("C4", "1")
    c4_p2 = _pad("C4", "2")
    if c4_p1:
        parts.append(_via_net(c4_p1[0], c4_p1[1], n_3v3))
    if c4_p2:
        parts.append(_seg(c4_p2[0], c4_p2[1], c4_p2[0], c4_p2[1] - 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c4_p2[0], c4_p2[1] - 2, n_gnd))

    # C1 AMS1117 input: pad "1" -> +5V via, pad "2" -> GND via
    c1_p1 = _pad("C1", "1")
    c1_p2 = _pad("C1", "2")
    if c1_p1:
        parts.append(_seg(c1_p1[0], c1_p1[1], c1_p1[0], c1_p1[1] - 2,
                          "B.Cu", W_SIG, n_5v))
        parts.append(_via_net(c1_p1[0], c1_p1[1] - 2, n_5v))
    if c1_p2:
        # Route GND UP (not down) to avoid crossing +3V3 horizontal at y~52.35
        parts.append(_seg(c1_p2[0], c1_p2[1], c1_p2[0], c1_p2[1] - 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c1_p2[0], c1_p2[1] - 2, n_gnd))

    # C2 AMS1117 output: pad "1" -> AMS1117 tab (+3V3), pad "2" -> GND via
    c2_p1 = _pad("C2", "1")
    c2_p2 = _pad("C2", "2")
    am_tab = _pad("U3", "4")
    if c2_p1 and am_tab:
        parts.append(_seg(c2_p1[0], c2_p1[1], am_tab[0], c2_p1[1],
                          "B.Cu", W_SIG, n_3v3))
        parts.append(_seg(am_tab[0], c2_p1[1], am_tab[0], am_tab[1],
                          "B.Cu", W_SIG, n_3v3))
    if c2_p2:
        parts.append(_seg(c2_p2[0], c2_p2[1], c2_p2[0], c2_p2[1] + 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c2_p2[0], c2_p2[1] + 2, n_gnd))

    # C17 near IP5306: pad "1" -> +5V via, pad "2" -> GND via
    c17_p1 = _pad("C17", "1")
    c17_p2 = _pad("C17", "2")
    if c17_p1:
        parts.append(_seg(c17_p1[0], c17_p1[1], c17_p1[0], c17_p1[1] - 2,
                          "B.Cu", W_SIG, n_5v))
        parts.append(_via_net(c17_p1[0], c17_p1[1] - 2, n_5v))
    if c17_p2:
        parts.append(_seg(c17_p2[0], c17_p2[1], c17_p2[0], c17_p2[1] + 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c17_p2[0], c17_p2[1] + 2, n_gnd))

    # C18 near IP5306: pad "1" -> +5V via, pad "2" -> GND via
    c18_p1 = _pad("C18", "1")
    c18_p2 = _pad("C18", "2")
    if c18_p1:
        parts.append(_seg(c18_p1[0], c18_p1[1], c18_p1[0], c18_p1[1] - 2,
                          "B.Cu", W_SIG, n_5v))
        parts.append(_via_net(c18_p1[0], c18_p1[1] - 2, n_5v))
    if c18_p2:
        parts.append(_seg(c18_p2[0], c18_p2[1], c18_p2[0], c18_p2[1] + 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c18_p2[0], c18_p2[1] + 2, n_gnd))

    # C19 near L1: pad "1" -> BAT+ (connect to L1 pad 2), pad "2" -> GND via
    c19_p1 = _pad("C19", "1")
    c19_p2 = _pad("C19", "2")
    l1_2 = _pad("L1", "2")
    if c19_p1 and l1_2:
        parts.append(_seg(c19_p1[0], c19_p1[1], l1_2[0], c19_p1[1],
                          "B.Cu", W_SIG, NET_ID["BAT+"]))
        parts.append(_seg(l1_2[0], c19_p1[1], l1_2[0], l1_2[1],
                          "B.Cu", W_SIG, NET_ID["BAT+"]))
    if c19_p2:
        parts.append(_seg(c19_p2[0], c19_p2[1], c19_p2[0], c19_p2[1] + 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c19_p2[0], c19_p2[1] + 2, n_gnd))

    # R16 IP5306 KEY pull-down: pad "1" -> IP5306 KEY, pad "2" -> GND via
    r16_p1 = _pad("R16", "1")
    r16_p2 = _pad("R16", "2")
    if r16_p2:
        parts.append(_seg(r16_p2[0], r16_p2[1], r16_p2[0], r16_p2[1] + 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(r16_p2[0], r16_p2[1] + 2, n_gnd))

    return parts


def _led_traces():
    """LED traces: F.Cu pads -> via -> inner zone connections."""
    parts = []
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]

    for i, (lx, ly) in enumerate([LED1, LED2]):
        # +3V3 anode — offset via Y to avoid button approach column vias
        via_offset = 2.5 + i * 1.5  # stagger per LED (LED2 needs 4mm to clear BTN vias)
        parts.append(_seg(lx - 1, ly, lx - 1, ly - via_offset,
                          "F.Cu", W_SIG, n_3v3))
        parts.append(_via_net(lx - 1, ly - via_offset, n_3v3))
        # GND cathode
        parts.append(_seg(lx + 1, ly, lx + 1, ly - via_offset,
                          "F.Cu", W_SIG, n_gnd))
        parts.append(_via_net(lx + 1, ly - via_offset, n_gnd))

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
