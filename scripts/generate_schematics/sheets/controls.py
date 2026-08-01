"""Sheet 6: Controls - 12 buttons with pull-ups and debounce capacitors."""

from ..sheet_base import SchematicSheet


class ControlsSheet(SchematicSheet):
    title = "Controls - 12 Buttons (SNES Layout)"
    page_number = 6
    paper = "A3"
    needed_symbols = ["SW_Push", "R", "C", "BAT54C"]

    def build(self):
        # Title
        self.text("CONTROLS - 12 Tact Switches", 30, 25, 5, True)
        self.text(
            "Active-low with 10k pull-up + 100nF"
            " debounce per button", 30, 33,
        )

        # Button definitions: 3 columns x 4 rows grid
        buttons = [
            # (label, net_name, sw_ref, r_ref, c_ref, gpio_label)
            # Row 0-3: D-pad
            ("UP", "BTN_UP", "SW1", "R4", "C5", "GPIO40"),
            ("DOWN", "BTN_DOWN", "SW2", "R5", "C6", "GPIO41"),
            ("LEFT", "BTN_LEFT", "SW3", "R6", "C7", "GPIO42"),
            ("RIGHT", "BTN_RIGHT", "SW4", "R7", "C8", "GPIO1"),
            # Row 0-3: Face buttons
            ("A", "BTN_A", "SW5", "R8", "C9", "GPIO2"),
            ("B", "BTN_B", "SW6", "R9", "C10", "GPIO48"),
            ("X", "BTN_X", "SW7", "R10", "C11", "GPIO47"),
            ("Y", "BTN_Y", "SW8", "R11", "C12", "GPIO21"),
            # Row 0-3: System + Shoulder
            ("START", "BTN_START", "SW9", "R12", "C13", "GPIO18"),
            ("SELECT", "BTN_SELECT", "SW10", "R13", "C14", "GPIO0"),
            ("L", "BTN_L", "SW11", "R14", "C15", "GPIO45"),
            ("R", "BTN_R", "SW12", "R15", "C16", "GPIO3"),
        ]

        # Grid layout: 3 columns x 4 rows
        col_x = [65, 200, 335]
        col_titles = [
            "D-PAD", "FACE BUTTONS (ABXY)", "SYSTEM + SHOULDER",
        ]
        row_start_y = 65
        row_spacing = 55

        for col_idx, title in enumerate(col_titles):
            self.text(
                title, col_x[col_idx] - 15,
                row_start_y - 12, 2.54, True,
            )

        for i, (name, net, sw, rr, cc, gpio) in enumerate(buttons):
            col = i // 4
            row = i % 4
            bx = col_x[col]
            by = row_start_y + row * row_spacing

            # Cell label
            # by-9, not by-5: at size 2 this label is ~16mm wide and its right
            # end ran into the GND symbol sitting at (bx, by).
            self.text(f"{name} ({gpio})", bx - 15, by - 9, 2, True)

            # Pull-up resistor (10k to +3V3).
            # Placed at 180 deg so pin 1 is the BOTTOM terminal (the
            # button/signal node) and pin 2 the TOP terminal (+3V3).
            # That is the pad order the R_0805 lands actually have on the
            # board (routing.py: pad 1 = BTN_x, pad 2 = +3V3). The
            # resistor symbol is vertically symmetric, so the drawing is
            # unchanged; only the pin numbering flips. This removes the
            # "R4..R15 pin 2" block from the verify_netlist_diff T4
            # allowlist rather than papering over it.
            ry = by + 5
            self.sym("R", rr, "10k", bx, ry, ["1", "2"], angle=180)
            self.v33(bx, by - 5)
            self.wire(bx, by - 5, bx, ry - 3.81)

            # Junction point (bottom of resistor)
            jx, jy = bx, ry + 3.81

            # Debounce capacitor (100nF to GND, right of resistor)
            cx, cy = bx + 18, by + 16
            self.sym("C", cc, "100nF", cx, cy, ["1", "2"])
            # Horizontal wire from junction to cap
            junc_y = jy + 3
            self.wire(jx, jy, jx, junc_y)
            self.wire(jx, junc_y, cx, junc_y)
            self.wire(cx, junc_y, cx, cy - 3.81)
            self.gnd(cx, cy + 8)
            self.wire(cx, cy + 3.81, cx, cy + 8)

            # Tact switch (to GND, below junction)
            sw_y = by + 24
            self.sym("SW_Push", sw, name, bx, sw_y, ["1", "2"])
            # Orthogonal wire: vertical then horizontal to switch pin
            self.wire(jx, junc_y, jx, sw_y)
            self.wire(jx, sw_y, bx - 5.08, sw_y)
            # Switch output to GND
            self.gnd(bx + 5.08, sw_y + 8)
            self.wire(bx + 5.08, sw_y, bx + 5.08, sw_y + 8)

            # Global label for net (right of cap)
            self.glabel(net, bx + 28, junc_y, 0)
            self.wire(cx, junc_y, bx + 28, junc_y)

        # ═══════════════════════════════════════════════
        # MENU BUTTON (separate from the 12-button grid)
        # ═══════════════════════════════════════════════
        # R9-MED-4 (2026-04-11): R19 pull-up and C20 debounce removed.
        # They were placed on a dead BTN_MENU net in the PCB (never wired
        # to MENU_K). Menu combo works via D1 BAT54C OR-gate: when SW13
        # closes, MENU_K pulls the D1 anodes (BTN_START + BTN_SELECT) low
        # through forward-biased Schottky diodes. Pull-up and debounce are
        # provided by BTN_START's and BTN_SELECT's individual R/C pairs
        # downstream — no separate pull-up/debounce on MENU_K needed.
        # Relocated between the D-PAD and FACE BUTTONS columns in the
        # empty strip below row 3 of the grid (was mx=335, my=250 —
        # the title collided with R15 in the R-button cell above it
        # on the SYSTEM+SHOULDER column).
        mx, my = 130, 260
        self.text("MENU BUTTON", mx - 15, my - 15, 2.54, True)

        # SW13 menu switch — closes MENU_K to GND.
        sw_y = my + 24
        junc_y = my + 8
        self.sym("SW_Push", "SW13", "MENU", mx, sw_y, ["1", "2"])
        self.wire(mx, junc_y, mx, sw_y)
        self.wire(mx, sw_y, mx - 5.08, sw_y)
        self.gnd(mx + 5.08, sw_y + 8)
        self.wire(mx + 5.08, sw_y, mx + 5.08, sw_y + 8)

        # MENU_K node label (SW13 pad 1 → D1.3 common cathode)
        self.glabel("MENU_K", mx + 28, junc_y, 0)
        self.wire(mx, junc_y, mx + 28, junc_y)

        # ── BAT54C dual Schottky diode D1 (R4-HIGH-1 class fix) ──
        # D1 implements the MENU combo: when SW13 pulls MENU_K to GND,
        # D1's common cathode (pin 3) also goes low and the two anodes
        # forward-bias to pull BTN_START and BTN_SELECT LOW through the
        # existing button pull-ups. Firmware has no dedicated BTN_MENU
        # GPIO — it detects the START+SELECT combo (see
        # ``software/main/board_config.h`` ``BTN_MENU_COMBO``).
        #
        # BAT54C library symbol layout (lib_symbols._SYMBOL_BAT54C) —
        # a SOT-23-3 body reused for both Q1 (P-MOSFET) on the Power
        # Supply sheet and D1 (dual Schottky) here. Symbol-local pin
        # positions (world_y = symbol_y - local_y):
        #   pin 1: (-5, -1.27)  bottom-left  → wired to BTN_START
        #   pin 2: (+5.08, -1.27)  bottom-right → wired to BTN_SELECT
        #   pin 3: (0, +5)      top          → wired to MENU_K
        #
        # BAT54C SOT-23 pinout (electrical role for D1):
        #   1 = Anode 1 → BTN_START
        #   2 = Anode 2 → BTN_SELECT
        #   3 = Common cathode → MENU_K
        dx, dy = mx + 40, my + 18
        self.sym("BAT54C", "D1", "BAT54C", dx, dy, ["1", "2", "3"])
        # Annotation moved to the right of the symbol so it does not
        # cover pin 3's stub / MENU_K glabel above D1.
        self.text("MENU combo", dx + 12, dy - 4, 1.5)
        self.text("(START + SELECT)", dx + 12, dy - 1, 1.5)
        # Pin 3 (common cathode, world (dx, dy - 5.08)) → MENU_K glabel
        # placed above D1. Same pattern as U4's +5V tap on sheet 1.
        self.glabel("MENU_K", dx, dy - 10, 90)
        self.wire(dx, dy - 5.08, dx, dy - 10)
        # Pin 1 (anode 1, world (dx - 5.08, dy + 1.27)) → BTN_START to the
        # left. Short horizontal stub, glabel points left (angle 180).
        self.glabel("BTN_START", dx - 11, dy + 1.27, 180)
        self.wire(dx - 5.08, dy + 1.27, dx - 11, dy + 1.27)
        # Pin 2 (anode 2, world (dx + 5.08, dy + 1.27)) → BTN_SELECT to the
        # right. Short horizontal stub, glabel points right (angle 0).
        self.glabel("BTN_SELECT", dx + 11, dy + 1.27, 0)
        self.wire(dx + 5.08, dy + 1.27, dx + 11, dy + 1.27)

        # Schematic note at bottom
        ny = 295
        self.text("BUTTON CIRCUIT (repeated 12x):", 30, ny, 2.54, True)
        self.text(
            "+3V3 --[10k R]-- junction --[100nF C]-- GND",
            30, ny + 8,
        )
        self.text(
            "                     |", 30, ny + 14,
        )
        self.text(
            "                     +-- [SW_Push] -- GND",
            30, ny + 20,
        )
        self.text(
            "                     |", 30, ny + 26,
        )
        self.text(
            "                     +-- GPIO (global label)",
            30, ny + 32,
        )
        self.text(
            "Idle = HIGH (3.3V via pull-up),"
            " Pressed = LOW (grounded)", 30, ny + 40,
        )
