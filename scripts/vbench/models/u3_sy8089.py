"""U3 — SY8089AAAC synchronous step-down regulator, the +3V3 source.

Every field cites `hardware/datasheets/U3_SY8089AAAC_C78988.pdf`. That file
is the Silergy application note, whose own footer reads "AN_SY8089/A Rev.
0.9A", so that is the revision recorded here rather than a product-datasheet
revision it does not carry.

The load-bearing claim is the output-programming formula, because it is what
sets this board's +3V3 and nothing in the repo had computed it:

    Vout = 0.6 * (1 + R1 / R2)        page 2, pin-description table, pin FB

with R1 the resistor from Vout to FB and R2 from FB to GND. The 0.6 is
V_REF, and page 4's electrical-characteristics table gives it as
0.588 / 0.600 / 0.612 V — so the formula's spread is real and belongs in the
answer. rails.py reads R1 and R2 out of the netlist and the BOM instead of
taking them from here: which resistor is which is a property of the board,
not of the part.
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "U3_SY8089AAAC_C78988.pdf"
REV = "AN_SY8089/A Rev. 0.9A"

# Pin roles: page 2, "Pinout (top view)" pin-description table.
PINS = (
    Pin("1", "EN", "in", "p.2 table 1"),
    Pin("2", "GND", "gnd", "p.2 table 1"),
    Pin("3", "LX", "out", "p.2 table 1"),
    Pin("4", "IN", "power_in", "p.2 table 1"),
    Pin("5", "FB", "analog_in", "p.2 table 1"),
)

U3 = Model(
    ref="U3",
    part="SY8089AAAC",
    mpn="C78988",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="Vout=0.6*(1+R1/R2) — page 2, FB pin description"),
    pins=PINS,
    params={
        # ── Output programming (page 2, FB pin description; page 4 table) ──
        "v_fb_ref": Param((0.588, 0.600, 0.612), "V", locator="p.4 table 1"),

        # ── Input range (page 2 recommended operating conditions, page 4) ──
        "v_in_range": Param((2.7, 5.0, 5.5), "V", locator="p.4 table 1"),
        # Page 2, Absolute Maximum Ratings — the number a bench must not
        # cross, as opposed to the recommended range above.
        "v_in_abs_max": Param(6.0, "V", locator="p.2 section 1"),

        # ── Switches and current capability ─────────────────────────────
        "r_ds_on_pfet": Param(0.110, "ohm", locator="p.4 table 1"),
        "r_ds_on_nfet": Param(0.080, "ohm", locator="p.4 table 1"),
        "i_limit_pfet": Param(3.5, "A", locator="p.4 table 1"),
        # Page 1, Features: "2A continuous, 3A peak load current capability".
        "i_out_continuous": Param(2.0, "A", locator="p.1 section 1"),
        "i_out_peak": Param(3.0, "A", locator="p.1 section 1"),

        # ── Quiescent and enable ────────────────────────────────────────
        "i_quiescent": Param(55e-6, "A", locator="p.4 table 1"),
        "i_shutdown": Param((0.0, 0.1e-6, 1e-6), "A", locator="p.4 table 1"),
        "v_en_rising": Param(1.5, "V", locator="p.4 table 1"),
        "v_en_falling": Param(0.4, "V", locator="p.4 table 1"),
        "v_uvlo": Param(2.5, "V", locator="p.4 table 1"),
        "v_uvlo_hysteresis": Param(0.2, "V", locator="p.4 table 1"),

        # ── Timing (Phase 1.4 transients will need these) ───────────────
        "f_switching": Param(1e6, "Hz", locator="p.4 table 1"),
        "t_soft_start": Param(1.2e-3, "s", locator="p.4 table 1"),
        "t_min_on": Param(75e-9, "s", locator="p.4 table 1"),
        "duty_max": Param(100.0, "%", locator="p.4 table 1"),

        # ── Thermal (Phase 1.5) ─────────────────────────────────────────
        # 170 C/W in SOT23-5 with a 0.6 W package limit at 25 C ambient is
        # the tightest thermal budget on this board by a wide margin. Note 2
        # on page 4 states the measurement condition: 2" x 2" FR-4, 2 oz
        # copper, minimum recommended pad and thermal vias to a bottom-layer
        # ground plane — so this figure already assumes more copper than a
        # SOT23-5 on a signal layer usually gets.
        "theta_ja": Param(170.0, "degC/W", locator="p.2 section 1"),
        "theta_jc": Param(130.0, "degC/W", locator="p.2 section 1"),
        "p_dissipation_max_25c": Param(0.6, "W", locator="p.2 section 1"),
        "t_junction_max": Param(125.0, "degC", locator="p.2 section 1"),
        "t_shutdown": Param(160.0, "degC", locator="p.4 table 1"),

        # ── The feedback divider's own tolerance ────────────────────────
        # Not a property of U3 but of R25/R26, recorded here because
        # v_out_spread is the consumer. Both divider parts are Uniroyal
        # thick-film, model codes 0805W8F1003T5E (R25, C149504) and
        # 0805W8F2202T5E (R26, C17560): the 7th code "F" means +/-1%,
        # per the part-number key on page 2 of the Uniroyal datasheet
        # (section 2.3, "F=+/-1%"). R25's document is held as
        # R16_100k-0805_C149504.pdf — same LCSC part, R16 got there first.
        "r_divider_tolerance": Param(
            0.01, "1", locator="p.2 sec 2.3",
            doc="R26_22k-0805_C17560.pdf"),

        # ── Derived, not cited: the datasheet's own worked example ───────
        # Figure 1 on page 1 draws R1 = 200k, R2 = 100k and labels the
        # output 1.8 V. 0.6 * (1 + 200/100) = 1.8 exactly, which is what
        # T1.2's "each model reproduces its datasheet's own worked example"
        # asks for. Declared derived because it is arithmetic on the
        # formula, not a number lifted off a page.
        "v_out_worked_example": Param(
            1.8, "V", derived_from=("v_fb_ref",),
            formula="0.6 * (1 + 200k/100k) = 1.8 V — figure 1, page 1, "
                    "reproduces the datasheet's own labelled output"),
    },
)


def v_out(r_top_ohm, r_bottom_ohm, v_ref=0.600):
    """Programmed output voltage for a given feedback divider.

    Vout = v_ref * (1 + r_top / r_bottom), page 2, FB pin description.
    `r_top` is Vout->FB, `r_bottom` is FB->GND. Which physical resistor is
    which comes from the netlist, never from this module.
    """
    if r_bottom_ohm <= 0:
        raise ValueError(
            "the bottom divider resistor is zero or missing — FB would sit "
            "at ground and the regulator would run to its duty limit")
    return v_ref * (1.0 + r_top_ohm / r_bottom_ohm)


def v_out_spread(r_top_ohm, r_bottom_ohm, include_resistors=True):
    """(min, typ, max) output from V_REF's tolerance and the divider's.

    The resistor tolerance is the cited +/-1% of the fitted Uniroyal parts
    (r_divider_tolerance above) — it stopped being an assumption on
    2026-07-31 when the part-number key landed in hardware/datasheets/.
    The worst case stacks the divider against itself: Vout is highest with
    R_top high and R_bottom low, and vice versa. `include_resistors=False`
    reproduces the old V_REF-only spread for comparison.
    """
    lo, typ, hi = U3.params["v_fb_ref"].value
    if not include_resistors:
        return (v_out(r_top_ohm, r_bottom_ohm, lo),
                v_out(r_top_ohm, r_bottom_ohm, typ),
                v_out(r_top_ohm, r_bottom_ohm, hi))
    tol = U3.params["r_divider_tolerance"].value
    return (v_out(r_top_ohm * (1 - tol), r_bottom_ohm * (1 + tol), lo),
            v_out(r_top_ohm, r_bottom_ohm, typ),
            v_out(r_top_ohm * (1 + tol), r_bottom_ohm * (1 - tol), hi))
