"""Sheet 6: Controls - 12 buttons with pull-ups and debounce capacitors."""

from ..sheet_base import SchematicSheet


class ControlsSheet(SchematicSheet):
    title = "Controls - 12 Buttons (SNES Layout)"
    page_number = 6
    paper = "A3"
    needed_symbols = ["SW_Push", "R", "C"]

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
            ("L", "BTN_L", "SW11", "R14", "C15", "GPIO35"),
            ("R", "BTN_R", "SW12", "R15", "C16", "GPIO19"),
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
            self.text(f"{name} ({gpio})", bx - 15, by - 5, 2, True)

            # Pull-up resistor (10k to +3V3)
            ry = by + 5
            self.sym("R", rr, "10k", bx, ry, ["1", "2"])
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
        mx, my = 335, 250
        self.text("MENU BUTTON", mx - 15, my - 15, 2.54, True)

        # R19 pull-up
        self.sym("R", "R19", "10k", mx, my + 5, ["1", "2"])
        self.v33(mx, my - 5)
        self.wire(mx, my - 5, mx, my + 5 - 3.81)

        # Junction
        jx, jy = mx, my + 5 + 3.81
        junc_y = jy + 3

        # C20 debounce
        cx, cy = mx + 18, my + 16
        self.sym("C", "C20", "100nF", cx, cy, ["1", "2"])
        self.wire(jx, jy, jx, junc_y)
        self.wire(jx, junc_y, cx, junc_y)
        self.wire(cx, junc_y, cx, cy - 3.81)
        self.gnd(cx, cy + 8)
        self.wire(cx, cy + 3.81, cx, cy + 8)

        # SW13 menu switch
        sw_y = my + 24
        self.sym("SW_Push", "SW13", "MENU", mx, sw_y, ["1", "2"])
        self.wire(jx, junc_y, jx, sw_y)
        self.wire(jx, sw_y, mx - 5.08, sw_y)
        self.gnd(mx + 5.08, sw_y + 8)
        self.wire(mx + 5.08, sw_y, mx + 5.08, sw_y + 8)

        # GPIO label
        self.glabel("BTN_MENU", mx + 28, junc_y, 0)
        self.wire(cx, junc_y, mx + 28, junc_y)

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
