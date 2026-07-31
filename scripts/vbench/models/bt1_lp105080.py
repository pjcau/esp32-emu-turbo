"""BT1 — the 105080 LiPo cell, modelled from a FAMILY datasheet.

Cites `hardware/datasheets/BAT_105080-5000mAh_DNK-LP105080-family.pdf`,
DNK Power's one-page specification for their LP105080 5000 mAh cell.

The distinction this module must not blur: **DNK is a manufacturer of
105080 cells, but not necessarily the manufacturer of the cell in this
build.** The fitted cell is bought by dimensions (10 x 50 x 80 mm) from an
unnamed vendor. So this document pins the *family* — geometry, nominal
voltage, charge limit, the ballpark of internal impedance — and nothing
here may be read as a measurement of the fitted part. That is why
`sources.py` keeps `calibrated = False` even though the battery now has a
citable Model: the flag tracks the FITTED cell, and only prototype
measurements (plan T5.4) change it.

What the citation buys anyway: the bench's 0.08 ohm internal-resistance
guess becomes a cited "< 60 mOhm" family bound, the 2.5 V discharge
cut-off and 4.2 V charge limit stop being folklore, and the C-rates give
the current limits a page.
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "BAT_105080-5000mAh_DNK-LP105080-family.pdf"
REV = "DNK105080 spec sheet, 2023 (single page)"

# The one-page spec's dimension drawing shows the two wire terminals.
PINS = (
    Pin("+", "POSITIVE", "power_out", "p.1 fig 1"),
    Pin("-", "NEGATIVE", "gnd", "p.1 fig 1"),
)

BT1 = Model(
    ref="BT1",
    part="LP105080",
    mpn="105080",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="family datasheet — DNK's LP105080, same geometry and "
             "capacity class as the fitted cell, NOT the fitted cell's "
             "own document"),
    pins=PINS,
    params={
        # p.1, the specification table.
        "v_nominal": Param(3.7, "V", locator="p.1 table 1"),
        "capacity": Param(5.0, "Ah", locator="p.1 table 1"),
        # "Internal Impedance < 60 mOhm" — a family upper bound.
        "r_internal_max": Param(0.060, "ohm", locator="p.1 table 1"),
        "v_charge_max": Param(4.2, "V", locator="p.1 table 1"),
        "v_discharge_cutoff": Param(2.5, "V", locator="p.1 table 1"),
        # C-rates: recommended charge/discharge 0.2C, max continuous
        # discharge 1C, pulse 3C for 10 ms.
        "i_charge_recommended": Param(1.0, "A", locator="p.1 table 1"),
        "i_discharge_max_cont": Param(5.0, "A", locator="p.1 table 1"),
        "i_discharge_pulse": Param(15.0, "A", locator="p.1 table 1"),
        "t_charge_range": Param((0.0, 25.0, 45.0), "degC",
                                locator="p.1 table 1"),
        "t_discharge_range": Param((-20.0, 25.0, 60.0), "degC",
                                   locator="p.1 table 1"),
    },
)

# The one-pager has no OCV-vs-SoC curve and no impedance-vs-SoC data, so
# the generic curve in sources.py stays generic, and stays flagged.
UNESTABLISHED = {
    "ocv_curve": "no discharge curve on the single page; sources.py keeps "
                 "its declared generic Li-polymer shape",
    "fitted_cell": "this is a family document. Nothing here is a "
                   "measurement of the cell actually fitted — plan T5.4 "
                   "replaces this with prototype measurements",
}
