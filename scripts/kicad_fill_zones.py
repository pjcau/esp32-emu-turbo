#!/usr/bin/env python3
"""Fill all zones in a KiCad PCB file using the pcbnew Python API.

Strategy: pcbnew's SaveBoard() strips orphan nets. To preserve them:
1. Fill zones via pcbnew, save to temp file
2. Extract filled_polygon blocks (raw polygon data) from temp
3. Inject into the ORIGINAL PCB file with correct indentation

Injection REPLACES any pre-existing ``filled_polygon`` blocks rather than
appending to them. This matters: the previous version inserted the new fill
just before the zone's closing paren, which lands *after* whatever fill was
already there. Run serially that was harmless (the regex happened to skip to
the last close), but two overlapping runs — e.g. ``drc_native.py --run``
racing a hook-triggered fill — each read the same unfilled original and both
injected, doubling every zone's copper.

A doubled board is invisible to every downstream gate: the geometry is
identical, so DRC is clean and power-net integrity still sees one connected
group. Only the poured area gives it away (it exceeds the board outline).
See scripts/verify_zone_fill_sanity.py for the guard.

Two independent defenses, in order of importance:

  Replace-not-append  — the written file is a pure function of (zone
                        definitions, pcbnew fill result). Prior fill state
                        cannot accumulate, so even an interleaved read/write
                        yields a valid board rather than a doubled one.
  Lock + atomic write — an exclusive lock serializes concurrent runs, and
                        os.replace() means a reader never observes a
                        half-written PCB. The lock is best-effort across
                        container boundaries; correctness does not depend
                        on it.

Usage:
    python3 scripts/kicad_fill_zones.py hardware/kicad/esp32-emu-turbo.kicad_pcb
"""

import fcntl
import os
import re
import sys
import tempfile

import pcbnew

from zone_fill_inject import inject_fills


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

    # Serialize concurrent fills across the whole read-fill-write cycle.
    # Sidecar lockfile rather than the PCB itself: the atomic replace swaps
    # the PCB's inode, which would drop a lock held on it.
    lock_path = pcb_path + ".fill.lock"
    with open(lock_path, "w") as lock_f:
        fcntl.flock(lock_f, fcntl.LOCK_EX)
        try:
            _fill_locked(pcb_path)
        finally:
            fcntl.flock(lock_f, fcntl.LOCK_UN)


def _fill_locked(pcb_path):
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

    # Inject into original PCB — replaces existing fills, never appends.
    result, missing = inject_fills(original, fills)
    for uid in missing:
        print(f"  WARNING: Could not find zone {uid} in original PCB")

    if missing:
        # A zone we filled but could not write back means the saved board is
        # not the board we verified. Fail loudly rather than ship a partial fill.
        print(f"ERROR: {len(missing)} zone(s) could not be injected: {missing}")
        sys.exit(1)

    # Atomic write: a concurrent reader sees either the old file or the new
    # one, never a truncated mix. Temp file lives in the same directory so
    # os.replace() stays within one filesystem.
    pcb_dir = os.path.dirname(os.path.abspath(pcb_path)) or "."
    fd, tmp_out = tempfile.mkstemp(suffix=".kicad_pcb", dir=pcb_dir)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(result)
        os.replace(tmp_out, pcb_path)
    except BaseException:
        if os.path.exists(tmp_out):
            os.unlink(tmp_out)
        raise
    print(f"Saved PCB with filled zones: {pcb_path}")


if __name__ == "__main__":
    main()
