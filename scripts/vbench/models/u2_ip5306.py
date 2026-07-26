"""U2 — IP5306, the charger + 5 V boost that feeds everything else.

Cites `hardware/datasheets/U2_IP5306_C181692.pdf`, whose footer reads
"V1.10 ... Copyright 2016, Injoinic Corp."

Deliberately incomplete, and it says so. The pages read for this model are
2 (pin definition), 3 (the PartList table, which is where the boost current
for this specific part number lives) and 4 (absolute maximum ratings and
recommended operating conditions). Those pages establish that pin 8 is the
"DCDC 5V output pin" and that the boost is rated 2.1 A — but they do NOT
give a tolerance on VOUT. So `v_out_typ` is 5.0 V with no spread, and
rails.py reports the +5V rail's tolerance as not established rather than
inventing one. Reading the electrical-characteristics table is the first
thing the next pass on this model should do.

The temptation here is to write (4.9, 5.0, 5.1) because that is what a 5 V
boost usually does. That is exactly the move this bench exists to prevent:
"usually" is not a citation, and the SY8089 downstream has a hard 5.5 V
input limit that a guessed spread would silently clear.
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "U2_IP5306_C181692.pdf"
REV = "V1.10"

# Page 2, "Pin Definition" table, next to figure 2.
PINS = (
    Pin("1", "VIN", "power_in", "p.2 table 1"),
    Pin("2", "LED1", "out", "p.2 table 1"),
    Pin("3", "LED2", "out", "p.2 table 1"),
    Pin("4", "LED3", "out", "p.2 table 1"),
    Pin("5", "KEY", "in", "p.2 table 1"),
    Pin("6", "BAT", "analog_in", "p.2 table 1"),
    Pin("7", "SW", "out", "p.2 table 1"),
    Pin("8", "VOUT", "power_out", "p.2 table 1"),
    Pin("EP", "PowerPAD", "gnd", "p.2 table 1"),
)

U2 = Model(
    ref="U2",
    part="IP5306",
    mpn="C181692",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="pin 8 = 'DCDC 5V output pin'; boost rating from the PartList "
             "table on page 3, which is per part number"),
    pins=PINS,
    params={
        # Page 2, pin 8: "DCDC 5V output pin". A nominal, not a spread —
        # see the module docstring.
        "v_out_typ": Param(5.0, "V", locator="p.2 table 1"),

        # Page 3, "The PartList of PowerBank SoC" — the IP5306 row. This
        # table is why the page matters: the boost and charger currents
        # differ across the family and only this row is ours.
        "i_boost_max": Param(2.1, "A", locator="p.3 table 1"),
        "i_charge_max": Param(2.4, "A", locator="p.3 table 1"),
        "led_count": Param(4, "1", locator="p.3 table 1"),

        # Page 4, recommended operating conditions. NOTE: this is the
        # charger INPUT voltage (VIN, pin 1), not VOUT. Kept named so it
        # cannot be mistaken for the output.
        "v_in_range": Param((4.75, 5.0, 5.5), "V", locator="p.4 table 2"),
        "i_load_range": Param((0.0, 2.1, 2.6), "A", locator="p.4 table 2"),
        "t_ambient_range": Param((0.0, 25.0, 70.0), "degC",
                                 locator="p.4 table 2"),

        # Page 4, absolute maximum ratings.
        "v_in_abs_max": Param(5.5, "V", locator="p.4 table 1"),
        "theta_ja": Param(40.0, "degC/W", locator="p.4 table 1"),
        "t_junction_max": Param(150.0, "degC", locator="p.4 table 1"),
        "esd_hbm": Param(4000.0, "V", locator="p.4 table 1"),
    },
)

# What this model cannot yet answer, listed so Phase 1.4/1.5 cannot quietly
# proceed as if it could. rails.py and the thermal pass read this.
UNESTABLISHED = {
    "v_out_tolerance": "VOUT spread is not on pages 2-4; read the "
                       "electrical-characteristics table before any check "
                       "that depends on the +5V rail's worst case",
    "boost_efficiency": "no efficiency curve on the pages read; the "
                        "battery-side current for a given +5V load cannot "
                        "be derived yet",
    "v_bat_thresholds": "charge termination and low-battery cut-off are "
                        "not on the pages read",
}
