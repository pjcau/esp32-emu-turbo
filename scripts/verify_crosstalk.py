#!/usr/bin/env python3
"""Fail on tightly coupled parallel runs between signals that cannot tolerate them.

The gap this closes
-------------------
`scripts/pcb_optimize.py:analyze_parallel_traces` looks like this check and is
not it. It is an unregistered advisory (nothing in `VERIFY_ALL_SCRIPTS` runs
it), it only sees axis-aligned segments (a 45 degree run is invisible to it),
it compares CENTRELINE distance against `3 * max_width` while calling the
result a 3W finding — which is the 2W rule wearing the wrong label — and it
scores the board instead of failing it. Nothing in the repo turns "these two
traces run together" into a verdict.

So LCD_WR could be re-routed to hug SD_CLK for 20 mm at a 0.15 mm gap and every
gate stays green.

What is measured
----------------
For every pair of same-layer track segments on different signal nets:

  * near-parallel filter — the angle between the two centrelines must be
    within PARALLEL_ANGLE_TOL_DEG, otherwise the "co-run" is a crossing;
  * co-run — the length of the interval, measured along the common direction,
    over which the two segments overlap;
  * edge gap — centreline distance minus (w1 + w2) / 2, i.e. copper edge to
    copper edge, evaluated as a linear function of position along the run.

Because the edge gap varies along the run (segments are only near-parallel),
this gate does not reduce a pair to one gap number and one length number the
way the prior art does. It integrates: `corun_1w` is the length over which the
gap is actually below 1W, `corun_3w` the length below 3W. That distinction
matters — two traces fanning out of adjacent pads touch 1W tightness for
0.2 mm and then diverge, which is pin pitch, not a coupling defect. Summing
raw overlap and reporting the single worst gap would call that a 20 mm
violation.

W convention
------------
W is the WIDER of the two traces. The classical 3W rule is stated on
centre-to-centre spacing (3W centres == 2W edge gap for equal widths), so this
gate's `edge gap < 1W` FAIL line is tighter than the classical rule and its
`edge gap < 3W` WARN line is looser. Both are stated in edge-gap terms because
that is the quantity that actually sets the coupling capacitance.

Victim classes
--------------
Crosstalk only matters where a glitch has somewhere to go.

  CRITICAL — asynchronous strobes, clocks and USB. There is no clock to
  re-sample against: a coupled glitch on LCD_WR latches whatever the data bus
  happens to be showing, a glitch on SD_CLK inserts a phantom SPI bit and
  desynchronises the whole transfer, and a glitch on the USB pair corrupts the
  differential decision directly. These FAIL.

  CONTROL — chip selects and mode pins. Push-pull driven and static for the
  whole duration of a transfer, so a coupled spike has to both exceed VIH/VIL
  against a low-impedance driver and land in the microseconds-wide window where
  anyone is looking. Reported, never fatal: WARN.

  INTRA-BUS — both nets in LCD_D0..D7. Every member of that bus is sampled by
  the same LCD_WR rising edge, and the bus is held for the whole write cycle
  (>= 25 ns at the 20 MHz ceiling) while the coupled disturbance decays in a
  few nanoseconds. Bus members coupling to each other therefore cannot change
  what gets latched. Routed as a tight bundle on purpose. INFO only.

  DIFFERENTIAL — see COUPLED_BY_DESIGN. Tight coupling is the specification.

Threshold honesty
-----------------
The 5 mm / 10 mm length thresholds are NOT the length at which this board
develops a crosstalk problem, and pretending otherwise would be the kind of
fake derivation this repo's conventions exist to prevent. The real numbers:

  ESP32 GPIO edge      tr  = 2 ns
  FR-4 microstrip velocity  v = c / sqrt(3.2) = 168 mm/ns  (same effective
                            permittivity used by verify_usb_impedance.py)
  rising-edge length   tr * v = 336 mm
  backward-crosstalk saturation length = tr * v / 2 = 168 mm

Backward (near-end) crosstalk grows linearly with coupled length until that
168 mm and then saturates. On the JLC04161H-7628 stackup an outer-layer trace
sits 0.21 mm from its reference plane, so two 0.2 mm traces at a 0.2 mm edge
gap have s/h ~= 1 and a backward coupling coefficient of roughly 0.04. A 5 mm
co-run is 5/168 of saturation, so the coupled amplitude is about
0.04 * 0.03 = 0.1 % of a 3.3 V swing — around 4 mV. Nothing on this board is
electrically endangered by 5 mm of coupling.

These thresholds are regression tripwires on ROUTING INTENT, set two orders of
magnitude below the electrical limit on purpose. A router that puts a strobe
inside 1W of another signal for more than 5 mm did not do it by accident of
pin escape, and the next revision that does it for 50 mm at 0.1 mm will not be
caught by a gate calibrated to the physics. The cost of holding this line is a
few millimetres of detour; the cost of a real LCD_WR glitch is a field fault
that reproduces once an hour.

Usage:
    python3 scripts/verify_crosstalk.py
    python3 scripts/verify_crosstalk.py --selftest
    Exit 0 = pass, 1 = failure, 2 = tooling/environment error
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pcb_cache import load_cache  # noqa: E402

# ── Geometry thresholds ──────────────────────────────────────────────

# Two segments count as parallel when their centrelines are within this angle.
# Chosen so that the 45 degree routing this board uses is never mistaken for a
# parallel run (45 >> 10) while the small angular error introduced by KiCad's
# arc-to-segment approximation and by pad-escape jogs still reads as parallel.
# The co-run is measured along the direction bisecting the two segments, so at
# the 10 degree limit each segment is 5 degrees off that axis and the projected
# length understates the true arc length by 1 - cos(5 deg) = 0.4 %.
PARALLEL_ANGLE_TOL_DEG = 10.0

# Edge gap below which coupling is treated as "tight" (FAIL band) and
# "close" (WARN band), in multiples of W = the wider of the two traces.
# See "W convention" above for why these are edge-gap and not centre-to-centre.
TIGHT_GAP_W = 1.0
CLOSE_GAP_W = 3.0

# Coupled length that turns tight/close coupling into a verdict, in mm.
# Derivation and its limits: see "Threshold honesty" above. Both are far below
# the 168 mm backward-crosstalk saturation length for a 2 ns edge on FR-4;
# they detect deliberate parallel routing, not a computed noise margin.
TIGHT_CORUN_FAIL_MM = 5.0
CLOSE_CORUN_WARN_MM = 10.0

# Bounding-box expansion used to find candidate segment pairs. Must be at
# least CLOSE_GAP_W * (widest signal trace) + that trace's own half-widths, or
# the prefilter would silently hide pairs the verdict law cares about. Asserted
# against the real board at runtime by _check_search_radius().
# 5.0, not 4.0, since the R32 trace-ampacity widenings: the widest
# non-plane trace is now the 1.10 mm BAT+/LX copper, whose 3W reach is
# 4.40 mm. Only affects candidate count (speed), never verdicts.
COUPLING_SEARCH_MM = 5.0

# Uniform grid cell for the candidate search, mm. Only affects speed.
GRID_CELL_MM = 5.0

# Segments shorter than this contribute no meaningful coupled length and their
# direction is numerically unstable. 0.01 mm is below KiCad's 1 nm file
# resolution times any quantity worth measuring.
MIN_SEGMENT_MM = 0.01


# ── Net classification ───────────────────────────────────────────────

# Nets excluded from the analysis entirely: they are DC distribution, so they
# neither inject a disturbance (no edges) nor care about receiving one (no
# threshold to cross). Each entry states why, per the ALLOWED-dict convention.
# NOTE the deliberate absences: LX / BUCK_LX (the SY8089 switch node) and
# SPK+ / SPK- (class-D PWM output) are power nets by voltage but are the two
# loudest AGGRESSORS on the board, so they stay in.
QUIET_DC_NETS = {
    "GND":      "reference plane, no switching content",
    "+3V3":     "regulated rail, decoupled — no edges to couple out",
    "+5V":      "regulated rail, decoupled — no edges to couple out",
    "VBUS":     "USB input rail, DC",
    "VBUS_IN":  "USB input rail upstream of the RPP FET, DC",
    "BAT+":     "battery rail, DC",
    "BAT_IN":   "battery rail upstream of the RPP FET, DC",
    "":         "unassigned copper carries no signal",
}

# Nets whose two halves are one physical run split by a series element. The
# pair must be judged as one logical signal, otherwise R22/R23 would turn the
# USB pair into four nets and the coupling ledger would be nonsense.
LOGICAL_NET = {
    "USB_DP_MCU": "USB_D+",
    "USB_DM_MCU": "USB_D-",
}

# Asynchronous strobes, clocks and USB — a coupled glitch is directly latched
# or directly corrupts a differential decision. FAIL class.
CRITICAL_VICTIMS = {
    "LCD_WR",     # 8080 write strobe: the data bus is sampled on its edge
    "SD_CLK",     # SPI clock: a phantom edge shifts every subsequent bit
    "USB_D+",     # differential decision, no re-clocking
    "USB_D-",
    "I2S_DOUT",   # PDM/I2S serial data, self-clocked by the receiver
}

# Push-pull driven and static during a transfer. WARN class.
CONTROL_VICTIMS = {
    "SD_CS", "LCD_CS", "LCD_DC", "LCD_RST",
}

# One parallel bus, latched together on one LCD_WR edge. INFO class.
LCD_DATA_BUS = {f"LCD_D{i}" for i in range(8)}

# Pairs whose tight coupling IS the design. Keyed by frozenset of logical net
# names, value is the reason.
COUPLED_BY_DESIGN = {
    frozenset({"USB_D+", "USB_D-"}):
        "differential pair — tight, symmetric coupling is the specification; "
        "separating them would raise the differential impedance and unbalance "
        "the common-mode return",
    frozenset({"SPK+", "SPK-"}):
        "PAM8403 bridge-tied speaker output — a differential pair carrying the "
        "same signal in antiphase, deliberately routed together",
}


def logical(name):
    """Collapse series-element net splits into one logical signal name."""
    return LOGICAL_NET.get(name, name)


def victim_class(a, b):
    """Verdict class for a logical net pair. Returns (class, reason)."""
    pair = frozenset({a, b})
    if pair in COUPLED_BY_DESIGN:
        return "DESIGN", COUPLED_BY_DESIGN[pair]
    if a in LCD_DATA_BUS and b in LCD_DATA_BUS:
        return "INTRA-BUS", ("both latched on the same LCD_WR edge and held "
                             "for the whole write cycle")
    if a in CRITICAL_VICTIMS or b in CRITICAL_VICTIMS:
        who = a if a in CRITICAL_VICTIMS else b
        return "CRITICAL", f"{who} is an asynchronous strobe/clock/USB net"
    if a in CONTROL_VICTIMS or b in CONTROL_VICTIMS:
        who = a if a in CONTROL_VICTIMS else b
        return "CONTROL", f"{who} is push-pull driven and static during transfers"
    return "OTHER", "no timing-critical member"


# ── Geometry ─────────────────────────────────────────────────────────

def _unit(seg):
    """Unit direction vector and length of a segment, or None if degenerate."""
    dx = seg["x2"] - seg["x1"]
    dy = seg["y2"] - seg["y1"]
    n = math.hypot(dx, dy)
    if n < MIN_SEGMENT_MM:
        return None
    return dx / n, dy / n, n


def _band_interval(m, c, limit, lo, hi):
    """{t in [lo, hi] : |m*t + c| < limit} as an interval, or None.

    The signed centreline offset between two near-parallel segments is linear
    in the position along the run, so the set where the offset is inside a
    band is one interval and its bounds are exact, not sampled.
    """
    if limit <= 0.0 or hi <= lo:
        return None
    if abs(m) < 1e-12:
        return (lo, hi) if abs(c) < limit else None
    t1 = (-limit - c) / m
    t2 = (limit - c) / m
    a, b = (t1, t2) if t1 <= t2 else (t2, t1)
    a, b = max(lo, a), min(hi, b)
    return (a, b) if b > a else None


def _union_length(intervals):
    """Total length covered by a list of (start, end) intervals, once each.

    Coupled length MUST be a union and not a sum. One net's run is stored as
    several collinear segments, and the opposing net's run is split at its own
    corners, so the same physical millimetre of parallel routing is produced by
    several segment pairs. Summing counted it once per pair and reported co-runs
    longer than the board.
    """
    if not intervals:
        return 0.0
    total = 0.0
    cur_a, cur_b = None, None
    for a, b in sorted(intervals):
        if cur_b is None or a > cur_b:
            if cur_b is not None:
                total += cur_b - cur_a
            cur_a, cur_b = a, b
        elif b > cur_b:
            cur_b = b
    if cur_b is not None:
        total += cur_b - cur_a
    return total


def coupling(s1, s2):
    """Coupling geometry of two segments, or None if they do not co-run.

    Returns a dict with the overlap length, the length spent below 1W and
    below 3W of edge gap, the minimum edge gap over the overlap, and the point
    at which that minimum occurs.
    """
    u1 = _unit(s1)
    u2 = _unit(s2)
    if u1 is None or u2 is None:
        return None
    ux, uy, _ = u1
    vx, vy, _ = u2

    cos_ang = ux * vx + uy * vy
    if abs(cos_ang) < math.cos(math.radians(PARALLEL_ANGLE_TOL_DEG)):
        return None
    # Anti-parallel segments are parallel runs driven in opposite directions;
    # flip one so the shared axis is well defined.
    if cos_ang < 0:
        vx, vy = -vx, -vy
        p2a = (s2["x2"], s2["y2"])
        p2b = (s2["x1"], s2["y1"])
    else:
        p2a = (s2["x1"], s2["y1"])
        p2b = (s2["x2"], s2["y2"])
    p1a = (s1["x1"], s1["y1"])
    p1b = (s1["x2"], s1["y2"])

    # Common axis = the bisector of the two directions, so neither segment is
    # privileged and the projection error is split evenly between them.
    bx, by = ux + vx, uy + vy
    bn = math.hypot(bx, by)
    if bn < 1e-12:
        return None
    dx, dy = bx / bn, by / bn
    nx, ny = -dy, dx

    ox, oy = p1a

    def proj(p):
        rx, ry = p[0] - ox, p[1] - oy
        return rx * dx + ry * dy, rx * nx + ry * ny

    t1a, s1a = proj(p1a)
    t1b, s1b = proj(p1b)
    t2a, s2a = proj(p2a)
    t2b, s2b = proj(p2b)

    lo = max(min(t1a, t1b), min(t2a, t2b))
    hi = min(max(t1a, t1b), max(t2a, t2b))
    if hi - lo <= 0.0:
        return None

    # Signed perpendicular offset of each centreline as a function of t.
    def line(ta, sa, tb, sb):
        if abs(tb - ta) < 1e-12:
            return 0.0, (sa + sb) / 2.0
        m = (sb - sa) / (tb - ta)
        return m, sa - m * ta

    m1, c1 = line(t1a, s1a, t1b, s1b)
    m2, c2 = line(t2a, s2a, t2b, s2b)
    m, c = m1 - m2, c1 - c2  # signed centreline separation, linear in t

    half = (s1["width"] + s2["width"]) / 2.0
    w = max(s1["width"], s2["width"])

    # Edge gap < G  <=>  |centreline separation| < G + half.
    band_1w = _band_interval(m, c, TIGHT_GAP_W * w + half, lo, hi)
    band_3w = _band_interval(m, c, CLOSE_GAP_W * w + half, lo, hi)

    # Minimum |separation| over [lo, hi]: at an endpoint, or zero if the sign
    # changes inside the interval (the centrelines cross).
    d_lo, d_hi = m * lo + c, m * hi + c
    if d_lo * d_hi < 0.0:
        sep, t_at = 0.0, (-c / m if abs(m) > 1e-12 else lo)
    elif abs(d_lo) <= abs(d_hi):
        sep, t_at = abs(d_lo), lo
    else:
        sep, t_at = abs(d_hi), hi

    def span(lambda_len):
        """Length of an interval given in bisector-axis units."""
        return 0.0 if lambda_len is None else lambda_len[1] - lambda_len[0]

    return {
        "overlap_mm": hi - lo,
        "len_1w_mm": span(band_1w),
        "len_3w_mm": span(band_3w),
        "band_1w": band_1w,
        "band_3w": band_3w,
        # Endpoint projections of each segment on the bisector axis. The caller
        # uses these to re-express a band in ONE net's own arc-length
        # coordinate, which is what makes the union in _union_length() valid.
        "t_s1": (t1a, t1b),
        "t_s2": (t2a, t2b),
        "min_gap_mm": sep - half,
        "w_mm": w,
        "at": (ox + dx * t_at, oy + dy * t_at),
    }


# ── Candidate search ─────────────────────────────────────────────────

def _bbox(seg, pad):
    return (min(seg["x1"], seg["x2"]) - pad, min(seg["y1"], seg["y2"]) - pad,
            max(seg["x1"], seg["x2"]) + pad, max(seg["y1"], seg["y2"]) + pad)


def candidate_pairs(segs):
    """Index pairs whose expanded bounding boxes overlap, one layer's worth.

    A uniform grid keeps this near-linear: the full O(n^2) sweep is affordable
    at today's ~700 segments but stops being so the moment the board grows a
    second routing region.
    """
    cells = {}
    boxes = []
    for i, s in enumerate(segs):
        b = _bbox(s, COUPLING_SEARCH_MM / 2.0)
        boxes.append(b)
        for cx in range(int(b[0] // GRID_CELL_MM), int(b[2] // GRID_CELL_MM) + 1):
            for cy in range(int(b[1] // GRID_CELL_MM),
                            int(b[3] // GRID_CELL_MM) + 1):
                cells.setdefault((cx, cy), []).append(i)

    seen = set()
    for bucket in cells.values():
        for a in range(len(bucket)):
            i = bucket[a]
            bi = boxes[i]
            for b in range(a + 1, len(bucket)):
                j = bucket[b]
                key = (i, j) if i < j else (j, i)
                if key in seen:
                    continue
                bj = boxes[j]
                if (bi[0] > bj[2] or bj[0] > bi[2]
                        or bi[1] > bj[3] or bj[1] > bi[3]):
                    continue
                seen.add(key)
    return seen


def _check_search_radius(segs):
    """The prefilter must not be able to hide a pair the verdict law judges."""
    if not segs:
        return None
    widest = max(s["width"] for s in segs)
    # Worst case both traces are the widest one: the WARN law reaches out to
    # 3W of edge gap plus both half-widths, i.e. 4W of centreline separation.
    needed = CLOSE_GAP_W * widest + widest
    if COUPLING_SEARCH_MM < needed:
        return (f"COUPLING_SEARCH_MM={COUPLING_SEARCH_MM} mm is smaller than "
                f"the {needed:.2f} mm reach implied by {CLOSE_GAP_W:g}W on the "
                f"widest signal trace ({widest} mm) — the prefilter would hide "
                f"pairs the verdict law judges")
    return None


# ── Analysis ─────────────────────────────────────────────────────────

def analyze(cache):
    """Aggregate coupling per logical net pair. Returns (pairs, stats)."""
    net_name = {n["id"]: n["name"] for n in cache["nets"]}

    segs_by_layer = {}
    considered = 0
    for s in cache["segments"]:
        raw = net_name.get(s["net"], "")
        if raw in QUIET_DC_NETS:
            continue
        seg = dict(s)
        seg["net_name"] = logical(raw)
        segs_by_layer.setdefault(s["layer"], []).append(seg)
        considered += 1

    all_signal = [s for segs in segs_by_layer.values() for s in segs]
    radius_error = _check_search_radius(all_signal)

    pairs = {}
    pair_count = 0
    for layer, segs in segs_by_layer.items():
        for i, j in candidate_pairs(segs):
            s1, s2 = segs[i], segs[j]
            if s1["net_name"] == s2["net_name"]:
                continue
            pair_count += 1
            c = coupling(s1, s2)
            if c is None or c["overlap_mm"] <= 0.0:
                continue
            names = tuple(sorted((s1["net_name"], s2["net_name"])))
            key = (names, layer)
            rec = pairs.get(key)
            if rec is None:
                rec = pairs[key] = {
                    "nets": names, "layer": layer,
                    "spans_1w": {}, "spans_3w": {},
                    "min_gap_mm": float("inf"), "w_at_min": 0.0,
                    "at": (0.0, 0.0),
                }

            # Anchor the measurement on the alphabetically-first net's segment
            # so every band lands in one fixed arc-length coordinate per
            # segment and overlapping contributions collapse instead of adding.
            if s1["net_name"] == names[0]:
                anchor_idx, anchor_t, anchor_seg = i, c["t_s1"], s1
            else:
                anchor_idx, anchor_t, anchor_seg = j, c["t_s2"], s2
            t_lo, t_hi = min(anchor_t), max(anchor_t)
            arc = _unit(anchor_seg)[2]
            scale = arc / (t_hi - t_lo) if (t_hi - t_lo) > 1e-12 else 0.0

            def to_arc(band, t_lo=t_lo, scale=scale):
                if band is None:
                    return None
                return ((band[0] - t_lo) * scale, (band[1] - t_lo) * scale)

            for name, band in (("spans_1w", to_arc(c["band_1w"])),
                               ("spans_3w", to_arc(c["band_3w"]))):
                if band is not None:
                    rec[name].setdefault(anchor_idx, []).append(band)

            if c["min_gap_mm"] < rec["min_gap_mm"]:
                rec["min_gap_mm"] = c["min_gap_mm"]
                rec["w_at_min"] = c["w_mm"]
                rec["at"] = c["at"]

    results = []
    for rec in pairs.values():
        rec["len_1w_mm"] = sum(_union_length(v) for v in rec["spans_1w"].values())
        rec["len_3w_mm"] = sum(_union_length(v) for v in rec["spans_3w"].values())
        a, b = rec["nets"]
        cls, reason = victim_class(a, b)
        verdict = "PASS"
        if cls == "CRITICAL" and rec["len_1w_mm"] > TIGHT_CORUN_FAIL_MM:
            verdict = "FAIL"
        elif cls in ("CRITICAL", "CONTROL", "OTHER") and \
                rec["len_3w_mm"] > CLOSE_CORUN_WARN_MM:
            verdict = "WARN"
        elif cls in ("INTRA-BUS", "DESIGN") and rec["len_3w_mm"] > 0.0:
            verdict = "INFO"
        rec.update({"class": cls, "reason": reason, "verdict": verdict})
        results.append(rec)

    results.sort(key=lambda r: (-r["len_1w_mm"], r["min_gap_mm"]))
    stats = {
        "segments_considered": considered,
        "layers": sorted(segs_by_layer),
        "candidate_pairs": pair_count,
        "coupled_pairs": len(results),
        "radius_error": radius_error,
    }
    return results, stats


# ── Self-test ────────────────────────────────────────────────────────

def _seg(x1, y1, x2, y2, w=0.2, layer="B.Cu", net=1):
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "width": w, "layer": layer, "net": net}


def selftest():
    """Hand-computed geometry cases. Returns the number of failures."""
    fails = []
    total = 0

    def check(name, got, want, tol=1e-6):
        nonlocal total
        total += 1
        ok = got is not None and abs(got - want) <= tol
        print(f"  {'PASS' if ok else 'FAIL'}  {name}"
              f"{'' if ok else f'  got {got!r}, want {want!r}'}")
        if not ok:
            fails.append(name)

    # Case 1 — two 0.2 mm traces, centrelines 0.4 mm apart, 10 mm of overlap.
    # Edge gap = 0.4 - 0.2 = 0.2 mm, which is exactly 1.0W. The band tested is
    # a strict inequality, so nothing sits below 1W and all 10 mm sits below
    # 3W (edge gap 0.6 mm).
    c = coupling(_seg(0, 0, 10, 0), _seg(0, 0.4, 10, 0.4))
    check("case1 overlap is 10 mm", c["overlap_mm"], 10.0)
    check("case1 min edge gap is 0.20 mm", c["min_gap_mm"], 0.2)
    check("case1 nothing below 1W", c["len_1w_mm"], 0.0)
    check("case1 all 10 mm below 3W", c["len_3w_mm"], 10.0)

    # Case 2 — perpendicular segments are a crossing, not a co-run.
    check("case2 perpendicular pair is rejected",
          0.0 if coupling(_seg(0, 0, 10, 0), _seg(5, -5, 5, 5)) is None else 1.0,
          0.0)

    # Case 3 — converging pair. B runs from (0, 1.0) to (10, 0.5): slope
    # -0.05, i.e. 2.86 deg, inside the 10 deg window. Centreline separation
    # is 1.0 - 0.05t. Edge gap = separation - 0.2, so edge gap < 1W = 0.2 mm
    # requires separation < 0.4, i.e. t > 12 — never inside [0, 10], so 0 mm.
    # Edge gap < 3W = 0.6 mm requires separation < 0.8, i.e. t > 4: 6 mm.
    # Minimum edge gap is at t = 10: 0.5 - 0.2 = 0.3 mm.
    c = coupling(_seg(0, 0, 10, 0), _seg(0, 1.0, 10, 0.5))
    check("case3 nothing below 1W", c["len_1w_mm"], 0.0, tol=2e-3)
    check("case3 6 mm below 3W", c["len_3w_mm"], 6.0, tol=2e-3)
    check("case3 min edge gap is 0.30 mm", c["min_gap_mm"], 0.3, tol=2e-3)

    # Case 4 — 15 deg apart is outside the parallel window.
    ang = math.radians(15.0)
    check("case4 15 deg pair is rejected",
          0.0 if coupling(
              _seg(0, 0, 10, 0),
              _seg(0, 0.4, 10 * math.cos(ang), 0.4 + 10 * math.sin(ang))
          ) is None else 1.0,
          0.0)

    # Case 5 — anti-parallel segments still co-run. Same geometry as case 1
    # with B's endpoints swapped.
    c = coupling(_seg(0, 0, 10, 0), _seg(10, 0.4, 0, 0.4))
    check("case5 anti-parallel overlap is 10 mm", c["overlap_mm"], 10.0)
    check("case5 anti-parallel min gap is 0.20 mm", c["min_gap_mm"], 0.2)

    # Case 6 — partial overlap: B spans t in [6, 20], A spans [0, 10].
    c = coupling(_seg(0, 0, 10, 0), _seg(6, 0.4, 20, 0.4))
    check("case6 partial overlap is 4 mm", c["overlap_mm"], 4.0)

    # Case 7 — interval union, the fix for cross-segment double counting.
    check("case7 overlapping intervals merge",
          _union_length([(0.0, 10.0), (5.0, 15.0)]), 15.0)
    check("case7 duplicate intervals count once",
          _union_length([(0.0, 10.0), (0.0, 10.0)]), 10.0)
    check("case7 disjoint intervals add",
          _union_length([(0.0, 2.0), (5.0, 8.0)]), 5.0)

    # Case 8 — end to end. One 10 mm LCD_WR segment runs beside SD_CLK, which
    # is stored as two 5 mm collinear segments. Centrelines are 0.35 mm apart,
    # so the edge gap is 0.35 - 0.20 = 0.15 mm, inside 1W = 0.2 mm, for the
    # whole run. The coupled length must be 10 mm (the physical stretch), not
    # 20 mm (once per segment pair) — and 10 mm > 5 mm must FAIL, which also
    # proves the verdict law is not a no-op on a board that currently passes.
    synth = {
        "nets": [{"id": 1, "name": "LCD_WR"}, {"id": 2, "name": "SD_CLK"}],
        "segments": [
            _seg(0, 0, 10, 0, net=1),
            _seg(0, 0.35, 5, 0.35, net=2),
            _seg(5, 0.35, 10, 0.35, net=2),
        ],
    }
    res, _ = analyze(synth)
    check("case8 one coupled pair found", float(len(res)), 1.0)
    check("case8 coupled length is 10 mm not 20", res[0]["len_1w_mm"], 10.0,
          tol=1e-3)
    check("case8 CRITICAL pair at 0.15 mm for 10 mm FAILs",
          1.0 if res[0]["verdict"] == "FAIL" else 0.0, 1.0)

    # Case 9 — same geometry between two LCD data lines is the allowed
    # intra-bus class and must never fail, however tight it is.
    synth_bus = dict(synth, nets=[{"id": 1, "name": "LCD_D0"},
                                  {"id": 2, "name": "LCD_D1"}])
    res_bus, _ = analyze(synth_bus)
    check("case9 intra-bus pair is INFO, not FAIL",
          1.0 if res_bus[0]["verdict"] == "INFO" else 0.0, 1.0)

    print()
    print(f"Results: {total - len(fails)} checks passed, {len(fails)} failed")
    return 1 if fails else 0


# ── Main ─────────────────────────────────────────────────────────────

def main():
    try:
        cache = load_cache()
    except Exception as exc:  # noqa: BLE001 — tooling failure, not a verdict
        print(f"  ERROR unable to parse the PCB: {exc}", file=sys.stderr)
        return 2

    results, stats = analyze(cache)

    print()
    print("── Crosstalk (3W rule on signal pairs) ──")
    print()
    print(f"  Signal segments   : {stats['segments_considered']} "
          f"on {', '.join(stats['layers'])}")
    print(f"  Candidate pairs   : {stats['candidate_pairs']} "
          f"(bbox prefilter, {COUPLING_SEARCH_MM:g} mm reach)")
    print(f"  Co-running pairs  : {stats['coupled_pairs']}")
    print(f"  FAIL law          : CRITICAL victim with > "
          f"{TIGHT_CORUN_FAIL_MM:g} mm below {TIGHT_GAP_W:g}W edge gap")
    print(f"  WARN law          : any pair with > "
          f"{CLOSE_CORUN_WARN_MM:g} mm below {CLOSE_GAP_W:g}W edge gap")
    print()

    if stats["radius_error"]:
        print(f"  ERROR {stats['radius_error']}", file=sys.stderr)
        return 2

    failures = [r for r in results if r["verdict"] == "FAIL"]
    warnings = [r for r in results if r["verdict"] == "WARN"]
    infos = [r for r in results if r["verdict"] == "INFO"]

    for r in failures + warnings:
        a, b = r["nets"]
        print(f"  {r['verdict']}  {a} || {b}  [{r['class']}] on {r['layer']}"
              f"  min edge gap {r['min_gap_mm']:.3f} mm "
              f"({r['min_gap_mm'] / r['w_at_min']:.2f}W at "
              f"({r['at'][0]:.2f}, {r['at'][1]:.2f}))"
              f"  coupled {r['len_1w_mm']:.2f} mm < 1W, "
              f"{r['len_3w_mm']:.2f} mm < 3W")
        print(f"        {r['reason']}")

    for r in infos:
        a, b = r["nets"]
        print(f"  INFO  {a} || {b}  [{r['class']}] on {r['layer']}"
              f"  min edge gap {r['min_gap_mm']:.3f} mm "
              f"({r['min_gap_mm'] / r['w_at_min']:.2f}W)"
              f"  coupled {r['len_1w_mm']:.2f} mm < 1W, "
              f"{r['len_3w_mm']:.2f} mm < 3W — allowed: {r['reason']}")

    if not failures:
        print()
        print("  PASS  no CRITICAL victim runs inside "
              f"{TIGHT_GAP_W:g}W for more than {TIGHT_CORUN_FAIL_MM:g} mm")

    print()
    print(f"Results: {stats['coupled_pairs'] - len(failures) - len(warnings)} "
          f"passed, {len(failures)} failed, {len(warnings)} warned, "
          f"{len(infos)} allowed by class")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
