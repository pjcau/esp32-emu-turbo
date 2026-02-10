"""KiCad S-expression primitives for schematic generation."""


class KiCadContext:
    """Manages UUID generation and provides KiCad S-expression helpers."""

    def __init__(self):
        self._n = 0
        self._pn = 0

    def uid(self) -> str:
        self._n += 1
        return f"{self._n:08x}-cafe-4000-8000-{self._n:012x}"

    def wire(self, x1: float, y1: float, x2: float, y2: float) -> str:
        return (
            f'  (wire (pts (xy {x1} {y1}) (xy {x2} {y2}))'
            f' (stroke (width 0) (type default))'
            f' (uuid "{self.uid()}"))\n'
        )

    def label(self, name: str, x: float, y: float, angle: float = 0) -> str:
        return (
            f'  (label "{name}" (at {x} {y} {angle})'
            f' (effects (font (size 1.27 1.27)))'
            f' (uuid "{self.uid()}"))\n'
        )

    def global_label(self, name: str, x: float, y: float, angle: float = 0,
                     shape: str = "bidirectional") -> str:
        return (
            f'  (global_label "{name}" (shape {shape}) (at {x} {y} {angle})'
            f' (effects (font (size 1.27 1.27)))'
            f' (uuid "{self.uid()}")'
            f' (property "Intersheetrefs" "" (at 0 0 0)'
            f' (effects (font (size 1.27 1.27)) hide)))\n'
        )

    def text(self, txt: str, x: float, y: float, sz: float = 2.54,
             bold: bool = False) -> str:
        b = " bold" if bold else ""
        return (
            f'  (text "{txt}" (at {x} {y} 0)'
            f' (effects (font (size {sz} {sz}){b}) (justify left)))\n'
        )

    def power_symbol(self, lib: str, ref: str, val: str,
                     x: float, y: float) -> str:
        return (
            f'  (symbol (lib_id "{lib}") (at {x} {y} 0) (unit 1)'
            f' (exclude_from_sim no) (in_bom no) (on_board no) (dnp no)'
            f' (uuid "{self.uid()}")'
            f' (property "Reference" "{ref}" (at {x} {y - 2} 0)'
            f' (effects (font (size 1.27 1.27)) hide))'
            f' (property "Value" "{val}" (at {x} {y + 2} 0)'
            f' (effects (font (size 1.27 1.27)) hide))'
            f' (pin "1" (uuid "{self.uid()}")))\n'
        )

    def gnd(self, x: float, y: float) -> str:
        self._pn += 1
        return self.power_symbol("GND", f"#PWR{self._pn:03d}", "GND", x, y)

    def v33(self, x: float, y: float) -> str:
        self._pn += 1
        return self.power_symbol("+3V3", f"#PWR{self._pn:03d}", "+3V3", x, y)

    def v5(self, x: float, y: float) -> str:
        self._pn += 1
        return self.power_symbol("+5V", f"#PWR{self._pn:03d}", "+5V", x, y)

    def no_connect(self, x: float, y: float) -> str:
        return (
            f'  (no_connect (at {x} {y})'
            f' (uuid "{self.uid()}"))\n'
        )

    def symbol(self, lib: str, ref: str, val: str,
               x: float, y: float, pins: list) -> str:
        s = (
            f'  (symbol (lib_id "{lib}") (at {x} {y} 0) (unit 1)'
            f' (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)'
            f' (uuid "{self.uid()}")'
            f' (property "Reference" "{ref}" (at {x} {y - 5} 0)'
            f' (effects (font (size 1.27 1.27))))'
            f' (property "Value" "{val}" (at {x} {y + 5} 0)'
            f' (effects (font (size 1.27 1.27))))'
        )
        for p in pins:
            s += f' (pin "{p}" (uuid "{self.uid()}"))'
        return s + ")\n"
