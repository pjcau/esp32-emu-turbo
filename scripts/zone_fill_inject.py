#!/usr/bin/env python3
"""Pure-text injection of zone fill data into a .kicad_pcb.

Split out of ``kicad_fill_zones.py`` so it can be unit-tested on the host:
that module imports ``pcbnew``, which only exists inside the KiCad container.
Everything here is plain string manipulation with no KiCad dependency.

The invariant this module exists to hold: injection REPLACES a zone's
``filled_polygon`` blocks, it never appends to them. See
``scripts/test_zone_fill_sanity.py`` for the regression tests and
``scripts/verify_zone_fill_sanity.py`` for the board-level gate.
"""

import re

# filled_polygon blocks as emitted by kicad_fill_zones' extractor: 4-space
# indent, closing paren alone on its own 4-space line. The zone's own
# (polygon ...) outline closes identically, so anchor on the block name.
EXISTING_FILL_RE = re.compile(r'[ \t]*\(filled_polygon\b.*?\n    \)\n', re.DOTALL)


def strip_existing_fills(zone_text):
    """Remove every filled_polygon block from a single zone block.

    Makes injection idempotent: filling an already-filled board reproduces the
    same bytes instead of stacking a second copy of the copper.
    """
    return EXISTING_FILL_RE.sub('', zone_text)


def zone_spans(text):
    """[(start, end)] byte spans of each top-level ``(zone ...)`` block.

    Balanced-paren scanning, NOT a regex. A regex of the form
    ``\\(zone\\b.*?\\(uuid "X"\\)`` looks right but is quietly wrong on a
    multi-zone board: the lazy ``.*?`` happily spans *earlier* zones to reach
    a later zone's uuid, so replacing that match eats every zone in between.
    That cost three zones their fill. Match structure, not text.
    """
    spans = []
    i = 0
    while True:
        i = text.find("  (zone", i)
        if i < 0:
            return spans
        depth, j = 0, text.index("(", i)
        while j < len(text):
            c = text[j]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        end = j + 1
        if end < len(text) and text[end] == "\n":
            end += 1
        spans.append((i, end))
        i = end


def inject_fills(original, fills):
    """Return (new_text, missing_uuids) with each zone's fill replaced.

    ``fills`` maps zone uuid -> filled_polygon text (already indented).
    """
    result = original
    missing = []

    for uid, fill_data in fills.items():
        needle = f'(uuid "{uid}")'
        target = None
        for start, end in zone_spans(result):
            if needle in result[start:end]:
                target = (start, end)
                break
        if target is None:
            missing.append(uid)
            continue

        start, end = target
        # Replace, never append: drop any fill already present, then insert
        # this run's fill immediately before the zone's closing paren.
        zone_text = strip_existing_fills(result[start:end])
        if not zone_text.endswith('\n  )\n'):
            raise ValueError(f"zone {uid}: unexpected block tail after stripping fills")
        rebuilt = zone_text[:-len('  )\n')] + fill_data + '\n' + '  )\n'
        result = result[:start] + rebuilt + result[end:]

    return result, missing
