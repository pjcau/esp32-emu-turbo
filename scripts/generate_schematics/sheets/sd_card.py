"""Sheet 5: SD Card - SPI interface for ROM storage."""

from ..sheet_base import SchematicSheet


class SDCardSheet(SchematicSheet):
    title = "Storage - SD Card SPI"
    page_number = 5
    needed_symbols = ["SD_Module"]

    def build(self):
        # Title
        self.text("STORAGE - Micro SD Card", 30, 25, 5, True)
        self.text(
            "SPI interface for ROM storage"
            " (SNES ROMs up to 6MB)", 30, 33,
        )

        # SD Card module centered
        sx, sy = 148, 110
        self.sym("SD_Module", "U6", "SD_Card_SPI", sx, sy, range(1, 7))

        # Power: +3V3
        self.glabel("+3V3", sx - 30, sy - 3.81, 0, "input")
        self.wire(sx - 30, sy - 3.81, sx - 10.16, sy - 3.81)

        # GND
        self.gnd(sx - 30, sy + 8)
        self.wire(sx - 10.16, sy, sx - 30, sy)
        self.wire(sx - 30, sy, sx - 30, sy + 8)

        # SPI signals (right side) with GPIO annotations
        self.text("SPI bus:", sx + 18, sy - 10, 2, True)
        spi_pins = [
            ("SD_MOSI", -3.81, "GPIO36"),
            ("SD_MISO", 0, "GPIO37"),
            ("SD_CLK", 3.81, "GPIO38"),
        ]
        for net, yoff, gpio_note in spi_pins:
            px = sx + 10.16
            py = sy + yoff
            self.wire(px, py, px + 25, py)
            self.glabel(net, px + 25, py, 0)
            self.text(gpio_note, px + 40, py, 1.5)

        # CS on left side
        self.text("Chip Select:", sx - 58, sy + 1, 2, True)
        self.glabel("SD_CS", sx - 30, sy + 3.81, 0, "input")
        self.wire(sx - 30, sy + 3.81, sx - 10.16, sy + 3.81)
        self.text("GPIO39", sx - 58, sy + 5, 1.5)

        # Notes
        ny = 160
        self.text("Design Notes:", 30, ny, 2.54, True)
        self.text(
            "- SPI bus @ up to 40MHz (ESP32-S3 max for SD)", 30, ny + 8,
        )
        self.text(
            "- SNES ROMs: 256KB to 6MB typical"
            " (HiROM/LoROM)", 30, ny + 14,
        )
        self.text(
            "- FAT32 filesystem for easy ROM management"
            " via PC", 30, ny + 20,
        )
        self.text(
            "- 3.3V logic: no level shifter needed"
            " (module has built-in)", 30, ny + 26,
        )
        self.text(
            "- GPIO36-39 grouped for clean SPI trace"
            " routing on PCB", 30, ny + 32,
        )
