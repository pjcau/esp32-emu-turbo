"""CLI entry point: python -m scripts.generate_pcb <output_dir>."""

import sys

from . import main

if len(sys.argv) < 2:
    print("Usage: python -m scripts.generate_pcb <output_dir>")
    sys.exit(1)

main(sys.argv[1])
