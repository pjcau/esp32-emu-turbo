"""Sheet 2: MCU - ESP32-S3-WROOM-1 N16R8 with decoupling and GPIO labels."""

from ..sheet_base import SchematicSheet
from ..config import GPIO_NETS, ESP_PINS


# GPIOs whose *net* at the module pin is not the same as the functional
# net name recorded in config.GPIO_NETS.
#
# GPIO19/GPIO20 are the native USB D-/D+ pins. Between the USB-C
# connector and these pins the design has U4 (USBLC6-2SC6 TVS) and the
# 22 ohm series resistors R22/R23, so the MCU pin sits on the
# POST-resistor node, not on the bus net:
#
#     J1 -- USB_D+ -- U4(3,4) -- R22 -- USB_DP_MCU -- U1.14 (GPIO20)
#     J1 -- USB_D- -- U4(1,6) -- R23 -- USB_DM_MCU -- U1.13 (GPIO19)
#
# hardware/datasheet_specs.py records exactly these nets for U1 pins
# 13/14, and routing.py assigns them on the board. config.GPIO_NETS is
# left alone because it is the GPIO -> *function* map shared with the
# firmware header (software/main/board_config.h).
_MCU_SIDE_NETS = {
    19: "USB_DM_MCU",
    20: "USB_DP_MCU",
}


class MCUSheet(SchematicSheet):
    title = "MCU - ESP32-S3-WROOM-1 N16R8"
    page_number = 2
    paper = "A3"
    needed_symbols = ["ESP32-S3-WROOM-1", "C", "R", "SW_Push"]

    def build(self):
        # Title
        self.text("MCU - ESP32-S3-WROOM-1 N16R8", 30, 25, 5, True)
        self.text("Dual-core LX7 @ 240MHz, 16MB Flash, 8MB PSRAM", 30, 33)

        # ESP32 centered on A3 landscape
        MCU_X, MCU_Y = 200, 170
        self.sym("ESP32-S3-WROOM-1", "U1", "ESP32-S3-N16R8", MCU_X, MCU_Y, range(1, 42))

        px_l = MCU_X - 15.24  # left pin edge
        px_r = MCU_X + 15.24  # right pin edge

        # --- 3V3 power to MCU pins 1,2 ---
        pwr_y = MCU_Y - 38.1  # pin 1 level
        self.glabel("+3V3", px_l - 20, pwr_y, 0, "input")
        self.wire(px_l - 20, pwr_y, px_l, pwr_y)
        # Pin 2 (3V3) tie to same rail
        pwr2_y = MCU_Y - 35.56
        self.wire(px_l, pwr2_y, px_l - 15, pwr2_y)
        self.wire(px_l - 15, pwr2_y, px_l - 15, pwr_y)

        # --- EN: bare on v1, no RC. See docs/known-issues.md, V2 section ---
        # This block used to claim the WROOM-1 "integrates a 10k EN pull-up
        # on-module (per Espressif reference design), so an external
        # pull-up is redundant". That is false, and it is the reason R3 was
        # dropped and C3 re-used elsewhere. The module datasheet says the
        # opposite, in its own words, on page 28 under the peripheral
        # reference schematic:
        #
        #   "To ensure the ESP32-S3 chip's supply is correct at power-up,
        #    an RC delay circuit MUST be added at the EN pin. R = 10 kOhm
        #    and C = 1 uF are the usual recommendation, but the values
        #    should be adjusted to the module's power-up timing and the
        #    chip's power-on reset timing."
        #
        # and its figure 7 draws exactly that: R7 from VDD33 to EN, C8
        # 0.1 uF from EN to GND, SW1 across the cap.
        #
        # On the v1 board EN has NEITHER. R3 is DNP and C3 is wired as a
        # second decoupling cap (see below), so EN reaches only U1.3 and
        # SW_RST pad 1. hardware-audit-bugs.md asserts "EN RC delay
        # (R3+C3) intact" in two places; nobody had compared that sentence
        # to the copper.
        #
        # v1 is not being re-fabricated, so this is recorded as an
        # as-built limitation rather than patched into a board that is
        # already assembled — dragging a cap 28 mm across the layout to
        # reach EN would trade a missing RC for a long high-impedance
        # antenna on the reset line, which is worse. v2 must place the RC
        # adjacent to the module's EN pin.
        en_y = MCU_Y - 33.02  # EN pin level
        r_en_x = px_l - 25
        r_en_y = MCU_Y - 45  # (legacy position kept for layout spacing)
        # No +3V3 tie: a hard wire from EN to the rail made EN and +3V3 the
        # same schematic net, so SW_RST — which bridges EN to GND — was
        # drawn shorting 3V3 straight to ground on every press. The PCB
        # always had EN as its own copper; only the drawing was wrong.
        # c_en_x stays the anchor the reset/boot columns are placed from.
        c_en_x = px_l - 35
        c_en_y = en_y + 10
        self.wire(px_l, en_y, r_en_x, en_y)
        # Name the net explicitly. A global label keeps it flat "EN" to
        # match the PCB net name — a local label would export as
        # "/MCU/EN" and re-fail the same gate for a different reason.
        self.glabel("EN", r_en_x, en_y, 180)
        # Kept short and lifted clear of the decoupling row below: the
        # full reasoning lives in the comment above and in
        # docs/known-issues.md, not on the plot.
        self.text("EN bare on v1 — R3 DNP, no RC",
                  r_en_x - 22, r_en_y - 12, 1.5)
        self.text("v2: 10k + 100nF at pin 3",
                  r_en_x - 22, r_en_y - 8, 1.5)

        # --- RESET button (EN to GND, active-low) ---
        # Own column, LEFT of C3. Sharing C3's column is what broke this:
        # the upper stub ran to c_en_y + 3.81, which is C3's BOTTOM pin
        # (GND), so the schematic drew the reset button bridging GND to
        # GND and never touching EN. The PCB always had it right
        # (SW_RST pad 1 = EN, pads 3/4 = GND).
        sw_rst_x = c_en_x - 12
        sw_rst_y = c_en_y + 18
        # SW_Push pins are HORIZONTAL at x +/- 5.08 (lib_symbols.py:133).
        # The stubs below were written for the R/C pattern — vertical at
        # y +/- 3.81 — so they landed ~5mm off both pins and the switch
        # was drawn connected to nothing at all. angle=270 puts pin 1
        # (PCB pad 1 = net EN) at the TOP, facing the EN line.
        self.sym("SW_Push", "SW_RST", "RESET", sw_rst_x, sw_rst_y,
                 ["1", "2"], angle=270)
        # Upper terminal -> the EN horizontal. The rail used to stop at
        # c_en_x because C3 tapped it there; with C3 moved to the
        # decoupling row, the rail runs on to this column and the switch
        # meets it at its endpoint rather than as a T.
        self.wire(sw_rst_x, sw_rst_y - 5.08, sw_rst_x, en_y)
        self.wire(r_en_x, en_y, sw_rst_x, en_y)
        self.gnd(sw_rst_x, sw_rst_y + 8)
        self.wire(sw_rst_x, sw_rst_y + 5.08, sw_rst_x, sw_rst_y + 8)
        self.text("Reset (EN->GND)", sw_rst_x - 25, sw_rst_y, 1.5)

        # --- BOOT button (GPIO0 to GND, enter download mode) ---
        # Pushed further down (c_en_y + 55) so its BTN_SELECT glabel
        # clears the DISPLAY / AUDIO / CONTROLS annotation column
        # headers, which live at y ~ MCU_Y - 35 .. MCU_Y + 12.
        sw_boot_x = c_en_x - 30
        sw_boot_y = c_en_y + 55
        # Same fix as SW_RST, and the SAME angle — 270, not 90.
        #
        # A tact switch has two POLES, not four terminals: pads 1+2 are one
        # pole, pads 3+4 the other, and pressing shorts pole to pole. The
        # symbol has one pin per pole (_TACT_MAP: pin 1 -> pads 1,2 and
        # pin 2 -> pads 3,4). routing.py drives BTN_SELECT onto pad 2 and
        # GND onto pads 3 and 4, so the signal pole is pads 1/2 = symbol
        # pin 1 — exactly as on SW_RST.
        #
        # angle=90 was chosen by reading "pad 2 = BTN_SELECT" and reaching
        # for pin 2, which confuses the pad number with the pin number. It
        # put GND on the signal pole and BTN_SELECT on the ground pole:
        # harmless on the bench, because the part is symmetric and the
        # button still shorts GPIO0 to ground, but it is the schematic
        # disagreeing with the board, and T4 says so.
        self.sym("SW_Push", "SW_BOOT", "BOOT", sw_boot_x, sw_boot_y,
                 ["1", "2"], angle=270)
        self.glabel("BTN_SELECT", sw_boot_x, sw_boot_y - 8, 0, "bidirectional")
        self.wire(sw_boot_x, sw_boot_y - 5.08, sw_boot_x, sw_boot_y - 8)
        self.gnd(sw_boot_x, sw_boot_y + 8)
        self.wire(sw_boot_x, sw_boot_y + 5.08, sw_boot_x, sw_boot_y + 8)
        # Help text stacked BELOW the switch so it stays in its own
        # vertical lane and doesn't collide with the CONTROLS group
        # header (which lives at y = MCU_Y + 8 = 178).
        self.text("BOOT (GPIO0->GND)", sw_boot_x - 15, sw_boot_y + 13, 1.5)
        self.text("Hold BOOT + tap RESET", sw_boot_x - 15, sw_boot_y + 17, 1.5)
        self.text("to enter download mode", sw_boot_x - 15, sw_boot_y + 21, 1.5)

        # --- Decoupling cap (100nF near 3V3) ---
        c_dec_x = px_l - 15
        c_dec_y = MCU_Y - 45  # above 3V3 pins
        self.sym("C", "C4", "100nF", c_dec_x, c_dec_y, ["1", "2"], angle=180)
        # Stop on the pin-1 +3V3 line and tap it, instead of running past
        # it down to pwr2_y: the old wire crossed that line at (169.76,
        # 131.90) and then lay on top of the pwr2->pwr riser for its last
        # 2.54 mm. Same net throughout, but it drew as a crossing plus a
        # duplicated segment. Guarded by verify_schematic_crossings.py.
        self.wire(c_dec_x, c_dec_y + 3.81, c_dec_x, pwr_y)
        self.junction(c_dec_x, pwr_y)
        self.gnd(c_dec_x, c_dec_y - 10)
        self.wire(c_dec_x, c_dec_y - 3.81, c_dec_x, c_dec_y - 10)
        self.text("Decoupling", c_dec_x - 15, c_dec_y, 1.5)

        # --- C3: second ESP32 decoupling cap (100nF) ---
        # C3 is drawn here, not on EN, because that is what the board has:
        # routing.py places it at (69.55, 42.0) as "ESP32 decoupling 1",
        # twin of C4 at (92.0, 42.0), with pad 1 on +3V3 and pad 2 on GND.
        # It used to be drawn as the EN reset cap, which is the half of the
        # missing RC network the EN block above documents — the schematic
        # was describing a circuit the copper does not have, and T4 caught
        # it as C3.1 sch='EN' pcb='+3V3'.
        # Placed to the RIGHT of C26, continuing the row outward. The
        # symmetric-looking spot at c_dec_x - 15 is already occupied: that
        # is where C4's own "Decoupling" caption sits, so a symbol there
        # lands underneath it.
        # c_dec_x + 30, not c26_x + 15: this block runs BEFORE C26 is
        # defined, so naming c26_x here would be a NameError.
        c3_x = c_dec_x + 34
        c3_y = c_dec_y
        self.sym("C", "C3", "100nF", c3_x, c3_y, ["1", "2"], angle=180)
        self.wire(c3_x, c3_y + 3.81, c3_x, pwr_y)
        self.gnd(c3_x, c3_y - 10)
        self.wire(c3_x, c3_y - 3.81, c3_x, c3_y - 10)
        self.text("Decoupling 2", c3_x + 4, c3_y, 1.5)

        # --- C26: Additional VDD bypass (100nF, close to pin 2) ---
        c26_x = c_dec_x + 15
        c26_y = c_dec_y
        self.sym("C", "C26", "100nF", c26_x, c26_y, ["1", "2"], angle=180)
        self.wire(c26_x, c26_y + 3.81, c26_x, pwr2_y)
        self.gnd(c26_x, c26_y - 10)
        self.wire(c26_x, c26_y - 3.81, c26_x, c26_y - 10)
        self.text("VDD bypass", c26_x + 4, c26_y, 1.5)

        # --- GND pins (40, 41) at bottom ---
        self.wire(MCU_X, MCU_Y + 41.91, MCU_X, MCU_Y + 48)
        self.gnd(MCU_X, MCU_Y + 48)
        self.wire(MCU_X + 2.54, MCU_Y + 41.91, MCU_X + 2.54, MCU_Y + 48)
        self.gnd(MCU_X + 2.54, MCU_Y + 48)

        # ═══════════════════════════════════════════════════
        # GPIO LABELS WITH FUNCTIONAL GROUPING
        # ═══════════════════════════════════════════════════

        # Left-side group annotations
        self.text("DISPLAY", px_l - 62, MCU_Y - 35, 2, True)
        self.text("(8080 bus)", px_l - 62, MCU_Y - 31, 1.5)

        self.text("AUDIO", px_l - 62, MCU_Y - 16, 2, True)
        self.text("(I2S)", px_l - 62, MCU_Y - 12, 1.5)

        self.text("CONTROLS", px_l - 62, MCU_Y + 8, 2, True)
        self.text("(buttons)", px_l - 62, MCU_Y + 12, 1.5)

        # Right-side group annotations
        self.text("DISPLAY", px_r + 28, MCU_Y - 42, 2, True)
        self.text("(ctrl)", px_r + 28, MCU_Y - 38, 1.5)

        self.text("CONTROLS", px_r + 28, MCU_Y - 30, 2, True)
        self.text("(face+sys)", px_r + 28, MCU_Y - 26, 1.5)

        self.text("SD CARD", px_r + 28, MCU_Y - 18, 2, True)
        self.text("(SPI)", px_r + 28, MCU_Y - 14, 1.5)

        self.text("USB", px_r + 28, MCU_Y + 2, 2, True)
        self.text("(native)", px_r + 28, MCU_Y + 6, 1.5)

        # Generate GPIO labels with 15mm wire stubs
        for _pn, (side, gpio, yoff) in ESP_PINS.items():
            if side == "B" or gpio in ("3V3", "EN", "GND"):
                continue

            if isinstance(gpio, int):
                net = _MCU_SIDE_NETS.get(gpio) or GPIO_NETS.get(gpio, f"GPIO{gpio}")
            else:
                net = gpio

            if side == "L":
                pin_x, pin_y = px_l, MCU_Y - yoff
                lx = pin_x - 15
                self.wire(pin_x, pin_y, lx, pin_y)
                self.glabel(net, lx, pin_y, 180)
            else:  # R
                pin_x, pin_y = px_r, MCU_Y - yoff
                lx = pin_x + 15
                self.wire(pin_x, pin_y, lx, pin_y)
                self.glabel(net, lx, pin_y, 0)

        # ═══════════════════════════════════════════════════
        # GPIO ASSIGNMENT TABLE (right side)
        # ═══════════════════════════════════════════════════
        ty = 30
        tx = 320
        self.text("GPIO ASSIGNMENT TABLE", tx, ty, 3, True)
        ty += 10
        self.text("Display (8080 parallel):", tx, ty, 2, True)
        ty += 5
        self.text("GPIO4-11 = D0-D7 (8-bit data bus)", tx, ty)
        ty += 5
        self.text("GPIO12=CS  GPIO13=RST  GPIO14=DC", tx, ty)
        ty += 5
        self.text("GPIO46=WR  (RD/BL tied +3V3 on FPC)", tx, ty)
        ty += 8
        self.text("Audio (I2S):", tx, ty, 2, True)
        ty += 5
        self.text("GPIO15=BCLK  GPIO16=LRCK  GPIO17=DOUT", tx, ty)
        ty += 8
        self.text("SD Card (SPI):", tx, ty, 2, True)
        ty += 5
        self.text("GPIO44=MOSI  GPIO43=MISO  GPIO38=CLK  GPIO39=CS", tx, ty)
        ty += 8
        self.text("Controls (active low, 10k pull-up):", tx, ty, 2, True)
        ty += 5
        self.text("D-pad: GPIO40=UP 41=DOWN 42=LEFT 1=RIGHT", tx, ty)
        ty += 5
        self.text("Face:  GPIO2=A 48=B 47=X 21=Y", tx, ty)
        ty += 5
        self.text("Sys:   GPIO18=START 0=SELECT 45=L 3=R", tx, ty)
        ty += 8
        self.text("USB (native, firmware flash + debug):", tx, ty, 2, True)
        ty += 5
        self.text("GPIO19=D-  GPIO20=D+", tx, ty)
        ty += 8
        self.text("Reserved (do not use, module-internal):", tx, ty, 2, True)
        ty += 5
        self.text("GPIO26-32 = Octal Flash (N16)", tx, ty)
        ty += 5
        self.text("GPIO33-37 = Octal PSRAM (R8)", tx, ty)
