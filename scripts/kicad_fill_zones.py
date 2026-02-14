#!/usr/bin/env python3
"""Fill all zones in a KiCad PCB file using the pcbnew Python API.

Designed to run inside the kicad Docker container where pcbnew is available.
This is needed because kicad-cli 9.0 does not have a --fill-all-zones flag
for Gerber export. Without filled zones, internal copper planes (GND, 3V3, 5V)
appear empty in the Gerber output.

Usage:
    python3 /scripts/kicad_fill_zones.py /project/esp32-emu-turbo.kicad_pcb
"""

import sys

import pcbnew


def main():
    if len(sys.argv) < 2:
        print("Usage: kicad_fill_zones.py <input.kicad_pcb>")
        sys.exit(1)

    pcb_path = sys.argv[1]
    print(f"Loading PCB: {pcb_path}")

    board = pcbnew.LoadBoard(pcb_path)

    # Fill all zones
    filler = pcbnew.ZONE_FILLER(board)
    zones = board.Zones()
    print(f"Found {len(zones)} zones:")
    for z in zones:
        net = z.GetNetname()
        layer = board.GetLayerName(z.GetLayer())
        prio = z.GetAssignedPriority()
        print(f"  - {net} on {layer} (priority {prio})")

    print("Filling zones...")
    filler.Fill(zones)

    # Save the board with filled zones
    pcbnew.SaveBoard(pcb_path, board)
    print(f"Saved PCB with filled zones: {pcb_path}")


if __name__ == "__main__":
    main()
