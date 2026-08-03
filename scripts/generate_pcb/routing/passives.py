"""Split from routing.py 2026-07-26 — mechanical, AST-driven, proven by a
byte-identical regenerated .kicad_pcb. One domain per module; every helper
and every constant lives in _shared (original order, so import-time
execution is unchanged). See routing/__init__.py for the contract."""
from ._shared import (
    DEBOUNCE_REFS,
    DIAG_LEDS,
    DIAG_VBUS_TAP_Y,
    NET_ID,
    PULL_UP_REFS,
    VIA_MIN,
    VIA_MIN_DRILL,
    VIA_STD,
    VIA_STD_DRILL,
    W_DATA,
    W_PWR,
    W_PWR_HIGH,
    W_PWR_LOW,
    W_SIG,
    W_VBUS_DIAG,
    _init_pads,
    _pad,
    _seg,
    _via_net,
)




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
        # CRITICAL FIX: i=10 (R14, BTN_L, GPIO45) must NOT have external pull-up.
        # GPIO45 is a VDD_SPI strapping pin: HIGH=1.8V (wrong for PSRAM), LOW=3.3V (correct).
        # With pull-up, GPIO45=HIGH at boot → VDD_SPI=1.8V → PSRAM fails.
        # Fix: skip +3V3 connection for R14. Firmware uses internal pull-up after boot.
        # R14 is marked DNP (Do Not Populate) in BOM.
        if i == 10:
            continue  # no +3V3 pull-up for BTN_L (GPIO45 strapping pin)
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
                          "B.Cu", W_SIG, n_3v3))   # W_SIG(0.25): 0.15mm gap to btn verts
        parts.append(_seg(via_x, ry, via_x, via_y_pu,
                          "B.Cu", W_SIG, n_3v3))   # W_SIG(0.25): 0.15mm gap to btn verts
        _pu_via_sz = VIA_MIN if i == 10 else VIA_STD
        _pu_via_dr = VIA_MIN_DRILL if i == 10 else VIA_STD_DRILL
        parts.append(_via_net(via_x, via_y_pu, n_3v3, size=_pu_via_sz, drill=_pu_via_dr))

    # Debounce caps: GND via at cap pad
    #
    # WHY THIS IS A THIN B.Cu STUB — do not "fix" the DFM warning it produces.
    # `validate_jlcpcb` reports twelve times, once per cap, that a POWER net
    # (GND) runs at 0.2mm on B.Cu. That is expected. Two independent
    # constraints pin it there:
    #
    #   1. The LAYER is B.Cu on purpose. GND's plane is In1.Cu, but the only
    #      inner layer these caps could otherwise route across is In2.Cu,
    #      which carries the +3V3 pour. Twelve traces through that pour would
    #      carve it into channels — the same failure mode as the +5V-priority
    #      bug documented at the zone definitions further down, where +3V3
    #      resolved into four isolated groups and no v1 board ever saw 3.3 V.
    #      Instead each cap runs ~2mm on B.Cu and drops through ONE 0.60/0.20
    #      via, punching a single small clearance circle the plane flows
    #      around. `make verify-power-nets` confirms +3V3 stays one group.
    #   2. The WIDTH is what fits. W_DATA(0.2) leaves 0.175mm to the button
    #      B.Cu verticals running between these caps — see the per-index
    #      via_x nudges below, each dodging a specific vertical. Widening the
    #      stub eats that gap, and a wider stub invites a larger via, i.e. a
    #      larger hole in the +3V3 plane, which is constraint 1 again.
    #
    # These stubs carry a decoupling cap's return current over ~2mm, not a
    # supply rail, so 0.2mm is electrically fine. The rule that flags them is
    # a blanket power-net width rule that cannot see that distinction.
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
        # DFA FIX: i=8 (BTN_START cap) GND via shortened to cy+1.5 (conservative).
        # R24 relocated to (86.0, 56.0) — no longer near this via, but keep
        # 1.5mm for BAT+ channel at y=52.5 clearance (via top 51.80, gap=0.32mm ✓).
        _db_via_dy = 1.5 if i == 8 else 2.0
        parts.append(_seg(via_x_db, cy, via_x_db, cy + _db_via_dy,
                          "B.Cu", W_DATA, n_gnd))  # W_DATA: 0.175mm gap to btn verts
        _db_via_sz = VIA_MIN if i == 10 else VIA_STD
        _db_via_dr = VIA_MIN_DRILL if i == 10 else VIA_STD_DRILL
        parts.append(_via_net(via_x_db, cy + _db_via_dy, n_gnd, size=_db_via_sz, drill=_db_via_dr))

    # Connect pull-up outputs to debounce cap inputs (R->C junction)
    # R9-MED-4: BTN_MENU removed — 12 buttons only (menu via D1 OR-gate).
    btn_nets = [
        NET_ID["BTN_UP"], NET_ID["BTN_DOWN"],
        NET_ID["BTN_LEFT"], NET_ID["BTN_RIGHT"],
        NET_ID["BTN_A"], NET_ID["BTN_B"],
        NET_ID["BTN_X"], NET_ID["BTN_Y"],
        NET_ID["BTN_START"], NET_ID["BTN_SELECT"],
        NET_ID["BTN_L"], NET_ID["BTN_R"],
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
        # Route to +3V3 via zone — C26 connects via In2.Cu (+3V3 plane) through
        # its own via, not through the ESP32 +3V3 via (which was moved above pin 2).
        _c26_via_y = c26_p1[1] - 1.5  # via below C26 pad 1
        parts.append(_seg(c26_p1[0], c26_p1[1], c26_p1[0], _c26_via_y,
                          "B.Cu", W_PWR_LOW, n_3v3))
        parts.append(_via_net(c26_p1[0], _c26_via_y, n_3v3,
                              size=VIA_STD, drill=VIA_STD_DRILL))
    if c26_p2:
        # GND via — short stub away from +3V3 trace
        parts.append(_seg(c26_p2[0], c26_p2[1], c26_p2[0], c26_p2[1] + 1.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c26_p2[0], c26_p2[1] + 1.5, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))

    # EN RC delay network (R25-CRIT-1 respin fix): R3 10k pull-up + C31 100nF.
    # Both rot=90 on B.Cu at y=22.3, pads at y=21.35 (north, "1") and
    # y=23.25 (south, "2"). South pads drop a stub onto the EN trace that
    # runs U1.3 (88.75, 24.78) -> (98.0, 24.78); north pads via to the
    # internal planes at y=19.6 — 0.5mm edge gap to the F.Cu LCD traces at
    # y=20.5 (via r=0.3 + trace half-width 0.1: 0.9 - 0.4 = 0.5mm).
    # verify_strapping_pins reads these nets off the copper: R3 must bridge
    # EN<->+3V3 and C31 must bridge EN<->GND for the RC arm to pass.
    r3_p1 = _pad("R3", "1")
    r3_p2 = _pad("R3", "2")
    if r3_p1:
        parts.append(_seg(r3_p1[0], r3_p1[1], r3_p1[0], 19.6,
                          "B.Cu", W_PWR_LOW, n_3v3))
        parts.append(_via_net(r3_p1[0], 19.6, n_3v3,
                              size=VIA_STD, drill=VIA_STD_DRILL))
    if r3_p2:
        parts.append(_seg(r3_p2[0], r3_p2[1], r3_p2[0], 24.78,
                          "B.Cu", 0.25, NET_ID["EN"]))
    c31_p1 = _pad("C31", "1")
    c31_p2 = _pad("C31", "2")
    if c31_p1:
        parts.append(_seg(c31_p1[0], c31_p1[1], c31_p1[0], 19.6,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c31_p1[0], 19.6, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))
    if c31_p2:
        parts.append(_seg(c31_p2[0], c31_p2[1], c31_p2[0], 24.78,
                          "B.Cu", 0.25, NET_ID["EN"]))

    # C28 ESP32 +3V3 bulk cap (10uF, rotated 90°): pad "1" -> +3V3, pad "2" -> GND.
    # At (86,24), 2.8mm from U1 pin 2. Improves PSRAM burst transient response.
    c28_p1 = _pad("C28", "1")
    c28_p2 = _pad("C28", "2")
    if c28_p1:
        parts.append(_seg(c28_p1[0], c28_p1[1], c28_p1[0], c28_p1[1] - 1.5,
                          "B.Cu", W_PWR_LOW, n_3v3))
        parts.append(_via_net(c28_p1[0], c28_p1[1] - 1.5, n_3v3,
                              size=VIA_STD, drill=VIA_STD_DRILL))
    if c28_p2:
        parts.append(_seg(c28_p2[0], c28_p2[1], c28_p2[0], c28_p2[1] + 1.5,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c28_p2[0], c28_p2[1] + 1.5, n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))

    # C1 (buck input cap) and C30 (buck output cap) are routed as part of
    # the U3 cluster in _buck_traces() — their loops are performance
    # critical and must stay together with the regulator geometry.
    # C2 (22uF tantalum, old AMS1117 output cap) has been DELETED.

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
        # R6 FIX (2026-04-10): previously the C17 VBUS stub went NORTH to a
        # dangling via at (110.95, 33.65) hoping for VBUS zone fill that did
        # not exist. C17 was electrically isolated from the VBUS network —
        # IP5306 VIN had no input decoupling (see hardware-audit-bugs.md
        # R5-CRIT-3).
        #
        # Fix: route C17.1 SOUTH instead to reach the existing VBUS F.Cu/B.Cu
        # transition via at (111.00, 40.095). Route:
        #   B.Cu (c17_p1.x, 35.00) → (c17_p1.x, 40.095) vertical 5.1mm
        #   B.Cu (c17_p1.x, 40.095) → (111.00, 40.095) jog, when the pad
        #   does not already sit on the via's column.
        # The stub endpoint touches the existing VBUS via which provides
        # the F.Cu↔B.Cu layer transition. No new vias needed.
        #
        # R32: growing the 0805 land to the JLC reference (±0.95 → ±1.00
        # centres) put pad 1 at exactly x=111.00, which turned that jog
        # into a zero-length segment — _seg() rejects those outright, so
        # it is emitted only when it has a real length. The pad now sits
        # on the via's own column, so on this board it is skipped.
        #
        # The vertical also narrowed 0.55 → 0.50 with that move: at
        # x=111.00 a 0.55mm trace would have come within 0.125mm of
        # LCD_D4. 0.50 is the floor for VBUS's Power-High net class
        # (verify_net_class_widths) and leaves exactly 0.15mm.
        #
        # Clearances along the vertical at x=111.00, y=[35, 40.095]:
        #   - LCD_D4 B.Cu vert at x=111.50 (w=0.20): dx=0.50, gap = 0.50-0.25-0.10 = 0.150mm ✓
        #   - U2.1 VBUS pad at (113, 40.59): same net, no clearance issue
        #   - EP (110, 42.5 y_max=43.9): 3.8mm south of our endpoint → clear
        #   - No other B.Cu traces on x≈111 between y=35 and y=40
        _c17_vbus_via_x = 111.00
        parts.append(_seg(c17_p1[0], c17_p1[1], c17_p1[0], 40.095,
                          "B.Cu", 0.50, NET_ID["VBUS"]))
        if abs(c17_p1[0] - _c17_vbus_via_x) > 1e-9:
            parts.append(_seg(c17_p1[0], 40.095, _c17_vbus_via_x, 40.095,
                              "B.Cu", 0.50, NET_ID["VBUS"]))
    if c17_p2:
        parts.append(_seg(c17_p2[0], c17_p2[1], c17_p2[0], c17_p2[1] + 2.7,
                          "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(c17_p2[0], c17_p2[1] + 2.7, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # C18 near IP5306: BAT decoupling at (116.95, 49.0), 10.7mm from pin 6.
    # R6 FIX (2026-04-10): the previous version routed C18.1 to a dangling
    # via at (116.95, 47.5) expecting a non-existent BAT+ zone fill to
    # connect it (see hardware-audit-bugs.md R5-CRIT-2). C18 was never
    # electrically part of the BAT+ rail — the cap was physically placed
    # and listed in the BOM but floating.
    #
    # Fix: extend C18.1 stub further north to y=46.135 where it meets the
    # new BAT+ corridor horizontal added in _power_traces(). No via needed —
    # both segments are B.Cu and T-junction at (116.95, 46.135).
    # Placed right of KEY vertical at x=114.05, between KEY route and R16.
    c18_p1 = _pad("C18", "1")
    c18_p2 = _pad("C18", "2")
    if c18_p1:
        # R6 FIX: route C18.1 all the way north to y=46.10 where the new
        # BAT+ corridor horizontal (from _power_traces) runs. Same-net
        # T-junction at (116.95, 46.10) — no via needed.
        # Length = 49.0 - 46.10 = 2.9mm. Passes over:
        #   - KEY horizontal at y=46.61: x=116.95 > 114.05 (KEY right end) → clear
        #   - KEY vertical at x=114.05: 2.9mm left of our x → clear
        #   - R16 pads at (114.05/115.95, 52.5): far south of our y range → clear
        parts.append(_seg(c18_p1[0], c18_p1[1], c18_p1[0], 46.10,
                          "B.Cu", W_PWR_HIGH, NET_ID["BAT+"]))
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
        # FIX: reduce Y offset from +2 to clear VBUS horiz @y=61.
        # R32: +1.0 put the hole exactly on C19.2's edge (the 1206 land is
        # 1.8mm tall, half-height 0.9). +1.30 gives 0.30mm of hole
        # clearance and still leaves 0.52mm to the VBUS F.Cu at y=61.0.
        parts.append(_seg(c19_p2[0], c19_p2[1], c19_p2[0], c19_p2[1] + 1.30,
                          "B.Cu", W_PWR, n_gnd))
        parts.append(_via_net(c19_p2[0], c19_p2[1] + 1.30, n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    # C27 near IP5306 VOUT: HF decoupling at (109, 39), 2.6mm from pin 8.
    # C_0805 pad layout: pad 1 at RIGHT (x+0.95), pad 2 at LEFT (x-0.95).
    # Pad 1 (right, x≈109.95) → GND via DOWN 1.5mm toward EP (same net).
    # Pad 2 (left, x≈108.05) → +5V: short B.Cu LEFT to existing VOUT via (107.5, 39.09).
    c27_p1 = _pad("C27", "1")
    c27_p2 = _pad("C27", "2")
    if c27_p2:
        # Pad 2 (left) → +5V: reuse existing VOUT via at (107.5, 39.09)
        # SW16 respin: C27 is the IP5306 boost's OWN output capacitor —
        # 10uF, 2.0 mm from pin 8 — so it belongs UPSTREAM of Q2, on
        # +5V_VOUT. It has to: with the switch OFF, Q2 opens and this is
        # the only bulk the boost has left. C19's 22uF stays downstream,
        # where it damps the soft-start ramp and feeds the loads.
        # R32: the VOUT barrel this taps moved west, off C27.2's pad (see
        # power.py). The stub follows it; both ends are +5V_VOUT so the
        # run crossing the pad is same-net. 106.05 rather than R32's
        # 106.10 because the barrel stepped another 0.05mm west when its
        # drill grew to 0.45 — power.py::_VOUT_VIA has the arithmetic.
        parts.append(_seg(c27_p2[0], c27_p2[1], 106.05, c27_p2[1],
                          "B.Cu", W_PWR, NET_ID["+5V_VOUT"]))
        parts.append(_seg(106.05, c27_p2[1], 106.05, 39.095,
                          "B.Cu", W_PWR, NET_ID["+5V_VOUT"]))
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
        # R32: 0.7 -> 0.90. The 0805 land grew to the JLC reference and its
        # half-width is now 0.60, so a 0.70mm offset put the hole 0.025mm
        # from the pad edge. 0.90 restores 0.225mm; nearest different-net
        # copper is 1.55mm away, so the extra 0.2mm costs nothing.
        gnd_via_x = led_p1[0] - 0.90
        parts.append(_seg(led_p1[0], led_p1[1], gnd_via_x, led_p1[1],
                          "F.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(gnd_via_x, led_p1[1], n_gnd, size=VIA_STD, drill=VIA_STD_DRILL))

    return parts


def _diag_led_traces():
    """Diagnostic LED bank — workstream H of docs/diagnostic-leds-roadmap.md.

    Three passive rail indicators (LED3/VBUS, LED4/+5V, LED5/+3V3) plus one
    firmware-driven heartbeat (LED6 on LED_HB / GPIO15). Everything is on
    F.Cu in the bottom-right pocket; see the DIAG_* block in _shared.py for
    why the resistors are NOT on B.Cu under their LEDs the way R17/R18 are.

    Per LED, the chain is identical to _led_traces() above:
        rail -> R pad2 (west) | R pad1 (east) -> LEDn_RA -> LED pad2/anode
        LED pad1/cathode -> short west stub -> GND via -> In1.Cu plane
    R28-R31 are placed at rot=180 precisely so that "rail west, _RA east"
    holds, which makes every R->LED link a straight vertical at x+0.95.

    The three rails arrive on their own horizontal lanes, and the lane of
    the LED that drops FURTHEST WEST is the SOUTHMOST, so no drop ever
    crosses another lane:
        VBUS   lane y=47.00, drops at x=133.05  (R28.2)
        +5V    lane y=46.00, drops at x=139.05  (R29.2)
        LED_HB lane y=38.00 area, drops at x=151.05 (R31.2)
    +3V3 needs no lane: R30 taps the In2.Cu plane through a local via.
    """
    parts = []
    _init_pads()
    n_gnd = NET_ID["GND"]

    # ── Per-LED local wiring (R -> LED -> GND) ───────────────────
    for r_ref, led_ref, _rail, ra_name, _label in DIAG_LEDS:
        r_p1 = _pad(r_ref, "1")      # F.Cu rot180: x+0.95 — EAST, _RA side
        led_p1 = _pad(led_ref, "1")  # F.Cu rot0:   x-0.95 — WEST, cathode
        led_p2 = _pad(led_ref, "2")  # F.Cu rot0:   x+0.95 — EAST, anode
        if not (r_p1 and led_p1 and led_p2):
            continue
        n_ra = NET_ID[ra_name]

        # R pad1 -> LED pad2: both at x+0.95, so one straight vertical.
        parts.append(_seg(r_p1[0], r_p1[1], led_p2[0], led_p2[1],
                          "F.Cu", W_SIG, n_ra))

        # Cathode -> GND via. 2.15 mm west of the pad centre: far enough to
        # respect the >=1 mm via-to-pad-centre rule, and the only offset
        # that puts all four vias inside a both-layers-clear window (B.Cu
        # here is the ABXY/SD fan-out — see the DIAG_* comment in _shared).
        gnd_via_x = led_p1[0] - 1.20
        parts.append(_seg(led_p1[0], led_p1[1], gnd_via_x, led_p1[1],
                          "F.Cu", W_PWR_LOW, n_gnd))
        parts.append(_via_net(gnd_via_x, led_p1[1], n_gnd,
                              size=VIA_STD, drill=VIA_STD_DRILL))

    # Every lane below has to get EAST of the FPC slot (x 125.5-128.5,
    # y 23.5-47.5, a board cutout — collision.register_slot). The band
    # immediately south of the slot is the pinch point of this whole layout:
    # between the slot and the U3/L2 buck cluster there is exactly ONE gap
    # wide enough for a trace, at y ~= 49.5. VBUS takes it; +5V enters the
    # corridor east of the pinch; LED_HB goes over the top of the slot.
    # These polylines were found by A* over the actual copper and then
    # clearance-checked — do not "straighten" them without re-running that.

    # ── VBUS: tap the existing F.Cu riser at x=111 ────────────────
    # The riser already carries VBUS from F1/J1 up to U2 (y 40.1..61.0), so
    # this is a branch off existing copper, not a new spur from the
    # connector — no extra load on the fused path.
    r28_p2 = _pad("R28", "2")
    if r28_p2:
        n_vbus = NET_ID["VBUS"]
        # W_VBUS_DIAG, not W_SIG: VBUS is in the "Power High" net class
        # (verify_net_class_widths) with a 0.50 mm floor. The branch itself
        # only carries LED3's 0.59 mA, but the class is a property of the
        # NET, and narrowing it here would be a waiver, not a fix.
        # The branch leaves the riser HORIZONTALLY. Leaving it vertically
        # (a 49.50 -> 49.75 step) doubled back along the riser and JLCDFM
        # read the 0 deg reversal as an acute corner.
        for x1, y1, x2, y2 in (
            (111.00, DIAG_VBUS_TAP_Y, 116.25, DIAG_VBUS_TAP_Y),
            (116.25, DIAG_VBUS_TAP_Y, 116.25, 50.00),
            (116.25, 50.00, 119.75, 50.00),
            (119.75, 50.00, 119.75, 54.00),
            (119.75, 54.00, 121.25, 54.00),
            (121.25, 54.00, 121.25, 54.75),
            (121.25, 54.75, 123.75, 54.75),
            (123.75, 54.75, 123.75, 54.00),
            (123.75, 54.00, r28_p2[0], 54.00),
        ):
            parts.append(_seg(x1, y1, x2, y2, "F.Cu", W_VBUS_DIAG, n_vbus))

    # ── +5V: via into the In2.Cu +5V island ───────────────────────
    # The island is (105,35)-(123,62) — see _power_zones(). The via sits at
    # x=119.75, i.e. 3.25 mm inside its east boundary, deliberately clear of
    # the x=123 edge: R22-CRIT-1 killed a board when vias landed just inside
    # a higher-priority pour and were orphaned from the plane they wanted.
    r29_p2 = _pad("R29", "2")
    if r29_p2:
        n_5v = NET_ID["+5V"]
        # y=48.75, not 49.50: at 49.50 the via barrel came within 0.075 mm
        # of the VBUS corner at (119.75, 50.00) — the two taps share this
        # column because it is the last x still safely inside the island.
        parts.append(_via_net(119.75, 48.75, n_5v, size=VIA_STD, drill=VIA_STD_DRILL))
        for x1, y1, x2, y2 in (
            (119.75, 48.75, 119.75, 49.25),
            (119.75, 49.25, 123.75, 49.25),
            (123.75, 49.25, 123.75, 50.75),
            (123.75, 50.75, 133.25, 50.75),
            (133.25, 50.75, 133.25, 52.50),
            (133.25, 52.50, 136.25, 52.50),
            (136.25, 52.50, 136.25, 54.00),
            (136.25, 54.00, r29_p2[0], 54.00),
        ):
            parts.append(_seg(x1, y1, x2, y2, "F.Cu", W_SIG, n_5v))

    # ── +3V3: local via to the In2.Cu plane ───────────────────────
    # East of V5_EAST=123, so In2.Cu here is the continuous +3V3 pour and a
    # plain via lands on it. (144.25, 51.60) is inside the [143.75, 144.75]
    # both-layers-clear window; a via straight above R30.2 would sit on the
    # BTN_B riser on B.Cu.
    r30_p2 = _pad("R30", "2")
    if r30_p2:
        n_3v3 = NET_ID["+3V3"]
        parts.append(_seg(r30_p2[0], r30_p2[1], r30_p2[0], 51.60,
                          "F.Cu", W_PWR_LOW, n_3v3))
        parts.append(_seg(r30_p2[0], 51.60, 144.25, 51.60, "F.Cu", W_PWR_LOW, n_3v3))
        parts.append(_via_net(144.25, 51.60, n_3v3, size=VIA_STD, drill=VIA_STD_DRILL))

    # ── LED_HB: U1.8 (GPIO15) all the way to R31.2 ────────────────
    # The long one, ~108 mm. It escapes east on B.Cu along the U1.8 pad row,
    # vias up to F.Cu at x=97, and then goes OVER THE TOP of the FPC slot
    # (north to y~20, east past x=140, back south) because the band south of
    # the slot is already spoken for by VBUS and +5V. A 1 Hz LED drive has
    # no signal-integrity stake in the detour; it is purely a space problem.
    r31_p2 = _pad("R31", "2")
    u1_p8 = _pad("U1", "8")
    if r31_p2 and u1_p8:
        n_hb = NET_ID["LED_HB"]
        parts.append(_seg(u1_p8[0], u1_p8[1], 97.00, u1_p8[1], "B.Cu", W_SIG, n_hb))
        parts.append(_via_net(97.00, u1_p8[1], n_hb, size=VIA_STD, drill=VIA_STD_DRILL))
        for x1, y1, x2, y2 in (
            (97.00, u1_p8[1], 123.50, u1_p8[1]),
            (123.50, u1_p8[1], 123.50, 21.00),
            (123.50, 21.00, 129.25, 21.00),
            (129.25, 21.00, 129.25, 19.50),
            (129.25, 19.50, 140.25, 19.50),
            (140.25, 19.50, 140.25, 33.50),
            (140.25, 33.50, 141.00, 33.50),
            (141.00, 33.50, 141.00, 42.50),
            (141.00, 42.50, 144.75, 42.50),
            (144.75, 42.50, 144.75, 43.25),
            (144.75, 43.25, 146.25, 43.25),
            (146.25, 43.25, 146.25, 52.50),
            (146.25, 52.50, 148.25, 52.50),
            (148.25, 52.50, 148.25, 54.00),
            (148.25, 54.00, r31_p2[0], 54.00),
        ):
            parts.append(_seg(x1, y1, x2, y2, "F.Cu", W_SIG, n_hb))

    return parts
