#!/usr/bin/env python3
"""Trace-length matching on the buses whose members must switch together.

The gap this closes
-------------------
`verify_usb_impedance` measures intra-pair skew, but only for USB, and
nothing on the board looks at the buses that actually carry parallel
data: the ILI9488 8080 bus (LCD_WR strobing LCD_D0..D7) and the SD SPI
group (SD_CLK against SD_MOSI/SD_MISO). A regenerated board can reroute
one bit of the LCD bus the long way round and every other gate stays
green: the net is connected, isolated, impedance-irrelevant and DRC
clean. Length matching is the one property nobody measures.

Why the thresholds are not the physics
--------------------------------------
Run the physics first and the honest answer is that this board cannot
fail a skew check. The whole design is slow:

  * USB is Full Speed, 12 Mbit/s — an 83.3 ns unit interval and a 4 ns
    minimum driver edge.
  * The LCD write strobe tops out at 20 MHz — a 50 ns cycle.
  * SD SPI tops out at 40 MHz — a 25 ns cycle.

On FR-4 a millimetre of trace is about 7 ps (see PROP_DELAY_S_PER_MM
below). So the LCD bus's current 10 mm of spread is roughly 74 ps
against a 15 ns setup margin — half a percent. You could add a hundred
millimetres to one data line and the panel would not notice.

That leaves two ways to write this gate. Set the threshold at the
electrical budget and it can never fire, which makes it decoration. Or
admit what it is actually for: catching the day the generator reroutes a
bus member and nobody notices. So each group's FAIL threshold is

    min(electrical budget, blunder bound)

where the electrical budget is derived from that bus's own timing (the
numbers are printed, so the margin is visible) and the blunder bound is
BLUNDER_FRACTION_OF_MEAN_LENGTH of the group's own mean routed length.
The second term is what binds on this board, and it is deliberate: a bus
member that differs from its peers by more than 40 % of the bus's own
length did not take the same path across the board, and that is a
routing regression whether or not it is electrically harmful. It also
scales itself — it needs no retuning when the board is re-laid out.

WARN sits at half the FAIL threshold and never affects the exit code.

Length accounting
-----------------
Per net: the summed length of its routed segments, plus BOARD_THICKNESS_MM
per via. The via term is an upper bound — a via on a 4-layer board may
only span F.Cu to In1.Cu, a third of the barrel — because the cache does
not record via spans. Overstating it is the safe direction here: it can
only inflate a measured delta, never hide one. It matters at all only
because the groups below differ by up to 4 vias, i.e. up to 6.4 mm.

Usage:
    python3 scripts/verify_length_match.py
    python3 scripts/verify_length_match.py --selftest
    Exit 0 = pass, 1 = failure, 2 = tooling/environment error
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pcb_cache import load_cache  # noqa: E402

# ── Physics ──────────────────────────────────────────────────────────

C_MM_PER_S = 2.99792458e11

# Effective permittivity seen by a trace on this stackup. An outer-layer
# microstrip sits half in air, so it runs fast (er_eff ~= 3.2); an inner
# stripline is fully embedded in FR-4 and runs slow (er_eff ~= 4.6).
# Traces here use both, and the gate has no per-layer breakdown, so it
# takes the slow figure: a given millimetre of skew is assumed to cost
# the most delay it can, and a given picosecond budget therefore converts
# to the fewest millimetres. Both directions land on the strict side.
#
# verify_usb_impedance.py uses the microstrip figure (6.0 ps/mm) for its
# own derivation; the two must stay within that 3.2-4.6 window, and this
# gate is intentionally the conservative end of it.
ER_EFF_MICROSTRIP = 3.2
ER_EFF_STRIPLINE = 4.6


def prop_delay_s_per_mm(er_eff):
    """One-way propagation delay of a trace, seconds per millimetre."""
    return math.sqrt(er_eff) / C_MM_PER_S


PROP_DELAY_S_PER_MM = prop_delay_s_per_mm(ER_EFF_STRIPLINE)  # ~7.15 ps/mm

# Finished board thickness — the length of a full via barrel.
BOARD_THICKNESS_MM = 1.6

# ── Threshold policy ─────────────────────────────────────────────────

# Share of the available timing margin that trace skew is allowed to
# consume. Allocating no more than 10 % of a setup budget to interconnect
# skew is the usual split; the remaining 90 % belongs to driver jitter,
# receiver uncertainty and temperature.
SKEW_FRACTION_OF_TIMING_MARGIN = 0.10

# The blunder bound described in the module docstring: skew larger than
# this share of the group's own mean routed length means one member took
# a structurally different path.
BLUNDER_FRACTION_OF_MEAN_LENGTH = 0.40

# WARN threshold as a share of the FAIL threshold.
WARN_FRACTION_OF_FAIL = 0.5

# ── Bus timing ───────────────────────────────────────────────────────

# USB 2.0 Full Speed. Same source data as verify_usb_impedance.py: the
# spec's 4 ns minimum driver rise/fall time (table 7-9) and the 12 Mbit/s
# line rate. Skew is allowed 5 % of the edge (so the differential
# crossing point barely moves) or 1 % of the unit interval (so it cannot
# eat the eye), whichever is tighter. At Full Speed the edge term binds.
USB_BITRATE_BPS = 12e6
USB_RISE_TIME_S = 4e-9
USB_SKEW_FRACTION_OF_RISE_TIME = 0.05
USB_SKEW_FRACTION_OF_UI = 0.01

# ILI9488 8080-II write cycle. The ESP32-S3 LCD_CAM peripheral drives the
# data lines and WR from one clock, so data is nominally valid for half a
# strobe period around the latching edge; the panel's own setup and hold
# requirements eat into that, and what is left is the margin trace skew
# competes for.
LCD_STROBE_HZ = 20e6
LCD_PANEL_SETUP_S = 10e-9   # tDST, ILI9488 datasheet AC characteristics
LCD_PANEL_HOLD_S = 10e-9    # tDHT

# SD SPI. The card samples MOSI half a clock after the driving edge; the
# SD Physical Layer spec asks for 6 ns of input setup in high-speed mode.
SD_CLOCK_HZ = 40e6
SD_CARD_INPUT_SETUP_S = 6e-9

# ── Net groups ───────────────────────────────────────────────────────

# Each USB pair member is split by its series termination resistor, so
# the electrical link is the union of the connector-side and MCU-side
# nets. Anything that measures only one half measures half a trace.
USB_DP_LINK = ("USB_D+", "USB_DP_MCU")
USB_DM_LINK = ("USB_D-", "USB_DM_MCU")

LCD_DATA_NETS = [f"LCD_D{i}" for i in range(8)]
LCD_STROBE_NET = "LCD_WR"
SD_CLOCK_NET = "SD_CLK"
SD_DATA_NETS = ["SD_MOSI", "SD_MISO"]


# ── Derived budgets ──────────────────────────────────────────────────

def usb_skew_budget_s():
    """Intra-pair skew budget for the configured USB speed, seconds."""
    ui_s = 1.0 / USB_BITRATE_BPS
    return min(USB_SKEW_FRACTION_OF_RISE_TIME * USB_RISE_TIME_S,
               USB_SKEW_FRACTION_OF_UI * ui_s)


def lcd_setup_margin_s():
    """Setup margin left for skew on the 8080 bus, seconds.

    Half a strobe period of nominal data validity, minus whichever of the
    panel's setup and hold requirements is larger.
    """
    half_period_s = 0.5 / LCD_STROBE_HZ
    return half_period_s - max(LCD_PANEL_SETUP_S, LCD_PANEL_HOLD_S)


def sd_setup_margin_s():
    """Setup margin left for skew on the SD SPI bus, seconds."""
    return 0.5 / SD_CLOCK_HZ - SD_CARD_INPUT_SETUP_S


def mm_from_s(seconds):
    return seconds / PROP_DELAY_S_PER_MM


def s_from_mm(mm):
    return mm * PROP_DELAY_S_PER_MM


def thresholds(skew_budget_s, mean_length_mm):
    """FAIL and WARN skew thresholds in mm for one group.

    `skew_budget_s` is the skew the bus timing can absorb, already net of
    whatever share of the margin the caller allocates to interconnect.
    The blunder bound is what a deliberate route can plausibly look like.
    The tighter of the two decides, and on this board that is always the
    blunder bound.
    """
    electrical_mm = mm_from_s(skew_budget_s)
    blunder_mm = BLUNDER_FRACTION_OF_MEAN_LENGTH * mean_length_mm
    fail_mm = min(electrical_mm, blunder_mm)
    return {
        "electrical_mm": electrical_mm,
        "blunder_mm": blunder_mm,
        "fail_mm": fail_mm,
        "warn_mm": fail_mm * WARN_FRACTION_OF_FAIL,
        "binding": "electrical" if electrical_mm < blunder_mm else "blunder",
    }


# ── Measurement ──────────────────────────────────────────────────────

def measure_nets(cache):
    """net name -> {segments_mm, vias, barrel_mm, total_mm}."""
    name_of = {n["id"]: n["name"] for n in cache["nets"]}
    out = {}

    def slot(net_id):
        name = name_of.get(net_id)
        if not name:
            return None
        return out.setdefault(name, {"segments_mm": 0.0, "vias": 0,
                                     "barrel_mm": 0.0, "total_mm": 0.0})

    for s in cache["segments"]:
        e = slot(s["net"])
        if e is not None:
            e["segments_mm"] += math.hypot(s["x2"] - s["x1"],
                                           s["y2"] - s["y1"])
    for v in cache["vias"]:
        e = slot(v["net"])
        if e is not None:
            e["vias"] += 1

    for e in out.values():
        e["barrel_mm"] = e["vias"] * BOARD_THICKNESS_MM
        e["total_mm"] = e["segments_mm"] + e["barrel_mm"]
    return out


def link_length(measured, nets):
    """Total length of an electrical link spanning one or more nets."""
    return sum(measured.get(n, {}).get("total_mm", 0.0) for n in nets)


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

    def skew(self, name, measured_mm, lim, detail):
        if measured_mm > lim["fail_mm"]:
            level = "FAIL"
        elif measured_mm > lim["warn_mm"]:
            level = "WARN"
        else:
            level = "PASS"
        self.verdict(level, name,
                     f"{measured_mm:.2f} mm "
                     f"({s_from_mm(measured_mm) * 1e12:.0f} ps)  "
                     f"warn>{lim['warn_mm']:.1f} "
                     f"fail>{lim['fail_mm']:.1f} mm  "
                     f"— {detail}")
        return level


# ── Checks ───────────────────────────────────────────────────────────

def check_present(rep, measured, needed):
    """Every net the gate measures must exist and carry copper."""
    missing = [n for n in needed
               if measured.get(n, {}).get("segments_mm", 0.0) <= 0.0]
    if missing:
        rep.verdict("FAIL", "all measured nets are routed",
                    f"no routed copper on {', '.join(missing)} — a length "
                    f"check cannot mean anything on an unrouted net")
        return False
    rep.verdict("PASS", "all measured nets are routed",
                f"{len(needed)} nets carry copper")
    return True


def check_usb(rep, measured):
    dp = link_length(measured, USB_DP_LINK)
    dm = link_length(measured, USB_DM_LINK)
    delta = abs(dp - dm)
    mean = (dp + dm) / 2
    budget_s = usb_skew_budget_s()
    lim = thresholds(budget_s, mean)

    ui_ns = 1e9 / USB_BITRATE_BPS
    rep.info(f"USB Full Speed {USB_BITRATE_BPS / 1e6:g} Mbit/s: "
             f"{ui_ns:.1f} ns unit interval, {USB_RISE_TIME_S * 1e9:g} ns "
             f"driver edge -> {budget_s * 1e12:.0f} ps skew budget "
             f"= {mm_from_s(budget_s):.1f} mm")
    rep.info(f"D+ link {'+'.join(USB_DP_LINK)} = {dp:.2f} mm, "
             f"D- link {'+'.join(USB_DM_LINK)} = {dm:.2f} mm")
    rep.skew("USB D+/D- intra-pair skew", delta, lim,
             f"{lim['binding']} bound binds "
             f"(electrical {lim['electrical_mm']:.0f} mm, "
             f"blunder {lim['blunder_mm']:.0f} mm)")


def check_lcd(rep, measured):
    lengths = {n: measured[n]["total_mm"] for n in LCD_DATA_NETS
               if n in measured}
    if len(lengths) < 2:
        rep.verdict("FAIL", "LCD data bus skew",
                    "fewer than two LCD data nets found")
        return
    spread = max(lengths.values()) - min(lengths.values())
    mean = sum(lengths.values()) / len(lengths)
    margin_s = lcd_setup_margin_s()
    lim = thresholds(margin_s * SKEW_FRACTION_OF_TIMING_MARGIN, mean)

    longest = max(lengths, key=lengths.get)
    shortest = min(lengths, key=lengths.get)
    rep.info(f"ILI9488 8080 bus at {LCD_STROBE_HZ / 1e6:g} MHz: "
             f"{1e9 / LCD_STROBE_HZ:.0f} ns cycle, "
             f"{0.5e9 / LCD_STROBE_HZ:.1f} ns nominal data validity minus "
             f"{max(LCD_PANEL_SETUP_S, LCD_PANEL_HOLD_S) * 1e9:g} ns panel "
             f"setup/hold -> {margin_s * 1e9:.1f} ns margin; "
             f"{SKEW_FRACTION_OF_TIMING_MARGIN:.0%} of it "
             f"= {lim['electrical_mm']:.0f} mm")
    rep.info(f"LCD_D0..D7 mean {mean:.2f} mm, "
             f"longest {longest} {lengths[longest]:.2f} mm, "
             f"shortest {shortest} {lengths[shortest]:.2f} mm")
    rep.skew("LCD_D0..D7 bus spread", spread, lim,
             f"{lim['binding']} bound binds "
             f"(electrical {lim['electrical_mm']:.0f} mm, "
             f"blunder {lim['blunder_mm']:.0f} mm)")

    if LCD_STROBE_NET not in measured:
        rep.verdict("FAIL", f"{LCD_STROBE_NET} vs data mean",
                    f"{LCD_STROBE_NET} not present")
        return
    wr = measured[LCD_STROBE_NET]["total_mm"]
    rep.info(f"{LCD_STROBE_NET} {wr:.2f} mm — the strobe latches every data "
             f"line, so its skew against the bus is setup/hold error too")
    rep.skew(f"{LCD_STROBE_NET} vs LCD_D0..D7 mean", abs(wr - mean), lim,
             f"{lim['binding']} bound binds "
             f"(electrical {lim['electrical_mm']:.0f} mm, "
             f"blunder {lim['blunder_mm']:.0f} mm)")


def check_sd(rep, measured):
    nets = [SD_CLOCK_NET] + SD_DATA_NETS
    if any(n not in measured for n in nets):
        rep.verdict("FAIL", "SD SPI skew",
                    f"missing {[n for n in nets if n not in measured]}")
        return
    lengths = {n: measured[n]["total_mm"] for n in nets}
    mean = sum(lengths.values()) / len(lengths)
    margin_s = sd_setup_margin_s()
    lim = thresholds(margin_s * SKEW_FRACTION_OF_TIMING_MARGIN, mean)

    rep.info(f"SD SPI at {SD_CLOCK_HZ / 1e6:g} MHz: "
             f"{1e9 / SD_CLOCK_HZ:.1f} ns cycle, "
             f"{0.5e9 / SD_CLOCK_HZ:.1f} ns until the sampling edge minus "
             f"{SD_CARD_INPUT_SETUP_S * 1e9:g} ns card input setup "
             f"-> {margin_s * 1e9:.1f} ns margin; "
             f"{SKEW_FRACTION_OF_TIMING_MARGIN:.0%} of it "
             f"= {lim['electrical_mm']:.0f} mm")
    rep.info("  ".join(f"{n} {v:.2f} mm" for n, v in lengths.items()))
    for data_net in SD_DATA_NETS:
        rep.skew(f"{SD_CLOCK_NET} vs {data_net}",
                 abs(lengths[SD_CLOCK_NET] - lengths[data_net]), lim,
                 f"{lim['binding']} bound binds "
                 f"(electrical {lim['electrical_mm']:.0f} mm, "
                 f"blunder {lim['blunder_mm']:.0f} mm)")


def print_table(rep, measured, nets):
    rep.section("Measured lengths")
    rep.info(f"{'net':12s} {'copper':>9s} {'vias':>5s} {'barrel':>8s} "
             f"{'total':>9s} {'delay':>9s}")
    for n in nets:
        e = measured.get(n)
        if not e:
            rep.info(f"{n:12s} {'— absent from the board —':>43s}")
            continue
        rep.info(f"{n:12s} {e['segments_mm']:8.2f}mm {e['vias']:5d} "
                 f"{e['barrel_mm']:7.2f}mm {e['total_mm']:8.2f}mm "
                 f"{s_from_mm(e['total_mm']) * 1e12:7.0f}ps")


# ── Self-check ───────────────────────────────────────────────────────

def selftest():
    """Hand-computed cases for the measurement and verdict logic."""
    failures = []
    total = 0

    def check(label, got, want, tol=1e-6):
        nonlocal total
        total += 1
        ok = abs(got - want) <= tol if isinstance(want, float) else got == want
        print(f"  {'PASS' if ok else 'FAIL'}  {label}  got={got!r} "
              f"want={want!r}")
        if not ok:
            failures.append(label)

    # Case 1 — length accumulation including via barrels.
    # Two 3-4-5 triangles: 5 mm each. Two vias: 2 x 1.6 = 3.2 mm.
    # Total must be 10 + 3.2 = 13.2 mm.
    cache = {
        "nets": [{"id": 1, "name": "NET_A"}, {"id": 2, "name": "USB_D+"},
                 {"id": 3, "name": "USB_DP_MCU"}],
        "segments": [
            {"x1": 0, "y1": 0, "x2": 3, "y2": 4, "net": 1},
            {"x1": 0, "y1": 0, "x2": 4, "y2": 3, "net": 1},
            {"x1": 0, "y1": 0, "x2": 10, "y2": 0, "net": 2},
            {"x1": 0, "y1": 0, "x2": 0, "y2": 2, "net": 3},
        ],
        "vias": [{"net": 1}, {"net": 1}, {"net": 2}, {"net": 3}],
    }
    m = measure_nets(cache)
    check("NET_A copper", m["NET_A"]["segments_mm"], 10.0)
    check("NET_A barrels", m["NET_A"]["barrel_mm"], 3.2)
    check("NET_A total", m["NET_A"]["total_mm"], 13.2)

    # Case 2 — a USB link is the union of its connector- and MCU-side
    # nets: (10 + 1.6) + (2 + 1.6) = 15.2 mm. Measuring either half alone
    # would report 11.6 or 3.6.
    check("USB D+ link union", link_length(m, USB_DP_LINK), 15.2)

    # Case 3 — verdict tiers. With a 100 mm mean the blunder bound is
    # 40 mm and WARN sits at 20 mm; the electrical term is far looser, so
    # it must not bind.
    lim = thresholds(lcd_setup_margin_s() * SKEW_FRACTION_OF_TIMING_MARGIN,
                     100.0)
    check("blunder bound at 100 mm mean", lim["blunder_mm"], 40.0)
    check("binding term", lim["binding"], "blunder")
    check("warn threshold", lim["warn_mm"], 20.0)
    for value, want in ((5.0, "PASS"), (25.0, "WARN"), (45.0, "FAIL")):
        level = ("FAIL" if value > lim["fail_mm"]
                 else "WARN" if value > lim["warn_mm"] else "PASS")
        check(f"{value:g} mm tier", level, want)

    # Case 4 — the propagation delay really is derived, not typed in.
    check("stripline delay ps/mm",
          round(PROP_DELAY_S_PER_MM * 1e12, 2), 7.15, 0.01)
    check("microstrip delay ps/mm",
          round(prop_delay_s_per_mm(ER_EFF_MICROSTRIP) * 1e12, 2), 5.97, 0.01)

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

    measured = measure_nets(cache)
    all_nets = (list(USB_DP_LINK) + list(USB_DM_LINK) + LCD_DATA_NETS
                + [LCD_STROBE_NET, SD_CLOCK_NET] + SD_DATA_NETS)

    rep = Report()
    print()
    print("Trace-length matching — bus and pair skew")
    print(f"  velocity {PROP_DELAY_S_PER_MM * 1e12:.2f} ps/mm "
          f"(er_eff {ER_EFF_STRIPLINE}, the slow inner-layer case), "
          f"via barrel {BOARD_THICKNESS_MM} mm")

    rep.section("Routing presence")
    routed = check_present(rep, measured, all_nets)

    if routed:
        rep.section("USB differential pair")
        check_usb(rep, measured)

        rep.section("LCD 8080 bus")
        check_lcd(rep, measured)

        rep.section("SD SPI")
        check_sd(rep, measured)

    print_table(rep, measured, all_nets)

    print()
    print(f"Results: {rep.passed} passed, {rep.failed} failed"
          + (f", {rep.warned} warned" if rep.warned else ""))
    return 1 if rep.failed else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    sys.exit(main())
