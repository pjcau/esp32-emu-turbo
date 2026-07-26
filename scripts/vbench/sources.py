"""Virtual PSU and virtual LiPo — what the bench connects the board to.

The PSU is honest by construction: a lab supply is a number you dial in, so
5.00 V with a programmable current limit needs no citation.

The battery is the opposite, and this module refuses to pretend otherwise.
BT1 is a generic 105080 LiPo cell with **no datasheet in
hardware/datasheets/** — it is bought by dimensions, not by part number. So
the OCV-vs-SoC curve below cannot cite a page, and under
models/_schema.py's rules it is not a Model at all: a Model would have to
carry a locator, and inventing one is precisely the failure the schema
exists to catch.

Instead the curve is declared for what it is — a generic single-cell
Li-polymer shape, stated openly, with `calibrated = False` — and every
report that consumes it must carry that flag. Plan T5.4/T5.5 is where two
measurements on prototype #1 replace it: open-circuit voltage at rest, and
the sag under a known load, which together pin both the curve and R_int.
Until then the bench is self-consistent and uncalibrated, and must say so.
"""

import collections

Source = collections.namedtuple("Source", "name v_open r_internal i_limit "
                                          "calibrated basis")

# ── Virtual PSU ─────────────────────────────────────────────────────
#
# USB-C VBUS from a bench supply. The 5.00 V and the current limit are dial
# settings, not claims about a part, so they are exact by definition. The
# 0.05 ohm is cable plus connector resistance, declared, not measured.

def psu(v=5.00, i_limit=3.0, r_cable=0.05):
    return Source("PSU", v, r_cable, i_limit, calibrated=True,
                  basis="bench supply dial setting; r_internal is declared "
                        "cable + connector resistance, not measured")


# ── Virtual LiPo ────────────────────────────────────────────────────
#
# Generic single-cell Li-polymer open-circuit voltage against state of
# charge. Monotonic, 4.20 V full to 3.00 V empty, with the long flat middle
# a Li-po actually has. NOT from a datasheet — see the module docstring.
_OCV_CURVE = (
    (1.00, 4.20), (0.90, 4.06), (0.80, 3.98), (0.70, 3.92), (0.60, 3.87),
    (0.50, 3.83), (0.40, 3.79), (0.30, 3.75), (0.20, 3.70), (0.10, 3.60),
    (0.05, 3.50), (0.00, 3.00),
)

# 5000 mAh pouch cells land in the tens of milliohms. 0.08 ohm is a
# deliberately pessimistic single number standing in for a curve that also
# varies with SoC and temperature.
_R_INTERNAL = 0.08


def lipo_ocv(soc):
    """Open-circuit voltage at a state of charge in [0, 1], interpolated."""
    if not 0.0 <= soc <= 1.0:
        raise ValueError(f"state of charge {soc} is outside [0, 1]")
    pts = sorted(_OCV_CURVE)
    for (s0, v0), (s1, v1) in zip(pts, pts[1:]):
        if s0 <= soc <= s1:
            if s1 == s0:
                return v0
            return v0 + (v1 - v0) * (soc - s0) / (s1 - s0)
    return pts[-1][1]


def lipo(soc=0.5, r_internal=_R_INTERNAL):
    return Source("LiPo 105080", lipo_ocv(soc), r_internal, i_limit=None,
                  calibrated=False,
                  basis="generic single-cell Li-polymer OCV shape; BT1 has "
                        "no datasheet in hardware/datasheets/. Replace with "
                        "prototype #1 measurements (plan T5.4).")


def terminal_voltage(source, i_load):
    """Voltage at the source's terminals under a load current."""
    return source.v_open - i_load * source.r_internal


CALIBRATION = "no"      # plan T5.5: dc / dc+transient / no
CALIBRATION_WHY = (
    "no prototype #1 measurement has been fed back yet, and the battery "
    "model cites no datasheet because the cell has none in this repo")
