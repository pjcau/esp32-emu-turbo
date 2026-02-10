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
        '  (version 20240108)\n'
        '  (generator "pcb_generator")\n'
        '  (generator_version "1.0")\n'
        f'  (general (thickness 1.6) (legacy_teardrops no))\n'
        '  (paper "A4")\n'
    )


def layers_4layer() -> str:
    return (
        '  (layers\n'
        '    (0 "F.Cu" signal)\n'
        '    (1 "In1.Cu" signal)\n'
        '    (2 "In2.Cu" signal)\n'
        '    (31 "B.Cu" signal)\n'
        '    (32 "B.Adhes" user "B.Adhesive")\n'
        '    (33 "F.Adhes" user "F.Adhesive")\n'
        '    (34 "B.Paste" user)\n'
        '    (35 "F.Paste" user)\n'
        '    (36 "B.SilkS" user "B.Silkscreen")\n'
        '    (37 "F.SilkS" user "F.Silkscreen")\n'
        '    (38 "B.Mask" user "B.Mask")\n'
        '    (39 "F.Mask" user "F.Mask")\n'
        '    (40 "Dwgs.User" user "User.Drawings")\n'
        '    (41 "Cmts.User" user "User.Comments")\n'
        '    (42 "Eco1.User" user "User.Eco1")\n'
        '    (43 "Eco2.User" user "User.Eco2")\n'
        '    (44 "Edge.Cuts" user)\n'
        '    (45 "Margin" user)\n'
        '    (46 "B.CrtYd" user "B.Courtyard")\n'
        '    (47 "F.CrtYd" user "F.Courtyard")\n'
        '    (48 "B.Fab" user "B.Fabrication")\n'
        '    (49 "F.Fab" user "F.Fabrication")\n'
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
        '  )\n'
    )


def nets() -> str:
    """Declare nets used in the board (required before any net reference)."""
    return (
        '  (net 0 "")\n'
        '  (net 1 "GND")\n'
    )


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
    return (
        f'  (gr_text "{text}" (at {x} {y})'
        f' (layer "{layer}")'
        f' (effects (font (size {size} {size})'
        f' (thickness 0.15))))\n'
    )


def mounting_hole(x, y, drill=2.5, pad_d=5.0):
    """M2.5 mounting hole with annular ring."""
    return (
        f'  (footprint "MountingHole:MountingHole_{drill}mm"'
        f' (at {x} {y})\n'
        f'    (layer "F.Cu")\n'
        f'    (uuid "{uid()}")\n'
        f'    (pad "" thru_hole circle (at 0 0)'
        f' (size {pad_d} {pad_d})'
        f' (drill {drill})'
        f' (layers "*.Cu" "*.Mask"))\n'
        f'  )\n'
    )


def via(x, y, size=0.6, drill=0.3, net=0):
    return (
        f'  (via (at {x} {y}) (size {size})'
        f' (drill {drill})'
        f' (layers "F.Cu" "B.Cu")'
        f' (net {net}) (uuid "{uid()}"))\n'
    )


def zone_gnd(layer, pts_list, net=1):
    """Copper fill zone for GND."""
    pts = " ".join(f"(xy {x} {y})" for x, y in pts_list)
    return (
        f'  (zone (net {net}) (net_name "GND")'
        f' (layer "{layer}")'
        f' (uuid "{uid()}")\n'
        f'    (fill yes (thermal_gap 0.5)'
        f' (thermal_bridge_width 0.5))\n'
        f'    (polygon (pts {pts}))\n'
        f'  )\n'
    )


def segment(x1, y1, x2, y2, layer="F.Cu", width=0.25, net=0):
    """PCB trace segment."""
    return (
        f'  (segment (start {x1} {y1}) (end {x2} {y2})'
        f' (width {width}) (layer "{layer}")'
        f' (net {net}) (uuid "{uid()}"))\n'
    )


def footer():
    return ')\n'
