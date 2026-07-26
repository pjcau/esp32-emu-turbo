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
_LAW_EXCEPTIONS: dict[str, tuple[float, str]] = {}


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
            rec["detail"] = (f"no cached EasyEDA reference for {bom['lcsc']} "
                             f"(API returns 403; cache is the only source)")
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
        # one: the EasyEDA API returns 403, so scripts/.easyeda_cache/ is the
        # only source and an incomplete checkout silently changed this gate's
        # verdict run to run. Exit 2 says "this gate could not judge", which is
        # a different repair from "the board is wrong".
        print(f"\n  {noref} part(s) have no cached EasyEDA reference, so the law")
        print("  could not be evaluated for them. The reference footprints are")
        print("  tracked under scripts/.easyeda_cache/ — restore them with")
        print("  `git checkout -- scripts/.easyeda_cache`. They cannot be")
        print("  re-downloaded: the EasyEDA API returns HTTP 403.")
    if bad:
        return 1
    return 2 if noref else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
