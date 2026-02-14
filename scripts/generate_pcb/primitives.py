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
        '    (pad_to_mask_clearance 0.05)\n'
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
    (17, "LCD_WR"), (18, "LCD_RD"), (19, "LCD_BL"),
    # SD card SPI
    (20, "SD_MOSI"), (21, "SD_MISO"), (22, "SD_CLK"), (23, "SD_CS"),
    # I2S audio
    (24, "I2S_BCLK"), (25, "I2S_LRCK"), (26, "I2S_DOUT"),
    # Buttons
    (27, "BTN_UP"), (28, "BTN_DOWN"), (29, "BTN_LEFT"), (30, "BTN_RIGHT"),
    (31, "BTN_A"), (32, "BTN_B"), (33, "BTN_X"), (34, "BTN_Y"),
    (35, "BTN_START"), (36, "BTN_SELECT"),
    (37, "BTN_L"), (38, "BTN_R"),
    (39, "BTN_MENU"),
    # USB
    (40, "USB_D+"), (41, "USB_D-"),
    # Audio output
    (42, "SPK+"), (43, "SPK-"),
    # Joystick (optional)
    (44, "JOY_X"), (45, "JOY_Y"),
]

NET_ID = {name: nid for nid, name in NET_LIST}


def nets() -> str:
    """Declare all nets used in the board."""
    lines = []
    for nid, name in NET_LIST:
        lines.append(f'  (net {nid} "{name}")\n')
    return "".join(lines)


def gr_line(x1, y1, x2, y2, layer="Edge.Cuts", width=0.05):
    return (
        f'  (gr_line (start {x1} {y1}) (end {x2} {y2})'
        f' (stroke (width {width}) (type default))'
        f' (layer "{layer}") (uuid "{uid()}"))\n'
    )


def gr_arc(sx, sy, mx, my, ex, ey,
           layer="Edge.Cuts", width=0.05):
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
        f' (thickness 0.15)){mirror}))\n'
    )


def mounting_hole(x, y, drill=2.5, pad_d=5.0):
    """M2.5 mounting hole with annular ring."""
    ref_uid = uid()
    val_uid = uid()
    fp_uid = uid()
    pad_uid = uid()
    return (
        f'  (footprint "MountingHole:MountingHole_{drill}mm"\n'
        f'    (layer "F.Cu")\n'
        f'    (uuid "{fp_uid}")\n'
        f'    (at {x} {y})\n'
        f'    (property "Reference" ""\n'
        f'      (at 0 0 0)\n'
        f'      (layer "F.SilkS")\n'
        f'      (uuid "{ref_uid}")\n'
        f'      (effects (font (size 1.27 1.27) (thickness 0.15)))\n'
        f'    )\n'
        f'    (property "Value" ""\n'
        f'      (at 0 0 0)\n'
        f'      (layer "F.Fab")\n'
        f'      (uuid "{val_uid}")\n'
        f'      (effects (font (size 1.27 1.27) (thickness 0.15)))\n'
        f'    )\n'
        f'    (pad "" thru_hole circle\n'
        f'      (at 0 0)\n'
        f'      (size {pad_d} {pad_d})\n'
        f'      (drill {drill})\n'
        f'      (layers "*.Cu" "*.Mask")\n'
        f'      (remove_unused_layers no)\n'
        f'      (uuid "{pad_uid}")\n'
        f'    )\n'
        f'    (embedded_fonts no)\n'
        f'  )\n'
    )


def via(x, y, size=0.6, drill=0.3, net=0):
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
