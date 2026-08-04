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
        self.glabel("USB_D-", u4x - 10.16 - stub, u4y - 2.54, 180)
        self.wire(u4x - 10.16 - stub, u4y - 2.54, u4x - 10.16, u4y - 2.54)
        self.glabel("USB_D+", u4x - 10.16 - stub, u4y,        180)
        self.wire(u4x - 10.16 - stub, u4y,        u4x - 10.16, u4y)
        # Right side stubs — SAME nets as the left side (internal node),
        # they are the pins the D+/D- traces leave the TVS on toward
        # R22/R23. The pre/post split is made by R22/R23, not by U4.
        self.glabel("USB_D-", u4x + 10.16 + stub, u4y + 2.54, 0)
        self.wire(u4x + 10.16, u4y + 2.54, u4x + 10.16 + stub, u4y + 2.54)
        self.glabel("USB_D+", u4x + 10.16 + stub, u4y,        0)
        self.wire(u4x + 10.16, u4y,        u4x + 10.16 + stub, u4y)
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

        # ---- VOUT -> +5V_VOUT rail ----
        # Route VOUT up then right to avoid L1.
        #
        # SW16 RESPIN: this rail is +5V_VOUT, the BOOST OUTPUT, and it stops
        # at Q2's source. The loads keep the name +5V and start at Q2's
        # drain, so every sheet, zone and gate that already speaks about
        # +5V still means the rail the loads see. Same shape as
        # VBUS_IN -> F1 -> VBUS and BAT_IN -> Q1 -> BAT+ elsewhere on this
        # sheet. The switch block itself is drawn in its own zone below.
        #
        # C19 (the 22uF bulk) LEFT this rail with the split: bulk belongs
        # where the inrush is drawn, which is the load side of the switch,
        # and it is drawn next to Q2 now. C27 (10uF HF) stays here, because
        # what it decouples is the boost output itself.
        vout_turn_y = 70

        # C27: HF decoupling (10uF) near VOUT, and now the only tap on the
        # upstream rail.
        c27_x = 227
        c27_y = 78
        self.wire(vout_x, vout_y, vout_x, vout_turn_y)
        # Rail drawn ONCE, end to end. It used to run to x=215 and then be
        # redrawn 205->227 and 215->225, so ~20mm of the rail was two or
        # three wires of ink stacked on each other.
        self.wire(vout_x, vout_turn_y, c27_x, vout_turn_y)
        # Placed at 180 deg: the C_0805 land for C27 on the board has
        # pad 1 on the GND side and pad 2 on the +5V side (routing.py
        # _c27 block: pad 1 -> GND via, pad 2 -> VOUT via), the opposite
        # of C19/C23/C25. Rotating the (vertically symmetric) capacitor
        # symbol keeps the drawing identical while making pin 1 the
        # bottom/GND terminal, so schematic and PCB agree on which pad
        # is which.
        self.sym("C", "C27", "10uF", c27_x, c27_y, ["1", "2"], angle=180)
        # BELOW the cap, not above: above at c27_x-3 collided with the rail
        # label. Underneath is empty (the GND symbol prints no visible text).
        self.text("HF bypass", c27_x - 5, c27_y + 13, 1.5)
        self.wire(c27_x, vout_turn_y, c27_x, c27_y - 3.81)
        self.gnd(c27_x, c27_y + 8)
        self.wire(c27_x, c27_y + 3.81, c27_x, c27_y + 8)

        # The rail's name, on its own east END so no extra wire is needed.
        # There is no +5V power SYMBOL here any more: the symbol would put
        # the load rail's name on the boost output, which is the one thing
        # the split exists to keep apart. It moved to the switch block,
        # onto Q2's drain.
        self.glabel("+5V_VOUT", c27_x, vout_turn_y, 0, "output")

        # NOTE: no PWR_FLAG here. IP5306 VOUT (pin 8) is typed `power_out`
        # in the library symbol, so it already drives this net. Adding a
        # flag would create a second power-output pin on it and cause ERC
        # "Pins of type Power output and Power output are connected". The
        # LOAD rail is a different story — nothing of power-out type sits
        # on +5V now that Q2's passive pins are in the way — so that one
        # does get a flag, in the switch block below.

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

        # ---- IP5306 KEY ----
        # R16 (a 100k pull-up from KEY to +5V) IS DELETED. It was
        # off-datasheet to begin with — the reference schematic has a button
        # to GND and no external pull-up — and on the respin's LOAD-side +5V
        # it would have inverted into a 100k pull-DOWN the moment the switch
        # went OFF, holding KEY asserted. Re-referencing it to +5V_VOUT or
        # BAT+ would only parallel the IP5306's internal pull-up and SHORTEN
        # the wake pulse, which is the one direction this design cannot
        # afford. C33 (in the switch block) drives KEY now, and it took over
        # R16's footprint site and its routing on the board.
        #
        # KEY leaves by label. Points UP, not right: a rightward stub
        # extends the KEY horizontal past x=185, where C18's tap crosses it
        # (see the CBAT comment). GLOBAL, and named IP5306_KEY to match the
        # board's net — a local label is scoped to the sheet, so KiCad
        # exported it as "/Power Supply/KEY" while the PCB called the same
        # node IP5306_KEY.
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
        # Q1 sits in series on the battery rail between J3 and IP5306:
        # J3.1 → BAT_IN → Q1 Drain (pin 3) → Q1 Source (pin 2) → BAT+ → IP5306
        # Gate pulled low via R24 100K → MOSFET always ON for correct polarity.
        #
        # THE CELL IS ON THE DRAIN (R31-HIGH-1) and the direction is the
        # entire circuit. A P-channel body diode conducts D->S: with the
        # cell on the drain a reversed pack reverse-biases it while V_GS is
        # positive, so nothing conducts. Drawn the other way round — cell on
        # the source, which is how sheets, specs and copper all agreed
        # through v4.5.0 — a reversed pack forward-biases that diode and Q1
        # protects nothing. Both wirings behave identically under correct
        # polarity, so no working board could ever have shown the
        # difference.
        q1x, q1y = 210, 92
        self.sym("BAT54C", "Q1", "SI2301CDS", q1x, q1y, ["1", "2", "3"])
        # NOTE: reusing BAT54C symbol footprint (SOT-23-3) for Q1 P-MOSFET
        # Pin mapping: 1=Gate(bottom-left)=RPP_GATE,
        #              2=Source(bottom-right)=BAT+, 3=Drain(top)=BAT_IN
        # Two-line annotation ABOVE the symbol with 3mm vertical spacing
        # so the lines don't touch each other or the symbol's Value text.
        self.text("P-MOSFET RPP", q1x + 8, q1y - 26, 1.5)
        self.text("(SI2301CDS)",  q1x - 6, q1y - 12, 1.5)

        # The BAT+ rail (L1.1, C18.1, U2.6, SW16.1) now ENDS at its own
        # global label instead of running into Q1's top pin: after
        # R31-HIGH-1 the top pin is the drain and belongs to BAT_IN, and a
        # rail arriving 0.62 mm above a pin of a different net is exactly
        # the kind of near-miss this sheet has been bitten by before. The
        # three Q1 pins are joined to their nets by global labels, which is
        # already this sheet's idiom for BAT+, BAT_IN, VBUS and RPP_GATE.
        #
        # Starts at l1_x, not cbat_x: cbat_x (185) is left of l1_x (190), so
        # this span used to re-draw 5mm of the bat_x->l1_x rail above it.
        self.wire(l1_x, bat_y, q1x - 10, bat_y)
        # C18 taps the rail mid-span now, so it needs a dot.
        self.junction(cbat_x, bat_y)
        # Label sits on the rail's east END. At (q1x + 2, bat_y - 2) it was
        # 2 mm off the horizontal and 2 mm off the vertical, i.e. on neither
        # — so BAT+ came out of the netlist with one node (SW16.1, from
        # its own global label) while L1.1, C18.1, Q1 and U2.6 were
        # absent. The battery rail was undrawn as far as any gate could see.
        # Global label (see VBUS note); angle=180 extends LEFT — rightward
        # the text lands on Q1's body.
        self.glabel("BAT+", q1x - 10, bat_y, 180)

        # Q1 pin 3 (Drain, top) — the CELL side, net BAT_IN.
        # Up out of the pin, then east into clear space; the label goes at
        # the far end so it does not land on the "(SI2301CDS)" annotation
        # below-left or on C27's "HF bypass" at (222, 91).
        self.wire(q1x, q1y - 5.08, q1x, q1y - 8)
        self.wire(q1x, q1y - 8, q1x + 16, q1y - 8)
        self.glabel("BAT_IN", q1x + 16, q1y - 8, 0)

        # Q1 pin 2 (Source, bottom-right) — the PROTECTED side, net BAT+.
        # Exits DOWNWARD. It used to run up to jst_plus_y and east to J3,
        # back when this pin was the cell side; that route is gone with the
        # net. Note for anyone re-drawing it: a horizontal at q1y + 1.27 ==
        # 93.27 is exactly jst_minus_y, so it lands on J3 pin 2 (GND) and
        # welds J3.1, J3.2 and this pin into one node — a battery connector
        # with + and - shorted (verify_netlist_diff T4 caught that once).
        self.wire(q1x + 5.08, q1y + 1.27, q1x + 5.08, q1y + 10)
        self.glabel("BAT+", q1x + 5.08, q1y + 10, 270)

        # J3.1 → BAT_IN. Label must sit ON the segment it names: at
        # q1y - 0.5 it once floated 1.77 mm off every wire and renamed
        # nothing, and the correction that replaced it, jst_plus_y - 1.5,
        # was still 1.5 mm off the same horizontal. BAT_IN kept coming out
        # of the netlist with one node (BT1.1) while J3.1 stayed missing.
        # Anchored at the wire's west END with angle=180 so the text
        # extends away from the copper it names — same shape as BT1's.
        self.wire(jst_plus_x - 20, jst_plus_y, jst_plus_x, jst_plus_y)
        self.glabel("BAT_IN", jst_plus_x - 20, jst_plus_y, 180)

        # Q1 pin 1 (Gate) — pulled to GND via R24 (100K)
        r24x, r24y = q1x - 8, q1y + 10
        self.sym("R", "R24", "100k", r24x, r24y, ["1", "2"])
        # Short label placed BELOW R24 (past its GND arrow) so it does
        # not run into Q1's symbol/value or the C18 annotation.
        self.text("Q1 gate PD", r24x - 5, r24y + 14, 1.5)
        # Wire Q1 gate to R24 pin 1
        self.wire(q1x - 5.08, q1y + 1.27, r24x, q1y + 1.27)
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
        # POWER SWITCH — SW16 gating the +5V loads through Q2
        #
        # SW16 was electrically inert on every board built to date: only
        # its common pin was routed, as a dead stub on BAT+, and its throws
        # carried no net, so sliding it changed no copper at all.
        #
        # Putting the CELL in series with it — the obvious fix — fails the
        # requirement twice: OFF would break charging as well as the loads,
        # and with USB plugged in the VBUS passthrough keeps the board
        # running anyway. So the +5V rail is switched instead, which gives
        # all three states that are actually wanted: ON = powered,
        # OFF = loads dead but USB still charges, no cell fitted =
        # identical behaviour on USB.
        #
        # Q2 (SI2301CDS, C10487 — the SAME part as Q1, so no new BOM line
        # and no new package family) breaks the rail between the boost
        # output and every load. SW16 does not carry rail current at all
        # now; it carries the GATE, which is why a slide switch rated for
        # signal levels is the right part for it.
        #
        #   ON  : the common is grounded, the gate divides R32/R33 to
        #         0.217 V, V_gs = -4.78 V, and Q2 is driven past its
        #         characterised -4.5 V spec point.
        #   OFF : the throw is open and R34 alone defines the node, so
        #         V_gs collapses to -0.028 V on a 3.7 V cell and -0.108 V
        #         with no cell fitted at all. See datasheet_specs.py for
        #         why R32 is 22k and not the obvious 100k: at 100k/10k/1M
        #         the no-cell case lands on -0.455 V, which IS the SI2301
        #         threshold minimum, in the USB-powered no-battery state a
        #         bench operator uses most.
        # ═══════════════════════════════════════════════
        sw_x, sw_y = 256, 232
        # The title sits at y<=188. Below that the two "+5V_VOUT" gate-return
        # labels rise off R32/C32 to y=191, and a 50-character subtitle at
        # 1.8 mm is 61 mm long — it reaches x=307 and runs straight through
        # both of them (verify_schematic_overlaps).
        self.text("POWER SWITCH", 246, 178, 2.54, True)
        self.text("SW16 -> Q2 high-side switch on the +5V load rail",
                  246, 184, 1.8)
        self.text("IP5306 keeps charging with the console switched off",
                  246, 188, 1.8)

        # ── SW16 ────────────────────────────────────────
        # Value kept as "SS-12D00G3" to match the CPL/footprint key (legacy
        # name); the actual part is MSK12C02 (LCSC C431540).
        #
        # Drawn at 180 deg so pin 1 — which is the board's pad 2, the
        # COMMON — lands on the RIGHT, facing the gate network it drives.
        # Unrotated the common exits west and the whole block reads
        # backwards. The switch body is symmetric, so the drawing is
        # unchanged.
        self.sym("SW_Push", "SW16", "SS-12D00G3", sw_x, sw_y, ["1", "2"], 180)
        self.text("MSK12C02 (C431540)", sw_x - 9, sw_y + 9, 1.5)
        # Pin 2 == board pad 1, the ON throw: it grounds the common.
        self.wire(sw_x - 5.08, sw_y, sw_x - 10, sw_y)
        self.gnd(sw_x - 10, sw_y)
        # The board's pad 3 (the other throw) is deliberately left OPEN and
        # so has no pin here — the 2-pin symbol is the whole switch as far
        # as this circuit is concerned. With the slider on that side the
        # node is defined by R34 alone, which is exactly the OFF state.

        # ── PWR_SW: the switch node ─────────────────────
        pwr_sw_y = sw_y
        gate_y = 215
        self.wire(sw_x + 5.08, pwr_sw_y, 267, pwr_sw_y)
        self.wire(267, pwr_sw_y, 288, pwr_sw_y)
        self.junction(267, pwr_sw_y)
        # Name it. Both ends of the spine are taken (SW16's pin and C33's
        # corner), so the label goes on a stub of its own, pointing UP into
        # the empty band between the two spines. An unnamed node here is
        # not cosmetic: KiCad exports it as "Net-(C33-Pad1)" and every
        # schematic-vs-PCB pin comparison on SW16, R33, R34 and C33 fails
        # against the board's PWR_SW.
        self.wire(283, pwr_sw_y, 283, 227)
        self.junction(283, pwr_sw_y)
        self.glabel("PWR_SW", 283, 227, 90)

        # R34 1M — holds PWR_SW at BAT+ while the throw is open, which is
        # what defines the OFF state, and it also keeps C33 charged ready
        # for the next wake pulse. It sits on the COMMON node rather than
        # on the open throw: with the throw open the common is the only
        # node it could reach either way, so the two positions are
        # electrically identical, and this one keeps the switch to ONE net
        # across the board instead of two. It costs 0.8 uA while ON.
        self.sym("R", "R34", "1M", 277, 240, ["1", "2"])
        self.wire(277, 236.19, 277, pwr_sw_y)
        self.junction(277, pwr_sw_y)
        self.wire(277, 243.81, 277, 248)
        self.glabel("BAT+", 277, 248, 270)

        # C33 4.7uF — the wake cap, and it is not optional. The IP5306 boost
        # shuts down after 32 s below 45 mA and restarts only on a KEY
        # press or a USB insertion (R30-MED-3); with the loads gated off
        # the draw is ~0.1 mA, so it WILL latch off every single time.
        # Flipping back to ON therefore has to generate a KEY press by
        # itself. KEY is active-low with an internal pull-up and the chip
        # stays alive from the cell while the boost is off, so a capacitor
        # is enough: C33 couples the PWR_SW 5V->0 step in as a low pulse
        # and recharges through R34 afterwards.
        #
        # BENCH-VALIDATE: the pulse width is tau against the IP5306's
        # UNDOCUMENTED internal pull-up. The chip accepts a press of
        # 50 ms..2 s (shorter is ignored, longer is a "long press" that
        # does NOT start the boost), and the press the cap synthesizes
        # lasts ~0.7*tau. That window makes 4.7uF the right size: it is
        # safe for an internal pull-up anywhere in ~15k..600k, where the
        # original 1uF needed >= ~70k to register at all. Community
        # practice (GPIO through 1-1.2k held low ~100 ms) confirms the
        # press model. Fallback if the value still misses: SW17, the DNP
        # momentary right next to C33, reaches KEY/GND directly.
        self.sym("C", "C33", "4.7uF", 288, 240, ["1", "2"])
        self.wire(288, 236.19, 288, pwr_sw_y)
        self.wire(288, 243.81, 288, 248)
        self.glabel("IP5306_KEY", 288, 248, 270)
        self.text("wake pulse", 293, 244, 1.5)
        self.text("BENCH-VALIDATE", 291, 247, 1.5)

        # ── SW17: the manual KEY wake button (DNP) ──────
        # Insurance for the C33 RC above. If the coupled pulse turns out
        # too short against the IP5306's undocumented internal KEY
        # pull-up, this is the datasheet's own wake topology (p.11 fig.4):
        # a momentary to GND on an active-low input. The land and its
        # copper are on the board; the part is marked DO NOT PLACE in the
        # BOM and is absent from the CPL, which is the file that decides
        # what JLCPCB populates.
        #
        # It is a 2-terminal TS-1088 (C720477) and not the 5.1x5.1 tact
        # the twelve user buttons use, because a 7.0 x 4.4 tact footprint
        # has no clearance-legal site anywhere in the IP5306 quadrant —
        # see routing/_shared.py::SW17_POS for the measurement.
        self.sym("SW_Push", "SW17", "TS-1088", 310, 240, ["1", "2"], 180)
        # Annotation BELOW the switch: above it runs into Q2's own
        # "(SI2301CDS, same as Q1)" line, and the row immediately under
        # the symbol is its Reference field.
        # South-west of the symbol. Straight below it runs into the
        # sheet's title block (x>=297, y>=255), which the overlap gate
        # does not model — so it looked clean and printed over the title;
        # and at y=252 it landed on the BAT+ / IP5306_KEY labels hanging
        # down off R34 and C33. y=260 is below both and west of the block.
        self.text("manual KEY wake (DO NOT PLACE)", 258, 260, 1.5)
        self.text("fit only if the C33 pulse is short", 258, 263, 1.5)
        # Pin 1 (right after the 180 deg rotation) is the KEY side, which
        # is the side C33 is on.
        self.wire(310 + 5.08, 240, 320, 240)
        self.glabel("IP5306_KEY", 320, 240, 0)
        self.wire(310 - 5.08, 240, 300, 240)
        self.gnd(300, 240)

        # R33 1k — series gate resistor, between the switch node and the
        # gate. It is what splits PWR_SW from PWR_SW_GATE, the same way R24
        # splits RPP_GATE off Q1's gate.
        self.sym("R", "R33", "1k", 267, 222, ["1", "2"])
        self.wire(267, 225.81, 267, pwr_sw_y)
        self.wire(267, 218.19, 267, gate_y)
        self.junction(267, gate_y)

        # ── PWR_SW_GATE: Q2's gate node ─────────────────
        self.wire(262, gate_y, 287.92, gate_y)
        self.glabel("PWR_SW_GATE", 262, gate_y, 180)

        # R32 22k pull-up and C32 1uF gate-source, BOTH returning to the
        # SOURCE (+5V_VOUT) and not to the load rail. Referenced to +5V
        # they would follow the drain down as Q2 turned off and never reach
        # V_gs = 0, so the switch could not hold itself off — that is the
        # one wiring mistake in this block that would look right and behave
        # wrongly, and verify_polarity holds both to it.
        #
        # C32 is 1uF, not 100nF, because the gate network shrank when R32
        # became 22k: tau_on = (R32||R33) x C32 = 957 ohm x 1uF = 957 us,
        # so the rail ramps over ~1.5 ms and the inrush into the ~50 uF of
        # load-side bulk is ~167 mA instead of amps. At 100nF the same
        # 957 ohm gives 96 us and puts 1.7 A through Q2. The TIME CONSTANT
        # is the specification here, not the capacitor value.
        #
        # Both at 180 deg: hung upward from the gate node, the default
        # orientation would put pin 1 on the +5V_VOUT end, and the board
        # has pad 1 on the gate. Rotating the (vertically symmetric)
        # symbols keeps the drawing identical while making pin 1 the
        # bottom terminal — the same trick C27 uses above.
        self.sym("C", "C32", "1uF", 272, 206, ["1", "2"], angle=180)
        self.wire(272, 209.81, 272, gate_y)
        self.junction(272, gate_y)
        self.wire(272, 202.19, 272, 198)
        self.glabel("+5V_VOUT", 272, 198, 90)

        self.sym("R", "R32", "22k", 282, 206, ["1", "2"], angle=180)
        self.wire(282, 209.81, 282, gate_y)
        self.junction(282, gate_y)
        self.wire(282, 202.19, 282, 198)
        self.glabel("+5V_VOUT", 282, 198, 90)

        # ── Q2 ──────────────────────────────────────────
        # Reusing the BAT54C symbol footprint (SOT-23-3), exactly as Q1
        # does. Pin mapping: 1 = Gate (bottom-left), 2 = Source
        # (bottom-right), 3 = Drain (top).
        #
        # The SOURCE is the boost side and the DRAIN is the load side, and
        # for a P-channel that direction is the whole part. The body diode
        # conducts D->S, so pointing it loads->boost means it BLOCKS in the
        # OFF state; wired the other way round the loads would stay powered
        # through the diode whatever the gate did.
        q2x, q2y = 293, 213.73
        self.sym("BAT54C", "Q2", "SI2301CDS", q2x, q2y, ["1", "2", "3"])
        # Annotation pushed east of the source stub: at q2x+6 it sat on the
        # "+5V_VOUT" label hanging off pin 2.
        self.text("P-MOSFET load switch", q2x + 12, q2y + 14, 1.5)
        self.text("(SI2301CDS, same as Q1)", q2x + 12, q2y + 17, 1.5)

        # Pin 2 (Source, bottom-right) -> +5V_VOUT. Exits DOWNWARD: run
        # east and it draws as one straight line through the transistor,
        # collinear with the gate node on the other side.
        self.wire(q2x + 5.08, q2y + 1.27, q2x + 5.08, 222)
        self.glabel("+5V_VOUT", q2x + 5.08, 222, 270)

        # Pin 3 (Drain, top) -> the +5V LOAD rail.
        self.wire(q2x, q2y - 5.08, q2x, 204)
        self.wire(q2x, 204, 315, 204)
        self.glabel("+5V", 315, 204, 0, "output")

        # PWR_FLAG on +5V. The load rail is produced THROUGH Q2, whose
        # symbol pins are passive, so no power-output pin sits on it and
        # ERC reports every +5V power-input pin as undriven — the same
        # situation as VBUS behind F1 and +3V3 behind L2. One flag per net,
        # here at its source. +5V_VOUT must NOT get one: IP5306 VOUT is
        # already power_out.
        self.flag(300, 198)
        self.wire(300, 198, 300, 204)
        self.junction(300, 204)

        # C19 22uF — the load-rail bulk. It used to hang off the VOUT rail
        # next to C27; it belongs on THIS side of the switch, because the
        # inrush it has to supply is drawn by the loads when Q2 turns on.
        self.sym("C", "C19", "22uF", 309, 212, ["1", "2"])
        self.wire(309, 208.19, 309, 204)
        self.junction(309, 204)
        self.gnd(309, 220)
        self.wire(309, 215.81, 309, 220)

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
        # DIAGNOSTIC RAIL LEDs (workstream H)
        # LED3/VBUS, LED4/+5V, LED5/+3V3 — passive "is this rail up?"
        # indicators, DNP in production. LED6 (the GPIO15 heartbeat) lives
        # on the MCU sheet, next to the pin that drives it.
        # Same topology as LED1/LED2 above: rail -> R -> LEDn_RA -> anode,
        # cathode -> GND.
        # ═══════════════════════════════════════════════
        # Own zone in the empty right-hand third of the A3 sheet. The
        # first attempt sat at x=led_x, y=led2_y+26 and landed straight
        # on the POWER SWITCH block at (284, 199).
        dg_x = 345
        dg_y0 = 120
        self.text("DIAGNOSTIC RAIL LEDs (DNP in production)",
                  dg_x - 30, dg_y0 - 16, 2.54, True)
        # Unrolled on purpose: verify_schematic_pcb_sync parses these sheet
        # sources STATICALLY for self.sym("<lib>", "<REF>", ...). A loop with
        # f-strings hides every ref from it, and the gate then reports the
        # parts as "BOM refs with no schematic symbol".
        def _diag_led(ledref, rail, y):
            if rail == "+3V3":
                self.v33(dg_x - 15, y - 8)
            elif rail == "+5V":
                self.v5(dg_x - 15, y - 8)
            else:
                # VBUS has no power-symbol helper; name it like every other
                # VBUS tap on this sheet.
                self.glabel(rail, dg_x - 15, y - 8, 90)
            self.wire(dg_x - 15, y - 8, dg_x - 15, y - 3.81)
            self.wire(dg_x - 15, y + 3.81, dg_x - 3.81, y)
            # Name the R<->LED junction, same reason as LED1_RA/LED2_RA.
            self.wire(dg_x - 3.81, y, dg_x - 3.81, y + 7)
            self.glabel(ledref + "_RA", dg_x - 3.81, y + 7, 270)
            self.gnd(dg_x + 8, y)
            self.wire(dg_x + 3.81, y, dg_x + 8, y)
            self.text(rail, dg_x + 12, y - 6, 1.5)

        self.sym("R", "R28", "5.1k", dg_x - 15, dg_y0, ["1", "2"], angle=180)
        self.sym("LED", "LED3", "Red", dg_x, dg_y0, ["1", "2"])
        _diag_led("LED3", "VBUS", dg_y0)
        self.sym("R", "R29", "5.1k", dg_x - 15, dg_y0 + 18, ["1", "2"], angle=180)
        self.sym("LED", "LED4", "Red", dg_x, dg_y0 + 18, ["1", "2"])
        _diag_led("LED4", "+5V", dg_y0 + 18)
        self.sym("R", "R30", "1k", dg_x - 15, dg_y0 + 36, ["1", "2"], angle=180)
        self.sym("LED", "LED5", "Red", dg_x, dg_y0 + 36, ["1", "2"])
        _diag_led("LED5", "+3V3", dg_y0 + 36)

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
            "- KEY driven by C33 wake pulse (R16 100k pull-up DELETED)",
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
