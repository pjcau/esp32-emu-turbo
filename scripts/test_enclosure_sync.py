#!/usr/bin/env python3
"""Mutation tests for verify_enclosure_sync.py — the sync gate must fail.

Each case mutates an in-memory copy of enclosure.scad the way a real
regression would (the battery pocket shrinking back to the pre-F1 size,
the ABXY DFM shift reverting, a constant silently renamed) and demands
the gate objects. An assertion that never fires is not evidence.

    M1  pcb_w 160 -> 159                     outline mismatch    -> exit 1
    M2  a screw boss off its mount hole                          -> exit 1
    M3  usbc_x 0 -> 5                        cutout drift        -> exit 1
    M4  abxy Y offset -9 -> -10              DFM shift reverted  -> exit 1
    M5  menu_y -24.2 -> -25                  button drift        -> exit 1
    M6  bat_d 10 -> 9.5                      pre-F1 pocket back  -> exit 1
    M7  body_d 26 -> 25                      battery/module clash-> exit 1
    M8  esp_d 3.1 -> 3.0                     envelope understated-> exit 1
    M9  pcb_w renamed                        contract broken     -> exit 2
    M10 pcb_w indented (module-local shape)  contract broken     -> exit 2
    M11 screw_positions uses an unknown name contract broken     -> exit 2
    M12 unmutated file                       all green           -> exit 0
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_enclosure_sync as ves  # noqa: E402

ORIGINAL = ves.SCAD.read_text()


def run_with(text: str) -> int:
    """Run the gate against a mutated scad, return its exit code."""
    with tempfile.NamedTemporaryFile("w", suffix=".scad",
                                     delete=False) as tf:
        tf.write(text)
        tmp = Path(tf.name)
    real = ves.SCAD
    try:
        ves.SCAD = tmp
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                return ves.main()
        except ves.Structural:
            return 2
    finally:
        ves.SCAD = real
        tmp.unlink()


def mutate(old: str, new: str) -> str:
    if ORIGINAL.count(old) != 1:
        raise AssertionError(
            f"mutation anchor not unique ({ORIGINAL.count(old)}x): {old!r}")
    return ORIGINAL.replace(old, new)


def main() -> int:
    print("=" * 72)
    print("ENCLOSURE-SYNC GATE MUTATION SUITE")
    print("=" * 72)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    cases = [
        ("M1 outline drift", "pcb_w = 160;", "pcb_w = 159;", 1),
        ("M2 boss off its hole",
         "[-body_w/2 + 15, body_h/2 - 12],    // Front-left",
         "[-body_w/2 + 17, body_h/2 - 12],    // Front-left", 1),
        ("M3 USB cutout drift", "usbc_x = 0;", "usbc_x = 5;", 1),
        ("M4 ABXY DFM shift reverted",
         "    [-9, 0],     // Y", "    [-10, 0],     // Y", 1),
        ("M5 menu drift", "menu_y = -24.2;", "menu_y = -25;", 1),
        ("M6 pre-F1 battery pocket", "bat_d = 10;", "bat_d = 9.5;", 1),
        ("M7 battery/module clash", "body_d = 26;", "body_d = 25;", 1),
        ("M8 ESP envelope understated", "esp_d = 3.1;", "esp_d = 3.0;", 1),
        ("M9 constant renamed", "pcb_w = 160;", "pcb_width = 160;", 2),
        ("M10 constant indented", "pcb_w = 160;", "  pcb_w = 160;", 2),
        ("M11 vector uses unknown name",
         "[-body_w/2 + 15, body_h/2 - 12],    // Front-left",
         "[-frame_w/2 + 15, body_h/2 - 12],   // Front-left", 2),
    ]
    for name, old, new, want in cases:
        rc = run_with(mutate(old, new))
        check(name, rc == want, f"rc={rc}, want {want}")

    rc = run_with(ORIGINAL)
    check("M12 unmutated file passes", rc == 0, f"rc={rc}")

    print("-" * 72)
    if failures:
        print(f"Results: FAIL — {len(failures)} case(s): "
              f"{', '.join(failures)}")
        return 1
    print("Results: PASS — 12/12 scad mutations detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
