#!/usr/bin/env python3
"""Mutation tests for verify_claims_ledger.py — the ledger gate must be
able to fail.

A claims gate that passes on a stale or evidence-free claim recreates
the exact failure it exists to contain: a confident declaration nobody
re-checks. So:

    T1  a well-formed ledger with a fresh UNVERIFIED claim passes
    T2  an UNVERIFIED claim older than MAX_AGE_DAYS is red
    T3  an unknown status is red
    T4  a VERIFIED claim with `evidence: none` is red
    T5  duplicate claim ids are red
    T6  an empty or missing ledger is red — zero claims must never read
        as zero problems
    T7  a claim missing a required field is red
    T8  the REAL hardware/CLAIMS.md passes today
    T9  the gate is in VERIFY_ALL_SCRIPTS and the dispatch law routes it
"""
from __future__ import annotations

import datetime
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import verify_claims_ledger as vcl  # noqa: E402
from issue_dispatch import gates_from_makefile, route  # noqa: E402

TODAY = datetime.date(2026, 8, 1)


def claim(cid="CLAIM-001", status="UNVERIFIED", declared="2026-07-31",
          evidence="none"):
    return (f"## {cid} — a test claim\n\n"
            f"- status: {status}\n"
            f"- declared: {declared}\n"
            f"- claim: something load-bearing\n"
            f"- where: somewhere/file.py:1\n"
            f"- risk-if-false: something breaks\n"
            f"- evidence: {evidence}\n\n")


def run(text, today=TODAY):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as tf:
        tf.write("# ledger\n\n" + text)
        path = tf.name
    try:
        return vcl.check_ledger(path=path, today=today)
    finally:
        Path(path).unlink()


def main() -> int:
    print("=" * 72)
    print("CLAIMS-LEDGER MUTATION SUITE")
    print("=" * 72)
    failures = []

    def check(name, ok, why=""):
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              + (f" — {why}" if why else ""))
        if not ok:
            failures.append(name)

    check("T1 fresh UNVERIFIED claim passes", run(claim()) == 0)

    stale = (TODAY - datetime.timedelta(days=vcl.MAX_AGE_DAYS + 1)).isoformat()
    check("T2 stale UNVERIFIED claim is red",
          run(claim(declared=stale)) != 0)

    check("T3 unknown status is red",
          run(claim(status="PROBABLY-FINE")) != 0)

    check("T4 VERIFIED without evidence is red",
          run(claim(status="VERIFIED-ON-DATASHEET", evidence="none")) != 0)

    check("T5 duplicate ids are red",
          run(claim() + claim()) != 0)

    check("T6a empty ledger is red", run("") != 0)
    check("T6b missing ledger is red",
          vcl.check_ledger(path="/nonexistent/CLAIMS.md", today=TODAY) != 0)

    broken = claim().replace("- evidence: none\n", "")
    check("T7 missing required field is red", run(broken) != 0)

    check("T8 the real hardware/CLAIMS.md passes",
          vcl.check_ledger() == 0)

    gates = gates_from_makefile()
    check("T9a verify_claims_ledger in VERIFY_ALL_SCRIPTS",
          "verify_claims_ledger" in gates)
    check("T9b dispatch routes verify_claims_ledger",
          route("verify_claims_ledger") is not None)
    check("T9c dispatch routes test_claims_ledger",
          route("test_claims_ledger") is not None)

    print("=" * 72)
    if failures:
        print(f"FAIL — {len(failures)} test(s): {', '.join(failures)}")
        return 1
    print("PASS — the claims-ledger gate can fail, and does so for the "
          "right reasons")
    return 0


if __name__ == "__main__":
    sys.exit(main())
