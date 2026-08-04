#!/usr/bin/env python3
"""Assert that every CPL rotation obeys ONE global law, instead of a table.

The problem this replaces
-------------------------
`_JLCPCB_ROT_DELTAS` (scripts/generate_pcb/jlcpcb_export.py) is a
hand-tuned per-part table, and `verify_easyeda_footprint.py` checks that a
*sign-off exists* for each geometric mismatch -- via that table, via
`_GEOMETRIC_MISMATCH_ALLOWLIST`, or via `_PENDING_VALIDATION`. A gate shaped
like a sign-off registry cannot catch a wrong sign-off. Git history shows the
tuning loop it was built around: `39e350c` set D1 to "90 -> 180", then
`c7514e7` set it to "180 -> 270" the same day, with no geometric argument.

The law
-------
Every component's CPL angle relates our board-frame pad row to the EasyEDA
reference pad row by one fixed constant per layer. Using the bearing of the
pad-1 -> pad-2 vector (origin-independent, so exposed pads, shield tabs and
mounting pads cannot skew it):

    top     R = (cpl - (row_board - row_ee))            == LAW_TOP
    bottom  R = (cpl + row_board + row_ee)              == LAW_BOTTOM

`row_board` is measured AFTER placement rotation and after the B.Cu mirror,
so the mirror appears as the sign flip on `row_board` in the bottom form.

LAW_TOP and LAW_BOTTOM below are not fitted at runtime -- deliberately. If
the constant were re-derived from the data on every run, a mass error would
silently redefine the law and the gate would always pass. They are pinned
from the derivation recorded in the commit that introduced this file, and
every angle involved came out an exact multiple of 90 degrees.

Exceptions
----------
`_LAW_EXCEPTIONS` is intentionally shaped so it cannot rot the way the old
allowlist did: each entry must state the residual it actually produces, so
any drift re-triggers a failure, and the report always prints the CPL angle
the law would have emitted. An exception is a claim that this specific LCSC
part is taped in a non-standard orientation -- not a licence to skip the
check.

Usage:
    python3 scripts/verify_cpl_rotation_law.py            # exit 1 on failure
    python3 scripts/verify_cpl_rotation_law.py --verbose
"""

from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))

LAW_TOP = 0.0
LAW_BOTTOM = 180.0

# Angles are exact multiples of 90 degrees in practice; this tolerance only
# absorbs footprints whose pads are not perfectly axis-aligned.
TOL_DEG = 8.0

# ref -> (expected_residual_deg, reason)
#
# Every entry must be a claim about the PHYSICAL part, checkable against the
# JLCPCB 3D preview or the manufacturer drawing. "It seemed to work" is not
# a reason -- see the note on falsified evidence in
# verify_easyeda_footprint.py's allowlist.
_LAW_EXCEPTIONS: dict[str, tuple[float, str]] = {
    # THE LAW IS WRONG WHENEVER (row_board + row_ee) mod 180 != 0.
    #
    # That is the whole defect, stated exactly. Where the sum is 0 or 180 the
    # bottom form coincides with the geometry, which covers ten of the
    # fourteen parts and is why the gate looked healthy for so long. The four
    # parts below are every part where it does not coincide:
    #
    #     U2  sum= 90     J4  sum= 90     Q1  sum= 90     D1  sum=270
    #
    # All four have residual 0 rather than 180, and they have it for the same
    # single reason. This is ONE law defect recorded four times, not four
    # independent part quirks — if this list ever grows, check the sum first.
    #
    # The anchor for all four is U2, whose 270 is confirmed on prototypes #1
    # and #2 (see its entry). Everything else was derived against it by the
    # same convention-free route: place the physical part at each candidate
    # angle, see which board pad each pin lands on, and read that pad's net.
    #
    # Each entry states a claim about the PHYSICAL part and pins the residual,
    # so a move in the copper or the placement fails it as stale.
    #
    # Each entry below is a claim about the PHYSICAL part, checkable without
    # trusting any KiCad-to-JLCPCB angle convention. If the copper or the
    # placement moves, the residual moves off 0 and the entry fails as stale.
    "U2": (0.0,
           "CONFIRMED ON HARDWARE 2026-07-26 (protos #1 and #2): the IP5306 "
           "sits vertical — which rules out 0/180 outright — with pin 1 at "
           "the top-left seen from the bottom side, USB-C on the lower edge. "
           "U2 is on B.Cu so X mirrors in that view, and pad 1 (VIN/VBUS) is "
           "exactly that position, so physical pin 1 sits on pad 1. "
           "IP5306 ESOP-8 (C181692) at cpl=270. Convention-free check: at "
           "270 every pin lands on its own pad (0.090 mm uniform) and every "
           "net is correct — VIN->VBUS, KEY->IP5306_KEY, BAT->BAT+, SW->LX, "
           "VOUT->+5V, EP->GND, LED1-3 open. The law's 90 solders the part "
           "with pin i on pad i+4: BAT+ onto the LED1 indicator sink, with "
           "BAT and VOUT unconnected. The old cpl=0 did not seat at all "
           "(5.012 mm, 0 of 8 leads on copper)."),
    "J4": (0.0,
           "FPC-40P (C2856812) at cpl=270. Convention-free check: the "
           "contacts must face the FPC slot, which board.py places at "
           "x 125.5-128.5 with J4's body at 133.5-136.5, i.e. on J4's -X "
           "side. At 270 contacts land at x=133.712 and mount tabs at "
           "136.288 (contacts toward the slot, 0.002 mm worst residual over "
           "all 42 pads); the law's 90 swaps them, contacts 0 of 42 pads, "
           "and would need the ribbon to enter from off the right board "
           "edge. Unrelated to the connector_pad = 41 - panel_pin netlist "
           "mapping, which is correct and untouched."),
    "D1": (0.0,
           "BAT54C SOT-23-3 (C37704) at cpl=90, KiCad 180. A 180 error on a "
           "SOT-23-3 puts the single leg where the pair is, so unlike U2 "
           "there is no solderable-but-wrong option: the old cpl=270 left "
           "every lead on bare mask (3.120 mm). At 90 the part seats "
           "(0.187 mm) and the nets are the diode-OR the schematic draws — "
           "the two anodes on BTN_START and BTN_SELECT, the common cathode "
           "on MENU_K. Note the prototypes cannot corroborate this one: D1 "
           "was relocated for R5-CRIT-6 after they were built, and its "
           "anodes were unrouted on every board produced so far."),
    "Q1": (0.0,
           "SI2301CDS SOT-23-3 (C10487) at cpl=90, KiCad 180 — the same "
           "pair as D1, the board's other SOT-23-3, since R31-HIGH-1 turned "
           "the package around so the DRAIN faces the cell. The angle moved "
           "by 180 and the residual did not, which is arithmetic rather "
           "than luck: the bottom law reads cpl + row_board + row_ee, and "
           "rotating a part adds the same 180 to both cpl and row_board. "
           "It seats exactly (0.000 mm) with G/S/D on RPP_GATE / BAT+ / "
           "BAT_IN, i.e. the cell on the drain, which is the only wiring in "
           "which the body diode blocks a reversed pack. The previous "
           "entry's cpl=270 / KiCad 0 seated just as exactly with S and D "
           "swapped — seating cannot tell the two apart, only the netlist "
           "can, which is how the defect survived to v4.5.0. "
           "POLARITY_AUDIT.md's 'boards R4-R8 power up through Q1, so its "
           "polarity is proven' remains retired repo-wide, and R31-HIGH-1 "
           "is the second thing it got wrong: those boards power up in "
           "either orientation."),
    "Q2": (0.0,
           "SI2301CDS SOT-23-3 (C10487) at cpl=90 — the SAME part, layer, "
           "footprint and placement transform as Q1 (rot 180 baked into the "
           "pads + B-mirror), so the same (row_board + row_ee) mod 180 = 90 "
           "arithmetic puts it in this list; the SW16-respin merge added "
           "the part but not the entry. Convention-free check: at 90 it "
           "seats exactly (0.000 mm) with G/S/D on PWR_SW_GATE / +5V_VOUT "
           "/ +5V — source on the boost output, drain on the loads, which "
           "is the only wiring in which the body diode blocks loads->VOUT "
           "when SW16 is OFF (the whole point of the high-side switch; "
           "vbench T2.3 reads the same nets off Q2's model). The law's 270 "
           "puts the single leg where the pair is and does not assemble."),
}


def _load(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, str(BASE / path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row_bearing(pads: dict) -> float | None:
    """Bearing of pad 1 -> pad 2 (or the next numbered pad), in degrees.

    Origin-independent: unaffected by where the footprint places its origin,
    and by exposed/mechanical pads that would skew a centroid.
    """
    if "1" not in pads:
        return None
    nxt = "2" if "2" in pads else next(
        (k for k in sorted((k for k in pads if k.isdigit()), key=int)
         if k != "1"), None)
    if nxt is None:
        return None
    (x1, y1), (x2, y2) = pads["1"], pads[nxt]
    dx, dy = x2 - x1, y2 - y1
    if math.hypot(dx, dy) < 1e-9:
        return None
    return math.degrees(math.atan2(dy, dx)) % 360.0


def _delta(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def evaluate() -> list[dict]:
    """Return one record per polarized component with a cached reference."""
    ee = _load("_ee", "scripts/verify_easyeda_footprint.py")
    marker = _load("_mk", "scripts/analyze_pin1_marker.py")

    ours = ee._build_our_pad_map()
    placements = ee._placement_rotations()

    out = []
    for bom in ee._load_bom():
        ref = bom["ref"]
        if not ee._is_polarized(ref, bom.get("footprint", ""),
                                bom.get("comment", "")):
            continue
        our = ours.get(ref)
        place = placements.get(ref)
        fp = marker.read_footprint(bom["lcsc"])
        rec = {"ref": ref, "lcsc": bom["lcsc"],
               "layer": (place or {}).get("layer", "?"),
               "status": "SKIP", "detail": "", "cpl": None,
               "residual": None, "law_cpl": None}

        if our is None or place is None:
            rec["detail"] = "not in PCB / placement list"
            out.append(rec)
            continue
        if fp is None:
            rec["status"] = "NOREF"
            rec["detail"] = (
                f"no cached EasyEDA reference for {bom['lcsc']} — restore it "
                f"with `git checkout -- scripts/.easyeda_cache`. Do not "
                f"re-fetch: this gate must judge against the geometry that "
                f"was reviewed, not whatever the API serves today.")
            out.append(rec)
            continue

        ee_pads: dict[str, tuple] = {}
        for num, x, y in fp["pads"]:
            ee_pads.setdefault(num, (x, y))

        row_board = _row_bearing(our["pads"])
        row_ee = _row_bearing(ee_pads)
        cpl = ee._cpl_rotation_for(ref)
        rec["cpl"] = cpl

        if row_board is None or row_ee is None or cpl is None:
            rec["status"] = "UNEVALUABLE"
            rec["detail"] = ("no usable pad-1/pad-2 pair — duplicate or "
                             "unnumbered pads (e.g. connector shield tabs)")
            out.append(rec)
            continue

        if rec["layer"] == "bottom":
            residual = (cpl + row_board + row_ee) % 360.0
            law = LAW_BOTTOM
            law_cpl = (law - row_board - row_ee) % 360.0
        else:
            residual = (cpl - (row_board - row_ee)) % 360.0
            law = LAW_TOP
            law_cpl = (law + row_board - row_ee) % 360.0
        rec["residual"] = residual
        rec["law_cpl"] = law_cpl
        rec["row_board"] = row_board
        rec["row_ee"] = row_ee

        if _delta(residual, law) <= TOL_DEG:
            rec["status"] = "OK"
        elif ref in _LAW_EXCEPTIONS:
            want, reason = _LAW_EXCEPTIONS[ref]
            if _delta(residual, want) <= TOL_DEG:
                rec["status"] = "EXCEPTION"
                rec["detail"] = reason
            else:
                rec["status"] = "FAIL"
                rec["detail"] = (f"declared exception expects R={want:.0f}deg "
                                 f"but R={residual:.0f}deg — entry is stale")
        else:
            rec["status"] = "FAIL"
            rec["detail"] = (f"violates the {rec['layer']} law by "
                             f"{_delta(residual, law):.0f}deg; law would emit "
                             f"cpl={law_cpl:.0f}deg, generator emits "
                             f"cpl={cpl:.0f}deg")
        out.append(rec)
    return out


def main(argv: list[str]) -> int:
    verbose = "--verbose" in argv or "-v" in argv
    records = evaluate()

    print("=" * 74)
    print("  CPL ROTATION LAW  —  one law per layer, not a per-part table")
    print(f"  top: R = cpl-(row_board-row_ee) == {LAW_TOP:.0f}deg   "
          f"bottom: R = cpl+row_board+row_ee == {LAW_BOTTOM:.0f}deg")
    print("=" * 74)
    print(f"{'ref':<8}{'lcsc':<11}{'layer':<8}{'cpl':>5}{'R':>7}  status")
    print("-" * 74)
    bad = 0
    noref = 0
    for r in records:
        if r["status"] == "NOREF":
            noref += 1
        elif r["status"] in ("FAIL", "UNEVALUABLE"):
            bad += 1
        if not verbose and r["status"] == "OK":
            continue
        cpl = "  -- " if r["cpl"] is None else f"{r['cpl']:5.0f}"
        res = "  --  " if r["residual"] is None else f"{r['residual']:6.1f}"
        print(f"{r['ref']:<8}{r['lcsc']:<11}{r['layer']:<8}{cpl}{res}  "
              f"{r['status']}")
        if r["detail"]:
            print(f"{'':<32}-> {r['detail']}")

    ok = sum(1 for r in records if r["status"] == "OK")
    exc = sum(1 for r in records if r["status"] == "EXCEPTION")
    print("-" * 74)
    print(f"  OK: {ok}   EXCEPTION: {exc}   "
          f"FAIL/UNEVALUABLE: {bad}   NOREF: {noref}   total: {len(records)}")
    if bad:
        print("\n  A violation means the emitted CPL angle disagrees with the")
        print("  angle every other part on that layer implies. Resolve it by")
        print("  checking the JLCPCB 3D preview for that LCSC part — then")
        print("  either fix the footprint or declare a _LAW_EXCEPTIONS entry")
        print("  stating what is physically non-standard about the part.")
    if noref:
        # A missing reference is not a violation and must not be reported as
        # one: an incomplete checkout of scripts/.easyeda_cache/ silently
        # changed this gate's verdict run to run. Exit 2 says "this gate could
        # not judge", which is a different repair from "the board is wrong".
        print(f"\n  {noref} part(s) have no EasyEDA reference, so the law could")
        print("  not be evaluated for them. The references are tracked under")
        print("  scripts/.easyeda_cache/ — restore them with")
        print("  `git checkout -- scripts/.easyeda_cache`. Do not re-fetch them")
        print("  from the API: this gate must judge against the geometry that")
        print("  was reviewed, not against whatever EasyEDA serves today.")
    if bad:
        return 1
    return 2 if noref else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
