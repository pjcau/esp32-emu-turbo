#!/usr/bin/env python3
"""Via count and pair symmetry on the nets where layer changes matter.

The gap this closes
-------------------
Nothing on this board counts vias per net. `verify_usb_impedance` checks
that each USB data via has a ground stitching via near it, but not how
many there are, and no gate looks at the LCD strobe, the SD clock or the
I2S output at all. A regenerated board can quietly grow a net from two
vias to twelve — every via legally drilled, plated, stitched and DRC
clean — and the only symptom is a route that has started thrashing
between layers.

Why the budget is NOT an impedance argument
-------------------------------------------
It is tempting to justify a via limit with impedance discontinuity. On
this board that argument is false, and stating it would be worse than
having no gate, because the next person would tighten the numbers to
chase a problem that does not exist. The arithmetic is printed at run
time and works out like this:

  * A via through the 1.6 mm board is about 11 ps of transit — and that
    length is already counted by verify_length_match.py, so it is not a
    discontinuity, it is trace.
  * The discontinuity proper is the barrel's shunt capacitance, roughly
    half a picofarad (derived below from the actual via geometry).
    Against a ~50 ohm source that is a ~30 ps time constant.
  * The fastest edge anywhere on this board is the ESP32 GPIO's ~2 ns,
    and USB Full Speed drivers are slower still at 4 ns. A 2 ns edge is
    about 280 mm long on FR-4; the via is 1.6 mm of it, well under 1 %.

So a via is electrically invisible here, and would remain invisible if
the capacitance estimate were off by a factor of ten. What a via is NOT
invisible for:

  * **Return path.** Every layer change forces the signal's return
    current to find another way home — a stitching via, or the
    plane-to-plane capacitance. That is a real EMC cost and it scales
    with the count, not with the bit rate.
  * **Reliability and yield.** Each via is a drilled hole and two plating
    joints.
  * **Regression detection.** A net that needs eight vias to get across
    a 160 x 75 mm board is telling you the router had a bad time there,
    which is worth seeing before the next respin, not after.

The budget is therefore derived from routing structure rather than from
signalling: see VIAS_PER_LAYER_EXCURSION below.

Usage:
    python3 scripts/verify_via_discontinuity.py
    python3 scripts/verify_via_discontinuity.py --selftest
    Exit 0 = pass, 1 = failure, 2 = tooling/environment error
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pcb_cache import load_cache  # noqa: E402

# ── Stackup and physics ──────────────────────────────────────────────

C_MM_PER_S = 2.99792458e11
# Slow inner-layer case, matching verify_length_match.py.
ER_EFF_STRIPLINE = 4.6
ER_BULK_FR4 = 4.4               # bulk dielectric constant, for via capacitance
BOARD_THICKNESS_MM = 1.6
MM_PER_INCH = 25.4

# Copper clearance a plane keeps from a via barrel, i.e. half the
# difference between antipad and pad diameter. This project's zone
# clearance. The capacitance below scales with it, but the conclusion
# does not: the answer stays "negligible" anywhere in the 0.2-1 pF range
# that any plausible clearance produces.
VIA_ANTIPAD_CLEARANCE_MM = 0.2

# Source impedance seen by a via: an ESP32-S3 GPIO driver is roughly
# 40 ohm, and the USB pair adds a 22 ohm series resistor. 50 ohm is the
# round figure between them and makes the derived RC the larger one.
DRIVER_SOURCE_OHM = 50.0

# Fastest edges present on the board. The ESP32 GPIO figure is the
# binding one; USB Full Speed drivers are specified no faster than 4 ns
# (USB 2.0 table 7-9).
GPIO_EDGE_S = 2e-9
USB_FS_EDGE_S = 4e-9

# ── Budget policy ────────────────────────────────────────────────────

# A deliberate route that has to leave its starting layer spends two
# vias: one down, one back. Everything below is counted in those pairs.
VIAS_PER_LAYER_EXCURSION = 2

# How many excursions a sane route is allowed before it is worth a look,
# and before it is a defect. Two excursions is a route that dived under
# one obstacle and then under a second; four means the router was
# thrashing and the placement or the keep-outs deserve attention.
EXCURSIONS_BEFORE_WARN = 2
EXCURSIONS_BEFORE_FAIL = 4

VIA_BUDGET_WARN = VIAS_PER_LAYER_EXCURSION * EXCURSIONS_BEFORE_WARN   # 4
VIA_BUDGET_FAIL = VIAS_PER_LAYER_EXCURSION * EXCURSIONS_BEFORE_FAIL   # 8

# Intra-pair via asymmetry. Both halves of a differential pair should
# make the same layer changes together. One via of difference is normal
# fan-out asymmetry — the two pads of the ESD device and the two series
# resistors are not mirror images. Beyond a full extra excursion on one
# leg only, the two halves are no longer following the same path.
PAIR_FANOUT_TOLERANCE_VIAS = 1
PAIR_ASYMMETRY_WARN = PAIR_FANOUT_TOLERANCE_VIAS                       # 1
PAIR_ASYMMETRY_FAIL = (PAIR_FANOUT_TOLERANCE_VIAS
                       + VIAS_PER_LAYER_EXCURSION)                     # 3

# ── Nets ─────────────────────────────────────────────────────────────

# Each USB pair member is split by its series termination resistor; the
# electrical link is the union of the connector-side and MCU-side nets.
USB_DP_LINK = ("USB_D+", "USB_DP_MCU")
USB_DM_LINK = ("USB_D-", "USB_DM_MCU")

# Critical nets, as (label, member nets). Everything with an edge fast
# enough or a clock high enough that its return path is worth tracking.
CRITICAL_LINKS = (
    [("USB D+ link", USB_DP_LINK), ("USB D- link", USB_DM_LINK)]
    + [("LCD_WR", ("LCD_WR",))]
    + [(f"LCD_D{i}", (f"LCD_D{i}",)) for i in range(8)]
    + [("SD_CLK", ("SD_CLK",)), ("I2S_DOUT", ("I2S_DOUT",))]
)

TABLE_ROWS = 15


# ── Derivations ──────────────────────────────────────────────────────

def prop_delay_s_per_mm(er_eff=ER_EFF_STRIPLINE):
    return math.sqrt(er_eff) / C_MM_PER_S


def via_capacitance_f(pad_diameter_mm):
    """Shunt capacitance of a via barrel, farads.

    Johnson & Graham's coaxial approximation, which wants inches:

        C[pF] = 1.41 * er * T * D1 / (D2 - D1)

    with T the board thickness, D1 the via pad diameter and D2 the
    antipad diameter in the reference planes.
    """
    d1_in = pad_diameter_mm / MM_PER_INCH
    d2_in = (pad_diameter_mm + 2 * VIA_ANTIPAD_CLEARANCE_MM) / MM_PER_INCH
    t_in = BOARD_THICKNESS_MM / MM_PER_INCH
    return 1.41 * ER_BULK_FR4 * t_in * d1_in / (d2_in - d1_in) * 1e-12


def negligibility(pad_diameter_mm):
    """The numbers behind 'a via is electrically invisible on this board'."""
    tpd = prop_delay_s_per_mm()
    cap_f = via_capacitance_f(pad_diameter_mm)
    return {
        "pad_mm": pad_diameter_mm,
        "cap_f": cap_f,
        "rc_s": DRIVER_SOURCE_OHM * cap_f,
        "barrel_transit_s": BOARD_THICKNESS_MM * tpd,
        "edge_length_mm": GPIO_EDGE_S / tpd,
        "barrel_share_of_edge": BOARD_THICKNESS_MM / (GPIO_EDGE_S / tpd),
        "rc_share_of_edge": (DRIVER_SOURCE_OHM * cap_f) / GPIO_EDGE_S,
        "rc_share_of_usb_edge": (DRIVER_SOURCE_OHM * cap_f) / USB_FS_EDGE_S,
    }


# ── Measurement ──────────────────────────────────────────────────────

def count_vias(cache):
    """net name -> via count, and net name -> list of via pad diameters."""
    name_of = {n["id"]: n["name"] for n in cache["nets"]}
    counts, sizes = {}, {}
    for v in cache["vias"]:
        name = name_of.get(v["net"])
        if not name:
            continue
        counts[name] = counts.get(name, 0) + 1
        sizes.setdefault(name, []).append(v["size"])
    return counts, sizes


def link_vias(counts, nets):
    return sum(counts.get(n, 0) for n in nets)


def median(values):
    if not values:
        return 0.0
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


# ── Report plumbing ──────────────────────────────────────────────────

class Report:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warned = 0

    def section(self, title):
        print()
        print(f"── {title} ──")

    def info(self, text):
        print(f"  INFO  {text}")

    def verdict(self, level, name, detail=""):
        print(f"  {level}  {name}{'  ' + detail if detail else ''}")
        if level == "FAIL":
            self.failed += 1
        elif level == "WARN":
            self.warned += 1
        else:
            self.passed += 1
        return level


def tier(value, warn_above, fail_above):
    if value > fail_above:
        return "FAIL"
    if value > warn_above:
        return "WARN"
    return "PASS"


# ── Checks ───────────────────────────────────────────────────────────

def check_pair_symmetry(rep, counts):
    dp = link_vias(counts, USB_DP_LINK)
    dm = link_vias(counts, USB_DM_LINK)
    delta = abs(dp - dm)
    rep.info(f"D+ link {'+'.join(USB_DP_LINK)} = {dp} vias, "
             f"D- link {'+'.join(USB_DM_LINK)} = {dm} vias")
    rep.info(f"tolerance: {PAIR_ASYMMETRY_WARN} via of fan-out asymmetry is "
             f"normal, {PAIR_ASYMMETRY_FAIL} = one full "
             f"{VIAS_PER_LAYER_EXCURSION}-via layer excursion on one leg only "
             f"plus fan-out; beyond that the halves are not on the same path")
    rep.verdict(tier(delta, PAIR_ASYMMETRY_WARN, PAIR_ASYMMETRY_FAIL),
                "USB D+/D- via symmetry",
                f"delta {delta} via(s) ({dp} vs {dm})  "
                f"warn>{PAIR_ASYMMETRY_WARN} fail>{PAIR_ASYMMETRY_FAIL}  "
                f"— asymmetry costs {delta} extra barrel(s), "
                f"electrically nil at Full Speed (see header), but each one "
                f"is another return-path event on one leg only")


def check_budgets(rep, counts):
    rep.info(f"budget: {VIAS_PER_LAYER_EXCURSION} vias per layer excursion, "
             f"warn above {EXCURSIONS_BEFORE_WARN} excursions "
             f"({VIA_BUDGET_WARN} vias), fail above {EXCURSIONS_BEFORE_FAIL} "
             f"({VIA_BUDGET_FAIL} vias) — a return-path and routing-sanity "
             f"budget, not an impedance one")
    for label, nets in CRITICAL_LINKS:
        n = link_vias(counts, nets)
        detail = f"{n} vias  warn>{VIA_BUDGET_WARN} fail>{VIA_BUDGET_FAIL}"
        excursions = n / VIAS_PER_LAYER_EXCURSION
        if n > VIA_BUDGET_WARN:
            detail += (f"  — {excursions:g} layer excursions; each one hands "
                       f"the return current to the stitching vias")
        rep.verdict(tier(n, VIA_BUDGET_WARN, VIA_BUDGET_FAIL),
                    f"{label} via budget", detail)


def print_table(rep, counts):
    rep.section(f"Via count by net (top {TABLE_ROWS})")
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for name, n in ranked[:TABLE_ROWS]:
        rep.info(f"{name:14s} {n:4d}")
    if len(ranked) > TABLE_ROWS:
        rep.info(f"({len(ranked) - TABLE_ROWS} further nets omitted, "
                 f"{ranked[TABLE_ROWS][1]} vias and below)")


# ── Self-check ───────────────────────────────────────────────────────

def selftest():
    failures = []
    total = 0

    def check(label, got, want, tol=1e-9):
        nonlocal total
        total += 1
        ok = abs(got - want) <= tol if isinstance(want, float) else got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}  got={got!r} "
              f"want={want!r}")
        if not ok:
            failures.append(label)

    # Case 1 — via counting per net, and the USB link as the union of its
    # connector-side and MCU-side nets. D+ has 2 + 1 = 3, D- has 1.
    cache = {
        "nets": [{"id": 1, "name": "USB_D+"}, {"id": 2, "name": "USB_DP_MCU"},
                 {"id": 3, "name": "USB_D-"}, {"id": 4, "name": "USB_DM_MCU"},
                 {"id": 5, "name": "GND"}],
        "vias": ([{"net": 1, "size": 0.6}] * 2 + [{"net": 2, "size": 0.6}]
                 + [{"net": 3, "size": 0.6}] + [{"net": 5, "size": 0.6}] * 9),
    }
    counts, sizes = count_vias(cache)
    check("USB_D+ raw count", counts["USB_D+"], 2)
    check("D+ link union", link_vias(counts, USB_DP_LINK), 3)
    check("D- link union", link_vias(counts, USB_DM_LINK), 1)
    check("GND count", counts["GND"], 9)
    check("median via pad", median(sizes["GND"]), 0.6)

    # Case 2 — the thresholds are built from the excursion model, not
    # typed in: 2 vias per excursion, 2 and 4 excursions.
    check("warn budget", VIA_BUDGET_WARN, 4)
    check("fail budget", VIA_BUDGET_FAIL, 8)
    check("pair asymmetry fail", PAIR_ASYMMETRY_FAIL, 3)

    # Case 3 — verdict tiers at every boundary.
    for n, want in ((0, "PASS"), (4, "PASS"), (5, "WARN"), (8, "WARN"),
                    (9, "FAIL")):
        check(f"{n} vias tier", tier(n, VIA_BUDGET_WARN, VIA_BUDGET_FAIL),
              want)
    for d, want in ((0, "PASS"), (1, "PASS"), (2, "WARN"), (3, "WARN"),
                    (4, "FAIL")):
        check(f"delta {d} tier",
              tier(d, PAIR_ASYMMETRY_WARN, PAIR_ASYMMETRY_FAIL), want)

    # Case 4 — the negligibility numbers. A 0.6 mm pad with 0.2 mm
    # clearance: 1.41 * 4.4 * 0.063" * (0.6/0.4) = 0.586 pF, so a 29 ps
    # RC against 50 ohm — about 1.5 % of the 2 ns GPIO edge.
    neg = negligibility(0.6)
    check("via capacitance pF", round(neg["cap_f"] * 1e12, 2), 0.59, 0.02)
    check("RC ps", round(neg["rc_s"] * 1e12, 1), 29.3, 0.5)
    check("RC share of GPIO edge under 5 %",
          neg["rc_share_of_edge"] < 0.05, True)

    print()
    print(f"Results: {total - len(failures)} passed, {len(failures)} failed")
    return 1 if failures else 0


# ── Main ─────────────────────────────────────────────────────────────

def main():
    try:
        cache = load_cache()
    except Exception as exc:                      # tooling / environment
        print(f"  FAIL  cannot load the PCB cache  {exc}")
        return 2

    counts, sizes = count_vias(cache)
    critical_sizes = [s for _, nets in CRITICAL_LINKS
                      for n in nets for s in sizes.get(n, [])]
    pad_mm = median(critical_sizes) or 0.6
    neg = negligibility(pad_mm)

    rep = Report()
    print()
    print("Via discontinuity — count and pair symmetry on high-speed nets")
    print(f"  {len(cache['vias'])} vias on the board, "
          f"{len(counts)} nets carry at least one")

    rep.section("Why the budget is not an impedance budget")
    rep.info(f"critical-net via pad {pad_mm:g} mm with "
             f"{VIA_ANTIPAD_CLEARANCE_MM:g} mm antipad clearance "
             f"-> {neg['cap_f'] * 1e12:.2f} pF, "
             f"{neg['rc_s'] * 1e12:.0f} ps against a "
             f"{DRIVER_SOURCE_OHM:g} ohm source")
    rep.info(f"fastest edge on the board {GPIO_EDGE_S * 1e9:g} ns "
             f"= {neg['edge_length_mm']:.0f} mm of trace; the "
             f"{BOARD_THICKNESS_MM} mm barrel is "
             f"{neg['barrel_share_of_edge']:.2%} of it and its RC is "
             f"{neg['rc_share_of_edge']:.1%} "
             f"({neg['rc_share_of_usb_edge']:.1%} of the USB "
             f"{USB_FS_EDGE_S * 1e9:g} ns edge)")
    rep.info(f"barrel transit {neg['barrel_transit_s'] * 1e12:.0f} ps is "
             f"trace, not discontinuity — verify_length_match.py already "
             f"counts it. What follows is a return-path and regression "
             f"budget.")

    rep.section("USB pair symmetry")
    check_pair_symmetry(rep, counts)

    rep.section("Via budget on critical nets")
    check_budgets(rep, counts)

    print_table(rep, counts)

    print()
    print(f"Results: {rep.passed} passed, {rep.failed} failed"
          + (f", {rep.warned} warned" if rep.warned else ""))
    return 1 if rep.failed else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
