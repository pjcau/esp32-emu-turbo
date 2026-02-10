"""Sheet 3: Display - ST7796S 4.0in 8080 parallel interface."""

from ..sheet_base import SchematicSheet


class DisplaySheet(SchematicSheet):
    title = "Display - ST7796S 4.0in 8080 Parallel"
    page_number = 3
    needed_symbols = ["ST7796S_Module", "FPC_16P"]

    def build(self):
        # Title
        self.text("DISPLAY - ST7796S 4.0in 320x480", 30, 25, 5, True)
        self.text(
            "8-bit 8080 parallel interface"
            " (mandatory for SNES emulation speed)", 30, 33,
        )

        # Display module centered
        dx, dy = 148, 120
        self.sym(
            "ST7796S_Module", "U4", "ST7796S 4.0in 8080",
            dx, dy, range(1, 17),
        )

        # --- Power connections ---
        self.glabel("+3V3", dx - 30, dy - 15.24, 0, "input")
        self.wire(dx - 30, dy - 15.24, dx - 10.16, dy - 15.24)

        self.gnd(dx - 30, dy - 12.7)
        self.wire(dx - 30, dy - 12.7, dx - 10.16, dy - 12.7)

        # --- Control signals (left side) ---
        # 25mm wire stubs for readable labels
        ctrl_pins = [
            ("LCD_CS", -10.16, "GPIO12"),
            ("LCD_RST", -7.62, "GPIO13"),
            ("LCD_DC", -5.08, "GPIO14"),
            ("LCD_WR", -2.54, "GPIO46"),
            ("LCD_RD", 0, "GPIO3"),
            ("LCD_BL", 5.08, "GPIO45"),
        ]
        self.text("Control signals:", dx - 60, dy - 14, 2, True)
        for net, yoff, gpio in ctrl_pins:
            px = dx - 10.16
            py = dy + yoff
            self.wire(px, py, px - 25, py)
            self.glabel(net, px - 25, py, 180)
            self.text(gpio, px - 50, py, 1.5)

        # --- Data bus (right side) ---
        # 25mm wire stubs
        data_pins = [
            ("LCD_D0", -15.24, "GPIO4"),
            ("LCD_D1", -12.7, "GPIO5"),
            ("LCD_D2", -10.16, "GPIO6"),
            ("LCD_D3", -7.62, "GPIO7"),
            ("LCD_D4", -5.08, "GPIO8"),
            ("LCD_D5", -2.54, "GPIO9"),
            ("LCD_D6", 0, "GPIO10"),
            ("LCD_D7", 2.54, "GPIO11"),
        ]
        self.text("8-bit data bus:", dx + 25, dy - 20, 2, True)
        for net, yoff, gpio in data_pins:
            px = dx + 10.16
            py = dy + yoff
            self.wire(px, py, px + 25, py)
            self.glabel(net, px + 25, py, 0)
            self.text(gpio, px + 40, py, 1.5)

        # --- FPC Connector (physical connector on PCB back) ---
        fpc_x, fpc_y = 260, 120
        self.text("FPC RIBBON CONNECTOR", fpc_x - 15, fpc_y - 25, 2, True)
        self.text("(on PCB back, connects to display module)", fpc_x - 15, fpc_y - 20, 1.5)
        self.sym("FPC_16P", "J4", "FPC-16P-0.5mm", fpc_x, fpc_y, range(1, 17))

        # Wire display module outputs to FPC pins
        fpc_nets = [
            "+3V3", "GND", "LCD_CS", "LCD_RST", "LCD_DC", "LCD_WR",
            "LCD_RD", "LCD_BL",
            "LCD_D0", "LCD_D1", "LCD_D2", "LCD_D3",
            "LCD_D4", "LCD_D5", "LCD_D6", "LCD_D7",
        ]
        for i, net in enumerate(fpc_nets):
            py = fpc_y + 17.78 - i * 2.54
            px = fpc_x - 7.62
            self.glabel(net, px - 10, py, 180, "input")
            self.wire(px, py, px - 10, py)

        # --- Performance notes ---
        ny = 180
        self.text("Design Notes:", 30, ny, 2.54, True)
        self.text(
            "- 8080 parallel: 1 pixel (16-bit RGB565)"
            " = 2 bus cycles", 30, ny + 8,
        )
        self.text(
            "- SPI alternative: 16 clock cycles per pixel"
            " (too slow for 60fps SNES)", 30, ny + 14,
        )
        self.text(
            "- GPIO4-11 form contiguous 8-bit bus for"
            " efficient register-level DMA", 30, ny + 20,
        )
        self.text(
            "- WR strobes data on rising edge,"
            " RD directly from GPIO3", 30, ny + 26,
        )
        self.text(
            "- BL (backlight) via GPIO45 for"
            " brightness/power management", 30, ny + 32,
        )
        self.text(
            "- No level shifter: ESP32-S3 GPIO = 3.3V"
            " = display logic level", 30, ny + 38,
        )
