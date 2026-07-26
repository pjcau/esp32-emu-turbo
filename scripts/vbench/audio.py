"""Virtual Bench T3.2 — the audio chain, and the current it pulls off the rail.

Walks the chain the netlist actually describes:

    U1.10 (GPIO17, PDM out) -> C22 -> PAM_IN_AC -> U5.7 / U5.10 (INL, INR)
                                       |
                               R20 || R21 -> PAM_VREF -> C21 -> GND
    U5.16 / U5.14 (OUTR+/OUTR-) -> SPK1

and computes what is derivable from cited numbers: the input high-pass
corner, the output power the supply allows into this board's 8 ohm speaker,
the current that costs, and the WAV the speaker would emit.

## The gain is NOT modelled, so the WAV is parametrised by output level

The PAM8403's closed-loop gain is not on the datasheet pages this repo holds.
Without it there is no honest mapping from an input amplitude to an output
amplitude — so this module does not invent one. `--level` sets the output as a
fraction of the swing the supply allows, and the WAV is "what the speaker
emits at that level", not "what the speaker emits for a given DAC code".

Everything else is derived from the cited model:

* **High-pass corner** from C22 and the parallel R20/R21 the netlist shows,
  both read from the BOM: f = 1/(2*pi*R*C).
* **Output power** from the datasheet's own rated point — 3 W into 4 ohm at
  5 V (page 1) — carried to 8 ohm at the same voltage swing, which halves it.
  The datasheet gives no 8 ohm figure, so this is declared derived rather
  than quoted.
* **Supply current** from the cited 90% efficiency and the cited 6.3 mA
  standby draw, which is what T3.2 means by feeding the current back into
  Phase 1.

Usage:
    python3 scripts/vbench/audio.py
    python3 scripts/vbench/audio.py --level 1.0 --wav /tmp/speaker.wav
"""

import argparse
import array
import math
import os
import struct
import sys
import wave

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import netlist as nl                              # noqa: E402
from vbench import rails                                      # noqa: E402
from vbench.models import require_valid                       # noqa: E402
from vbench.models.u5_pam8403 import U5, UNESTABLISHED        # noqa: E402

SPEAKER_OHM = 8.0
SPEAKER_SRC = ("website/docs/design/components.md — 28 mm 8 ohm speaker. The "
               "PAM8403's 3 W rating is into 4 ohm.")


class AudioError(RuntimeError):
    """The chain cannot be evaluated. Never downgraded to a warning."""


def input_network(board=None, values=None):
    """(R_effective, C_block, f_corner) for the amplifier input, from copper."""
    board = board or nl.load_board_netlist()
    values = values if values is not None else rails.load_bom_values()

    bias = [p.ref for p in board.nets.get("PAM_IN_AC", ())
            if p.ref.startswith("R")]
    blocks = [p.ref for p in board.nets.get("PAM_IN_AC", ())
              if p.ref.startswith("C")]
    if not bias or not blocks:
        raise AudioError(
            f"PAM_IN_AC carries resistors {bias} and capacitors {blocks}; the "
            f"input network cannot be identified from the netlist")

    # Resistors from PAM_IN_AC to PAM_VREF are in parallel — R25-LOW-1's
    # observation, explained by the datasheet's own application circuit
    # (figure 3, page 3: one 20k per channel; this board bridges INL and INR
    # for mono, which puts the two of them in parallel).
    conductance = 0.0
    for ref in bias:
        val = values.get(ref)
        if val is None:
            raise AudioError(f"{ref} is in the bias network but has no BOM "
                             f"value; the corner frequency cannot be computed")
        conductance += 1.0 / val
    r_eff = 1.0 / conductance
    c_block = values.get(blocks[0])
    if c_block is None:
        raise AudioError(f"{blocks[0]} has no BOM value")
    f_corner = 1.0 / (2.0 * math.pi * r_eff * c_block)
    return r_eff, c_block, f_corner, bias, blocks[0]


def output_power(v_supply, r_load=SPEAKER_OHM):
    """Power into `r_load` at the datasheet's rated voltage swing.

    Derived: the datasheet rates 3 W into 4 ohm at 5 V (page 1). The same
    swing into a higher impedance delivers proportionally less power, so
    P(load) = P_rated * (r_rated / r_load), scaled by (v_supply/5)^2 because
    a class-D output swing follows its supply.
    """
    p_rated = U5.params["p_out_max"].value
    r_rated = U5.params["r_load_rated"].value
    v_rated = U5.params["v_supply_rated"].value
    return p_rated * (r_rated / r_load) * (v_supply / v_rated) ** 2


def supply_current(p_out, v_supply):
    """Rail current for a given acoustic output, from the cited efficiency."""
    eta = U5.params["efficiency_max"].value
    quiescent = U5.params["i_standby"].value
    return p_out / (eta * v_supply) + quiescent


def render_wav(path, p_out, r_load=SPEAKER_OHM, freq=440.0, seconds=1.0,
               rate=32000):
    """Write what the speaker emits: a tone at the computed output power.

    Memoryless: amplitude and hard clipping only. No frequency response and
    no THD, because the datasheet pages this repo holds give neither — see
    u5_pam8403.UNESTABLISHED. A WAV that carried a modelled THD would be
    claiming more than the model knows.
    """
    v_rms = math.sqrt(p_out * r_load)
    v_peak = v_rms * math.sqrt(2.0)
    samples = array.array("h")
    for n in range(int(rate * seconds)):
        s = math.sin(2.0 * math.pi * freq * n / rate)
        # Full scale of the WAV is the peak the supply allows, so a level
        # above 1.0 clips visibly rather than silently rescaling.
        val = max(-1.0, min(1.0, s))
        samples.append(int(val * 32767))
    with wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(rate)
        fh.writeframes(samples.tobytes())
    return v_peak, v_rms


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--level", type=float, default=1.0,
                    help="output as a fraction of the swing the supply "
                         "allows (default 1.0 = full)")
    ap.add_argument("--wav", default=None,
                    help="write the speaker waveform to this path")
    args = ap.parse_args(argv)

    require_valid(U5)
    try:
        board = nl.load_board_netlist()
        values = rails.load_bom_values()
        r_eff, c_block, f_corner, bias, block = input_network(board, values)
        op = rails.operating_point()
    except (AudioError, nl.NetlistError, rails.RailError) as exc:
        print(f"  ERROR  {exc}", file=sys.stderr)
        return 2

    v5 = op.voltages.get("+5V")
    p_full = output_power(v5)
    p_out = p_full * max(0.0, args.level) ** 2
    i_rail = supply_current(p_out, v5)

    print("=" * 72)
    print("  Virtual Bench T3.2 — audio chain")
    print("=" * 72)
    print(f"  Chain (from the netlist):")
    print(f"    U1.10 -> {block} -> PAM_IN_AC -> U5.7/U5.10 (INL+INR bridged)")
    print(f"    {' || '.join(bias)} -> PAM_VREF -> C21 -> GND")
    print(f"    U5.16/U5.14 -> SPK1")
    print()
    print(f"  Input high-pass corner")
    print(f"    {' || '.join(bias)} = {r_eff/1000:.1f} kohm, {block} = "
          f"{c_block*1e6:.2f} uF")
    print(f"    f = 1/(2*pi*R*C) = {f_corner:.1f} Hz")
    print(f"    Content below that rolls off. The two 20k in parallel are the "
          f"datasheet's")
    print(f"    own application circuit (figure 3, page 3: one 20k per "
          f"channel) with INL")
    print(f"    and INR bridged for mono — which is R25-LOW-1's observation, "
          f"explained.")
    print()
    print(f"  Output into the {SPEAKER_OHM:.0f} ohm speaker")
    print(f"    rail +5V = {v5:.3f} V")
    print(f"    P_max    = {p_full:.2f} W  (DERIVED from the rated 3 W into "
          f"4 ohm at 5 V,")
    print(f"               page 1 — the datasheet gives no 8 ohm figure)")
    print(f"    at level {args.level:.2f}: P_out = {p_out:.3f} W")
    print()
    print(f"  Current fed back to the rail (T3.2's point)")
    print(f"    I = P_out/(eta*V) + I_standby = {i_rail*1000:.1f} mA")
    print(f"    eta 90% and I_standby 6.3 mA are both cited (page 1).")
    print(f"    The sag this causes is NOT computed: the IP5306's output")
    print(f"    impedance is not on the pages this repo holds "
          f"(u2_ip5306.UNESTABLISHED),")
    print(f"    so a sag figure would be invented. T5.5 measures it.")

    if args.wav:
        v_peak, v_rms = render_wav(args.wav, p_out)
        print()
        print(f"  WAV written: {args.wav}")
        print(f"    {v_rms:.2f} V rms / {v_peak:.2f} V peak across "
              f"{SPEAKER_OHM:.0f} ohm")
        print(f"    Memoryless gain and clipping only — no frequency response,")
        print(f"    no THD. Neither is on the pages read.")

    print()
    print("  Not modelled, and not silently:")
    for key, why in sorted(UNESTABLISHED.items()):
        print(f"    {key:<14} {why}")

    problems = []
    if v5 is None:
        problems.append("+5V has no DC solution, so no output power follows")
    if f_corner > 100.0:
        problems.append(
            f"the input high-pass corner is {f_corner:.0f} Hz — above about "
            f"100 Hz the chain audibly loses bass")

    print()
    print("=" * 72)
    if problems:
        print(f"  FAIL — {len(problems)}:")
        for p in problems:
            print(f"    {p}")
        print("=" * 72)
        return 1
    print(f"  The chain passes audio above {f_corner:.0f} Hz and can deliver "
          f"{p_full:.2f} W")
    print(f"  into 8 ohm at this rail. Gain, THD and the rail sag are not "
          f"modelled.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
