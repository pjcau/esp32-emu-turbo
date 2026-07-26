#!/usr/bin/env python3
"""Gate on the context budget: fail when the repo's per-session cost regresses.

Why this exists
---------------
`make context-budget` MEASURES what the repo costs a context window, but a
measurement nobody is forced to look at is a dashboard, not a gate — and the
repo has already paid for that difference once: `.claudeheavy` silently lost
its `hardware-audit-bugs.md` entry in a merge, re-exposing a 47k-token
landmine, and nothing went red. This gate makes that class of regression
loud.

Ceilings, and why these numbers
-------------------------------
Measured 2026-07-26 after the cleanup that introduced this gate:

    M1 preamble        ~6.0k tok   (MEMORY.md 1.9k + CLAUDE.md 2.0k + skills 1.4k)
    M2 exposed         ~126.5k tok (routing.py 88k + verify_dfm_v2.py 38.5k —
                                    both actively edited, so not blockable)

The ceilings sit above the measured values by enough margin that ordinary
drift (a new memory line, a new gate's docstring) never fires them, and a
REGRESSION always does:

  * M1 > 8k  ≈ someone pasted a table or a changelog into the preamble.
  * M2 > 150k ≈ a .claudeheavy entry was lost, or a new giant file appeared
    outside the blocklists (the .erc-report.json alone was 103k).

Raising a ceiling is allowed — with a sentence here saying what grew and why
it should. Raising it to silence the gate is the failure mode this repo
documents in feedback_never_silence_errors.

Usage:
    python3 scripts/verify_context_budget.py     # exit 1 on breach
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import context_budget  # noqa: E402

M1_CEILING_TOK = 8_000
M2_CEILING_TOK = 150_000


def main() -> int:
    m1 = context_budget.m1_preamble()
    m2 = context_budget.m2_landmines()

    m1_total = m1["total"]
    m2_exposed = m2["exposed_total"]

    ok = True
    print("── Context budget gate ──")

    status = "PASS" if m1_total <= M1_CEILING_TOK else "FAIL"
    if status == "FAIL":
        ok = False
    print(f"  {status}  M1 preamble {m1_total:,} tok <= {M1_CEILING_TOK:,}")
    if status == "FAIL":
        for name, tok_n in sorted(m1["parts"].items(), key=lambda x: -x[1]):
            print(f"          {tok_n:>7,}  {name}")

    status = "PASS" if m2_exposed <= M2_CEILING_TOK else "FAIL"
    if status == "FAIL":
        ok = False
    print(f"  {status}  M2 exposed landmines {m2_exposed:,} tok <= {M2_CEILING_TOK:,}")
    if status == "FAIL":
        print("          a .claudeheavy/.claudeignore entry was probably lost,"
              " or a new giant file appeared:")
        for tok_n, name in m2["worst"][:6]:
            print(f"          {tok_n:>7,}  {name}")

    print(f"\nResults: {'2 passed, 0 failed' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
