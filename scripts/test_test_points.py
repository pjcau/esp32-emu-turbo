#!/usr/bin/env python3
"""Mutation tests for verify_test_points.py — the promoted gate must fail.

The test-point law was advisory for months; promoting it to blocking is
only worth anything if each verdict class is proven reachable:

    T1  a REQUIRED_SIGNALS net absent from the board  -> exit 2
    T2  MIN_PAD_DIM raised beyond every pad (nothing probeable) -> exit 1
    T3  the fine-pitch INFO branch stays advisory: a signal whose only
        probeable copper is below FINE_PITCH_DIM must be reported and
        must NOT fail the run
    T4  the real board at HEAD                         -> exit 0
"""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_test_points as vtp  # noqa: E402


def run() -> tuple[int, str]:
    buf = io.StringIO()
    # reset the module counters main() accumulates into
    vtp.PASS = vtp.FAIL = vtp.INFO_COUNT = vtp.ERROR = 0
    with contextlib.redirect_stdout(buf):
        rc = vtp.main()
    return rc, buf.getvalue()


def main() -> int:
    print("=" * 72)
    print("TEST-POINT GATE MUTATION SUITE")
    print("=" * 72)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    real_signals = vtp.REQUIRED_SIGNALS
    real_min_pad = vtp.MIN_PAD_DIM

    # T1: a law naming a net this board does not have is structural
    try:
        vtp.REQUIRED_SIGNALS = {**real_signals,
                                "Bogus": ["NO_SUCH_NET_EXISTS"]}
        rc, _ = run()
        check("T1 unknown required net exits 2", rc == 2, f"rc={rc}")
    finally:
        vtp.REQUIRED_SIGNALS = real_signals

    # T2: with the bar raised beyond every pad, the gate must go red —
    # proves the FAIL branch is reachable, not decorative
    try:
        vtp.MIN_PAD_DIM = 50.0
        vtp.MIN_VIA_DRILL = 50.0
        rc, _ = run()
        check("T2 nothing probeable exits 1", rc == 1, f"rc={rc}")
    finally:
        vtp.MIN_PAD_DIM = real_min_pad
        vtp.MIN_VIA_DRILL = 0.45

    # T3: the fine-pitch branch must be advisory, not fatal.
    # This used to read the branch straight off HEAD, because USB_D+/-
    # landed on U4's 0.60x0.70 SOT-23-6 pads. R32 grew that land to the
    # JLC reference (0.60x1.00) and no required signal is fine-pitch any
    # more — so reading it off the board silently stopped testing
    # anything. Raise the bar instead: at 1.2mm the USB pads fall into
    # the branch, and the run must still be green.
    real_fine = vtp.FINE_PITCH_DIM
    try:
        vtp.FINE_PITCH_DIM = 1.2
        rc, out = run()
        check("T3 fine-pitch stays advisory",
              "fine-pitch" in out and rc == 0,
              "INFO branch present, rc=0" if "fine-pitch" in out
              else f"no INFO line (rc={rc})")
    finally:
        vtp.FINE_PITCH_DIM = real_fine

    # T4: the real board at HEAD
    rc, out = run()
    check("T4 real board passes", rc == 0, f"rc={rc}")

    print("-" * 72)
    if failures:
        print(f"Results: FAIL — {len(failures)} case(s): "
              f"{', '.join(failures)}")
        return 1
    print("Results: PASS — 4/4 gate mutations detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
