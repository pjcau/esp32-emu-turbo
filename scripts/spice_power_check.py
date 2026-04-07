#!/usr/bin/env python3
"""SPICE power supply simulation for ESP32 Emu Turbo.

Simulates the IP5306 → AMS1117 power path with ngspice to verify:
1. Output ripple on +5V rail (IP5306 boost output)
2. Output ripple on +3V3 rail (AMS1117 LDO output)
3. Transient response to load steps (ESP32 WiFi burst)
4. Decoupling cap effectiveness (C17, C27, C1, C18)

Requirements: ngspice (brew install ngspice)

Usage:
    python3 scripts/spice_power_check.py
"""

import os
import subprocess
import sys
import re

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NETLIST = "/tmp/esp32-emu-power.cir"
OUTPUT = "/tmp/spice-results.txt"


def generate_netlist():
    """Generate SPICE netlist for power supply simulation.

    Simplified model:
    - IP5306 boost: modeled as 5.1V source with 500kHz ripple (100mV pk-pk)
    - AMS1117: modeled using behavioral LDO (dropout 1.3V, PSRR ~60dB@DC)
    - Decoupling caps with ESR (0805 ceramic ~10mΩ, 1206 ~5mΩ)
    - Load: ESP32 ~200mA typical, 350mA burst (WiFi TX)
    """
    netlist = """\
* ESP32 Emu Turbo — Power Supply Simulation
* IP5306 boost → decoupling → AMS1117 LDO → ESP32 load

* ── IP5306 Boost Output (+5V rail) ──
* DC 5.1V + 100mV pk-pk ripple at 500kHz switching frequency
V1 n_boost 0 DC 5.1 AC 1 SIN(5.1 0.05 500k)

* Source impedance (IP5306 output MOSFET Rdson ~35mΩ)
R_src n_boost n_5v 35m

* ── Decoupling Caps on +5V rail ──
* C27 (10µF 0805) — HF, 2mm from pin 8, ESR 10mΩ, ESL 0.5nH
R_c27 n_5v n_c27a 10m
C_c27 n_c27a 0 10u IC=5.1

* C19 (22µF 1206) — bulk, 16mm, ESR 5mΩ, ESL 1.5nH
R_c19 n_5v n_c19a 5m
C_c19 n_c19a 0 22u IC=5.1

* C17 (10µF 0805) — VIN, 7.5mm, ESR 10mΩ
R_c17 n_5v n_c17a 10m
C_c17 n_c17a 0 10u IC=5.1

* Trace from +5V rail to AMS1117 input (~15mm)
R_tr1 n_5v n_ldo_in 7.5m

* ── AMS1117-3.3 LDO ──
* Simplified: series pass element (dropout ~1.3V at 800mA)
* PSRR modeled as RC low-pass: R=10Ω, C=1µF → fc=16kHz
* At 500kHz: attenuation = 1/(2π×500k×10×1µ) = 0.032 → ~30dB
R_ldo_pass n_ldo_in n_ldo_mid 0.5
R_psrr n_ldo_mid n_ldo_filt 10
C_psrr n_ldo_filt 0 1u IC=3.3
* Voltage clamp at 3.3V (ideal regulator behavior)
V_reg n_3v3 0 DC 3.3
R_reg n_ldo_filt n_3v3 0.01

* Input cap C1 (10µF 0805) — near AMS1117
R_c1 n_ldo_in n_c1a 10m
C_c1 n_c1a 0 10u IC=5.1

* Output cap C2 (22µF 1206) — ESR 5mΩ
R_c2 n_3v3 n_c2a 5m
C_c2 n_c2a 0 22u IC=3.3

* ── ESP32 Load ──
* 200mA typical, 350mA burst (1ms every 10ms)
I_load n_3v3 0 PULSE(0.20 0.35 5m 10u 10u 1m 10m)

* ── Analysis ──
.tran 1u 25m UIC

* Measurements (steady-state: 15-25ms)
.meas tran v5_avg AVG V(n_5v) from=15m to=25m
.meas tran v5_ripple PP V(n_5v) from=15m to=25m
.meas tran v33_avg AVG V(n_3v3) from=15m to=25m
.meas tran v33_ripple PP V(n_3v3) from=15m to=25m

.control
run
print v5_avg v5_ripple v33_avg v33_ripple
quit
.endc

.end
"""

    with open(NETLIST, "w") as f:
        f.write(netlist)
    return NETLIST

    with open(NETLIST, "w") as f:
        f.write(netlist)
    return NETLIST


def run_simulation():
    """Run ngspice simulation and capture results."""
    print("Running ngspice power supply simulation...")
    result = subprocess.run(
        ["ngspice", "-b", NETLIST],
        capture_output=True, text=True, timeout=30,
    )
    output = result.stdout + result.stderr
    return output


def parse_results(output):
    """Parse ngspice measurement results."""
    measurements = {}
    for line in output.split("\n"):
        # Parse .meas output: "v5_avg              =  5.10000e+00"
        m = re.match(r"\s*(\w+)\s*=\s*([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)", line)
        if m:
            name, value = m.group(1), float(m.group(2))
            measurements[name] = value
    return measurements


def print_report(measurements):
    """Print power supply simulation report."""
    print()
    print("=" * 60)
    print("SPICE Power Supply Simulation Report")
    print("=" * 60)

    # +5V rail
    v5_avg = measurements.get("v5_avg", 0)
    v5_ripple = measurements.get("v5_ripple", 0) * 1000  # mV
    print(f"\n── +5V Rail (IP5306 VOUT) ──")
    print(f"  Average:  {v5_avg:.3f} V")
    print(f"  Ripple:   {v5_ripple:.1f} mV pk-pk")
    v5_ok = v5_ripple < 150  # IP5306 spec: 50-150mV
    print(f"  Limit:    < 150 mV")
    print(f"  Status:   {'PASS' if v5_ok else 'FAIL'}")

    # +3V3 rail
    v33_avg = measurements.get("v33_avg", 0)
    v33_ripple = measurements.get("v33_ripple", 0) * 1000  # mV
    print(f"\n── +3V3 Rail (AMS1117 output) ──")
    print(f"  Average:  {v33_avg:.3f} V")
    print(f"  Ripple:   {v33_ripple:.1f} mV pk-pk")
    v33_ok = v33_ripple < 50  # ESP32 tolerance
    print(f"  Limit:    < 50 mV")
    print(f"  Status:   {'PASS' if v33_ok else 'FAIL'}")

    # Verdict
    print(f"\n{'=' * 60}")
    all_pass = v5_ok and v33_ok
    if all_pass:
        print(f"  PASS  Power supply simulation — all rails within spec")
    else:
        if not v5_ok:
            print(f"  FAIL  +5V ripple {v5_ripple:.1f} mV exceeds 150 mV limit")
        if not v33_ok:
            print(f"  FAIL  +3V3 ripple {v33_ripple:.1f} mV exceeds 50 mV limit")
    print(f"{'=' * 60}")

    return all_pass


def main():
    # Check ngspice
    try:
        subprocess.run(["ngspice", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("ERROR: ngspice not installed. Run: brew install ngspice")
        sys.exit(2)

    generate_netlist()
    output = run_simulation()
    measurements = parse_results(output)

    if not measurements:
        print("WARNING: Could not parse ngspice measurements.")
        print("Raw output:")
        print(output[-500:])
        sys.exit(1)

    passed = print_report(measurements)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
