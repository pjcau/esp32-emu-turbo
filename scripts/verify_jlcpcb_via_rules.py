#!/usr/bin/env python3
"""Via and hole rules straight from JLCPCB's own design guide.

Source: https://jlcpcb.com/blog/pcb-via-design-best-practices

Our .kicad_dru encodes what KiCad should enforce, and verify_dfm_v2.py
encodes what we learned the hard way. Neither is JLCPCB's published guidance,
which is the thing the fabricator actually applies. This script transcribes
the numeric rules from that page directly, so a change on their side is a
one-file diff here instead of a scattered hunt.

Two severities, kept apart on purpose:

  HARD      below a stated manufacturing limit. The board cannot be built as
            drawn. Fails the gate.
  ADVISORY  legal but penalised — JLCPCB calls anything under 0.30 mm a
            "small hole" and recommends larger for cost and yield. Reported
            with the count and never hidden, but it does not fail: it is a
            cost decision, and silently failing on it would train people to
            ignore the gate.

Slot rules apply only to elongated (oval) holes. A round NPTH is not a slot,
and conflating the two produces false failures on mounting and peg holes.

Usage:
    python3 scripts/verify_jlcpcb_via_rules.py
    python3 scripts/verify_jlcpcb_via_rules.py --verbose
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))
PCB = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"

# ── JLCPCB published limits ──────────────────────────────────────────
MIN_DRILL_MM = 0.15          # smallest drill bit
MIN_VIA_OUTER_MM = 0.25      # smallest finished via outer diameter
SMALL_HOLE_MM = 0.30         # below this = "small hole": legal, surcharged
DRILL_INCREMENT_MM = 0.05    # bits step in 0.05 mm
MIN_PLATED_SLOT_MM = 0.65    # metallized slot width
MIN_NPTH_SLOT_MM = 1.00      # non-metallized slot width
MIN_SLOT_RATIO = 2.5         # slot length / width — short slots are hardest
SLOT_ANNULAR_MIN_MM = 0.20   # absolute floor
SLOT_ANNULAR_TARGET_MM = 0.30  # recommended

_OVAL_DRILL_RE = re.compile(r"\(drill\s+oval\s+([\d.]+)\s+([\d.]+)\)")


def _slots() -> list[dict]:
    """Every oval-drilled pad: width, length, plated flag, ref."""
    text = PCB.read_text(errors="replace")
    out = []
    for m in re.finditer(r"\(pad\s+\"?([^\s\")]*)\"?\s+(\S+)\s+(\S+)(.{0,600}?)\)\n",
                         text, re.S):
        body = m.group(4)
        d = _OVAL_DRILL_RE.search(body)
        if not d:
            continue
        w, l = float(d.group(1)), float(d.group(2))
        size = re.search(r"\(size ([\d.]+) ([\d.]+)\)", body)
        out.append({
            "num": m.group(1),
            "plated": m.group(2) != "np_thru_hole",
            "w": min(w, l), "l": max(w, l),
            "pad_w": float(size.group(1)) if size else None,
            "pad_l": float(size.group(2)) if size else None,
        })
    return out


def main(argv: list[str]) -> int:
    from pcb_cache import load_cache
    verbose = "--verbose" in argv or "-v" in argv
    cache = load_cache(PCB)
    vias = cache["vias"]
    pads = [p for p in cache["pads"] if p.get("drill")]

    hard: list[str] = []
    advisory: list[str] = []

    print("=" * 72)
    print("  JLCPCB VIA & HOLE RULES")
    print("  https://jlcpcb.com/blog/pcb-via-design-best-practices")
    print("=" * 72)

    # -- drill floor + increment ------------------------------------
    holes = [("via", v["drill"], v) for v in vias] + \
            [("pad", p["drill"], p) for p in pads]
    for kind, d, item in holes:
        if d < MIN_DRILL_MM - 1e-9:
            hard.append(f"{kind} drill {d:.3f} mm < {MIN_DRILL_MM} mm "
                        f"(smallest bit)")
        steps = d / DRILL_INCREMENT_MM
        if abs(steps - round(steps)) > 1e-6:
            hard.append(f"{kind} drill {d:.3f} mm is not a multiple of "
                        f"{DRILL_INCREMENT_MM} mm (bit increment)")
    print(f"  [{'FAIL' if hard else 'PASS'}] drill >= {MIN_DRILL_MM} mm and on "
          f"the {DRILL_INCREMENT_MM} mm grid ({len(holes)} holes)")

    # -- via outer diameter ------------------------------------------
    bad_outer = [v for v in vias if v["size"] < MIN_VIA_OUTER_MM - 1e-9]
    for v in bad_outer:
        hard.append(f"via outer {v['size']:.3f} mm < {MIN_VIA_OUTER_MM} mm "
                    f"@({v['x']}, {v['y']})")
    print(f"  [{'FAIL' if bad_outer else 'PASS'}] via outer diameter >= "
          f"{MIN_VIA_OUTER_MM} mm ({len(vias)} vias)")

    # -- small-hole advisory -----------------------------------------
    small = [v for v in vias if v["drill"] < SMALL_HOLE_MM - 1e-9]
    if small:
        sizes = sorted({round(v["drill"], 3) for v in small})
        advisory.append(
            f"{len(small)} of {len(vias)} vias drill {sizes} mm, under the "
            f"{SMALL_HOLE_MM} mm \"small hole\" threshold — legal, but JLCPCB "
            f"surcharges and yields worse. Going to 0.30 mm costs board area "
            f"in the FPC/ESP32 fan-out; decide, do not drift into it.")
    print(f"  [{'NOTE' if small else 'PASS'}] holes >= {SMALL_HOLE_MM} mm "
          f"(\"small hole\" cost threshold)")

    # -- slots --------------------------------------------------------
    slots = _slots()
    slot_bad = []
    for s in slots:
        floor = MIN_PLATED_SLOT_MM if s["plated"] else MIN_NPTH_SLOT_MM
        kind = "plated" if s["plated"] else "NPTH"
        if s["w"] < floor - 1e-9:
            slot_bad.append(f"{kind} slot width {s['w']:.2f} mm < {floor} mm "
                            f"(pad {s['num'] or '-'})")
        ratio = s["l"] / s["w"] if s["w"] else 0
        if ratio < MIN_SLOT_RATIO - 1e-9:
            advisory.append(
                f"{kind} slot pad {s['num'] or '-'} is {s['l']:.2f}x"
                f"{s['w']:.2f} mm, ratio {ratio:.2f} < {MIN_SLOT_RATIO} — "
                f"short slots are the hardest to route")
        if s["pad_w"] and s["pad_l"]:
            ring = min(s["pad_w"] - s["w"], s["pad_l"] - s["l"]) / 2
            if ring < SLOT_ANNULAR_MIN_MM - 1e-9:
                slot_bad.append(f"{kind} slot annular {ring:.3f} mm < "
                                f"{SLOT_ANNULAR_MIN_MM} mm (pad {s['num']})")
            elif ring < SLOT_ANNULAR_TARGET_MM - 1e-9:
                advisory.append(f"{kind} slot pad {s['num']} annular "
                                f"{ring:.3f} mm below the {SLOT_ANNULAR_TARGET_MM} mm "
                                f"recommendation (floor is {SLOT_ANNULAR_MIN_MM})")
    hard += slot_bad
    print(f"  [{'FAIL' if slot_bad else 'PASS'}] slot width, ratio and annular "
          f"ring ({len(slots)} slots)")

    print("-" * 72)
    if advisory:
        print(f"  ADVISORY ({len(advisory)}) — legal, but costed or penalised:")
        for a in (advisory if verbose else advisory[:6]):
            print(f"    - {a}")
        if not verbose and len(advisory) > 6:
            print(f"    ... {len(advisory) - 6} more (--verbose)")
    if hard:
        print(f"\n  HARD ({len(hard)}) — below a stated manufacturing limit:")
        for h in hard[:20]:
            print(f"    - {h}")
        print("\n  The board cannot be built as drawn. Fix before ordering.")
        return 1
    print("\n  Every hole and slot is within JLCPCB's published limits.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
