"""Sheet 4: Audio - I2S DAC -> PAM8403 -> Speaker."""

from ..sheet_base import SchematicSheet


class AudioSheet(SchematicSheet):
    title = "Audio - I2S -> PAM8403 -> Speaker"
    page_number = 4
    needed_symbols = ["PAM8403_Module", "Speaker"]

    def build(self):
        # Title
        self.text("AUDIO OUTPUT", 30, 25, 5, True)
        self.text(
            "I2S DAC -> PAM8403 Class-D Amplifier"
            " -> 28mm 8ohm Speaker", 30, 33,
        )

        # PAM8403 module
        ax, ay = 120, 110
        self.sym("PAM8403_Module", "U5", "PAM8403", ax, ay, range(1, 6))

        # Power: +5V
        self.glabel("+5V", ax - 30, ay - 3.81, 0, "input")
        self.wire(ax - 30, ay - 3.81, ax - 10.16, ay - 3.81)

        # GND
        self.gnd(ax - 30, ay + 8)
        self.wire(ax - 10.16, ay, ax - 30, ay)
        self.wire(ax - 30, ay, ax - 30, ay + 8)

        # Audio input from I2S (DOUT)
        self.glabel("I2S_DOUT", ax - 30, ay + 3.81, 0, "input")
        self.wire(ax - 30, ay + 3.81, ax - 10.16, ay + 3.81)

        # I2S bus reference (informational labels)
        self.text("I2S Bus (directly from ESP32-S3):", 30, 55, 2.54, True)
        self.glabel("I2S_BCLK", 30, 68, 0, "input")
        self.text("GPIO15 - Bit Clock (1.411 MHz @ 44.1kHz)", 65, 68)
        self.glabel("I2S_LRCK", 30, 78, 0, "input")
        self.text("GPIO16 - L/R Word Select (44.1kHz)", 65, 78)
        self.glabel("I2S_DOUT", 30, 88, 0, "output")
        self.text("GPIO17 - Serial Data Out -> PAM8403", 65, 88)

        # Speaker (moved further right for orthogonal routing)
        spk_x, spk_y = ax + 65, ay
        self.sym("Speaker", "LS1", "28mm 8ohm", spk_x, spk_y, ["1", "2"])
        self.text("28mm speaker", spk_x + 8, spk_y - 5)
        self.text("8 ohm / 0.5W", spk_x + 8, spk_y + 1)

        # SPK+ wire (orthogonal L-shape)
        spk_plus_y = ay - 3.81
        self.wire(ax + 10.16, spk_plus_y, spk_x - 3.81, spk_plus_y)
        self.wire(spk_x - 3.81, spk_plus_y, spk_x - 3.81, spk_y - 0.635)
        # SPK- wire (orthogonal L-shape)
        spk_minus_y = ay
        self.wire(ax + 10.16, spk_minus_y, spk_x - 10, spk_minus_y)
        self.wire(spk_x - 10, spk_minus_y, spk_x - 10, spk_y + 0.635)
        self.wire(spk_x - 10, spk_y + 0.635, spk_x - 3.81, spk_y + 0.635)

        # Notes
        ny = 165
        self.text("Design Notes:", 30, ny, 2.54, True)
        self.text(
            "- PAM8403: filterless Class-D stereo amplifier"
            " (3W per channel max)", 30, ny + 8,
        )
        self.text(
            "- Only one channel used for mono audio", 30, ny + 14,
        )
        self.text(
            "- No external DAC needed: ESP32-S3 has"
            " built-in I2S with DMA", 30, ny + 20,
        )
        self.text(
            "- Powered from +5V rail for max headroom"
            " (3.3V limits volume)", 30, ny + 26,
        )
        self.text(
            "- DMA-driven audio streaming for"
            " low CPU overhead", 30, ny + 32,
        )
