#!/usr/bin/env python3
"""Gate-coverage audit — inject known faults, demand the gate NETWORK object.

Every verifier in this repo proves (at best) that ITS assertion fires. None
of them answers the question that actually matters before an order: if a
bug of class X reached the artifacts today, would ANY gate go red? Round
after round, the painful findings were exactly the faults no gate owned —
the split +3V3 plane, the 180-degree CPL rotations, the stale release d356.

This script measures that directly:

    1. copy the working tree's artifacts into a sandbox (scripts, board,
       release dir, firmware, docs — everything the gates read),
    2. run the FULL verify-all gate list there once, unmutated: gates that
       already fail in the sandbox are environmental noise and are excluded
       from evidence (differential baseline),
    3. for each fault in FAULTS: mutate the sandbox artifacts the way a
       real historical bug would have, re-run every gate, and demand at
       least one baseline-green gate turns red,
    4. restore the touched files and move to the next fault.

The verdict per fault is CAUGHT (with the list of gates that fired — the
measured owners of that bug class) or BLIND SPOT. Any blind spot fails the
run: it means a bug class can reach the fab with every light green, and the
fix is a new gate, never a shrug.

The gate list is parsed from the Makefile via issue_dispatch.gates_from_
makefile() — the same single source verify-all uses. This script is NOT in
VERIFY_ALL_SCRIPTS: it runs the whole suite N+1 times (~3-5 minutes) and
belongs to release preparation (`make verify-gate-coverage`), not to every
edit.

Exit codes: 0 all faults caught · 1 blind spot(s) · 2 structural error
(sandbox broken, mutation did not apply, baseline too red to judge).
"""

from __future__ import annotations

import concurrent.futures
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# everything any verifier reads; missing pieces surface as baseline noise,
# which the differential handles, but keep this list honest anyway
SANDBOX_ITEMS = ["Makefile", "scripts", "hardware", "release_jlcpcb",
                 "software", "docs"]

BOARD = "hardware/kicad/esp32-emu-turbo.kicad_pcb"
BOM = "release_jlcpcb/bom.csv"
CPL = "release_jlcpcb/cpl.csv"
D356 = "release_jlcpcb/esp32-emu-turbo.d356"
FIRMWARE = "software/main/board_config.h"

# a fault whose mutation touches nothing is a lie, not a pass
class Fatal(RuntimeError):
    pass


def _sub(path: Path, pattern: str, repl, count=0, expect_min=1, flags=0):
    """Regex-edit a sandbox file and refuse to continue if nothing matched."""
    text = path.read_text()
    new, n = re.subn(pattern, repl, text, count=count, flags=flags)
    if n < expect_min:
        raise Fatal(f"mutation matched {n} time(s) (< {expect_min}) "
                    f"for {pattern!r} in {path.name}")
    path.write_text(new)
    return n


def _net_number(board_text: str, net_name: str) -> int:
    m = re.search(r'\(net (\d+) "%s"\)' % re.escape(net_name), board_text)
    if not m:
        raise Fatal(f"net {net_name!r} not found in board")
    return int(m.group(1))


def _delete_zone_of_net(path: Path, net_no: int) -> int:
    """Remove every top-level (zone ...) block carrying (net <net_no>)."""
    text = path.read_text()
    out, i, removed = [], 0, 0
    while True:
        j = text.find("(zone", i)
        if j < 0:
            out.append(text[i:])
            break
        depth, k = 0, j
        while k < len(text):
            if text[k] == "(":
                depth += 1
            elif text[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        block = text[j : k + 1]
        if re.search(r"\(net %d\)" % net_no, block):
            out.append(text[i:j])
            removed += 1
        else:
            out.append(text[i : k + 1])
        i = k + 1
    if not removed:
        raise Fatal(f"no zone with net {net_no} found")
    path.write_text("".join(out))
    return removed


# ------------------------------------------------------------------ faults
#
# Each entry: (name, historical bug class, files it touches, mutate(sandbox)).
# Every fault reproduces a REAL bug this project has already had once —
# the suite asks whether today's gates would have caught yesterday's bugs.

def f_plane_split(sb: Path):
    board = sb / BOARD
    n = _net_number(board.read_text(), "+3V3")
    removed = _delete_zone_of_net(board, n)
    return f"deleted {removed} +3V3 zone(s) — the R24 split-plane dead board"


def f_track_cut(sb: Path):
    board = sb / BOARD
    n = _net_number(board.read_text(), "VBUS")
    removed = _sub(board, r"^\s*\(segment .*\(net %d\).*\n" % n, "",
                   flags=re.MULTILINE)
    return f"deleted all {removed} VBUS segments — an unpoured net cut open"


def f_net_swap_short(sb: Path):
    board = sb / BOARD
    text = board.read_text()
    gnd = _net_number(text, "GND")
    v33 = _net_number(text, "+3V3")
    _sub(board,
         r"(\(segment .*\(net )%d(\).*)" % gnd,
         r"\g<1>%d\g<2>" % v33, count=1)
    return "relabeled one GND segment as +3V3 — copper of two nets touching"


def f_annular_collapse(sb: Path):
    board = sb / BOARD
    _sub(board,
         r"(\(via \(at [^)]+\) \(size )0\.9(\) \(drill )0\.35",
         r"\g<1>0.37\g<2>0.35", count=1)
    return "shrunk one via to size 0.37/drill 0.35 — 0.01 mm annular ring"


def f_cpl_rotation(sb: Path):
    _sub(sb / CPL, r"^(U2,IP5306,ESOP-8,[^,]+,[^,]+,)270(,Bottom)$",
         r"\g<1>0\g<2>", flags=re.MULTILINE)
    return "U2 CPL rotation 270 -> 0 — the pre-R25 IP5306 rotation bug"


def f_cpl_missing(sb: Path):
    _sub(sb / CPL, r"^U3,.*\n", "", flags=re.MULTILINE)
    return "removed U3 from the CPL — regulator on the BOM but never placed"


def f_bom_value(sb: Path):
    # R26 is the buck feedback divider's lower leg: Vout = 0.6*(1 + R25/R26),
    # so a wrong value here silently reprograms the 3V3 rail
    _sub(sb / BOM, r"^22k 0805,R26,", "47k 0805,R26,", count=1,
         flags=re.MULTILINE)
    return "R26 22k -> 47k in the BOM — the 3V3 rail silently reprogrammed"


def f_release_drift(sb: Path):
    d356 = sb / D356
    text = d356.read_text()
    # the net-name field is fixed-width (14 chars): GND+11 spaces becomes
    # +3V3+10 spaces so the column layout survives the relabeling
    new, n = re.subn(r"^317GND {11}", "317+3V3" + " " * 10,
                     text, count=5, flags=re.MULTILINE)
    if n < 5:
        raise Fatal(f"only {n} GND d356 records relabeled")
    d356.write_text(new)
    return "relabeled 5 GND e-test points as +3V3 — release netlist drift"


def f_firmware_desync(sb: Path):
    fw = sb / FIRMWARE
    m = re.search(r"BTN_R\s+GPIO_NUM_(\d+)", fw.read_text())
    if not m:
        raise Fatal("BTN_R GPIO define not found in board_config.h")
    old = int(m.group(1))
    _sub(fw, r"(BTN_R\s+GPIO_NUM_)%d\b" % old, r"\g<1>%d" % (old + 1),
         count=1)
    return f"BTN_R GPIO_NUM_{old} -> GPIO_NUM_{old + 1} — firmware desync"


FAULTS = [
    ("plane-split", "dead board: power plane fragmented", [BOARD], f_plane_split),
    ("track-cut", "dead board: power net cut open", [BOARD], f_track_cut),
    ("net-swap-short", "short: copper relabeled across nets", [BOARD], f_net_swap_short),
    ("annular-collapse", "fabrication: via annular ring below minimum", [BOARD], f_annular_collapse),
    ("cpl-rotation", "assembly: part rotated 270 degrees", [CPL], f_cpl_rotation),
    ("cpl-missing", "assembly: part missing from CPL", [CPL], f_cpl_missing),
    ("bom-designator", "sourcing: BOM row no longer matches the board", [BOM], f_bom_value),
    ("release-drift", "release: d356 disagrees with the gerbers", [D356], f_release_drift),
    ("firmware-desync", "cross-domain: GPIO map out of sync", [FIRMWARE], f_firmware_desync),
]


# ------------------------------------------------------------- gate running

def run_gates(sandbox: Path, gates):
    """Run every gate in the sandbox, return {gate: exit_code}."""
    # single-process cache warm first — 50 verifiers racing to rebuild
    # .pcb_cache.json at once is how you get a torn cache file
    subprocess.run(
        [sys.executable, "-c",
         "import sys; sys.path.insert(0, 'scripts'); "
         "import pcb_cache; pcb_cache.load_cache()"],
        cwd=sandbox, capture_output=True)

    env = dict(os.environ)
    env.setdefault("CLAUDE_MEMORY_DIR", str(
        Path.home() / ".claude" / "projects"
        / "-Users-pierrejonnycau-Documents-WORKS-esp32-emu-turbo" / "memory"))

    def one(gate):
        p = subprocess.run(
            [sys.executable, f"scripts/{gate}.py"],
            cwd=sandbox, env=env, capture_output=True, timeout=600)
        return gate, p.returncode

    results = {}
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(4, (os.cpu_count() or 8) - 2)) as pool:
        for gate, rc in pool.map(one, gates):
            results[gate] = rc
    return results


def main() -> int:
    print("=" * 72)
    print("GATE COVERAGE — inject the old bugs, demand the gates object")
    print("=" * 72)

    sys.path.insert(0, str(BASE / "scripts"))
    from issue_dispatch import gates_from_makefile

    gates = gates_from_makefile()
    if "verify_gate_coverage" in gates:
        raise Fatal("this audit must not be in VERIFY_ALL_SCRIPTS — it runs "
                    "the whole suite per fault and would recurse")

    tmp = Path(tempfile.mkdtemp(prefix="gate-coverage-"))
    try:
        print(f"  sandbox : {tmp}")
        for item in SANDBOX_ITEMS:
            src = BASE / item
            if not src.exists():
                raise Fatal(f"sandbox input missing: {item}")
            if src.is_dir():
                shutil.copytree(src, tmp / item, symlinks=True)
            else:
                shutil.copy2(src, tmp / item)

        print(f"  gates   : {len(gates)} (from Makefile VERIFY_ALL_SCRIPTS)")
        print("-" * 72)
        print("  baseline run (unmutated sandbox)...")
        baseline = run_gates(tmp, gates)
        green = sorted(g for g, rc in baseline.items() if rc == 0)
        noise = sorted(g for g, rc in baseline.items() if rc != 0)
        print(f"  baseline: {len(green)} green, {len(noise)} environmental "
              f"({', '.join(noise) if noise else 'none'})")
        if len(green) < len(gates) * 0.8:
            raise Fatal(
                f"only {len(green)}/{len(gates)} gates pass in the sandbox — "
                "too much noise to attribute failures to injected faults")

        blind, caught = [], []
        for name, klass, files, mutate in FAULTS:
            saved = {f: (tmp / f).read_bytes() for f in files}
            desc = mutate(tmp)
            after = run_gates(tmp, green)
            fired = sorted(g for g in green if after[g] != 0)
            for f, data in saved.items():
                (tmp / f).write_bytes(data)
            if fired:
                caught.append((name, fired))
                shown = ", ".join(fired[:4]) + (
                    f" (+{len(fired) - 4} more)" if len(fired) > 4 else "")
                print(f"  CAUGHT     {name:<18} {desc}")
                print(f"             by: {shown}")
            else:
                blind.append((name, klass, desc))
                print(f"  BLIND SPOT {name:<18} {desc}")

        print("-" * 72)
        if blind:
            print(f"Results: FAIL — {len(blind)}/{len(FAULTS)} fault "
                  "class(es) reach the fab with every gate green:")
            for name, klass, desc in blind:
                print(f"  {name}: {klass}")
            print()
            print("A blind spot is a missing gate, not a tolerable gap —")
            print("write the gate that catches it, then re-run this audit.")
            return 1
        print(f"Results: PASS — {len(FAULTS)}/{len(FAULTS)} injected fault "
              "classes caught by at least one gate")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Fatal as e:
        print(f"STRUCTURAL ERROR: {e}", file=sys.stderr)
        sys.exit(2)
