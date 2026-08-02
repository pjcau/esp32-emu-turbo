"""KiCad PCB S-expression primitives."""


class PcbUid:
    """Sequential UUID generator for PCB elements."""

    def __init__(self):
        self._n = 0

    def uid(self) -> str:
        self._n += 1
        return f"{self._n:08x}-dead-4000-a000-{self._n:012x}"


_uid = PcbUid()


def uid() -> str:
    return _uid.uid()


def header() -> str:
    return (
        '(kicad_pcb\n'
        '  (version 20241229)\n'
        '  (generator "pcbnew")\n'
        '  (generator_version "9.0")\n'
        '  (general (thickness 1.6) (legacy_teardrops no))\n'
        '  (paper "A4")\n'
    )


def layers_4layer() -> str:
    return (
        '  (layers\n'
        '    (0 "F.Cu" signal)\n'
        '    (4 "In1.Cu" signal)\n'
        '    (6 "In2.Cu" signal)\n'
        '    (2 "B.Cu" signal)\n'
        '    (9 "F.Adhes" user "F.Adhesive")\n'
        '    (11 "B.Adhes" user "B.Adhesive")\n'
        '    (13 "F.Paste" user)\n'
        '    (15 "B.Paste" user)\n'
        '    (5 "F.SilkS" user "F.Silkscreen")\n'
        '    (7 "B.SilkS" user "B.Silkscreen")\n'
        '    (1 "F.Mask" user)\n'
        '    (3 "B.Mask" user)\n'
        '    (17 "Dwgs.User" user "User.Drawings")\n'
        '    (19 "Cmts.User" user "User.Comments")\n'
        '    (21 "Eco1.User" user "User.Eco1")\n'
        '    (23 "Eco2.User" user "User.Eco2")\n'
        '    (25 "Edge.Cuts" user)\n'
        '    (27 "Margin" user)\n'
        '    (31 "F.CrtYd" user "F.Courtyard")\n'
        '    (29 "B.CrtYd" user "B.Courtyard")\n'
        '    (35 "F.Fab" user "F.Fabrication")\n'
        '    (33 "B.Fab" user "B.Fabrication")\n'
        '  )\n'
    )


def setup_4layer() -> str:
    return (
        '  (setup\n'
        '    (stackup\n'
        '      (layer "F.SilkS" (type "Top Silk Screen"))\n'
        '      (layer "F.Paste" (type "Top Solder Paste"))\n'
        '      (layer "F.Mask" (type "Top Solder Mask")'
        ' (thickness 0.01))\n'
        '      (layer "F.Cu" (type "copper")'
        ' (thickness 0.035))\n'
        '      (layer "dielectric 1" (type "prepreg")'
        ' (thickness 0.2104) (material "FR4")'
        ' (epsilon_r 4.5) (loss_tangent 0.02))\n'
        '      (layer "In1.Cu" (type "copper")'
        ' (thickness 0.0175))\n'
        '      (layer "dielectric 2" (type "core")'
        ' (thickness 1.065) (material "FR4")'
        ' (epsilon_r 4.5) (loss_tangent 0.02))\n'
        '      (layer "In2.Cu" (type "copper")'
        ' (thickness 0.0175))\n'
        '      (layer "dielectric 3" (type "prepreg")'
        ' (thickness 0.2104) (material "FR4")'
        ' (epsilon_r 4.5) (loss_tangent 0.02))\n'
        '      (layer "B.Cu" (type "copper")'
        ' (thickness 0.035))\n'
        '      (layer "B.Mask" (type "Bottom Solder Mask")'
        ' (thickness 0.01))\n'
        '      (layer "B.Paste"'
        ' (type "Bottom Solder Paste"))\n'
        '      (layer "B.SilkS"'
        ' (type "Bottom Silk Screen"))\n'
        '      (copper_finish "ENIG")\n'
        '    )\n'
        '    (pad_to_mask_clearance 0)\n'
    '    (allow_soldermask_bridges_in_footprints yes)\n'
        '    (pcbplotparams\n'
        '      (layerselection 0x00000000_00000000_55555555_5755f5ff)\n'
        '      (plot_on_all_layers_selection'
        ' 0x00000000_00000000_00000000_00000000)\n'
        '      (disableapertmacros no)\n'
        '      (usegerberextensions no)\n'
        '      (usegerberattributes yes)\n'
        '      (usegerberadvancedattributes yes)\n'
        '      (creategerberjobfile yes)\n'
        '      (dashed_line_dash_ratio 12.000000)\n'
        '      (dashed_line_gap_ratio 3.000000)\n'
        '      (svgprecision 4)\n'
        '      (plotframeref no)\n'
        '      (mode 1)\n'
        '      (useauxorigin no)\n'
        '      (hpglpennumber 1)\n'
        '      (hpglpenspeed 20)\n'
        '      (hpglpendiameter 15.000000)\n'
        '      (pdf_front_fp_property_popups yes)\n'
        '      (pdf_back_fp_property_popups yes)\n'
        '      (pdf_metadata yes)\n'
        '      (pdf_single_document no)\n'
        '      (dxfpolygonmode yes)\n'
        '      (dxfimperialunits yes)\n'
        '      (dxfusepcbnewfont yes)\n'
        '      (psnegative no)\n'
        '      (psa4output no)\n'
        '      (plot_black_and_white yes)\n'
        '      (sketchpadsonfab no)\n'
        '      (plotpadnumbers no)\n'
        '      (hidednponfab no)\n'
        '      (sketchdnponfab yes)\n'
        '    )\n'
        '  )\n'
    )


# ── Complete netlist ──────────────────────────────────────────────

NET_LIST = [
    (0, ""),
    (1, "GND"),
    (2, "VBUS"),
    (3, "+5V"),
    (4, "+3V3"),
    (5, "BAT+"),
    # Display 8080 data bus
    (6, "LCD_D0"), (7, "LCD_D1"), (8, "LCD_D2"), (9, "LCD_D3"),
    (10, "LCD_D4"), (11, "LCD_D5"), (12, "LCD_D6"), (13, "LCD_D7"),
    # Display control
    (14, "LCD_CS"), (15, "LCD_RST"), (16, "LCD_DC"),
    (17, "LCD_WR"),
    # 18 and 19 are RETIRED, and deliberately left as gaps: renumbering the
    # nets below them would rewrite every net id in the .kicad_pcb for no gain.
    #   18 was LCD_RD, 19 was LCD_BL. Both are real FPC signals (pins 12 and
    #   33) but neither is driven: routing.py ties them to +3V3 (read strobe
    #   disabled, display is write-only; backlight always on). Their pads
    #   therefore live on the +3V3 net, and the two names survived only as
    #   declarations carrying zero pads — which is what made DRC report them
    #   as nets with no copper.
    # SD card SPI
    (20, "SD_MOSI"), (21, "SD_MISO"), (22, "SD_CLK"), (23, "SD_CS"),
    # I2S audio
    # Old slots: (24, "I2S_BCLK"), (25, "I2S_LRCK") — retired 2026-07-26
    # (R10-LOW-2), gap left deliberately like 18/19 and 39. Each net had
    # exactly ONE pad (U1.8 / U1.9) and zero copper: the audio path is PDM
    # TX, which uses only DOUT — software/main/audio.c sets
    # .clk = I2S_GPIO_UNUSED. A one-pin net is a label, not a circuit, and
    # it cost three gate allowlists (verify_design_intent KNOWN_SINGLE +
    # DIRECT_ROUTED, drc_check _UNROUTED_OK) to keep green.
    (26, "I2S_DOUT"),
    # Buttons
    (27, "BTN_UP"), (28, "BTN_DOWN"), (29, "BTN_LEFT"), (30, "BTN_RIGHT"),
    (31, "BTN_A"), (32, "BTN_B"), (33, "BTN_X"), (34, "BTN_Y"),
    (35, "BTN_START"), (36, "BTN_SELECT"),
    (37, "BTN_L"), (38, "BTN_R"),
    # R9-MED-4 (2026-04-11): BTN_MENU net removed. R19/C20 were placed on
    # this dead net in the button pull-up/debounce block but never connected
    # to MENU_K (which holds SW13 + D1.3). The menu button is detected via
    # the START+SELECT combo through D1 BAT54C — no separate pull-up or
    # debounce is required, because BTN_START/BTN_SELECT already have their
    # own R/C pairs. R19 and C20 deleted from BOM/CPL in the same commit.
    # Old slot: (39, "BTN_MENU") — leave gap, KiCad tolerates non-contiguous IDs.
    # USB
    (40, "USB_D+"), (41, "USB_D-"),
    # Audio output
    (42, "SPK+"), (43, "SPK-"),
    # IP5306 boost converter
    (46, "LX"), (47, "IP5306_KEY"),
    # USB CC pull-down
    (48, "USB_CC1"), (49, "USB_CC2"),
    # PAM8403 internal reference
    (50, "PAM_VREF"),
    # LED resistor-to-anode internal nets
    (51, "LED1_RA"),
    (52, "LED2_RA"),
    # EN reset net (ESP32 EN pin — active-low reset)
    (53, "EN"),
    # USB ESD protection: MCU-side nets after 22Ω series resistors
    (54, "USB_DP_MCU"),
    (55, "USB_DM_MCU"),
    # Menu button: BAT54C cathode junction (D1 pin 3 → SW13 pad 2)
    (56, "MENU_K"),
    # Reverse polarity protection: battery-side of Q1 P-MOSFET
    (57, "BAT_IN"),
    # Q1 gate net: pulled to GND via R24 (static, but distinct for schematic clarity)
    (58, "RPP_GATE"),
    # U3 SY8089AAAC synchronous buck (replaces the AMS1117 LDO):
    #   BUCK_LX — switch node, U3 pin 3 (LX) -> L2 pin 2
    #   BUCK_FB — feedback node, U3 pin 5 (FB) -> R25/R26 divider tap + C29
    # Named with a BUCK_ prefix so they are never confused with net 46 "LX",
    # which is the IP5306 boost switch node (U2 pin 7 -> L1).
    (59, "BUCK_LX"),
    (60, "BUCK_FB"),
    # Audio AC-coupled input node: PAM8403 side of the C22 series DC-block.
    # C22.1 is I2S_DOUT (ESP32 PDM TX), C22.2 is PAM_IN_AC. They are two
    # electrically distinct nets separated by the cap dielectric — labelling
    # both "I2S_DOUT" made DRC report a permanent phantom "unconnected"
    # on I2S_DOUT, which masked real faults. Carries: C22.2, U5.7 (INL),
    # U5.10 (INR) and the R20/R21 VREF bias taps.
    (61, "PAM_IN_AC"),
    # Backlight anode node: J4 pad 8 (panel pin 33, LED-A) after the R27
    # series resistor from +5V. R25-HIGH-1 fix — the anode used to be
    # hard-tied to +3V3 with no current-limiting element at all; from +5V
    # the 1.8 V of headroom lets a 20 Ω resistor actually set the current
    # (~90 mA for the 6-LED family class, datasheet
    # DISPLAY-FAMILY_E35RG73248LW6M250-R outline note 7).
    (62, "LED_BLA"),
    # USB-C connector side of the F1 VBUS PTC fuse (R3-HIGH-4 fix): J1's
    # VBUS pads and their reversibility loop live on VBUS_IN; everything
    # downstream of F1 (U2.1, U4.5, C17.1) stays VBUS. A series element
    # is two nets, not one "logically fragmented" net — same rule as
    # PAM_IN_AC above.
    (63, "VBUS_IN"),
    # Diagnostic LED heartbeat, GPIO15 (U1.8) -> R31 -> LED6. Workstream H
    # of docs/diagnostic-leds-roadmap.md. GPIO15 and GPIO16 are the only
    # genuinely free module pins — GPIO26-37 belong to the flash / octal
    # PSRAM — so the driven tier of the diagnostic tree is ONE pin carrying
    # blink codes per subsystem, not one LED per subsystem.
    (64, "LED_HB"),
    # Resistor-to-anode junctions for the four diagnostic LEDs, exactly like
    # LED1_RA / LED2_RA above: the series resistor and the LED are two
    # elements, so the node between them is its own net. Unnamed, KiCad
    # drops it from the exported netlist and verify_netlist_diff cannot
    # match it against the copper.
    (65, "LED3_RA"),
    (66, "LED4_RA"),
    (67, "LED5_RA"),
    (68, "LED6_RA"),
]

NET_ID = {name: nid for nid, name in NET_LIST}


def nets() -> str:
    """Declare all nets used in the board."""
    lines = []
    for nid, name in NET_LIST:
        lines.append(f'  (net {nid} "{name}")\n')
    return "".join(lines)


def gr_line(x1, y1, x2, y2, layer="Edge.Cuts", width=0.15):
    return (
        f'  (gr_line (start {x1} {y1}) (end {x2} {y2})'
        f' (stroke (width {width}) (type default))'
        f' (layer "{layer}") (uuid "{uid()}"))\n'
    )


def gr_arc(sx, sy, mx, my, ex, ey,
           layer="Edge.Cuts", width=0.15):
    return (
        f'  (gr_arc (start {sx} {sy})'
        f' (mid {mx} {my}) (end {ex} {ey})'
        f' (stroke (width {width}) (type default))'
        f' (layer "{layer}") (uuid "{uid()}"))\n'
    )


def gr_text(text, x, y, layer="F.SilkS", size=1.0):
    mirror = " (justify mirror)" if "B." in layer else ""
    return (
        f'  (gr_text "{text}" (at {x} {y})'
        f' (layer "{layer}")'
        f' (effects (font (size {size} {size})'
        f' (thickness 0.2)){mirror}))\n'
    )


def mounting_hole(x, y, drill=2.5, pad_d=3.5):
    """M2.5 mounting hole — NPTH (no copper annular ring, purely mechanical).

    DFM: NPTH eliminates 4× THT-to-SMD and 2× pad spacing DANGER violations
    caused by the old PTH copper pad interfering with nearby SMD components.

    R21 FIX (2026-07-25): the footprint identifier used to be
    "MountingHole:MountingHole_2.5mm", i.e. it named an external KiCad
    library ("MountingHole") which this project's fp-lib-table does not
    contain — KiCad DRC raised 6x lib_footprint_issues, one per hole.
    Every other footprint this generator emits is fully embedded in the
    board file and carries a bare, library-less identifier ("C_0805",
    "USB-C-16P", "Fiducial", ...). The mounting hole now follows the same
    convention: it is self-contained here, so it must not claim to come
    from a library that would have to be resolved at load time.
    """
    ref_uid = uid()
    val_uid = uid()
    fp_uid = uid()
    pad_uid = uid()
    return (
        f'  (footprint "MountingHole_{drill}mm"\n'
        f'    (layer "F.Cu")\n'
        f'    (uuid "{fp_uid}")\n'
        f'    (at {x} {y})\n'
        f'    (property "Reference" ""\n'
        f'      (at 0 0 0)\n'
        f'      (layer "F.Fab")\n'
        f'      (uuid "{ref_uid}")\n'
        f'      (effects (font (size 1.27 1.27) (thickness 0.2)))\n'
        f'    )\n'
        f'    (property "Value" ""\n'
        f'      (at 0 0 0)\n'
        f'      (layer "F.Fab")\n'
        f'      (uuid "{val_uid}")\n'
        f'      (effects (font (size 1.27 1.27) (thickness 0.2)))\n'
        f'    )\n'
        f'    (pad "" np_thru_hole circle\n'
        f'      (at 0 0)\n'
        f'      (size {drill} {drill})\n'
        f'      (drill {drill})\n'
        f'      (layers "*.Cu" "*.Mask")\n'
        f'      (uuid "{pad_uid}")\n'
        f'    )\n'
        f'    (embedded_fonts no)\n'
        f'  )\n'
    )


def via(x, y, size=0.9, drill=0.35, net=0):
    return (
        f'  (via (at {x} {y}) (size {size})'
        f' (drill {drill})'
        f' (layers "F.Cu" "B.Cu")'
        f' (net {net}) (uuid "{uid()}"))\n'
    )


def zone_fill(layer, pts_list, net=1, net_name="GND", priority=0):
    """Copper fill zone with clearance from other nets."""
    pts = " ".join(f"(xy {x} {y})" for x, y in pts_list)
    prio = f'    (priority {priority})\n'
    return (
        f'  (zone\n'
        f'    (net {net})\n'
        f'    (net_name "{net_name}")\n'
        f'    (layer "{layer}")\n'
        f'    (uuid "{uid()}")\n'
        f'    (hatch none 0.5)\n'
        f'    (connect_pads (clearance 0.5))\n'
        f'    (min_thickness 0.25)\n'
        f'    (filled_areas_thickness no)\n'
        f'{prio}'
        f'    (fill yes\n'
        f'      (thermal_gap 0.5)\n'
        f'      (thermal_bridge_width 0.5)\n'
        f'    )\n'
        f'    (polygon\n'
        f'      (pts {pts})\n'
        f'    )\n'
        f'  )\n'
    )


def zone_gnd(layer, pts_list, net=1):
    """GND copper fill zone."""
    return zone_fill(layer, pts_list, net, "GND")


def segment(x1, y1, x2, y2, layer="F.Cu", width=0.25, net=0):
    """PCB trace segment."""
    return (
        f'  (segment (start {x1} {y1}) (end {x2} {y2})'
        f' (width {width}) (layer "{layer}")'
        f' (net {net}) (uuid "{uid()}"))\n'
    )


def footer():
    return ')\n'
