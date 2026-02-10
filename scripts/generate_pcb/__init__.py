"""Generate KiCad PCB (.kicad_pcb) for ESP32 Emu Turbo."""

import os

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

    # Generate JLCPCB CPL
    jlcpcb_dir = os.path.join(output_dir, "jlcpcb")
    os.makedirs(jlcpcb_dir, exist_ok=True)
    export_cpl(jlcpcb_dir)

    print("Done.")
