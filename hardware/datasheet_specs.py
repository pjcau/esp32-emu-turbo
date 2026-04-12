#!/usr/bin/env python3
"""Centralized datasheet pin-to-net specifications for all PCB components.

This is the SINGLE SOURCE OF TRUTH for expected pin connections.
Each component's pin mapping is derived from its manufacturer datasheet
in hardware/datasheets/.

Usage:
    from hardware.datasheet_specs import COMPONENT_SPECS
    spec = COMPONENT_SPECS["J1"]
    for pin, info in spec["pins"].items():
        print(f"Pin {pin}: {info['net']} ({info['function']})")
"""

# ---------------------------------------------------------------------------
# Net matching helpers
# ---------------------------------------------------------------------------

# Exact net name match
def _exact(net_name):
    """Pin must connect to exactly this net."""
    return {"match": "exact", "net": net_name}


def _any_of(*net_names):
    """Pin must connect to one of these nets (for pins with acceptable aliases)."""
    return {"match": "any_of", "nets": list(net_names)}


def _unconnected():
    """Pin is intentionally unconnected (net 0 / empty)."""
    return {"match": "unconnected"}


# ---------------------------------------------------------------------------
# Component Specifications
# ---------------------------------------------------------------------------

COMPONENT_SPECS = {

    # ======================================================================
    # J1 — USB-C 16-Pin Connector (C2765186)
    # Datasheet: J1_USB-C-16pin_C2765186.pdf, page 1
    # Pin Assignments table (TYPE-C 16PIN 2MD(073)):
    #   A1=GND, A4=VBUS, A5=CC1, A6=DP1, A7=DN1, A8=SBU1, A9=VBUS, A12=GND
    #   B1=GND, B4=VBUS, B5=CC2, B6=DP2, B7=DN2, B8=SBU2, B9=VBUS, B12=GND
    # JLCPCB footprint uses 12 signal pads + 4 shield pads (13, 14, 13, 14)
    # Our mapping: 1-12 SMD signal, 13/14 front shield THT, 13/14 rear THT (duplicate names)
    # R16 FIX (2026-04-12): pad SIZES corrected to match JLCPCB/EasyEDA
    # reference retrieved via easyeda2kicad — wide signal 0.55mm,
    # narrow signal 0.30mm, rear shield 1.2×1.8, NPTH drill 0.70mm.
    # Pin names changed to duplicate 13/14 to match JLCPCB/EasyEDA reference.
    # ======================================================================
    "J1": {
        "component": "USB-C 16-Pin Connector",
        "lcsc": "C2765186",
        "datasheet": "J1_USB-C-16pin_C2765186.pdf",
        "datasheet_page": 1,
        "pins": {
            "1":   {"net": _exact("GND"),      "function": "GND (A1/A12 merged)", "type": "smd"},
            "2":   {"net": _exact("VBUS"),     "function": "VBUS (A4/B4 merged)", "type": "smd"},
            "3":   {"net": _unconnected(),     "function": "DM_B (DN2) — no USB mux, OK unconnected", "type": "smd"},
            "4":   {"net": _exact("USB_CC1"),  "function": "CC1", "type": "smd"},
            "5":   {"net": _unconnected(),     "function": "DM_A (DN1) — no USB mux, OK unconnected", "type": "smd"},
            "6":   {"net": _exact("USB_D+"),   "function": "DP_A (DP1)", "type": "smd"},
            "7":   {"net": _exact("USB_D-"),   "function": "DP_B (DN1/DP2 — used as D-)", "type": "smd"},
            "8":   {"net": _unconnected(),     "function": "SBU — unused", "type": "smd"},
            "9":   {"net": _exact("VBUS"),     "function": "VBUS (A9/B9 merged)", "type": "smd"},
            "10":  {"net": _exact("USB_CC2"),  "function": "CC2", "type": "smd"},
            "11":  {"net": _exact("VBUS"),     "function": "VBUS (B4 merged)", "type": "smd"},
            "12":  {"net": _exact("GND"),      "function": "GND (B1/B12 merged)", "type": "smd"},
            "13":  {"net": _exact("GND"),      "function": "Shield (front left)", "type": "thru_hole", "min_drill": 0.5},
            "14":  {"net": _exact("GND"),      "function": "Shield (front right)", "type": "thru_hole", "min_drill": 0.5},
            # Rear shield pads also named "13"/"14" (duplicate names, same GND net).
            # datasheet_specs uses dict keys so only the last "13"/"14" entry survives;
            # both front and rear pads share the same net/type, so this is correct.
            # The verify_datasheet_nets script matches by name, and duplicate-name pads
            # in the PCB all get the same net assignment.
        },
    },

    # ======================================================================
    # U1 — ESP32-S3-WROOM-1-N16R8 (C2913202)
    # Datasheet: U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf, pages 10-12
    # Table 3: Pin Definition (41 pins)
    # Pin 1=GND, 2=3V3, 3=EN, 4=IO4, ... 40=GND, 41=EPAD(GND)
    # GPIO mapping from config.py (source of truth for firmware)
    # Pins 28-30 (IO35/IO36/IO37) used for Octal SPI PSRAM — not available
    # ======================================================================
    "U1": {
        "component": "ESP32-S3-WROOM-1-N16R8",
        "lcsc": "C2913202",
        "datasheet": "U1_ESP32-S3-WROOM-1-N16R8_C2913202.pdf",
        "datasheet_page": 11,
        "pins": {
            # Pin 1 is GND — connected via copper zone fill, not direct pad net
            "1":  {"net": _any_of("GND", ""),   "function": "GND (zone-filled)", "type": "smd"},
            "2":  {"net": _exact("+3V3"),       "function": "3V3 power supply", "type": "smd"},
            # Pin 3 (EN) — connected via pull-up resistor trace, may not show in pad net
            "3":  {"net": _any_of("EN", ""),    "function": "EN (chip enable, via pull-up)", "type": "smd"},
            "4":  {"net": _exact("LCD_D0"),     "function": "GPIO4 — LCD data bus D0", "type": "smd"},
            "5":  {"net": _exact("LCD_D1"),     "function": "GPIO5 — LCD data bus D1", "type": "smd"},
            "6":  {"net": _exact("LCD_D2"),     "function": "GPIO6 — LCD data bus D2", "type": "smd"},
            "7":  {"net": _exact("LCD_D3"),     "function": "GPIO7 — LCD data bus D3", "type": "smd"},
            "8":  {"net": _exact("I2S_BCLK"),   "function": "GPIO15 — I2S bit clock (unused, PAM8403 is analog)", "type": "smd"},
            "9":  {"net": _exact("I2S_LRCK"),   "function": "GPIO16 — I2S L/R clock (unused, PAM8403 is analog)", "type": "smd"},
            "10": {"net": _exact("I2S_DOUT"),   "function": "GPIO17 — I2S data out", "type": "smd"},
            "11": {"net": _exact("BTN_START"),  "function": "GPIO18 — Start button", "type": "smd"},
            "12": {"net": _exact("LCD_D4"),     "function": "GPIO8 — LCD data bus D4", "type": "smd"},
            "13": {"net": _exact("USB_DM_MCU"), "function": "GPIO19 — USB D- (after 22Ω R23)", "type": "smd"},
            "14": {"net": _exact("USB_DP_MCU"), "function": "GPIO20 — USB D+ (after 22Ω R22)", "type": "smd"},
            "15": {"net": _exact("BTN_R"),      "function": "GPIO3 — R shoulder button", "type": "smd"},
            "16": {"net": _exact("LCD_WR"),     "function": "GPIO46 — LCD write strobe", "type": "smd"},
            "17": {"net": _exact("LCD_D5"),     "function": "GPIO9 — LCD data bus D5", "type": "smd"},
            "18": {"net": _exact("LCD_D6"),     "function": "GPIO10 — LCD data bus D6", "type": "smd"},
            "19": {"net": _exact("LCD_D7"),     "function": "GPIO11 — LCD data bus D7", "type": "smd"},
            "20": {"net": _exact("LCD_CS"),     "function": "GPIO12 — LCD chip select", "type": "smd"},
            "21": {"net": _exact("LCD_RST"),    "function": "GPIO13 — LCD reset", "type": "smd"},
            "22": {"net": _exact("LCD_DC"),     "function": "GPIO14 — LCD data/command", "type": "smd"},
            "23": {"net": _exact("BTN_Y"),      "function": "GPIO21 — Y button", "type": "smd"},
            "24": {"net": _exact("BTN_X"),      "function": "GPIO47 — X button", "type": "smd"},
            "25": {"net": _exact("BTN_B"),      "function": "GPIO48 — B button", "type": "smd"},
            "26": {"net": _exact("BTN_L"),      "function": "GPIO45 — L shoulder button", "type": "smd"},
            "27": {"net": _exact("BTN_SELECT"), "function": "GPIO0 — Select button (also BOOT)", "type": "smd"},
            "28": {"net": _unconnected(),       "function": "GPIO35 — Octal SPI PSRAM (N/A)", "type": "smd"},
            "29": {"net": _unconnected(),       "function": "GPIO36 — Octal SPI PSRAM (N/A)", "type": "smd"},
            "30": {"net": _unconnected(),       "function": "GPIO37 — Octal SPI PSRAM (N/A)", "type": "smd"},
            "31": {"net": _exact("SD_CLK"),     "function": "GPIO38 — SD card clock", "type": "smd"},
            "32": {"net": _exact("SD_CS"),      "function": "GPIO39 — SD card chip select", "type": "smd"},
            "33": {"net": _exact("BTN_UP"),     "function": "GPIO40 — D-pad up", "type": "smd"},
            "34": {"net": _exact("BTN_DOWN"),   "function": "GPIO41 — D-pad down", "type": "smd"},
            "35": {"net": _exact("BTN_LEFT"),   "function": "GPIO42 — D-pad left", "type": "smd"},
            "36": {"net": _exact("SD_MOSI"),    "function": "GPIO44 (U0RXD) — SD MOSI", "type": "smd"},
            "37": {"net": _exact("SD_MISO"),    "function": "GPIO43 (U0TXD) — SD MISO", "type": "smd"},
            "38": {"net": _exact("BTN_RIGHT"),  "function": "GPIO1 — D-pad right", "type": "smd"},
            "39": {"net": _exact("BTN_A"),      "function": "GPIO2 — A button", "type": "smd"},
            # Pin 40 is GND — connected via copper zone fill, not direct pad net
            "40": {"net": _any_of("GND", ""),   "function": "GND (bottom pad row, zone-filled)", "type": "smd"},
            "41": {"net": _exact("GND"),        "function": "EPAD — exposed ground pad", "type": "smd"},
        },
    },

    # ======================================================================
    # U2 — IP5306 Power Bank SoC (C181692)
    # Datasheet: U2_IP5306_C181692.pdf, page 2
    # eSOP8: Pin 1=VIN, 2=LED1, 3=LED2, 4=LED3, 5=KEY, 6=BAT, 7=SW, 8=VOUT
    # PowerPAD = GND
    # Note: In our circuit VIN receives USB VBUS, VOUT provides +5V boost
    # ======================================================================
    "U2": {
        "component": "IP5306 Power Bank SoC",
        "lcsc": "C181692",
        "datasheet": "U2_IP5306_C181692.pdf",
        "datasheet_page": 2,
        "pins": {
            "1":  {"net": _exact("VBUS"),        "function": "VIN — charger 5V input (USB VBUS)", "type": "smd"},
            "2":  {"net": _unconnected(),        "function": "LED1 — battery indicator 1 (unused)", "type": "smd"},
            "3":  {"net": _unconnected(),        "function": "LED2 — battery indicator 2 (unused)", "type": "smd"},
            "4":  {"net": _unconnected(),        "function": "LED3 — battery indicator 3 (unused)", "type": "smd"},
            "5":  {"net": _exact("IP5306_KEY"),  "function": "KEY — ON/OFF key input", "type": "smd"},
            "6":  {"net": _exact("BAT+"),        "function": "BAT — battery voltage sense", "type": "smd"},
            "7":  {"net": _exact("LX"),          "function": "SW — DCDC switch node (inductor)", "type": "smd"},
            "8":  {"net": _exact("+5V"),         "function": "VOUT — DCDC 5V output", "type": "smd"},
            "EP": {"net": _exact("GND"),         "function": "PowerPAD — ground", "type": "smd"},
        },
    },

    # ======================================================================
    # U3 — AMS1117-3.3 LDO Regulator (C6186)
    # Datasheet: U3_AMS1117-3.3_C6186.pdf, page 1
    # SOT-223: Pin 1=GND/ADJ, 2=VOUT, 3=VIN, Tab(4)=VOUT
    # ======================================================================
    "U3": {
        "component": "AMS1117-3.3 LDO Regulator",
        "lcsc": "C6186",
        "datasheet": "U3_AMS1117-3.3_C6186.pdf",
        "datasheet_page": 1,
        "pins": {
            "1": {"net": _exact("GND"),   "function": "GND/Adjust", "type": "smd"},
            "2": {"net": _any_of("", "+3V3"),  "function": "VOUT tab — +3V3 trace (intentional, tab=VOUT)", "type": "smd"},
            "3": {"net": _exact("+5V"),   "function": "VIN (5V input)", "type": "smd"},
            "4": {"net": _exact("+3V3"),  "function": "Tab/heatsink — VOUT (3.3V)", "type": "smd"},
        },
    },

    # ======================================================================
    # U5 — PAM8403 Class-D Audio Amplifier (C5122557)
    # Datasheet: U5_PAM8403_C5122557.pdf, pages 2-3
    # SOP-16 narrow (3.9mm body):
    #   1=OUTL+, 2=PGND, 3=OUTL-, 4=PVDD, 5=MUTE, 6=VDD,
    #   7=INL, 8=VREF, 9=NC, 10=INR, 11=GND, 12=SHDN,
    #   13=PVDD, 14=OUTR-, 15=PGND, 16=OUTR+
    # We use mono (RIGHT channel wired to speaker): INL=INR=I2S_DOUT
    # (both tied to the single PDM data line through C22 DC-block).
    # OUTR+ → SPK+, OUTR- → SPK- (BTL output on the right-channel pair).
    # OUTL+/OUTL- are left floating — PAM8403 datasheet app note allows
    # unused BTL outputs to float; both amplifiers are still biased and
    # consume ~2mA quiescent each (negligible on a handheld battery).
    # SHDN tied high (+5V) for always-on; MUTE tied high (+5V) for unmuted.
    # ======================================================================
    "U5": {
        "component": "PAM8403 Class-D Audio Amplifier",
        "lcsc": "C5122557",
        "datasheet": "U5_PAM8403_C5122557.pdf",
        "datasheet_page": 2,
        "pins": {
            "1":  {"net": _unconnected(),       "function": "OUTL+ — left channel + (floating, only right channel wired to speaker)", "type": "smd"},
            "2":  {"net": _exact("GND"),        "function": "PGND — power ground", "type": "smd"},
            "3":  {"net": _unconnected(),       "function": "OUTL- — left channel - (floating, only right channel wired to speaker)", "type": "smd"},
            "4":  {"net": _exact("+5V"),        "function": "PVDD — power supply", "type": "smd"},
            "5":  {"net": _exact("+5V"),        "function": "MUTE — active low, tied high (unmuted)", "type": "smd"},
            "6":  {"net": _exact("+5V"),        "function": "VDD — analog power supply", "type": "smd"},
            "7":  {"net": _exact("I2S_DOUT"),   "function": "INL — left audio input", "type": "smd"},
            "8":  {"net": _any_of("PAM_VREF", ""),  "function": "VREF — internal reference (bypass cap C21 to GND)", "type": "smd"},
            "9":  {"net": _unconnected(),       "function": "NC — no connection", "type": "smd"},
            "10": {"net": _exact("I2S_DOUT"),   "function": "INR — right audio input (tied to INL)", "type": "smd"},
            "11": {"net": _exact("GND"),        "function": "GND — analog ground", "type": "smd"},
            "12": {"net": _exact("+5V"),        "function": "SHDN — active low shutdown, tied high", "type": "smd"},
            "13": {"net": _exact("+5V"),        "function": "PVDD — power supply", "type": "smd"},
            "14": {"net": _exact("SPK-"),       "function": "OUTR- — right channel - (speaker -)", "type": "smd"},
            "15": {"net": _exact("GND"),        "function": "PGND — power ground", "type": "smd"},
            "16": {"net": _exact("SPK+"),       "function": "OUTR+ — right channel + (speaker +)", "type": "smd"},
        },
    },

    # ======================================================================
    # U6 — TF-01A MicroSD Card Slot (C91145)
    # Datasheet: U6_TF-01A_MicroSD_C91145.pdf, page 1
    # Standard MicroSD pinout:
    #   1=DAT2(NC), 2=CS, 3=MOSI, 4=VDD, 5=CLK, 6=GND, 7=MISO, 8=DAT1(NC)
    #   9=CD(card detect, NC), 10-13=shell GND, NPTH positioning holes
    # ======================================================================
    "U6": {
        "component": "TF-01A MicroSD Card Slot",
        "lcsc": "C91145",
        "datasheet": "U6_TF-01A_MicroSD_C91145.pdf",
        "datasheet_page": 1,
        "pins": {
            "1":  {"net": _unconnected(),      "function": "DAT2 — unused in SPI mode", "type": "smd"},
            "2":  {"net": _exact("SD_CS"),     "function": "CS — chip select", "type": "smd"},
            "3":  {"net": _exact("SD_MOSI"),   "function": "CMD/MOSI — data in", "type": "smd"},
            "4":  {"net": _exact("+3V3"),      "function": "VDD — 3.3V supply", "type": "smd"},
            "5":  {"net": _exact("SD_CLK"),    "function": "CLK — SPI clock", "type": "smd"},
            "6":  {"net": _exact("GND"),       "function": "VSS — ground", "type": "smd"},
            "7":  {"net": _exact("SD_MISO"),   "function": "DAT0/MISO — data out", "type": "smd"},
            # Pins 8 (DAT1) and 9 (DAT2) are unused in SPI mode — the SD card
            # tri-states them when CMD1 selects SPI mode. The PCB routes SD_MISO
            # (x=145.6) and BTN_R (x=146.85) vertical tracks through the DAT1/DAT2
            # pad positions; _PAD_NETS in routing.py assigns same-net to silence
            # the trace-through-pad fab short. See commit 9709bea → 775e9fd → eff85e6.
            "8":  {"net": _any_of("", "SD_MISO"), "function": "DAT1 — unused in SPI, shares copper with SD_MISO trace", "type": "smd"},
            "9":  {"net": _any_of("", "BTN_R"),   "function": "DAT2 — unused in SPI, shares copper with BTN_R shoulder-button trace", "type": "smd"},
            "10": {"net": _exact("GND"),       "function": "Shell/GND", "type": "smd"},
            "11": {"net": _unconnected(),      "function": "Shell (not connected)", "type": "smd"},
            "12": {"net": _exact("GND"),       "function": "Shell/GND", "type": "smd"},
            "13": {"net": _unconnected(),      "function": "Shell (not connected)", "type": "smd"},
        },
    },

    # ======================================================================
    # J3 — JST PH 2-Pin Battery Connector (C295747)
    # Pin 1=BAT+, Pin 2=GND, Pins 3/4=mechanical reinforcement tabs (no net)
    # R15-FIX (2026-04-12): added pins 3, 4 for JLCDFM "Pin without pad" fix
    # ======================================================================
    "J3": {
        "component": "JST PH 2-Pin SMD Battery Connector",
        "lcsc": "C295747",
        "datasheet": "J3_JST-PH-2P-SMD_C295747.pdf",
        "datasheet_page": 1,
        "pins": {
            "1": {"net": _exact("BAT_IN"), "function": "Battery positive (via Q1 P-MOSFET RPP to BAT+)", "type": "smd"},
            "2": {"net": _exact("GND"),    "function": "Battery ground", "type": "smd"},
            "3": {"net": _unconnected(),   "function": "Mechanical reinforcement tab (left)", "type": "smd"},
            "4": {"net": _unconnected(),   "function": "Mechanical reinforcement tab (right)", "type": "smd"},
        },
    },

    # ======================================================================
    # J4 — FPC 40-Pin 0.5mm Connector (C2856812)
    # For ILI9488 3.95" 320x480 8-bit 8080 parallel display
    # Datasheet: J4_FPC-40pin-0.5mm_C2856812.pdf
    #
    # ⚠  IMPORTANT — this table uses the CONNECTOR-PAD numbering, NOT the
    #    panel-side pin numbering. Because the display sits above the PCB
    #    in landscape orientation and the FPC ribbon passes straight
    #    through a slot to J4 on the back side (no twist), the mapping is:
    #
    #        connector_pad = 41 - panel_pin
    #
    #    So what the panel datasheet calls "pin 9" (CS) lands on J4 pad 32
    #    here. For the panel-side pinout, see:
    #      - website/docs/design/components.md (authoritative table)
    #      - scripts/generate_schematics/sheets/display.py (docstring)
    #      - website/docs/design/schematics.md §"FPC slot & pin reversal"
    #
    #    R4-CRIT-1 was falsely raised against this discrepancy — do NOT
    #    "fix" this file to match the panel-side numbering; both are
    #    correct views of the same electrical design. The sync verifier
    #    (scripts/verify_schematic_pcb_sync.py) only checks the NET SET
    #    on each connector, which is identical under the reversal.
    #
    # CONNECTOR-side pad mapping (= panel-side pinout reversed via 41-N):
    #   1=GND (panel 40=IM2),   2=VCC+3V3 (panel 39=IM1),
    #   3=VCC+3V3 (panel 38=IM0),   4-7=GND (panel 34-37),
    #   8=LED_A/LCD_BL (panel 33),   9-16=NC (panel 25-32 DB8-DB15),
    #   17-24=DB7..DB0 (panel 24-17, LCD_D7..LCD_D0 reversed),
    #   25=GND (panel 16),   26=LCD_RST (panel 15),
    #   27-28=NC (panel 13-14 SDI/SDO),
    #   29=LCD_RD (panel 12, tied +3V3),
    #   30=LCD_WR (panel 11),   31=LCD_DC (panel 10),
    #   32=LCD_CS (panel 9),   33=NC (panel 8 TE),
    #   34=+3V3 (panel 7 VDDA),   35=+3V3 (panel 6 VDDI),
    #   36=GND (panel 5),   37-40=NC (panel 1-4 touch XL/YU/XR/YD)
    #
    # Pins 41-42 are shell/anchor pads on the FPC connector body.
    # ======================================================================
    "J4": {
        "component": "FPC 40-Pin 0.5mm Connector",
        "lcsc": "C2856812",
        "datasheet": "J4_FPC-40pin-0.5mm_C2856812.pdf",
        "datasheet_page": 1,
        "pins": {
            "1":  {"net": _exact("GND"),      "function": "GND", "type": "smd"},
            "2":  {"net": _exact("+3V3"),     "function": "VCC (3.3V)", "type": "smd"},
            "3":  {"net": _exact("+3V3"),     "function": "VCC (3.3V)", "type": "smd"},
            "4":  {"net": _exact("GND"),      "function": "GND", "type": "smd"},
            "5":  {"net": _exact("GND"),      "function": "GND", "type": "smd"},
            "6":  {"net": _exact("GND"),      "function": "GND", "type": "smd"},
            "7":  {"net": _exact("GND"),      "function": "GND", "type": "smd"},
            # Hard-tied to +3V3 (always-on backlight, no GPIO control). The "LCD_BL"
            # label is retained in firmware/docs as the logical identifier but the
            # PCB net is +3V3 — see routing.py::_fpc_power_traces DFM v3 fix.
            "8":  {"net": _any_of("LCD_BL", "+3V3"),  "function": "LED_A — backlight anode, hard-tied to +3V3", "type": "smd"},
            "9":  {"net": _unconnected(),     "function": "NC (touch panel)", "type": "smd"},
            "10": {"net": _unconnected(),     "function": "NC (touch panel)", "type": "smd"},
            "11": {"net": _unconnected(),     "function": "NC (touch panel)", "type": "smd"},
            "12": {"net": _unconnected(),     "function": "NC (touch panel)", "type": "smd"},
            "13": {"net": _unconnected(),     "function": "NC (touch panel)", "type": "smd"},
            "14": {"net": _unconnected(),     "function": "NC (touch panel)", "type": "smd"},
            # J4 pads 15/16 map to panel pins 26/25 after 41-N reversal,
            # i.e. DB9/DB8 — unused upper data bits in 8-bit 8080 mode.
            # The IM0/IM1 mode-select pins are on panel pins 38/39 which
            # map to J4 pads 3/2 (both tied to +3V3 — see above).
            "15": {"net": _unconnected(),     "function": "NC (DB9 — unused in 8-bit 8080 mode)", "type": "smd"},
            "16": {"net": _unconnected(),     "function": "NC (DB8 — unused in 8-bit 8080 mode)", "type": "smd"},
            "17": {"net": _exact("LCD_D7"),   "function": "DB7 — LCD data bit 7", "type": "smd"},
            "18": {"net": _exact("LCD_D6"),   "function": "DB6 — LCD data bit 6", "type": "smd"},
            "19": {"net": _exact("LCD_D5"),   "function": "DB5 — LCD data bit 5", "type": "smd"},
            "20": {"net": _exact("LCD_D4"),   "function": "DB4 — LCD data bit 4", "type": "smd"},
            "21": {"net": _exact("LCD_D3"),   "function": "DB3 — LCD data bit 3", "type": "smd"},
            "22": {"net": _exact("LCD_D2"),   "function": "DB2 — LCD data bit 2", "type": "smd"},
            "23": {"net": _exact("LCD_D1"),   "function": "DB1 — LCD data bit 1", "type": "smd"},
            "24": {"net": _exact("LCD_D0"),   "function": "DB0 — LCD data bit 0", "type": "smd"},
            "25": {"net": _exact("GND"),      "function": "GND", "type": "smd"},
            "26": {"net": _exact("LCD_RST"),  "function": "RST — LCD reset", "type": "smd"},
            "27": {"net": _unconnected(),     "function": "NC", "type": "smd"},
            "28": {"net": _unconnected(),     "function": "NC", "type": "smd"},
            # Hard-tied to +3V3 (read strobe disabled — display is write-only 8080).
            # The "LCD_RD" label is retained in firmware/docs as the logical identifier
            # but the PCB net is +3V3 — see routing.py::_fpc_power_traces DFM v3 fix.
            "29": {"net": _any_of("LCD_RD", "+3V3"),  "function": "RD — LCD read strobe, hard-tied to +3V3", "type": "smd"},
            "30": {"net": _exact("LCD_WR"),   "function": "WR — LCD write strobe", "type": "smd"},
            "31": {"net": _exact("LCD_DC"),   "function": "DC — data/command select", "type": "smd"},
            "32": {"net": _exact("LCD_CS"),   "function": "CS — LCD chip select", "type": "smd"},
            "33": {"net": _unconnected(),     "function": "NC (TE tearing effect)", "type": "smd"},
            "34": {"net": _exact("+3V3"),     "function": "VCC (3.3V)", "type": "smd"},
            "35": {"net": _exact("+3V3"),     "function": "VCC (3.3V)", "type": "smd"},
            "36": {"net": _exact("GND"),      "function": "GND", "type": "smd"},
            "37": {"net": _unconnected(),     "function": "NC", "type": "smd"},
            "38": {"net": _unconnected(),     "function": "NC", "type": "smd"},
            "39": {"net": _unconnected(),     "function": "NC", "type": "smd"},
            "40": {"net": _unconnected(),     "function": "NC", "type": "smd"},
            # Shell/anchor pads on FPC connector body
            "41": {"net": _unconnected(),     "function": "Shell/anchor (mechanical)", "type": "smd"},
            "42": {"net": _unconnected(),     "function": "Shell/anchor (mechanical)", "type": "smd"},
        },
    },

    # ======================================================================
    # SW_PWR — MSK12C02 Slide Switch (C431540)
    # Datasheet: SW_PWR_Slide-Switch_C431540.pdf, page 1
    # 3 signal pins + 2 shell NPTHs
    # Circuit diagram: pin 2 is common, connects to 1 or 3 based on position
    # In our design: pin 2 = BAT+ (battery), pin 1 or 3 = switched output
    # Shell pads (4a-4d) are mechanical anchors
    # ======================================================================
    "SW_PWR": {
        "component": "MSK12C02 Slide Switch",
        "lcsc": "C431540",
        "datasheet": "SW_PWR_Slide-Switch_C431540.pdf",
        "datasheet_page": 1,
        "pins": {
            "1":  {"net": _unconnected(),  "function": "Position 1 (OFF)", "type": "smd"},
            "2":  {"net": _exact("BAT+"),  "function": "Common — battery positive", "type": "smd"},
            "3":  {"net": _unconnected(),  "function": "Position 2 (ON)", "type": "smd"},
            # Shell/anchor pads 4a-4d are mechanical retention tabs soldered to the
            # switch body. The shell metal is internally isolated from the slide
            # signal terminals (1/2/3). Pads 4b and 4d (right-side) are crossed by
            # the BTN_SELECT vertical track at x=35.95 — _PAD_NETS in routing.py
            # assigns same-net to eliminate the fab short. Safe because the shell
            # is electrically floating inside the component.
            "4a": {"net": _unconnected(),                "function": "Shell/anchor (mechanical) — top-left", "type": "smd"},
            "4b": {"net": _any_of("", "BTN_SELECT"),     "function": "Shell/anchor (mechanical) — top-right, shares copper with BTN_SELECT trace", "type": "smd"},
            "4c": {"net": _unconnected(),                "function": "Shell/anchor (mechanical) — bottom-left", "type": "smd"},
            "4d": {"net": _any_of("", "BTN_SELECT"),     "function": "Shell/anchor (mechanical) — bottom-right, shares copper with BTN_SELECT trace", "type": "smd"},
        },
    },

    # ======================================================================
    # SW_RST — Tact Switch for Reset (C318884)
    # 4-pin tact switch: pins 1+2 shorted, pins 3+4 shorted
    # In our design: one side = EN (chip enable), other side = GND
    # Pressing pulls EN low -> reset
    # ======================================================================
    "SW_RST": {
        "component": "Tact Switch (Reset)",
        "lcsc": "C318884",
        "datasheet": "SW1-SW13_Tact-Switch_C318884.pdf",
        "datasheet_page": 1,
        "pins": {
            "1": {"net": _exact("EN"),    "function": "EN — chip enable (internally shorted to pin 2)", "type": "smd"},
            "2": {"net": _unconnected(),  "function": "EN (shorted to pin 1, may not have net)", "type": "smd"},
            "3": {"net": _exact("GND"),   "function": "GND (internally shorted to pin 4)", "type": "smd"},
            "4": {"net": _exact("GND"),   "function": "GND (shorted to pin 3)", "type": "smd"},
        },
    },

    # ======================================================================
    # SW_BOOT — Tact Switch for Boot/Select (C318884)
    # Dual purpose: GPIO0/BTN_SELECT during runtime, BOOT during programming
    # ======================================================================
    "SW_BOOT": {
        "component": "Tact Switch (Boot/Select)",
        "lcsc": "C318884",
        "datasheet": "SW1-SW13_Tact-Switch_C318884.pdf",
        "datasheet_page": 1,
        "pins": {
            "1": {"net": _unconnected(),         "function": "BTN_SELECT (shorted to pin 2, may not have net)", "type": "smd"},
            "2": {"net": _exact("BTN_SELECT"),   "function": "BTN_SELECT / GPIO0 (BOOT)", "type": "smd"},
            "3": {"net": _exact("GND"),          "function": "GND (internally shorted to pin 4)", "type": "smd"},
            "4": {"net": _exact("GND"),          "function": "GND (shorted to pin 3)", "type": "smd"},
        },
    },
}

# ---------------------------------------------------------------------------
# Generate tact switch specs for SW1-SW13 (game buttons)
# Tact switch C318884: 4 pins, pads 1+2 shorted, pads 3+4 shorted
# Convention varies by placement orientation:
#   D-pad/shoulder (SW1-4,SW9-12): pin 2=signal, pin 3=GND
#   Face buttons (SW5-8): pin 1=signal, pin 4=GND
# SW13 = menu button
# ---------------------------------------------------------------------------

_BUTTON_MAP = {
    "SW1":  ("BTN_UP",     "D-pad Up"),
    "SW2":  ("BTN_DOWN",   "D-pad Down"),
    "SW3":  ("BTN_LEFT",   "D-pad Left"),
    "SW4":  ("BTN_RIGHT",  "D-pad Right"),
    "SW5":  ("BTN_A",      "A button"),
    "SW6":  ("BTN_B",      "B button"),
    "SW7":  ("BTN_X",      "X button"),
    "SW8":  ("BTN_Y",      "Y button"),
    "SW9":  ("BTN_START",  "Start button"),
    "SW10": ("BTN_SELECT", "Select button"),
    "SW11": ("BTN_L",      "L shoulder"),
    "SW12": ("BTN_R",      "R shoulder"),
    # SW13 = menu button — currently unrouted placeholder (no net assigned)
    # Excluded from auto-generation; defined manually below with relaxed rules
    # "SW13": ("BTN_MENU",   "Menu button"),
}

for _ref, (_net, _desc) in _BUTTON_MAP.items():
    # For tact switches, the signal can be on pin 1 or 2 (shorted pair),
    # and GND can be on pin 3 or 4 (shorted pair).
    # We check that at least one pin in each pair has the right net.
    # Tact switches have two shorted pairs: pins 1+2 and pins 3+4.
    # Depending on rotation, signal can be on either pair and GND on the other.
    # So we allow signal net or GND on ANY of the 4 pins, and require that
    # signal appears on at least one pin and GND on at least one pin.
    COMPONENT_SPECS[_ref] = {
        "component": f"Tact Switch ({_desc})",
        "lcsc": "C318884",
        "datasheet": "SW1-SW13_Tact-Switch_C318884.pdf",
        "datasheet_page": 1,
        "pins": {
            "1": {"net": _any_of(_net, "GND", ""),  "function": f"{_desc} signal or GND (shorted pair)", "type": "smd"},
            "2": {"net": _any_of(_net, "GND", ""),  "function": f"{_desc} signal or GND (shorted pair)", "type": "smd"},
            "3": {"net": _any_of(_net, "GND", ""),  "function": f"{_desc} signal or GND (shorted pair)", "type": "smd"},
            "4": {"net": _any_of(_net, "GND", ""),  "function": f"{_desc} signal or GND (shorted pair)", "type": "smd"},
        },
        # Extra validation: signal and GND must each appear on at least one pin
        "_require_signal_pair": {"pins": ["1", "2", "3", "4"], "net": _net},
        "_require_gnd_pair":    {"pins": ["1", "2", "3", "4"], "net": "GND"},
    }


# ---------------------------------------------------------------------------
# Passive components — spot-check critical connections only
# Full passive BOM checking is beyond pin-level verification.
# We verify the critical passives that have specific net requirements.
# ---------------------------------------------------------------------------

# SW13: Menu button — triggers START+SELECT combo via BAT54C diode D1
COMPONENT_SPECS["SW13"] = {
    "component": "Tact Switch (Menu button — START+SELECT combo via D1)",
    "lcsc": "C318884",
    "datasheet": "SW1-SW13_Tact-Switch_C318884.pdf",
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _any_of("MENU_K", ""),  "function": "Cathode junction (shorted with pad 2)", "type": "smd"},
        "2": {"net": _any_of("MENU_K", ""),  "function": "Cathode junction (D1 common cathode)", "type": "smd"},
        "3": {"net": _any_of("GND", ""),     "function": "GND (when pressed, pulls cathode LOW)", "type": "smd"},
        "4": {"net": _any_of("GND", ""),     "function": "GND (shorted with pad 3)", "type": "smd"},
    },
}

# D1: BAT54C Dual Schottky Diode (menu combo — START+SELECT)
COMPONENT_SPECS["D1"] = {
    "component": "BAT54C Dual Schottky Diode",
    "lcsc": "C37704",
    "datasheet": "D1_BAT54C-SOT23_C37704.pdf",
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("BTN_START"),   "function": "Anode 1 — Start button signal", "type": "smd"},
        "2": {"net": _exact("BTN_SELECT"),  "function": "Anode 2 — Select button signal", "type": "smd"},
        "3": {"net": _exact("MENU_K"),      "function": "Common cathode — to SW13", "type": "smd"},
    },
}

# R1, R2: USB CC pull-down resistors (5.1k to GND)
COMPONENT_SPECS["R1"] = {
    "component": "5.1k CC1 Pull-Down Resistor",
    "lcsc": "C27834",
    "datasheet": "R1-R2_5.1k-0805_C27834.pdf",
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("USB_CC1"), "function": "CC1 signal", "type": "smd"},
        "2": {"net": _exact("GND"),     "function": "Ground", "type": "smd"},
    },
}

COMPONENT_SPECS["R2"] = {
    "component": "5.1k CC2 Pull-Down Resistor",
    "lcsc": "C27834",
    "datasheet": "R1-R2_5.1k-0805_C27834.pdf",
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("USB_CC2"), "function": "CC2 signal", "type": "smd"},
        "2": {"net": _exact("GND"),     "function": "Ground", "type": "smd"},
    },
}

# U4: USBLC6-2SC6 USB ESD TVS Diode (SOT-23-6)
COMPONENT_SPECS["U4"] = {
    "component": "USBLC6-2SC6 USB ESD TVS",
    "lcsc": "C7519",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("USB_D-"), "function": "I/O1 (D-)", "type": "smd"},
        "2": {"net": _exact("GND"),    "function": "Ground", "type": "smd"},
        "3": {"net": _exact("USB_D+"), "function": "I/O2 (D+)", "type": "smd"},
        "4": {"net": _exact("USB_D+"), "function": "I/O2 (D+)", "type": "smd"},
        "5": {"net": _exact("VBUS"),   "function": "VBUS reference", "type": "smd"},
        "6": {"net": _exact("USB_D-"), "function": "I/O1 (D-)", "type": "smd"},
    },
}

# R22, R23: USB 22Ω series resistors (0402)
COMPONENT_SPECS["R22"] = {
    "component": "22R USB D+ Series Resistor",
    "lcsc": "C25092",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("USB_DP_MCU"), "function": "ESP32 side (after resistor)", "type": "smd"},
        "2": {"net": _exact("USB_D+"),     "function": "Connector side (before resistor)", "type": "smd"},
    },
}

COMPONENT_SPECS["R23"] = {
    "component": "22R USB D- Series Resistor",
    "lcsc": "C25092",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("USB_DM_MCU"), "function": "ESP32 side (after resistor)", "type": "smd"},
        "2": {"net": _exact("USB_D-"),     "function": "Connector side (before resistor)", "type": "smd"},
    },
}

# L1: Inductor for IP5306 boost converter
COMPONENT_SPECS["L1"] = {
    "component": "1uH Power Inductor",
    "lcsc": "C280579",
    "datasheet": "L1_1uH-Inductor_C280579.pdf",
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("BAT+"), "function": "Battery side", "type": "smd"},
        "2": {"net": _exact("LX"),   "function": "SW/LX node (to IP5306 pin 7)", "type": "smd"},
    },
}

# SPK1: Speaker
COMPONENT_SPECS["SPK1"] = {
    "component": "28mm Speaker",
    "lcsc": None,
    "datasheet": None,
    "datasheet_page": None,
    "pins": {
        "1": {"net": _exact("SPK+"), "function": "Speaker positive", "type": "smd"},
        "2": {"net": _exact("SPK-"), "function": "Speaker negative", "type": "smd"},
    },
}

# LED1, LED2
COMPONENT_SPECS["LED1"] = {
    "component": "Red LED 0805",
    "lcsc": "C84256",
    "datasheet": "LED1_Red-LED-0805_C84256.pdf",
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("GND"),     "function": "Cathode — ground", "type": "smd"},
        "2": {"net": _exact("LED1_RA"), "function": "Anode — via resistor", "type": "smd"},
    },
}

COMPONENT_SPECS["LED2"] = {
    "component": "Green LED 0805",
    "lcsc": "C19171391",
    "datasheet": "LED2_Green-LED-0805_C19171391.pdf",
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("GND"),     "function": "Cathode — ground", "type": "smd"},
        "2": {"net": _exact("LED2_RA"), "function": "Anode — via resistor", "type": "smd"},
    },
}


# ======================================================================
# Q1 — SI2301CDS P-Channel MOSFET (C10487) — Reverse Polarity Protection
# SOT-23-3: Pin 1=Gate, Pin 2=Source (battery in), Pin 3=Drain (to IP5306)
# Gate pulled low via R24 (100K to GND) — MOSFET always ON when battery
# connected with correct polarity. Reverse polarity: body diode blocks.
# ======================================================================
COMPONENT_SPECS["Q1"] = {
    "component": "SI2301CDS P-Channel MOSFET",
    "lcsc": "C10487",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("RPP_GATE"), "function": "Gate — pulled to GND via R24 (always ON)", "type": "smd"},
        "2": {"net": _exact("BAT_IN"),   "function": "Source — battery connector side (J3 pin 1)", "type": "smd"},
        "3": {"net": _exact("BAT+"),     "function": "Drain — IP5306 BAT pin side", "type": "smd"},
    },
}

# R24: Q1 gate pull-down resistor (100K to GND)
COMPONENT_SPECS["R24"] = {
    "component": "100K Gate Pull-Down Resistor",
    "lcsc": "C149504",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("RPP_GATE"), "function": "Q1 gate connection", "type": "smd"},
        "2": {"net": _exact("GND"),      "function": "Ground (gate pull-down)", "type": "smd"},
    },
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def get_all_verified_refs():
    """Return sorted list of all component references that have specs."""
    return sorted(COMPONENT_SPECS.keys())


if __name__ == "__main__":
    refs = get_all_verified_refs()
    total_pins = sum(len(s["pins"]) for s in COMPONENT_SPECS.values())
    print(f"Datasheet specs: {len(refs)} components, {total_pins} pins defined")
    for r in refs:
        s = COMPONENT_SPECS[r]
        print(f"  {r:10s}  {s['component']:40s}  {len(s['pins'])} pins")
