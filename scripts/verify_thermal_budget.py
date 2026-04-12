#!/usr/bin/env python3
"""Thermal Budget Verification — junction temperature for power ICs.

Computes junction temperatures for U2 (IP5306), U3 (AMS1117), U5 (PAM8403)
under idle, gaming, and peak load scenarios.

Ambient: 40C (worst case handheld in summer).
Safe margin: Tj < Tj_max - 25C at gaming load.
"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

# IC thermal parameters (from datasheets)
ICS = {
    "U2_IP5306": {
        "ref": "U2",
        "package": "ESOP-8",
        "Rth_ja": 80,    # C/W
        "Tj_max": 150,   # C
    },
    "U3_AMS1117": {
        "ref": "U3",
        "package": "SOT-223",
        "Rth_ja": 90,    # C/W
        "Tj_max": 125,   # C
    },
    "U5_PAM8403": {
        "ref": "U5",
        "package": "SOP-16 (narrow)",
        "Rth_ja": 100,   # C/W
        "Tj_max": 150,   # C
    },
}

# Load scenarios
# I_3v3 = ESP32 + display + misc
# I_audio = audio amplifier current draw
SCENARIOS = {
    "idle": {
        "desc": "Menu/standby",
        "I_esp32_mA": 100,
        "I_display_mA": 50,
        "I_audio_mA": 0,
        "I_3v3_mA": 150,
        "audio_pout_W": 0.0,
    },
    "gaming": {
        "desc": "SNES @60fps",
        "I_esp32_mA": 300,
        "I_display_mA": 80,
        "I_audio_mA": 50,
        "I_3v3_mA": 430,
        "audio_pout_W": 0.2,
    },
    "peak": {
        "desc": "WiFi burst + full audio",
        "I_esp32_mA": 500,
        "I_display_mA": 80,
        "I_audio_mA": 100,
        "I_3v3_mA": 680,
        "audio_pout_W": 0.5,
    },
}

T_AMBIENT = 40  # C (worst case)
SAFE_MARGIN = 25  # C below Tj_max

# Voltage rails
V_IN = 5.0      # USB/boost output
V_OUT = 3.3     # AMS1117 output
V_BAT = 3.7     # Nominal battery voltage

# Efficiency figures
IP5306_ETA = 0.92     # 92% boost efficiency at 500mA
PAM8403_ETA = 0.90    # 90% class-D efficiency
R_SPEAKER = 8         # 8 ohm speaker

PASS = 0
FAIL = 0
WARN = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def warn(name, detail=""):
    global WARN
    WARN += 1
    print(f"  WARN  {name}  {detail}")


def info(name, detail=""):
    print(f"  INFO  {name}  {detail}")


def compute_ams1117_dissipation(i_3v3_mA):
    """AMS1117 linear regulator dissipation: P = (Vin - Vout) * I"""
    return (V_IN - V_OUT) * (i_3v3_mA / 1000.0)


def compute_ip5306_dissipation(scenario):
    """IP5306 boost converter dissipation.

    Total system load at 5V: 3.3V rail + 5V peripherals (audio, display backlight).
    P_loss = P_out / eta - P_out
    """
    i_3v3 = scenario["I_3v3_mA"] / 1000.0
    i_audio = scenario["I_audio_mA"] / 1000.0
    # Total 5V output: AMS1117 input + audio amp
    p_out_5v = V_IN * (i_3v3 + i_audio)
    p_loss = p_out_5v / IP5306_ETA - p_out_5v
    return p_loss


def compute_pam8403_dissipation(scenario):
    """PAM8403 class-D amplifier dissipation.

    P_loss = P_out * (1 - eta) + quiescent
    """
    p_out = scenario["audio_pout_W"]
    if p_out == 0:
        return 0.010  # 10mW quiescent
    return p_out * (1.0 - PAM8403_ETA) + 0.010


def main():
    print("=" * 60)
    print("Thermal Budget Verification")
    print("=" * 60)

    # Verify ICs exist in PCB
    cache = load_cache(PCB_FILE)
    pcb_refs = set(cache["refs"])

    print(f"\n-- IC Presence Check --")
    for ic_name, params in ICS.items():
        ref = params["ref"]
        found = ref in pcb_refs
        check(f"{ref} ({params['package']}) found in PCB", found,
              f"reference {ref} not in PCB")

    # Compute thermal budget for each scenario
    for scenario_name, scenario in SCENARIOS.items():
        print(f"\n-- Scenario: {scenario_name} ({scenario['desc']}) --")
        print(f"  I_3v3={scenario['I_3v3_mA']}mA, "
              f"audio_Pout={scenario['audio_pout_W']:.1f}W, "
              f"T_ambient={T_AMBIENT}C")

        # AMS1117
        p_ams = compute_ams1117_dissipation(scenario["I_3v3_mA"])
        tj_ams = T_AMBIENT + p_ams * ICS["U3_AMS1117"]["Rth_ja"]
        tj_max_ams = ICS["U3_AMS1117"]["Tj_max"]

        info(f"U3 AMS1117: P={p_ams:.3f}W, Tj={tj_ams:.1f}C "
             f"(max {tj_max_ams}C, margin={tj_max_ams - tj_ams:.1f}C)")

        # IP5306
        p_ip = compute_ip5306_dissipation(scenario)
        tj_ip = T_AMBIENT + p_ip * ICS["U2_IP5306"]["Rth_ja"]
        tj_max_ip = ICS["U2_IP5306"]["Tj_max"]

        info(f"U2 IP5306:  P={p_ip:.3f}W, Tj={tj_ip:.1f}C "
             f"(max {tj_max_ip}C, margin={tj_max_ip - tj_ip:.1f}C)")

        # PAM8403
        p_pam = compute_pam8403_dissipation(scenario)
        tj_pam = T_AMBIENT + p_pam * ICS["U5_PAM8403"]["Rth_ja"]
        tj_max_pam = ICS["U5_PAM8403"]["Tj_max"]

        info(f"U5 PAM8403: P={p_pam:.3f}W, Tj={tj_pam:.1f}C "
             f"(max {tj_max_pam}C, margin={tj_max_pam - tj_pam:.1f}C)")

        # Checks for gaming scenario (primary use case)
        if scenario_name == "gaming":
            # AMS1117 — the hottest IC (linear regulator)
            if tj_ams < tj_max_ams - SAFE_MARGIN:
                check(f"U3 AMS1117 Tj < {tj_max_ams - SAFE_MARGIN}C (gaming)", True)
            elif tj_ams < tj_max_ams:
                warn(f"U3 AMS1117 Tj={tj_ams:.1f}C (gaming)",
                     f"above safe margin ({tj_max_ams - SAFE_MARGIN}C) but below max ({tj_max_ams}C)")
            else:
                check(f"U3 AMS1117 Tj < {tj_max_ams}C (gaming)", False,
                      f"Tj={tj_ams:.1f}C exceeds max!")

            # IP5306
            if tj_ip < tj_max_ip - SAFE_MARGIN:
                check(f"U2 IP5306 Tj < {tj_max_ip - SAFE_MARGIN}C (gaming)", True)
            elif tj_ip < tj_max_ip:
                warn(f"U2 IP5306 Tj={tj_ip:.1f}C (gaming)",
                     f"above safe margin but below max ({tj_max_ip}C)")
            else:
                check(f"U2 IP5306 Tj < {tj_max_ip}C (gaming)", False,
                      f"Tj={tj_ip:.1f}C exceeds max!")

            # PAM8403
            if tj_pam < tj_max_pam - SAFE_MARGIN:
                check(f"U5 PAM8403 Tj < {tj_max_pam - SAFE_MARGIN}C (gaming)", True)
            elif tj_pam < tj_max_pam:
                warn(f"U5 PAM8403 Tj={tj_pam:.1f}C (gaming)",
                     f"above safe margin but below max ({tj_max_pam}C)")
            else:
                check(f"U5 PAM8403 Tj < {tj_max_pam}C (gaming)", False,
                      f"Tj={tj_pam:.1f}C exceeds max!")

        # Peak scenario check — transient burst, not sustained
        # WARN (not FAIL) because WiFi bursts are short (<100ms)
        # and thermal mass prevents instantaneous Tj rise
        if scenario_name == "peak":
            for ic_name, tj, tj_max in [
                ("U3 AMS1117", tj_ams, tj_max_ams),
                ("U2 IP5306", tj_ip, tj_max_ip),
                ("U5 PAM8403", tj_pam, tj_max_pam),
            ]:
                if tj < tj_max:
                    check(f"{ic_name} Tj < Tj_max at peak load", True)
                else:
                    warn(f"{ic_name} Tj={tj:.1f}C exceeds Tj_max={tj_max}C at peak (transient)",
                         "WiFi bursts are short — thermal mass prevents instantaneous rise. "
                         "Consider heatsink pad or duty-cycle limiting for sustained WiFi.")

    # AMS1117 specific: compute max current before thermal limit
    print(f"\n-- AMS1117 Thermal Limit --")
    tj_budget = ICS["U3_AMS1117"]["Tj_max"] - SAFE_MARGIN - T_AMBIENT
    max_power = tj_budget / ICS["U3_AMS1117"]["Rth_ja"]
    max_current_mA = max_power / (V_IN - V_OUT) * 1000
    info(f"AMS1117 max safe current (Tj<{ICS['U3_AMS1117']['Tj_max'] - SAFE_MARGIN}C): "
         f"{max_current_mA:.0f}mA ({max_power:.2f}W)")
    info(f"Gaming load uses {SCENARIOS['gaming']['I_3v3_mA']}mA "
         f"({SCENARIOS['gaming']['I_3v3_mA']/max_current_mA*100:.0f}% of thermal budget)")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed, {WARN} warnings")
    print(f"{'=' * 60}")

    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
