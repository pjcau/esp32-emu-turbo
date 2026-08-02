"""Q1 — Si2301CDS P-channel MOSFET, the reverse-polarity gate on the battery.

Cites `hardware/datasheets/Q1_SI2301CDS-SOT23_C10487.pdf`, Vishay Siliconix
document 68741, whose footer reads "S10-2430-Rev. C, 25-Oct-10".

Two things about this part are easy to get wrong and are therefore spelled
out here.

**R_DS(on) is a function of V_GS, and this board sits between the two
characterised points.** Page 2 gives 0.090 Ω typ / 0.112 Ω max at
V_GS = -4.5 V and 0.110 Ω typ / 0.142 Ω max at V_GS = -2.5 V. On this board
the gate is pulled to GND through R24 and the source sits at the cell, so
V_GS = -V_BAT: about -4.2 V on a full cell and -3.5 V near empty. Neither
row applies exactly. `r_ds_on()` therefore returns the **-2.5 V row** for
any |V_GS| below 4.5 V rather than interpolating: interpolation between two
table rows invents a number the datasheet does not contain, and the
conservative row is the honest choice when the answer feeds a voltage-drop
budget.

**The thermal figure has three values and the smallest one is the wrong
one.** Page 1's thermal table gives R_thJA 120 typ / 145 max — but for
t <= 5 s, and note d says "Maximum under steady state conditions is
175 °C/W". A handheld running an emulator is steady state, so 175 is the
number that applies. `theta_ja_steady_state` carries it and `theta_ja_5s`
is kept separately so nobody can reach for the small one by accident.
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "Q1_SI2301CDS-SOT23_C10487.pdf"
REV = "S10-2430-Rev. C, 25-Oct-10 (document 68741)"

# Page 1, "TO-236 (SOT-23) Top View": 1 = G, 2 = S, 3 = D.
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
    part="Si2301CDS",
    mpn="C10487",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="P-Channel 20 V (D-S) MOSFET, TrenchFET, application: load "
             "switch (page 1)"),
    pins=PINS,
    params={
        # ── Static, page 2 "MOSFET Specifications" ──────────────────────
        "v_ds_breakdown": Param(-20.0, "V", locator="p.2 table 1"),
        # Page 2 gives min -0.4 V and max -1.0 V with no typical. The max
        # magnitude is the one that matters — it is the drive below which
        # the channel is not guaranteed on — so it is recorded alone rather
        # than padded into a (min, typ, max) triple with an invented middle.
        "v_gs_threshold": Param(-1.0, "V", locator="p.2 table 1"),
        "r_ds_on_at_4v5": Param((0.0, 0.090, 0.112), "ohm",
                                locator="p.2 table 1"),
        "r_ds_on_at_2v5": Param((0.0, 0.110, 0.142), "ohm",
                                locator="p.2 table 1"),
        "i_dss_leakage": Param(1e-6, "A", locator="p.2 table 1"),
        "g_fs": Param(9.5, "S", locator="p.2 table 1"),

        # ── Body diode, page 2 ──────────────────────────────────────────
        # Matters for the reverse-polarity claim: with the cell reversed the
        # channel is off and this diode is what has to block. It can only
        # block if the cell is on the DRAIN — a P-channel body diode
        # conducts D->S, so cell-on-source (the pre-R31-HIGH-1 wiring) sent
        # the fault current straight through it, and the 1.3 A rating below
        # was then the only thing between a reversed pack and U2.
        "v_body_diode": Param((0.0, -0.8, -1.2), "V", locator="p.2 table 1"),
        "i_body_diode_max": Param(-1.3, "A", locator="p.2 table 1"),

        # ── Absolute maxima, page 1 ─────────────────────────────────────
        "v_gs_abs_max": Param(8.0, "V", locator="p.1 table 2"),
        "i_d_max_ta25": Param(-2.3, "A", locator="p.1 table 2"),
        "i_d_max_ta70": Param(-1.8, "A", locator="p.1 table 2"),
        "p_d_max_ta25": Param(0.86, "W", locator="p.1 table 2"),
        "p_d_max_ta70": Param(0.55, "W", locator="p.1 table 2"),
        "t_junction_max": Param(150.0, "degC", locator="p.1 table 2"),

        # ── Thermal, page 1 "Thermal Resistance Ratings" ────────────────
        # See the module docstring: 120/145 are the <=5 s figures, note d
        # gives 175 for steady state, and steady state is what a handheld is.
        "theta_ja_5s": Param((0.0, 120.0, 145.0), "degC/W",
                             locator="p.1 table 3"),
        "theta_ja_steady_state": Param(175.0, "degC/W", locator="p.1 table 3"),
        "theta_jf": Param((0.0, 62.0, 78.0), "degC/W", locator="p.1 table 3"),

        # ── Derived ─────────────────────────────────────────────────────
        # The measurement condition behind those numbers, note b: "Surface
        # mounted on 1" x 1" FR4 board". This board gives Q1 far less copper
        # than a square inch, so the real figure is worse than 175.
        "copper_caveat": Param(
            "1 inch square FR4", "1", derived_from=("theta_ja_steady_state",),
            formula="note b, page 1: the thermal figures assume a 1\" x 1\" "
                    "FR4 board; Q1 on this layout has less copper, so the "
                    "true theta_JA is above 175 degC/W and the bench's "
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
