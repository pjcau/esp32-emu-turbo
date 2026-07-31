#!/usr/bin/env python3
"""Cross-check our parsed netlist against KiCad's own IPC-D-356 export.

Why this is the strongest check in the repo
-------------------------------------------
Every other tool here reads the `.kicad_pcb` with our own parser
(`pcb_cache`, `pcb_copper_graph`, the regex helpers in
`generate_net_explorer`). They agree with each other because they share
assumptions — which means a parsing mistake is invisible to all of them
at once.

`kicad-cli pcb export ipcd356` asks KiCad itself. IPC-D-356 is the bare-
board electrical test netlist: one record per pad and per via, carrying
the net name, the reference designator, the pin, the drill and the layer
access. If our net membership disagrees with that file, our parser is
wrong, not KiCad.

Format note: the record is fixed-width — [0:3] type, [3:20] net name,
[20:26] refdes, [26] '-', [27:31] pin. The refdes field is six columns,
so `SW14` is written `SW_BOO`; that truncation is the format's, not a
discrepancy, and this check truncates our side to match rather than
special-casing the parts that happen to be affected.
"""
import collections
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCB = os.path.join(PROJECT_DIR, "hardware/kicad/esp32-emu-turbo.kicad_pcb")

REFDES_WIDTH = 6  # IPC-D-356 field width


def kicad_netlist(path):
    """net name -> {(refdes, pin)}, plus the via count."""
    nets = collections.defaultdict(set)
    vias = 0
    for line in open(path):
        if line[:3] not in ("317", "327"):
            continue
        net = line[3:20].strip()
        ref = line[20:26].strip()
        pin = line[27:31].strip()
        if ref == "VIA":
            vias += 1
            continue
        nets[net].add((ref, pin))
    return nets, vias


def our_netlist():
    from generate_net_explorer import merge_through_pads
    from pcb_cache import load_cache

    cache = load_cache()
    name = {n["id"]: n["name"] for n in cache["nets"]}
    nets = collections.defaultdict(set)
    for p in merge_through_pads(cache["pads"]):
        if p["net"]:
            nets[name[p["net"]]].add(
                (p["ref"][:REFDES_WIDTH], str(p["num"])))
    return nets, len(cache["vias"])


def main():
    print()
    print("=" * 62)
    print("Netlist cross-check — our parser vs KiCad's IPC-D-356 export")
    print("=" * 62)
    print()

    with tempfile.TemporaryDirectory() as tmp:
        d356 = os.path.join(tmp, "board.d356")
        proc = subprocess.run(
            ["kicad-cli", "pcb", "export", "ipcd356", "--output", d356, PCB],
            capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.exists(d356):
            # Fail loudly: a missing kicad-cli must not silently pass the
            # one check that does not share our parsing assumptions.
            print("  FAIL  kicad-cli could not export the IPC-D-356 netlist")
            print(f"        {(proc.stderr or proc.stdout).strip()[:300]}")
            print()
            print("STATUS: FAIL — this check needs kicad-cli on PATH")
            return 1
        theirs, their_vias = kicad_netlist(d356)

    ours, our_vias = our_netlist()

    # KiCad emits an N/C bucket for pads on no net; we simply omit them.
    theirs.pop("N/C", None)

    only_theirs = sorted(set(theirs) - set(ours))
    only_ours = sorted(set(ours) - set(theirs))
    shared = sorted(set(theirs) & set(ours))
    mismatched = [n for n in shared if theirs[n] != ours[n]]

    print(f"  Nets — KiCad: {len(theirs)}   ours: {len(ours)}")
    print(f"  Vias — KiCad: {their_vias}   ours: {our_vias}")
    print()

    failed = False
    if only_theirs:
        failed = True
        print(f"  FAIL  {len(only_theirs)} nets KiCad has and we do not: "
              f"{', '.join(only_theirs[:10])}")
    if only_ours:
        failed = True
        print(f"  FAIL  {len(only_ours)} nets we invented: "
              f"{', '.join(only_ours[:10])}")
    for net in mismatched:
        failed = True
        print(f"  FAIL  {net} membership differs")
        print(f"          only KiCad: "
              f"{sorted(theirs[net] - ours[net])}")
        print(f"          only ours : "
              f"{sorted(ours[net] - theirs[net])}")
    if their_vias != our_vias:
        failed = True
        print(f"  FAIL  via count differs: KiCad {their_vias}, ours {our_vias}")

    if not failed:
        print(f"  PASS  All {len(shared)} nets have identical membership")
        print(f"  PASS  Via count matches ({our_vias})")

    print()
    print("=" * 62)
    print(f"Results: {len(shared) - len(mismatched)}/{len(shared)} nets agree")
    print("STATUS: " + ("FAIL — our parser disagrees with KiCad"
                        if failed else "PASS"))
    print("=" * 62)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
