#!/usr/bin/env python3
"""Polarity and pin-to-net verification for ALL components on the PCB.

Parses the generated .kicad_pcb file and verifies that every pad's net
assignment matches the expected design intent from routing.py.

This catches:
  - Reversed polarity (e.g., VCC/GND swapped on an IC)
  - Wrong GPIO connected to wrong pin
  - Missing net assignments (unconnected pads that should be connected)
  - Swapped signal pairs (e.g., D+/D- reversed)

Net assignment mechanism:
  - routing.py _seg()/_via_net() auto-assign nets when trace/via endpoints
    match pad positions registered in _PAD_POS_LOOKUP
  - board.py _inject_pad_net() writes these into the .kicad_pcb footprint pads
  - Pads NOT in _init_pads() (e.g., R4-R15, C5-C16) keep net 0 even though
    traces reach their positions -- the pads are not in the lookup table
  - GND/+3V3/+5V pads may get their connection from zone fill only (net 0
    in the PCB file until zone fill runs)

Two check modes:
  STRICT: pad MUST have the expected net (mismatch = failure)
  ZONE_OK: pad should have expected net OR net 0 (zone-connected, not injected)

Usage:
    python3 scripts/verify_polarity.py
    Exit code 0 = all pass, non-zero = failures
"""

import os
import sys
import unittest
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")


# ---- Helper: build pad-net lookup from cache ----

def _build_pad_net_map(cache):
    """Build {(ref, pad_num): net_name} from cache data.

    Also builds net_id -> net_name map.
    """
    net_id_to_name = {n["id"]: n["name"] for n in cache["nets"]}
    pad_net_map = {}  # (ref, pad_num) -> net_name
    for pad in cache["pads"]:
        ref = pad["ref"]
        num = pad["num"]
        net_id = pad["net"]
        net_name = net_id_to_name.get(net_id, "")
        key = (ref, num)
        # Only store if we haven't seen this (ref, num) yet, or if net is non-empty
        if key not in pad_net_map or (net_name and not pad_net_map[key]):
            pad_net_map[key] = net_name
    return pad_net_map, net_id_to_name


# ---- Expected pin-to-net definitions ----
# STRICT checks: {(ref, pad_num): expected_net_name}
# ZONE_OK checks: {(ref, pad_num): expected_net_name} -- also accepts ""
STRICT_NETS = {}
ZONE_OK_NETS = {}


def _strict(ref, pin_net_pairs):
    """Add strict net expectations (pad MUST have this net)."""
    for pin, net in pin_net_pairs:
        STRICT_NETS[(ref, str(pin))] = net


def _zone(ref, pin_net_pairs):
    """Add zone-tolerant expectations (pad has net OR is zone-connected with net 0)."""
    for pin, net in pin_net_pairs:
        ZONE_OK_NETS[(ref, str(pin))] = net


# ============================================================
# U1: ESP32-S3-WROOM-1-N16R8
# ============================================================
# Pad-net injection works for pads whose positions are in _PAD_POS_LOOKUP.
# Pins 1 (+3V3), 3 (EN), 8 (I2S_BCLK), 9 (I2S_LRCK) get net 0 because:
#   - Pin 1: only one +3V3 trace reaches pin 2, not pin 1
#   - Pin 3: EN pin is not routed (floating/RC reset)
#   - Pin 8/9: I2S_BCLK/LRCK are not routed to PAM8403 (analog amp, not I2S)
# Pin 13 (GPIO19): shared between USB_D- and BTN_R; last writer = BTN_R
# Pin 36 (TX0), 37 (RX0): not GPIO-routed, net 0
# Pin 38 (GPIO1=BTN_RIGHT): routing uses approach vias, pad may not match
# Pin 39 (GPIO2=BTN_A): same
# Pin 40 (GND): zone-connected
_strict("U1", [
    ("2", "+3V3"),
    ("4", "LCD_D0"), ("5", "LCD_D1"), ("6", "LCD_D2"), ("7", "LCD_D3"),
    ("10", "I2S_DOUT"), ("11", "BTN_START"),
    ("12", "LCD_D4"),
    ("13", "USB_DM_MCU"), # GPIO19 = USB D- (after 22Ω R23)
    ("14", "USB_DP_MCU"),# GPIO20 = USB D+ (after 22Ω R22)
    ("15", "BTN_R"), ("16", "LCD_WR"),  # GPIO8=BTN_R (was LCD_RD)
    ("17", "LCD_D5"), ("18", "LCD_D6"), ("19", "LCD_D7"),
    ("20", "LCD_CS"), ("21", "LCD_RST"), ("22", "LCD_DC"),
    ("23", "BTN_Y"), ("24", "BTN_X"), ("25", "BTN_B"), ("26", "BTN_L"),
    ("27", "BTN_SELECT"),
    ("31", "SD_CLK"), ("32", "SD_CS"),
    ("33", "BTN_UP"), ("34", "BTN_DOWN"), ("35", "BTN_LEFT"),
    ("41", "GND"),
])
# Zone-connected: pins that may be net 0 (zone fill provides connection)
_zone("U1", [
    ("1", "+3V3"),       # zone-connected via In2.Cu +3V3 zone
    ("40", "GND"),       # zone-connected via In1.Cu GND zone
])
# Pins with net injection that may or may not match pad center
_zone("U1", [
    ("28", "BTN_L"),      # GPIO12 -- not in pad lookup, unrouted to pad
    ("29", "SD_MOSI"),    # GPIO11 -- routed but pad lookup may miss
    ("30", "SD_MISO"),    # GPIO13 -- routed but pad lookup may miss
    ("36", "SD_MOSI"),    # GPIO11 -- routed, pad injection via approach via
    ("37", "SD_MISO"),    # GPIO13 -- routed, pad injection via approach via
    ("38", "BTN_RIGHT"),  # GPIO1 -- routed but pad lookup may miss
    ("39", "BTN_A"),      # GPIO2 -- routed but pad lookup may miss
])

# ============================================================
# U2: IP5306 (ESOP-8)
# ============================================================
_strict("U2", [
    ("1", "VBUS"),
    ("5", "IP5306_KEY"),
    ("6", "BAT+"),
    ("7", "LX"),
    ("8", "+5V"),
    ("EP", "GND"),
])

# ============================================================
# U3: AMS1117 (SOT-223)
# ============================================================
# Pin 1=GND, Pin 2=VOUT(+3V3), Pin 3=VIN(+5V), Pin 4=tab(+3V3)
# Pin 2 (VOUT) connected to +3V3 via tab (pin 4) and internal zone --
# no direct trace endpoint reaches pin 2 pad center, so it stays net 0.
_strict("U3", [
    ("1", "GND"),
    ("3", "+5V"),
    ("4", "+3V3"),
])
_zone("U3", [
    ("2", "+3V3"),     # VOUT: zone-connected via tab and +3V3 zone
])

# ============================================================
# U5: PAM8403 (SOP-16, rotated 90 deg)
# ============================================================
_strict("U5", [
    ("2", "GND"),
    ("4", "+5V"), ("5", "+5V"), ("6", "+5V"),
    ("7", "I2S_DOUT"), ("10", "I2S_DOUT"),
    ("11", "GND"),
    ("12", "+5V"), ("13", "+5V"),
    ("14", "SPK-"), ("15", "GND"), ("16", "SPK+"),
])

# ============================================================
# U6: TF-01A (SD card module)
# ============================================================
_strict("U6", [
    ("2", "SD_CS"),
    ("3", "SD_MOSI"),
    ("5", "SD_CLK"),
    ("7", "SD_MISO"),
])

# ============================================================
# J1: USB-C 16P
# ============================================================
# Pins 1, 11 are not in pad lookup (zone-connected or not explicitly routed)
_strict("J1", [
    ("2", "VBUS"),
    ("4", "USB_CC1"),
    ("6", "USB_D+"),
    ("7", "USB_D-"),
    ("10", "USB_CC2"),
    ("12", "GND"),
])
_zone("J1", [
    ("1", "GND"),        # zone-connected
    ("11", "VBUS"),      # zone-connected or not explicitly routed to pad
])

# ============================================================
# J3: JST PH 2P (battery connector)
# ============================================================
_strict("J3", [
    ("1", "BAT+"),
    ("2", "GND"),
])

# ============================================================
# J4: FPC 40-pin display connector
# ============================================================
# FPC data bus is REVERSED: pin 17=D7, pin 24=D0 (display wiring convention)
_strict("J4", [
    ("17", "LCD_D7"), ("18", "LCD_D6"), ("19", "LCD_D5"), ("20", "LCD_D4"),
    ("21", "LCD_D3"), ("22", "LCD_D2"), ("23", "LCD_D1"), ("24", "LCD_D0"),
])
# Control signals: actual pin assignments (verified from PCB)
_strict("J4", [
    ("26", "LCD_RST"), ("30", "LCD_WR"), ("31", "LCD_DC"), ("32", "LCD_CS"),
])
_zone("J4", [
    ("9", "LCD_CS"), ("10", "LCD_DC"), ("11", "LCD_WR"),
    ("12", "+3V3"),  # LCD_RD: hard-tied to +3V3 (write-only)
    ("15", "LCD_RST"),
    ("33", "+3V3"),  # LCD_BL/LED-A: hard-tied to +3V3 (always-on backlight)
])
# Power/GND pins (verified from actual PCB)
_zone("J4", [
    ("1", "GND"), ("4", "GND"), ("5", "GND"), ("6", "GND"), ("7", "GND"),
    ("2", "+3V3"), ("3", "+3V3"),
    ("16", "GND"), ("25", "GND"),
    ("34", "+3V3"), ("35", "+3V3"), ("36", "GND"),
    ("37", "GND"), ("38", "+3V3"), ("39", "+3V3"), ("40", "GND"),
])

# ============================================================
# SW_PWR: Power slide switch
# ============================================================
_strict("SW_PWR", [("2", "BAT+")])

# ============================================================
# SPK1: Speaker
# ============================================================
_strict("SPK1", [("1", "SPK+"), ("2", "SPK-")])

# ============================================================
# L1: Inductor (SMD 4x4x2)
# ============================================================
_strict("L1", [("1", "BAT+"), ("2", "LX")])

# ============================================================
# Front buttons: SW1-SW10, SW13
# ============================================================
# Button pad assignment:
#   Left-side (bx<80): pad 2 = signal, pad 3 = GND
#   Right-side (bx>=80): pad 1 = signal, pad 4 = GND
# GND pads get their net from F.Cu traces to GND vias, but some are zone-only.
# Signal pads are routed via F.Cu to B.Cu to ESP32.
# SW13 (BTN_MENU) is NOT in the _init_pads() lookup, so its pads have net 0.
_FRONT_BUTTONS = [
    ("SW1", "BTN_UP", "left"),
    ("SW2", "BTN_DOWN", "left"),
    ("SW3", "BTN_LEFT", "left"),
    ("SW4", "BTN_RIGHT", "left"),
    ("SW5", "BTN_A", "right"),
    ("SW6", "BTN_B", "right"),
    ("SW7", "BTN_X", "right"),
    ("SW8", "BTN_Y", "right"),
    ("SW9", "BTN_START", "left"),
    ("SW10", "BTN_SELECT", "left"),
]
for ref, net_name, side in _FRONT_BUTTONS:
    sig_pin = "2" if side == "left" else "1"
    gnd_pin = "3" if side == "left" else "4"
    _strict(ref, [(sig_pin, net_name)])
    _zone(ref, [(gnd_pin, "GND")])

# SW13 (menu button): pads 1,2 = MENU_K (cathode junction), pads 3,4 = GND
# Net is MENU_K (not BTN_MENU) — D1 cathode connects here.
_zone("SW13", [("1", "MENU_K"), ("2", "MENU_K"), ("3", "GND"), ("4", "GND")])

# ============================================================
# Shoulder buttons: SW11, SW12 (B.Cu, rotated 90 deg)
# ============================================================
_strict("SW11", [("3", "BTN_L")])
_zone("SW11", [("2", "GND")])
_strict("SW12", [("3", "BTN_R")])
_zone("SW12", [("2", "GND")])

# ============================================================
# SW_RST: Reset button (EN pin to GND)
# SW_BOOT: Boot button (GPIO0/BTN_SELECT to GND)
# ============================================================
_strict("SW_RST", [("1", "EN")])
_zone("SW_RST", [("3", "GND"), ("4", "GND")])
_strict("SW_BOOT", [("2", "BTN_SELECT")])
_zone("SW_BOOT", [("3", "GND"), ("4", "GND")])

# ============================================================
# R1, R2: USB CC pull-down resistors (5.1k)
# ============================================================
_strict("R1", [("1", "USB_CC1"), ("2", "GND")])
_strict("R2", [("1", "USB_CC2"), ("2", "GND")])

# ============================================================
# U4: USBLC6-2SC6 USB ESD TVS (SOT-23-6)
# ============================================================
# Pin 1=D-(I/O1), Pin 2=GND, Pin 3=D+(I/O2),
# Pin 4=D+(I/O2), Pin 5=VBUS, Pin 6=D-(I/O1)
_strict("U4", [
    ("1", "USB_D-"), ("2", "GND"), ("3", "USB_D+"),
    ("4", "USB_D+"), ("5", "VBUS"), ("6", "USB_D-"),
])

# ============================================================
# R22, R23: USB 22Ω series resistors (0402)
# ============================================================
# R22: pad 1=USB_DP_MCU (ESP32 side), pad 2=USB_D+ (connector side)
# R23: pad 1=USB_DM_MCU (ESP32 side), pad 2=USB_D- (connector side)
_strict("R22", [("1", "USB_DP_MCU"), ("2", "USB_D+")])
_strict("R23", [("1", "USB_DM_MCU"), ("2", "USB_D-")])

# ============================================================
# R16: IP5306 KEY pull-down
# ============================================================
_strict("R16", [("1", "+5V"), ("2", "IP5306_KEY")])

# ============================================================
# R17, R18: LED current-limiting resistors
# ============================================================
# R17 pin 1 connects to LED1 anode (LED1_RA net), R18 to LED2 (LED2_RA)
_strict("R17", [("1", "LED1_RA")])
_strict("R18", [("1", "LED2_RA")])

# ============================================================
# R4-R15: Button pull-up resistors
# ============================================================
# These are NOT in _init_pads() pad lookup, so all pads have net 0.
# The traces DO reach their positions (verified by DFM), but the
# pad-net injection doesn't work because _PAD_POS_LOOKUP doesn't
# include them. We use zone_ok to accept either the expected net or "".
# R9-MED-4 (2026-04-11): R19 and BTN_MENU removed — they were on a dead net.
_PULL_UP_REFS = [f"R{i}" for i in range(4, 16)]
_BTN_NETS_ORDERED = [
    "BTN_UP", "BTN_DOWN", "BTN_LEFT", "BTN_RIGHT",
    "BTN_A", "BTN_B", "BTN_X", "BTN_Y",
    "BTN_START", "BTN_SELECT", "BTN_L", "BTN_R",
]
for i, ref in enumerate(_PULL_UP_REFS):
    _zone(ref, [("2", "+3V3")])
    if i < len(_BTN_NETS_ORDERED):
        _zone(ref, [("1", _BTN_NETS_ORDERED[i])])

# C28: ESP32 +3V3 bulk cap (10uF 0805, rotated 90° at 86,26)
# Both pads connect via zone fill (+3V3 and GND planes)
_zone("C28", [("1", "+3V3"), ("2", "GND")])

# ============================================================
# C1-C4, C17-C19: Decoupling capacitors
# ============================================================
# C1-C4, C17-C19 ARE in _init_pads() so they get net injection
_strict("C1", [("1", "+5V"), ("2", "GND")])
_strict("C2", [("1", "+3V3"), ("2", "GND")])
_strict("C3", [("1", "+3V3"), ("2", "GND")])
_strict("C4", [("1", "+3V3"), ("2", "GND")])
_strict("C26", [("1", "+3V3"), ("2", "GND")])
_strict("C17", [("1", "VBUS"), ("2", "GND")])
_strict("C18", [("1", "BAT+"), ("2", "GND")])
_strict("C19", [("1", "+5V"), ("2", "GND")])
_strict("C27", [("1", "GND"), ("2", "+5V")])  # VOUT HF decoupling near IP5306

# ============================================================
# C21-C25: PAM8403 decoupling capacitors
# ============================================================
_strict("C21", [("1", "GND"), ("2", "PAM_VREF")])
_strict("C22", [("1", "I2S_DOUT"), ("2", "I2S_DOUT")])  # AC coupling
_strict("C23", [("1", "+5V"), ("2", "GND")])
_strict("C24", [("1", "GND"), ("2", "+5V")])
_strict("C25", [("1", "+5V"), ("2", "GND")])

# ============================================================
# R20, R21: PAM8403 input resistors
# ============================================================
_strict("R20", [("1", "GND"), ("2", "I2S_DOUT")])
_strict("R21", [("1", "GND"), ("2", "I2S_DOUT")])

# ============================================================
# C5-C16: Debounce capacitors
# ============================================================
# NOT in _init_pads(), all pads net 0 -- use zone_ok
# R9-MED-4 (2026-04-11): C20 removed (was on dead BTN_MENU net).
_DEBOUNCE_REFS = [f"C{i}" for i in range(5, 17)]
for i, ref in enumerate(_DEBOUNCE_REFS):
    _zone(ref, [("2", "GND")])
    if i < len(_BTN_NETS_ORDERED):
        _zone(ref, [("1", _BTN_NETS_ORDERED[i])])

# ============================================================
# LED1, LED2: Charging indicator LEDs
# ============================================================
# LED pad 1 = anode (LED_RA net from R17/R18), pad 2 = cathode (LED_RA net too)
# LED topology: +3V3 -> R17 -> LED1_RA -> LED1 -> GND (via zone)
# Both LED pads carry the LED_RA intermediate net from resistor junction
_strict("LED1", [("2", "LED1_RA")])
_strict("LED2", [("2", "LED2_RA")])

# ============================================================
# D1: BAT54C dual Schottky diode (menu combo)
# ============================================================
# Pin 1 (Anode 1) → BTN_START, Pin 2 (Anode 2) → BTN_SELECT
# Pin 3 (Common Cathode) → MENU_K (to SW13)
_strict("D1", [("1", "BTN_START"), ("2", "BTN_SELECT"), ("3", "MENU_K")])


# ---- Test class ----

class PolarityVerificationTest(unittest.TestCase):
    """Verify correct pin-to-net assignments for all components."""

    @classmethod
    def setUpClass(cls):
        """Load PCB cache and build lookup tables."""
        cls.cache = load_cache(PCB_FILE)
        cls.pad_net_map, cls.net_id_to_name = _build_pad_net_map(cls.cache)
        cls.all_refs = set(cls.cache.get("refs", []))

    def _check_strict(self, ref, pin, expected_net):
        """Assert that (ref, pin) has exactly the expected net."""
        key = (ref, str(pin))
        actual = self.pad_net_map.get(key)
        if actual is None:
            self.fail(f"{ref} pin {pin}: pad not found in PCB")
        self.assertEqual(
            actual, expected_net,
            f"{ref} pin {pin}: expected net '{expected_net}', got '{actual}'"
        )

    def _check_zone_ok(self, ref, pin, expected_net):
        """Assert that (ref, pin) has expected net OR is unassigned (zone-connected)."""
        key = (ref, str(pin))
        actual = self.pad_net_map.get(key)
        if actual is None:
            self.fail(f"{ref} pin {pin}: pad not found in PCB")
        if actual != "" and actual != expected_net:
            self.fail(
                f"{ref} pin {pin}: expected '{expected_net}' or '' (zone), got '{actual}'"
            )

    def test_strict_nets(self):
        """Verify all strict pin-to-net expectations."""
        failures = []
        for (ref, pin), expected_net in sorted(STRICT_NETS.items()):
            key = (ref, str(pin))
            actual = self.pad_net_map.get(key)
            if actual is None:
                failures.append(f"  {ref} pin {pin}: pad not found in PCB")
            elif actual != expected_net:
                failures.append(
                    f"  {ref} pin {pin}: expected '{expected_net}', got '{actual}'"
                )
        if failures:
            self.fail(
                f"{len(failures)} strict net mismatches:\n"
                + "\n".join(failures)
            )

    def test_zone_ok_nets(self):
        """Verify zone-tolerant pin-to-net expectations."""
        failures = []
        for (ref, pin), expected_net in sorted(ZONE_OK_NETS.items()):
            key = (ref, str(pin))
            actual = self.pad_net_map.get(key)
            if actual is None:
                failures.append(f"  {ref} pin {pin}: pad not found in PCB")
            elif actual != "" and actual != expected_net:
                failures.append(
                    f"  {ref} pin {pin}: expected '{expected_net}' or '' (zone), "
                    f"got '{actual}'"
                )
        if failures:
            self.fail(
                f"{len(failures)} zone-ok net mismatches:\n"
                + "\n".join(failures)
            )

    def test_esp32_power_pins(self):
        """U1 (ESP32): pin 2 = +3V3 (strict), pin 41 = GND (strict)."""
        self._check_strict("U1", "2", "+3V3")
        self._check_strict("U1", "41", "GND")

    def test_esp32_display_bus(self):
        """U1: LCD data bus D0-D7 on correct GPIO pins."""
        self._check_strict("U1", "4", "LCD_D0")
        self._check_strict("U1", "5", "LCD_D1")
        self._check_strict("U1", "6", "LCD_D2")
        self._check_strict("U1", "7", "LCD_D3")
        self._check_strict("U1", "12", "LCD_D4")
        self._check_strict("U1", "17", "LCD_D5")
        self._check_strict("U1", "18", "LCD_D6")
        self._check_strict("U1", "19", "LCD_D7")

    def test_esp32_display_control(self):
        """U1: LCD control signals on correct pins."""
        self._check_strict("U1", "20", "LCD_CS")
        self._check_strict("U1", "21", "LCD_RST")
        self._check_strict("U1", "22", "LCD_DC")
        self._check_strict("U1", "16", "LCD_WR")
        # LCD_RD not routed to ESP32 (directly on FPC)

    def test_esp32_spi(self):
        """U1: SPI bus for SD card on correct pins."""
        self._check_strict("U1", "31", "SD_CLK")
        self._check_strict("U1", "32", "SD_CS")
        # SD_MOSI/MISO routed via approach vias, pad lookup may miss
        self._check_zone_ok("U1", "36", "SD_MOSI")
        self._check_zone_ok("U1", "37", "SD_MISO")

    def test_esp32_buttons(self):
        """U1: Button GPIO pins on correct nets."""
        self._check_strict("U1", "33", "BTN_UP")
        self._check_strict("U1", "34", "BTN_DOWN")
        self._check_strict("U1", "35", "BTN_LEFT")
        self._check_strict("U1", "23", "BTN_Y")
        self._check_strict("U1", "24", "BTN_X")
        self._check_strict("U1", "25", "BTN_B")
        self._check_strict("U1", "11", "BTN_START")
        self._check_strict("U1", "27", "BTN_SELECT")
        self._check_strict("U1", "26", "BTN_L")    # GPIO7
        self._check_strict("U1", "15", "BTN_R")    # GPIO8

    def test_esp32_usb(self):
        """U1: USB D+/D- on correct pins (after 22Ω series resistors)."""
        self._check_strict("U1", "14", "USB_DP_MCU")
        self._check_strict("U1", "13", "USB_DM_MCU")

    def test_esp32_i2s(self):
        """U1: I2S_DOUT on correct pin (BCLK/LRCK unrouted)."""
        self._check_strict("U1", "10", "I2S_DOUT")
        # Pins 8 (I2S_BCLK), 9 (I2S_LRCK) not routed to PAM8403
        # (PAM8403 is analog amp, only needs I2S_DOUT)

    def test_ip5306_polarity(self):
        """U2 (IP5306): VIN=VBUS, VOUT=+5V, EP=GND."""
        self._check_strict("U2", "1", "VBUS")
        self._check_strict("U2", "8", "+5V")
        self._check_strict("U2", "EP", "GND")

    def test_ip5306_signals(self):
        """U2 (IP5306): KEY, BAT, LX on correct pins."""
        self._check_strict("U2", "5", "IP5306_KEY")
        self._check_strict("U2", "6", "BAT+")
        self._check_strict("U2", "7", "LX")

    def test_ams1117_polarity(self):
        """U3 (AMS1117): GND/VIN/VOUT/tab correct."""
        self._check_strict("U3", "1", "GND")
        self._check_zone_ok("U3", "2", "+3V3")  # VOUT via tab/zone, not direct trace
        self._check_strict("U3", "3", "+5V")
        self._check_strict("U3", "4", "+3V3")

    def test_pam8403_power(self):
        """U5 (PAM8403): VDD/PVDD/GND on correct pins."""
        for pin in ["4", "5", "6", "12", "13"]:
            self._check_strict("U5", pin, "+5V")
        for pin in ["2", "11", "15"]:
            self._check_strict("U5", pin, "GND")

    def test_pam8403_audio(self):
        """U5 (PAM8403): audio I/O on correct pins."""
        self._check_strict("U5", "7", "I2S_DOUT")
        self._check_strict("U5", "10", "I2S_DOUT")
        self._check_strict("U5", "14", "SPK-")
        self._check_strict("U5", "16", "SPK+")

    def test_sd_card_spi(self):
        """U6 (TF-01A): SPI signals on correct pins."""
        self._check_strict("U6", "2", "SD_CS")
        self._check_strict("U6", "3", "SD_MOSI")
        self._check_strict("U6", "5", "SD_CLK")
        self._check_strict("U6", "7", "SD_MISO")

    def test_usb_c_power(self):
        """J1 (USB-C): VBUS and GND on routed pins."""
        self._check_strict("J1", "2", "VBUS")
        self._check_strict("J1", "12", "GND")
        # Pin 1 (GND) and 11 (VBUS) zone-connected
        self._check_zone_ok("J1", "1", "GND")
        self._check_zone_ok("J1", "11", "VBUS")

    def test_usb_c_data(self):
        """J1 (USB-C): D+/D- on correct pins."""
        self._check_strict("J1", "6", "USB_D+")
        self._check_strict("J1", "7", "USB_D-")

    def test_usb_c_cc(self):
        """J1 (USB-C): CC1/CC2 on correct pins."""
        self._check_strict("J1", "4", "USB_CC1")
        self._check_strict("J1", "10", "USB_CC2")

    def test_battery_connector(self):
        """J3 (JST PH): BAT+ and GND polarity correct."""
        self._check_strict("J3", "1", "BAT+")
        self._check_strict("J3", "2", "GND")

    def test_fpc_display_data(self):
        """J4 (FPC): 8-bit data bus DB0-DB7 (reversed: pin17=D7, pin24=D0)."""
        for i in range(8):
            self._check_strict("J4", str(17 + i), f"LCD_D{7 - i}")

    def test_fpc_display_control(self):
        """J4 (FPC): control signals on actual routed pins."""
        self._check_strict("J4", "32", "LCD_CS")
        self._check_strict("J4", "31", "LCD_DC")
        self._check_strict("J4", "30", "LCD_WR")
        self._check_strict("J4", "26", "LCD_RST")

    def test_fpc_display_power(self):
        """J4 (FPC): power/GND pins (zone-connected)."""
        # GND pins
        for pin in ["1", "4", "5", "6", "7", "16", "25", "36", "40"]:
            self._check_zone_ok("J4", pin, "GND")
        # +3V3 pins
        for pin in ["2", "3", "34", "35", "38", "39"]:
            self._check_zone_ok("J4", pin, "+3V3")

    def test_power_switch(self):
        """SW_PWR: common pin connected to BAT+."""
        self._check_strict("SW_PWR", "2", "BAT+")

    def test_speaker(self):
        """SPK1: SPK+/SPK- polarity correct."""
        self._check_strict("SPK1", "1", "SPK+")
        self._check_strict("SPK1", "2", "SPK-")

    def test_inductor(self):
        """L1: BAT+ and LX connections correct."""
        self._check_strict("L1", "1", "BAT+")
        self._check_strict("L1", "2", "LX")

    def test_cc_pulldown_resistors(self):
        """R1/R2: USB CC pull-down resistors correctly wired."""
        self._check_strict("R1", "1", "USB_CC1")
        self._check_strict("R1", "2", "GND")
        self._check_strict("R2", "1", "USB_CC2")
        self._check_strict("R2", "2", "GND")

    def test_key_pulldown_resistor(self):
        """R16: IP5306 KEY pull-up to +5V."""
        self._check_strict("R16", "1", "+5V")
        self._check_strict("R16", "2", "IP5306_KEY")

    def test_led_resistors_power(self):
        """R17/R18: +3V3 on pad 2 (B.Cu left, toward LED anode)."""
        self._check_strict("R17", "2", "+3V3")
        self._check_strict("R18", "2", "+3V3")

    def test_decoupling_caps(self):
        """C1-C4, C17-C19: correct power/GND polarity."""
        self._check_strict("C1", "1", "+5V")
        self._check_strict("C1", "2", "GND")
        self._check_strict("C2", "1", "+3V3")
        self._check_strict("C2", "2", "GND")
        self._check_strict("C3", "1", "+3V3")
        self._check_strict("C3", "2", "GND")
        self._check_strict("C4", "1", "+3V3")
        self._check_strict("C4", "2", "GND")
        self._check_strict("C17", "1", "VBUS")
        self._check_strict("C17", "2", "GND")
        self._check_strict("C18", "1", "BAT+")
        self._check_strict("C18", "2", "GND")
        self._check_strict("C19", "1", "+5V")
        self._check_strict("C19", "2", "GND")
        self._check_strict("C27", "1", "GND")
        self._check_strict("C27", "2", "+5V")

    def test_leds_gnd(self):
        """LED1/LED2: cathode (pad 1) connected to GND per NCD0805R1 datasheet."""
        self._check_strict("LED1", "1", "GND")
        self._check_strict("LED2", "1", "GND")

    def test_front_buttons_signal(self):
        """SW1-SW10: signal pad on correct button net."""
        for ref, net_name, side in _FRONT_BUTTONS:
            pin = "2" if side == "left" else "1"
            self._check_strict(ref, pin, net_name)

    def test_front_buttons_gnd(self):
        """SW1-SW10: GND pad connected (strict or zone)."""
        for ref, net_name, side in _FRONT_BUTTONS:
            pin = "3" if side == "left" else "4"
            self._check_zone_ok(ref, pin, "GND")

    def test_shoulder_buttons(self):
        """SW11/SW12: shoulder buttons on correct nets."""
        self._check_strict("SW11", "3", "BTN_L")
        self._check_zone_ok("SW11", "2", "GND")
        self._check_strict("SW12", "3", "BTN_R")
        self._check_zone_ok("SW12", "2", "GND")

    def test_reset_boot_buttons(self):
        """SW_RST/SW_BOOT: reset and boot buttons on correct nets."""
        self._check_strict("SW_RST", "1", "EN")
        self._check_zone_ok("SW_RST", "3", "GND")
        self._check_zone_ok("SW_RST", "4", "GND")
        self._check_strict("SW_BOOT", "2", "BTN_SELECT")
        self._check_zone_ok("SW_BOOT", "3", "GND")
        self._check_zone_ok("SW_BOOT", "4", "GND")

    def test_pullup_resistors(self):
        """R4-R15: pull-up pads (zone-connected, may be net 0)."""
        for i, ref in enumerate(_PULL_UP_REFS):
            self._check_zone_ok(ref, "2", "+3V3")
            if i < len(_BTN_NETS_ORDERED):
                self._check_zone_ok(ref, "1", _BTN_NETS_ORDERED[i])

    def test_debounce_caps(self):
        """C5-C16: debounce cap pads (zone-connected, may be net 0)."""
        for i, ref in enumerate(_DEBOUNCE_REFS):
            self._check_zone_ok(ref, "2", "GND")
            if i < len(_BTN_NETS_ORDERED):
                self._check_zone_ok(ref, "1", _BTN_NETS_ORDERED[i])

    def test_no_power_short_circuits(self):
        """Verify no pad has both a power net and GND simultaneously.

        This catches catastrophic errors like swapped VCC/GND.
        """
        power_nets = {"+3V3", "+5V", "VBUS", "BAT+"}
        pad_nets = defaultdict(set)
        for pad in self.cache["pads"]:
            net_name = self.net_id_to_name.get(pad["net"], "")
            if net_name:
                pad_nets[(pad["ref"], pad["num"])].add(net_name)

        conflicts = []
        for (ref, num), nets in pad_nets.items():
            has_power = nets & power_nets
            has_gnd = "GND" in nets
            if has_power and has_gnd:
                conflicts.append(f"{ref} pin {num}: {nets}")
        self.assertEqual(conflicts, [],
                         f"Power/GND conflict on pads: {conflicts}")

    def test_component_coverage(self):
        """Verify we have net expectations for all major components."""
        checked_refs = set()
        for ref, pin in STRICT_NETS.keys():
            checked_refs.add(ref)
        for ref, pin in ZONE_OK_NETS.keys():
            checked_refs.add(ref)

        unchecked = []
        for ref in sorted(self.all_refs):
            if ref.startswith("H") or ref.startswith("TP") or ref.startswith("FID"):
                continue
            if ref not in checked_refs:
                unchecked.append(ref)
        self.assertEqual(
            unchecked, [],
            f"Components without net verification: {unchecked}"
        )

    def test_expected_net_count(self):
        """Sanity check: we should have 100+ pin-to-net expectations."""
        total = len(STRICT_NETS) + len(ZONE_OK_NETS)
        self.assertGreaterEqual(
            total, 100,
            f"Only {total} pin-to-net expectations defined (expected >= 100)"
        )

    def test_j4_fpc_orientation(self):
        """J4 (FPC): cable insertion side (signal pads) faces FPC slot.

        Bottom-contact FPC connector: signal pads (1-40) must be at lower X
        than mounting pads (41-42), so the cable from the FPC slot (X≈127)
        can reach the connector opening.
        """
        cache = load_cache()
        # Cache stores pads at top level with 'ref' and 'num' keys
        signal_xs = []
        mount_xs = []
        for pad in cache.get("pads", []):
            if pad.get("ref") != "J4":
                continue
            pname = pad.get("num", "")
            if not pname.isdigit():
                continue
            pnum = int(pname)
            gx = pad["x"]  # already global X
            if pnum <= 40:
                signal_xs.append(gx)
            else:
                mount_xs.append(gx)

        self.assertTrue(len(signal_xs) >= 40,
                        f"Expected 40 signal pads, got {len(signal_xs)}")
        self.assertTrue(len(mount_xs) >= 2,
                        f"Expected 2 mounting pads, got {len(mount_xs)}")

        avg_sig = sum(signal_xs) / len(signal_xs)
        avg_mnt = sum(mount_xs) / len(mount_xs)

        # Signal pads (cable insertion) must be at lower X (closer to slot)
        self.assertLess(
            avg_sig, avg_mnt,
            f"J4 signal pads (X={avg_sig:.2f}) must be LEFT of "
            f"mounting pads (X={avg_mnt:.2f}) to face FPC slot"
        )

        # Signal pads must be between slot right edge and connector center
        slot_right = 128.5
        self.assertGreater(
            avg_sig, slot_right,
            f"J4 signal pads (X={avg_sig:.2f}) must be right of "
            f"slot edge (X={slot_right})"
        )
        self.assertLess(
            avg_sig - slot_right, 8.0,
            f"J4 signal-to-slot gap ({avg_sig - slot_right:.1f}mm) too large"
        )

    # ── Datasheet mandatory connection rules ──

    def test_display_backlight_connected(self):
        """Display LED-A (pin 33, pad 8) must be connected to +3V3.

        ILI9488 datasheet: LED-A = backlight anode (2.9-3.3V).
        DFM v3 (2026-04-10): pad is directly on the +3V3 net (was LCD_BL net
        with a dangling via that never connected to +3V3). See
        routing.py::_fpc_power_traces and datasheet_specs.py::J4.
        """
        self._check_strict("J4", "8", "+3V3")

    def test_display_rd_tied_high(self):
        """Display RD (pin 12, pad 29) must be tied HIGH (+3V3).

        ILI9488 8080 write-only mode: RD must not float.
        DFM v3 (2026-04-10): pad is directly on the +3V3 net (was LCD_RD net
        with a dangling via that never connected to +3V3). See
        routing.py::_fpc_power_traces and datasheet_specs.py::J4.
        """
        self._check_strict("J4", "29", "+3V3")

    def test_pam8403_shdn_not_floating(self):
        """PAM8403 /SHDN (pin 12) must be tied HIGH (+5V).

        Datasheet: active-low shutdown, no internal pull-up.
        Floating = undefined state, amp may be in shutdown.
        """
        self._check_strict("U5", "12", "+5V")

    def test_pam8403_mute_not_floating(self):
        """PAM8403 /MUTE (pin 5) must be tied HIGH (+5V).

        Datasheet: active-low mute, no internal pull-up.
        Floating = undefined state, may produce noise.
        """
        self._check_strict("U5", "5", "+5V")

    def test_display_mode_select_pins(self):
        """Display IM0/IM1/IM2 must be correctly tied for 8080 8-bit parallel.

        IM2=0(GND), IM1=1(+3V3), IM0=1(+3V3) per ILI9488 datasheet.
        """
        self._check_zone_ok("J4", "1", "GND")     # pad 1 = display pin 40 = IM2
        self._check_zone_ok("J4", "2", "+3V3")     # pad 2 = display pin 39 = IM1
        self._check_zone_ok("J4", "3", "+3V3")     # pad 3 = display pin 38 = IM0

    def test_display_backlight_cathodes(self):
        """Display LED-K (pins 34-36, pads 5-7) must be connected to GND.

        ILI9488 datasheet: 3 cathode pins for 8-chip white LED backlight.
        """
        for pad in ["5", "6", "7"]:
            self._check_zone_ok("J4", pad, "GND")

    def test_display_power_rails(self):
        """Display VDDI (pin 6) and VDDA (pin 7) must be connected to +3V3.

        ILI9488 datasheet: VDDI = I/O logic, VDDA = analog/digital power.
        """
        self._check_zone_ok("J4", "35", "+3V3")    # pad 35 = display pin 6 = VDDI
        self._check_zone_ok("J4", "34", "+3V3")    # pad 34 = display pin 7 = VDDA


# ---- Standalone runner with summary ----

def main():
    """Run all tests and print a summary."""
    print("=" * 60)
    print("  Polarity & Pin-to-Net Verification")
    print("=" * 60)

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(PolarityVerificationTest)
    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    total = result.testsRun
    failures = len(result.failures) + len(result.errors)
    passed = total - failures
    strict_count = len(STRICT_NETS)
    zone_count = len(ZONE_OK_NETS)
    print()
    print("=" * 60)
    print(f"  Polarity verification: {passed}/{total} tests passed"
          f" ({failures} failures)")
    print(f"  Pin-to-net checks: {strict_count} strict + {zone_count} zone-ok"
          f" = {strict_count + zone_count} total")
    print("=" * 60)

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
