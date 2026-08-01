#!/usr/bin/env python3
"""Turn failing hardware gates into briefings addressed to a named agent.

Why
---
The repo has 65 gates and they already know what is wrong. What was
missing is the step after: a red gate is a paragraph of console text
that nobody owns. `open_issues_report.py` made the reds visible at
session start; this makes them *assignable* — one finding, one owner,
one reproduction command, one mandate.

Three rules hold this together, and each exists because the opposite
already failed here at least once:

1. The gate list is READ FROM THE MAKEFILE, never copied. A second list
   of "the checks we care about" drifts from `verify-all` the first time
   someone adds a gate, and the drift is invisible — the dispatcher would
   just quietly stop dispatching the new one.

2. Routing is a derived law plus declared exceptions, not a 65-row
   table. A table has to be edited for every new gate, and an unedited
   table silently mis-routes. The law derives the owner from what the
   gate's name says it inspects, prints WHICH rule fired for every
   finding, and an exception must state why it is not the default.

3. A failing gate that matches no rule is a HARD ERROR. There is no
   catch-all owner. A catch-all would turn "nobody thought about where
   this goes" into "assigned to the PCB engineer", which reads as a
   decision when it is an omission.

Output
------
  .claude/issues/issues.json   machine-readable findings
  .claude/issues/<gate>.md     one briefing per failing gate

Usage
-----
    python3 scripts/issue_dispatch.py             # run gates, write briefings
    python3 scripts/issue_dispatch.py --fast      # only the open_issues gates
    python3 scripts/issue_dispatch.py --json      # findings on stdout, no files
"""
import concurrent.futures
import json
import os
import re
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAKEFILE = os.path.join(PROJECT_DIR, "Makefile")
OUT_DIR = os.path.join(PROJECT_DIR, ".claude/issues")

TIMEOUT_S = 120
EVIDENCE_LINES = 40

# An agent's answer to a work order. Written by the agent, never by this
# script, and never deleted by it.
PROPOSAL_SUFFIX = ".proposal.md"


# ── the gate list, derived ───────────────────────────────────────────

def gates_from_makefile():
    """The exact set `make verify-all` runs — parsed, not duplicated.

    Reads the `VERIFY_ALL_SCRIPTS = a \\ b \\ c` block. If the variable
    ever disappears or is renamed, this raises instead of returning an
    empty set: dispatching zero gates and dispatching a healthy board
    look identical from the outside, and only one of them is good news.
    """
    text = open(MAKEFILE).read()
    m = re.search(r"^VERIFY_ALL_SCRIPTS\s*=\s*((?:.*\\\n)*.*)$",
                  text, re.MULTILINE)
    if not m:
        raise SystemExit(
            "issue_dispatch: VERIFY_ALL_SCRIPTS not found in the Makefile. "
            "The gate list moved — fix this parser, do not fall back to a "
            "hardcoded list.")
    names = [w for w in m.group(1).replace("\\", " ").split() if w]
    if not names:
        raise SystemExit("issue_dispatch: VERIFY_ALL_SCRIPTS parsed empty.")
    return names


def fast_gates():
    """The session-start subset, so `--fast` and the hook agree by import."""
    sys.path.insert(0, os.path.join(PROJECT_DIR, "scripts"))
    import open_issues_report
    return [g[0] for g in open_issues_report.GATES]


# ── the routing law ──────────────────────────────────────────────────
#
# Ordered rules. The FIRST whose keyword appears in the gate name wins,
# so the more specific domains are listed first. Each rule names the
# owning agent, the skill that agent should open, and the severity that
# domain carries.
#
# severity is about consequence, not effort:
#   blind-spot  the verification machinery itself is broken, so every
#               other verdict on this page is untrustworthy — it outranks
#               a dead board because you cannot even tell if the board is
#               dead while it is red
#   dead-board  the board does not work, or is assembled wrong
#   degraded    it works but out of spec (margin, heat, EMC)
#   cosmetic    documentation and rendering only
ROUTING_LAW = [
    # (keyword, domain, agent, skill, severity, why this severity)
    ("dispatch",   "verification tooling",    "software-dev", "/check",
     "blind-spot", "while the dispatcher is wrong, findings are going "
                   "unassigned and nobody can tell which"),
    ("coverage",   "verification tooling",    "software-dev", "/check",
     "blind-spot", "while the coverage auditor is broken, nobody can say "
                   "which bug classes the gate network actually catches"),
    # The Virtual Bench measures its own coverage against a corpus of this
    # board's real historical bugs (docs/archived/virtual-bench-plan.md, T5.1). When
    # it goes red, either a model has drifted from its datasheet or the
    # bench has stopped rediscovering a bug it used to catch — and in the
    # second case every "no problem found" it prints is worth less than it
    # looks. That is a blind spot, not a degraded board. Placed above the
    # domain keywords so a bench gate is never claimed by "netlist" or
    # "thermal" just because its name contains one.
    ("vbench",     "virtual bench",           "pcb-engineer", "/hardware-audit",
     "blind-spot", "the bench's own coverage is what makes its silence "
                   "meaningful; while it is red, a clean bench report proves "
                   "less than it appears to"),
    # The bring-up firmware is the only instrument the bench has. Stale
    # against board_config.h, it measures pins the board does not have —
    # its PASS lines and its FAIL lines are equally about a fiction, so
    # a red here poisons first-power-on telemetry, not the board.
    ("bringup",    "bring-up telemetry",      "software-dev", "/hardware-test-gen",
     "blind-spot", "while the bring-up firmware lags board_config.h, every "
                   "verdict it prints is about a board that does not exist"),
    ("context",    "agent context",           "software-dev", "/context-engineering",
     "blind-spot", "a bloated preamble or an exposed token landmine degrades "
                   "every session before its first question"),
    ("memory",     "agent context",           "software-dev", "/context-engineering",
     "blind-spot", "the memory preamble is loaded before every question, so a "
                   "wrong claim in it outranks the derived truth for the whole "
                   "session"),
    # A load-bearing claim ("the shell is isolated", "the module has the
    # pull-up") is what every geometric gate checks the board AGAINST.
    # While one is stale or evidence-free, a green suite proves the board
    # matches the declaration — not that the declaration is true. That is
    # the R25 failure mode, and it is a blind spot, not a broken board.
    ("claims",     "design assumptions",      "pcb-engineer", "/datasheet-verify",
     "blind-spot", "gates check the board against declarations; while a "
                   "load-bearing claim is unverified past its deadline, every "
                   "green that rests on it is unproven"),
    ("manifest",   "release integrity",       "pcb-engineer", "/release",
     "dead-board", "what was verified and what the fab receives can differ; "
                   "a stale order fingerprint is how a fixed bug gets "
                   "fabricated anyway"),
    ("netlist",    "schematic/PCB agreement", "pcb-engineer", "/pcb-schematic",
     "dead-board", "a pin wired to the wrong net is a wrong board"),
    ("schematic",  "schematic",               "pcb-engineer", "/pcb-schematic",
     "dead-board", "the schematic is the netlist source of truth"),
    ("firmware",   "firmware",                "software-dev", "/firmware-sync",
     "dead-board", "firmware driving the wrong pin cannot be fixed in the field"),
    ("gpio",       "firmware",                "software-dev", "/firmware-sync",
     "dead-board", "firmware driving the wrong pin cannot be fixed in the field"),
    ("rotation",   "assembly (CPL)",          "pcb-engineer", "/fix-rotation",
     "dead-board", "a part placed at the wrong angle is soldered wrong"),
    ("polarity",   "assembly (CPL)",          "pcb-engineer", "/fix-rotation",
     "dead-board", "reversed polarity destroys the part on power-up"),
    ("cpl",        "assembly (CPL)",          "pcb-engineer", "/fix-rotation",
     "dead-board", "the CPL is what the pick-and-place actually obeys"),
    ("bom",        "assembly (BOM)",          "pcb-engineer", "/jlcpcb-parts",
     "dead-board", "the wrong part number is the wrong board"),
    ("connectivity", "copper connectivity",   "pcb-engineer", "/pcb-routing",
     "dead-board", "a net that is not one piece of copper is an open circuit"),
    ("dangling",   "copper connectivity",     "pcb-engineer", "/pcb-routing",
     "dead-board", "copper ending in air is either a missed link or debris"),
    ("isolation",  "copper isolation",        "pcb-engineer", "/isolation-check",
     "dead-board", "a short is the one defect that cannot be reworked out"),
    ("short",      "copper isolation",        "pcb-engineer", "/isolation-check",
     "dead-board", "a short is the one defect that cannot be reworked out"),
    ("clearance",  "copper isolation",        "pcb-engineer", "/isolation-check",
     "dead-board", "sub-clearance copper shorts at the fab, not on the bench"),
    ("power",      "power integrity",         "pcb-engineer", "/pcb-routing",
     "dead-board", "a split power net powers half a board"),
    ("zone",       "copper pour",             "pcb-engineer", "/pcb-routing",
     "dead-board", "a mis-poured plane is a silent open or a silent short"),
    ("jlcpcb",     "manufacturability",       "pcb-engineer", "/jlcpcb-check",
     "dead-board", "the fab rejects or silently 'corrects' the design"),
    ("drill",      "manufacturability",       "pcb-engineer", "/jlcpcb-check",
     "dead-board", "an out-of-range hole is re-drilled by the fab to suit"),
    ("gerber",     "manufacturability",       "pcb-engineer", "/jlcpcb-validate",
     "dead-board", "the gerbers are the only file the fab reads"),
    ("dfa",        "assembly process",        "pcb-engineer", "/dfm-fix",
     "dead-board", "assembly defects are found after the money is spent"),
    ("dfm",        "manufacturability",       "pcb-engineer", "/dfm-fix",
     "dead-board", "the yield loss lands on every unit, not one"),
    ("stencil",    "assembly process",        "pcb-engineer", "/dfm-fix",
     "degraded",  "aperture ratio shifts paste volume, not net topology"),
    ("width",      "trace sizing",            "pcb-engineer", "/pcb-routing",
     "degraded",  "an undersized trace carries current, just hotter"),
    ("thermal",    "thermal",                 "pcb-engineer", "/pcb-optimize",
     "degraded",  "heat shortens life before it stops function"),
    ("impedance",  "signal integrity",        "pcb-engineer", "/pcb-optimize",
     "degraded",  "impedance error degrades margin, not connectivity"),
    ("resonance",  "signal integrity",        "pcb-engineer", "/pcb-optimize",
     "degraded",  "a resonance is a margin problem"),
    ("return_path", "return path",            "pcb-engineer", "/pcb-routing",
     "degraded",  "a broken return path costs margin and radiates; the "
                  "signal still arrives"),
    ("ground",     "grounding",               "pcb-engineer", "/pcb-routing",
     "degraded",  "a ground loop couples noise, it does not open the circuit"),
    ("crossing",   "layout legibility",       "pcb-engineer", "/pcb-routing",
     "degraded",  "crossings mislead the reader before they break the board"),
    ("antenna",    "RF",                      "pcb-engineer", "/pcb-optimize",
     "degraded",  "keepout violations cost range, not boot"),
    ("esd",        "protection",              "pcb-engineer", "/electrical-review",
     "degraded",  "missing protection fails in the field, not on the bench"),
    ("enclosure",  "mechanical fit",          "cad-engineer", "/enclosure-design",
     "degraded",  "a shell that does not fit the board is discovered after "
                  "printing, not before"),
    ("balance",    "fabrication",             "pcb-engineer", "/dfm-fix",
     "degraded",  "copper imbalance warps the panel"),
    ("stackup",    "fabrication",             "pcb-engineer", "/dfm-fix",
     "degraded",  "the stackup sets impedance and thickness"),
    ("datasheet",  "part correctness",        "pcb-engineer", "/datasheet-verify",
     "dead-board", "a footprint that disagrees with the datasheet is wrong copper"),
    ("decoupling", "power integrity",         "pcb-engineer", "/electrical-review",
     "degraded",  "poor decoupling shows up as instability under load"),
    ("strapping",  "boot configuration",      "pcb-engineer", "/electrical-review",
     "dead-board", "a wrong strapping pin stops the chip from booting"),
    ("test_point", "bring-up",                "pcb-engineer", "/pcb-review",
     "degraded",  "missing test points cost debugging time, not function"),
    ("explorer",   "documentation",           "software-dev", "/website-dev",
     "cosmetic",  "stale explorer data misleads the reader only"),
    ("design_intent", "design intent",        "pcb-engineer", "/design-intent",
     "dead-board", "the board no longer matches what it was specified to be"),
    ("signal_chain",  "signal path",          "pcb-engineer", "/electrical-review",
     "dead-board", "a broken chain means no audio, no video, no input"),
    ("component",  "placement",               "pcb-engineer", "/pcb-components",
     "dead-board", "an unplaced or unconnected part does nothing"),
    ("pad",        "pad geometry",            "pcb-engineer", "/pad-analysis",
     "dead-board", "pad geometry decides whether the joint forms at all"),
    ("via",        "via rules",               "pcb-engineer", "/jlcpcb-check",
     "dead-board", "an illegal via is drilled wrong or not at all"),
    ("trace",      "routing",                 "pcb-engineer", "/pcb-routing",
     "dead-board", "a trace through a pad is a short waiting to happen"),
    ("drc",        "KiCad DRC",               "pcb-engineer", "/drc-audit",
     "dead-board", "DRC is the last automated word on the copper"),
    ("erc",        "KiCad ERC",               "pcb-engineer", "/pcb-schematic",
     "dead-board", "ERC is the last automated word on the schematic"),
    ("simulate",   "simulation",              "pcb-engineer", "/electrical-review",
     "degraded",  "a failing sim predicts a margin problem"),
    ("battery",    "protection",              "pcb-engineer", "/electrical-review",
     "dead-board", "unprotected lithium is a safety defect"),
    ("easyeda",    "part correctness",        "pcb-engineer", "/datasheet-verify",
     "dead-board", "a wrong pin-1 reference rotates the part on the panel"),
    ("sd_interface", "SD interface",          "pcb-engineer", "/electrical-review",
     "dead-board", "no SD card means no ROMs"),
    ("distances",  "pad geometry",            "pcb-engineer", "/pad-analysis",
     "dead-board", "pads too close bridge during reflow"),
]

# Exceptions to the law. Key = gate name, value = (agent, skill, severity,
# why the default rule is wrong for THIS gate). Empty is the honest state:
# add an entry only when a specific gate genuinely does not belong where
# its name puts it, and say why here rather than in a commit message.
ROUTING_EXCEPTIONS = {
    # The law's "manifest" keyword would give this mutation suite the
    # dead-board severity of the gate it tests. A red mutation suite does
    # not mean the release drifted — it means the manifest gate itself can
    # no longer be trusted to notice drift, which is a tooling blind spot,
    # same as test_issue_dispatch (which the "dispatch" keyword happens to
    # classify correctly by accident of naming).
    "test_order_manifest": (
        "software-dev", "/check", "blind-spot",
        "while the manifest gate's own tests are red, its PASS verdicts on "
        "release integrity are untrustworthy"),
    # Same shape: the "enclosure" keyword would hand this mutation suite
    # the cad-engineer and a degraded severity, but a red mutation suite
    # means the SYNC GATE can no longer be trusted, not that the shell
    # drifted — a tooling blind spot.
    "test_enclosure_sync": (
        "software-dev", "/check", "blind-spot",
        "while the enclosure-sync gate's own tests are red, its PASS "
        "verdicts on mechanical fit are untrustworthy"),
    # The "test_point" keyword would hand this suite the degraded severity
    # of the gate it tests; a red mutation suite is a tooling blind spot.
    "test_test_points": (
        "software-dev", "/check", "blind-spot",
        "while the test-point gate's own tests are red, its verdicts on "
        "probe access are untrustworthy"),
    # The "esd" keyword would hand this suite the degraded severity of
    # the gate it tests; a red mutation suite is a tooling blind spot.
    "test_esd_protection": (
        "software-dev", "/check", "blind-spot",
        "while the ESD gate's own tests are red, its verdicts on "
        "protection presence are untrustworthy"),
    # The "power" keyword would rank this dead-board, but an undersized
    # via transition carries the current — hotter, with less margin —
    # rather than opening the net: same class as law:width (Decision D2
    # of docs/gate-coverage-expansion-plan.md).
    "verify_power_via_ampacity": (
        "pcb-engineer", "/pcb-routing", "degraded",
        "a starved layer transition runs hot and ages the barrel; it "
        "degrades margin before it kills the board"),
    # And its mutation suite is a tooling blind spot, like the others.
    "test_power_via_ampacity": (
        "software-dev", "/check", "blind-spot",
        "while the ampacity gate's own tests are red, its verdicts on "
        "via sizing are untrustworthy"),
}


def route(gate):
    """Owner, skill and severity for a gate — with the reason it got them.

    Returns a dict, or None when nothing matches. None is deliberately
    not a default: the caller turns it into a hard error.
    """
    if gate in ROUTING_EXCEPTIONS:
        agent, skill, severity, why = ROUTING_EXCEPTIONS[gate]
        return {"agent": agent, "skill": skill, "severity": severity,
                "domain": "declared exception", "decidedBy": f"exception:{gate}",
                "severityWhy": why}
    name = gate.lower()
    for keyword, domain, agent, skill, severity, why in ROUTING_LAW:
        if keyword in name:
            return {"agent": agent, "skill": skill, "severity": severity,
                    "domain": domain, "decidedBy": f"law:{keyword}",
                    "severityWhy": why}
    return None


# ── running the gates ────────────────────────────────────────────────

def run_gate(gate):
    path = os.path.join(PROJECT_DIR, "scripts", f"{gate}.py")
    if not os.path.exists(path):
        return {"gate": gate, "status": "MISSING", "rc": None,
                "log": f"scripts/{gate}.py does not exist"}
    try:
        p = subprocess.run([sys.executable, path], cwd=PROJECT_DIR,
                           capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"gate": gate, "status": "TIMEOUT", "rc": None,
                "log": f"exceeded {TIMEOUT_S}s"}
    out = (p.stdout or "") + (p.stderr or "")
    return {"gate": gate, "status": "PASS" if p.returncode == 0 else "FAIL",
            "rc": p.returncode, "log": out}


def evidence(log):
    """The lines that actually name the failure, not the whole transcript.

    Prefers explicit FAIL lines; falls back to the tail, because a gate
    that crashed has no FAIL line and its traceback is the evidence.
    """
    fails = [l.rstrip() for l in log.splitlines()
             if l.strip().startswith("FAIL") or "  FAIL" in l
             or l.strip().startswith("->")]
    if fails:
        return fails[:EVIDENCE_LINES]
    return [l.rstrip() for l in log.splitlines() if l.strip()][-EVIDENCE_LINES:]


SEVERITY_ORDER = {"blind-spot": 0, "dead-board": 1, "degraded": 2,
                  "cosmetic": 3}


def briefing(f):
    """The markdown an agent is handed. It is a work order, not a report."""
    ev = "\n".join(f["evidence"])
    return f"""# {f['gate']} — FAILING

**Owner:** `{f['agent']}`  ·  **Skill to open:** `{f['skill']}`
**Domain:** {f['domain']}  ·  **Severity:** {f['severity']} — {f['severityWhy']}
**Routed by:** {f['decidedBy']}  ·  **Gate exit code:** {f['rc']}

## Mandate

Diagnose and PROPOSE. Do not edit `hardware/`, `release_jlcpcb/`, the CPL
or the schematic sources in this pass. The user approves before anything
is applied.

Deliver:
1. **Root cause** — the specific line of the generator, footprint or
   schematic source that produces this, quoted with its path and line.
2. **Why the gate is right** — or, if you believe the gate is wrong,
   the physical evidence that it is (a datasheet page, a prototype
   observation). "The gate is a false positive" without evidence is not
   an acceptable answer in this repo.
3. **The proposed change** — as a diff or an exact edit description.
4. **Blast radius** — what else this touches: CPL, gerbers, firmware
   `board_config.h`, docs, `release_jlcpcb/`.
5. **How the fix is proven** — the command that goes from red to green.

## Reproduce

```bash
python3 scripts/{f['gate']}.py
```

## Evidence

```
{ev}
```

## Context

- Visual: `website/static/net-explorer.html` — per-pin copper, dangling
  ends and the clearance map for this board.
- Full suite: `make verify-all` ({f['suiteSize']} gates).
- Current reds: `make open-issues`.
"""


def main():
    fast = "--fast" in sys.argv
    json_only = "--json" in sys.argv

    gates = fast_gates() if fast else gates_from_makefile()

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(run_gate, gates))

    bad = [r for r in results if r["status"] != "PASS"]

    findings, unrouted = [], []
    for r in bad:
        rt = route(r["gate"])
        if rt is None:
            unrouted.append(r["gate"])
            continue
        findings.append({
            "gate": r["gate"],
            "status": r["status"],
            "rc": r["rc"],
            "evidence": evidence(r["log"]),
            "suiteSize": len(gates),
            **rt,
        })

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9),
                                 f["gate"]))

    payload = {
        "suite": "fast" if fast else "verify-all",
        "gatesRun": len(gates),
        "passed": len(gates) - len(bad),
        "findings": findings,
    }

    if json_only:
        json.dump(payload, sys.stdout, indent=2)
        print()
    else:
        os.makedirs(OUT_DIR, exist_ok=True)
        # Briefings are derived state: clear the stale ones, or a gate
        # that went green leaves a work order lying around for a problem
        # that no longer exists.
        #
        # `*.proposal.md` is NOT derived state — it is an agent's analysis,
        # the expensive half of this loop, and it is not reproducible by
        # re-running anything. A blanket "delete every .md" wiped those on
        # the next dispatch, which is how you lose the only copy of the
        # work you asked for.
        for old in os.listdir(OUT_DIR):
            if old.endswith(PROPOSAL_SUFFIX):
                continue
            if old.endswith(".md") or old == "issues.json":
                os.remove(os.path.join(OUT_DIR, old))
        with open(os.path.join(OUT_DIR, "issues.json"), "w") as fh:
            json.dump(payload, fh, indent=2)
        for f in findings:
            with open(os.path.join(OUT_DIR, f"{f['gate']}.md"), "w") as fh:
                fh.write(briefing(f))

        rel = os.path.relpath(OUT_DIR, PROJECT_DIR)
        print(f"Gates: {payload['passed']}/{payload['gatesRun']} passing")
        if findings:
            print(f"\n{len(findings)} finding(s) dispatched -> {rel}/\n")
            width = max(len(f["gate"]) for f in findings)
            for f in findings:
                print(f"  [{f['severity']:<10}] {f['gate']:<{width}}  "
                      f"-> {f['agent']:<13} {f['skill']:<20} ({f['decidedBy']})")
        else:
            print("\nNothing to dispatch — every gate is green.")

        # Proposals whose gate has since gone green.
        #
        # These are deliberately NOT deleted (see the note above: an agent's
        # analysis is the expensive half of this loop and re-running nothing
        # reproduces it). But a directory whose whole purpose is "what needs
        # working on" was left holding five detailed write-ups of problems that
        # had all been fixed — verify_cpl_rotation_law, verify_dangling_copper,
        # verify_net_class_widths, verify_netlist_diff and
        # verify_schematic_pin_connectivity, every one describing a gate that now
        # passes. Anyone opening the directory reads five open problems. Keeping
        # them silently is how a closed finding gets re-investigated; saying so
        # costs one line.
        failing = {f["gate"] for f in findings}
        resolved = sorted(
            old[: -len(PROPOSAL_SUFFIX)]
            for old in os.listdir(OUT_DIR)
            if old.endswith(PROPOSAL_SUFFIX)
            and old[: -len(PROPOSAL_SUFFIX)] not in failing
        )
        if resolved:
            print(f"\n{len(resolved)} proposal(s) kept for gates that now PASS "
                  f"— analysis, not open work:")
            for gate in resolved:
                print(f"  {rel}/{gate}{PROPOSAL_SUFFIX}")
            print("  Delete each once its reasoning is recorded in "
                  "docs/known-issues.md or hardware-audit-bugs.md.")

    if unrouted:
        print(f"\nUNROUTED ({len(unrouted)}): "
              f"{' '.join(unrouted)}", file=sys.stderr)
        print("These gates failed and the routing law does not cover them. "
              "Add a keyword rule or a declared exception in "
              "scripts/issue_dispatch.py — there is no default owner on "
              "purpose.", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
