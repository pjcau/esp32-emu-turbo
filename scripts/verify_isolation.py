#!/usr/bin/env python3
"""Every conductor is connected where intended and isolated everywhere else.

The repo has 53 verification scripts and `make verify-all` runs all of them —
but only five run automatically when the PCB changes. Everything that answers
"is anything shorted to anything else?" sits in the other forty-eight, which
means it is checked when somebody remembers, not when the board changes.

The whole isolation set costs about two seconds. There is no reason for it to
be optional, so this composes it into one gate that the Stop hook can run on
every edit.

Two questions, over pads, drilled holes, copper layers and zones:

  CONNECTED   everything that should be one net IS one piece of copper
  ISOLATED    nothing that should be separate touches anything else

Members, and what each one would catch on its own:

  short_circuit_analysis        different nets sharing copper
  verify_trace_through_pad      a netted trace crossing an unnetted pad —
                                the v3.3 regression (775e9fd), a real short
  verify_trace_crossings        two segments meeting on one layer without a
                                node; the fabricator merges them
  verify_copper_clearance       copper-to-copper gaps below the fab minimum
  analyze_pad_distances         pad-to-pad and pad-to-via spacing
  verify_via_in_pad             a via landing inside a different-net SMD pad
  verify_zone_connectivity      vias and THT pads actually reaching the fill
  verify_power_net_integrity    each power net is ONE group — the check that
                                would have caught the split +3V3 plane
  verify_net_connectivity       per-net union-find over the copper graph
  verify_component_connectivity phantom components with no copper at all
  verify_stackup                nets on the layers the stackup says
  verify_polarity               every pad carries the net the design intends
  verify_jlcpcb_via_rules       JLCPCB's own published via, hole and slot
                                limits, transcribed from their design guide
                                rather than inferred

Exit 0 when all pass, 1 otherwise. `--verbose` shows each script's output.

Usage:
    python3 scripts/verify_isolation.py
    python3 scripts/verify_isolation.py --verbose
    python3 scripts/verify_isolation.py --list
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# (script, one-line reason it is in this set)
CHECKS: list[tuple[str, str]] = [
    ("short_circuit_analysis",      "different nets sharing copper"),
    ("verify_trace_through_pad",    "netted trace crossing an unnetted pad"),
    ("verify_trace_crossings",      "segments merging on one layer"),
    ("verify_copper_clearance",     "copper-to-copper below fab minimum"),
    ("analyze_pad_distances",       "pad-to-pad / pad-to-via spacing"),
    ("verify_via_in_pad",           "via inside a different-net SMD pad"),
    ("verify_zone_connectivity",    "vias/THT pads reaching the zone fill"),
    ("verify_power_net_integrity",  "each power net is ONE copper group"),
    ("verify_net_connectivity",     "per-net union-find over the copper"),
    ("verify_component_connectivity", "phantom components with no copper"),
    ("verify_stackup",              "nets on the layers the stackup declares"),
    ("verify_polarity",             "every pad carries the intended net"),
    ("verify_jlcpcb_via_rules",     "JLCPCB published via/hole/slot limits"),
]


def run(name: str, verbose: bool) -> tuple[str, int, float, str]:
    path = BASE / "scripts" / f"{name}.py"
    if not path.exists():
        return (name, 127, 0.0, f"missing: {path.relative_to(BASE)}")
    t0 = time.monotonic()
    proc = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True, text=True, cwd=str(BASE),
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if verbose:
        print(out)
    tail = ""
    for line in reversed(out.strip().splitlines()):
        if line.strip():
            tail = line.strip()[:70]
            break
    return (name, proc.returncode, time.monotonic() - t0, tail)


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for name, why in CHECKS:
            print(f"{name:<32} {why}")
        return 0

    verbose = "--verbose" in argv or "-v" in argv
    print("=" * 74)
    print("  ISOLATION GATE — connected where intended, isolated everywhere else")
    print(f"  {len(CHECKS)} checks over pads, holes, layers and zones")
    print("=" * 74)

    failed, missing = [], []
    total = 0.0
    for name, why in CHECKS:
        n, rc, secs, tail = run(name, verbose)
        total += secs
        if rc == 127:
            missing.append(n)
            mark = "MISS"
        elif rc == 0:
            mark = "PASS"
        else:
            failed.append(n)
            mark = "FAIL"
        print(f"  [{mark}] {n:<32} {secs:5.2f}s  {why}")
        if rc not in (0, 127) and not verbose:
            print(f"         -> {tail}")

    print("-" * 74)
    print(f"  {len(CHECKS) - len(failed) - len(missing)} passed, "
          f"{len(failed)} failed, {len(missing)} missing  ({total:.1f}s)")

    if missing:
        # A check that vanished is a silent loss of coverage, so it fails the
        # gate rather than being skipped.
        print(f"\n  MISSING: {', '.join(missing)}")
        print("  A check that disappeared is lost coverage, not a pass.")
    if failed:
        print(f"\n  FAILED: {', '.join(failed)}")
        print("  Re-run the individual script for detail, or use --verbose.")
        print("  Something on the board is shorted, unconnected, or on the")
        print("  wrong layer. Do not commit and do not order.")
    if not failed and not missing:
        print("\n  Every net is one piece of copper, and nothing touches "
              "anything it should not.")
    return 1 if (failed or missing) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
