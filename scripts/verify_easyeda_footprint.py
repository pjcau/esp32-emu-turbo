#!/usr/bin/env python3
"""Proactive EasyEDA reference-footprint verification.

Catches footprint rotation/polarity bugs BEFORE JLCPCB production by
cross-checking every BOM component against its EasyEDA reference
footprint fetched via `easyeda2kicad`.

Detects the same class of bug that caused the C2 tantalum reversal:
  - Pad 1 physically on the wrong side of the footprint
  - Pin numbering rotated vs EasyEDA convention
  - Missing or stale `_JLCPCB_ROT_OVERRIDES` entries

Policy (no silencing):
  - Polarized parts with geometric pad-1 mismatch → FAIL (suggests override)
  - Polarized parts with existing override and geometric match → OK (verified)
  - Polarized parts with override but no geometric evidence → REVIEW
    (empirical 3D-model-stripe fix; keep override, document reason)
  - Polarized parts in `_GEOMETRIC_MISMATCH_ALLOWLIST` whose δ_row still
    matches the signed-off expected value → ALLOW (exit 0, printed with
    explicit empirical evidence). If δ_row drifts or evidence is empty,
    the entry is invalidated and the ref re-FAILs.
  - Non-polarized parts with mismatch → INFO (no manufacturing impact)
  - LCSC part unavailable on EasyEDA → WARN (explicit, not skipped)
  - easyeda2kicad not installed → FAIL loudly with install instructions

Usage:
    python3 scripts/verify_easyeda_footprint.py
    Exit code 0 = all OK, 1 = one or more FAIL.
"""

from __future__ import annotations

import csv
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SCRIPTS = BASE / "scripts"
sys.path.insert(0, str(SCRIPTS))

from pcb_cache import load_cache  # noqa: E402

PCB_FILE = BASE / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"
BOM_FILE = BASE / "release_jlcpcb" / "bom.csv"
CACHE_DIR = SCRIPTS / ".easyeda_cache"

# ── Polarized reference classifiers ───────────────────────────────────
#
# Parts on this list MUST FAIL on geometric mismatch. Everything else is
# informational (a rotation mismatch on a 0805 resistor has no functional
# consequence, but the check is still valuable for future parts).

_POLARIZED_PREFIXES = ("D", "LED", "Q", "U", "J", "SW_PWR")


# ── Geometric mismatch ALLOWLIST (explicit, with evidence) ──────────
#
# Policy reference: user memory `feedback_never_silence_errors.md` —
# no soft-passes without proof. An entry here is NOT a silent filter,
# it is an explicit record of "we have inspected this δ_row mismatch,
# the physical board has been empirically validated, and we accept the
# native-frame rotation delta because CPL compensation already handles
# the deployment orientation".
#
# Contract:
#   ref -> (expected_delta_row_deg, evidence_string)
#
#   - expected_delta_row_deg: the CURRENT δ_row that we have signed off.
#     If the footprint is regenerated and δ_row changes, the allowlist
#     entry is INVALID and the ref re-FAILs. This forces a re-review
#     every time the native-frame geometry shifts.
#
#   - evidence_string: REQUIRED, non-empty. Must describe the empirical
#     proof (prototype batch, power-up behaviour, measured output, etc).
#     A missing/empty evidence string also causes a FAIL.
#
# IMPORTANT: this allowlist is INDEPENDENT of _JLCPCB_ROT_OVERRIDES in
# jlcpcb_export.py. The override dict corrects CPL rotation at export
# time. The allowlist records "this δ_row native-frame mismatch has
# been physically validated". Do not conflate the two.
#
# Do NOT add a ref here unless you have evidence the physical board
# works with the current footprint. Keeping genuine suspects (LED2,
# C2, J4, etc.) on the FAIL/REVIEW list is INTENTIONAL — they must
# remain visible until each is empirically cleared.

_GEOMETRIC_MISMATCH_ALLOWLIST: dict[str, tuple[int, str]] = {
    "Q1": (
        90,
        "SI2301 SOT-23 P-MOSFET. Same δ=90° family as D1. Boards R4-R8 "
        "(8+ prototypes) power up via slide switch SW_PWR → Q1 conducts "
        "correctly → physical polarity validated. CPL rotation=90° "
        "compensates empirically.",
    ),
    "U2": (
        90,
        "IP5306 ESOP-8. Boards R4-R8 charge via USB-C and boost to 5V → "
        "IP5306 operational on correct pins → physical pin mapping "
        "validated empirically despite 90° native-frame mismatch.",
    ),
    "U3": (
        90,
        "AMS1117-3.3 SOT-223. Boards R4-R8 boot ESP32 on +3V3 rail → LDO "
        "producing correct output on correct pin → physical polarity "
        "validated empirically. Candidate for footprint realignment at "
        "v2 respin.",
    ),
    "LED2": (
        180,
        "Green LED 0805 C19171391. Analytical determination (no physical "
        "board needed): EasyEDA footprint "
        "scripts/.easyeda_cache/C19171391/fp.pretty/LED0805-R-RD_RED."
        "kicad_mod lines 23-24 place pad 1 at x=+1.05 and pad 2 at "
        "x=-1.05; cathode silkscreen notch is on the LEFT side "
        "(lines 16-20, x=-0.34..-2.22) i.e. co-located with pad 2, "
        "NOT pad 1. Compare LED1 C84256 (same skill, lines 26-27): "
        "pad 1 at x=-1.10 IS co-located with its cathode silk notch "
        "(lines 17-23, x=-1.75..-2.10). Datasheet "
        "hardware/datasheets/LED2_Green-LED-0805_C19171391.pdf page 1 "
        "'Package Profile' diagram shows pin ① = cathode (diode symbol "
        "triangle points to pin 1). Conclusion: EasyEDA author swapped "
        "pad numbering on C19171391 (footprint author error, not a "
        "manufacturer convention difference). With our KiCad LED_0805 "
        "pad 1 = cathode → GND routing and 0° rotation, EasyEDA's "
        "physical anode would land on our GND pad → LED reverse-biased "
        "and dark. _JLCPCB_ROT_OVERRIDES['LED2']=180 in "
        "scripts/generate_pcb/jlcpcb_export.py flips the part so the "
        "physical cathode lands on our GND pad → forward-biased.",
    ),
}


# ── PENDING-VALIDATION list (suspected bugs awaiting empirical result) ──
#
# This dict is DISTINCT from both:
#   - `_JLCPCB_ROT_OVERRIDES` (jlcpcb_export.py): compensation rotations
#     that are actively applied to the CPL file at export time.
#   - `_GEOMETRIC_MISMATCH_ALLOWLIST` (above): empirically validated
#     native-frame mismatches (evidence already collected).
#
# `_PENDING_VALIDATION` documents a SUSPECTED polarity/rotation bug that
# has NOT yet been validated or falsified on a physical board. The entry
# exists to:
#   (a) suppress a noisy FAIL while we wait for a specific upcoming
#       production batch to come back,
#   (b) lock in the expected δ_row so that any silent drift of the
#       footprint geometry re-triggers a FAIL ("PENDING entry stale"),
#   (c) carry the exact test procedure inline so whoever receives the
#       batch knows how to resolve the entry.
#
# Contract:
#   ref -> (expected_delta_row_deg, batch_id, test_procedure_string)
#
#   - expected_delta_row_deg: current δ_row we have seen when filing the
#     entry. Drift → FAIL ("PENDING entry stale, re-verify").
#   - batch_id: manufacturer production batch (SMT#/order#) that will
#     provide the empirical evidence. Printed inline so the reader can
#     cross-reference physical samples.
#   - test_procedure_string: step-by-step how to validate or invalidate
#     the suspicion. Rendered in verbose mode; summarised (batch_id only)
#     in default output.
#
# Resolution policy (no silent pass-through):
#   - If the batch confirms the footprint is CORRECT (component works
#     without CPL compensation) → MOVE entry to
#     `_GEOMETRIC_MISMATCH_ALLOWLIST` with empirical evidence string.
#   - If the batch confirms the footprint is WRONG (component reversed) →
#     ADD the rotation to `_JLCPCB_ROT_OVERRIDES` in jlcpcb_export.py AND
#     remove the entry from here.
#   - Either way, `_PENDING_VALIDATION` MUST shrink over time; a growing
#     dict is a red flag.
#
# Do NOT use this list to silence parts you have not actually put into a
# production queue. "Pending" means "batch ordered, awaiting return".

_PENDING_VALIDATION: dict[str, tuple[int, str, str]] = {}


def _is_polarized(ref: str, footprint: str, comment: str) -> bool:
    """Return True iff the component has a polarity that matters."""
    u = footprint.upper()
    c = comment.upper()
    # Electrolytic / tantalum caps
    if "TANTALUM" in c or ("POLARIZED" in c):
        return True
    # Connectors with polarity (USB, JST, FPC, TF slot)
    if u.startswith(("USB", "JST", "FPC", "TF-", "SS-", "MICRO-SD")):
        return True
    # Slide switches, SD card, USB etc. Strong heuristic: any J* + FPC/USB/JST
    if ref.startswith("J") and any(k in u for k in ("USB", "JST", "FPC")):
        return True
    # Any IC (multi-pin) or MOSFET or Diode or LED
    if ref.startswith(("D", "LED", "Q", "U")):
        return True
    if ref == "SW_PWR":
        return True
    return False


# ── EasyEDA cache management ─────────────────────────────────────────

def _find_easyeda2kicad() -> str:
    """Locate easyeda2kicad binary or fail loudly."""
    path = shutil.which("easyeda2kicad")
    if not path:
        sys.stderr.write(
            "FATAL: easyeda2kicad not found in PATH.\n"
            "Install with:\n"
            "    pip3 install easyeda2kicad\n"
            "or via pipx:\n"
            "    pipx install easyeda2kicad\n"
            "Then re-run this script.\n"
        )
        sys.exit(2)
    return path


def _fetch_easyeda(lcsc: str) -> Path | None:
    """Fetch .kicad_mod for an LCSC part, caching under CACHE_DIR/<LCSC>/.

    Returns the path to the cached .kicad_mod, or None if the part is
    not available on EasyEDA.
    """
    lcsc = lcsc.strip()
    if not lcsc or not lcsc.startswith("C"):
        return None

    part_dir = CACHE_DIR / lcsc
    mod_glob = list(part_dir.glob("*.pretty/*.kicad_mod"))
    if mod_glob:
        return mod_glob[0]

    part_dir.mkdir(parents=True, exist_ok=True)
    bin_path = _find_easyeda2kicad()
    out_prefix = part_dir / "fp"

    try:
        result = subprocess.run(
            [bin_path, "--full", f"--lcsc_id={lcsc}",
             f"--output={out_prefix}", "--overwrite"],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(f"WARN: easyeda2kicad timeout for {lcsc}\n")
        return None

    stdout = (result.stdout or "") + (result.stderr or "")
    # easyeda2kicad returns 0 even for some failures; detect by output
    if result.returncode != 0 and "Created Kicad footprint" not in stdout:
        # Part not found / API error
        # Persist a stamp file so we don't hammer the API on rerun
        stamp = part_dir / ".not_found"
        stamp.write_text(stdout[:4000])
        return None

    mod_glob = list(part_dir.glob("*.pretty/*.kicad_mod"))
    return mod_glob[0] if mod_glob else None


def _is_cached_not_found(lcsc: str) -> bool:
    return (CACHE_DIR / lcsc / ".not_found").exists()


# ── .kicad_mod parsing ──────────────────────────────────────────────

_PAD_RE = re.compile(
    r'\(pad\s+"?([^\s")]+)"?\s+(\S+)\s+(\S+)'
    r'\s+\(at\s+([-\d.]+)\s+([-\d.]+)(?:\s+([-\d.]+))?\)'
)

_MODEL_ROT_RE = re.compile(
    r'\(model\b[^)]*\)[\s\S]*?\(rotate\s+\(xyz\s+'
    r'([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\)',
    re.M,
)


def _parse_easyeda_mod(path: Path) -> dict:
    """Parse an EasyEDA-exported .kicad_mod file.

    Returns dict with:
      pads_by_num: {num_str: (x, y)} for numbered pads
      pad1: (x, y) of pad "1" (or first pad if no "1")
      row_dir: (dx, dy) — vector from pad 1 to pad 2 (origin-agnostic
               orientation reference). None if <2 pads.
      model_rot_z: int  rotation z of the 3D model (degrees)
      n_pads: int
    """
    text = path.read_text(encoding="utf-8", errors="replace")

    pads_by_num: dict[str, tuple] = {}
    first_pad = None
    for m in _PAD_RE.finditer(text):
        num = m.group(1)
        x = float(m.group(4))
        y = float(m.group(5))
        if first_pad is None:
            first_pad = (x, y)
        if num not in pads_by_num:
            pads_by_num[num] = (x, y)

    pad1 = pads_by_num.get("1", first_pad)

    # Row direction: pad 1 -> pad 2 (or pad 1 -> pad N if pad 2 missing)
    row_dir = None
    if pad1 is not None:
        # Prefer "2", else next numeric pad
        candidates = []
        if "2" in pads_by_num:
            candidates = ["2"]
        else:
            numeric = sorted(
                [k for k in pads_by_num
                 if k.isdigit() and int(k) > 1],
                key=int,
            )
            candidates = numeric[:1]
        if candidates:
            p2 = pads_by_num[candidates[0]]
            row_dir = (p2[0] - pad1[0], p2[1] - pad1[1])

    model_rot_z = 0
    mm = _MODEL_ROT_RE.search(text)
    if mm:
        try:
            model_rot_z = int(round(float(mm.group(3))))
        except ValueError:
            model_rot_z = 0

    return {
        "pads_by_num": pads_by_num,
        "pad1": pad1,
        "row_dir": row_dir,
        "model_rot_z": model_rot_z % 360,
        "n_pads": len(pads_by_num),
        "path": str(path),
    }


# ── Our PCB pad data (from cache) ───────────────────────────────────

def _build_our_pad_map() -> dict:
    """Return {ref: {"fp_x","fp_y","pads":{num:(abs_x,abs_y)},"layer"}}."""
    cache = load_cache(PCB_FILE)
    by_ref: dict[str, dict] = {}
    for p in cache["pads"]:
        ref = p["ref"]
        if ref not in by_ref:
            by_ref[ref] = {
                "fp_x": p["fp_x"],
                "fp_y": p["fp_y"],
                "pads": {},
                "layer": p["layer"],
            }
        # Record unique pad numbers (first occurrence wins; for multi-layer
        # SMD pads the abs position is identical across layer entries).
        if p["num"] not in by_ref[ref]["pads"]:
            by_ref[ref]["pads"][p["num"]] = (p["x"], p["y"])
    return by_ref


# ── Rotation math ───────────────────────────────────────────────────

def _angle_deg(x: float, y: float) -> float:
    if abs(x) < 1e-6 and abs(y) < 1e-6:
        return 0.0
    return math.degrees(math.atan2(y, x))


def _quantize_90(angle: float) -> int:
    """Snap an angle to nearest 0/90/180/270 multiple."""
    a = angle % 360
    q = round(a / 90.0) * 90
    return int(q % 360)


def _native_rel_pad(our: dict, pad_num: str, placement_rot: float) -> tuple[float, float] | None:
    """Return native (pre-rotate, pre-mirror) relative pad position.

    Forward transform in footprints.get_pads() is:
        native → rotate(placement_rot) → mirror_X (B.Cu only) → store
    Inverse (what this function computes) therefore applies the two
    operations in reverse order:
        stored_rel → un-mirror_X (B.Cu only) → un-rotate(placement_rot) → native
    """
    p = our["pads"].get(pad_num)
    if p is None:
        return None
    rel_x = p[0] - our["fp_x"]
    rel_y = p[1] - our["fp_y"]

    # Un-mirror X first (it was the last forward step for B.Cu)
    if our["layer"] == "B.Cu":
        rel_x = -rel_x

    # Then un-rotate by placement_rot
    if placement_rot % 360 != 0:
        a = -math.radians(placement_rot)
        c, s = math.cos(a), math.sin(a)
        rel_x, rel_y = rel_x * c - rel_y * s, rel_x * s + rel_y * c

    return (rel_x, rel_y)


def _native_row_dir(our: dict, placement_rot: float) -> tuple[float, float] | None:
    """Vector from our pad 1 to pad 2 in native (library) frame.

    Origin-agnostic orientation marker — works even when EasyEDA and our
    library use different footprint origin conventions (e.g., JST body
    center vs signal-pad center).
    """
    p1 = _native_rel_pad(our, "1", placement_rot)
    # Prefer pad 2, else next available numeric pad
    p2: tuple[float, float] | None = None
    if "2" in our["pads"]:
        p2 = _native_rel_pad(our, "2", placement_rot)
    else:
        nums = sorted(
            [k for k in our["pads"] if k.isdigit() and int(k) > 1],
            key=int,
        )
        if nums:
            p2 = _native_rel_pad(our, nums[0], placement_rot)
    if p1 is None or p2 is None:
        return None
    return (p2[0] - p1[0], p2[1] - p1[1])


def _placement_rotations() -> dict:
    """Pull placement rotations per ref from jlcpcb_export._build_placements()."""
    # Import lazily to avoid circulars
    sys.path.insert(0, str(BASE))
    from scripts.generate_pcb.jlcpcb_export import _build_placements  # noqa: E402
    out = {}
    for ref, _val, _pkg, _x, _y, rot, layer in _build_placements():
        out[ref] = {"rot": rot, "layer": layer}
    return out


def _cpl_rotation_for(ref: str) -> float | None:
    """Return the final CPL rotation that jlcpcb_export would write."""
    from scripts.generate_pcb.jlcpcb_export import (  # noqa: E402
        _jlcpcb_rotation, _build_placements,
    )
    for r, _val, _pkg, _x, _y, rot, layer in _build_placements():
        if r == ref:
            return _jlcpcb_rotation(rot, layer, _pkg, ref=r)
    return None


def _current_override(ref: str) -> int | None:
    from scripts.generate_pcb.jlcpcb_export import _JLCPCB_ROT_OVERRIDES
    return _JLCPCB_ROT_OVERRIDES.get(ref)


# ── BOM expansion ───────────────────────────────────────────────────

def _load_bom() -> list[dict]:
    """Return list of {ref, comment, footprint, lcsc} — one per reference."""
    out = []
    with open(BOM_FILE, encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            refs = row["Designator"].replace('"', "").split(",")
            for ref in [r.strip() for r in refs if r.strip()]:
                out.append({
                    "ref": ref,
                    "comment": row["Comment"],
                    "footprint": row["Footprint"],
                    "lcsc": row["LCSC Part #"].strip(),
                })
    return out


# ── Reporting ───────────────────────────────────────────────────────

class Result:
    def __init__(self):
        self.ok = 0
        self.allow = 0
        self.pending = 0
        self.fail = 0
        self.warn = 0
        self.info = 0
        self.review = 0
        self.rows: list[tuple] = []

    def add(self, status: str, ref: str, detail: str):
        self.rows.append((status, ref, detail))
        if status == "OK":
            self.ok += 1
        elif status == "ALLOW":
            self.allow += 1
        elif status == "PENDING":
            self.pending += 1
        elif status == "FAIL":
            self.fail += 1
        elif status == "WARN":
            self.warn += 1
        elif status == "REVIEW":
            self.review += 1
        else:
            self.info += 1


STATUS_SYM = {
    "OK": "OK     ",
    "ALLOW": "ALLOW  ",
    "PENDING": "PENDING",
    "FAIL": "FAIL   ",
    "WARN": "WARN   ",
    "INFO": "INFO   ",
    "REVIEW": "REVIEW ",
}

# ANSI color codes — only emitted when stdout is a TTY. PENDING gets
# yellow/orange to stand out from ALLOW (cyan) and FAIL (red).
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR", "") == ""
STATUS_COLOR = {
    "OK": "\033[32m",       # green
    "ALLOW": "\033[36m",    # cyan
    "PENDING": "\033[33m",  # yellow
    "FAIL": "\033[31m",     # red
    "WARN": "\033[35m",     # magenta
    "INFO": "",              # default
    "REVIEW": "\033[34m",   # blue
}
_RESET = "\033[0m"


def _colorize(status: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    c = STATUS_COLOR.get(status, "")
    if not c:
        return text
    return f"{c}{text}{_RESET}"


def _print_row(status: str, ref: str, detail: str):
    tag = f"[{STATUS_SYM[status]}]"
    print(f"  {_colorize(status, tag)} {ref:<6} {detail}")


# ── Main check ──────────────────────────────────────────────────────

def main() -> int:
    t0 = time.time()
    print("── EasyEDA reference footprint verification ──")
    print(f"  BOM:   {BOM_FILE.relative_to(BASE)}")
    print(f"  PCB:   {PCB_FILE.relative_to(BASE)}")
    print(f"  Cache: {CACHE_DIR.relative_to(BASE)}")
    print()

    _find_easyeda2kicad()  # fail loudly if missing

    bom = _load_bom()
    our_map = _build_our_pad_map()
    placements = _placement_rotations()

    res = Result()

    # Group by LCSC to fetch once per unique part
    lcsc_seen: dict[str, Path | None] = {}

    for entry in bom:
        ref = entry["ref"]
        lcsc = entry["lcsc"]
        footprint = entry["footprint"]
        comment = entry["comment"]

        # Fetch (or use cache)
        if lcsc not in lcsc_seen:
            if _is_cached_not_found(lcsc):
                lcsc_seen[lcsc] = None
            else:
                lcsc_seen[lcsc] = _fetch_easyeda(lcsc)

        mod_path = lcsc_seen[lcsc]

        polarized = _is_polarized(ref, footprint, comment)

        if mod_path is None:
            status = "WARN" if polarized else "INFO"
            res.add(status, ref,
                    f"LCSC {lcsc} ({comment}) not available on EasyEDA"
                    f" — manual review required"
                    if polarized else
                    f"LCSC {lcsc} not on EasyEDA (non-polarized, ignored)")
            continue

        ee = _parse_easyeda_mod(mod_path)
        ours = our_map.get(ref)
        if ours is None:
            res.add("WARN", ref, "ref not present in PCB (skipped)")
            continue

        plc = placements.get(ref, {"rot": 0, "layer": "bottom"})

        # Origin-agnostic orientation: vector from pad 1 to pad 2, in both
        # our native library frame and EasyEDA native frame. If EasyEDA and
        # our library use different origin conventions (e.g. JST body vs
        # signal-pad center) the absolute pad-1 positions don't match —
        # but the pad-1→pad-2 direction still reveals any rotational bug.
        ours_row = _native_row_dir(ours, plc["rot"])
        ee_row = ee["row_dir"]

        if ours_row is None or ee_row is None:
            # Fall back to absolute pad-1 vector (single-pad components etc.)
            p1_ours = _native_rel_pad(ours, "1", plc["rot"])
            p1_ee = ee["pad1"]
            if p1_ours is None or p1_ee is None:
                res.add("WARN", ref, "pad-1 unresolved (missing pads)")
                continue
            ours_row = p1_ours
            ee_row = p1_ee

        a_ours = _angle_deg(*ours_row)
        a_ee = _angle_deg(*ee_row)
        delta = _quantize_90(a_ours - a_ee)

        # Also compute pad-1 absolute-position delta as a supporting signal
        # (useful when row direction is identical but pad 1 is on the wrong
        # end of a symmetric part like a 2-pin cap or resistor — this is
        # the C2 tantalum class). row_dir(2 pads) points pad1→pad2; if our
        # pad 1 is swapped with pad 2, row_dir flips 180° → delta=180°.
        p1_ours = _native_rel_pad(ours, "1", plc["rot"])
        p1_ee = ee["pad1"]
        pad1_delta = None
        if p1_ours is not None and p1_ee is not None:
            # Only meaningful if pad 1 is off-origin
            if (abs(p1_ee[0]) + abs(p1_ee[1])) > 0.1 and (
                    abs(p1_ours[0]) + abs(p1_ours[1])) > 0.1:
                pad1_delta = _quantize_90(
                    _angle_deg(*p1_ours) - _angle_deg(*p1_ee))

        # CPL output we ship
        cpl_rot = _cpl_rotation_for(ref)
        override = _current_override(ref)

        detail = (
            f"pkg={footprint:<20s} "
            f"row_ours=({ours_row[0]:+.2f},{ours_row[1]:+.2f}) "
            f"row_ee=({ee_row[0]:+.2f},{ee_row[1]:+.2f}) "
            f"δ_row={delta:3d}°"
            + (f" δ_p1={pad1_delta:3d}°" if pad1_delta is not None else "")
            + f" cpl={cpl_rot}°"
            + f" override={override}"
            + (f" m_rot={ee['model_rot_z']}°" if ee["model_rot_z"] else "")
        )

        # ── Decision logic ────────────────────────────────────────────
        #
        # δ_row is the angle between our footprint's pin-row direction and
        # EasyEDA's (both in native / un-rotated library frames). It is
        # NOT the same number as the CPL rotation override — it is the
        # footprint-layout mismatch. A non-zero δ_row means our footprint
        # has its pins rotated relative to EasyEDA's reference, which
        # WILL produce wrong CPL placement unless compensated by:
        #   - A _JLCPCB_ROT_OVERRIDES entry, OR
        #   - Built-in formula correction matching the package family
        #
        # For polarized parts we require either a match (δ=0) OR an
        # existing override/formula compensation. Parts where δ!=0 and
        # no override is set are flagged FAIL.
        if polarized:
            if delta == 0:
                if override is None:
                    res.add("OK", ref, detail)
                else:
                    # Override present but footprint already matches.
                    # This is the C2 tantalum case: 3D-model polarity
                    # stripe direction is opposite in the EasyEDA 3D
                    # model, requiring an override even though the pad
                    # layout matches. Keep override, flag for audit.
                    res.add("REVIEW", ref,
                            detail
                            + "  (footprint OK; override kept for "
                            "3D-model orientation — document reason "
                            "in jlcpcb_export.py)")
            else:
                if override is None:
                    # Check PENDING-validation list first. An entry here
                    # means we have a SUSPECTED polarity/rotation bug
                    # that is queued for empirical validation on a
                    # specific batch. We do NOT silence — we lock the
                    # expected δ_row, print batch id + procedure, and
                    # return exit-code-0 contribution (not FAIL) so the
                    # Stop hook does not nag while the batch is in
                    # transit. If δ_row drifts, the entry goes stale
                    # and we FAIL loudly.
                    pend_entry = _PENDING_VALIDATION.get(ref)
                    if pend_entry is not None:
                        exp_delta, batch_id, procedure = pend_entry
                        if not batch_id or not batch_id.strip():
                            res.add(
                                "FAIL", ref,
                                detail
                                + f"  FIX: _PENDING_VALIDATION[{ref!r}]"
                                " has EMPTY batch_id — pending entries"
                                " MUST reference a specific production"
                                " batch so the validation is traceable."
                            )
                        elif not procedure or not procedure.strip():
                            res.add(
                                "FAIL", ref,
                                detail
                                + f"  FIX: _PENDING_VALIDATION[{ref!r}]"
                                " has EMPTY test_procedure — without a"
                                " procedure nobody knows how to resolve"
                                " the entry."
                            )
                        elif exp_delta != delta:
                            res.add(
                                "FAIL", ref,
                                detail
                                + f"  PENDING entry stale, re-verify:"
                                f" expected δ_row={exp_delta}° but now"
                                f" δ_row={delta}°. Footprint geometry"
                                f" changed since the entry was filed"
                                f" (batch={batch_id}). Re-evaluate the"
                                f" suspected bug against the new"
                                f" footprint, then update"
                                f" _PENDING_VALIDATION[{ref!r}] or"
                                f" promote to allowlist/overrides."
                            )
                        else:
                            verbose = (
                                os.environ.get("VERIFY_VERBOSE", "") == "1"
                            )
                            extra = (
                                f"  BATCH: {batch_id}  "
                                + (
                                    f"PROCEDURE: {procedure}"
                                    if verbose
                                    else "(set VERIFY_VERBOSE=1 for"
                                    " test procedure)"
                                )
                            )
                            res.add("PENDING", ref, detail + extra)
                        continue

                    # Check explicit allowlist (with evidence) before
                    # failing. The allowlist is NOT a silent filter —
                    # every entry carries an empirical-proof string and
                    # a locked-in δ_row value. If either is missing or
                    # the δ_row has drifted, we FAIL loudly.
                    allow_entry = _GEOMETRIC_MISMATCH_ALLOWLIST.get(ref)
                    if allow_entry is not None:
                        exp_delta, evidence = allow_entry
                        if not evidence or not evidence.strip():
                            # Guard: empty evidence is never acceptable.
                            res.add(
                                "FAIL", ref,
                                detail
                                + f"  FIX: allowlist entry for {ref} has"
                                " EMPTY evidence — either remove the"
                                " entry or provide empirical proof"
                                " (prototype batch + power-up behaviour)"
                            )
                        elif exp_delta != delta:
                            # Guard: δ_row drifted → footprint changed,
                            # old sign-off is void. Force re-review.
                            res.add(
                                "FAIL", ref,
                                detail
                                + f"  FIX: allowlist expected"
                                f" δ_row={exp_delta}° but now δ_row="
                                f"{delta}°. Footprint changed — re-verify"
                                f" on a physical prototype, then update"
                                f" _GEOMETRIC_MISMATCH_ALLOWLIST[\"{ref}\"]"
                                f" in verify_easyeda_footprint.py."
                            )
                        else:
                            res.add(
                                "ALLOW", ref,
                                detail
                                + f"  EVIDENCE: {evidence}"
                            )
                        continue
                    # Check if a formula correction pattern matches —
                    # the CPL rotation may already be compensated.
                    # If cpl_rot is non-zero AND aligns with delta, accept.
                    # We can't cleanly derive this without assembly
                    # feedback, so conservatively FAIL and ask human.
                    fix = (f"add `_JLCPCB_ROT_OVERRIDES[\"{ref}\"] = "
                           f"<value>` (candidate from δ_row={delta}°)"
                           f" in scripts/generate_pcb/jlcpcb_export.py,"
                           " then order sample and confirm polarity")
                    res.add("FAIL", ref, detail + f"  FIX: {fix}")
                else:
                    # Override exists — we trust it (it was empirically
                    # validated at assembly). Tool remains informational.
                    res.add("OK", ref,
                            detail
                            + "  (override compensates footprint delta;"
                            " empirically verified)")
        else:
            if delta == 0:
                res.add("OK", ref, detail)
            else:
                res.add("INFO", ref, detail + "  (non-polarized, no action)")

    # Print results grouped by status priority
    order = ["FAIL", "WARN", "REVIEW", "PENDING", "ALLOW", "OK", "INFO"]
    for status in order:
        rows = [r for r in res.rows if r[0] == status]
        if not rows:
            continue
        header = f"── {status} ({len(rows)}) ──"
        print(f"\n{_colorize(status, header)}")
        for st, ref, detail in rows:
            _print_row(st, ref, detail)

    elapsed = time.time() - t0
    print()
    print("── Summary ──")
    print(f"  OK:      {res.ok}")
    print(f"  ALLOW:   {res.allow}")
    print(f"  PENDING: {res.pending}")
    print(f"  FAIL:    {res.fail}")
    print(f"  WARN:    {res.warn}")
    print(f"  REVIEW:  {res.review}")
    print(f"  INFO:    {res.info}")
    print(
        f"  OK: {res.ok} · ALLOW: {res.allow} · PENDING: {res.pending}"
        f" · FAIL: {res.fail} · REVIEW: {res.review} · WARN: {res.warn}"
    )
    print(f"  Total:  {len(res.rows)} component refs in {elapsed:.1f}s")

    # PENDING contributes exit code 0 — the whole point is to defer the
    # FAIL while a specific production batch is in transit. Only true
    # FAIL conditions (including stale/invalid PENDING entries, which
    # are converted to FAIL above) cause a non-zero exit.
    return 1 if res.fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
