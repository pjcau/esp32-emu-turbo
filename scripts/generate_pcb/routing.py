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
SHOULDER_L = ("SW11", enc(-65, 32))
SHOULDER_R = ("SW12", enc(65, 32))

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
R17_POS = (25.0, 65.0)   # LED1 current limit (near LED1 on B.Cu)
R18_POS = (32.0, 65.0)   # LED2 current limit (near LED2 on B.Cu)

C1_POS = (125.0, 48.5)   # AMS1117 input cap (amx, amy-7)
C2_POS = (125.0, 62.5)   # AMS1117 output cap (amx, amy+7)
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
        ("R17", "R_0805", *R17_POS, 0, "B"),
        ("R18", "R_0805", *R18_POS, 0, "B"),
        ("LED1", "LED_0805", *LED1, 0, "F"),
        ("LED2", "LED_0805", *LED2, 0, "F"),
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


def _via_net(x, y, net=0, size=None, drill=None):
    if size is not None and drill is not None:
        return P.via(x, y, size=size, drill=drill, net=net)
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
    n_lx = NET_ID["LX"]
    n_key = NET_ID["IP5306_KEY"]

    # ── Get exact pad positions ─────────────────────────────────
    # IP5306 (U2): ESOP-8 — corrected per datasheet
    # Pin 1=VIN, 5=KEY, 6=BAT, 7=SW/LX, 8=VOUT, EP=GND
    # Pins 2-4 = LED indicators (NC in this design)
    ip_vbus = _pad("U2", "1")     # VIN (charger 5V input)
    ip_key = _pad("U2", "5")      # KEY (on/off control)
    ip_bat = _pad("U2", "6")      # BAT (battery terminal)
    ip_sw = _pad("U2", "7")       # SW/LX (inductor switch node)
    ip_vout = _pad("U2", "8")     # VOUT (5V boost output)
    ip_ep = _pad("U2", "EP")      # GND (exposed pad)

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
        (ip_ep[0], ip_ep[1] + 3),          # IP5306 GND (via below exposed pad)
        (am_gnd[0], am_gnd[1] + 2),       # AMS1117 GND
        (esp_gnd[0], esp_gnd[1] + 2),     # ESP32 GND
        (jst_n[0] - 2, jst_n[1]),          # JST GND (offset AWAY from BAT+ pad)
    ]
    for gvx, gvy in gnd_via_positions:
        parts.append(_via_net(gvx, gvy, n_gnd))

    # B.Cu stubs from IC GND pads to vias
    parts.append(_seg(usb_gnd[0], usb_gnd[1], usb_gnd[0], usb_gnd[1] - 2,
                       "B.Cu", W_PWR, n_gnd))
    # IP5306 GND: vertical DOWN from exposed pad
    parts.append(_seg(ip_ep[0], ip_ep[1], ip_ep[0], ip_ep[1] + 3,
                       "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(am_gnd[0], am_gnd[1], am_gnd[0], am_gnd[1] + 2,
                       "B.Cu", W_PWR, n_gnd))
    # ESP32 GND pad (pin 41) to GND via
    parts.append(_seg(esp_gnd[0], esp_gnd[1], esp_gnd[0], esp_gnd[1] + 2,
                       "B.Cu", W_PWR, n_gnd))
    # JST GND pad to offset via (LEFT, away from BAT+ pad)
    parts.append(_seg(jst_n[0], jst_n[1], jst_n[0] - 2, jst_n[1],
                       "B.Cu", W_PWR, n_gnd))

    # ── +5V: IP5306 VOUT (pin 8) -> AMS1117 input ──────────────
    # VOUT via to +5V zone on In2.Cu
    parts.append(_via_net(ip_vout[0], ip_vout[1] - 2, n_5v))
    parts.append(_seg(ip_vout[0], ip_vout[1], ip_vout[0], ip_vout[1] - 2,
                       "B.Cu", W_PWR, n_5v))
    # AMS1117 VIN via
    parts.append(_via_net(am_vin[0], am_vin[1] - 2, n_5v))
    parts.append(_seg(am_vin[0], am_vin[1], am_vin[0], am_vin[1] - 2,
                       "B.Cu", W_PWR, n_5v))

    # ── LX: IP5306 SW (pin 7) -> L1 inductor ────────────────
    # Route from SW pin down to L1 pin 2 (closer pin)
    parts.append(_seg(ip_sw[0], ip_sw[1], ip_sw[0], l1_2[1],
                       "B.Cu", W_PWR, n_lx))
    parts.append(_seg(ip_sw[0], l1_2[1], l1_2[0], l1_2[1],
                       "B.Cu", W_PWR, n_lx))

    # ── BAT+ side of L1: L1 pin 1 to BAT+ zone ─────────────
    parts.append(_via_net(l1_1[0], l1_1[1] - 2, n_bat))
    parts.append(_seg(l1_1[0], l1_1[1], l1_1[0], l1_1[1] - 2,
                       "B.Cu", W_PWR, n_bat))

    # ── KEY: IP5306 pin 5 -> R16 pull-up to +5V ─────────────
    # B.Cu route from KEY pin down to R16 area
    r16_p1 = _pad("R16", "1")
    r16_p2 = _pad("R16", "2")
    if r16_p2 and ip_key:
        # R16 pin 2 -> IP5306 KEY (pin 5) via B.Cu L-route
        parts.append(_seg(r16_p2[0], r16_p2[1], r16_p2[0], ip_key[1],
                           "B.Cu", W_SIG, n_key))
        parts.append(_seg(r16_p2[0], ip_key[1], ip_key[0], ip_key[1],
                           "B.Cu", W_SIG, n_key))
    if r16_p1:
        # R16 pin 1 -> +5V via (pull-up for always-on)
        parts.append(_seg(r16_p1[0], r16_p1[1], r16_p1[0], r16_p1[1] + 2,
                           "B.Cu", W_SIG, n_5v))
        parts.append(_via_net(r16_p1[0], r16_p1[1] + 2, n_5v))

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

    # USB CC pull-down resistor GND traces are in _usb_traces()

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

        bypass_y = 5.0 + idx * 1.0   # DFM: was 0.5mm pitch (via overlap)
        # Approach column: 0.90mm pitch with 0.7mm/0.3mm vias (DFM fix).
        # All approach vias east of BTN_Y (x=129.6) and west of BTN_A (x=138)
        # so B.Cu stubs go EAST to FPC pads without crossing button verticals.
        apx = 130.0 + idx * 0.90
        col_x = 124.0 - idx * 1.1  # 1.1mm pitch avoids +5V vertical at x~117

        is_bottom = abs(epy - 40.0) < 1.0

        if is_bottom:
            # Bottom-side ESP32 pins: vertical stub UP to staggered Y
            # to avoid parallel overlapping horizontal stubs at y=40
            stagger_y = 38.0 - stagger_idx * 1.0  # DFM: was 0.6mm (via overlap)
            stagger_idx += 1

            # 1. B.Cu vertical from pad up to stagger level
            parts.append(_seg(epx, epy, epx, stagger_y,
                              "B.Cu", W_DATA, net))
            parts.append(_via_net(epx, stagger_y, net))

            # 2. F.Cu horizontal to col_x
            parts.append(_seg(epx, stagger_y, col_x, stagger_y,
                              "F.Cu", W_DATA, net))
            parts.append(_via_net(col_x, stagger_y, net, size=0.7, drill=0.3))
        else:
            # Side pins: horizontal stub right to via
            via1_x = epx + 2.0  # DFM: was 1.5 (too close to col_x vias)
            parts.append(_seg(epx, epy, via1_x, epy,
                              "B.Cu", W_DATA, net))
            parts.append(_via_net(via1_x, epy, net))

            # F.Cu horizontal to col_x
            parts.append(_seg(via1_x, epy, col_x, epy,
                              "F.Cu", W_DATA, net))
            parts.append(_via_net(col_x, epy, net, size=0.7, drill=0.3))

        # 3. B.Cu vertical up to bypass level (above slot)
        from_y = stagger_y if is_bottom else epy
        parts.append(_seg(col_x, from_y, col_x, bypass_y,
                          "B.Cu", W_DATA, net))
        parts.append(_via_net(col_x, bypass_y, net, size=0.7, drill=0.3))

        # 4. F.Cu horizontal across slot at safe Y
        parts.append(_seg(col_x, bypass_y, apx, bypass_y,
                          "F.Cu", W_DATA, net))
        # Stay on F.Cu — no via here (avoid B.Cu vertical crossing others)

        # 5. F.Cu vertical down to FPC pin Y level
        parts.append(_seg(apx, bypass_y, apx, fpy, "F.Cu", W_DATA, net))
        parts.append(_via_net(apx, fpy, net, size=0.7, drill=0.3))

        # 6. B.Cu horizontal to FPC pad (short stub only)
        parts.append(_seg(apx, fpy, fpx, fpy, "B.Cu", W_DATA, net))

    # ── Power and GND connections to FPC (per ILI9488 datasheet) ──
    n_gnd = NET_ID["GND"]
    n_3v3 = NET_ID["+3V3"]

    # GND pins: 5, 16, 34, 35, 36, 37, 40(IM2)
    # DFM: large staggered offsets to ensure drill spacing ≥0.25mm
    gnd_pins_offsets = [
        (5, -3, 0),     # pin 5: offset x=-3
        (16, -3, 2),    # pin 16: offset x=-3, y=+2
        (34, 3, -3),    # pin 34: offset x=+3, y=-3
        (35, -3, 2),    # pin 35: offset x=-3, y=+2
        (36, 3, 3),     # pin 36: offset x=+3, y=+3
        (37, -3, -2),   # pin 37: offset x=-3, y=-2
        (40, -3, 2),    # pin 40 (IM2): offset x=-3, y=+2
    ]
    for pin, ox, oy in gnd_pins_offsets:
        pos = _fpc_pin(pin)
        if pos:
            vx, vy = pos[0] + ox, pos[1] + oy
            parts.append(_via_net(vx, vy, n_gnd, size=0.7, drill=0.3))
            parts.append(_seg(pos[0], pos[1], vx, vy, "B.Cu", 0.3, n_gnd))

    # +3V3 pins: 6(VDDI), 7(VDDA), 38(IM0=HIGH), 39(IM1=HIGH)
    # DFM: large staggered offsets to ensure drill spacing ≥0.25mm
    v33_pins_offsets = [
        (6, 3, -3),     # pin 6 (VDDI): offset x=+3, y=-3
        (7, -3, 2),     # pin 7 (VDDA): offset x=-3, y=+2
        (38, -3, -3),   # pin 38 (IM0): offset x=-3, y=-3
        (39, 3, 2),     # pin 39 (IM1): offset x=+3, y=+2
    ]
    for pin, ox, oy in v33_pins_offsets:
        pos = _fpc_pin(pin)
        if pos:
            vx, vy = pos[0] + ox, pos[1] + oy
            parts.append(_via_net(vx, vy, n_3v3, size=0.7, drill=0.3))
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
        bypass_y = 20.0 + i * 1.0  # DFM: was 0.5mm pitch (via overlap)

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
    """Audio chain: ESP32 I2S_DOUT -> PAM8403 -> Speaker (BTL right channel).

    PAM8403 SOP-16 correct pinout:
      Pin 1=+OUT_L, 2=PGND, 3=-OUT_L, 4=PVDD, 5=MUTE, 6=VDD,
      7=INL, 8=VREF, 9=NC, 10=INR, 11=GND, 12=SHDN,
      13=PVDD, 14=-OUT_R, 15=PGND, 16=+OUT_R

    Audio input: only I2S_DOUT (GPIO 17) routed to INR (pin 10) and INL
      (pin 7) for mono. BCLK/LRCK unused by PAM8403 (analog amp, not I2S).
    Speaker: BTL right channel: SPK+ = +OUT_R (pin 16), SPK- = -OUT_R (pin 14).
    Power: PVDD (4,13) + VDD (6) → +5V; PGND (2,15) + GND (11) → GND.
    Control: MUTE (5) + SHDN (12) → +5V (always on/unmuted).
    VREF (8): internal reference, left unconnected (no spare cap in BOM).
    """
    parts = []
    _init_pads()

    n_5v = NET_ID["+5V"]
    n_gnd = NET_ID["GND"]
    n_dout = NET_ID["I2S_DOUT"]
    n_spk_p = NET_ID["SPK+"]
    n_spk_m = NET_ID["SPK-"]

    # ── Audio input: ESP32 I2S_DOUT → PAM8403 INR (pin 10) + INL (pin 7)
    epx, epy = _esp_pin(17)  # GPIO 17 = I2S_DOUT
    pam_inr = _pad("U5", "10")   # INR (26.825, 24.850)
    pam_inl = _pad("U5", "7")    # INL (26.825, 34.150)

    if pam_inr:
        inrx, inry = pam_inr
        # B.Cu stub from ESP32 pad → via
        via1_x = epx - 1.5
        parts.append(_seg(epx, epy, via1_x, epy, "B.Cu", W_DATA, n_dout))
        parts.append(_via_net(via1_x, epy, n_dout))
        # F.Cu horizontal across board to PAM8403 area
        parts.append(_seg(via1_x, epy, inrx, epy, "F.Cu", W_DATA, n_dout))
        parts.append(_via_net(inrx, epy, n_dout))
        # B.Cu vertical to INR pad
        parts.append(_seg(inrx, epy, inrx, inry, "B.Cu", W_DATA, n_dout))

    if pam_inr and pam_inl:
        inrx, inry = pam_inr
        inlx, inly = pam_inl
        # Bridge INR to INL for mono (same X column, vertical trace)
        parts.append(_seg(inrx, inry, inrx, inly, "B.Cu", W_DATA, n_dout))

    # ── Speaker output: BTL right channel
    # SPK+ = +OUT_R (pin 16), SPK- = -OUT_R (pin 14)
    spk_1 = _pad("SPK1", "1")    # (39.5, 52.5)
    spk_2 = _pad("SPK1", "2")    # (20.5, 52.5)
    pam_outr_p = _pad("U5", "16")  # +OUT_R (34.445, 24.850)
    pam_outr_m = _pad("U5", "14")  # -OUT_R (31.905, 24.850)

    if pam_outr_p and spk_1:
        # SPK+: +OUT_R (pin 16) → speaker pad 1
        ox, oy = pam_outr_p
        sx, sy = spk_1
        col_x = ox + 1.5  # offset right to avoid SPK- path
        mid_y = 23.0
        parts.append(_seg(ox, oy, col_x, oy, "B.Cu", W_AUDIO, n_spk_p))
        parts.append(_seg(col_x, oy, col_x, mid_y, "B.Cu", W_AUDIO, n_spk_p))
        parts.append(_via_net(col_x, mid_y, n_spk_p))
        parts.append(_seg(col_x, mid_y, sx, mid_y, "F.Cu", W_AUDIO, n_spk_p))
        parts.append(_via_net(sx, mid_y, n_spk_p))
        parts.append(_seg(sx, mid_y, sx, sy, "B.Cu", W_AUDIO, n_spk_p))

    if pam_outr_m and spk_2:
        # SPK-: -OUT_R (pin 14) → speaker pad 2
        ox, oy = pam_outr_m
        sx, sy = spk_2
        mid_y = 21.0  # different Y channel to avoid crossing SPK+
        parts.append(_seg(ox, oy, ox, mid_y, "B.Cu", W_AUDIO, n_spk_m))
        parts.append(_via_net(ox, mid_y, n_spk_m))
        parts.append(_seg(ox, mid_y, sx, mid_y, "F.Cu", W_AUDIO, n_spk_m))
        parts.append(_via_net(sx, mid_y, n_spk_m))
        parts.append(_seg(sx, mid_y, sx, sy, "B.Cu", W_AUDIO, n_spk_m))

    # ── PAM8403 +5V: chain on each row, single via per row
    # Top row (y=34.15): VDD(6) → MUTE(5) → PVDD(4), via from VDD(6)
    # VDD pin 6 at x=28.095, safe from BTN_RIGHT at x=31.0
    # PVDD pin 4 at x=30.635 too close to BTN_RIGHT for a direct via
    pam_vdd6 = _pad("U5", "6")
    pam_mute = _pad("U5", "5")
    pam_pvdd4 = _pad("U5", "4")
    if pam_vdd6 and pam_mute:
        parts.append(_seg(pam_vdd6[0], pam_vdd6[1],
                          pam_mute[0], pam_mute[1],
                          "B.Cu", W_PWR, n_5v))
    if pam_mute and pam_pvdd4:
        parts.append(_seg(pam_mute[0], pam_mute[1],
                          pam_pvdd4[0], pam_pvdd4[1],
                          "B.Cu", W_PWR, n_5v))
    if pam_vdd6:
        via_y = pam_vdd6[1] + 2.0  # outward from IC
        parts.append(_seg(pam_vdd6[0], pam_vdd6[1],
                          pam_vdd6[0], via_y, "B.Cu", W_PWR, n_5v))
        parts.append(_via_net(pam_vdd6[0], via_y, n_5v))

    # Bottom row (y=24.85): SHDN(12) → PVDD(13), via from PVDD(13)
    pam_shdn = _pad("U5", "12")
    pam_pvdd13 = _pad("U5", "13")
    if pam_shdn and pam_pvdd13:
        parts.append(_seg(pam_shdn[0], pam_shdn[1],
                          pam_pvdd13[0], pam_pvdd13[1],
                          "B.Cu", W_PWR, n_5v))
    if pam_pvdd13:
        via_y = pam_pvdd13[1] - 2.0  # outward from IC
        parts.append(_seg(pam_pvdd13[0], pam_pvdd13[1],
                          pam_pvdd13[0], via_y, "B.Cu", W_PWR, n_5v))
        parts.append(_via_net(pam_pvdd13[0], via_y, n_5v))

    # ── PAM8403 GND: PGND (pins 2, 15) + GND (pin 11) → GND
    # All GND pins route vias outward from IC center
    for pin in ["2", "15", "11"]:
        p = _pad("U5", pin)
        if p:
            px, py = p
            via_y = py + (2.0 if py > 30 else -2.0)  # outward
            parts.append(_seg(px, py, px, via_y, "B.Cu", W_PWR, n_gnd))
            parts.append(_via_net(px, via_y, n_gnd))

    # VREF (pin 8): internal analog reference output.
    # Ideally needs 100nF bypass cap to GND; no spare cap in BOM.
    # Left unconnected — internal reference still functions with higher noise.

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

    # ── USB CC pull-down resistors ──────────────────────────────
    # CC1 (A5) → R1 pad1, CC2 (B5) → R2 pad1
    # R1/R2 pad2 → GND vias
    n_gnd = NET_ID["GND"]
    n_cc1 = NET_ID["USB_CC1"]
    n_cc2 = NET_ID["USB_CC2"]

    usb_cc1 = _pad("J1", "A5")   # CC1 pad
    usb_cc2 = _pad("J1", "B5")   # CC2 pad
    r1_p1 = _pad("R1", "1")      # signal side
    r1_p2 = _pad("R1", "2")      # GND side
    r2_p1 = _pad("R2", "1")      # signal side
    r2_p2 = _pad("R2", "2")      # GND side

    # CC1 → R1: L-shaped route on B.Cu
    if usb_cc1 and r1_p1:
        parts.extend(_L(usb_cc1[0], usb_cc1[1], r1_p1[0], r1_p1[1],
                        "B.Cu", W_SIG, n_cc1, h_first=False))

    # CC2 → R2: L-shaped route on B.Cu
    if usb_cc2 and r2_p1:
        parts.extend(_L(usb_cc2[0], usb_cc2[1], r2_p1[0], r2_p1[1],
                        "B.Cu", W_SIG, n_cc2, h_first=False))

    # R1/R2 GND side → GND vias
    usb_gnd = _pad("J1", "A12")
    if usb_gnd:
        cc_gnd_via_y = usb_gnd[1] - 2
        if r1_p2:
            parts.append(_seg(r1_p2[0], r1_p2[1], r1_p2[0],
                              cc_gnd_via_y, "B.Cu", W_SIG, n_gnd))
            parts.append(_via_net(r1_p2[0], cc_gnd_via_y, n_gnd))
        if r2_p2:
            parts.append(_seg(r2_p2[0], r2_p2[1], r2_p2[0],
                              cc_gnd_via_y, "B.Cu", W_SIG, n_gnd))
            parts.append(_via_net(r2_p2[0], cc_gnd_via_y, n_gnd))

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
            ax = epx + 2 + i * 1.0   # DFM: was 0.6mm (via overlap)
        else:
            ax = epx - 2 - i * 1.0   # DFM: was 0.6mm (via overlap)
        # Nudge away from passive traces and previously used columns
        for _ in range(20):
            conflict = False
            for px in passive_trace_xs:
                if abs(ax - px) < 0.8:  # DFM: was 0.5mm
                    ax = px + 0.8 if ax > px else px - 0.8
                    conflict = True
                    break
            for ux in used_approach_xs:
                if abs(ax - ux) < 1.0:  # DFM: was 0.4mm (via overlap)
                    ax = ux - 1.0 if ax < ux else ux + 1.0
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
            stagger_y = 38.0 - bottom_stagger_idx * 1.0  # DFM: was 0.8mm
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

        # 6. GND via on opposite button pad (mini-via: low current)
        gp = b["gnd_pad"]
        if gp:
            parts.append(_via_net(gp[0], gp[1], n_gnd, size=0.7, drill=0.3))

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

    # C17 near IP5306: VIN decoupling, pad "1" -> VBUS via, pad "2" -> GND via
    c17_p1 = _pad("C17", "1")
    c17_p2 = _pad("C17", "2")
    if c17_p1:
        parts.append(_seg(c17_p1[0], c17_p1[1], c17_p1[0], c17_p1[1] - 2,
                          "B.Cu", W_SIG, NET_ID["VBUS"]))
        parts.append(_via_net(c17_p1[0], c17_p1[1] - 2, NET_ID["VBUS"]))
    if c17_p2:
        parts.append(_seg(c17_p2[0], c17_p2[1], c17_p2[0], c17_p2[1] + 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c17_p2[0], c17_p2[1] + 2, n_gnd))

    # C18 near IP5306: BAT decoupling, pad "1" -> BAT+ via, pad "2" -> GND via
    c18_p1 = _pad("C18", "1")
    c18_p2 = _pad("C18", "2")
    if c18_p1:
        parts.append(_seg(c18_p1[0], c18_p1[1], c18_p1[0], c18_p1[1] - 2,
                          "B.Cu", W_SIG, NET_ID["BAT+"]))
        parts.append(_via_net(c18_p1[0], c18_p1[1] - 2, NET_ID["BAT+"]))
    if c18_p2:
        parts.append(_seg(c18_p2[0], c18_p2[1], c18_p2[0], c18_p2[1] + 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c18_p2[0], c18_p2[1] + 2, n_gnd))

    # C19 near L1: VOUT decoupling, pad "1" -> +5V via, pad "2" -> GND via
    c19_p1 = _pad("C19", "1")
    c19_p2 = _pad("C19", "2")
    if c19_p1:
        parts.append(_seg(c19_p1[0], c19_p1[1], c19_p1[0], c19_p1[1] - 2,
                          "B.Cu", W_SIG, NET_ID["+5V"]))
        parts.append(_via_net(c19_p1[0], c19_p1[1] - 2, NET_ID["+5V"]))
    if c19_p2:
        parts.append(_seg(c19_p2[0], c19_p2[1], c19_p2[0], c19_p2[1] + 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c19_p2[0], c19_p2[1] + 2, n_gnd))

    # R16 IP5306 KEY pull-up: now handled in _power_traces()

    return parts


def _led_traces():
    """LED traces with inline current-limiting resistors.

    Circuit: +3V3 → R17/R18 (B.Cu) → via → LED1/LED2 (F.Cu) → GND
    R17 at (25.0, 65.0) B.Cu, LED1 at (25.0, 67.5) F.Cu
    R18 at (32.0, 65.0) B.Cu, LED2 at (32.0, 67.5) F.Cu
    """
    parts = []
    _init_pads()
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]

    pairs = [("R17", "LED1"), ("R18", "LED2")]
    for i, (r_ref, led_ref) in enumerate(pairs):
        r_p1 = _pad(r_ref, "1")   # B.Cu: x+0.95 (mirrored)
        r_p2 = _pad(r_ref, "2")   # B.Cu: x-0.95 (mirrored)
        led_p1 = _pad(led_ref, "1")  # F.Cu: x-0.95
        led_p2 = _pad(led_ref, "2")  # F.Cu: x+0.95
        if not (r_p1 and r_p2 and led_p1 and led_p2):
            continue

        # +3V3 via → R pad 1 (B.Cu, right side of resistor)
        via_3v3_y = r_p1[1] - 2.0
        parts.append(_via_net(r_p1[0], via_3v3_y, n_3v3))
        parts.append(_seg(r_p1[0], via_3v3_y, r_p1[0], r_p1[1],
                          "B.Cu", W_SIG, n_3v3))

        # R pad 2 (B.Cu, left side) → via → LED pad 1 (F.Cu, left side)
        # Same X column, use mid-point via at x=pad2 x
        mid_y = (r_p2[1] + led_p1[1]) / 2
        parts.append(_seg(r_p2[0], r_p2[1], r_p2[0], mid_y,
                          "B.Cu", W_SIG, 0))
        parts.append(P.via(r_p2[0], mid_y, size=0.8, drill=0.35, net=0))
        parts.append(_seg(led_p1[0], mid_y, led_p1[0], led_p1[1],
                          "F.Cu", W_SIG, 0))

        # LED pad 2 (F.Cu, right side) → GND via
        # Offset GND via horizontally RIGHT to avoid same-X column as +3V3 via
        gnd_via_x = led_p2[0] + 1.5
        parts.append(_seg(led_p2[0], led_p2[1], gnd_via_x, led_p2[1],
                          "F.Cu", W_SIG, n_gnd))
        parts.append(_via_net(gnd_via_x, led_p2[1], n_gnd))

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
