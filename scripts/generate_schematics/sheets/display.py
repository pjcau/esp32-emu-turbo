"""Sheet 3: Display — ILI9488 3.95" 320×480 8-bit 8080 parallel interface.

Source of truth: ``website/docs/design/components.md`` (section
"FPC 40-Pin Pinout") — verified against the actual ILI9488 4.0" bare
panel datasheet shipped by the AliExpress seller
(https://it.aliexpress.com/item/1005009422879126.html). The panel has
touch pins on 1-4 but **we do not use them as touch** — they remain NC.

⚠  CRITICAL — FPC pin reversal on the PCB
    The panel sits above the PCB in landscape orientation and the FPC
    ribbon passes straight through a slot to J4 on the back side. The
    ribbon does NOT twist, so:

        connector_pad = 41 - panel_pin

    i.e. panel pin 17 (DB0) contacts connector pad 24.

    Because of this, ``hardware/datasheet_specs.py`` (the PCB net
    source of truth) lists the SAME ELECTRICAL DESIGN with the pad
    numbers reversed:

        panel_pin 6  (VDDI/+3V3)   ↔  J4 pad 35 (+3V3)
        panel_pin 9  (CS)          ↔  J4 pad 32 (LCD_CS)
        panel_pin 11 (WR)          ↔  J4 pad 30 (LCD_WR)
        panel_pin 17 (DB0)         ↔  J4 pad 24 (LCD_D0)
        panel_pin 33 (LED_A)       ↔  J4 pad  8 (LCD_BL)
        panel_pin 38 (IM0)         ↔  J4 pad  3 (+3V3)
        panel_pin 40 (IM2)         ↔  J4 pad  1 (GND)

    This was flagged as R4-CRIT-1 in an earlier audit round and later
    closed as a FALSE POSITIVE once the 41-N reversal was understood.
    ``scripts/verify_schematic_pcb_sync.py`` checks the NET SET on J4,
    not the per-pin mapping, so both conventions round-trip correctly.

    NEVER "fix" the apparent disagreement between this file and
    ``datasheet_specs.py`` by rewriting one of them — they are two
    views of the same electrical design.

Panel-side FPC 40-pin pinout (verified against components.md):

  1-4:   Touch (XL/YU/XR/YD) — NC (panel supports touch, we don't use it)
  5:     GND
  6:     VDDI (I/O power, 3.3V)
  7:     VDDA (analog power, 3.3V)
  8:     TE — NC (tearing-effect, not used)
  9:     CS  → GPIO12 (LCD_CS)
  10:    DC/RS → GPIO14 (LCD_DC)
  11:    WR → GPIO46 (LCD_WR)
  12:    RD → tied +3V3 (LCD_RD — write-only mode)
  13-14: SPI SDI/SDO — NC (parallel mode only)
  15:    RESET → GPIO13 (LCD_RST)
  16:    GND
  17-24: DB0-DB7 → GPIO4-11 (LCD_D0..LCD_D7)
  25-32: DB8-DB15 — NC (8-bit mode only)
  33:    LED-A → +3V3 (LCD_BL — backlight always on)
  34-36: LED-K → GND (backlight cathode, 8-LED string)
  37:    GND
  38:    IM0 → +3V3 (mode select HIGH)
  39:    IM1 → +3V3 (mode select HIGH)
  40:    IM2 → GND  (mode select LOW)

Interface mode: IM2=0 IM1=1 IM0=1 → 8080 8-bit parallel (mandatory
for SNES emulation bandwidth; see website/docs/design/components.md).
"""

from ..sheet_base import SchematicSheet


class DisplaySheet(SchematicSheet):
    title = "Display - ILI9488 4.0in 8080 Parallel"
    page_number = 3
    needed_symbols = ["ST7796S_Module", "FPC_16P"]

    def build(self):
        # Title
        self.text("DISPLAY - ILI9488 4.0in 320x480", 30, 25, 5, True)
        self.text(
            "8-bit 8080 parallel interface"
            " (mandatory for SNES emulation speed)", 30, 33,
        )

        # Display module centered. Ref is "DS1" (Display symbol) rather
        # than "U4" — "U4" is reserved for the physical USBLC6-2SC6 TVS
        # on the back of the PCB (see power_supply.py / routing.py). The
        # display panel is off-board via the FPC ribbon, so DS1 is a
        # schematic-only visual aid that carries no BOM line of its own;
        # the physical connector is J4.
        dx, dy = 148, 120
        self.sym(
            "ST7796S_Module", "DS1", "ILI9488 4.0in 8080",
            dx, dy, range(1, 17),
        )

        # --- Power connections ---
        self.glabel("+3V3", dx - 30, dy - 15.24, 0, "input")
        self.wire(dx - 30, dy - 15.24, dx - 10.16, dy - 15.24)

        self.gnd(dx - 30, dy - 12.7)
        self.wire(dx - 30, dy - 12.7, dx - 10.16, dy - 12.7)

        # --- Control signals (left side) ---
        # FPC pin numbers in parentheses (per ILI9488 datasheet)
        ctrl_pins = [
            ("LCD_CS", -10.16, "GPIO12 (FPC9)"),
            ("LCD_RST", -7.62, "GPIO13 (FPC15)"),
            ("LCD_DC", -5.08, "GPIO14 (FPC10)"),
            ("LCD_WR", -2.54, "GPIO46 (FPC11)"),
            ("LCD_RD", 0, "+3V3 tied (FPC12, write-only)"),
            ("LCD_BL", 5.08, "+3V3 tied (FPC33, always-on)"),
        ]
        self.text("Control signals:", dx - 60, dy - 14, 2, True)
        for net, yoff, gpio in ctrl_pins:
            px = dx - 10.16
            py = dy + yoff
            self.wire(px, py, px - 25, py)
            self.glabel(net, px - 25, py, 180)
            self.text(gpio, px - 50, py, 1.5)

        # --- Data bus (right side) ---
        data_pins = [
            ("LCD_D0", -15.24, "GPIO4 (FPC17)"),
            ("LCD_D1", -12.7, "GPIO5 (FPC18)"),
            ("LCD_D2", -10.16, "GPIO6 (FPC19)"),
            ("LCD_D3", -7.62, "GPIO7 (FPC20)"),
            ("LCD_D4", -5.08, "GPIO8 (FPC21)"),
            ("LCD_D5", -2.54, "GPIO9 (FPC22)"),
            ("LCD_D6", 0, "GPIO10 (FPC23)"),
            ("LCD_D7", 2.54, "GPIO11 (FPC24)"),
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
        self.text("FPC RIBBON CONNECTOR (J4)", fpc_x - 15, fpc_y - 25, 2, True)
        self.text("(40P on PCB, 16 active signals shown)", fpc_x - 15, fpc_y - 20, 1.5)
        self.sym("FPC_16P", "J4", "FPC-16P-0.5mm", fpc_x, fpc_y, range(1, 17))

        # Wire display module outputs to FPC pins
        # Schematic uses simplified 16-pin symbol; physical FPC-40P footprint
        # maps these to correct pins per ILI9488 datasheet
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

        # --- FPC pinout reference (panel-side, per website/docs) ---
        ny = 180
        self.text("ILI9488 Panel FPC-40P Pin Mapping "
                  "(source: components.md):",
                  30, ny, 2.54, True)
        self.text(
            "Panel 6,7=VDDI/VDDA(+3V3)  9=CS  10=DC"
            "  11=WR  12=RD  15=RESET", 30, ny + 8,
        )
        self.text(
            "Panel 17-24=DB0-DB7  33=LED-A(BL)"
            "  34-36=LED-K(GND)  38,39=IM0,IM1(+3V3)"
            "  40=IM2(GND)", 30, ny + 14,
        )
        self.text(
            "Interface mode: IM2=0 IM1=1 IM0=1"
            " = 8080 8-bit parallel", 30, ny + 20,
        )
        self.text(
            "- GPIO4-11 form contiguous 8-bit bus for"
            " efficient register-level DMA", 30, ny + 28,
        )
        self.text(
            "- WR strobes data on rising edge,"
            " RD tied HIGH (+3V3, write-only mode)", 30, ny + 34,
        )
        self.text(
            "⚠ FPC PIN REVERSAL on PCB: panel pin N ↔ J4 pad (41-N).",
            30, ny + 42,
        )
        self.text(
            "  e.g. panel pin 17 (DB0) contacts J4 pad 24. See "
            "datasheet_specs.py for the connector-side mapping.",
            30, ny + 48,
        )
