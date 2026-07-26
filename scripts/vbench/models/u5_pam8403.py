"""U5 — PAM8403 filterless class-D amplifier, the speaker driver.

Cites `hardware/datasheets/U5_PAM8403_C5122557.pdf` (Slkor, Chinese-language
datasheet). The document carries no revision string of its own, so `rev`
records that fact rather than a number nobody can check.

Worth recording because it settles two open observations elsewhere in this
repo:

* **Figure 3 on page 3, the typical application, uses a 20 kohm series
  resistor and a 0.47 uF blocking capacitor on each input, and 0.1 uF on
  VREF.** That is R20/R21, C22 and C21 on this board — so the input network
  follows the datasheet's own application circuit. R25-LOW-1's observation
  that "R20 and R21 are in parallel, not a divider" is explained by it: the
  datasheet has one 20 kohm per channel, and this board bridges INL and INR
  for mono, which puts the two of them in parallel. The topology is right,
  it just carries a part more than a mono design needs.
* **Pin 5 is MUTE and pin 12 is SHDN, both active low** (page 3 pin table:
  "低电平有效"). Both are tied to +5V on this board, i.e. unmuted and not
  shut down, which is what `datasheet_specs.py::U5` already says.

Not established from the pages read: there is no thermal-resistance table on
pages 1-3. `scripts/verify_thermal_budget.py` uses 100 degC/W for this part
and cites nothing for it — see UNESTABLISHED below.
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "U5_PAM8403_C5122557.pdf"
REV = "no revision printed on the document (Slkor, www.slkormicro.com)"

# Page 3, "PAM8403 引脚描述" (pin description) table, with the I/O column.
PINS = (
    Pin("1", "OUTL+", "out", "p.3 table 1"),
    Pin("2", "PGND", "gnd", "p.3 table 1"),
    Pin("3", "OUTL-", "out", "p.3 table 1"),
    Pin("4", "PVDD", "power_in", "p.3 table 1"),
    Pin("5", "MUTE", "in", "p.3 table 1"),
    Pin("6", "VDD", "power_in", "p.3 table 1"),
    Pin("7", "INL", "analog_in", "p.3 table 1"),
    Pin("8", "VREF", "analog_out", "p.3 table 1"),
    Pin("9", "NC", "nc", "p.3 table 1"),
    Pin("10", "INR", "analog_in", "p.3 table 1"),
    Pin("11", "GND", "gnd", "p.3 table 1"),
    Pin("12", "SHDN", "in", "p.3 table 1"),
    Pin("13", "PVDD", "power_in", "p.3 table 1"),
    Pin("14", "OUTR-", "out", "p.3 table 1"),
    Pin("15", "PGND", "gnd", "p.3 table 1"),
    Pin("16", "OUTR+", "out", "p.3 table 1"),
)

U5 = Model(
    ref="U5",
    part="PAM8403",
    mpn="C5122557",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="3W filterless class-D stereo amplifier; features list on "
             "page 1, pin table on page 3"),
    pins=PINS,
    params={
        # Page 1, features list (芯片功能主要特性).
        # "在 4Ω负载和 5V 电源条件下，提供高达 3W 输出功率"
        "p_out_max": Param(3.0, "W", locator="p.1 section 1"),
        "r_load_rated": Param(4.0, "ohm", locator="p.1 section 1"),
        "v_supply_rated": Param(5.0, "V", locator="p.1 section 1"),
        # "效率高达 90%"
        "efficiency_max": Param(0.90, "1", locator="p.1 section 1"),
        # "待机电流 6.3mA" / "关断电路 16uA"
        "i_standby": Param(6.3e-3, "A", locator="p.1 section 1"),
        "i_shutdown": Param(16e-6, "A", locator="p.1 section 1"),

        # Page 2 block diagram: the input stage references VDD/2, and page 3
        # calls pin 8 "内部基准源" (internal reference). Declared derived
        # because VDD/2 is read off the block diagram, not a spec table.
        "v_ref": Param(2.5, "V", derived_from=("v_supply_rated",),
                       formula="VDD/2 per the input-stage reference marked "
                               "'VDD/2' in the page 2 block diagram; 2.5 V "
                               "at the rated 5 V supply"),

        # Page 3, figure 3 (典型应用电路图) — the application circuit this
        # board follows.
        "r_input_series_app": Param(20e3, "ohm", locator="p.3 figure 3"),
        "c_input_block_app": Param(0.47e-6, "F", locator="p.3 figure 3"),
        "c_vref_bypass_app": Param(0.1e-6, "F", locator="p.3 figure 3"),
    },
)

# The speaker on this board is 8 ohm, not the 4 ohm the 3 W figure is rated
# into, so the rated output power does not apply directly. Recorded here
# rather than silently scaled: the datasheet pages read give no 8 ohm figure.
UNESTABLISHED = {
    "theta_ja": "no thermal-resistance table on pages 1-3. "
                "verify_thermal_budget.py uses 100 degC/W for U5 and cites "
                "no source for it; that number is unverified.",
    "p_out_8ohm": "the 3 W rating is into 4 ohm at 5 V; this board drives an "
                  "8 ohm speaker, and no 8 ohm figure is on the pages read.",
    "thd_vs_power": "no THD curve on the pages read, so audio quality "
                    "cannot be predicted, only power.",
}
