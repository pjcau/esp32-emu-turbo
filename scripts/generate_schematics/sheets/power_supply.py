"""Sheet 1: Power Supply - USB-C -> IP5306 -> AMS1117 -> 3.3V."""

from ..sheet_base import SchematicSheet


class PowerSupplySheet(SchematicSheet):
    title = "Power Supply"
    page_number = 1
    needed_symbols = [
        "USB_C", "IP5306_Module", "AMS1117-3.3", "Battery",
        "C", "R", "PWR_FLAG",
    ]

    def build(self):
        # Title
        self.text("POWER SUPPLY", 30, 25, 5, True)
        self.text("USB-C -> IP5306 (charge + boost) -> AMS1117-3.3 -> 3.3V rail", 30, 33)

        # ---- USB-C Connector (left side) ----
        ux, uy = 55, 85
        self.sym("USB_C", "J1", "USB_C", ux, uy, range(1, 7))

        # CC1, CC2 pull-down resistors (5.1k for USB-C detection)
        r1x, r1y = ux + 25, uy + 10
        r2x, r2y = ux + 35, uy + 10
        self.sym("R", "R1", "5.1k", r1x, r1y, ["1", "2"])
        self.sym("R", "R2", "5.1k", r2x, r2y, ["1", "2"])
        # CC1 wire from USB-C pin to R1 (orthogonal L-shape)
        self.wire(ux + 7.62, uy, r1x, uy)
        self.wire(r1x, uy, r1x, r1y - 3.81)
        # CC2 wire from USB-C pin to R2 (orthogonal L-shape)
        self.wire(ux + 7.62, uy - 3.81, r2x, uy - 3.81)
        self.wire(r2x, uy - 3.81, r2x, r2y - 3.81)
        # R1 R2 GND
        self.gnd(r1x, r1y + 8)
        self.wire(r1x, r1y + 3.81, r1x, r1y + 8)
        self.gnd(r2x, r2y + 8)
        self.wire(r2x, r2y + 3.81, r2x, r2y + 8)
        # USB GND
        self.gnd(ux, uy + 13)
        self.wire(ux, uy + 8.89, ux, uy + 13)

        # VBUS wire to IP5306 (orthogonal L-shape, no diagonal)
        ip_x, ip_y = 145, 85
        vbus_y = uy + 3.81
        ip_in_y = ip_y - 3.81
        # Horizontal from USB VBUS pin
        self.wire(ux + 7.62, vbus_y, ux + 20, vbus_y)
        # Vertical jog to IP5306 input level
        self.wire(ux + 20, vbus_y, ux + 20, ip_in_y)
        # Horizontal into IP5306 USB_5V pin
        self.wire(ux + 20, ip_in_y, ip_x - 10.16, ip_in_y)

        # VBUS label
        self.label("VBUS", ux + 12, vbus_y - 2)

        # ---- IP5306 Module ----
        self.sym("IP5306_Module", "U2", "IP5306 USB-C", ip_x, ip_y, range(1, 6))
        # IP5306 GND
        self.gnd(ip_x - 17, ip_y + 8)
        self.wire(ip_x - 10.16, ip_y, ip_x - 17, ip_y)
        self.wire(ip_x - 17, ip_y, ip_x - 17, ip_y + 8)

        # ---- Battery ----
        bt_x, bt_y = ip_x + 45, ip_y - 15
        self.sym("Battery", "BT1", "LiPo 3.7V 5000mAh", bt_x, bt_y, ["1", "2"])
        self.text("105080", bt_x + 5, bt_y - 3)
        self.text("3.7V 5000mAh", bt_x + 5, bt_y + 1)
        # BAT+ wire (orthogonal)
        bat_plus_y = ip_y - 3.81
        self.wire(ip_x + 10.16, bat_plus_y, bt_x, bat_plus_y)
        self.wire(bt_x, bat_plus_y, bt_x, bt_y - 3.81)
        # BAT- wire (orthogonal L-shape)
        bat_minus_y = ip_y
        self.wire(ip_x + 10.16, bat_minus_y, bt_x + 10, bat_minus_y)
        self.wire(bt_x + 10, bat_minus_y, bt_x + 10, bt_y + 3.81)
        self.wire(bt_x + 10, bt_y + 3.81, bt_x, bt_y + 3.81)
        # Battery GND
        self.gnd(bt_x, bt_y + 10)
        self.wire(bt_x, bt_y + 3.81, bt_x, bt_y + 10)

        # ---- 5V output rail ----
        out5v_x = ip_x + 10.16
        out5v_y = ip_y + 3.81
        self.wire(out5v_x, out5v_y, out5v_x + 15, out5v_y)
        self.v5(out5v_x + 15, out5v_y - 5)
        self.wire(out5v_x + 15, out5v_y - 5, out5v_x + 15, out5v_y)
        # Global label for +5V
        self.glabel("+5V", out5v_x + 20, out5v_y, 0, "output")
        self.wire(out5v_x + 15, out5v_y, out5v_x + 20, out5v_y)

        # Power flag on 5V rail
        self.parts.append(self.ctx.power_symbol(
            "PWR_FLAG", "#FLG01", "PWR_FLAG",
            out5v_x + 15, out5v_y + 5))
        self.wire(out5v_x + 15, out5v_y, out5v_x + 15, out5v_y + 5)

        # ═══════════════════════════════════════════════════
        # VOLTAGE REGULATOR SECTION (below)
        # ═══════════════════════════════════════════════════
        self.text("VOLTAGE REGULATOR", 30, 130, 3.81, True)
        self.text("5V -> AMS1117-3.3 -> 3.3V (800mA max)", 30, 137)

        # ---- Input cap for AMS1117 ----
        ams_x, ams_y = 80, 160
        c1x, c1y = ams_x - 25, ams_y
        self.sym("C", "C1", "10uF", c1x, c1y, ["1", "2"])
        self.text("Input", c1x - 5, c1y - 7, 1.5)
        self.v5(c1x, c1y - 10)
        self.wire(c1x, c1y - 10, c1x, c1y - 3.81)
        self.gnd(c1x, c1y + 10)
        self.wire(c1x, c1y + 3.81, c1x, c1y + 10)

        # ---- AMS1117-3.3 Regulator ----
        self.sym("AMS1117-3.3", "U3", "AMS1117-3.3", ams_x, ams_y, ["1", "2", "3"])
        # VIN wire from 5V rail (orthogonal)
        self.v5(ams_x - 15, ams_y - 10)
        self.wire(ams_x - 15, ams_y - 10, ams_x - 15, ams_y - 2.54)
        self.wire(ams_x - 7.62, ams_y - 2.54, ams_x - 15, ams_y - 2.54)
        # AMS1117 GND
        self.gnd(ams_x, ams_y + 13)
        self.wire(ams_x, ams_y + 6.35, ams_x, ams_y + 13)

        # ---- Output cap (tantalum) ----
        c2x, c2y = ams_x + 30, ams_y
        self.sym("C", "C2", "22uF tant.", c2x, c2y, ["1", "2"])
        self.text("Output", c2x - 3, c2y - 7, 1.5)
        # VOUT to cap (horizontal)
        self.wire(ams_x + 7.62, ams_y - 2.54, c2x, ams_y - 2.54)
        self.wire(c2x, ams_y - 2.54, c2x, c2y - 3.81)
        self.gnd(c2x, c2y + 10)
        self.wire(c2x, c2y + 3.81, c2x, c2y + 10)

        # 3.3V output power symbol
        self.v33(c2x, c2y - 12)
        self.wire(c2x, c2y - 12, c2x, c2y - 3.81)
        # Global label for +3V3
        self.glabel("+3V3", c2x + 12, ams_y - 2.54, 0, "output")
        self.wire(c2x, ams_y - 2.54, c2x + 12, ams_y - 2.54)

        # ═══════════════════════════════════════════════════
        # NOTES
        # ═══════════════════════════════════════════════════
        ny = 195
        self.text("Design Notes:", 30, ny, 2.54, True)
        self.text("- IP5306 provides charge-and-play (simultaneous charging + 5V boost output)", 30, ny + 6)
        self.text("- AMS1117-3.3 provides stable 3.3V for ESP32-S3 and all peripherals (800mA max)", 30, ny + 12)
        self.text("- 22uF tantalum on LDO VOUT required for regulator stability", 30, ny + 18)
        self.text("- 5.1kR pull-downs on CC1/CC2 identify device as USB-C UFP (5V sink)", 30, ny + 24)
        self.text("- Battery: LiPo 3.7V 5000mAh (105080 form factor, 50x80x10mm)", 30, ny + 30)
