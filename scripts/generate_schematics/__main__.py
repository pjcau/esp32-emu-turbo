#!/usr/bin/env python3
"""CLI entry point: python -m generate_schematics /output/dir"""

import os
import sys


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "hardware", "kicad",
    )

    print(f"Generating multi-sheet schematics in {output_dir}")

    # Initialize sheet definitions (lazy imports)
    from . import config
    config._init()

    from . import main as generate_all
    generated = generate_all(output_dir)

    print(f"\nGenerated {len(generated)} schematic sheets:")
    for path in generated:
        print(f"  {os.path.basename(path)}")
    print("Done.")


if __name__ == "__main__":
    main()
