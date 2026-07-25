"""KiCad S-expression primitives for schematic generation."""

# Project name as KiCad sees it (the .kicad_pro basename). Symbol instance
# paths are scoped to it; a mismatch makes the instance invisible.
PROJECT_NAME = "esp32-emu-turbo"


def sheet_uuid(index: int) -> str:
    """UUID of the root's ``(sheet ...)`` block for sub-sheet ``index``.

    The root schematic allocates UUIDs from a fresh context: #1 for the root
    itself, then #2, #3, ... one per sheet in SHEET_DEFS order (``text()``
    emits no UUID, so nothing else consumes the sequence). Sub-sheet symbols
    must reference these exact UUIDs in their instance paths, so both sides
    derive them here rather than each re-deriving the formula.
    """
    n = index + 2
    return f"{n:08x}-cafe-4000-8000-{n:012x}"


class KiCadContext:
    """Manages UUID generation and provides KiCad S-expression helpers.

    ``sheet_path`` is the root sheet UUID this file's symbols live under. It
    is required to emit ``(instances ...)``: without that block KiCad treats
    every symbol as unannotated, reports "schematic has annotation errors",
    and DROPS the symbol from the netlist. Power symbols suffer worst — all
    33 ``gnd()`` ports were silently absent, leaving GND with 3 nodes instead
    of ~80, so the schematic was not an electrical model of the board.
    """

    def __init__(self, sheet_path: str | None = None,
                 project: str = PROJECT_NAME):
        self._n = 0
        self._pn = 0
        self.sheet_path = sheet_path
        self.project = project

    def uid(self) -> str:
        self._n += 1
        return f"{self._n:08x}-cafe-4000-8000-{self._n:012x}"

    def instances(self, ref: str, unit: int = 1) -> str:
        """The ``(instances ...)`` block that annotates a symbol.

        Emitted for every symbol. Returns "" only when no sheet path is known
        (a bare context in a test), which keeps the old behaviour rather than
        writing a path that points nowhere.
        """
        if not self.sheet_path:
            return ""
        return (
            f' (instances (project "{self.project}"'
            f' (path "/{self.sheet_path}"'
            f' (reference "{ref}") (unit {unit}))))'
        )

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

    def junction(self, x: float, y: float) -> str:
        """Connection dot where a wire ENDS on another wire mid-span.

        Without it KiCad treats the touch as a crossing, not a connection,
        and so does a human reader. See scripts/verify_schematic_crossings.py.
        """
        return (
            f'  (junction (at {x} {y}) (diameter 0) (color 0 0 0 0)'
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
            f' (pin "1" (uuid "{self.uid()}"))'
            f'{self.instances(ref)})\n'
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
               x: float, y: float, pins: list, angle: int = 0) -> str:
        """Place a symbol instance.

        ``angle`` rotates the symbol body (KiCad convention: CCW degrees).
        It is used to make a symmetric two-terminal part's *pin numbering*
        agree with the PCB footprint's pad numbering without changing how
        the part is drawn. A 180 deg rotation of a vertically symmetric
        R/C symbol looks identical but swaps which end is pin 1, which is
        exactly what is needed when the footprint on the board has pad 1
        on the opposite end from the default symbol orientation.
        """
        # Keep the Reference/Value fields OUTSIDE the drawn body. The old
        # fixed +-5mm printed them across the outline of anything taller --
        # U3 (body +-5.08) and U6 (+-6.35) both had their Value struck
        # through the component. Derived from the symbol's own graphics, so a
        # symbol that grows pushes its labels out by itself.
        from .lib_symbols import body_half_height
        _fo = max(5.0, body_half_height(lib) + 2.0)
        s = (
            f'  (symbol (lib_id "{lib}") (at {x} {y} {angle}) (unit 1)'
            f' (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)'
            f' (uuid "{self.uid()}")'
            f' (property "Reference" "{ref}" (at {x} {y - _fo} 0)'
            f' (effects (font (size 1.27 1.27))))'
            f' (property "Value" "{val}" (at {x} {y + _fo} 0)'
            f' (effects (font (size 1.27 1.27))))'
        )
        for p in pins:
            s += f' (pin "{p}" (uuid "{self.uid()}"))'
        return s + self.instances(ref) + ")\n"
