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
    ("SW8", enc(53, 5)),      # Y — DFM: shifted right (enc 53 not 52): pad1 left edge at 129.4mm clears FPC slot edge (128.5mm) by 0.9mm; right pads at x=136, clear J4 contact x=133.8 by 2.2mm
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

C1_POS = (122.0, 48.5)   # AMS1117 input cap — DFM: was 124.0 (pad/via too close to FPC slot)
C2_POS = (125.0, 62.5)   # AMS1117 output cap (amx, amy+7)
C3_POS = (69.5, 42.0)    # ESP32 decoupling 1 — DFM: was 68 (R3[1]@65.95 to C3[2]@67.05 gap=0.10mm danger). At 69.5: gap=2.60mm clear
C4_POS = (92.0, 42.0)    # ESP32 decoupling 2 — DFM: moved from 85 (pad1@85.95 hit U1[16]@85.715 at y=40)
C17_POS = (110.0, 35.0)  # IP5306 cap
C18_POS = (118.0, 55.0)  # IP5306 cap — DFM: moved to (118,55) below display trace zone (was 116 hit col_x; 131 hit SW8)
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

    The transform order matches get_pads() / the .kicad_pcb file:
      1. Generate local pad coords via gen(layer_char)
      2. Pre-rotate by `rot` degrees (same as _pre_rotate_element)
      3. Mirror X for B.Cu pads (same as _mirror_pad_x)
      4. Translate to board coordinates (cx, cy)

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
        lx, ly = float(at_m.group(1)), float(at_m.group(2))

        # Step 1: pre-rotate by footprint rotation angle
        if rot % 360 != 0:
            rot_rad = math.radians(rot)
            cos_r, sin_r = math.cos(rot_rad), math.sin(rot_rad)
            rx = lx * cos_r - ly * sin_r
            ry = lx * sin_r + ly * cos_r
        else:
            rx, ry = lx, ly

        # Step 2: mirror X for B.Cu
        if layer_char == "B":
            rx = -rx

        # Step 3: translate to absolute board position
        result[num_m.group(1)] = (cx + rx, cy + ry)
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
    # B.Cu stub from USB-C VBUS pad -> via at y=60 (clear of button channels y=62-71)
    # DFM: was y = usb_vbus[1]-2 = 66.25 which overlaps BTN_A F.Cu channel at y=66
    # DFM v2: VBUS via moved LEFT from x=136.3 (USB pad) to x=133.0 to avoid LCD approach
    # column vias at x=134.5..140.35 (pitch 0.45mm). B.Cu horiz stub LEFT, then vertical.
    vbus_via_y = 60.0   # fixed safe Y above all button channels
    vbus_via_x = 133.0  # LEFT of LCD approach column start (x=134.5), gap=1.25mm ✓
    # B.Cu horizontal LEFT from USB pad to via X, then vertical down to via Y
    parts.append(_seg(usb_vbus[0], usb_vbus[1], vbus_via_x, usb_vbus[1],
                       "B.Cu", W_PWR, n_vbus))
    parts.append(_seg(vbus_via_x, usb_vbus[1], vbus_via_x, vbus_via_y,
                       "B.Cu", W_PWR, n_vbus))
    parts.append(_via_net(vbus_via_x, vbus_via_y, n_vbus))
    # F.Cu horizontal to IP5306 area, then F.Cu vertical up to IP5306 pin Y
    # (avoid long B.Cu vertical crossing BAT+ horizontal at y~58.5)
    ip_vbus_via_x = ip_vbus[0] - 2
    # DFM: via placed 0.5mm above ip_vbus[1] to avoid U2[EP]@(110,42.5) exposed pad.
    # ip_vbus[1]=40.595. Via at y=40.595: U2[EP] top=41.1, gap=41.1-40.595-0.45=0.055mm < 0.10mm.
    # At y=40.095: gap_y=41.1-40.095-0.45=0.555mm OK.
    ip_vbus_via_y = ip_vbus[1] - 0.5  # DFM: was ip_vbus[1] (gap 0.055mm to U2[EP])
    parts.append(_seg(vbus_via_x, vbus_via_y, ip_vbus_via_x, vbus_via_y,
                       "F.Cu", W_PWR, n_vbus))
    parts.append(_seg(ip_vbus_via_x, vbus_via_y, ip_vbus_via_x, ip_vbus_via_y,
                       "F.Cu", W_PWR, n_vbus))
    parts.append(_via_net(ip_vbus_via_x, ip_vbus_via_y, n_vbus))
    # Short B.Cu stub: via -> ip_vbus pad (horizontal then vertical)
    parts.append(_seg(ip_vbus_via_x, ip_vbus_via_y, ip_vbus_via_x, ip_vbus[1],
                       "B.Cu", W_PWR, n_vbus))
    parts.append(_seg(ip_vbus_via_x, ip_vbus[1], ip_vbus[0], ip_vbus[1],
                       "B.Cu", W_PWR, n_vbus))

    # ── GND: vias to In1.Cu GND zone ──────────────────────────
    # GND vias near key components
    # ESP32 GND: thermal pad (pin 41) at (81.5, 29.96), size 3.9x3.9 → top edge at y=28.01.
    # Via at +2mm = y=31.96 is INSIDE pad (pad bottom at y=31.91).  Use +2.5mm → y=32.46
    # (gap = 32.46 - 31.91 - 0.45 = 0.10mm OK).
    gnd_via_positions = [
        (usb_gnd[0], usb_gnd[1] - 2),    # USB-C GND
        # DFM FIX: IP5306 GND via moved to x=112.4 (outside KEY span, clear of pads 2,3,4)
        # to avoid crossing the IP5306_KEY horizontal stub.
        (ip_ep[0] + 2.4, ip_ep[1] + 3),   # IP5306 GND (via at x=112.4, right of pads)
        (am_gnd[0], am_gnd[1] + 2),       # AMS1117 GND
        (esp_gnd[0], esp_gnd[1] + 3.0),   # DFM: was +2.5 (via ring at 32.01 hit pad bottom 31.91, gap=0.10mm danger). +3.0: via at 32.96, ring top=32.51, gap=0.60mm clear
        (jst_n[0] - 2, jst_n[1]),          # JST GND (offset AWAY from BAT+ pad)
    ]
    for gvx, gvy in gnd_via_positions:
        parts.append(_via_net(gvx, gvy, n_gnd))

    # B.Cu stubs from IC GND pads to vias
    parts.append(_seg(usb_gnd[0], usb_gnd[1], usb_gnd[0], usb_gnd[1] - 2,
                       "B.Cu", W_PWR, n_gnd))
    # IP5306 GND: DFM FIX: was straight vertical DOWN at x=ip_ep[0]=110.
    # This crossed IP5306_KEY horizontal (114.05,44.41)→(107.00,44.41) at (110,44.41).
    # Fix: horizontal stub RIGHT to x=115 (outside KEY span 107..114.05), then vertical.
    # DFM v2: EP pad right edge at x=111.70. Trace at x=110 is only 0.085mm from pads 2,3.
    # Move start point to x=112.4 (EP right edge + 0.5mm trace/2 + 0.2mm clearance).
    gnd_ep_start_x = ip_ep[0] + 2.4  # 110 + 2.4 = 112.4, clear of pads 2,3,4
    gnd_ep_safe_x = ip_ep[0] + 5.0  # 110 + 5 = 115, right of KEY span (107..114.05)
    # Vertical stub from EP pad down 1mm to clear pads, then horizontal, then vertical to via
    parts.append(_seg(ip_ep[0], ip_ep[1], ip_ep[0], ip_ep[1] + 1.0,
                       "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(ip_ep[0], ip_ep[1] + 1.0, gnd_ep_start_x, ip_ep[1] + 1.0,
                       "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(gnd_ep_start_x, ip_ep[1] + 1.0, gnd_ep_start_x, ip_ep[1] + 3,
                       "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(am_gnd[0], am_gnd[1], am_gnd[0], am_gnd[1] + 2,
                       "B.Cu", W_PWR, n_gnd))
    # ESP32 GND pad (pin 41) to GND via (+3.0mm to clear thermal pad bottom edge at 31.91)
    # DFM: was single vertical at x=81.5 (esp_gnd[0]). Gap to LCD_D7 B.Cu vert at x=81.905
    # was only 0.055mm (DANGER). Fix: horizontal LEFT to x=80.0, then vertical.
    gnd_offset_x = esp_gnd[0] - 1.5  # x=80.0 — left of LCD_D7 at x=81.905, gap=1.555mm
    parts.append(_seg(esp_gnd[0], esp_gnd[1], gnd_offset_x, esp_gnd[1],
                       "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(gnd_offset_x, esp_gnd[1], gnd_offset_x, esp_gnd[1] + 3.0,
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
    # DFM: SW pin at x=107, BAT pin also at x=107 — route LX LEFT 2mm first.
    # DFM FIX: was -1.0 (x=106). LX vert at x=106 crossed BAT+ horiz at y=43.13
    # (107→105.5). Also KEY horiz at y=44.41 spans x=107..114.05; x=106 is inside.
    # Fix: lx_col_x = ip_sw[0] - 2.0 = 105 (left of both BAT+ end 105.5 and KEY 107).
    lx_col_x = ip_sw[0] - 2.5   # x=104.5 — DFM: was -2.0 (x=105), gap to BAT+ at x=105.5 was 0mm. Now 0.50mm edge gap
    parts.append(_seg(ip_sw[0], ip_sw[1], lx_col_x, ip_sw[1],
                       "B.Cu", W_PWR, n_lx))
    parts.append(_seg(lx_col_x, ip_sw[1], lx_col_x, l1_2[1],
                       "B.Cu", W_PWR, n_lx))
    parts.append(_seg(lx_col_x, l1_2[1], l1_2[0], l1_2[1],
                       "B.Cu", W_PWR, n_lx))

    # ── BAT+ side of L1: L1 pin 1 to BAT+ zone ─────────────
    # DFM: offset 3.0mm (was 2.0). L1[1]@(111.7,52.5) pad size 1.4x3.4mm -> half_h=1.7.
    # Pad top = 52.5-1.7=50.8. Via at 2mm: y=50.5 is INSIDE pad (top 50.8).
    # At 3mm: y=49.5, via bottom=49.95, gap to pad top=0.85mm OK.
    # DFM clearance fix: via at (111.7,49.5) was 0.0mm from VBUS F.Cu vertical at x=111.0
    # (via left ring=111.25, VBUS trace right edge=111.25 → gap=0.0mm, shorting violation).
    # Fix: offset via 0.7mm RIGHT → bat_via_x=112.4: gap=112.4-0.45-111.25=0.70mm ✓.
    # Add B.Cu horizontal stub from L1[1] x=111.7 to via x=112.4 at bat_via_y.
    bat_via_x = l1_1[0] + 0.7   # 112.4 — right of VBUS trace at x=111.0
    bat_via_y = l1_1[1] - 3     # 49.5 — above L1[1] pad top (50.8mm) by 0.85mm
    parts.append(_via_net(bat_via_x, bat_via_y, n_bat))
    parts.append(_seg(l1_1[0], l1_1[1], l1_1[0], bat_via_y,
                       "B.Cu", W_PWR, n_bat))
    parts.append(_seg(l1_1[0], bat_via_y, bat_via_x, bat_via_y,
                       "B.Cu", W_PWR, n_bat))

    # ── KEY: IP5306 pin 5 -> R16 pull-up to +5V ─────────────
    # B.Cu route from KEY pin down to R16 area
    # DFM v2: KEY pin at (107, 44.405), pad 4 at (113, 44.405). Direct horizontal crosses pad 4.
    # Route with Z-shape: R16→down to safe Y, horizontal to KEY X, vertical to KEY pin.
    r16_p1 = _pad("R16", "1")
    r16_p2 = _pad("R16", "2")
    if r16_p2 and ip_key:
        # R16 pin 2 -> IP5306 KEY (pin 5) via B.Cu Z-route (avoid pad 4 at y=44.405)
        key_safe_y = ip_key[1] + 1.0  # y=45.405, above pad 4 bottom edge (44.70)
        parts.append(_seg(r16_p2[0], r16_p2[1], r16_p2[0], key_safe_y,
                           "B.Cu", W_SIG, n_key))
        parts.append(_seg(r16_p2[0], key_safe_y, ip_key[0], key_safe_y,
                           "B.Cu", W_SIG, n_key))
        parts.append(_seg(ip_key[0], key_safe_y, ip_key[0], ip_key[1],
                           "B.Cu", W_SIG, n_key))
    if r16_p1:
        # R16 pin 1 -> +5V via (pull-up for always-on)
        parts.append(_seg(r16_p1[0], r16_p1[1], r16_p1[0], r16_p1[1] + 2,
                           "B.Cu", W_SIG, n_5v))
        parts.append(_via_net(r16_p1[0], r16_p1[1] + 2, n_5v))

    # ── +3V3: AMS1117 output via outside +5V zone ─────────────
    # AMS1117 VOUT (pin 2) and tab (pin 4) are +3V3
    # Route to via outside +5V zone (x < 100)
    # DFM: v3_via at am_tab[0]-2 = 123.0, y=49.35 overlaps C1 pad1 at (122.95,48.5).
    # Fix: move via to am_tab[0] = 125.0 (same X as tab pad) to stay clear of C1 at x=122.95.
    v3_via_x = am_tab[0]   # 125.0 — same X as AMS1117 tab, clear of C1 (at x=122.95)
    v3_via_y = am_tab[1] - 3
    # B.Cu vertical from tab pad down to via
    parts.append(_seg(v3_via_x, am_tab[1], v3_via_x, v3_via_y,
                       "B.Cu", 0.4, n_3v3))
    parts.append(_via_net(v3_via_x, v3_via_y, n_3v3))
    # DFM FIX: removed F.Cu horizontal from x=125 to x=100.5 at y=49.35 — this trace
    # crossed the VBUS F.Cu vertical at x=111, gap=0mm (DANGER violation).
    # The AMS1117 tab via at (125, 49.35) connects directly to In2.Cu +3V3 zone which
    # covers the full board, so a second via at x=100.5 is redundant.
    # ESP32 +3V3: via near pin 2 with B.Cu stub
    # DFM: offset 2mm caused via at y=21.51 to overlap U1 pin1 at y=22.24 (gap=-0.17mm).
    # U1 pin1 at y=22.24, pad half-height=0.45mm → lower edge y=22.69.
    # Via radius=0.45 → need center-to-center ≥ 0.9mm from pin1 center.
    # Use 2.5mm offset: via at y=23.51-2.5=21.01, gap=22.24-21.01-0.45-0.45=0.33mm OK.
    esp_3v3 = _pad("U1", "2")  # pin 2 = +3V3 power input
    if esp_3v3:
        parts.append(_via_net(esp_3v3[0], esp_3v3[1] - 2.5, n_3v3))
        parts.append(_seg(esp_3v3[0], esp_3v3[1], esp_3v3[0],
                           esp_3v3[1] - 2.5, "B.Cu", 0.4, n_3v3))

    # ── BAT+: IP5306 -> JST battery connector ─────────────────
    # DFM: ip_bat at x=107 same as ip_sw — offset BAT+ via to separate column.
    # DFM FIX: was bat_col_x=ip_bat[0]+1=108 (inside IP5306_KEY horizontal x=107..114.05).
    # The BAT+ vertical at x=108 crossed KEY horizontal at y=44.41 → SHORT CIRCUIT.
    # Fix: route BAT+ LEFT to x=105.5 (outside KEY span to the left of x=107).
    bat_col_x = ip_bat[0] - 1.5   # x=105.5, left of KEY span (107..114.05)
    bat_via_y = ip_bat[1] + 3
    parts.append(_seg(ip_bat[0], ip_bat[1], bat_col_x, ip_bat[1],
                       "B.Cu", W_PWR, n_bat))
    parts.append(_seg(bat_col_x, ip_bat[1], bat_col_x, bat_via_y,
                       "B.Cu", W_PWR, n_bat))
    parts.append(_via_net(bat_col_x, bat_via_y, n_bat))
    # F.Cu horizontal to JST approach column between pull-up resistors R11(x=78) and R12(x=83).
    # DFM: was via at jst_p[0]=81 giving 0.10mm gap to R12[2] (borderline). Then tried 78
    # which hit R11[1]/R11[2] with gap=0.0mm. Use midpoint x=80.5 (0.60mm gap to both).
    bat_approach_x = 80.5  # DFM: midpoint between R11@78 and R12@83 (gap 0.60mm to each)
    parts.append(_seg(bat_col_x, bat_via_y, bat_approach_x, bat_via_y,
                       "F.Cu", W_PWR, n_bat))
    parts.append(_via_net(bat_approach_x, bat_via_y, n_bat))
    # B.Cu: horizontal to JST pad X, then vertical down to JST pad
    parts.append(_seg(bat_approach_x, bat_via_y, jst_p[0], bat_via_y,
                       "B.Cu", W_PWR, n_bat))
    parts.append(_seg(jst_p[0], bat_via_y, jst_p[0], jst_p[1],
                       "B.Cu", W_PWR, n_bat))

    # ── Power switch -> BAT+ junction ──────────────────────────
    # DFM FIX v1: was F.Cu long vertical at x=39.25, y=46.13..70.05.
    # This crossed D-pad button F.Cu horizontals at y=62,63,64,65.
    # Fix: use B.Cu for the long vertical — button channels are F.Cu so no conflict.
    # DFM FIX v2: SPK+ B.Cu vertical at x=39.5 (to SPK1 pad 1) overlaps BAT+ B.Cu at x=39.25.
    # Gap = |39.5-39.25| - (0.5+0.3)/2 = 0.25-0.40 = -0.15mm OVERLAP (y=46.135..52.5).
    # Fix: after the via at (sw_com[0], sw_via_y), switch to a separate column x=38.0
    # for the long B.Cu vertical.  Gap to SPK+ at x=39.5: 1.5-0.40=1.1mm CLEAR.
    # Note x=38.0 is clear of D-pad buttons (leftmost at x=9.0 area) and LED pads.
    BAT_COL_X = 38.0  # DFM: separate column for long B.Cu vertical (avoids SPK+ at x=39.5)
    sw_via_y = sw_com[1] - 2  # short B.Cu stub down from switch pad
    parts.append(_seg(sw_com[0], sw_com[1], sw_com[0], sw_via_y,
                       "B.Cu", W_PWR, n_bat))
    parts.append(_via_net(sw_com[0], sw_via_y, n_bat))
    # B.Cu horizontal from sw_com X to separate column, then long vertical down
    parts.append(_seg(sw_com[0], sw_via_y, BAT_COL_X, sw_via_y,
                       "B.Cu", W_PWR, n_bat))
    parts.append(_seg(BAT_COL_X, sw_via_y, BAT_COL_X, bat_via_y,
                       "B.Cu", W_PWR, n_bat))
    # F.Cu horizontal from BAT_COL_X to JST pad (at bat_via_y level)
    parts.append(_via_net(BAT_COL_X, bat_via_y, n_bat))
    parts.append(_seg(BAT_COL_X, bat_via_y, jst_p[0], bat_via_y,
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

    # Combined list for unified stagger handling.
    # DFM FIX: Sort by FPC pin y-position (fpy) so that approach column apx is assigned
    # in the same order as fpy.  This ensures each step-6 horizontal stub goes from
    # apx → fpx=133.15 at fpy without crossing any other signal's step-5 B.Cu vertical:
    # - Signals with lower fpy get lower apx.
    # - Their step-5 vertical stops at their (lower) fpy, so it does NOT extend down to
    #   the fpy of higher-rank signals — eliminating all step-6 crossing conflicts.
    # Build raw list, then sort, then assign sequential idx for apx.
    _raw_lcd = []
    for i, (gpio, fpc_pin) in enumerate(zip(data_gpios, fpc_data_pins)):
        _raw_lcd.append((gpio, fpc_pin, f"LCD_D{i}"))
    for gpio, net_name, fpc_pin in ctrl:
        _raw_lcd.append((gpio, fpc_pin, net_name))
    # Sort by fpy (FPC connector y position, ascending)
    _raw_lcd.sort(key=lambda e: (_fpc_pin(e[1]) or (0, 999))[1])
    # Build all_lcd with sequential idx for apx/bypass_y assignment
    all_lcd = [(idx, gpio, fpc_pin, net_name)
               for idx, (gpio, fpc_pin, net_name) in enumerate(_raw_lcd)]

    # Bottom-side stagger counter (pins at y ≈ 40 need Y separation)
    stagger_idx = 0

    for idx, gpio, fpc_pin, net_name in all_lcd:
        net = NET_ID[net_name]
        epx, epy = _esp_pin(gpio)
        fpx, fpy = _fpc_pin(fpc_pin)

        bypass_y = 5.0 + idx * 1.0   # DFM: was 0.5mm pitch (via overlap)
        # DFM FIX: unique staggered approach column per signal.
        # F.Cu horizontal from col_x to apx (unique per signal), via to B.Cu,
        # then B.Cu vertical straight down to FPC pin y, then B.Cu to FPC pad.
        # This avoids:
        #   - Collinear F.Cu overlap: each signal has unique bypass_y AND unique apx
        #     so F.Cu segments never share both x and y range simultaneously.
        #   - Collinear B.Cu overlap: each vertical at unique apx column.
        #   - No B.Cu horizontal stagger stubs that would cross other B.Cu verticals.
        #   - SW8 moved to enc(53,5)→PCB(133,32.5): SW8[2] now at x=136, clear of J4 contact x=133.8.
        # DFM v3: Pitch increased from 0.45mm to 0.70mm for via-to-track clearance.
        # At 0.45mm: trace_width=0.2mm (±0.1), via_dia=0.7mm (±0.35) → gap=0.45-0.1-0.35=0.0mm.
        # At 0.70mm: gap=0.70-0.1-0.35=0.25mm ≥ 0.254mm min via-to-track clearance ✓
        # DFM v4: Start position moved from 134.5 to 131.0 to avoid SD conflict at x=141.2.
        # apx range: 131.0 (idx=0) to 131.0+13*0.70=140.1 (idx=13), 0.70mm pitch.
        # Rightmost via right edge: 140.1+0.35=140.45mm, gap to SD=141.2-140.45=0.75mm ✓
        # B.Cu stubs from via@(apx,bypass_y) to FPC pad@(fpx, fpy): B.Cu vertical + horizontal.
        # No via at (apx, fpy): both seg5 and seg6 are B.Cu — no layer switch needed.
        apx = round(131.0 + idx * 0.70, 4)  # DFM v4: start=131.0, pitch=0.70mm for clearances
        col_x = 124.0 - idx * 1.1  # 1.1mm pitch avoids power verticals at x~117

        is_bottom = abs(epy - 40.0) < 1.0
        via_inside_gnd = False  # default; set True in via_inside_gnd escape branch
        escape_y = None         # set only when via_inside_gnd is True

        if is_bottom:
            # Bottom-side ESP32 pins: vertical stub UP to staggered Y
            # to avoid parallel overlapping horizontal stubs at y=40
            # DFM: stagger at ESP32 pin pitch midpoints (0.635mm offset)
            # ESP32 side pins at y=22.24+n*1.27; midpoints at 22.875+n*1.27
            # Start near y=38: 22.875 + 12*1.27 = 38.115
            stagger_y = 38.115 - stagger_idx * 1.27
            stagger_idx += 1

            # U1[41] GND thermal pad bbox: x=79.55..83.45, y=28.01..31.91
            # If epx is inside the GND pad X range AND stagger_y is inside the
            # GND pad Y range, the via would land inside the thermal pad.
            # Fix: first route horizontally OUT of the pad X range to a safe
            # escape_x (left edge - via_radius - clearance = 79.55-0.45-0.15=78.95),
            # then place the via at (escape_x, stagger_y).
            U1_GND_X1, U1_GND_X2 = 79.55, 83.45
            U1_GND_Y1, U1_GND_Y2 = 28.01, 31.91
            VIA_R_DEFAULT = 0.45   # default via size 0.9, radius 0.45

            via_inside_gnd = (U1_GND_X1 <= epx <= U1_GND_X2 and
                              U1_GND_Y1 <= stagger_y <= U1_GND_Y2)

            if via_inside_gnd:
                # DFM: stagger_y lands inside U1[41] GND thermal pad for
                # GPIO 10 (epx=83.175) and GPIO 11 (epx=81.905).
                # Route B.Cu horizontal escape to x just left of pad before via.
                # escape_x = pad_left - via_radius - clearance = 79.55-0.45-0.15 = 78.95
                escape_x = U1_GND_X1 - VIA_R_DEFAULT - 0.15   # 78.95
                # CROSSING FIX: the B.Cu escape horizontal at stagger_y crosses:
                #   - the ESP32 GND B.Cu vert at x=81.50 (y=29.96..32.96) when stagger_y in that range
                #   - the other GPIO's own B.Cu vert (GPIO10/11 cross each other's escape horizontals)
                # Fix: route B.Cu vert further UP from stagger_y to escape_y (above GND pad top=28.01),
                # then B.Cu horiz at escape_y to escape_x.
                # escape_y = 26.5 - escape_idx*1.0 so each GPIO gets a unique y above the pad.
                # stagger_idx already incremented above; for the first via_inside_gnd call: idx-1.
                # Use stagger_idx-1 (the value when this pin was processed) for escape_y staggering.
                escape_y = 26.5 - (stagger_idx - 1) * 1.0  # e.g. 26.5 for first, 25.5 for second
                # 1a. B.Cu vertical from pad up to stagger level (to separate from adjacent pins)
                parts.append(_seg(epx, epy, epx, stagger_y,
                                  "B.Cu", W_DATA, net))
                # 1b. B.Cu vertical further UP from stagger_y to escape_y (above GND pad top=28.01)
                parts.append(_seg(epx, stagger_y, epx, escape_y,
                                  "B.Cu", W_DATA, net))
                parts.append(_via_net(epx, escape_y, net))
                # 1c. F.Cu horizontal from epx to col_x at escape_y.
                # CROSSING FIX: was B.Cu horiz from epx to escape_x, then B.Cu escape_x to col_x.
                # GPIO10 (epx=83.175) B.Cu horiz at escape_y=20.50 from x=83.175→78.95 crossed
                # GPIO11 (LCD_D7) B.Cu vert at x=81.91 (y=19.50..29.23). F.Cu does not cross B.Cu verts.
                # Merged: single F.Cu horiz from epx to col_x (skip intermediate escape_x stop).
                parts.append(_seg(epx, escape_y, col_x, escape_y,
                                  "F.Cu", W_DATA, net))
                parts.append(_via_net(col_x, escape_y, net, size=0.7, drill=0.3))
            else:
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
        # For via_inside_gnd signals: col_x via is at escape_y (not stagger_y)
        if is_bottom and via_inside_gnd:
            from_y = escape_y
        elif is_bottom:
            from_y = stagger_y
        else:
            from_y = epy
        parts.append(_seg(col_x, from_y, col_x, bypass_y,
                          "B.Cu", W_DATA, net))
        parts.append(_via_net(col_x, bypass_y, net, size=0.7, drill=0.3))

        # 4. F.Cu horizontal across slot to unique approach column apx
        parts.append(_seg(col_x, bypass_y, apx, bypass_y,
                          "F.Cu", W_DATA, net))
        parts.append(_via_net(apx, bypass_y, net, size=0.7, drill=0.3))

        # 5. B.Cu vertical from bypass_y down to FPC pin Y level
        parts.append(_seg(apx, bypass_y, apx, fpy, "B.Cu", W_DATA, net))
        # DFM FIX: removed via at (apx, fpy) — both step 5 and step 6 are B.Cu,
        # no layer change needed. The via was causing via-pad overlaps with
        # J4 contact pads (x=136.200..137.500, y=25.75..45.25) for idx=4..8.

        # 6. B.Cu horizontal to FPC pad (short stub only)
        parts.append(_seg(apx, fpy, fpx, fpy, "B.Cu", W_DATA, net))

    # ── Power and GND connections to FPC (per ILI9488 datasheet) ──
    n_gnd = NET_ID["GND"]
    n_3v3 = NET_ID["+3V3"]

    # GND pins: 5, 16, 34, 35, 36, 37, 40(IM2)
    # DFM: L-shaped Manhattan routes to avoid diagonal crossing of J4 signal pads.
    # Route: horizontal from pad → (vx, py), then vertical → (vx, vy).
    # Offsets (ox, oy) from pad position (fpx=133.15, fpy):
    #   ox < 0 → go LEFT (vx < 133.15); ox > 0 → go RIGHT
    #   oy = 0 means via stays at same Y as pad (single horizontal segment)
    gnd_pins_offsets = [
        # CROSSING FIX: All LEFT-going stubs (ox<0) cross button B.Cu verts at x=130.30..131.80.
        # All RIGHT-going stubs (ox>0) cross LCD approach column B.Cu verts at x=134.50,134.90.
        # Fix: use vert-only stubs (ox=0) so no horizontal spans the forbidden x zones.
        # Via y values at x=133.15 are staggered ≥0.95mm apart to satisfy drill spacing.
        #
        # pin5:  fpy=27.75, oy=+3 → via at (133.15,30.75) [vert DOWN]
        # pin16: fpy=33.25, oy=+3 → via at (133.15,36.25) [vert DOWN]  gap from pin5=5.5mm ✓
        # pin34: fpy=42.25, oy=+4 → via at (133.15,46.25) [vert DOWN]  eliminates right-going horiz crossing LCD_RD
        # pin35: fpy=42.75, oy=+2 → via at (133.15,44.75) [vert DOWN]  gap from pin34=1.5mm ✓
        # pin36: keep as is (3,3) → via at (136.15,46.25) — already clear, not in crossings list
        # pin37: fpy=43.75, oy=+4 → via at (133.15,47.75) [vert DOWN]  gap from pin34=1.5mm ✓
        # pin40: fpy=45.25, oy=+4 → via at (133.15,49.25) [vert DOWN]  gap from pin37=1.5mm ✓
        (5, -0.65, 3),  # pin 5:  DFM v3: was ox=-0.3 (x=132.85), 0.05mm gap to LCD_WR@133.15. ox=-0.65 → x=132.50, gap=0.40mm ✓
        (16, -0.65, 3), # pin 16: DFM v3: was ox=-0.3 (x=132.85), 0.05mm gap to LCD_D5@133.15. ox=-0.65 → x=132.50, gap=0.40mm ✓
        (34, 0, 4),     # pin 34: vert DOWN to via at (133.15,46.25)
        (35, 0, 2),     # pin 35: vert DOWN to via at (133.15,44.75)
        (36, 3, 3),     # pin 36: via at (136.15,46.25) — horiz right then down (unchanged, no crossing)
        (37, 0, 4),     # pin 37: vert DOWN to via at (133.15,47.75)
        (40, 0, 4),     # pin 40 (IM2): vert DOWN to via at (133.15,49.25)
    ]
    for pin, ox, oy in gnd_pins_offsets:
        pos = _fpc_pin(pin)
        if pos:
            px, py = pos[0], pos[1]
            vx, vy = px + ox, py + oy
            parts.append(_via_net(vx, vy, n_gnd, size=0.7, drill=0.3))
            # L-route: horizontal first (exit J4 pad zone), then vertical
            if abs(oy) > 0.001:
                parts.append(_seg(px, py, vx, py, "B.Cu", 0.3, n_gnd))
                parts.append(_seg(vx, py, vx, vy, "B.Cu", 0.3, n_gnd))
            else:
                # oy=0: single horizontal segment
                parts.append(_seg(px, py, vx, vy, "B.Cu", 0.3, n_gnd))

    # +3V3 pins: 6(VDDI), 7(VDDA), 38(IM0=HIGH), 39(IM1=HIGH)
    # DFM: L-shaped Manhattan routes (same approach as GND stubs above).
    v33_pins_offsets = [
        # CROSSING FIX: pin6 RIGHT-going stub (ox=2) crossed LCD_CS V@134.50 and LCD_DC V@134.90.
        # pin7 LEFT-going stub (ox=-3.5) crossed button B.Cu verts at x=130.30..131.80.
        # pin38 LEFT-going stub (ox=-3) crossed button B.Cu verts.
        # Fix: use vert-only stubs (ox=0) for pin6, pin7, pin38.
        # Via y values at x=133.15 must be ≥0.95mm from all GND vias there:
        #   GND vias: 30.75, 36.25, 44.75, 46.25, 47.75, 49.25.
        # pin6:  fpy=28.25, oy=-4 → via at (133.15,24.25) — vert UP, gap from pin7=1.5mm ✓
        # pin7:  fpy=28.75, oy=-3 → via at (133.15,25.75) — vert UP, gap from pin6=1.5mm ✓, gap from GND pin5=5mm ✓
        # pin38: fpy=44.25, oy=-3 → via at (133.15,41.25) — vert UP, gap from GND pin16=5mm ✓, gap from pin35=3.5mm ✓
        # pin39: keep as is (3,3.5) → via at (136.15,48.25) — already clear, not in crossings list
        (6, 0, -4),     # pin 6 (VDDI): vert UP to via at (133.15,24.25)
        (7, 0, -3),     # pin 7 (VDDA): vert UP to via at (133.15,25.75)
        (38, 0, -3),    # pin 38 (IM0): vert UP to via at (133.15,41.25)
        (39, 3, 3.5),   # pin 39 (IM1): via at (136.15, 48.25) — horiz right then down (unchanged)
    ]
    for pin, ox, oy in v33_pins_offsets:
        pos = _fpc_pin(pin)
        if pos:
            px, py = pos[0], pos[1]
            vx, vy = px + ox, py + oy
            parts.append(_via_net(vx, vy, n_3v3, size=0.7, drill=0.3))
            # L-route: horizontal first, then vertical
            if abs(oy) > 0.001:
                parts.append(_seg(px, py, vx, py, "B.Cu", 0.3, n_3v3))
                parts.append(_seg(vx, py, vx, vy, "B.Cu", 0.3, n_3v3))
            else:
                parts.append(_seg(px, py, vx, vy, "B.Cu", 0.3, n_3v3))

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

        # DFM FIX: Complete SPI routing redesign to eliminate all crossing violations.
        # Old approach: B.Cu horizontal stub LEFT from ESP32 (x=71.25) to stub_x<70.45,
        # then B.Cu vertical up to bypass_y.  This caused:
        #   a) All B.Cu horizontal stubs crossed BTN_UP B.Cu vert at x=70.45 (all stubs span 70.45).
        #   b) SPI B.Cu vertical columns (x=67..68.5) crossed other SPI B.Cu horizontals at epy.
        #   c) Long F.Cu verticals (x=142..145, y=19..68.5) crossed each other's F.Cu bypass horizontals.
        #   d) Long F.Cu verticals crossed BTN_B F.Cu stub at y=30.65 (x=132..149) and FPC GND stubs.
        #
        # New routing strategy:
        #   Step 1: B.Cu stub RIGHT (71.25 → stub_x_r), avoids BTN_UP at x=70.45 (never crosses it).
        #   Step 2: via at stub_x_r.
        #   Step 3: B.Cu vertical UP from stub_x_r to bypass_y (above ESP32 pins, < y=19).
        #   Step 4: via at (stub_x_r, bypass_y).
        #   Step 5: F.Cu horizontal from stub_x_r to post_slot_x at bypass_y.
        #           bypass_y values differ per signal so no two F.Cu horizontals share y.
        #   Step 6: via at (post_slot_x, bypass_y).
        #   Step 7: B.Cu vertical DOWN from post_slot_x at bypass_y to stagger_y.
        #           post_slot_x is REVERSED (largest for i=0) so no F.Cu horizontal at bypass_y_j
        #           can cross B.Cu vert for i<j (B.Cu ≠ F.Cu anyway — different layers).
        #   Step 8: B.Cu L-route to SD pad.
        #
        # B.Cu stubs go RIGHT → never cross BTN_UP (x=70.45 < epx=71.25).
        # B.Cu verticals at stub_x_r (71.75..73.25) — all different x from each other and from
        #   LCD_BL (73.02), BTN_UP (70.45). These short B.Cu verts are above all button channels.
        # F.Cu horizontals at unique bypass_y (17..20) → no same-layer conflicts.
        # I2S_DOUT uses F.Cu at y=33.67 (x=26.825..87.25). bypass_y=17..20 → different y. CLEAR.
        # B.Cu verticals at post_slot_x (140,142,146,150) go down from bypass_y to stagger_y.
        # BTN_B F.Cu at y=30.65 (x=132..149): B.Cu ≠ F.Cu. CLEAR.
        # SW5/SW7 GND vias at (143.5,24.85)/(143.5,44.85): post_slot B.Cu verts avoid x=[143,144]
        #   by using x=140 and x=150 instead (gap ≥ 3.5mm to GND via ✓). CLEAR.

        # stub_x_r: short RIGHT stub column to separate from ESP32 pin column (x=71.25).
        # CROSSING FIX: old B.Cu H stubs from epx=71.25 to stub_x_r caused mutual crossings:
        #   SD_MISO H at epy=34.94 from 71.25→72.25 crossed SD_MOSI B.Cu vert at x=71.75.
        #   SD_CLK H at epy=33.67 from 71.25→72.75 crossed SD_MOSI(71.75) and SD_MISO(72.25) verts.
        #   SD_CS  H at epy=32.40 from 71.25→73.25 crossed all 3 verts + LCD_BL at x=73.02.
        # Fix: B.Cu horizontal stub from pad to stub_x_r, then via at stub_x_r.
        # No via at (epx, epy) — eliminates adjacent-pad overlap at ESP32 pin column.
        # stub_x_r values chosen so stub_x_r[3] = 72.95 < 73.02 (LCD_BL B.Cu vert) → CLEAR.
        # All stub_x_r values < 73.02 (LCD_BL B.Cu vert x). ✓
        stub_x_r = epx + 0.65 + i * 0.35  # 71.90, 72.25, 72.60, 72.95 for i=0,1,2,3

        # bypass_y: unique row ABOVE ESP32 pins (epy=32.4..36.21) and I2S F.Cu (y=33.67)
        # DFM fix: was 19+i (19,20,21,22). Row y=20 with post_slot_x=146 placed via@(146,20)
        # which overlapped SW5[2]@(145,20.65) with edge gap=-0.003mm.
        # Fix: shift all bypass rows up by 2 → 17+i (17,18,19,20). Via@(146,18): dist to
        # SW5[2] nearest corner (145.6,20.2)=2.24mm, edge=1.79mm ✓. All rows still well
        # above board top edge (y=0) and above ESP32 pins (epy≥32.4).
        bypass_y = 17.0 + i * 1.0   # 17, 18, 19, 20

        # post_slot_x: SD B.Cu verticals from bypass_y to stagger_y.
        # Must be OUTSIDE LCD approach column range (134.5..140.35 at 0.45mm pitch)
        # and outside GND via forbidden zone [142.75,144.25].
        # SD_MOSI(0) sdx=139.96 → post=141; SD_MISO(1) sdx=144.36 → post=146;
        # SD_CLK(2) sdx=142.16 → post=145; SD_CS(3) sdx=138.86 → post=148.
        # Pairwise gaps: (141,145)=4mm, (141,146)=5mm, (141,148)=7mm,
        #   (145,146)=1mm, (145,148)=3mm, (146,148)=2mm — all > 1.0mm ✓.
        # DFM: SD post_slot columns must be OUTSIDE LCD approach range (134.5..140.35)
        # and outside GND via forbidden zone [142.75,144.25].
        # Old values {0:137,1:146,2:140,3:142} had MOSI@137 and CLK@140 inside LCD range.
        # DFM v3: MOSI post=141 vs stagger via@139.96 has 0.140mm gap (via size 0.9).
        # Move MOSI post to 141.2 → gap = 1.24 - 0.9 = 0.34mm ✓
        _post_slot_map = {0: 141.2, 1: 146, 2: 145, 3: 148}
        post_slot_x = _post_slot_map[i]

        # stagger_y: approach Y for SD pad (below SD pads and MENU button SW13).
        # SW13 (5.1x5.1 tactile) at (142,63.2): pad3=(139,65.05), pad4=(145,65.05).
        # Old stagger_y=65.5+i (i=0→65.5): sdx via@(139.96,65.5) overlapped SW13[3]@(139,65.05)
        # with edge gap=-0.09mm.  New start=66.0: via@(139.96,66.0) gives edge=0.17mm ✓.
        stagger_y = 66.0 + i * 1.0  # 66.0, 67.0, 68.0, 69.0

        # Step 1: B.Cu horizontal stub RIGHT from ESP32 pad to stub_x_r column.
        # NO via at (epx, epy) — avoids via-in-pad violation on adjacent ESP32 pins.
        # Old approach: F.Cu stub + via at (epx,epy-0.8) [micro-stub] caused via at x=71.25
        #   to overlap adjacent ESP32 pins (pin pitch=1.27mm, via offset=0.8mm → only
        #   0.47mm to next pin center, far less than via_r+pad_r=0.45+0.45=0.90mm).
        # Fix: single B.Cu horizontal to stub_x_r, then via — no via at epx column.
        # Gap check: stub_x_r[1]=72.25 vs BTN_SELECT near_epx via(70.75,35.0):
        #   dist=sqrt((72.25-70.75)^2+(34.94-35.0)^2)=1.50mm >> 0.55mm min. CLEAR.
        parts.append(_seg(epx, epy, stub_x_r, epy, "B.Cu", W_DATA, net))
        parts.append(_via_net(stub_x_r, epy, net))

        # Step 3: B.Cu vertical UP to bypass row
        parts.append(_seg(stub_x_r, epy, stub_x_r, bypass_y, "B.Cu", W_DATA, net))
        parts.append(_via_net(stub_x_r, bypass_y, net))

        # Step 5: F.Cu horizontal across board past slot to unique post_slot column
        parts.append(_seg(stub_x_r, bypass_y, post_slot_x, bypass_y, "F.Cu", W_DATA, net))
        parts.append(_via_net(post_slot_x, bypass_y, net))

        # Step 7: B.Cu vertical DOWN to stagger row
        parts.append(_seg(post_slot_x, bypass_y, post_slot_x, stagger_y, "B.Cu", W_DATA, net))
        parts.append(_via_net(post_slot_x, stagger_y, net))

        # Step 8: F.Cu horizontal to SD pad X, then B.Cu vert to SD pad Y.
        # CROSSING FIX: old B.Cu horizontal from post_slot_x to sdx at stagger_y caused crossings:
        #   SD_MOSI B.Cu H at y=65.5 from x=145→139.96 crossed SD_MISO B.Cu vert at x=144,
        #   SD_CLK vert at x=143, SD_CS vert at x=142, and SD_MISO approach vert at x=144.36.
        # Fix: use F.Cu for the stagger horizontal. F.Cu does not cross B.Cu verts.
        parts.append(_seg(post_slot_x, stagger_y, sdx, stagger_y, "F.Cu", W_DATA, net))
        parts.append(_via_net(sdx, stagger_y, net))
        if abs(stagger_y - sdy) > 0.01:
            parts.append(_seg(sdx, stagger_y, sdx, sdy, "B.Cu", W_DATA, net))

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
        # DFM: was epx-1.5 (x=87.25). LCD_RD via at (86.985,34.305) was 0.688mm away
        # (pad edge gap=-0.212mm overlap). Offset to -3.0: via at (85.75,33.67),
        # dist=1.389mm, gap=0.489mm ✓
        via1_x = epx - 3.0
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
        mid_y = 22.5  # DFM: was 23.0 (too close to FPC slot top at y=23.5)
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
        # DFM: mid_y=23.5 (was 21.0). Via at (sx=20.5,21.0) overlapped SW1[2]@(21.0,21.65):
        # gap_y=|21.0-21.65|-0.45-0.45=-0.25mm OVERLAP. At 23.5: gap_y=0.95mm OK.
        # SPK+ is on F.Cu at mid_y=22.5, SPK- at 23.5 gives 1mm vertical separation OK.
        mid_y = 23.5  # DFM: was 21.0 (via@20.5,21.0 hit SW1[2] pad at y=21.65)
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
        via_y = pam_vdd6[1] + 2.0  # outward from IC (downward = larger y)
        parts.append(_seg(pam_vdd6[0], pam_vdd6[1],
                          pam_vdd6[0], via_y, "B.Cu", W_PWR, n_5v))
        parts.append(_via_net(pam_vdd6[0], via_y, n_5v))

        # DFM FIX: removed F.Cu bridge trace (net3 +5V at x=107 F.Cu crossed
        # 8+ LCD data bus horizontal traces at y=26..35 on F.Cu, gap=0mm).
        # PAM8403 +5V now supplied via a separate +5V In2.Cu zone island covering
        # the PAM8403 area (see _power_zones). The via above connects to In2.Cu.

    # Bottom row (y=24.85): SHDN(12) → PVDD(13), via from PVDD(13)
    pam_shdn = _pad("U5", "12")
    pam_pvdd13 = _pad("U5", "13")
    if pam_shdn and pam_pvdd13:
        parts.append(_seg(pam_shdn[0], pam_shdn[1],
                          pam_pvdd13[0], pam_pvdd13[1],
                          "B.Cu", W_PWR, n_5v))
    if pam_pvdd13:
        # DFM: offset 3.5mm (was 2.0). U5[13]@(29.365,32.2); via at 2mm y=30.2 overlapped
        # SW4[2]@(30.0,30.65) — same X, gap_x=-0.415mm OVERLAP.
        # At 3.5mm: via y=28.7, gap_y=|28.7-30.65|-0.45-0.45=1.95-0.9=1.05mm -> CLEAR.
        via_y = pam_pvdd13[1] - 3.5  # DFM: was 2.0 (overlapped SW4[2])
        parts.append(_seg(pam_pvdd13[0], pam_pvdd13[1],
                          pam_pvdd13[0], via_y, "B.Cu", W_PWR, n_5v))
        parts.append(_via_net(pam_pvdd13[0], via_y, n_5v))

    # B.Cu bridge: connect top row (PVDD4) to bottom row (PVDD13)
    # Route along LEFT edge of PAM8403 (via VDD6 column) to avoid
    # BTN_RIGHT approach column at x=31.0
    if pam_vdd6 and pam_pvdd13:
        # From VDD6 x-column down to PVDD13 y level
        parts.append(_seg(pam_vdd6[0], pam_vdd6[1],
                          pam_vdd6[0], pam_pvdd13[1],
                          "B.Cu", W_PWR, n_5v))
        # Horizontal to PVDD13 x
        if abs(pam_vdd6[0] - pam_pvdd13[0]) > 0.01:
            parts.append(_seg(pam_vdd6[0], pam_pvdd13[1],
                              pam_pvdd13[0], pam_pvdd13[1],
                              "B.Cu", W_PWR, n_5v))

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
    dp_col_x = dp_x + 1.5   # DFM fix: was +2 (gap to GND cap 0.575mm vs 0.075mm)
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
    dm_col_x = dm_x + 2.5   # DFM fix: was +3 (match dp shift)
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

    # CC1 → R1: route BELOW pad level to avoid crossing D+/D-/VBUS verticals.
    # DFM FIX: old route went UP from CC1 pad (x=81.25,y=68.255) then horizontal LEFT
    # to R1p1 at y=66 — this crossed D+ vert (x=80.25), D- vert (x=79.75), and CC2 horiz.
    # Fix: CC1 goes DOWN (increasing y) to y=70.5, then LEFT to r1p1 x, then UP to r1p1 y.
    # CC2 goes RIGHT at pad level to x=87.5 (past R2p1=86.95), DOWN to y=69.5, LEFT, UP to R2.
    # D+/D- go UP (decreasing y) and never reach y=69.5+, so no crossing with CC routes.
    if usb_cc2 and r2_p1:
        # CC2: RIGHT to safe x, DOWN to stagger y, LEFT to R2p1 x, UP to R2p1 y.
        cc2_safe_x = r2_p1[0] + 0.55   # 87.5 — right of R2p1=86.95 (pad half=0.65, via 0.45, margin=0.5)
        cc2_low_y = usb_cc2[1] + 1.25   # 69.5 — below USB pad cluster (avoids D+/D- range)
        parts.append(_seg(usb_cc2[0], usb_cc2[1], cc2_safe_x, usb_cc2[1],
                           "B.Cu", W_SIG, n_cc2))
        parts.append(_seg(cc2_safe_x, usb_cc2[1], cc2_safe_x, cc2_low_y,
                           "B.Cu", W_SIG, n_cc2))
        parts.append(_seg(cc2_safe_x, cc2_low_y, r2_p1[0], cc2_low_y,
                           "B.Cu", W_SIG, n_cc2))
        parts.append(_seg(r2_p1[0], cc2_low_y, r2_p1[0], r2_p1[1],
                           "B.Cu", W_SIG, n_cc2))

    if usb_cc1 and r1_p1:
        # CC1: DOWN past BTN_R vert end (y=72.5), then LEFT to R1p1 x, UP to R1p1 y.
        # CROSSING FIX: old cc1_low_y=70.5 crossed BTN_R B.Cu vert at x=76.25 (y=36.21..72.5).
        # CC1 H from (81.25,70.5)→(74.95,70.5) spanned x=76.25 which is in BTN_R vert range.
        # Fix: use cc1_low_y=73.5 (> BTN_R vert bottom y=72.5). Horiz at y=73.5 is below BTN_R. CLEAR.
        cc1_low_y = usb_cc1[1] + 5.25   # 73.5 — below BTN_R vert end (y=72.5), below CC2 stagger (69.5)
        parts.append(_seg(usb_cc1[0], usb_cc1[1], usb_cc1[0], cc1_low_y,
                           "B.Cu", W_SIG, n_cc1))
        parts.append(_seg(usb_cc1[0], cc1_low_y, r1_p1[0], cc1_low_y,
                           "B.Cu", W_SIG, n_cc1))
        parts.append(_seg(r1_p1[0], cc1_low_y, r1_p1[0], r1_p1[1],
                           "B.Cu", W_SIG, n_cc1))

    # R1/R2 GND side → GND vias (offset 1.5mm from pad to avoid via-in-pad)
    if r1_p2:
        gnd_via_y1 = r1_p2[1] - 1.5  # 1.5mm above pad
        parts.append(_seg(r1_p2[0], r1_p2[1], r1_p2[0],
                          gnd_via_y1, "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(r1_p2[0], gnd_via_y1, n_gnd))
    if r2_p2:
        gnd_via_y2 = r2_p2[1] - 1.5  # 1.5mm above pad
        parts.append(_seg(r2_p2[0], r2_p2[1], r2_p2[0],
                          gnd_via_y2, "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(r2_p2[0], gnd_via_y2, n_gnd))

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
            # DFM v3: was +2.3 (BTN_R approach at x=91.0, 0.025mm gap to USB_D- at x=91.25).
            # +2.8 → first col at x=91.55, gap to USB_D- = 0.30mm (USB_D- is w=0.2, edge at 91.35) ✓
            ax = epx + 2.8 + i * 1.0   # DFM: was 0.6mm pitch (via overlap)
        else:
            ax = epx - 2.8 - i * 1.0   # DFM: was 0.6mm pitch (via overlap)
        # Nudge away from passive traces and previously used columns.
        # Use expanding-step search to escape oscillation: when a candidate
        # is blocked from both sides (passive on one side, used on other),
        # step away from the ESP32 in increasing increments.
        step = 0
        for _ in range(40):
            conflict = False
            for px in passive_trace_xs:
                if abs(ax - px) < 1.5:  # DFM: 1.5mm clearance from passive traces
                    ax = px + 1.5 if ax > px else px - 1.5
                    conflict = True
                    break
            for ux in used_approach_xs:
                if abs(ax - ux) < 1.5:  # DFM: 1.5mm min separation between columns
                    # Always step AWAY from ESP32 pin to expand outward
                    step += 1.5
                    ax = (ux + step) if epx > CX else (ux - step)
                    conflict = True
                    break
            # DFM v3: check USB D+/D- verticals (defined below, but hoisted here for approach column check)
            for usb_x, margin in [(79.75, 0.50), (91.25, 0.50)]:
                if abs(ax - usb_x) < margin:
                    # Push away from USB vertical
                    ax = usb_x + margin if ax > usb_x else usb_x - margin
                    conflict = True
                    break
            if not conflict:
                break
        used_approach_xs.add(round(ax, 2))
        b["approach_x"] = round(ax, 2)

    # Compute via X: beyond signal pad (clear of pad edge).
    # Minimum offset = pad half-width (0.6) + via radius (0.45) + margin (0.10) = 1.15mm.
    # Use 1.2mm for 0.15mm margin.
    # Additional forbidden x ranges: B.Cu button traces run full vertical from ~y=20 to ~y=72,
    # so vx must not land in ANY B.Cu pad x column in that y range.
    # R17[2]@(24.05,65), R18[2]@(31.05,65), R17[1]@(25.95,65), R18[1]@(32.95,65) are B.Cu.
    # Forbidden x: pad_half_w(0.5) + trace_half_w(0.125) = 0.625mm either side.
    _led_forbidden_x = [
        (24.05, 0.625),   # R17[2] / LED1[1] column
        (25.95, 0.625),   # R17[1] column
        (31.05, 0.625),   # R18[2] / LED2[1] column
        (32.95, 0.625),   # R18[1] / LED2[2] column
    ]

    # LCD approach columns on B.Cu: apx = 134.5 + k*0.40 for k=0..17
    # Button B.Cu trace (w=0.25, hw=0.125) must clear LCD B.Cu trace (w=0.20, hw=0.10)
    # by ≥0.10mm: |vx - apx_k| ≥ 0.125 + 0.10 + 0.10 = 0.325mm (use 0.40mm margin)
    _lcd_approach_xs = [round(134.5 + k * 0.45, 4) for k in range(18)]  # DFM: match 0.45mm pitch
    # FPC connector entry zone: LCD step-6 B.Cu horizontal stubs go from apx_min=134.5
    # LEFT to fpx=133.15 at each fpy.  Any button B.Cu vertical in this x band will be
    # crossed by all those stubs.  Forbidden: 132.825 < vx < 134.175
    # (133.15 - 0.325 = 132.825, 134.5 - 0.325 = 134.175)
    # DFM: also forbid J4 contact pad zone (x=132.5..133.8, y=25.5..45.5).
    # Via (r=0.45) must not overlap J4 pad left edge at x=132.5:
    # vx + 0.45 >= 132.5 → vx >= 132.05 is forbidden.
    # Extend entry zone left to cover this: X1 = 132.5 - 0.45 - 0.15 = 131.90
    _FPC_ENTRY_X1 = 131.90            # DFM: was 132.825, extended left to clear J4 pad edge
    _FPC_ENTRY_X2 = 134.5  - 0.325   # 134.175

    # DFM v3: USB D+/D- B.Cu vertical columns (w=0.2, hw=0.1)
    # Button trace (w=0.25, hw=0.125) must clear USB trace by ≥0.09mm:
    # |vx - usb_x| ≥ 0.125 + 0.10 + 0.09 = 0.315mm
    # Use 0.50mm margin to ensure conflict detection triggers reliably.
    _usb_vertical_xs = [
        (79.75, 0.50),   # USB_D- vertical at x=79.75
        (91.25, 0.50),   # USB_D- vertical at x=91.25 (main conflict with BTN_R)
    ]

    def _vx_in_forbidden(vx):
        # Check if via X would cause B.Cu trace to pass through a forbidden pad column.
        # Threshold = pad_half_w + via_radius + clearance_margin = 0.5 + 0.45 + 0.10 = 1.05mm
        # (was hw+0.125=0.75mm which missed boundary cases like |32.2-32.95|=0.75 not < 0.75)
        for cx, hw in _led_forbidden_x:
            if abs(vx - cx) < 1.05:
                return True
        # LCD approach columns on B.Cu: button B.Cu trace must stay ≥0.40mm away
        for apx in _lcd_approach_xs:
            if abs(vx - apx) < 0.40:
                return True
        # DFM v3: USB D+/D- B.Cu verticals: button B.Cu trace must stay clear
        for usb_x, margin in _usb_vertical_xs:
            if abs(vx - usb_x) < margin:
                return True
        # FPC entry zone: x between FPC connector (133.15) and first approach column (134.5)
        # Any B.Cu vertical here is crossed by ALL LCD step-6 horizontal stubs
        if _FPC_ENTRY_X1 < vx < _FPC_ENTRY_X2:
            return True
        return False

    via_x_map = {}
    for b in btn_data:
        spx = b["spx"]
        is_right = b["bx"] >= CX
        if not is_right:
            base_vx = spx + 1.2  # DFM: 1.2mm > 0.6+0.45+0.10 margin (was 1.1mm=only 0.05mm)
        else:
            base_vx = spx - 1.2  # left of left pad
        # Check slot zone
        # DFM: old formula SLOT_X2+0.6+0.5=129.6 placed via touching SW8[1] right edge
        # at x=129.6 (pad_edge). Need via_center >= pad_edge + via_radius + clearance
        # = 129.6 + 0.45 + 0.15 = 130.2. Use offset 1.2: 128.5+0.6+1.2=130.3 (0.7mm margin).
        slot_margin = 0.6
        if (SLOT_X1 - slot_margin < base_vx < SLOT_X2 + slot_margin and
                SLOT_Y1 - slot_margin < b["spy"] < SLOT_Y2 + slot_margin):
            base_vx = SLOT_X2 + slot_margin + 1.2
        # DFM: hard cap for right-side buttons in J4 FPC contact band y=[25.5,45.5].
        # Via ring (r=0.45) must clear J4 left edge (x=136.2) by ≥0.15mm:
        # vx ≤ 136.2 - 0.45 - 0.15 = 135.60.
        # This cap is applied BEFORE forbidden-x loop so the loop can further
        # push vx left away from LCD approach columns near x=135.60.
        J4_PAD_X1 = 136.2
        J4_PAD_Y1, J4_PAD_Y2 = 25.5, 45.5
        is_right = b["bx"] >= CX
        if J4_PAD_Y1 <= b["spy"] <= J4_PAD_Y2 and is_right:
            max_vx = J4_PAD_X1 - 0.45 - 0.15   # = 135.60
            if base_vx > max_vx:
                base_vx = max_vx

        # Push vx away from forbidden x columns (R17/R18 B.Cu pad columns + LCD approach)
        step_dir = -1.0 if is_right else 1.0
        vx = base_vx
        for _ in range(40):
            if not _vx_in_forbidden(vx):
                break
            vx += step_dir * 0.5

        # DFM: enforce minimum center-to-center gap between button vx columns.
        # Trace width = 0.25mm (hw=0.125). For edge gap >= 0.15mm between parallel
        # B.Cu verticals: need center gap >= 0.125+0.15+0.125 = 0.40mm.
        # This also ensures via pad gap >= 0.15mm at chan_y (1mm Y spacing):
        # dist = sqrt(0.40^2 + 1.0^2) = 1.077mm, pad_gap = 1.077-0.9 = 0.177mm ✓
        MIN_VX_GAP = 0.40
        for _ in range(20):
            too_close = False
            for prev_vx in via_x_map:
                if abs(vx - prev_vx) < MIN_VX_GAP:
                    vx = prev_vx + MIN_VX_GAP * step_dir
                    too_close = True
            if not too_close:
                break
        # Slot zone safety: if gap enforcement pushed vx into the FPC slot zone,
        # push it back outside (to the RIGHT of slot).
        if (SLOT_X1 - slot_margin < vx < SLOT_X2 + slot_margin and
                SLOT_Y1 - slot_margin < b["spy"] < SLOT_Y2 + slot_margin):
            vx = SLOT_X2 + slot_margin + 1.2   # 130.3
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

        # 4-5. Route to ESP32 pad: B.Cu vertical + F.Cu horizontal.
        # DFM: do NOT place a via at (epx, stagger_y) or (epx, epy) because epx may
        # coincide with other ESP32 pad X columns (x=71.25 or x=74-88), causing
        # via-in-pad violations.  Instead, transition to B.Cu before reaching epx.
        #
        # DFM FIX for near_epx: the B.Cu stub from near_epx→epx must not cross any
        # B.Cu LCD signal vertical that runs through the near-ESP32 area.
        # LCD_BL B.Cu vert at x=73.02 (y=27.96..40.0): stub from near_epx→epx must
        # not span x=73.02 when stagger_y or epy is in [27.96, 40.0].
        # OLD: near_epx = epx+2 if epx<CX else epx-2 → stub goes INWARD toward LCD_BL.
        # FIX: near_epx goes OUTWARD (away from board center) so stub avoids LCD_BL:
        #   For left buttons (epx<CX): near_epx = epx - 2.0 (go LEFT, away from LCD_BL at 73.02)
        #     Exception: if epx > LCD_BL_x (73.02), going left would span LCD_BL.
        #     In that case push near_epx just right of LCD_BL: max(LCD_BL_x+0.5, epx-2.0)
        #     but only if that doesn't put near_epx>epx (stub would be reversed).
        #   For right buttons (epx>CX): near_epx = epx + 2.0 (go RIGHT, away from LCD_RD at 86.98)
        LCD_BL_X = 73.02  # LCD_BL B.Cu vert x (crosses left-side button stubs)
        is_bottom = abs(epy - 40.0) < 2.0
        if is_bottom:
            stagger_y = 35.5 - bottom_stagger_idx * 1.2  # DFM fix: 1.2mm step for 0.3mm via pad gap
            bottom_stagger_idx += 1
            # B.Cu vertical from approach column to stagger Y
            parts.append(_seg(ax, cy, ax, stagger_y, "B.Cu", W_SIG, net))
            parts.append(_via_net(ax, stagger_y, net))
            # F.Cu horizontal toward ESP32 pad (outward direction to avoid LCD_BL)
            # DFM FIX: was epx+2 if epx<CX else epx-2 (inward) — caused B.Cu stub crossing LCD_BL.
            # Fix: go OUTWARD (away from center):
            #   epx<CX: near_epx = epx-2.0, but if epx > LCD_BL_X (73.02), ensure stub
            #           [near_epx,epx] doesn't span LCD_BL_X. Push near_epx > LCD_BL_X+0.4.
            #   epx>CX: near_epx = epx+2.0 (go right, away from LCD_RD at 86.98).
            # BTN_UP B.Cu vert at x=70.45 (spans y=31.13..62): if B.Cu stub spans x=70.45
            # and stagger_y is in that y range, it crosses BTN_UP vert.
            # CROSSING FIX [42]: BTN_SELECT (epx=71.25) → near_epx=69.25 → stub [69.25,71.25]
            # spans BTN_UP vert at x=70.45. Fix: if stub would span BTN_UP, push near_epx > 70.45.
            BTN_UP_VX = 70.45  # BTN_UP B.Cu vert x (from crossing analysis)
            if epx < CX:
                _ne = epx - 2.0
                if _ne < LCD_BL_X < epx:
                    _ne = LCD_BL_X + 0.5 + (bottom_stagger_idx - 1) * 0.4  # DFM fix: stagger vias apart
                # Additional check: if stub [_ne,epx] spans BTN_UP vert, push _ne > BTN_UP_VX
                if _ne < BTN_UP_VX < epx:
                    _ne = BTN_UP_VX + 0.3  # 70.75 — just right of BTN_UP vert
                near_epx = _ne
            else:
                # DFM v3: BTN_R approach via@(91.0,37.48) vs near_epx via@(90.0,37.48): gap=0.1mm.
                # epx+2.0 would place near_epx at epx+2 (90→92 for BTN_R), but approach is at epx+2.8+i.
                # For BTN_R (i=0 for right-side buttons), approach≈91.55. Distance to near_epx=92:
                # 92-91.55=0.45mm gap (size 0.9 each) → insufficient. Use epx+3.0: 93-91.55=1.45, gap=0.55mm ✓
                near_epx = epx + 3.0   # DFM: was +2.0 (0.1mm gap to approach via)
            parts.append(_seg(ax, stagger_y, near_epx, stagger_y,
                              "F.Cu", W_SIG, net))
            parts.append(_via_net(near_epx, stagger_y, net))
            # B.Cu: horizontal to pad X, then vertical to pad Y (no extra via)
            parts.append(_seg(near_epx, stagger_y, epx, stagger_y,
                              "B.Cu", W_SIG, net))
            parts.append(_seg(epx, stagger_y, epx, epy,
                              "B.Cu", W_SIG, net))
        else:
            # B.Cu vertical to ESP32 Y level
            if abs(ax - epx) < 1.5:
                # DFM: approach column close to ESP32 pad — route B.Cu
                # directly to pad to avoid hole_to_hole violation
                parts.append(_seg(ax, cy, ax, epy, "B.Cu", W_SIG, net))
                if abs(ax - epx) > 0.01:
                    parts.append(_seg(ax, epy, epx, epy,
                                      "B.Cu", W_SIG, net))
            else:
                parts.append(_seg(ax, cy, ax, epy, "B.Cu", W_SIG, net))
                # Transition to F.Cu at approach column (no via at epx)
                parts.append(_via_net(ax, epy, net))
                # F.Cu horizontal OUTWARD (away from board center) to avoid LCD signal verts.
                # DFM FIX: was epx+2 if epx<CX else epx-2 (INWARD) — B.Cu stub spanned LCD_BL.
                # Fix: go OUTWARD:
                #   epx<CX: near_epx = epx-2.0 (go left, away from LCD_BL at x=73.02)
                #   epx>CX: near_epx = epx+2.0 (go right, away from LCD_RD at x=86.98)
                near_epx = epx - 2.0 if epx < CX else epx + 2.0
                parts.append(_seg(ax, epy, near_epx, epy,
                                  "F.Cu", W_SIG, net))
                parts.append(_via_net(near_epx, epy, net))
                # B.Cu short horizontal stub to pad
                parts.append(_seg(near_epx, epy, epx, epy,
                                  "B.Cu", W_SIG, net))

        # 6. GND via near opposite button pad (offset 1mm for DFM lead-to-hole)
        gp = b["gnd_pad"]
        if gp:
            # DFM: route GND via INWARD (toward board center) by 1.5mm to avoid
            # routing conflicts at gp[0] (e.g. SD_CS F.Cu vertical at x=145 for SW5/SW7).
            # Right-side buttons: gnd_pad at bx+3, move via 1.5mm LEFT (x-1.5).
            # Left-side buttons: gnd_pad at bx-3, move via 1.5mm RIGHT (x+1.5).
            if b["bx"] >= CX:
                gnd_via_x = gp[0] - 1.5
                # DFM: J4 FPC contact pads occupy x=132.5..133.8 (fpx=133.15 ± 0.65mm).
                # Via (size=0.7, r=0.35) must clear J4 pad left edge (x=132.5) by ≥0.15mm:
                # gnd_via_x + 0.35 + 0.15 ≤ 132.5 → gnd_via_x ≤ 132.0
                # Only apply when the via would ACTUALLY land inside the J4 contact band
                # (not for buttons far right where gnd_via_x > 133.8).
                J4_CONTACT_X2 = 133.15 + 0.65   # 133.80 (J4 pad right edge)
                J4_CONTACT_X1 = 133.15 - 0.65   # 132.50 (J4 pad left edge)
                MAX_GND_VX = J4_CONTACT_X1 - 0.35 - 0.15   # 132.00
                # Only cap if via would be within the J4 pad X band (left edge - tolerance)
                if J4_CONTACT_X1 - 0.35 <= gnd_via_x <= J4_CONTACT_X2 + 0.35:
                    gnd_via_x = MAX_GND_VX
            else:
                gnd_via_x = gp[0] + 1.5
            gnd_via_y = gp[1] + 0.5   # small Y offset to clear pad edge
            # L-shape: horizontal inward, then short segment to via
            parts.append(_seg(gp[0], gp[1], gnd_via_x, gp[1],
                              "F.Cu", W_SIG, n_gnd))
            parts.append(_seg(gnd_via_x, gp[1], gnd_via_x, gnd_via_y,
                              "F.Cu", W_SIG, n_gnd))
            parts.append(_via_net(gnd_via_x, gnd_via_y, n_gnd, size=0.7, drill=0.3))

    # Shoulder button BTN_L (B.Cu, rotated 90°)
    net_l = NET_ID["BTN_L"]
    # Use actual pad position instead of button center
    sl_pad = _pad("SW11", "3")  # signal pad (inner side toward board center)
    sx_l = sl_pad[0] if sl_pad else SHOULDER_L[1][0]
    sy_l = sl_pad[1] if sl_pad else SHOULDER_L[1][1]
    epx_l, epy_l = _esp_pin(35)
    # DFM: was 58+len(btn_data)=68, collided with BTN_X chan_y=62+6=68 (F.Cu horizontal conflict).
    # Use 74.0 (below all face button channels 62-71) to avoid F.Cu horizontal overlap.
    chan_y_l = 74.0

    # B.Cu vertical from shoulder button pad to channel
    parts.append(_seg(sx_l, sy_l, sx_l, chan_y_l, "B.Cu", W_SIG, net_l))
    parts.append(_via_net(sx_l, chan_y_l, net_l))
    # F.Cu horizontal to approach column
    # DFM FIX: was approach_l = epx_l - 2 = 69.25.
    # B.Cu vert at x=69.25 (74.0→37.48) crossed +3V3 horiz at y=42 (x=68.45..70.45): 68.45<69.25<70.45.
    # B.Cu horiz at (69.25,37.48)→(71.25,37.48) crossed BTN_UP vert at x=70.45: 69.25<70.45<71.25.
    # Fix: approach_l = epx_l + 1.0 = 72.25 (RIGHT of BTN_UP at x=70.45 and +3V3 end at x=70.45).
    # B.Cu vert at x=72.25: +3V3 horiz ends at x=70.45 < 72.25 → CLEAR; BTN_UP at 70.45 < 72.25 → CLEAR.
    # B.Cu horiz (72.25,37.48)→(71.25,37.48): BTN_UP at x=70.45 < 71.25 → NOT in span → CLEAR.
    # LCD_BL vert at x=73.02 > 72.25 → NOT in stub span [71.25,72.25] → CLEAR.
    approach_l = epx_l + 1.0   # DFM FIX: was epx_l-2=69.25 (crossed +3V3 and BTN_UP); now 72.25
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
    # DFM: was 1mm offset — via ring at 14.15-0.45=13.70, pad right=13.15+0.45=13.60, gap=0.10mm danger.
    # Use 1.5mm: via at 14.65, ring left=14.20, pad right=13.60, gap=0.60mm clear.
    sl_gnd = _pad("SW11", "2")
    if sl_gnd:
        gnd_via_x = sl_gnd[0] + 1.5  # DFM: was 1.0mm (gap=0.10mm danger)
        parts.append(_seg(sl_gnd[0], sl_gnd[1], gnd_via_x, sl_gnd[1],
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(gnd_via_x, sl_gnd[1], n_gnd))

    # Shoulder button BTN_R (B.Cu, rotated 90°)
    # SW12 at enc(65, 32) = (145, 5.5) on the right side of the board.
    # Route: pad 3 (inner signal pad) -> B.Cu down -> F.Cu across -> ESP32 GPIO19
    # GPIO mapping: BTN_R = GPIO 19 (epx=88.75, epy=37.48) — RIGHT side of ESP32.
    # Old bug: used _esp_pin(36) (SD_MOSI position, left ESP32 column) → wrong pin.
    # Fix: use _esp_pin(19) → routes to right-side ESP32 column, no conflict with
    #   SD_MOSI vias at x=71.9..72.95 or BTN_X/BTN_B stagger vias at x=73..76.
    net_r = NET_ID["BTN_R"]
    sr_pad = _pad("SW12", "3")  # signal pad (inner side toward board center)
    epx_r, epy_r = _esp_pin(19)   # GPIO 19 = BTN_R (right-side ESP32 pin)
    if sr_pad:
        sx_r, sy_r = sr_pad
        # DFM FIX: was chan_y_l + 1.0 = 75.0 (board edge! board height=75mm).
        # Copper at y=75.0 violates edge clearance (need >=0.5mm from Edge.Cuts).
        # hole_to_hole FIX: chan_y_r=72.5 placed via at approach column too close to J1 S4.
        # Use chan_y_r = chan_y_l - 2.5 = 71.5mm (was 74.0-2.5).
        # DFM via-pad fix: chan_y_r=71.5 placed BTN_R channel via at (sx_r=146.85, 71.5)
        # which overlapped U6[11]@(147.76,72.1) [SD card shield pad] with edge=-0.14mm.
        # Fix: use chan_y_r=69.5 → via@(146.85,69.5): U6[11] edge=1.18mm ✓.
        chan_y_r = chan_y_l - 4.5  # 69.5mm — clears board edge AND U6 shield pad

        # B.Cu vertical from shoulder-R pad down to channel
        parts.append(_seg(sx_r, sy_r, sx_r, chan_y_r, "B.Cu", W_SIG, net_r))
        parts.append(_via_net(sx_r, chan_y_r, net_r))
        # F.Cu horizontal LEFT across board to approach column just RIGHT of GPIO19 (epx=88.75)
        # approach_r = epx_r + 1.5 = 90.25: right of GPIO19, avoids any left-side conflicts.
        # GPIO19 is on the RIGHT ESP32 column (x=88.75), away from SD_MOSI/BTN vias at x<77.
        # DFM v2: was +2.0 (x=90.75), 0.085mm gap to VBUS/LCD traces. +2.25 → x=91.0, gap=0.34mm ✓
        # DFM v3: +2.25 (x=91.0) conflicts with USB_D- vertical at x=91.25 (gap=0.025mm).
        # USB_D- right edge at 91.35, need gap >= 0.09mm: approach_r >= 91.35 + 0.09 + 0.125 = 91.565.
        # Use +2.85 → x=91.60, gap to USB_D- = 0.25mm ✓
        approach_r = epx_r + 2.85  # 91.60 — right-side approach column, clear of USB_D- vertical
        parts.append(_seg(sx_r, chan_y_r, approach_r, chan_y_r,
                           "F.Cu", W_SIG, net_r))
        parts.append(_via_net(approach_r, chan_y_r, net_r))
        # B.Cu vertical UP from channel to GPIO19 pin level
        parts.append(_seg(approach_r, chan_y_r, approach_r, epy_r,
                           "B.Cu", W_SIG, net_r))
        # Layer hop at approach_r column to switch from B.Cu to F.Cu
        parts.append(_via_net(approach_r, epy_r, net_r))
        # F.Cu horizontal LEFT to near_epx_r (just right of pad for B.Cu stub clearance)
        # DFM v3: was epx_r+1.25=90.0, gap to approach_r@91.0 = 1.0mm (via spacing=0.1mm FAIL).
        # approach_r now at 91.60, need via gap >= 0.15mm: |near_epx_r - approach_r| >= 0.9+0.15=1.05mm.
        # near_epx_r <= 91.60 - 1.05 = 90.55 OR >= 91.60 + 1.05 = 92.65.
        # Use epx_r+1.7=90.45 (left option, shorter hop to pad).
        near_epx_r = epx_r + 1.7  # 90.45 — via gap to approach_r = 1.15mm (spacing=0.25mm ✓)
        parts.append(_seg(approach_r, epy_r, near_epx_r, epy_r,
                           "F.Cu", W_SIG, net_r))
        parts.append(_via_net(near_epx_r, epy_r, net_r))
        # B.Cu short stub LEFT to ESP32 GPIO19 pad
        parts.append(_seg(near_epx_r, epy_r, epx_r, epy_r,
                           "B.Cu", W_SIG, net_r))
        # GND via on outer pad of SW12
        # DFM: was 1mm offset — same issue as SW11 (via ring gap=0.10mm to pad, danger).
        # Use 1.5mm: gap=0.60mm clear.
        sr_gnd = _pad("SW12", "2")
        if sr_gnd:
            gnd_via_x_r = sr_gnd[0] + 1.5  # DFM: was 1.0mm (gap=0.10mm danger)
            parts.append(_seg(sr_gnd[0], sr_gnd[1], gnd_via_x_r, sr_gnd[1],
                              "B.Cu", W_SIG, n_gnd))
            parts.append(_via_net(gnd_via_x_r, sr_gnd[1], n_gnd))

    return parts


def _passive_traces():
    """Traces for passive components using exact pad positions.

    Power connections (+3V3, GND, +5V) use vias to inner layer zones.
    """
    parts = []
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]
    n_5v = NET_ID["+5V"]

    # Button pull-up resistors: +3V3 via above pad with sufficient clearance.
    # B.Cu pad "2" (mirrored) at (rx-0.95, ry).  Via radius=0.45, pad half-h=0.65mm.
    # Minimum offset = 0.45+0.65+0.10=1.20mm.  Use 1.40mm for 0.25mm margin.
    for i, ref in enumerate(PULL_UP_REFS):
        rx = 43 + i * 5
        ry = 46
        # DFM: was 1.0mm offset (via overlapped pad edge by 0.1mm)
        parts.append(_seg(rx - 0.95, ry, rx - 0.95, ry - 1.4,
                          "B.Cu", W_SIG, n_3v3))
        parts.append(_via_net(rx - 0.95, ry - 1.4, n_3v3))

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
    # DFM: was LEFT 2mm via at x=68.45 → overlaps C3[2] GND pad at (68.55,42.0)
    # (C3[2] bbox x=68.05..69.05, via extends 68.0..68.9 = 0.85mm X overlap).
    # DFM v2: was UP 2.5mm via at (70.45,39.5) → overlaps U1[27]@(71.25,38.75)
    # (U1[27] bbox x=70.5..72.0, y=38.3..39.2; via x=70.0..70.9 overlaps pad x).
    # Fix: route DOWN 2mm then LEFT to x=67.0, place via at (67.0, 44.0).
    # Route: (70.45,42) → (70.45,44) → (67.0,44) → via@(67.0,44)
    # Clearances: via@(67.0,44.0) r=0.45 — no pads within 1.5mm of this point.
    # Segment y=44.0 x=67..70.45 — no pads in this region.
    c3_p1 = _pad("C3", "1")
    if c3_p1:
        # CROSSING FIX [44]: old route went DOWN then LEFT to via at (67.0, 44.0).
        # The B.Cu horiz at y=44 from x=70.45→67.0 crossed BTN_DOWN B.Cu vert at x=67.45
        # (67.0 < 67.45 < 70.45, and y=44 in BTN_DOWN vert span y=29.86..63.0).
        # Fix: use vert-only stub — route B.Cu DOWN from pad to via at same x.
        # Via at (c3_p1[0]=70.45, 44.0) — same x as pad, no horizontal → no crossing.
        via_y = c3_p1[1] + 2.0   # 42.0 + 2.0 = 44.0 (below C3, clear of pads above)
        parts.append(_seg(c3_p1[0], c3_p1[1], c3_p1[0], via_y,
                          "B.Cu", W_SIG, n_3v3))
        parts.append(_via_net(c3_p1[0], via_y, n_3v3))
    # C3 pad "2" -> GND via
    c3_p2 = _pad("C3", "2")
    if c3_p2:
        parts.append(_seg(c3_p2[0], c3_p2[1], c3_p2[0], c3_p2[1] - 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c3_p2[0], c3_p2[1] - 2, n_gnd))

    # C4 near ESP32: pad "1" -> +3V3 via (DFM: was 1.0mm, overlapped pad edge by 0.1mm)
    c4_p1 = _pad("C4", "1")
    c4_p2 = _pad("C4", "2")
    if c4_p1:
        parts.append(_seg(c4_p1[0], c4_p1[1], c4_p1[0], c4_p1[1] - 1.4,
                          "B.Cu", W_SIG, n_3v3))
        parts.append(_via_net(c4_p1[0], c4_p1[1] - 1.4, n_3v3))
    if c4_p2:
        parts.append(_seg(c4_p2[0], c4_p2[1], c4_p2[0], c4_p2[1] - 2,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c4_p2[0], c4_p2[1] - 2, n_gnd))

    # C1 AMS1117 input: pad "1" -> +5V via, pad "2" -> GND via
    # DFM: 2.5mm offset (was 2mm) to avoid via-in-pad with 0805 (1.3mm tall pad)
    c1_p1 = _pad("C1", "1")
    c1_p2 = _pad("C1", "2")
    if c1_p1:
        parts.append(_seg(c1_p1[0], c1_p1[1], c1_p1[0], c1_p1[1] - 2.5,
                          "B.Cu", W_SIG, n_5v))
        parts.append(_via_net(c1_p1[0], c1_p1[1] - 2.5, n_5v))
    if c1_p2:
        parts.append(_seg(c1_p2[0], c1_p2[1], c1_p2[0], c1_p2[1] - 2.5,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c1_p2[0], c1_p2[1] - 2.5, n_gnd))

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
    # DFM: 2.5mm offset (was 2mm) to avoid via overlap with IP5306 pads
    c18_p1 = _pad("C18", "1")
    c18_p2 = _pad("C18", "2")
    if c18_p1:
        parts.append(_seg(c18_p1[0], c18_p1[1], c18_p1[0], c18_p1[1] - 2.5,
                          "B.Cu", W_SIG, NET_ID["BAT+"]))
        parts.append(_via_net(c18_p1[0], c18_p1[1] - 2.5, NET_ID["BAT+"]))
    if c18_p2:
        parts.append(_seg(c18_p2[0], c18_p2[1], c18_p2[0], c18_p2[1] + 2.5,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(c18_p2[0], c18_p2[1] + 2.5, n_gnd))

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
        # DFM: mid_y=66.25 (between R_pad bottom at 65.65 and LED1_top at 66.85).
        # R17[2]/R18[2] bottom edge = 65+0.65=65.65. LED1[1]/LED2[1] top edge = 67.5-0.65=66.85.
        # Via r=0.40: need 65.65+0.40+0.10=66.15 < via_y < 66.85-0.40-0.10=66.35. Use 66.25.
        # 1.5mm offset gave via at y=66.5 which overlapped LED1[1] top (66.85-66.5-0.4=-0.05mm).
        mid_y = r_p2[1] + 1.25  # DFM: was 1.5mm (via@66.5 overlapped LED1 top edge 66.85)
        parts.append(_seg(r_p2[0], r_p2[1], r_p2[0], mid_y,
                          "B.Cu", W_SIG, 0))
        parts.append(P.via(r_p2[0], mid_y, size=0.8, drill=0.35, net=0))
        parts.append(_seg(led_p1[0], mid_y, led_p1[0], led_p1[1],
                          "F.Cu", W_SIG, 0))

        # LED pad 2 (F.Cu, right side) → GND via
        # Offset GND via horizontally RIGHT to avoid same-X column as +3V3 via.
        # DFM fix: was +1.5mm → LED2 GND via at (34.45,67.5) was only 0.175mm from
        # BTN_SELECT B.Cu trace at x=35.2 (gap=0.175mm < 0.2mm required clearance).
        # Reduce to +1.0mm: via at (33.95,67.5), gap to trace = 35.075-34.40=0.675mm ✓.
        # DFM v2: was +1.0mm (x=33.95), 0.075mm gap to VBUS trace. +0.7mm → x=33.65, gap=0.40mm ✓
        gnd_via_x = led_p2[0] + 0.7
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

    # +5V zone on In2.Cu — power management area (IP5306/AMS1117)
    # Start at x=105 to keep R19 pull-up +3V3 vias (x≈103) outside
    v5_pts = [
        (105, 35), (140, 35), (140, 65), (105, 65),
    ]
    parts.append(P.zone_fill("In2.Cu", v5_pts, NET_ID["+5V"], "+5V",
                             priority=1))

    # +5V zone island for PAM8403 audio amp (x=20..42, y=24..42)
    # DFM FIX: replaces the F.Cu bridge trace that crossed 8+ LCD data bus
    # horizontal traces at y=26..35 F.Cu (caused 0mm pad spacing violations).
    # PAM8403 VDD6 via connects to this In2.Cu island.
    v5_pam_pts = [
        (20, 24), (42, 24), (42, 42), (20, 42),
    ]
    parts.append(P.zone_fill("In2.Cu", v5_pam_pts, NET_ID["+5V"], "+5V",
                             priority=2))

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
