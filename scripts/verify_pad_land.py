#!/usr/bin/env python3
"""Pad-vs-reference-land coverage gate (JLC SMT DFM pin/lead classes).

Born from the 2026-08-03 JLCDFM report:
  - "Pin inner edge 0.08mm" — 50 DANGERs = the 25 bottom-side 0805 MLCCs
    (pads 1.0x1.3 vs JLC's C0805 land 1.41x1.35);
  - "Lead area overlapping pad 0.02mm" — 2 DANGER + 43 Warning (J4's
    FPC pads 1.0mm long vs 1.5mm reference land, SOT-23 lands, J3).

JLC's SMT DFM measures each component's LEAD (from their own EasyEDA
land pattern / 3D model) against our copper pad. A pad much smaller
than the reference land means the lead overhangs copper: weak joints,
tombstoning on passives, DANGER flags at assembly review.

For every SMD pad whose part has a cached JLC reference footprint
(scripts/.easyeda_cache/, keyed by BOM LCSC number, matched by pad
number), this gate requires:
  - covered-area ratio min(w)*min(h) / (lw*lh) >= MIN_COVERAGE
  - per-axis land-minus-pad deficit <= MAX_AXIS_DEFICIT

Orientation-free: the ratio is computed for both land orientations and
the better one is used, so a failed outline fit (U1, J1) cannot produce
a false positive here.

No per-ref allowlist. If a pad genuinely cannot reach the reference
land (routing constraint), the constraint gets fixed, not listed.
"""
import csv
import math
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PCB = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"
BOM = BASE / "hardware" / "kicad" / "jlcpcb" / "bom.csv"
CACHE = BASE / "scripts" / ".easyeda_cache"

# Calibrated against the 2026-08-03 JLCDFM verdicts: the classes JLC
# flagged (0805 MLCC 0.683, J4 FPC 0.667, SOT-23 0.653-0.675, J3 0.658)
# fail; the classes JLC rated Good (R0805 at 0.833, 1206 caps at 0.808,
# U6 card pads at 0.833) pass with margin.
MIN_COVERAGE = 0.80     # fraction of the JLC reference land our pad covers
MAX_AXIS_DEFICIT = 0.45  # mm the land may exceed the pad on one axis

PAD_RE = re.compile(
    r'\(pad\s+"?([^"\s]*)"?\s+(\S+)\s+\S+\s*'
    r"\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\s*\)\s*"
    r"\(size\s+([-\d.]+)\s+([-\d.]+)\)")


def sexp_blocks(s, tag):
    out = []
    for m in re.finditer(r"\(" + tag + r"[\s\"]", s):
        i = m.start()
        depth = 0
        j = i
        instr = False
        while j < len(s):
            c = s[j]
            if instr:
                if c == '"' and s[j - 1] != "\\":
                    instr = False
            else:
                if c == '"':
                    instr = True
                elif c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        out.append((i, j + 1))
                        break
            j += 1
    return out


def load_ref_lands(lcsc):
    """pad number -> (w, h) of the JLC reference land, local orientation."""
    mods = list((CACHE / lcsc).glob("**/*.kicad_mod"))
    if not mods:
        return {}
    lands = {}
    for m in PAD_RE.finditer(mods[0].read_text()):
        if m.group(2) == "np_thru_hole":
            continue
        w, h = float(m.group(6)), float(m.group(7))
        rot = float(m.group(5) or 0)
        if abs(rot % 180 - 90) < 1e-6:
            w, h = h, w
        lands.setdefault(m.group(1), (w, h))
    return lands


def main():
    print("=" * 68)
    print("PAD vs JLC REFERENCE LAND COVERAGE (JLC SMT DFM pin/lead classes)")
    print("=" * 68)

    ref2lcsc = {}
    with open(BOM) as f:
        for row in csv.DictReader(f):
            lcsc = (row.get("LCSC Part #") or row.get("LCSC") or "").strip()
            for d in row["Designator"].replace('"', "").split(","):
                ref2lcsc[d.strip()] = lcsc

    src = PCB.read_text()
    checked = 0
    skipped = []
    bad = []
    for a, b in sexp_blocks(src, "footprint"):
        blk = src[a:b]
        mref = re.search(r'\(property\s+"Reference"\s+"([^"]*)"', blk)
        ref = mref.group(1) if mref else ""
        lcsc = ref2lcsc.get(ref)
        if not lcsc:
            continue
        lands = load_ref_lands(lcsc)
        if not lands:
            skipped.append((ref, lcsc))
            continue
        for pa, pb in sexp_blocks(blk, "pad"):
            p = blk[pa:pb]
            mp = PAD_RE.match(p)
            if not mp or mp.group(2) != "smd":
                continue
            land = lands.get(mp.group(1))
            if not land:
                continue
            checked += 1
            pw, ph = float(mp.group(6)), float(mp.group(7))
            lw, lh = land
            best = None
            for LW, LH in ((lw, lh), (lh, lw)):
                cov = (min(pw, LW) * min(ph, LH)) / (LW * LH)
                deficit = max(LW - pw, LH - ph, 0.0)
                cand = (cov, deficit)
                if best is None or cand[0] > best[0]:
                    best = cand
            cov, deficit = best
            if cov < MIN_COVERAGE or deficit > MAX_AXIS_DEFICIT:
                bad.append((cov, deficit, ref, mp.group(1),
                            (pw, ph), (lw, lh)))

    print(f"\n{checked} SMD pads checked against cached reference lands")
    for ref, lcsc in skipped:
        print(f"        skip {ref} ({lcsc}): no cached reference footprint")

    if bad:
        bad.sort()
        # group by (ref-prefix geometry) for a readable summary
        print(f"\n  FAIL  {len(bad)} pad(s) under-cover their JLC reference "
              f"land (coverage < {MIN_COVERAGE} or axis deficit > "
              f"{MAX_AXIS_DEFICIT}mm):")
        for cov, deficit, ref, num, (pw, ph), (lw, lh) in bad[:20]:
            print(f"        {ref}.{num:<4} pad {pw:.2f}x{ph:.2f} vs land "
                  f"{lw:.2f}x{lh:.2f}  coverage={cov:.3f} deficit={deficit:.2f}mm")
        if len(bad) > 20:
            print(f"        ... and {len(bad) - 20} more")
        print("\nFix the footprint in scripts/generate_pcb/footprints.py "
              "(grow the pad toward the reference land), not this gate.")
        print("=" * 68)
        print(f"Results: 0 passed, 1 failed ({len(bad)} pads)")
        return 1

    print(f"\n  PASS  every checked pad covers >= {MIN_COVERAGE} of its "
          f"reference land (axis deficit <= {MAX_AXIS_DEFICIT}mm)")
    print("=" * 68)
    print("Results: 1 passed, 0 failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
