#!/usr/bin/env python3
"""Report which hardware gates are currently failing, at session start.

Why
---
Round 24 concluded that the problem was never a missing check — the repo
has 90+ — but that a gate which is habitually red stops being read, and
its next failure (a real one) reads as background noise. The same applies
across sessions: an open finding written into a report is invisible to
whoever opens the project tomorrow.

So this runs the gates that guard known-open work and states what is
red RIGHT NOW. It derives that by executing them, not from a hardcoded
list of "current problems" — when a gate is fixed this report goes quiet
on its own, and it can never claim something is broken that isn't, or
stay silent about something that broke since.

Wired as a SessionStart hook in .claude/settings.json, so its output is
injected into context at the start of every session. Also runnable by
hand: `make open-issues`.

Usage:
    python3 scripts/open_issues_report.py            # hook JSON on stdout
    python3 scripts/open_issues_report.py --text     # plain text
"""
import concurrent.futures
import json
import os
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Gates that guard known-open hardware work. Each entry is
# (script, one-line meaning when it fails).
#
# Keep this to fast, self-contained gates — it runs at every session
# start. `make verify-all` remains the exhaustive suite.
GATES = [
    ("verify_dangling_copper",
     "copper that ends in the air (no pad/via/junction/zone)"),
    ("verify_schematic_pin_connectivity",
     "symbol pins with no wire, label or junction on them"),
    ("verify_netlist_diff",
     "schematic and PCB disagree on where a pin connects"),
    ("verify_net_class_widths",
     "traces narrower than their net class allows"),
    ("verify_cpl_rotation_law",
     "CPL angle disagrees with the rotation law for that layer"),
    ("verify_netlist_vs_kicad",
     "our parser disagrees with KiCad's own IPC-D-356 netlist"),
    ("verify_strapping_pins",
     "a strapping pin is forced to the wrong boot state, or EN has no "
     "pull-up / RC delay on copper"),
    ("verify_claims_ledger",
     "a load-bearing design claim is stale (UNVERIFIED past its deadline) "
     "or carries a verdict without evidence"),
    ("verify_order_manifest",
     "the JLCPCB order fingerprint lags the files in release_jlcpcb/ — "
     "what gets uploaded is not what was verified"),
]

TIMEOUT_S = 30

# Per-gate cap on reported failing rows. This report is injected into every
# session's context, so one gate that fails on 200 rows must not crowd out the
# other five — but the cap ANNOUNCES what it hid (see run_gate), because a
# silent truncation reads as "that was the whole list".
MAX_DETAIL_ROWS = 12


def run_gate(entry):
    script, meaning = entry
    path = os.path.join(PROJECT_DIR, "scripts", f"{script}.py")
    if not os.path.exists(path):
        # A renamed or deleted gate must be loud, not silently skipped —
        # a check that vanished looks exactly like a check that passes.
        return script, meaning, "MISSING", ["script not found"]
    try:
        p = subprocess.run([sys.executable, path], cwd=PROJECT_DIR,
                           capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return script, meaning, "TIMEOUT", [f"exceeded {TIMEOUT_S}s"]
    if p.returncode == 0:
        return script, meaning, "PASS", []
    # EVERY line that names a failure, not just the first. Reporting one row
    # of a multi-row failure is its own way of going stale: verify_cpl_rotation_law
    # failed on U2 *and* J4 for months while this report named only U2, so the
    # second one was invisible to every session that read the injected context
    # and trusted it to be the whole list.
    detail = []
    for line in (p.stdout or "").splitlines():
        s = line.strip()
        if s.startswith("FAIL") or "  FAIL" in line:
            detail.append(s)
    if len(detail) > MAX_DETAIL_ROWS:
        hidden = len(detail) - MAX_DETAIL_ROWS
        detail = detail[:MAX_DETAIL_ROWS]
        detail.append(f"... and {hidden} more failing row(s) — run the script "
                      f"for the full list")
    return script, meaning, "FAIL", detail


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(GATES)) as ex:
        results = list(ex.map(run_gate, GATES))

    bad = [r for r in results if r[2] != "PASS"]

    if not bad:
        body = ("Hardware gates: all clear. Every gate in "
                "scripts/open_issues_report.py::GATES passes.")
    else:
        lines = [
            f"Hardware gates: {len(bad)} of {len(results)} FAILING. "
            f"These are known-open items, not fresh news — but do not "
            f"treat them as background noise: if you touch the PCB, "
            f"schematic or CPL, re-run them and make sure YOUR change "
            f"did not add to the list.",
            "",
        ]
        for script, meaning, status, detail in bad:
            lines.append(f"  [{status}] {script} — {meaning}")
            for row in detail:
                lines.append(f"           {row[:150]}")
        lines += [
            "",
            "  Detail: `make verify-all`, or run any script above directly.",
            "  What each one means, and what must NOT be 'fixed': "
            "docs/known-issues.md.",
            "  Findings and root causes: hardware-audit-bugs.md "
            "(Round 24 section).",
            "  Visual: website/static/net-explorer.html "
            "(`make net-explorer` regenerates its data).",
        ]
        body = "\n".join(lines)

    if "--text" in sys.argv:
        print(body)
        return 1 if bad else 0

    json.dump({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": body,
    }}, sys.stdout)
    print()
    # A SessionStart hook must never block the session on a red gate.
    return 0


if __name__ == "__main__":
    sys.exit(main())
