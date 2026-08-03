#!/usr/bin/env python3
"""Silkscreen legibility gate — silk vs drill holes and mask openings.

Born from the 2026-08-03 JLCDFM report (gerbers 64a9f79b): 53 "silkscreen
to hole 0mm" DANGERs. Two distinct causes, both checked here at the
gerber level (the only artifact the fab reads):

1. Dark silk strokes crossing or grazing drill holes. Ink over a hole is
   cut off by the drill (illegible) and can smear into the barrel. JLC
   flags any intersection as DANGER. This gate requires every dark silk
   stroke to stay >= MIN_HOLE_CLR from every hole edge.

2. Clear-polarity (LPC) objects on the silk layers. kicad-cli's
   --subtract-soldermask emits a clear flash per mask opening near silk;
   JLCDFM's checker ignores polarity and reported each one as a 0mm
   silk-to-hole DANGER (41 of the 53). The export scripts therefore no
   longer pass that flag, and this gate fails if clear objects reappear.

Dropping --subtract-soldermask removes the safety net that used to clip
silk printed over exposed copper, so this gate also enforces what the
flag used to guarantee: no dark silk stroke may intersect a solder-mask
opening (pad flashes and drawn openings in the mask gerbers).

No allowlist. A hit is fixed by moving the silk (or the via), never by
listing it here.
"""
import math
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
GERBER_DIR = BASE / "hardware" / "kicad" / "gerbers"

MIN_HOLE_CLR = 0.15   # mm from hole edge to silk stroke edge (JLC danger = 0)
SCALE = 10 ** 6       # KiCad emits %FSLAX46Y46 (4.6, mm)

LAYERS = [
    ("F", "esp32-emu-turbo-F_Silkscreen.gto", "esp32-emu-turbo-F_Mask.gts"),
    ("B", "esp32-emu-turbo-B_Silkscreen.gbo", "esp32-emu-turbo-B_Mask.gbs"),
]
DRILL = "esp32-emu-turbo.drl"

failures = []
passes = []


def check(name, ok, detail=""):
    if ok:
        passes.append(name)
        print(f"  PASS  {name}")
    else:
        failures.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def parse_drill(path):
    """[(x, y, dia)] for every hole; G85 slots contribute both endpoints."""
    holes = []
    tools = {}
    current = None
    header = True
    for raw in path.read_text().splitlines():
        line = raw.strip()
        tm = re.match(r"^T(\d+)C([\d.]+)", line)
        if tm:
            tools[tm.group(1)] = float(tm.group(2))
            continue
        if line == "%" or line.startswith("G90") or line.startswith("M95"):
            header = False
            continue
        if header:
            continue
        sm = re.match(r"^T(\d+)$", line)
        if sm:
            current = sm.group(1)
            continue
        cm = re.match(
            r"^X(-?[\d.]+)Y(-?[\d.]+)(?:G85X(-?[\d.]+)Y(-?[\d.]+))?$", line)
        if cm and current is not None:
            d = tools[current]
            holes.append((float(cm.group(1)), float(cm.group(2)), d))
            if cm.group(3):
                holes.append((float(cm.group(3)), float(cm.group(4)), d))
    return holes


def parse_gerber(path):
    """(dark_segments, dark_flashes, clear_count) for one RS-274X file.

    dark_segments: (x1, y1, x2, y2, stroke_width) — D01 draws; arcs are
    chord-approximated, which is conservative enough for glyph strokes.
    dark_flashes:  (x, y, shape, w, h) — D03 flashes.
    clear_count:   number of objects emitted in LPC (clear) polarity.
    """
    txt = path.read_text()
    apertures = {}
    for m in re.finditer(r"%ADD(\d+)([A-Z]+),([\d.]+)(?:X([\d.]+))?", txt):
        w = float(m.group(3))
        h = float(m.group(4)) if m.group(4) else w
        apertures[m.group(1)] = (m.group(2), w, h)

    segs, flashes = [], []
    clear = 0
    polarity = "D"
    cur = None
    cx = cy = None
    for line in txt.splitlines():
        line = line.strip()
        if line == "%LPC*%":
            polarity = "C"
            continue
        if line == "%LPD*%":
            polarity = "D"
            continue
        m = re.match(r"^(?:G0?[123])?D(\d+)\*$", line)
        if m and m.group(1) not in ("01", "02", "03"):
            cur = m.group(1)
            continue
        m = re.match(
            r"^(?:G0?[123])?(?:X(-?\d+))?(?:Y(-?\d+))?"
            r"(?:I-?\d+)?(?:J-?\d+)?D0([123])\*$", line)
        if not m:
            continue
        x = int(m.group(1)) / SCALE if m.group(1) else cx
        y = int(m.group(2)) / SCALE if m.group(2) else cy
        op = m.group(3)
        if polarity == "D":
            shape, w, h = apertures.get(cur, ("C", 0.0, 0.0))
            if op == "1" and cx is not None:
                segs.append((cx, cy, x, y, max(w, h)))
            elif op == "3":
                flashes.append((x, y, shape, w, h))
        elif op in ("1", "3"):
            clear += 1
        cx, cy = x, y
    return segs, flashes, clear


def seg_point(x1, y1, x2, y2, px, py):
    dx, dy = x2 - x1, y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def silk_to_rect(x1, y1, x2, y2, sw, fx, fy, w, h):
    """Min distance from a stroked segment to an axis-aligned rect/oval
    flash, by sampling along the segment (glyph strokes are short)."""
    best = None
    steps = max(2, int(math.hypot(x2 - x1, y2 - y1) / 0.1))
    for i in range(steps + 1):
        t = i / steps
        px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        dx = max(abs(px - fx) - w / 2, 0)
        dy = max(abs(py - fy) - h / 2, 0)
        d = math.hypot(dx, dy) - sw / 2
        if best is None or d < best:
            best = d
    return best


def main():
    print("=" * 68)
    print("SILKSCREEN vs HOLES / MASK OPENINGS (JLCDFM silk-to-hole class)")
    print("=" * 68)

    missing = [p for p in [GERBER_DIR / DRILL]
               + [GERBER_DIR / s for _, s, _ in LAYERS]
               + [GERBER_DIR / m for _, _, m in LAYERS]
               if not p.exists()]
    if missing:
        print(f"  FAIL  gerbers missing: {[str(p) for p in missing]}")
        print("        run: make export-gerbers-fast")
        return 1

    holes = parse_drill(GERBER_DIR / DRILL)
    print(f"\n{len(holes)} drill holes")

    for side, silk_name, mask_name in LAYERS:
        segs, flashes, clear = parse_gerber(GERBER_DIR / silk_name)
        print(f"\n── {side} silk: {len(segs)} strokes, {len(flashes)} flashes ──")

        check(f"{side}: no clear-polarity objects on silk", clear == 0,
              f"{clear} LPC objects — JLCDFM counts each as a 0mm "
              "silk-to-hole DANGER; was --subtract-soldermask re-added "
              "to an export script?")

        viol = []
        for hx, hy, hd in holes:
            worst = None
            for x1, y1, x2, y2, sw in segs:
                d = seg_point(x1, y1, x2, y2, hx, hy) - hd / 2 - sw / 2
                if worst is None or d < worst:
                    worst = d
            for fx, fy, shape, w, h in flashes:
                d = math.hypot(fx - hx, fy - hy) - hd / 2 - max(w, h) / 2
                if worst is None or d < worst:
                    worst = d
            if worst is not None and worst < MIN_HOLE_CLR:
                viol.append((hx, hy, hd, worst))
        detail = "; ".join(
            f"hole({hx:.2f},{hy:.2f}) dia{hd:.2f} clr={d:.3f}mm"
            for hx, hy, hd, d in sorted(viol, key=lambda v: v[3])[:8])
        check(f"{side}: silk >= {MIN_HOLE_CLR}mm from every hole edge",
              not viol, f"{len(viol)} holes: {detail}")

        msegs, mflashes, _ = parse_gerber(GERBER_DIR / mask_name)
        over = []
        for fx, fy, shape, w, h in mflashes:
            for x1, y1, x2, y2, sw in segs:
                if shape == "C":
                    d = seg_point(x1, y1, x2, y2, fx, fy) - w / 2 - sw / 2
                else:
                    d = silk_to_rect(x1, y1, x2, y2, sw, fx, fy, w, h)
                if d < 0:
                    over.append((fx, fy, -d))
                    break
        for x1, y1, x2, y2, w in msegs:
            for sx1, sy1, sx2, sy2, sw in segs:
                d = min(seg_point(x1, y1, x2, y2, sx1, sy1),
                        seg_point(x1, y1, x2, y2, sx2, sy2),
                        seg_point(sx1, sy1, sx2, sy2, x1, y1),
                        seg_point(sx1, sy1, sx2, sy2, x2, y2)) - w / 2 - sw / 2
                if d < 0:
                    over.append((x1, y1, -d))
                    break
        detail = "; ".join(f"({x:.2f},{y:.2f}) by {o:.3f}mm"
                           for x, y, o in over[:8])
        check(f"{side}: no silk over mask openings (prints on copper)",
              not over, f"{len(over)} openings hit: {detail}")

    print("\n" + "=" * 68)
    print(f"Results: {len(passes)} passed, {len(failures)} failed")
    if failures:
        print("Fix by moving the silk text/marker or the via in the")
        print("generator (scripts/generate_pcb/board.py) — never by")
        print("whitelisting the location here.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
