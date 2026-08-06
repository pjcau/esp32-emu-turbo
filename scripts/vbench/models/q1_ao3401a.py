"""Q1/Q2 — AO3401A P-channel MOSFET: battery RPP gate and +5V load switch.

Cites `hardware/datasheets/Q1_AO3401A-SOT23_C15127.pdf`, Alpha & Omega
Semiconductor, footer "Rev 3.1: December 2023".

The AO3401A replaced the Si2301CDS (C10487) in the R32 audit round: every
amp of the battery path flows through Q1's channel, and the Si2301's cited
continuous rating — −2.3 A at 25 °C, −1.8 A at 70 °C — sat BELOW both the
derived worst-case cell current (4.348 A, see verify_power_via_ampacity's
BAT+ citation) and the realistic sustained draw at rated boost output
(~3.5 A at a nominal cell). The AO3401A is a SOT-23 drop-in with the same
gate polarity and threshold class (−0.5 V min vs the Si2301's −0.4 V, so
every SW16 OFF-state margin argument survives with slightly MORE room),
double the continuous rating, roughly half the on-resistance, and a body
diode rated −2 A instead of −1.3 A for the reverse-polarity fault path.

Two readings carried over from the Si2301 model, re-checked here:

**R_DS(on) is a function of V_GS and this board sits between characterised
points.** Page 2 gives 47/60 mΩ (typ/max) at V_GS = −4.5 V and 60/85 mΩ at
−2.5 V. Q1's gate is pulled to GND through R24, so V_GS = −V_BAT: −4.2 V
full, −3.5 V near empty. `r_ds_on()` returns the −2.5 V row for any |V_GS|
below 4.5 V rather than interpolating — the conservative row is the honest
choice when the answer feeds a voltage-drop budget.

**The thermal figure has two time bases and the smaller one is the wrong
one.** Page 1 gives R_thJA 70/90 °C/W for t ≤ 10 s and 100/125 °C/W steady
state (note D). A handheld running an emulator is steady state, so 125 max
is the number that applies; `theta_ja_10s` is kept separately so nobody
reaches for the small one by accident. Note A: both assume 1 in² FR-4 with
2 oz copper — this board gives the part less, so real θ_JA is higher.
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "Q1_AO3401A-SOT23_C15127.pdf"
REV = "Rev 3.1: December 2023"

# Page 1, SOT-23 top view: 1 = G, 2 = S, 3 = D (same pinout as the
# Si2301CDS it replaced — no footprint or routing change).
# On this board Q1.1 = RPP_GATE, Q1.3 = BAT_IN (DRAIN, cell side),
# Q1.2 = BAT+ (SOURCE, IP5306 side). Conduction in discharge is therefore
# drain to source — the body diode's own direction — and that is the point
# rather than an accident: it is the only wiring in which a reversed cell
# reverse-biases that diode (see the body-diode params below). The board
# shipped source-on-cell through v4.5.0, which behaves identically under
# correct polarity and differently only under the fault (R31-HIGH-1).
#
# power_in/power_out follow the discharge direction, which is what
# conflicts.py's _feeds_from_another_rail reads: Q1 has a power_in pin on
# BAT_IN, so its BAT+ pin is a pass element's output and not a second
# driver fighting the cell.
PINS = (
    Pin("1", "G", "in", "p.1 figure 1"),
    Pin("3", "D", "power_in", "p.1 figure 1"),
    Pin("2", "S", "power_out", "p.1 figure 1"),
)

Q1 = Model(
    ref="Q1",
    part="AO3401A",
    mpn="C15127",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="30 V P-Channel MOSFET, trench technology, 'suitable for use "
             "as a load switch or other general applications' (page 1)"),
    pins=PINS,
    params={
        # ── Static, page 2 "Electrical Characteristics" (table 1) ───────
        "v_ds_breakdown": Param(-30.0, "V", locator="p.2 table 1"),
        # Page 2 gives min −0.5 / typ −0.9 / max −1.3. The max magnitude is
        # the one an ON claim is judged against — it is the drive below
        # which the channel is not guaranteed on.
        "v_gs_threshold": Param(-1.3, "V", locator="p.2 table 1"),
        # The other end of that pair. An OFF claim is judged against the
        # MINIMUM threshold magnitude: below it the part is specified not
        # to conduct, so it is the pessimistic bound an off-state has to
        # clear. (Used by vbench T2.3, which reads Q2's gate to decide
        # whether the switch is off.) −0.5 V vs the Si2301's −0.4 V: every
        # recorded OFF margin gains 0.1 V by the swap.
        "v_gs_th_min": Param(-0.5, "V", locator="p.2 table 1"),
        # The drive the R_ds(on) row below is measured at.
        "v_gs_rds_on": Param(-4.5, "V", locator="p.2 table 1"),
        "r_ds_on_at_4v5": Param((0.0, 0.047, 0.060), "ohm",
                                locator="p.2 table 1"),
        "r_ds_on_at_2v5": Param((0.0, 0.060, 0.085), "ohm",
                                locator="p.2 table 1"),
        "i_dss_leakage": Param(1e-6, "A", locator="p.2 table 1"),
        "g_fs": Param(17.0, "S", locator="p.2 table 1"),

        # ── Body diode, page 2 ──────────────────────────────────────────
        # Matters for the reverse-polarity claim: with the cell reversed the
        # channel is off and this diode is what has to block. It can only
        # block if the cell is on the DRAIN — a P-channel body diode
        # conducts D->S, so cell-on-source (the pre-R31-HIGH-1 wiring) sent
        # the fault current straight through it. −2 A continuous vs the
        # Si2301's −1.3 A.
        "v_body_diode": Param((0.0, -0.7, -1.0), "V",
                              locator="p.2 table 1"),
        "i_body_diode_max": Param(-2.0, "A", locator="p.2 table 1"),

        # ── Absolute maxima, page 1 table 1 ─────────────────────────────
        "v_gs_abs_max": Param(12.0, "V", locator="p.1 table 1"),
        "i_d_max_ta25": Param(-4.0, "A", locator="p.1 table 1"),
        "i_d_max_ta70": Param(-3.2, "A", locator="p.1 table 1"),
        "p_d_max_ta25": Param(1.4, "W", locator="p.1 table 1"),
        "p_d_max_ta70": Param(0.9, "W", locator="p.1 table 1"),
        "t_junction_max": Param(150.0, "degC", locator="p.1 table 1"),

        # ── Thermal, page 1 "Thermal Characteristics" (table 2) ─────────
        # See the module docstring: 70/90 is the t <= 10 s figure, 100/125
        # is steady state, and steady state is what a handheld is.
        "theta_ja_10s": Param((0.0, 70.0, 90.0), "degC/W",
                              locator="p.1 table 2"),
        "theta_ja_steady_state": Param(125.0, "degC/W",
                                       locator="p.1 table 2"),
        "theta_jl": Param((0.0, 63.0, 80.0), "degC/W",
                          locator="p.1 table 2"),

        # ── Derived ─────────────────────────────────────────────────────
        # The measurement condition behind those numbers, note A: "mounted
        # on 1in² FR-4 board with 2oz Copper". This board gives Q1 less
        # copper than a square inch of 2 oz, so the real figure is worse
        # than 125.
        "copper_caveat": Param(
            "1 inch square FR-4, 2 oz copper", "1",
            derived_from=("theta_ja_steady_state",),
            formula="note A, page 1: the thermal figures assume a 1\" x 1\" "
                    "2 oz FR-4 board; Q1 on this layout has less copper, so "
                    "the true theta_JA is above 125 degC/W and the bench's "
                    "junction temperature is optimistic"),
    },
)


def r_ds_on(v_gs, worst_case=True):
    """On-resistance at a gate drive, in ohm. v_gs is negative for a PMOS.

    Returns the -2.5 V row for any |v_gs| < 4.5, deliberately, rather than
    interpolating between two table rows — see the module docstring.
    """
    if v_gs > 0:
        raise ValueError(
            f"V_GS = {v_gs} V is positive; a P-channel device is turned on "
            f"by a negative gate-source voltage")
    if abs(v_gs) < abs(Q1.params["v_gs_threshold"].value):
        raise ValueError(
            f"V_GS = {v_gs} V does not exceed the threshold "
            f"{Q1.params['v_gs_threshold'].value} V (max): the channel is "
            f"not guaranteed to be on at all, so no on-resistance applies")
    row = "r_ds_on_at_4v5" if abs(v_gs) >= 4.5 else "r_ds_on_at_2v5"
    _, typ, mx = Q1.params[row].value
    return mx if worst_case else typ


def drop(i_amps, v_gs, worst_case=True):
    """Voltage lost across the protection FET at a load current."""
    return abs(i_amps) * r_ds_on(v_gs, worst_case)
