"""Sheet 2: MCU - ESP32-S3-WROOM-1 N16R8 with decoupling and GPIO labels."""

from ..sheet_base import SchematicSheet
from ..config import GPIO_NETS, ESP_PINS


class MCUSheet(SchematicSheet):
    title = "MCU - ESP32-S3-WROOM-1 N16R8"
    page_number = 2
    paper = "A3"
    needed_symbols = ["ESP32-S3-WROOM-1", "C", "R"]

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

        # --- EN pull-up resistor (10k) ---
        en_y = MCU_Y - 33.02  # EN pin level
        r_en_x = px_l - 25
        r_en_y = MCU_Y - 45  # resistor center above EN line
        self.sym("R", "R3", "10k", r_en_x, r_en_y, ["1", "2"])
        self.wire(px_l, en_y, r_en_x, en_y)
        self.wire(r_en_x, en_y, r_en_x, r_en_y + 3.81)
        self.v33(r_en_x, r_en_y - 8)
        self.wire(r_en_x, r_en_y - 8, r_en_x, r_en_y - 3.81)
        self.text("EN pull-up", r_en_x - 12, r_en_y, 1.5)

        # --- EN reset capacitor (100nF to GND) ---
        # Cap below EN line: pin 1 (top) connects to EN, pin 2 (bottom) to GND
        c_en_x = px_l - 35
        c_en_y = en_y + 10  # center below EN line
        self.sym("C", "C3", "100nF", c_en_x, c_en_y, ["1", "2"])
        self.wire(r_en_x, en_y, c_en_x, en_y)
        self.wire(c_en_x, en_y, c_en_x, c_en_y - 3.81)
        self.gnd(c_en_x, c_en_y + 8)
        self.wire(c_en_x, c_en_y + 3.81, c_en_x, c_en_y + 8)
        self.text("RC reset delay", c_en_x - 15, c_en_y + 3, 1.5)

        # --- Decoupling cap (100nF near 3V3) ---
        c_dec_x = px_l - 15
        c_dec_y = MCU_Y - 45  # above 3V3 pins
        self.sym("C", "C4", "100nF", c_dec_x, c_dec_y, ["1", "2"])
        self.wire(c_dec_x, c_dec_y + 3.81, c_dec_x, pwr2_y)
        self.gnd(c_dec_x, c_dec_y - 8)
        self.wire(c_dec_x, c_dec_y - 3.81, c_dec_x, c_dec_y - 8)
        self.text("Decoupling", c_dec_x - 10, c_dec_y, 1.5)

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

        self.text("JOYSTICK", px_r + 28, MCU_Y + 2, 2, True)
        self.text("(ADC)", px_r + 28, MCU_Y + 6, 1.5)

        # Generate GPIO labels with 15mm wire stubs
        for _pn, (side, gpio, yoff) in ESP_PINS.items():
            if side == "B" or gpio in ("3V3", "EN", "GND"):
                continue

            if isinstance(gpio, int):
                net = GPIO_NETS.get(gpio, f"GPIO{gpio}")
            elif gpio == "TX0":
                net = "UART_TX0"
            elif gpio == "RX0":
                net = GPIO_NETS.get(44, "JOY_Y")
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
        self.text("GPIO46=WR  GPIO3=RD  GPIO45=BL", tx, ty)
        ty += 8
        self.text("Audio (I2S):", tx, ty, 2, True)
        ty += 5
        self.text("GPIO15=BCLK  GPIO16=LRCK  GPIO17=DOUT", tx, ty)
        ty += 8
        self.text("SD Card (SPI):", tx, ty, 2, True)
        ty += 5
        self.text("GPIO36=MOSI  GPIO37=MISO  GPIO38=CLK  GPIO39=CS", tx, ty)
        ty += 8
        self.text("Controls (active low, 10k pull-up):", tx, ty, 2, True)
        ty += 5
        self.text("D-pad: GPIO40=UP 41=DOWN 42=LEFT 1=RIGHT", tx, ty)
        ty += 5
        self.text("Face:  GPIO2=A 48=B 47=X 21=Y", tx, ty)
        ty += 5
        self.text("Sys:   GPIO18=START 0=SELECT 35=L 19=R", tx, ty)
        ty += 8
        self.text("Joystick (ADC, optional):", tx, ty, 2, True)
        ty += 5
        self.text("GPIO20=X_AXIS (ADC2_CH9)", tx, ty)
        ty += 5
        self.text("GPIO44/RX0=Y_AXIS (ADC2_CH7)", tx, ty)
        ty += 8
        self.text("Reserved (do not use):", tx, ty, 2, True)
        ty += 5
        self.text("GPIO26-32 = Octal PSRAM (internal)", tx, ty)
        ty += 5
        self.text("GPIO43 = TX0 (debug UART output)", tx, ty)
