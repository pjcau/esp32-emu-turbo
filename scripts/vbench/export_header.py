"""Virtual Bench T4.1 — export the derived board facts as a C header.

`software/sim/vbench_board.h` is what lets the C simulator run *on the board
model* instead of on wishful constants: every number in it is computed by the
Phase 0-3 modules from the netlist, the BOM and the cited datasheets, and
each line carries its provenance. The header is DO-NOT-EDIT and deterministic
(no timestamps), so a freshness test can regenerate it and diff.

The one C-side structure worth explaining is the bus map. The i80 write path
in `vbench_hal.c` pushes every pixel byte through `VB_LCD_BUS_MAP`: entry n
answers "which LCD_D line does the panel's DBn actually receive, through pad
41-N?". On this board the answer is the identity — DB0..DB7 arrive in order —
so the picture is untouched. But the map is DERIVED from the netlist at
generation time, so the day a data line is crossed the simulator's picture
visibly scrambles, which is the whole point of running the firmware on the
model: the bug becomes a thing you can see.

Usage:
    python3 scripts/vbench/export_header.py            # write the header
    python3 scripts/vbench/export_header.py --check    # fail if stale
"""

import argparse
import io
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import audio, buttons, display, rails, sources, thermal  # noqa: E402
from vbench import netlist as nl                                      # noqa: E402
from vbench import pins as pinmod                                     # noqa: E402
from vbench.models.q1_si2301 import Q1, r_ds_on                       # noqa: E402
from vbench.models.u1_esp32s3 import (                                # noqa: E402
    U1, boot_mode, vdd_spi_voltage)
from vbench.models.u3_sy8089 import U3                                # noqa: E402
from vbench.models.u5_pam8403 import U5                               # noqa: E402

HEADER = os.path.join(BASE, "software", "sim", "vbench_board.h")

# sim_hal.h bit order for the 12 buttons — the header maps bench facts onto
# these bits, so the order is part of the contract and asserted at build.
BTN_ORDER = ("BTN_UP", "BTN_DOWN", "BTN_LEFT", "BTN_RIGHT",
             "BTN_A", "BTN_B", "BTN_X", "BTN_Y",
             "BTN_START", "BTN_SELECT", "BTN_L", "BTN_R")


def derive():
    """Run the bench and collect everything the header needs."""
    board = nl.load_board_netlist()
    op = rails.operating_point()
    lo, typ, hi = op.rail_spread["+3V3"]
    v5 = op.voltages["+5V"]

    # Bus map: for DBn (panel side), which LCD_D line feeds it.
    view, _ = display.panel_view()
    bus = {}
    for p in view:
        m = re.match(r"^DB(\d)$", p.symbol)
        if m and p.net and p.net.startswith("LCD_D"):
            bus[int(m.group(1))] = int(p.net[len("LCD_D"):])
    if sorted(bus) != list(range(8)):
        raise SystemExit(f"bus map incomplete: {bus} — the panel view no "
                         f"longer resolves DB0..DB7, refusing to emit a "
                         f"partial map")
    mode_ok, mode, _ = display.check_interface_mode(view)

    survey = buttons.survey()
    by_net = {b.net: b for b in survey}
    t_rise = max((b.t_rise_s for b in survey if b.t_rise_s), default=0.0)
    rc_mask = 0
    for bit, name in enumerate(BTN_ORDER):
        b = by_net.get(name)
        if b and b.tau_s:
            rc_mask |= 1 << bit

    fabric, _o, _v = pinmod.fabric()
    strap = pinmod.strapping_state(fabric)
    mode_now, _why = boot_mode(strap["GPIO0"][0], strap["GPIO46"][0])
    vdd_spi, _w = vdd_spi_voltage(strap["GPIO45"][0])

    duty, v_out, v_in = thermal.duty_cycle()
    from vbench.transients import r_conduction
    ok_off, off = buttons.switch_off_scenario()

    return {
        "pcb_hash": board.pcb_hash,
        "rail3v3": (lo, typ, hi),
        "rail5v": v5,
        "ocv": [(s, sources.lipo_ocv(s)) for s in
                (0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)],
        "r_int": sources.lipo(0.5).r_internal,
        "bus": [bus[n] for n in range(8)],
        "mode_8080_8bit": mode_ok,
        "t_rise_us": t_rise * 1e6,
        "rc_mask": rc_mask,
        "boot_mode": mode_now,
        "vdd_spi": vdd_spi,
        "en_floating": op.voltages.get("EN", 0) is rails.UNDEFINED,
        "duty": duty,
        "r_cond": r_conduction(),
        "u3_theta": U3.params["theta_ja"].value,
        "u3_tjmax": U3.params["t_junction_max"].value,
        "q1_theta": Q1.params["theta_ja_steady_state"].value,
        "q1_rdson": r_ds_on(-3.83, worst_case=True),
        "ambient": thermal.GOVERNING_AMBIENT,
        "audio_p_max": audio.output_power(v5),
        "audio_eta": U5.params["efficiency_max"].value,
        "audio_i_standby": U5.params["i_standby"].value,
        "speaker_ohm": audio.SPEAKER_OHM,
        "i_idle": thermal.SCENARIOS[0].i_3v3,
        "i_gaming": thermal.SCENARIOS[1].i_3v3,
        "switch_not_in_series": ok_off and not off["routed_throws"],
        "calibrated": sources.CALIBRATION,
    }


def render(d):
    out = io.StringIO()
    w = out.write
    w("/* vbench_board.h — the board, as the Virtual Bench derived it.\n")
    w(" *\n")
    w(" * GENERATED by scripts/vbench/export_header.py — DO NOT EDIT.\n")
    w(" * Regenerate: make bench-header. Every value below is computed from\n")
    w(" * the netlist, the BOM and cited datasheet parameters; the source of\n")
    w(" * each is noted inline. No timestamps: the file is deterministic so\n")
    w(" * a freshness check can diff a regeneration against it.\n")
    w(" */\n#pragma once\n\n")
    w(f"/* Fingerprint of the .kicad_pcb this was derived from. */\n")
    w(f'#define VB_PCB_HASH "{d["pcb_hash"]}"\n\n')

    lo, typ, hi = d["rail3v3"]
    w("/* Rails — rails.py: +3V3 = V_REF*(1+R25/R26) from the real divider;\n")
    w(" * spread is V_REF's own tolerance (SY8089 AN p.4). +5V is the\n")
    w(" * IP5306's nominal; its tolerance is NOT established (u2 model). */\n")
    w(f"#define VB_RAIL_3V3_MIN_MV {round(lo*1000)}\n")
    w(f"#define VB_RAIL_3V3_TYP_MV {round(typ*1000)}\n")
    w(f"#define VB_RAIL_3V3_MAX_MV {round(hi*1000)}\n")
    w(f"#define VB_RAIL_5V_MV      {round(d['rail5v']*1000)}\n\n")

    w("/* LiPo OCV vs SoC — sources.py. UNCALIBRATED: generic single-cell\n")
    w(" * shape, BT1 has no datasheet; T5.4 replaces it with measurements. */\n")
    w(f"#define VB_BAT_R_INT_MOHM {round(d['r_int']*1000)}\n")
    w("#define VB_BAT_OCV_POINTS 12\n")
    w("static const struct { float soc; float v; } VB_BAT_OCV[VB_BAT_OCV_POINTS] = {\n")
    for soc, v in d["ocv"]:
        w(f"    {{ {soc:.2f}f, {v:.3f}f }},\n")
    w("};\n\n")

    w("/* i80 bus map — display.py panel view through the 41-N reversal:\n")
    w(" * VB_LCD_BUS_MAP[n] = which LCD_D line the panel's DBn receives.\n")
    w(" * Identity on this board; a crossed data line scrambles the picture\n")
    w(" * in the simulator, which is the point. */\n")
    w("static const unsigned char VB_LCD_BUS_MAP[8] = { "
      + ", ".join(str(n) for n in d["bus"]) + " };\n")
    w(f"#define VB_LCD_MODE_8080_8BIT {1 if d['mode_8080_8bit'] else 0} "
      f"/* IM straps, derived from copper */\n\n")

    w("/* Buttons — buttons.py: release edge to 70% of rail through the\n")
    w(" * 10k x 100nF network. Bit order matches sim_hal.h SIM_BTN_*. A\n")
    w(" * clear bit in VB_BTN_RC_MASK = no external RC (BTN_L: R14 is DNP\n")
    w(" * because GPIO45 is a strapping pin). */\n")
    w(f"#define VB_BTN_T_RISE_US {round(d['t_rise_us'])}\n")
    w(f"#define VB_BTN_RC_MASK 0x{d['rc_mask']:03X}\n\n")

    w("/* Boot — pins.py, strapping tables (module datasheet v1.3 t.4/6/7).\n")
    w(" * GPIO0 rides BTN_SELECT: held at reset -> Joint Download Boot. */\n")
    w(f'#define VB_BOOT_MODE_DEFAULT "{d["boot_mode"]}"\n')
    w(f"#define VB_VDD_SPI_MV {round((d['vdd_spi'] or 0)*1000)}\n")
    w(f"#define VB_EN_FLOATING {1 if d['en_floating'] else 0} "
      f"/* R25-CRIT-1: no RC on EN, as-built */\n\n")

    w("/* Thermal — thermal.py: Tj = amb + P*thetaJA, conduction only for\n")
    w(" * U3 (LOWER BOUND). Load currents are engineering estimates. */\n")
    w(f"#define VB_AMBIENT_C {d['ambient']:.1f}f\n")
    w(f"#define VB_BUCK_DUTY {d['duty']:.4f}f\n")
    w(f"#define VB_U3_R_COND_MOHM {round(d['r_cond']*1000)}\n")
    w(f"#define VB_U3_THETA_JA {d['u3_theta']:.1f}f\n")
    w(f"#define VB_U3_TJ_MAX_C {d['u3_tjmax']:.1f}f\n")
    w(f"#define VB_Q1_THETA_JA {d['q1_theta']:.1f}f\n")
    w(f"#define VB_Q1_RDSON_MOHM {round(d['q1_rdson']*1000)}\n")
    w(f"#define VB_I_IDLE_MA {round(d['i_idle']*1000)}\n")
    w(f"#define VB_I_GAMING_MA {round(d['i_gaming']*1000)}\n\n")

    w("/* Audio — audio.py: P into 8 ohm DERIVED from the 3W/4ohm rating;\n")
    w(" * eta and standby cited (PAM8403 p.1). */\n")
    w(f"#define VB_AUDIO_P_MAX_MW {round(d['audio_p_max']*1000)}\n")
    w(f"#define VB_AUDIO_ETA {d['audio_eta']:.2f}f\n")
    w(f"#define VB_AUDIO_I_STANDBY_MA {d['audio_i_standby']*1000:.1f}f\n")
    w(f"#define VB_SPEAKER_OHM {d['speaker_ohm']:.0f}f\n\n")

    w("/* Invariants the simulator must REPRODUCE, not report:\n")
    w(" * SW16 is not in series — operating it must NOT cut power. */\n")
    w(f"#define VB_SWITCH_NOT_IN_SERIES "
      f"{1 if d['switch_not_in_series'] else 0}\n\n")
    w(f'#define VB_CALIBRATION "{d["calibrated"]}" '
      f"/* dc / dc+transient / no — T5.4 */\n")
    return out.getvalue()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the header on disk is stale")
    args = ap.parse_args(argv)
    text = render(derive())
    if args.check:
        try:
            with open(HEADER) as fh:
                on_disk = fh.read()
        except OSError:
            print(f"STALE: {HEADER} missing — run make bench-header")
            return 1
        if on_disk != text:
            print(f"STALE: {HEADER} does not match the derived board — a "
                  f"net, value or model moved. Run make bench-header.")
            return 1
        print("vbench_board.h is current")
        return 0
    with open(HEADER, "w") as fh:
        fh.write(text)
    print(f"Wrote {os.path.relpath(HEADER, BASE)} "
          f"({len(text.splitlines())} lines, all derived)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
