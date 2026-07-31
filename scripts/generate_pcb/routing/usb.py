"""Split from routing.py 2026-07-26 — mechanical, AST-driven, proven by a
byte-identical regenerated .kicad_pcb. One domain per module; every helper
and every constant lives in _shared (original order, so import-time
execution is unchanged). See routing/__init__.py for the contract."""
from ._shared import (
    CC1_FCU_Y,
    FP,
    J1_SHIELD_XS,
    NET_ID,
    USBC,
    VIA_MIN,
    VIA_MIN_DRILL,
    VIA_STD,
    VIA_STD_DRILL,
    W_DATA,
    W_J1_BYPASS,
    W_PWR,
    W_PWR_HIGH,
    W_PWR_LOW,
    W_SIG,
    _PAD_NETS,
    _esp_pin,
    _init_pads,
    _pad,
    _seg,
    _via_net,
    math,
)




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
    # v4.0 NOTE: dm_col_x cannot move closer to dp_col_x (90.25) due to:
    # 1. VBUS via at (90.95, 59.3) OD=0.60 blocks x=90.65..91.25
    # 2. R14 pad at (92.05, 46.0) left edge=91.55 blocks x=91.30..91.55
    # 3. U4 TVS pins 1/6 at x=91.9 require D- approach near x=91.65
    # These three constraints pin dm_col_x to ~91.65. Zdiff ≈ 130Ω is acceptable
    # for USB 2.0 Full-Speed (12 Mbps, tolerance ~25mm mismatch at 12 MHz).
    dm_col_x = dm_x + 2.90   # 91.65 — clears C4 GND via and R14 +3V3 stub
    # USB D+/D- LENGTH MATCHING: D- is already ~4.6mm longer than D+.
    # The meander was incorrectly added to D- (making the delta worse).
    # Removed: 4.56mm delta is acceptable for USB Full-Speed 12Mbps
    # (USB 2.0 FS tolerance is ~25mm mismatch at 12MHz).
    # Straight F.Cu horizontal from D- via to dm_col_x.
    parts.append(_seg(usb_dm[0], dm_via_y, dm_col_x, dm_via_y, "F.Cu", W_DATA, n_dm))
    # DFM FIX: SW15[2] (GND, tact switch terminal B) at (92.00, 63.65)
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
    # DFM FIX: D- B.Cu vertical at dm_col_x=91.65 overlaps R14 pull-up pad
    # at (92.05, 46.0) and C16 debounce pad at (92.05, 50.0).
    # Jog through channel between R13@88 and R14@93.
    # Must clear USB_D+ vertical at x=90.25 (w=0.20): need gap >= 0.20mm edge-to-edge.
    # _dm_jog_x right edge = 91.10+0.10=91.20. R14 pad left edge = 91.55. Gap=0.35mm ✓
    # _dm_jog_x left edge = 91.10-0.10=91.00. USB_D+ right edge = 90.35. Gap=0.65mm ✓
    _dm_jog_x = 91.10   # clears USB_D+ at 90.25 and R14 pad at 92.05
    _dm_jog_y_bot = 53.0
    _dm_jog_y_top = 43.5
    parts.append(_seg(dm_col_x, _dm_fcu_bridge_y, dm_col_x, _dm_jog_y_bot,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_seg(dm_col_x, _dm_jog_y_bot, _dm_jog_x, _dm_jog_y_bot,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_seg(_dm_jog_x, _dm_jog_y_bot, _dm_jog_x, _dm_jog_y_top,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_seg(_dm_jog_x, _dm_jog_y_top, dm_col_x, _dm_jog_y_top,
                       "B.Cu", W_DATA, n_dm))
    parts.append(_seg(dm_col_x, _dm_jog_y_top, dm_col_x, _c4_pad_top,
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
        parts.append(_seg(usb_cc1[0], usb_cc1[1], usb_cc1[0], CC1_FCU_Y,
                           "B.Cu", W_SIG, n_cc1))
        parts.append(_via_net(usb_cc1[0], CC1_FCU_Y, n_cc1, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(usb_cc1[0], CC1_FCU_Y, r1_p1[0], CC1_FCU_Y,
                           "F.Cu", W_SIG, n_cc1))
        parts.append(_via_net(r1_p1[0], CC1_FCU_Y, n_cc1, size=VIA_STD, drill=VIA_STD_DRILL))
        parts.append(_seg(r1_p1[0], CC1_FCU_Y, r1_p1[0], r1_p1[1],
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

    # ── USB return path GND stitching vias ──────────────────────────
    # R17 (2026-04-12): the 2 stitching vias previously placed at
    # (86.0, 69.0) and (88.0, 69.0) had no F.Cu/B.Cu copper anchor —
    # they connected only to the inner-plane GND fill, which gives
    # zero benefit for the F.Cu USB D+/D- return path. KiCad DRC
    # correctly flagged them as via_dangling. Removed. To improve USB
    # return path integrity in v2, route a small F.Cu GND patch under
    # the USB D+ serpentine and connect a stitching via to that patch.

    return parts


def _usb_c_reversibility_traces():
    """Wire up the J1 lands that make the receptacle orientation-agnostic.

    A USB-C receptacle presents each signal twice, once on the A row and
    once on the B row, so that the plug lands on a live contact whichever
    way round it goes in. On this 12-land part (see the land map in
    footprints.usb_c_16p) that means:

        GND   lands 1 (A1+B12) and 12 (B1+A12)
        VBUS  lands 2 (A4+B9)  and 11 (B4+A9)
        D+    lands 6 (A6/DP1) and 8  (B6/DP2)
        D-    lands 7 (A7/DN1) and 5  (B7/DN2)
        CC1   land 4,  CC2 land 10  (already terminated by R1 / R2)

    Before R21 only one land of each pair was wired: 12, 2, 6, 7. Two
    separate defects came out of that.

    1. VBUS / GND (the DRC "unconnected" reports). Lands 1 and 11 were
       given a net and left to "connect through the zone fill", but they
       are SMD lands with no barrel, so they never reached In1.Cu or
       In2.Cu and sat electrically floating. The board still charged —
       the merged A4+B9 land alone is live in both orientations — but on
       two of the four VBUS contacts and two of the four GND contacts
       instead of all four. The datasheet rates each contact at 40 mOhm
       max, and the IP5306 pulls up to 2.1 A, so halving the contact
       count roughly doubles the connector's share of the charging-path
       drop and its self-heating. Now bonded with real copper.

    2. D+ / D- (the actual "USB-C is not reversible" defect, and it does
       NOT show up as a DRC unconnected item because lands 5 and 8 had no
       net at all, so nothing was looking for them). USB Type-C r2.1
       s4.2 requires a USB 2.0 device to tie A6-B6 and A7-B7 together on
       the PCB, because a C-to-A or captive cable populates only one of
       the two pairs in the plug. With only A6/A7 wired, the plug's data
       pair lands on B6/B7 in the flipped orientation and the device
       simply does not enumerate. Charging worked either way round, which
       is why this was never caught on the bench. Now shorted.

    Everything here is on B.Cu (J1's own side) except a single 1 mm F.Cu
    hop that lets the two data links cross, because the two shorts
    interleave (6-8 has to step over 7, 5-7 has to step over 6) and a
    planar crossing is impossible.

    Geometry notes, board coordinates, J1 origin (80.0, 71.15):
      signal land row  y = 68.775, lands span y = 68.225 .. 69.325
      land pitch       0.50 mm, wide lands 0.55 wide, narrow 0.30
      peg NPTH         (77.11, 69.845) and (82.89, 69.845), r = 0.325
      front shield     x 75.075..76.275 / 83.725..84.925, y 68.265..70.385
      rear shield      y 72.565..74.485
    The band y = 70.5 .. 72.4 between the two shield rows is empty on
    B.Cu across the whole connector and is what makes this routable.
    """
    parts = []
    _init_pads()

    n_gnd = NET_ID["GND"]
    n_vbus = NET_ID["VBUS"]
    n_dp = NET_ID["USB_D+"]
    n_dm = NET_ID["USB_D-"]

    p1 = _pad("J1", "1")     # GND  (A1 + B12)
    p2 = _pad("J1", "2")     # VBUS (A4 + B9)  — already routed to the IP5306
    p5 = _pad("J1", "5")     # D-   (B7 / DN2)
    p6 = _pad("J1", "6")     # D+   (A6 / DP1) — already routed to U4/R22
    p7 = _pad("J1", "7")     # D-   (A7 / DN1) — already routed to U4/R23
    p8 = _pad("J1", "8")     # D+   (B6 / DP2)
    p11 = _pad("J1", "11")   # VBUS (B4 + A9)
    if not all((p1, p2, p5, p6, p7, p8, p11)):
        return parts

    # ── GND: land 1 -> front shield tab 13 ──────────────────────────
    # The shield tab is a plated through-hole already bonded to the
    # In1.Cu GND plane, and it sits 0.525 mm to the right of land 1 with
    # nothing in between, so a straight stub on the land row is the whole
    # connection. Kept on the row (y = 68.775) rather than angled down,
    # because that puts the trace 1.114 mm from the right peg hole —
    # comfortably past the 0.879 mm the "NPTH to Track" rule needs for a
    # 0.60 mm trace. Left end clears land 2 (VBUS) by 0.225 mm.
    # The second leg drops onto the tab's centre so both ends of the link
    # terminate on a pad origin (JLCDFM dead-end check); it is 0.30 mm
    # inside the tab's own copper, so it adds no new clearance case.
    _shield_x = J1_SHIELD_XS[1]
    _shield_y = USBC[1] + FP.USBC_SHIELD_FRONT_DY
    parts.append(_seg(p1[0], p1[1], _shield_x, p1[1], "B.Cu", W_PWR, n_gnd))
    parts.append(_seg(_shield_x, p1[1], _shield_x, _shield_y, "B.Cu", W_PWR, n_gnd))
    _PAD_NETS[("J1", "1")] = n_gnd

    # ── VBUS: land 11 -> land 2 ─────────────────────────────────────
    # Both wide VBUS lands are pinned between a peg hole on their outer
    # side and a 0.30 mm signal land on their inner side, so the escape
    # has to thread the diagonal gap between the two. The escape runs
    # perpendicular to the peg-to-corner line, which is the only
    # orientation in which anything fits at all — a purely vertical drop
    # out of land 11 is impossible, the peg keepout covers it entirely.
    #
    # R22 (2026-07-25): the gap is now solved instead of guessed, and the
    # corridor below it is widened to the Power High width.
    #
    # WIDTH OF THE GATE IS A HARD GEOMETRIC LIMIT, NOT A STYLE CHOICE.
    # The free span between the peg hole and the corner of the adjacent
    # land is fixed by the connector's own datasheet dimensions — both
    # features belong to J1, so nothing on the board can move to open it
    # up. Along the peg-centre-to-land-corner line the budget is
    #     |PQ| = 1.1183 mm
    #   - 0.325 mm  peg hole radius
    #   - 0.300 mm  NPTH-to-copper (validate_jlcpcb; stricter than the
    #               0.254 mm in the .kicad_dru, so the tighter one wins)
    #   - 0.200 mm  pad-to-track
    #   = 0.293 mm  widest trace that can physically pass
    # Confirmed independently by a maximin-clearance path search over an
    # exact B.Cu clearance field (0.2888 mm at 5 um resolution, pinch at
    # (77.795, 69.485) — i.e. exactly this gap). The same search puts the
    # alternative escape, upward into the board interior, at 0.170 mm,
    # and that route is topologically blocked further on anyway: every
    # one of lands 3..10 drops a B.Cu via/trace through the band above,
    # and F.Cu is spanned end to end by the BTN_B and USB_CC1 runs.
    # So 0.50 mm cannot be reached here by ANY routing; the Power High
    # class minimum is unsatisfiable at this gate.
    #
    # This used to say the two escapes were deliberately NOT allowlisted,
    # so that verify_net_class_widths would keep reporting them. That was
    # the wrong instrument. A gate held permanently red by a condition
    # nothing can satisfy does not preserve the warning — it teaches
    # everyone to skip the gate, and the next real neck arrives into an
    # audience that has stopped reading. The two escapes now carry
    # coordinate-pinned POWER_HIGH_ALLOWLIST rows with this geometry proof
    # and the IPC-2221 numbers below attached to them; the gate still
    # PRINTS them on every run, and because the width here is derived
    # rather than typed, any change to the footprint or the clearance
    # constants moves the coordinates, stops the rows matching, and turns
    # the gate red again.
    #
    # The width is therefore solved from the geometry rather than typed
    # in, so it always uses the whole available budget: if the footprint
    # or the clearance rules ever change, the escape widens by itself and
    # is capped at W_PWR_HIGH once the gap can take it.
    #
    # This is in any case a PARALLEL bond, not the supply path: land 2
    # keeps its 0.60 mm run to the IP5306. At 0.273 mm the gate carries
    # 0.93 A on its own (IPC-2221, external, 1 oz, 10 C rise) and the
    # link as a whole is ~9.7 mOhm, against ~20 mOhm for the two
    # connector contacts it brings online, so of the IP5306's 2.1 A peak
    # roughly 0.7 A takes this path — inside the gate's rating.
    _peg_x, _peg_y = USBC[0] - 2.89, USBC[1] - 1.305      # left peg hole
    _peg_r = 0.325
    _C_NPTH = 0.30        # NPTH to copper
    _C_PAD = 0.20         # pad to track
    _MARGIN = 0.01        # absorbs KiCad's 0.005 mm polygon chord error
    _l10 = _pad("J1", "10")
    _corner = (_l10[0] - 0.15, _l10[1] + 0.55)            # land 10 lower-left
    _dx, _dy = _corner[0] - _peg_x, _corner[1] - _peg_y
    _span = math.hypot(_dx, _dy)
    _free = _span - (_peg_r + _C_NPTH) - _C_PAD
    _esc_w = round(min(W_PWR_HIGH, _free - 2 * _MARGIN), 3)
    if _esc_w < W_SIG:
        raise RuntimeError(
            "J1 VBUS escape gate collapsed to %.3f mm (was 0.273 mm). "
            "The peg-to-land-10 span is now %.4f mm — check whether the "
            "J1 footprint or the clearance constants changed."
            % (_esc_w, _span))
    _ux, _uy = _dx / _span, _dy / _span                   # peg -> corner
    # Gate point: hole edge + NPTH clearance + half trace + margin, which
    # centres the trace in the free span.
    _gate_d = _peg_r + _C_NPTH + _esc_w / 2 + _MARGIN
    _gate = (_peg_x + _ux * _gate_d, _peg_y + _uy * _gate_d)
    _px, _py = -_uy, _ux                                  # perpendicular, downward
    _esc_in = (round(_gate[0] - 0.55 * _px, 3), round(_gate[1] - 0.55 * _py, 3))
    _esc_out = (round(_gate[0] + 0.85 * _px, 3), round(_gate[1] + 0.85 * _py, 3))
    # Cross-connector run, mid-way between the two shield rows.
    _vbus_link_y = 72.10
    _esc_in_r = (round(2 * USBC[0] - _esc_in[0], 3), _esc_in[1])
    _esc_out_r = (round(2 * USBC[0] - _esc_out[0], 3), _esc_out[1])
    # Start/finish on the land origins so the link has no free endpoints
    # (JLCDFM dead-end check). Both stubs stay wholly inside their land.
    # In-land stubs and the two diagonal escapes are necked to _esc_w
    # because they share the gate's budget.
    #
    # Everything past the gate is in open copper and carries the full
    # Power High width. It used to be W_PWR_LOW (0.30 mm) for no reason
    # other than matching the gate; measured against the clearance field
    # the two vertical legs take 1.045 mm and the cross-connector run
    # 0.850 mm before anything is violated, so W_PWR_HIGH (0.76 mm) fits
    # with 0.143 / 0.045 mm of margin. Widening it drops the link from
    # ~17.4 mOhm to ~9.7 mOhm, which is what actually decides how much of
    # the charging current the second VBUS land pair carries.
    parts.append(_seg(p11[0], p11[1], _esc_in[0], _esc_in[1],
                       "B.Cu", _esc_w, n_vbus))
    parts.append(_seg(p2[0], p2[1], _esc_in_r[0], _esc_in_r[1],
                       "B.Cu", _esc_w, n_vbus))
    parts.append(_seg(_esc_in[0], _esc_in[1], _esc_out[0], _esc_out[1],
                       "B.Cu", _esc_w, n_vbus))
    parts.append(_seg(_esc_out[0], _esc_out[1], _esc_out[0], _vbus_link_y,
                       "B.Cu", W_PWR_HIGH, n_vbus))
    parts.append(_seg(_esc_out[0], _vbus_link_y, _esc_out_r[0], _vbus_link_y,
                       "B.Cu", W_PWR_HIGH, n_vbus))
    parts.append(_seg(_esc_out_r[0], _vbus_link_y, _esc_out_r[0], _esc_out_r[1],
                       "B.Cu", W_PWR_HIGH, n_vbus))
    parts.append(_seg(_esc_out_r[0], _esc_out_r[1], _esc_in_r[0], _esc_in_r[1],
                       "B.Cu", _esc_w, n_vbus))
    _PAD_NETS[("J1", "11")] = n_vbus
    # Land 9 is SBU1, not VBUS. It was on the VBUS net until R21, which
    # is why DRC kept asking for a VBUS connection to it. SBU1/SBU2 are
    # unused by this design (no alternate mode, no analog audio adapter
    # accessory), so they stay deliberately unconnected — and must stay
    # off VBUS, since an audio adapter would drive them.

    # ── D+ / D- : land 6 <-> land 8, and land 7 <-> land 5 ──────────
    # The two shorts interleave in X (8, 7, 6, 5 left to right, linking
    # 8-6 and 7-5), so exactly one of them has to change layer. There is
    # no room to do that anywhere except directly below the lands: at
    # 0.5 mm pitch a 0.50 mm via on one land column leaves 0.175 mm to a
    # 0.15 mm trace on the neighbouring column, which is the project's
    # CLEARANCE_VIA_TRACE target exactly and 0.085 mm above the JLCPCB
    # minimum. Hence W_J1_BYPASS and VIA_MIN here rather than the usual
    # W_DATA / VIA_STD.
    #
    # D- takes the layer change because its two lands (7 and 5) are the
    # outer pair of the interleave, so its vias land on the outer columns
    # and only have to clear D+ on one side each.
    #
    # Stub length is ~2.6 mm of unterminated branch on each data line.
    # ESP32-S3's native USB is Full Speed (12 Mbit/s, ~5 ns edges): a
    # 2.6 mm stub is under 0.2% of a wavelength, so it is electrically
    # invisible. Same reasoning as the Zdiff note in the project memory.
    _dm_hop_y = 70.00   # free F.Cu band between BTN_B (68.00) and BTN_X (70.81)
    parts.append(_seg(p7[0], p7[1], p7[0], _dm_hop_y, "B.Cu", W_J1_BYPASS, n_dm))
    parts.append(_via_net(p7[0], _dm_hop_y, n_dm,
                          size=VIA_MIN, drill=VIA_MIN_DRILL))
    parts.append(_seg(p7[0], _dm_hop_y, p5[0], _dm_hop_y,
                       "F.Cu", W_J1_BYPASS, n_dm))
    parts.append(_via_net(p5[0], _dm_hop_y, n_dm,
                          size=VIA_MIN, drill=VIA_MIN_DRILL))
    parts.append(_seg(p5[0], _dm_hop_y, p5[0], p5[1], "B.Cu", W_J1_BYPASS, n_dm))
    _PAD_NETS[("J1", "5")] = n_dm

    # D+ stays on B.Cu, dropping past the D- vias (0.175 mm clear on each
    # side) into the empty band between the two shield rows.
    _dp_link_y = 71.40
    parts.append(_seg(p8[0], p8[1], p8[0], _dp_link_y, "B.Cu", W_J1_BYPASS, n_dp))
    parts.append(_seg(p8[0], _dp_link_y, p6[0], _dp_link_y,
                       "B.Cu", W_J1_BYPASS, n_dp))
    parts.append(_seg(p6[0], _dp_link_y, p6[0], p6[1], "B.Cu", W_J1_BYPASS, n_dp))
    _PAD_NETS[("J1", "8")] = n_dp

    return parts
