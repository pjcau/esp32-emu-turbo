#!/usr/bin/env python3
"""Mutation tests for verify_esd_protection.py — the promoted gate must fail.

The old gate was a false-green (a global BOM OR let a data-line part
answer the VBUS question); the promoted one blocks on net-verified
evidence and defers its one heuristic to the claims ledger. Each verdict
class must be proven reachable:

    T1  U4 stripped from the BOM (no ESD parts at all)      -> exit 1
    T2  no CLAIMS.md entry covering the surge absence       -> exit 1
    T3  the covering claim FALSIFIED                        -> exit 1
    T4  the covering claim UNVERIFIED                       -> exit 0 + WARN
        (advisory — the ledger's own 45-day clock blocks instead)
    T5  the real board + real ledger at HEAD                -> exit 0
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_esd_protection as vesd  # noqa: E402


def run() -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            rc = vesd.analyze_esd_protection()
        except SystemExit as e:      # _fatal() path
            rc = e.code
    return rc, buf.getvalue()


def claims_stub(status: str | None) -> str:
    """A temp CLAIMS.md — with a covering entry in `status`, or none."""
    if status is None:
        return "# ledger\n\n## CLAIM-099 — unrelated\n- where: elsewhere\n"
    return ("# ledger\n\n## CLAIM-004 — VBUS surge TVS absence\n"
            f"- status: {status}\n"
            "- where: scripts/verify_esd_protection.py\n")


def main() -> int:
    print("=" * 72)
    print("ESD GATE MUTATION SUITE")
    print("=" * 72)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    real_bom = vesd._load_bom
    real_claims = vesd.CLAIMS_FILE

    # T1: no ESD part anywhere — every protection check loses its evidence
    try:
        vesd._load_bom = lambda: {r: c for r, c in real_bom().items()
                                  if r != "U4"}
        rc, _ = run()
        check("T1 U4 stripped from BOM exits 1", rc == 1, f"rc={rc}")
    finally:
        vesd._load_bom = real_bom

    # T2-T4: the surge verdict must come from the ledger, not the regex
    for name, status, want in [
            ("T2 no covering claim exits 1", None, 1),
            ("T3 FALSIFIED claim exits 1", "FALSIFIED", 1),
            ("T4 UNVERIFIED claim stays advisory", "UNVERIFIED", 0)]:
        with tempfile.NamedTemporaryFile("w", suffix=".md",
                                         delete=False) as tf:
            tf.write(claims_stub(status))
            tmp = tf.name
        try:
            vesd.CLAIMS_FILE = tmp
            rc, out = run()
            ok = rc == want
            if status == "UNVERIFIED":
                ok = ok and "WARN" in out
            check(name, ok, f"rc={rc}, want {want}")
        finally:
            vesd.CLAIMS_FILE = real_claims
            Path(tmp).unlink()

    # T5: the real board and the real ledger are green
    rc, _ = run()
    check("T5 real board + ledger passes", rc == 0, f"rc={rc}")

    print("-" * 72)
    if failures:
        print(f"Results: FAIL — {len(failures)} case(s): "
              f"{', '.join(failures)}")
        return 1
    print("Results: PASS — 5/5 gate mutations detected")
    return 0


if __name__ == "__main__":
    sys.exit(main())
