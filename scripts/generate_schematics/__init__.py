"""Multi-sheet KiCad schematic generator for ESP32 Emu Turbo."""

from .kicad_primitives import KiCadContext
from .sheet_base import SchematicSheet


def main(output_dir: str) -> list[str]:
    """Generate all schematic sheets into output_dir.

    Returns list of generated file paths.
    """
    import os
    from . import config

    os.makedirs(output_dir, exist_ok=True)
    generated = []

    for sheet_def in config.SHEET_DEFS:
        mod = sheet_def["module"]
        filename = sheet_def["filename"]
        path = os.path.join(output_dir, filename)

        ctx = KiCadContext()
        sheet = mod(ctx)
        content = sheet.render()

        with open(path, "w") as f:
            f.write(content)
        generated.append(path)
        print(f"  {filename} ({content.count(chr(10))} lines)")

    return generated
