"""Split from routing.py 2026-07-26 — mechanical, AST-driven, proven by a
byte-identical regenerated .kicad_pcb. One domain per module; every helper
and every constant lives in _shared (original order, so import-time
execution is unchanged). See routing/__init__.py for the contract."""
from ._shared import (
    NET_ID,
    VIA_STD,
    VIA_STD_DRILL,
    W_DATA,
    _esp_pin,
    _init_pads,
    _pad,
    _seg,
    _via_net,
)




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
        # R32 (2026-08-03): 72.2 -> 72.35. The module's pads end at
        # x=72.00, so a 0.20mm hole at 72.20 sat 0.10mm from the pad edge
        # — under verify_via_in_pad's 0.15mm floor. 72.35 gives 0.25mm and
        # still leaves 0.42mm to LCD_BL's B.Cu column at x=73.02.
        shared_via_x = 72.35  # between ESP32 pad (71.25+0.35=71.60) and approach cols
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
