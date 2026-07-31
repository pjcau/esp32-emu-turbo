#!/usr/bin/env python3
"""Mutation tests for verify_gerber_etest.py — prove the gate can fail.

An e-test gate that never fires is not evidence of a sound board, so every
failure direction is exercised against the real release artifacts:

    M1  clean release inputs                  -> zero failures
    M2  +3V3/GND labels swapped on some vias  -> SHORT and/or OPEN reported
    M3  truncated d356                        -> structural error, not a pass
    M4  every record shifted 7 mm             -> structural error ("mapping
        broken"), never a silent all-bare pass

The copper is rasterized ONCE and shared across mutations, so the whole
suite costs one gate run plus noise.

Historical fixture (the reason this gate exists): the v4.3.1 release gerbers
— the fabricated prototype #1 — fail with +3V3 in 4 pieces and VBUS in 3.
Reproduce by hand with:

    git archive v4.3.1 release_jlcpcb/gerbers.zip | tar -x -C /tmp/v431
    unzip /tmp/v431/release_jlcpcb/gerbers.zip -d /tmp/v431/gerbers
    kicad-cli pcb export ipcd356 --output /tmp/v431/fresh.d356 \
        <v4.3.1 release_jlcpcb/esp32-emu-turbo.kicad_pcb>
    python3 scripts/verify_gerber_etest.py --gerbers /tmp/v431/gerbers \
        --d356 /tmp/v431/fresh.d356

Not run here: it needs kicad-cli and ~20 s, and the mutations above already
prove every detection path the fixture exercises (opens, shorts, bare).
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_gerber_etest import (  # noqa: E402
    DEF_D356,
    DEF_GERBERS,
    Fatal,
    analyze,
    find_drill,
    parse_d356,
    parse_drill,
    rasterize_layers,
)

DPMM = 40


def main() -> int:
    print("=" * 72)
    print("GERBER E-TEST MUTATION SUITE — the gate must be able to fail")
    print("=" * 72)
    failures = []

    records = parse_d356(DEF_D356)
    holes = parse_drill(find_drill(DEF_GERBERS))
    masks, minx, maxy = rasterize_layers(DEF_GERBERS, DPMM)

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    # M1: the release artifacts themselves are electrically sound
    found, stats = analyze(records, holes, masks, minx, maxy, DPMM)
    check("M1 clean release inputs pass", not found,
          "; ".join(h for h, _ in found[:3]) if found else
          f"{stats['records']} points, {stats['nets']} nets")

    # M2: swap net labels on ten GND vias — the copper no longer matches the
    # netlist, and the gate must say so (as a SHORT, an OPEN, or both)
    mutated = copy.deepcopy(records)
    swapped = 0
    for rec in mutated:
        if rec["net"] == "GND" and rec["ref"] == "VIA" and swapped < 10:
            rec["net"] = "+3V3"
            swapped += 1
    found_m2, _ = analyze(mutated, holes, masks, minx, maxy, DPMM)
    hit = [h for h, _ in found_m2 if "+3V3" in h and "GND" in h]
    check("M2 swapped GND->+3V3 labels detected", swapped == 10 and bool(hit),
          hit[0] if hit else f"swapped={swapped}, findings={len(found_m2)}")

    # M3: a truncated netlist must be a structural error, never a quiet pass
    import tempfile

    kept = 0
    with tempfile.NamedTemporaryFile("w", suffix=".d356", delete=False) as tf:
        for line in DEF_D356.read_text().splitlines():
            if line.startswith(("317", "327")):
                if kept >= 40:
                    continue
                kept += 1
            tf.write(line + "\n")
        truncated = Path(tf.name)
    try:
        parse_d356(truncated)
        check("M3 truncated d356 rejected", False, "no error raised")
    except Fatal:
        check("M3 truncated d356 rejected", True)
    finally:
        truncated.unlink()

    # M4: shift every record 7 mm — the mapping self-check must refuse to
    # judge instead of reporting 500 bare points as if they were findings
    shifted = copy.deepcopy(records)
    for rec in shifted:
        rec["x"] += 7.0
        rec["y"] += 7.0
    try:
        analyze(shifted, holes, masks, minx, maxy, DPMM)
        check("M4 shifted coordinates rejected as structural", False,
              "analyze returned instead of raising Fatal")
    except Fatal:
        check("M4 shifted coordinates rejected as structural", True)

    print("-" * 72)
    if failures:
        print(f"Results: FAIL — {len(failures)} mutation(s) survived: "
              f"{', '.join(failures)}")
        return 1
    print("Results: PASS — 4/4 mutations detected")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fatal as e:
        print(f"STRUCTURAL ERROR: {e}", file=sys.stderr)
        sys.exit(2)
