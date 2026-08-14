"""Sheet 4: Audio - I2S DAC -> PAM8403 -> Speaker."""

from ..sheet_base import SchematicSheet


class AudioSheet(SchematicSheet):
    title = "Audio - I2S -> PAM8403 -> Speaker + Headphone Jack"
    page_number = 4
    needed_symbols = ["PAM8403_Module", "Speaker", "C", "R",
                      "AudioJack_PJ327A", "NMOS_SOT23"]

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

        # GND — global label, NOT a power-symbol drop.
        # Same defect as sheet 5: a vertical GND stub from (ax-30, ay)
        # down to (ax-30, ay+8) passes through (ax-30, ay+3.81), the
        # anchor of the I2S_DOUT label / U5 input row, and shorted the
        # amplifier input to ground.
        self.glabel("GND", ax - 30, ay, 0, "input")
        self.wire(ax - 30, ay, ax - 10.16, ay)

        # Audio input — PAM8403 side of the C22 series DC-block.
        # NOT I2S_DOUT: C22 separates the ESP32 PDM output (I2S_DOUT, on
        # C22.1) from the amplifier input node (PAM_IN_AC, on C22.2 and
        # U5.7/U5.10). Labelling both sides "I2S_DOUT" made DRC report a
        # permanent phantom "unconnected" on I2S_DOUT.
        self.glabel("PAM_IN_AC", ax - 30, ay + 3.81, 0, "input")
        self.wire(ax - 30, ay + 3.81, ax - 10.16, ay + 3.81)

        # I2S bus reference (informational labels).
        # R10-LOW-2: GPIO15/16 are reserved in GPIO_NETS as I2S_BCLK/
        # I2S_LRCK for historical reasons, but firmware uses PDM TX
        # mode (see software/main/audio.c). PDM only needs the DOUT
        # pin — BCLK/LRCK are NOT externally connected on the PCB.
        # The two glabels below are informational only (dead nets,
        # 1 pad / 0 segments in the PCB cache). Candidates for reuse
        # as ADC2 channels (battery voltage) in v2.
        # I2S informational block — moved higher (y=45-65) so its
        # rightmost text ("PDM sigma-delta out ...") no longer runs
        # into the PAM8403 VDD/PVDD decoupling caps (C23-C25 at y=90).
        #
        # These three net names are CAPTIONS, so they are drawn with text()
        # and not with glabel(). A global label is a connectivity
        # instrument: used as a caption it declares a net that connects
        # nothing, which is how a name comes to exist in the schematic
        # netlist with no pin behind it. All three sat
        # attached to no wire — scripts/verify_schematic_label_attach.py
        # reports exactly that, and it is the same instrument-misuse that
        # left LCD_BL and LCD_RD in the PCB net table with zero pads.
        # I2S_DOUT is a real net; it is named where it is wired, at C22.
        self.text("I2S Bus (PDM TX mode — DOUT only):", 30, 45, 2.54, True)
        self.text("I2S_BCLK", 30, 55)
        self.text("GPIO15 - Bit Clock (UNUSED — PDM mode, v2 free)", 65, 55)
        self.text("I2S_LRCK", 30, 62)
        self.text("GPIO16 - L/R Word Select (UNUSED — PDM mode, v2 free)", 65, 62)
        self.text("I2S_DOUT", 30, 69)
        self.text("GPIO17 - PDM sigma-delta out @ 32kHz -> C22 -> PAM_IN_AC", 65, 69)

        # Speaker (moved further right for orthogonal routing)
        spk_x, spk_y = ax + 65, ay
        self.sym("Speaker", "SPK1", "28mm 8ohm", spk_x, spk_y, ["1", "2"])
        self.text("28mm speaker", spk_x + 8, spk_y - 5)
        self.text("8 ohm / 0.5W", spk_x + 8, spk_y + 1)

        # SPK+ / SPK- carry the same net names the PCB uses, so the
        # speaker terminals are no longer PCB-only nets needing a T2
        # allowlist entry in verify_netlist_diff.py.
        self.glabel("SPK+", ax + 16, ay - 3.81, 0, "output")
        self.glabel("SPK-", ax + 40, ay, 0, "output")

        # SPK+ wire (orthogonal L-shape)
        spk_plus_y = ay - 3.81
        self.wire(ax + 10.16, spk_plus_y, spk_x - 3.81, spk_plus_y)
        self.wire(spk_x - 3.81, spk_plus_y, spk_x - 3.81, spk_y - 1.27)
        # SPK- wire (orthogonal L-shape)
        spk_minus_y = ay
        self.wire(ax + 10.16, spk_minus_y, spk_x - 10.16, spk_minus_y)
        self.wire(spk_x - 10.16, spk_minus_y, spk_x - 10.16, spk_y + 1.27)
        self.wire(spk_x - 10.16, spk_y + 1.27, spk_x - 3.81, spk_y + 1.27)

        # --- PAM8403 passive components (per datasheet application circuit) ---
        self.text("PAM8403 Passives:", 30, 122, 2.54, True)

        # VREF bypass capacitor (C21, 100nF) — PAM8403 pin 8 (VREF) to GND.
        # VREF is the internal half-supply bias rail. R20/R21 (below) tie
        # the AC-coupled inputs to this node, NOT to GND — see R4-HIGH-3.
        # A VREF glabel is emitted so the bias resistor wiring can
        # reference it without running a long visible net through the
        # schematic page.
        # The node is named PAM_VREF — the same name routing.py uses on
        # the board. It used to be called VREF here only, which forced
        # both a T1 ("VREF missing from PCB") and a T2 ("PAM_VREF has no
        # schematic counterpart") allowlist entry in
        # verify_netlist_diff.py for what is one and the same node.
        # C21 is placed at 180 deg so pin 1 is the GND terminal and pin 2
        # the PAM_VREF terminal, matching the C_0805 pads on the board
        # (routing.py: C21 pad 1 -> GND, pad 2 -> PAM_VREF).
        c21x, c21y = ax + 30, ay + 25
        self.sym("C", "C21", "100nF", c21x, c21y, ["1", "2"], angle=180)
        self.wire(c21x, c21y - 3.81, c21x, c21y - 10)
        self.wire(c21x, c21y - 10, ax + 10.16, c21y - 10)
        self.gnd(c21x, c21y + 8)
        self.wire(c21x, c21y + 3.81, c21x, c21y + 8)
        # Emit the PAM_VREF label at the far (left) end of C21's top
        # stub so the label text runs into open sheet instead of over
        # the capacitor's own reference designator.
        self.glabel("PAM_VREF", ax + 10.16, c21y - 10, 180, "output")
        self.text("VREF bypass (pin 8)", c21x + 9.5, c21y)

        # DC-blocking capacitor (C22, 0.47uF) — input coupling.
        # Series DC-block. C22.1 = I2S_DOUT (ESP32 PDM TX side),
        # C22.2 = PAM_IN_AC (amplifier side) — two electrically distinct
        # nets separated by the dielectric.
        #
        # BUG FIX: the "C" library symbol has its pins VERTICALLY at
        # (0, +/-3.81), but this block wired horizontal stubs at
        # (c22x +/- 3.81, c22y). Neither stub touched a pin, so C22 was
        # floating in the exported netlist — the schematic showed the PDM
        # output reaching the amplifier with no coupling capacitor at all.
        # Placing the symbol at 90 deg puts the pins where the horizontal
        # wiring already is, and matches the board (routing.py also places
        # C22 at 90 deg).
        # Moved to its own row (was on the amplifier input row at
        # y=ay+3.81, where the rotated symbol's value text ran through R20).
        c22x, c22y = ax - 50, ay - 10
        self.sym("C", "C22", "0.47uF", c22x, c22y, ["1", "2"], angle=90)
        self.wire(c22x - 3.81, c22y, c22x - 12, c22y)
        self.glabel("I2S_DOUT", c22x - 12, c22y, 180, "input")
        self.wire(c22x + 3.81, c22y, c22x + 12, c22y)
        self.glabel("PAM_IN_AC", c22x + 12, c22y, 0, "output")
        # Anchored further left so the run ends before C23's plates.
        self.text("DC-block (in series, I2S_DOUT -> PAM_IN_AC)",
                  c22x - 26, c22y - 8.5, 1.5)

        # INL bias resistor (R20, 20k) — biases INL node to VREF (pin 8),
        # NOT to GND. R4-HIGH-3: PAM8403 single-ended app circuit per
        # datasheet Fig. 3 requires the bias network to reference VREF so
        # the input DC operating point sits at mid-supply. Tying to GND
        # fights the internal bias and produces asymmetric clipping.
        # Spread R20/R21 further apart (15mm gap instead of 10mm) and
        # move the descriptive text BELOW the VREF glabels so nothing
        # collides with the PAM8403 module or with each other.
        # BUG FIX: the top stub used to run from the pin up to
        # (r20x, c22y), which is the *centre* of the C22 symbol — a point
        # with no wire and no pin on it. R20/R21 therefore had a floating
        # top terminal. They now reach the amplifier input node through
        # an explicit I2S_DOUT label stub going left.
        r20x, r20y = ax - 50, ay + 24
        # angle=180: draws identically (the R symbol is vertically symmetric)
        # but puts pin 1 on the BOTTOM, matching the footprint — the board's
        # pad 1 (x=38.95) is the VREF side. Without this the nets agree while
        # the pin NUMBERS stay swapped, and verify_netlist_diff still fails.
        self.sym("R", "R20", "20k", r20x, r20y, ["1", "2"], angle=180)
        # Top terminal joins the amplifier-side node by name. The old wire ran
        # from here straight up to (r20x, c22y) — a point inside the C22 symbol
        # body touching neither pin, so the bias network was dangling in the
        # schematic while the PCB routed it.
        # Stub 8mm (not 6) and label HORIZONTAL (angle 0, reading right).
        # A vertical label extends ~7.3mm along the stub axis, so the two
        # resistors' labels grew toward each other and collided; 6mm also put
        # the label on top of the symbol's Value field at y+5. Horizontal
        # labels extend sideways into empty space instead.
        # Guarded by verify_schematic_overlaps.py.
        self.wire(r20x, r20y - 3.81, r20x, r20y - 8)
        self.glabel("PAM_IN_AC", r20x, r20y - 8, 0, "input")
        # Bottom terminal goes to PAM_VREF (net 50) via a named label stub.
        self.wire(r20x, r20y + 3.81, r20x, r20y + 8)
        self.glabel("PAM_VREF", r20x, r20y + 8, 0, "input")
        # Down-left of the resistor, below R21's PAM_IN_AC label line —
        # every same-row anchor printed through one glabel or another.
        self.text("INL bias -> PAM_VREF", r20x - 30, r20y + 15.5, 1.5)

        # INR bias resistor (R21, 20k) — biases INR node to VREF (pin 8).
        # Same rationale as R20 — see R4-HIGH-3.
        # 20mm below R20 (was 16): at 16 the two resistors' label stubs and
        # Value fields ran into each other. See verify_schematic_overlaps.py.
        r21x, r21y = ax - 50, ay + 44
        # angle=180 for the same reason as R20 — pad 1 is the VREF side.
        self.sym("R", "R21", "20k", r21x, r21y, ["1", "2"], angle=180)
        # Top terminal joins the amplifier-side node by name. The old wire ran
        # from here straight up to (r21x, c22y) — a point inside the C22 symbol
        # body touching neither pin, so the bias network was dangling in the
        # schematic while the PCB routed it.
        # Horizontal labels on 8mm stubs — same reason as R20.
        self.wire(r21x, r21y - 3.81, r21x, r21y - 8)
        self.glabel("PAM_IN_AC", r21x, r21y - 8, 0, "input")
        # Bottom terminal goes to PAM_VREF (net 50) via a named label stub.
        self.wire(r21x, r21y + 3.81, r21x, r21y + 8)
        self.glabel("PAM_VREF", r21x, r21y + 8, 0, "input")
        # Same offset as R20's note, same reason.
        self.text("INR bias -> PAM_VREF", r21x - 30, r21y + 15.5, 1.5)
        self.text("R20/R21 bias the amplifier inputs to PAM_VREF (R4-HIGH-3).",
                  r21x - 12, r21y + 18, 1.5)

        # VDD decoupling (C23, 1uF) — VDD pin to GND. Labels placed
        # BELOW each cap so they don't extend rightward into the next
        # cap's label or into the I2S info block (moved up to y=45-69).
        c23x, c23y = ax - 20, ay - 20
        self.sym("C", "C23", "1uF", c23x, c23y, ["1", "2"])
        self.glabel("+5V", c23x, c23y - 8, 0, "input")
        self.wire(c23x, c23y - 3.81, c23x, c23y - 8)
        self.gnd(c23x, c23y + 8)
        self.wire(c23x, c23y + 3.81, c23x, c23y + 8)
        self.text("VDD", c23x - 3, c23y + 14, 1.5)

        # PVDD top bypass (C24, 1uF) — power output stage
        c24x, c24y = ax, ay - 20
        # 180 deg: on the board C24's pad 1 is the GND terminal and pad 2
        # the PVDD/+5V terminal (routing.py: PVDD pin 4 -> C24 pad 2,
        # C24 pad 1 -> GND via), the opposite of C23/C25. Rotating the
        # symmetric capacitor symbol aligns the pin numbers with the pads
        # without changing how the sheet looks.
        self.sym("C", "C24", "1uF", c24x, c24y, ["1", "2"], angle=180)
        self.glabel("+5V", c24x, c24y - 8, 0, "input")
        self.wire(c24x, c24y - 3.81, c24x, c24y - 8)
        self.gnd(c24x, c24y + 8)
        self.wire(c24x, c24y + 3.81, c24x, c24y + 8)
        # ABOVE this cap, unlike its two neighbours: C24 sits directly over
        # U5, so anything placed below it lands inside the amplifier body.
        self.text("PVDD-top", c24x + 4, c24y - 9, 1.5)

        # PVDD bottom bypass (C25, 1uF) — power output stage
        c25x, c25y = ax + 20, ay - 20
        self.sym("C", "C25", "1uF", c25x, c25y, ["1", "2"])
        self.glabel("+5V", c25x, c25y - 8, 0, "input")
        self.wire(c25x, c25y - 3.81, c25x, c25y - 8)
        self.gnd(c25x, c25y + 8)
        self.wire(c25x, c25y + 3.81, c25x, c25y + 8)
        self.text("PVDD-bot", c25x - 5, c25y + 14, 1.5)

        # ── Headphone jack (J5) + speaker auto-mute ─────────────────
        # Passive line-out: the PDM output is tapped UPSTREAM of the
        # PAM8403 (its filterless BTL outputs must never reach a
        # ground-referenced jack — SPK- is not ground). R35/R36 divide
        # the 3.3Vpp PDM stream to headphone level, C34 low-passes the
        # PDM carrier (~30 kHz corner), C35 AC-couples, R39 bleeds the
        # DC so tip/ring idle at 0 V, R37/R38 fan the mono signal to
        # both plug channels.
        self.text("HEADPHONE OUT + AUTO-MUTE", 200, 46, 3.0, True)
        self.text("Passive line-out from PDM (pre-amplifier tap)",
                  200, 52, 1.5)

        hp_y = 62
        # NOTE on label placement: kicad-cli renders a glabel's text as a
        # HORIZONTAL run centred on the anchor regardless of the stored
        # angle, so every label on this row is positioned so its
        # half-width clears the neighbouring pin-number digits
        # (verify_schematic_render_overlaps measures the real SVG).
        self.glabel("I2S_DOUT", 199, hp_y, 90, "input")
        self.wire(199, hp_y, 204.19, hp_y)
        # angle=90: pin 1 west (upstream), pin 2 east — the same
        # convention every horizontal part in this section uses, and the
        # PCB routes each pad to the matching net.
        self.sym("R", "R35", "150R", 208, hp_y, ["1", "2"], angle=90)
        # HP_FILT: R35.2 -> C35.1, with R36 attenuator + C34 PDM filter
        # hanging off the run.
        self.wire(211.81, hp_y, 228.19, hp_y)
        self.glabel("HP_FILT", 221, hp_y, 90, "output")
        self.sym("R", "R36", "470R", 218, 74, ["1", "2"])
        self.wire(218, hp_y, 218, 70.19)
        self.junction(218, hp_y)
        self.gnd(218, 82)
        self.wire(218, 77.81, 218, 82)
        self.sym("C", "C34", "47nF", 227.5, 74, ["1", "2"])
        self.wire(227.5, hp_y, 227.5, 70.19)
        self.junction(227.5, hp_y)
        self.gnd(227.5, 82)
        self.wire(227.5, 77.81, 227.5, 82)
        # C35 AC coupling (series) -> HP_AC
        self.sym("C", "C35", "47uF", 232, hp_y, ["1", "2"], angle=90)
        self.wire(235.81, hp_y, 244.19, hp_y)
        # R39 bleed to GND (defines 0 V DC on the jack side of C35).
        # The HP_AC name hangs mid-way down R39's stub — the row itself
        # has no gap wide enough for a 5-char label between the C35 and
        # R37 pin numbers.
        self.sym("R", "R39", "4.7k", 241, 74, ["1", "2"])
        self.wire(241, hp_y, 241, 70.19)
        self.junction(241, hp_y)
        self.glabel("HP_AC", 241, 66, 0, "output")
        self.gnd(241, 82)
        self.wire(241, 77.81, 241, 82)
        # R37 series -> jack TIP (left channel)
        self.sym("R", "R37", "33R", 248, hp_y, ["1", "2"], angle=90)
        self.wire(251.81, hp_y, 258.11, hp_y)
        self.glabel("HP_L", 255, hp_y, 90, "output")

        # Jack: J5 placed so TIP lands exactly on the hp_y run
        self.sym("AudioJack_PJ327A", "J5", "PJ-327A", 267, 67.08,
                 ["2", "3", "4", "5", "6"])
        # R38 series -> jack RING (right channel) — own row, linked to
        # HP_AC by name; the wire climbs to the RING pin.
        self.glabel("HP_AC", 228, 90, 90, "input")
        self.wire(228, 90, 232.19, 90)
        self.sym("R", "R38", "33R", 236, 90, ["1", "2"], angle=90)
        self.wire(239.81, 90, 250, 90)
        self.glabel("HP_R", 245, 90, 90, "output")
        self.wire(250, 90, 250, 64.54)
        self.wire(250, 64.54, 258.11, 64.54)
        # SLV (sleeve, pin 2) -> GND
        self.wire(258.11, 69.62, 255, 69.62)
        self.gnd(255, 69.62)
        # SSW (pin 6): the SLEEVE normally-closed switch = jack detect
        # (R36-HIGH-1: this is the sleeve switch, GND-referenced when
        # closed, not the tip switch).
        self.wire(275.89, 62, 281.5, 62)
        self.glabel("JACK_DET", 281.5, 62, 90, "output")
        # TSW (pin 4, tip rest contact): unused
        self.nc(275.89, 69.62)

        # Detect network: R40 pull-up + Q3. No gate RC is needed: the
        # detect is the SLEEVE switch, so when unplugged it ties JACK_DET
        # to GND (a clean 0V, NOT the tip audio) — Q3 stays hard off with
        # no chatter regardless of volume.
        # (Notes live at y>=140, clear of the speaker's own captions.)
        self.text("Plug inserted -> sleeve switch opens -> R40 pulls",
                  200, 140, 1.5)
        self.text("JACK_DET high -> Q3 pulls PAM8403 MUTE low (spk off).",
                  200, 143.5, 1.5)
        self.text("Unplugged: sleeve switch ties JACK_DET to GND (0V),",
                  200, 147, 1.5)
        self.text("so Q3 is hard off and the speaker plays.",
                  200, 150.5, 1.5)
        # R40 220k: +3V3 -> JACK_DET (3V3 fully enhances Q3, and the
        # divider vs R37+R39 parks the gate at ~70 mV when unplugged)
        self.sym("R", "R40", "220k", 226, 118, ["1", "2"])
        self.v33(226, 112)
        self.wire(226, 112, 226, 114.19)
        self.wire(226, 121.81, 226, 124)
        self.glabel("JACK_DET", 226, 124, 0, "input")
        # Q3 2N7002: gate on JACK_DET, source to GND, open drain on
        # PAM_MUTE. Fields moved left of the body: the default spot
        # above the drain pin collides with its pin number.
        self.glabel("JACK_DET", 238, 130, 90, "input")
        self.wire(238, 130, 244.92, 130)
        self.sym("NMOS_SOT23", "Q3", "2N7002", 250, 128.73,
                 ["1", "2", "3"],
                 fields={"ref": (-9.0, -4.5, "left"),
                         "val": (-9.0, -2.3, "left")})
        self.wire(255.08, 130, 257.5, 130)
        self.gnd(257.5, 130)
        self.wire(250, 123.65, 250, 120)
        self.glabel("PAM_MUTE", 250, 120, 90, "output")

        # U5 MUTE pin (module symbol pin 6 = SOP-16 pad 5, drawn on the
        # right edge below SPK-) — freed from the historic +5V strap,
        # now driven by Q3's open drain.
        self.wire(ax + 10.16, ay + 3.81, ax + 13, ay + 3.81)
        self.glabel("PAM_MUTE", ax + 13, ay + 3.81, 0, "input")

        # Notes
        ny = 178
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
