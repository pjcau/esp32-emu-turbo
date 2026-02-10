"""Sheet 7: Joystick - PSP analog joystick with 2 ADC channels."""

from ..sheet_base import SchematicSheet


class JoystickSheet(SchematicSheet):
    title = "Joystick - PSP Analog (Optional)"
    page_number = 7
    needed_symbols = ["PSP_Joystick"]

    def build(self):
        # Title
        self.text(
            "JOYSTICK - PSP Analog Stick (Optional)", 30, 25, 5, True,
        )
        self.text(
            "2-axis analog input via ESP32-S3 ADC channels", 30, 33,
        )

        # Joystick module
        jx, jy = 120, 110
        self.sym(
            "PSP_Joystick", "J2", "PSP_Joystick",
            jx, jy, range(1, 5),
        )

        # Power: +3V3
        self.glabel("+3V3", jx - 25, jy - 3.81, 0, "input")
        self.wire(jx - 25, jy - 3.81, jx - 7.62, jy - 3.81)

        # GND
        self.gnd(jx - 25, jy + 8)
        self.wire(jx - 7.62, jy, jx - 25, jy)
        self.wire(jx - 25, jy, jx - 25, jy + 8)

        # X axis output (with longer wire stub)
        self.wire(jx + 7.62, jy - 3.81, jx + 30, jy - 3.81)
        self.glabel("JOY_X", jx + 30, jy - 3.81, 0)
        self.text("GPIO20 (ADC2_CH9)", jx + 45, jy - 3.81)

        # Y axis output
        self.wire(jx + 7.62, jy, jx + 30, jy)
        self.glabel("JOY_Y", jx + 30, jy, 0)
        self.text("GPIO44/RX0 (ADC2_CH7)", jx + 45, jy)

        # Notes
        ny = 160
        self.text("Design Notes:", 30, ny, 2.54, True)
        self.text(
            "- PSP-style mini analog stick with"
            " potentiometer outputs", 30, ny + 8,
        )
        self.text(
            "- X/Y outputs: 0V (min) to 3.3V (max),"
            " ~1.65V at center", 30, ny + 14,
        )
        self.text(
            "- ESP32-S3 ADC2: 12-bit resolution"
            " (4096 steps per axis)", 30, ny + 20,
        )
        self.text(
            "- Optional: can be omitted for"
            " D-pad-only build", 30, ny + 26,
        )
        self.text(
            "- GPIO44 shares RX0 UART pin;"
            " debug input unavailable when connected", 30, ny + 32,
        )
        self.text(
            "- GPIO43 (TX0) still works for"
            " debug UART output", 30, ny + 38,
        )
