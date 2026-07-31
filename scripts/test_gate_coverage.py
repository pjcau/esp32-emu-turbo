#!/usr/bin/env python3
"""Mutation tests for verify_gate_coverage.py — the auditor must itself
be able to fail.

A coverage audit that cannot report a blind spot is worse than no audit:
it stamps "9/9 caught" on a gate network it never actually questioned. So:

    T1  a mutation that matches nothing raises Fatal (a fault that did not
        apply must never count as caught)
    T2  zone deletion removes exactly the requested net's zone
    T3  verify_gate_coverage is NOT in VERIFY_ALL_SCRIPTS (it runs the
        whole suite per fault — inclusion would recurse)
    T4  every fault's target files exist and fault names are unique
    T5  with run_gates stubbed to "everything stays green", the audit
        reports every fault as a blind spot and exits 1 — the failure
        path is real, not decorative
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_gate_coverage as vgc  # noqa: E402
from issue_dispatch import gates_from_makefile  # noqa: E402

BASE = Path(__file__).resolve().parent.parent


def main() -> int:
    print("=" * 72)
    print("GATE-COVERAGE AUDITOR MUTATION SUITE")
    print("=" * 72)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    # T1: no-match mutation is a structural error, never a silent pass
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
        tf.write("nothing to see here\n")
        scratch = Path(tf.name)
    try:
        vgc._sub(scratch, r"^does-not-exist$", "x")
        check("T1 unapplied mutation raises Fatal", False, "no error raised")
    except vgc.Fatal:
        check("T1 unapplied mutation raises Fatal", True)
    finally:
        scratch.unlink()

    # T2: zone deletion is surgical — net 3 goes, net 7 stays
    text = ('(kicad_pcb\n'
            '  (zone (net 3) (polygon (pts (xy 0 0) (xy 1 1))))\n'
            '  (zone (net 7) (polygon (pts (xy 2 2) (xy 3 3))))\n'
            ')\n')
    with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb",
                                     delete=False) as tf:
        tf.write(text)
        board = Path(tf.name)
    try:
        removed = vgc._delete_zone_of_net(board, 3)
        after = board.read_text()
        check("T2 zone deletion is surgical",
              removed == 1 and "(net 3)" not in after and "(net 7)" in after)
    finally:
        board.unlink()

    # T3: the audit must never audit itself from inside verify-all
    gates = gates_from_makefile()
    check("T3 audit not in VERIFY_ALL_SCRIPTS",
          "verify_gate_coverage" not in gates,
          f"{len(gates)} gates parsed")

    # T4: fault definitions stay applicable as the repo evolves
    names = [f[0] for f in vgc.FAULTS]
    missing = [p for f in vgc.FAULTS for p in f[2] if not (BASE / p).exists()]
    check("T4 fault targets exist, names unique",
          len(set(names)) == len(names) and not missing,
          f"missing: {missing}" if missing else f"{len(names)} faults")

    # T5: if no gate ever objects, the audit must say BLIND SPOT and fail —
    # stub the runner so both baseline and post-fault runs are all green
    real_run = vgc.run_gates
    real_argv = sys.argv[:]
    try:
        vgc.run_gates = lambda sandbox, gs: {g: 0 for g in gs}
        rc = vgc.main()
        check("T5 all-green stub yields exit 1 (blind spots reported)",
              rc == 1, f"rc={rc}")
    finally:
        vgc.run_gates = real_run
        sys.argv = real_argv

    print("-" * 72)
    if failures:
        print(f"Results: FAIL — {len(failures)} check(s): "
              f"{', '.join(failures)}")
        return 1
    print("Results: PASS — 5/5 auditor mutations detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
