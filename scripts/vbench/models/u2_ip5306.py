"""U2 — IP5306, the charger + 5 V boost that feeds everything else.

Cites `hardware/datasheets/U2_IP5306_C181692_official-V1.32.pdf` — the
official Injoinic datasheet, V1.32, footer "Copyright 2023, Injoinic
Corp.", fetched from injoinic.com. It supersedes the 11-page English brief
(`U2_IP5306_C181692.pdf`, V1.10) this model used to cite, and three claims
change with it:

* **theta_JA is 50 degC/W, not 40** (p.7, section 8). The brief's figure
  was optimistic; the official one governs.
* **Boost and charge maxima were swapped in this model.** The V1.32
  description (p.2) reads "同步升压系统提供最大 2.4A 输出电流" (boost:
  2.4 A max output) and "开关充电技术，提供最大 2.1A 电流" (charger:
  2.1 A max) — the previous revision of this file carried 2.1 A boost /
  2.4 A charge, read from the brief's PartList. The recommended-operating
  table (p.7, section 9: load 0-2.4 A) agrees with the correction.
* **Efficiency is "up to 92%" boost / "91%" charge** (p.2 description),
  not the 96%/97% the brief's feature list still claims. The lower, newer,
  official numbers govern; they are single "up to" points, not a curve —
  see UNESTABLISHED.

The electrical-characteristics table (p.7 section 10, continuing on p.8)
is the reason this file could finally be completed: it is the table the
brief does not contain.
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "U2_IP5306_C181692_official-V1.32.pdf"
REV = "V1.32 (2023)"

# p.6, section 7 (pin definition table), ESOP8.
PINS = (
    Pin("1", "VIN", "power_in", "p.6 sec 7"),
    Pin("2", "LED1", "out", "p.6 sec 7"),
    Pin("3", "LED2", "out", "p.6 sec 7"),
    Pin("4", "LED3", "out", "p.6 sec 7"),
    Pin("5", "KEY", "in", "p.6 sec 7"),
    Pin("6", "BAT", "analog_in", "p.6 sec 7"),
    Pin("7", "SW", "out", "p.6 sec 7"),
    Pin("8", "VOUT", "power_out", "p.6 sec 7"),
    Pin("EP", "PowerPAD", "gnd", "p.6 sec 7"),
)

U2 = Model(
    ref="U2",
    part="IP5306",
    mpn="C181692",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="official Injoinic V1.32; electrical characteristics are "
             "section 10, p.7 (charge system) and p.8 (boost system)"),
    pins=PINS,
    params={
        # ── description, p.2 ────────────────────────────────────────
        "i_boost_max": Param(2.4, "A", locator="p.2 sec 2"),
        "i_charge_max": Param(2.1, "A", locator="p.2 sec 2"),
        "eta_boost_max": Param(0.92, "1", locator="p.2 sec 2"),
        "eta_charge_max": Param(0.91, "1", locator="p.2 sec 2"),
        "led_count": Param(4, "1", locator="p.2 sec 2"),

        # ── absolute maximum ratings, p.7 section 8 ─────────────────
        "v_in_abs_max": Param(6.0, "V", locator="p.7 sec 8"),
        "t_junction_max": Param(150.0, "degC", locator="p.7 sec 8"),
        "theta_ja": Param(50.0, "degC/W", locator="p.7 sec 8"),
        "esd_hbm": Param(4000.0, "V", locator="p.7 sec 8"),

        # ── recommended operating conditions, p.7 section 9 ─────────
        "v_in_range": Param((4.65, 5.0, 5.5), "V", locator="p.7 sec 9"),
        "i_load_range": Param((0.0, 2.0, 2.4), "A", locator="p.7 sec 9"),
        "t_ambient_range": Param((0.0, 25.0, 70.0), "degC",
                                 locator="p.7 sec 9"),

        # ── electrical characteristics: charge system, p.7 sec 10 ───
        "v_charge_target": Param(4.2, "V", locator="p.7 sec 10"),
        "i_charge_typ": Param(1.8, "A", locator="p.7 sec 10"),
        "fs_charge": Param(750e3, "Hz", locator="p.7 sec 10"),
        "i_trickle": Param(100e-3, "A", locator="p.7 sec 10"),
        "v_trickle_end": Param(2.9, "V", locator="p.7 sec 10"),
        "v_recharge": Param(4.1, "V", locator="p.7 sec 10"),
        "t_charge_end": Param(24.0, "hour", locator="p.7 sec 10"),
        "v_in_uvlo": Param(4.5, "V", locator="p.7 sec 10"),

        # ── electrical characteristics: boost system, p.8 ───────────
        "v_in_uvlo_hyst": Param(0.2, "V", locator="p.8 sec 10"),
        # The boost's own battery window: below 3.0 V the converter is
        # out of its stated operating range. This is the low-battery
        # answer the brief never gave.
        "v_bat_operating_min": Param(3.0, "V", locator="p.8 sec 10"),
        "v_bat_operating_max": Param(4.4, "V", locator="p.8 sec 10"),
        "v_out_typ": Param(5.0, "V", locator="p.8 sec 10"),
        "v_out_ripple": Param(0.1, "V", locator="p.8 sec 10"),
        "fs_boost": Param(500e3, "Hz", locator="p.8 sec 10"),
        # Output undervoltage: VOUT held below 4.4 V trips the overload
        # protection. This is the +5V rail's brownout point.
        "v_out_uvp": Param(4.4, "V", locator="p.8 sec 10"),
        "i_out_short_detect": Param(4.0, "A", locator="p.8 sec 10"),
        "r_dson_nmos": Param(35e-3, "ohm", locator="p.8 sec 10"),
        "r_dson_pmos": Param(30e-3, "ohm", locator="p.8 sec 10"),
        "i_standby": Param(100e-6, "A", locator="p.8 sec 10"),
        # Light-load auto shutdown: under 45 mA for 32 s the boost turns
        # itself off. This board's ESP32 alone draws more at idle, so the
        # console never trips it — but a suspend mode would.
        "i_load_autooff": Param(45e-3, "A", locator="p.8 sec 10"),
        "t_load_autooff": Param(32.0, "s", locator="p.8 sec 10"),
        "t_otp": Param(125.0, "degC", locator="p.8 sec 10"),
        "t_otp_hyst": Param(40.0, "degC", locator="p.8 sec 10"),

        # ── derived ─────────────────────────────────────────────────
        # Small-signal output resistance of the synchronous boost from
        # its cited FET resistances. For a boost at duty D = 1 - VBAT/VOUT
        # the switch resistances reflect to the output divided by
        # (1-D)^2; the average conducting resistance is
        # D*r_nmos + (1-D)*r_pmos. This is conduction only — no inductor
        # DCR (the coil is external and its DCR belongs to the BOM part),
        # no control-loop stiffening, so it is an UPPER bound on the
        # small-signal droop the silicon itself causes and carries no
        # load-regulation authority beyond that.
        "r_out_boost": Param(
            0.089, "ohm",
            derived_from=("r_dson_nmos", "r_dson_pmos", "v_out_typ"),
            formula="(D*r_nmos + (1-D)*r_pmos) / (1-D)^2 at the operating "
                    "floor VBAT=3.0 V (worst case): D = 1 - 3.0/5.0 = 0.40, "
                    "(0.40*0.035 + 0.60*0.030) / 0.60^2 = 0.089 ohm; at "
                    "VBAT=3.7 V the same expression gives 0.057 ohm"),
    },
)

# What this model still cannot answer, so downstream passes cannot quietly
# proceed as if it could. rails.py and the thermal pass read this.
UNESTABLISHED = {
    "v_out_tolerance": "the p.8 table gives VOUT a 5.0 V typical at "
                       "VBAT=3.7 V and a 100 mV ripple, but no min/max "
                       "over load and battery voltage; the +5V rail's "
                       "worst case is bounded only by v_out_uvp below",
    "efficiency_curve": "92% is the p.2 'up to' figure, a single point; "
                        "no efficiency-vs-load curve is in the text of "
                        "the pages read, so any loss computed from it is "
                        "a LOWER bound on the real loss",
    "charge_and_play_path": "with VIN present the load is fed through the "
                            "power-path, not the boost; no efficiency or "
                            "resistance is cited for that path, so U2's "
                            "dissipation while charging remains not "
                            "computable",
}
