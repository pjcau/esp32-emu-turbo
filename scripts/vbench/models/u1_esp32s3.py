"""U1 — ESP32-S3-WROOM-1-N16R8: the strapping pins and what they decide.

Cites `hardware/datasheets/U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf`,
"ESP32-S3-WROOM-1 & WROOM-1U 技术规格书 v1.3".

This model deliberately covers **only** the strapping and reset behaviour.
The full 41-pin table already lives in `hardware/datasheet_specs.py::U1` and
is checked by `verify_datasheet_nets`; duplicating it here would create a
second copy to drift. What is not anywhere else is the answer to "what does
this board boot into, and why" — which is decided by four pins and their
internal pull resistors.

## The four facts that matter, from §3.3 (page 13)

Table 4, "Strapping 管脚默认配置", gives the default each pin takes when
nothing external drives it:

    GPIO0   上拉 (pull-up)    -> 1
    GPIO3   浮空 (floating)   -> no default at all
    GPIO45  下拉 (pull-down)  -> 0
    GPIO46  下拉 (pull-down)  -> 0

and the surrounding paragraph says why: GPIO0, GPIO45 and GPIO46 connect to
the chip's internal weak pull-up/pull-down at reset, and "如果 strapping 管脚
没有外部连接或者连接的外部线路处于高阻抗状态，这些电阻将决定 strapping 管脚
的默认值" — if the pin has no external connection, or the external circuit is
high-impedance, those resistors decide.

**GPIO3 is the exception and it is not a small one.** §3.3.4 (page 15) says
"该管脚没有内部上下拉电阻，strapping 的值必须由不处于高阻抗状态的外部电路
控制" — GPIO3 has no internal pull of either kind, so its strapping value
*must* be driven by external circuitry that is not high-impedance. A design
that leaves GPIO3 floating has no defined JTAG source selection. On this
board GPIO3 is BTN_R, which carries an external pull-up, so it is defined —
but by the board, not by the chip.

## What the pins decide

Table 6 (page 14), 芯片启动模式控制:

    default            GPIO0=1 (pull-up), GPIO46=0 (pull-down)
    SPI Boot (默认)    GPIO0=1, GPIO46=任意值 (any)
    Joint Download     GPIO0=0, GPIO46=0

Table 7 (page 15), VDD_SPI 电压控制, with EFUSE_VDD_SPI_FORCE=0:

    GPIO45=0 -> 3.3 V (VDD3P3_RTC through R_SPI)
    GPIO45=1 -> 1.8 V (flash regulator)

This is why R14 must stay DNP: the N16R8's PSRAM runs at 3.3 V, and an
external pull-up on GPIO45 would select 1.8 V. That decision is recorded in
several places in this repo; here it finally has a page behind it.

Table 5 (page 13) gives the timing: t_SU min 0 ms (rails stable before
CHIP_PU rises) and t_H min **3 ms** (how long the strapping values stay
readable after CHIP_PU is high, before the pins become ordinary IO).
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf"
REV = "技术规格书 v1.3"

# Only the pins this model reasons about. The full table is in
# datasheet_specs.py::U1 — see the module docstring.
PINS = (
    Pin("3", "EN", "in", "p.13 section 3.3"),
    Pin("27", "GPIO0", "inout", "p.13 table 4"),
    Pin("15", "GPIO3", "inout", "p.15 section 3.3"),
    Pin("31", "GPIO45", "inout", "p.13 table 4"),
    Pin("32", "GPIO46", "inout", "p.13 table 4"),
)

U1 = Model(
    ref="U1",
    part="ESP32-S3-WROOM-1-N16R8",
    mpn="C2913202",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="strapping pins and their internal pulls: section 3.3, "
             "tables 4-7"),
    pins=PINS,
    params={
        # Table 5, page 13 — strapping timing.
        "t_setup_min": Param(0.0, "s", locator="p.13 table 5"),
        "t_hold_min": Param(3e-3, "s", locator="p.13 table 5"),
        # The EN RC the datasheet requires — see docs/virtual-bench-plan.md
        # phase -1(a). Page 28, note to figure 7 (外围设计原理图): an RC delay
        # circuit MUST be added at EN, R = 10k and C = 1uF recommended.
        "en_rc_r_recommended": Param(10e3, "ohm", locator="p.28 figure 7"),
        "en_rc_c_recommended": Param(1e-6, "F", locator="p.28 figure 7"),
        # Supply range, for rails.py's V_3V3_VALID threshold.
        "v_supply_range": Param((3.0, 3.3, 3.6), "V", locator="p.13 table 5"),
        # Chip reset release threshold — the EN pin's V_IH_nRST, as a
        # ratio of VDD ("芯片复位释放电压", min 0.75 x VDD). This is the
        # level EN must cross for the chip to leave reset, i.e. the
        # threshold dynamics.py measures the EN RC ramp against.
        "v_ih_nrst_ratio": Param(0.75, "1", locator="p.16 table 11"),
    },
)

# Table 4, page 13. `None` means the datasheet gives no default because the
# pin has no internal pull — that is GPIO3, and it is a fact, not a gap.
STRAPPING_DEFAULTS = {
    "GPIO0": {"internal": "pull-up", "default": 1,
              "locator": "p.13 table 4"},
    "GPIO3": {"internal": None, "default": None,
              "locator": "p.15 section 3.3.4"},
    "GPIO45": {"internal": "pull-down", "default": 0,
               "locator": "p.13 table 4"},
    "GPIO46": {"internal": "pull-down", "default": 0,
               "locator": "p.13 table 4"},
}

# What each strapping pin selects, and the citation for the table that says so.
STRAPPING_ROLES = {
    "GPIO0": ("chip boot mode (with GPIO46)", "p.14 table 6"),
    "GPIO3": ("JTAG signal source", "p.15 table 8"),
    "GPIO45": ("VDD_SPI voltage: 0 -> 3.3 V, 1 -> 1.8 V", "p.15 table 7"),
    "GPIO46": ("chip boot mode (with GPIO0) and ROM log printing",
               "p.14 table 6"),
}


def boot_mode(gpio0, gpio46):
    """Boot mode from table 6, page 14. Returns (mode, why).

    `gpio0` and `gpio46` are 0, 1 or None (undefined at reset).
    """
    if gpio0 is None:
        return ("UNDEFINED",
                "GPIO0 has no defined level at reset, so the boot mode is "
                "whatever the internal pull-up settles to against whatever "
                "the board does — not a design, an outcome")
    if gpio0 == 1:
        return ("SPI Boot",
                "GPIO0=1 selects SPI Boot regardless of GPIO46 "
                "(table 6: GPIO46 = 任意值 / any value)")
    if gpio46 == 0:
        return ("Joint Download Boot",
                "GPIO0=0 with GPIO46=0 is Joint Download Boot (table 6) — "
                "USB-Serial-JTAG, USB-OTG or UART download")
    return ("SPI Boot",
            "GPIO0=0 but GPIO46=1, which table 6 does not list as a download "
            "combination")


def vdd_spi_voltage(gpio45):
    """VDD_SPI from table 7, page 15, with EFUSE_VDD_SPI_FORCE = 0."""
    if gpio45 is None:
        return (None, "GPIO45 undefined at reset — VDD_SPI voltage is not "
                      "determined, and the N16R8's PSRAM needs 3.3 V")
    if gpio45 == 0:
        return (3.3, "GPIO45=0 -> 3.3 V from VDD3P3_RTC through R_SPI, which "
                     "is what the N16R8's 3.3 V PSRAM requires")
    return (1.8, "GPIO45=1 -> 1.8 V from the flash regulator, which would "
                 "starve the 3.3 V PSRAM — this is why R14 must stay DNP")
