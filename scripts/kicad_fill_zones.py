#!/usr/bin/env python3
"""Fill all zones in a KiCad PCB file using the pcbnew Python API.

Strategy: pcbnew's SaveBoard() strips orphan nets. To preserve them:
1. Fill zones via pcbnew, save to temp file
2. Extract filled_polygon blocks (raw polygon data) from temp
3. Inject into the ORIGINAL PCB file with correct indentation

Usage:
    python3 scripts/kicad_fill_zones.py hardware/kicad/esp32-emu-turbo.kicad_pcb
"""

import os
import re
import sys
import tempfile

import pcbnew


def _extract_zone_fills_from_pcbnew(filled_path):
    """Extract filled_polygon blocks from pcbnew-saved file.

    pcbnew uses tab indentation. Returns dict: {uuid: filled_polygon_text}
    with indentation converted to 4-space (matching our generator format).
    """
    with open(filled_path) as f:
        content = f.read()

    result = {}

    # Find zone blocks (tab-indented in pcbnew output)
    # Split by zone UUID
    zone_pattern = re.compile(
        r'\(zone\b.*?\(uuid "([^"]+)"\).*?\n\t\)',
        re.DOTALL
    )

    for m in zone_pattern.finditer(content):
        uid = m.group(1)
        zone_text = m.group(0)

        # Extract filled_polygon blocks
        fp_pattern = re.compile(
            r'\t\t\(filled_polygon\b.*?\n\t\t\)',
            re.DOTALL
        )
        fp_blocks = fp_pattern.findall(zone_text)
        if fp_blocks:
            # Convert tab indentation to 4-space
            converted = []
            for block in fp_blocks:
                # Remove leading tabs, add spaces
                lines = block.split('\n')
                spaced_lines = []
                for line in lines:
                    # Count leading tabs
                    stripped = line.lstrip('\t')
                    n_tabs = len(line) - len(stripped)
                    # Our zone content is at 4-space indent, so:
                    # 2 tabs = 4 spaces (zone content level)
                    # 3 tabs = 6 spaces (pts level)
                    # 4 tabs = 8 spaces (xy data level)
                    spaced_lines.append('  ' * n_tabs + stripped)
                converted.append('\n'.join(spaced_lines))
            result[uid] = '\n'.join(converted)

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: kicad_fill_zones.py <input.kicad_pcb>")
        sys.exit(1)

    pcb_path = sys.argv[1]
    print(f"Loading PCB: {pcb_path}")

    # Read original PCB
    with open(pcb_path) as f:
        original = f.read()

    # Fill zones with pcbnew
    board = pcbnew.LoadBoard(pcb_path)
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

    # Save filled board to temp
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".kicad_pcb")
    os.close(tmp_fd)
    pcbnew.SaveBoard(tmp_path, board)

    # Extract filled polygon data
    fills = _extract_zone_fills_from_pcbnew(tmp_path)
    os.unlink(tmp_path)
    print(f"Extracted fill data for {len(fills)} zones")

    # Inject into original PCB
    # Our zones end with: \n  )\n  (closing of zone block)
    # We insert filled_polygon after the (polygon ...) block
    result = original
    for uid, fill_data in fills.items():
        # Find zone with this UUID and inject before its closing '  )\n'
        # Pattern: zone block ends with "    )\n  )\n" (polygon close + zone close)
        zone_re = re.compile(
            r'(\(zone\b.*?\(uuid "' + re.escape(uid) + r'"\).*?'
            r'\(polygon\b.*?\n    \)\n)'  # polygon block close
            r'(  \)\n)',                   # zone close
            re.DOTALL
        )
        m = zone_re.search(result)
        if m:
            result = (result[:m.end(1)] +
                      fill_data + '\n' +
                      m.group(2) +
                      result[m.end():])
        else:
            print(f"  WARNING: Could not find zone {uid} in original PCB")

    # Write result
    with open(pcb_path, 'w') as f:
        f.write(result)
    print(f"Saved PCB with filled zones: {pcb_path}")


if __name__ == "__main__":
    main()
