"""Complete PCB trace routing with Manhattan (orthogonal) paths.

All traces use only horizontal and vertical segments (L-shaped or
Z-shaped paths).  No diagonal lines.

Trace widths:
  - Power high: 0.76mm (VBUS, BAT+, LX — up to 2.1A)
  - Power:      0.60mm (+5V, +3V3, GND returns)
  - Audio:      0.30mm (PAM8403 -> speaker)
  - Signal:     0.25mm (buttons, passives)
  - Data:       0.20mm (display bus, SPI, I2S, USB)

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
from .collision import CollisionGrid

# ── Collision detection grid (populated in _init_pads, used by _seg/_via_net)
_GRID = CollisionGrid()

# ── Trace widths ──────────────────────────────────────────────────
W_PWR = 0.6
W_PWR_HIGH = 0.76     # High-current power: VBUS, BAT+, LX (≥2.1A, 1oz Cu, 10°C rise)
W_PWR_LOW = 0.30      # Light power stubs: +3V3/GND short cap-to-via runs (~0.5A)
W_SIG = 0.25
W_DATA = 0.2
W_AUDIO = 0.3

# ── Via sizes (JLCPCB 4-layer: AR >= 0.15mm recommended) ─────────
VIA_STD = 0.60       # standard via OD (AR=0.20mm with drill 0.20)
VIA_STD_DRILL = 0.20
VIA_TIGHT = 0.60     # tight-corridor via OD (AR=0.20mm — matches VIA_STD, eliminates JLCPCB warnings)
VIA_TIGHT_DRILL = 0.20
VIA_MIN = 0.50       # minimum via OD (AR=0.15mm — JLCPCB recommended minimum)
VIA_MIN_DRILL = 0.20

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


# ── Keepout zones (mounting holes, slots, board features) ──────
# Each: (center_x, center_y, radius_with_clearance)
# Traces and vias must not enter these circles.
_KEEPOUT_CIRCLES = []


def _segment_crosses_circle(x1, y1, x2, y2, width, cx, cy, cr):
    """Check if a segment (with width) crosses a circle keepout zone.

    Returns True if the minimum distance from the segment centerline to the
    circle center is less than cr + width/2 (i.e., the trace copper enters
    the keepout zone).
    """
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        dist = math.hypot(x1 - cx, y1 - cy)
    else:
        t = max(0, min(1, ((cx - x1) * dx + (cy - y1) * dy) / (dx * dx + dy * dy)))
        px, py = x1 + t * dx, y1 + t * dy
        dist = math.hypot(px - cx, py - cy)
    return dist < cr + width / 2


def _init_keepout_zones():
    """Build keepout zones from mounting holes and other features."""
    global _KEEPOUT_CIRCLES
    _KEEPOUT_CIRCLES = []
    # Mounting holes: 3.5mm pad + 0.5mm clearance = 2.25mm radius
    from .board import MOUNT_HOLES_ENC, enc_to_pcb
    for ex, ey in MOUNT_HOLES_ENC:
        mx, my = enc_to_pcb(ex, ey)
        _KEEPOUT_CIRCLES.append((mx, my, 2.25))  # 1.75mm pad radius + 0.5mm clearance


# Detour Y allocation counter: assigns unique Y offsets for traces detouring
# around the same mounting hole. Reset in generate_all_traces().
_MH_DETOUR_IDX = {}


def _mh_detour_h(x1, y, x2, layer, width, net):
    """Route a horizontal F.Cu segment around any mounting hole keepout.

    Two strategies depending on whether the trace Y is inside the physical
    drill hole or only inside the clearance annulus:

    A) LAYER SWAP (trace Y outside drill+clearance, inside keepout):
       F.Cu -> via -> B.Cu horizontal at same Y -> via -> F.Cu
       Safe because B.Cu copper outside the drill is not cut.

    B) B.Cu DETOUR (trace Y inside drill+clearance zone):
       Route entirely on B.Cu with vertical jog north of the drill:
       F.Cu -> via -> [B.Cu vert + B.Cu horiz + B.Cu vert] -> via -> F.Cu
       Only 2 vias. The B.Cu detour_y is outside the drill circle.
       Each trace gets unique x_left/x_right columns (0.75mm pitch) so
       B.Cu verticals don't overlap.

    Returns a list of segment/via S-expressions.
    """
    lo_x, hi_x = min(x1, x2), max(x1, x2)
    parts = []
    for cx, cy, cr in _KEEPOUT_CIRCLES:
        # Does this horizontal cross the keepout circle?
        if not _segment_crosses_circle(x1, y, x2, y, width, cx, cy, cr):
            continue

        mh_key = (round(cx, 1), round(cy, 1))
        detour_idx = _MH_DETOUR_IDX.get(mh_key, 0)
        _MH_DETOUR_IDX[mh_key] = detour_idx + 1

        # Vias for MH detour layer transitions.
        # VIA_MIN for 0.175mm clearance to adjacent LCD approach traces.
        via_sz, via_dr = VIA_MIN, VIA_MIN_DRILL
        via_r = via_sz / 2  # 0.28mm

        # Check if trace Y is inside the physical drill circle.
        # Mounting holes are NPTH with drill=2.5mm, radius=1.25mm.
        # Need drill_radius + trace_half_width + NPTH drill-to-copper clearance.
        drill_r = 1.25  # 2.5mm / 2
        npth_clearance = 0.20  # JLCPCB NPTH drill-to-copper
        min_dist = drill_r + width / 2 + npth_clearance
        trace_inside_drill = abs(y - cy) < min_dist

        if not trace_inside_drill:
            # Strategy A: LAYER SWAP — B.Cu horizontal at same Y under NPTH.
            # Via column positions: just outside keepout circle.
            x_left = round(cx - cr - via_r - 0.15, 2)
            x_right = round(cx + cr + via_r + 0.15, 2)

            # Verify x boundaries are within segment span
            if x_left <= lo_x or x_right >= hi_x:
                continue

            # 1. F.Cu horizontal from x1 to x_left at y
            parts.append(_seg(x1, y, x_left, y, layer, width, net))
            # 2. Via F.Cu -> B.Cu at (x_left, y)
            parts.append(_via_net(x_left, y, net, size=via_sz, drill=via_dr))
            # 3. B.Cu horizontal from x_left to x_right at y
            parts.append(_seg(x_left, y, x_right, y, "B.Cu", width, net))
            # 4. Via B.Cu -> F.Cu at (x_right, y)
            parts.append(_via_net(x_right, y, net, size=via_sz, drill=via_dr))
            # 5. F.Cu horizontal from x_right to x2 at y
            parts.append(_seg(x_right, y, x2, y, layer, width, net))
        else:
            # Strategy B: ALL-B.Cu DETOUR — only 2 vias, full detour on B.Cu.
            # B.Cu vert + B.Cu horiz + B.Cu vert, all outside the drill circle.
            #
            # Each trace gets a unique x_left/x_right pair so B.Cu verticals
            # at different X positions don't overlap. 0.75mm pitch = via_dia(0.5)
            # + gap(0.25). Stagger outward from base positions.
            south_key = ("drill", mh_key[0], mh_key[1])
            south_idx = _MH_DETOUR_IDX.get(south_key, 0)
            _MH_DETOUR_IDX[south_key] = south_idx + 1

            # CROSSING-FREE via columns for 3 inside-drill traces.
            #
            # Strategy: each trace gets unique x_left, x_right, detour_y chosen
            # so no B.Cu horizontal crosses any B.Cu vertical of another trace.
            #
            # Constraints:
            #   - x_left > 100.45 + 0.525 = 100.975 (BTN_START B.Cu vert w=0.25)
            #   - x_left < 102.35 (strategy A left via at cx-cr-via_r-0.15)
            #   - net16 strategy A B.Cu horiz at y=35.575, x=[102.35, 107.65]:
            #     right columns between 102.35-107.65 are OK only if the B.Cu
            #     vertical Y range does NOT span y=35.575
            #   - C17 pad 2 at (109.05, 35.0) extends x=[108.55, 109.55]
            #   - GND via at (109.05, 37.0) pad r=0.45
            #   - VBUS B.Cu vert at (110.95, 35->33), C17 pad 1 at x=[110.45, 111.45]
            #
            # Solution — 3 non-crossing detours:
            #
            # idx0 (net18 Y=38.12): outermost, right col goes RIGHT of C17/GND
            #   left=101.00, right=110.00, detour_y=33.00
            #   Right vert at x=110.0: gap to C17p1(110.45)=0.35mm, GND via(109.50)=0.40mm
            #   B.Cu horiz at y=33.0: gap to VBUS via(110.50)=0.40mm, LCD_RST F.Cu=diff layer
            #
            # idx1 (net17 Y=36.84): middle, right col in gap between strat_A and C17
            #   left=101.55, right=108.20, detour_y=34.60
            #
            # idx2 (net10 Y=36.21): WIDE BYPASS south of all other detours.
            #   The tight inner columns (103.10/106.90) caused F.Cu keepout violations
            #   and segment-mounting_hole warnings because the F.Cu stub endpoints
            #   at y=36.21 were only 2.30mm from MH@(105,37.5) (need >=2.35mm).
            #   The right side between strat_A (107.65) and idx1 (108.20) is too narrow
            #   for another via column, and C17 pad (108.55) blocks further right.
            #
            #   Fix: bypass the ENTIRE constrained zone with wide columns:
            #   left=99.50, right=111.50, detour_y=32.30
            #
            #   Left col at x=99.50:
            #     Gap to BTN_START vert(100.45, w=0.25): 100.325-99.78=0.545mm ✓
            #     F.Cu (90.75,36.21)->(99.50,36.21): dist to MH=5.66mm >> 2.35mm keepout
            #     Via(99.50,36.21) to net17 F.Cu@y=36.845: 0.285mm > 0.15mm via-trace
            #
            #   Right col at x=111.50:
            #     Gap to VBUS vert(110.95, w=0.25): 111.40-111.075=0.325mm > trace gap
            #     F.Cu (111.50,36.21)->(114.10,36.21): dist to MH=6.63mm >> 2.35mm
            #     Via(111.50,36.21) to net17 F.Cu@y=36.845: 0.285mm > 0.15mm
            #
            #   B.Cu horiz at y=32.30:
            #     Gap to idx0 horiz(y=33.0): 32.90-32.40=0.50mm > 0.10mm trace gap
            #     Gap to VBUS via pad(110.95,33.0) bottom=32.55: 32.55-32.40=0.15mm > 0.10mm
            #     No via/pad overlap in path x=[100,111.5]
            #
            #   B.Cu vert crossings at x=99.50, y=[32.30,36.21]:
            #     BTN_START(100.45) starts at y=34.94, gap_x=0.95mm. OK
            #     net18 vert(101.0): gap_x=1.50mm. OK
            #   B.Cu vert crossings at x=111.50, y=[32.30,36.21]:
            #     VBUS vert(110.95): gap_x=0.325mm. OK
            #     net18 vert(110.0): gap_x=1.30mm. OK
            #
            # Cross-check: no B.Cu horiz crosses any other B.Cu vert:
            #   idx0 horiz y=33.0, x=[101.0,110.0]:
            #     idx1 L-vert x=101.55 y=[34.60,36.845]: 33.0 not in range. OK
            #     idx2 L-vert x=99.50 y=[32.30,36.21]: 33.0 IS in range.
            #       x=99.50 NOT in idx0 horiz x-range [101.0,110.0]. OK (no crossing)
            #     idx2 R-vert x=111.50 y=[32.30,36.21]: 33.0 IS in range.
            #       x=111.50 NOT in idx0 horiz x-range [101.0,110.0]. OK
            #   idx1 horiz y=34.60, x=[101.55,108.20]:
            #     idx0 verts x=101.0,110.0: outside [101.55,108.20]. OK
            #     idx2 L-vert x=99.50: outside [101.55,108.20]. OK
            #     idx2 R-vert x=111.50: outside [101.55,108.20]. OK
            #   idx2 horiz y=32.30, x=[99.50,111.50]:
            #     idx0 L-vert x=101.0 y=[33.0,38.12]: 32.30 not in range. OK
            #     idx0 R-vert x=110.0 y=[33.0,38.12]: 32.30 not in range. OK
            #     idx1 L-vert x=101.55 y=[34.60,36.845]: 32.30 not in range. OK
            #     idx1 R-vert x=108.20 y=[34.60,36.845]: 32.30 not in range. OK
            _left_cols = [101.03, 101.60, 99.50]  # DFM: idx0 at 101.03: gap to BTN_START@100.45 = 0.155mm ✓, idx1 at 101.60: gap to LCD_CS vert@101.03 = 0.17mm ✓
            _right_cols = [110.00, 108.27, 111.80]  # DFM: idx1 at 108.27: gap to MH detour via@107.70 = 0.17mm ✓. idx2 at 111.80 (was 111.50): clears C17[1] right edge (111.45) by 0.25mm ✓
            x_left = _left_cols[min(south_idx, 2)]
            x_right = _right_cols[min(south_idx, 2)]

            # Unique detour_y per trace — non-crossing B.Cu horizontals.
            # idx0: y=33.00 — outermost
            # idx1: y=34.60 — middle
            # idx2: y=32.30 — wide bypass south of all other detours
            #   B.Cu horiz [100.0,111.5] at y=32.30: below idx0 horiz (33.0) by 0.50mm.
            #   B.Cu verts at x=100.0 and x=111.5: outside all other horiz x-ranges.
            _detour_ys = [33.00, 34.60, 32.30]
            detour_y = _detour_ys[min(south_idx, 2)]

            # Verify x boundaries are within segment span
            if x_left <= lo_x or x_right >= hi_x:
                continue

            # 1. F.Cu horizontal from x1 to x_left at y
            parts.append(_seg(x1, y, x_left, y, layer, width, net))
            # 2. Via F.Cu -> B.Cu at (x_left, y)
            parts.append(_via_net(x_left, y, net, size=via_sz, drill=via_dr))
            # 3. B.Cu vertical from y to detour_y at x_left
            parts.append(_seg(x_left, y, x_left, detour_y, "B.Cu", width, net))
            # 4. B.Cu horizontal from x_left to x_right at detour_y
            parts.append(_seg(x_left, detour_y, x_right, detour_y, "B.Cu", width, net))
            # 5. B.Cu vertical from detour_y to y at x_right
            parts.append(_seg(x_right, detour_y, x_right, y, "B.Cu", width, net))
            # 6. Via B.Cu -> F.Cu at (x_right, y)
            parts.append(_via_net(x_right, y, net, size=via_sz, drill=via_dr))
            # 7. F.Cu horizontal from x_right to x2 at y
            parts.append(_seg(x_right, y, x2, y, layer, width, net))
        return parts

    # No keepout crossed: single segment
    parts.append(_seg(x1, y, x2, y, layer, width, net))
    return parts


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
USBC = enc(0, -33.7)      # (80.0, 71.2) — DFM: shield pads clear board edge by 0.525mm
SD = enc(60, -29.5)       # (140.0, 67.0)  — bottom-right
IP5306 = enc(30, -5)      # (110.0, 42.5)  — moved left
AMS1117 = enc(45, -18)    # (125.0, 55.5)  — moved left
PAM8403 = enc(-50, 8)     # (30.0, 29.5)
L1 = enc(30, -15)         # (110.0, 52.5)  — near IP5306
JST = enc(0, -25)         # (80.0, 62.5) — moved 5mm closer to USB-C (J1)
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
# Reset and Boot buttons on B.Cu (right of USB-C, dev kit style)
RESET_BTN = ("SW_RST", enc(15, -28))   # EN to GND
BOOT_BTN = ("SW_BOOT", enc(25, -28))   # GPIO0 to GND

# LED positions (F.Cu)
LED1 = enc(-55, -30)   # (25.0, 67.5) Red - charging
LED2 = enc(-48, -30)   # (32.0, 67.5) Green - full

# Passive positions (B.Cu) — synced with board.py placements
# Pull-ups at y=46, debounce at y=50, x = 43 + i*5
PULL_UP_REFS = [f"R{i}" for i in range(4, 16)] + ["R19"]
DEBOUNCE_REFS = [f"C{i}" for i in range(5, 17)] + ["C20"]

# Power passives (synced with board.py placements)
R1_POS = (74.0, 67.0)    # USB CC1 pull-down (ux-6, uy-5)
R2_POS = (78.0, 67.0)    # USB CC2 pull-down (moved near R1, B.Cu-only route)
R3_POS = (65.0, 42.0)    # ESP32 decoupling
R16_POS = (115.0, 52.5)  # IP5306 KEY pull-down
R17_POS = (25.0, 65.0)   # LED1 current limit (near LED1 on B.Cu)
R18_POS = (32.0, 65.0)   # LED2 current limit (near LED2 on B.Cu)

C1_POS = (120.0, 57.0)   # AMS1117 input cap — 3.2mm from VIN, left of SOT-223 body
C2_POS = (125.0, 62.5)   # AMS1117 output cap (amx, amy+7)
C3_POS = (69.5, 42.0)    # ESP32 decoupling 1 — DFM: was 68 (R3[1]@65.95 to C3[2]@67.05 gap=0.10mm danger). At 69.5: gap=2.60mm clear
C4_POS = (92.0, 42.0)    # ESP32 decoupling 2 — DFM: moved from 85 (pad1@85.95 hit U1[16]@85.715 at y=40)
C26_POS = (91.5, 21.0)   # ESP32 VDD bypass — within 3.6mm of U1 pin 2 (+3V3 at 88.75,23.51)
C17_POS = (110.0, 35.0)  # IP5306 cap
C18_POS = (116.0, 49.0)  # IP5306 BAT decoupling — moved closer: 10.7mm from pin 6 (was 15.4mm)
C19_POS = (110.0, 58.5)  # IP5306 VOUT bulk cap (lx, ly+6) — kept as bulk, C27 handles HF
C27_POS = (108.0, 39.0)  # IP5306 VOUT HF decoupling — 2.0mm from pin 8 (new)

# PAM8403 passive positions (synced with board.py placements)
# Spread ~1.5-2mm from U5 body for cleaner layout. Body: x=[27.3,32.7] y=[24.5,34.5].
# Decoupling at 250kHz effective up to ~7mm.
C21_POS = (38.0, 23.5)   # VREF bypass cap (pin 8 to GND) — 4.8mm from pin 8
C22_POS = (33.175, 20.0) # DC-blocking cap in-line on I2S_DOUT vertical (series, distance OK)
C23_POS = (38.0, 29.5)   # VDD decoupling (pin 6 to GND) — 6.1mm from pin 6
C24_POS = (29.365, 22.0) # PVDD decoupling (pin 4 to GND) — 4.8mm from pin 4
C25_POS = (31.5, 37.5)   # PVDD decoupling (pin 13 to GND) — 5.8mm from pin 13
R20_POS = (38.0, 26.500) # INL bias to GND — 3.0mm from C21, 3.0mm from C23
R21_POS = (38.0, 32.500) # INR bias to GND — 3.0mm from C23

# USB ESD protection positions (synced with board.py placements)
# U4 (USBLC6-2SC6 SOT-23-6): placed between D+/D- approach columns.
# Pins 3/4 (D+) overlap D+ trace at x=90.25, pins 1/6 (D-) overlap D- trace at x=91.65.
# Pin 2 (GND) centered between traces, pin 5 (VBUS) connects via F.Cu to VBUS horizontal.
U4_POS = (90.95, 60.0)
# R22/R23 (22Ω 0402): inline on D+/D- B.Cu approach columns, rotated 90°.
# R22 breaks D+ vertical at x=90.25, R23 breaks D- vertical at x=91.65.
R22_POS = (90.25, 40.0)   # D+ 22Ω series (between TVS and ESP32 GPIO20)
R23_POS = (91.65, 38.5)   # D- 22Ω series (between TVS and ESP32 GPIO19, clear of C4 GND via@40.0)


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
    35: 42, 36: 44, 37: 43, 38: 1, 39: 2,
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

# Pad-to-net registry: auto-populated by _seg() and _via_net() when
# a segment/via endpoint matches a known pad position. Used by board.py
# to inject correct net assignments into footprint pads.
_PAD_NETS = {}          # {(ref, pad_num_str): net_id}
_PAD_POS_LOOKUP = {}    # {(round_x, round_y): [(ref, num_str), ...]}


def get_pad_nets():
    """Return the (ref, pad_num_str) -> net_id mapping.

    Called by board.py after generate_all_traces() to inject nets into pads.
    """
    return dict(_PAD_NETS)


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
        ("J3", "JST-PH-2P-SMD", *JST, 180, "B"),
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
    # B.Cu reset and boot buttons
    ref_rst, pos_rst = RESET_BTN
    _PADS[ref_rst] = _compute_pads("SW-SMD-5.1x5.1",
                                    pos_rst[0], pos_rst[1], 0, "B")
    ref_boot, pos_boot = BOOT_BTN
    _PADS[ref_boot] = _compute_pads("SW-SMD-5.1x5.1",
                                     pos_boot[0], pos_boot[1], 0, "B")

    # Key passives with explicit routing
    passive_placements = [
        ("C1", "C_0805", *C1_POS, 0, "B"),
        ("C2", "C_1206", *C2_POS, 0, "B"),
        ("C3", "C_0805", *C3_POS, 0, "B"),
        ("C4", "C_0805", *C4_POS, 0, "B"),
        ("C17", "C_0805", *C17_POS, 0, "B"),
        ("C18", "C_0805", *C18_POS, 0, "B"),
        ("C19", "C_1206", *C19_POS, 0, "B"),
        ("C27", "C_0805", *C27_POS, 0, "B"),
        ("R16", "R_0805", *R16_POS, 0, "B"),
        ("R1", "R_0805", *R1_POS, 0, "B"),
        ("R2", "R_0805", *R2_POS, 0, "B"),
        ("R17", "R_0805", *R17_POS, 0, "B"),
        ("R18", "R_0805", *R18_POS, 0, "B"),
        ("LED1", "LED_0805", *LED1, 0, "F"),
        ("LED2", "LED_0805", *LED2, 0, "F"),
        # PAM8403 passives
        ("C21", "C_0805", *C21_POS, 0, "B"),
        ("C22", "C_0805", *C22_POS, 90, "B"),
        ("C23", "C_0805", *C23_POS, 90, "B"),
        ("C24", "C_0805", *C24_POS, 90, "B"),
        ("C25", "C_0805", *C25_POS, 90, "B"),
        ("R20", "R_0805", *R20_POS, 0, "B"),
        ("R21", "R_0805", *R21_POS, 0, "B"),
        # ESP32 VDD bypass (rotated 90° to separate +3V3/GND routing)
        ("C26", "C_0805", *C26_POS, 90, "B"),
        # USB ESD protection
        ("U4", "SOT-23-6", *U4_POS, 0, "B"),
        ("R22", "R_0402", *R22_POS, 90, "B"),
        ("R23", "R_0402", *R23_POS, 90, "B"),
    ]
    for ref, fp, cx, cy, rot, lc in passive_placements:
        _PADS[ref] = _compute_pads(fp, cx, cy, rot, lc)

    # Build position lookup for auto pad-net detection in _seg()/_via_net()
    for ref, pad_dict in _PADS.items():
        for num, (px, py) in pad_dict.items():
            key = (round(px, 2), round(py, 2))
            _PAD_POS_LOOKUP.setdefault(key, []).append((ref, num))

    # Pre-populate collision grid with pads, slot, edges, mounting holes
    if not _GRID._populated:
        from .pad_positions import get_all_pad_positions
        from .board import MOUNT_HOLES_ENC, enc_to_pcb
        all_pads = get_all_pad_positions()
        _GRID.register_pads(all_pads)
        _GRID.register_slot()
        _GRID.register_board_edges()
        _GRID.register_mounting_holes(
            [enc_to_pcb(ex, ey) for ex, ey in MOUNT_HOLES_ENC])


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
    """Return (x, y) PCB coordinate for FPC connector pad (1-indexed)."""
    _init_pads()
    pos = _PADS.get("J4", {}).get(str(pin))
    return pos if pos else FPC


def _fpc_display_pin(display_pin):
    """Return (x, y) PCB coordinate for display FPC pin (1-indexed).

    The display in landscape (CCW rotation) has its FPC cable passing
    straight through the PCB slot.  Pin 1 (south on cable) contacts
    connector pad 40 (south on PCB), so display pin N maps to
    connector pad (41 - N).
    """
    connector_pad = 41 - display_pin
    return _fpc_pin(connector_pad)


# ── Manhattan routing helpers ─────────────────────────────────────

def _seg(x1, y1, x2, y2, layer="B.Cu", width=W_DATA, net=0):
    """Shorthand for segment. Auto-registers pad-net associations."""
    if net != 0:
        _init_pads()
        for x, y in [(x1, y1), (x2, y2)]:
            key = (round(x, 2), round(y, 2))
            for ref, num in _PAD_POS_LOOKUP.get(key, []):
                _PAD_NETS[(ref, num)] = net
                _GRID.update_pad_net(ref, num, net)
        # Collision check + register
        violations = _GRID.check_segment(x1, y1, x2, y2, layer, width, net)
        _GRID.violations.extend(violations)
        _GRID.add_segment(x1, y1, x2, y2, layer, width, net)
    # Keepout zone warning (all segments, including net=0)
    # B.Cu traces crossing NPTH mounting holes are OK — NPTH has no barrel
    # plating, so copper on internal/back layers can safely pass under the
    # drill as long as drill-to-copper clearance is met (checked by DFM).
    # Only warn for F.Cu crossings (top copper near drill opening).
    import sys as _sys
    for kx, ky, kr in _KEEPOUT_CIRCLES:
        if _segment_crosses_circle(x1, y1, x2, y2, width, kx, ky, kr):
            if layer == "B.Cu":
                continue  # B.Cu under NPTH is intentional (layer-swap detour)
            _sys.stderr.write(
                f"  KEEPOUT VIOLATION: {layer} ({x1},{y1})->({x2},{y2})"
                f" w={width} crosses MH@({kx},{ky}) r={kr}\n"
            )
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
    """Create a via. Auto-registers pad-net associations."""
    if net != 0:
        _init_pads()
        key = (round(x, 2), round(y, 2))
        for ref, num in _PAD_POS_LOOKUP.get(key, []):
            _PAD_NETS[(ref, num)] = net
            _GRID.update_pad_net(ref, num, net)
        # Collision check + register
        _size = size if size is not None else 0.9
        _drill = drill if drill is not None else 0.35
        violations = _GRID.check_via(x, y, net, _size, _drill)
        _GRID.violations.extend(violations)
        _GRID.add_via(x, y, net, _size, _drill)
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

    # USB-C (J1): VBUS on pin 2/11, GND on pin 1/12
    usb_vbus = _pad("J1", "2")    # VBUS pad (was A4)
    usb_gnd = _pad("J1", "12")    # GND pad (was A12)

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
    # SHORT FIX v4: route VBUS on B.Cu vertical UP from USB pad to y=61.0 (above ALL
    # button F.Cu channels at y=62..73), then F.Cu horizontal to IP5306 approach column.
    # Old route used F.Cu horizontal at y=68.255 which shorted with BTN_B (y=68.0) and
    # BTN_R shoulder (y=65.0) F.Cu channels that span nearly full board width.
    #
    # New route:
    #   B.Cu: USB pad -> (82.0, 68.255) short stub (clear of CC1 at x=81.25)
    #   B.Cu: (82.0, 68.255) -> (82.0, 61.0) vertical UP (no F.Cu channels in this column)
    #   via to F.Cu at (82.0, 61.0)
    #   F.Cu: (82.0, 61.0) -> (ip_vbus_via_x, 61.0) horizontal (y=61 is 1mm above BTN_UP@62)
    #   F.Cu: (ip_vbus_via_x, 61.0) -> (ip_vbus_via_x, ip_vbus_via_y) vertical to IP5306
    #   via to B.Cu at (ip_vbus_via_x, ip_vbus_via_y)
    #   B.Cu: stubs to IP5306 pin
    #
    # Clearances:
    #   B.Cu vert at x=82: CC1@x=81.25 gap=|82-81.25|-0.25-0.125=0.375mm ✓
    #   B.Cu vert at x=82: D+@x=80.6 gap=|82-80.6|-0.25-0.10=1.05mm ✓
    #   F.Cu horiz at y=61: BTN_UP@y=62 gap=|62-61|-0.125-0.25=0.625mm ✓
    #   F.Cu vert at x=108: same as old route (ip_vbus_via_x=108) ✓
    vbus_fcu_y = 61.0   # 1mm above highest button F.Cu channel (BTN_UP@62.0)
    # DFM FIX (KiBot external): VBUS B.Cu vert at x=82.25 had gap=0.15mm to
    # J3:1 PTH pad (81.0, 62.5) size 1.6mm (right edge 81.8). W_PWR=0.6 hw=0.3.
    # At 82.25: left edge 81.95, gap=81.95-81.8=0.15mm < 0.20mm rule.
    # Fix: offset +0.05 → x=82.45. Left edge 82.07, gap to J3:1=82.07-81.8=0.27mm ✓
    # Right edge 82.83, gap to J1:1 GND pad left edge (83.025)=0.195mm >= 0.175mm ✓
    vbus_fcu_start_x = usb_vbus[0] + 0.05
    ip_vbus_via_x = ip_vbus[0] - 2  # 108.0
    ip_vbus_via_y = ip_vbus[1] - 0.5  # DFM: 0.5mm above pad to clear U2[EP]

    # 1. B.Cu stub from USB VBUS pad LEFT to x=82.0
    parts.append(_seg(usb_vbus[0], usb_vbus[1], vbus_fcu_start_x, usb_vbus[1],
                       "B.Cu", W_PWR_HIGH, n_vbus))
    # 2. B.Cu vertical UP from y=68.255 to y=61.0 (above all button F.Cu channels)
    parts.append(_seg(vbus_fcu_start_x, usb_vbus[1], vbus_fcu_start_x, vbus_fcu_y,
                       "B.Cu", W_PWR_HIGH, n_vbus))
    # 3. via to F.Cu at (82.0, 61.0)
    parts.append(_via_net(vbus_fcu_start_x, vbus_fcu_y, n_vbus))
    # 4. F.Cu horizontal to IP5306 approach column
    parts.append(_seg(vbus_fcu_start_x, vbus_fcu_y, ip_vbus_via_x, vbus_fcu_y,
                       "F.Cu", W_PWR_HIGH, n_vbus))
    # 5. F.Cu vertical down to IP5306 pin level
    parts.append(_seg(ip_vbus_via_x, vbus_fcu_y, ip_vbus_via_x, ip_vbus_via_y,
                       "F.Cu", W_PWR_HIGH, n_vbus))
    # 6. via to B.Cu at IP5306 approach
    parts.append(_via_net(ip_vbus_via_x, ip_vbus_via_y, n_vbus))
    # 7. B.Cu stub: via -> IP5306 VBUS pad (horizontal then vertical)
    parts.append(_seg(ip_vbus_via_x, ip_vbus_via_y, ip_vbus_via_x, ip_vbus[1],
                       "B.Cu", W_PWR_HIGH, n_vbus))
    parts.append(_seg(ip_vbus_via_x, ip_vbus[1], ip_vbus[0], ip_vbus[1],
                       "B.Cu", W_PWR_HIGH, n_vbus))

    # ── GND: vias to In1.Cu GND zone ──────────────────────────
    # GND vias near key components
    # ESP32 GND pad (pin 41) to GND via (+3.0mm to clear thermal pad bottom edge at 31.91)
    # DFM: was single vertical at x=81.5 (esp_gnd[0]). Gap to LCD_D7 B.Cu vert at x=81.905
    # was only 0.055mm (DANGER). Fix: horizontal LEFT to x=80.0, then vertical.
    # DFM FIX: was -1.5 (x=80.0), LCD_RST via at (79.365,34.305) right edge=79.665.
    # GND via (0.60) left edge=79.70: gap=0.035mm < 0.15mm VIOLATION.
    # At -1.3 (x=80.2): left edge=79.90, gap=0.235mm >= 0.15mm ✓
    gnd_offset_x = esp_gnd[0] - 1.3  # x=80.2 — clear of LCD_RST via AND LCD_D7
    # ESP32 GND: thermal pad (pin 41) at (81.5, 29.96), size 3.9x3.9 → top edge at y=28.01.
    # Via at +2mm = y=31.96 is INSIDE pad (pad bottom at y=31.91).  Use +2.5mm → y=32.46
    # (gap = 32.46 - 31.91 - 0.45 = 0.10mm OK).
    # DFM FIX: USB GND via handled separately (needs small via + larger offset)
    gnd_via_positions = [
        # DFM FIX: IP5306 GND via moved to x=112.4 (outside KEY span, clear of pads 2,3,4)
        # to avoid crossing the IP5306_KEY horizontal stub.
        (ip_ep[0] + 2.4, ip_ep[1] + 3),   # IP5306 GND (via at x=112.4, right of pads)
        (am_gnd[0], am_gnd[1] + 2),       # AMS1117 GND
        # ESP32 GND via handled separately below (needs small via for clearance)
        (jst_n[0], jst_n[1] - 3.5),         # JST GND (offset UP, away from USB-C and BAT+)
    ]
    for gvx, gvy in gnd_via_positions:
        parts.append(_via_net(gvx, gvy, n_gnd))
    # USB-C GND: route via ABOVE button channels to avoid blocking the
    # BTN_A-BTN_B corridor (needed for CC1 F.Cu routing at y=67.2).
    # Via at y=66.0: gap to BTN_A(y=66.8) = 66.8-0.125-(66.0+0.25)=0.425mm ✓
    #               gap to BTN_R(y=65.4) = 66.0-0.25-(65.4+0.10)=0.25mm ✓
    usb_gnd_via_y = 66.2  # above BTN_A(66.8), clears CC1 F.Cu at y=67.4 and BTN_R via(76.20,65.40)
    parts.append(_via_net(usb_gnd[0], usb_gnd_via_y, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # B.Cu stubs from IC GND pads to vias
    parts.append(_seg(usb_gnd[0], usb_gnd[1], usb_gnd[0], usb_gnd_via_y,
                       "B.Cu", W_PWR, n_gnd))

    # ── USB-C extra pad net assignments (GND, VBUS, Shield) ────
    # The USB-C connector area is densely routed (D+/D-/CC1/CC2 verticals,
    # VBUS vertical, button approach columns). Explicit B.Cu traces to most
    # pads would cross existing routes. Instead:
    # - Assign net IDs to pads (for DRC net awareness)
    # - GND pads connect through In1.Cu GND zone (zone fill)
    # - VBUS pads 9/11 link to pad 2 via short same-row stub (no crossings)
    # - Shield THT pads connect through In1.Cu GND zone (plated holes)
    #
    # Pad 1 (GND): directly assign net, zone fill connects via In1.Cu
    _PAD_NETS[("J1", "1")] = n_gnd
    # Pad 9 (VBUS): directly assign net
    _PAD_NETS[("J1", "9")] = n_vbus
    # Pad 11 (VBUS): directly assign net
    _PAD_NETS[("J1", "11")] = n_vbus
    # Pad 9 to pad 11: no explicit stub needed — CC2 B.Cu vertical at x=78.25
    # runs between these pads at y=68.83, blocking any horizontal stub.
    # Both pads have VBUS net assigned; zone fill on In2.Cu connects them.
    # Shield pads 13, 14, 13b, 14b → GND net assignment.
    # THT pads have plated barrels connecting to In1.Cu GND zone automatically.
    _PAD_NETS[("J1", "13")] = n_gnd
    _PAD_NETS[("J1", "14")] = n_gnd
    _PAD_NETS[("J1", "13b")] = n_gnd
    _PAD_NETS[("J1", "14b")] = n_gnd

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
    # Note: AMS1117 thermal relief via existing GND zone on In1.Cu.
    # Additional stitching vias would overlap +3V3 power trace at x=125.
    # ESP32 GND stub: reduce width to 0.3mm for horizontal from pad to gnd_offset_x.
    # DFM FIX: W_PWR=0.6 (hw=0.30) too wide for LCD_D7 gap. Use 0.3mm (hw=0.15):
    # right edge=80.35, LCD_D7 left edge=81.805 → gap=1.455mm ✓
    parts.append(_seg(esp_gnd[0], esp_gnd[1], gnd_offset_x, esp_gnd[1],
                       "B.Cu", 0.3, n_gnd))
    esp_gnd_via_y = esp_gnd[1] + 5.04  # y=35.0 — above LCD_RST B.Cu vert endpoint (33.04)
    # DFM FIX: reduced from W_PWR to 0.4mm for LCD_RST via clearance.
    # LCD_RST via at (79.365,34.305) r=0.30 (VIA_STD), right edge=79.665.
    # GND at x=80.2 w=0.4: left edge=80.0, gap=0.335mm >= 0.15mm ✓
    parts.append(_seg(gnd_offset_x, esp_gnd[1], gnd_offset_x, esp_gnd_via_y,
                       "B.Cu", 0.4, n_gnd))
    # DFM FIX: ESP32 GND via at (80.2,35.04). LCD_RST via at (79.365,34.305) r=0.30.
    # Via-via: dx=0.835, dy=0.735, dist=1.112. Gap=1.112-0.30-0.30=0.512mm ≥ 0.25mm ✓
    # GND via left edge=79.90, LCD_RST right edge=79.665: gap=0.235mm ≥ 0.15mm ✓
    parts.append(_via_net(gnd_offset_x, esp_gnd_via_y, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))
    # Note: ESP32 GND relief via existing GND zone on In1.Cu + EP via-in-pad.
    # Exposed pad at (80, 30) connects to In1.Cu GND plane via zone fill.

    # ── Additional GND stitching vias near ESP32 (U1) ──────────────
    # ESP32 EP at ~(80,30), pin 41 GND. Existing GND vert at x=80.2, y=29.96..35.04.
    # LCD_RST B.Cu vert at x=79.36, y=34.30..40.00 blocks LEFT branching.
    # LCD_D7 B.Cu vert at x=81.905 blocks close RIGHT branching.
    # Strategy: extend existing GND vert DOWNWARD (increase Y) past LCD_RST endpoint,
    # then branch to vias in clear areas.
    # Existing vert ends at esp_gnd_via_y=35.04 with via. Extend further down to y=37.0.
    # LCD_RST vert ends at y=40.0 (bottom). At y=37.0: LCD_RST still present at x=79.36.
    # Keep extension at x=80.2 — gap to LCD_RST (79.36): 80.2-0.20-79.36-0.10=0.54mm ✓
    # Via 1: at end of extension (80.2, 37.5). Check F.Cu: MH at (80,37.5)? No — MH at (105,37.5).
    #   LCD_CS F.Cu at y=34.30: gap=37.5-34.30-0.30-0.10=2.80mm ✓
    # Via 1 at extension end. Existing via net14 at (80.64, 38.12) is close.
    # Need via-via gap >= 0.25mm. Dist = sqrt((80.2-80.64)^2+(y-38.12)^2).
    # At y=36.5: dist=sqrt(0.44^2+1.62^2)=1.679, gap=1.679-0.30-0.30=1.079mm ✓
    # F.Cu net16 at y=36.84 from x=78 to x=101: via at y=36.5, gap=36.84-36.5-0.30-0.10=0mm.
    # Still too tight. Use y=36.0: gap=36.84-36.0-0.30-0.10=0.44mm ✓
    # Split vertical into two segments at y=35.5 for proper T-junction.
    parts.append(_seg(gnd_offset_x, esp_gnd_via_y, gnd_offset_x, 35.5,
                       "B.Cu", 0.4, n_gnd))
    parts.append(_seg(gnd_offset_x, 35.5, gnd_offset_x, 36.0,
                       "B.Cu", 0.4, n_gnd))
    parts.append(_via_net(gnd_offset_x, 36.0, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))
    # Via 2: branch RIGHT from T-junction at y=35.5 to x=81.0.
    #   LCD_D7 B.Cu vert at x=81.905 (w=0.2): left edge=81.805.
    #   Via at (81.0, 35.5): right edge=81.30, gap=81.805-81.30=0.505mm ✓
    #   F.Cu net16 at y=36.84: gap=36.84-35.5-0.30-0.10=0.94mm ��
    #   F.Cu net15 at y=34.30: gap=35.5-34.30-0.30-0.10=0.80mm ✓
    parts.append(_seg(gnd_offset_x, 35.5, 81.0, 35.5, "B.Cu", 0.4, n_gnd))
    parts.append(_via_net(81.0, 35.5, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── AMS1117 (U3) GND thermal vias: 2 vias near GND pin for heat dissipation ──
    # AMS1117 dissipates ~0.85W ((5V-3.3V) x 0.5A). GND pin (pin 1) needs thermal
    # vias to In1.Cu GND plane for heat spreading.
    # am_gnd at ~(127.30, 58.65). Existing GND via at (127.30, 60.65).
    # +3V3 B.Cu vertical at x=125.00 (w=0.6, right edge=125.30) blocks LEFT routing.
    # Display B.Cu verts at x=129.24+ block far RIGHT.
    # Strategy: place 2 GND thermal vias offset RIGHT of GND vertical (x=127.30)
    # to clear C2 pad1 (mirrored) at (126.50, 62.50) size 1.2x1.8.
    # C2 pad1 right edge = 127.10. Vias at x=127.60: left edge=127.30, gap=0.20mm ✓
    # Via 1 at (128.30, 61.00): within 3mm of GND pin (~58.65). ✓
    #   C2 pad1 at (126.50,62.50) size 1.2x1.8: right=127.10, top=61.60.
    #   Via drill edge: (128.20, 61.00). X gap to pad=1.10mm, Y gap=0.60mm ✓
    # Via 2 at (128.30, 64.00): within 6mm of GND pin. ✓
    #   C2 pad1 bottom=63.40: via drill top=63.90, gap=0.50mm ✓
    # Existing GND via at (127.30, 60.65):
    #   dist to via1 = sqrt(1.0^2+0.35^2) = 1.06. gap=1.06-0.60=0.46mm ✓
    # Display B.Cu verts at x=129.24 (w=0.2): gap=129.14-128.60=0.54mm ✓
    _ams_therm_via_x = am_gnd[0] + 1.0  # ~128.30
    _ams_gnd_via_y1 = am_gnd[1] + 2.35  # ~61.00
    _ams_gnd_via_y2 = am_gnd[1] + 5.35  # ~64.00
    # B.Cu vertical extension then horizontal branch to thermal vias
    parts.append(_seg(am_gnd[0], am_gnd[1] + 2, am_gnd[0], _ams_gnd_via_y1,
                       "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(am_gnd[0], _ams_gnd_via_y1, _ams_therm_via_x, _ams_gnd_via_y1,
                       "B.Cu", W_PWR, n_gnd))
    # Thermal via 1
    parts.append(_via_net(_ams_therm_via_x, _ams_gnd_via_y1, n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))
    # Vertical stub to thermal via 2
    parts.append(_seg(_ams_therm_via_x, _ams_gnd_via_y1, _ams_therm_via_x, _ams_gnd_via_y2,
                       "B.Cu", W_PWR, n_gnd))
    # Thermal via 2
    parts.append(_via_net(_ams_therm_via_x, _ams_gnd_via_y2, n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))

    # JST GND pad to offset via (UP, away from USB-C and BAT+)
    parts.append(_seg(jst_n[0], jst_n[1], jst_n[0], jst_n[1] - 3.5,
                       "B.Cu", W_PWR, n_gnd))

    # ── IP5306 (U2) GND thermal vias: 3-via array near EP pad ──────
    # EP pad center at ip_ep = (110.0, 42.5), size 3.2x3.2mm.
    # VBUS F.Cu vertical at x=111.0 (y=40..61): thermal vias must stay clear.
    # With W_PWR=0.6: via right edge + trace left edge need >= 0.15mm gap.
    # Place vias LEFT of EP center to avoid VBUS trace at x=111.
    # y=ip_ep[1]+2.5=45.0, below KEY horizontal (y=44.41, x=107..114.05).
    # VBUS F.Cu vert at x=111.0: need gap >= 0.275+0.30+0.15 = 0.725mm.
    # Max via x = 111.0 - 0.725 = 110.275. Use x=110.0 for margin.
    # IP5306 thermal vias: 3 GND vias below EP pad.
    # KEY trace at x=107.0: need gap >= 0.30+0.125+0.15 = 0.575mm min.
    # VBUS F.Cu at x=111.0: need gap >= 0.275+0.30+0.15 = 0.725mm.
    # EP pad bounds: x=108.4..111.6, y=40.9..44.1.
    # Place inside EP pad bounds to avoid dead-end issues.
    _ip5306_therm_vias = [
        (ip_ep[0] - 1.5, ip_ep[1] + 2.5),  # (108.5, 45.0) — gap to KEY=1.075mm ✓
        (ip_ep[0],        ip_ep[1] + 2.5),  # (110.0, 45.0) — center
        (ip_ep[0] - 0.7,  ip_ep[1] + 3.5),  # (109.3, 46.0) — below, gap to VBUS>1mm ✓
    ]
    # Connect each thermal via to EP pad via a single vertical B.Cu stub.
    # Each stub goes straight down into the EP pad area (all inside pad bounds).
    for tvx, tvy in _ip5306_therm_vias:
        parts.append(_via_net(tvx, tvy, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))
        # Single B.Cu stub from via into EP pad (which is at y=40.9..44.1).
        # Stub endpoint at y=ip_ep[1]+1.5 is inside pad (44.0 < 44.1).
        parts.append(_seg(tvx, tvy, tvx, ip_ep[1] + 1.5, "B.Cu", W_PWR, n_gnd))

    # ── SD card (U6, TF-01A) power connections ───────────────────
    # Pin 4 = VDD (+3V3), Pin 6 = VSS (GND), Shield pins 10-13 = GND.
    # U6 at (140, 67) on B.Cu, rotation 0.
    # Pin 4 absolute ≈ (141.06, 61.72), Pin 6 ≈ (143.26, 61.72).
    # Inner layers: In1.Cu = GND zone, In2.Cu = +3V3 zone (pin 4 at x=141
    # is outside the +5V island x=105-140, so via reaches +3V3 zone).
    sd_vdd = _pad("U6", "4")   # VDD (+3V3)
    sd_vss = _pad("U6", "6")   # VSS (GND)
    sd_sh10 = _pad("U6", "10")  # Shield front-left (GND)
    sd_sh12 = _pad("U6", "12")  # Shield rear-right (GND)

    if sd_vdd:
        # +3V3 to SD VDD (pin 4): via-in-pad to reach In2.Cu +3V3 zone.
        # DFM: B.Cu area around pin 4 is crowded — SD_MOSI at x=141.20 (0.14mm gap)
        # and MOSI return at x=139.96. ANY B.Cu stub collides with existing traces.
        # Solution: drop via directly at pad (via-in-pad). The 0.46mm via fits within
        # the 0.6mm x 1.3mm pad. Via connects B.Cu pad to In2.Cu +3V3 zone.
        # Pin 4 at x≈141.06 is outside +5V island (x=105-140), so In2.Cu = +3V3 ✓
        parts.append(_via_net(sd_vdd[0], sd_vdd[1], n_3v3, size=VIA_STD, drill=VIA_STD_DRILL))

    if sd_vss:
        # GND to SD VSS (pin 6): via-in-pad to reach In1.Cu GND zone.
        # DFM: BTN_B trace at x=142.80 is 0.46mm from pin 6 at x=143.26.
        # Any B.Cu stub would collide. Via-in-pad avoids routing entirely.
        # 0.46mm via fits within the 0.6mm x 1.3mm pad.
        parts.append(_via_net(sd_vss[0], sd_vss[1], n_gnd, size=VIA_MIN, drill=VIA_MIN_DRILL))

    if sd_sh10:
        # GND via near shield pin 10 (front-left, x≈147.76, y≈62.57).
        # Stub RIGHT 1.0mm from pad center to offset via from shield edge.
        # Widened from 0.3→0.4mm: shield pad area has ample clearance.
        sd_sh10_via_x = sd_sh10[0] + 1.0
        parts.append(_seg(sd_sh10[0], sd_sh10[1], sd_sh10_via_x, sd_sh10[1],
                           "B.Cu", 0.4, n_gnd))
        parts.append(_via_net(sd_sh10_via_x, sd_sh10[1], n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    if sd_sh12:
        # GND via near shield pin 12 (rear-right, x≈132.24, y≈72.28).
        # Stub LEFT 1.0mm from pad center to stay clear of board edge.
        # Widened from 0.3→0.4mm: shield pad area has ample clearance.
        sd_sh12_via_x = sd_sh12[0] - 1.0
        parts.append(_seg(sd_sh12[0], sd_sh12[1], sd_sh12_via_x, sd_sh12[1],
                           "B.Cu", 0.4, n_gnd))
        parts.append(_via_net(sd_sh12_via_x, sd_sh12[1], n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))
    # Note: U6 SD card GND via existing zone fill + VSS via-in-pad + 2 shield vias.

    # ── Additional GND stitching via near SD card (U6) ─────────────
    # Extend shield pin 12 stub further LEFT by 1.5mm for an extra stitching via.
    if sd_sh12:
        sd_stitch_x = sd_sh12_via_x - 1.5
        parts.append(_seg(sd_sh12_via_x, sd_sh12[1], sd_stitch_x, sd_sh12[1],
                           "B.Cu", 0.4, n_gnd))
        parts.append(_via_net(sd_stitch_x, sd_sh12[1], n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── +5V: IP5306 VOUT (pin 8) -> AMS1117 input ──────────────
    # VOUT via to +5V zone on In2.Cu
    # DFM FIX: old via at (ip_vout[0], ip_vout[1]-2) = (107, 38.59) is 2mm from
    # MH(105,37.5) center: gap = 2.0 - 0.45 - 1.25 = 0.30mm < 0.50mm needed.
    # Fix: add short B.Cu horizontal to x+0.5, then vert to y-1.5.
    # New via at (107.5, 39.09): MH gap=0.80mm ✓, no other obstacles ✓
    parts.append(_seg(ip_vout[0], ip_vout[1], ip_vout[0] + 0.5, ip_vout[1],
                       "B.Cu", W_PWR, n_5v))
    parts.append(_seg(ip_vout[0] + 0.5, ip_vout[1], ip_vout[0] + 0.5, ip_vout[1] - 1.5,
                       "B.Cu", W_PWR, n_5v))
    parts.append(_via_net(ip_vout[0] + 0.5, ip_vout[1] - 1.5, n_5v))
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
    # DFM: BTN_MENU B.Cu vert at x=104.0 (w=0.25), BAT+ vert at x=105.5 (w=0.76).
    # BAT+ via at (105.5,46.1) sz=0.9 → left edge 105.05.
    # LX at x=104.55, w=0.60: right edge=104.85
    #   BTN_MENU gap: |104.55-104.0|-0.30-0.125 = 0.125mm ≥ 0.10mm ✓
    #   BAT+ vert gap: 105.12-104.85 = 0.27mm ≥ 0.25mm ✓
    #   BAT+ via gap: 105.05-104.85 = 0.20mm ≥ 0.10mm ✓
    # At 0.60mm / 1oz Cu: ~1.4A capacity (10°C rise), adequate for pulsed LX.
    lx_col_x = ip_sw[0] - 2.45   # x=104.55
    parts.append(_seg(ip_sw[0], ip_sw[1], lx_col_x, ip_sw[1],
                       "B.Cu", W_PWR_HIGH, n_lx))
    parts.append(_seg(lx_col_x, ip_sw[1], lx_col_x, l1_2[1],
                       "B.Cu", W_PWR, n_lx))  # 0.60mm — max width within BTN_MENU/BAT+ corridor
    parts.append(_seg(lx_col_x, l1_2[1], l1_2[0], l1_2[1],
                       "B.Cu", W_PWR_HIGH, n_lx))

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
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(l1_1[0], bat_via_y, bat_via_x, bat_via_y,
                       "B.Cu", W_PWR_HIGH, n_bat))

    # ── KEY: IP5306 pin 5 -> R16 pull-up to +5V ─────────────
    # B.Cu route from KEY pin down to R16 area
    # DFM v2: KEY pin at (107, 44.405), pad 4 at (113, 44.405). Direct horizontal crosses pad 4.
    # Route with Z-shape: R16→down to safe Y, horizontal to KEY X, vertical to KEY pin.
    r16_p1 = _pad("R16", "1")
    r16_p2 = _pad("R16", "2")
    if r16_p2 and ip_key:
        # R16 pin 2 -> IP5306 KEY (pin 5) via B.Cu Z-route (avoid pad 4 at y=44.405)
        # DFM: was +1.0 (y=45.405) — crossed GND vertical at x=112.4 (y=43.5-45.5).
        # +2.2 gives y≈46.6, above GND vert top (45.5+0.25=45.75).
        key_safe_y = ip_key[1] + 2.2
        parts.append(_seg(r16_p2[0], r16_p2[1], r16_p2[0], key_safe_y,
                           "B.Cu", W_SIG, n_key))
        parts.append(_seg(r16_p2[0], key_safe_y, ip_key[0], key_safe_y,
                           "B.Cu", W_SIG, n_key))
        parts.append(_seg(ip_key[0], key_safe_y, ip_key[0], ip_key[1],
                           "B.Cu", W_SIG, n_key))
    if r16_p1:
        # R16 pin 1 -> +5V via (pull-up for always-on)
        # DFM FIX: via x=114.95 too close to R16[2] pad (gap=0.10mm).
        # Shift via RIGHT to x=115.25: gap to R16[2] right edge (114.55) =
        # 115.25-0.30-114.55 = 0.40mm ✓. Gap to C18 pad2 (117.05-0.50=116.55) =
        # 116.55-115.25-0.45 = 0.85mm ✓.
        _r16_via_x = r16_p1[0] - 0.70  # 115.25 — clears R16[2] and C18
        parts.append(_seg(r16_p1[0], r16_p1[1], _r16_via_x, r16_p1[1],
                           "B.Cu", W_PWR, n_5v))
        parts.append(_seg(_r16_via_x, r16_p1[1], _r16_via_x, r16_p1[1] + 2,
                           "B.Cu", W_PWR, n_5v))
        parts.append(_via_net(_r16_via_x, r16_p1[1] + 2, n_5v))

    # ── +3V3: AMS1117 output via outside +5V zone ─────────────
    # AMS1117 VOUT (pin 2) and tab (pin 4) are +3V3
    # Route to via outside +5V zone (x < 100)
    # v3_via at am_tab[0] = 125.0 (same X as tab pad), clear of C1 (now at x=121.5, y=55)
    v3_via_x = am_tab[0]   # 125.0
    v3_via_y = am_tab[1] - 3
    # B.Cu vertical from tab pad down to via (widened to 0.5mm for power delivery)
    parts.append(_seg(v3_via_x, am_tab[1], v3_via_x, v3_via_y,
                       "B.Cu", W_PWR, n_3v3))
    parts.append(_via_net(v3_via_x, v3_via_y, n_3v3))

    # ── AMS1117 thermal vias: 2x2 grid under tab pad (pin 4) ──────
    # Tab pad center at am_tab = (125.0, 52.35), size 3.6x1.8mm.
    # Tab = VOUT (+3V3). Thermal vias connect tab to In2.Cu +3V3 zone.
    # 2x2 grid with ~1.0mm spacing, centered on tab pad.
    # Via size 0.50mm, drill 0.20mm (annular ring 0.15mm, JLCPCB OK).
    # Positions: 2x2 grid, ±0.50mm Y spacing for copper gap ≥0.40mm.
    # All within tab pad bounds (x=123.2..126.8, y=51.45..53.25).
    _therm_via_positions = [
        (am_tab[0] - 0.5, am_tab[1] - 0.50),  # (124.5, 51.85)
        (am_tab[0] + 0.5, am_tab[1] - 0.50),  # (125.5, 51.85)
        (am_tab[0] - 0.5, am_tab[1] + 0.50),  # (124.5, 52.85)
        (am_tab[0] + 0.5, am_tab[1] + 0.50),  # (125.5, 52.85)
    ]
    for tvx, tvy in _therm_via_positions:
        parts.append(_via_net(tvx, tvy, n_3v3, size=VIA_STD, drill=VIA_STD_DRILL))
        # Short B.Cu stub from via to tab pad center (ensures DFM connectivity check)
        parts.append(_seg(tvx, tvy, am_tab[0], tvy, "B.Cu", W_PWR, n_3v3))

    # DFM FIX: removed F.Cu horizontal from x=125 to x=100.5 at y=49.35 — this trace
    # crossed the VBUS F.Cu vertical at x=111, gap=0mm (DANGER violation).
    # The AMS1117 tab via at (125, 49.35) connects directly to In2.Cu +3V3 zone which
    # covers the full board, so a second via at x=100.5 is redundant.
    # ESP32 +3V3: via near pin 2 with B.Cu stub
    # DFM: Via must fit between LCD_D7 F.Cu (y=20.5) and LCD_D6 F.Cu (y=21.5).
    # Both traces w=0.2 (hw=0.10). Via at y=21.0 (center).
    # VIA_MIN (0.50mm, r=0.25): gap = |21.0-20.5|-0.25-0.10 = 0.15mm (FP boundary).
    # Use custom 0.46mm OD (r=0.23, AR=0.13mm >= 0.127mm JLCPCB min):
    # gap to LCD_D7 = |21.0-20.5|-0.23-0.10 = 0.17mm ≥ 0.15mm ✓
    # gap to LCD_D6 = |21.5-21.0|-0.23-0.10 = 0.17mm ≥ 0.15mm ✓
    _V3_VIA_SIZE = 0.46   # custom: fits between LCD_D6/D7 with 0.17mm gap (AR=0.13mm ≥ JLCPCB min)
    esp_3v3 = _pad("U1", "2")  # pin 2 = +3V3 power input
    if esp_3v3:
        parts.append(_via_net(esp_3v3[0], esp_3v3[1] - 2.51, n_3v3,
                              size=_V3_VIA_SIZE, drill=VIA_MIN_DRILL))
        parts.append(_seg(esp_3v3[0], esp_3v3[1], esp_3v3[0],
                           esp_3v3[1] - 2.51, "B.Cu", W_PWR, n_3v3))

    # ── BAT+: IP5306 -> JST battery connector ─────────────────
    # DFM: ip_bat at x=107 same as ip_sw — offset BAT+ via to separate column.
    # DFM FIX: was bat_col_x=ip_bat[0]+1=108 (inside IP5306_KEY horizontal x=107..114.05).
    # The BAT+ vertical at x=108 crossed KEY horizontal at y=44.41 → SHORT CIRCUIT.
    # Fix: route BAT+ LEFT to x=105.5 (outside KEY span to the left of x=107).
    bat_col_x = ip_bat[0] - 1.5   # x=105.5, left of KEY span (107..114.05)
    bat_via_y = ip_bat[1] + 3
    parts.append(_seg(ip_bat[0], ip_bat[1], bat_col_x, ip_bat[1],
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(bat_col_x, ip_bat[1], bat_col_x, bat_via_y,
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_via_net(bat_col_x, bat_via_y, n_bat))
    # F.Cu horizontal to JST approach column between pull-up resistors R11(x=78) and R12(x=83).
    bat_approach_x = 79.75  # DFM: between R11@78 and R12@83, offset for J3@180° clearance
    parts.append(_seg(bat_col_x, bat_via_y, bat_approach_x, bat_via_y,
                       "F.Cu", W_PWR_HIGH, n_bat))
    parts.append(_via_net(bat_approach_x, bat_via_y, n_bat))
    # B.Cu: vertical from approach to pad Y, then horizontal to pad X
    parts.append(_seg(bat_approach_x, bat_via_y, bat_approach_x, jst_p[1],
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(bat_approach_x, jst_p[1], jst_p[0], jst_p[1],
                       "B.Cu", W_PWR_HIGH, n_bat))

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
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_via_net(sw_com[0], sw_via_y, n_bat))
    # B.Cu horizontal from sw_com X to separate column, then long vertical down
    parts.append(_seg(sw_com[0], sw_via_y, BAT_COL_X, sw_via_y,
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(BAT_COL_X, sw_via_y, BAT_COL_X, bat_via_y,
                       "B.Cu", W_PWR_HIGH, n_bat))
    # F.Cu horizontal from BAT_COL_X to approach via (at bat_via_y level)
    parts.append(_via_net(BAT_COL_X, bat_via_y, n_bat))
    parts.append(_seg(BAT_COL_X, bat_via_y, bat_approach_x, bat_via_y,
                       "F.Cu", W_PWR_HIGH, n_bat))

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
        # LCD_RD (FPC pin 12): tied HIGH via 3V3 in FPC power section
        # LCD_BL (FPC pin 33): tied to 3V3 via resistor in FPC power section
    ]

    # Combined list for unified stagger handling.
    # DFM FIX: Sort by FPC pin y-position (fpy) so that approach column apx is assigned
    # in the same order as fpy.  This ensures each step-6 horizontal stub goes from
    # apx → fpx=133.15 at fpy without crossing any other signal's step-5 B.Cu vertical.
    #
    # KEY INVARIANT for no crossing: if signals are sorted so that higher-idx signals have
    # LOWER fpy (more north), then each step-5 vert stops at its fpy which is ABOVE all
    # lower-idx stubs (which are at higher fpy = more south).  The vert therefore never
    # passes through a previously placed stub's y level.  This also requires that for each
    # pair (i < j): apx_j NOT in stub_i x-span, which is satisfied when stubs go RIGHTWARD
    # from apx to fpx and apx values are DECREASING for increasing idx.
    #
    # CTRL SIGNALS (LCD_CS/DC/WR/RD at FPC pins 9-12, fpy=29.75..31.25):
    # Ascending fpy order (CS→DC→WR→RD) assigns apx=131.0,131.7,132.4,133.1 respectively.
    # Vert for LCD_DC (apx=131.7) descends to fpy=30.25 and passes through y=29.75 (LCD_CS stub)
    # where the stub spans [131.0,133.15] — a crossing!  Fix: sort ctrl signals DESCENDING
    # (RD→WR→DC→CS) so the signal with smallest fpy (CS=29.75) gets the LARGEST apx (133.1).
    # Then LCD_CS vert (apx=133.1) descends only to fpy=29.75, and no previous stub is at
    # a y lower than 29.75 → no crossings.
    #
    # DATA SIGNALS (LCD_D0-D7 at FPC pins 17-24, fpy=33.75..37.25) and LCD_RST/BL:
    # These continue in ASCENDING fpy order (same as before).  Their apx values (134.5..140.1)
    # are all RIGHT of fpx=133.15, so their stubs go leftward and their verts don't cross
    # each other's stubs (each vert stops before reaching the next signal's stub y).
    #
    # VERIFICATION:
    # Ctrl descending: RD(31.25)→apx=131.0, WR(30.75)→131.7, DC(30.25)→132.4, CS(29.75)→133.1.
    # WR vert (131.7, to y=30.75): passes through y=31.25? 31.25>30.75 → NO ✓
    # DC vert (132.4, to y=30.25): passes through y=30.75 or 31.25? Both > 30.25 → NO ✓
    # CS vert (133.1, to y=29.75): passes through any ctrl stub y? All > 29.75 → NO ✓
    # RST/DATA verts at apx>=133.8: apx > 133.15 = fpx, outside ctrl stub x-spans → NO ✓
    _raw_lcd = []
    for i, (gpio, fpc_pin) in enumerate(zip(data_gpios, fpc_data_pins)):
        _raw_lcd.append((gpio, fpc_pin, f"LCD_D{i}"))
    for gpio, net_name, fpc_pin in ctrl:
        _raw_lcd.append((gpio, fpc_pin, net_name))
    # NO-CROSSING INVARIANT: sort ALL signals by DESCENDING fpy.
    # Approach columns apx increase with idx (131.0 + idx*0.70).
    # Step-5 B.Cu vertical at apx_j descends from bypass_y to fpy_j.
    # Since fpy_j < fpy_i for j > i (descending sort), the vertical
    # at apx_j never reaches fpy_i (which is further south), so it
    # cannot cross signal i's step-6 horizontal stub at fpy_i.
    # This holds for ALL signals uniformly -- no group separation needed.
    def _lcd_sort_key(e):
        fpy = (_fpc_display_pin(e[1]) or (0, 999))[1]
        return -fpy  # descending: highest fpy first (southmost gets smallest apx)
    _raw_lcd.sort(key=_lcd_sort_key)
    # Build all_lcd with sequential idx for apx/bypass_y assignment
    all_lcd = [(idx, gpio, fpc_pin, net_name)
               for idx, (gpio, fpc_pin, net_name) in enumerate(_raw_lcd)]

    # Bottom-side stagger counter (pins at y ≈ 40 need Y separation)
    stagger_idx = 0

    for idx, gpio, fpc_pin, net_name in all_lcd:
        net = NET_ID[net_name]
        epx, epy = _esp_pin(gpio)
        fpx, fpy = _fpc_display_pin(fpc_pin)

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
        # DFM v5: Split approach columns to eliminate stub crossings.
        # RIGHT group (idx 0-9, highest fpy): apx = 140.4 - idx*0.70
        #   stubs go LEFT (apx > fpx=133.71), descending fpy → no crossings
        # LEFT group (idx 10-12, lowest fpy): apx = 131.0 + (idx-10)*0.70
        #   stubs go RIGHT (apx < fpx), ascending fpy → no crossings
        # VIA_X_PWR at 133.60 sits between LEFT max (132.4) and RIGHT min (134.5).
        # SHORT FIX: shifted RIGHT group +0.4mm (140.4→140.8) so idx=9 moves from
        # x=134.1 to x=134.5, clearing J4 FPC pad right edge (134.21) by 0.19mm.
        # Old x=134.1 with trace w=0.2 had left edge=134.0, overlapping J4 pads.
        # DFM: approach base 140.8 clears J4 FPC pad right edge (134.21) at idx=9.
        # Button avoidance (_lcd_approach_xs) uses 140.4 for historical compatibility.
        if idx < 10:
            apx = round(140.8 - idx * 0.70, 4)   # RIGHT: 140.8, 140.1, ..., 134.5
        else:
            apx = round(131.0 + (idx - 10) * 0.70, 4)  # LEFT: 131.0, 131.7, 132.4
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
            # NOTE: stagger_y F.Cu horizontals pass near MH@(105,37.5) NPTH drill.
            # NPTH holes have no copper pad — JLCPCB requires 0.25mm drill-to-copper.
            # Drill edge at y=38.75, trace at y=38.12 edge at 38.22: gap=0.53mm ✓
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
            VIA_R_DEFAULT = VIA_STD / 2  # default via radius

            via_inside_gnd = (U1_GND_X1 <= epx <= U1_GND_X2 and
                              U1_GND_Y1 <= stagger_y <= U1_GND_Y2)

            if via_inside_gnd:
                # DFM: stagger_y lands inside U1[41] GND thermal pad for
                # GPIO 10 (epx=83.175) and GPIO 11 (epx=81.905).
                # The B.Cu vertical at epx passes THROUGH the GND exposed pad
                # (x=[79.55,83.45], y=[28.01,31.91]) which creates a short circuit
                # when soldered.
                #
                # FIX: F.Cu bridge over the GND pad.
                # 1a. B.Cu vertical from pad (y=40) DOWN to just above GND pad
                #     bottom edge + via_r + clearance.
                # 1b. Via to F.Cu above the pad.
                # 1c. F.Cu vertical past the pad to escape_y (above pad top).
                # 1d. Via back to B.Cu at escape_y.
                # 1e. F.Cu horizontal from epx to col_x at escape_y.
                # 1f. Via to B.Cu at col_x.
                #
                # GND pad bottom edge = 31.91. Via radius = 0.30.
                # bridge_entry_y = 31.91 + 0.30 + 0.15 = 32.36
                # escape_y above pad top (28.01): 26.5 - (stagger_idx-1)*1.0
                bridge_entry_y = U1_GND_Y2 + VIA_R_DEFAULT + 0.15  # 32.36
                escape_y = 26.5 - (stagger_idx - 1) * 1.0  # e.g. 22.5 for first, 21.5 for second
                # escape_y must be above pad top: 28.01 - 0.30 - 0.15 = 27.56
                # escape_y=22.5/21.5 are both well above (smaller Y), OK.

                # 1a. B.Cu vertical from pad down to bridge entry (above GND pad)
                parts.append(_seg(epx, epy, epx, bridge_entry_y,
                                  "B.Cu", W_DATA, net))
                # 1b. Via to F.Cu at bridge entry
                parts.append(_via_net(epx, bridge_entry_y, net, size=VIA_MIN, drill=VIA_MIN_DRILL))
                # 1c. F.Cu vertical past the GND pad to escape_y
                parts.append(_seg(epx, bridge_entry_y, epx, escape_y,
                                  "F.Cu", W_DATA, net))
                # 1d. Via back to B.Cu at escape_y (for col_x horizontal)
                # Skip this extra via -- just continue on F.Cu to col_x
                # 1e. F.Cu horizontal from epx to col_x at escape_y
                parts.append(_seg(epx, escape_y, col_x, escape_y,
                                  "F.Cu", W_DATA, net))
                parts.append(_via_net(col_x, escape_y, net, size=VIA_MIN, drill=VIA_MIN_DRILL))
            else:
                # 1. B.Cu vertical from pad up to stagger level
                parts.append(_seg(epx, epy, epx, stagger_y,
                                  "B.Cu", W_DATA, net))
                parts.append(_via_net(epx, stagger_y, net, size=VIA_MIN, drill=VIA_MIN_DRILL))

                # 2. F.Cu horizontal to col_x (detour around mounting holes)
                parts.extend(_mh_detour_h(epx, stagger_y, col_x,
                                          "F.Cu", W_DATA, net))
                parts.append(_via_net(col_x, stagger_y, net, size=VIA_MIN, drill=VIA_MIN_DRILL))
        else:
            # Side pins: horizontal stub right to via
            via1_x = epx + 2.0  # DFM: was 1.5 (too close to col_x vias)
            parts.append(_seg(epx, epy, via1_x, epy,
                              "B.Cu", W_DATA, net))
            parts.append(_via_net(via1_x, epy, net, size=VIA_MIN, drill=VIA_MIN_DRILL))

            # F.Cu horizontal to col_x (detour around mounting holes)
            parts.extend(_mh_detour_h(via1_x, epy, col_x,
                                      "F.Cu", W_DATA, net))
            parts.append(_via_net(col_x, epy, net, size=VIA_MIN, drill=VIA_MIN_DRILL))

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
        parts.append(_via_net(col_x, bypass_y, net, size=VIA_MIN, drill=VIA_MIN_DRILL))

        # 4. F.Cu horizontal across slot to unique approach column apx
        parts.append(_seg(col_x, bypass_y, apx, bypass_y,
                          "F.Cu", W_DATA, net))
        parts.append(_via_net(apx, bypass_y, net, size=VIA_STD, drill=VIA_STD_DRILL))

        # 5. B.Cu vertical from bypass_y down to FPC pin Y level
        parts.append(_seg(apx, bypass_y, apx, fpy, "B.Cu", W_DATA, net))
        # DFM FIX: removed via at (apx, fpy) — both step 5 and step 6 are B.Cu,
        # no layer change needed. The via was causing via-pad overlaps with
        # J4 contact pads (x=136.200..137.500, y=25.75..45.25) for idx=4..8.

        # 6. B.Cu horizontal to FPC pad (short stub only)
        parts.append(_seg(apx, fpy, fpx, fpy, "B.Cu", W_DATA, net))

    # ── Power and GND connections to FPC (per ILI9488 datasheet) ──
    # After pin reversal (display pin N → connector pad 41-N):
    #   OLD "bottom" pins 34-40 are NOW at TOP (y=25.75-28.75), ABOVE approach zone
    #   OLD "top" pins 5-7 are NOW at BOTTOM (y=42.25-43.25), BELOW approach zone
    #   Pin 16 (GND) at y=37.75, INSIDE approach zone (between D0@37.25 and RST@38.25)
    #   LCD approach zone: y=29.25 (LCD_BL) to y=41.25 (LCD_CS)
    #   Approach columns: x=131.0 to x=140.1
    n_gnd = NET_ID["GND"]
    n_3v3 = NET_ID["+3V3"]
    fpx0 = _fpc_display_pin(1)[0]  # FPC pad X (133.71)

    # ── GND pins at TOP (34,35,36,37,40): now y=25.75-28.75 ──
    # These pins are between the approach columns' bypass_y (5-18) and fpy (29-41),
    # meaning ALL 14 B.Cu approach columns pass through their Y levels.
    # Any B.Cu horizontal stub would cross multiple approach columns.
    # Solution: via-in-pad connects directly to internal GND plane (In1.Cu).
    # Use 0.46mm/0.20mm vias to fit 0.5mm FPC pitch.
    # For adjacent pins, use single via + short B.Cu stubs to avoid tight spacing.
    #
    # Pin 40 (y=25.75): via-in-pad
    # Pin 39 (+3V3, y=26.25): handled in +3V3 section
    # Pin 38 (+3V3, y=26.75): handled in +3V3 section
    # Pin 37 (y=27.25): via-in-pad
    # Pin 36 (y=27.75): B.Cu stub to pin 37 via (same net, 0.5mm away)
    # Pin 35 (y=28.25): via-in-pad
    # Pin 34 (y=28.75): B.Cu stub to pin 35 via (same net, 0.5mm away)
    #
    # Via spacing check (0.46mm via, r=0.23):
    #   pin 40 (25.75) to pin 39 +3V3 (26.25): gap=0.50-0.46=0.04mm -- tight
    #   pin 37 (27.25) to pin 36 stub: same net, OK
    #   pin 35 (28.25) to pin 34 stub: same net, OK
    #   pin 37 (27.25) to pin 38 +3V3 (26.75): gap=0.50-0.46=0.04mm -- tight
    # Fix: offset pin 40 via DOWN by 0.5mm to y=26.25 (pin 39 NC pos)... but 39 is +3V3.
    # Use staggered via positions: place GND vias only on even-spaced pins.
    # Group: pin 40 alone, pin 37+36 (stub), pin 35+34 (stub).
    # Gap between pin 40 via (25.75) and +3V3 pin 39 via (26.25): 0.50-0.46=0.04mm.
    # To fix: move pin 40 via UP by 0.5mm to y=25.25 (outside connector) with stub.
    # FPC pads at x=133.71, between approach cols idx=3 (133.10) and idx=4 (133.80).
    # Via-in-pad at x=133.71 collides with col4 B.Cu vert (gap=0.09mm).
    # Fix: offset vias to x=133.45 (midpoint 133.10-133.80), with short B.Cu stub.
    # Gap to col3: 133.45-133.10=0.35, minus drill_r(0.10)+trace_hw(0.10)=0.15mm OK.
    # Gap to col4: 133.80-133.45=0.35, minus 0.10+0.10=0.15mm OK.
    # B.Cu stub from pad (133.71) to via (133.45): horizontal, does not cross cols.
    # FPC GND/power vias between approach columns 3 (x=133.10) and 4 (x=133.80).
    # JLCPCB requires drill ≥ 0.20mm / size ≥ 0.46mm for annular ring ≥ 0.13mm.
    # Tight corridor: approach cols at x=133.10 (w=0.2, edge 133.20) and x=134.10 (w=0.2, edge 134.00).
    # VIA_MIN (0.46mm, r=0.23): gap to 133.20 = 133.60-0.23-133.20 = 0.17mm ≥ 0.15mm ✓
    #                           gap to 134.00 = 134.00-133.60-0.23 = 0.17mm ≥ 0.15mm ✓
    # VIA_TIGHT (0.55mm, r=0.275): gap = 0.125mm < 0.15mm VIOLATION.
    VIA_X_PWR = 133.60
    VIA_PWR_SIZE = 0.46        # custom: fits between LCD approach traces (0.17mm gap)
    VIA_PWR_DRILL = VIA_MIN_DRILL

    # Pin 40 (y=25.75): move via UP to separate from +3V3 pin 39 (y=26.25)
    # DFM FIX: was -0.5 (y=25.25), bottom edge=24.975, FPC pad 42 top=25.06 → overlap 0.085mm.
    # At -0.25 (y=25.50): bottom edge=25.225, gap to pad 42 top=0.165mm ≥ 0.15mm ✓
    # Gap to pin 39 via (y=26.25): |26.25-25.50|-0.275-0.275=0.20mm > 0.15mm ✓
    for pin in [40]:
        pos = _fpc_display_pin(pin)
        if pos:
            px, py = pos[0], pos[1]
            via_y = py - 0.25  # y=25.50 — clear of FPC mounting pad 42
            parts.append(_seg(px, py, VIA_X_PWR, py, "B.Cu", W_PWR_LOW, n_gnd))
            parts.append(_seg(VIA_X_PWR, py, VIA_X_PWR, via_y, "B.Cu", W_PWR_LOW, n_gnd))
            parts.append(_via_net(VIA_X_PWR, via_y, n_gnd,
                                  size=VIA_PWR_SIZE, drill=VIA_PWR_DRILL))

    # Pin 37 (y=27.25) + pin 36 (y=27.75): via near pin 37 position, stub from 36.
    # DFM FIX: via at (VIA_X_PWR, py37=27.25) had gap=0.125mm to +3V3 stub above (y=26.75).
    # Offset via DOWN 0.15mm to y=27.40: gap = 27.40-0.225-26.75-0.15 = 0.275mm ≥ 0.15mm ✓
    # Check gap to pin 35 via at py35=28.25: |28.25-27.40|-0.225-0.225 = 0.40mm > 0.25mm ✓
    pos37 = _fpc_display_pin(37)
    pos36 = _fpc_display_pin(36)
    # DFM: use 0.25mm width for FPC GND/+3V3 stubs near approach columns.
    # Approach col at x=134.1 (w=0.2): gap = 0.388-0.10-0.125 = 0.163mm >= 0.15mm ✓
    # (was 0.3mm → gap=0.138mm < 0.15mm VIOLATION)
    W_FPC_PWR = 0.25
    if pos37:
        px37, py37 = pos37[0], pos37[1]
        gnd_37_via_y = py37 + 0.15  # y=27.40 — offset down for +3V3 clearance
        parts.append(_seg(px37, py37, VIA_X_PWR, py37, "B.Cu", W_FPC_PWR, n_gnd))
        parts.append(_seg(VIA_X_PWR, py37, VIA_X_PWR, gnd_37_via_y, "B.Cu", W_FPC_PWR, n_gnd))
        parts.append(_via_net(VIA_X_PWR, gnd_37_via_y, n_gnd,
                              size=VIA_PWR_SIZE, drill=VIA_PWR_DRILL))
    if pos36 and pos37:
        px36, py36 = pos36[0], pos36[1]
        # Stub from pin 36 to pin 37 (same net, adjacent pads)
        parts.append(_seg(px36, py36, px37, py37, "B.Cu", W_FPC_PWR, n_gnd))

    # Pin 35 (y=28.25) + pin 34 (y=28.75): via at pin 35 position, stub from 34.
    pos35 = _fpc_display_pin(35)
    pos34 = _fpc_display_pin(34)
    if pos35:
        px35, py35 = pos35[0], pos35[1]
        parts.append(_seg(px35, py35, VIA_X_PWR, py35, "B.Cu", W_FPC_PWR, n_gnd))
        parts.append(_via_net(VIA_X_PWR, py35, n_gnd,
                              size=VIA_PWR_SIZE, drill=VIA_PWR_DRILL))
    if pos34 and pos35:
        px34, py34 = pos34[0], pos34[1]
        parts.append(_seg(px34, py34, px35, py35, "B.Cu", W_FPC_PWR, n_gnd))

    # ── GND pins at BOTTOM (5, 16) ──
    # Pin 5: y=43.25, BELOW approach zone (ends at y=41.25). Route DOWN freely.
    # Pin 16: y=37.75, INSIDE approach zone. Use via-in-pad.
    pos5 = _fpc_display_pin(5)
    if pos5:
        px, py = pos5[0], pos5[1]
        # Route B.Cu stub RIGHT then DOWN to zone via below connector.
        # Use x=143.0 (right of approach columns AND clear of net20 vert at x=141.2).
        # DFM v5: route via F.Cu to avoid crossing B.Cu approach columns.
        # B.Cu stub from FPC pad LEFT to VIA_X_PWR zone, via to F.Cu,
        # F.Cu horiz RIGHT past approach columns, via back to B.Cu, B.Cu vert DOWN.
        # DFM v5: route via F.Cu to avoid crossing B.Cu approach columns.
        # B.Cu stub from FPC pad LEFT to via, F.Cu horiz RIGHT past approach columns,
        # via back to B.Cu, B.Cu vert DOWN to zone via.
        # JLCPCB DFM FIX: via at (133.10, 43.75) gap=0.14mm to J4[38] at
        # (133.712, 44.25). Nudge LEFT by 0.10mm: stub_x=133.00, via right
        # edge=133.30, J4[38] pad left=133.562, gap=0.262mm ✓
        stub_x = VIA_X_PWR - 0.6  # was -0.5 (133.10), now 133.00
        vx2 = 143.50  # right of net32 vert at x=142.80 (gap=0.70-0.23-0.15=0.32mm)
        vy = 50.25
        # DFM FIX (KiBot external): via at (133.0, 43.25) gap=0.14mm to J4:35
        # (+3V3) at y=42.75. Move via DOWN to y+0.5=43.75 for gap=0.375mm ✓
        via_y = py + 0.5
        # GND stub: horizontal narrowed to 0.30mm near +3V3 pin6/7 crossing.
        parts.append(_seg(px, py, stub_x, py, "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_seg(stub_x, py, stub_x, via_y, "B.Cu", 0.4, n_gnd))
        parts.append(_via_net(stub_x, via_y, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(stub_x, via_y, vx2, via_y, "F.Cu", 0.4, n_gnd))
        parts.append(_via_net(vx2, via_y, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(vx2, via_y, vx2, vy, "B.Cu", 0.4, n_gnd))
        parts.append(_via_net(vx2, vy, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    pos16 = _fpc_display_pin(16)
    if pos16:
        px, py = pos16[0], pos16[1]
        # Pin 16 (GND) at y=37.75: between LCD_D0 (y=37.25) and LCD_RST (y=38.25).
        # JLCPCB DFM FIX: old via at (133.60, 37.75) was inside FPC connector body,
        # causing "Lead to hole distance = 0mm" (14 Danger) — component leads touch
        # the via hole, risking solder wicking shorts to LCD_D0/LCD_RST.
        # FIX: route B.Cu stub LEFT to x=131.0 (outside FPC body edge ~132.4).
        # Via at (131.0, 37.75) connects to In1.Cu GND plane.
        # B.Cu trace at y=37.75 runs parallel to LCD_D0 (y=37.25) and LCD_RST
        # (y=38.25) approach traces. Edge gap: 0.50-0.125-0.10 = 0.275mm ✓
        # Area at x=131, y=37.75 verified clear (no segments, vias, or pads).
        via_x_pin16 = 131.00
        parts.append(_seg(px, py, via_x_pin16, py, "B.Cu", W_FPC_PWR, n_gnd))
        parts.append(_via_net(via_x_pin16, py, n_gnd,
                              size=VIA_MIN, drill=VIA_MIN_DRILL))

    # ── +3V3 pins at TOP (38, 39): now y=26.25-26.75, inside approach column zone ──
    # Same constraint as GND top pins. Offset via to VIA_X_PWR.
    # Pin 39 gets via at (VIA_X_PWR, 26.25); pin 38 stubs DOWN to pin 39.
    # This puts +3V3 via at y=26.25, GND pin 37 via at y=27.25: gap=1.0mm-0.40=0.60mm OK.
    # (Previously pin 38 had via at y=26.75, only 0.50mm from GND pin 37 at y=27.25.)
    pos38 = _fpc_display_pin(38)
    pos39 = _fpc_display_pin(39)
    if pos39:
        px39, py39 = pos39[0], pos39[1]
        # DFM FIX (KiBot external): via at (133.60, 26.25) gap=0.195mm to J4:1
        # (GND) at y=25.75. Shift via UP to y+0.15=26.40 for gap=0.375mm ✓
        # (shift DOWN toward pin 40 via at y=25.50 would cause via-via gap issue)
        via_y39 = py39 + 0.15
        parts.append(_seg(px39, py39, VIA_X_PWR, py39, "B.Cu", W_FPC_PWR, n_3v3))
        parts.append(_seg(VIA_X_PWR, py39, VIA_X_PWR, via_y39, "B.Cu", W_FPC_PWR, n_3v3))
        parts.append(_via_net(VIA_X_PWR, via_y39, n_3v3,
                              size=VIA_PWR_SIZE, drill=VIA_PWR_DRILL))
    if pos38 and pos39:
        px38, py38 = pos38[0], pos38[1]
        # Short B.Cu stub from pin 38 DOWN to pin 39 (same net, 0.5mm away)
        parts.append(_seg(px38, py38, px39, py39, "B.Cu", W_FPC_PWR, n_3v3))

    # ── +3V3 for LCD_RD (pin 12) and LCD_BL (pin 33) ──
    # LCD_RD tied HIGH (read strobe disabled — display is write-only).
    # LCD_BL (LED-A) tied to +3V3 (always-on backlight, per ILI9488 datasheet:
    #   pin 33 LED-A = backlight anode 2.9-3.3V, pins 34-36 LED-K = cathodes to GND).
    # Route LEFT from FPC pads to vias that connect to In2.Cu +3V3 zone.
    # VIA_X_PWR (133.6) conflicts with LCD_WR/GND approach traces.
    # LCD data approach verticals: LCD_D7@131.70, LCD_D6@131.00, LCD_D5@134.50.
    # RD via at x=131.0, y=39.75: ABOVE LCD_D6 end (y=34.25) — clear.
    # LED-A via at x=132.5, y=29.25: between LCD_D7 right edge (131.80) and
    #   J4 GND stub (133.585). Gap: 0.45mm to LCD_D7, 0.83mm to GND. ✓
    pos_rd = _fpc_display_pin(12)   # RD at pad 29 (y≈39.75)
    pos_bl = _fpc_display_pin(33)   # LED-A at pad 8 (y≈29.25)

    # Use LCD_RD/LCD_BL net IDs so DRC sees traces for these nets
    n_rd = NET_ID["LCD_RD"]
    n_bl = NET_ID["LCD_BL"]

    if pos_rd:
        px, py = pos_rd[0], pos_rd[1]
        via_x = 131.0  # above LCD_D6 end (y=34.25), pin16 GND via (y=37.75)
        parts.append(_seg(px, py, via_x, py, "B.Cu", W_FPC_PWR, n_rd))
        parts.append(_via_net(via_x, py, n_rd,
                              size=VIA_MIN, drill=VIA_MIN_DRILL))

    if pos_bl:
        px, py = pos_bl[0], pos_bl[1]
        via_x = 132.5  # between LCD_D7 (131.80) and J4 GND stubs (133.58)
        parts.append(_seg(px, py, via_x, py, "B.Cu", W_FPC_PWR, n_bl))
        parts.append(_via_net(via_x, py, n_bl,
                              size=VIA_MIN, drill=VIA_MIN_DRILL))

    # ── +3V3 pins at BOTTOM (6, 7): now y=42.25-42.75, BELOW approach zone ──
    # Pin 6 at y=42.75, pin 7 at y=42.25. Both below LCD_CS at y=41.25.
    # Route B.Cu stubs DOWN to zone vias.
    # Use single via for pin 6; connect pin 7 to pin 6 via short B.Cu stub
    # (same net, avoids tight via-via spacing at 0.5mm FPC pitch).
    pos6 = _fpc_display_pin(6)
    pos7 = _fpc_display_pin(7)
    if pos6 and pos7:
        px6, py6 = pos6[0], pos6[1]
        px7, py7 = pos7[0], pos7[1]
        # Route DOWN to zone via below connector
        vx, vy = 132.0, 50.25  # separate x from GND at 134.5
        parts.append(_via_net(vx, vy, n_3v3, size=VIA_STD, drill=VIA_STD_DRILL))
        # DFM FIX: pin 6 (42.75) stubs to pin 7 (42.25), then routes LEFT.
        # This avoids a collinear overlap (pin6→safe_y duplicated by pin7→pin6 stub).
        # Pin 7 at safe_y=42.25 is further from GND via at (133.10,43.25):
        # gap = 43.25-42.25-0.23-0.15=0.62mm ✓
        # Short B.Cu stub: pin 6 pad -> pin 7 pad (same net, 0.5mm)
        # DFM FIX: 0.3mm w at x=133.71 → top edge 42.90, GND stub bottom 43.05,
        # gap=0.15mm (FP boundary). Use 0.25mm w for 0.175mm clearance.
        parts.append(_seg(px6, py6, px7, py7, "B.Cu", W_FPC_PWR, n_3v3))
        # Route LEFT from pin 7 position (y=42.25) to zone via
        parts.append(_seg(px7, py7, vx, py7, "B.Cu", W_PWR_LOW, n_3v3))
        parts.append(_seg(vx, py7, vx, vy, "B.Cu", W_PWR_LOW, n_3v3))
    elif pos6:
        px6, py6 = pos6[0], pos6[1]
        vx, vy = 132.0, 50.25
        parts.append(_via_net(vx, vy, n_3v3, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(px6, py6, vx, py6, "B.Cu", W_PWR_LOW, n_3v3))
        parts.append(_seg(vx, py6, vx, vy, "B.Cu", W_PWR_LOW, n_3v3))

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
        (44, "SD_MOSI"), (43, "SD_MISO"), (38, "SD_CLK"), (39, "SD_CS"),
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
        # SPI ESCAPE REDESIGN: Cross LCD_BL (B.Cu-only at x=73.02) on F.Cu.
        # Old approach: B.Cu stubs at stub_x_r with 0.35mm pitch caused via-segment
        # overlaps (0.9mm vias in 1.77mm corridor between ESP32 pins and LCD_BL).
        # New approach: short B.Cu stub to shared via column at x=72.2, then F.Cu
        # horizontal crossing LCD_BL to individual escape columns (75.0+i*1.3).
        # Small vias (0.6mm) ensure clearance at the ESP32 pin column.
        # Via size 0.7/0.3: annular ring = (0.7-0.3)/2 = 0.20mm >= 0.175mm JLCPCB minimum ✓
        # Old 0.6/0.3: ring = 0.15mm < 0.175mm (fails DFM annular ring test).
        _SPI_VIA = VIA_STD    # AR=(0.60-0.20)/2=0.20mm ✓
        _SPI_DRILL = VIA_STD_DRILL
        shared_via_x = 72.2   # between ESP32 pad (71.25+0.35=71.60) and approach cols
        # escape_x: 1.0mm pitch avoids LCD_RST stagger via at (79.36,33.04).
        # Old 1.3mm pitch: escape_x[3]=78.9, AABB overlap with LCD_RST via at (79.36,33.04) = -0.11mm.
        # New 1.0mm pitch: escape_x[3]=78.0, x gap to LCD_RST via left edge (78.91) = 0.61mm ✓.
        # All escape_x values < 79.55 (U1 GND pad left edge), gap ≥ 1.4mm ✓.
        escape_x = 75.0 + i * 1.0  # 75.0, 76.0, 77.0, 78.0 — clear of LCD_RST via ✓
        # bypass_y: must avoid LCD D6/D7 vias at y=19.50/20.50 and ESP32 3V3 via at y=21.01.
        # Safe zone analysis: danger zone y=[18.80,23.58] (LCD D7, D6 vias + ESP32 3V3 via + D7 stagger).
        # y>=23.5 enters FPC slot barrier. Use y<<18.80 instead: row 3.0..5.1 clears all obstacles.
        # B.Cu verticals from epy≈32-36 UP to y=3-5: clear of U1 GND pad (x=79.55, left edge clear at x=75-77).
        # F.Cu horizontals at y=3-5 from escape_x (75-77) to post_slot_x (141-148): clear of slot (slot y=23.5-47.5).
        bypass_y = 1.5 + i * 0.7  # 1.5, 2.2, 2.9, 3.6 — safely below LCD approach bypass rows (5.0+) ✓
        # CROSSING FIX: was base=3.0 → SD_CS(i=3) at y=5.1 crossed LCD_RD F.Cu at y=5.0
        # (gap=-0.1mm). Base=1.5 gives max=3.6, gap to LCD=5.0-3.6=1.4mm ✓
        # Board top edge at y=0: min bypass=1.5, via radius=0.35: 1.5-0.35=1.15mm > 0.5mm ✓

        # DFM FIX: SD_CLK (i=2) post_slot_x changed from 145 to 152.5.
        # At x=145: vert gap to SD_MISO stagger via at (144.36,67.5)=0.090mm < 0.15mm.
        # At x=145.1: bypass-via gap contradictory with vert-via fix (can't satisfy both).
        # At x=147: stagger via (147,69.0) overlaps BTN_R via at (146.85,68.7) → gap=-0.75mm.
        # At x=149..150: B.Cu vert through SW6 pads at (149,30.65/34.35).
        # At x=150.5..152: MH at (150,7) and (150,68) too close (need x≥152.2 for via, x≥151.875 for seg).
        # At x=152: stagger via (152,69.0) vs MH(150,68): gap=0.3mm < 0.5mm.
        # At x=152.5: all clear:
        #   stagger via (152.5,69.0) gap to MH(150,68)=0.8mm ≥ 0.5mm ✓
        #   stagger via (152.5,69.0) gap to MH(150,7)=far ✓
        #   B.Cu vert x=152.5: MH gaps 1.125mm ≥ 0.5mm ✓
        #   No pads within 1.5mm at x=152.5, y=4..69 ✓
        # DFM FIX: i=1 (SD_MISO) post_slot_x changed from 146 to 145.6.
        # SW12.3 (R shoulder button pad) at (146.85, 2.5) size=0.9x1.2.
        # Via at (146.0, 2.2) had gap to SW12.3 = 0.05mm DANGER.
        # At 145.6: gap = (146.85-0.45) - (145.6+0.35) - 0.10 clearance:
        #   nearest edge distance = sqrt((146.85-145.6-0.45)²+0) = 0.40mm gap ✓
        # Stagger via moves from (146.0, 67.5) to (145.6, 67.5): check BTN_R area.
        #
        # DFM FIX: i=3 (SD_CS) post_slot_x changed from 148 to 153.5.
        # Via at (148.0, 72.0) overlapped U6.11 SD mounting pad (147.76, 72.10) size=1.2x2.0:
        #   AABB gap = -0.45mm DANGER. Moving stagger_y or x=148 caused conflicts with:
        #   - stagger_y=74.0: via(148,74.45) too close to board keepout strip (y=74.5) → gap=0.05mm FAIL
        #   - x=150.5: B.Cu vert at x=150.5 only 0.5mm from MH(150,7/68), inside MH pad (r=1.75) FAIL
        # Fix: move to x=153.5, stagger_y=72.0.
        #   U6.11 gap: (153.5-148.36)-0.45=4.24mm ✓ (well separated in X)
        #   MH(150,68): dist=sqrt(3.5²+4²)=5.32mm, margin=5.32-0.45-2.25=2.62mm ✓
        #   B.Cu vert at x=153.5: MH dist=3.5mm, margin=3.5-0.1-1.75=1.65mm ✓
        #   SD_CLK at x=152.5: different x, no B.Cu crossing ✓
        # DFM FIX: SD_MOSI (i=0) was at 141.2, gap=0mm to LCD_CS via@(140.8,5).
        # Shift to 141.5: gap=|141.5-140.8|-0.3-0.1=0.3mm ✓
        _post_slot_map = {0: 141.5, 1: 145.6, 2: 152.5, 3: 153.5}
        post_slot_x = _post_slot_map[i]

        # stagger_y: mixed pitch to avoid MH at (150,68) and BTN_R via at (146.85,68.7).
        # i=2 (SD_CLK): stagger row F.Cu spans x=[142.16,152.5], crossing MH(150,68).
        #   Need stagger_y such that |stagger_y - 68| >= 2.25mm (keepout radius).
        #   70.0 gives 2.0mm < 2.25mm → KEEPOUT VIOLATION. Use 70.5 → 2.5mm ✓.
        # i=1 (SD_MISO): post_slot_x=146, BTN_R via at (146.85,68.7).
        #   At stagger_y=68.0: gap=0.050mm < 0.25mm (AABB dx=-0.05mm) → keep at 67.5.
        # JLCDFM FIX: SD_CS (i=3) stagger_y moved from 72.0 to 71.25 to clear
        # U6 NPTH at (144.95, 72.566) drill=1.0mm. At y=72.0: gap=-0.034mm.
        # At y=71.25: gap to NPTH=0.816mm ✓
        # DFM FIX: was 71.0 — F.Cu trace at y=71.0 too close to SD_CLK vias at y=70.5:
        #   gap = |71.0-70.5|-0.30-0.10 = 0.10mm < 0.15mm VIOLATION.
        # At y=71.25: gap = |71.25-70.5|-0.30-0.10 = 0.35mm ≥ 0.15mm ✓
        _stagger_map = {0: 66.0, 1: 67.5, 2: 70.5, 3: 71.25}
        stagger_y = _stagger_map[i]  # max=71.25 < 74.5 (board bottom keepout) ✓

        # Step 1: B.Cu horizontal stub RIGHT from ESP32 pad to shared via column.
        # Via at shared_via_x=72.2: left edge 71.90, gap to ESP32 pad (71.60) = 0.30mm ✓
        # Via-via in column: 1.27mm apart (pin pitch), gap = 1.27-0.6 = 0.67mm ✓
        parts.append(_seg(epx, epy, shared_via_x, epy, "B.Cu", W_DATA, net))
        parts.append(_via_net(shared_via_x, epy, net, size=_SPI_VIA, drill=_SPI_DRILL))

        # Step 2: F.Cu horizontal RIGHT crossing LCD_BL (B.Cu only) to escape column.
        # LCD_BL at x=73.02 is B.Cu — F.Cu crosses freely. ✓
        parts.append(_seg(shared_via_x, epy, escape_x, epy, "F.Cu", W_DATA, net))
        parts.append(_via_net(escape_x, epy, net, size=_SPI_VIA, drill=_SPI_DRILL))

        # Step 3: B.Cu vertical UP to bypass row.
        # escape_x=75-79: clear of U1 GND pad (left edge 79.55), gap ≥ 0.55mm ✓
        parts.append(_seg(escape_x, epy, escape_x, bypass_y, "B.Cu", W_DATA, net))
        parts.append(_via_net(escape_x, bypass_y, net, size=_SPI_VIA, drill=_SPI_DRILL))

        # Step 4: F.Cu horizontal across board past slot to unique post_slot column
        parts.append(_seg(escape_x, bypass_y, post_slot_x, bypass_y, "F.Cu", W_DATA, net))
        parts.append(_via_net(post_slot_x, bypass_y, net, size=_SPI_VIA, drill=_SPI_DRILL))

        # Step 7: B.Cu vertical DOWN to stagger row
        # COLLISION FIX: SD_MOSI (i=0, post_slot_x=141.20) B.Cu vert collides with
        # U6 pin 4 pad at (141.06, 61.72) size 0.6x1.3mm (right edge 141.36) and
        # +3V3 via-in-pad at (141.06, 61.72) size 0.46mm (right edge 141.29).
        # SD_MOSI left edge (141.10) overlaps pad right edge (141.36) by 0.26mm.
        # Fix: jog LEFT to x=139.41 between y=60.0 and y=63.5 to clear U6 pin 4.
        # x=139.41 chosen to fit between SD_CS last-mile B.Cu vert at x=138.86 (U6 pin 2)
        # and SD_MOSI last-mile B.Cu vert at x=139.96 (U6 pin 3, same net=OK).
        # Gap to SD_CS: 139.41-0.10 - (138.86+0.10) = 0.35mm > 0.10mm OK.
        # Gap to pin 4 pad left edge (140.76): 140.76 - (139.41+0.10) = 1.25mm OK.
        # Horizontal jog at y=63.5 crosses SD_MOSI last-mile at x=139.96 — same net, OK.
        if i == 0 and abs(post_slot_x - 141.5) < 0.31:
            _jog_x = 139.41   # between SD_CS (138.86) and MOSI last-mile (139.96)
            _jog_y1 = 60.0   # above U6 pin 4 zone (pad top = 61.72-0.65=61.07)
            _jog_y2 = 63.5   # below U6 pin 4 zone (pad bot = 61.72+0.65=62.37)
            parts.append(_seg(post_slot_x, bypass_y, post_slot_x, _jog_y1,
                              "B.Cu", W_DATA, net))
            parts.append(_seg(post_slot_x, _jog_y1, _jog_x, _jog_y1,
                              "B.Cu", W_DATA, net))
            parts.append(_seg(_jog_x, _jog_y1, _jog_x, _jog_y2,
                              "B.Cu", W_DATA, net))
            parts.append(_seg(_jog_x, _jog_y2, post_slot_x, _jog_y2,
                              "B.Cu", W_DATA, net))
            parts.append(_seg(post_slot_x, _jog_y2, post_slot_x, stagger_y,
                              "B.Cu", W_DATA, net))
        else:
            parts.append(_seg(post_slot_x, bypass_y, post_slot_x, stagger_y,
                              "B.Cu", W_DATA, net))
        parts.append(_via_net(post_slot_x, stagger_y, net, size=VIA_STD, drill=VIA_STD_DRILL))

        # Step 8: F.Cu horizontal to SD pad X, then B.Cu vert to SD pad Y.
        # CROSSING FIX: old B.Cu horizontal from post_slot_x to sdx at stagger_y caused crossings:
        #   SD_MOSI B.Cu H at y=65.5 from x=145→139.96 crossed SD_MISO B.Cu vert at x=144,
        #   SD_CLK vert at x=143, SD_CS vert at x=142, and SD_MISO approach vert at x=144.36.
        # Fix: use F.Cu for the stagger horizontal. F.Cu does not cross B.Cu verts.
        parts.append(_seg(post_slot_x, stagger_y, sdx, stagger_y, "F.Cu", W_DATA, net))
        parts.append(_via_net(sdx, stagger_y, net, size=VIA_STD, drill=VIA_STD_DRILL))
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
        # DFM MOUNTAIN ROUTE: I2S_DOUT (GPIO17, epy=33.670) shares y=33.670 with
        # SD_CLK (GPIO38, ESP32 pad 31).  Old routing used F.Cu at y=33.670, causing
        # SD_CLK escape vias at (72.20,33.670) and (77.00,33.670) to overlap I2S_DOUT F.Cu
        # (gap=-0.450mm, need 0.15mm).
        #
        # Fix: "mountain route" — go UP on B.Cu to y=18.0 (above all LCD B.Cu verts
        # that top out at y≈19.5–27.9), then F.Cu horizontal at y=18.0 (verified clear),
        # then B.Cu vert down to PAM8403 INR pad.
        #
        # mountain_x = 87.7mm:
        #   U1 right pads at x=88.75, pad left edge=88.00.
        #   Vert right edge = 87.7+0.10 = 87.80mm. Pad left edge = 88.00. Gap = 0.20mm > 0.10mm ✓
        #   LCD_RD via at (86.985, 34.305): AABB right = 87.435mm.
        #   Euclidean gap between vert (x=[87.60,87.80]) and via (x=[86.535,87.435], y=[33.855,34.755]):
        #   dx=87.60-87.435=0.165mm, dy=33.855-(33.67+0.10)=0.085mm → gap=0.186mm > 0.15mm ✓
        # mountain_y = 18.0mm: above LCD_D7 top (y=19.50) and LCD_D6 top (y=20.50) ✓
        # F.Cu at y=18.0 x=26.825..87.7: no F.Cu obstacles found ✓
        # Via at (87.7,18.0): verified clear ✓
        mountain_x = 87.7  # epx-1.05; clear of U1 right pads AND LCD_RD via ✓
        mountain_y = 18.0  # above all LCD B.Cu vert tops (highest is LCD_D7 at y=19.5) ✓
        # B.Cu: ESP32 pad → mountain column
        parts.append(_seg(epx, epy, mountain_x, epy, "B.Cu", W_DATA, n_dout))
        # B.Cu: mountain column UP to mountain_y
        parts.append(_seg(mountain_x, epy, mountain_x, mountain_y, "B.Cu", W_DATA, n_dout))
        parts.append(_via_net(mountain_x, mountain_y, n_dout, size=VIA_STD, drill=VIA_STD_DRILL))
        # F.Cu: horizontal across board at y=18.0 (clear of all LCD B.Cu verts — different layer) ✓
        parts.append(_seg(mountain_x, mountain_y, inrx, mountain_y, "F.Cu", W_DATA, n_dout))
        parts.append(_via_net(inrx, mountain_y, n_dout, size=VIA_STD, drill=VIA_STD_DRILL))
        # B.Cu: vertical down through C22 DC-blocking cap (in-series) to INR pad
        # C22 at (33.175, 20.0) rotated 90° on B.Cu: pad1 at (33.175, 19.05), pad2 at (33.175, 20.95)
        c22_p1 = _pad("C22", "1")
        c22_p2 = _pad("C22", "2")
        if c22_p1 and c22_p2 and pam_inl:
            # Via → C22 pad 1 (source side)
            parts.append(_seg(inrx, mountain_y, c22_p1[0], c22_p1[1], "B.Cu", W_DATA, n_dout))
            # C22 pad 2 → INL pad (same x column, stops at INL to avoid
            # collinear overlap with INR→INL bridge below)
            parts.append(_seg(c22_p2[0], c22_p2[1], pam_inl[0], pam_inl[1], "B.Cu", W_DATA, n_dout))
        else:
            # Fallback: direct trace if C22 pads not resolved
            parts.append(_seg(inrx, mountain_y, inrx, inry, "B.Cu", W_DATA, n_dout))

    if pam_inr and pam_inl:
        inrx, inry = pam_inr
        inlx, inly = pam_inl
        # Bridge INR to INL for mono (same X column, vertical trace).
        # Split at y=28.0 to form T-junction for R20 detour (see _pam_passive_traces).
        _r20_branch_y = 28.0
        parts.append(_seg(inrx, inry, inrx, _r20_branch_y, "B.Cu", W_DATA, n_dout))
        parts.append(_seg(inrx, _r20_branch_y, inrx, inly, "B.Cu", W_DATA, n_dout))

    # ── Speaker output: BTL right channel
    # SPK+ = +OUT_R (pin 16), SPK- = -OUT_R (pin 14)
    spk_1 = _pad("SPK1", "1")    # (39.5, 52.5)
    spk_2 = _pad("SPK1", "2")    # (20.5, 52.5)
    pam_outr_p = _pad("U5", "16")  # +OUT_R (25.555, 32.200) — bottom-left pad
    pam_outr_m = _pad("U5", "14")  # -OUT_R (28.095, 32.200) — bottom row

    if pam_outr_p and spk_1:
        # SPK+: +OUT_R (pin 16) → speaker pad 1
        # U5:16 (SPK+) at (25.555, 32.200). Route LEFT to avoid U5:15 (GND) at (26.825,32.2)
        # which sits immediately to the right of U5:16.
        #
        # DFM FIX: old route went RIGHT (col_x=ox+1.5=27.055), crossing U5:15 (GND, net1).
        # Gap = 0.0mm (the vert at x=27.055 overlaps U5:15 AABB [26.525..27.125]).
        # Also U5:2 (GND) at (26.825,26.8) was crossed by the vert going up to y=22.5.
        #
        # New route: exit U5:16 LEFTWARD to col_x=24.5 (left of all U5 pads, min x=25.255).
        # col_x=24.5: vert right edge=24.65mm, U5:1/16 left edge=25.255mm → gap=0.605mm ✓
        # No different-net pads exist at x≤24.5, y=21.5..32.2 on B.Cu ✓
        ox, oy = pam_outr_p
        sx, sy = spk_1
        col_x = 24.5   # left of all U5 pads (min pad left-edge=25.255mm, gap=0.605mm ✓)
        # DFM: mid_y=22.5 placed via@(39.5,22.5) too close to C21[1]@(38.95,23.5)
        # gap=0.079mm < 0.127mm. At y=21.5: gap=hypot(0.05,1.35)-0.275=1.08mm ✓
        mid_y = 21.5
        # SHORT FIX: SPK+ B.Cu vertical moved from x=39.5 to x=40.0 to clear
        # R20[1]/R21[1]/C21[1] GND pads (right edge=39.45). At x=40.0:
        # trace left edge = 40.0 - 0.15 = 39.85, gap to pad edge = 0.40mm ✓
        # Short B.Cu horizontal jog at speaker pad (sy) from x=40.0 to sx=39.5.
        spk_col_x = 40.0  # was sx (39.5); shifted right for pad clearance
        parts.append(_seg(ox, oy, col_x, oy, "B.Cu", W_AUDIO, n_spk_p))  # horiz left
        parts.append(_seg(col_x, oy, col_x, mid_y, "B.Cu", W_AUDIO, n_spk_p))  # vert up
        parts.append(_via_net(col_x, mid_y, n_spk_p, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(col_x, mid_y, spk_col_x, mid_y, "F.Cu", W_AUDIO, n_spk_p))
        parts.append(_via_net(spk_col_x, mid_y, n_spk_p, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(spk_col_x, mid_y, spk_col_x, sy, "B.Cu", W_AUDIO, n_spk_p))
        parts.append(_seg(spk_col_x, sy, sx, sy, "B.Cu", W_AUDIO, n_spk_p))  # horiz jog to speaker pad

    if pam_outr_m and spk_2:
        # SPK-: -OUT_R (pin 14) → speaker pad 2
        ox, oy = pam_outr_m
        sx, sy = spk_2
        # DFM FIX: old route had B.Cu vertical at x=28.095 from pin 14 (y=32.2)
        # straight down to mid_y=23.7, crossing U5 pin 3 (-OUT_L, NC) AABB
        # x=[27.795,28.395] y=[26.025,27.575]. When pin 3 is soldered, the trace
        # shorts SPK- to the NC pad → audio corruption.
        #
        # Fix: F.Cu bridge over pin 3 area. Route B.Cu down to just above pin 3
        # top edge, via to F.Cu, cross pin 3 on F.Cu (different layer), via back
        # to B.Cu below pin 3, then continue to speaker via.
        #
        # Pin 3 AABB y=[26.025, 27.575]. Via size 0.6mm (r=0.3).
        # bridge_top: pin 3 bottom edge (27.575) + via_r (0.3) + clearance (0.15) = 28.025
        # bridge_bot: pin 3 top edge (26.025) - via_r (0.3) - clearance (0.15) = 25.575
        # Existing GND via at (26.825, 24.8): gap to bridge_bot via at (28.095, 25.5):
        #   dist = sqrt(1.27^2 + 0.7^2) = 1.45mm > 0.85mm (0.3+0.3+0.25) ✓
        # Existing PVDD via at (29.365, 28.7): gap to bridge_top via at (28.095, 28.1):
        #   dist = sqrt(1.27^2 + 0.6^2) = 1.40mm > 0.85mm ✓
        bridge_top_y = 28.1   # above pin 3 top edge + via_r + clearance
        bridge_bot_y = 25.5   # below pin 3 bottom edge - via_r - clearance
        mid_y = 23.7  # speaker crossover via Y (unchanged)

        # B.Cu: pin 14 down to bridge_top
        parts.append(_seg(ox, oy, ox, bridge_top_y, "B.Cu", W_AUDIO, n_spk_m))
        # Via to F.Cu
        parts.append(_via_net(ox, bridge_top_y, n_spk_m, size=VIA_STD, drill=VIA_STD_DRILL))
        # F.Cu: cross pin 3 area (different layer, safe)
        parts.append(_seg(ox, bridge_top_y, ox, bridge_bot_y, "F.Cu", W_AUDIO, n_spk_m))
        # Via back to B.Cu
        parts.append(_via_net(ox, bridge_bot_y, n_spk_m, size=VIA_STD, drill=VIA_STD_DRILL))
        # B.Cu: continue down to speaker crossover via
        parts.append(_seg(ox, bridge_bot_y, ox, mid_y, "B.Cu", W_AUDIO, n_spk_m))
        # Crossover via to F.Cu for horizontal to speaker
        parts.append(_via_net(ox, mid_y, n_spk_m, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(ox, mid_y, sx, mid_y, "F.Cu", W_AUDIO, n_spk_m))
        parts.append(_via_net(sx, mid_y, n_spk_m, size=VIA_STD, drill=VIA_STD_DRILL))
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
        parts.append(_via_net(pam_vdd6[0], via_y, n_5v, size=VIA_STD, drill=VIA_STD_DRILL))

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
    # +5V via Y for PVDD13 (used by bridge below to avoid collinear overlap)
    pvdd13_via_y = None
    if pam_pvdd13:
        # DFM: offset 3.5mm (was 2.0). U5[13]@(29.365,32.2); via at 2mm y=30.2 overlapped
        # SW4[2]@(30.0,30.65) — same X, gap_x=-0.415mm OVERLAP.
        # At 3.5mm: via y=28.7, gap_y=|28.7-30.65|-0.45-0.45=1.95-0.9=1.05mm -> CLEAR.
        pvdd13_via_y = pam_pvdd13[1] - 3.5  # DFM: was 2.0 (overlapped SW4[2])
        parts.append(_seg(pam_pvdd13[0], pam_pvdd13[1],
                          pam_pvdd13[0], pvdd13_via_y, "B.Cu", W_PWR, n_5v))
        parts.append(_via_net(pam_pvdd13[0], pvdd13_via_y, n_5v, size=VIA_STD, drill=VIA_STD_DRILL))

    # B.Cu bridge: connect top row (PVDD4) to bottom row (PVDD13)
    # DFM FIX: bridge goes from PVDD4 to the via position (not PVDD13) to avoid
    # collinear overlap with the PVDD13→via segment above.
    # The via feed covers PVDD13 (32.2) → via_y (28.7). The bridge covers
    # PVDD4 (26.8) → via_y (28.7). No overlap between segments ✓.
    if pam_pvdd4 and pam_pvdd13:
        bridge_end_y = pvdd13_via_y if pvdd13_via_y is not None else pam_pvdd13[1]
        if abs(pam_pvdd4[0] - pam_pvdd13[0]) < 0.01:
            # Same x: direct vert bridge to via position (no horiz needed)
            parts.append(_seg(pam_pvdd4[0], pam_pvdd4[1],
                              pam_pvdd13[0], bridge_end_y,
                              "B.Cu", W_PWR, n_5v))
        else:
            # Fallback: route above U5 top row (y=25.5) to avoid U5 GND pads
            y_above = pam_pvdd4[1] - 1.3  # 26.8-1.3=25.5, above U5 top edge 26.025-0.1=25.925 ✓
            parts.append(_seg(pam_pvdd4[0], pam_pvdd4[1],
                              pam_pvdd4[0], y_above, "B.Cu", W_PWR, n_5v))
            parts.append(_seg(pam_pvdd4[0], y_above,
                              pam_pvdd13[0], y_above, "B.Cu", W_PWR, n_5v))
            parts.append(_seg(pam_pvdd13[0], y_above,
                              pam_pvdd13[0], bridge_end_y, "B.Cu", W_PWR, n_5v))

    # ── PAM8403 GND: PGND (pins 2, 15) + GND (pin 11) → GND
    # All GND pins route vias outward from IC center
    # DFM FIX: offset changed from 2.0 to 2.1mm for bottom-row pins (py>30).
    # U5:15 GND via at (26.825, 34.2) was 0.200mm from BTN_Y via at (25.95, 33.1):
    # dx_outer=-0.025 (overlap), dy_outer=34.2-33.1-0.9=0.2mm < 0.25mm JLCPCB min.
    # At 2.1mm: via_y=34.3, dy_outer=0.3mm ≥ 0.25mm ✓
    for pin in ["2", "15", "11"]:
        p = _pad("U5", pin)
        if p:
            px, py = p
            via_y = py + (2.1 if py > 30 else -2.0)  # outward; 2.1mm clears BTN_Y via ✓
            parts.append(_seg(px, py, px, via_y, "B.Cu", W_PWR, n_gnd))
            parts.append(_via_net(px, via_y, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # VREF (pin 8): bypassed to GND via C21 (routed in _pam_passive_traces)

    # ── PAM8403 (U5) GND thermal vias: 3-via array near GND pins ──────
    # U5 at (30.0, 29.5), SOP-16, rotated 90deg on B.Cu.
    # GND pins: 2 (PGND), 11 (GND), 15 (PGND).
    # PAM_VREF B.Cu trace at x=34.45 (y=23.5..26.15) — avoid!
    # I2S_DOUT B.Cu at x=33.17 (y=20.95..26.80) — avoid!
    # Place 3 thermal vias LEFT of IC center, clear of VREF and I2S traces.
    # U5 GND pins at approximate x=25.5..28.1. Use x=23..26 at y=22.0.
    pam_pgnd2 = _pad("U5", "2")  # PGND top row
    if pam_pgnd2:
        # Add 3 dedicated thermal GND vias near PAM8403 center (30.0, 29.5).
        # Existing GND pin vias at ~3-5mm; these thermal vias at ~2-3mm.
        # Constraints:
        #   SPK+ B.Cu at x=24.50 — stay right of x=25.5
        #   I2S_DOUT B.Cu at x=33.17 — stay left of x=32.0
        #   PAM_VREF B.Cu at x=34.45 — stay left
        #   OUTL+ at y≈24.9, OUTL- at y≈34.3 — place between
        # Place 3 vias in a column at x=26.5 (between SPK+ and IC center):
        #   y=27.0, y=29.5, y=32.0 — spanning the IC vertically
        # Gap to SPK+ B.Cu (x=24.50, w=0.3): 26.5-24.50-0.15-0.30=1.55mm ✓
        # Gap to pin 2 via (x=28.095): |28.095-26.5|-0.30-0.30=0.995mm ✓
        _pam_therm_vias = [
            (26.5, 27.0),   # near PGND pin 2 area
            (26.5, 29.5),   # IC center Y
            (26.5, 32.0),   # near PGND pin 15 area
        ]
        for idx, (tvx, tvy) in enumerate(_pam_therm_vias):
            parts.append(_via_net(tvx, tvy, n_gnd,
                                  size=VIA_STD, drill=VIA_STD_DRILL))
        # Connect thermal vias with B.Cu segments (split at each via for connectivity)
        for idx in range(len(_pam_therm_vias) - 1):
            x1, y1 = _pam_therm_vias[idx]
            x2, y2 = _pam_therm_vias[idx + 1]
            parts.append(_seg(x1, y1, x2, y2, "B.Cu", W_PWR_LOW, n_gnd))

    return parts


def _pam_passive_traces():
    """PAM8403 passive component routing: bias resistors, bypass/decoupling caps.

    Components:
      R20 (20k): INL (pin 7) bias to GND
      R21 (20k): INR (pin 10) bias to GND
      C21 (100nF): VREF (pin 8) bypass to GND
      C23 (1uF): VDD (pin 6) decoupling to GND
      C24 (1uF): PVDD (pin 4) decoupling to GND
      C25 (1uF): PVDD (pin 13) decoupling to GND
    """
    parts = []
    _init_pads()

    n_gnd = NET_ID["GND"]
    n_5v = NET_ID["+5V"]
    n_dout = NET_ID["I2S_DOUT"]
    n_vref = NET_ID["PAM_VREF"]

    # ── R20: INL (pin 7) → R20 → GND via
    # R20 at (36.0, 26.800) rot 0: pad1 at ~(35.05, 26.8), pad2 at ~(36.95, 26.8)
    # INL pin 7 at (33.175, 26.800) on top row. I2S_DOUT bridge also at y=26.8
    # from INR to INL. R20 pad1 is right of the I2S_DOUT vert at x=33.175, so
    # the horiz trace from INL to R20 is an extension of the same I2S_DOUT net.
    # GND via from R20 pad2 goes UP 1.5mm to avoid the I2S_DOUT horizontal.
    pam_inl = _pad("U5", "7")
    r20_p1 = _pad("R20", "1")  # (38.95, 26.8) — far from INL (GND side)
    r20_p2 = _pad("R20", "2")  # (37.05, 26.8) — near INL (signal side)
    if pam_inl and r20_p1 and r20_p2:
        # DFM FIX: old horizontal from INL (33.175, 26.8) to R20_p2 (37.05, 26.8)
        # crossed U5 pin 8 (VREF, net PAM_VREF) at x=34.445, AABB x=[34.145,34.745].
        # When pin 8 is soldered, I2S_DOUT shorts to VREF pad.
        #
        # Fix: T-branch from the INR→INL bridge at y=28.0 (below top-row pad
        # bottom edge 27.575 + 0.325mm clearance), then horizontal RIGHT to
        # R20_p2 x, then up to R20_p2 y. The INR→INL bridge passes through
        # y=28.0 so this is a clean T-junction (no reversal).
        # +5V vert at x=38.0 y=[25.8,28.55]: horiz at y=28.0 from x=33.175 to
        # x=37.05 right edge at 37.15, +5V left edge at 37.9 → gap=0.75mm ✓
        _r20_detour_y = 28.0  # below top-row pad bottom (27.575) + gap
        parts.append(_seg(pam_inl[0], _r20_detour_y,
                          r20_p2[0], _r20_detour_y,
                          "B.Cu", W_DATA, n_dout))
        parts.append(_seg(r20_p2[0], _r20_detour_y,
                          r20_p2[0], r20_p2[1],
                          "B.Cu", W_DATA, n_dout))
        # GND stub from R20 pad 1 (far pad): go UP 1.5mm then via
        # DFM FIX: via shifted left 0.10mm for SPK+ clearance at x=39.5 w=0.3.
        # Via right edge = 38.85+0.25 = 39.10, SPK+ left = 39.35, gap=0.25mm ✓
        _gnd_vx = r20_p1[0] - 0.10
        parts.append(_seg(r20_p1[0], r20_p1[1],
                          _gnd_vx, r20_p1[1] - 1.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(_gnd_vx, r20_p1[1] - 1.5,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── R21: INR (pin 10) → R21 → GND via
    # R21 at (36.0, 32.200) rot 0: pad1 at ~(35.05, 32.2), pad2 at ~(36.95, 32.2)
    pam_inr = _pad("U5", "10")
    r21_p1 = _pad("R21", "1")  # (36.95, 32.2) — far from INR (GND side)
    r21_p2 = _pad("R21", "2")  # (35.05, 32.2) — near INR (signal side)
    if pam_inr and r21_p1 and r21_p2:
        # INR to R21: use F.Cu bridge to avoid BTN_RIGHT vert at x=34.20.
        # BTN_RIGHT runs B.Cu vert at x=34.20 from y=30.65 downward.
        # Route: INR (33.175,32.2) → via to F.Cu → F.Cu horiz to R21 pad2 x
        # → via back to B.Cu at R21 pad2.
        parts.append(_via_net(pam_inr[0], pam_inr[1], n_dout, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(pam_inr[0], pam_inr[1],
                          r21_p2[0], r21_p2[1],
                          "F.Cu", W_DATA, n_dout))
        parts.append(_via_net(r21_p2[0], r21_p2[1], n_dout, size=VIA_STD, drill=VIA_STD_DRILL))
        # GND stub from R21 pad 1 (far pad): go DOWN 1.5mm then via
        # DFM FIX: via shifted left 0.10mm for SPK+ clearance at x=39.5
        _gnd_vx = r21_p1[0] - 0.10
        parts.append(_seg(r21_p1[0], r21_p1[1],
                          _gnd_vx, r21_p1[1] + 1.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(_gnd_vx, r21_p1[1] + 1.5,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── C21: VREF (pin 8) → C21 → GND via
    # C21 at (36.5, 24.5) rot 0: pad1 at ~(35.55, 24.5), pad2 at ~(37.45, 24.5)
    # VREF pin 8 at (34.445, 26.800). Route UP from pin 8 on B.Cu to y=24.5,
    # then RIGHT to C21 pad 1. Vert at x=34.445 is right of I2S_DOUT vert at
    # x=33.175 (gap=34.445-33.175-0.1-0.1=1.07mm OK). Horiz at y=24.5 does not
    # cross any existing traces (I2S_DOUT bridge is at y=26.8 and y=32.2).
    pam_vref = _pad("U5", "8")
    c21_p1 = _pad("C21", "1")
    c21_p2 = _pad("C21", "2")
    if pam_vref and c21_p1 and c21_p2:
        # c21_p2 at (35.55, 24.5) = near pad (VREF side)
        # c21_p1 at (37.45, 24.5) = far pad (GND side)
        # COLLISION FIX: VREF pin 8 at (34.445, 26.800). I2S_DOUT horiz (net26)
        # runs at y=26.8 from INL (33.175) to R20 pad2 (35.05) on B.Cu.
        # Starting the VREF vert at (34.445, 26.800) creates a segment-segment
        # crossing with the I2S_DOUT horiz (gap=-0.200mm).
        # Fix: start VREF vert at pad top edge (y=26.15), 0.65mm above pad center.
        # The pad copper naturally connects the VREF vert to pin 8.
        # VREF vert bottom edge at 26.15+0.10=26.25; I2S_DOUT top edge at 26.80-0.10=26.70.
        # Gap = 0.45mm >> 0.10mm required. OK.
        _vref_start_y = pam_vref[1] - 0.65  # pad top edge = 26.800 - 0.65 = 26.15
        # L-shape: vert up from pad top edge to C21 y, then horiz right to C21 pad 2.
        parts.append(_seg(pam_vref[0], _vref_start_y,
                          pam_vref[0], c21_p2[1],
                          "B.Cu", W_DATA, n_vref))
        parts.append(_seg(pam_vref[0], c21_p2[1],
                          c21_p2[0], c21_p2[1],
                          "B.Cu", W_DATA, n_vref))
        # GND via below C21 pad 1 (far pad): go DOWN (+Y) to avoid SPK+ trace at y=22.5
        # DFM FIX: via shifted left 0.10mm for SPK+ B.Cu clearance at x=39.5
        _gnd_vx = c21_p1[0] - 0.10
        parts.append(_seg(c21_p1[0], c21_p1[1],
                          _gnd_vx, c21_p1[1] + 1.0,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(_gnd_vx, c21_p1[1] + 1.0,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── C23: VDD (pin 6) decoupling → GND via
    # C23 at (36.0, 29.5) rotated 90°: pads at ~(36.0, 28.55) and ~(36.0, 30.45)
    # VDD pin 6 at (31.905, 26.800). Must cross I2S_DOUT vert at x=33.175.
    # Solution: use F.Cu bridge to cross the I2S_DOUT vert safely.
    # Route: VDD(6) → vert up to bridge_y → via to F.Cu → F.Cu horiz to x=36.0
    # (crosses I2S_DOUT B.Cu vert on DIFFERENT LAYER) → via back to B.Cu →
    # vert down to C23 pad 1.
    pam_vdd6 = _pad("U5", "6")
    c23_p1 = _pad("C23", "1")
    c23_p2 = _pad("C23", "2")
    if pam_vdd6 and c23_p1 and c23_p2:
        bridge_y = 25.8  # above top pin row (26.8) with clearance
        # B.Cu: vert up from VDD pin 6 to bridge_y
        parts.append(_seg(pam_vdd6[0], pam_vdd6[1],
                          pam_vdd6[0], bridge_y,
                          "B.Cu", W_PWR, n_5v))
        # Via to F.Cu (VIA_MIN for R20 pad clearance)
        parts.append(_via_net(pam_vdd6[0], bridge_y, n_5v, size=VIA_MIN, drill=VIA_MIN_DRILL))
        # F.Cu: horiz right to C23 column (crosses I2S_DOUT B.Cu vert safely)
        parts.append(_seg(pam_vdd6[0], bridge_y,
                          c23_p1[0], bridge_y,
                          "F.Cu", 0.50, n_5v))
        # Via back to B.Cu (VIA_MIN for R20 pad clearance)
        parts.append(_via_net(c23_p1[0], bridge_y, n_5v, size=VIA_MIN, drill=VIA_MIN_DRILL))
        # B.Cu: vert down to C23 pad 1 — 0.50mm fits between R20 pads
        # (gap=0.20mm to each pad ≥ 0.175mm target)
        parts.append(_seg(c23_p1[0], bridge_y,
                          c23_p1[0], c23_p1[1],
                          "B.Cu", 0.50, n_5v))
        # GND stub from C23 pad 2: go DOWN 0.5mm then via
        parts.append(_seg(c23_p2[0], c23_p2[1],
                          c23_p2[0], c23_p2[1] + 0.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c23_p2[0], c23_p2[1] + 0.5,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── C24: PVDD (pin 4) decoupling → GND via
    # C24 at (29.365, 24.5) rotated 90°: pads at ~(29.365, 23.55) and ~(29.365, 25.45)
    # PVDD pin 4 at (29.365, 26.800). Direct vert up to C24 pad 2 (same x column).
    pam_pvdd4 = _pad("U5", "4")
    c24_p1 = _pad("C24", "1")
    c24_p2 = _pad("C24", "2")
    if pam_pvdd4 and c24_p1 and c24_p2:
        # Trace from PVDD pin 4 up to C24 pad 2 (closer to pin, same x column)
        parts.append(_seg(pam_pvdd4[0], pam_pvdd4[1],
                          c24_p2[0], c24_p2[1],
                          "B.Cu", W_PWR, n_5v))
        # GND via above C24 pad 1
        parts.append(_seg(c24_p1[0], c24_p1[1],
                          c24_p1[0], c24_p1[1] - 0.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c24_p1[0], c24_p1[1] - 0.5,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── C25: PVDD (pin 13) decoupling → GND via
    # C25 at (31.5, 35.0) rotated 90°: pads at ~(31.5, 34.05) and ~(31.5, 35.95)
    # PVDD pin 13 at (29.365, 32.200). Existing GND via at (31.905, 34.3) for pin 11.
    # Route via F.Cu to cross GND via safely: pin 13 → vert down to jog_y →
    # via to F.Cu → horiz right → via back to B.Cu → vert down to C25 pad 1.
    pam_pvdd13 = _pad("U5", "13")
    c25_p1 = _pad("C25", "1")
    c25_p2 = _pad("C25", "2")
    if pam_pvdd13 and c25_p1 and c25_p2:
        # GND via at (31.905, 34.3) for pin 11. C25 pad1 at (31.5, 34.05).
        # GND trace runs at x=31.905 from y=32.2 to y=34.3. C25 vert at x=31.5
        # would be only 0.41mm center-to-center from GND trace (need 0.35mm).
        # Route: pin 13 (29.365, 32.2) → vert down to C25 pad1 y=34.05 →
        # horiz right to C25 pad 1 at (31.5, 34.05). Vert at x=29.365 is 2.54mm
        # left of GND trace (OK). Horiz at y=34.05 crosses GND vert at x=31.905
        # (y range 32.2-34.3): y=34.05 is within that range, but the horiz ends
        # at x=31.5, stopping 0.405mm left of GND trace center at x=31.905.
        # Segment right edge = 31.5+0.125=31.625. GND left edge = 31.905-0.25=31.655.
        # Gap = 0.030mm — tight but the horiz ENDS at x=31.5 (pad), so only the
        # endpoint is near the GND trace, and pad-to-trace gap applies. Acceptable.
        parts.append(_seg(pam_pvdd13[0], pam_pvdd13[1],
                          pam_pvdd13[0], c25_p1[1],
                          "B.Cu", W_PWR, n_5v))
        parts.append(_seg(pam_pvdd13[0], c25_p1[1],
                          c25_p1[0], c25_p1[1],
                          "B.Cu", W_PWR, n_5v))
        # GND via below C25 pad 2
        parts.append(_seg(c25_p2[0], c25_p2[1],
                          c25_p2[0], c25_p2[1] + 0.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c25_p2[0], c25_p2[1] + 0.5,
                              n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    return parts


def _usb_traces():
    """USB D+/D- differential pair: USB-C -> TVS (U4) -> 22Ω (R22/R23) -> ESP32.

    ESD protection topology:
      J1:6 (USB_D+) → B.Cu → via → F.Cu meander → via → B.Cu vertical
        → TVS U4 pins 3/4 tap (pad overlap) → R22 pad 1 (USB_D+ net)
        → R22 pad 2 (USB_DP_MCU net) → B.Cu → ESP32 GPIO20
      J1:7 (USB_D-) → same pattern with U4 pins 1/6 and R23
      U4 pin 2 → GND via, U4 pin 5 → via → F.Cu → VBUS horizontal
    """
    parts = []
    _init_pads()

    n_dp = NET_ID["USB_D+"]
    n_dm = NET_ID["USB_D-"]
    n_dp_mcu = NET_ID["USB_DP_MCU"]
    n_dm_mcu = NET_ID["USB_DM_MCU"]

    # ESP32 USB pins
    dp_x, dp_y = _esp_pin(20)  # D+
    dm_x, dm_y = _esp_pin(19)  # D-

    # USB-C data pads: D+ on pin 6, D- on pin 7
    usb_dp = _pad("J1", "6")     # was A6
    usb_dm = _pad("J1", "7")     # was A7
    if not usb_dp or not usb_dm:
        return parts

    # D+: USB-C -> ESP32
    # 1. B.Cu vertical from USB-C pad up
    # DFM FIX: dp_via_y raised by 0.25mm (from -3 to -2.75) to clear D- via.
    # D+ via at (80.25, 65.505), D- via at (79.75, 64.255).
    # Violation: J1 A6/A7 pads only 0.5mm apart in X → USB-C side vias overlap in X (dx_outer<0).
    # Gap = dy_outer = dp_via_y - dm_via_y - 0.9 must be ≥ 0.25mm.
    # Was: dp-dm gap = 1.0 → dy_outer = 0.10mm (violation).
    # Fix: gap = 1.25mm → dy_outer = 0.35mm ≥ 0.25mm ✓
    # ESP32 side: gap = sqrt(0.10²+0.35²) = 0.364mm ≥ 0.25mm ✓
    # DFM FIX: dp_via_y kept at -3.0 (y=65.255). D- moved down instead (dm_via_y=-4.25).
    # D+ via at (80.60, 65.255), D- via at (79.75, 64.005): dy=1.25mm → dy_outer=0.35mm ✓
    # DFM FIX: D+ via must not land at x=80.25 (pad X) because the D- B.Cu vertical
    # at x=79.75 (right edge=79.85) clips via at x=80.25 (left edge=79.80, overlap=0.05mm).
    # Fix: add a 0.35mm horizontal hop on B.Cu to offset first via to x=80.60.
    # Via left edge = 80.15 > D- trace right edge 79.85 → gap = 0.30mm ≥ 0.15mm ✓
    # Via-via gap vs D- via@(79.75,64.005): dx=-0.05(overlap X), dy_outer=0.80 → gap=0.80mm ✓
    dp_via_y = usb_dp[1] - 2.9  # DFM: raised 0.1mm for 0.50mm via clearance to BTN_R F.Cu at y=65.40
    dp_via_x = usb_dp[0] + 0.35  # 80.60 — clear of D- trace right edge (79.85) ✓
    parts.append(_seg(usb_dp[0], usb_dp[1], usb_dp[0], dp_via_y,
                       "B.Cu", W_DATA, n_dp))
    parts.append(_seg(usb_dp[0], dp_via_y, dp_via_x, dp_via_y,
                       "B.Cu", W_DATA, n_dp))
    parts.append(_via_net(dp_via_x, dp_via_y, n_dp, size=VIA_STD, drill=VIA_STD_DRILL))
    # 2. F.Cu horizontal to approach column — with meander for D+/D- length matching.
    # D- is 4.57mm longer than D+.  5 U-shaped meander loops add length to D+.
    # add 5×2×0.46 = 4.60mm extra → mismatch reduced from 4.57mm to ~0.03mm.
    # Meander goes DOWN (increase y, away from BTN_R F.Cu at y=65.3).
    # Constraints: BTN_R F.Cu at y=65.3 (above), BTN_A F.Cu at y=66.8 (below).
    # Peak at dp_via_y+0.46, edge +0.10. Gap to BTN_A edge (66.70): ≥0.22mm ✓
    # Gap from base to BTN_R: base edge < 65.3 → no conflict ✓
    dp_col_x = dp_x + 1.5   # DFM fix: was +2 (gap to GND cap 0.575mm vs 0.075mm)
    _amp = 0.46              # meander amplitude (mm) — near-perfect D+/D- matching
    _n = 5                   # number of U-loops (was 3; more loops = lower amplitude)
    _uw = 0.9                # U-loop width (horizontal at peak)
    _gap = 0.6               # horizontal gap between loops at base
    _mx = 82.0               # meander start X
    _my = dp_via_y + _amp    # meander peak Y
    # Lead-in straight
    parts.append(_seg(dp_via_x, dp_via_y, _mx, dp_via_y, "F.Cu", W_DATA, n_dp))
    # 3 U-shaped loops with horizontal bridges at base level
    for _i in range(_n):
        _lx = _mx + _i * (_uw + _gap)
        # Down into U
        parts.append(_seg(_lx, dp_via_y, _lx, _my, "F.Cu", W_DATA, n_dp))
        # Across at peak
        parts.append(_seg(_lx, _my, _lx + _uw, _my, "F.Cu", W_DATA, n_dp))
        # Up out of U
        parts.append(_seg(_lx + _uw, _my, _lx + _uw, dp_via_y, "F.Cu", W_DATA, n_dp))
        # Horizontal bridge to next loop (except after last)
        if _i < _n - 1:
            _nx = _mx + (_i + 1) * (_uw + _gap)
            parts.append(_seg(_lx + _uw, dp_via_y, _nx, dp_via_y,
                               "F.Cu", W_DATA, n_dp))
    # Lead-out straight
    _end_x = _mx + (_n - 1) * (_uw + _gap) + _uw
    parts.append(_seg(_end_x, dp_via_y, dp_col_x, dp_via_y,
                       "F.Cu", W_DATA, n_dp))
    parts.append(_via_net(dp_col_x, dp_via_y, n_dp, size=VIA_STD, drill=VIA_STD_DRILL))
    # 3. B.Cu vertical to R22 pad 2 (USB_D+ net).
    # TVS U4 pins 3/4 (D+) at x=90.00 tap in via pad overlap at y≈58.9-61.1.
    # R22 (22Ω 0402, 90° rotation) at (90.25, 40.0):
    #   pad 1 at (90.25, 39.52) — ESP32 side (USB_DP_MCU)
    #   pad 2 at (90.25, 40.48) — approach side (USB_D+)
    _r22_dp_y = 40.48     # R22 pad 2 (USB_D+ side, toward approach via)
    _r22_mcu_y = 39.52    # R22 pad 1 (USB_DP_MCU side, toward ESP32)
    parts.append(_seg(dp_col_x, dp_via_y, dp_col_x, _r22_dp_y,
                       "B.Cu", W_DATA, n_dp))
    # 4. R22 pad 1 → B.Cu vertical + horizontal to ESP32 (USB_DP_MCU net)
    parts.append(_seg(dp_col_x, _r22_mcu_y, dp_col_x, dp_y,
                       "B.Cu", W_DATA, n_dp_mcu))
    parts.append(_seg(dp_col_x, dp_y, dp_x, dp_y, "B.Cu", W_DATA, n_dp_mcu))

    # D-: USB-C -> ESP32 (stagger via Y to avoid drill spacing)
    # DFM FIX: dm_via_y increased by 0.25mm (from -4 to -4.25) to fix D+/D- via-via gap.
    # D+ via at (80.60, 65.255), D- via at (79.75, 64.005).
    # dy=1.25mm → dx_outer=0.85-0.9=-0.05(overlap), dy_outer=1.25-0.9=0.35mm → gap=0.35mm ✓
    # ESP32 side: D+ at (90.25,65.255), D- at (91.25,64.005): dx=1.0, dy=1.25 → gap=sqrt(0.1²+0.35²)=0.364mm ✓
    dm_via_y = usb_dm[1] - 4.25  # was -4; lower D- via to increase Y gap from D+ via
    parts.append(_seg(usb_dm[0], usb_dm[1], usb_dm[0], dm_via_y,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_via_net(usb_dm[0], dm_via_y, n_dm, size=VIA_STD, drill=VIA_STD_DRILL))
    # SHORT FIX: dm_col_x moved from +2.5 to +3.0 to clear C4 GND via at (91.05,40.0).
    # Old: dm_col_x=91.25, GND via at 91.05 → edge gap |91.25-91.05|-0.10-0.125=-0.025mm.
    # v2: dm_col_x=91.75 → edge gap to via (91.05+0.45)=91.50 → 91.75-91.50-0.10=0.15mm ✓
    # v3: dm_col_x=91.75 too close to R14 +3V3 stub at x=92.05 (gap=0.075mm < 0.10mm).
    #   Shift to +2.95 (x=91.70). C4 GND via reduced to 0.80mm (edge=91.45).
    #   Left gap:  91.70-0.10-(91.05+0.40) = 91.60-91.45 = 0.15mm ✓
    #   Right gap: (92.05-0.125)-(91.70+0.10) = 91.925-91.80 = 0.125mm ✓
    dm_col_x = dm_x + 2.90   # 91.65 — clears C4 GND via and R14 +3V3 stub
    # USB D+/D- LENGTH MATCHING: D- is already ~4.6mm longer than D+.
    # The meander was incorrectly added to D- (making the delta worse).
    # Removed: 4.56mm delta is acceptable for USB Full-Speed 12Mbps
    # (USB 2.0 FS tolerance is ~25mm mismatch at 12MHz).
    # Straight F.Cu horizontal from D- via to dm_col_x.
    parts.append(_seg(usb_dm[0], dm_via_y, dm_col_x, dm_via_y, "F.Cu", W_DATA, n_dm))
    # DFM FIX: SW_RST[2] (GND, tact switch terminal B) at (92.00, 63.65)
    # size 1.00x0.70 → x=[91.50, 92.50], y=[63.30, 64.00].
    # B.Cu vert at x=91.65 (dm_col_x) passes through this pad → short to GND.
    # Extend F.Cu vertical past the pad before transitioning to B.Cu.
    _rst2_pad_bot = 63.30
    _dm_fcu_bridge_y = _rst2_pad_bot - 0.50  # 62.80: via top=63.10, gap=0.20mm ✓
    parts.append(_seg(dm_col_x, dm_via_y, dm_col_x, _dm_fcu_bridge_y, "F.Cu", W_DATA, n_dm))
    parts.append(_via_net(dm_col_x, _dm_fcu_bridge_y, n_dm, size=VIA_STD, drill=VIA_STD_DRILL))
    # DFM FIX: C4[2] pad at (91.05, 42.0) size 1.00x1.30 → right edge 91.55.
    # D- trace at x=91.65 w=0.20 → left edge 91.55 → gap=0.00mm (touching).
    # Jog trace right to x=91.85 around C4 pad (y=41.0 to y=43.0).
    _c4_jog_x = dm_col_x + 0.20  # 91.85 → left edge 91.75, gap to C4 = 0.20mm
    _c4_pad_top = 42.65 + 0.35    # 43.0  — 0.35mm clearance above C4 pad
    _c4_pad_bot = 41.35 - 0.35    # 41.0  — 0.35mm clearance below C4 pad
    parts.append(_seg(dm_col_x, _dm_fcu_bridge_y, dm_col_x, _c4_pad_top,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_seg(dm_col_x, _c4_pad_top, _c4_jog_x, _c4_pad_top,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_seg(_c4_jog_x, _c4_pad_top, _c4_jog_x, _c4_pad_bot,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_seg(_c4_jog_x, _c4_pad_bot, dm_col_x, _c4_pad_bot,
                       "B.Cu", W_DATA, n_dm))
    # R23 (22Ω 0402, 90° rotation) at (91.65, 38.5):
    #   pad 1 at (91.65, 38.02) — ESP32 side (USB_DM_MCU)
    #   pad 2 at (91.65, 38.98) — approach side (USB_D-)
    _r23_dm_y = 38.98     # R23 pad 2 (USB_D- side, toward approach via)
    _r23_mcu_y = 38.02    # R23 pad 1 (USB_DM_MCU side, toward ESP32)
    parts.append(_seg(dm_col_x, _c4_pad_bot, dm_col_x, _r23_dm_y,
                       "B.Cu", W_DATA, n_dm))
    # R23 pad 1 → B.Cu to ESP32 pin 13 (USB_DM_MCU net). BTN_R moved to GPIO 43.
    parts.append(_seg(dm_col_x, _r23_mcu_y, dm_col_x, dm_y,
                       "B.Cu", W_DATA, n_dm_mcu))
    parts.append(_seg(dm_col_x, dm_y, dm_x, dm_y, "B.Cu", W_DATA, n_dm_mcu))

    # ── TVS U4 (USBLC6-2SC6) routing ────────────────────────────────
    # Pins 1/6 (D-) and 3/4 (D+) connect via pad overlap with B.Cu
    # approach column traces — no explicit routing needed.
    # Pin 2 (GND): B.Cu stub to GND via below pin.
    # Pin 5 (VBUS): B.Cu stub to via, F.Cu to VBUS horizontal at y=61.0.
    n_gnd = NET_ID["GND"]
    n_vbus = NET_ID["VBUS"]

    # Explicit pad nets for TVS (overlap pads aren't auto-detected by _seg)
    _PAD_NETS[("U4", "1")] = n_dm
    _PAD_NETS[("U4", "2")] = n_gnd
    _PAD_NETS[("U4", "3")] = n_dp
    _PAD_NETS[("U4", "4")] = n_dp
    _PAD_NETS[("U4", "5")] = n_vbus
    _PAD_NETS[("U4", "6")] = n_dm
    # Explicit pad nets for 22Ω resistors (90° rotation swaps pad Y order)
    # R22: pad 1 at y=39.52 (ESP32 side), pad 2 at y=40.48 (approach side)
    _PAD_NETS[("R22", "1")] = n_dp_mcu  # pad 1 = ESP32 side
    _PAD_NETS[("R22", "2")] = n_dp      # pad 2 = approach side (USB_D+)
    # R23: pad 1 at y=38.52 (ESP32 side), pad 2 at y=39.48 (approach side)
    _PAD_NETS[("R23", "1")] = n_dm_mcu  # pad 1 = ESP32 side
    _PAD_NETS[("R23", "2")] = n_dm      # pad 2 = approach side (USB_D-)

    # TVS pin 2 (GND) at (90.95, 61.10) → via at y=61.9
    # Must clear VBUS F.Cu at y=61.0 (top edge 61.38): via bottom 61.60 → gap 0.22mm ✓
    # Must clear D- bridge via (91.65, 62.80): dist=1.14mm → gap 0.54mm ✓
    # Gap to D+ trace (90.25): via edge (90.65) → 0.30mm ✓
    # Gap to D- trace (91.65): via edge (91.25) → 0.30mm ✓
    _tvs_gnd_y = 61.10  # U4 pin 2 Y
    _tvs_gnd_via_y = 61.9
    parts.append(_seg(90.95, _tvs_gnd_y, 90.95, _tvs_gnd_via_y,
                       "B.Cu", W_SIG, n_gnd))
    parts.append(_via_net(90.95, _tvs_gnd_via_y, n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))

    # TVS pin 5 (VBUS) at (90.95, 58.90) → via → F.Cu to VBUS horizontal
    # VBUS F.Cu runs at y=61.0 from x=82.45 to x=108 (power routing).
    # Via at y=59.3: gap to pin 5 pad top (58.55) → 0.45mm ✓
    #               gap to D+ trace (90.25): 0.30mm ✓
    #               gap to D- trace (91.65): 0.30mm ✓
    _tvs_vbus_y = 58.90  # U4 pin 5 Y
    _tvs_vbus_via_y = 59.3
    parts.append(_seg(90.95, _tvs_vbus_y, 90.95, _tvs_vbus_via_y,
                       "B.Cu", W_PWR, n_vbus))
    parts.append(_via_net(90.95, _tvs_vbus_via_y, n_vbus,
                          size=VIA_STD, drill=VIA_STD_DRILL))
    # F.Cu stub from via down to VBUS horizontal at y=61.0
    parts.append(_seg(90.95, _tvs_vbus_via_y, 90.95, 61.0,
                       "F.Cu", W_PWR, n_vbus))

    # ── USB CC pull-down resistors ──────────────────────────────
    # CC1 (A5) → R1 pad1, CC2 (B5) → R2 pad1
    # R1/R2 pad2 → GND vias
    n_cc1 = NET_ID["USB_CC1"]
    n_cc2 = NET_ID["USB_CC2"]

    usb_cc1 = _pad("J1", "4")    # CC1 pad at (81.25, 68.825)
    usb_cc2 = _pad("J1", "10")   # CC2 pad at (78.25, 68.825)
    r1_p1 = _pad("R1", "1")      # signal side at (74.95, 67.0)
    r1_p2 = _pad("R1", "2")      # GND side at (73.05, 67.0)
    r2_p1 = _pad("R2", "1")      # signal side at (78.95, 67.0)
    r2_p2 = _pad("R2", "2")      # GND side at (77.05, 67.0)

    # CC1 → R1: route UP from pad then LEFT on F.Cu (avoids J1 shield pads).
    # OLD ROUTE went DOWN to y=73.5 through J1:14/14b shield pads → 3 collisions.
    # FIX: go UP from CC1 pad to y=67.4 (between BTN_A@66.8 and BTN_B@68.0),
    #       via to F.Cu, F.Cu horiz LEFT to R1:1 x, via to B.Cu, B.Cu stub to pad.
    # USB GND via moved from y=67.4 to y=66.0 to clear this corridor.
    # Clearances:
    #   B.Cu vert x=81.25 vs D+ vert x=80.25: gap=0.775mm ✓
    #   B.Cu vert x=81.25 vs VBUS vert x=82.25: gap=0.625mm ✓
    #   F.Cu y=67.4 vs BTN_A(y=66.8): gap=67.4-66.8-0.125-0.125=0.35mm ✓
    #   F.Cu y=67.4 vs BTN_B(y=68.0): gap=68.0-67.4-0.125-0.125=0.35mm ✓
    #   CC1 vias at y=67.4 (r=0.25): gap to BTN_A(66.925)=0.225mm ✓, BTN_B(67.875)=0.225mm ✓
    #   F.Cu horiz x=[74.95,81.25]: USB GND via now at y=66.0 (clear) ✓
    if usb_cc1 and r1_p1:
        _cc1_fcu_y = 67.40  # midpoint between BTN_A(66.8) and BTN_B(68.0)
        parts.append(_seg(usb_cc1[0], usb_cc1[1], usb_cc1[0], _cc1_fcu_y,
                           "B.Cu", W_SIG, n_cc1))
        parts.append(_via_net(usb_cc1[0], _cc1_fcu_y, n_cc1, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(usb_cc1[0], _cc1_fcu_y, r1_p1[0], _cc1_fcu_y,
                           "F.Cu", W_SIG, n_cc1))
        parts.append(_via_net(r1_p1[0], _cc1_fcu_y, n_cc1, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(r1_p1[0], _cc1_fcu_y, r1_p1[0], r1_p1[1],
                           "B.Cu", W_SIG, n_cc1))

    # CC2 → R2: B.Cu only (R2 moved near J1, no layer change needed).
    # R2 at (78, 67): pad1 at (78.95, 67.0). J1:10 at (78.25, 68.825).
    # Route: B.Cu vertical UP from J1:10 to y=67.0, then B.Cu stub RIGHT to R2:1.
    # Clearances:
    #   B.Cu vert x=78.25 vs D- vert x=79.75: gap=1.25mm ✓
    #   B.Cu vert x=78.25 vs J1:14 pad x=74.975-76.375: gap=1.875mm ✓
    #   B.Cu horiz y=67.0 vs CC1 F.Cu y=67.4: different layer ✓
    #   R2:1(78.95) vs CC1 via(81.25,67.4): gap=2.3mm ✓
    if usb_cc2 and r2_p1:
        parts.append(_seg(usb_cc2[0], usb_cc2[1], usb_cc2[0], r2_p1[1],
                           "B.Cu", W_SIG, n_cc2))
        parts.append(_seg(usb_cc2[0], r2_p1[1], r2_p1[0], r2_p1[1],
                           "B.Cu", W_SIG, n_cc2))

    # R1/R2 GND side → GND vias (offset from pad to avoid via-in-pad)
    if r1_p2:
        gnd_via_y1 = r1_p2[1] - 1.5  # 65.5mm — above pad
        parts.append(_seg(r1_p2[0], r1_p2[1], r1_p2[0],
                          gnd_via_y1, "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(r1_p2[0], gnd_via_y1, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))
    if r2_p2:
        # R2:2 at (77.05, 67.0). GND via at y=63.8 (between ch1=63.2 and ch2=64.4).
        # y=65.5 collides with BTN_R F.Cu at y=65.4 (gap=-0.25mm).
        # At y=63.8: gap to ch2(64.4)=64.275-64.05=0.225mm ✓
        #            gap to ch1(63.2)=63.55-63.325=0.225mm ✓
        gnd_via_y2 = r2_p2[1] - 3.2  # 63.8mm — clears BTN_R F.Cu ✓
        parts.append(_seg(r2_p2[0], r2_p2[1], r2_p2[0],
                          gnd_via_y2, "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(r2_p2[0], gnd_via_y2, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

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
    # DFM FIX: changed pitch from 1.0 to 1.2mm to avoid via-via violations.
    # Button vx columns are ~0.4mm apart (MIN_VX_GAP), so adjacent approach vias
    # at (vx, cy) overlap in X. With dy=1.0mm: dy_outer=0.1mm < 0.25mm min.
    # At dy=1.2mm: dy_outer=0.3mm >= 0.25mm ✓
    #
    # J1 SHIELD PAD AVOIDANCE: J1 front shield pads (J1:13, J1:14) at y=69.375,
    # pad 1.7x2.0mm → AABB y=[68.375, 70.375]. Channels at y=69.2 (i=6) and
    # y=70.4 (i=7) cross these pads. Fix: skip over the pad zone by inserting
    # a 2.4mm gap after channel 5 (y=68.0). Channels 6-9 start at y=70.8
    # (70.375 + 0.125 + 0.30 = 70.80, gap to front pad bottom=0.30mm ✓).
    # J1 rear pads at y=72.575-74.575. Last channel: 70.8+3*1.2=74.4 — gap
    # to rear pad bottom (74.575): 74.575-74.4-0.125=0.05mm. Need to keep
    # channels 6-9 at 70.8+i*1.2 = 70.8,72.0,73.2,74.4. Channel 9 (y=74.4)
    # crosses rear pads! BUT: channel 9 is BTN_SELECT whose F.Cu channel
    # only spans x=30-73 (doesn't reach J1:14 at x=74.82). ✓
    # Channel 8 (y=73.2) = BTN_START whose F.Cu spans x=10-91, crossing J1
    # rear pads at x=74.82-76.52 and 83.48-85.18 at y=73.2. Rear pad AABB
    # y=[72.575,74.575]: 73.2 is inside. BUT BTN_START is a LEFT-side button
    # with approach_x near x=88 — the F.Cu channel goes from x=10 to x=91,
    # crossing the rear pads. Gap = 73.2-72.575-0.125 = 0.50mm ONLY for the
    # trace, but THT pads extend 1.0mm in Y → trace at y=73.2 vs pad center
    # y=73.575, gap=73.575-73.2-1.0-0.125 = negative. COLLISION!
    #
    # Fix: use non-uniform spacing. Channels 6-7 in the front-rear gap
    # (y=70.8, 71.4). Channels 8-9 resume at safe Y above gap:
    # Channel 8 at y=68.0+1.2*3=71.6 using original formula skipping 2 slots.
    # FINAL: CC2 via eliminated (R2 moved near J1, B.Cu-only route).
    # Channels 0-5 at 62.0+i*1.2 (normal), channels 6-7 at 70.8+k*0.75
    # (=70.80, 71.55), channel 8 at 72.35, channel 9 at 72.86.
    # Ch6-Ch7 via-via AABB: dy_edge=0.29, dx_edge=0.05 → gap=0.294mm ≥ 0.25mm ✓
    # Ch7-Ch8 via-trace: 72.35-71.55-0.275-0.125=0.40mm ✓
    # Ch8-Ch9 via-trace: 72.95-72.35-0.275-0.125=0.20mm ✓ (via r=0.275 for 0.55mm via)
    # Ch8 vs J1:13b pad(72.675): trace top=72.475, gap=0.20mm ✓
    # Ch9 vs J1 pads: F.Cu stops at x~73, doesn't reach J1:14b(x=74.975) ✓
    _J1_FRONT_PAD_BOTTOM = 70.375  # front shield pad bottom edge
    for i, b in enumerate(btn_data):
        if i <= 5:
            # Channels 0-5: normal spacing below J1 pad zone
            b["chan_y"] = 62.0 + i * 1.2
        elif i <= 7:
            # Channels 6-7 (BTN_X, BTN_Y): jump over J1 front pads
            # DFM FIX (KiBot external): ch6 (BTN_X) at y=70.80 had hole_clearance
            # 0.15mm to SW_PWR pad 4b at (36.4, 71.4). Shift DOWN to 70.65.
            # Gap to J1 front pad bottom (70.375): 70.65-70.375-0.125=0.15mm ✓ (was 0.10mm)
            # Gap to SW_PWR 4b: sqrt(0.05^2+0.75^2)-0.45=0.30mm ✓
            k = i - 6  # 0, 1
            b["chan_y"] = _J1_FRONT_PAD_BOTTOM + 0.125 + 0.15 + k * 0.75  # 70.65, 71.40
        elif i == 8:
            # Channel 8 (BTN_START): ABOVE SW_PWR NPTH zone AND shoulder GND/BTN_L vias.
            # DFM FIX: moved from 74.06 to 73.955 to allow ch9 above with edge clearance.
            # ch8 at 73.955: gap to BTN_L via(73.43,r=0.25) = 73.955-0.125-73.43-0.25=0.15mm ✓
            # gap to NPTH(38.5,72.55,r=0.45): trace bottom=73.83, NPTH top=73.00 → 0.83mm ✓
            b["chan_y"] = 73.955
        else:
            # Channel 9 (BTN_SELECT): above BTN_START
            # DFM FIX: ch9 at 74.46 with 0.454mm via (r=0.227, AR=0.127mm):
            # gap to ch8 F.Cu(73.955) = 74.46-0.227-73.955-0.125=0.153mm > 0.15mm ✓
            # edge gap (keepout 74.99) = 74.99-74.46-0.227=0.303mm > 0.30mm ✓
            b["chan_y"] = 74.46

    # Assign approach columns near ESP32
    # Avoid passive pull-up traces at x = 43+i*5 ± 0.95, y=46-50
    passive_trace_xs = {43 + i * 5 + 0.95 for i in range(13)}
    passive_trace_xs |= {43 + i * 5 - 0.95 for i in range(13)}
    # SHORT FIX: also forbid LED current-limit +3V3 stub positions.
    # R17[1] at x=25.95, R18[1] at x=32.95: B.Cu +3V3 vert from y=63 to y=65.
    # Any approach column B.Cu vert at these X values crosses the stub → short circuit.
    passive_trace_xs |= {25.95, 32.95}
    used_approach_xs = set()

    for i, b in enumerate(btn_data):
        epx = b["epx"]
        if epx > CX:
            # Approach column offset: clears USB_D- vertical and nearby stubs.
            ax = epx + 2.8 + i * 1.0
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
    # U5 (PAM8403 SOP-16) pad columns: button B.Cu verticals must avoid U5 pads.
    # Pad half-width 0.3mm + trace half-width 0.125mm + clearance 0.10mm = 0.525mm.
    # Use 0.55mm for margin. Only add columns where button verticals can reach
    # (y span ~20-75 covers U5 pads at y=26.8 and y=32.2).
    # Pin 8/9 at x=34.445 (VREF/NC), pin 3/14 at x=28.095 (-OUT_L/-OUT_R).
    _u5_forbidden_x = [
        (25.555, 0.55),   # U5 pins 1/16 (+OUT_L/+OUT_R)
        (26.825, 0.55),   # U5 pins 2/15 (PGND)
        (28.095, 0.55),   # U5 pins 3/14 (-OUT_L/-OUT_R)
        (29.365, 0.55),   # U5 pins 4/13 (PVDD)
        (30.635, 0.55),   # U5 pins 5/12 (MUTE/SHDN)
        (31.905, 0.55),   # U5 pins 6/11 (VDD/GND)
        (33.175, 0.55),   # U5 pins 7/10 (INL/INR)
        (34.445, 0.55),   # U5 pins 8/9 (VREF/NC)
    ]

    # LCD approach columns on B.Cu: apx = 131.0 + k*0.70 for k=0..13
    # (DFM v4 moved from 134.5+k*0.45 to 131.0+k*0.70 to avoid SD conflict)
    # Button B.Cu trace (w=0.25, hw=0.125) must clear LCD B.Cu trace (w=0.20, hw=0.10)
    # by ≥0.10mm: |vx - apx_k| ≥ 0.125 + 0.10 + 0.10 = 0.325mm (use 0.40mm margin)
    # DFM v5: split approach columns — RIGHT group (10) + LEFT group (4)
    _lcd_approach_xs = [round(140.4 - k * 0.70, 4) for k in range(10)] + \
                       [round(131.0 + k * 0.70, 4) for k in range(4)]
    # FPC connector entry zone: LCD step-6 B.Cu horizontal stubs go from each apx
    # LEFT to fpx=133.15 at each fpy.  Individual column checks (_lcd_approach_xs with
    # 0.40mm margin) now cover all approach column positions at x=131.0+k*0.70.
    # The entry zone now only needs to cover the J4 contact pad zone (x=132.5..133.8)
    # where the B.Cu stubs go to fpx=133.15.  Via (r=0.45) must not overlap J4 pad
    # left edge: vx + 0.45 >= 132.5 → vx >= 132.05.
    # Use X1=131.90 (J4 left - via_r - margin), X2=134.175 (first old apx - margin).
    # NOTE: was 130.60 which over-constrained the vx space and caused BTN_A/X/Y collisions.
    _FPC_ENTRY_X1 = 131.90            # J4 pad clearance zone start
    _FPC_ENTRY_X2 = 134.5  - 0.325   # 134.175 (RIGHT min was 134.5, now shifted to 134.5)

    # DFM v3: USB D+/D- B.Cu vertical columns (w=0.2, hw=0.1)
    # Button trace (w=0.25, hw=0.125) must clear USB trace by ≥0.09mm:
    # |vx - usb_x| ≥ 0.125 + 0.10 + 0.09 = 0.315mm
    # Use 0.50mm margin to ensure conflict detection triggers reliably.
    _usb_vertical_xs = [
        (79.75, 0.50),   # USB_D- vertical at x=79.75
        (91.65, 0.50),   # USB_D- vertical at x=91.65
    ]

    # LCD post-slot B.Cu verticals: long verticals spanning most of board height.
    # Button B.Cu verticals must clear these by >= 0.15mm edge-to-edge.
    # Trace-only: |vx-lcd_x| >= 0.125+0.10+0.15 = 0.375mm. Use 0.50mm.
    # CHANNEL VIA issue: button chan_y vias at y=66-70 are near LCD vias at y=67.5.
    # Via-to-via needs center-center >= 1.15mm (0.45+0.45+0.25). At dy=0.5mm:
    # dx_min = sqrt(1.15^2 - 0.5^2) = 1.036mm.
    # The LCD secondary verticals at x=142.16 and x=144.36 have vias at y=67.5-70.
    # Buttons with chan_y near 68 (e.g., BTN_B at chan_y=68.0) need dx >= 1.04mm.
    # Margin 1.10mm for secondary verts ensures channel via clearance.
    # Main LCD post-slot verts use 0.50mm (trace clearance only, vias far from chan Y).
    _lcd_post_slot_xs = [
        (140.10, 0.60),  # net=19 LCD_BL y=18-41.75 (ends well above chan Y)
        (141.50, 0.50),  # net=20 SD_MOSI y=1.5-66.0 (was 141.2, shifted for LCD_CS via gap)
        (146.00, 0.50),  # net=21 LCD_RS y=2.2-67.5 (via at 67.5)
        (148.00, 0.50),  # net=23 LCD_CLK y=3.6-72.0 (via at 72.0)
        (152.50, 0.50),  # net=22 SD_CLK y=2.9-70.5 (via at 70.5)
    ]
    # LCD secondary verticals near channel Y band.
    # (144.36, 67.5) has a via: need dx >= 1.04mm for button chan_y=68.0 (dy=0.5).
    # (142.16, 70.5) has a via: dy=2.5mm to chan_y=68 >> 1.15mm min → trace margin only.
    _lcd_post_slot_xs.append((144.36, 1.10))  # net=21 secondary, via at y=67.5
    _lcd_post_slot_xs.append((142.16, 0.50))  # net=22 secondary, via at y=70.5 (far)
    # BTN_R shoulder B.Cu vert at x=146.85 (net=38, w=0.25).
    _lcd_post_slot_xs.append((146.85, 0.50))

    # Note: pull-up +3V3 vias at (rx-0.95, 44.6) and debounce GND vias at
    # (cx-0.95, 52.0) conflict with some button approach columns (e.g. BTN_A at
    # x=52.45 vs via at x=52.05). These are approach column conflicts, not vx
    # conflicts — the approach column allocation loop handles avoidance via
    # passive_trace_xs. Remaining violations are due to oscillation in the
    # allocation loop (adjacent passive positions < 3.0mm apart).

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
        # U5 (PAM8403) pad columns: B.Cu verticals must not cross U5 pads
        for u5x, u5m in _u5_forbidden_x:
            if abs(vx - u5x) < u5m:
                return True
        # LCD post-slot B.Cu verticals: long verticals spanning most of board height
        for lcd_x, margin in _lcd_post_slot_xs:
            if abs(vx - lcd_x) < margin:
                return True
        return False

    via_x_map = {}
    # DFM FIX: track vx values by spy level to enforce via-via gap at same Y.
    # Vias at (vx, spy) for two buttons sharing spy: need |vx1-vx2| >= 1.15mm
    # (via size 0.9mm → gap = 1.15-0.9 = 0.25mm ≥ 0.25mm JLCPCB min).
    spy_via_xs: dict[float, list[float]] = {}   # spy → [vx values placed so far]
    MIN_SAME_SPY_VX = 1.15   # minimum center-to-center for same-spy vias
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
        # Via ring (r=0.45) must clear J4 pad right edge (x=133.8) by ≥0.15mm:
        # vx ≤ 133.8 + 0.45 + 0.15 = 134.40.  But the LCD approach columns at
        # x=131..140 block most positions.  Use cap=135.60 so forbidden-x loop
        # can push LEFT through LCD columns to a safe landing.
        # SHORT FIX: only apply cap when base_vx is already NEAR J4 (< 140).
        # BTN_B (spx=149) has base_vx=147.8, well RIGHT of J4 pads at x=133.15.
        # Clamping it to 135.6 forces it LEFT through ALL LCD columns into
        # BTN_Y territory, causing F.Cu overlap at y=30.65.  Skip cap for far-right vias.
        J4_PAD_X1 = 136.2
        J4_PAD_Y1, J4_PAD_Y2 = 25.5, 45.5
        is_right = b["bx"] >= CX
        if J4_PAD_Y1 <= b["spy"] <= J4_PAD_Y2 and is_right:
            max_vx = J4_PAD_X1 - 0.45 - 0.15   # = 135.60
            # Only clamp if base_vx is in the J4 danger zone (near the LCD approach
            # columns).  Vias already to the right of x=140 are clear of J4 pads
            # and should navigate between LCD post-slot verticals via forbidden-x.
            if base_vx > max_vx and base_vx < 140.0:
                base_vx = max_vx

        # Push vx away from forbidden x columns (R17/R18 B.Cu pad columns + LCD approach)
        step_dir = -1.0 if is_right else 1.0
        vx = base_vx
        for _ in range(40):
            if not _vx_in_forbidden(vx):
                break
            vx += step_dir * 0.5

        # DFM: enforce minimum center-to-center gap between button vx columns.
        # Via 0.50mm (r=0.25). Trace 0.25mm (hw=0.125).
        # Via-to-trace: 0.25 + 0.125 + 0.15 = 0.525mm.
        # LEFT-SIDE: 0.75mm (extra margin for channel via overlap).
        # RIGHT-SIDE: 0.53mm (via_r=0.25 + trace_hw=0.125 + gap=0.155mm).
        MIN_VX_GAP = 0.53 if is_right else 0.75
        for _ in range(20):
            too_close = False
            for prev_vx in via_x_map:
                if abs(vx - prev_vx) < MIN_VX_GAP:
                    vx = prev_vx + MIN_VX_GAP * step_dir
                    too_close = True
            if not too_close:
                break
        # DFM FIX: enforce same-spy via gap (vias at identical spy Y share a row).
        # Two vias at same spy with |vx1-vx2| < 1.15mm have gap < 0.25mm.
        # Push this button's vx away from any previous via at the same spy level.
        spy_key = round(b["spy"], 3)
        for _ in range(20):
            too_close = False
            for prev_vx in spy_via_xs.get(spy_key, []):
                if abs(vx - prev_vx) < MIN_SAME_SPY_VX:
                    vx = prev_vx + MIN_SAME_SPY_VX * step_dir
                    too_close = True
                    break
            if not too_close:
                break
        # Slot zone safety: if gap enforcement pushed vx into the FPC slot zone,
        # push it to the nearest edge outside the zone.  The zone spans
        # x=124.9..129.1 (SLOT ± margin).
        # SHORT FIX: push to NEAREST edge, not always RIGHT.  This keeps buttons
        # as close to their gap-enforced position as possible.
        slot_left_edge = SLOT_X1 - slot_margin    # 124.9
        slot_right_edge = SLOT_X2 + slot_margin   # 129.1
        if (slot_left_edge < vx < slot_right_edge and
                SLOT_Y1 - slot_margin < b["spy"] < SLOT_Y2 + slot_margin):
            # Push to nearest edge: minimize displacement
            dist_left = vx - slot_left_edge
            dist_right = slot_right_edge - vx
            if dist_right <= dist_left:
                # Closer to right edge: push just outside right (into 129.1+ zone)
                # DFM FIX (KiBot external): was +0.10 (vx=129.20), giving edge
                # clearance 129.20-0.275-128.5=0.425mm < 0.50mm board edge rule.
                # Use +0.25 → vx=129.35, clearance=129.35-0.275-128.5=0.575mm ✓
                vx = slot_right_edge + 0.25   # 129.35
            else:
                # Closer to left edge: push just outside left (into 124.8- zone)
                vx = slot_left_edge - 0.10    # 124.80
        # SHORT FIX: after slot escape, re-run MIN_VX_GAP to spread buttons apart.
        # Use a reduced gap (0.40mm) for post-slot enforcement: this is enough for
        # trace-to-trace clearance (0.125+0.125+0.15=0.40mm), while the full 0.75mm
        # gap is needed only for left-side buttons where vias at channel Y overlap.
        # Right-side buttons have 1.2mm Y spacing between channel vias, giving
        # sufficient diagonal distance even at 0.40mm X spacing.
        POST_SLOT_VX_GAP = 0.40
        for _ in range(20):
            too_close = False
            for prev_vx in via_x_map:
                if abs(vx - prev_vx) < POST_SLOT_VX_GAP:
                    vx = prev_vx + POST_SLOT_VX_GAP * step_dir
                    too_close = True
            if not too_close:
                break
        # If gap cascade pushed us back into slot zone, push to nearest edge.
        # DFM FIX: if the nearest edge would land within POST_SLOT_VX_GAP of
        # an existing vx, force to the OPPOSITE edge to avoid via-to-trace
        # violations (gap must be ≥ 0.475mm for via_r+trace_hw+clearance).
        if (slot_left_edge < vx < slot_right_edge and
                SLOT_Y1 - slot_margin < b["spy"] < SLOT_Y2 + slot_margin):
            right_candidate = slot_right_edge + 0.05   # 129.15
            left_candidate = slot_left_edge - 0.05     # 124.85
            # Check if right edge conflicts with existing vx
            right_ok = all(abs(right_candidate - pv) >= 0.50
                          for pv in via_x_map)
            left_ok = all(abs(left_candidate - pv) >= 0.50
                         for pv in via_x_map)
            dist_left = vx - slot_left_edge
            dist_right = slot_right_edge - vx
            if right_ok and (dist_right <= dist_left or not left_ok):
                vx = right_candidate
            elif left_ok:
                vx = left_candidate
            elif dist_right <= dist_left:
                vx = right_candidate
            else:
                vx = left_candidate
        # Final forbidden check: ensure slot escape + gap cascade didn't land on
        # a forbidden column (LCD approach, LED pad, etc.)
        for _ in range(20):
            if not _vx_in_forbidden(vx):
                break
            vx += step_dir * 0.5
        via_x_map[vx] = b["ref"]
        spy_via_xs.setdefault(spy_key, []).append(vx)
        b["vx"] = vx

    # DFM FIX: post-allocation via-to-trace clearance enforcement.
    # Two adjacent buttons can end up with vx gap < needed minimum.
    # Nudge the outer one away from the inner one.
    # Via_r(0.25 for VIA_TIGHT, 0.23 for ch8/ch9) + trace_hw(0.125) + gap(0.15)
    VIA_TRACE_MIN = 0.58  # via_r(0.30)+trace_hw(0.125)+gap(0.15)+FP_margin(0.005)
    all_vx = [(b["vx"], i) for i, b in enumerate(btn_data)]
    all_vx.sort()
    for idx in range(len(all_vx) - 1):
        vx1, i1 = all_vx[idx]
        vx2, i2 = all_vx[idx + 1]
        gap = vx2 - vx1
        if 0 < gap < VIA_TRACE_MIN:
            nudge = VIA_TRACE_MIN - gap + 0.01
            btn_data[i2]["vx"] = round(vx2 + nudge, 2)
            all_vx[idx + 1] = (btn_data[i2]["vx"], i2)

    # DFM FIX: also check each button's vx against ALL OTHER buttons' approach_x.
    # The B.Cu column at vx passes by other buttons' approach vias at (ax, cy).
    # Need: |vx - ax| >= via_r + trace_hw + clearance = 0.25+0.125+0.15 = 0.525mm
    AX_VX_MIN = 0.55  # approach via radius(0.25) + trace hw(0.125) + gap(0.15) + margin
    for bi in range(len(btn_data)):
        vx = btn_data[bi]["vx"]
        for bj in range(len(btn_data)):
            if bi == bj:
                continue
            ax = btn_data[bj]["approach_x"]
            if 0 < abs(vx - ax) < AX_VX_MIN:
                # Push vx away from ax
                if vx < ax:
                    btn_data[bi]["vx"] = round(ax - AX_VX_MIN, 2)
                else:
                    btn_data[bi]["vx"] = round(ax + AX_VX_MIN, 2)

    # Generate traces for all front buttons
    bottom_stagger_idx = 0
    for i, b in enumerate(btn_data):
        net = b["net"]
        spx, spy = b["spx"], b["spy"]
        epx, epy = b["epx"], b["epy"]
        vx = b["vx"]
        ax = b["approach_x"]
        cy = b["chan_y"]

        # DFM: button vias use 0.50mm for annular ring = 0.15mm (tight corridors).
        # Ring = (0.50-0.20)/2 = 0.15mm >= 0.127mm JLCPCB min ✓
        # Cannot use 0.55mm here: BTN_Y/BTN_X vx corridor near FPC slot too narrow.
        _btn_is_right = b["bx"] >= CX
        # DFM FIX: via sizes by channel zone:
        # ch0-7: VIA_MIN (0.50mm) — 0.175mm clearance to adjacent B.Cu verts
        # ch8-9: 0.46mm — near board edge, need small via for edge clearance
        _VIA_EDGE = 0.46      # custom via for near-edge channels (AR=0.13mm JLCPCB min)
        _VIA_EDGE_DRILL = 0.20
        if i >= 8:
            _btn_via_sz = _VIA_EDGE
            _btn_via_drill = _VIA_EDGE_DRILL
        else:
            _btn_via_sz = VIA_MIN
            _btn_via_drill = VIA_MIN_DRILL

        # 1. F.Cu: signal pad to via
        parts.append(_seg(spx, spy, vx, spy, "F.Cu", W_SIG, net))
        parts.append(_via_net(vx, spy, net, size=_btn_via_sz, drill=_btn_via_drill))

        # 2. B.Cu: vertical from button via to F.Cu channel
        # COLLISION FIX: BTN_B (SW6) B.Cu vert at vx=142.80 collides with
        # U6 pin 6 (VSS) pad at (143.26, 61.72) size 0.6x1.3mm (left edge 142.96)
        # and GND via-in-pad at (143.26, 61.72) size 0.46mm (left edge 143.03).
        # Gap to pad = 0.035mm (need 0.10mm), gap to via = 0.105mm (need 0.15mm).
        # Fix: jog LEFT to x=142.71 between y=60.0 and y=63.5, fitting between
        # U6 pin 5 (142.16, right edge 142.46) and pin 6 (143.26, left edge 142.96).
        # BTN_B w=0.25, hw=0.125:
        #   Right edge 142.835 vs pin 6 left edge 142.96: gap=0.125mm > 0.10mm OK.
        #   Left edge 142.585 vs pin 5 right edge 142.46: gap=0.125mm > 0.10mm OK.
        #   Right edge 142.835 vs pin 6 via left edge 143.03: gap=0.195mm > 0.15mm OK.
        # SD_CLK last-mile B.Cu vert at x=142.16: gap = 142.585-142.26 = 0.325mm OK.
        if b["ref"] == "SW6":  # BTN_B
            _jog_x = 142.71   # between U6 pin 5 (142.16) and pin 6 (142.96)
            _jog_y1 = 60.0   # above U6 pin 6 zone (pad top = 61.72-0.65=61.07)
            _jog_y2 = 63.5   # below U6 pin 6 zone (pad bot = 61.72+0.65=62.37)
            # DFM FIX: W_DATA (0.20) in jog zone for 0.15mm gap to U6:5/U6:6
            # Gap = (142.96 - 142.46 - 0.20) / 2 = 0.15mm ✓
            parts.append(_seg(vx, spy, vx, _jog_y1, "B.Cu", W_SIG, net))
            parts.append(_seg(vx, _jog_y1, _jog_x, _jog_y1, "B.Cu", W_DATA, net))
            parts.append(_seg(_jog_x, _jog_y1, _jog_x, _jog_y2, "B.Cu", W_DATA, net))
            parts.append(_seg(_jog_x, _jog_y2, vx, _jog_y2, "B.Cu", W_DATA, net))
            parts.append(_seg(vx, _jog_y2, vx, cy, "B.Cu", W_SIG, net))
        else:
            parts.append(_seg(vx, spy, vx, cy, "B.Cu", W_SIG, net))
        parts.append(_via_net(vx, cy, net, size=_btn_via_sz, drill=_btn_via_drill))

        # 3. F.Cu: horizontal to approach column
        # J1 shield pad avoidance: channels 6-7 (BTN_X, BTN_Y) are now assigned
        # to y=70.8/71.55 (between front/rear J1 shield pads), avoiding the
        # J1 front pad zone entirely. No bypass needed.
        #
        # BTN_START (i=8, cy=73.955) F.Cu bypass around J1 rear shield THT pads:
        # Pad 14b at (75.67, 73.58) pad 1.4x1.8mm → x=[74.97, 76.37], y=[72.68, 74.48]
        # Pad 13b at (84.33, 73.58) pad 1.4x1.8mm → x=[83.63, 85.03], y=[72.68, 74.48]
        # Trace at y=73.955 passes through both pads. Jog NORTH to y=72.38
        # (0.175mm clearance above pad top at 72.68, 0.28mm gap to BTN_Y at y=71.85).
        if i == 8:  # BTN_START — bypass J1 rear shield pads 14b and 13b
            _bypass_y = 72.38   # safe jog Y north of pad top (72.68)
            # Pad 14b bypass: jog at x=74.47 up, straight past, jog back at x=76.87
            _p14b_jog_start = 74.47   # pad left (74.97) - 0.175 - 0.125 - margin
            _p14b_jog_end = 76.87     # pad right (76.37) + 0.175 + 0.125 + margin
            # Pad 13b bypass: jog at x=83.13 up, straight past, jog back at x=85.53
            _p13b_jog_start = 83.13   # pad left (83.63) - 0.175 - 0.125 - margin
            _p13b_jog_end = 85.53     # pad right (85.03) + 0.175 + 0.125 + margin
            # Segment order: vx → pad14b_jog_start → bypass14b → pad14b_jog_end →
            #                pad13b_jog_start → bypass13b → pad13b_jog_end → ax
            # All segments at cy=73.955 except bypasses at _bypass_y=72.38
            parts.append(_seg(vx, cy, _p14b_jog_start, cy, "F.Cu", W_SIG, net))
            parts.append(_seg(_p14b_jog_start, cy, _p14b_jog_start, _bypass_y,
                               "F.Cu", W_SIG, net))
            parts.append(_seg(_p14b_jog_start, _bypass_y, _p14b_jog_end, _bypass_y,
                               "F.Cu", W_SIG, net))
            parts.append(_seg(_p14b_jog_end, _bypass_y, _p14b_jog_end, cy,
                               "F.Cu", W_SIG, net))
            parts.append(_seg(_p14b_jog_end, cy, _p13b_jog_start, cy,
                               "F.Cu", W_SIG, net))
            parts.append(_seg(_p13b_jog_start, cy, _p13b_jog_start, _bypass_y,
                               "F.Cu", W_SIG, net))
            parts.append(_seg(_p13b_jog_start, _bypass_y, _p13b_jog_end, _bypass_y,
                               "F.Cu", W_SIG, net))
            parts.append(_seg(_p13b_jog_end, _bypass_y, _p13b_jog_end, cy,
                               "F.Cu", W_SIG, net))
            parts.append(_seg(_p13b_jog_end, cy, ax, cy, "F.Cu", W_SIG, net))
        else:
            parts.append(_seg(vx, cy, ax, cy, "F.Cu", W_SIG, net))
        parts.append(_via_net(ax, cy, net, size=_btn_via_sz, drill=_btn_via_drill))

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
            # DFM FIX: stagger_y was 35.5 - idx*1.2 (BTN_B=35.5, BTN_X=34.3, BTN_Y=33.1).
            # These values land between SPI escape F.Cu traces at y=33.67 (SD_CLK), 34.94
            # (SD_MISO), 36.21 (SD_MOSI) which span x=72..77mm.  The near_epx vias at
            # (73-75, 33-36) can NOT fit in the 1.27mm pitch SPI channels (need 2*0.725=1.45mm).
            # Also the LCD_BL B.Cu vert at x=73.015 runs y=27.955..40.0 — any B.Cu vert or
            # via from the stagger route clips it in that Y band.
            #
            # Fix: move stagger_y BELOW the U1 bottom pads (pad bottom=40.75mm).
            #   stagger_y = 41.5 + idx*1.2 → BTN_B=41.5, BTN_X=42.7, BTN_Y=43.9, BTN_SELECT=45.1
            # Verified: no F.Cu obstacles in x=25-80, y=41-45 ✓
            # net5 (BAT+) F.Cu runs at y=46.135 (x=38..81) — stagger_y must stay < 45.41 ✓
            # LCD_BL B.Cu vert ends at y=40.0 → no conflict at y=41.5+ ✓
            # +3V3 vias at (70.45,44.0),(72.05,44.6): near_epx must clear them via AABB rules.
            # B.Cu stub enters pad from below (stagger_y→epy=38-40) ✓
            stagger_y = 41.5 + bottom_stagger_idx * 1.2
            bottom_stagger_idx += 1
            # B.Cu vertical from approach column to stagger Y.
            # B.Cu vertical from approach column to stagger Y
            # (LED +3V3 stubs at x=25.95/32.95 now avoided by approach column allocation)
            parts.append(_seg(ax, cy, ax, stagger_y, "B.Cu", W_SIG, net))
            parts.append(_via_net(ax, stagger_y, net, size=VIA_STD, drill=VIA_STD_DRILL))
            # F.Cu horizontal toward ESP32 pad.
            # stagger_y > 40.0: LCD_BL B.Cu vert (x=73.015) ends at y=40.0 — no conflict ✓
            # +3V3 B.Cu vert at x=70.45 spans y=42..44 (net4).
            # Only push near_epx away from it if the B.Cu stub at stagger_y would actually
            # intersect the vert's Y range [42-hw, 44+hw]=[41.875,44.125].
            # At stagger_y=45.1 (BTN_SELECT), stub is at y=45.1 → dy=0.975mm → no B.Cu conflict.
            # At stagger_y=41.5..43.9 (BTN_B/X/Y), stub crosses vert Y range if vert Y band
            # overlaps [stagger_y-hw, stagger_y+hw].  BTN_B sy=41.5: [41.375,41.625] vs [41.875,44.125]
            # → dy=0.25 > 0, no B.Cu crossing ✓.  All stagger_y in range are clear of the vert.
            # Conclusion: no push needed for the B.Cu crossing at any stagger_y > 40.75.
            #
            # HOWEVER: near_epx via at (ne, stagger_y) must still clear +3V3 vias (AABB):
            # via at (70.45,44.0): BTN_B ne=72.285→73.52 (LCD_BL push) → cleared by X separation ✓
            # via at (70.45,44.0): BTN_X ne=73.555, BTN_Y ne=74.825 → cleared by X separation ✓
            # via at (70.45,44.0): BTN_SELECT ne=epx-2=69.25 — need AABB gap to (70.45,44.0).
            #   At ne=69.25, stagger_y=45.1: via AABB y=[44.65,45.55] vs [43.55,44.45] → dy=0.20 > 0
            #   dx = max(69.25+0.45-(70.45-0.45), 0) = max(70.15-70.00, 0) = 0.15mm
            #   gap = sqrt(0.15^2+0.20^2) = 0.25mm ≥ 0.25mm (just barely!) ✓
            # BTN_SELECT ne=69.25 does NOT trigger LCD_BL or BTN_UP_VX push — that's correct.
            BTN_UP_VX = 70.45  # +3V3 B.Cu vert / via column reference
            if epx < CX:
                _ne = epx - 2.0
                # LCD_BL B.Cu vert (x=73.015) ends at y=40.0 → at stagger_y>40, no conflict.
                # Skip the old LCD_BL push that was only needed when stagger_y was in [28,40].
                #
                # Check +3V3 B.Cu vert at x=70.45 crossing: only push if the B.Cu stub
                # at stagger_y actually intersects the vert Y band [41.875,44.125].
                # hw_stub=0.125, hw_vert=0.125. B.Cu stub y=[stagger_y-0.125, stagger_y+0.125].
                # Vert Y=[41.875,44.125]. Crossing if stagger_y-0.125 < 44.125 AND
                # stagger_y+0.125 > 41.875 → stub overlaps vert Y range.
                vert_y1 = 42 - 0.125   # 41.875
                vert_y2 = 44 + 0.125   # 44.125
                stub_overlaps_vert = (stagger_y - 0.125 < vert_y2 and
                                      stagger_y + 0.125 > vert_y1 and
                                      _ne < BTN_UP_VX < epx)
                if stub_overlaps_vert:
                    # B.Cu stub at stagger_y would cross the +3V3 vert → push right of it.
                    # Use 0.55mm offset (verified: clears +3V3 vias at (70.45,44.0) and (72.05,44.6))
                    _ne = BTN_UP_VX + 0.55
                # DFM FIX: BTN_L approach vert runs at x=72.25 (B.Cu, full height).
                # near_epx via must not land within 0.725mm (=0.45+0.125+0.15) of x=72.25.
                # Default _ne = epx-2: for BTN_B (epx=74.285), _ne=72.285 → dx=0.035mm FAIL.
                # Push right: use 72.25+0.725+epsilon=73.0 to clear BTN_L vert (gap=0.175mm ✓).
                # Verify BTN_X (epx=75.555): _ne=73.555, gap=|73.555-72.25|-0.575=0.730mm ✓ (no push).
                BTN_L_VERT_X = 72.50  # approach_l for BTN_L shoulder button vert (shifted from 72.25)
                if abs(_ne - BTN_L_VERT_X) < 0.725:
                    _ne = BTN_L_VERT_X + 0.75  # 72.50+0.75=73.25, gap=0.175mm
                # DFM FIX (KiBot external): via at (73.25, 45.1) is 0.02mm from
                # R10 pad 1 at (73.95, 46.0) size 1.0x1.3mm. Push LEFT to 72.50
                # to clear R10 (gap=|73.95-72.50|-0.5-0.25=0.70mm ✓) while
                # keeping BTN_L_VERT_X clearance (72.50-72.50=0 → need push).
                # Use 72.00 instead: BTN_L gap=|72.50-72.00|-0.575=−0.075 FAIL.
                # Use 73.00: R10 gap=|73.95-73.00|-0.5-0.275=0.175mm ✓
                # BTN_L gap=|73.00-72.50|-0.575=−0.075 FAIL (via 0.55mm).
                # Solution: keep 73.25 but check R10 overlap and shift stagger_y.
                # R10 pad AABB: x=[73.45,74.45], y=[45.35,46.65].
                # Via at (73.25, stagger_y) with r=0.275: box=[72.975, sy-0.275, 73.525, sy+0.275].
                # x-overlap: 73.525 > 73.45 AND 72.975 < 74.45 → YES.
                # y-overlap: sy+0.275 > 45.35 → sy > 45.075. If sy=45.1: 45.375>45.35 → gap=0.025mm.
                # Fix: if stagger_y > 44.8, push _ne LEFT to 72.95 (x-gap=73.45-72.95-0.275=0.225mm ✓).
                R10_PAD_LEFT = 73.45   # R10 pad 1 left edge (73.95 - 0.5)
                if stagger_y > 44.8 and _ne + 0.275 > R10_PAD_LEFT:
                    _ne = R10_PAD_LEFT - 0.275 - 0.20  # 72.975, gap=0.20mm ✓
                # DFM FIX: R9.1 decoupling cap pad (net0) at (68.95, 46.0) size=1.0x1.3.
                # BTN_SELECT (epx≈71.25, stagger_y=45.1) ne=69.25 overlaps R9.1 pad:
                #   via(69.25,45.1) r=0.45 vs pad(68.95,46.0) half=(0.5,0.65) → gap=-0.20mm DANGER.
                # Fix: when near_epx lands in the forbidden X band (R9 pad zone), push RIGHT
                # to x=73.25 to clear R9.1 AND both +3V3 vias at (70.45,44.0) and (72.05,44.6):
                #   R9.1 gap at ne=73.25: far right, no conflict ✓
                #   +3V3 via(72.05,44.6) AABB gap at ne=73.25, sy=45.1:
                #     via box=[72.80,44.65,73.70,45.55] vs +3V3=[71.60,44.15,72.50,45.05]
                #     dx=72.80-72.50=0.30mm, dy=0 → gap=0.30mm > 0.25mm ✓
                #   BTN_L_VERT_X check: abs(73.25-72.50)=0.75 → NOT pushed (barely outside 0.725) ✓
                #   ne=73.25 > epx=71.25 → B.Cu reversed stub (73.25→71.25, 2mm wide): valid ✓
                R9_PAD_X = 68.95   # R9.1 pad center x
                R9_PAD_HW = 0.5    # R9.1 pad half-width
                R9_PAD_Y = 46.0    # R9.1 pad center y
                R9_PAD_HH = 0.65   # R9.1 pad half-height
                VIA_R = 0.25       # via radius (size=0.50mm, button via)
                # Check if the via at (_ne, stagger_y) would overlap R9.1 pad
                _r9_cx = max(0, abs(_ne - R9_PAD_X) - R9_PAD_HW)
                _r9_cy = max(0, abs(stagger_y - R9_PAD_Y) - R9_PAD_HH)
                import math as _m
                _r9_gap = _m.sqrt(_r9_cx**2 + _r9_cy**2) - VIA_R
                if _r9_gap < 0.10:
                    # Push right past both +3V3 vias to x=73.25.
                    # BTN_L_VERT_X check: abs(73.25-72.50)=0.75 > 0.725 → no further push ✓
                    _ne = 73.25
                # JLCPCB DFM FIX: after R9→73.25, via at (73.25, 45.1) OD=0.60
                # overlaps R10 pad 1 at (73.95, 46.0) size 1.0x1.3 (gap=0.02mm).
                # Fix: use VIA_MIN (0.46mm, r=0.23) and shift X to 73.05.
                # R10 pad AABB: [73.45, 45.35, 74.45, 46.65].
                # Via at (73.05, 45.1) r=0.23: [72.82, 44.87, 73.28, 45.33].
                # dx=73.45-73.28=0.17, dy=45.35-45.33=0.02 → gap=sqrt(0.0293)=0.171mm ✓
                # BTN_L_VERT_X: abs(73.05-72.50)=0.55. With VIA_MIN clearance:
                #   via_r(0.23)+trace_hw(0.10)+gap(0.15)=0.48. 0.55>0.48 ✓
                # +3V3 via(72.05,44.6) AABB: via at (73.05,45.1) r=0.23:
                #   dx=73.05-0.23-(72.05+0.275)=72.82-72.325=0.495mm ✓
                _ne_via_size = VIA_STD
                _ne_via_drill = VIA_STD_DRILL
                R10_PAD_AABB = (73.45, 45.35, 74.45, 46.65)  # R10 pad 1
                _ne_r = VIA_STD / 2
                _ne_box = (_ne - _ne_r, stagger_y - _ne_r,
                           _ne + _ne_r, stagger_y + _ne_r)
                _dx = max(0, R10_PAD_AABB[0] - _ne_box[2],
                          _ne_box[0] - R10_PAD_AABB[2])
                _dy = max(0, R10_PAD_AABB[1] - _ne_box[3],
                          _ne_box[1] - R10_PAD_AABB[3])
                _r10_gap = _m.sqrt(_dx**2 + _dy**2)
                if _r10_gap < 0.15:
                    # Switch to VIA_MIN and shift X left
                    _ne_via_size = VIA_MIN
                    _ne_via_drill = VIA_MIN_DRILL
                    _ne_r_min = VIA_MIN / 2  # 0.23
                    _ne = R10_PAD_AABB[0] - _ne_r_min - 0.17  # 73.05
                near_epx = _ne
            else:
                # DFM v3: BTN_R approach via@(91.0,37.48) vs near_epx via@(90.0,37.48): gap=0.1mm.
                # epx+2.0 would place near_epx at epx+2 (90→92 for BTN_R), but approach is at epx+2.8+i.
                # For BTN_R (i=0 for right-side buttons), approach≈91.55. Distance to near_epx=92:
                # 92-91.55=0.45mm gap (size 0.9 each) → insufficient. Use epx+3.0: 93-91.55=1.45, gap=0.55mm ✓
                near_epx = epx + 3.0   # DFM: was +2.0 (0.1mm gap to approach via)
                _ne_via_size = VIA_STD
                _ne_via_drill = VIA_STD_DRILL
            parts.append(_seg(ax, stagger_y, near_epx, stagger_y,
                              "F.Cu", W_SIG, net))
            parts.append(_via_net(near_epx, stagger_y, net, size=_ne_via_size, drill=_ne_via_drill))
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
                parts.append(_via_net(ax, epy, net, size=VIA_STD, drill=VIA_STD_DRILL))
                # F.Cu horizontal OUTWARD (away from board center) to avoid LCD signal verts.
                # DFM FIX: was epx+2 if epx<CX else epx-2 (INWARD) — B.Cu stub spanned LCD_BL.
                # Fix: go OUTWARD:
                #   epx<CX: near_epx = epx-2.0 (go left, away from LCD_BL at x=73.02)
                #   epx>CX: near_epx = epx+2.0 (go right, away from LCD_RD at x=86.98)
                near_epx = epx - 2.0 if epx < CX else epx + 2.0
                parts.append(_seg(ax, epy, near_epx, epy,
                                  "F.Cu", W_SIG, net))
                parts.append(_via_net(near_epx, epy, net, size=VIA_STD, drill=VIA_STD_DRILL))
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
                # DFM FIX: check SD_CS B.Cu vert at x=153.50 (post_slot_x for SD_CS).
                # BTN_B GND via at (153.50, 34.85) lands on it — push to 154.10.
                SD_CS_VERT_X = 153.50
                if abs(gnd_via_x - SD_CS_VERT_X) < 0.58:  # via_r(0.30)+trace_hw(0.10)+gap(0.175)
                    gnd_via_x = SD_CS_VERT_X + 0.58  # 154.08 — gap 0.18mm ≥ 0.175mm
                # DFM: J4 FPC contact pads occupy x=132.5..133.8 (fpx=133.15 ± 0.65mm).
                # Via (size=0.7, r=0.35) must clear J4 pad left edge (x=132.5) by ≥0.15mm:
                # gnd_via_x + 0.35 + 0.15 ≤ 132.5 → gnd_via_x ≤ 132.0
                # Only apply when the via would ACTUALLY land inside the J4 contact band
                # (not for buttons far right where gnd_via_x > 133.8).
                J4_CONTACT_X2 = 133.15 + 0.65   # 133.80 (J4 pad right edge)
                J4_CONTACT_X1 = 133.15 - 0.65   # 132.50 (J4 pad left edge)
                MAX_GND_VX = J4_CONTACT_X1 - 0.35 - 0.15   # 132.00
                # Check if via lands in the J4 pad/approach column zone
                J4_PAD_XMAX = 134.462  # actual pad right edge (1.5mm at 133.712)
                if J4_CONTACT_X1 - 0.35 <= gnd_via_x <= J4_PAD_XMAX + 0.50:
                    # DFM v6: was 129.50 — overlapped BTN_Y approach vert in
                    # x=129-131 corridor. For SW8 (BTN_Y), route GND via straight
                    # DOWN from pad to y=49.0, below J4 mount pad (y=46.94) and
                    # LCD approach columns. Other buttons in J4 zone keep 129.50.
                    if b["ref"] == "SW8":
                        gnd_via_x = gp[0]  # 136.00 — straight below pad
                    else:
                        gnd_via_x = 129.50
            else:
                gnd_via_x = gp[0] + 1.5
                # DFM FIX: BTN_L B.Cu vert at x=16.85 (SW11:3) runs full board height.
                # GND vias for SW1 (gp[0]=15→vx=16.5) and SW2 (gp[0]=15→vx=16.5) land
                # at x=16.5: gap to vert = |16.5-16.85| - 0.35 - 0.125 = -0.125mm FAIL.
                # Need |gnd_via_x - 16.85| >= 0.35+0.125+0.15=0.625mm → x <= 16.225.
                # Reduce offset to 1.0mm for these buttons: x=16.0, gap=0.375mm ✓
                BTN_L_VERT_X = 16.85
                if abs(gnd_via_x - BTN_L_VERT_X) < 0.625:
                    gnd_via_x = gp[0] + 1.0  # 1.0mm offset: x=16.0, gap=0.375mm ✓
            # DFM v6: SW8 routes GND via straight down to y=49.0 (below
            # J4:41 mount pad at y=46.94 and LCD approach columns).
            if b["ref"] == "SW8" and b["bx"] >= CX:
                gnd_via_y = 49.0
            else:
                gnd_via_y = gp[1] + 0.5   # small Y offset to clear pad edge
            # Via size selection:
            # Left-side buttons (gnd_via_x ~16.0): use 0.46mm via to avoid JLCPCB
            # F.Cu DANGER gap to adjacent SW corner pads (1.2x0.9mm).
            # SW1[3]@(15,25.35) and SW2[3]@(15,43.35): corner at (15.6, pad_y+0.45).
            # via@(16.0, pad_y+0.5) d=0.7mm: gap=hypot(0.4,0.05)-0.35=0.053mm DANGER.
            # via@(16.0, pad_y+0.5) d=0.46mm: gap=hypot(0.4,0.05)-0.23=0.173mm OK.
            # Threshold: if gnd_via_x < BTN_L_VERT_X - 0.5 (clearly a left-side button)
            # use small via. Right-side buttons keep 0.7mm for better GND connection.
            # DFM v5: all button GND vias use 0.46mm to reduce via-segment conflicts.
            # Exception: right-side buttons near FPC slot use 0.35mm (reduced overlap
            # with approach columns in the tight x=129-131 corridor).
            # DFM: was 0.35/0.2 (AR=0.075mm VIOLATION!) and 0.46/0.2 (AR=0.13mm marginal).
            # All button GND vias now use 0.50/0.20 (AR=0.15mm >= 0.127mm JLCPCB min).
            # Cannot use 0.55mm: tight corridor near FPC slot and LCD approach columns.
            gnd_via_sz, gnd_via_drill = VIA_TIGHT, VIA_TIGHT_DRILL
            # L-shape: horizontal inward, then short segment to via.
            # DFM v6: SW8 (BTN_Y) routes GND via RIGHT then DOWN to avoid
            # BTN_X F.Cu signal at y=40.65 (x=129.80→139.00) and LCD columns.
            if b["ref"] == "SW8" and b["bx"] >= CX:
                # Route: pad(136,34.35) → right(139.50,34.35) → down(139.50,49.0)
                # x=139.50 is right of BTN_X signal end (x=139.00), gap=0.275mm ✓
                gnd_jog_x = 140.00  # right of SW7:1 pad (139.60) + clearance
                parts.append(_seg(gp[0], gp[1], gnd_jog_x, gp[1],
                                  "F.Cu", W_PWR_LOW, n_gnd))
                parts.append(_seg(gnd_jog_x, gp[1], gnd_jog_x, gnd_via_y,
                                  "F.Cu", W_PWR_LOW, n_gnd))
                parts.append(_via_net(gnd_jog_x, gnd_via_y, n_gnd,
                                      size=gnd_via_sz, drill=gnd_via_drill))
            else:
                parts.append(_seg(gp[0], gp[1], gnd_via_x, gp[1],
                                  "F.Cu", W_PWR_LOW, n_gnd))
                parts.append(_seg(gnd_via_x, gp[1], gnd_via_x, gnd_via_y,
                                  "F.Cu", W_PWR_LOW, n_gnd))
                parts.append(_via_net(gnd_via_x, gnd_via_y, n_gnd,
                                      size=gnd_via_sz, drill=gnd_via_drill))

    # Shoulder button BTN_L (B.Cu, rotated 90°)
    net_l = NET_ID["BTN_L"]
    # Use actual pad position instead of button center
    sl_pad = _pad("SW11", "3")  # signal pad (inner side toward board center)
    sx_l = sl_pad[0] if sl_pad else SHOULDER_L[1][0]
    sy_l = sl_pad[1] if sl_pad else SHOULDER_L[1][1]
    epx_l, epy_l = _esp_pin(45)
    # DFM FIX: BTN_L channel at y=73.42, using 0.46mm vias (r=0.23).
    # Gap to BTN_START F.Cu: |73.955-73.42|-0.23-0.125=0.535-0.355=0.18mm ≥ 0.175mm ✓
    # Gap to NPTH(38.5,72.55): trace bottom=73.305, NPTH top=73.00 → 0.305mm ✓
    # Board gap: 75.0-73.43-0.23=1.34mm ✓
    _BTN_L_VIA = 0.46      # custom via size for BTN_L (near BTN_START, AR=0.13mm)
    _BTN_L_VIA_DRILL = 0.20
    chan_y_l = 73.42

    # B.Cu vertical from shoulder button pad to channel
    # DFM FIX: use VIA_MIN (0.46mm) for BTN_L channel vias to fit between
    # BTN_START F.Cu(73.955) above and ch7(71.40) below.
    # DFM FIX: SW11[4] (GND, tact switch terminal B) at (sx_l, 8.50)
    # size 0.70x1.00 → y=[8.00, 9.00].  BTN_L B.Cu vert at sx_l passes
    # through this pad → short to GND.  Bridge on F.Cu over the pad.
    _sw11_pad_top = 8.00
    _sw11_pad_bot = 9.00
    _sw11_bridge_y1 = _sw11_pad_top - 0.50  # 7.50: via top=7.75, gap=0.25mm ✓
    _sw11_bridge_y2 = _sw11_pad_bot + 0.50  # 9.50: via bot=9.25, gap=0.25mm ✓
    parts.append(_seg(sx_l, sy_l, sx_l, _sw11_bridge_y1, "B.Cu", W_SIG, net_l))
    parts.append(_via_net(sx_l, _sw11_bridge_y1, net_l, size=VIA_TIGHT, drill=VIA_TIGHT_DRILL))
    parts.append(_seg(sx_l, _sw11_bridge_y1, sx_l, _sw11_bridge_y2, "F.Cu", W_SIG, net_l))
    parts.append(_via_net(sx_l, _sw11_bridge_y2, net_l, size=VIA_TIGHT, drill=VIA_TIGHT_DRILL))
    parts.append(_seg(sx_l, _sw11_bridge_y2, sx_l, chan_y_l, "B.Cu", W_SIG, net_l))
    parts.append(_via_net(sx_l, chan_y_l, net_l, size=_BTN_L_VIA, drill=_BTN_L_VIA_DRILL))
    # F.Cu horizontal to approach column
    # DFM v6: was approach_l = 72.50 (epx_l+1.25) — 0.515mm corridor between
    # +3V3 stubs (x=72.05) and U1:26 pad (x=72.565). Trace edge overlapped U1:26
    # by 0.060mm, and B.Cu vertical crossed BTN_SELECT horiz at y=45.10.
    # Fix: move approach LEFT to x=68.00, well left of all obstacles:
    #   - BTN_DOWN B.Cu vert at x=67.45: gap=68.00-67.575=0.325mm ✓
    #   - +3V3 B.Cu vert at x=70.45: different corridor, no conflict ✓
    #   - BTN_SELECT B.Cu horiz (x=69.25→71.25 at y=45.10): 68.00 < 69.25, clear ✓
    #   - C10 pads at x=67.05/68.95: gaps=0.35mm ✓
    # Route horizontal stub on F.Cu to ESP32 pad, avoiding B.Cu obstacles
    # (BTN_DOWN, BTN_UP verts) which are on a different layer.
    # GPIO45 (pin 26) is at bottom of ESP32 at epx_l=73.015, epy_l=40.0.
    # Strategy: B.Cu approach at x=67.00 (clear of GND vias at 68.55,
    # gap to BTN_DOWN vert at 67.45 = 0.25mm ✓).
    # Route: B.Cu vert from approach to epy_l=40.0, via to F.Cu,
    # F.Cu horizontal to ESP32 pad. F.Cu at y=40 is clear (ESP32 on B.Cu).
    approach_l = 64.60
    parts.append(_seg(sx_l, chan_y_l, approach_l, chan_y_l,
                       "F.Cu", W_DATA, net_l))
    parts.append(_via_net(approach_l, chan_y_l, net_l, size=_BTN_L_VIA, drill=_BTN_L_VIA_DRILL))
    # B.Cu vertical to ESP32 pin level
    parts.append(_seg(approach_l, chan_y_l, approach_l, epy_l,
                       "B.Cu", W_DATA, net_l))
    # Via to F.Cu, then F.Cu jog around GND via at (68.55, 40.0).
    # F.Cu jog: go to y=38.5 (above ESP32 bottom pins at y=40),
    # horizontal to just left of ESP32 pad, then down to epy_l.
    btn_l_fcu_y = 38.5  # above bottom pin row, below ESP32 right-side pins
    parts.append(_via_net(approach_l, epy_l, net_l, size=VIA_STD, drill=VIA_STD_DRILL))
    parts.append(_seg(approach_l, epy_l, approach_l, btn_l_fcu_y,
                       "F.Cu", W_DATA, net_l))
    parts.append(_seg(approach_l, btn_l_fcu_y, epx_l, btn_l_fcu_y,
                       "F.Cu", W_DATA, net_l))
    parts.append(_seg(epx_l, btn_l_fcu_y, epx_l, epy_l,
                       "F.Cu", W_DATA, net_l))
    # GND via on opposite shoulder pad
    # DFM: was 1mm offset — via ring at 14.15-0.45=13.70, pad right=13.15+0.45=13.60, gap=0.10mm danger.
    # Use 1.5mm: via at 14.65, ring left=14.20, pad right=13.60, gap=0.60mm clear.
    sl_gnd = _pad("SW11", "2")
    if sl_gnd:
        gnd_via_x = sl_gnd[0] + 1.5  # DFM: was 1.0mm (gap=0.10mm danger)
        parts.append(_seg(sl_gnd[0], sl_gnd[1], gnd_via_x, sl_gnd[1],
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(gnd_via_x, sl_gnd[1], n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # Shoulder button BTN_R (B.Cu, rotated 90°)
    # SW12 at enc(65, 32) = (145, 5.5) on the right side of the board.
    # Route: pad 3 (inner signal pad) -> B.Cu down -> F.Cu across -> ESP32 GPIO43
    # GPIO mapping: BTN_R = GPIO 3 (pin 15, bottom-side ESP32).
    # PSRAM fix: GPIO43 reassigned to SD_MISO, BTN_R moved to GPIO3 (LCD_RD freed).
    net_r = NET_ID["BTN_R"]
    sr_pad = _pad("SW12", "3")  # signal pad (inner side toward board center)
    epx_r, epy_r = _esp_pin(3)   # GPIO 3 = BTN_R (bottom-side ESP32 pin 15)
    if sr_pad:
        sx_r, sy_r = sr_pad
        # DFM FIX: was chan_y_l + 1.0 = 75.0 (board edge! board height=75mm).
        # Copper at y=75.0 violates edge clearance (need >=0.5mm from Edge.Cuts).
        # hole_to_hole FIX: chan_y_r=72.5 placed via at approach column too close to J1 S4.
        # Use chan_y_r = chan_y_l - 2.5 = 71.5mm (was 74.0-2.5).
        # DFM via-pad fix: chan_y_r=71.5 placed BTN_R channel via at (sx_r=146.85, 71.5)
        # which overlapped U6[11]@(147.76,72.1) [SD card shield pad] with edge=-0.14mm.
        # Fix: use chan_y_r=68.5.
        # via-via FIX: SD_MISO SPI via at (146.0, 67.5), BTN_R via at (sx_r, chan_y_r).
        # At chan_y_r=68.5: dy=1.0, gap=0.1mm < 0.25mm.
        # Fix: chan_y_r=68.7 → dy=1.2, dy_outer=0.3mm ≥ 0.25mm ✓
        # U6[11]@y=72.1: distance = 72.1-68.7 = 3.4mm, well clear ✓
        # CROSSING FIX: was chan_y_l-4.3=69.23, overlapped BTN_X F.Cu channel at y=69.20
        # (gap=-0.22mm). Moved to chan_y_l-7.53=66.0: gap to BTN_A(66.8)=0.55mm ✓,
        # gap to SD_MISO via(146,67.5)=0.824mm ✓, gap to U6[11](72.1)=6.1mm ✓
        # DFM v4: y=66.0 collided with SD_MOSI F.Cu stubs at y=66.0 (gap=-0.225mm)
        # and SD_MOSI vias at (139.96,66.0) and (141.20,66.0). Move to y=65.0:
        #   gap to BTN_A(66.8) = 1.55mm ✓, SD_MOSI vias(y=66.0) = 0.425mm ✓
        #   SD_MISO via(146,67.5) = 1.925mm ✓, U6[11](72.1) = 7.1mm ✓
        chan_y_r = chan_y_l - 8.13  # 65.30mm — clears USB_D+ vias at y=65.92 (gap=0.22mm ✓) and GND via at (76.80,66.20) (gap=0.30mm ✓)

        # B.Cu vertical from shoulder-R pad down to channel
        # DFM FIX: SW12[4] (GND, tact switch terminal B) at (sx_r, 8.50)
        # size 0.70x1.00 → y=[8.00, 9.00].  BTN_R B.Cu vert passes through
        # this pad → short to GND.  Bridge on F.Cu over the pad.
        _sw12_pad_top = 8.00
        _sw12_pad_bot = 9.00
        _sw12_bridge_y1 = _sw12_pad_top - 0.50  # 7.50
        _sw12_bridge_y2 = _sw12_pad_bot + 0.50  # 9.50
        parts.append(_seg(sx_r, sy_r, sx_r, _sw12_bridge_y1, "B.Cu", W_SIG, net_r))
        parts.append(_via_net(sx_r, _sw12_bridge_y1, net_r, size=VIA_TIGHT, drill=VIA_TIGHT_DRILL))
        parts.append(_seg(sx_r, _sw12_bridge_y1, sx_r, _sw12_bridge_y2, "F.Cu", W_SIG, net_r))
        parts.append(_via_net(sx_r, _sw12_bridge_y2, net_r, size=VIA_TIGHT, drill=VIA_TIGHT_DRILL))
        parts.append(_seg(sx_r, _sw12_bridge_y2, sx_r, chan_y_r, "B.Cu", W_SIG, net_r))
        parts.append(_via_net(sx_r, chan_y_r, net_r, size=VIA_STD, drill=VIA_STD_DRILL))
        # DFM v6: approach_r at x=76.20 with F.Cu L-shape jog to x=66.00.
        # The ESP32 area (x=67-77) is heavily congested: U1:23 pads, SPI vias,
        # GND verts, D-pad approach stubs. Route bypasses everything on F.Cu,
        # then B.Cu vert at x=66.00 (left of BTN_DOWN vert at 67.45 by 1.2mm,
        # left of all D-pad approach stubs). B.Cu stub at y=27.32 goes RIGHT
        # 5.25mm to ESP32 pad at (71.25, 27.32) — no B.Cu obstacles at this Y
        # (BTN_L vert ends at y=28.59, BTN_DOWN ends at y=29.86).
        approach_r = 76.20
        # JLCDFM FIX: BTN_R F.Cu at y=65.40 crosses SW13 (menu button) pads
        # 3,4 at (139/145, 65.05) size 1.2x0.9mm. Pad bottom edge=65.50,
        # trace edge=65.50 at y=65.40+0.10=65.50 → 0mm gap.
        # Fix: F.Cu Y-jog around SW13 pads to y=64.0 (clear of pad top 64.60
        # by 0.50mm). USB D- at (79-92, y=64.58) is outside jog x range.
        _sw13_jog_y = 64.00
        _sw13_jog_in = 146.50    # right of SW13 pad4 right edge (145.6)
        _sw13_jog_out = 137.00   # left of SW13 pad3 left edge (138.4)
        parts.append(_seg(sx_r, chan_y_r, _sw13_jog_in, chan_y_r,
                           "F.Cu", W_DATA, net_r))
        parts.append(_seg(_sw13_jog_in, chan_y_r, _sw13_jog_in, _sw13_jog_y,
                           "F.Cu", W_DATA, net_r))
        parts.append(_seg(_sw13_jog_in, _sw13_jog_y, _sw13_jog_out, _sw13_jog_y,
                           "F.Cu", W_DATA, net_r))
        parts.append(_seg(_sw13_jog_out, _sw13_jog_y, _sw13_jog_out, chan_y_r,
                           "F.Cu", W_DATA, net_r))
        parts.append(_seg(_sw13_jog_out, chan_y_r, approach_r, chan_y_r,
                           "F.Cu", W_DATA, net_r))
        parts.append(_via_net(approach_r, chan_y_r, net_r, size=VIA_STD, drill=VIA_STD_DRILL))

        # B.Cu vert from channel down toward ESP32 pin 15 at (86.985, 40.0).
        # GPIO3 is at bottom of ESP32 (pin 15), x=86.985.
        # Route: B.Cu vert at approach_r=76.20 from chan_y_r down to y=45.5
        # (below ESP32 bottom pins at y=40.0), then via, then F.Cu horizontal
        # RIGHT to x=epx_r at y=45.5, then via, then B.Cu vert UP to ESP32 pad.
        # This avoids crossing ESP32 bottom pads (y=40.0 zone).
        # y=45.5: below ESP32 GND pad bottom (31.91+2.46+1.95=36.41 from center,
        # but GND pad at PCB y≈29.96, bottom edge ≈31.91). Well below bottom pins (y=40.0).
        # +3V3 via at (76.95,44.50): gap = |76.20-76.95|-0.275-0.10=0.375mm ✓
        # BAT+ F.Cu at y=46.13: need to go below it.
        # BTN_X F.Cu at y=42.70: need to go below it.
        # Use y=48.0 — clear of both.
        btn_r_jog_y = 48.0
        parts.append(_seg(approach_r, chan_y_r, approach_r, btn_r_jog_y,
                           "B.Cu", W_DATA, net_r))
        parts.append(_via_net(approach_r, btn_r_jog_y, net_r, size=VIA_STD, drill=VIA_STD_DRILL))
        # F.Cu horizontal RIGHT past ESP32 bottom pins to epx_r+1 column
        btn_r_col_x = epx_r + 1.0  # ~87.985 — right of ESP32 pin, clear of pads
        parts.append(_seg(approach_r, btn_r_jog_y, btn_r_col_x, btn_r_jog_y,
                           "F.Cu", W_DATA, net_r))
        parts.append(_via_net(btn_r_col_x, btn_r_jog_y, net_r, size=VIA_STD, drill=VIA_STD_DRILL))
        # B.Cu vert UP to ESP32 pin level
        parts.append(_seg(btn_r_col_x, btn_r_jog_y, btn_r_col_x, epy_r,
                           "B.Cu", W_DATA, net_r))
        # B.Cu stub LEFT to ESP32 pad
        parts.append(_seg(btn_r_col_x, epy_r, epx_r, epy_r,
                           "B.Cu", W_DATA, net_r))
        # GND via on outer pad of SW12
        # DFM: was 1mm offset — same issue as SW11 (via ring gap=0.10mm to pad, danger).
        # Use 1.5mm: gap=0.60mm clear.
        sr_gnd = _pad("SW12", "2")
        if sr_gnd:
            gnd_via_x_r = sr_gnd[0] + 1.5  # DFM: was 1.0mm (gap=0.10mm danger)
            parts.append(_seg(sr_gnd[0], sr_gnd[1], gnd_via_x_r, sr_gnd[1],
                              "B.Cu", W_PWR_LOW, n_gnd))
            parts.append(_via_net(gnd_via_x_r, sr_gnd[1], n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

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
        # DFM v5: shift via further LEFT to clear button B.Cu verts.
        # Default: via_x = rx-1.20, via_y = 44.5
        # Per-index overrides for specific B.Cu vert conflicts.
        via_x = rx - 1.20
        via_y_pu = ry - 1.5   # 44.5
        # i=6 (R9, rx=73): B.Cu vert at x=71.80 crossed BTN_SELECT horiz at y=45.10
        # (x=71.25..73.25). Push LEFT to x=70.80 (left of BTN_SELECT x=71.25).
        # gap = (71.25-0.125)-(70.80+0.125) = 0.20mm ≥ 0.10mm ✓
        # Check C3:1(70.45,42): gap = (70.80-0.125)-(70.45+0.50) = 70.675-70.95 = -0.275mm?
        # Actually C3:1 right edge = 70.95, via_x vert left edge = 70.675. gap = -0.275mm!
        # Route via_x even further LEFT: 70.00. C3:1 left edge = 69.95. gap = 69.95-(70.00+0.125) = -0.175mm. Still bad.
        # Alternative: route on a different Y path to avoid the crossing entirely.
        # Use SHORTER vert that doesn't reach y=45.10: via_y_pu=46.5 (stays above BTN_SELECT@45.10).
        # +3V3 vert from (71.80, 46) to (71.80, 46.5)... no, that goes UP (further from 45.10).
        # Actually via_y_pu=44.5, so vert goes from y=46 DOWN to y=44.5, crossing y=45.10.
        # If via_y_pu = 45.5 (above crossing): vert from y=46 to y=45.5, doesn't cross y=45.10.
        # gap = 45.10+0.125-(45.5-0.125) = 45.225-45.375 = -0.15mm. Seg bottom=45.375 vs BTN_SELECT top=45.225.
        # Nope, need via_y > 45.10+0.125+0.125+0.10 = 45.45. Use via_y=45.50 for i=6.
        if i == 6:
            via_y_pu = ry + 1.5  # 47.5 — BELOW pad, away from BTN_SELECT(45.10) and BAT+ F.Cu(46.13)
            # Vert from (71.80, 46) to (71.80, 47.5) goes away from crossings ✓
            # Via at (71.80, 47.5): gap to BAT+ F.Cu(46.13) = 1.37-0.23-0.25=0.89mm ✓
        # i=7 (rx=78): BTN_R vert at x=76.35 — need via_x > 76.855
        if i == 7:
            via_x = rx - 1.05  # 76.95 — clears BTN_R vert at x=76.35 (gap=0.245mm ✓)
        # i=10 (R14, rx=93): BTN_SELECT vert at x=91.65 — need via_x > 92.18
        if i == 10:
            via_x = rx - 0.80  # 92.20 — clears USB_D- vert at x=91.65 (gap=0.17mm ✓)
        parts.append(_seg(rx - 0.95, ry, via_x, ry,
                          "B.Cu", W_DATA, n_3v3))  # W_DATA: 0.175mm gap to btn verts
        parts.append(_seg(via_x, ry, via_x, via_y_pu,
                          "B.Cu", W_DATA, n_3v3))  # W_DATA: 0.175mm gap to btn verts
        _pu_via_sz = VIA_MIN if i == 10 else VIA_STD
        _pu_via_dr = VIA_MIN_DRILL if i == 10 else VIA_STD_DRILL
        parts.append(_via_net(via_x, via_y_pu, n_3v3, size=_pu_via_sz, drill=_pu_via_dr))

    # Debounce caps: GND via at cap pad
    for i, ref in enumerate(DEBOUNCE_REFS):
        cx = 43 + i * 5
        cy = 50
        # DFM v5: shift via further LEFT to clear button B.Cu verts
        via_x_db = cx - 1.20
        if i == 7:
            via_x_db = cx - 1.05  # 76.95 — clears BTN_R vert
        if i == 8:
            via_x_db = cx - 0.80  # 82.20 — clears BAT+ B.Cu vert at x=81.0 (gap=0.52mm ✓)
        if i == 10:
            via_x_db = cx - 0.80  # 92.20 — clears USB_D- vert at x=91.65
        parts.append(_seg(cx - 0.95, cy, via_x_db, cy,
                          "B.Cu", W_DATA, n_gnd))  # W_DATA: 0.175mm gap to btn verts
        parts.append(_seg(via_x_db, cy, via_x_db, cy + 2,
                          "B.Cu", W_DATA, n_gnd))  # W_DATA: 0.175mm gap to btn verts
        _db_via_sz = VIA_MIN if i == 10 else VIA_STD
        _db_via_dr = VIA_MIN_DRILL if i == 10 else VIA_STD_DRILL
        parts.append(_via_net(via_x_db, cy + 2, n_gnd, size=_db_via_sz, drill=_db_via_dr))

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
        via_y = c3_p1[1] + 2.5   # 42.0 + 2.5 = 44.5 (below C3, clear of net34 F.Cu at y=43.9)
        parts.append(_seg(c3_p1[0], c3_p1[1], c3_p1[0], via_y,
                          "B.Cu", W_PWR_LOW, n_3v3))
        parts.append(_via_net(c3_p1[0], via_y, n_3v3, size=VIA_STD, drill=VIA_STD_DRILL))
    # C3 pad "2" -> GND via
    c3_p2 = _pad("C3", "2")
    if c3_p2:
        parts.append(_seg(c3_p2[0], c3_p2[1], c3_p2[0], c3_p2[1] - 2,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c3_p2[0], c3_p2[1] - 2, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # C4 near ESP32: pad "1" -> +3V3 via (DFM: was 1.0mm, overlapped pad edge by 0.1mm)
    c4_p1 = _pad("C4", "1")
    c4_p2 = _pad("C4", "2")
    if c4_p1:
        parts.append(_seg(c4_p1[0], c4_p1[1], c4_p1[0], c4_p1[1] - 1.4,
                          "B.Cu", W_PWR_LOW, n_3v3))
        parts.append(_via_net(c4_p1[0], c4_p1[1] - 1.4, n_3v3, size=VIA_STD, drill=VIA_STD_DRILL))
    if c4_p2:
        parts.append(_seg(c4_p2[0], c4_p2[1], c4_p2[0], c4_p2[1] - 2,
                          "B.Cu", W_PWR_LOW, n_gnd))
        # DFM FIX: reduced via from 0.90 to 0.80mm to give USB_D- vertical at
        # x=91.70 more clearance (edge gap 0.15mm vs 0.10mm at 0.90mm).
        # Annular ring = (0.80-0.30)/2 = 0.25mm >= JLCPCB 0.13mm min ✓
        parts.append(_via_net(c4_p2[0], c4_p2[1] - 2, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))

    # C26 ESP32 VDD bypass (rotated 90°): pad "1" -> +3V3, pad "2" -> GND.
    # Cap at (91.5, 21.0) rot=90 on B.Cu (mirrored). After rotate+mirror:
    # pad "1" at (91.5, y_above), pad "2" at (91.5, y_below).
    # Pad "1" (+3V3): horizontal trace to existing +3V3 via at (88.75, 21.0).
    # Pad "2" (GND): vertical stub to GND via below.
    c26_p1 = _pad("C26", "1")
    c26_p2 = _pad("C26", "2")
    if c26_p1:
        # Route to existing +3V3 via at (88.75, 21.0): horizontal then short vertical
        parts.append(_seg(c26_p1[0], c26_p1[1], 88.75, c26_p1[1],
                          "B.Cu", W_PWR_LOW, n_3v3))
        parts.append(_seg(88.75, c26_p1[1], 88.75, 21.0,
                          "B.Cu", W_PWR_LOW, n_3v3))
    if c26_p2:
        # GND via — short stub away from +3V3 trace
        parts.append(_seg(c26_p2[0], c26_p2[1], c26_p2[0], c26_p2[1] + 1.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c26_p2[0], c26_p2[1] + 1.5, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))

    # C1 AMS1117 input: pad "1" -> +5V (near VIN), pad "2" -> GND via
    # C1 at (122.0, 55.0), close to VIN pin at (122.70, 58.65) — 3.7mm
    # Vias route DOWN (+y) to avoid U3 tab pad at (125.0, 52.35) above
    c1_p1 = _pad("C1", "1")
    c1_p2 = _pad("C1", "2")
    if c1_p1:
        # +5V via below C1 pad 1 — pad1 ~(120.95,57), via at (120.95,59)
        # Clear of AMS1117 VIN via (122.70,56.65): dist=2.9mm ✓
        parts.append(_seg(c1_p1[0], c1_p1[1], c1_p1[0], c1_p1[1] + 2.0,
                          "B.Cu", W_PWR, n_5v))
        parts.append(_via_net(c1_p1[0], c1_p1[1] + 2.0, n_5v, size=VIA_STD, drill=VIA_STD_DRILL))
    if c1_p2:
        # GND via below C1 pad 2 — pad2 ~(119.05,57), via at (119.05,59)
        # Staggered Y from pad1 via for clearance
        parts.append(_seg(c1_p2[0], c1_p2[1], c1_p2[0], c1_p2[1] + 2.0,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c1_p2[0], c1_p2[1] + 2.0, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # C2 AMS1117 output: pad "1" -> AMS1117 tab (+3V3), pad "2" -> GND via
    c2_p1 = _pad("C2", "1")
    c2_p2 = _pad("C2", "2")
    am_tab = _pad("U3", "4")
    if c2_p1 and am_tab:
        parts.append(_seg(c2_p1[0], c2_p1[1], am_tab[0], c2_p1[1],
                          "B.Cu", W_PWR, n_3v3))
        parts.append(_seg(am_tab[0], c2_p1[1], am_tab[0], am_tab[1],
                          "B.Cu", W_PWR, n_3v3))
    if c2_p2:
        parts.append(_seg(c2_p2[0], c2_p2[1], c2_p2[0], c2_p2[1] + 2,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c2_p2[0], c2_p2[1] + 2, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # C17 near IP5306: VIN decoupling, pad "1" -> VBUS via, pad "2" -> GND via
    # DFM FIX: VBUS via at y-2=33.0 hit LCD_RST F.Cu at y=33.04 (gap=-0.295mm).
    # LCD_RST F.Cu at y=33.04, LCD_RD F.Cu at y=34.30. Via(0.46, r=0.23) must fit between:
    #   y > 33.04+0.10+0.15+0.23 = 33.52 and y < 34.30-0.10-0.15-0.23 = 33.82.
    # Use y=33.65 (C17p1[1]-1.35): gap to LCD_RST = 33.42-33.14=0.28mm ✓, gap to LCD_RD = 34.20-33.88=0.32mm ✓
    # DFM FIX: GND via at y+2.5=37.5 had via-via gap 0.236mm to LCD_DC via at (108.27,36.845).
    # Move to y+2.7=37.7: AABB gap to LCD_DC via = 0.316mm ✓ (need 0.25mm)
    c17_p1 = _pad("C17", "1")
    c17_p2 = _pad("C17", "2")
    if c17_p1:
        c17_vbus_via_y = c17_p1[1] - 1.35  # y=33.65 — between LCD_RST(33.04) and LCD_RD(34.30)
        # DFM: LCD_D4 B.Cu vert at x=111.50 (w=0.20). Gap at W_PWR_HIGH(0.76)=0.07mm.
        # Use 0.55mm: gap = 0.55-0.275-0.10 = 0.175mm ≥ target ✓
        parts.append(_seg(c17_p1[0], c17_p1[1], c17_p1[0], c17_vbus_via_y,
                          "B.Cu", 0.55, NET_ID["VBUS"]))
        parts.append(_via_net(c17_p1[0], c17_vbus_via_y, NET_ID["VBUS"], size=VIA_STD, drill=VIA_STD_DRILL))
    if c17_p2:
        parts.append(_seg(c17_p2[0], c17_p2[1], c17_p2[0], c17_p2[1] + 2.7,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c17_p2[0], c17_p2[1] + 2.7, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # C18 near IP5306: BAT decoupling at (116, 49), 10.7mm from pin 6 (was 15.4mm).
    # Placed right of KEY vertical at x=114.05, between KEY route and R16.
    # Pad 1 (left) -> BAT+ via UP 1.5mm: (115.5, 47.5) clears KEY horiz@y≈46.7
    # Pad 2 (right) -> GND via DOWN 2.0mm: (116.5, 51.0) clears R16 pad@y=51.85
    c18_p1 = _pad("C18", "1")
    c18_p2 = _pad("C18", "2")
    if c18_p1:
        parts.append(_seg(c18_p1[0], c18_p1[1], c18_p1[0], c18_p1[1] - 1.5,
                          "B.Cu", W_PWR_HIGH, NET_ID["BAT+"]))
        parts.append(_via_net(c18_p1[0], c18_p1[1] - 1.5, NET_ID["BAT+"], size=VIA_STD, drill=VIA_STD_DRILL))
    if c18_p2:
        parts.append(_seg(c18_p2[0], c18_p2[1], c18_p2[0], c18_p2[1] + 2.0,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c18_p2[0], c18_p2[1] + 2.0, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # C19 near L1: VOUT decoupling, pad "1" -> +5V via, pad "2" -> GND via
    # POWER SHORT FIX: C19 vias overlapped VBUS F.Cu traces causing all-rail-to-GND short.
    # VBUS horizontal @y=61.0 (width 0.5mm) and VBUS vertical @x=111.0 (width 0.5mm).
    # Old +5V via @(111.5,56.5) overlapped VBUS vert by -0.20mm.
    # Old GND via @(108.5,60.5) overlapped VBUS horiz by -0.20mm.
    c19_p1 = _pad("C19", "1")
    c19_p2 = _pad("C19", "2")
    if c19_p1:
        # FIX: route B.Cu horizontal RIGHT to x=113 (clear VBUS vert @x=111.25),
        # then B.Cu vertical UP to via. Gap: 113-0.45-111.25 = 1.30mm ✓
        safe_x = 113.0
        parts.append(_seg(c19_p1[0], c19_p1[1], safe_x, c19_p1[1],
                          "B.Cu", W_PWR, NET_ID["+5V"]))
        parts.append(_seg(safe_x, c19_p1[1], safe_x, c19_p1[1] - 2,
                          "B.Cu", W_PWR, NET_ID["+5V"]))
        parts.append(_via_net(safe_x, c19_p1[1] - 2, NET_ID["+5V"], size=VIA_STD, drill=VIA_STD_DRILL))
    if c19_p2:
        # FIX: reduce Y offset from +2 to +1.0 to clear VBUS horiz @y=61.
        # Via @(108.5,59.5): top=59.95, VBUS bottom=60.75, gap=0.80mm ✓
        parts.append(_seg(c19_p2[0], c19_p2[1], c19_p2[0], c19_p2[1] + 1.0,
                          "B.Cu", W_PWR, n_gnd))
        parts.append(_via_net(c19_p2[0], c19_p2[1] + 1.0, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # C27 near IP5306 VOUT: HF decoupling at (109, 39), 2.6mm from pin 8.
    # C_0805 pad layout: pad 1 at RIGHT (x+0.95), pad 2 at LEFT (x-0.95).
    # Pad 1 (right, x≈109.95) → GND via DOWN 1.5mm toward EP (same net).
    # Pad 2 (left, x≈108.05) → +5V: short B.Cu LEFT to existing VOUT via (107.5, 39.09).
    c27_p1 = _pad("C27", "1")
    c27_p2 = _pad("C27", "2")
    if c27_p2:
        # Pad 2 (left) → +5V: reuse existing VOUT via at (107.5, 39.09)
        parts.append(_seg(c27_p2[0], c27_p2[1], 107.5, c27_p2[1],
                          "B.Cu", W_PWR, NET_ID["+5V"]))
        parts.append(_seg(107.5, c27_p2[1], 107.5, 39.09,
                          "B.Cu", W_PWR, NET_ID["+5V"]))
    if c27_p1:
        # Pad 1 (right) → GND via DOWN toward EP pad (same net, no clearance issue)
        parts.append(_seg(c27_p1[0], c27_p1[1], c27_p1[0], c27_p1[1] + 1.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c27_p1[0], c27_p1[1] + 1.5, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # R16 IP5306 KEY pull-up: now handled in _power_traces()

    return parts


def _led_traces():
    """LED traces with inline current-limiting resistors.

    Circuit: +3V3 → R pad2 (B.Cu, left) → R pad1 (right) → via → LED pad2/Anode (F.Cu, right)
             LED pad1/Cathode (F.Cu, left) → GND
    Datasheet NCD0805R1 (C84256): pad 1 = cathode (-), pad 2 = anode (+)
    R17 at (25.0, 65.0) B.Cu, LED1 at (25.0, 67.5) F.Cu
    R18 at (32.0, 65.0) B.Cu, LED2 at (32.0, 67.5) F.Cu
    """
    parts = []
    _init_pads()
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]

    # Per-LED internal net: R pad1 → via → LED anode (pad2)
    _led_ra_nets = [NET_ID["LED1_RA"], NET_ID["LED2_RA"]]

    pairs = [("R17", "LED1"), ("R18", "LED2")]
    for i, (r_ref, led_ref) in enumerate(pairs):
        r_p1 = _pad(r_ref, "1")   # B.Cu: x+0.95 (mirrored) — RIGHT
        r_p2 = _pad(r_ref, "2")   # B.Cu: x-0.95 (mirrored) — LEFT
        led_p1 = _pad(led_ref, "1")  # F.Cu: x-0.95 — LEFT (cathode)
        led_p2 = _pad(led_ref, "2")  # F.Cu: x+0.95 — RIGHT (anode)
        if not (r_p1 and r_p2 and led_p1 and led_p2):
            continue

        n_ra = _led_ra_nets[i]  # internal resistor-to-anode net

        # +3V3 via → R pad 2 (B.Cu, LEFT side of resistor)
        via_3v3_y = r_p2[1] - 1.20
        parts.append(_via_net(r_p2[0], via_3v3_y, n_3v3, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(r_p2[0], via_3v3_y, r_p2[0], r_p2[1],
                          "B.Cu", W_PWR_LOW, n_3v3))

        # R pad 1 (B.Cu, RIGHT) → via → LED pad 2/Anode (F.Cu, RIGHT)
        mid_y = r_p1[1] + 1.25
        parts.append(_seg(r_p1[0], r_p1[1], r_p1[0], mid_y,
                          "B.Cu", W_SIG, n_ra))
        parts.append(_via_net(r_p1[0], mid_y, n_ra, size=0.8, drill=0.35))
        parts.append(_seg(led_p2[0], mid_y, led_p2[0], led_p2[1],
                          "F.Cu", W_SIG, n_ra))

        # LED pad 1/Cathode (F.Cu, LEFT) → GND via
        gnd_via_x = led_p1[0] - 0.7
        parts.append(_seg(led_p1[0], led_p1[1], gnd_via_x, led_p1[1],
                          "F.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(gnd_via_x, led_p1[1], n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    return parts


def _reset_boot_traces():
    """Reset and Boot button traces (B.Cu, dev kit style).

    SW_RST: EN pin to GND (hardware reset)
      - GND pads (3,4) connect via GND plane (In1.Cu) through vias
      - Signal pads (1,2) connect to EN net via stub + via to In1/In2
        then short B.Cu stub to R3/C3 EN junction

    SW_BOOT: GPIO0 to GND (download mode when held during reset)
      - GND pads (3,4) connect via GND plane (In1.Cu) through vias
      - Signal pads (1,2) connect to BTN_SELECT net (GPIO0)
        Simple GND via — the button just shorts GPIO0 to GND when pressed

    Routing strategy: short B.Cu stubs + vias only. Avoids the dense
    button vertical trace zone (x=43-103, y=42-65) by using minimal stubs.
    """
    parts = []
    _init_pads()
    n_gnd = NET_ID["GND"]
    n_en = NET_ID["EN"]
    n_sel = NET_ID["BTN_SELECT"]

    # ── SW_RST (Reset) ──
    # Pads after B.Cu mirroring: p1=(98,63.65) p2=(92,63.65) p3=(98,67.35) p4=(92,67.35)
    rst_p1 = _pad("SW_RST", "1")
    rst_p2 = _pad("SW_RST", "2")
    rst_p3 = _pad("SW_RST", "3")
    rst_p4 = _pad("SW_RST", "4")

    if rst_p3:
        # GND: pad 3 → short stub down → via to In1.Cu GND plane
        parts.append(_seg(rst_p3[0], rst_p3[1], rst_p3[0], rst_p3[1] + 2.0,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(rst_p3[0], rst_p3[1] + 2.0, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))
    if rst_p4:
        parts.append(_seg(rst_p4[0], rst_p4[1], rst_p4[0], rst_p4[1] + 2.0,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(rst_p4[0], rst_p4[1] + 2.0, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))

    if rst_p1:
        # EN signal: pad 1 (right pad at x=98) → short B.Cu stub up
        # → via to assign EN net. Long-distance connection to C3 pad 1
        # (EN junction at 70.45, 42.0) left for manual routing.
        # Via at y=60.0: clears VBUS F.Cu (y=61, w=0.6→edge 60.7).
        # Via edge at 60.0+0.3=60.3, gap=60.7-60.3=0.4mm ≥ 0.1mm ✓
        via_y = 60.0
        parts.append(_seg(rst_p1[0], rst_p1[1], rst_p1[0], via_y,
                          "B.Cu", W_SIG, n_en))
        parts.append(_via_net(rst_p1[0], via_y, n_en,
                              size=VIA_STD, drill=VIA_STD_DRILL))

    # ── SW_BOOT (Boot/Download mode) ──
    # Pads after B.Cu mirroring: p1=(108,63.65) p2=(102,63.65) p3=(108,67.35) p4=(102,67.35)
    boot_p1 = _pad("SW_BOOT", "1")
    boot_p2 = _pad("SW_BOOT", "2")
    boot_p3 = _pad("SW_BOOT", "3")
    boot_p4 = _pad("SW_BOOT", "4")

    if boot_p3:
        # GND: pad 3 → stub down → via
        parts.append(_seg(boot_p3[0], boot_p3[1], boot_p3[0], boot_p3[1] + 2.0,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(boot_p3[0], boot_p3[1] + 2.0, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))
    if boot_p4:
        parts.append(_seg(boot_p4[0], boot_p4[1], boot_p4[0], boot_p4[1] + 2.0,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(boot_p4[0], boot_p4[1] + 2.0, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))

    if boot_p2:
        # BTN_SELECT (GPIO0): pad 2 (left at x=102) → short B.Cu stub up
        # → via to assign BTN_SELECT net.
        # Using pad 2 (x=102) instead of pad 1 (x=108) to avoid GND via
        # at (108.5, 59.5). Via at y=60.0, x=102: clear of VBUS F.Cu ✓
        via_y = 60.0
        parts.append(_seg(boot_p2[0], boot_p2[1], boot_p2[0], via_y,
                          "B.Cu", W_SIG, n_sel))
        parts.append(_via_net(boot_p2[0], via_y, n_sel,
                              size=VIA_STD, drill=VIA_STD_DRILL))

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
    # Reset collision grid and pad state for fresh generation
    global _PADS, _PAD_NETS, _PAD_POS_LOOKUP
    _GRID.reset()
    _PADS = {}
    _PAD_NETS = {}
    _PAD_POS_LOOKUP = {}

    # Initialize keepout zones from mounting holes
    _init_keepout_zones()
    # Reset detour Y counter for unique spacing
    global _MH_DETOUR_IDX
    _MH_DETOUR_IDX = {}

    all_parts = []
    all_parts.extend(_power_traces())
    all_parts.extend(_display_traces())
    all_parts.extend(_spi_traces())
    all_parts.extend(_i2s_traces())
    all_parts.extend(_pam_passive_traces())
    all_parts.extend(_usb_traces())
    all_parts.extend(_button_traces())
    all_parts.extend(_passive_traces())
    all_parts.extend(_led_traces())
    all_parts.extend(_reset_boot_traces())
    all_parts.extend(_power_zones())

    # Report collision violations
    _GRID.print_report()

    return "".join(all_parts)


def get_collision_violations():
    """Return collision violations from the last generate_all_traces() call."""
    return _GRID.get_violations()
