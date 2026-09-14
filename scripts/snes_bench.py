#!/usr/bin/env python3
"""SNES renderer benchmark on the first article: resume each saved scene, capture PROF.

    snes_bench.py [--label NAME] [--games smw,kart,...] [--settle 6] [--capture 6]

Every game has a save-state in slot 0 (see docs/first-boot-session-2026-08-29.md,
"benchmark scenes"): `resume` reboots into it, so every run measures the same
frames. Needs a SNES_PROF=1 build of retro-core. Results go to
software/benchmark/results/<label>.json and are printed as a table; pass a
second label with --compare to print the delta against an earlier run.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from board_ctl import Board  # noqa: E402

ROMS = {  # scene -> ROM; "name@N" resumes save slot N (default 0)
    "smw": "/sd/roms/snes/Super Mario World (U) [!].smc",           # overworld map, Yoshi's Island 2 node
    "smw-level": "/sd/roms/snes/Super Mario World (U) [!].smc@1",   # inside Yoshi's Island 2
    "kart": "/sd/roms/snes/Super Mario Kart (USA).sfc",
    "zelda": "/sd/roms/snes/Legend of Zelda - A Link to the Past (USA).sfc",
    "mmx": "/sd/roms/snes/Mega Man X (USA) (Rev 1).sfc",
    "metroid": "/sd/roms/snes/Super Metroid (Japan, USA) (En,Ja).sfc",
}
COLS = ["efps", "drawn", "busy", "R", "main(skip)", "d.update", "d.sub", "d.main",
        "d.combine", "d.obj", "d.objsetup", "d.clear", "d.conv", "d.strips"]
RESULTS = os.path.join(os.path.dirname(__file__), "..", "software", "benchmark", "results")


def run(board, games, settle, capture):
    out = {}
    for g in games:
        print(f"== {g}", file=sys.stderr)
        rom, _, slot = ROMS[g].partition("@")
        board.launch("snes", rom, resume=True, slot=int(slot or 0))
        if not board.wait_boot():
            print(f"{g}: no ping after resume", file=sys.stderr)
            continue
        time.sleep(settle)
        out[g] = board.capture(capture, echo=False, summary=False)
    return out


def table(res, ref=None):
    print(f"{'game':8}" + "".join(f"{c:>11}" for c in COLS))
    for g, r in res.items():
        row = f"{g:8}"
        for c in COLS:
            v = r.get(c)
            if v is None:
                row += f"{'-':>11}"
            elif ref and ref.get(g, {}).get(c) and c in ("R", "d.update", "d.sub", "d.main", "d.combine"):
                row += f"{v:8.0f}{(v / ref[g][c] - 1) * 100:+3.0f}%"
            else:
                row += f"{v:11.1f}"
        print(row)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default=os.environ.get("ESP_PORT", "/dev/ttyACM0"))
    ap.add_argument("--label", default=datetime.now().strftime("%Y%m%d-%H%M"))
    ap.add_argument("--games", default=",".join(ROMS))
    ap.add_argument("--settle", type=float, default=6)
    ap.add_argument("--capture", type=float, default=6)
    ap.add_argument("--compare", help="label of an earlier run to diff against")
    a = ap.parse_args()

    res = run(Board(a.port), a.games.split(","), a.settle, a.capture)
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, f"{a.label}.json")
    json.dump({"label": a.label, "date": datetime.now().isoformat(timespec="seconds"),
               "settle": a.settle, "capture": a.capture, "results": res}, open(path, "w"), indent=1)
    ref = json.load(open(os.path.join(RESULTS, f"{a.compare}.json")))["results"] if a.compare else None
    print(f"# {a.label}" + (f" vs {a.compare}" if ref else "") + f"  (us per drawn frame; {a.capture}s capture)")
    table(res, ref)
    print(f"saved {os.path.relpath(path)}")


if __name__ == "__main__":
    main()
