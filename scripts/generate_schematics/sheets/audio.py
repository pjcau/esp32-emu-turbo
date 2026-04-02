"""Sheet 4: Audio - I2S DAC -> PAM8403 -> Speaker."""

from ..sheet_base import SchematicSheet


class AudioSheet(SchematicSheet):
    title = "Audio - I2S -> PAM8403 -> Speaker"
    page_number = 4
    needed_symbols = ["PAM8403_Module", "Speaker", "C", "R"]

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
        self.sym("Speaker", "SPK1", "28mm 8ohm", spk_x, spk_y, ["1", "2"])
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

        # --- PAM8403 passive components (per datasheet application circuit) ---
        self.text("PAM8403 Passives:", 30, 135, 2.54, True)

        # VREF bypass capacitor (C21, 100nF) — pin VREF to GND
        c21x, c21y = ax + 30, ay + 25
        self.sym("C", "C21", "100nF", c21x, c21y, ["1", "2"])
        self.wire(c21x, c21y - 3.81, c21x, c21y - 10)
        self.wire(c21x, c21y - 10, ax + 10.16, c21y - 10)
        self.gnd(c21x, c21y + 8)
        self.wire(c21x, c21y + 3.81, c21x, c21y + 8)
        self.text("VREF bypass", c21x + 3, c21y)

        # DC-blocking capacitor (C22, 0.47uF) — input coupling
        c22x, c22y = ax - 45, ay + 3.81
        self.sym("C", "C22", "0.47uF", c22x, c22y, ["1", "2"])
        self.wire(c22x + 3.81, c22y, c22x + 15, c22y)
        self.wire(c22x - 3.81, c22y, c22x - 8, c22y)
        self.glabel("I2S_DOUT", c22x - 8, c22y, 0, "input")
        self.text("DC-block", c22x - 3, c22y - 5)

        # INL bias resistor (R20, 20k) — input bias to VREF
        r20x, r20y = ax - 35, ay + 18
        self.sym("R", "R20", "20k", r20x, r20y, ["1", "2"])
        self.wire(r20x, r20y - 3.81, r20x, c22y)
        self.gnd(r20x, r20y + 8)
        self.wire(r20x, r20y + 3.81, r20x, r20y + 8)
        self.text("INL bias", r20x + 3, r20y)

        # INR bias resistor (R21, 20k) — input bias to VREF
        r21x, r21y = ax - 25, ay + 18
        self.sym("R", "R21", "20k", r21x, r21y, ["1", "2"])
        self.wire(r21x, r21y - 3.81, r21x, c22y)
        self.gnd(r21x, r21y + 8)
        self.wire(r21x, r21y + 3.81, r21x, r21y + 8)
        self.text("INR bias", r21x + 3, r21y)

        # VDD decoupling (C23, 1uF) — VDD pin to GND
        c23x, c23y = ax - 20, ay - 20
        self.sym("C", "C23", "1uF", c23x, c23y, ["1", "2"])
        self.glabel("+5V", c23x, c23y - 8, 0, "input")
        self.wire(c23x, c23y - 3.81, c23x, c23y - 8)
        self.gnd(c23x, c23y + 8)
        self.wire(c23x, c23y + 3.81, c23x, c23y + 8)
        self.text("VDD decoupl.", c23x + 3, c23y)

        # PVDD top bypass (C24, 1uF) — power output stage
        c24x, c24y = ax, ay - 20
        self.sym("C", "C24", "1uF", c24x, c24y, ["1", "2"])
        self.glabel("+5V", c24x, c24y - 8, 0, "input")
        self.wire(c24x, c24y - 3.81, c24x, c24y - 8)
        self.gnd(c24x, c24y + 8)
        self.wire(c24x, c24y + 3.81, c24x, c24y + 8)
        self.text("PVDD top", c24x + 3, c24y)

        # PVDD bottom bypass (C25, 1uF) — power output stage
        c25x, c25y = ax + 20, ay - 20
        self.sym("C", "C25", "1uF", c25x, c25y, ["1", "2"])
        self.glabel("+5V", c25x, c25y - 8, 0, "input")
        self.wire(c25x, c25y - 3.81, c25x, c25y - 8)
        self.gnd(c25x, c25y + 8)
        self.wire(c25x, c25y + 3.81, c25x, c25y + 8)
        self.text("PVDD bottom", c25x + 3, c25y)

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
