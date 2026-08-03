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

from .. import primitives as P
from .. import footprints as FP
from ..primitives import NET_ID
from ..collision import CollisionGrid

# ── Collision detection grid (populated in _init_pads, used by _seg/_via_net)
_GRID = CollisionGrid()

# ── Trace widths ──────────────────────────────────────────────────
W_PWR = 0.6
W_PWR_HIGH = 0.76     # High-current power: VBUS, BAT+, LX (≥2.1A, 1oz Cu, 10°C rise)
W_PWR_LOW = 0.30      # Light power stubs: +3V3/GND short cap-to-via runs (~0.5A)
W_SIG = 0.25
# Diagnostic VBUS branch: the 'Power High' class floor, not the current it
# needs. LED3 draws 0.59 mA and 0.15 mm would carry it, but VBUS is a
# Power High net and verify_net_class_widths judges the net, not the branch.
W_VBUS_DIAG = 0.50
W_DATA = 0.2
W_AUDIO = 0.3
# Narrow width used only where a button channel has to thread the gap
# between the CC1 via and J1's front shield pads (see the BTN_B bypass in
# _button_traces). 0.15 mm is well above the 0.09 mm JLCPCB / .kicad_dru
# minimum and carries a pulled-up button input, so the extra ~0.3 ohm over
# the 12 mm bypass is irrelevant.
W_J1_BYPASS = 0.15

# ── Via sizes (JLCPCB 4-layer: AR >= 0.15mm recommended) ─────────
VIA_STD = 0.60       # standard via OD (AR=0.20mm with drill 0.20)
VIA_STD_DRILL = 0.20
VIA_TIGHT = 0.60     # tight-corridor via OD (AR=0.20mm — matches VIA_STD, eliminates JLCPCB warnings)
VIA_TIGHT_DRILL = 0.20
VIA_MIN = 0.50       # minimum via OD (AR=0.15mm — JLCPCB recommended minimum)
VIA_MIN_DRILL = 0.20

# ── Power-rail barrels ────────────────────────────────────────────
# A layer transition on a power rail is a conductor like any other and
# has to be sized for the rail's current, not for "a via fits here".
# verify_power_via_ampacity.py measures a transition against the IPC-2221B
# internal curve with an 18 um barrel and a 10 degC rise:
#
#     0.20 mm drill -> 0.527 A     0.35 mm drill -> 0.791 A
#     0.45 mm drill -> 0.949 A
#
# so a 2 A rail needs at least three 0.35 mm barrels in parallel and the
# 4.35 A battery path needs six. Annular ring stays >= 0.13 mm (the
# drc_check.py minimum) at every OD/drill pair below.
VIA_PWR = 0.90        # power barrel OD (AR=0.275 with drill 0.35) — the _via_net default
VIA_PWR_DRILL = 0.35
VIA_PWR_TIGHT = 0.80  # power barrel for crowded clusters (AR=0.225 with drill 0.35)
VIA_PWR_BIG_DRILL = 0.45  # 0.949 A per barrel; OD 0.85 -> AR=0.20

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
    """Build keepout zones from mounting holes and other features.

    In-place (clear+append), NEVER rebound: domain modules hold eager
    bindings to this list, and a rebind here would fork the state — the
    split's one semantic trap. Same rule for _PADS/_PAD_NETS/_PAD_POS_LOOKUP.
    """
    _KEEPOUT_CIRCLES.clear()
    # Mounting holes: 3.5mm pad + 0.5mm clearance = 2.25mm radius
    from ..board import MOUNT_HOLES_ENC, enc_to_pcb, USBC_ENC
    for ex, ey in MOUNT_HOLES_ENC:
        mx, my = enc_to_pcb(ex, ey)
        _KEEPOUT_CIRCLES.append((mx, my, 2.25))  # 1.75mm pad radius + 0.5mm clearance

    # J1 lives in a 0.015 mm-tight vertical budget between the BTN_B button
    # channel and the board edge (see footprints.usb_c_16p "ANNULAR BUDGET").
    # board.py and routing.py each carry their own copy of its position, so
    # a one-sided edit would silently move the shield pads into the button
    # channels. Fail loudly instead of drifting.
    _board_usbc = enc_to_pcb(*USBC_ENC)
    if (round(_board_usbc[0], 4), round(_board_usbc[1], 4)) != (
            round(USBC[0], 4), round(USBC[1], 4)):
        raise AssertionError(
            f"J1 placement out of sync: board.USBC_ENC -> {_board_usbc}, "
            f"routing.USBC = {USBC}. Update both (and re-check the J1 "
            f"annular budget in footprints.usb_c_16p)."
        )


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

       A strategy-B detour may also HAND BACK at detour_y instead of
       climbing to y (see _exit_at_detour): the right-hand B.Cu vertical
       is dropped and the F.Cu run resumes at the detour level. Same via
       count, and the caller continues from the returned exit y.

    Returns (parts, exit_y): the segment/via S-expressions, and the Y at
    which the trace is back on `layer` at x2. exit_y is y for every route
    except an exit-at-detour strategy-B detour.
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
            # Strategy A: NORTH JOG — stay on `layer`, step over the keepout.
            #
            # This used to be a LAYER SWAP: via down, B.Cu horizontal at the
            # same Y under the NPTH, via back up. Its only user is LCD_WR at
            # y=35.575, and that B.Cu span crossed the In2.Cu +3V3/+5V seam at
            # x=105.05 — the display's write strobe losing its return plane
            # halfway through the pulse (verify_reference_plane FAIL). The
            # layer swap also drove B.Cu straight through the keepout it was
            # supposed to respect, and cost two vias.
            #
            # The trace is outside the drill+clearance zone by definition here,
            # so it only has to clear the (larger) keepout radius. Jogging north
            # on the same layer does that with no vias and no reference change
            # at all: F.Cu references the solid In1.Cu GND pour throughout.
            #
            # Columns stay where the old vias were, so the horizontal extent is
            # unchanged and the vertical legs sit 2.65mm from the hole centre,
            # clear of the 2.35mm keepout+halfwidth radius.
            x_left = round(cx - cr - via_r - 0.15, 2)
            x_right = round(cx + cr + via_r + 0.15, 2)
            # North of the keepout circle by half a trace width plus 0.15mm.
            # LCD_WR: 37.5 - 2.25 - 0.10 - 0.15 = 35.00, which leaves 0.495mm
            # to the LCD_RST lane at y=34.305 (edges 34.405 / 34.90) and clears
            # BTN_START's F.Cu at y=34.94 by x (it stops at x=100.45).
            jog_y = round(cy - cr - width / 2 - 0.15, 3)

            # Verify x boundaries are within segment span, and that jogging
            # north is actually a step away from the hole.
            if x_left <= lo_x or x_right >= hi_x or jog_y >= y:
                continue

            # 1. Horizontal from x1 to x_left at y
            parts.append(_seg(x1, y, x_left, y, layer, width, net))
            # 2. Vertical north to the jog level
            parts.append(_seg(x_left, y, x_left, jog_y, layer, width, net))
            # 3. Horizontal across the keepout at the jog level
            parts.append(_seg(x_left, jog_y, x_right, jog_y, layer, width, net))
            # 4. Vertical back south to the lane
            parts.append(_seg(x_right, jog_y, x_right, y, layer, width, net))
            # 5. Horizontal from x_right to x2 at y
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
            # R32: idx1 108.27 -> 108.24. C17's 0805 land grew to the JLC
            # reference and pad 2's west edge moved to 108.475, leaving this
            # column 0.105mm — under JLCPCB's 0.127mm floor. The column is
            # boxed in: the MH detour via at 107.70 (r=0.30) bounds it at
            # 108.227 and C17.2 at 108.248, so 108.24 is the only place it
            # fits — 0.140mm west, 0.135mm east.
            _right_cols = [110.00, 108.24, 111.80]  # DFM: idx2 at 111.80 (was 111.50): clears C17[1] right edge by 0.175mm ✓
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

            # Where the detour hands the trace back to `layer`.
            #
            # idx2 is LCD_D4, and its lane y=36.21 is 1.21mm SOUTH of the
            # +5V island on In2.Cu (island top edge y=35.00, x=105..123).
            # Climbing back to that lane at x_right=111.80 put a B.Cu
            # vertical straight through the +3V3/+5V seam, and the caller's
            # col_x vertical at x=115.20 then crossed back — two return-path
            # breaks on the fastest bus on the board (verify_reference_plane
            # FAIL). detour_y=32.30 is north of the island everywhere, so
            # handing back there keeps every B.Cu millimetre of LCD_D4 over
            # solid +3V3. The right-hand B.Cu vertical disappears and its via
            # simply moves north with the hand-off — via count unchanged.
            #
            # idx0/idx1 keep the classic climb-back: their lanes are needed
            # further south and the crossing analysis above is written for it.
            _exit_at_detour = [False, False, True]
            exit_at_detour = _exit_at_detour[min(south_idx, 2)]

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
            if exit_at_detour:
                # 5. Via B.Cu -> F.Cu at (x_right, detour_y)
                parts.append(_via_net(x_right, detour_y, net,
                                      size=via_sz, drill=via_dr))
                # 6. F.Cu horizontal from x_right to x2 at detour_y
                parts.append(_seg(x_right, detour_y, x2, detour_y,
                                  layer, width, net))
                return parts, detour_y
            # 5. B.Cu vertical from detour_y to y at x_right
            parts.append(_seg(x_right, detour_y, x_right, y, "B.Cu", width, net))
            # 6. Via B.Cu -> F.Cu at (x_right, y)
            parts.append(_via_net(x_right, y, net, size=via_sz, drill=via_dr))
            # 7. F.Cu horizontal from x_right to x2 at y
            parts.append(_seg(x_right, y, x2, y, layer, width, net))
        return parts, y

    # No keepout crossed: single segment
    parts.append(_seg(x1, y, x2, y, layer, width, net))
    return parts, y


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
# R21 (2026-07-25): -33.70 -> -33.65 (J1 backed 0.05 mm off the board edge)
# so the taller rear shield pads keep 0.5 mm copper-to-edge. Must stay in
# sync with board.USBC_ENC — asserted in _init_keepout_zones().
USBC = enc(0, -33.65)     # (80.0, 71.15) — rear shield pads clear board edge by 0.515mm

# ── J1 USB-C shield THT pads, in board coordinates ───────────────
# Derived from the footprint's single source of truth so the button
# F.Cu channels below re-tune themselves if the land pattern changes.
# J1 is placed unrotated, so local Y adds directly to the origin Y.
J1_SHIELD_XS = (USBC[0] - FP.USBC_SHIELD_DX, USBC[0] + FP.USBC_SHIELD_DX)
J1_FRONT_PAD_TOP = (USBC[1] + FP.USBC_SHIELD_FRONT_DY
                    - FP.USBC_SHIELD_FRONT_H / 2)          # 68.265
J1_FRONT_PAD_BOTTOM = (USBC[1] + FP.USBC_SHIELD_FRONT_DY
                       + FP.USBC_SHIELD_FRONT_H / 2)       # 70.385
J1_REAR_PAD_TOP = (USBC[1] + FP.USBC_SHIELD_REAR_DY
                   - FP.USBC_SHIELD_REAR_H / 2)            # 72.565
J1_REAR_PAD_BOTTOM = (USBC[1] + FP.USBC_SHIELD_REAR_DY
                      + FP.USBC_SHIELD_REAR_H / 2)         # 74.485
J1_SHIELD_HALF_W = FP.USBC_SHIELD_FRONT_W / 2              # 0.60

# CC1 escape: J1 pad 4 goes up on B.Cu, vias to F.Cu here, then runs west
# to R1. Module-level because the BTN_B bypass in _button_traces is pinned
# against the bottom edge of the via this creates.
CC1_FCU_Y = 67.40  # midpoint between BTN_A(66.8) and BTN_B(68.0)


def _crosses_j1_front_shield(x1, x2, y, width):
    """True if an F.Cu horizontal at y would violate clearance to either
    J1 front shield THT pad.

    Used to decide whether a button channel needs a bypass. Purely
    geometric so it re-evaluates itself if the land pattern or J1's
    placement moves — no hardcoded channel index.
    """
    pad_clearance = 0.20
    if not (J1_FRONT_PAD_TOP - pad_clearance - width / 2
            < y
            < J1_FRONT_PAD_BOTTOM + pad_clearance + width / 2):
        return False
    lo, hi = min(x1, x2), max(x1, x2)
    return any(lo <= px + J1_SHIELD_HALF_W and hi >= px - J1_SHIELD_HALF_W
               for px in J1_SHIELD_XS)

SD = enc(60, -29.5)       # (140.0, 67.0)  — bottom-right
IP5306 = enc(30, -5)      # (110.0, 42.5)  — moved left
# U3 = SY8089AAAC synchronous buck (SOT-23-5), replaces the AMS1117 LDO.
# Placed with the IN/FB column facing WEST so the +5V side sits inside the
# In2.Cu +5V pour (x < 123) while LX / L2 / C_OUT sit east of it, on the
# continuous +3V3 plane.  See _power_traces() for the full clearance math.
BUCK = enc(39.8, -16.0)   # (119.8, 53.5)
PAM8403 = enc(-50, 8)     # (30.0, 29.5)
L1 = enc(30, -15)         # (110.0, 52.5)  — near IP5306
JST = enc(-0.25, -25)     # (79.75, 62.5) — moved 5mm closer to USB-C (J1);
                          # R32: 0.25mm further WEST. Two things need it:
                          # F1's 1812 body overlapped J3's housing by
                          # 0.430mm (verify_component_bodies), and J3's
                          # signal pads grew to the 3.4mm JST land, which
                          # only clears the USB_D- via at (79.75, 64.525)
                          # when the 1.0mm inter-pad channel is centred on
                          # it. F1 takes the other 0.45mm of the split.
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
MENU = ("SW13", enc(62, -24.2))   # Synced with board.py MENU_ENC
# BAT54C dual Schottky diode — menu combo (START+SELECT via D1)
#
# R5-CRIT-6 FIX (2026-07-25) — D1 RELOCATED from enc(76,-15) = (156, 52.5).
# At x=156 the two anodes could not be reached: BTN_START and BTN_SELECT
# both terminate around x=100-102 and every corridor east of there is
# blocked (south perimeter y=73.95 crosses the J1 back-row shield pads at
# y=[72.575,74.575]; north crosses IP5306 / L1 / AMS1117 / C17-C19 / the
# MENU_K F.Cu at x=156 / the USB D+/D- verticals at x=90-91). Result: both
# anodes were isolated pads and the menu combo did not work.
#
# New home: enc(21.225,-19.0) = (101.225, 56.5) on B.Cu, rotation 180°.
# It sits in the 1.30 mm free channel between the two button columns:
#   BTN_START  B.Cu vertical x=100.45 (spans y=34.94..73.955)
#   BTN_SELECT B.Cu vertical x=102.00 (spans y=60.00..63.65)
# At 180° the SOT-23 two-pad row faces NORTH and the solo cathode pad
# faces SOUTH, which puts pin 1 (anode → BTN_START) on the west column
# and pin 2 (anode → BTN_SELECT) on the east column with no crossing:
#   pin 1 = (100.275, 55.400)   pin 2 = (102.175, 55.400)
#   pin 3 = (101.225, 57.600)  → MENU_K heads south to the y=62.4 corridor
# Only MENU_K now has to cross the board, instead of two anode nets.
# Kept west of x=105 so it does not collide with the parallel SY8089A
# buck-regulator rework in x=[105,125], y=[39,59].
D1_DIODE = ("D1", enc(21.225, -19.0))
D1_POS = enc(21.225, -19.0)
D1_ROT = 180   # SOT-23 two-pad row faces north; single import point for
               # board.py placement, _init_pads() and the JLCPCB CPL export.

# Geometry the D1 menu-combo routing hangs off (see _menu_diode_traces).
# These mirror values produced elsewhere in this module — kept as named
# constants so a future move of either button column is a one-line change
# instead of a silent disconnection.
_MENU_BTN_START_COL_X = 100.45    # BTN_START B.Cu vertical (y=34.94..73.955)
_MENU_BTN_SELECT_COL_X = 102.00   # BTN_SELECT B.Cu vertical
_MENU_BTN_SELECT_VIA_Y = 60.00    # BTN_SELECT B.Cu→F.Cu via at (102.00, 60.00)
_MENU_K_COL_X = 101.225           # MENU_K B.Cu descent, centred in the
                                  # 1.30 mm channel between the two columns
_MENU_K_CORRIDOR_Y = 62.400       # MENU_K F.Cu east run: below the VBUS rail
                                  # (y=61.0) and above the SW13 GND row (63.55)
_MENU_K_RISER_X = 137.000         # F.Cu riser up to the SW13 terminal row
# Shoulder buttons on B.Cu (back side, rotated 90deg, aligned to top edge)
SHOULDER_L = ("SW11", enc(-65, 32))
SHOULDER_R = ("SW12", enc(65, 32))
# Reset and Boot buttons on B.Cu (right of USB-C, dev kit style)
RESET_BTN = ("SW15", enc(15, -28))   # EN to GND
BOOT_BTN = ("SW14", enc(25, -28))   # GPIO0 to GND

# LED positions (F.Cu)
LED1 = enc(-55, -30)   # (25.0, 67.5) Red - charging
LED2 = enc(-48, -30)   # (32.0, 67.5) Green - full

# Passive positions (B.Cu) — synced with board.py placements
# Pull-ups at y=46, debounce at y=50, x = 43 + i*5
# R9-MED-4 (2026-04-11): R19/C20 removed — they were on a dead BTN_MENU
# net never wired to MENU_K. 12 button pull-ups + 12 debounce caps only.
PULL_UP_REFS = [f"R{i}" for i in range(4, 16)]
DEBOUNCE_REFS = [f"C{i}" for i in range(5, 17)]

# Power passives (synced with board.py placements)
R1_POS = (74.0, 67.0)    # USB CC1 pull-down (ux-6, uy-5)
R2_POS = (77.95, 67.0)   # USB CC2 pull-down (moved near R1, B.Cu-only route)
                         # R32: 78.0 -> 77.95. The 0805 land grew to the JLC
                         # reference width and R2.1's east edge came within
                         # 0.125mm of the USB_D- B.Cu column at x=79.75, which
                         # is pinned to J1 pad 7 and cannot move. 0.05mm west
                         # restores 0.175mm.
# (R3 was "ESP32 decoupling" at (65, 42) in an earlier layout; the ref
# now belongs to the EN RC pull-up — see the authoritative R3_POS below.
# The old module-level duplicate was shadowed and only misleading.)
R16_POS = (115.0, 52.5)  # IP5306 KEY pull-down
R17_POS = (25.0, 65.0)   # LED1 current limit (near LED1 on B.Cu)
R18_POS = (32.0, 65.0)   # LED2 current limit (near LED2 on B.Cu)

# ── Diagnostic LED bank (workstream H, docs/diagnostic-leds-roadmap.md) ──
# LED3/VBUS, LED4/+5V, LED5/+3V3 passive rail indicators + LED6 on LED_HB
# (GPIO15). Two F.Cu rows in the bottom-right pocket: resistors at y=54,
# LEDs at y=58, silk labels in the 2.7 mm gap between them at y=56.
#
# Why F.Cu for the RESISTORS too, breaking the R17/R18 "resistor on B.Cu
# under its LED" pattern: B.Cu here is the SD-card / ABXY button fan-out
# (BTN_A/BTN_X/BTN_Y risers plus SD_MOSI). A 0805 only fits on B.Cu at
# x 132.5-139.5 and 149-150.5 — room for two of the four. F.Cu, by
# contrast, is one clear 28 x 4.9 mm rectangle (x 128.5-156.5, y 53.5-58.4).
#
# Why x = 134/140/146/152 and not a rounder 132/138/144/150: each LED
# cathode needs a GND via, and a via must be clear on BOTH layers. The
# both-layers-clear windows here are x [131.25, 140.50], [143.75, 144.75]
# and [147.75, 151.50]; this pitch puts every cathode via (at x - 2.15)
# inside one of them. At 132/138/144/150 three of the four vias landed on
# BTN_A/BTN_X/BTN_Y or SD_MOSI on B.Cu.
#
# Why not further west: the display module PCB is 98 x 72 mm and the
# enclosure seats it 0.5 mm above the board (enclosure.scad
# `pcb_z + pcb_d + 0.5`), so x 31..129 is a height keepout for anything
# taller than that gap. x=134 keeps the westmost pad 2.45 mm clear of it.
# Y at which the diagnostic VBUS tap leaves the F.Cu VBUS riser at x=111.
# power.py SPLITS the riser here so the branch meets a shared endpoint:
# a mid-segment T has degree 1 and verify_dangling_copper reads it as copper
# ending in air (the same bug already fixed once for the U4 VBUS tap).
# Shared constant so the split and the branch cannot drift apart.
DIAG_VBUS_TAP_Y = 49.75
DIAG_LED_Y = 58.0        # LED row (F.Cu)
DIAG_R_Y = 54.0          # series-resistor row (F.Cu, 4 mm north)
DIAG_LABEL_Y = 56.0      # F.SilkS rail labels, centred between the rows
DIAG_X = {"R28": 134.0, "R29": 140.0, "R30": 146.0, "R31": 152.0}
R28_POS = (DIAG_X["R28"], DIAG_R_Y)    # VBUS  indicator, 5.1k -> 0.59 mA
R29_POS = (DIAG_X["R29"], DIAG_R_Y)    # +5V   indicator, 5.1k -> 0.59 mA
R30_POS = (DIAG_X["R30"], DIAG_R_Y)    # +3V3  indicator, 1k   -> 1.33 mA
R31_POS = (DIAG_X["R31"], DIAG_R_Y)    # LED_HB heartbeat, 1k  -> 1.33 mA
LED3_POS = (DIAG_X["R28"], DIAG_LED_Y)
LED4_POS = (DIAG_X["R29"], DIAG_LED_Y)
LED5_POS = (DIAG_X["R30"], DIAG_LED_Y)
LED6_POS = (DIAG_X["R31"], DIAG_LED_Y)
# (ref_r, ref_led, rail net, RA net) — one row per diagnostic LED, consumed
# by routing.passives._diag_led_traces() and by board.py for the silk.
DIAG_LEDS = [
    ("R28", "LED3", "VBUS", "LED3_RA", "VBUS"),
    ("R29", "LED4", "+5V", "LED4_RA", "5V"),
    ("R30", "LED5", "+3V3", "LED5_RA", "3V3"),
    ("R31", "LED6", "LED_HB", "LED6_RA", "HB"),
]

# ── U3 SY8089AAAC buck converter cluster ─────────────────────────
# All coordinates are hand-verified against the surrounding copper; see the
# clearance table in _power_traces()::"buck converter" for the arithmetic.
# C2 (22uF tantalum, the old AMS1117 output cap) is DELETED — a 1 MHz buck
# needs a low-ESR MLCC output cap, and C2 was the part that destroyed
# prototype #1 when it was assembled reversed
# (website/docs/rework/incident-c2-reversed.md).
C1_POS = (119.8, 56.6)   # C_IN 22uF 1206 MLCC, rot 180 (pad1 +5V west, pad2 GND east)
L2_POS = (126.0, 54.45)  # 2.2uH output inductor, rot 0 (pad2 west = BUCK_LX)
C30_POS = (127.8, 58.9)  # C_OUT 22uF 1206 MLCC, rot 90 (pad1 +3V3 north, pad2 GND south)
# The divider parts are placed at rot 180 so pad 1 is the WEST pad. That makes
# the pin numbering match the natural schematic drawing order:
#   R25/C29: pin 1 = +3V3 (top of the divider), pin 2 = BUCK_FB (tap)
#   R26:     pin 1 = BUCK_FB (tap),             pin 2 = GND (bottom)
# Rotating a 2-pad passive by 180 deg does not move either pad, it only swaps
# which physical pad carries number 1 — the layout below is unaffected.
R25_POS = (118.0, 63.4)  # FB divider upper 100k, rot 180 (pad1 west = +3V3)
C29_POS = (118.0, 60.3)  # 22pF feed-forward across R25, rot 180 (same pad sides)
R26_POS = (121.35, 63.4) # FB divider lower 22k, rot 180 (pad1 west = BUCK_FB)
                         # R32: 121.2 -> 121.35. With the wider 0805 land the
                         # R25.2/R26.1 pad gap fell to 0.150mm, under JLCPCB's
                         # 0.25mm SMD pad-to-pad matrix; 0.30mm now.
                         # x was 121.1: 3.10mm centres on two 0805s leaves only
                         # 3.10 - 1.45 - 1.45 = 0.20mm of copper gap, under
                         # JLCPCB's published 0.25mm minimum for 0805<->0805.
                         # 121.2 gives 3.20mm centres -> 0.30mm gap. Found by
                         # drc_check's corrected rule, which measures real
                         # pad-to-pad copper instead of centre distance; the
                         # old centre-distance rule could not see it.
C3_POS = (69.55, 42.0)   # ESP32 decoupling 1 — 0.05mm right of 69.5 (C3[2] gap to BTN_UP: 0.095→0.145mm)
C4_POS = (92.0, 42.0)    # ESP32 decoupling 2 — DFM: moved from 85 (pad1@85.95 hit U1[16]@85.715 at y=40)
C26_POS = (91.5, 21.0)   # ESP32 VDD bypass — within 3.6mm of U1 pin 2 (+3V3 at 88.75,23.51)
C28_POS = (86.0, 26.0)   # ESP32 +3V3 bulk cap (10uF) — 3.7mm from U1 pin 2, clear of F.Cu LCD traces
# EN RC delay network (R25-CRIT-1 respin fix, module datasheet p.28 fig.7:
# an RC delay circuit MUST be added at EN — R=10k to +3V3, C to GND).
# Placed on the EN trace (y=24.78) 5-7mm east of U1 pin 3 (88.75, 24.78),
# in the empty B.Cu pocket between C26 (x=91.5) and the EN corner (x=98).
# rot=90 puts pad 1 north (via to the In-plane at y=19.6, clear of the
# F.Cu LCD traces at y=20.5/21.5 by 0.5mm) and pad 2 south (stub onto EN).
R3_POS = (94.0, 22.3)    # 10k pull-up: pad1 -> +3V3 via, pad2 -> EN
C31_POS = (96.2, 22.3)   # 100nF reset cap: pad1 -> GND via, pad2 -> EN
# Backlight series resistor (R25-HIGH-1 respin fix): 20R 1206, rot=90 on
# B.Cu inside the +5V island footprint (x<=123, y=35..62), south of the
# LCD bus ladder via row. Three earlier placements failed in the
# collision grid and are recorded so nobody retries them: x=127.0 sat in
# the middle of the FPC slot cutout (x=125.5..128.5, y=23.5..47.5 —
# nothing places or routes through it); x=121.5 sat 0.05 mm off the
# net17 ladder column; x=124.2 sat 0.05 mm off the net14 column — the
# LCD B.Cu bus ladder runs 1.1 mm-pitch columns at x=114.1..124.0, so no
# 1206 fits anywhere in x 114..125.5. Pad 1 (north, y=44.0) carries
# LED_BLA under the ladder's via row (y=41.3), up the corridor between
# the net14 column (x=124.0) and the slot's west edge (x=124.75), and
# over the slot's north edge at y=22.3 to J4 pad 8. Pad 2 (south,
# y=47.0) drops straight into the island tap via at (121.7, 48.5).
# 20R from the family class rating (6 LED / 90 mA, Vf 3.2V:
# (5.0-3.2)/0.090 ≈ 20R, P=0.16W -> 1206). See routing/display.py.
R27_POS = (121.7, 45.5)
# VBUS PTC resettable fuse (R3-HIGH-4 fix): BHFUSE BSMD1812-200-30V
# (hold 2 A / trip 4 A, 20 mΩ — sized for the IP5306's ~2 A charge
# draw). In series between J1's VBUS pads and everything downstream:
# the J1 side (pads 2/11, the reversibility loop, the B.Cu riser at
# x=82.4) becomes net VBUS_IN; U2.1 / U4.5 / C17.1 stay VBUS. Placed
# rot 0 in the pocket between the J3 mech tab (J3.4 top y=58.35, 0.35mm
# pad-pad gap) and U4 (pads at x>=89.7, 0.30 mm gap); pad 1 west =
# VBUS_IN from the riser, pad 2 east = VBUS via the via cluster in the
# fuse's own inter-pad channel (see routing/power.py).
#
# R32 (2026-08-03): x 85.8 -> 86.25. verify_component_bodies measured
# F1's 1812 body 0.430mm INSIDE J3's connector housing — the JLCDFM
# "component collision" DANGER. 0.68mm of separation is needed for the
# 0.25mm rule; J3 gives 0.25 (it has the D- via to stay centred on) and
# F1 gives 0.45. East is the only free direction for F1: U4 cannot move
# (its pins ARE the D+/D- approach columns at x=90.25/91.65), so the
# 0.75mm F1-pad-to-U4-pad gap pays for the move and ends at 0.30mm.
F1_POS = (86.25, 60.6)
C17_POS = (110.0, 35.0)  # IP5306 cap
C18_POS = (116.0, 49.0)  # IP5306 BAT decoupling — moved closer: 10.7mm from pin 6 (was 15.4mm)
C19_POS = (110.0, 58.5)  # IP5306 VOUT bulk cap (lx, ly+6) — kept as bulk, C27 handles HF
C27_POS = (108.0, 39.0)  # IP5306 VOUT HF decoupling — 2.0mm from pin 8 (new)

# PAM8403 passive positions (synced with board.py placements)
# Spread ~1.5-2mm from U5 body for cleaner layout. Body: x=[27.3,32.7] y=[24.5,34.5].
# Decoupling at 250kHz effective up to ~7mm.
C21_POS = (38.0, 23.5)   # VREF bypass cap (pin 8 to GND) — 4.8mm from pin 8
C22_POS = (33.175, 20.0) # DC-blocking cap in series between I2S_DOUT and PAM_IN_AC
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

# P-MOSFET reverse polarity protection (v4.0; re-oriented for R31-HIGH-1)
# Q1 (SI2301CDS SOT-23-3): right of J3, above J3.4 mech tab.
# Pin 1=Gate, Pin 2=Source (BAT+, IP5306 side), Pin 3=Drain (BAT_IN, cell side)
#
# THE DRAIN FACES THE CELL AND THAT IS THE WHOLE POINT (R31-HIGH-1).
# A P-channel body diode conducts D->S. With the cell on the drain, a
# correctly-inserted cell forward-biases the diode (the load pre-charges
# through it) and V_GS = -V_BAT then turns the channel on; a REVERSED cell
# reverse-biases the diode while V_GS is positive, so both the diode and
# the channel block. Wired the other way round — cell on the source, which
# is what shipped through v4.5.0 — normal polarity behaves identically,
# which is exactly why working boards never revealed anything, but a
# reversed cell forward-biases the body diode and the protection does
# nothing. Do not "simplify" this back by swapping the nets without also
# turning the package around.
#
# Turning the package around is what Q1_ROT is: at 180 deg the lone drain
# pad lands on the y=54.1 channel, which is the ONLY corridor from J3 to
# Q1 (J3.4's mounting tab occupies x 82.60-84.10, y 54.95-58.35 below it,
# and the BAT+ channel is above it). The two-pad row moves north, so the
# gate moves north with it — see R24_POS.
Q1_ROT = 180   # drain (pad 3) faces J3; single import point for board.py,
               # jlcpcb_export.py and the pad table below
# Pads at Q1_ROT=180 on B.Cu (X-mirrored):
#   Gate   (84.05, 51.90)   Source/BAT+ (85.95, 51.90)   Drain/BAT_IN (85.00, 54.10)
# Clearance analysis:
#   - Drain (85.0, 54.1): BAT_IN horizontal at y=54.1 clears J3.4 (top 54.95) by 0.55mm
#   - Source (85.95, 51.9): BAT+ riser clears GND via (86.80,52.0) by 0.25mm
#   - Gate (84.05, 51.9): BAT+ channel at y=52.9 passes 0.35mm below it
#   - BAT+ channel at y=52.9 clears GND via (82.20,51.5) by 0.80mm, (86.80,52.0) by 0.25mm
#   - BAT_IN at y=54.1 clears VBUS B.Cu (starts y=61) and USB_D- B.Cu (starts y=64.58)
Q1_POS = (85.0, 53.0)    # right of J3, above J3.4 tab — clears all B.Cu verticals
# R24 (100K 0805): gate pull-down resistor, pin 1=RPP_GATE, pin 2=GND.
#
# R24 lives NORTH of Q1 and it has to: with the drain turned toward J3 the
# gate pad moves to the north row, and the BAT+ channel (y=52.9) plus the
# BAT_IN channel (y=54.1) are two continuous walls of copper between that
# pad and everything south of the part. The old spot (86.0, 56.0) is on
# the far side of both.
#
# Vertical (90 deg) in the 2.1 mm gap between the C13 and C14 pad columns,
# which is the only column north of Q1 wide enough. The GND via sits in
# the one free horizontal band left by the three F.Cu rails that cross
# this area — BAT+ (y 45.755-46.515), BTN_R (y 47.9-48.1) and +5V
# (y 48.47-49.23) — namely y 46.99-47.42. Moving R24 by a millimetre in y
# will put its via on one of those rails.
#   pad1 RPP_GATE at (85.40, 49.25), pad2 GND at (85.40, 47.35)
# Clearance: pad edges x 84.75-86.05 → C13.1 (ends 84.45) 0.30mm,
#            C14.2 (starts 86.55) 0.50mm; GND via 0.25mm to the BTN_R rail
R24_POS = (85.5, 48.3)   # C13/C14 gap, north of Q1's gate pad
                         # R32: 85.4 -> 85.5. The wider 0805 land closed the
                         # gap to C13.1/R12.1 (west) to 0.200/0.224mm, under
                         # JLCPCB's 0.25mm matrix. The window is only
                         # [85.45, 85.55] — C14.2/R13.2 bound it at x=86.475 —
                         # so 85.5 is the centre of it: 0.30mm west, 0.30mm east.
R24_ROT = 270            # pad 1 (gate) south, toward Q1


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

# Pad nets known BEFORE the first trace is placed, consumed by _init_pads()
# when it seeds the collision grid. Filled by _assemble.generate_all_traces
# from the previous (discovery) pass's _PAD_NETS; empty during that pass.
#
# Without it the collision detector was default-OPEN: a pad only acquired a
# net when a trace endpoint reached it, so a pad the router never targets
# stayed at net 0 forever — and net-0 pads were skipped in queries. A trace
# could be laid straight over such a pad with nothing reported.
_SEED_PAD_NETS = {}     # {(ref, pad_num_str): net_id}


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
        ("U3", "SOT-23-5", *BUCK, 180, "B"),
        ("U5", "SOP-16", *PAM8403, 90, "B"),
        ("L1", "SMD-4x4x2", *L1, 0, "B"),
        ("L2", "IND-SMD-4.0x4.0", *L2_POS, 0, "B"),
        ("J3", "JST-PH-2P-SMD", *JST, 180, "B"),
        ("SPK1", "Speaker-28mm", *SPEAKER, 0, "B"),
        ("SW16", "SS-12D00G3", *PWR_SW, 0, "B"),
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

    # BAT54C dual Schottky diode (B.Cu, between the BTN_START and
    # BTN_SELECT columns — see D1_DIODE for the R5-CRIT-6 relocation)
    ref_d1, pos_d1 = D1_DIODE
    _PADS[ref_d1] = _compute_pads("SOT-23-3", pos_d1[0], pos_d1[1], D1_ROT, "B")

    # P-MOSFET reverse polarity protection (v4.0)
    _PADS["Q1"] = _compute_pads("SOT-23-3", Q1_POS[0], Q1_POS[1], Q1_ROT, "B")
    _PADS["R24"] = _compute_pads("R_0805", R24_POS[0], R24_POS[1], R24_ROT, "B")

    # Key passives with explicit routing
    passive_placements = [
        # U3 buck cluster (C2 deleted — see C1_POS comment block)
        ("C1", "C_1206", *C1_POS, 180, "B"),
        ("C30", "C_1206", *C30_POS, 90, "B"),
        ("R25", "R_0805", *R25_POS, 180, "B"),
        ("R26", "R_0805", *R26_POS, 180, "B"),
        ("C29", "C_0805", *C29_POS, 180, "B"),
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
        # Diagnostic LED bank — all F.Cu. The resistors are rot=180 so that
        # pad 2 (the rail side) faces WEST, towards the incoming rails, and
        # pad 1 (the LEDn_RA side) faces EAST, towards the LED anode. That
        # keeps the polarity convention identical to R17/R18 (pad 1 = _RA,
        # pad 2 = rail) while making every link a plain Manhattan hop.
        ("R28", "R_0805", *R28_POS, 180, "F"),
        ("R29", "R_0805", *R29_POS, 180, "F"),
        ("R30", "R_0805", *R30_POS, 180, "F"),
        ("R31", "R_0805", *R31_POS, 180, "F"),
        ("LED3", "LED_0805", *LED3_POS, 0, "F"),
        ("LED4", "LED_0805", *LED4_POS, 0, "F"),
        ("LED5", "LED_0805", *LED5_POS, 0, "F"),
        ("LED6", "LED_0805", *LED6_POS, 0, "F"),
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
        # EN RC delay network (R25-CRIT-1 respin fix)
        ("R3", "R_0805", *R3_POS, 90, "B"),
        ("C31", "C_0805", *C31_POS, 90, "B"),
        # Backlight series resistor (R25-HIGH-1 respin fix)
        ("R27", "R_1206", *R27_POS, 90, "B"),
        # VBUS PTC fuse (R3-HIGH-4 fix)
        ("F1", "F_1812", *F1_POS, 180, "B"),
        # USB ESD protection
        ("U4", "SOT-23-6", *U4_POS, 0, "B"),
        ("R22", "R_0402", *R22_POS, 90, "B"),
        ("R23", "R_0402", *R23_POS, 90, "B"),
    ]
    # Button pull-up resistors (y=46, x=43..103, 5mm spacing)
    for i, ref in enumerate(PULL_UP_REFS):
        passive_placements.append((ref, "R_0805", 43 + i * 5, 46, 0, "B"))
    # Button debounce caps (y=50, x=43..103, 5mm spacing)
    for i, ref in enumerate(DEBOUNCE_REFS):
        passive_placements.append((ref, "C_0805", 43 + i * 5, 50, 0, "B"))
    # R3 history: the original R3 was an UNROUTED 10k at x=65.95 (overlapping
    # the BTN_DOWN approach column) and was removed. It is back as the EN
    # pull-up at R3_POS, this time routed — see the R3_POS comment block.
    # C28: ESP32 +3V3 bulk cap (10uF, 2.8mm from U1 pin 2)
    passive_placements.append(("C28", "C_0805", *C28_POS, 90, "B"))
    for ref, fp, cx, cy, rot, lc in passive_placements:
        _PADS[ref] = _compute_pads(fp, cx, cy, rot, lc)

    # Build position lookup for auto pad-net detection in _seg()/_via_net()
    for ref, pad_dict in _PADS.items():
        for num, (px, py) in pad_dict.items():
            key = (round(px, 2), round(py, 2))
            _PAD_POS_LOOKUP.setdefault(key, []).append((ref, num))

    # Pre-populate collision grid with pads, slot, edges, mounting holes
    if not _GRID._populated:
        from ..pad_positions import get_pads_and_layers
        from ..board import MOUNT_HOLES_ENC, enc_to_pcb
        # One call, not two: _component_placeholders() consumes UUIDs, so a
        # second walk would shift every uuid in the emitted board.
        all_pads, pad_layers = get_pads_and_layers()
        # Pads whose net must be seeded before the first trace arrives.
        # Derived from NET_ID, never hardcoded — the previous copy of this
        # table inside collision.py went stale on J3.1 (BAT+ -> BAT_IN) and
        # turned a legitimate same-net connection into a reported short.
        #
        # These four are the pads the discovery pass cannot supply: J1.13/14
        # are duplicate pad NAMES on the shield (the position lookup keeps
        # one), and J3.1/2 sit under the connector body where no trace
        # endpoint lands. Everything else comes from _SEED_PAD_NETS below.
        _seed_nets = {
            ("J1", "13"): NET_ID["GND"],    # shield front (duplicate pad name)
            ("J1", "14"): NET_ID["GND"],    # shield rear  (duplicate pad name)
            ("J3", "1"): NET_ID["BAT_IN"],  # JST pin 1 — through Q1 RPP MOSFET
            ("J3", "2"): NET_ID["GND"],     # JST pin 2
        }
        # The routed pad->net map from the discovery pass (see
        # _assemble.generate_all_traces). Empty on the discovery pass itself.
        # The explicit four above win on conflict: they describe pads the
        # discovery pass gets wrong, not pads it misses.
        for _key, _net in _SEED_PAD_NETS.items():
            _seed_nets.setdefault(_key, _net)
        _GRID.register_pads(all_pads, _seed_nets, pad_layers)
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
    """Shorthand for segment. Auto-registers pad-net associations.

    Raises on a zero-length segment. Such a segment is degenerate copper: it
    has no extent, so it connects nothing, yet it still lands in the netlist
    as an isolated fragment of its net. One of these sat on VBUS at
    (82.40, 68.78) for the whole life of v1, hidden by the unconnected_zone
    baseline, and only surfaced when that suppression was removed. They are
    always a bug — usually a jog left behind after its two endpoints were
    aligned — so fail loudly rather than emit copper nobody asked for.
    """
    if abs(x2 - x1) < 1e-6 and abs(y2 - y1) < 1e-6:
        raise ValueError(
            f"zero-length segment at ({x1}, {y1}) on {layer}, net {net}: "
            f"degenerate copper connects nothing. Remove the call, or give "
            f"the segment a real endpoint."
        )
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
# ── Tap points on button approach verticals ──────────────────────────
# A branch that lands on the MIDDLE of an existing segment is electrically
# fine, but it leaves the branch endpoint without a coincident endpoint —
# indistinguishable from a dead-end stub both for the DFM checker and for a
# human reading the file. Registering the tap here splits the vertical so
# the junction becomes a real 3-way endpoint.
#   (100.45, BTN_START) @ y=55.400 — D1 anode 1 stub (R5-CRIT-6 relocation)
_VERT_TAP_POINTS = {
    (100.45, "BTN_START"): (55.400,),
}
_NET_NAME_BY_ID = {nid: name for name, nid in NET_ID.items()}


def _pu_jog_vert(x, y1, y2, width, net):
    """B.Cu vertical — pass through directly, split at registered taps.

    Pull-up/debounce pad conflicts are prevented at the approach column
    allocation stage (passive_trace_xs forbidden zone check).
    """
    taps = sorted(
        (ty for ty in _VERT_TAP_POINTS.get(
            (round(x, 3), _NET_NAME_BY_ID.get(net, "")), ())
         if min(y1, y2) < ty < max(y1, y2)),
        reverse=(y1 > y2),
    )
    ys = [y1, *taps, y2]
    return [_seg(x, ys[i], x, ys[i + 1], "B.Cu", width, net)
            for i in range(len(ys) - 1)]


def get_collision_violations():
    """Return collision violations from the last generate_all_traces() call."""
    return _GRID.get_violations()
