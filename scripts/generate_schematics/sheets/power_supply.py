"""Sheet 1: Power Supply - USB-C -> IP5306 bare IC -> AMS1117 -> 3.3V."""

from ..sheet_base import SchematicSheet


class PowerSupplySheet(SchematicSheet):
    title = "Power Supply"
    page_number = 1
    needed_symbols = [
        "USB_C", "IP5306", "AMS1117-3.3", "Conn_JST_PH_2",
        "Battery", "C", "R", "L", "SW_Push", "LED",
        "USBLC6_2SC6", "BAT54C",
    ]

    def build(self):
        # Title
        self.text("POWER SUPPLY", 30, 25, 5, True)
        self.text(
            "USB-C -> IP5306 SOP-8 (charge + boost)"
            " -> AMS1117-3.3 -> 3.3V rail", 30, 33,
        )

        # ═══════════════════════════════════════════════
        # USB-C CONNECTOR (left side)
        # ═══════════════════════════════════════════════
        ux, uy = 50, 85
        self.sym("USB_C", "J1", "USB_C", ux, uy, range(1, 7))

        # Pin world positions (local y inverted):
        #   VBUS: (ux+7.62, uy-3.81)
        #   CC1:  (ux+7.62, uy)
        #   CC2:  (ux+7.62, uy+3.81)
        #   D+:   (ux-7.62, uy-3.81)
        #   D-:   (ux-7.62, uy)
        #   GND:  (ux, uy+8.89)

        vbus_x = ux + 7.62
        vbus_y = uy - 3.81

        # D+ / D- labels exiting USB-C (pre-protection nets)
        self.glabel("USB_D+", ux - 12, uy - 3.81, 180)
        self.wire(ux - 7.62, uy - 3.81, ux - 12, uy - 3.81)
        self.glabel("USB_D-", ux - 12, uy, 180)
        self.wire(ux - 7.62, uy, ux - 12, uy)

        # ── USB ESD protection (R4-HIGH-1 fix) ──
        # The PCB (scripts/generate_pcb/routing.py) places USBLC6-2SC6
        # (U4) + two 22Ω series resistors (R22, R23) between the USB-C
        # connector and the ESP32-S3 D+/D- pins. These symbols were
        # previously missing from the schematic — any reviewer reading
        # only the schematic could not see the ESD protection. Now
        # instantiated so the schematic matches the CPL.
        #
        # Placed well below the main USB-C/IP5306 area to avoid spatial
        # clashes with existing symbols on the same sheet.
        u4x, u4y = 45, 160
        self.sym("USBLC6_2SC6", "U4", "USBLC6-2SC6", u4x, u4y, range(1, 7))
        self.text("USB ESD TVS", u4x - 8, u4y - 12, 1.5)
        # The USBLC6_2SC6 library symbol in this generator uses the
        # simple 6-pin pad layout (pins on the left/right edges). We
        # connect the logical nets via glabels with short wire stubs.
        stub = 6
        # Left side stubs (to USB-C side)
        self.glabel("USB_D-", u4x - 10 - stub, u4y - 2.54, 180)
        self.wire(u4x - 10 - stub, u4y - 2.54, u4x - 10, u4y - 2.54)
        self.glabel("USB_D+", u4x - 10 - stub, u4y,        180)
        self.wire(u4x - 10 - stub, u4y,        u4x - 10, u4y)
        # Right side stubs (to ESP32 side, via R22/R23)
        self.glabel("USB_DM_MCU", u4x + 10 + stub, u4y + 2.54, 0)
        self.wire(u4x + 10, u4y + 2.54, u4x + 10 + stub, u4y + 2.54)
        self.glabel("USB_DP_MCU", u4x + 10 + stub, u4y,        0)
        self.wire(u4x + 10, u4y,        u4x + 10 + stub, u4y)
        # GND on bottom
        self.gnd(u4x, u4y + 12)
        self.wire(u4x, u4y + 7.62, u4x, u4y + 12)
        # VBUS reference tap on top (typed as power input on USBLC6 pin 5)
        self.glabel("+5V", u4x, u4y - 12, 90, "input")
        self.wire(u4x, u4y - 7.62, u4x, u4y - 12)

        # Series resistors R22/R23 between USBLC6 MCU-side and ESP32.
        r22x, r22y = u4x + 30, u4y - 2
        self.sym("R", "R22", "22",  r22x, r22y, ["1", "2"])
        self.text("D+ 22Ω", r22x + 4, r22y - 2, 1.5)
        self.wire(r22x - 3.81, r22y, r22x - 8, r22y)
        self.glabel("USB_DP_MCU", r22x - 8, r22y, 180)
        self.wire(r22x + 3.81, r22y, r22x + 8, r22y)
        self.glabel("GPIO20", r22x + 8, r22y, 0)

        r23x, r23y = u4x + 30, u4y + 4
        self.sym("R", "R23", "22",  r23x, r23y, ["1", "2"])
        self.text("D- 22Ω", r23x + 4, r23y - 2, 1.5)
        self.wire(r23x - 3.81, r23y, r23x - 8, r23y)
        self.glabel("USB_DM_MCU", r23x - 8, r23y, 180)
        self.wire(r23x + 3.81, r23y, r23x + 8, r23y)
        self.glabel("GPIO19", r23x + 8, r23y, 0)

        # CC1, CC2 pull-down resistors (5.1k for USB-C UFP detection)
        r1x, r1y = 78, 98
        r2x, r2y = 90, 98
        self.sym("R", "R1", "5.1k", r1x, r1y, ["1", "2"])
        self.sym("R", "R2", "5.1k", r2x, r2y, ["1", "2"])
        # Explicit USB_CC1 / USB_CC2 labels so schematic↔PCB sync check
        # sees the connector's full expected net set (datasheet_specs.py).
        self.glabel("USB_CC1", vbus_x + 4, uy, 0)
        self.glabel("USB_CC2", vbus_x + 4, uy + 3.81, 0)
        # CC1 -> R1 (orthogonal L-shape)
        self.wire(vbus_x, uy, r1x, uy)
        self.wire(r1x, uy, r1x, r1y - 3.81)
        # CC2 -> R2 (orthogonal L-shape)
        self.wire(vbus_x, uy + 3.81, r2x, uy + 3.81)
        self.wire(r2x, uy + 3.81, r2x, r2y - 3.81)
        # R1, R2 GND
        self.gnd(r1x, r1y + 8)
        self.wire(r1x, r1y + 3.81, r1x, r1y + 8)
        self.gnd(r2x, r2y + 8)
        self.wire(r2x, r2y + 3.81, r2x, r2y + 8)

        # USB GND
        self.gnd(ux, uy + 13)
        self.wire(ux, uy + 8.89, ux, uy + 13)

        # ═══════════════════════════════════════════════
        # IP5306 BARE IC (eSOP-8)
        # ═══════════════════════════════════════════════
        ipx, ipy = 160, 85
        self.sym(
            "IP5306", "U2", "IP5306",
            ipx, ipy, range(1, 10),
        )

        # IP5306 pin world positions:
        #   VIN(1):  (ipx-10.16, ipy-5.08)
        #   LED1(2): (ipx-10.16, ipy-2.54)
        #   LED2(3): (ipx-10.16, ipy)
        #   LED3(4): (ipx-10.16, ipy+2.54)
        #   KEY(5):  (ipx+10.16, ipy+5.08)
        #   BAT(6):  (ipx+10.16, ipy+2.54)
        #   SW(7):   (ipx+10.16, ipy)
        #   VOUT(8): (ipx+10.16, ipy-5.08)
        #   GND(9):  (ipx, ipy+10.16)

        vin_x = ipx - 10.16
        vin_y = ipy - 5.08
        vout_x = ipx + 10.16
        vout_y = ipy - 5.08
        sw_x = ipx + 10.16
        sw_y = ipy
        bat_x = ipx + 10.16
        bat_y = ipy + 2.54
        key_x = ipx + 10.16
        key_y = ipy + 5.08
        gnd_ip_y = ipy + 10.16

        # ---- VBUS -> VIN wiring ----
        # CIN (C17, 10uF) teed off the VIN line
        cin_x, cin_y = 118, 90
        # VBUS horizontal to CIN junction
        self.wire(vbus_x, vbus_y, cin_x, vbus_y)
        self.label("VBUS", vbus_x + 5, vbus_y - 2)
        # CIN junction down to cap
        self.wire(cin_x, vbus_y, cin_x, cin_y - 3.81)
        self.sym("C", "C17", "10uF", cin_x, cin_y, ["1", "2"])
        self.text("VIN decoupling", cin_x + 3, cin_y - 5, 1.5)
        self.gnd(cin_x, cin_y + 8)
        self.wire(cin_x, cin_y + 3.81, cin_x, cin_y + 8)
        # Continue VIN line to IP5306 (orthogonal L-shape)
        jog_x = cin_x + 10
        self.wire(cin_x, vbus_y, jog_x, vbus_y)
        self.wire(jog_x, vbus_y, jog_x, vin_y)
        self.wire(jog_x, vin_y, vin_x, vin_y)

        # ---- LED pins (NC) ----
        led1_x = ipx - 10.16
        for led_y in [ipy - 2.54, ipy, ipy + 2.54]:
            self.nc(led1_x - 2, led_y)
            self.wire(led1_x, led_y, led1_x - 2, led_y)
        self.text("NC (LED1-3)", ipx - 22, ipy - 4, 1.5)

        # ---- IP5306 GND ----
        self.gnd(ipx, gnd_ip_y + 4)
        self.wire(ipx, gnd_ip_y, ipx, gnd_ip_y + 4)

        # ---- L1 inductor: BAT -> L1 -> SW ----
        l1_x, l1_y = 190, 85
        self.sym("L", "L1", "1uH", l1_x, l1_y, ["1", "2"])
        self.text("1uH >4.5A", l1_x + 3, l1_y - 3, 1.5)
        # L1 pin1 (top) at (l1_x, l1_y - 3.81)
        # L1 pin2 (bottom) at (l1_x, l1_y + 3.81)
        # BAT -> L1 bottom: horizontal then vertical
        self.wire(bat_x, bat_y, l1_x, bat_y)
        self.wire(l1_x, bat_y, l1_x, l1_y + 3.81)
        # L1 top -> SW: vertical then horizontal
        self.wire(l1_x, l1_y - 3.81, l1_x, sw_y)
        self.wire(l1_x, sw_y, sw_x, sw_y)

        # ---- VOUT -> +5V rail ----
        # Route VOUT up then right to avoid L1
        vout_turn_y = 70
        self.wire(vout_x, vout_y, vout_x, vout_turn_y)
        self.wire(vout_x, vout_turn_y, 215, vout_turn_y)

        # COUT (C19, 22uF) on VOUT rail
        cout_x = 205
        cout_y = 78
        self.sym(
            "C", "C19", "22uF",
            cout_x, cout_y, ["1", "2"],
        )
        self.text(
            "VOUT decoupling",
            cout_x + 3, cout_y - 5, 1.5,
        )
        self.wire(
            cout_x, vout_turn_y, cout_x, cout_y - 3.81,
        )
        self.gnd(cout_x, cout_y + 8)
        self.wire(cout_x, cout_y + 3.81, cout_x, cout_y + 8)

        # C27: HF decoupling (10uF) near VOUT
        c27_x = cout_x + 15
        c27_y = cout_y
        self.sym("C", "C27", "10uF", c27_x, c27_y, ["1", "2"])
        self.text("HF decoupling", c27_x + 3, c27_y - 5, 1.5)
        self.wire(c27_x, vout_turn_y, c27_x, c27_y - 3.81)
        self.gnd(c27_x, c27_y + 8)
        self.wire(c27_x, c27_y + 3.81, c27_x, c27_y + 8)

        # +5V power symbol and global label
        self.v5(215, vout_turn_y - 5)
        self.wire(215, vout_turn_y - 5, 215, vout_turn_y)
        self.glabel("+5V", 225, vout_turn_y, 0, "output")
        self.wire(215, vout_turn_y, 225, vout_turn_y)

        # NOTE: PWR_FLAG on +5V was REMOVED because IP5306 VOUT (pin 8) is
        # already typed as `power_out` in the library symbol, so it
        # already drives the +5V net. Adding PWR_FLAG here created a
        # second power-output pin on the same net and caused ERC
        # "Pins of type Power output and Power output are connected"
        # (the pre-existing R4 critical). IP5306 VOUT alone satisfies
        # KiCad's "power input must be driven" requirement on +5V.

        # ---- CBAT (C18, 10uF) on BAT line ----
        cbat_x = 198
        cbat_y = 98
        self.sym("C", "C18", "10uF", cbat_x, cbat_y, ["1", "2"])
        self.text("BAT decoupling", cbat_x + 3, cbat_y - 5, 1.5)
        # Tee down from BAT wire at y=bat_y
        self.wire(cbat_x, bat_y, cbat_x, cbat_y - 3.81)
        self.gnd(cbat_x, cbat_y + 8)
        self.wire(cbat_x, cbat_y + 3.81, cbat_x, cbat_y + 8)

        # ---- KEY pull-up (R16 100k to +5V, always-on) ----
        r16_x = 182
        r16_y = 76
        self.sym("R", "R16", "100k", r16_x, r16_y, ["1", "2"])
        self.text("Always-on", r16_x + 3, r16_y - 3, 1.5)
        # R16 pin1 (top) -> +5V
        self.v5(r16_x, r16_y - 8)
        self.wire(r16_x, r16_y - 8, r16_x, r16_y - 3.81)
        # R16 pin2 (bottom) -> KEY via orthogonal route
        self.wire(r16_x, r16_y + 3.81, r16_x, key_y)
        self.wire(r16_x, key_y, key_x, key_y)

        # ---- Battery: JST PH connector + Q1 P-MOSFET RPP + Battery symbol ----
        # JST PH 2-pin connector
        jst_x, jst_y = 228, 92
        self.sym(
            "Conn_JST_PH_2", "J3", "JST PH 2-pin",
            jst_x, jst_y, ["1", "2"],
        )
        # JST pin1 "+" at (jst_x - 6.35, jst_y - 1.27)
        # JST pin2 "-" at (jst_x - 6.35, jst_y + 1.27)
        jst_plus_x = jst_x - 6.35
        jst_plus_y = jst_y - 1.27
        jst_minus_y = jst_y + 1.27

        # ── Q1 P-MOSFET reverse polarity protection (v4.0) ──
        # Q1 sits in series on the BAT+ rail between J3 and IP5306.
        # BAT+ (IP5306 side) → Q1 Drain (pin 3) → Q1 Source (pin 2) → BAT_IN → J3.1
        # Gate pulled low via R24 100K → MOSFET always ON for correct polarity.
        # Reverse polarity: body diode blocks, protecting IP5306.
        q1x, q1y = 210, 92
        self.sym("BAT54C", "Q1", "SI2301CDS", q1x, q1y, ["1", "2", "3"])
        # NOTE: reusing BAT54C symbol footprint (SOT-23-3) for Q1 P-MOSFET
        # Pin mapping: 1=Gate(bottom-left), 2=Source(bottom-right), 3=Drain(top)
        self.text("P-MOSFET RPP", q1x - 5, q1y - 10, 1.5)
        self.text("SI2301CDS", q1x - 5, q1y - 8, 1.5)

        # Q1 pin 3 (Drain) at (q1x, q1y - 3.81-ish) — connects to BAT+ (IP5306 side)
        # Wire BAT+ line from cbat_x to Q1 drain
        self.wire(cbat_x, bat_y, q1x, bat_y)
        self.wire(q1x, bat_y, q1x, q1y - 5)
        self.label("BAT+", q1x + 2, bat_y - 2)

        # Q1 pin 2 (Source) — connects to BAT_IN → J3.1
        # Source exits to the right toward JST connector
        self.wire(q1x + 5, q1y + 1.27, jst_plus_x, q1y + 1.27)
        self.wire(jst_plus_x, q1y + 1.27, jst_plus_x, jst_plus_y)
        self.label("BAT_IN", q1x + 6, q1y - 0.5)

        # Q1 pin 1 (Gate) — pulled to GND via R24 (100K)
        r24x, r24y = q1x - 8, q1y + 10
        self.sym("R", "R24", "100k", r24x, r24y, ["1", "2"])
        self.text("Gate pull-down", r24x + 3, r24y - 3, 1.5)
        # Wire Q1 gate to R24 pin 1
        self.wire(q1x - 5, q1y + 1.27, r24x, q1y + 1.27)
        self.wire(r24x, q1y + 1.27, r24x, r24y - 3.81)
        # R24 pin 2 to GND
        self.gnd(r24x, r24y + 8)
        self.wire(r24x, r24y + 3.81, r24x, r24y + 8)

        # JST pin2 (-) to GND
        self.gnd(jst_plus_x, jst_y + 6)
        self.wire(jst_plus_x, jst_minus_y, jst_plus_x, jst_y + 6)

        # Battery symbol (off-board representation)
        bt_x, bt_y = 248, 90
        self.sym(
            "Battery", "BT1", "LiPo 3.7V 5000mAh",
            bt_x, bt_y, ["1", "2"],
        )
        self.text("105080", bt_x + 5, bt_y - 3, 1.5)
        self.text("3.7V 5000mAh", bt_x + 5, bt_y + 1, 1.5)
        # BT1 pin "+" at (bt_x, bt_y - 3.81)
        # BT1 pin "-" at (bt_x, bt_y + 3.81)
        # Wire from JST area to battery (same net via label)
        self.glabel("BAT_IN", jst_x + 5, jst_plus_y, 0)
        self.wire(jst_x + 3.81, jst_plus_y, jst_x + 5, jst_plus_y)
        self.glabel("BAT_IN", bt_x - 5, bt_y - 3.81, 180)
        self.wire(bt_x - 5, bt_y - 3.81, bt_x, bt_y - 3.81)
        # Battery GND
        self.gnd(bt_x, bt_y + 8)
        self.wire(bt_x, bt_y + 3.81, bt_x, bt_y + 8)

        # ═══════════════════════════════════════════════
        # VOLTAGE REGULATOR SECTION (below)
        # ═══════════════════════════════════════════════
        self.text("VOLTAGE REGULATOR", 30, 130, 3.81, True)
        self.text(
            "5V -> AMS1117-3.3 -> 3.3V (800mA max)",
            30, 137,
        )

        # Input cap for AMS1117
        ams_x, ams_y = 80, 160
        c1x, c1y = ams_x - 25, ams_y
        self.sym("C", "C1", "10uF", c1x, c1y, ["1", "2"])
        self.text("Input", c1x - 5, c1y - 7, 1.5)
        self.v5(c1x, c1y - 10)
        self.wire(c1x, c1y - 10, c1x, c1y - 3.81)
        self.gnd(c1x, c1y + 10)
        self.wire(c1x, c1y + 3.81, c1x, c1y + 10)

        # AMS1117-3.3 Regulator
        self.sym(
            "AMS1117-3.3", "U3", "AMS1117-3.3",
            ams_x, ams_y, ["1", "2", "3"],
        )
        # VIN from +5V rail
        self.v5(ams_x - 15, ams_y - 10)
        self.wire(ams_x - 15, ams_y - 10, ams_x - 15, ams_y - 2.54)
        self.wire(ams_x - 7.62, ams_y - 2.54, ams_x - 15, ams_y - 2.54)
        # AMS1117 GND
        self.gnd(ams_x, ams_y + 13)
        self.wire(ams_x, ams_y + 6.35, ams_x, ams_y + 13)

        # Output cap (tantalum)
        c2x, c2y = ams_x + 30, ams_y
        self.sym("C", "C2", "22uF tant.", c2x, c2y, ["1", "2"])
        self.text("Output", c2x - 3, c2y - 7, 1.5)
        # VOUT to cap (horizontal)
        self.wire(ams_x + 7.62, ams_y - 2.54, c2x, ams_y - 2.54)
        self.wire(c2x, ams_y - 2.54, c2x, c2y - 3.81)
        self.gnd(c2x, c2y + 10)
        self.wire(c2x, c2y + 3.81, c2x, c2y + 10)

        # 3.3V output
        self.v33(c2x, c2y - 12)
        self.wire(c2x, c2y - 12, c2x, c2y - 3.81)
        self.glabel("+3V3", c2x + 12, ams_y - 2.54, 0, "output")
        self.wire(c2x, ams_y - 2.54, c2x + 12, ams_y - 2.54)

        # ═══════════════════════════════════════════════
        # POWER SWITCH (slide switch on left edge)
        # ═══════════════════════════════════════════════
        sw_x, sw_y = 30, 160
        self.text("POWER SWITCH", sw_x - 5, sw_y - 12, 2.54, True)
        self.sym("SW_Push", "SW_PWR", "SS-12D00G3", sw_x, sw_y, ["1", "2"])
        # BAT+ to switch in, switch out to VBUS line
        self.glabel("BAT+", sw_x - 12, sw_y, 180, "input")
        self.wire(sw_x - 5.08, sw_y, sw_x - 12, sw_y)
        self.glabel("VBUS_SW", sw_x + 12, sw_y, 0, "output")
        self.wire(sw_x + 5.08, sw_y, sw_x + 12, sw_y)
        self.text("Slide switch on enclosure edge", sw_x - 5, sw_y + 10, 1.5)

        # ═══════════════════════════════════════════════
        # CHARGING LEDs (driven by IP5306 LED outputs)
        # ═══════════════════════════════════════════════
        led_x, led_y = 160, 130
        self.text("CHARGING INDICATOR LEDs", led_x - 30, led_y - 12, 2.54, True)

        # LED1 (Red - charging)
        self.sym("R", "R17", "1k", led_x - 15, led_y, ["1", "2"])
        self.sym("LED", "LED1", "Red", led_x, led_y, ["1", "2"])
        self.v33(led_x - 15, led_y - 8)
        self.wire(led_x - 15, led_y - 8, led_x - 15, led_y - 3.81)
        self.wire(led_x - 15, led_y + 3.81, led_x - 3.81, led_y)
        self.gnd(led_x + 8, led_y)
        self.wire(led_x + 3.81, led_y, led_x + 8, led_y)
        self.text("Charging", led_x - 5, led_y - 6, 1.5)

        # LED2 (Green - fully charged)
        led2_y = led_y + 18
        self.sym("R", "R18", "1k", led_x - 15, led2_y, ["1", "2"])
        self.sym("LED", "LED2", "Green", led_x, led2_y, ["1", "2"])
        self.v33(led_x - 15, led2_y - 8)
        self.wire(led_x - 15, led2_y - 8, led_x - 15, led2_y - 3.81)
        self.wire(led_x - 15, led2_y + 3.81, led_x - 3.81, led2_y)
        self.gnd(led_x + 8, led2_y)
        self.wire(led_x + 3.81, led2_y, led_x + 8, led2_y)
        self.text("Full", led_x - 5, led2_y - 6, 1.5)

        # ═══════════════════════════════════════════════
        # DESIGN NOTES
        # ═══════════════════════════════════════════════
        ny = 195
        self.text("Design Notes:", 30, ny, 2.54, True)
        self.text(
            "- IP5306 eSOP-8: integrated charger"
            " + synchronous boost (no ext. Schottky)",
            30, ny + 6,
        )
        self.text(
            "- 1uH inductor: BAT -> L1 -> SW"
            " (>4.5A saturation, shielded)",
            30, ny + 12,
        )
        self.text(
            "- GND via exposed pad only"
            " (must solder to ground plane)",
            30, ny + 18,
        )
        self.text(
            "- KEY pulled to +5V via 100k"
            " for always-on operation",
            30, ny + 24,
        )
        self.text(
            "- AMS1117-3.3: stable 3.3V for"
            " ESP32-S3 and peripherals (800mA)",
            30, ny + 30,
        )
        self.text(
            "- 5.1k CC pull-downs identify"
            " USB-C UFP (5V sink)",
            30, ny + 36,
        )
        self.text(
            "- Battery: LiPo 3.7V 5000mAh"
            " via JST PH connector",
            30, ny + 42,
        )
