#!/usr/bin/env python3
"""Electrical verification and simulation for ESP32 Emu Turbo.

Performs static analysis of the circuit design:
  1. Power budget analysis (current draw, thermal, battery life)
  2. Signal timing verification (debounce, bus throughput, audio)
  3. Component value validation (resistors, caps, inductor)
  4. GPIO conflict check (pin mapping, strapping pins, reserved pins)
  5. Net connectivity analysis (power distribution, button circuits)

Usage:
    python3 scripts/simulate_circuit.py

Exit code 0 = all checks passed, 1 = errors found.
"""

import math
import os
import sys

# ── Project imports ──────────────────────────────────────────────────
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from scripts.generate_schematics.config import (   # noqa: E402
    GPIO_NETS, BUTTON_NETS, JOYSTICK_NETS,
    DISPLAY_NETS, AUDIO_NETS, SD_NETS,
)
from scripts.generate_pcb.primitives import NET_LIST, NET_ID  # noqa: E402
from scripts.generate_pcb.routing import PULL_UP_REFS, DEBOUNCE_REFS  # noqa: E402

# ── Electrical specifications (from datasheets) ─────────────────────

# Component current draw on +3V3 rail (Amps)
COMPONENTS_3V3 = {
    "ESP32-S3 (240MHz active)":     {"typ": 0.150, "max": 0.200},
    "ST7796S display (backlight)":  {"typ": 0.080, "max": 0.100},
    "SD card (SPI read)":           {"typ": 0.020, "max": 0.030},
    "Button pull-ups (14x worst)":  {"typ": 0.000, "max": 0.00462},
    "EN pull-up (R3 10k)":          {"typ": 0.00033, "max": 0.00033},
}

# Component current draw on +5V rail (Amps)
COMPONENTS_5V = {
    "PAM8403 (avg audio output)":   {"typ": 0.030, "max": 0.050},
    "LED1 red (1k limiting)":       {"typ": 0.0013, "max": 0.0013},
    "LED2 green (1k limiting)":     {"typ": 0.0011, "max": 0.0011},
}

# Regulator specs
AMS1117_MAX_CURRENT = 0.800      # A (SOT-223)
AMS1117_VIN = 5.0                # V
AMS1117_VOUT = 3.3               # V
AMS1117_DROPOUT = 1.2            # V
AMS1117_RTH_JA = 90.0            # degC/W (SOT-223 typical)
AMS1117_TJ_MAX = 125.0           # degC
AMBIENT_TEMP = 40.0              # degC (worst case inside enclosure)

IP5306_MAX_OUTPUT = 2.4          # A (5V boost output)
IP5306_BOOST_EFF = 0.90          # 90% efficiency

# Battery
BATTERY_CAPACITY_MAH = 5000
BATTERY_VOLTAGE = 3.7            # V nominal

# Passive component values
PASSIVES = {
    "R1":  {"value": 5100,   "unit": "ohm", "function": "USB-C CC1 pull-down"},
    "R2":  {"value": 5100,   "unit": "ohm", "function": "USB-C CC2 pull-down"},
    "R3":  {"value": 10000,  "unit": "ohm", "function": "ESP32 EN pull-up"},
    "R4":  {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R5":  {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R6":  {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R7":  {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R8":  {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R9":  {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R10": {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R11": {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R12": {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R13": {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R14": {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R15": {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "R16": {"value": 100000, "unit": "ohm", "function": "IP5306 KEY pull-down"},
    "R17": {"value": 1000,   "unit": "ohm", "function": "LED1 current limit"},
    "R18": {"value": 1000,   "unit": "ohm", "function": "LED2 current limit"},
    "R19": {"value": 10000,  "unit": "ohm", "function": "BTN pull-up"},
    "C1":  {"value": 10e-6,  "unit": "F",   "function": "AMS1117 input decoupling"},
    "C2":  {"value": 22e-6,  "unit": "F",   "function": "AMS1117 output bulk"},
    "C3":  {"value": 100e-9, "unit": "F",   "function": "ESP32 EN reset delay"},
    "C4":  {"value": 100e-9, "unit": "F",   "function": "ESP32 3V3 bypass"},
    "C17": {"value": 10e-6,  "unit": "F",   "function": "IP5306 input cap"},
    "C18": {"value": 10e-6,  "unit": "F",   "function": "IP5306 output cap"},
    "C19": {"value": 22e-6,  "unit": "F",   "function": "IP5306 VOUT bulk"},
    "L1":  {"value": 1e-6,   "unit": "H",   "function": "Boost inductor",
             "current_rating": 4.5},
}
# Button debounce caps C5-C16, C20
for i in range(5, 17):
    PASSIVES[f"C{i}"] = {
        "value": 100e-9, "unit": "F",
        "function": "Button debounce"
    }
PASSIVES["C20"] = {"value": 100e-9, "unit": "F", "function": "Button debounce"}

# Signal timing specs
DISPLAY_RES = (320, 480)
DISPLAY_BPP = 2                  # bytes per pixel (RGB565)
DISPLAY_FPS = 60
DISPLAY_BUS_WIDTH = 8            # 8-bit 8080 parallel
DISPLAY_BUS_FREQ_HZ = 20e6      # practical 8080 bus clock

SPI_MAX_FREQ_HZ = 40e6
SNES_MAX_ROM_BYTES = 6 * 1024 * 1024  # 6 MB (HiROM)
ROM_LOAD_ACCEPTABLE_S = 5.0     # max acceptable ROM load time

I2S_SAMPLE_RATE = 32000          # Hz (native SNES)
I2S_BIT_DEPTH = 16
I2S_CHANNELS = 2                 # stereo
I2S_MAX_BCLK_HZ = 8e6           # ESP32 I2S max

DEBOUNCE_MIN_MS = 1.0
DEBOUNCE_MAX_MS = 10.0
DEBOUNCE_R = 10000               # ohm
DEBOUNCE_C = 100e-9              # F

EN_PULLUP_R = 10000              # ohm
EN_RESET_C = 100e-9              # F
EN_THRESHOLD_FACTOR = 0.75       # Vih = 0.75 * Vdd
VDD = 3.3                        # V

# USB-C CC resistor spec (USB Type-C R1.4 Table 4-25)
CC_R_MIN = 4700                  # ohm
CC_R_MAX = 5600                  # ohm

# LED specs
LED_VF_RED = 2.0                 # V typical forward voltage
LED_VF_GREEN = 2.2               # V
LED_MAX_CONTINUOUS_MA = 20.0
LED_MIN_VISIBLE_MA = 0.5

# ESP32-S3 GPIO constraints
PSRAM_GPIOS = list(range(26, 33))  # GPIO 26-32 reserved for Octal PSRAM
UART_TX0 = 43
UART_RX0 = 44
STRAPPING_PINS = {
    0: "Boot mode (HIGH=SPI boot, LOW=download mode)",
    3: "JTAG signal select",
    45: "VDD_SPI voltage (LOW=3.3V, HIGH=1.8V)",
    46: "Boot mode / ROM log (LOW=normal boot)",
}
# ESP32-S3 ADC2 channel mapping (GPIO -> ADC2 channel)
ADC2_CHANNELS = {
    11: 0, 12: 1, 13: 2, 14: 3, 15: 4,
    16: 5, 17: 6, 18: 7, 19: 8, 20: 9,
}
ADC1_CHANNELS = {
    1: 0, 2: 1, 3: 2, 4: 3, 5: 4,
    6: 5, 7: 6, 8: 7, 9: 8, 10: 9,
}


# ── Output helpers ───────────────────────────────────────────────────

def _header(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _check(name, errors, warnings=None):
    """Print check result, return (errors, warnings)."""
    warnings = warnings or []
    if errors:
        status = f"FAIL ({len(errors)} errors)"
    elif warnings:
        status = f"WARN ({len(warnings)} warnings)"
    else:
        status = "PASS"
    print(f"  [{status}] {name}")
    for e in errors[:5]:
        print(f"    ERROR: {e}")
    if len(errors) > 5:
        print(f"    ... and {len(errors) - 5} more errors")
    for w in warnings[:5]:
        print(f"    WARN:  {w}")
    if len(warnings) > 5:
        print(f"    ... and {len(warnings) - 5} more warnings")
    return errors, warnings


# ── Check 1: Power Budget Analysis ──────────────────────────────────

def check_power_budget():
    errors = []
    warnings = []

    # +3V3 rail
    typ_3v3 = sum(c["typ"] for c in COMPONENTS_3V3.values())
    max_3v3 = sum(c["max"] for c in COMPONENTS_3V3.values())

    print(f"\n  +3V3 Rail:")
    for name, draw in COMPONENTS_3V3.items():
        print(f"    {name:40s}  typ {draw['typ']*1000:6.1f} mA"
              f"  max {draw['max']*1000:6.1f} mA")
    print(f"    {'TOTAL':40s}  typ {typ_3v3*1000:6.1f} mA"
          f"  max {max_3v3*1000:6.1f} mA")

    e, w = _check(
        f"AMS1117 capacity: {max_3v3*1000:.0f}mA / "
        f"{AMS1117_MAX_CURRENT*1000:.0f}mA "
        f"({max_3v3/AMS1117_MAX_CURRENT*100:.0f}%)",
        ["3V3 demand exceeds AMS1117 800mA max"] if max_3v3 > AMS1117_MAX_CURRENT else [],
    )
    errors.extend(e)

    # AMS1117 thermal
    p_dissipation = (AMS1117_VIN - AMS1117_VOUT) * max_3v3
    tj = AMBIENT_TEMP + p_dissipation * AMS1117_RTH_JA
    thermal_errs = []
    thermal_warns = []
    if p_dissipation > 1.5:
        thermal_errs.append(
            f"Dissipation {p_dissipation:.2f}W exceeds 1.5W absolute max")
    elif tj > 100:
        thermal_warns.append(
            f"Junction temp {tj:.1f}C is high (Tj_max={AMS1117_TJ_MAX}C)")

    print(f"\n  AMS1117 thermal:")
    print(f"    P = (Vin - Vout) x I = ({AMS1117_VIN} - {AMS1117_VOUT})"
          f" x {max_3v3*1000:.0f}mA = {p_dissipation:.3f} W")
    print(f"    Tj = {AMBIENT_TEMP}C + {p_dissipation:.3f}W x "
          f"{AMS1117_RTH_JA} C/W = {tj:.1f}C")

    e, w = _check(
        f"AMS1117 thermal: {p_dissipation:.3f}W, Tj={tj:.1f}C",
        thermal_errs, thermal_warns,
    )
    errors.extend(e)
    warnings.extend(w)

    # +5V rail (includes AMS1117 pass-through)
    typ_5v_direct = sum(c["typ"] for c in COMPONENTS_5V.values())
    max_5v_direct = sum(c["max"] for c in COMPONENTS_5V.values())
    typ_5v_total = typ_5v_direct + typ_3v3  # AMS1117 input = 3V3 output
    max_5v_total = max_5v_direct + max_3v3

    print(f"\n  +5V Rail:")
    for name, draw in COMPONENTS_5V.items():
        print(f"    {name:40s}  typ {draw['typ']*1000:6.1f} mA"
              f"  max {draw['max']*1000:6.1f} mA")
    print(f"    {'AMS1117 (3V3 pass-through)':40s}  typ {typ_3v3*1000:6.1f} mA"
          f"  max {max_3v3*1000:6.1f} mA")
    print(f"    {'TOTAL':40s}  typ {typ_5v_total*1000:6.1f} mA"
          f"  max {max_5v_total*1000:6.1f} mA")

    e, w = _check(
        f"IP5306 capacity: {max_5v_total:.2f}A / "
        f"{IP5306_MAX_OUTPUT}A ({max_5v_total/IP5306_MAX_OUTPUT*100:.0f}%)",
        ["5V demand exceeds IP5306 2.4A max"]
        if max_5v_total > IP5306_MAX_OUTPUT else [],
    )
    errors.extend(e)

    # Battery life
    p_total_typ = typ_5v_total * 5.0  # Watts at 5V
    p_total_max = max_5v_total * 5.0
    i_bat_typ = (p_total_typ / IP5306_BOOST_EFF) / BATTERY_VOLTAGE
    i_bat_max = (p_total_max / IP5306_BOOST_EFF) / BATTERY_VOLTAGE
    hours_typ = BATTERY_CAPACITY_MAH / (i_bat_typ * 1000)
    hours_max = BATTERY_CAPACITY_MAH / (i_bat_max * 1000)

    print(f"\n  Battery life:")
    print(f"    System power: typ {p_total_typ:.2f}W, max {p_total_max:.2f}W")
    print(f"    Battery draw (90% eff): typ {i_bat_typ*1000:.0f}mA,"
          f" max {i_bat_max*1000:.0f}mA")
    print(f"    Estimated: typ {hours_typ:.1f}h, heavy use {hours_max:.1f}h")

    bat_warns = []
    if hours_max < 4:
        bat_warns.append(f"Battery life {hours_max:.1f}h < 4h at max draw")
    e, w = _check(
        f"Battery life: {hours_typ:.1f}h typical, {hours_max:.1f}h heavy",
        [], bat_warns,
    )
    warnings.extend(w)

    # Power tree
    print(f"\n  Power Distribution Tree:")
    print(f"    LiPo 3.7V 5000mAh")
    print(f"      |")
    print(f"      +--[IP5306 boost]--> +5V ({max_5v_total*1000:.0f}mA max)")
    print(f"      |    |")
    print(f"      |    +--[AMS1117 LDO]--> +3V3 ({max_3v3*1000:.0f}mA max)")
    print(f"      |    |    |-- ESP32-S3 ({COMPONENTS_3V3['ESP32-S3 (240MHz active)']['max']*1000:.0f}mA)")
    print(f"      |    |    |-- Display ({COMPONENTS_3V3['ST7796S display (backlight)']['max']*1000:.0f}mA)")
    print(f"      |    |    +-- SD card ({COMPONENTS_3V3['SD card (SPI read)']['max']*1000:.0f}mA)")
    print(f"      |    |")
    print(f"      |    +-- PAM8403 ({COMPONENTS_5V['PAM8403 (avg audio output)']['max']*1000:.0f}mA)")
    print(f"      |    +-- LEDs ({(COMPONENTS_5V['LED1 red (1k limiting)']['max']+COMPONENTS_5V['LED2 green (1k limiting)']['max'])*1000:.1f}mA)")
    print(f"      |")
    print(f"      +--[USB-C VBUS]--> charge input (1A max)")

    return errors, warnings


# ── Check 2: Signal Timing Verification ─────────────────────────────

def check_signal_timing():
    errors = []
    warnings = []

    # Button debounce RC
    tau_ms = (DEBOUNCE_R * DEBOUNCE_C) * 1000
    settle_ms = tau_ms * 5  # 99.3% settling
    debounce_errs = []
    if tau_ms < DEBOUNCE_MIN_MS:
        debounce_errs.append(f"RC time constant {tau_ms:.2f}ms < {DEBOUNCE_MIN_MS}ms")
    if tau_ms > DEBOUNCE_MAX_MS:
        debounce_errs.append(f"RC time constant {tau_ms:.2f}ms > {DEBOUNCE_MAX_MS}ms")

    print(f"\n  Button debounce:")
    print(f"    R = {DEBOUNCE_R/1000:.0f}k, C = {DEBOUNCE_C*1e9:.0f}nF")
    print(f"    tau = R x C = {tau_ms:.2f} ms")
    print(f"    Settling (5*tau) = {settle_ms:.1f} ms")
    e, w = _check(f"Debounce RC: {tau_ms:.1f}ms", debounce_errs)
    errors.extend(e)

    # Display 8080 bus throughput
    pixels = DISPLAY_RES[0] * DISPLAY_RES[1]
    bytes_per_frame = pixels * DISPLAY_BPP
    required_bps = bytes_per_frame * DISPLAY_FPS
    available_bps = DISPLAY_BUS_FREQ_HZ  # 1 byte per clock cycle
    margin_pct = (available_bps - required_bps) / available_bps * 100

    print(f"\n  Display 8080 bus:")
    print(f"    {DISPLAY_RES[0]}x{DISPLAY_RES[1]} x {DISPLAY_BPP}B x "
          f"{DISPLAY_FPS}fps = {required_bps/1e6:.1f} MB/s required")
    print(f"    8-bit parallel @ {DISPLAY_BUS_FREQ_HZ/1e6:.0f}MHz = "
          f"{available_bps/1e6:.1f} MB/s available")
    print(f"    Margin: {margin_pct:.1f}%")

    disp_errs = []
    disp_warns = []
    if required_bps > available_bps:
        disp_errs.append("Display throughput insufficient for 60fps!")
    elif margin_pct < 10:
        disp_warns.append(f"Display margin only {margin_pct:.1f}%")
    e, w = _check(f"Display throughput: {margin_pct:.1f}% margin", disp_errs, disp_warns)
    errors.extend(e)
    warnings.extend(w)

    # SPI SD card read speed
    spi_bytes_per_sec = SPI_MAX_FREQ_HZ / 8
    load_time = SNES_MAX_ROM_BYTES / spi_bytes_per_sec

    print(f"\n  SPI SD card:")
    print(f"    SPI @ {SPI_MAX_FREQ_HZ/1e6:.0f}MHz = "
          f"{spi_bytes_per_sec/1e6:.1f} MB/s")
    print(f"    Largest SNES ROM: {SNES_MAX_ROM_BYTES/1e6:.1f} MB")
    print(f"    Load time: {load_time:.2f}s")
    e, w = _check(
        f"SD card load: {load_time:.1f}s",
        [f"ROM load time {load_time:.1f}s > {ROM_LOAD_ACCEPTABLE_S}s"]
        if load_time > ROM_LOAD_ACCEPTABLE_S else [],
    )
    errors.extend(e)

    # I2S audio
    i2s_data_rate = I2S_SAMPLE_RATE * I2S_BIT_DEPTH * I2S_CHANNELS
    i2s_bclk = I2S_SAMPLE_RATE * I2S_BIT_DEPTH * 2  # BCLK per sample

    print(f"\n  I2S audio:")
    print(f"    {I2S_SAMPLE_RATE/1000:.0f}kHz x {I2S_BIT_DEPTH}bit x "
          f"{I2S_CHANNELS}ch = {i2s_data_rate/1e6:.3f} Mbps")
    print(f"    BCLK = {i2s_bclk/1e6:.3f} MHz "
          f"(ESP32 max: {I2S_MAX_BCLK_HZ/1e6:.0f} MHz)")
    e, w = _check(
        f"I2S audio: BCLK {i2s_bclk/1e6:.3f}MHz / {I2S_MAX_BCLK_HZ/1e6:.0f}MHz",
        ["I2S BCLK exceeds ESP32 maximum"]
        if i2s_bclk > I2S_MAX_BCLK_HZ else [],
    )
    errors.extend(e)

    # EN reset delay
    en_tau = EN_PULLUP_R * EN_RESET_C
    v_threshold = EN_THRESHOLD_FACTOR * VDD
    # Time to reach threshold: V(t) = Vcc * (1 - e^(-t/tau))
    # t = -tau * ln(1 - Vth/Vcc)
    t_en = -en_tau * math.log(1 - v_threshold / VDD)

    print(f"\n  ESP32 EN reset delay:")
    print(f"    R3 = {EN_PULLUP_R/1000:.0f}k, C3 = {EN_RESET_C*1e9:.0f}nF")
    print(f"    tau = {en_tau*1000:.2f} ms")
    print(f"    Time to reach {v_threshold:.3f}V (Vih): {t_en*1000:.3f} ms")
    e, w = _check(
        f"EN delay: {t_en*1000:.2f}ms (min 0.05ms)",
        ["EN delay too short for stable boot"]
        if t_en < 50e-6 else [],
    )
    errors.extend(e)

    return errors, warnings


# ── Check 3: Component Value Validation ─────────────────────────────

def check_component_values():
    errors = []
    warnings = []

    # USB-C CC resistors
    r1 = PASSIVES["R1"]["value"]
    r2 = PASSIVES["R2"]["value"]

    print(f"\n  USB-C CC pull-down resistors:")
    print(f"    R1 = {r1} ohm, R2 = {r2} ohm")
    print(f"    USB-C spec (UFP): {CC_R_MIN}-{CC_R_MAX} ohm")
    cc_errs = []
    for name, val in [("R1", r1), ("R2", r2)]:
        if val < CC_R_MIN or val > CC_R_MAX:
            cc_errs.append(f"{name} = {val} ohm outside USB-C range "
                          f"{CC_R_MIN}-{CC_R_MAX}")
    e, w = _check("USB-C CC resistors", cc_errs)
    errors.extend(e)

    # LED current limiting
    i_led1 = (VDD - LED_VF_RED) / PASSIVES["R17"]["value"] * 1000
    i_led2 = (VDD - LED_VF_GREEN) / PASSIVES["R18"]["value"] * 1000

    print(f"\n  LED current limiting:")
    print(f"    LED1 (red):  I = (3.3 - {LED_VF_RED}) / "
          f"{PASSIVES['R17']['value']} = {i_led1:.1f} mA")
    print(f"    LED2 (green): I = (3.3 - {LED_VF_GREEN}) / "
          f"{PASSIVES['R18']['value']} = {i_led2:.1f} mA")
    led_errs = []
    led_warns = []
    for name, i_ma in [("LED1", i_led1), ("LED2", i_led2)]:
        if i_ma > LED_MAX_CONTINUOUS_MA:
            led_errs.append(f"{name} current {i_ma:.1f}mA > {LED_MAX_CONTINUOUS_MA}mA max")
        if i_ma < LED_MIN_VISIBLE_MA:
            led_warns.append(f"{name} current {i_ma:.1f}mA may be too dim")
    e, w = _check("LED current", led_errs, led_warns)
    errors.extend(e)
    warnings.extend(w)

    # Pull-up logic levels
    vih = EN_THRESHOLD_FACTOR * VDD

    print(f"\n  Pull-up logic levels:")
    print(f"    Vdd = {VDD}V")
    print(f"    Vih (ESP32) = 0.75 x {VDD} = {vih:.3f}V")
    print(f"    Vil (ESP32) = 0.25 x {VDD} = {VDD*0.25:.3f}V")
    print(f"    Pull-up to 3.3V (button open):  {VDD}V > Vih ({vih:.3f}V) -> HIGH")
    print(f"    Button pressed (to GND):         0V < Vil ({VDD*0.25:.3f}V) -> LOW")
    e, w = _check(
        "Pull-up logic levels",
        ["Pull-up voltage below Vih threshold"] if VDD < vih else [],
    )
    errors.extend(e)

    # Decoupling capacitor presence
    ic_caps = {
        "ESP32 (U1)":     ["C3", "C4"],
        "AMS1117 (U3)":   ["C1", "C2"],
        "IP5306 (U2)":    ["C17", "C18", "C19"],
    }
    print(f"\n  Decoupling capacitors:")
    cap_warns = []
    for ic, caps in ic_caps.items():
        cap_vals = [f"{c}={PASSIVES[c]['value']*1e6:.0f}uF"
                    if PASSIVES[c]["value"] >= 1e-6
                    else f"{c}={PASSIVES[c]['value']*1e9:.0f}nF"
                    for c in caps]
        print(f"    {ic:20s}: {', '.join(cap_vals)}")
    print(f"    {'PAM8403 (U5)':20s}: uses +5V rail bulk caps (C18, C19)")
    e, w = _check("Decoupling capacitors", [], cap_warns)
    warnings.extend(w)

    # Inductor current rating
    l1 = PASSIVES["L1"]
    l1_rating = l1["current_rating"]
    # At max 5V load, worst case inductor current
    max_5v_load = sum(c["max"] for c in COMPONENTS_5V.values())
    max_5v_load += sum(c["max"] for c in COMPONENTS_3V3.values())

    print(f"\n  Inductor L1:")
    print(f"    Value: {l1['value']*1e6:.0f} uH, rated: {l1_rating} A")
    print(f"    Max system load: {max_5v_load*1000:.0f} mA")
    e, w = _check(
        f"Inductor rating: {l1_rating}A > {max_5v_load:.2f}A load",
        [f"Inductor rated {l1_rating}A < system draw {max_5v_load:.2f}A"]
        if max_5v_load > l1_rating else [],
    )
    errors.extend(e)

    # AMS1117 output cap requirement
    c2_val = PASSIVES["C2"]["value"]
    print(f"\n  AMS1117 output cap:")
    print(f"    C2 = {c2_val*1e6:.0f} uF (datasheet requires >= 22 uF)")
    e, w = _check(
        "AMS1117 output cap",
        [f"C2 = {c2_val*1e6:.0f}uF < 22uF required"]
        if c2_val < 22e-6 else [],
    )
    errors.extend(e)

    return errors, warnings


# ── Check 4: GPIO Conflict Check ────────────────────────────────────

def check_gpio_conflicts():
    errors = []
    warnings = []

    used_gpios = GPIO_NETS  # dict: gpio_num -> net_name
    print(f"\n  GPIO assignments: {len(used_gpios)} / 45 GPIOs used")

    # Duplicate check (invert mapping)
    net_to_gpios = {}
    for gpio, net in used_gpios.items():
        net_to_gpios.setdefault(net, []).append(gpio)
    dup_errs = []
    for net, gpios in net_to_gpios.items():
        if len(gpios) > 1:
            dup_errs.append(f"Net '{net}' assigned to multiple GPIOs: {gpios}")
    e, w = _check("No duplicate GPIO assignments", dup_errs)
    errors.extend(e)

    # PSRAM reserved GPIOs
    psram_conflicts = [g for g in used_gpios if g in PSRAM_GPIOS]
    print(f"\n  PSRAM reserved GPIOs (26-32):")
    if psram_conflicts:
        print(f"    CONFLICT: {psram_conflicts}")
    else:
        print(f"    No conflicts")
    e, w = _check(
        "PSRAM GPIO reservation",
        [f"GPIO {g} ({used_gpios[g]}) conflicts with PSRAM"
         for g in psram_conflicts],
    )
    errors.extend(e)

    # UART TX0
    print(f"\n  UART TX0 (GPIO{UART_TX0}):")
    if UART_TX0 in used_gpios:
        print(f"    CONFLICT: assigned to {used_gpios[UART_TX0]}")
        errors.append(f"GPIO{UART_TX0} (UART TX) used for {used_gpios[UART_TX0]}")
    else:
        print(f"    Not used (available for debug)")
    e, w = _check(
        "UART TX0 reserved",
        [f"GPIO{UART_TX0} used for {used_gpios[UART_TX0]}"]
        if UART_TX0 in used_gpios else [],
    )
    errors.extend(e)

    # UART RX0
    rx0_warns = []
    if UART_RX0 in used_gpios:
        rx0_warns.append(
            f"GPIO{UART_RX0} ({used_gpios[UART_RX0]}) shares with "
            f"UART RX0 -- debug input unavailable")
    e, w = _check("UART RX0", [], rx0_warns)
    warnings.extend(w)

    # Strapping pins
    print(f"\n  Strapping pins:")
    strap_warns = []
    for gpio, desc in STRAPPING_PINS.items():
        assigned = used_gpios.get(gpio)
        status = f"-> {assigned}" if assigned else "not used"
        print(f"    GPIO{gpio:2d}: {desc}")
        print(f"            {status}")
        if assigned:
            if gpio == 0:
                strap_warns.append(
                    f"GPIO0 ({assigned}): pressing during reset enters "
                    f"download mode")
            elif gpio == 45:
                strap_warns.append(
                    f"GPIO45 ({assigned}): must be LOW at boot for 3.3V "
                    f"operation (backlight off = safe)")
            elif gpio == 46:
                strap_warns.append(
                    f"GPIO46 ({assigned}): must be LOW at boot for "
                    f"normal operation")
    e, w = _check("Strapping pins", [], strap_warns)
    warnings.extend(w)

    # ADC pins for joystick
    print(f"\n  Joystick ADC pins:")
    adc_warns = []
    for net_name in JOYSTICK_NETS:
        gpio = None
        for g, n in used_gpios.items():
            if n == net_name:
                gpio = g
                break
        if gpio is None:
            continue
        adc_ch = ADC2_CHANNELS.get(gpio) or ADC1_CHANNELS.get(gpio)
        adc_unit = "ADC2" if gpio in ADC2_CHANNELS else (
            "ADC1" if gpio in ADC1_CHANNELS else "NONE")
        print(f"    {net_name}: GPIO{gpio} -> {adc_unit}"
              f"{f' CH{adc_ch}' if adc_ch is not None else ''}")
        if adc_ch is None and gpio not in ADC1_CHANNELS and gpio not in ADC2_CHANNELS:
            adc_warns.append(
                f"GPIO{gpio} ({net_name}) has no ADC — joystick is "
                f"optional, reassign to ADC-capable GPIO if needed")
    e, w = _check("Joystick ADC pins", [], adc_warns)
    errors.extend(e)

    return errors, warnings


# ── Check 5: Net Connectivity Analysis ──────────────────────────────

def check_net_connectivity():
    errors = []
    warnings = []

    # Verify all expected nets are declared
    expected_power_nets = ["GND", "VBUS", "+5V", "+3V3", "BAT+"]
    print(f"\n  Power nets declared:")
    net_names = {name for _, name in NET_LIST if name}
    for pn in expected_power_nets:
        present = pn in net_names
        print(f"    {pn:10s}: {'OK' if present else 'MISSING'}")
        if not present:
            errors.append(f"Power net '{pn}' not declared")
    e, w = _check("Power net declarations", errors)

    # Verify all signal nets declared
    all_signal_nets = DISPLAY_NETS + AUDIO_NETS + SD_NETS + BUTTON_NETS + ["BTN_MENU"]
    all_signal_nets += JOYSTICK_NETS + ["USB_D+", "USB_D-", "SPK+", "SPK-"]
    missing_nets = [n for n in all_signal_nets if n not in net_names]
    print(f"\n  Signal nets: {len(all_signal_nets)} expected, "
          f"{len(all_signal_nets) - len(missing_nets)} declared")
    e, w = _check(
        "Signal net declarations",
        [f"Missing net: {n}" for n in missing_nets],
    )
    errors.extend(e)

    # Button circuit completeness
    print(f"\n  Button circuits:")
    print(f"    Pull-up resistors: {len(PULL_UP_REFS)} "
          f"({', '.join(PULL_UP_REFS[:3])}...{PULL_UP_REFS[-1]})")
    print(f"    Debounce caps:     {len(DEBOUNCE_REFS)} "
          f"({', '.join(DEBOUNCE_REFS[:3])}...{DEBOUNCE_REFS[-1]})")
    print(f"    Button nets:       {len(BUTTON_NETS) + 1} "
          f"(12 directional + BTN_MENU)")

    btn_count = len(BUTTON_NETS) + 1  # +1 for BTN_MENU
    btn_errs = []
    if len(PULL_UP_REFS) < btn_count:
        btn_errs.append(
            f"Only {len(PULL_UP_REFS)} pull-ups for {btn_count} buttons")
    if len(DEBOUNCE_REFS) < btn_count:
        btn_errs.append(
            f"Only {len(DEBOUNCE_REFS)} debounce caps for {btn_count} buttons")
    e, w = _check("Button circuit completeness", btn_errs)
    errors.extend(e)

    # USB differential pair
    print(f"\n  USB differential pair:")
    usb_dp = "USB_D+" in net_names
    usb_dm = "USB_D-" in net_names
    print(f"    USB_D+: {'declared' if usb_dp else 'MISSING'}")
    print(f"    USB_D-: {'declared' if usb_dm else 'MISSING'}")
    usb_errs = []
    if not usb_dp:
        usb_errs.append("USB_D+ net not declared")
    if not usb_dm:
        usb_errs.append("USB_D- net not declared")
    e, w = _check("USB differential pair", usb_errs)
    errors.extend(e)

    # Net count summary
    print(f"\n  Net summary:")
    print(f"    Total declared: {len(NET_LIST)} nets "
          f"({len(net_names)} named)")
    print(f"    Power: {len(expected_power_nets)}")
    print(f"    Display: {len(DISPLAY_NETS)}")
    print(f"    SPI: {len(SD_NETS)}")
    print(f"    I2S: {len(AUDIO_NETS)}")
    print(f"    Buttons: {len(BUTTON_NETS) + 1}")
    print(f"    USB: 2")
    print(f"    Audio: 2")
    print(f"    Joystick: {len(JOYSTICK_NETS)}")

    return errors, warnings


# ── Main ─────────────────────────────────────────────────────────────

def main():
    print("ESP32 Emu Turbo — Electrical Verification")
    print("Static circuit analysis (pre-production check)")
    print("=" * 60)

    all_errors = []
    all_warnings = []

    checks = [
        ("POWER BUDGET ANALYSIS", check_power_budget),
        ("SIGNAL TIMING VERIFICATION", check_signal_timing),
        ("COMPONENT VALUE VALIDATION", check_component_values),
        ("GPIO CONFLICT CHECK", check_gpio_conflicts),
        ("NET CONNECTIVITY ANALYSIS", check_net_connectivity),
    ]

    for title, check_fn in checks:
        _header(title)
        errs, warns = check_fn()
        all_errors.extend(errs)
        all_warnings.extend(warns)

    print()
    print("=" * 60)
    if all_errors:
        print(f"RESULT: FAIL — {len(all_errors)} errors, "
              f"{len(all_warnings)} warnings")
        sys.exit(1)
    else:
        print(f"RESULT: PASS — 0 errors, {len(all_warnings)} warnings")
        sys.exit(0)


if __name__ == "__main__":
    main()
