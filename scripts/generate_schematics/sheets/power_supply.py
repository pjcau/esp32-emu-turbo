"""Sheet 1: Power Supply - USB-C -> IP5306 bare IC -> AMS1117 -> 3.3V."""

from ..sheet_base import SchematicSheet


class PowerSupplySheet(SchematicSheet):
    title = "Power Supply"
    page_number = 1
    needed_symbols = [
        "USB_C", "IP5306", "AMS1117-3.3", "Conn_JST_PH_2",
        "Battery", "C", "R", "L", "PWR_FLAG", "SW_Push", "LED",
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

        # D+ / D- labels (left side of USB-C)
        self.glabel("USB_D+", ux - 12, uy - 3.81, 180)
        self.wire(ux - 7.62, uy - 3.81, ux - 12, uy - 3.81)
        self.glabel("USB_D-", ux - 12, uy, 180)
        self.wire(ux - 7.62, uy, ux - 12, uy)

        # CC1, CC2 pull-down resistors (5.1k for USB-C UFP detection)
        r1x, r1y = 78, 98
        r2x, r2y = 90, 98
        self.sym("R", "R1", "5.1k", r1x, r1y, ["1", "2"])
        self.sym("R", "R2", "5.1k", r2x, r2y, ["1", "2"])
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

        # +5V power symbol and global label
        self.v5(215, vout_turn_y - 5)
        self.wire(215, vout_turn_y - 5, 215, vout_turn_y)
        self.glabel("+5V", 225, vout_turn_y, 0, "output")
        self.wire(215, vout_turn_y, 225, vout_turn_y)

        # Power flag on 5V rail
        self.parts.append(self.ctx.power_symbol(
            "PWR_FLAG", "#FLG01", "PWR_FLAG",
            215, vout_turn_y + 5))
        self.wire(215, vout_turn_y, 215, vout_turn_y + 5)

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

        # ---- Battery: JST PH connector + Battery symbol ----
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

        # Wire BAT line to JST pin1
        # BAT wire already goes to l1_x and cbat_x
        # Extend to JST: horizontal from cbat_x to jst_plus_x
        self.wire(cbat_x, bat_y, jst_plus_x, bat_y)
        self.wire(jst_plus_x, bat_y, jst_plus_x, jst_plus_y)

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
        self.glabel("BAT+", jst_x + 5, jst_plus_y, 0)
        self.wire(jst_x + 3.81, jst_plus_y, jst_x + 5, jst_plus_y)
        self.glabel("BAT+", bt_x - 5, bt_y - 3.81, 180)
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
