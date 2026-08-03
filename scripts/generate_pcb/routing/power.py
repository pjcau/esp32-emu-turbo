"""Split from routing.py 2026-07-26 — mechanical, AST-driven, proven by a
byte-identical regenerated .kicad_pcb. One domain per module; every helper
and every constant lives in _shared (original order, so import-time
execution is unchanged). See routing/__init__.py for the contract."""
from ._shared import (
    BOARD_H,
    BOARD_W,
    DIAG_VBUS_TAP_Y,
    NET_ID,
    P,
    VIA_MIN,
    VIA_MIN_DRILL,
    VIA_PWR,
    VIA_PWR_BIG_DRILL,
    VIA_PWR_DRILL,
    VIA_PWR_TIGHT,
    VIA_STD,
    VIA_STD_DRILL,
    W_PWR,
    W_PWR_HIGH,
    W_SIG,
    _PAD_NETS,
    _init_pads,
    _pad,
    _seg,
    _via_net,
)




# ── Routing functions ─────────────────────────────────────────────

def _buck_traces(bk_en, bk_gnd, bk_lx, bk_in, bk_fb):
    """U3 SY8089AAAC synchronous buck: +5V -> 3.327V, 2A continuous.

    Replaces the AMS1117-3.3 LDO. The LDO burned 1.7 V x I_load as heat
    (0.85 W at 500 mA) and its 22 uF tantalum output cap (C2) destroyed
    prototype #1 when it was assembled reversed — see
    website/docs/rework/incident-c2-reversed.md. C2 is deleted; the buck
    uses a low-ESR MLCC (C30) on the output, as a 1 MHz converter requires.

    Topology (datasheet AN_SY8089/A Rev 0.9A, Figure 1 typical application):

        +5V --[C1 22uF]--+-- IN (4) ---- LX (3) --[L2 2.2uH]--+-- +3V3
                         |                                     |
                        GND                              [C30 22uF]
                                                               |
                        FB (5) <--+-- R25 100k --+-------------+
                                  |              |
                                  |            [C29 22pF]  (across R25)
                                  +-- R26 22k --+
                                       |
                                      GND

        Vout = 0.6 * (1 + R25/R26) = 0.6 * (1 + 100k/22k) = 3.327 V
        (Vfb = 0.6 V, datasheet page 7 "Feedback resistor dividers")

    EN (pin 1) is tied to the +5V pour: the rail is only present when the
    IP5306 boost is running, so the buck follows it. EN abs-max is
    Vin + 0.6 V, so a hard tie to the input rail is within spec. The
    datasheet's 1 Mohm pull-down recommendation applies only when EN is
    driven from a high-impedance source, which is not the case here.

    Layout rules applied (datasheet page 8 "Layout Design"):
      1) GND pin gets a two-via cluster straight into the In1.Cu plane.
      2) C1 sits 0.95 mm south of the package; the IN -> C1 -> GND loop is
         closed through In1.Cu (via pair at (122.40, 53.50)/(122.40, 51.80)
         next to the GND pin and (122.60, 56.60) next to C1.2) rather than
         through a long B.Cu detour around the LX pad. Physical loop
         ~4 mm x 3 mm; the return runs directly underneath on the plane.
      3) LX copper is a single 3.10 mm x 0.76 mm B.Cu run plus the two
         pads — no vias, no plane, nothing else shares the node.
         0.76 mm at 1 oz carries ~2.1 A (10 C rise) which covers the 2 A
         continuous rating.
      4) FB is routed on F.Cu, which is separated from every switching
         node (all on B.Cu) by the In1.Cu GND plane AND the In2.Cu power
         plane. R25/R26/C29 sit in the y > 62 band so their +3V3 sense via
         lands on the continuous +3V3 plane, i.e. electrically on the far
         side of C30, not on the inductor node.

    IMPORTANT ZONE CONSTRAINT (this is what killed v1): every +5V feature
    of this block is at x < 123 and y < 62, i.e. inside the In2.Cu +5V
    pour; every +3V3 feature is outside it. See _power_zones().
    """
    parts = []
    n_5v = NET_ID["+5V"]
    n_3v3 = NET_ID["+3V3"]
    n_gnd = NET_ID["GND"]
    n_lx = NET_ID["BUCK_LX"]
    n_fb = NET_ID["BUCK_FB"]

    c1_p1 = _pad("C1", "1")     # (118.30, 56.60) +5V
    c1_p2 = _pad("C1", "2")     # (121.30, 56.60) GND
    l2_p2 = _pad("L2", "2")     # (124.20, 54.45) BUCK_LX
    l2_p1 = _pad("L2", "1")     # (127.80, 54.45) +3V3
    c30_p1 = _pad("C30", "1")   # (127.80, 57.40) +3V3
    c30_p2 = _pad("C30", "2")   # (127.80, 60.40) GND
    # Divider parts are at rot 180 → pad 1 is the WEST pad (see R25_POS).
    r25_3v3 = _pad("R25", "1")  # (117.05, 63.40) +3V3 sense
    r25_fb = _pad("R25", "2")   # (118.95, 63.40) BUCK_FB
    r26_fb = _pad("R26", "1")   # (120.15, 63.40) BUCK_FB
    r26_gnd = _pad("R26", "2")  # (122.05, 63.40) GND
    c29_3v3 = _pad("C29", "1")  # (117.05, 60.30) +3V3 sense
    c29_fb = _pad("C29", "2")   # (118.95, 60.30) BUCK_FB

    # ── +5V input: In2.Cu pour -> C1 -> U3 IN ────────────────────
    # Two 0.90 mm vias (0.35 mm drill) share the input current; one via is
    # ~1.5 A, the pair covers the 2 A worst case with margin.
    #   via A (118.30, 58.30) x[117.85,118.75] y[57.85,58.75]
    #   via B (119.60, 58.30) x[119.15,120.05] y[57.85,58.75]
    #   via-to-via gap  1.30 - 0.90                    = 0.40mm ✓
    #   C1 pad bottom edge 57.50 -> via top 57.85      = 0.35mm ✓
    #   C1.2 pad left edge 120.70 -> via B right 120.05 = 0.65mm ✓
    #   C29.1 pad top edge 59.65 -> via bottom 58.75    = 0.90mm ✓
    _v5_via_y = 58.30
    parts.append(_via_net(118.30, _v5_via_y, n_5v))
    parts.append(_via_net(119.60, _v5_via_y, n_5v))
    parts.append(_seg(118.30, _v5_via_y, 119.60, _v5_via_y,
                      "B.Cu", W_PWR_HIGH, n_5v))
    parts.append(_seg(c1_p1[0], c1_p1[1], c1_p1[0], _v5_via_y,
                      "B.Cu", W_PWR_HIGH, n_5v))
    # IN pad -> C1.1 (vertical inside the C1.1 pad column, then land on
    # the pad centre so the pad-net registrar tags C1.1 = +5V).
    parts.append(_seg(bk_in[0], bk_in[1], bk_in[0], c1_p1[1],
                      "B.Cu", W_PWR_HIGH, n_5v))
    parts.append(_seg(bk_in[0], c1_p1[1], c1_p1[0], c1_p1[1],
                      "B.Cu", W_PWR_HIGH, n_5v))

    # ── GND: input-loop return and regulator thermal path ────────
    # The GND pin (2) is boxed in by EN (north) and LX (south) on the east
    # column, so it can only exit east. Two vias take it straight down to
    # the In1.Cu plane; a third sits next to C1.2 so the C_IN return is
    # local.
    #   GND stub y[53.20,53.80] vs LX pad top 54.15  = 0.35mm ✓
    #                            vs EN pad bottom 52.85 = 0.35mm ✓
    #   via (122.40,53.50) x[122.10,122.70] vs L2.2 pad left 123.45 = 0.75mm ✓
    #   via (122.40,51.80) vs EN pad right 121.65    = 0.45mm ✓
    #   via (122.60,56.60) vs L2.2 pad corner (123.45,56.45): 0.56mm ✓
    #
    # AMPACITY (verify_power_via_ampacity): the buck's return current leaves
    # through this column and nowhere else — there is no B.Cu GND pour, so
    # these barrels ARE the path to In1.Cu. Two 0.20 mm barrels carry
    # 1.054 A against the 2 A the regulator returns. The column now runs
    # 0.35 mm barrels and reaches one via further south:
    #   (122.40,53.50) stays VIA_STD — a 0.80 OD ring here leaves only
    #     0.17 mm to the BUCK_LX trace at y[54.07,54.83], under the 0.175
    #     house clearance, so this one cannot grow;
    #   (122.40,51.80) -> 0.80/0.35, U3.1 pad corner gap 0.354mm ✓
    #   (122.40,50.60) -> 0.80/0.35, new; +5V via (121.10,51.20) copper
    #     gap 0.732mm ✓, via-to-via copper gap to (122.40,51.80) 0.40mm ✓
    # 0.527 + 0.791 + 0.791 = 2.109 A against 2.0 A returned.
    parts.append(_seg(bk_gnd[0], bk_gnd[1], 122.40, bk_gnd[1],
                      "B.Cu", W_PWR, n_gnd))
    parts.append(_via_net(122.40, bk_gnd[1], n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))
    parts.append(_seg(122.40, bk_gnd[1], 122.40, 51.80,
                      "B.Cu", W_PWR, n_gnd))
    parts.append(_via_net(122.40, 51.80, n_gnd,
                          size=VIA_PWR_TIGHT, drill=VIA_PWR_DRILL))
    parts.append(_seg(122.40, 51.80, 122.40, 50.60,
                      "B.Cu", W_PWR, n_gnd))
    parts.append(_via_net(122.40, 50.60, n_gnd,
                          size=VIA_PWR_TIGHT, drill=VIA_PWR_DRILL))
    parts.append(_seg(c1_p2[0], c1_p2[1], 122.60, c1_p2[1],
                      "B.Cu", W_PWR, n_gnd))
    parts.append(_via_net(122.60, c1_p2[1], n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))

    # ── EN: tied high to the +5V pour ────────────────────────────
    #   via (121.10, 51.20) OD 0.60, inside the +5V pour (x<123, y<62) ✓
    #   EN pad top 52.25 -> via bottom 51.50            = 0.75mm ✓
    #   BUCK_FB via (118.50,51.20) OD 0.50 right edge 118.75 = 2.05mm ✓
    parts.append(_seg(bk_en[0], bk_en[1], bk_en[0], 51.20,
                      "B.Cu", W_SIG, n_5v))
    parts.append(_via_net(bk_en[0], 51.20, n_5v,
                          size=VIA_STD, drill=VIA_STD_DRILL))

    # ── BUCK_LX: U3 pin 3 -> L2 pin 2 ────────────────────────────
    # Single straight run, no vias — the whole node is 3.10 x 0.76 mm of
    # B.Cu plus the two pads (datasheet rule 3: minimise LX copper).
    #   trace y[54.07,54.83] vs GND via (122.40,53.50) top 53.80 = 0.27mm ✓
    #   trace vs C1.2 pad top 55.70                              = 0.87mm ✓
    parts.append(_seg(bk_lx[0], bk_lx[1], l2_p2[0], l2_p2[1],
                      "B.Cu", W_PWR_HIGH, n_lx))

    # ── +3V3 output: L2 -> C30 -> In2.Cu +3V3 plane ──────────────
    #   vertical x[127.42,128.18] vs BTN_Y B.Cu x=129.24 (w 0.25,
    #     west edge 129.115)                                  = 0.935mm ✓
    parts.append(_seg(l2_p1[0], l2_p1[1], c30_p1[0], c30_p1[1],
                      "B.Cu", W_PWR_HIGH, n_3v3))
    # Two output vias, both EAST of the +5V pour boundary (x=123) so they
    # land on the continuous +3V3 plane. Sense/feed point is at C30, i.e.
    # after the output cap, not at the inductor node.
    #   trace y[57.02,57.78] vs L2 pad bottom 56.45          = 0.57mm ✓
    #   via (126.00,57.40) vs C30.1 pad left 126.90          = 0.45mm ✓
    #   via (124.60,57.40) vs L2.2 pad corner (124.95,56.45) = 0.56mm ✓
    #   via-to-via gap 1.40 - 0.90                           = 0.50mm ✓
    #
    # AMPACITY (verify_power_via_ampacity): every amp the buck delivers
    # crosses this pair — the whole rail lives on the In2.Cu +3V3 plane and
    # this is the only way onto it. Two 0.35 mm barrels are 1.582 A against
    # the 1.989 A the loads take, so a third hangs off a stub 1.20 mm south
    # of the run, where the nearest different-net copper is the C30 GND
    # return at y=60.40 (1.05 mm) and both siblings are 0.489 mm away.
    _v3_out_via_y2 = 58.60
    parts.append(_seg(c30_p1[0], c30_p1[1], 126.00, c30_p1[1],
                      "B.Cu", W_PWR_HIGH, n_3v3))
    # Split at 125.30 so the third via's stub starts on a shared endpoint
    # rather than T-ing into the middle of this run (verify_dangling_copper).
    parts.append(_seg(126.00, c30_p1[1], 125.30, c30_p1[1],
                      "B.Cu", W_PWR_HIGH, n_3v3))
    parts.append(_seg(125.30, c30_p1[1], 124.60, c30_p1[1],
                      "B.Cu", W_PWR_HIGH, n_3v3))
    parts.append(_via_net(126.00, c30_p1[1], n_3v3))
    parts.append(_via_net(124.60, c30_p1[1], n_3v3))
    parts.append(_seg(125.30, c30_p1[1], 125.30, _v3_out_via_y2,
                      "B.Cu", W_PWR_HIGH, n_3v3))
    parts.append(_via_net(125.30, _v3_out_via_y2, n_3v3))

    # ── C30 GND return: two vias to In1.Cu ───────────────────────
    #   via (126.30,60.40) right edge 126.60 vs C30.2 pad left 126.90 = 0.30mm ✓
    #   via-to-via gap 1.30 - 0.60                                    = 0.70mm ✓
    parts.append(_seg(c30_p2[0], c30_p2[1], 126.30, c30_p2[1],
                      "B.Cu", W_PWR, n_gnd))
    parts.append(_via_net(126.30, c30_p2[1], n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))
    parts.append(_seg(126.30, c30_p2[1], 125.00, c30_p2[1],
                      "B.Cu", W_PWR, n_gnd))
    parts.append(_via_net(125.00, c30_p2[1], n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))

    # ── BUCK_FB: U3 pin 5 -> divider, routed on F.Cu ─────────────
    # Datasheet rule 4: R25/R26 and the FB trace must not sit next to LX.
    # Every switching node on this board is on B.Cu; F.Cu is separated
    # from it by In1.Cu (GND) and In2.Cu (power), so an F.Cu run is the
    # quietest path available and is a microstrip over solid ground.
    #   B.Cu stub  (118.50, 52.55) -> (118.50, 51.20)
    #   via        (118.50, 51.20) OD 0.50
    #   F.Cu       -> (116.60, 51.20) -> (116.60, 61.85) -> (118.95, 61.85)
    #   via        (118.95, 61.85) OD 0.50, lands on the B.Cu FB column
    # Clearances on the F.Cu column x[116.475,116.725]:
    #   +5V via (115.25, 54.50) OD 0.90 right edge 115.70   = 0.775mm ✓
    #   GND via (115.05, 51.00) OD 0.60 right edge 115.35   = 1.125mm ✓
    #   +5V via (118.30, 58.30) OD 0.90 left edge 117.85    = 1.125mm ✓
    #   R16 / C1 / C29 pads are B.Cu — different layer ✓
    _fb_via_n = (bk_fb[0], 51.20)
    _fb_col_x = 116.60
    _fb_via_s = (r25_fb[0], 61.85)
    parts.append(_seg(bk_fb[0], bk_fb[1], _fb_via_n[0], _fb_via_n[1],
                      "B.Cu", W_SIG, n_fb))
    parts.append(_via_net(_fb_via_n[0], _fb_via_n[1], n_fb,
                          size=VIA_MIN, drill=VIA_MIN_DRILL))
    parts.append(_seg(_fb_via_n[0], _fb_via_n[1], _fb_col_x, _fb_via_n[1],
                      "F.Cu", W_SIG, n_fb))
    parts.append(_seg(_fb_col_x, _fb_via_n[1], _fb_col_x, _fb_via_s[1],
                      "F.Cu", W_SIG, n_fb))
    parts.append(_seg(_fb_col_x, _fb_via_s[1], _fb_via_s[0], _fb_via_s[1],
                      "F.Cu", W_SIG, n_fb))
    parts.append(_via_net(_fb_via_s[0], _fb_via_s[1], n_fb,
                          size=VIA_MIN, drill=VIA_MIN_DRILL))

    # ── Divider ──────────────────────────────────────────────────
    # FB column: C29 tap (118.95, 60.30) - via (118.95, 61.85) - R25 tap
    # (118.95, 63.40) - R26 tap (120.15, 63.40).
    parts.append(_seg(c29_fb[0], c29_fb[1], r25_fb[0], r25_fb[1],
                      "B.Cu", W_SIG, n_fb))
    parts.append(_seg(r25_fb[0], r25_fb[1], r26_fb[0], r26_fb[1],
                      "B.Cu", W_SIG, n_fb))
    # +3V3 sense column: C29 (117.05, 60.30) - R25 (117.05, 63.40), then
    # west to a via that taps the +3V3 plane. y=63.40 is SOUTH of the +5V
    # pour (which ends at y=62), so this via lands on +3V3 copper — this is
    # the whole reason the divider sits in the y>62 band.
    #   via (115.55, 63.40) OD 0.60 right edge 115.85
    #       vs R25 +3V3 pad left edge 116.55               = 0.70mm ✓
    parts.append(_seg(c29_3v3[0], c29_3v3[1], r25_3v3[0], r25_3v3[1],
                      "B.Cu", W_SIG, n_3v3))
    parts.append(_seg(r25_3v3[0], r25_3v3[1], 115.55, r25_3v3[1],
                      "B.Cu", W_SIG, n_3v3))
    parts.append(_via_net(115.55, r25_3v3[1], n_3v3,
                          size=VIA_STD, drill=VIA_STD_DRILL))
    # R26 lower leg -> GND via
    parts.append(_seg(r26_gnd[0], r26_gnd[1], 123.55, r26_gnd[1],
                      "B.Cu", W_SIG, n_gnd))
    parts.append(_via_net(123.55, r26_gnd[1], n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))

    return parts


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

    # U3 = SY8089AAAC synchronous buck (SOT-23-5), rot 180 on B.Cu.
    # Datasheet AN_SY8089/A p.2: 1=EN, 2=GND, 3=LX, 4=IN, 5=FB.
    # After rot 180 + B.Cu X-mirror the pads land at:
    #   IN  (4) west-south (bx-1.30, by+0.95)
    #   FB  (5) west-north (bx-1.30, by-0.95)
    #   LX  (3) east-south (bx+1.30, by+0.95)
    #   GND (2) east-mid   (bx+1.30, by)
    #   EN  (1) east-north (bx+1.30, by-0.95)
    bk_en = _pad("U3", "1")
    bk_gnd = _pad("U3", "2")
    bk_lx = _pad("U3", "3")
    bk_in = _pad("U3", "4")
    bk_fb = _pad("U3", "5")

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
    sw_com = _pad("SW16", "2")   # Common pin

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
    # R16 FIX (2026-04-12): after updating J1 pads to the JLCPCB reference
    # footprint, the wide signal pads (1, 2, 11, 12) grew from 0.35mm to
    # 0.55mm wide, moving J1.1 GND pad left edge from x=83.025 to x=82.925.
    # The old VBUS B.Cu vertical at x=82.45 with W_PWR_HIGH (0.76mm, half
    # 0.38) had right edge at 82.83 → new gap to GND 0.095mm (DANGER).
    # Fix: tuck the B.Cu vertical to x=82.40 (centered on pad 2) and
    # narrow to W_PWR (0.60mm, half 0.30). New constraints:
    #   Left edge  82.10 → gap to pad 3 (unnetted, 0.30 wide, right 81.90) = 0.20mm ✓
    #   Left edge  82.10 → gap to J3.1 (PTH 1.6 wide, right 81.80) = 0.30mm ✓
    #   Right edge 82.70 → gap to J1.1 (GND 0.55 wide, left 82.925)   = 0.225mm ✓
    # W_PWR=0.60 handles up to 2.3A at 1oz 1-layer ext. 10°C rise — above
    # the 2.1A VBUS peak charging current per IP5306 datasheet.
    vbus_fcu_start_x = usb_vbus[0]  # x=82.40, centered on pad 2
    ip_vbus_via_x = ip_vbus[0] - 2  # 108.0
    ip_vbus_via_y = ip_vbus[1] - 0.5  # DFM: 0.5mm above pad to clear U2[EP]

    # 1. (removed) There used to be a B.Cu stub from the USB VBUS pad LEFT
    #    to x=82.0 here. The R16 fix above tucked the vertical onto the pad
    #    centre (vbus_fcu_start_x = usb_vbus[0]), which turned that stub
    #    into a ZERO-LENGTH segment: start and end both (82.40, 68.775).
    #    KiCad keeps such a segment and gerbers carry it as a degenerate
    #    flash, so it reaches the fabricator. It is invisible to every check
    #    that measures a gap BETWEEN two things, which is why DRC stayed
    #    clean; it survived the whole life of v1 because the unconnected_zone
    #    baseline swallowed it. verify_power_net_integrity.py reported VBUS
    #    as two groups the moment that suppression was removed — the orphan
    #    has no extent, so it can never touch anything.
    #    The vertical in step 2 already starts on the pad centre, so the stub
    #    has nothing to do — deleted rather than given a token length.
    #    _seg() now raises on any zero-length segment, closing the class.
    # 2. B.Cu vertical UP from y=68.255 to y=61.0 (above all button F.Cu
    #    channels). R3-HIGH-4 FIX (2026-07-31): the connector side of the
    #    VBUS path is now net VBUS_IN — F1 (PTC 2A hold / 4A trip) sits in
    #    series before anything downstream sees the USB source.
    n_vbus_in = NET_ID["VBUS_IN"]
    parts.append(_seg(vbus_fcu_start_x, usb_vbus[1], vbus_fcu_start_x, vbus_fcu_y,
                       "B.Cu", W_PWR, n_vbus_in))
    # 3. B.Cu east from the riser bottom into F1 pad 1 (the old via to
    #    F.Cu at (82.4, 61.0) is gone — the connector side stays entirely
    #    on B.Cu now).
    f1_p1 = _pad("F1", "1")   # (83.6, 60.6)
    f1_p2 = _pad("F1", "2")   # (88.0, 60.6)
    if f1_p1 and f1_p2:
        parts.append(_seg(vbus_fcu_start_x, vbus_fcu_y, f1_p1[0], vbus_fcu_y,
                           "B.Cu", W_PWR, n_vbus_in))
        parts.append(_seg(f1_p1[0], vbus_fcu_y, f1_p1[0], f1_p1[1],
                           "B.Cu", W_PWR, n_vbus_in))
        # 3b. F1 pad 2 -> VBUS: B.Cu south stub, via cluster, F.Cu east to
        #     the U4-tap vertical's endpoint at (90.95, 59.3) — landing on
        #     the endpoint keeps the junction visible to
        #     verify_dangling_copper (same rule as the U4-tap split
        #     below).
        #
        #     R32 (2026-08-03): all three barrels used to sit on the
        #     y=59.3 row at x = f1_p2, 86.90, 85.80, and the first two had
        #     their HOLES inside / 0.025mm off F1 pad 2's copper — the
        #     JLCDFM "lead to hole distance 0mm" DANGER (solder drains
        #     down the barrel and starves the fuse joint). verify_via_in_pad
        #     is the permanent guard: every hole edge must clear every SMD
        #     pad by >= 0.15mm.
        #
        #     The barrels moved into F1's own inter-pad channel, which is
        #     2.50mm wide (pad 1 ends x=85.00, pad 2 starts x=87.50) and
        #     empty on both layers — the only copper crossing this pocket
        #     is BTN_L / BTN_SELECT F.Cu at y=57.5 / 58.0, both south of
        #     the cluster. That channel admits a via centre in
        #     x = [85.65, 87.175]: 0.45 (barrel radius) + 0.20 (clearance
        #     to the DIFFERENT-net VBUS_IN pad 1) on the west, 0.95 + 0.15
        #     + 0.175 (hole rule against pad 2) on the east. 1.525mm of
        #     window will not hold three barrels at the 1.10mm pitch that
        #     0.90mm annuli need, so the third one steps north instead of
        #     making a fourth column:
        #       (85.90, 59.30) — 0.45mm B.Cu clearance to F1.1's pad edge,
        #         hole 0.725mm clear of it.
        #       (87.00, 59.30) — hole 0.325mm clear of F1.2's pad edge.
        #       (85.90, 60.40) — 1.10mm north of the first, under the fuse
        #         body where both layers are free; 0.45mm clearance to
        #         F1.1, 1.60mm to F1.2.
        #     Nearest pair 1.10mm apart => 0.20mm copper, 0.75mm hole.
        #     AMPACITY (verify_power_via_ampacity): F1 is the source of
        #     this net and everything downstream — U2.1 and the U4 TVS —
        #     sits on F.Cu, so this cut carries the fuse's whole 2 A hold
        #     current. 3 x 0.35mm barrels = 3 x 0.791 = 2.373 A, unchanged
        #     by the move.
        _F1_VIA_ROW_Y = 59.3
        _F1_VIA_W_X = 85.90          # west barrel, on the row
        _F1_VIA_E_X = 87.00          # east barrel, on the row
        _F1_VIA_N = (85.90, 60.40)   # third barrel, stepped north
        parts.append(_seg(f1_p2[0], f1_p2[1], f1_p2[0], _F1_VIA_ROW_Y,
                           "B.Cu", W_PWR, n_vbus))
        parts.append(_seg(f1_p2[0], _F1_VIA_ROW_Y, _F1_VIA_E_X, _F1_VIA_ROW_Y,
                           "B.Cu", W_PWR, n_vbus))
        parts.append(_seg(_F1_VIA_E_X, _F1_VIA_ROW_Y, _F1_VIA_W_X, _F1_VIA_ROW_Y,
                           "B.Cu", W_PWR, n_vbus))
        parts.append(_seg(_F1_VIA_W_X, _F1_VIA_ROW_Y, *_F1_VIA_N,
                           "B.Cu", W_PWR, n_vbus))
        for _vx, _vy in ((_F1_VIA_W_X, _F1_VIA_ROW_Y),
                         (_F1_VIA_E_X, _F1_VIA_ROW_Y), _F1_VIA_N):
            parts.append(_via_net(_vx, _vy, n_vbus))
        # F.Cu mirrors the cluster and carries VBUS east to the U4 tap.
        parts.append(_seg(_F1_VIA_W_X, _F1_VIA_ROW_Y, *_F1_VIA_N,
                           "F.Cu", W_PWR_HIGH, n_vbus))
        parts.append(_seg(_F1_VIA_W_X, _F1_VIA_ROW_Y, _F1_VIA_E_X, _F1_VIA_ROW_Y,
                           "F.Cu", W_PWR_HIGH, n_vbus))
        parts.append(_seg(_F1_VIA_E_X, _F1_VIA_ROW_Y, 90.95, _F1_VIA_ROW_Y,
                           "F.Cu", W_PWR_HIGH, n_vbus))
    # 4. F.Cu horizontal to IP5306 approach column, starting at the U4
    #    tap. Historical note (still load-bearing): this run used to start
    #    at the (now deleted) (82.4, 61.0) via as one single 28.6mm F.Cu
    #    segment, with the U4 TVS VBUS stub (emitted in _usb_traces)
    #    ending mid-segment at (90.95, 61.0). The copper overlapped, so
    #    the board was fabricated connected — but a mid-segment T has no
    #    shared endpoint, so verify_dangling_copper read the TVS stub as
    #    copper ending in air. The tap is a real endpoint now; with F1 in
    #    series, VBUS reaches this run through the U4-tap vertical
    #    (90.95, 59.3 -> 61.0).
    _u4_vbus_tap_x = 90.95
    parts.append(_seg(_u4_vbus_tap_x, vbus_fcu_y, ip_vbus_via_x, vbus_fcu_y,
                       "F.Cu", W_PWR_HIGH, n_vbus))
    # 5. F.Cu vertical down to IP5306 pin level, SPLIT at the diagnostic
    #    VBUS tap. LED3's series resistor branches off this riser, and a
    #    mid-segment T has no shared endpoint — exactly the U4-tap bug
    #    described in note 4 above. Splitting here gives the junction
    #    degree 3 instead of leaving the branch at degree 1.
    parts.append(_seg(ip_vbus_via_x, vbus_fcu_y,
                       ip_vbus_via_x, DIAG_VBUS_TAP_Y,
                       "F.Cu", W_PWR_HIGH, n_vbus))
    parts.append(_seg(ip_vbus_via_x, DIAG_VBUS_TAP_Y,
                       ip_vbus_via_x, ip_vbus_via_y,
                       "F.Cu", W_PWR_HIGH, n_vbus))
    # 6. via to B.Cu at IP5306 approach
    #
    # AMPACITY (verify_power_via_ampacity): this is where the fuse's whole
    # 2 A hold current leaves F.Cu for U2.1, so one barrel (0.791 A) was
    # not enough. A second one sits 1.075 mm further south — the F.Cu
    # column runs on and the C17 B.Cu run at x=110.95 is already under it,
    # so the pair joins the same two islands. It cannot go further: LCD_CS
    # crosses on F.Cu at y=38.115 and a third ring would land on it.
    _ip_vbus_via2_y = ip_vbus_via_y - 1.075
    parts.append(_via_net(ip_vbus_via_x, ip_vbus_via_y, n_vbus))
    parts.append(_seg(ip_vbus_via_x, ip_vbus_via_y, ip_vbus_via_x, _ip_vbus_via2_y,
                       "F.Cu", W_PWR_HIGH, n_vbus))
    parts.append(_via_net(ip_vbus_via_x, _ip_vbus_via2_y, n_vbus))
    # 7. B.Cu stub: via -> IP5306 VBUS pad (horizontal then vertical)
    # R13-CU-CLR FIX (2026-04-11): narrow last-mile to U2.1 to W_PWR (0.60)
    # to pass U2.EP GND (top edge y=41.10) with ≥0.15mm clearance.
    # At W_PWR_HIGH (0.76) the seg top edge at 40.975 left only 0.125mm
    # gap to EP top (violation #4 in verify_copper_clearance).
    # W_PWR (0.60) → top edge 40.895, gap = 0.205mm ✓.
    # Path length ≤2.5mm, IP5306 VIN peaks ~2.1A; W_PWR rating ~2.3A/1oz ✓.
    parts.append(_seg(ip_vbus_via_x, ip_vbus_via_y, ip_vbus_via_x, ip_vbus[1],
                       "B.Cu", W_PWR, n_vbus))
    parts.append(_seg(ip_vbus_via_x, ip_vbus[1], ip_vbus[0], ip_vbus[1],
                       "B.Cu", W_PWR, n_vbus))

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
        # R9-HIGH-3 FIX (2026-04-11): REMOVED the IP5306 side GND stitching via.
        # Previously it was at (112.40, 45.30) with VIA_STD — DRC reported 0.145 mm
        # clearance to U2.4 pad (below 0.20 mm rule). All attempted relocations
        # either collided with U2.4, with the BAT+ corridor at y=46.135, or with
        # the VBUS F.Cu vertical at x=111.00 (the corridor 111.30..112.15 is
        # only 0.85 mm wide — not enough for a 0.60 mm via with 0.20 mm clearance
        # on each side).
        # The IP5306 EP has its own thermal via array immediately south of
        # the exposed pad (see _ip5306_therm_vias below) — that array is
        # the EP→In1.Cu GND plane connection and is sized for the return
        # current. The east-side stitching via was redundant.
        # U3 buck GND vias are emitted in the dedicated buck block below —
        # they need to be a tight pair right at the GND pin, not a single
        # generic stitching via.
        # ESP32 GND via handled separately below (needs small via for clearance)
        (jst_n[0], jst_n[1] - 3.5),         # JST GND (offset UP, away from USB-C and BAT+)
    ]
    for gvx, gvy in gnd_via_positions:
        parts.append(_via_net(gvx, gvy, n_gnd))
    # USB-C GND: route via ABOVE button channels to avoid blocking the
    # BTN_A-BTN_B corridor (needed for CC1 F.Cu routing at y=67.2).
    # Via at y=66.0: gap to BTN_A(y=66.8) = 66.8-0.125-(66.0+0.25)=0.425mm ✓
    #               gap to BTN_R(y=65.4) = 66.0-0.25-(65.4+0.10)=0.25mm ✓
    # R32: 66.2 -> 66.0. R2.2's 0805 land grew north to y=66.325 and left
    # the hole 0.025mm from it; 66.0 restores 0.225mm. The clearances the
    # note above quotes were computed for y=66.0 in the first place.
    usb_gnd_via_y = 66.0  # above BTN_A(66.8), clears CC1 F.Cu at y=67.4 and BTN_R via(76.20,65.40)
    parts.append(_via_net(usb_gnd[0], usb_gnd_via_y, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # B.Cu stubs from IC GND pads to vias
    parts.append(_seg(usb_gnd[0], usb_gnd[1], usb_gnd[0], usb_gnd_via_y,
                       "B.Cu", W_PWR, n_gnd))

    # ── USB-C extra pad net assignments (GND, VBUS, Shield) ────
    # R21 (2026-07-25): pads 1, 9 and 11 used to be given a net here and
    # then left to "connect through the zone fill". That does not work for
    # SMD pads: an SMD pad has no barrel, so it never touches In1.Cu or
    # In2.Cu, and KiCad DRC correctly reported all three as unconnected.
    # Pad 9 was additionally on the WRONG net — it is SBU1, not VBUS (see
    # the land map in footprints.usb_c_16p).
    # Real copper is now routed in _usb_c_reversibility_traces(); the net
    # assignments for 1, 9 and 11 live there with the traces that justify
    # them. Only the shield THT pads, which do have plated barrels into
    # the In1.Cu GND plane, are assigned here.
    #
    # Shield pads 13, 14 (front + rear, duplicate names) → GND net assignment.
    # THT pads have plated barrels connecting to In1.Cu GND zone automatically.
    # NOTE: USB shield tied directly to signal GND (no RC filter). Acceptable for
    # prototype; for v2 consider 1M||4.7nF between shield and GND to reduce EMI.
    # DFA FIX: renamed 13b/14b → 13/14 (duplicate names). _PAD_NETS keyed by
    # (ref, pad_name) so a single entry covers both front and rear pads with
    # the same name — net assignment applies to all pads sharing that name.
    _PAD_NETS[("J1", "13")] = n_gnd
    _PAD_NETS[("J1", "14")] = n_gnd

    # IP5306 GND: R9-HIGH-3 FIX (2026-04-11): REMOVED the east-side B.Cu stub
    # from EP to (112.40, 45.30). It previously led to a GND stitching via
    # that collided with U2.4 pad clearance. The EP is grounded via the three
    # thermal vias under the exposed pad (defined in _ip5306_therm_vias above)
    # and the In1.Cu GND plane zone fill.
    # EP pad-net registration is handled upstream by modifying the center
    # thermal via stub to start at the EP centre (see _ip5306_therm_vias).

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

    parts.extend(_buck_traces(bk_en, bk_gnd, bk_lx, bk_in, bk_fb))

    # JST GND pad to offset via (UP, away from USB-C and BAT+)
    parts.append(_seg(jst_n[0], jst_n[1], jst_n[0], jst_n[1] - 3.5,
                       "B.Cu", W_PWR, n_gnd))

    # ── IP5306 (U2) GND thermal vias: 2x2 array south of the EP pad ──
    # EP pad centre at ip_ep = (110.0, 42.5), 3.4 x 2.8mm, so the pad
    # occupies x=108.3..111.7, y=41.1..43.9. The array sits south of it,
    # in the only free pocket U2's pin field and its neighbours leave.
    #
    # AMPACITY (verify_power_via_ampacity): there is no B.Cu GND pour, so
    # this array is the ONLY path from the boost's return pad to In1.Cu.
    # Three 0.20 mm barrels are 1.581 A and the return carries the whole
    # battery current, 4.348 A. The array is now a 2x2 grid of 0.35 mm
    # barrels (3.164 A) which, with the buck's own column at 2.109 A,
    # brings the net's source cut to 5.273 A.
    #
    # The pocket it has to fit in is 2.0 mm tall and 2.0 mm wide, so the
    # grid is pitched at exactly 1.00 mm (0.20 mm of copper between rings)
    # and cannot hold a third row or column:
    #   south — BAT+ B.Cu corridor at y=46.100 (rings stop at 45.70, 0.25)
    #   east  — VBUS F.Cu vertical at x=111.00 (rings stop at 109.95, 0.67)
    #   west  — U2.5 pad ends at x=107.85 (rings start at 108.15, 0.30)
    #   north — the EP pad itself; the inner row's rings meet its bottom
    #           edge at y=43.90 on the SAME net, and the drills stay
    #           0.225 mm clear of it so the paste aperture is untouched.
    _ip5306_therm_vias = [
        (108.55, 44.30), (109.55, 44.30),   # inner row, along the EP edge
        (108.55, 45.30), (109.55, 45.30),   # outer row
    ]
    # Connect each column of thermal vias to the EP pad with a vertical
    # B.Cu stub that lands ON the EP pad centre. ONE rule for all of them.
    #
    # The previous split — centre via to ip_ep[1], the other two to
    # ip_ep[1] + 1.5 — stopped the side stubs at y = 44.0, and the EP
    # pad's bottom edge is y = 43.9 (centre 42.5, height 2.8). So both
    # side stubs ended 0.1mm OUTSIDE the pad: copper reaching nothing on
    # the layer it was drawn on, and no B.Cu thermal bond between those
    # two vias and the EP they exist to cool. The block's own comment
    # above ("Place inside EP pad bounds to avoid dead-end issues") is
    # the intent; +1.5 missed it by a tenth of a millimetre.
    # Caught by verify_dangling_copper.py.
    #
    # Shape matters as much as reach, and three gates each police a
    # different part of it:
    #   - stopping at (tvx, ip_ep[1]) is inside the pad, so
    #     verify_dangling_copper passes, but the JLCDFM dead-end rule in
    #     verify_dfm_v2 recognises a termination only at a registered pad
    #     position, a via, or another segment endpoint — the two side
    #     stubs read as dead ends at x = 108.5 / 109.3;
    #   - running each stub diagonally to ip_ep fixes that, but three
    #     diagonals meeting at one point make a 31 deg wedge, and the
    #     JLCDFM sharp-corner rule calls that an acid trap.
    # So: drop each via vertically onto the EP centre line, then chain
    # the drops together along that line into the pad centre. Every
    # corner is 90 deg, every endpoint is shared with the next segment,
    # and no two segments overlap.
    #
    # With two vias per column the drop is emitted per COLUMN, not per
    # via: outer via -> inner via -> EP centre line. Two stubs on the same
    # x would otherwise be drawn on top of each other, which is the
    # overlapping copper the rule above exists to prevent.
    _therm_cols = {}
    for tvx, tvy in _ip5306_therm_vias:
        parts.append(_via_net(tvx, tvy, n_gnd,
                              size=VIA_PWR_TIGHT, drill=VIA_PWR_DRILL))
        _therm_cols.setdefault(tvx, []).append(tvy)
    for tvx in sorted(_therm_cols):
        for _ya, _yb in zip(sorted(_therm_cols[tvx], reverse=True),
                            sorted(_therm_cols[tvx], reverse=True)[1:]):
            parts.append(_seg(tvx, _ya, tvx, _yb, "B.Cu", W_PWR, n_gnd))
        parts.append(_seg(tvx, min(_therm_cols[tvx]), tvx, ip_ep[1],
                          "B.Cu", W_PWR, n_gnd))
    _therm_xs = sorted(set(_therm_cols) | {ip_ep[0]})
    for _xa, _xb in zip(_therm_xs, _therm_xs[1:]):
        parts.append(_seg(_xa, ip_ep[1], _xb, ip_ep[1], "B.Cu", W_PWR, n_gnd))

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
        # R32 (2026-08-03): via-in-pad is exactly the JLCDFM "lead to hole
        # distance 0mm" DANGER — solder wicks down the barrel and starves
        # the card socket's VDD joint. The barrel steps 1.176mm SOUTH
        # instead, past the pad's bottom edge (62.374), on a stub that
        # threads the only free lane: SD_MOSI's post-slot column at
        # x=141.50 is absent between y=60.0 and 63.5 (it jogs west to
        # 139.41 there), so x=141.06 is clear. Hole clearance 0.426mm to
        # the pad, copper 0.200mm to SD_MOSI's y=63.5 jog.
        _sd_vdd_via_y = sd_vdd[1] + 1.176   # 62.90
        parts.append(_seg(sd_vdd[0], sd_vdd[1], sd_vdd[0], _sd_vdd_via_y,
                          "B.Cu", W_SIG, n_3v3))
        parts.append(_via_net(sd_vdd[0], _sd_vdd_via_y, n_3v3, size=VIA_STD, drill=VIA_STD_DRILL))

    if sd_vss:
        # GND to SD VSS (pin 6): via-in-pad to reach In1.Cu GND zone.
        # DFM: BTN_B trace at x=142.80 is 0.46mm from pin 6 at x=143.26.
        # Any B.Cu stub would collide. Via-in-pad avoids routing entirely.
        # 0.46mm via fits within the 0.6mm x 1.3mm pad.
        # R32: same via-in-pad finding as pin 4 above. The barrel steps
        # SOUTH to y=62.90, keeping 0.426mm of hole clearance to the pad
        # and 0.200mm of copper to BTN_B's B.Cu column at x=142.71.
        _sd_vss_via_y = sd_vss[1] + 1.176   # 62.90
        parts.append(_seg(sd_vss[0], sd_vss[1], sd_vss[0], _sd_vss_via_y,
                          "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(sd_vss[0], _sd_vss_via_y, n_gnd, size=VIA_MIN, drill=VIA_MIN_DRILL))

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
    #
    # AMPACITY (verify_power_via_ampacity): VOUT reaches every +5V consumer
    # through the In2.Cu pour, so this via was the whole rail's only layer
    # transition — 0.791 A against the 2.150 A the loads take. Two more
    # barrels flank it, each on its own short B.Cu stub so no two vias
    # crowd the same corridor:
    #   (105.60, 40.595) — west of the VOUT pad, under U2's body. Nearest
    #     different-net copper is the LX run at y=41.865 (0.44 mm) and the
    #     LX column at x=104.40 (0.37 mm); MH(105,37.5) is 1.40 mm away.
    #   (107.50, 37.90)  — south of C27.2 on the existing VOUT column.
    #     LCD_DC B.Cu at x=108.27 is 0.22 mm away, its via 0.606 mm.
    # Both land inside the In2.Cu pour, which is the copper the rail
    # actually distributes on. 3 x 0.791 = 2.373 A.
    #
    # SW16 RESPIN: these three barrels now feed the +5V_VOUT sub-island,
    # not +5V. The boost output no longer reaches the loads through the
    # plane — it reaches Q2's source, and Q2's drain feeds the +5V plane.
    # Nothing about the geometry changed, only the net, because the
    # ampacity argument above is about the barrels and is unaffected by
    # which of the two 5 V rails they belong to.
    n_5v_vout = NET_ID["+5V_VOUT"]
    parts.append(_seg(ip_vout[0], ip_vout[1], ip_vout[0] + 0.5, ip_vout[1],
                       "B.Cu", W_PWR, n_5v_vout))
    parts.append(_seg(ip_vout[0] + 0.5, ip_vout[1], ip_vout[0] + 0.5, ip_vout[1] - 1.5,
                       "B.Cu", W_PWR, n_5v_vout))
    # R32 (2026-08-03): this barrel used to sit at (107.50, 39.095),
    # inside C27.2's pad after the 0805 land grew to the JLC reference.
    # It cannot step in y — the sibling barrel is 1.195mm south and U2.8's
    # pad 1.5mm north — so it steps WEST along C27.2's own y, off the end
    # of the pad: 0.200mm of hole clearance to C27.2's west edge
    # (106.475), 1.83mm to the nearest different-net copper, and still
    # inside the In2.Cu island. (The island is +5V_VOUT since the SW16
    # respin; the geometry argument is unchanged, C27 moved net with it.)
    _vout_via_c = (106.10, ip_vout[1] - 1.5)   # (106.10, 39.095)
    parts.append(_seg(ip_vout[0] + 0.5, ip_vout[1] - 1.5, _vout_via_c[0], _vout_via_c[1],
                       "B.Cu", W_PWR, n_5v_vout))
    parts.append(_via_net(_vout_via_c[0], _vout_via_c[1], n_5v_vout))
    _vout_via_w = (105.60, ip_vout[1])          # (105.60, 40.595)
    _vout_via_s = (ip_vout[0] + 0.5, 37.90)     # (107.50, 37.90)
    parts.append(_seg(ip_vout[0], ip_vout[1], _vout_via_w[0], _vout_via_w[1],
                       "B.Cu", W_PWR, n_5v_vout))
    parts.append(_via_net(_vout_via_w[0], _vout_via_w[1], n_5v_vout))
    parts.append(_seg(_vout_via_s[0], ip_vout[1] - 1.5, _vout_via_s[0], _vout_via_s[1],
                       "B.Cu", W_PWR, n_5v_vout))
    parts.append(_via_net(_vout_via_s[0], _vout_via_s[1], n_5v_vout))
    # U3 buck input: C1 (C_IN) taps the In2.Cu +5V pour through its own via
    # pair; see _buck_traces(). No dedicated VIN via here any more.

    # ── LX: IP5306 SW (pin 7) -> L1 inductor ────────────────
    # Route from SW pin down to L1 pin 2 (closer pin)
    # DFM: SW pin at x=107, BAT pin also at x=107 — route LX LEFT 2mm first.
    # DFM FIX: was -1.0 (x=106). LX vert at x=106 crossed BAT+ horiz at y=43.13
    # (107→105.5). Also KEY horiz at y=44.41 spans x=107..114.05; x=106 is inside.
    # Fix: lx_col_x = ip_sw[0] - 2.0 = 105 (left of both BAT+ end 105.5 and KEY 107).
    #
    # LX column clearance analysis.
    #
    # R27-MED-1 (2026-07-26): the whole node now runs at W_PWR_HIGH. It used
    # to be 0.60 (W_PWR) on five of its seven segments, justified by the note
    # that replaced this one: "At 0.60mm / 1oz Cu: ~1.4A capacity (10°C rise),
    # adequate for pulsed LX". That sentence contradicted W_PWR_HIGH's own
    # definition three lines up — ">=2.1A, 1oz Cu, 10°C rise" — and the
    # contradiction survived because verify_net_class_widths floors Power High
    # at 0.50mm, so neither number was ever compared to the copper.
    #
    # The constraint it cited was also stale. It predates R9-MED-4, which
    # deleted R19/C20 and freed this corridor, and it measured the BAT+ via at
    # (105.5,46.1) against the x=104.55 column — but the jog moved to x=103.00
    # for exactly that span (y 44.5..51.5), so that via no longer bounds LX at
    # all.
    #
    # Solved rather than eyeballed: for each segment, grow the trace until the
    # house clearance (0.175mm to any different-net copper on the same layer)
    # breaks. Binary search over the merged obstacle union, per layer:
    #
    #   (104.55,41.87)->(104.55,44.50)   max 0.79   <- the binding one
    #   (104.55,44.50)->(103.00,44.50)   max 1.19
    #   (103.00,44.50)->(103.00,51.50)   max 1.19   (the freed corridor)
    #   (103.00,51.50)->(104.55,51.50)   max 1.19
    #   (104.55,51.50)->(104.55,52.50)   max 1.19
    #
    # That search used the 0.175mm house clearance, which is NOT the rule for
    # this pair: verify_dfm_v2's "LX vs BAT+ Trace Spacing Test" demands
    # 0.25mm between these two verticals specifically. Only the first segment
    # is affected — BAT+ runs x=105.50, y 43.13..46.13, and of the two LX
    # verticals at this column only y 41.87..44.50 overlaps that span.
    #
    # At the old x=104.55 the 0.25mm rule caps LX at
    #   0.95 (centre gap) - 0.38 (BAT+ half) - 0.25 = 0.32 half-width = 0.64mm
    # so the column is moved 0.15mm further left instead of narrowing one
    # segment. The corridor to its left is the one R9-MED-4 freed, and the
    # binary search above shows >=0.46mm of slack there at 0.76mm wide, so
    # nothing else moves:
    #   centre gap 1.10 - 0.38 - 0.38 = 0.34mm >= 0.25mm  ✓
    #
    # At 2.1A the IPC-2221 rise goes from ~18°C (0.60) to ~12°C (0.76), and
    # the switch-node loop area drops with it.
    lx_col_x = ip_sw[0] - 2.60   # x=104.40 (was 104.55; see the 0.25mm rule above)
    parts.append(_seg(ip_sw[0], ip_sw[1], lx_col_x, ip_sw[1],
                       "B.Cu", W_PWR_HIGH, n_lx))
    # Legacy jog at x=103.00 (preserved).
    # R9-MED-4 (2026-04-11): R19 (was at 103.95, 46.0) and C20 (was at
    # 103.95, 50.0) were deleted along with the dead BTN_MENU net. The
    # jog originally dodged their pads; now there is full ~3 mm clearance
    # in that corridor but the jog is preserved because LX is already
    # DFM-clean on these coordinates and a straight run would overlap
    # the C3/C4 passive row at y=42. Changing the jog would force
    # cascade re-verification with no electrical benefit.
    _lx_jog_x = 103.00   # between ex-R19 footprint and left free corridor
    _lx_jog_y_bot = 44.5  # below ex-R19 placement row
    _lx_jog_y_top = 51.5  # above ex-C20 placement row
    parts.append(_seg(lx_col_x, ip_sw[1], lx_col_x, _lx_jog_y_bot,
                       "B.Cu", W_PWR_HIGH, n_lx))   # max 0.79 — the binding segment
    parts.append(_seg(lx_col_x, _lx_jog_y_bot, _lx_jog_x, _lx_jog_y_bot,
                       "B.Cu", W_PWR_HIGH, n_lx))
    parts.append(_seg(_lx_jog_x, _lx_jog_y_bot, _lx_jog_x, _lx_jog_y_top,
                       "B.Cu", W_PWR_HIGH, n_lx))
    parts.append(_seg(_lx_jog_x, _lx_jog_y_top, lx_col_x, _lx_jog_y_top,
                       "B.Cu", W_PWR_HIGH, n_lx))
    parts.append(_seg(lx_col_x, _lx_jog_y_top, lx_col_x, l1_2[1],
                       "B.Cu", W_PWR_HIGH, n_lx))
    parts.append(_seg(lx_col_x, l1_2[1], l1_2[0], l1_2[1],
                       "B.Cu", W_PWR_HIGH, n_lx))

    # ── BAT+ side of L1: L1 pin 1 to BAT+ network ─────────────
    # R6 FIX (2026-04-10): the previous version created a B.Cu stub
    # (111.7,52.5)→(111.7,49.5)→(112.4,49.5)→dangling via hoping to be
    # picked up by a "BAT+ zone fill". But _power_zones() never created
    # a BAT+ pour — L1.1 was electrically isolated from the rest of the
    # BAT+ network since v3.1, leaving the boost converter unable to
    # draw current from the battery. Board only booted on USB-C.
    # (see hardware-audit-bugs.md R5-CRIT-1)
    #
    # Fix: route L1.1 → dogleg east around the IP5306_KEY vertical at
    # x=114.05 → B.Cu horizontal at y=46.135 threading the narrow
    # corridor between the Fix1a GND trace (y=45.3, hw 0.3, bottom
    # edge 45.6) and the IP5306_KEY trace (y=46.61, hw 0.125, top
    # edge 46.485). Usable y band 45.6..46.485 = 0.885mm.
    # New BAT+ hz at y=46.135, w=0.3mm (hw 0.15):
    #   top edge 45.985, gap to GND bottom 0.385mm ✓
    #   bottom edge 46.285, gap to KEY top 0.2mm ✓
    W_BAT_CORRIDOR = 0.3  # must be ≤ 0.4mm to fit the 0.885mm corridor
    CORRIDOR_Y = 46.10    # y=46.10 gives ≥0.1mm annular ring gap to KEY hz at 46.61
    #
    # Route plan (R9-HIGH-2 FIX 2026-04-11: bridge y shifted from 48.00
    # to 47.80. The old (114.65, 48.00) BAT+ via sat 0.10 mm from C18.2 GND
    # pad at (115.05, 49.00) — below the 0.20 mm pad-to-via rule. Shifting
    # the bridge 0.20 mm north gives dy=1.20 → edge gap 1.20-0.23-0.65=0.32 mm ✓.
    # KEY vert at x=114.05 still clears at y=47.80: KEY spans y=44.41..46.61,
    # so y=47.80 is 1.19 mm south of KEY → safe.):
    #   L1.1 (111.7,52.5) → (111.7,47.8) B.Cu vertical
    #   (111.7,47.8) → (113.45,47.8) B.Cu — clear of KEY vert (gap ≥ 0.225mm)
    #   F.Cu bridge (113.45,47.8) → (114.65,47.8) over KEY vertical at x=114.05
    #   (114.65,47.8) → (114.65,46.135) B.Cu — back on main corridor layer
    #
    #   Main corridor: the BAT+ B.Cu horizontal at y=46.135 cannot run from
    #   x=105.5 directly because it would cross the left KEY vertical at x=107
    #   (KEY left vert: (107, 46.61) → (107, 44.41) blocks y=46.135 on B.Cu).
    #   Solution: extend the existing F.Cu BAT+ horizontal from (105.5, 46.135)
    #   east to (107.8, 46.135), then via to B.Cu clear of the KEY vertical.
    #
    #   (107.8, 46.135) F.Cu→B.Cu via → B.Cu (107.8,46.135) → (116.95,46.135)
    #     Clearances: KEY hz top 46.485, BAT+ bottom 46.285 (gap 0.2 ✓);
    #                 GND Fix1a hz top 45.6, BAT+ top 45.985 (gap 0.385 ✓);
    #                 GND thermal via (109.3, 44.5) — below BAT+, gap ~0.635 ✓.
    #
    #   C18.1 picks up via its own stub (extended to 46.135 in _passive_traces).
    #
    # AMPACITY (2026-08-01): the dogleg described above is GONE. It was
    # L1.1's only supply and it delivered that supply through three
    # 0.20 mm barrels in series — the corridor entry at (107.80, 46.10)
    # and the two ends of the F.Cu bridge — 0.527 A each against the
    # 4.348 A the cell can push into the boost inductor. None of the
    # three can grow: the corridor is 0.78 mm tall between the U2.EP
    # thermal via rings and the IP5306_KEY horizontal, and the bridge's
    # west landing is capped at 0.60 OD by the KEY vertical at x=114.05.
    #
    # L1.1 is now fed from the pocket SOUTH of the KEY horizontal on
    # 0.76 mm of B.Cu with no barrel on the last leg at all — see
    # _BAT_BAND2_* at the end of this function. Once that exists the
    # dogleg carries a negligible share of the current, so keeping it
    # would only preserve four undersized (0.30 mm) segments, two more
    # sub-0.6 A barrels and their POWER_HIGH_ALLOWLIST waivers.
    #
    # What it cost: C18.1 now reaches U2.6 through the single corridor
    # barrel instead of two. C18 is a BULK cap 11.55 mm from the BAT pin
    # whose path is dominated by ~10 mm of 0.30 mm corridor (~15 mOhm);
    # the second barrel was worth ~0.25 mOhm of that. It is classified
    # "not a DC load" by verify_power_via_ampacity for the same reason.
    _L1_FEED_Y = 49.90  # where the fat B.Cu feed meets L1.1's column
    parts.append(_seg(l1_1[0], l1_1[1], l1_1[0], _L1_FEED_Y,
                       "B.Cu", W_PWR_HIGH, n_bat))      # L1.1 → the fat feed

    # Main corridor: F.Cu bridge east from (105.5, 46.135) past KEY left vertical
    # (x=107) to (107.8, CORRIDOR_Y=46.10), then via to B.Cu for the eastward run.
    # Bridge F.Cu from existing (105.5, 46.135) via to new y=46.10. Short 0.035mm
    # vertical stub makes the F.Cu horizontal land correctly on the new corridor.
    parts.append(_seg(105.5, 46.135, 105.5, CORRIDOR_Y,
                       "F.Cu", W_BAT_CORRIDOR, n_bat))
    parts.append(_seg(105.5, CORRIDOR_Y, 107.8, CORRIDOR_Y,
                       "F.Cu", W_BAT_CORRIDOR, n_bat))  # F.Cu bridge over KEY left vert
    # R12 JLCDFM fix: shrink BAT+ corridor via from 0.50mm → 0.46mm.
    # IP5306_KEY horizontal at y=46.61 (w=0.25, top edge 46.485) sits
    # 0.51mm above this via center. With VIA_MIN (r=0.25) the edge gap
    # was only 0.135 mm (JLCDFM flagged). With 0.46mm via (r=0.23) the
    # gap becomes 0.155 mm — safely above 0.15 mm JLCPCB minimum.
    parts.append(_via_net(107.8, CORRIDOR_Y, n_bat, size=0.46, drill=0.20))
    # One run, not two: the old split at x=114.65 existed only so the L1.1
    # dogleg could land on a shared endpoint, and that dogleg is gone.
    parts.append(_seg(107.8, CORRIDOR_Y, 116.95, CORRIDOR_Y,
                       "B.Cu", W_BAT_CORRIDOR, n_bat))  # corridor → C18.1 stub

    # ── KEY: IP5306 pin 5 -> C33 wake cap (SW16 respin) ─────────────
    # This copper is R16's, verbatim. R16 was a 100k pull-up from KEY to
    # +5V; it is DELETED (see hardware/datasheet_specs.py for the full
    # argument — in one sentence, on the new LOAD-side +5V it inverts into
    # a 100k pull-DOWN whenever the switch is OFF and holds KEY asserted).
    # C33, the 1uF wake cap, takes over the same footprint site, so the KEY
    # leg keeps R16's proven Z-route and the far leg keeps its via — which
    # now lands on the PWR_SW F.Cu corridor instead of tapping the +5V pour.
    #
    # DFM v2: KEY pin at (107, 44.405), pad 4 at (113, 44.405). Direct horizontal crosses pad 4.
    # Route with Z-shape: C33→down to safe Y, horizontal to KEY X, vertical to KEY pin.
    c33_p1 = _pad("C33", "1")   # PWR_SW side  (115.95, 52.5)
    c33_p2 = _pad("C33", "2")   # IP5306_KEY side (114.05, 52.5)
    n_pwr_sw = NET_ID["PWR_SW"]
    if c33_p2 and ip_key:
        # C33 pin 2 -> IP5306 KEY (pin 5) via B.Cu Z-route (avoid pad 4 at y=44.405)
        # DFM: was +1.0 (y=45.405) — crossed GND vertical at x=112.4 (y=43.5-45.5).
        # +2.2 gives y≈46.6, above GND vert top (45.5+0.25=45.75).
        key_safe_y = ip_key[1] + 2.2
        parts.append(_seg(c33_p2[0], c33_p2[1], c33_p2[0], key_safe_y,
                           "B.Cu", W_SIG, n_key))
        parts.append(_seg(c33_p2[0], key_safe_y, ip_key[0], key_safe_y,
                           "B.Cu", W_SIG, n_key))
        parts.append(_seg(ip_key[0], key_safe_y, ip_key[0], ip_key[1],
                           "B.Cu", W_SIG, n_key))
    if c33_p1:
        # C33 pin 1 -> PWR_SW via, the east end of the F.Cu corridor that
        # carries the switch node across the board (see _pwr_switch_traces).
        # Position is R16's, and the clearance proof is R16's:
        # via x=114.95 was too close to the west pad (gap=0.10mm); at
        # x=115.25 the gap to the west pad's right edge (114.55) is
        # 115.25-0.30-114.55 = 0.40mm ✓, and to C18 pad2 (117.05-0.50=116.55)
        # it is 116.55-115.25-0.45 = 0.85mm ✓.
        _c33_col_x = c33_p1[0] - 0.70  # 115.25 — clears C33[2] and C18
        parts.append(_seg(c33_p1[0], c33_p1[1], _c33_col_x, c33_p1[1],
                           "B.Cu", W_SIG, n_pwr_sw))
        parts.append(_seg(_c33_col_x, c33_p1[1], _c33_col_x, 55.60,
                           "B.Cu", W_SIG, n_pwr_sw))

    # ── +3V3 rail source ──────────────────────────────────────────
    # The +3V3 In2.Cu plane is fed by the buck output via pair placed on the
    # C30 (C_OUT) node in _buck_traces(): (126.00, 57.40) and (124.60, 57.40),
    # both east of the +5V pour boundary at x=123 so they land on the
    # continuous +3V3 plane. Nothing else drives +3V3.
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
        # R32 (2026-08-03): the barrel used to sit ON pin 2's pad at
        # (88.75, 23.70) — same net, so no short, but JLCDFM counts it as
        # "lead to hole distance 0mm": solder drains down the hole and
        # starves the module's +3V3 joint. The module's castellated pads
        # are stacked at 1.27mm pitch (pin 1 at 22.24, pin 3 at 24.78),
        # so there is no room to step along y; the barrel goes EAST
        # instead, off the end of the 1.5mm-wide pad.
        #   (89.90, 23.51): 0.300mm of hole clearance to pin 2's east
        #   edge (89.50), 0.682mm of copper to pins 1 and 3, 1.07mm to
        #   the GND barrel at (91.50, 23.45).
        _3v3_via_x = esp_3v3[0] + 1.15   # 89.90
        parts.append(_seg(esp_3v3[0], esp_3v3[1], _3v3_via_x, esp_3v3[1],
                           "B.Cu", W_PWR, n_3v3))
        parts.append(_via_net(_3v3_via_x, esp_3v3[1], n_3v3,
                              size=_V3_VIA_SIZE, drill=VIA_MIN_DRILL))

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
    #
    # AMPACITY (verify_power_via_ampacity): U2.6 is the IP5306's battery
    # pin — the entire 4.348 A crosses from the F.Cu corridor onto this
    # B.Cu column, and it used to do so through this one barrel (0.791 A).
    # The transition is now a 2 x 2 field in the pocket between the LX
    # column at x=104.40/103.00 and the IP5306_KEY column at x=107.00,
    # 1.075 mm south of the corridor where the B.Cu is otherwise empty:
    #   x = 104.30 / 105.50   ring gap to the LX column 0.47mm ✓
    #   y = 46.135 / 47.210   ring gap to LX horizontal y=44.50 0.875mm ✓,
    #                         to the +5V F.Cu run at y=48.85 0.88mm ✓
    # Drill 0.45 (0.949 A a barrel) rather than 0.35: four 0.35 barrels
    # come to 4.482 A against 4.348 A required, and a 3% margin on the
    # battery path is not a margin.
    _bat_stitch_y2 = 47.210
    _bat_stitch_x2 = 104.300
    parts.append(_seg(bat_col_x, bat_via_y, bat_col_x, _bat_stitch_y2,
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(bat_col_x, bat_via_y, bat_col_x, _bat_stitch_y2,
                       "F.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(bat_col_x, bat_via_y, _bat_stitch_x2, bat_via_y,
                       "B.Cu", W_PWR_HIGH, n_bat))
    for _layer in ("F.Cu", "B.Cu"):
        parts.append(_seg(bat_col_x, _bat_stitch_y2, _bat_stitch_x2, _bat_stitch_y2,
                           _layer, W_PWR_HIGH, n_bat))
        parts.append(_seg(_bat_stitch_x2, _bat_stitch_y2, _bat_stitch_x2, bat_via_y,
                           _layer, W_PWR_HIGH, n_bat))
    for _sx in (bat_col_x, _bat_stitch_x2):
        for _sy in (bat_via_y, _bat_stitch_y2):
            parts.append(_via_net(_sx, _sy, n_bat,
                                  size=VIA_PWR, drill=VIA_PWR_BIG_DRILL))
    #
    # AMPACITY (verify_power_via_ampacity) — L1.1, the IP5306's boost
    # inductor, is the second consumer that carries the whole 4.348 A.
    # It used to hang off THREE 0.20 mm barrels in series: the corridor
    # entry at (107.80, 46.10) — 0.46 OD, 0.527 A — and the two ends of
    # the F.Cu bridge that hops the IP5306_KEY vertical at x=114.05.
    #
    # None of them can grow. The corridor is 0.78 mm tall, boxed between
    # the U2.EP thermal vias (ring bottom 45.70) and the IP5306_KEY
    # horizontal (top edge 46.48), which admits a 0.43 mm ring at best;
    # the bridge's west landing is capped at 0.60 OD by that same KEY
    # vertical. The corridor is simply the wrong place to carry a
    # battery: it is the narrowest channel on this half of the board.
    #
    # The pocket SOUTH of the KEY horizontal is the opposite — x
    # 106.0..110.3, y 47.2..50.3 is empty on BOTH outer layers:
    #   +5V's F.Cu run ends at x=105.88 (cap) with its plane via at
    #     (105.50, 48.85)
    #   VBUS' F.Cu wall starts at x=110.62 and is the reason nothing can
    #     reach L1.1 from the west on F.Cu — hence the B.Cu-only feed
    #   L1.2's pad starts at y=50.80, KEY's horizontal ends at y=46.73
    # So BAT+ takes a second F.Cu/B.Cu stitching band there and then
    # reaches L1.1 on 0.76 mm of uninterrupted B.Cu — no barrel at all
    # on the last leg, which is what actually removes the bottleneck.
    #
    #   band  y=47.55, x = 106.60 / 107.70 / 108.80 / 109.90
    #         0.90 OD / 0.45 drill -> 4 x 0.949 = 3.796 A, in PARALLEL
    #         with the U2.6 field above -> 7.592 A onto L1.1's island,
    #         so the binding cut moves back to the 5.114 A west bank
    #   feed  (109.90,47.55) -> (109.90,49.90) -> (111.70,49.90) -> L1.1
    #
    # Clearances, 0.175 mm house margin, worst case per obstacle:
    #   band trace top edge 47.17 vs KEY horizontal bottom 46.73   0.44
    #   ring top 47.10 vs KEY horizontal bottom 46.73              0.37
    #   ring (106.60) vs the KEY vertical's end cap (107.00,46.73) 0.42
    #   ring (109.90) right edge 110.35 vs VBUS F.Cu 110.62        0.27
    #   ring (106.60) vs the +5V plane via at (105.50, 48.85)      0.37
    #   ring (108.80) vs the U2.EP thermal via at (108.55, 45.30)  1.41
    #   band cap bottom 47.93 vs +5V F.Cu top edge 48.47           0.54
    #   feed column x=109.90 left edge 109.52 vs L1.2 pad 109.00   0.52
    #   feed row y=49.90 bottom edge 50.28 vs L1.2 pad top 50.80   0.52
    #   barrel-to-barrel hole gap 1.10 - 0.45                      0.65
    _BAT_BAND2_Y = 47.550
    _BAT_BAND2_XS = (106.600, 107.700, 108.800, 109.900)
    _band2_nodes = (bat_col_x,) + _BAT_BAND2_XS
    for _layer in ("F.Cu", "B.Cu"):
        parts.append(_seg(bat_col_x, _bat_stitch_y2, bat_col_x, _BAT_BAND2_Y,
                           _layer, W_PWR_HIGH, n_bat))
        for _xa, _xb in zip(_band2_nodes, _band2_nodes[1:]):
            parts.append(_seg(_xa, _BAT_BAND2_Y, _xb, _BAT_BAND2_Y,
                               _layer, W_PWR_HIGH, n_bat))
    for _bx in _BAT_BAND2_XS:
        parts.append(_via_net(_bx, _BAT_BAND2_Y, n_bat,
                              size=VIA_PWR, drill=VIA_PWR_BIG_DRILL))
    parts.append(_seg(_BAT_BAND2_XS[-1], _BAT_BAND2_Y,
                       _BAT_BAND2_XS[-1], _L1_FEED_Y,
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(_BAT_BAND2_XS[-1], _L1_FEED_Y, l1_1[0], _L1_FEED_Y,
                       "B.Cu", W_PWR_HIGH, n_bat))
    # F.Cu horizontal to JST approach column between pull-up resistors R11(x=78) and R12(x=83).
    # DFM FIX: was 79.75 (overlapped R11), was 80.05 (too close to J3[2]).
    # At 80.01 with VIA_STD (r=0.45): via ring gap = 0.11mm (was rule 0.10mm).
    #
    # R9-HIGH-1 FIX (2026-04-11): After R8 assigned R11.1 to BTN_Y (instead of
    # the old +3V3 dead-end), the BAT+ via at (80.01, 46.135) is now within
    # 0.11 mm of a DIFFERENT-NET pad (BTN_Y) — failing the 0.20 mm pad-to-via
    # clearance rule. Root cause: R8 changed the net assignment on R11.1.
    # Fix: shrink the BAT+ approach via to VIA_MIN (0.50mm, r=0.25):
    #   Via right edge: 80.01+0.25=80.26
    #   Via left  edge: 80.01-0.25=79.76
    #   R11.1 pad right edge: 78.95+0.50=79.45 → gap 79.76-79.45=0.31 mm ✓
    #   J3[2] pad left edge:  80.50-0.60=80.00? No, J3 is ~1.20x1.40 THT
    #     J3[2] left edge ≈ 80.50 → gap 80.50-80.26=0.24 mm ✓ (>0.20)
    # R32: 80.01 -> 80.08. The 0805 land grew to the JLC reference and
    # R11.1 / C12.1's east edge moved to 79.525, leaving this 0.76mm-wide
    # run 0.105mm of clearance. The window east is narrow: the band-0
    # barrel at x=80.90 (r=0.40) exists on the INNER layers too, where
    # this approach via's 0.25mm annulus is the only other copper, so
    # x <= 80.10 keeps those two annuli 0.15mm apart. 80.08 sits in
    # [80.055, 80.10]: 0.175mm to the pads, 0.17mm to the band-0 annulus.
    bat_approach_x = 80.08
    # Split at the U2.6 stitching field's west column so that field's
    # copper shares an endpoint with this corridor (verify_dangling_copper).
    parts.append(_seg(bat_col_x, bat_via_y, _bat_stitch_x2, bat_via_y,
                       "F.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(_bat_stitch_x2, bat_via_y, bat_approach_x, bat_via_y,
                       "F.Cu", W_PWR_HIGH, n_bat))
    parts.append(_via_net(bat_approach_x, bat_via_y, n_bat,
                          size=VIA_MIN, drill=VIA_MIN_DRILL))
    #
    # AMPACITY (verify_power_via_ampacity) — the worst transition on the
    # board. Q1's drain and everything downstream of it live on B.Cu; the
    # rail crosses to F.Cu here and ONLY here, so this one 0.20 mm barrel
    # carried 4.348 A worth of battery current on 0.527 A of copper.
    #
    # The via itself cannot grow: R11.1 (BTN_Y, a different net) ends at
    # x=79.45 and the 0.175 mm house clearance caps the ring at 0.50 mm
    # OD, which is exactly why R9-HIGH-1 shrank it. So the transition is
    # widened instead of the hole, in two places:
    #
    #   band 0, on the existing corridor at y=46.135 — one more barrel
    #     0.89 mm east at (80.90). R12.2 (+3V3) starts at x=81.55, leaving
    #     a 0.25 mm ring gap; the B.Cu stub between the two vias reaches
    #     x=81.28, 0.27 mm short of that pad. 0.80 OD / 0.35 -> 0.791 A.
    #
    #   band 1, a second F.Cu/B.Cu overlap 1.14 mm north at y=47.275 —
    #     four barrels. This band is 0.95 mm tall and that is not a choice:
    #     R11/R12's pads end at y=46.65 below it and BTN_R's F.Cu channel
    #     runs at y=48.0 above it, so a 0.85 OD ring centred at 47.275
    #     clears both by 0.25 mm and nothing larger fits. Sideways it is
    #     bounded by the BTN_Y (x=78.95) and BTN_START (x=83.95) B.Cu
    #     columns. Drill 0.45 rather than 0.35 buys 0.949 A per barrel and
    #     is what puts the rail comfortably over its requirement — the
    #     four 0.35 mm barrels this band would otherwise hold come to
    #     4.482 A total, a 3% margin, and this is the battery.
    #
    # 0.527 + 0.791 + 4 x 0.949 = 5.114 A against 4.348 A required.
    _bat_band0_via_x = 80.90
    _bat_band1_y = 47.275
    _bat_band1_xs = (79.725, 80.750, 81.775, 82.800)
    parts.append(_seg(bat_approach_x, bat_via_y, _bat_band0_via_x, bat_via_y,
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_via_net(_bat_band0_via_x, bat_via_y, n_bat,
                          size=VIA_PWR_TIGHT, drill=VIA_PWR_DRILL))
    # Riser to band 1: B.Cu already runs north from the via (the Q1 column
    # below), so only F.Cu needs one. Both bands are chained through
    # bat_approach_x so every segment ends on a via or on another
    # segment's endpoint — verify_dangling_copper and the JLCDFM dead-end
    # rule both measure endpoints, not overlaps.
    parts.append(_seg(bat_approach_x, bat_via_y, bat_approach_x, _bat_band1_y,
                       "F.Cu", W_PWR_HIGH, n_bat))
    _bat_band1_nodes = sorted(set(_bat_band1_xs) | {bat_approach_x})
    for _layer in ("F.Cu", "B.Cu"):
        for _xa, _xb in zip(_bat_band1_nodes, _bat_band1_nodes[1:]):
            parts.append(_seg(_xa, _bat_band1_y, _xb, _bat_band1_y,
                               _layer, W_PWR_HIGH, n_bat))
    for _bx in _bat_band1_xs:
        parts.append(_via_net(_bx, _bat_band1_y, n_bat,
                              size=0.85, drill=VIA_PWR_BIG_DRILL))
    # ── BAT+ approach → Q1 SOURCE (P-MOSFET RPP) ──────────────────
    # Q1 (SI2301CDS SOT-23-3) at (85.0, 53.0) on B.Cu, Q1_ROT=180:
    #   Pin 3 (Drain/BAT_IN) at (85.0, 54.1)   — faces J3, the cell side
    #   Pin 2 (Source/BAT+)  at (85.95, 51.9)  — faces the IP5306 side
    #   Pin 1 (Gate/RPP_GATE) at (84.05, 51.9)
    #
    # R31-HIGH-1: through v4.5.0 this was the other way round — cell on the
    # source, IP5306 on the drain — and that is not reverse-polarity
    # protection. The P-channel body diode conducts D->S, so a reversed
    # cell forward-biased it and fault current flowed anyway, through a
    # diode rated 1.3 A and through U2's structures. With the cell on the
    # drain, a reversed cell reverse-biases the diode while V_GS is
    # positive: diode and channel both block. Correct polarity is
    # indistinguishable between the two wirings, which is why every board
    # built so far worked and nothing caught it.
    #
    # The copper had to move with the part, not just the net labels: the
    # y=54.1 channel is the only way in from J3 (J3.4's mounting tab owns
    # x 82.60-84.10, y 54.95-58.35 directly below Q1), so whichever pad
    # sits on that channel is the cell-side pad. Turning the package 180
    # deg is what puts the drain there.
    q1_drain = _pad("Q1", "3")    # (85.0, 54.1) — BAT_IN net (cell side)
    q1_source = _pad("Q1", "2")   # (85.95, 51.9) — BAT+ net (IP5306 side)
    q1_gate = _pad("Q1", "1")     # (84.05, 51.9) — RPP_GATE net
    n_bat_in = NET_ID["BAT_IN"]
    n_rpp_gate = NET_ID["RPP_GATE"]

    # Pad net assignments for Q1 and R24
    _PAD_NETS[("Q1", "1")] = n_rpp_gate
    _PAD_NETS[("Q1", "2")] = n_bat
    _PAD_NETS[("Q1", "3")] = n_bat_in
    _PAD_NETS[("R24", "1")] = n_rpp_gate
    _PAD_NETS[("R24", "2")] = n_gnd
    # J3 pin 1 is BAT_IN (pre-RPP), not BAT+
    _PAD_NETS[("J3", "1")] = n_bat_in

    # BAT+ approach → Q1 source
    # bat_approach_x=80.01 vertical from via down to y=52.9 (channel),
    # horizontal RIGHT to x=85.95, short vertical UP to the source y=51.9.
    # The channel is at 52.9 and not the old 52.5 because the gate pad now
    # sits at (84.05, 51.9): at 52.5 a 0.6 mm trace (bottom 52.20) would
    # have overlapped that pad (bottom edge 52.25).
    # Clearance checks (trace half-width 0.30):
    #   Channel y=52.9: gate pad (84.05,51.9) bottom 52.25 → gap 0.35mm OK
    #   Channel y=52.9: GND via (82.20,51.5) bottom 51.80 → gap 0.80mm OK
    #   Channel y=52.9: GND via (86.80,52.0) west 86.50, trace end 86.25 → 0.25mm OK
    #   Source riser x=85.95: drain pad (85.0,54.1) east 85.30 → gap 0.35mm OK
    _bat_q1_channel_y = 52.9  # above J3.4 tab (54.95), below the gate pad
    # Split at the band-1 stitching row so that row's copper shares an
    # endpoint with this column instead of T-ing into the middle of it.
    parts.append(_seg(bat_approach_x, bat_via_y, bat_approach_x, _bat_band1_y,
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(bat_approach_x, _bat_band1_y, bat_approach_x, _bat_q1_channel_y,
                       "B.Cu", W_PWR_HIGH, n_bat))
    parts.append(_seg(bat_approach_x, _bat_q1_channel_y, q1_source[0], _bat_q1_channel_y,
                       "B.Cu", W_PWR, n_bat))
    parts.append(_seg(q1_source[0], _bat_q1_channel_y, q1_source[0], q1_source[1],
                       "B.Cu", W_PWR, n_bat))

    # BAT_IN: Q1 drain → J3 pin 1
    # Q1 drain at (85.0, 54.1), J3.1 at (79.0, 62.5)
    # B.Cu horizontal left at y=54.1 (clears J3.4 top 54.95 by 0.55mm),
    # then vertical down to J3.1.
    # Clearance: VBUS B.Cu starts at y=61.0, USB_D- at y=64.58 — both far below.
    # BAT+ channel at y=52.9: gap = 54.1-52.9-0.30-0.30 = 0.60mm OK
    parts.append(_seg(q1_drain[0], q1_drain[1], jst_p[0], q1_drain[1],
                       "B.Cu", W_PWR, n_bat_in))
    parts.append(_seg(jst_p[0], q1_drain[1], jst_p[0], jst_p[1],
                       "B.Cu", W_PWR, n_bat_in))

    # RPP_GATE: Q1 gate → R24 pad 1
    # Gate at (84.05, 51.9), R24.1 at (85.40, 49.25) [rot=270 on B.Cu].
    # R24 moved north of Q1 with the gate pad — the BAT+ channel (52.9)
    # and the BAT_IN channel (54.1) are two unbroken walls of copper
    # between this pad and the old R24 spot at (86.0, 56.0).
    # Z-shaped: north out of the pad into the 0.90 mm corridor between the
    # C13 pad row (bottom 50.65) and Q1's own pad row (top 51.55), east in
    # that corridor, then north up the C13/C14 gap into R24.1.
    # Clearance checks (trace half-width 0.125):
    #   Corridor y=51.1: C13.1 bottom 50.65 → 0.325mm; Q1 pads top 51.55 → 0.325mm
    #   Riser x=85.40: C13.1 east 84.45 → 0.825mm; C14.2 west 86.55 → 1.025mm
    #   Riser x=85.40 vs Q1 source pad (85.65,51.55): diagonal 0.348mm OK
    _gate_corridor_y = 51.1
    _gate_riser_x = 85.50   # R32: follows R24_POS, which moved 0.1mm east
    r24_1 = _pad("R24", "1")   # RPP_GATE (85.40, 49.25)
    r24_2 = _pad("R24", "2")   # GND (85.40, 47.35)
    parts.append(_seg(q1_gate[0], q1_gate[1], q1_gate[0], _gate_corridor_y,
                       "B.Cu", W_SIG, n_rpp_gate))
    parts.append(_seg(q1_gate[0], _gate_corridor_y, _gate_riser_x, _gate_corridor_y,
                       "B.Cu", W_SIG, n_rpp_gate))
    parts.append(_seg(_gate_riser_x, _gate_corridor_y, r24_1[0], r24_1[1],
                       "B.Cu", W_SIG, n_rpp_gate))

    # R24 pad 2 → GND via (connects to In1.Cu GND zone)
    #
    # R32 (2026-08-03): the barrel used to sit on R24.2's centre. Three
    # F.Cu rails cross this area — BAT+ (y 45.755-46.515), BTN_R
    # (47.9-48.1) and +5V (48.47-49.23) — so y is pinned to the
    # 46.99-47.42 band and the barrel cannot leave the pad vertically.
    # It steps EAST instead, 1.00mm along the pad's own y: the hole then
    # clears R24.2's east edge (86.075) by 0.225mm, R13.2's pad corner by
    # 0.579mm, and the barrel keeps 0.25mm to the BTN_R rail. R24.1
    # (RPP_GATE, the one different-net neighbour) stays 1.06mm away.
    _r24_gnd_via_x = r24_2[0] + 1.00
    parts.append(_seg(r24_2[0], r24_2[1], _r24_gnd_via_x, r24_2[1],
                      "B.Cu", W_SIG, n_gnd))
    parts.append(_via_net(_r24_gnd_via_x, r24_2[1], n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))

    # ── SW16: the switch node, and the BAT+ stub that is now gone ─────
    #
    # WHAT WAS HERE: a W_PWR_HIGH branch of BAT+ that left the rail at
    # x=80, ran 42 mm west on F.Cu at y=46.135, climbed the x=38 column
    # and dead-ended on SW16 pad 2. It was the entire electrical
    # relationship the switch had with the board: pads 1 and 3 carried no
    # net, so sliding it changed nothing. Deleted, in full — that stub was
    # the bug, not a wire that needed re-purposing.
    #
    # WHAT IS HERE NOW: the same corridor, carrying PWR_SW, the Q2 gate
    # control node. Three things are deliberate.
    #
    #  1. It runs on F.Cu for the long haul. F.Cu references the
    #     continuous In1.Cu GND pour, so a net that crosses the whole
    #     board never meets the In2.Cu +5V/+5V_VOUT seam. On B.Cu it
    #     would cross it, and a seam between two rails that differ by 5 V
    #     in the OFF state is a real return-path break.
    #  2. y=54.35 is a MEASURED corridor, not a guess: on F.Cu it is
    #     clear from x=36 to x=110.3 with nothing in it at all, the only
    #     unobstructed full-width band on the board. J3's tabs start at
    #     y=54.95 (0.425 mm below) and the SPK1 pad ends at y=54.0.
    #  3. It is W_SIG. PWR_SW carries the gate's leakage and R34's 0.8 uA
    #     — it is a control node, and calling it a power net would put a
    #     0.5 mm minimum on 70 mm of copper for no reason.
    SW_COL_X = 38.0    # the freed BAT+ column; SPK+ at x=39.5 is 1.5 mm east
    PWR_SW_FCU_Y = 54.35
    sw_via_y = sw_com[1] - 2   # 68.3 — short B.Cu stub north from the pad
    parts.append(_seg(sw_com[0], sw_com[1], sw_com[0], sw_via_y,
                       "B.Cu", W_SIG, n_pwr_sw))
    parts.append(_seg(sw_com[0], sw_via_y, SW_COL_X, sw_via_y,
                       "B.Cu", W_SIG, n_pwr_sw))
    # B.Cu column north to the corridor. It stays on B.Cu for exactly the
    # reason the old stub did: the D-pad button channels at y=62..65 are
    # F.Cu, so this column passes under them. At W_SIG (0.25) the SPK1 pad
    # taper the old W_PWR_HIGH run needed is unnecessary — right edge
    # 38.125 against the pad's left edge 38.50 is 0.375 mm.
    parts.append(_seg(SW_COL_X, sw_via_y, SW_COL_X, PWR_SW_FCU_Y,
                       "B.Cu", W_SIG, n_pwr_sw))
    parts.append(_via_net(SW_COL_X, PWR_SW_FCU_Y, n_pwr_sw,
                          size=VIA_STD, drill=VIA_STD_DRILL))
    # The long F.Cu run, split at the R34 drop so both junctions are real
    # endpoints (verify_dangling_copper measures endpoints, not overlaps).
    # VBUS's F.Cu column at x=111.0 (y 49.75..61.0) cuts the corridor, so
    # it ends 1.0 mm short of it and continues on B.Cu — see
    # _pwr_switch_traces, which picks the net up at this endpoint.
    _PWR_SW_FCU_END = 110.0
    # Split at R34's drop: verify_dangling_copper measures ENDPOINTS, not
    # overlaps, so a branch that T's into the middle of this run reads as
    # copper ending in air even though it is fabricated connected.
    _R34_TAP_X = 85.15
    parts.append(_seg(SW_COL_X, PWR_SW_FCU_Y, _R34_TAP_X, PWR_SW_FCU_Y,
                       "F.Cu", W_SIG, n_pwr_sw))
    parts.append(_seg(_R34_TAP_X, PWR_SW_FCU_Y, _PWR_SW_FCU_END, PWR_SW_FCU_Y,
                       "F.Cu", W_SIG, n_pwr_sw))

    # SW16 pad 1 -> GND. This is the ON position: grounding the common
    # pulls PWR_SW to 0 V, the R32/R33 divider puts Q2's gate 4.55 V below
    # its source and the load rail comes up. Pad 3 is left OPEN on purpose
    # — with the throw open, R34 alone defines the node (see R34 below),
    # which is what keeps the switch down to ONE net across the board.
    sw_on = _pad("SW16", "1")     # (42.25, 70.3)
    if sw_on:
        parts.append(_seg(sw_on[0], sw_on[1], sw_on[0], sw_on[1] - 1.6,
                           "B.Cu", W_SIG, n_gnd))
        parts.append(_via_net(sw_on[0], sw_on[1] - 1.6, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))

    parts.extend(_pwr_switch_traces())

    # USB CC pull-down resistor GND traces are in _usb_traces()

    # ── R21 FIX: +5V bridge from IP5306 zone to PAM8403 zone ──────────
    # Before this fix the two +5V In2.Cu zones were electrically isolated:
    #   Zone #1 (105-140, 35-65) — IP5306 VOUT / AMS1117 VIN
    #   Zone #2 (20-42, 24-53)   — PAM8403 VDD  (south edge extended
    #                              from 42→53 in _power_zones for this bridge)
    # Previous commit "DFM FIX: removed F.Cu bridge trace" (routing.py:2427)
    # deleted the original bridge because it crossed the LCD data bus at
    # y=26..35 F.Cu. The bridge was NEVER replaced — PAM8403 VDD was
    # floating (no copper path to the IP5306 +5V rail), which is why DRC
    # reports "C27.2 [+5V] ↔ Track [+5V] 2.75mm unconnected".
    #
    # New route: F.Cu horizontal at y=48.7 from x=41.0 (inside PAM zone #2,
    # extended to y=53) to x=105.5 (just inside IP5306 zone #1 east of
    # the 105 boundary).
    # y=48.7 chosen because it sits in the narrow gap between BTN_R@48
    # (F.Cu horiz x=76.20..98.95) and C5..C16 debounce caps (F.Cu pads
    # at y=49.35..50.65). Earlier attempt at y=51 hit GND via @(82.2, 51.5)
    # and cap-pad overlap; y=53 hit BAT+ B.Cu@y=52.5.
    # Verified clearances along x=[41, 105.5]:
    #   BTN_R@48 (top edge 48.10):   gap 48.85-0.38-48.10 = 0.37mm ≥ 0.10mm (different net) ✓
    #   BTN_R vias @(76.20/88.00, 48.00) sz=0.6 outer y=48.30:
    #                                gap trace-top 48.47 → via-edge 48.30 = 0.17mm ≥ 0.10mm ✓
    #   C5..C16 pads (bottom 49.35): gap 49.35-(48.85+0.38) = 0.12mm ≥ 0.10mm ✓
    #   Pull-up vias@y=52 (outer 51.70): gap=51.70-49.23=2.47mm ✓
    #   BAT+ F.Cu@46.13 (edge 46.51): gap 48.85-0.38-46.51 = 1.96mm ✓
    #   GND via @(82.2, 51.5) sz=0.6: dist=sqrt(0²+2.65²)-0.3-0.38=1.97mm ✓
    # Via endpoints:
    #   (105.5, 48.85): BAT+ via @(105.5, 46.13) dist=2.72mm - 2×0.30 = 2.12mm ≥ 0.25mm ✓
    #                   Inside zone #1 (105-140, 35-65) ✓
    #   (39.0, 48.85):  C5 pad @(42.05, 49.35) dist=sqrt(3.05²+0.50²)=3.09mm - 0.30 = 2.79mm ✓
    #                   Inside zone #2 (20-39.6, 24-53) with 0.3mm margin ✓
    # Width W_PWR_HIGH=0.76mm, ~2A @1oz, PAM8403 peak 0.6A → 3× margin.
    #
    # R22-CRIT-1 FIX: the west via moved from x=41.0 to x=39.0 so the PAM
    # +5V island can be pulled back from x=42 to x=39.6, freeing the R4
    # pull-up +3V3 via at (41.80, 44.50) that the island used to trap.
    # Clearances at the new via (39.0, 48.85), OD 0.60 → edge radius 0.30:
    #   SPK+ B.Cu vert x=40.90 (w=0.30, left edge 40.75): gap 1.45mm ✓
    #   BAT+ B.Cu vert x=38.00 (w=0.76, right edge 38.38): gap 0.32mm ✓
    #   SPK1 pad 1 (39.5, 52.5) 2.0x3.0 (top edge 51.00):  gap 1.85mm ✓
    #   BAT+ via (38.00, 46.135) OD 0.90: centre dist 2.89mm − 0.75 = 2.14mm ✓
    # The extra 2 mm of F.Cu run (x=41→39 at y=48.85) is clear: the only
    # F.Cu in that band is BAT+ at y=46.135 and BTN_SELECT at y=52.65
    # (x≤35.95) — both ≥2.3mm away.
    _bridge_y = 48.85
    _bridge_x_west = 39.0
    parts.append(_via_net(105.5, _bridge_y, n_5v, size=VIA_STD, drill=VIA_STD_DRILL))
    parts.append(_seg(105.5, _bridge_y, _bridge_x_west, _bridge_y,
                        "F.Cu", W_PWR_HIGH, n_5v))
    parts.append(_via_net(_bridge_x_west, _bridge_y, n_5v,
                          size=VIA_STD, drill=VIA_STD_DRILL))

    return parts


def _pwr_switch_traces():
    """Q2 high-side +5V load switch, its gate network and the KEY wake path.

    The rail split, in one picture (B.Cu unless noted):

        U2.8 ==3 vias==> [In2 +5V_VOUT island] ==vias==> Q2.S
                                                            |
                              R32 100k --+-- C32 100nF      | channel
                                         |                  v
                                    Q2.G-+-- R33 10k --PWR_SW    Q2.D ==vias==> [In2 +5V island] ==> loads
                                                          |
                                              R34 4.7M --BAT+
                                              C33 1uF ---IP5306_KEY
                                                          |
                                                       SW16.2 (common)
                                                       SW16.1 -> GND (ON)

    EVERY B.CU TRACE HERE STAYS ON ONE SIDE OF THE y=45 PLANE SEAM.
    Q2 straddles it so each pad vias straight down into its own plane;
    the gate network is entirely north of it; PWR_SW crosses only on
    F.Cu, which references the continuous In1.Cu GND pour. That is not
    tidiness — with the switch OFF the two halves of the old +5V rail sit
    5 V apart, so a B.Cu run crossing the seam would be a genuine broken
    return path, and verify_reference_plane is right to count them.
    """
    parts = []
    _init_pads()
    n_5v = NET_ID["+5V"]
    n_5v_vout = NET_ID["+5V_VOUT"]
    n_gate = NET_ID["PWR_SW_GATE"]
    n_pwr_sw = NET_ID["PWR_SW"]
    n_bat = NET_ID["BAT+"]
    n_gnd = NET_ID["GND"]
    n_key = NET_ID["IP5306_KEY"]

    q2_g = _pad("Q2", "1")     # (117.25, 43.90) PWR_SW_GATE
    q2_s = _pad("Q2", "2")     # (119.15, 43.90) +5V_VOUT
    q2_d = _pad("Q2", "3")     # (118.20, 46.10) +5V
    r32_1, r32_2 = _pad("R32", "1"), _pad("R32", "2")
    c32_1, c32_2 = _pad("C32", "1"), _pad("C32", "2")
    r33_1, r33_2 = _pad("R33", "1"), _pad("R33", "2")
    r34_1, r34_2 = _pad("R34", "1"), _pad("R34", "2")

    for ref, pin, net in (
        ("Q2", "1", n_gate), ("Q2", "2", n_5v_vout), ("Q2", "3", n_5v),
        ("R32", "1", n_gate), ("R32", "2", n_5v_vout),
        ("C32", "1", n_gate), ("C32", "2", n_5v_vout),
        ("R33", "1", n_gate), ("R33", "2", n_pwr_sw),
        ("R34", "1", n_pwr_sw), ("R34", "2", n_bat),
        ("C33", "1", n_pwr_sw), ("C33", "2", n_key),
        ("SW16", "1", n_gnd), ("SW16", "2", n_pwr_sw),
    ):
        _PAD_NETS[(ref, pin)] = net

    # ── +5V_VOUT: plane -> Q2 source ──────────────────────────────
    # The boost's 2 A arrives on the In2 sub-island; these barrels are the
    # only way back up to the B.Cu source pad, so they carry the whole
    # rail. Sized the way the BAT+ transition was: 0.85 OD / 0.45 drill is
    # 0.949 A each, and three of them is 2.847 A against the 2.150 A the
    # +5V loads take.
    _s_via_ys = (43.90, 42.85, 41.80)
    parts.append(_seg(q2_s[0], q2_s[1], q2_s[0], _s_via_ys[-1],
                       "B.Cu", W_PWR_HIGH, n_5v_vout))
    for _y in _s_via_ys:
        parts.append(_via_net(q2_s[0], _y, n_5v_vout, size=0.85, drill=0.45))

    # ── +5V: Q2 drain -> plane ────────────────────────────────────
    # Same current, same three barrels, on the load side of the seam.
    # South is the only free direction: BAT+ runs west of the drain at
    # y=46.1 and the island's east edge is 2.1 mm away.
    _d_via_ys = (46.10, 47.15, 48.20)
    parts.append(_seg(q2_d[0], q2_d[1], q2_d[0], _d_via_ys[-1],
                       "B.Cu", W_PWR_HIGH, n_5v))
    for _y in _d_via_ys:
        parts.append(_via_net(q2_d[0], _y, n_5v, size=0.85, drill=0.45))

    # ── Gate node: one straight column at x=117.25 ────────────────
    # Q2's gate pad and pad 1 of R32, R33 and C32 all sit on this x, so
    # the gate is a single vertical run. Entirely inside the +5V_VOUT
    # island — the gate is referenced to the SOURCE, and a gate network
    # that lost its reference when Q2 opened would float the switch.
    _GATE_X = q2_g[0]
    _gate_ys = sorted({q2_g[1], r32_1[1], r33_1[1], c32_1[1]})
    for _ya, _yb in zip(_gate_ys, _gate_ys[1:]):
        parts.append(_seg(_GATE_X, _ya, _GATE_X, _yb, "B.Cu", W_SIG, n_gate))

    # ── Gate return: R32.2 and C32.2 -> +5V_VOUT plane ────────────
    for _p in (r32_2, c32_2):
        parts.append(_via_net(_p[0], _p[1], n_5v_vout,
                              size=VIA_MIN, drill=VIA_MIN_DRILL))

    # ── PWR_SW: corridor -> R34 -> R33 ────────────────────────────
    # Three obstacles decide this path and each one is a wall, not a
    # preference:
    #   * VBUS's F.Cu column at x=111 cuts the y=54.35 corridor, so the
    #     corridor stops at x=110.0 and steps around L1 on B.Cu.
    #   * BAT+ runs unbroken on B.Cu at y=46.1 from x=107.8 to 116.95, so
    #     nothing on B.Cu gets from south to north anywhere near here.
    #   * the In2 plane seam is at y=45. Crossing it on F.Cu costs
    #     nothing (F.Cu references the continuous In1 GND pour); crossing
    #     it on B.Cu would be a real return-path break.
    # So: B.Cu up to R34, then F.Cu over BAT+ and over the seam to R33.
    parts.append(_via_net(110.0, 54.35, n_pwr_sw, size=VIA_STD, drill=VIA_STD_DRILL))
    parts.append(_seg(110.0, 54.35, 110.0, 55.60, "B.Cu", W_SIG, n_pwr_sw))
    # The east leg picks up C33's wake-cap pad; that column is C33's own.
    parts.append(_seg(110.0, 55.60, 115.25, 55.60, "B.Cu", W_SIG, n_pwr_sw))
    # North of BAT+ the net has to be on F.Cu, so it leaves the corridor
    # again at x=112.95 and climbs to R33.
    parts.append(_via_net(112.95, 55.60, n_pwr_sw, size=VIA_MIN, drill=VIA_MIN_DRILL))
    # VBUS's F.Cu run at y=49.75 is the one wall in this column, so the
    # net ducks under it on B.Cu between y=50.6 and y=48.9. That hop is
    # entirely inside the +5V island (both ends are south of the y=45
    # seam), so it crosses no plane boundary either.
    parts.append(_seg(112.95, 55.60, 112.95, 50.60, "F.Cu", W_SIG, n_pwr_sw))
    parts.append(_via_net(112.95, 50.60, n_pwr_sw, size=VIA_MIN, drill=VIA_MIN_DRILL))
    parts.append(_seg(112.95, 50.60, 112.95, 48.90, "B.Cu", W_SIG, n_pwr_sw))
    parts.append(_via_net(112.95, 48.90, n_pwr_sw, size=VIA_MIN, drill=VIA_MIN_DRILL))
    parts.append(_seg(112.95, 48.90, 112.95, 43.20, "F.Cu", W_SIG, n_pwr_sw))
    parts.append(_seg(112.95, 43.20, r33_2[0], 43.20, "F.Cu", W_SIG, n_pwr_sw))
    parts.append(_seg(r33_2[0], 43.20, r33_2[0], r33_2[1], "F.Cu", W_SIG, n_pwr_sw))
    parts.append(_via_net(r33_2[0], r33_2[1], n_pwr_sw,
                          size=VIA_MIN, drill=VIA_MIN_DRILL))

    # ── R34: PWR_SW tap off the corridor, BAT+ up to Q1's source ──
    # Pad 1 drops a via straight onto the F.Cu corridor 1.55 mm away; pad 2
    # climbs to the BAT+ channel at y=52.9, east of where BAT_IN turns off
    # toward J3 (that run ends at x=85.0, 1.75 mm west of this column).
    parts.append(_via_net(r34_1[0], r34_1[1], n_pwr_sw,
                          size=VIA_MIN, drill=VIA_MIN_DRILL))
    parts.append(_seg(r34_1[0], r34_1[1], r34_1[0], 54.35, "F.Cu", W_SIG, n_pwr_sw))
    # W_PWR and not W_SIG: this leg carries 1.3 uA, but it is BAT+ copper
    # and BAT+ is a Power High net. Widening 3 mm of trace is cheaper than
    # an allowlist entry, and an allowlist entry on the battery rail is
    # exactly the kind of exception that stops being read.
    parts.append(_seg(r34_2[0], r34_2[1], r34_2[0], 52.90, "B.Cu", W_PWR, n_bat))
    parts.append(_seg(r34_2[0], 52.90, 85.95, 52.90, "B.Cu", W_PWR, n_bat))

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

    # +5V zone on In2.Cu — power management area (IP5306 / U3 buck input)
    # Start at x=105 — historical boundary from when R19 pull-up vias
    # sat at x≈103 (R19 removed in R9-MED-4, but the +5V island stays
    # east of x=105 to keep the BAT+ corridor and LX jog unaffected).
    #
    # R22-CRIT-1 FIX (+3V3 split plane, board dead on v1):
    # The east boundary used to be x=140. That rectangle was far larger
    # than the +5V copper actually needs and it SWALLOWED every +3V3 via
    # east of x=123 — the regulator output vias (x=123.8..126.2), the
    # J4 display-power vias (x=131..133.7) and the FPC pads J4.29/34/35.
    # Because a lower-priority zone is deleted wherever a higher-priority
    # zone overlaps it, those vias landed on +5V copper on In2.Cu and were
    # simply not connected to anything: +3V3 resolved into FOUR isolated
    # electrical groups (regulator island 4.92 mm², main plane at 0 V,
    # J4.34/35 orphan, J4.29 orphan). The ESP32 therefore never saw 3.3 V.
    #
    # Real +5V extent (measured from the generated PCB, not estimated):
    #   x 105.5 … 121.1, y 39.0 … 58.3  (IP5306 VOUT, C19, C27, R16, the
    #   U3 buck C_IN via pair and the U3 EN via). Nothing on +5V lives east
    #   of x=123 or south of y=62.
    # V5_EAST = 123.0 frees the whole regulator-output / display-power area
    # back to the continuous +3V3 plane.
    # V5_SOUTH = 62.0 frees the y>62 band so the U3 feedback divider
    # (R25/R26/C29 at y=63.4) can tap +3V3 with a plain via; inside the
    # pour that via would be an isolated island — exactly the failure mode
    # this fix is removing.
    V5_EAST = 123.0
    V5_SOUTH = 62.0
    v5_pts = [
        (105, 35), (V5_EAST, 35), (V5_EAST, V5_SOUTH), (105, V5_SOUTH),
    ]
    parts.append(P.zone_fill("In2.Cu", v5_pts, NET_ID["+5V"], "+5V",
                             priority=1))

    # +5V zone island for PAM8403 audio amp (x=20..42, y=24..53)
    # DFM FIX: replaces the F.Cu bridge trace that crossed 8+ LCD data bus
    # horizontal traces at y=26..35 F.Cu (caused 0mm pad spacing violations).
    # PAM8403 VDD6 via connects to this In2.Cu island.
    # R21 FIX (+5V PAM supply): was (20-42, 24-42). Extended south to y=53
    # so a new F.Cu bridge at y=53 (from x=41 to x=105) can drop a via
    # into this island, carrying +5V from IP5306 VOUT zone (105-140, 35-65).
    # Previously the PAM +5V zone was floating — PAM8403 VDD pins had no
    # path back to the IP5306 +5V rail. The extended south area is clear
    # of +3V3 vias/pads (button pull-up strip starts at x=46.80, outside
    # x=20-42). SPK1 speaker at (30, 52.5) is unaffected (different layer).
    #
    # R22-CRIT-1 FIX: the east boundary used to be x=42, which trapped the
    # R4 pull-up +3V3 via at (41.80, 44.50) (via OD 0.60 → x 41.50..42.10)
    # inside this +5V island. Boundary pulled back to x=39.6 and the +5V
    # PAM bridge via moved from x=41.0 to x=39.0 (see _bridge_x in
    # _power_traces) so the via still sits 0.3 mm inside the pour while the
    # +3V3 via now clears the island by 1.9 mm.
    # Easternmost +5V feature in this island is C23.1 (pad right edge
    # x=38.5) → 1.1 mm margin to the new boundary.
    V5_PAM_EAST = 39.6
    v5_pam_pts = [
        (20, 24), (V5_PAM_EAST, 24), (V5_PAM_EAST, 53), (20, 53),
    ]
    parts.append(P.zone_fill("In2.Cu", v5_pam_pts, NET_ID["+5V"], "+5V",
                             priority=2))

    # ── +5V_VOUT sub-island (SW16 respin) ─────────────────────────────
    # Q2 breaks the +5V rail between the IP5306 boost and every load, and
    # 2 A cannot be woven from U2.8 across to Q2 on B.Cu: the VBUS column
    # at x=111, U2's own pad ring and the LCD bus box the boost output in
    # on every side. So the boost output travels east on the PLANE, in its
    # own island carved out of the +5V pour at a higher priority.
    #
    # THE BOUNDARY IS WHERE IT IS BECAUSE NOTHING CROSSES IT.
    # Every existing B.Cu run in this corner was checked against the two
    # cut lines before they were chosen:
    #   y=45, x 105..120.3 — U2's pads and the whole VBUS column
    #     (110.95, y 35..40.6) sit north of it; BAT+ (y=46.1), the KEY
    #     run (y=46.605) and everything below sit south. LX leaves the
    #     island westward at y=41.865, which is the crossing it already
    #     had at x=105 and is unchanged.
    #   x=120.3, y 35..45 — R27's backlight pads start at x=120.8 and its
    #     LED_BLA run is at x=121.7, so the east cut clears both. 120.3 is
    #     also the furthest east the pour may go and still keep the 0.5 mm
    #     zone clearance to R27's pad.
    # The only B.Cu that crosses either line is Q2 itself, which straddles
    # y=45 on purpose so each pad vias into its own plane.
    #
    # The +5V remainder stays ONE piece: the x 120.3..123 strip runs the
    # full height and ties the y>45 block to the y<45 block east of the
    # cut. verify_power_net_integrity is the gate that holds this — if a
    # future edit pinches that strip, +5V resolves into two groups and the
    # board is dead, which is exactly the R22-CRIT-1 failure above.
    V5_VOUT_EAST = 120.3
    V5_VOUT_SOUTH = 45.0
    v5_vout_pts = [
        (105, 35), (V5_VOUT_EAST, 35),
        (V5_VOUT_EAST, V5_VOUT_SOUTH), (105, V5_VOUT_SOUTH),
    ]
    parts.append(P.zone_fill("In2.Cu", v5_vout_pts, NET_ID["+5V_VOUT"],
                             "+5V_VOUT", priority=3))

    return parts
