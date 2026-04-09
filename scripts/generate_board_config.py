#!/usr/bin/env python3
"""Generate board_config.h GPIO #defines from config.py GPIO_NETS.

Usage:
    python3 scripts/generate_board_config.py           # print generated defines
    python3 scripts/generate_board_config.py --check   # compare against board_config.h
"""

import re
import sys
from pathlib import Path

# Ensure project root is on the path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generate_schematics.config import GPIO_NETS

# Signal-name prefix -> category label (order determines output order)
CATEGORIES = [
    ("LCD_", "Display: ILI9488 8-bit 8080 parallel"),
    ("SD_",  "SD Card: SPI mode"),
    ("I2S_", "Audio: I2S"),
    ("BTN_", "Buttons: active-low"),
    ("USB_", "USB: native USB on ESP32-S3"),
]


def sanitize(signal: str) -> str:
    """Convert signal name to a valid C macro identifier."""
    return signal.replace("+", "P").replace("-", "N")


def categorize(gpio_nets: dict) -> dict:
    """Group GPIO_NETS entries by category. Uncategorized signals go to Other."""
    groups: dict[str, list[tuple[int, str]]] = {label: [] for _, label in CATEGORIES}
    groups["Other"] = []

    for gpio, signal in sorted(gpio_nets.items()):
        macro = sanitize(signal)
        placed = False
        for prefix, label in CATEGORIES:
            if signal.startswith(prefix):
                groups[label].append((gpio, macro))
                placed = True
                break
        if not placed:
            groups["Other"].append((gpio, macro))

    return groups


def generate_lines(groups: dict) -> list[str]:
    """Produce formatted #define lines, one section per category."""
    lines = []
    for _, label in CATEGORIES:
        entries = groups.get(label, [])
        if not entries:
            continue
        lines.append(f"/* -- {label} */")
        for gpio, macro in sorted(entries, key=lambda x: x[0]):
            lines.append(f"#define {macro:<20s} GPIO_NUM_{gpio}")
        lines.append("")
    if groups.get("Other"):
        lines.append("/* -- Other */")
        for gpio, macro in sorted(groups["Other"], key=lambda x: x[0]):
            lines.append(f"#define {macro:<20s} GPIO_NUM_{gpio}")
        lines.append("")
    return lines


def parse_board_config(path: Path) -> dict[str, int]:
    """Parse #define NAME GPIO_NUM_N lines from board_config.h."""
    pattern = re.compile(r"^#define\s+(\w+)\s+GPIO_NUM_(\d+)")
    result = {}
    for line in path.read_text().splitlines():
        m = pattern.match(line.strip())
        if m:
            result[m.group(1)] = int(m.group(2))
    return result


def main():
    check_mode = "--check" in sys.argv

    groups = categorize(GPIO_NETS)
    generated_lines = generate_lines(groups)

    if not check_mode:
        print("\n".join(generated_lines))
        return

    # Build expected dict from GPIO_NETS
    expected = {sanitize(sig): gpio for gpio, sig in GPIO_NETS.items()}

    board_config_path = ROOT / "software" / "main" / "board_config.h"
    if not board_config_path.exists():
        print(f"ERROR: board_config.h not found at {board_config_path}", file=sys.stderr)
        sys.exit(1)

    actual = parse_board_config(board_config_path)

    mismatches = []
    missing = []
    extras = []

    for macro, exp_gpio in sorted(expected.items()):
        if macro not in actual:
            missing.append((macro, exp_gpio))
        elif actual[macro] != exp_gpio:
            mismatches.append((macro, exp_gpio, actual[macro]))

    for macro in sorted(actual):
        if macro not in expected:
            extras.append((macro, actual[macro]))

    if not mismatches and not missing and not extras:
        print("OK: board_config.h GPIO defines match config.py GPIO_NETS")
        sys.exit(0)

    if mismatches:
        print("MISMATCH (wrong GPIO):")
        for macro, exp, got in mismatches:
            print(f"  {macro:<20s}  expected GPIO_NUM_{exp:<3d}  got GPIO_NUM_{got}")
    if missing:
        print("MISSING in board_config.h (defined in config.py):")
        for macro, gpio in missing:
            print(f"  #define {macro:<20s} GPIO_NUM_{gpio}")
    if extras:
        print("EXTRA in board_config.h (not in config.py GPIO_NETS):")
        for macro, gpio in extras:
            print(f"  #define {macro:<20s} GPIO_NUM_{gpio}  <-- review")

    sys.exit(1)


if __name__ == "__main__":
    main()
