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
        panel_pin 33 (LED_A)       ↔  J4 pad  8 (LED_BLA)
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
  33:    LED-A → +5V via R27 20R (LED_BLA — backlight always on, ~90mA)
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
    # A3 (420x297 landscape): the FPC connector block sits at x=260,
    # which is off the right-hand edge of an A4 sheet (210 mm wide) —
    # J4 was being drawn outside the page border and did not appear in
    # the exported SVG/PDF at all.
    paper = "A3"
    needed_symbols = ["ST7796S_Module", "FPC_16P", "R"]

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
        # FPC pin numbers in parentheses (per ILI9488 datasheet).
        # Annotation text is placed further LEFT (dx - 72 instead of
        # dx - 50) so the long tied-net notes do not overlap the
        # LCD_RD / LCD_BL global labels at dx - 35.
        ctrl_pins = [
            ("LCD_CS", -10.16, "GPIO12 / FPC9"),
            ("LCD_RST", -7.62, "GPIO13 / FPC15"),
            ("LCD_DC", -5.08, "GPIO14 / FPC10"),
            ("LCD_WR", -2.54, "GPIO46 / FPC11"),
            # RD is tied to the 3.3 V rail on the board, so the label has
            # to say "+3V3" — naming it LCD_RD drew a net that exists on
            # no copper, and a schematic net with no PCB counterpart is
            # exactly what verify_netlist_diff T1 is for. LED-A carries
            # the real LED_BLA net (R25-HIGH-1 fix: +5V through R27 20R,
            # drawn below the control column). Which panel pin each one
            # is stays in the annotation text on the right.
            # Keep these annotations as short as the ones above: the text
            # column and the global labels share a narrow gap, and a longer
            # string overlaps the label (verify_schematic_overlaps catches it).
            ("+3V3", 0, "+3V3 (FPC12, RO)"),
            ("LED_BLA", 5.08, "BL via R27 (FPC33)"),
        ]
        self.text("Control signals:", dx - 72, dy - 14, 2, True)
        for net, yoff, gpio in ctrl_pins:
            px = dx - 10.16
            py = dy + yoff
            self.wire(px, py, px - 25, py)
            self.glabel(net, px - 25, py, 180)
            self.text(gpio, px - 62, py, 1.5)

        # --- R27: backlight series resistor (R25-HIGH-1 fix) ---
        # +5V -> R27 (20R 1206) -> LED_BLA -> J4 pad 8 (panel 33, LED-A).
        # Pin roles match the PCB pad map: pad 1 = LED_BLA (north stub to
        # the J4-side vias), pad 2 = +5V (south leg to the In2 island tap).
        # angle=180 puts pin 2 on top (+5V rail above) and pin 1 on the
        # bottom (LED_BLA label below).
        r27_x = dx - 55
        r27_y = dy + 18
        self.sym("R", "R27", "20", r27_x, r27_y, ["1", "2"], angle=180)
        self.v5(r27_x, r27_y - 8)
        self.wire(r27_x, r27_y - 8, r27_x, r27_y - 3.81)
        self.link("LED_BLA", r27_x, r27_y + 3.81, 270, glob=True)
        # Notes BELOW the LED_BLA label's text extent (r27_y + 18/+21):
        # at r27_y + 12 the first line ran into the label whichever side
        # of the column it started on (verify_schematic_overlaps).
        self.text("Backlight: (5.0-3.2V)/20R = 90mA", r27_x - 30, r27_y + 18, 1.5)
        self.text("(family class 6-LED/90mA)", r27_x - 30, r27_y + 21, 1.5)

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
        self.text("(40P on PCB, 16 active signals shown)", fpc_x - 45, fpc_y - 23, 1.5)
        self.sym("FPC_16P", "J4", "FPC-16P-0.5mm", fpc_x, fpc_y, range(1, 17))

        # Wire display module outputs to FPC pins
        # Schematic uses simplified 16-pin symbol; physical FPC-40P footprint
        # maps these to correct pins per ILI9488 datasheet
        # fpc_nets[i] is the net on FPC_16P symbol pin (i+1). The order
        # here is the one encoded in J4_SYM_PIN_TO_PAD in
        # scripts/verify_netlist_diff.py — changing it without updating
        # that table will make the netlist cross-check fail.
        #
        # Pin 7 carries "+3V3", not "LCD_RD": on the board the panel's RD
        # pin (panel 12 -> pad 29) is hard-tied to the 3.3 V rail because
        # the interface is write-only. Pin 8 (LED-A, panel 33 -> pad 8)
        # carries LED_BLA — the backlight anode node after R27, fed from
        # +5V (R25-HIGH-1 fix, 2026-07-31). The always-on choice is
        # unchanged; the current is now defined by R27.
        fpc_nets = [
            "+3V3", "GND", "LCD_CS", "LCD_RST", "LCD_DC", "LCD_WR",
            "+3V3", "LED_BLA",
            "LCD_D0", "LCD_D1", "LCD_D2", "LCD_D3",
            "LCD_D4", "LCD_D5", "LCD_D6", "LCD_D7",
        ]
        # FPC_16P pin n sits at world y = fpc_y - 17.78 + (n-1)*2.54.
        # BUG FIX: this loop used to compute py = fpc_y + 17.78 - i*2.54,
        # which walks the pins backwards (net[0] landed on pin 15) and
        # ran one step off the end of the symbol, so LCD_D7 attached to
        # nothing at all — the schematic showed a 7-bit data bus.
        for i, net in enumerate(fpc_nets):
            py = fpc_y - 17.78 + i * 2.54
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
