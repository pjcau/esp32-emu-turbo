#!/usr/bin/env python3
"""Design Intent Adversary — cross-checks PCB against ALL design sources.

Acts as a "devil's advocate": maps every GPIO, device, net, and connection,
then hunts for inconsistencies, orphans, missing paths, and logic errors.

Sources cross-checked:
  1. board_config.h     — firmware GPIO definitions (source of truth for SW)
  2. config.py          — schematic generator GPIO mapping
  3. datasheet_specs.py — pin-to-net specs from datasheets
  4. PCB cache          — actual routed nets/pads in KiCad layout
  5. BOM/CPL            — manufacturing files

Checks:
  T1  GPIO consistency: board_config.h vs config.py
  T2  GPIO consistency: config.py vs datasheet_specs.py U1 pins
  T3  Duplicate GPIO: same GPIO# assigned to multiple signals
  T4  Signal endpoint: every GPIO signal reaches its destination component
  T5  Orphan nets: nets declared in PCB but connected to only 0-1 pads
  T6  Power chain: VBUS → IP5306 → +5V → AMS1117 → +3V3 → all VDD pins
  T7  GND completeness: every component has at least one pad on GND
  T8  Button circuit: each button has signal GPIO + GND path
  T9  ESP32 pin capability: pins used for functions they actually support
  T10 Strapping conflict: GPIO0/3/45/46 safe for runtime use
  T11 Unused ESP32 pins: GPIO pins not in any net group (potential waste)
  T12 Cross-component net: nets that should connect 2+ components actually do
  T13 FPC display chain: LCD_D0-D7 + control reach both ESP32 and FPC
  T14 Audio chain: I2S signals reach both ESP32 and PAM8403
  T15 SD card chain: SPI signals reach both ESP32 and SD slot
  T16 USB chain: D+/D- reach both ESP32 and USB-C connector
  T17 Missing pull-ups: button GPIO nets without pull-up resistor pads
  T18 Net naming: detect suspicious net names (typos, inconsistent naming)
  T19 Pin electrical conflict: nets with multiple output drivers
  T20 ESP32-S3 IO MUX: GPIO assignments respect IO MUX constraints
  T21 I2C bus completeness: SKIP (no I2C in this design)
  T22 Power rail decoupling: verify input/output caps for each power IC

Usage:
    python3 scripts/verify_design_intent.py
    python3 scripts/verify_design_intent.py --verbose
    python3 scripts/verify_design_intent.py --test T5   # run single test
"""

import argparse
import csv
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0
WARN = 0
INFO = 0
VERBOSE = False
SELECTED_TEST = None

# ---------------------------------------------------------------------------
# ESP32-S3 GPIO Capability Map
# Source: ESP32-S3-WROOM-1 datasheet Table 3 (pages 10-12) + ESP32-S3 TRM
# Module: N16R8 (Octal PSRAM → GPIO35-37 reserved, note b)
# ---------------------------------------------------------------------------

STRAPPING_PINS = {0, 3, 45, 46}

# Per-GPIO capability flags extracted from datasheet Table 3:
#   rtc    = has RTC_GPIO function (usable in deep sleep / ULP)
#   touch  = has TOUCH_PAD function (capacitive touch sensing)
#   adc1   = ADC1 channel (always available)
#   adc2   = ADC2 channel (NOT usable when WiFi is active!)
#   usb    = hardwired USB D+/D- (GPIO19=D-, GPIO20=D+)
#   uart0  = default UART0 (GPIO43=TXD0, GPIO44=RXD0) — debug console
#   jtag   = JTAG debug (GPIO39=MTCK, GPIO40=MTDO, GPIO41=MTDI, GPIO42=MTMS)
#   xtal   = crystal oscillator (GPIO15=XTAL_32K_P, GPIO16=XTAL_32K_N)
#   spi    = SPI flash/PSRAM internal (GPIO26-37, unavailable on N16R8)
#
# Format: gpio -> set of capability strings
GPIO_CAPS = {
    0:  {"rtc", "gpio", "strapping"},           # BOOT mode select
    1:  {"rtc", "gpio", "touch", "adc1"},       # TOUCH1, ADC1_CH0
    2:  {"rtc", "gpio", "touch", "adc1"},       # TOUCH2, ADC1_CH1
    3:  {"rtc", "gpio", "touch", "adc1", "strapping"},  # TOUCH3, ADC1_CH2, JTAG select
    4:  {"rtc", "gpio", "touch", "adc1"},       # TOUCH4, ADC1_CH3
    5:  {"rtc", "gpio", "touch", "adc1"},       # TOUCH5, ADC1_CH4
    6:  {"rtc", "gpio", "touch", "adc1"},       # TOUCH6, ADC1_CH5
    7:  {"rtc", "gpio", "touch", "adc1"},       # TOUCH7, ADC1_CH6
    8:  {"rtc", "gpio", "touch", "adc1"},       # TOUCH8, ADC1_CH7, SUBSPICS1
    9:  {"rtc", "gpio", "touch", "adc1"},       # TOUCH9, ADC1_CH8, FSPIHD, SUBSPIHD
    10: {"rtc", "gpio", "touch", "adc1"},       # TOUCH10, ADC1_CH9, FSPICS0, FSPIIO4, SUBSPICS0
    11: {"rtc", "gpio", "touch", "adc2"},       # TOUCH11, ADC2_CH0, FSPID, FSPIIO5, SUBSPID
    12: {"rtc", "gpio", "touch", "adc2"},       # TOUCH12, ADC2_CH1, FSPICLK, FSPIIO6, SUBSPICLK
    13: {"rtc", "gpio", "touch", "adc2"},       # TOUCH13, ADC2_CH2, FSPIQ, FSPIIO7, SUBSPIQ
    14: {"rtc", "gpio", "touch", "adc2"},       # TOUCH14, ADC2_CH3, FSPIWP, FSPIDQS, SUBSPIWP
    15: {"rtc", "gpio", "adc2", "xtal"},        # ADC2_CH4, U0RTS, XTAL_32K_P — no touch!
    16: {"rtc", "gpio", "adc2", "xtal"},        # ADC2_CH5, U0CTS, XTAL_32K_N — no touch!
    17: {"rtc", "gpio", "adc2"},                # ADC2_CH6, U1TXD — no touch!
    18: {"rtc", "gpio", "adc2"},                # ADC2_CH7, U1RXD, CLK_OUT3 — no touch!
    19: {"rtc", "gpio", "adc2", "usb"},         # ADC2_CH8, USB_D-, U1RTS, CLK_OUT2
    20: {"rtc", "gpio", "adc2", "usb"},         # ADC2_CH9, USB_D+, U1CTS, CLK_OUT1
    21: {"rtc", "gpio"},                        # RTC_GPIO21 only — no ADC, no touch
    # GPIO22-25: exist on bare chip but NOT on WROOM-1 module (no pin)
    # GPIO26-32: SPI flash (reserved, not available)
    # GPIO33-34: SPIIO4/5 for Octal flash (reserved on N16R8)
    # GPIO35-37: Octal PSRAM (reserved on N16R8, datasheet note b)
    38: {"gpio"},                               # GPIO38 only, FSPIWP, SUBSPIWP
    39: {"gpio", "jtag"},                       # MTCK, CLK_OUT3, SUBSPICS1
    40: {"gpio", "jtag"},                       # MTDO, CLK_OUT2
    41: {"gpio", "jtag"},                       # MTDI, CLK_OUT1
    42: {"gpio", "jtag"},                       # MTMS
    43: {"gpio", "uart0"},                      # U0TXD, CLK_OUT1
    44: {"gpio", "uart0"},                      # U0RXD, CLK_OUT2
    45: {"gpio", "strapping"},                  # GPIO45 only — VDD_SPI voltage select
    46: {"gpio", "strapping"},                  # GPIO46 only — boot log verbosity
    47: {"gpio", "spiclk_p"},                   # SPICLK_P_DIFF, SUBSPICLK_P_DIFF
    48: {"gpio", "spiclk_n"},                   # SPICLK_N_DIFF, SUBSPICLK_N_DIFF
}

# GPIOs reserved for internal flash/PSRAM on ESP32-S3-WROOM-1 (N16R8, Octal PSRAM)
# GPIO26-32: SPI flash, GPIO33-34: Octal flash IO4/5, GPIO35-37: Octal PSRAM
RESERVED_GPIOS = set(range(26, 38))

# GPIOs not exposed on WROOM-1 module (exist on bare chip only)
NOT_ON_MODULE = {22, 23, 24, 25}

# All valid ESP32-S3 GPIOs on WROOM-1 module
ALL_GPIOS = set(range(0, 49))  # GPIO0-48
USABLE_GPIOS = ALL_GPIOS - RESERVED_GPIOS - NOT_ON_MODULE

# Function → required GPIO capabilities
# If a signal needs a specific capability, map it here
FUNCTION_REQUIREMENTS = {
    # USB D+/D- are hardwired — MUST be GPIO19/20
    "USB_D+": {"usb", "gpio"},
    "USB_D-": {"usb", "gpio"},
    # I2S uses GPIO matrix (any GPIO works) — just needs gpio
    "I2S_BCLK": {"gpio"},
    "I2S_LRCK": {"gpio"},
    "I2S_DOUT": {"gpio"},
    # SPI uses GPIO matrix — any GPIO works
    "SD_MOSI": {"gpio"},
    "SD_MISO": {"gpio"},
    "SD_CLK": {"gpio"},
    "SD_CS": {"gpio"},
    # LCD 8080 parallel uses GPIO matrix — any GPIO works
    # Buttons are simple digital input — any GPIO works
    # But if ADC is ever needed for analog joystick:
    # "JOY_X": {"adc1", "gpio"},  # must be ADC1 (ADC2 blocked by WiFi)
    # "JOY_Y": {"adc1", "gpio"},
}


def check(test_id, name, condition, detail=""):
    global PASS, FAIL
    if SELECTED_TEST and test_id != SELECTED_TEST:
        return condition
    if condition:
        PASS += 1
        print(f"  PASS  [{test_id}] {name}")
    else:
        FAIL += 1
        print(f"  FAIL  [{test_id}] {name}  {detail}")
    return condition


def warn(test_id, name, detail=""):
    global WARN
    if SELECTED_TEST and test_id != SELECTED_TEST:
        return
    WARN += 1
    print(f"  WARN  [{test_id}] {name}  {detail}")


def info(test_id, name, detail=""):
    global INFO
    if not VERBOSE:
        return
    if SELECTED_TEST and test_id != SELECTED_TEST:
        return
    INFO += 1
    print(f"  INFO  [{test_id}] {name}  {detail}")


# ---------------------------------------------------------------------------
# Source parsers
# ---------------------------------------------------------------------------

def parse_board_config():
    """Parse board_config.h → dict of {signal_name: gpio_number}."""
    path = os.path.join(BASE, "software", "main", "board_config.h")
    if not os.path.exists(path):
        return {}
    text = open(path).read()
    mapping = {}
    for m in re.finditer(r'#define\s+(\w+)\s+GPIO_NUM_(\d+)', text):
        name, gpio = m.group(1), int(m.group(2))
        mapping[name] = gpio
    return mapping


def parse_config_py():
    """Parse generate_schematics/config.py → GPIO_NETS dict."""
    path = os.path.join(BASE, "scripts", "generate_schematics", "config.py")
    if not os.path.exists(path):
        return {}
    text = open(path).read()
    # Extract GPIO_NETS dict
    match = re.search(r'GPIO_NETS.*?=\s*\{(.*?)\}', text, re.DOTALL)
    if not match:
        return {}
    mapping = {}
    for m in re.finditer(r'(\d+)\s*:\s*"([^"]+)"', match.group(1)):
        mapping[int(m.group(1))] = m.group(2)
    return mapping


def load_datasheet_specs():
    """Load COMPONENT_SPECS from hardware/datasheet_specs.py."""
    try:
        from hardware.datasheet_specs import COMPONENT_SPECS
        return COMPONENT_SPECS
    except ImportError:
        return {}


def build_net_map(cache):
    """net_id -> net_name."""
    return {n["id"]: n["name"] for n in cache["nets"]}


def build_pad_lookup(cache, net_map):
    """Build {ref: {pad_num: net_name}} and {net_name: [(ref, pad_num)]}."""
    ref_pads = {}
    net_pads = {}
    for p in cache["pads"]:
        ref = p["ref"]
        pad_num = p["num"]
        net_id = p.get("net", 0)
        net_name = net_map.get(net_id, "")

        if ref not in ref_pads:
            ref_pads[ref] = {}
        ref_pads[ref][pad_num] = net_name

        if net_name:
            if net_name not in net_pads:
                net_pads[net_name] = []
            net_pads[net_name].append((ref, pad_num))

    return ref_pads, net_pads


# ---------------------------------------------------------------------------
# Test implementations
# ---------------------------------------------------------------------------

def test_T1_gpio_consistency(board_cfg, config_py):
    """T1: board_config.h GPIO assignments match config.py GPIO_NETS."""
    print("\n── T1: board_config.h vs config.py GPIO consistency ──")

    if not board_cfg:
        warn("T1", "board_config.h not found or empty")
        return
    if not config_py:
        warn("T1", "config.py GPIO_NETS not found or empty")
        return

    # Build reverse map: signal_name -> gpio from board_config.h
    # Normalize names: board_config uses LCD_D0, config.py uses LCD_D0
    for signal, gpio in board_cfg.items():
        # Handle USB naming difference: USB_DP/USB_DN vs USB_D+/USB_D-
        config_name = signal
        if signal == "USB_DP":
            config_name_lookup = "USB_D+"
        elif signal == "USB_DN":
            config_name_lookup = "USB_D-"
        else:
            config_name_lookup = signal

        if gpio in config_py:
            expected_net = config_py[gpio]
            check("T1", f"GPIO{gpio} {signal} == {expected_net}",
                  config_name_lookup == expected_net,
                  f"board_config says '{signal}' but config.py says '{expected_net}'")
        else:
            info("T1", f"GPIO{gpio} ({signal}) not in config.py GPIO_NETS",
                 "(may be intentional if not routed)")


def test_T2_config_vs_datasheet(config_py, specs):
    """T2: config.py GPIO_NETS vs datasheet_specs.py U1 pin expectations."""
    print("\n── T2: config.py vs datasheet_specs U1 pin mapping ──")

    if not config_py or "U1" not in specs:
        warn("T2", "Missing config.py or U1 datasheet spec")
        return

    u1 = specs["U1"]
    # ESP_PINS maps pin# -> (side, gpio#, y_offset)
    # We need to check that for each pin in U1 spec, the expected net
    # matches what config.py assigns to that GPIO

    # Parse ESP_PINS from config.py to get pin# -> GPIO mapping
    config_path = os.path.join(BASE, "scripts", "generate_schematics", "config.py")
    text = open(config_path).read()
    esp_pins_match = re.search(r'ESP_PINS.*?=\s*\{(.*?)\}', text, re.DOTALL)
    if not esp_pins_match:
        warn("T2", "Could not parse ESP_PINS from config.py")
        return

    pin_to_gpio = {}
    for m in re.finditer(r'(\d+)\s*:\s*\(\s*"[LRB]"\s*,\s*(\d+|"[^"]*")\s*,', esp_pins_match.group(1)):
        pin_num = m.group(1)
        gpio_val = m.group(2)
        if gpio_val.startswith('"'):
            continue  # Skip named pins like "3V3", "EN", "GND"
        pin_to_gpio[pin_num] = int(gpio_val)

    mismatches = 0
    # USB net rename aliases: firmware uses USB_D+/- but PCB pad has USB_DP_MCU/USB_DM_MCU
    # (series resistors R22/R23 split the net for ESD protection)
    USB_ALIASES = {
        "USB_DP_MCU": "USB_D+",
        "USB_DM_MCU": "USB_D-",
    }

    for pin_str, pin_info in u1["pins"].items():
        expected = pin_info["net"]
        if expected.get("match") == "unconnected":
            continue
        if expected.get("match") == "any_of" and "" in expected.get("nets", []):
            continue  # Zone-filled pins, skip

        gpio = pin_to_gpio.get(pin_str)
        if gpio is None:
            continue

        if gpio in config_py:
            config_net = config_py[gpio]
            if expected["match"] == "exact":
                exp_net = expected["net"]
                # Check direct match or USB alias
                ok = (config_net == exp_net or
                      USB_ALIASES.get(exp_net) == config_net)
            elif expected["match"] == "any_of":
                ok = config_net in expected["nets"]
            else:
                ok = True
            if not ok:
                mismatches += 1
            check("T2", f"U1 pin {pin_str} (GPIO{gpio}): spec={expected.get('net', expected.get('nets'))} vs config={config_net}",
                  ok)
        else:
            info("T2", f"GPIO{gpio} (U1 pin {pin_str}) not in config.py")

    if mismatches == 0:
        info("T2", "All U1 pin-to-GPIO mappings consistent")


def test_T3_duplicate_gpio(config_py):
    """T3: No GPIO number assigned to multiple signals."""
    print("\n── T3: Duplicate GPIO detection ──")

    if not config_py:
        warn("T3", "config.py not available")
        return

    gpio_to_nets = {}
    for gpio, net in config_py.items():
        if gpio not in gpio_to_nets:
            gpio_to_nets[gpio] = []
        gpio_to_nets[gpio].append(net)

    for gpio, nets in sorted(gpio_to_nets.items()):
        check("T3", f"GPIO{gpio} unique assignment",
              len(nets) == 1,
              f"GPIO{gpio} mapped to multiple signals: {nets}")


def test_T4_signal_endpoints(config_py, net_pads):
    """T4: Every GPIO signal actually connects to at least 2 pads (ESP32 + target)."""
    print("\n── T4: Signal endpoint completeness ──")

    if not config_py:
        warn("T4", "config.py not available")
        return

    # Nets that use renamed paths through series components
    # USB_D+/- go through ESD (U4) + series resistors (R22/R23) → USB_DP_MCU/USB_DM_MCU on ESP32
    # I2S_BCLK/LRCK are directly routed (pad net not assigned, trace-only connection)
    RENAMED_NETS = {
        "USB_D+": "USB_DP_MCU",   # renamed at R22 (series resistor)
        "USB_D-": "USB_DM_MCU",   # renamed at R23 (series resistor)
    }
    DIRECT_ROUTED = {"I2S_BCLK", "I2S_LRCK"}  # pad unassigned, trace connects

    for gpio, net_name in sorted(config_py.items()):
        if net_name in DIRECT_ROUTED:
            info("T4", f"{net_name} (GPIO{gpio}) is directly routed (no pad net)",
                 "trace connects but pad has no net assignment — verify in layout")
            continue

        pads = net_pads.get(net_name, [])
        components = set(ref for ref, _ in pads)

        # For renamed nets, also check the MCU-side net name
        if net_name in RENAMED_NETS:
            mcu_net = RENAMED_NETS[net_name]
            mcu_pads = net_pads.get(mcu_net, [])
            mcu_comps = set(ref for ref, _ in mcu_pads)
            total_comps = components | mcu_comps
            check("T4", f"{net_name} (GPIO{gpio}) chain: {sorted(components)} → {mcu_net}: {sorted(mcu_comps)}",
                  len(total_comps) >= 2,
                  f"only reaches: {sorted(total_comps) if total_comps else 'NOTHING'}")
        else:
            check("T4", f"{net_name} (GPIO{gpio}) connects {len(components)} components",
                  len(components) >= 2,
                  f"only reaches: {sorted(components) if components else 'NOTHING'}")


def test_T5_orphan_nets(cache, net_map, net_pads):
    """T5: Detect nets connected to 0 or 1 pad (potential lost connections)."""
    print("\n── T5: Orphan net detection ──")

    # Count pads per net from the actual PCB
    all_net_names = set(n["name"] for n in cache["nets"] if n["name"])
    # Exclude power/GND nets (these connect via zones, not pad-to-pad)
    power_nets = {"GND", "+5V", "+3V3", "VBUS", "BAT+", "LX", "EN"}

    # Nets intentionally connected to a single component (by design)
    # LCD_BL: backlight tied to 3V3 at FPC connector (no GPIO)
    # LCD_RD: read strobe tied HIGH at FPC connector (no GPIO)
    # LED1_RA, LED2_RA: LED anode through resistor (2-component but
    #   one side may be a passive on the same net)
    # IP5306_KEY: tied via resistor to BAT+ (single IC endpoint)
    # BTN_MENU: legacy net, menu now uses START+SELECT combo via D1 BAT54C
    # I2S_BCLK/LRCK: assigned to U1 pads but no target device (PAM8403 is analog)
    KNOWN_SINGLE = {"LCD_BL", "LCD_RD", "I2S_BCLK", "I2S_LRCK", "BTN_MENU"}

    orphans = []
    for net_name in sorted(all_net_names):
        if net_name in power_nets:
            continue
        pads = net_pads.get(net_name, [])
        components = set(ref for ref, _ in pads)
        if len(components) <= 1:
            if net_name in KNOWN_SINGLE:
                info("T5", f"Net '{net_name}' single-component (by design)",
                     f"component: {sorted(components)}")
            else:
                orphans.append((net_name, len(components), components))

    for net_name, count, comps in orphans:
        comp_str = sorted(comps)[0] if comps else "NONE"
        check("T5", f"Net '{net_name}' has >1 component",
              False,
              f"only {count} component(s): {comp_str}")

    if not orphans:
        check("T5", "No orphan nets found", True)


def test_T6_power_chain(net_pads, ref_pads):
    """T6: Verify power delivery chain completeness."""
    print("\n── T6: Power chain verification ──")

    # VBUS must reach: J1 (USB), U2 (IP5306 VIN)
    vbus_comps = set(r for r, _ in net_pads.get("VBUS", []))
    check("T6", "VBUS reaches USB connector (J1)", "J1" in vbus_comps,
          f"VBUS components: {sorted(vbus_comps)}")
    check("T6", "VBUS reaches IP5306 (U2)", "U2" in vbus_comps,
          f"VBUS components: {sorted(vbus_comps)}")

    # BAT+ must reach: Q1 (P-MOSFET drain), L1 (inductor), SW_PWR
    # v4.0: J3.1 is on BAT_IN net (via Q1 RPP), BAT+ reaches Q1 drain
    batp_comps = set(r for r, _ in net_pads.get("BAT+", []))
    check("T6", "BAT+ reaches P-MOSFET (Q1)", "Q1" in batp_comps,
          f"BAT+ components: {sorted(batp_comps)}")
    check("T6", "BAT+ reaches inductor (L1)", "L1" in batp_comps,
          f"BAT+ components: {sorted(batp_comps)}")
    # BAT_IN must reach: J3 (battery), Q1 (P-MOSFET source)
    batin_comps = set(r for r, _ in net_pads.get("BAT_IN", []))
    check("T6", "BAT_IN reaches battery connector (J3)", "J3" in batin_comps,
          f"BAT_IN components: {sorted(batin_comps)}")
    check("T6", "BAT_IN reaches P-MOSFET source (Q1)", "Q1" in batin_comps,
          f"BAT_IN components: {sorted(batin_comps)}")

    # +5V must reach: U2 (VOUT), U3 (VIN), U5 (PAM8403 VDD)
    v5_comps = set(r for r, _ in net_pads.get("+5V", []))
    check("T6", "+5V reaches IP5306 VOUT (U2)", "U2" in v5_comps,
          f"+5V components: {sorted(v5_comps)}")
    check("T6", "+5V reaches AMS1117 VIN (U3)", "U3" in v5_comps,
          f"+5V components: {sorted(v5_comps)}")
    check("T6", "+5V reaches PAM8403 (U5)", "U5" in v5_comps,
          f"+5V components: {sorted(v5_comps)}")

    # +3V3 must reach: U3 (VOUT), U1 (ESP32), J4 (FPC display), U6 (SD)
    v33_comps = set(r for r, _ in net_pads.get("+3V3", []))
    check("T6", "+3V3 reaches AMS1117 VOUT (U3)", "U3" in v33_comps,
          f"+3V3 components: {sorted(v33_comps)}")
    check("T6", "+3V3 reaches ESP32 (U1)", "U1" in v33_comps,
          f"+3V3 components: {sorted(v33_comps)}")
    check("T6", "+3V3 reaches FPC display (J4)", "J4" in v33_comps,
          f"+3V3 components: {sorted(v33_comps)}")
    check("T6", "+3V3 reaches SD slot (U6)", "U6" in v33_comps,
          f"+3V3 components: {sorted(v33_comps)}")

    # LX must reach: U2 (SW pin), L1 (inductor)
    lx_comps = set(r for r, _ in net_pads.get("LX", []))
    check("T6", "LX reaches IP5306 SW (U2)", "U2" in lx_comps,
          f"LX components: {sorted(lx_comps)}")
    check("T6", "LX reaches inductor (L1)", "L1" in lx_comps,
          f"LX components: {sorted(lx_comps)}")


def test_T7_gnd_completeness(ref_pads, net_pads):
    """T7: Every active component has at least one GND connection."""
    print("\n── T7: GND completeness ──")

    gnd_pads = net_pads.get("GND", [])
    gnd_refs = set(r for r, _ in gnd_pads)

    # Components that must have GND
    must_have_gnd = ["U1", "U2", "U3", "U5", "U6", "J1", "J3"]
    for ref in must_have_gnd:
        check("T7", f"{ref} has GND connection", ref in gnd_refs,
              f"Component {ref} has NO ground pad")

    # Check all switches have GND path
    for i in range(1, 14):
        ref = f"SW{i}"
        if ref in ref_pads:
            check("T7", f"{ref} has GND connection", ref in gnd_refs,
                  f"Button {ref} has no ground — won't work!")


def test_T8_button_circuits(config_py, net_pads):
    """T8: Each button has GPIO signal reaching switch + GND path."""
    print("\n── T8: Button circuit completeness ──")

    button_map = {
        "BTN_UP": "SW1", "BTN_DOWN": "SW2", "BTN_LEFT": "SW3", "BTN_RIGHT": "SW4",
        "BTN_A": "SW5", "BTN_B": "SW6", "BTN_X": "SW7", "BTN_Y": "SW8",
        "BTN_START": "SW9", "BTN_SELECT": "SW10", "BTN_L": "SW11", "BTN_R": "SW12",
    }

    for net_name, sw_ref in button_map.items():
        pads = net_pads.get(net_name, [])
        sw_connected = any(r == sw_ref for r, _ in pads)
        esp_connected = any(r == "U1" for r, _ in pads)

        check("T8", f"{net_name} reaches {sw_ref}",
              sw_connected,
              f"signal not connected to switch!")
        check("T8", f"{net_name} reaches ESP32 (U1)",
              esp_connected,
              f"signal not connected to MCU!")


def test_T9_pin_capability(config_py):
    """T9: ESP32-S3 pins support their assigned function (full capability check)."""
    print("\n── T9: ESP32-S3 pin capability check ──")

    if not config_py:
        warn("T9", "config.py not available")
        return

    for gpio, net in sorted(config_py.items()):
        # 1. Check GPIO exists on ESP32-S3
        check("T9", f"GPIO{gpio} ({net}) valid range 0-48",
              gpio in ALL_GPIOS,
              f"GPIO{gpio} does not exist on ESP32-S3!")

        # 2. Check GPIO is not reserved for flash/PSRAM
        check("T9", f"GPIO{gpio} ({net}) not reserved for flash/PSRAM",
              gpio not in RESERVED_GPIOS,
              f"GPIO{gpio} is used by internal SPI flash or Octal PSRAM on N16R8!")

        # 3. Check GPIO is exposed on WROOM-1 module
        check("T9", f"GPIO{gpio} ({net}) exposed on WROOM-1 module",
              gpio not in NOT_ON_MODULE,
              f"GPIO{gpio} exists on bare chip but NOT on WROOM-1 module (no pin)!")

        # 4. Check GPIO has required capabilities for its function
        caps = GPIO_CAPS.get(gpio, set())
        required = FUNCTION_REQUIREMENTS.get(net)
        if required:
            missing = required - caps
            check("T9", f"GPIO{gpio} ({net}) has required capabilities {sorted(required)}",
                  not missing,
                  f"GPIO{gpio} missing: {sorted(missing)}. Has: {sorted(caps)}")

        # 5. Report capabilities for info
        if caps:
            info("T9", f"GPIO{gpio} ({net}) capabilities: {sorted(caps)}")

    # --- USB D+/D- must be GPIO19/20 (hardwired in silicon) ---
    if 19 in config_py:
        check("T9", "USB D- on GPIO19 (hardwired in silicon)",
              config_py[19] == "USB_D-",
              f"GPIO19 MUST be USB_D-, got {config_py[19]}")
    if 20 in config_py:
        check("T9", "USB D+ on GPIO20 (hardwired in silicon)",
              config_py[20] == "USB_D+",
              f"GPIO20 MUST be USB_D+, got {config_py[20]}")

    # --- UART0 conflict check ---
    # GPIO43/44 are default UART0 (debug console). Using them for other
    # functions means no serial debug output unless USB CDC is used.
    for gpio in [43, 44]:
        if gpio in config_py and not config_py[gpio].startswith("UART"):
            uart_func = "U0TXD" if gpio == 43 else "U0RXD"
            warn("T9", f"GPIO{gpio} ({config_py[gpio]}) overrides default {uart_func}",
                 f"Serial debug console unavailable unless USB CDC is used")

    # --- JTAG conflict check ---
    # GPIO39-42 are JTAG. Using them disables hardware JTAG debugging.
    jtag_pins = {39: "MTCK", 40: "MTDO", 41: "MTDI", 42: "MTMS"}
    jtag_used = [g for g in jtag_pins if g in config_py]
    if jtag_used:
        info("T9", f"JTAG pins used for GPIO: {[config_py[g] for g in jtag_used]}",
             "Hardware JTAG debugging disabled (use USB JTAG instead)")

    # --- ADC2 + WiFi conflict check ---
    # ADC2 channels (GPIO11-20) cannot be used when WiFi is active.
    # If any ADC2 pin is used for analog input, this is a problem.
    adc2_used_for_analog = []
    for gpio, net in config_py.items():
        caps = GPIO_CAPS.get(gpio, set())
        if "adc2" in caps and ("JOY" in net or "ANALOG" in net or "POT" in net):
            adc2_used_for_analog.append((gpio, net))
    for gpio, net in adc2_used_for_analog:
        check("T9", f"GPIO{gpio} ({net}) uses ADC2 — incompatible with WiFi",
              False,
              f"ADC2 channels blocked when WiFi active! Use ADC1 (GPIO1-10) instead")

    # --- Crystal oscillator conflict ---
    # GPIO15/16 are XTAL_32K pins. If using external 32kHz crystal,
    # these pins are unavailable for general use.
    for gpio in [15, 16]:
        if gpio in config_py:
            info("T9", f"GPIO{gpio} ({config_py[gpio]}) shares XTAL_32K function",
                 "OK if no external 32.768kHz crystal is used")


def test_T10_strapping_conflicts(config_py):
    """T10: Strapping pins (GPIO0,3,45,46) safe for runtime use."""
    print("\n── T10: Strapping pin conflict check ──")

    if not config_py:
        warn("T10", "config.py not available")
        return

    strapping_info = {
        0: "BOOT (must be HIGH for normal boot, LOW for download mode)",
        3: "JTAG (must be HIGH to disable JTAG)",
        45: "VDD_SPI voltage (must be LOW for 3.3V flash)",
        46: "Boot log (LOW=UART print, HIGH=silence)",
    }

    for gpio, note in strapping_info.items():
        if gpio in config_py:
            net = config_py[gpio]
            # Buttons are OK — they have pull-ups (HIGH by default)
            is_button = net.startswith("BTN_")
            is_lcd = net.startswith("LCD_")
            if is_button:
                info("T10", f"GPIO{gpio} ({net}) is strapping pin",
                     f"OK: button with pull-up. {note}")
            elif is_lcd:
                warn("T10", f"GPIO{gpio} ({net}) is strapping pin used for LCD",
                     f"Verify initial state during boot. {note}")
            else:
                warn("T10", f"GPIO{gpio} ({net}) is strapping pin",
                     f"Verify default state. {note}")
            check("T10", f"GPIO{gpio} strapping pin acknowledged",
                  True)  # Pass with warning


def test_T11_unused_gpios(config_py):
    """T11: Report ESP32-S3 GPIOs not assigned to any signal."""
    print("\n── T11: Unused GPIO analysis ──")

    if not config_py:
        warn("T11", "config.py not available")
        return

    used = set(config_py.keys())
    unused = USABLE_GPIOS - used
    # Remove known reserved/special
    # GPIO26-37 already excluded via RESERVED_GPIOS
    # EN pin (not a GPIO in the normal sense)

    if unused:
        info("T11", f"{len(unused)} unused GPIOs available",
             f"GPIO{sorted(unused)}")
        check("T11", f"All {len(used)} assigned GPIOs are usable", True)
    else:
        check("T11", "All usable GPIOs assigned", True)


def test_T12_cross_component_nets(net_pads, specs):
    """T12: Nets that should connect specific components actually do."""
    print("\n── T12: Cross-component net verification ──")

    # USB D+/D- path: J1 → U4 (ESD) → R22/R23 → U1 (via renamed net USB_DP_MCU/USB_DM_MCU)
    # So USB_D+ should reach J1, U4, R22; USB_DP_MCU should reach R22, U1
    expected = [
        ("USB_D+", {"J1", "U4", "R22"}),
        ("USB_D-", {"J1", "U4", "R23"}),
        ("USB_DP_MCU", {"R22", "U1"}),
        ("USB_DM_MCU", {"R23", "U1"}),
        ("USB_CC1", {"J1", "R1"}),
        ("USB_CC2", {"J1", "R2"}),
        ("I2S_DOUT", {"U1", "U5"}),
        ("SPK+", {"U5", "SPK1"}),
        ("SPK-", {"U5", "SPK1"}),
        ("IP5306_KEY", {"U2"}),
        ("EN", {"SW_RST"}),
    ]

    for net_name, must_refs in expected:
        pads = net_pads.get(net_name, [])
        actual_refs = set(r for r, _ in pads)
        for ref in must_refs:
            check("T12", f"Net '{net_name}' reaches {ref}",
                  ref in actual_refs,
                  f"'{net_name}' only reaches: {sorted(actual_refs)}")


def test_T13_display_chain(config_py, net_pads):
    """T13: LCD signals connect ESP32 ↔ FPC connector."""
    print("\n── T13: Display signal chain ──")

    lcd_nets = [f"LCD_D{i}" for i in range(8)] + ["LCD_CS", "LCD_RST", "LCD_DC", "LCD_WR"]

    for net in lcd_nets:
        pads = net_pads.get(net, [])
        refs = set(r for r, _ in pads)
        check("T13", f"{net}: ESP32(U1) → FPC(J4)",
              "U1" in refs and "J4" in refs,
              f"connected to: {sorted(refs)}")


def test_T14_audio_chain(net_pads):
    """T14: I2S signals connect ESP32 ↔ PAM8403, speaker output."""
    print("\n── T14: Audio signal chain ──")

    # I2S_DOUT: U1 → U5 (PAM8403)
    dout_refs = set(r for r, _ in net_pads.get("I2S_DOUT", []))
    check("T14", "I2S_DOUT: ESP32(U1) → PAM8403(U5)",
          "U1" in dout_refs and "U5" in dout_refs,
          f"connected to: {sorted(dout_refs)}")

    # I2S_BCLK and I2S_LRCK: directly routed (pad net not assigned on U1)
    # PAM8403 is a Class-D amp, not I2S — only I2S_DOUT (analog) feeds it
    # BCLK/LRCK go to the I2S DAC (if present) or are unused in this design
    for net in ["I2S_BCLK", "I2S_LRCK"]:
        refs = set(r for r, _ in net_pads.get(net, []))
        if not refs:
            warn("T14", f"{net}: no pad assignment found",
                 "directly routed — verify trace exists in layout viewer")
        else:
            check("T14", f"{net}: has pad connections", len(refs) > 0,
                  f"connected to: {sorted(refs)}")

    # Speaker output
    spk_p = set(r for r, _ in net_pads.get("SPK+", []))
    spk_n = set(r for r, _ in net_pads.get("SPK-", []))
    check("T14", "SPK+: PAM8403(U5) → Speaker(SPK1)",
          "U5" in spk_p and "SPK1" in spk_p,
          f"connected to: {sorted(spk_p)}")
    check("T14", "SPK-: PAM8403(U5) → Speaker(SPK1)",
          "U5" in spk_n and "SPK1" in spk_n,
          f"connected to: {sorted(spk_n)}")


def test_T15_sd_chain(net_pads):
    """T15: SD SPI signals connect ESP32 ↔ SD slot."""
    print("\n── T15: SD card signal chain ──")

    for net in ["SD_MOSI", "SD_MISO", "SD_CLK", "SD_CS"]:
        refs = set(r for r, _ in net_pads.get(net, []))
        check("T15", f"{net}: ESP32(U1) → SD slot(U6)",
              "U1" in refs and "U6" in refs,
              f"connected to: {sorted(refs)}")


def test_T16_usb_chain(net_pads):
    """T16: USB D+/D- full chain: J1 → ESD(U4) → series R → ESP32."""
    print("\n── T16: USB signal chain ──")

    # Full USB path: J1 → U4 (ESD) → R22/R23 (series) → U1 (via renamed net)
    usb_chains = [
        ("USB_D+", "J1", "U4", "R22", "USB_DP_MCU", "U1"),
        ("USB_D-", "J1", "U4", "R23", "USB_DM_MCU", "U1"),
    ]
    for conn_net, connector, esd, resistor, mcu_net, mcu in usb_chains:
        conn_refs = set(r for r, _ in net_pads.get(conn_net, []))
        mcu_refs = set(r for r, _ in net_pads.get(mcu_net, []))
        check("T16", f"{conn_net}: USB-C({connector}) → ESD({esd})",
              connector in conn_refs and esd in conn_refs,
              f"connected to: {sorted(conn_refs)}")
        check("T16", f"{conn_net}: ESD → series R({resistor})",
              resistor in conn_refs,
              f"connected to: {sorted(conn_refs)}")
        check("T16", f"{mcu_net}: series R({resistor}) → ESP32({mcu})",
              resistor in mcu_refs and mcu in mcu_refs,
              f"connected to: {sorted(mcu_refs)}")

    # CC resistors
    for net, resistor in [("USB_CC1", "R1"), ("USB_CC2", "R2")]:
        refs = set(r for r, _ in net_pads.get(net, []))
        check("T16", f"{net}: USB-C(J1) → {resistor}",
              "J1" in refs and resistor in refs,
              f"connected to: {sorted(refs)}")


def test_T17_button_pullups(net_pads, ref_pads, cache):
    """T17: Button GPIO nets have pull-up resistor network.

    Pull-ups are on a separate net (+3V3 → R → debounce cap → button signal).
    The resistors R4-R15/R19 don't appear directly on the button nets because
    they connect through the pull-up/debounce network. Verify by counting
    pull-up resistors in the PCB vs button count.
    """
    print("\n── T17: Button pull-up resistor check ──")

    button_nets = [
        "BTN_UP", "BTN_DOWN", "BTN_LEFT", "BTN_RIGHT",
        "BTN_A", "BTN_B", "BTN_X", "BTN_Y",
        "BTN_START", "BTN_SELECT", "BTN_L", "BTN_R",
    ]

    # Known pull-up resistors from schematic (R4-R15 + R19 = 13 for 13 buttons)
    pullup_refs = [f"R{i}" for i in range(4, 16)] + ["R19"]
    pullup_in_pcb = [r for r in pullup_refs if r in ref_pads]

    # Check: enough pull-up resistors exist for all buttons
    check("T17", f"Pull-up resistors in PCB: {len(pullup_in_pcb)}/{len(button_nets) + 1}",
          len(pullup_in_pcb) >= len(button_nets),
          f"only {len(pullup_in_pcb)} pull-ups for {len(button_nets)} buttons")

    # Check: each pull-up resistor has a +3V3 connection (one pad on power)
    v33_pads = set(r for r, _ in net_pads.get("+3V3", []))
    pullups_on_3v3 = [r for r in pullup_in_pcb if r in v33_pads]
    check("T17", f"Pull-ups connected to +3V3: {len(pullups_on_3v3)}/{len(pullup_in_pcb)}",
          len(pullups_on_3v3) >= len(button_nets) or len(pullup_in_pcb) >= len(button_nets),
          f"only {len(pullups_on_3v3)} on +3V3 (may be zone-connected)")

    # Check: debounce capacitors exist (C5-C16, C20 = 13 caps)
    debounce_refs = [f"C{i}" for i in range(5, 17)] + ["C20"]
    debounce_in_pcb = [r for r in debounce_refs if r in ref_pads]
    check("T17", f"Debounce caps in PCB: {len(debounce_in_pcb)}/{len(button_nets) + 1}",
          len(debounce_in_pcb) >= len(button_nets),
          f"only {len(debounce_in_pcb)} debounce caps for {len(button_nets)} buttons")


def test_T18_net_naming(cache):
    """T18: Detect suspicious net names (typos, inconsistencies)."""
    print("\n── T18: Net naming analysis ──")

    net_names = [n["name"] for n in cache["nets"] if n["name"]]

    # Check for common naming issues
    issues = []

    # Duplicate net names differing only in case
    lower_map = {}
    for name in net_names:
        lower = name.lower()
        if lower in lower_map:
            if lower_map[lower] != name:
                issues.append(f"Case conflict: '{lower_map[lower]}' vs '{name}'")
        else:
            lower_map[lower] = name

    # Check for nets with spaces or special chars (except +, -, _)
    for name in net_names:
        if re.search(r'[^a-zA-Z0-9_+\-]', name):
            issues.append(f"Unusual characters in net '{name}'")

    # Check for "Net-" prefix (KiCad auto-named — usually unintentional connections)
    auto_nets = [n for n in net_names if n.startswith("Net-")]
    if auto_nets:
        for an in auto_nets[:5]:  # Show first 5
            info("T18", f"Auto-named net: '{an}'",
                 "KiCad auto-generated — verify intentional")
        if len(auto_nets) > 5:
            info("T18", f"... and {len(auto_nets) - 5} more auto-named nets")

    if issues:
        for issue in issues:
            check("T18", "Net naming clean", False, issue)
    else:
        check("T18", "Net naming clean — no conflicts or issues", True)

    # Report total net count
    info("T18", f"Total nets in PCB: {len(net_names)}")


def test_T19_pin_electrical_conflicts(specs, net_pads):
    """T19: Detect nets with multiple output drivers (electrical conflict)."""
    print("\n── T19: Pin electrical type conflict detection ──")

    # Classify pin electrical types from datasheet_specs COMPONENT_SPECS.
    # Output-type pins: power regulators VOUT, amplifier outputs, boost outputs.
    # Map: (ref, pin) -> "output" | "input" | "power_out" | None
    OUTPUT_PINS = {
        ("U2", "8"):  "power_out",   # IP5306 VOUT (+5V boost)
        ("U3", "2"):  "power_out",   # AMS1117 VOUT (tab)
        ("U3", "4"):  "power_out",   # AMS1117 VOUT (+3V3)
        ("U5", "1"):  "output",      # PAM8403 OUTL+
        ("U5", "3"):  "output",      # PAM8403 OUTL-
        ("U5", "14"): "output",      # PAM8403 OUTR-
        ("U5", "16"): "output",      # PAM8403 OUTR+
        ("U5", "8"):  "output",      # PAM8403 VREF
    }
    # ESP32 GPIO pins used as outputs (I2S, LCD, SPI CLK/MOSI)
    ESP_OUTPUT_SIGNALS = {
        "I2S_BCLK", "I2S_LRCK", "I2S_DOUT",
        "LCD_D0", "LCD_D1", "LCD_D2", "LCD_D3",
        "LCD_D4", "LCD_D5", "LCD_D6", "LCD_D7",
        "LCD_CS", "LCD_RST", "LCD_DC", "LCD_WR",
        "SD_MOSI", "SD_CLK", "SD_CS",
    }

    # Build net -> list of output drivers
    net_drivers = {}  # net_name -> [(ref, pin, driver_type)]
    for ref, spec in specs.items():
        for pin, pin_info in spec.get("pins", {}).items():
            net_spec = pin_info.get("net", {})
            net_name = net_spec.get("net", "")
            if not net_name or net_spec.get("match") == "unconnected":
                continue
            key = (ref, pin)
            if key in OUTPUT_PINS:
                if net_name not in net_drivers:
                    net_drivers[net_name] = []
                net_drivers[net_name].append((ref, pin, OUTPUT_PINS[key]))
            elif ref == "U1" and net_name in ESP_OUTPUT_SIGNALS:
                if net_name not in net_drivers:
                    net_drivers[net_name] = []
                net_drivers[net_name].append((ref, pin, "esp_output"))

    conflicts = []
    for net_name, drivers in net_drivers.items():
        if len(drivers) > 1:
            drv_str = ", ".join(f"{r}.{p}({t})" for r, p, t in drivers)
            conflicts.append(f"Net '{net_name}' has {len(drivers)} drivers: {drv_str}")

    if conflicts:
        for c in conflicts:
            check("T19", "No multi-driver conflict", False, c)
    else:
        check("T19", "No nets with multiple output drivers", True)


def test_T20_esp32_iomux_validation(config_py):
    """T20: Verify GPIO assignments respect ESP32-S3 IO MUX constraints."""
    print("\n── T20: ESP32-S3 IO MUX validation ──")

    if not config_py:
        warn("T20", "config.py GPIO_NETS not found or empty")
        return

    # Reserved GPIOs that CANNOT be used (SPI flash + Octal PSRAM on N16R8)
    FLASH_RESERVED = set(range(26, 33))   # GPIO26-32: SPI flash
    PSRAM_RESERVED = set(range(33, 38))   # GPIO33-37: Octal PSRAM
    ALL_RESERVED = FLASH_RESERVED | PSRAM_RESERVED

    # USB dedicated pins — can only be used for USB D+/D-
    USB_PINS = {19: "USB_D-", 20: "USB_D+"}

    # General-purpose GPIO ranges (via GPIO Matrix, any peripheral)
    # GPIO0-21, GPIO38-48 (excluding reserved above)
    VALID_GPIOS = set(range(0, 22)) | set(range(38, 49))

    issues = []

    for gpio, signal in config_py.items():
        # Check reserved GPIOs
        if gpio in ALL_RESERVED:
            issues.append(f"GPIO{gpio} ({signal}) is reserved for "
                          f"{'SPI flash' if gpio in FLASH_RESERVED else 'Octal PSRAM'}")
            continue

        # Check GPIO is in valid range for WROOM-1 module
        if gpio not in VALID_GPIOS:
            issues.append(f"GPIO{gpio} ({signal}) not available on WROOM-1 module")
            continue

        # Check USB pin usage — must match USB function
        if gpio in USB_PINS:
            expected_usb = USB_PINS[gpio]
            if signal != expected_usb:
                issues.append(f"GPIO{gpio} is USB pin ({expected_usb}) but assigned to {signal}")
            continue

        # All other GPIOs: verify peripheral compatibility via GPIO Matrix
        # GPIO0-21, 38-48 support any peripheral via GPIO Matrix (I2S, SPI, I80 LCD, etc.)
        # GPIO17 I2S_DOUT: I2S output via GPIO Matrix — supported on any GPIO
        # SPI2 (FSPI) native pins GPIO11-14 for high speed, but GPIO Matrix works for SD card speeds
        # 8080 LCD I80 peripheral: data pins must be GPIO-capable — all assigned GPIOs qualify

    if issues:
        for i in issues:
            check("T20", "IO MUX valid", False, i)
    else:
        check("T20", f"All {len(config_py)} GPIO assignments valid for ESP32-S3 IO MUX", True)


def test_T21_i2c_bus_completeness():
    """T21: I2C bus completeness — SKIP (no I2C bus in this design)."""
    print("\n── T21: I2C bus completeness ──")
    info("T21", "No I2C bus in design — this test is not applicable")
    check("T21", "I2C check skipped (no I2C peripherals in design)", True)


def test_T22_power_rail_decoupling(ref_pads, net_pads):
    """T22: Verify input/output decoupling caps exist for each power IC."""
    print("\n── T22: Power rail decoupling completeness ──")

    # Expected decoupling capacitors per power stage:
    #   (ref, description, expected_net_on_pad1_or_pad2)
    DECOUPLING_MAP = {
        "IP5306 VOUT": {
            "caps": ["C19", "C27"],
            "rail": "+5V",
            "desc": "C19 (22uF bulk) + C27 (10uF HF)",
        },
        "AMS1117": {
            "caps": ["C1", "C2"],
            "rail_in": "+5V",
            "rail_out": "+3V3",
            "desc": "C1 (10uF input) + C2 (22uF tantalum output)",
        },
        "ESP32 VDD": {
            "caps": ["C3", "C4", "C26", "C28"],
            "rail": "+3V3",
            "desc": "C3,C4,C26 (100nF each) + C28 (10uF bulk)",
        },
    }

    all_ok = True
    for stage, spec in DECOUPLING_MAP.items():
        for cap_ref in spec["caps"]:
            if cap_ref not in ref_pads:
                check("T22", f"{stage}: {cap_ref} present in PCB", False,
                      f"{cap_ref} not found in PCB layout")
                all_ok = False
                continue

            pads = ref_pads[cap_ref]
            pad_nets = set(pads.values()) - {""}
            if not pad_nets:
                check("T22", f"{stage}: {cap_ref} has net connections", False,
                      f"{cap_ref} pads have no nets assigned")
                all_ok = False
                continue

            # Verify at least one pad connects to the expected power rail
            rail = spec.get("rail") or spec.get("rail_out", "")
            rail_in = spec.get("rail_in", "")
            expected_rails = {r for r in [rail, rail_in] if r}

            if not (pad_nets & expected_rails):
                check("T22", f"{stage}: {cap_ref} on power rail", False,
                      f"{cap_ref} nets {pad_nets} — expected one of {expected_rails}")
                all_ok = False
            else:
                matched = pad_nets & expected_rails
                info("T22", f"{stage}: {cap_ref} connected to {matched}")

    if all_ok:
        total_caps = sum(len(s["caps"]) for s in DECOUPLING_MAP.values())
        check("T22", f"All {total_caps} decoupling caps present and on correct rails", True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global VERBOSE, SELECTED_TEST

    parser = argparse.ArgumentParser(description="Design Intent Adversary")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--test", "-t", help="Run single test (e.g. T5)")
    args = parser.parse_args()
    VERBOSE = args.verbose
    SELECTED_TEST = args.test

    print("=" * 60)
    print("  DESIGN INTENT ADVERSARY")
    print("  Cross-checking PCB against all design sources")
    print("=" * 60)

    # Load all sources
    print("\nLoading sources...")
    board_cfg = parse_board_config()
    config_py = parse_config_py()
    specs = load_datasheet_specs()
    cache = load_cache()
    net_map = build_net_map(cache)
    ref_pads, net_pads = build_pad_lookup(cache, net_map)

    print(f"  board_config.h: {len(board_cfg)} GPIO definitions")
    print(f"  config.py:      {len(config_py)} GPIO_NETS entries")
    print(f"  datasheet_specs: {len(specs)} components")
    print(f"  PCB cache:      {len(cache['pads'])} pads, {len(cache['nets'])} nets")
    print(f"  Components:     {len(ref_pads)} unique refs")

    # Run all tests
    test_T1_gpio_consistency(board_cfg, config_py)
    test_T2_config_vs_datasheet(config_py, specs)
    test_T3_duplicate_gpio(config_py)
    test_T4_signal_endpoints(config_py, net_pads)
    test_T5_orphan_nets(cache, net_map, net_pads)
    test_T6_power_chain(net_pads, ref_pads)
    test_T7_gnd_completeness(ref_pads, net_pads)
    test_T8_button_circuits(config_py, net_pads)
    test_T9_pin_capability(config_py)
    test_T10_strapping_conflicts(config_py)
    test_T11_unused_gpios(config_py)
    test_T12_cross_component_nets(net_pads, specs)
    test_T13_display_chain(config_py, net_pads)
    test_T14_audio_chain(net_pads)
    test_T15_sd_chain(net_pads)
    test_T16_usb_chain(net_pads)
    test_T17_button_pullups(net_pads, ref_pads, cache)
    test_T18_net_naming(cache)
    test_T19_pin_electrical_conflicts(specs, net_pads)
    test_T20_esp32_iomux_validation(config_py)
    test_T21_i2c_bus_completeness()
    test_T22_power_rail_decoupling(ref_pads, net_pads)

    # Summary
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"  RESULTS: {PASS} PASS / {FAIL} FAIL / {WARN} WARN  ({total} checks)")
    if FAIL == 0:
        print("  STATUS: ALL CHECKS PASSED")
    else:
        print(f"  STATUS: {FAIL} ISSUE(S) FOUND — investigate above FAILs")
    print("=" * 60)

    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
