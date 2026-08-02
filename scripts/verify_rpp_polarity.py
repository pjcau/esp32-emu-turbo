#!/usr/bin/env python3
"""Q1 reverse-polarity-protection orientation, proven from the ORDER artifacts.

R31-HIGH-1 (2026-08-02): Q1 (Si2301 P-FET) spent four releases wired
source-on-cell — the load-switch orientation, whose body diode conducts
INTO a reversed cell instead of blocking it. Every gate was green because
every gate checked the board against the same wrong declaration, and
working boards proved nothing: with a correctly-inserted cell a P-channel
pass FET conducts either way round. See hardware/CLAIMS.md CLAIM-006.

This gate replaces the bench continuity check (J3.1 -> Q1 pad 3) the fix
left owed — the user ruled bench measurements out, and the fabrication
half of that check is fully deterministic: the IPC-D-356 netlist that
ships in the JLCPCB order records which net lands on every pad. So we
assert, on BOTH the working d356 and the shipped release copy:

    BAT_IN   owns J3-1 (cell +) and Q1-3 (drain)   — cell on the DRAIN
    BAT+     owns Q1-2 (source)                    — load on the SOURCE
    RPP_GATE owns Q1-1 (gate)
    and the swapped (load-switch) wiring is EXPLICITLY absent.

Physics, so the assertion is reviewable: a P-FET body diode conducts
D->S. Cell on drain: normal polarity pre-charges the load through the
diode, then Vgs=-Vbat turns the channel on; a reversed cell sees the
diode reverse-biased AND the channel off. Cell on source (the bug):
a reversed cell forward-biases the diode and the protection is defeated.

The assembly half (JLC soldering Q1 rotated) is NOT checkable from
files, but needs no bench either: SOT-23's lead pattern (2 pins south,
1 north) is not 180-degree symmetric, so a wrongly-rotated part cannot
seat on the lands — it fails visually/AOI and at first-article preview.

Files are positional args for mutation testing; defaults are the truth.
"""
import re
import sys

DEFAULT_FILES = [
    "hardware/kicad/jlcpcb/esp32-emu-turbo.d356",
    "release_jlcpcb/esp32-emu-turbo.d356",
]

# (net, ref, pin) triples that MUST be present…
REQUIRED = [
    ("BAT_IN", "J3", "1"),    # cell + from the battery connector
    ("BAT_IN", "Q1", "3"),    # …arrives on the DRAIN
    ("BAT+", "Q1", "2"),      # SOURCE faces the IP5306
    ("RPP_GATE", "Q1", "1"),  # gate held low by R24
]
# …and the load-switch wiring (the R31-HIGH-1 bug) that MUST be absent.
FORBIDDEN = [
    ("BAT_IN", "Q1", "2"),
    ("BAT+", "Q1", "3"),
]

REC = re.compile(r"^327(\S+)\s+(\S+)\s+-(\S+)")


def pad_nets(path):
    triples = set()
    with open(path) as fh:
        for line in fh:
            m = REC.match(line)
            if m:
                triples.add((m.group(1), m.group(2), m.group(3)))
    return triples


def main():
    files = sys.argv[1:] or DEFAULT_FILES
    failures = 0
    for path in files:
        try:
            triples = pad_nets(path)
        except OSError as e:
            print(f"  FAIL  {path}: unreadable ({e}) — cannot prove Q1 orientation")
            failures += 1
            continue
        for net, ref, pin in REQUIRED:
            if (net, ref, pin) in triples:
                print(f"  PASS  {path}: {net} owns {ref}-{pin}")
            else:
                print(f"  FAIL  {path}: {net} does NOT own {ref}-{pin} — "
                      f"Q1 RPP orientation broken or netlist stale (R31-HIGH-1)")
                failures += 1
        for net, ref, pin in FORBIDDEN:
            if (net, ref, pin) in triples:
                print(f"  FAIL  {path}: {net} owns {ref}-{pin} — the LOAD-SWITCH "
                      f"wiring is back: body diode conducts into a reversed cell "
                      f"(R31-HIGH-1 regression)")
                failures += 1
        q1_pins = {p for (n, r, p) in triples if r == "Q1"}
        if q1_pins != {"1", "2", "3"}:
            print(f"  FAIL  {path}: Q1 pins in netlist are {sorted(q1_pins)}, "
                  f"expected exactly 1/2/3")
            failures += 1
    print("=" * 60)
    if failures:
        print(f"Results: FAILED ({failures} failure(s)) — do not fabricate")
        return 1
    print(f"Results: PASS — cell on Q1 drain, load on source, in "
          f"{len(files)} netlist(s); reverse-polarity protection is real")
    return 0


if __name__ == "__main__":
    sys.exit(main())
