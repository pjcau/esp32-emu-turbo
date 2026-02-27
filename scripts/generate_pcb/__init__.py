"""Generate KiCad PCB (.kicad_pcb) for ESP32 Emu Turbo."""

import os
import sys
from pathlib import Path

from .board import generate_board
from .jlcpcb_export import export_cpl


def main(output_dir: str):
    """Generate the .kicad_pcb file and JLCPCB exports."""
    os.makedirs(output_dir, exist_ok=True)

    # Generate PCB
    pcb_path = os.path.join(output_dir, "esp32-emu-turbo.kicad_pcb")
    content = generate_board()
    with open(pcb_path, "w") as f:
        f.write(content)
    print(f"  PCB: {pcb_path}")

    # Build parse cache for downstream analysis scripts
    _scripts_dir = str(Path(__file__).resolve().parent.parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    from pcb_cache import build_cache
    build_cache(Path(pcb_path))

    # Generate JLCPCB CPL
    jlcpcb_dir = os.path.join(output_dir, "jlcpcb")
    os.makedirs(jlcpcb_dir, exist_ok=True)
    export_cpl(jlcpcb_dir)

    print("Done.")
