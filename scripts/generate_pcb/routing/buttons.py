"""Split from routing.py 2026-07-26 — mechanical, AST-driven, proven by a
byte-identical regenerated .kicad_pcb. One domain per module; every helper
and every constant lives in _shared (original order, so import-time
execution is unchanged). See routing/__init__.py for the contract."""
from ._shared import (
    ABXY,
    C3_POS,
    CC1_FCU_Y,
    CX,
    DPAD,
    J1_FRONT_PAD_BOTTOM,
    J1_FRONT_PAD_TOP,
    J1_REAR_PAD_TOP,
    J1_SHIELD_HALF_W,
    J1_SHIELD_XS,
    NET_ID,
    SHOULDER_L,
    SLOT_X1,
    SLOT_X2,
    SLOT_Y1,
    SLOT_Y2,
    SS,
    VIA_MIN,
    VIA_MIN_DRILL,
    VIA_STD,
    VIA_STD_DRILL,
    VIA_TIGHT,
    VIA_TIGHT_DRILL,
    W_DATA,
    W_J1_BYPASS,
    W_PWR_LOW,
    W_SIG,
    _MENU_BTN_SELECT_COL_X,
    _MENU_BTN_SELECT_VIA_Y,
    _MENU_BTN_START_COL_X,
    _MENU_K_COL_X,
    _MENU_K_CORRIDOR_Y,
    _MENU_K_RISER_X,
    _PAD_NETS,
    _crosses_j1_front_shield,
    _esp_pin,
    _init_pads,
    _pad,
    _pad_box,
    _pu_jog_vert,
    _seg,
    _via_net,
)

# Where BTN_B's B.Cu run out of the C3 channel rejoins its own F.Cu stagger
# horizontal. Read by both producers — the stagger loop, which splits the
# horizontal here, and _bottom_button_r_traces(), which drops the stub onto
# it — because when the two disagreed the stub landed mid-segment and read
# as dangling copper.
BTN_B_TAP_X = 69.55


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
    # R21 (2026-07-25): was hardcoded 70.375, which had already drifted
    # (the real edge was 70.425). Now derived from the footprint.
    _J1_FRONT_PAD_BOTTOM = J1_FRONT_PAD_BOTTOM  # front shield pad bottom edge
    for i, b in enumerate(btn_data):
        if i <= 5:
            # Channels 0-5: normal spacing below J1 pad zone
            b["chan_y"] = 62.0 + i * 1.2
        elif i <= 7:
            # Channels 6-7 (BTN_X, BTN_Y): jump over J1 front pads.
            # R9-HIGH-4 FIX (2026-04-11): reverted ch6 from 70.65 back to 70.80.
            # The old 70.65 position was a compromise for SW16.4b clearance
            # (SW16.4b at (36.40, 71.40), BTN_X approach via at (36.55, 70.65)
            #  had only 0.15 mm gap). But 70.65 was 0.15 mm from J1 front pad
            # bottom (70.375), also failing the 0.20 mm rule.
            # Proper fix: move the BTN_X approach column (ax) WEST of SW16
            # entirely (override below) so the SW16 constraint no longer
            # forces a low chan_y. With ax=34.30, via (34.30, 70.80) is
            # 2.10 mm west of SW16.4b center → clears by 1.35 mm ✓.
            # Gap to J1 front pad bottom (70.375): 70.80-0.125-70.375=0.30 mm ✓.
            # Gap to ch7 (71.55): 0.625 mm ✓.
            k = i - 6  # 0, 1
            b["chan_y"] = _J1_FRONT_PAD_BOTTOM + 0.125 + 0.30 + k * 0.75  # 70.80, 71.55
        elif i == 8:
            # Channel 8 (BTN_START): ABOVE SW16 NPTH zone AND shoulder GND/BTN_L vias.
            # DFM FIX: moved from 74.06 to 73.955 to allow ch9 above with edge clearance.
            # ch8 at 73.955: gap to BTN_L via(73.43,r=0.25) = 73.955-0.125-73.43-0.25=0.15mm ✓
            # gap to NPTH(38.5,72.55,r=0.45): trace bottom=73.83, NPTH top=73.00 → 0.83mm ✓
            b["chan_y"] = 73.955
        else:
            # Channel 9 (BTN_SELECT): above BTN_START
            # DFM FIX: ch9 moved from 74.46 to 74.25 for board edge clearance.
            # gap to ch8 F.Cu(73.955) = 74.25-0.227-73.955-0.125=−0.057mm... TOO CLOSE
            # Need ch9 > 73.955+0.125+0.227+0.15 = 74.457. At 74.46:
            # edge gap = 75.0-74.46-0.227=0.313mm < 0.50mm (KiCad rule).
            # JLCPCB actual min edge clearance is 0.30mm. Accept 0.31mm.
            b["chan_y"] = 74.46

    # Assign approach columns near ESP32
    # Avoid passive pull-up traces at x = 43+i*5 ± 0.95, y=46-50
    # R9-MED-4: loop still covers 13 slots for defensive reservation of
    # the ex-R19/C20 x=103 column; active components are R4-R15/C5-C16
    # (12 buttons). Keeping the extra slot reserved prevents future
    # routing from accidentally using 103.95/102.05 without re-audit.
    passive_trace_xs = {43 + i * 5 + 0.95 for i in range(13)}
    passive_trace_xs |= {43 + i * 5 - 0.95 for i in range(13)}
    # SHORT FIX: also forbid LED current-limit +3V3 stub positions.
    # R17[1] at x=25.95, R18[1] at x=32.95: B.Cu +3V3 vert from y=63 to y=65.
    # Any approach column B.Cu vert at these X values crosses the stub → short circuit.
    passive_trace_xs |= {25.95, 32.95}

    # DFM FIX: pull-up/debounce PAD forbidden zones for approach columns.
    # 24 active components (R4-R15 at y=46 + C5-C16 at y=50) densely packed
    # at 5mm spacing across x=43-98. The 13th slot at x=103 is defensively
    # reserved (ex-R19/C20 position, removed in R9-MED-4).
    # 0805 pad_hw=0.50mm, approach trace hw=0.125mm, gap=0.15mm → radius=0.775mm.
    _pu_pad_centers = []
    for _i in range(13):
        _pcx = 43 + _i * 5
        _pu_pad_centers.append(_pcx - 0.95)  # pad "2" center
        _pu_pad_centers.append(_pcx + 0.95)  # pad "1" center
    # C3 decoupling cap near ESP32
    _pu_pad_centers.append(C3_POS[0] - 0.95)  # C3 pad "2"
    _pu_pad_centers.append(C3_POS[0] + 0.95)  # C3 pad "1"
    # R3 removed — its pads at (64.05, 65.95) previously overlapped BTN_DOWN
    # approach column at x=65.55. No longer an issue.
    _PU_PAD_FORBIDDEN_R = 0.80   # pad_hw(0.50) + trace_hw(0.125) + gap(0.175)
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
            # DFM FIX: check pull-up/debounce pad zones (tighter clearance than trace endpoints)
            for _pc in _pu_pad_centers:
                if abs(ax - _pc) < _PU_PAD_FORBIDDEN_R:
                    # Push to nearest safe channel center (midpoint between components)
                    # Component centers at cx=43+5k. Pad centers at cx±0.95.
                    # Safe channel center: cx+2.50 or cx-2.50
                    _nearest_cx = round(((_pc + 0.95 if _pc % 5 > 2 else _pc - 0.95) + 0.95) / 5) * 5 + 43 - (43 % 5)
                    # Simpler: find which component this pad belongs to
                    _comp_cx = round((_pc + 0.95) if abs((_pc + 0.95) % 5 - 0) < 1 else (_pc - 0.95))
                    # Round to nearest 5mm grid
                    _comp_cx = round((_pc + 0.95) / 5) * 5 if abs((_pc + 0.95) % 5) < 1.5 else round((_pc - 0.95) / 5) * 5
                    # Push toward safe channel
                    if ax > _pc:
                        ax = _pc + _PU_PAD_FORBIDDEN_R + 0.05
                    else:
                        ax = _pc - _PU_PAD_FORBIDDEN_R - 0.05
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

    # R9-HIGH-4 FIX (2026-04-11): force BTN_X approach column WEST of SW16.
    #
    # Problem: the default allocator placed BTN_X (SW7, i=6) at ax=36.55 —
    # inside the SW16 footprint body (x=35.8..44.2). BTN_X F.Cu channel
    # trace at y=70.80 crosses the B.Cu SW16.4b (BTN_SELECT) pad at
    # (36.40, 71.40) on a different layer — no F.Cu conflict there, but the
    # approach via at (36.55, 70.80) has BOTH F.Cu and B.Cu annuli, and the
    # B.Cu side was 0.15 mm from SW16.4b. Also the 93.28 mm BTN_X F.Cu
    # horizontal from vx=129.83 west to ax=36.55 crossed J1 shield front
    # pads J1.13/14 at y=69.375 with only 0.15 mm clearance.
    #
    # Fix: override BTN_X ax to 34.30 — west of SW16 body left edge
    # (35.80) by 1.50 mm. The B.Cu approach-column vertical at x=34.30 is
    # clear of SW16 pad 3 (37.75), pad 2 (39.25), and all 4x pads.
    #
    # This does not change the F.Cu 93.28 mm horizontal length noticeably
    # (34.30 vs 36.55 is 2.25 mm) but removes the via conflict and lets
    # chan_y move back to 70.80 for J1 front-pad clearance (≥0.30 mm).
    for b in btn_data:
        if b["ref"] == "SW7":   # BTN_X
            b["approach_x"] = 34.30
            break
    used_approach_xs.add(34.30)

    # NOTE: BTN_UP (ax=67.72) and BTN_START (ax=64.60) have borderline clearance
    # to R9/C10 and R8/C9 pads (gap=0.045-0.050mm vs 0.09mm JLCPCB min).
    # Post-allocation nudging creates cascading collisions with neighboring
    # approach columns. Fixing requires a global approach column redesign.

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

    # DFM FIX: post-allocation approach-to-pad clearance enforcement.
    # Approach columns (B.Cu verticals at approach_x) span from channel Y to ESP32
    # and can pass too close to passive pads if the allocation loop oscillated.
    # Trace hw = 0.125 (W_SIG), pad hw = 0.50 (0805), gap = 0.15mm JLCPCB min.
    _AX_PAD_MIN = 0.50 + 0.125 + 0.15 + 0.01  # 0.785mm from pad center
    for bi in range(len(btn_data)):
        ax = btn_data[bi]["approach_x"]
        # Iterate until no conflicts or max 20 iterations to escape oscillation
        for _ in range(20):
            conflict = False
            for _pc in _pu_pad_centers:
                if abs(ax - _pc) < _AX_PAD_MIN:
                    # Push approach AWAY from pad center (whichever side ax is on)
                    if ax >= _pc:
                        ax = round(_pc + _AX_PAD_MIN, 2)
                    else:
                        ax = round(_pc - _AX_PAD_MIN, 2)
                    conflict = True
                    break  # re-check all pads from start
            if not conflict:
                break
        btn_data[bi]["approach_x"] = ax

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
            # DFM FIX: check if B.Cu vertical at vx crosses a pull-up/debounce
            # pad (y=46/50 zone, pads at cx±0.95 for cx=43,48,...,103).
            # If so, jog through the nearest safe channel between components.
            _pu_jog_x = None
            _PAD_HW = 0.50      # 0805 pad half-width
            _TR_HW = 0.125      # W_SIG/2
            _MIN_GAP = 0.15     # JLCPCB min clearance
            _FORBIDDEN_R = _PAD_HW + _TR_HW + _MIN_GAP  # 0.775mm
            for _pi in range(13):
                _pcx = 43 + _pi * 5
                for _pad_cx in [_pcx - 0.95, _pcx + 0.95]:
                    if abs(vx - _pad_cx) < _FORBIDDEN_R:
                        # Jog to nearest channel center (midpoint between components)
                        _ch_left = _pcx - 2.50   # center of gap to LEFT component
                        _ch_right = _pcx + 2.50  # center of gap to RIGHT component
                        _pu_jog_x = _ch_left if abs(vx - _ch_left) < abs(vx - _ch_right) else _ch_right
                        break
                if _pu_jog_x is not None:
                    break

            parts.extend(_pu_jog_vert(vx, spy, cy, W_SIG, net))
        parts.append(_via_net(vx, cy, net, size=_btn_via_sz, drill=_btn_via_drill))

        # 3. F.Cu: horizontal to approach column
        # J1 shield pad avoidance: channels 6-7 (BTN_X, BTN_Y) are now assigned
        # to y=70.8/71.55 (between front/rear J1 shield pads), avoiding the
        # J1 front pad zone entirely. No bypass needed.
        #
        # BTN_START (i=8, cy=73.955) F.Cu bypass around J1 rear shield THT pads:
        # Pad 14b at (75.67, 73.58) pad 1.4x1.8mm → x=[74.97, 76.37], y=[72.68, 74.48]
        # Pad 13b at (84.33, 73.58) pad 1.4x1.8mm → x=[83.63, 85.03], y=[72.68, 74.48]
        # Trace at y=73.955 passes through both pads.
        # R9-HIGH-5 FIX (2026-04-11): bypass_y was 72.38, giving a 0.17 mm
        # edge gap to the pad top at 72.675 (below 0.20 mm rule). Shift to
        # 72.30: gap = 72.675 - 72.30 - 0.125 = 0.25 mm ✓. Gap to ch7 BTN_Y
        # (71.55 with R9-HIGH-4 fix): 72.30 - 0.125 - 71.55 - 0.125 = 0.50 mm ✓.
        if i == 8:  # BTN_START — bypass J1 rear shield pads 14b and 13b
            # R21 (2026-07-25): derived from J1_REAR_PAD_TOP instead of the
            # old literal 72.30, which assumed a 1.80 mm-tall rear pad. The
            # pad is now 1.92 mm (JLCPCB annular ring) and 0.05 mm higher,
            # so its top edge moved from 72.675 to 72.565 and the literal
            # would have left only 0.14 mm instead of the required 0.20 mm.
            # Lower bound is the channel-7 approach vias at y=71.56
            # (r=0.275 -> bottom 71.835): 72.20 - 0.125 = 72.075, gap 0.24 mm.
            _bypass_y = round(J1_REAR_PAD_TOP - 0.20 - W_SIG / 2 - 0.04, 3)
            _rear_l, _rear_r = J1_SHIELD_XS
            # Jog columns: pad edge + trace half width + 0.20 clearance + margin
            _jog_off = J1_SHIELD_HALF_W + W_SIG / 2 + 0.20 + 0.28
            _p14b_jog_start = round(_rear_l - _jog_off, 3)
            _p14b_jog_end = round(_rear_l + _jog_off, 3)
            _p13b_jog_start = round(_rear_r - _jog_off, 3)
            _p13b_jog_end = round(_rear_r + _jog_off, 3)
            # Segment order: vx → pad14b_jog_start → bypass14b → pad14b_jog_end →
            #                pad13b_jog_start → bypass13b → pad13b_jog_end → ax
            # All segments at cy=73.955 except bypasses at _bypass_y=72.38
            # R13-CU-CLR FIX (2026-04-12): BTN_START F.Cu at y=73.955
            # (top edge 74.08 at W_SIG) meets the BTN_SELECT approach vias
            # at (35.95, 74.46) and (60.45, 74.46) bottom edge 74.23 with
            # exactly 0.150mm gap — at the verify_copper_clearance threshold
            # (violation #1). Use W_DATA (0.20) on the long W-E span that
            # runs just above y=73.83 to y=74.08 to give 0.175mm gap:
            #   top edge at W_DATA = 73.955+0.10 = 74.055 → gap 0.175 ✓.
            # BTN_START is a low-speed digital input, W_DATA is sufficient.
            parts.append(_seg(vx, cy, _p14b_jog_start, cy, "F.Cu", W_DATA, net))
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
        elif _crosses_j1_front_shield(vx, ax, cy, W_SIG):
            # BTN_B (channel 5, y=68.0) — bypass J1 FRONT shield pads.
            #
            # R21 (2026-07-25). The front shield pads had to grow from
            # 2.10 to 2.12 mm tall for a JLCPCB-legal 0.25 mm annular ring
            # and their top edge is now 68.265, only 0.14 mm below this
            # channel's bottom edge at full W_SIG. Rather than move the
            # whole channel plan, step over the two pads exactly the way
            # channel 8 steps over the rear pads.
            #
            # Bypass Y is pinned between two hard obstacles:
            #   above — the CC1 via at (74.95, 67.40), VIA_STD r=0.30, so
            #           bottom edge 67.70. It sits inside the left pad's
            #           bypass window in X, so it cannot be dodged.
            #   below — the front shield pad top edge at 68.265.
            # That is a 0.565 mm window and it must hold 0.20 mm + trace +
            # 0.20 mm, hence the narrowed W_J1_BYPASS. Widening this trace
            # or lowering the CC1 via re-breaks the annular ring. The real
            # v2 fix is to move R1 (and its via) out of this corridor.
            _cc1_via_bottom = CC1_FCU_Y + VIA_STD / 2          # 67.70
            _fb_y = round((_cc1_via_bottom + 0.20 + W_J1_BYPASS / 2
                           + J1_FRONT_PAD_TOP - 0.20 - W_J1_BYPASS / 2) / 2, 3)
            _fb_off = J1_SHIELD_HALF_W + W_J1_BYPASS / 2 + 0.20 + 0.10
            _l, _r = J1_SHIELD_XS
            _windows = sorted(
                [(round(_l - _fb_off, 3), round(_l + _fb_off, 3)),
                 (round(_r - _fb_off, 3), round(_r + _fb_off, 3))]
            )
            _lo, _hi = min(vx, ax), max(vx, ax)
            _cursor = _lo
            for _wx0, _wx1 in _windows:
                parts.append(_seg(_cursor, cy, _wx0, cy, "F.Cu", W_SIG, net))
                parts.append(_seg(_wx0, cy, _wx0, _fb_y,
                                   "F.Cu", W_J1_BYPASS, net))
                parts.append(_seg(_wx0, _fb_y, _wx1, _fb_y,
                                   "F.Cu", W_J1_BYPASS, net))
                parts.append(_seg(_wx1, _fb_y, _wx1, cy,
                                   "F.Cu", W_J1_BYPASS, net))
                _cursor = _wx1
            parts.append(_seg(_cursor, cy, _hi, cy, "F.Cu", W_SIG, net))
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
            parts.extend(_pu_jog_vert(ax, cy, stagger_y, W_SIG, net))
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
            # The layer change normally happens on the stagger lane itself.
            # A button whose channel is too tight there may pull it off the
            # lane (see BTN_SELECT below); jog segments are then emitted on
            # both layers so the lane geometry stays as it is.
            _ne_via_y = stagger_y
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
                # MEASURED, not transcribed. The literal that used to sit
                # here — (73.45, 45.35, 74.45, 46.65) — described the 1.0 x
                # 1.3 land R10 had before the 0805 footprint moved to the
                # JLC reference. Every shift computed off it was 0.075 mm
                # optimistic in x, which is how the barrel below ended up
                # 0.1819 mm from the pad against a 0.2 mm netclass rule.
                R10_PAD_AABB = _pad_box("R10", "1")
                _ne_r = VIA_STD / 2
                _ne_box = (_ne - _ne_r, stagger_y - _ne_r,
                           _ne + _ne_r, stagger_y + _ne_r)
                _dx = max(0, R10_PAD_AABB[0] - _ne_box[2],
                          _ne_box[0] - R10_PAD_AABB[2])
                _dy = max(0, R10_PAD_AABB[1] - _ne_box[3],
                          _ne_box[1] - R10_PAD_AABB[3])
                _r10_gap = _m.sqrt(_dx**2 + _dy**2)
                if _r10_gap < 0.15:
                    # The channel between R10's two pads is 0.75 mm wide and
                    # no legal barrel fits in it: KiCad resolves via-to-pad
                    # against the Default netclass at 0.2 mm (the .kicad_dru
                    # relaxation to 0.09 mm is conditioned on A.Type ==
                    # 'track'), so the ring may be at most 0.35 mm OD —
                    # under the 0.45 mm via floor the same .kicad_dru sets.
                    # Shrinking the barrel, which is what every previous fix
                    # here did, therefore cannot succeed.
                    #
                    # Centre it in the channel and drop it 0.5 mm SOUTH of
                    # the stagger lane instead, clear of the pad row
                    # entirely: from (73.00, 44.60) the nearest pad corner
                    # is sqrt(0.375^2 + 0.725^2) = 0.816 mm away, so a
                    # 0.46 mm ring keeps 0.586 mm. The lane itself does not
                    # move — the F.Cu approach still arrives at stagger_y
                    # (0.175 mm from the +3V3 via at (70.45, 44.50), which
                    # is the binding constraint up there) and short jogs on
                    # both layers carry the transition down and back.
                    _ne_via_size = 0.46
                    _ne_via_drill = 0.20
                    _r10_box = _pad_box("R10", "2")
                    _ne = round((_r10_box[2] + R10_PAD_AABB[0]) / 2, 3)  # 73.00
                    _ne_via_y = 44.60
                near_epx = _ne
            else:
                # DFM v3: BTN_R approach via@(91.0,37.48) vs near_epx via@(90.0,37.48): gap=0.1mm.
                # epx+2.0 would place near_epx at epx+2 (90→92 for BTN_R), but approach is at epx+2.8+i.
                # For BTN_R (i=0 for right-side buttons), approach≈91.55. Distance to near_epx=92:
                # 92-91.55=0.45mm gap (size 0.9 each) → insufficient. Use epx+3.0: 93-91.55=1.45, gap=0.55mm ✓
                near_epx = epx + 3.0   # DFM: was +2.0 (0.1mm gap to approach via)
                _ne_via_size = VIA_STD
                _ne_via_drill = VIA_STD_DRILL
            # BTN_B's escape from the C3 channel drops an F.Cu stub onto
            # this horizontal at BTN_B_TAP_X. Split it there: dangling-copper
            # counts segment ENDPOINTS, so a stub that merely crosses another
            # segment's interior reads as copper stopping in the air.
            _taps = [x for x in (BTN_B_TAP_X,)
                     if net == NET_ID["BTN_B"]
                     and min(ax, near_epx) < x < max(ax, near_epx)]
            _nodes = [ax] + sorted(_taps, reverse=ax > near_epx) + [near_epx]
            for _xa, _xb in zip(_nodes, _nodes[1:]):
                parts.append(_seg(_xa, stagger_y, _xb, stagger_y,
                                  "F.Cu", W_SIG, net))
            if abs(_ne_via_y - stagger_y) > 1e-6:
                # Layer change pulled off the lane — jog down on F.Cu, land
                # the barrel, jog back up on B.Cu so the horizontal below
                # still starts at (near_epx, stagger_y).
                parts.append(_seg(near_epx, stagger_y, near_epx, _ne_via_y,
                                  "F.Cu", W_SIG, net))
            parts.append(_via_net(near_epx, _ne_via_y, net,
                                  size=_ne_via_size, drill=_ne_via_drill))
            if abs(_ne_via_y - stagger_y) > 1e-6:
                parts.append(_seg(near_epx, _ne_via_y, near_epx, stagger_y,
                                  "B.Cu", W_SIG, net))
            # B.Cu: horizontal to pad X, then vertical to pad Y (no extra via)
            # R13-CU-CLR FIX (2026-04-12): BTN_SELECT (SW10) B.Cu horizontal
            # at y=stagger_y=45.10 passes R10.2 +3V3 pad bottom (y=45.35)
            # with only 0.125mm gap at W_SIG (W_SIG hw=0.125 → top 45.225).
            # Narrow the full horizontal stub to 0.18 → top edge 45.190
            # → gap 0.160mm ✓. Same for the vertical stub that goes through
            # C3.1 (violation #5 in verify_copper_clearance).
            _SEL_W = 0.18 if b["ref"] == "SW10" else W_SIG
            parts.append(_seg(near_epx, stagger_y, epx, stagger_y,
                              "B.Cu", _SEL_W, net))
            if b["ref"] == "SW10":  # BTN_SELECT
                # Entire BTN_SELECT vertical stub tapered to 0.18 to clear
                # both C3.1 (violation #5 at y=42.65) and R10.2 (new
                # violation at y=45.35). Also handles the stagger horizontal
                # above. Stub length ~6.35mm; 0.18mm trace for a button
                # signal is well within W_DATA (0.20) budget.
                #
                # R32 (2026-08-03): the taper alone stopped being enough
                # once the 0805 land grew to the JLC reference width —
                # C3.1's east edge moved 68.025→71.075 side to 71.075 and
                # left 0.085mm, a verify_copper_clearance DANGER. The stub
                # now steps 0.15mm EAST while it passes C3's pad row
                # (y=41.325..42.675), which buys 0.235mm there. It steps
                # back before y=41.0 so the run into the ESP32 pad at
                # x=71.25 is unchanged, and the step band stays clear of
                # R10.2 (pad row starts at y=45.325).
                _TAPER_W = 0.18
                _c3_step_x = epx + 0.15
                _c3_step_top = 43.0    # C3 pads start at y=41.325
                _c3_step_bot = 41.0    # ... and end at y=42.675
                parts.append(_seg(epx, stagger_y, epx, _c3_step_top,
                                  "B.Cu", _TAPER_W, net))
                parts.append(_seg(epx, _c3_step_top, _c3_step_x, _c3_step_top,
                                  "B.Cu", _TAPER_W, net))
                parts.append(_seg(_c3_step_x, _c3_step_top, _c3_step_x, _c3_step_bot,
                                  "B.Cu", _TAPER_W, net))
                parts.append(_seg(_c3_step_x, _c3_step_bot, epx, _c3_step_bot,
                                  "B.Cu", _TAPER_W, net))
                parts.append(_seg(epx, _c3_step_bot, epx, epy,
                                  "B.Cu", _TAPER_W, net))
            else:
                parts.append(_seg(epx, stagger_y, epx, epy,
                                  "B.Cu", W_SIG, net))
        else:
            # B.Cu vertical to ESP32 Y level
            if abs(ax - epx) < 1.5:
                # DFM: approach column close to ESP32 pad — route B.Cu
                # directly to pad to avoid hole_to_hole violation
                parts.extend(_pu_jog_vert(ax, cy, epy, W_SIG, net))
                if abs(ax - epx) > 0.01:
                    parts.append(_seg(ax, epy, epx, epy,
                                      "B.Cu", W_SIG, net))
            else:
                # R13-CU-CLR FIX (2026-04-12): BTN_UP (SW1) approach column
                # vert at x=ax=67.83 squeezes between R9.2/C10.2 pads and
                # C3.2's GND pad. Taper the y-band across C3 from W_SIG
                # (0.25) to 0.18 (hw=0.09).
                # C3 pad y-range: 41.325..42.675. Taper band y=[40.8, 43.2].
                #   Right edge 67.92 → gap to C3.2 (west edge 68.025) = 0.105mm
                #   Left edge  67.74 → nothing west of it until x≈67.0
                #
                # R32 (2026-08-03): the 0805 land grew to the JLC reference
                # width (1.0 → 1.15), which moved R9.2 / C10.2's east edge
                # from 67.55 to 67.625 and left the full-width column only
                # 0.080mm away — a verify_copper_clearance DANGER. The
                # column now steps EAST to the centre of that channel
                # while it crosses the two 0805 rows: R9/C10's pads bound
                # it at 67.625 (pad 2) and 68.375 (pad 1), so x=68.00 is
                # 0.25mm clear on both sides. It steps back afterwards so
                # the south bridge via and the button pad tap keep their
                # proven x.
                if b["ref"] == "SW1":  # BTN_UP
                    _c3_y_top = 40.8
                    _c3_y_bot = 43.2
                    _rows_y_top = 44.9    # above R9's pad row (45.325)
                    _rows_y_bot = 51.1    # below C10's pad row (50.675)
                    _rows_x = 68.00       # centred in the 0.75mm pad channel
                    # R32: the taper also steps 0.15mm WEST across C3.
                    # C3.2's pad grew to the JLC reference land and its
                    # west edge moved to 68.025, leaving the 0.18mm taper
                    # 0.105mm — under JLCPCB's 0.127mm floor. Nothing sits
                    # west of x=67.6 in this y band, so the step is free
                    # and buys 0.255mm.
                    _c3_x = ax - 0.15     # 67.68
                    _TAPER_W = 0.18
                    y_lo, y_hi = min(cy, epy), max(cy, epy)
                    if y_lo < _c3_y_top < y_hi:
                        parts.append(_seg(ax, y_lo, ax, _c3_y_top,
                                          "B.Cu", W_SIG, net))
                        parts.append(_seg(ax, _c3_y_top, _c3_x, _c3_y_top,
                                          "B.Cu", _TAPER_W, net))
                        parts.append(_seg(_c3_x, _c3_y_top, _c3_x, _c3_y_bot,
                                          "B.Cu", _TAPER_W, net))
                        parts.append(_seg(_c3_x, _c3_y_bot, ax, _c3_y_bot,
                                          "B.Cu", _TAPER_W, net))
                        parts.append(_seg(ax, _c3_y_bot, ax, _rows_y_top,
                                          "B.Cu", W_SIG, net))
                        # Step east across the R9/C10 rows and back.
                        # The jog horizontals sit 0.30mm clear of the
                        # nearest pad edge (45.325 / 50.675).
                        parts.append(_seg(ax, _rows_y_top, _rows_x, _rows_y_top,
                                          "B.Cu", W_SIG, net))
                        parts.append(_seg(_rows_x, _rows_y_top, _rows_x, _rows_y_bot,
                                          "B.Cu", W_SIG, net))
                        parts.append(_seg(_rows_x, _rows_y_bot, ax, _rows_y_bot,
                                          "B.Cu", W_SIG, net))
                        parts.append(_seg(ax, _rows_y_bot, ax, y_hi,
                                          "B.Cu", W_SIG, net))
                    else:
                        parts.extend(_pu_jog_vert(ax, cy, epy, W_SIG, net))
                else:
                    parts.extend(_pu_jog_vert(ax, cy, epy, W_SIG, net))
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
    # DFM FIX: was 64.60 — trace left edge (64.50) only 0.050mm from R8[1]/C9[1]
    # pad right edge (64.45).  Need ≥0.15mm gap.  At 64.75: left edge=64.65,
    # gap to pad=64.65-64.45=0.20mm ✓.  Gap to BTN_DOWN vert at 65.55:
    # 65.55-0.125-(64.75+0.10)=0.575mm ✓.
    # R32: 64.75 -> 64.80. The 0805 land grew to the JLC reference, moving
    # R8.1/C9.1's east edge to 64.525 and leaving 0.125mm. BTN_DOWN's
    # vertical at x=65.55 is 0.525mm east, so the 0.05mm step is free.
    approach_l = 64.80
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
    # R32 (2026-08-03): the F.Cu used to run all the way down to epy_l and
    # drop a barrel on U1.26's pad centre. That is the JLCDFM "lead to hole
    # distance 0mm" DANGER — a hole under a module castellation wicks the
    # joint dry. The module's pads are 1.27mm apart in y, so the barrel
    # steps NORTH off the pad's top edge (39.25) instead: 0.250mm of hole
    # clearance, 0.592mm of copper to U1.25 and 0.715mm to U1.27, and the
    # last 1.1mm into the pad runs on B.Cu.
    _btn_l_via_y = 38.90
    parts.append(_seg(epx_l, btn_l_fcu_y, epx_l, _btn_l_via_y,
                       "F.Cu", W_DATA, net_l))
    # R6 FIX (2026-04-10): missing via-in-pad at U1:26 (GPIO45, B.Cu).
    # Without this via, the F.Cu trace ends at (epx_l, epy_l) on the wrong
    # layer and never touches the ESP32 pad on B.Cu. The L shoulder button
    # has been electrically non-functional since v3.1. Detected by
    # verify_net_connectivity.py: BTN_L showed U1.26 as an isolated
    # component. via-in-pad on a 0.9x1.5mm SMD pad is acceptable for an
    # ESP32-S3 module (solder-mask-defined pad, standard assembly practice).
    parts.append(_via_net(epx_l, _btn_l_via_y, net_l, size=VIA_STD, drill=VIA_STD_DRILL))
    parts.append(_seg(epx_l, _btn_l_via_y, epx_l, epy_l,
                       "B.Cu", W_DATA, net_l))
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
        # R31-HIGH-2: this column used to run straight from the SW12 bridge
        # to the channel via at (146.85, 65.29), and on the way it crossed
        # U6 pad 9 — trace west edge 146.725 against pad east edge 146.81,
        # an 0.085 mm merge. It was silenced with a same-net _PAD_NETS entry
        # justified as "DAT2, tri-stated in SPI mode". Pad 9 is not DAT2. A
        # microSD card has EIGHT contacts; the ninth pad on this socket is
        # the card-DETECT spring, which mates with the grounded shell. In
        # one card state that pad is a short to GND, so the same-net trick
        # was tying the R shoulder button to ground — most plausibly
        # whenever a card is inserted, i.e. during all gameplay.
        #
        # So the copper moves rather than the declaration: east around the
        # whole pad row and the pad-10 shield tab, through the open lane
        # between the pad-10 GND stitch (east edge 149.06) and the SD_CLK
        # column (x=152.5), then back west to the unchanged channel via.
        # Note the gap between pads 9 and 10 (146.81 -> 147.16, 0.35 mm) is
        # too narrow to thread — going east means going east of pad 10.
        # Clearances on the detour (W_SIG half-width 0.125):
        #   exit y=60.0: U6 pad row top 61.074 -> 0.949mm
        #   riser x=149.6: pad-10 GND via (148.76) east edge 149.06 -> 0.415mm
        #                  pad 10 east edge 148.36 -> 1.115mm
        #                  SD_CLK column west edge 152.40 -> 2.675mm
        #   return y=64.5: pad 10 bottom 63.274 -> 1.101mm
        #                  GND via (148.0, 66.5) top 66.20 -> 1.575mm
        _u6_detour_exit_y = 60.0    # above U6's signal pad row
        _u6_detour_x = 149.6        # east of the pad-10 shield tab and its via
        _u6_detour_return_y = 64.5  # below the shield tab, above the channel via
        parts.append(_seg(sx_r, _sw12_bridge_y2, sx_r, _u6_detour_exit_y,
                           "B.Cu", W_SIG, net_r))
        parts.append(_seg(sx_r, _u6_detour_exit_y, _u6_detour_x, _u6_detour_exit_y,
                           "B.Cu", W_SIG, net_r))
        parts.append(_seg(_u6_detour_x, _u6_detour_exit_y, _u6_detour_x, _u6_detour_return_y,
                           "B.Cu", W_SIG, net_r))
        parts.append(_seg(_u6_detour_x, _u6_detour_return_y, sx_r, _u6_detour_return_y,
                           "B.Cu", W_SIG, net_r))
        parts.append(_seg(sx_r, _u6_detour_return_y, sx_r, chan_y_r,
                           "B.Cu", W_SIG, net_r))
        parts.append(_via_net(sx_r, chan_y_r, net_r, size=VIA_STD, drill=VIA_STD_DRILL))
        # DFM v6: approach_r at x=76.20 with F.Cu L-shape jog to x=66.00.
        # The ESP32 area (x=67-77) is heavily congested: U1:23 pads, SPI vias,
        # GND verts, D-pad approach stubs. Route bypasses everything on F.Cu,
        # then B.Cu vert at x=66.00 (left of BTN_DOWN vert at 67.45 by 1.2mm,
        # left of all D-pad approach stubs). B.Cu stub at y=27.32 goes RIGHT
        # 5.25mm to ESP32 pad at (71.25, 27.32) — no B.Cu obstacles at this Y
        # (BTN_L vert ends at y=28.59, BTN_DOWN ends at y=29.86).
        approach_r = 76.20
        # JLCDFM FIX: BTN_R F.Cu jog around SW13 (menu button) pads
        # 3,4 at (139/145, 63.55) size 1.2x0.9mm. Pad bottom edge=64.00.
        # SW13 pads now on GND net → need different-net clearance (0.15mm).
        # Trace at W_DATA=0.2mm: half_w=0.1mm. Need y >= 64.00+0.10+0.15 = 64.25.
        # Use y=64.50 for margin. USB D- at y=64.58 is outside jog x range.
        _sw13_jog_y = 64.50
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
        # J3.3 mech tab at board (76.65, 56.65) size 1.5×3.4mm.
        # BTN_R B.Cu vert at x=76.20 must jog west around the tab.
        # Tab AABB: x=[75.90,77.40], y=[54.95,58.35].
        _j3_tab_top = 58.35 + 0.50   # 0.50mm clearance above tab
        _j3_tab_bot = 54.95 - 0.50   # 0.50mm clearance below tab
        _j3_jog_x = 75.20            # west of tab left edge 75.90
        parts.append(_seg(approach_r, chan_y_r, approach_r, _j3_tab_top,
                           "B.Cu", W_DATA, net_r))
        parts.append(_seg(approach_r, _j3_tab_top, _j3_jog_x, _j3_tab_top,
                           "B.Cu", W_DATA, net_r))
        parts.append(_seg(_j3_jog_x, _j3_tab_top, _j3_jog_x, _j3_tab_bot,
                           "B.Cu", W_DATA, net_r))
        parts.append(_seg(_j3_jog_x, _j3_tab_bot, approach_r, _j3_tab_bot,
                           "B.Cu", W_DATA, net_r))
        parts.append(_seg(approach_r, _j3_tab_bot, approach_r, btn_r_jog_y,
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


def _reset_boot_traces():
    """Reset and Boot button traces (B.Cu, dev kit style).

    SW15: EN pin to GND (hardware reset)
      - GND pads (3,4) connect via GND plane (In1.Cu) through vias
      - Signal pads (1,2) connect to EN net via stub + via
        then B.Cu route to U1 pin 3 (EN)

    SW14: GPIO0 to GND (download mode when held during reset)
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

    # ── SW15 (Reset) ──
    # Pads after B.Cu mirroring: p1=(98,63.65) p2=(92,63.65) p3=(98,67.35) p4=(92,67.35)
    rst_p1 = _pad("SW15", "1")
    rst_p2 = _pad("SW15", "2")
    rst_p3 = _pad("SW15", "3")
    rst_p4 = _pad("SW15", "4")

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
        # EN signal: pad 1 (right pad at x=98) → B.Cu vertical run down to
        # y=24.78 → horizontal to U1 pin 3. Pure B.Cu, no via needed.
        #
        # B.Cu route analysis (verified clear):
        #   Vertical leg x=98, y=63.65→24.78: passes between R15/C16 pads
        #     R15:1 left edge 98.45, trace right edge 98.125, gap=0.325mm
        #     R15:2 right edge 97.55, trace left edge 97.875, gap=0.325mm
        #   Horizontal leg y=24.78, x=98→88.75: no vertical obstacles
        #     U1:2 (+3V3) top edge 23.96, trace bottom edge 24.655, gap=0.695mm
        #     U1:4 (LCD_D0) bottom edge 25.60, trace top edge 24.905, gap=0.695mm
        #
        # R17 (2026-04-12): removed vestigial via at (98, 60). The original
        # routing intended a F.Cu↔B.Cu transition there, but the current
        # implementation only ever uses B.Cu, so the via was orphan
        # (DRC: via_dangling). The straight-line B.Cu run from (98, 63.65)
        # to (88.75, 24.78) is unchanged.
        en_pin = _pad("U1", "3")  # (88.75, 24.78)
        if en_pin:
            en_x, en_y = en_pin
            # Vertical: rst_p1 → (rst_p1.x, en_y)
            parts.append(_seg(rst_p1[0], rst_p1[1], rst_p1[0], en_y,
                              "B.Cu", W_SIG, n_en))
            # Horizontal: (98, en_y) → (en_x, en_y) = U1 pin 3, split at
            # the C31 (96.2) and R3 (94.0) tap points so each stub from
            # the EN RC network (passives.py) lands on a segment ENDPOINT —
            # the JLCDFM dead-end check does not credit mid-segment
            # T-junctions.
            from ._shared import C31_POS, R3_POS
            taps = sorted({C31_POS[0], R3_POS[0]}, reverse=True)
            xs = [rst_p1[0]] + taps + [en_x]
            for x_a, x_b in zip(xs, xs[1:]):
                parts.append(_seg(x_a, en_y, x_b, en_y,
                                  "B.Cu", W_SIG, n_en))

    # ── SW14 (Boot/Download mode) ──
    # Pads after B.Cu mirroring: p1=(108,63.65) p2=(102,63.65) p3=(108,67.35) p4=(102,67.35)
    boot_p1 = _pad("SW14", "1")
    boot_p2 = _pad("SW14", "2")
    boot_p3 = _pad("SW14", "3")
    boot_p4 = _pad("SW14", "4")

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


def _menu_diode_traces():
    """BAT54C menu combo diode (D1) routing — R5-CRIT-6 FIX (2026-07-25).

    Circuit: SW13 (menu button) pulls BTN_START + BTN_SELECT low at the
    same time through the dual Schottky diode D1 (BAT54C, SOT-23-3, B.Cu).

    D1 pinout (BAT54C, common cathode):
      Pin 1 (Anode 1)        -> BTN_START
      Pin 2 (Anode 2)        -> BTN_SELECT
      Pin 3 (Common Cathode) -> MENU_K -> SW13 pads 1+2

    SW13 pads 3/4 -> GND. Pressing SW13 grounds the cathode, so both
    anodes are pulled low through the diodes and firmware sees the
    START+SELECT combo without the user pressing two buttons.

    WHAT WAS BROKEN
    ---------------
    D1 used to sit at (156, 52.5), next to SW13. Its two anodes ended in
    isolated pads: BTN_START and BTN_SELECT both terminate around
    x=100-102 and no corridor reaches x=156.
      * south perimeter at y=73.955 crosses the J1 USB-C back-row shield
        pads (J1.13b / J1.14b) which occupy y=[72.575, 74.575];
      * north through the power area is blocked by IP5306, L1, the
        regulator, the C17-C19 pads, the MENU_K F.Cu at x=156 and the
        USB_D+/D- verticals at x=90-91.
    KiCad DRC reported "BTN_START track <-> D1 pad 1" and
    "BTN_SELECT track <-> D1 pad 2" as unconnected, and the menu combo
    had to be pressed by hand.

    THE FIX
    -------
    Move D1 to the buttons instead of dragging the buttons to D1, so only
    ONE net (MENU_K) has to cross the board. D1 now sits at
    (101.225, 56.5) rotated 180 deg, in the 1.30 mm free channel between
    the two button columns:

        BTN_START  B.Cu vertical x=100.45  (y=34.94..73.955)
        BTN_SELECT B.Cu vertical x=102.00  (y=60.00..63.65)

    At 180 deg the SOT-23 two-pad row faces north, so pin 1 lands on the
    west column and pin 2 on the east column with no crossing:

        D1.1 = (100.275, 55.400)  ->  0.175 mm stub east onto x=100.45
        D1.2 = (102.175, 55.400)  ->  0.175 mm stub west onto x=102.00,
                                      then the BTN_SELECT column is
                                      extended north from y=60.00
        D1.3 = (101.225, 57.600)  ->  MENU_K south to the y=62.400
                                      F.Cu corridor, then east to SW13

    MENU_K corridor clearances (verified against the generated PCB):
      B.Cu vertical x=101.225, y=57.60..62.40, w=0.25 (edges 101.100/101.350)
        vs BTN_START  vert (edges 100.325/100.575)   gap 0.525 mm
        vs BTN_SELECT vert (edges 101.875/102.125)   gap 0.525 mm
      via (101.225, 62.400) size 0.60 (AABB x=[100.925,101.525])
        vs BTN_START  vert                           gap 0.350 mm
        vs BTN_SELECT vert                           gap 0.350 mm
        vs SW14.2 pad (x=[101.5,102.5] y=[63.3,64.0])
                                                     gap 0.600 mm
        vs VBUS F.Cu y=61.0 (bottom edge 61.38)      gap 0.720 mm
      F.Cu y=62.400, x=101.225..137.0, w=0.25 (edges 62.275/62.525)
        vs VBUS F.Cu y=61.0 + its vertical at x=111  gap 0.895 mm
        vs GND via (127.30, 60.65) r=0.45            gap 1.175 mm
        vs GND via (128.30, 61.00) r=0.30            gap 0.725 mm
        vs GND via (135.00, 63.55) r=0.30            gap 0.725 mm
        vs GND vias (123.50, 64.50) / (128.30, 64.00) gap >= 1.175 mm
        C2 / U3 / U6 / SW14 pads and the BTN_A/BTN_X/BTN_Y verticals
        crossing this band are all B.Cu, so they do not share the layer.
      F.Cu vertical x=137.0, y=59.85..62.40
        vs BTN_R F.Cu jog at x=137, y=64.40..65.39   gap 2.000 mm
        vs SW13.3 pad (x=[138.5,139.5])              gap 1.375 mm

    Everything stays west of x=105 in the y=[39,59] band so it does not
    collide with the parallel SY8089A buck-regulator rework.
    """
    parts = []
    _init_pads()
    n_gnd = NET_ID["GND"]
    n_start = NET_ID["BTN_START"]
    n_sel = NET_ID["BTN_SELECT"]
    n_menu_k = NET_ID["MENU_K"]

    # ── Assign pad nets ──
    _PAD_NETS[("D1", "1")] = n_start     # Anode 1 → BTN_START
    _PAD_NETS[("D1", "2")] = n_sel       # Anode 2 → BTN_SELECT
    _PAD_NETS[("D1", "3")] = n_menu_k    # Common cathode → MENU_K
    _PAD_NETS[("SW13", "2")] = n_menu_k  # SW13 terminal → cathode junction
    _PAD_NETS[("SW13", "1")] = n_menu_k  # SW13 terminal (shorted pair with pad 2)
    _PAD_NETS[("SW13", "3")] = n_gnd     # SW13 → GND
    _PAD_NETS[("SW13", "4")] = n_gnd     # SW13 → GND (shorted pair)

    # Get pad positions
    d1_p1 = _pad("D1", "1")   # Anode 1 (BTN_START)
    d1_p2 = _pad("D1", "2")   # Anode 2 (BTN_SELECT)
    d1_p3 = _pad("D1", "3")   # Cathode (MENU_K)
    sw13_p1 = _pad("SW13", "1")
    sw13_p2 = _pad("SW13", "2")
    sw13_p3 = _pad("SW13", "3")
    sw13_p4 = _pad("SW13", "4")
    if not all((d1_p1, d1_p2, d1_p3, sw13_p1, sw13_p2, sw13_p3, sw13_p4)):
        # Never silence: the menu combo is a functional feature. If a pad
        # cannot be resolved the generator must stop rather than emit a
        # board with floating diode anodes again — that is R5-CRIT-6.
        raise RuntimeError(
            "menu diode: cannot resolve D1/SW13 pads "
            f"(D1={d1_p1},{d1_p2},{d1_p3} "
            f"SW13={sw13_p1},{sw13_p2},{sw13_p3},{sw13_p4})"
        )

    # ── 1. D1 anode 1 (pin 1) → BTN_START column ──
    # The BTN_START B.Cu vertical already runs at x=100.45 through
    # y=55.400, so a 0.175 mm stub east from the pad centre lands on its
    # centreline and forms an explicit T-junction.
    parts.append(_seg(d1_p1[0], d1_p1[1], _MENU_BTN_START_COL_X, d1_p1[1],
                      "B.Cu", W_SIG, n_start))

    # ── 2. D1 anode 2 (pin 2) → BTN_SELECT column ──
    # BTN_SELECT only reached down to (102.00, 60.00) — the via that drops
    # onto its F.Cu channel at y=58. Stub west onto the column, then
    # extend the column from the D1 pad row south to that via.
    parts.append(_seg(d1_p2[0], d1_p2[1], _MENU_BTN_SELECT_COL_X, d1_p2[1],
                      "B.Cu", W_SIG, n_sel))
    parts.append(_seg(_MENU_BTN_SELECT_COL_X, d1_p2[1],
                      _MENU_BTN_SELECT_COL_X, _MENU_BTN_SELECT_VIA_Y,
                      "B.Cu", W_SIG, n_sel))

    # ── 3. D1 cathode (pin 3) → MENU_K → SW13 pads 1+2 ──
    # South on B.Cu in the free channel, via to F.Cu, then the long east
    # run at y=62.400 (between the VBUS F.Cu rail at y=61.0 and the SW13
    # GND row at y=63.55), north at x=137.0, finally east across BOTH
    # SW13 terminals — KiCad does not auto-bridge same-net tact-switch
    # pads, so the copper has to be laid over pad 1 and pad 2 (R17).
    parts.append(_seg(d1_p3[0], d1_p3[1], _MENU_K_COL_X, _MENU_K_CORRIDOR_Y,
                      "B.Cu", W_SIG, n_menu_k))
    parts.append(_via_net(_MENU_K_COL_X, _MENU_K_CORRIDOR_Y, n_menu_k,
                          size=VIA_STD, drill=VIA_STD_DRILL))
    parts.append(_seg(_MENU_K_COL_X, _MENU_K_CORRIDOR_Y,
                      _MENU_K_RISER_X, _MENU_K_CORRIDOR_Y,
                      "F.Cu", W_SIG, n_menu_k))
    parts.append(_seg(_MENU_K_RISER_X, _MENU_K_CORRIDOR_Y,
                      _MENU_K_RISER_X, sw13_p1[1],
                      "F.Cu", W_SIG, n_menu_k))
    parts.append(_seg(_MENU_K_RISER_X, sw13_p1[1], sw13_p1[0], sw13_p1[1],
                      "F.Cu", W_SIG, n_menu_k))
    parts.append(_seg(sw13_p1[0], sw13_p1[1], sw13_p2[0], sw13_p2[1],
                      "F.Cu", W_SIG, n_menu_k))

    # ── 4. SW13 GND pads → vias ──
    # SW13 pad 3 at (139.0, 63.55): route LEFT to x=135.0 and drop the via
    # right there.
    # R5-CRIT-6 (2026-07-25): the via used to sit at (135.0, 61.55) with a
    # 2 mm F.Cu riser between them. That riser occupied x=[134.85,135.15],
    # y=[61.40,63.70] on F.Cu — straight across the only usable MENU_K
    # corridor at y=62.400. Dropping the riser frees the corridor.
    # Via (135.0, 63.55) size 0.60 → AABB x=[134.7,135.3], y=[63.25,63.85]:
    #   vs U6.13 pad B.Cu (right edge 133.68)         gap 1.020 mm
    #   vs BTN_R F.Cu y=65.29 (top edge 65.19)        gap 1.340 mm
    #   vs MENU_K F.Cu y=62.400 (bottom edge 62.525)  gap 0.725 mm
    #   vs SD_CS B.Cu vert x=138.86                   gap 3.560 mm
    gnd_via_x = 135.00  # left, clear of SD_CS@138.86 and U6
    parts.append(_seg(sw13_p3[0], sw13_p3[1], gnd_via_x, sw13_p3[1],
                      "F.Cu", W_PWR_LOW, n_gnd))
    parts.append(_via_net(gnd_via_x, sw13_p3[1], n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))
    # SW13 pad 4 at (145.0, 63.55): BTN_R F.Cu jog at y=64 blocks going
    # south. Route RIGHT to x=148 (right of the jog endpoint at 146.5),
    # then DOWN.
    gnd_jog_x = 148.00   # right of BTN_R F.Cu jog start (146.5) by 1.5mm
    gnd_via_y = 66.50    # below BTN_R via (65.29+0.45=65.74) by 0.76mm
    parts.append(_seg(sw13_p4[0], sw13_p4[1], gnd_jog_x, sw13_p4[1],
                      "F.Cu", W_PWR_LOW, n_gnd))
    parts.append(_seg(gnd_jog_x, sw13_p4[1], gnd_jog_x, gnd_via_y,
                      "F.Cu", W_PWR_LOW, n_gnd))
    parts.append(_via_net(gnd_jog_x, gnd_via_y, n_gnd,
                          size=VIA_STD, drill=VIA_STD_DRILL))

    return parts


def _button_pullup_bridges():
    """R6 FIX (2026-04-10): bridge the isolated R.1/C.1 pull-up+debounce
    junctions to the main button signal lines.

    Pre-existing bug (R5-CRIT-4 in hardware-audit-bugs.md): the 12 button
    pull-up resistors (R4..R15) and debounce caps (C5..C16) are placed in
    a 5mm-pitch strip at y=46/50, with same-net verticals between R.1
    and C.1, but no connection to the main button signal path. The
    pull-ups pulled nothing; debounce caps saw no signal. Firmware
    internal pull-ups kept the buttons functional, but the external
    R/C network was BOM cost without electrical effect.

    Fix: for each button, route a bridge from the R.1 pad (at y=46 on
    the strip) to the nearest existing signal point on the main button
    net. The geometry of each button is different, so the bridges are
    hand-coded per button rather than scripted.
    """
    parts = []

    # ── EASY: BTN_B, BTN_X, BTN_Y ──
    # These buttons have their F.Cu main horizontal at y ∈ [41.50, 43.90]
    # running near the R strip (y=46). A short B.Cu vertical of 2-5mm
    # from R.1 to the main F.Cu / B.Cu at x≈R.1.x connects them.

    # BTN_B: R9.1@(68.95, 46) → main F.Cu (45.55, 41.50)-(73.25, 41.50)
    # DFM: C3.2 (GND) at (68.60, 42.00) west, C3.1 (+3V3) at (70.50, 42.00) east.
    # The vertical at x=69.40..69.60 is blocked on both sides by the C3 cap pads
    # (pad x ranges: [68.10, 69.10] for C3.2, [70.00, 71.00] for C3.1).
    #
    # R9-CRIT-2 FIX (2026-04-11): the old bridge via at (69.40, 41.50) was 0.05 mm
    # copper / 0.20 mm hole from C3.2 (below 0.20/0.254 rule). A naive shift east
    # to 69.60 would bring it 0.197 mm from C3.1 (+3V3, different net). Root cause:
    # the via needs to land in the tiny 0.90 mm gap between the two C3 pads, but
    # the via+pad clearance (0.23+0.50+0.20=0.93 mm centre-to-centre on each side)
    # is bigger than the gap.
    #
    # The barrel does NOT fit in that channel and no via size makes it fit.
    # C3's JLC reference 0805 land is 1.15 x 1.35, so the pads own
    # x <= 69.175 and x >= 69.925 — a 0.75 mm channel. KiCad resolves
    # via-to-pad against the Default netclass (0.2 mm; the 0.09 mm relaxation
    # in the .kicad_dru is conditioned on A.Type == 'track' and never applies
    # to a barrel), which needs OD + 0.4 <= 0.75, i.e. OD <= 0.35 — below the
    # 0.45 mm JLCPCB via floor the same .kicad_dru enforces. Successive
    # shrinks (0.50 -> 0.46) bought margin against the 0.127 mm copper floor
    # and were still 0.145 mm from both pads, which is what CI reported.
    #
    # So the via leaves the channel: the B.Cu vertical runs on through it
    # (a 0.25 mm track keeps 0.25 mm each side and tracks answer to the
    # 0.09 mm rule anyway) and surfaces 0.65 mm NORTH of C3's pads, where
    # the nearest copper is a pad corner at
    # sqrt(0.375^2 + 0.475^2) = 0.605 mm — 0.305 mm clear at VIA_STD's
    # 0.60 mm OD, which also restores the 0.20 mm annular ring the 0.46 mm
    # barrel had given up. An F.Cu stub then drops the 0.65 mm south onto
    # the main BTN_B horizontal at y=41.50, on F.Cu the whole way, where
    # C3's bottom-side pads are not in the picture at all.
    n_btn_b = NET_ID["BTN_B"]
    _b_x = BTN_B_TAP_X
    _b_via_y = 40.85
    parts.append(_seg(68.95, 46.00, _b_x, 46.00, "B.Cu", W_SIG, n_btn_b))  # horiz within R9.1 pad
    parts.append(_seg(_b_x, 46.00, _b_x, _b_via_y, "B.Cu", W_SIG, n_btn_b))  # vertical — through the C3 channel, 0.25 mm each side
    parts.append(_via_net(_b_x, _b_via_y, n_btn_b,
                          size=VIA_STD, drill=VIA_STD_DRILL))
    # F.Cu stub down onto the main horizontal at y=41.50, which the stagger
    # loop splits at BTN_B_TAP_X so this lands on a real endpoint.
    parts.append(_seg(_b_x, _b_via_y, _b_x, 41.50, "F.Cu", W_SIG, n_btn_b))

    # BTN_X: R10.1@(73.95, 46) → existing BTN_X F.Cu↔B.Cu via at (73.555, 42.70)
    # Use the existing via (west end of the (73.56, 42.70)-(75.56, 42.70) segment)
    # instead of a mid-segment tap. Routing east of x=73.56 would cross the
    # BTN_Y B.Cu horizontal at y=43.90 from (74.83, 43.90)-(76.83, 43.90).
    # Route: small westward hop within R10.1 pad, then vertical to the via.
    n_btn_x = NET_ID["BTN_X"]
    parts.append(_seg(73.95, 46.00, 73.555, 46.00, "B.Cu", W_SIG, n_btn_x))
    parts.append(_seg(73.555, 46.00, 73.555, 42.70, "B.Cu", W_SIG, n_btn_x))

    # BTN_Y: R11.1@(78.95, 46) → existing BTN_Y F.Cu/B.Cu via at (74.83, 43.90)
    # Blockers:
    #   - B.Cu: R11.2/C12.2 +3V3/GND pads at x=77.05
    #   - B.Cu: R11 own +3V3 pull-up via at (76.95, 44.5) size 0.6
    #   - F.Cu: BAT+ horizontal at y=46.135 (main BAT+ network)
    # Bridge strategy: B.Cu stub from R11.1 going NORTH to y=43.0 (well
    # past the +3V3 via row at y=44.5), via to F.Cu, then F.Cu diagonal
    # to the existing BTN_Y F.Cu via at (74.83, 43.90).
    # Diagonal clearance to R11 +3V3 via: perpendicular distance 1.05mm
    # gives gap = 1.05 - 0.3 - 0.125 = 0.625mm ✓.
    n_btn_y = NET_ID["BTN_Y"]
    parts.append(_seg(78.95, 46.00, 78.95, 43.00, "B.Cu", W_SIG, n_btn_y))  # stub north past +3V3 via row
    parts.append(_via_net(78.95, 43.00, n_btn_y, size=VIA_MIN, drill=VIA_MIN_DRILL))
    # Use exact via x=74.825 (cache rounds to 74.83 in text display) so the
    # dead-end detector's rounding keys match at the existing BTN_Y via.
    parts.append(_seg(78.95, 43.00, 74.825, 43.90, "F.Cu", W_SIG, n_btn_y))  # diagonal to existing F.Cu endpoint

    # ── MEDIUM: BTN_R ──
    # R15.1@(98.95, 46) → existing BTN_R F.Cu horizontal (76.20, 48)-(87.985, 48)
    # B.Cu area y=[46, 52] is crowded with USB_D+/-, GND verticals. Use F.Cu.
    # Place a via at (98.95, 47.0) — sits on the existing R15.1→C16.1
    # junction B.Cu vertical at x=98.95 (y=46..50), same net → electrically
    # connected without an explicit stub. y=47 is clear of BAT+ F.Cu at
    # y=46.135 (via top=46.77, BAT+ bot=46.515 → gap 0.255mm ✓).
    n_btn_r = NET_ID["BTN_R"]
    parts.append(_via_net(98.95, 47.00, n_btn_r, size=VIA_MIN, drill=VIA_MIN_DRILL))
    parts.append(_seg(98.95, 47.00, 98.95, 48.00, "F.Cu", W_SIG, n_btn_r))
    parts.append(_seg(98.95, 48.00, 87.985, 48.00, "F.Cu", W_SIG, n_btn_r))

    # ── MEDIUM: BTN_START ──
    # R12.1@(83.95, 46) → existing BTN_START approach via at (100.45, 34.94).
    #
    # R9-CRIT-1 FIX (2026-04-11): the previous diagonal F.Cu route
    # (83.95, 43.00) → (90.75, 34.94) crossed LCD_CS/LCD_DC/LCD_WR F.Cu
    # horizontals (y=35.58-38.12) on the same layer — 3 physical shorts.
    # R9 revised plan: route the bridge via F.Cu east in the clear y=43 band
    # to x=100.15 (just east of LCD_D4/CS endpoints), transition to B.Cu, and
    # go south to (100.15, 34.94) where an existing via joins the main
    # BTN_START network. Avoids:
    #   - LCD F.Cu cluster (stays at y=43 on F.Cu, and the B.Cu south leg at
    #     x=100.15 is clear of LCD F.Cu traces entirely — different layer)
    #   - Mounting hole keepout at (105, 37.5) r=2.25 (x=100.15 → dx=4.85 ✓)
    #   - LCD_D4 B.Cu vert at x=99.50 (dx=0.65 → edge gap 0.425 mm ✓)
    #   - LCD_DC B.Cu horiz at y=34.60 (y end 34.94 → dy=0.34 > 0.225 ✓)
    # R13-CRIT-1 FIX (2026-04-11): the R9 reroute above terminated at
    # (100.15, 43) and then ran B.Cu vertical from (100.15, 43) to
    # (100.15, 34.94) before jogging east to (100.45, 34.94) — where
    # it met the existing stagger column B.Cu vert at x=100.45 running
    # from y=34.94 up to y=73.955. Result: two parallel B.Cu verticals
    # at x=100.15 and x=100.45 with center-to-center 0.30 mm, edge
    # gap = 0.30 − 0.125 − 0.125 = 0.050 mm. Same net (BTN_START) so
    # verify_copper_clearance.py was not catching it — but JLCDFM's
    # dry-film rule doesn't care about net and flagged it as
    # "Trace spacing Danger 0.05mm" twice (v3.4 and v3.5 uploads).
    #
    # Fix: land the R9 bridge directly on the existing stagger column
    # at x=100.45 by running the F.Cu bridge further east and dropping
    # the via at (100.45, 43). The existing stagger column already
    # covers y=34.94..73.955 at x=100.45, so the via at y=43 lands
    # mid-segment and provides the electrical junction. No new B.Cu
    # vertical at x=100.15 is needed — the 0.050 mm parallel cluster
    # disappears entirely.
    n_btn_start = NET_ID["BTN_START"]
    parts.append(_seg(83.95, 46.00, 83.95, 43.00, "B.Cu", W_SIG, n_btn_start))
    parts.append(_via_net(83.95, 43.00, n_btn_start, size=VIA_MIN, drill=VIA_MIN_DRILL))
    # F.Cu bridge from (83.95, 43) east to (100.45, 43) — the existing
    # stagger B.Cu column at x=100.45 runs through y=43, so we land
    # the via on top of it.
    parts.append(_seg(83.95, 43.00, 100.45, 43.00, "F.Cu", W_SIG, n_btn_start))
    parts.append(_via_net(100.45, 43.00, n_btn_start, size=VIA_MIN, drill=VIA_MIN_DRILL))

    # ── SOUTH-HIGHWAY PATTERN (staggered y per button) ──
    #
    # The y=[42,45] north band is saturated — all new routes go south of
    # the R/C strip (y > 50.65 clearance). Each button uses a different
    # y to avoid horizontal overlap with other button bridges. Targets
    # are B.Cu verticals on the main signal path that span the chosen y.
    #
    # Obstacles to avoid at y=[55, 65]:
    #   - SPK1.1 at (39.5, 52.5) pad y range [51, 54] → use y ≥ 55
    #   - SPK1.2 at (19.5, 52.5) — same, west of all our targets
    #   - BAT+ B.Cu vert (38, 46.135→68.3)  — block x=38 for y ∈ that range
    #   - BAT+ B.Cu vert (80.01, 46.135→62.5) — block x=80.01 for that y
    #
    # Per-button pattern:
    #   1. B.Cu stub (x_r, 50) → (x_r, y_br) south — through C.1 same net
    #   2. B.Cu horizontal (x_r, y_br) → (target_x, y_br)
    #   3. Via at (target_x, y_br) — mid-segment tap on main B.Cu vertical
    #      (same net + same layer = electrically connected; via provides
    #      a "connection point" for the JLCDFM dead-end detector)

    def _bridge_south(parts_list, x_r, target_x, y_br, net_id):
        """South-highway bridge: B.Cu stub → via → F.Cu horizontal → via.
        Uses F.Cu for the horizontal to avoid crossing other buttons'
        B.Cu verticals at y=55-57. Target via sits on the main B.Cu
        vertical (same net, connected via the via's B.Cu annulus).

        R12 JLCDFM fix (2026-04-11): the button bridge F.Cu rows are
        stacked at 0.5 mm pitch (y=55.0..58.0). With W_SIG=0.25 and
        VIA_MIN=0.50, the via-to-adjacent-trace gap was only 0.125 mm
        (= 0.5 - 0.25 - 0.125) which JLCDFM flagged at 0.1 mm cyan.
        Fix: narrow the F.Cu horizontal to W_DATA (0.20) and shrink the
        bridge vias to 0.46 mm — new gap = 0.5 - 0.23 - 0.10 = 0.170 mm
        (safely above 0.15 mm JLCPCB minimum). 0.46 mm via with 0.20 mm
        drill gives AR = 0.13 mm ≥ JLCPCB 0.127 mm min.
        """
        _V_BRIDGE = 0.46   # via OD: 0.5 - 0.23 - 0.10 = 0.170mm gap
        _V_DRILL = 0.20
        # B.Cu stub from C.1 (through pad, same net) down to bridge y
        parts_list.append(_seg(x_r, 50.00, x_r, y_br, "B.Cu", W_SIG, net_id))
        # Via to F.Cu (0.46 mm bridge via)
        parts_list.append(_via_net(x_r, y_br, net_id,
                                    size=_V_BRIDGE, drill=_V_DRILL))
        # F.Cu horizontal on clean layer — narrowed to W_DATA for row-pitch clearance
        parts_list.append(_seg(x_r, y_br, target_x, y_br, "F.Cu", W_DATA, net_id))
        # Via back to B.Cu at target (same-net tap on main vertical)
        parts_list.append(_via_net(target_x, y_br, net_id,
                                    size=_V_BRIDGE, drill=_V_DRILL))

    # Stagger y 0.5mm apart to avoid trace-trace overlap between bridges.
    # 5 buttons whose x range does NOT cross x=38 or x=80 (BAT+ B.Cu vertical
    # blockers) use the clean y=55-57 band south of SPK1 (y≤54).
    _bridge_south(parts, 63.95, 53.10, 55.0, NET_ID["BTN_A"])       # west 10.85mm
    _bridge_south(parts, 53.95, 63.10, 55.5, NET_ID["BTN_LEFT"])    # east 9.15mm
    _bridge_south(parts, 48.95, 65.55, 56.0, NET_ID["BTN_DOWN"])    # east 16.6mm
    _bridge_south(parts, 58.95, 58.10, 56.5, NET_ID["BTN_RIGHT"])   # west 0.85mm
    _bridge_south(parts, 43.95, 67.83, 57.0, NET_ID["BTN_UP"])      # east 23.9mm

    # BTN_SELECT: B.Cu stub from R13/C14 junction south to meet the
    # SW14 bridge F.Cu at y=58. Tap as a T-junction via mid-F.Cu.
    # Same net same layer after the via transition → connected.
    # R12 JLCDFM fix: via shrunk to 0.46 mm for 0.17 mm clearance to
    # BTN_L F.Cu at y=57.50 (row pitch 0.5 mm − via r 0.23 − trace hw 0.10).
    parts.append(_seg(88.95, 50.00, 88.95, 58.00, "B.Cu", W_SIG, NET_ID["BTN_SELECT"]))
    parts.append(_via_net(88.95, 58.00, NET_ID["BTN_SELECT"],
                           size=0.46, drill=0.20))

    # BTN_L: F.Cu horizontal at y=57.5 (staggered 0.5mm from BTN_UP y=57)
    # from R14.1 area to x=64.75 (main B.Cu vertical x=64.75 y=40-73.42
    # span includes y=57.5). Via at each end.
    _bridge_south(parts, 93.95, 64.75, 57.5, NET_ID["BTN_L"])       # west 29.2mm

    # D1.1 / D1.2 menu-diode anodes: deferred to v2 PCB respin.
    # South-perimeter routes at y=73.95/74.46 cross J1.13b/J1.14b USB-C
    # back-row shield pads at (84.325, 73.575) / (75.675, 73.575) pad y
    # range [72.575, 74.575] — different net GND. Jog routes through the
    # J1 shield areas would require multiple vias and complex DRC fights.
    # North-perimeter routes blocked by IP5306/AMS1117/MENU_K/USB_D+-.
    # Allowlisted. SW13 menu-combo button is usable by pressing START+SELECT
    # separately as a workaround.

    # ── SW14.2 → BTN_SELECT main chain ──
    # The existing SW14 → (102, 60) dangling via + short B.Cu stub
    # (102, 63.65)→(102, 60) is already on BTN_SELECT net. Extend from
    # (102, 60) via F.Cu to BTN_SELECT main B.Cu vertical at x=60.45.
    # Route: F.Cu (102, 60) → (102, 58) short stub north (clear of EN
    # via at (98, 60) by 2mm), then F.Cu (102, 58) → (60.45, 58)
    # horizontal west 41.55mm (clean at y=58 — VBUS F.Cu is at y=61,
    # BTN_UP F.Cu at y=62, EN/VBUS/GND vias at y=59-62 all ≥0.575mm
    # gap away). Via at (60.45, 58) taps the BTN_SELECT main vertical.
    n_btn_select = NET_ID["BTN_SELECT"]
    # R12 JLCDFM fix: F.Cu horizontal narrowed to W_DATA and tap via
    # shrunk to 0.46 mm — see _bridge_south docstring for math.
    parts.append(_seg(102.00, 60.00, 102.00, 58.00, "F.Cu", W_DATA, n_btn_select))
    parts.append(_seg(102.00, 58.00, 60.45, 58.00, "F.Cu", W_DATA, n_btn_select))
    parts.append(_via_net(60.45, 58.00, n_btn_select,
                           size=0.46, drill=0.20))

    return parts
