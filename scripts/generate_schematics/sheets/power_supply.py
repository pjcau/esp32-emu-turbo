"""Sheet 1: Power Supply - USB-C -> IP5306 bare IC -> SY8089 buck -> 3.3V."""

from ..sheet_base import SchematicSheet


class PowerSupplySheet(SchematicSheet):
    title = "Power Supply"
    page_number = 1
    # Upgraded to A3 (297x420 landscape) so the USB-C / IP5306 / battery
    # cluster, the USB ESD block, the SY8089 buck regulator, the power
    # switch and the charging LEDs can each sit in their own zone
    # without overlapping annotation text. Previously A4 (210x297) —
    # too small once R22/R23/U4 (USB ESD) were added.
    paper = "A3"
    needed_symbols = [
        "USB_C", "IP5306", "SY8089AAAC", "Conn_JST_PH_2",
        "Battery", "C", "R", "L", "SW_Push", "LED",
        "USBLC6_2SC6", "BAT54C", "PWR_FLAG",
    ]

    def build(self):
        # Title
        self.text("POWER SUPPLY", 30, 25, 5, True)
        self.text(
            "USB-C -> IP5306 SOP-8 (charge + boost)"
            " -> SY8089AAAC buck -> 3.3V rail", 30, 33,
        )

        # ═══════════════════════════════════════════════
        # USB-C CONNECTOR (left side)
        # ═══════════════════════════════════════════════
        ux, uy = 50, 85
        self.sym("USB_C", "J1", "USB_C", ux, uy, range(1, 7))

        # Pin world positions (local y inverted):
        #   VBUS: (ux+7.62, uy-3.81)
        #   CC1:  (ux+7.62, uy)
        #   CC2:  (ux+7.62, uy+3.81)
        #   D+:   (ux-7.62, uy-3.81)
        #   D-:   (ux-7.62, uy)
        #   GND:  (ux, uy+8.89)

        vbus_x = ux + 7.62
        vbus_y = uy - 3.81

        # D+ / D- labels exiting USB-C (pre-protection nets)
        self.glabel("USB_D+", ux - 12, uy - 3.81, 180)
        self.wire(ux - 7.62, uy - 3.81, ux - 12, uy - 3.81)
        self.glabel("USB_D-", ux - 12, uy, 180)
        self.wire(ux - 7.62, uy, ux - 12, uy)

        # ── USB ESD protection (R4-HIGH-1 fix) ──
        # The PCB (scripts/generate_pcb/routing.py) places USBLC6-2SC6
        # (U4) + two 22Ω series resistors (R22, R23) between the USB-C
        # connector and the ESP32-S3 D+/D- pins. These symbols were
        # previously missing from the schematic — any reviewer reading
        # only the schematic could not see the ESD protection. Now
        # instantiated so the schematic matches the CPL.
        #
        # RELOCATED (2026-07-24): the previous position (45, 160) sat
        # directly on top of SW16, C1, U3 (AMS1117) and C2 which all
        # live at y=160 in the VOLTAGE REGULATOR / POWER SWITCH row.
        # Now placed on its own dedicated USB-DATA row (y=140) tucked
        # underneath the USB-C connector on the A3-landscape sheet,
        # well clear of the CHARGING LEDs (x>=250) and of the AMS1117
        # regulator row (y>=190) below.
        u4x, u4y = 60, 140
        self.sym("USBLC6_2SC6", "U4", "USBLC6-2SC6", u4x, u4y, range(1, 7))
        self.text("USB ESD TVS", u4x - 20, u4y - 16, 1.5)
        # The USBLC6_2SC6 library symbol in this generator uses the
        # simple 6-pin pad layout (pins on the left/right edges). We
        # connect the logical nets via glabels with short wire stubs.
        stub = 6
        # USBLC6-2SC6 pin table (ST doc ID 11265 Rev 5, p.1 "Functional
        # diagram (top view)", mirrored in
        # hardware/datasheets/U4_USBLC6-2SC6_C7519.pdf):
        #
        #     I/O1  1 | 6  I/O1
        #     GND   2 | 5  VBUS
        #     I/O2  3 | 4  I/O2
        #
        # Pins 1 and 6 are the SAME internal node (I/O1); pins 3 and 4
        # are the SAME internal node (I/O2). The part is a two-line
        # protector, so each data line is bonded out twice to let the
        # trace run *through* the package. Consequently pin 6 CANNOT
        # carry the post-series-resistor net: putting USB_DM_MCU on
        # pin 6 while USB_D- sits on pin 1 would short R23 out
        # internally (same for USB_DP_MCU / R22 on pins 4 / 3).
        # The PCB (routing.py _PAD_NETS) already has 1=6=USB_D- and
        # 3=4=USB_D+; the schematic now agrees.
        #
        # Left side stubs (connector side)
        self.glabel("USB_D-", u4x - 10 - stub, u4y - 2.54, 180)
        self.wire(u4x - 10 - stub, u4y - 2.54, u4x - 10, u4y - 2.54)
        self.glabel("USB_D+", u4x - 10 - stub, u4y,        180)
        self.wire(u4x - 10 - stub, u4y,        u4x - 10, u4y)
        # Right side stubs — SAME nets as the left side (internal node),
        # they are the pins the D+/D- traces leave the TVS on toward
        # R22/R23. The pre/post split is made by R22/R23, not by U4.
        self.glabel("USB_D-", u4x + 10 + stub, u4y + 2.54, 0)
        self.wire(u4x + 10, u4y + 2.54, u4x + 10 + stub, u4y + 2.54)
        self.glabel("USB_D+", u4x + 10 + stub, u4y,        0)
        self.wire(u4x + 10, u4y,        u4x + 10 + stub, u4y)
        # GND on bottom
        self.gnd(u4x, u4y + 12)
        self.wire(u4x, u4y + 7.62, u4x, u4y + 12)
        # Pin 5 is the VBUS clamp reference — it must sit on the USB
        # input rail (VBUS), NOT on +5V. +5V is the IP5306 BOOST OUTPUT
        # and is present even with the cable unplugged; tying the TVS
        # reference there would forward-bias the VBUS clamp from the
        # battery whenever no charger is attached.
        self.glabel("VBUS", u4x, u4y - 12, 90, "input")
        self.wire(u4x, u4y - 7.62, u4x, u4y - 12)

        # Series resistors R22/R23 between USBLC6 MCU-side and ESP32.
        #
        # BUG FIX: these two resistors used to be wired HORIZONTALLY
        # (stubs at r22x ± 3.81) while the "R" library symbol has its
        # pins VERTICALLY at (0, ±3.81). Both stubs therefore missed
        # both pins and R22/R23 were completely floating in the netlist
        # — the exported netlist contained no node for either part, so
        # the schematic silently claimed the USB data lines went
        # straight from the TVS to the MCU with no series termination.
        #
        # Pin order follows the PCB footprint (routing.py _PAD_NETS):
        #   R22: pad 1 = USB_DP_MCU (MCU side), pad 2 = USB_D+ (TVS side)
        #   R23: pad 1 = USB_DM_MCU (MCU side), pad 2 = USB_D-  (TVS side)
        # The "R" symbol has pin 1 on top and pin 2 at the bottom, so the
        # MCU-side label goes above and the connector-side label below.
        r22x, r22y = u4x + 30, u4y - 6
        self.sym("R", "R22", "22",  r22x, r22y, ["1", "2"])
        self.text("D+ 22Ω", r22x + 4, r22y, 1.5)
        self.wire(r22x, r22y - 3.81, r22x, r22y - 8)
        self.glabel("USB_DP_MCU", r22x, r22y - 8, 90)
        self.wire(r22x, r22y + 3.81, r22x, r22y + 8)
        self.glabel("USB_D+", r22x, r22y + 8, 270)

        r23x, r23y = u4x + 46, u4y - 6
        self.sym("R", "R23", "22",  r23x, r23y, ["1", "2"])
        self.text("D- 22Ω", r23x + 4, r23y, 1.5)
        self.wire(r23x, r23y - 3.81, r23x, r23y - 8)
        self.glabel("USB_DM_MCU", r23x, r23y - 8, 90)
        self.wire(r23x, r23y + 3.81, r23x, r23y + 8)
        self.glabel("USB_D-", r23x, r23y + 8, 270)

        # CC1, CC2 pull-down resistors (5.1k for USB-C UFP detection)
        r1x, r1y = 78, 98
        r2x, r2y = 90, 98
        self.sym("R", "R1", "5.1k", r1x, r1y, ["1", "2"])
        self.sym("R", "R2", "5.1k", r2x, r2y, ["1", "2"])
        # Explicit USB_CC1 / USB_CC2 labels so schematic↔PCB sync check
        # sees the connector's full expected net set (datasheet_specs.py).
        self.glabel("USB_CC1", vbus_x + 4, uy, 0)
        self.glabel("USB_CC2", vbus_x + 4, uy + 3.81, 0)
        # CC1 -> R1 BY LABEL, not by wire.
        # The L-shaped route ran down x=78 and crossed the CC2 line at
        # (78, 88.81). Two different nets crossing reads as a connection to
        # anyone scanning the sheet, and only the absence of a junction dot
        # says otherwise. Guarded by scripts/verify_schematic_crossings.py.
        self.wire(vbus_x, uy, vbus_x + 4, uy)
        self.link("USB_CC1", r1x, r1y - 3.81, 90, glob=True)
        # CC2 -> R2 (orthogonal L-shape)
        self.wire(vbus_x, uy + 3.81, r2x, uy + 3.81)
        self.wire(r2x, uy + 3.81, r2x, r2y - 3.81)
        # R1, R2 GND
        self.gnd(r1x, r1y + 8)
        self.wire(r1x, r1y + 3.81, r1x, r1y + 8)
        self.gnd(r2x, r2y + 8)
        self.wire(r2x, r2y + 3.81, r2x, r2y + 8)

        # USB GND
        self.gnd(ux, uy + 13)
        self.wire(ux, uy + 8.89, ux, uy + 13)

        # ═══════════════════════════════════════════════
        # IP5306 BARE IC (eSOP-8)
        # ═══════════════════════════════════════════════
        ipx, ipy = 160, 85
        self.sym(
            "IP5306", "U2", "IP5306",
            ipx, ipy, range(1, 10),
        )

        # IP5306 pin world positions:
        #   VIN(1):  (ipx-10.16, ipy-5.08)
        #   LED1(2): (ipx-10.16, ipy-2.54)
        #   LED2(3): (ipx-10.16, ipy)
        #   LED3(4): (ipx-10.16, ipy+2.54)
        #   KEY(5):  (ipx+10.16, ipy+5.08)
        #   BAT(6):  (ipx+10.16, ipy+2.54)
        #   SW(7):   (ipx+10.16, ipy)
        #   VOUT(8): (ipx+10.16, ipy-5.08)
        #   GND(9):  (ipx, ipy+10.16)

        vin_x = ipx - 10.16
        vin_y = ipy - 5.08
        vout_x = ipx + 10.16
        vout_y = ipy - 5.08
        sw_x = ipx + 10.16
        sw_y = ipy
        bat_x = ipx + 10.16
        bat_y = ipy + 2.54
        key_x = ipx + 10.16
        key_y = ipy + 5.08
        gnd_ip_y = ipy + 10.16

        # ---- VBUS_IN -> F1 (PTC) -> VBUS -> VIN wiring ----
        # R3-HIGH-4 FIX (2026-07-31): F1 (PTC resettable fuse, 2A hold /
        # 4A trip, BSMD1812-200-30V) sits in series between the USB-C
        # VBUS lands and everything downstream. The connector side is
        # net VBUS_IN; U4.5 (TVS clamp reference), C17 and U2 VIN stay
        # on VBUS. Drawn with the "R" symbol (no fuse symbol in
        # lib_symbols) at angle=90: pin 1 lands LEFT (VBUS_IN, matching
        # PCB pad 1 west toward J1) and pin 2 RIGHT (VBUS).
        # CIN (C17, 10uF) teed off the VIN line
        cin_x, cin_y = 118, 90
        f1x = 72
        self.wire(vbus_x, vbus_y, f1x - 3.81, vbus_y)
        # ON the wire, not 2 mm above it. At vbus_y - 2 a label names
        # nothing, so the rail would stay unnamed and KiCad would drop it
        # from the exported netlist (the original VBUS label had exactly
        # that bug).
        self.glabel("VBUS_IN", vbus_x + 4, vbus_y, 0)
        self.sym("R", "F1", "2A", f1x, vbus_y, ["1", "2"], angle=90)
        self.text("PTC 2A hold / 4A trip", f1x - 16, vbus_y - 7, 1.5)
        self.wire(f1x + 3.81, vbus_y, cin_x, vbus_y)
        # PWR_FLAG: VBUS used to be driven by J1's power-out VBUS pin;
        # with F1 in series that pin now drives VBUS_IN, and nothing of
        # power-out type sits on VBUS itself (F1 is drawn with passive
        # "R" pins) — same situation as +3V3 behind L2. Without this,
        # ERC reports power_pin_not_driven on U2 VIN.
        self.flag(90, vbus_y)
        # Global, not local: the net already has a VBUS global label at
        # U4, and mixing label types on one net is the ERC
        # same_local_global_label warning — the merge works but only by
        # KiCad's same-text courtesy.
        self.glabel("VBUS", f1x + 8, vbus_y, 0)
        # CIN junction down to cap
        self.wire(cin_x, vbus_y, cin_x, cin_y - 3.81)
        self.sym("C", "C17", "10uF", cin_x, cin_y, ["1", "2"])
        self.text("VIN decoupling", cin_x + 3, cin_y - 5, 1.5)
        self.gnd(cin_x, cin_y + 8)
        self.wire(cin_x, cin_y + 3.81, cin_x, cin_y + 8)
        # Continue VIN line to IP5306 (orthogonal L-shape)
        jog_x = cin_x + 10
        self.wire(cin_x, vbus_y, jog_x, vbus_y)
        self.wire(jog_x, vbus_y, jog_x, vin_y)
        self.wire(jog_x, vin_y, vin_x, vin_y)

        # ---- LED pins (NC) ----
        led1_x = ipx - 10.16
        for led_y in [ipy - 2.54, ipy, ipy + 2.54]:
            self.nc(led1_x - 2, led_y)
            self.wire(led1_x, led_y, led1_x - 2, led_y)
        self.text("NC (LED1-3)", ipx - 22, ipy - 4, 1.5)

        # ---- IP5306 GND ----
        self.gnd(ipx, gnd_ip_y + 4)
        self.wire(ipx, gnd_ip_y, ipx, gnd_ip_y + 4)

        # ---- L1 inductor: BAT -> L1 -> SW ----
        l1_x, l1_y = 190, 85
        # Rotated 180 deg so pin 1 is the BOTTOM terminal, which is the one
        # the BAT+ rail arrives on. Upright, this drawing put pin 2 on BAT+
        # and pin 1 on the switching node — the reverse of the board and of
        # datasheet_specs.py::L1, which states pin 1 = "Battery side" and
        # pin 2 = "SW/LX node (to IP5306 pin 7)". An inductor is symmetric,
        # so nothing was electrically wrong, but the netlist said something
        # false about which pad is which.
        #
        # This was invisible until the BAT+ label above was moved onto its
        # wire: while the rail was unnamed, L1 had no BAT+ pin at all in the
        # exported netlist and T4 had nothing to compare. Rotating rather
        # than rerouting is what symbol()'s own docstring prescribes for a
        # symmetric two-terminal part whose pad 1 is at the other end; the
        # body is a symmetric rectangle, so the sheet looks identical.
        self.sym("L", "L1", "1uH", l1_x, l1_y, ["1", "2"], 180)
        self.text("1uH >4.5A", l1_x + 3, l1_y - 3, 1.5)
        # After the rotation: pin 2 (top) at (l1_x, l1_y - 3.81)
        #                     pin 1 (bottom) at (l1_x, l1_y + 3.81)
        # BAT -> L1 bottom: horizontal then vertical
        self.wire(bat_x, bat_y, l1_x, bat_y)
        self.wire(l1_x, bat_y, l1_x, l1_y + 3.81)
        # L1 top -> SW: vertical then horizontal
        self.wire(l1_x, l1_y - 3.81, l1_x, sw_y)
        self.wire(l1_x, sw_y, sw_x, sw_y)
        # Name the boost switch node with the PCB's net name. Until the
        # uuid-collision fix (2026-07-31) L1.2/U2.7 were silently absent
        # from the exported netlist, so T4 had nothing to compare; now
        # they exist and the label closes the LX entry in T2_ALLOW.
        # GLOBAL label, not local: a local label exports as
        # "/Power Supply/LX" and never matches the PCB's "LX".
        # Mid-span on the horizontal, which runs LEFT from L1 to the SW
        # pin (l1_x=190 -> sw_x=170.16) — at l1_x+6 it floated past the
        # wire's end, and at l1_x it sat on L1's body.
        self.glabel("LX", l1_x - 6, sw_y, 0)

        # ---- VOUT -> +5V rail ----
        # Route VOUT up then right to avoid L1
        vout_turn_y = 70
        self.wire(vout_x, vout_y, vout_x, vout_turn_y)

        # COUT (C19, 22uF) on VOUT rail
        cout_x = 205
        cout_y = 78
        # Rail drawn ONCE, up to the first tap. It used to run to x=215 and
        # then be redrawn 205->227 and 215->225, so ~20mm of the rail was
        # two or three wires of ink stacked on each other.
        self.wire(vout_x, vout_turn_y, cout_x, vout_turn_y)
        self.sym(
            "C", "C19", "22uF",
            cout_x, cout_y, ["1", "2"],
        )
        # Short label placed above the cap so it does not crowd C27 to
        # its right or the Q1/C18 cluster below.
        self.text(
            "VOUT bulk",
            cout_x - 3, cout_y - 8, 1.5,
        )
        self.wire(
            cout_x, vout_turn_y, cout_x, cout_y - 3.81,
        )
        self.gnd(cout_x, cout_y + 8)
        self.wire(cout_x, cout_y + 3.81, cout_x, cout_y + 8)

        # C27: HF decoupling (10uF) near VOUT
        # Placed with extra horizontal gap from C19 so its label does
        # not run into "VOUT bulk" above C19.
        c27_x = cout_x + 22
        c27_y = cout_y
        # Placed at 180 deg: the C_0805 land for C27 on the board has
        # pad 1 on the GND side and pad 2 on the +5V side (routing.py
        # _c27 block: pad 1 -> GND via, pad 2 -> VOUT via), the opposite
        # of C19/C23/C25. Rotating the (vertically symmetric) capacitor
        # symbol keeps the drawing identical while making pin 1 the
        # bottom/GND terminal, so schematic and PCB agree on which pad
        # is which.
        self.sym("C", "C27", "10uF", c27_x, c27_y, ["1", "2"], angle=180)
        # BELOW the cap, not above: above at c27_x-3 collided with the +5V
        # rail label, and shifting it left ran it into "VOUT bulk" over C19.
        # Underneath is empty (the GND symbol prints no visible text).
        self.text("HF bypass", c27_x - 5, c27_y + 13, 1.5)
        self.wire(cout_x, vout_turn_y, c27_x, vout_turn_y)
        self.wire(c27_x, vout_turn_y, c27_x, c27_y - 3.81)
        self.gnd(c27_x, c27_y + 8)
        self.wire(c27_x, c27_y + 3.81, c27_x, c27_y + 8)

        # +5V power symbol and global label
        self.v5(215, vout_turn_y - 5)
        self.wire(215, vout_turn_y - 5, 215, vout_turn_y)
        # Junction: this vertical lands mid-span on the cout_x->c27_x rail.
        self.junction(215, vout_turn_y)
        # Label sits on the rail's own right-hand end (c27_x), so no extra
        # wire is needed — the 215->225 stub duplicated the rail underneath.
        self.glabel("+5V", c27_x, vout_turn_y, 0, "output")

        # NOTE: PWR_FLAG on +5V was REMOVED because IP5306 VOUT (pin 8) is
        # already typed as `power_out` in the library symbol, so it
        # already drives the +5V net. Adding PWR_FLAG here created a
        # second power-output pin on the same net and caused ERC
        # "Pins of type Power output and Power output are connected"
        # (the pre-existing R4 critical). IP5306 VOUT alone satisfies
        # KiCad's "power input must be driven" requirement on +5V.

        # ---- CBAT (C18, 10uF) on BAT line ----
        # Moved further down and slightly right of R16 (was cbat_x=198,
        # causing "BAT decoupling" text to run into Q1's "P-MOSFET RPP /
        # SI2301CDS" labels). The new tap (185, 87.54) sits between R16
        # at x=182 and Q1 at x=210 — clear of both the KEY horizontal
        # wire (which runs at y=90.08 from x=170.16 to x=182) and the
        # Q1 label cluster.
        cbat_x = 185
        cbat_y = 108
        self.sym("C", "C18", "10uF", cbat_x, cbat_y, ["1", "2"])
        # Label placed to the LEFT of the cap to keep the right side
        # (which points toward Q1/J3) completely clear.
        self.text("BAT bypass", cbat_x - 16, cbat_y - 8, 1.5)
        # Tee down from BAT wire at y=bat_y
        self.wire(cbat_x, bat_y, cbat_x, cbat_y - 3.81)
        self.gnd(cbat_x, cbat_y + 8)
        self.wire(cbat_x, cbat_y + 3.81, cbat_x, cbat_y + 8)

        # ---- KEY pull-up (R16 100k to +5V, always-on) ----
        r16_x = 182
        # 76.5, threading two constraints half a millimetre apart:
        #   * at 76.0 the Reference field (y-5) landed on the +5V rail
        #     junction at y=70 — verify_schematic_overlaps.py.
        #   * at 79.0 the KEY link stub (y+3.81, then 3.81 further) reached
        #     y=86.6 and crossed the IP5306 wire at y=85 —
        #     verify_schematic_crossings.py.
        # 76.5 puts the Reference at 71.5 (0.365mm clear of the junction) and
        # the stub end at 84.1 (0.88mm clear of the y=85 wire).
        r16_y = 72
        self.sym("R", "R16", "100k", r16_x, r16_y, ["1", "2"])
        self.text("Always-on", r16_x + 3, r16_y - 3, 1.5)
        # R16 pin1 (top) -> +5V by TAPPING the rail, not by a second
        # power symbol. The old stub ran from a redundant +5V symbol at
        # y=68 down to the pin and crossed the +5V rail at (182, 70) —
        # same net, so harmless electrically, but it drew as a crossing.
        self.wire(r16_x, vout_turn_y, r16_x, r16_y - 3.81)
        self.junction(r16_x, vout_turn_y)
        # R16 pin2 (bottom) -> KEY BY LABEL, not by wire.
        # The orthogonal route went down x=182 from y=79.81 to y=90.08 and
        # crossed the IP5306 lines at y=85.00 and y=87.54 on the way.
        # GLOBAL label, and named IP5306_KEY to match the board's net.
        # A local label is scoped to the sheet, so KiCad exported it as
        # "/Power Supply/KEY" while the PCB called the same node
        # IP5306_KEY — two of the T4 pin-to-net mismatches, plus the T1
        # "schematic net missing from PCB" failure, for one naming slip.
        self.link("IP5306_KEY", r16_x, r16_y + 3.81, 270, glob=True)
# Points UP, not right: a rightward stub extends the KEY horizontal
        # past x=185, where C18's tap crosses it (see the CBAT comment).
        self.link("IP5306_KEY", key_x, key_y, 90, glob=True)

        # ---- Battery: JST PH connector + Q1 P-MOSFET RPP + Battery symbol ----
        # JST PH 2-pin connector — pushed further right on A3 landscape
        # so the JST/BT1 pair have room to breathe and the Q1 label
        # cluster doesn't run into them.
        jst_x, jst_y = 268, 92
        self.sym(
            "Conn_JST_PH_2", "J3", "JST PH 2-pin",
            jst_x, jst_y, ["1", "2"],
        )
        # JST pin1 "+" at (jst_x - 6.35, jst_y - 1.27)
        # JST pin2 "-" at (jst_x - 6.35, jst_y + 1.27)
        jst_plus_x = jst_x - 6.35
        jst_plus_y = jst_y - 1.27
        jst_minus_y = jst_y + 1.27

        # ── Q1 P-MOSFET reverse polarity protection (v4.0) ──
        # Q1 sits in series on the BAT+ rail between J3 and IP5306.
        # BAT+ (IP5306 side) → Q1 Drain (pin 3) → Q1 Source (pin 2) → BAT_IN → J3.1
        # Gate pulled low via R24 100K → MOSFET always ON for correct polarity.
        # Reverse polarity: body diode blocks, protecting IP5306.
        q1x, q1y = 210, 92
        self.sym("BAT54C", "Q1", "SI2301CDS", q1x, q1y, ["1", "2", "3"])
        # NOTE: reusing BAT54C symbol footprint (SOT-23-3) for Q1 P-MOSFET
        # Pin mapping: 1=Gate(bottom-left), 2=Source(bottom-right), 3=Drain(top)
        # Two-line annotation ABOVE the symbol with 3mm vertical spacing
        # so the lines don't touch each other or the symbol's Value text.
        self.text("P-MOSFET RPP", q1x + 8, q1y - 26, 1.5)
        self.text("(SI2301CDS)",  q1x - 6, q1y - 12, 1.5)

        # Q1 pin 3 (Drain) at (q1x, q1y - 3.81-ish) — connects to BAT+ (IP5306 side)
        # Wire BAT+ line from cbat_x to Q1 drain
        # Starts at l1_x, not cbat_x: cbat_x (185) is left of l1_x (190), so
        # this span used to re-draw 5mm of the bat_x->l1_x rail above it.
        self.wire(l1_x, bat_y, q1x, bat_y)
        # C18 taps the rail mid-span now, so it needs a dot.
        self.junction(cbat_x, bat_y)
        self.wire(q1x, bat_y, q1x, q1y - 5)
        # Mid-span on the horizontal rail. At (q1x + 2, bat_y - 2) it was
        # 2 mm off the horizontal and 2 mm off the vertical, i.e. on neither
        # — so BAT+ came out of the netlist with one node (SW16.1, from
        # its own global label) while L1.1, C18.1, Q1.3 and U2.6 were
        # absent. The battery rail was undrawn as far as any gate could see.
        # Global label (see VBUS note); angle=180 extends LEFT — rightward
        # the text lands on Q1's body.
        self.glabel("BAT+", q1x - 10, bat_y, 180)

        # Q1 pin 2 (Source) — connects to BAT_IN → J3.1
        # Source exits to the right toward JST connector.
        #
        # Jog UP to jst_plus_y FIRST, then run horizontally. The previous
        # route ran horizontally at q1y + 1.27 == 93.27, which is exactly
        # jst_minus_y — so the wire landed on J3 pin 2 (GND) and the
        # following vertical welded J3.1, J3.2 and Q1.2 into a single
        # node. The schematic then described a battery connector with its
        # + and - shorted together, while the PCB copper was correct
        # (verify_netlist_diff T4: J3.1 sch='GND' pcb='BAT_IN').
        self.wire(q1x + 5, q1y + 1.27, q1x + 5, jst_plus_y)
        self.wire(q1x + 5, jst_plus_y, jst_plus_x, jst_plus_y)
        # Label must sit ON the segment it names. At q1y - 0.5 it floated
        # 1.77mm off every wire and renamed nothing — and the correction
        # that replaced it, jst_plus_y - 1.5, was still 1.5 mm off the same
        # horizontal, so it renamed nothing either. BAT_IN kept coming out
        # of the netlist with one node (BT1.1) and both J3.1 and Q1.2 stayed
        # missing. That is why the T4 mismatch this comment records stopped
        # being reported: the pins left the netlist, they did not agree.
        # Placed relative to the wire's right-hand end rather than to Q1:
        # at q1x + 8 it sits on the wire correctly but lands on C27's
        # "HF bypass" annotation at (222, 91), which verify_schematic_overlaps
        # rejects. Anywhere on the span x in [q1x + 5, jst_plus_x] names the
        # same net, so it goes where there is room.
        # Global label (see VBUS note): this is the one that names the
        # Q1->J3 copper run.
        self.glabel("BAT_IN", jst_plus_x - 20, jst_plus_y, 0)

        # Q1 pin 1 (Gate) — pulled to GND via R24 (100K)
        r24x, r24y = q1x - 8, q1y + 10
        self.sym("R", "R24", "100k", r24x, r24y, ["1", "2"])
        # Short label placed BELOW R24 (past its GND arrow) so it does
        # not run into Q1's symbol/value or the C18 annotation.
        self.text("Q1 gate PD", r24x - 5, r24y + 14, 1.5)
        # Wire Q1 gate to R24 pin 1
        self.wire(q1x - 5, q1y + 1.27, r24x, q1y + 1.27)
        self.wire(r24x, q1y + 1.27, r24x, r24y - 3.81)
        # Name the gate node with the PCB's net name (same story as LX:
        # Q1.1/R24.1 were missing from the netlist until the uuid fix).
        # GLOBAL label so the net exports as "RPP_GATE", not
        # "/Power Supply/RPP_GATE". angle=180 extends the text LEFT —
        # rightward it lands on Q1's symbol body.
        self.glabel("RPP_GATE", r24x, q1y + 1.27, 180)
        # R24 pin 2 to GND
        self.gnd(r24x, r24y + 8)
        self.wire(r24x, r24y + 3.81, r24x, r24y + 8)

        # JST pin2 (-) to GND
        self.gnd(jst_plus_x, jst_y + 6)
        self.wire(jst_plus_x, jst_minus_y, jst_plus_x, jst_y + 6)

        # Battery symbol (off-board representation) — pushed further
        # right to match the moved JST connector.
        bt_x, bt_y = 315, 90
        self.sym(
            "Battery", "BT1", "LiPo 3.7V 5000mAh",
            bt_x, bt_y, ["1", "2"],
        )
        self.text("105080", bt_x + 5, bt_y - 3, 1.5)
        self.text("3.7V 5000mAh", bt_x + 5, bt_y + 1, 1.5)
        # BT1 pin "+" at (bt_x, bt_y - 3.81)
        # BT1 pin "-" at (bt_x, bt_y + 3.81)
        # J3 <-> BT1 continuity comes from the BAT_IN global labels (one
        # on the Q1->J3 run, one here). The old extra stub at jst_x+3.81
        # started on no pin — J3's pins are both on its LEFT side — and
        # dangled for as long as it existed (ERC unconnected_wire_endpoint).
        self.glabel("BAT_IN", bt_x - 5, bt_y - 3.81, 180)
        self.wire(bt_x - 5, bt_y - 3.81, bt_x, bt_y - 3.81)
        # Battery GND
        self.gnd(bt_x, bt_y + 8)
        self.wire(bt_x, bt_y + 3.81, bt_x, bt_y + 8)

        # ═══════════════════════════════════════════════
        # VOLTAGE REGULATOR SECTION (below)
        # Pushed further down on the A3 sheet so the title/subtitle
        # don't collide with the USB ESD block on the row above
        # (U4 at y=140, R22/R23 at y=138/144).
        # ═══════════════════════════════════════════════
        self.text("VOLTAGE REGULATOR", 30, 175, 3.81, True)
        self.text(
            "5V -> SY8089AAAC synchronous buck -> 3.327V (2A cont. / 3A peak)",
            30, 182,
        )
        self.text(
            "Replaces AMS1117-3.3 LDO: ~90% efficiency instead of burning"
            " 1.7V x Iload (0.85W at 500mA).",
            30, 187, 1.8,
        )

        # ── Input side ──────────────────────────────────────────
        # C_IN: datasheet AN_SY8089/A requires >= 10uF ceramic on IN and
        # shows 22uF in the typical application. C1 is a 22uF X5R MLCC.
        u3x, u3y = 100, 205
        in_y = u3y - 2.54     # world Y of the IN pin (local +2.54)
        en_y = u3y + 2.54     # world Y of the EN pin (local -2.54)

        c1x, c1y = 75, 206.27
        self.sym("C", "C1", "22uF", c1x, c1y, ["1", "2"])
        self.text("C_IN", c1x - 11, c1y - 2, 1.5)
        self.v5(c1x, 196)
        self.wire(c1x, 196, c1x, in_y)           # +5V rail down to C1 pin 1
        self.wire(c1x, in_y, u3x - 8.89, in_y)   # +5V rail across to U3 IN
        self.gnd(c1x, 216)
        self.wire(c1x, c1y + 3.81, c1x, 216)

        # ── SY8089AAAC ──────────────────────────────────────────
        self.sym(
            "SY8089AAAC", "U3", "SY8089AAAC",
            u3x, u3y, ["1", "2", "3", "4", "5"],
        )
        # EN tied high to the input rail. Datasheet: "Pull high (>1.5V) to
        # turn on. Do not float." EN abs-max is Vin+0.6V, so a hard tie to
        # the input rail is in spec; the 1M pull-down in the datasheet note
        # is only needed when EN is driven from a high-impedance source.
        self.v5(80, en_y)
        self.wire(80, en_y, u3x - 8.89, en_y)
        self.text("EN tied to VIN (always on)", 46, en_y - 11, 1.5)
        # GND
        self.gnd(u3x, u3y + 15)
        self.wire(u3x, u3y + 7.62, u3x, u3y + 15)

        # ── Switch node -> inductor ─────────────────────────────
        l2x, l2y = 125, 206.27
        self.sym("L", "L2", "2.2uH", l2x, l2y, ["1", "2"])
        self.text("Isat 2.95A", l2x + 4, l2y + 2, 1.5)
        # LX -> L2 pin 2. The horizontal run is split at x=117 so the
        # BUCK_LX global label sits on a wire ENDPOINT (a floating label
        # would leave the net unnamed and break the schematic<->PCB net
        # cross-check).
        # SW exits RIGHT before dropping. Dropping first ran it straight down
        # the shared right-hand pin column, over the FB pin and along FB's own
        # vertical -- two different nets on one line.
        self.wire(u3x + 8.89, in_y, 117, in_y)
        self.wire(117, in_y, 117, l2y + 3.81)
        self.wire(117, l2y + 3.81, l2x, l2y + 3.81)
        self.glabel("BUCK_LX", 117, l2y + 3.81, 0, "passive")

        # ── Output side ─────────────────────────────────────────
        # C_OUT: datasheet recommends >= 22uF X5R ceramic. C30 is a 22uF
        # 1206 MLCC — deliberately NOT a tantalum: the old AMS1117 output
        # cap C2 (22uF tantalum) destroyed prototype #1 when assembled
        # reversed, and 2.9 ohm ESR is unusable at 1MHz anyway.
        c30x, c30y = 150, 206.27
        self.sym("C", "C30", "22uF", c30x, c30y, ["1", "2"])
        self.text("C_OUT (MLCC)", c30x + 4, c30y - 2, 1.5)
        self.wire(l2x, in_y, c30x, in_y)          # L2 pin 1 -> C30 pin 1
        self.gnd(c30x, 216)
        self.wire(c30x, c30y + 3.81, c30x, 216)
        self.v33(165, 196)
        self.wire(165, 196, 165, in_y)
        self.wire(c30x, in_y, 165, in_y)
        self.glabel("+3V3", 180, in_y, 0, "output")
        self.wire(165, in_y, 180, in_y)
        # PWR_FLAG: +3V3 is produced by the buck THROUGH L2/C30, so no
        # power-output pin sits on the net and ERC reports every +3V3
        # power-input pin as undriven. GND has the same problem (ground
        # symbols are power inputs). One flag per net, here at the source.
        # +5V must NOT get one — IP5306 VOUT is already power_out.
        self.flag(172, 192)
        self.wire(172, 192, 172, in_y)
        self.junction(172, in_y)
        self.flag(158, 212)
        self.wire(158, 212, 158, 216)
        self.wire(158, 216, c30x, 216)

        # ── Feedback divider ────────────────────────────────────
        # Vout = 0.6 * (1 + R25/R26) = 0.6 * (1 + 100k/22k) = 3.327 V
        # C29 (22pF) across R25 is the datasheet feed-forward cap that
        # speeds up the load-transient response.
        # Placed in the free right-hand column (x 195..230) so it does not
        # collide with the Design Notes block (x 30..180, y 240+).
        r25x, fb_y = 205, 215
        c29x = 220
        r26y = 235
        self.sym("R", "R25", "100k", r25x, fb_y, ["1", "2"])
        self.sym("C", "C29", "22pF", c29x, fb_y, ["1", "2"])
        self.sym("R", "R26", "22k", r25x, r26y, ["1", "2"])

        # Top of the divider = +3V3, sensed AFTER C30 (not at the inductor).
        self.v33(r25x, fb_y - 12)
        self.wire(r25x, fb_y - 12, r25x, fb_y - 3.81)
        self.wire(r25x, fb_y - 3.81, c29x, fb_y - 3.81)

        # Tap node: R25 bottom + C29 bottom + R26 top + U3 FB pin.
        self.wire(r25x, fb_y + 3.81, c29x, fb_y + 3.81)
        self.wire(r25x, fb_y + 3.81, r25x, 225)
        self.wire(r25x, 225, r25x, r26y - 3.81)
        # FB pin -> tap node. Split at x=160 so the BUCK_FB global label
        # sits on a wire endpoint.
        # FB drops on its OWN column (u3x+14), not u3x+8.89: the SW node
        # already runs down x=u3x+8.89 from in_y to L2, so the two shared
        # 2.54mm of the same vertical line. KiCad kept them as separate nets
        # (it connects by shared endpoints and junctions, not bare overlap),
        # but two different nets drawn on one line is exactly what a reader
        # misreads as a connection. Guarded by verify_schematic_overlaps.py.
        self.wire(u3x + 8.89, en_y, u3x + 8.89, 225)
        self.wire(u3x + 8.89, 225, 160, 225)
        self.wire(160, 225, r25x, 225)
        self.glabel("BUCK_FB", 160, 225, 0, "passive")

        # Bottom leg to GND
        self.gnd(r25x, r26y + 13)
        self.wire(r25x, r26y + 3.81, r25x, r26y + 13)

        self.text("FEEDBACK DIVIDER", 195, 258, 2.54, True)
        self.text("Vout = 0.6 x (1 + 100k/22k) = 3.327V", 195, 264, 1.8)
        self.text("C29 = datasheet feed-forward cap (load transient)",
                  195, 269, 1.8)

        # ═══════════════════════════════════════════════
        # POWER SWITCH (moved to its own zone on the right column of
        # the A3 sheet — previously at (30, 160) where its long help
        # text overlapped C1 / U3 (AMS1117) / C2 at the same y=160.)
        # ═══════════════════════════════════════════════
        sw_x, sw_y = 285, 200
        self.text("POWER SWITCH", sw_x - 5, sw_y - 12, 2.54, True)
        # Value kept as "SS-12D00G3" to match the CPL/footprint key (legacy
        # name); the actual part is MSK12C02 (LCSC C431540) — noted as text
        # below. Renaming the footprint key across routing/footprints/CPL is
        # a v2 cleanup item.
        self.sym("SW_Push", "SW16", "SS-12D00G3", sw_x, sw_y, ["1", "2"])
        self.text("Actual part: MSK12C02 (LCSC C431540)", sw_x - 5, sw_y + 14, 1.5)
        # v1 AS-BUILT: only the switch COMMON pin (pad 2) is routed — it taps
        # the BAT+ net as a stub. Throw pins 1/3 are unrouted (see
        # hardware/datasheet_specs.py::SW16), so the slide switch does NOT
        # break the battery path: J3 -> Q1 -> BAT+ -> IP5306 pin 6 is
        # continuous copper. Power on/off relies on the IP5306 KEY logic
        # (SW13/MENU via R16) and its automatic light-load standby.
        # v2 respin: route the battery through pins 1-2 in series.
        self.glabel("BAT+", sw_x - 12, sw_y, 180, "input")
        self.wire(sw_x - 5.08, sw_y, sw_x - 12, sw_y)
        # Explicit no-connect on pin 2: the throw side is deliberately
        # unrouted on v1 (see block comment above). The nc marker states
        # that intent to ERC instead of leaving a bare pin.
        self.nc(sw_x + 5.08, sw_y)
        self.text("N.C. (v1: throw pins unrouted)", sw_x + 7, sw_y, 1.5)
        self.text("!! v1 as-built: NOT in series - cannot disconnect battery", sw_x - 5, sw_y + 8, 1.5)
        self.text("Power on/off = IP5306 KEY + auto-standby. v2: wire pins 1-2 in series.", sw_x - 5, sw_y + 11, 1.5)

        # ═══════════════════════════════════════════════
        # CHARGING LEDs (driven by IP5306 LED outputs)
        # Moved to a dedicated zone in the middle-right of the A3
        # sheet so the CHARGING INDICATOR LEDs group does not intrude
        # into the USB ESD row (U4 / R22 / R23 at y=118) nor into the
        # buck regulator row (y=175+).
        # ═══════════════════════════════════════════════
        led_x, led_y = 275, 145
        self.text("CHARGING INDICATOR LEDs", led_x - 30, led_y - 12, 2.54, True)

        # LED1 (Red - charging)
        self.sym("R", "R17", "1k", led_x - 15, led_y, ["1", "2"], angle=180)
        self.sym("LED", "LED1", "Red", led_x, led_y, ["1", "2"])
        self.v33(led_x - 15, led_y - 8)
        self.wire(led_x - 15, led_y - 8, led_x - 15, led_y - 3.81)
        self.wire(led_x - 15, led_y + 3.81, led_x - 3.81, led_y)
        # NAME the R17<->LED1 junction. The wire above already connects them,
        # but KiCad drops unnamed nets from the exported netlist, so the node
        # was invisible to verify_netlist_diff while the board called it
        # LED1_RA. Global, not local: a local label would export as
        # "/Power Supply/LED1_RA" and still not match.
        self.wire(led_x - 3.81, led_y, led_x - 3.81, led_y + 7)
        self.glabel("LED1_RA", led_x - 3.81, led_y + 7, 270)
        self.gnd(led_x + 8, led_y)
        self.wire(led_x + 3.81, led_y, led_x + 8, led_y)
        self.text("Charging", led_x - 32, led_y - 8, 1.5)

        # LED2 (Green - fully charged)
        led2_y = led_y + 18
        self.sym("R", "R18", "1k", led_x - 15, led2_y, ["1", "2"], angle=180)
        self.sym("LED", "LED2", "Red", led_x, led2_y, ["1", "2"])  # C19171391 = YLED0805R, red
        self.v33(led_x - 15, led2_y - 8)
        self.wire(led_x - 15, led2_y - 8, led_x - 15, led2_y - 3.81)
        self.wire(led_x - 15, led2_y + 3.81, led_x - 3.81, led2_y)
        # Same as LED1 — name the R18<->LED2 junction.
        self.wire(led_x - 3.81, led2_y, led_x - 3.81, led2_y + 7)
        self.glabel("LED2_RA", led_x - 3.81, led2_y + 7, 270)
        self.gnd(led_x + 8, led2_y)
        self.wire(led_x + 3.81, led2_y, led_x + 8, led2_y)
        self.text("Full", led_x + 12, led2_y - 6, 1.5)

        # ═══════════════════════════════════════════════
        # DESIGN NOTES — moved further down to sit below the
        # VOLTAGE REGULATOR / POWER SWITCH row on the A3 sheet.
        # ═══════════════════════════════════════════════
        ny = 240
        self.text("Design Notes:", 30, ny, 2.54, True)
        self.text(
            "- IP5306 eSOP-8: integrated charger"
            " + synchronous boost (no ext. Schottky)",
            30, ny + 6,
        )
        self.text(
            "- 1uH inductor: BAT -> L1 -> SW"
            " (>4.5A saturation, shielded)",
            30, ny + 12,
        )
        self.text(
            "- GND via exposed pad only"
            " (must solder to ground plane)",
            30, ny + 18,
        )
        self.text(
            "- KEY pulled to +5V via 100k"
            " for always-on operation",
            30, ny + 24,
        )
        self.text(
            "- SY8089AAAC buck: 3.327V for ESP32-S3"
            " and peripherals (2A cont., 3A peak)",
            30, ny + 30,
        )
        self.text(
            "- C2 (22uF tantalum) DELETED: reversed assembly destroyed"
            " prototype #1; C30 is a non-polarized MLCC",
            30, ny + 36,
        )
        self.text(
            "- 5.1k CC pull-downs identify"
            " USB-C UFP (5V sink)",
            30, ny + 42,
        )
        self.text(
            "- Battery: LiPo 3.7V 5000mAh"
            " via JST PH connector",
            30, ny + 48,
        )
