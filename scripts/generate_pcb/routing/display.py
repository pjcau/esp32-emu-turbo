"""Split from routing.py 2026-07-26 — mechanical, AST-driven, proven by a
byte-identical regenerated .kicad_pcb. One domain per module; every helper
and every constant lives in _shared (original order, so import-time
execution is unchanged). See routing/__init__.py for the contract."""
from ._shared import (
    NET_ID,
    VIA_MIN,
    VIA_MIN_DRILL,
    VIA_STD,
    VIA_STD_DRILL,
    W_DATA,
    W_PWR_LOW,
    _esp_pin,
    _fpc_display_pin,
    _init_pads,
    _mh_detour_h,
    _seg,
    _via_net,
)




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
        # DFM FIX: J4:42 structural pad at (136.29, 24.06) size 2.5x2.0mm blocks
        # LCD approach columns at x=135.04..137.54. Bridge via F.Cu for traces
        # that cross this pad.
        # R9-HIGH-6 FIX (2026-04-11): shifted Y2 from 25.50 → 25.52
        # to give 0.21 mm clearance to J4.42 pad bottom (25.06 + pad_hh 1.0 = 25.06
        # wait - actually pad bottom in KiCad PCB coord is pad_center+half = 24.06+1.0=25.06).
        # Old: gap = 25.50 - 0.25 - 25.06 = 0.19 mm FAIL.
        # New: gap = 25.52 - 0.25 - 25.06 = 0.21 mm ≥ 0.20 rule ✓.
        # Also shifted Y1 in sympathy (keeps symmetry of the F.Cu bridge segment
        # around the J4.42 pad).
        # JLCPCB FIX: stagger bridge via Y positions for adjacent columns
        # so via-to-via hole gap >= 0.50mm (JLCPCB diff-net minimum).
        # Even idx: Y1=22.20, Y2=25.80; odd idx: Y1=22.48, Y2=25.52.
        # Diagonal distance: sqrt(0.70² + 0.28²) = 0.754mm → gap=0.554mm ✓
        if idx % 2 == 0:
            _J4_42_Y1 = 22.20   # 0.86mm above pad top (23.06)
            _J4_42_Y2 = 25.80   # 0.74mm below pad bottom (25.06)
        else:
            _J4_42_Y1 = 22.48   # 0.58mm above pad top (23.06)
            _J4_42_Y2 = 25.52   # 0.46mm below pad bottom (25.06)
        if 135.04 - 0.20 < apx < 137.54 + 0.20 and bypass_y < _J4_42_Y1 and fpy > _J4_42_Y2:
            # Split: B.Cu above → via → F.Cu through pad → via → B.Cu below
            parts.append(_seg(apx, bypass_y, apx, _J4_42_Y1, "B.Cu", W_DATA, net))
            parts.append(_via_net(apx, _J4_42_Y1, net, size=VIA_MIN, drill=VIA_MIN_DRILL))
            parts.append(_seg(apx, _J4_42_Y1, apx, _J4_42_Y2, "F.Cu", W_DATA, net))
            parts.append(_via_net(apx, _J4_42_Y2, net, size=VIA_MIN, drill=VIA_MIN_DRILL))
            parts.append(_seg(apx, _J4_42_Y2, apx, fpy, "B.Cu", W_DATA, net))
        else:
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
        # JLCPCB DFM FIX v3 (2026-04-10):
        # - v1: via at (133.10, 43.75) → gap=0.14mm to J4[panel 38] at (133.712, 44.25)
        # - v2: nudged LEFT to stub_x=133.00 → CAUGHT gap to J4[panel 38] but
        #       CAUSED a 0.088mm overlap with connector-pad J4[37] at (133.712, 43.75),
        #       reported as DRC shorting_item (GND via vs J4.37 NC pad).
        # - v3: nudged further LEFT to stub_x=132.60. Via right edge = 132.90.
        #       Gap to J4 pad left edge (133.212) = 0.312mm ≥ 0.15 clearance ✓.
        #       Gap to pads at y=42.75/43.25/43.75/44.25: all ≥ 0.3mm ✓.
        stub_x = VIA_X_PWR - 1.0  # 132.60 (was 133.00, now +0.3mm further clear)
        vx2 = 143.50  # right of net32 vert at x=142.80 (gap=0.70-0.23-0.15=0.32mm)
        vy = 50.25
        # DFM FIX (KiBot external): via at (133.0, 43.25) gap=0.14mm to J4:35
        # (+3V3) at y=42.75. Move via DOWN to y+0.5=43.75 for gap=0.375mm ✓
        via_y = py + 0.5
        # GND stub: horizontal narrowed to 0.30mm near +3V3 pin6/7 crossing.
        parts.append(_seg(px, py, stub_x, py, "B.Cu", W_PWR_LOW, n_gnd))
        parts.append(_seg(stub_x, py, stub_x, via_y, "B.Cu", 0.4, n_gnd))
        # R12 JLCDFM fix (2026-04-11): shrink via from VIA_STD (0.60mm) to
        # 0.46mm. With VIA_STD the left edge was at 132.30, only 0.150 mm
        # from the +3V3 B.Cu vertical right edge at x=132.15 (trace w=0.3,
        # hw=0.15). 0.46mm via left edge moves to 132.37 → gap = 0.220mm
        # (safely above 0.15mm JLCPCB min). Right edge 132.83 preserves
        # the v3 clearance to J4 connector pads (still 0.38mm away).
        parts.append(_via_net(stub_x, via_y, n_gnd, size=0.46, drill=0.20))
        # R9-HIGH-4 SIDE-FIX (2026-04-11): the F.Cu horizontal from (stub_x,
        # via_y) to (vx2, via_y) at y=43.75 ran 0.05 mm from SW7.3 (no-net)
        # pad at (139, 44.35). Rather than fighting the clearance, jog the
        # trace south around SW7.3 pad (x=[138.5, 139.5], y=[44.0, 44.7]):
        #   (stub_x, 43.75) → (137.80, 43.75) straight
        #   (137.80, 43.75) → (137.80, 45.10) south jog (trace bot 45.30,
        #     pad bot 44.70 → gap 0.60 mm, but trace edge is 45.10-0.20=44.90 ≥
        #     pad bot 44.70 + 0.20 clearance ✓)
        #   (137.80, 45.10) → (139.90, 45.10) east across south of pad
        #   (139.90, 45.10) → (139.90, 43.75) back north
        #   (139.90, 43.75) → (vx2, 43.75) continue east
        parts.append(_seg(stub_x, via_y, 137.80, via_y, "F.Cu", 0.4, n_gnd))
        parts.append(_seg(137.80, via_y, 137.80, 45.10, "F.Cu", 0.4, n_gnd))
        parts.append(_seg(137.80, 45.10, 139.90, 45.10, "F.Cu", 0.4, n_gnd))
        parts.append(_seg(139.90, 45.10, 139.90, via_y, "F.Cu", 0.4, n_gnd))
        parts.append(_seg(139.90, via_y, vx2, via_y, "F.Cu", 0.4, n_gnd))
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
    # NOTE: No series current-limiting resistor — and this is R25-HIGH-1, an
    # OPEN defect, not a design choice.
    #
    # "Most ILI9488 bare panels have internal LED current limiting" was the
    # claim here and it is unverified. R28/R29 sharpened the sourcing: the
    # panel's own pin table IS in the repo (website/static/img/
    # ili9488-fpc40-pinout.png — pin 33: "Anode of Backlight, 2.9V-3.3V
    # Typical 3.1V", no resistor mention, no current rating), and the old
    # "components.md, quoting the panel, says VIA RESISTOR" line was our own
    # design note wearing quote marks. 8 parallel white LEDs at Vf 2.9-3.3 V
    # across a measured 3.327 V rail leaves 0.227 V at typical Vf, dropped
    # across nothing but the LEDs' own dynamic resistance, with a -2 mV/°C
    # tempco pushing current UP as the panel warms.
    #
    # The "1-10 ohm" figure below follows from that headroom (0.227/I_BL), not
    # from any rated current, so it is arithmetic on a guess. Do not fit a part
    # on the strength of it: the respin fix is to drive LED-A from +5V, where
    # 1.9 V of headroom lets a resistor actually set the current (~32 ohm at
    # 60 mA), or to use a constant-current driver.
    #
    # Full analysis and what is blocking the value: RESPIN section of
    # docs/known-issues.md.
    #
    # DFM v3 FIX (2026-04-10): previously used separate LCD_RD/LCD_BL nets for
    # the segment and via. Since both pins are hard-tied to +3V3 (no ESP32 GPIO
    # connection), creating a LCD_RD/LCD_BL via didn't actually connect to +3V3
    # (the +3V3 zone fill only connects to +3V3 nets) — leaving 2 dangling vias.
    # Fix: route directly on +3V3 net. The J4 pad gets +3V3 via the datasheet_specs
    # mapping (J4.8 and J4.29 updated to +3V3).
    #
    # Route LEFT from FPC pads to vias that connect to In2.Cu +3V3 zone.
    # VIA_X_PWR (133.6) conflicts with LCD_WR/GND approach traces.
    # LCD data approach verticals: LCD_D7@131.70, LCD_D6@131.00, LCD_D5@134.50.
    # RD via at x=131.0, y=39.75: ABOVE LCD_D6 end (y=34.25) — clear.
    # LED-A via at x=132.5, y=29.25: between LCD_D7 right edge (131.80) and
    #   J4 GND stub (133.585). Gap: 0.45mm to LCD_D7, 0.83mm to GND. ✓
    pos_rd = _fpc_display_pin(12)   # RD at pad 29 (y≈39.75), hard-tied to +3V3
    pos_bl = _fpc_display_pin(33)   # LED-A at pad 8 (y≈29.25), hard-tied to +3V3

    if pos_rd:
        px, py = pos_rd[0], pos_rd[1]
        # RESOLVED 2026-07-25 — this via is NOT on an orphan island.
        # verify_power_net_integrity reports +3V3 as a single connected group
        # (98 copper items, 29 pads, 4 filled islands total for 4 zones), and
        # J4.29 is in that group. A later zone re-fill merged the fragment the
        # note below described.
        #
        # The note is kept because its REASONING was wrong and must not be
        # copied: it argued that "display has 5 other +3V3 pads (2,3,7,8,34)
        # that reach the main zone, so loss of pad 29 is redundancy only".
        # Pad 29 is not a supply pad. It is the panel's RD strobe (FPC pin 12)
        # which is hard-tied HIGH because the display is write-only. On an
        # orphan island it is not a redundant supply connection — it is a
        # FLOATING CMOS input on the display controller. If a future fill ever
        # re-fragments this area, that is a real defect, not accepted debt.
        #
        # Original constraint, still true: the via cannot move further LEFT
        # without crossing the LCD net vertical at x=130.4 (different net,
        # same layer on B.Cu).
        via_x = 131.0
        parts.append(_seg(px, py, via_x, py, "B.Cu", W_FPC_PWR, n_3v3))
        parts.append(_via_net(via_x, py, n_3v3,
                              size=VIA_MIN, drill=VIA_MIN_DRILL))

    # ── +3V3 for SPI SDI (panel pin 13, pad 28) — R28-HIGH-1 fix ──
    # The panel's pin table (ili9488-fpc40-pinout.png, pin 13 "SPI SDI/SDA"):
    # "If not used, please fix this pin at VDDI or DGND level." It is an
    # INPUT — unlike pin 14 (SDO), which the same table says to leave open —
    # and it floated on every board fabricated so far (as-built note in
    # docs/known-issues.md). Tied to VDDI (+3V3), matching the RDX choice.
    #
    # Geometry: pad 28 (y=39.25) sits 0.5 mm below pad 29 (RDX, y=39.75),
    # which already carries +3V3 through the via at x=131.0. One vertical
    # same-net stub joins them — the exact pattern of the pin 38 -> 39 stub
    # at the top of the connector. No new via, no new crossing.
    pos_sdi = _fpc_display_pin(13)  # SPI SDI at pad 28 (y≈39.25)
    if pos_sdi and pos_rd:
        parts.append(_seg(pos_sdi[0], pos_sdi[1], pos_rd[0], pos_rd[1],
                          "B.Cu", W_FPC_PWR, n_3v3))

    if pos_bl:
        px, py = pos_bl[0], pos_bl[1]
        via_x = 132.5  # between LCD_D7 (131.80) and J4 GND stubs (133.58)
        parts.append(_seg(px, py, via_x, py, "B.Cu", W_FPC_PWR, n_3v3))
        parts.append(_via_net(via_x, py, n_3v3,
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
        # R21 FIX: was vy=50.25 — that position landed on tiny orphan
        # +3V3 fill island (x=131.71..132.29, y=49.95..50.55). Moved to
        # y=52.0 (below the orphan) to reach main +3V3 zone.
        # Clearance: main component row at y=52 has button pull-up vias
        # at x=46.80..96.80 (far from x=132). Q1 pads at (84-86, 52-54)
        # on B.Cu — 46mm away, no conflict.
        vx, vy = 132.0, 52.0  # main +3V3 zone (was 50.25 — orphan island)
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
