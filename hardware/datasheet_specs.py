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
    #
    # R22 CORRECTION (2026-07-25): the land -> contact map below was wrong
    # for lands 3, 5, 8 and 9, and the errors were mutually consistent
    # enough to survive several reviews. Re-derived by reading the
    # datasheet itself rather than by reasoning about USB-C in general:
    # the "RECOMMENDED PCB LAYOUT (TOP VIEW)" on page 1 labels every one
    # of the 12 lands with the receptacle contact(s) it carries. Rendered
    # at 1800 dpi the labels sit directly over their lands and read, left
    # to right:
    #
    #   A1·B12 | A4·B9 | B8 | A5 | B7 | A6 | A7 | B6 | A8 | B5 | B4·A9 | B1·A12
    #    wide     wide   ..... eight narrow 0.30 mm lands .....   wide     wide
    #
    # which matches the drawing's own "0.60(4X)" / "0.30(8X)" land-width
    # callouts (4 wide, 8 narrow). Feeding those through the PIN
    # ASSIGNMENTS table on the same sheet gives the land map used here.
    # Cross-check: the resulting sequence is 180°-rotationally symmetric
    # (reversing it swaps every A contact for its B partner), exactly as a
    # USB-C receptacle must be — the old map was not symmetric, which is
    # what made it wrong.
    #
    # Two consequences, both already implemented in the PCB by
    # routing._usb_c_reversibility_traces():
    #   - land 9 is SBU1, NOT VBUS. It was on the VBUS net, which is why
    #     DRC kept demanding a VBUS connection to it. All four VBUS
    #     contacts (A4/B9/B4/A9) are already carried by the two wide
    #     lands 2 and 11, so nothing is lost by freeing land 9.
    #   - lands 5 (B7=DN2) and 8 (B6=DP2) are the flipped-orientation USB
    #     2.0 pair and previously had no net at all. USB Type-C r2.1 §4.2
    #     requires a device with no USB mux to tie A6-B6 and A7-B7 on the
    #     PCB; without that the board does not enumerate with the plug
    #     upside down. They are now shorted to lands 6 and 7.
    # ======================================================================
    "J1": {
        "component": "USB-C 16-Pin Connector",
        "lcsc": "C2765186",
        "datasheet": "J1_USB-C-16pin_C2765186.pdf",
        "datasheet_page": 1,
        "pins": {
            "1":   {"net": _exact("GND"),      "function": "A1+B12 — GND (merged land)", "type": "smd"},
            "2":   {"net": _exact("VBUS_IN"),  "function": "A4+B9 — VBUS_IN (merged land; F1 PTC fuse to VBUS, R3-HIGH-4 fix)", "type": "smd"},
            "3":   {"net": _unconnected(),     "function": "B8 — SBU2, unused (no alt-mode/audio accessory)", "type": "smd"},
            "4":   {"net": _exact("USB_CC1"),  "function": "A5 — CC1 (5.1k pull-down R1)", "type": "smd"},
            "5":   {"net": _exact("USB_D-"),   "function": "B7 — DN2, flipped-orientation D- (tied to A7 per USB-C r2.1 §4.2)", "type": "smd"},
            "6":   {"net": _exact("USB_D+"),   "function": "A6 — DP1, normal-orientation D+", "type": "smd"},
            "7":   {"net": _exact("USB_D-"),   "function": "A7 — DN1, normal-orientation D-", "type": "smd"},
            "8":   {"net": _exact("USB_D+"),   "function": "B6 — DP2, flipped-orientation D+ (tied to A6 per USB-C r2.1 §4.2)", "type": "smd"},
            "9":   {"net": _unconnected(),     "function": "A8 — SBU1, unused (no alt-mode/audio accessory)", "type": "smd"},
            "10":  {"net": _exact("USB_CC2"),  "function": "B5 — CC2 (5.1k pull-down R2)", "type": "smd"},
            "11":  {"net": _exact("VBUS_IN"),  "function": "B4+A9 — VBUS_IN (merged land; F1 PTC fuse to VBUS, R3-HIGH-4 fix)", "type": "smd"},
            "12":  {"net": _exact("GND"),      "function": "B1+A12 — GND (merged land)", "type": "smd"},
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
            # GPIO15/16: the I2S_BCLK/I2S_LRCK net reservation was retired
            # 2026-07-26 (R10-LOW-2) — audio is PDM TX, .clk = I2S_GPIO_UNUSED,
            # only DOUT is used. GPIO15 was then taken by the diagnostic
            # heartbeat LED (workstream H): unlike the retired I2S labels, it
            # is a real two-pin circuit, U1.8 -> R31 -> LED6 -> GND. GPIO16
            # stays unconnected and free for v2 (ADC2).
            "8":  {"net": _exact("LED_HB"),     "function": "GPIO15 — diagnostic heartbeat LED (R31/LED6)", "type": "smd"},
            "9":  {"net": _unconnected(),       "function": "GPIO16 — unused, free for v2 (I2S reservation retired)", "type": "smd"},
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
            "5":  {"net": _exact("IP5306_KEY"),  "function": "KEY — ON/OFF key input, active low with an internal pull-up (datasheet p.11 fig.4). Driven by the C33 wake cap; there is no button on this net (SW17 was specified and then dropped for want of a clearance-legal site)", "type": "smd"},
            "6":  {"net": _exact("BAT+"),        "function": "BAT — battery voltage sense", "type": "smd"},
            "7":  {"net": _exact("LX"),          "function": "SW — DCDC switch node (inductor)", "type": "smd"},
            "8":  {"net": _exact("+5V_VOUT"),    "function": "VOUT — DCDC 5V output, upstream of the Q2 high-side switch (SW16 respin)", "type": "smd"},
            "EP": {"net": _exact("GND"),         "function": "PowerPAD — ground", "type": "smd"},
        },
    },

    # ======================================================================
    # U3 — SY8089AAAC 2A Synchronous Buck Regulator (C78988)
    # Datasheet: U3_SY8089AAAC_C78988.pdf (AN_SY8089/A Rev 0.9A), page 2
    # SOT-23-5: Pin 1=EN, 2=GND, 3=LX, 4=IN, 5=FB
    # Replaces the AMS1117-3.3 LDO: 5V->3.3V at up to 2A with ~90% efficiency
    # instead of burning 1.7V x I_load as heat (0.85 W at 500 mA).
    # Vout = 0.6 * (1 + R25/R26) = 0.6 * (1 + 100k/22k) = 3.327 V.
    # EN is tied to the +5V rail (always on while the IP5306 boost runs);
    # EN abs-max is Vin + 0.6 V so the hard tie is within spec.
    # ======================================================================
    "U3": {
        "component": "SY8089AAAC 2A Synchronous Buck Regulator",
        "lcsc": "C78988",
        "datasheet": "U3_SY8089AAAC_C78988.pdf",
        "datasheet_page": 2,
        "pins": {
            "1": {"net": _exact("+5V"),      "function": "EN — enable, tied high to the input rail (do not float)", "type": "smd"},
            "2": {"net": _exact("GND"),      "function": "GND — ground return, two vias to the In1.Cu plane", "type": "smd"},
            "3": {"net": _exact("BUCK_LX"),  "function": "LX — switch node to L2 (2.2uH)", "type": "smd"},
            "4": {"net": _exact("+5V"),      "function": "IN — 5V input, decoupled by C1 (22uF MLCC)", "type": "smd"},
            "5": {"net": _exact("BUCK_FB"),  "function": "FB — feedback, R25/R26 divider tap + C29 feed-forward", "type": "smd"},
        },
    },

    # ======================================================================
    # L2 — 2.2uH output inductor for U3 (SWPA4030S2R2MT, C36409)
    # 2.2uH +/-20%, Isat 2.95 A, DCR 39 mOhm, 4.0 x 4.0 mm.
    # Datasheet rule (AN_SY8089/A page 8): Isat must exceed the peak
    # inductor current at full load, and DCR should stay below 50 mOhm.
    #   Ipk = Iout + (Vout*(1-Vout/Vin))/(2*Fsw*L)
    #       = 2.0 + (3.3*(1-3.3/5.5))/(2*1e6*2.2e-6) = 2.0 + 0.30 = 2.30 A
    #   2.95 A Isat > 2.30 A peak  ✓
    # ======================================================================
    "L2": {
        "component": "2.2uH 2.95A Power Inductor (buck output)",
        "lcsc": "C36409",
        "datasheet": "",
        "datasheet_page": 0,
        "pins": {
            "1": {"net": _exact("+3V3"),     "function": "Output side — +3V3 rail / C30", "type": "smd"},
            "2": {"net": _exact("BUCK_LX"),  "function": "Switch side — U3 pin 3 (LX)", "type": "smd"},
        },
    },

    # ======================================================================
    # U5 — PAM8403 Class-D Audio Amplifier (C5122557)
    # Datasheet: U5_PAM8403_C5122557.pdf, pages 2-3
    # SOP-16 narrow (3.9mm body):
    #   1=OUTL+, 2=PGND, 3=OUTL-, 4=PVDD, 5=MUTE, 6=VDD,
    #   7=INL, 8=VREF, 9=NC, 10=INR, 11=GND, 12=SHDN,
    #   13=PVDD, 14=OUTR-, 15=PGND, 16=OUTR+
    # We use mono (RIGHT channel wired to speaker): INL=INR=PAM_IN_AC
    # (both tied to the single PDM data line through the C22 DC-block).
    # C22 is a SERIES cap, so its two terminals are two distinct nets:
    #   ESP32 GPIO17 --I2S_DOUT--> C22.1 || C22.2 --PAM_IN_AC--> U5.7/U5.10
    # Do NOT label the PAM side "I2S_DOUT": that made DRC report a
    # permanent phantom "unconnected" on I2S_DOUT.
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
            "7":  {"net": _exact("PAM_IN_AC"),  "function": "INL — left audio input (AC-coupled through C22)", "type": "smd"},
            "8":  {"net": _any_of("PAM_VREF", ""),  "function": "VREF — internal reference (bypass cap C21 to GND)", "type": "smd"},
            "9":  {"net": _unconnected(),       "function": "NC — no connection", "type": "smd"},
            "10": {"net": _exact("PAM_IN_AC"),  "function": "INR — right audio input (tied to INL, AC-coupled through C22)", "type": "smd"},
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
    # Standard MicroSD pinout — eight CARD contacts plus the socket's own
    # card-detect switch. The datasheet's "PCB Layout (Pattern Side)" view
    # labels the row (1)(2)(3)(4)(5)(6)(7)(8) then **Cd**:
    #   1=DAT2(NC), 2=CS, 3=MOSI, 4=VDD, 5=CLK, 6=GND, 7=MISO, 8=DAT1(NC)
    #   9=CD (socket card-detect spring, NOT a card contact — see pin 9),
    #   10-13=shell GND, NPTH positioning holes
    #
    # DO NOT relabel pad 9 "DAT2" again. That mistake came from SanDisk's
    # pin tables, which are the FULL-SIZE SD tables (9 contacts, rows headed
    # "SD Card", "the host uses a dedicated 9-pin connector" — p.17 sec 3.1)
    # laid over this socket's 9 pads. On full-size SD, contact 9 IS DAT2; a
    # microSD card has eight contacts, so every name past 8 shifted onto a
    # contact that does not exist. See R31-HIGH-2 for the consequence.
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
            # Pin 8 (DAT1) is a card contact unused in SPI mode: the card
            # holds the extended DAT lines as inputs on power-up
            # (SDCARD_SanDisk-Industrial-microSD_2016.pdf p.17 table 3-1
            # note b) and contact 8 is RSV in SPI (table 3-2 p.18). The PCB
            # runs the SD_MISO vertical (x=145.6) through that pad and
            # _PAD_NETS assigns same-net so the overlap is not a fab short.
            #
            # Pin 9 is NOT a card contact and used to be declared as one.
            # A microSD card has eight contacts; the socket's ninth pad is
            # the card-detect spring, which mates with the grounded shell —
            # i.e. a switch to GND, not an idle data line. The old entry
            # carried pad 8's tri-state argument and a same-net BTN_R
            # assignment covering the BTN_R vertical that crossed it, which
            # put the R shoulder button on a switched ground. Fixed in
            # R31-HIGH-2: the BTN_R riser now detours east of the pad row
            # and pad 9 carries no net. See 9709bea → 775e9fd → eff85e6 →
            # R31-HIGH-2 for how the wrong identity survived three passes.
            "8":  {"net": _any_of("", "SD_MISO"), "function": "DAT1 — unused in SPI, shares copper with SD_MISO trace", "type": "smd"},
            "9":  {"net": _unconnected(),         "function": "CD/DET — card-detect spring contact (mates with grounded shell); polarity closed-on-insert vs closed-on-empty unverifiable from the mechanical-only datasheet, bench continuity check owed", "type": "smd"},
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
            # R25-HIGH-1 FIXED IN THE DESIGN 2026-07-31: LED-A is fed from
            # +5V through R27 (20R 1206) on the dedicated LED_BLA net —
            # the anode was hard-tied to +3V3 with no current-limiting
            # element on every board fabricated through v4.3.1 (8 parallel
            # white LEDs, Vf 2.9-3.3 V, across a measured 3.327 V rail:
            # 0.227 V of headroom and no defined operating point).
            # 20R sizing from the family class rating (6 LED / 90 mA,
            # Vf 3.2 V ± 0.3: (5.0-3.2)/0.090 ≈ 20R), datasheet
            # DISPLAY-FAMILY_E35RG73248LW6M250-R_FocusLCDs.pdf outline
            # note 7. Final value still owes ONE bench measurement on the
            # actual panel (drive LED-A at 3.2 V, read the current) —
            # known-issues.md RESPIN section keeps that record.
            "8":  {"net": _exact("LED_BLA"),  "function": "LED_A — backlight anode, +5V via R27 20R (defined ~90 mA)", "type": "smd"},
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
            "28": {"net": _exact("+3V3"),    "function": "SPI SDI (panel pin 13) — unused input, tied HIGH per the panel pin table: 'If not used, please fix this pin at VDDI or DGND level' (R28-HIGH-1 fix; floated on boards fabricated before 2026-07-26)", "type": "smd"},
            # Hard-tied to +3V3 (read strobe disabled — display is write-only 8080).
            # Was _any_of("LCD_RD", "+3V3"); the LCD_RD net declaration is gone
            # (primitives.NET_LIST ids 18/19 retired), so +3V3 is the only net
            # this pad can carry. Which panel pin it is stays in "function".
            "29": {"net": _exact("+3V3"),  "function": "RD — LCD read strobe, hard-tied to +3V3", "type": "smd"},
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
    # SW16 — MSK12C02 Slide Switch (C431540)
    # Datasheet: SW16_Slide-Switch_C431540.pdf, page 1
    # 3 signal pins + 2 shell NPTHs
    # Circuit diagram: pin 2 is common, connects to 1 or 3 based on position
    #
    # SW16 RESPIN (2026-08-03): pin 2 is the gate control node PWR_SW, not
    # a dead stub on BAT+. Slid toward pin 1 (east, board interior) the
    # common is shorted to GND, PWR_SW goes to 0 V and Q2 turns the whole
    # +5V load rail on. Slid the other way the common lands on pin 3,
    # which is deliberately left OPEN: the node is then defined by R34
    # (1 M to BAT+) alone, so the gate sits within ~0.1 V of the source
    # and Q2 is off. R34 sits on the COMMON node, not on the open throw —
    # electrically identical, since with the throw open the common IS the
    # only node R34 can reach, and it keeps the switch to ONE long net
    # across the board instead of two.
    # Shell pads (4a-4d) are mechanical anchors
    # ======================================================================
    "SW16": {
        "component": "MSK12C02 Slide Switch",
        "lcsc": "C431540",
        "datasheet": "SW16_Slide-Switch_C431540.pdf",
        "datasheet_page": 1,
        "pins": {
            "1":  {"net": _exact("GND"),     "function": "Throw ON — grounds the common, pulling PWR_SW low so Q2 conducts", "type": "smd"},
            "2":  {"net": _exact("PWR_SW"),  "function": "Common — Q2 gate control node (via R33)", "type": "smd"},
            "3":  {"net": _unconnected(),    "function": "Throw OFF — deliberately open; R34 alone then defines PWR_SW", "type": "smd"},
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
    # SW15 — Tact Switch for Reset (C318884)
    # 4-pin tact switch: pins 1+2 shorted, pins 3+4 shorted
    # In our design: one side = EN (chip enable), other side = GND
    # Pressing pulls EN low -> reset
    # ======================================================================
    "SW15": {
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
    # SW14 — Tact Switch for Boot/Select (C318884)
    # Dual purpose: GPIO0/BTN_SELECT during runtime, BOOT during programming
    # ======================================================================
    "SW14": {
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
    "component": "Red LED 0805 (C19171391 YLED0805R; BOM said green for months — the part and its datasheet are red)",
    "lcsc": "C19171391",
    "datasheet": "LED2_Red-LED-0805_C19171391.pdf",
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("GND"),     "function": "Cathode — ground", "type": "smd"},
        "2": {"net": _exact("LED2_RA"), "function": "Anode — via resistor", "type": "smd"},
    },
}


# ======================================================================
# LED3-LED6 + R28-R31 — diagnostic LED bank (workstream H,
# docs/diagnostic-leds-roadmap.md). Three passive rail indicators plus one
# firmware heartbeat, all on the TOP side so a photo of the powered board
# reports the power tree without a multimeter. All four LEDs are the SAME
# part as LED2 (C19171391) and therefore share its 180 deg CPL delta.
#
# Series resistors are sized for ~0.6-1.3 mA — visible indoors, negligible
# drain, and both values were already on the BOM:
#   R28/R29  5.1k (C27834) on 5 V rails -> (5.000-2.0)/5100 = 0.59 mA
#   R30/R31  1k   (C17513) on 3.3 V     -> (3.327-2.0)/1000 = 1.33 mA
# The bank is marked "bring-up diagnostic, DNP in production" in the BOM:
# ~3.7 mA of constant drain is fine on the bench, not in a battery handheld.
# ======================================================================
_DIAG_BANK = [
    ("R28", "LED3", "5.1k", "C27834", "VBUS",   "VBUS present, F1 fuse intact"),
    ("R29", "LED4", "5.1k", "C27834", "+5V",    "IP5306 boost alive"),
    ("R30", "LED5", "1k",   "C17513", "+3V3",   "buck alive, rail not shorted"),
    ("R31", "LED6", "1k",   "C17513", "LED_HB", "GPIO15 heartbeat / blink codes"),
]

for _r, _led, _val, _rlcsc, _rail, _why in _DIAG_BANK:
    COMPONENT_SPECS[_r] = {
        "component": f"{_val} 0805 diagnostic LED series resistor ({_why})",
        "lcsc": _rlcsc,
        "datasheet": None,
        "datasheet_page": 1,
        "pins": {
            "1": {"net": _exact(f"{_led}_RA"),
                  "function": f"{_led} anode side", "type": "smd"},
            "2": {"net": _exact(_rail),
                  "function": f"{_rail} rail tap", "type": "smd"},
        },
    }
    COMPONENT_SPECS[_led] = {
        "component": f"Red LED 0805 (C19171391 YLED0805R) — {_why}",
        "lcsc": "C19171391",
        "datasheet": "LED2_Red-LED-0805_C19171391.pdf",
        "datasheet_page": 1,
        "pins": {
            "1": {"net": _exact("GND"),
                  "function": "Cathode — ground", "type": "smd"},
            "2": {"net": _exact(f"{_led}_RA"),
                  "function": f"Anode — via {_r}", "type": "smd"},
        },
    }


# ======================================================================
# Q1 — SI2301CDS P-Channel MOSFET (C10487) — Reverse Polarity Protection
# SOT-23-3: Pin 1=Gate, Pin 2=Source (to IP5306), Pin 3=Drain (battery in)
# Gate pulled low via R24 (100K to GND).
#
# THE CELL IS ON THE DRAIN, AND THAT IS THE PROTECTION (R31-HIGH-1).
# A P-channel body diode conducts drain->source. Correct polarity: the
# diode forward-biases (the load pre-charges through it), then V_GS =
# -V_BAT enrichs the channel and the diode is shorted out by ~0.1 ohm.
# Reversed cell: the diode is reverse-biased AND V_GS is positive, so
# nothing conducts. Wired the other way round — cell on the source, which
# is what shipped through v4.5.0 — a reversed cell forward-biases the body
# diode and the protection does nothing at all. Correct polarity behaves
# identically in both wirings, which is why no working board revealed it.
# ======================================================================
COMPONENT_SPECS["Q1"] = {
    "component": "SI2301CDS P-Channel MOSFET",
    "lcsc": "C10487",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("RPP_GATE"), "function": "Gate — pulled to GND via R24 (always ON)", "type": "smd"},
        "2": {"net": _exact("BAT+"),     "function": "Source — protected side, IP5306 BAT pin", "type": "smd"},
        "3": {"net": _exact("BAT_IN"),   "function": "Drain — battery connector side (J3 pin 1); body diode blocks a reversed cell", "type": "smd"},
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


# ======================================================================
# SW16 RESPIN — high-side +5V load switch (Q2) and its control network
#
# The problem it fixes: SW16 was wired to nothing. Only its common pin
# was routed, as a dead stub on BAT+, so sliding it changed no copper.
# Putting the cell in series with the switch — the plan this replaces —
# would have broken charging in the OFF position AND still left the
# board running whenever USB was plugged in, because VBUS passes
# through to the loads. Switching the +5V rail instead satisfies all
# three required states: ON = powered, OFF = loads dead but USB still
# charges, no cell fitted = identical behaviour on USB.
#
# Q2 is the SAME part as Q1 (SI2301CDS, C10487) on purpose: no new BOM
# line, no new package family, and the SOT-23-3 CPL rotation is already
# proven by Q1 and D1.
#
# GATE ARITHMETIC (the numbers this design lives or dies on)
#
#   ON  — SW16 shorts PWR_SW to GND. The gate divides R32/R33 between
#         +5V_VOUT and ground: Vg = 5 x 1k/23k = 0.217 V, so
#         Vgs = -4.78 V. SI2301 characterises Rds(on) = 55 mohm at
#         Vgs = -4.5 V, so the part is driven past its spec point.
#
#   OFF — the throw is open, so the only path is R34 to BAT+:
#             +5V_VOUT --R32 22k-- G --R33 1k-- PWR_SW --R34 1M-- BAT+
#         3.7 V cell : I = 1.3/1.023M = 1.271 uA, Vg = 4.972, Vgs = -0.028 V
#         4.2 V cell : I = 0.8/1.023M = 0.782 uA, Vg = 4.983, Vgs = -0.017 V
#         no cell    : I = 5.0/1.023M = 4.888 uA, Vg = 4.892, Vgs = -0.108 V
#         SI2301's Vgs(th) minimum magnitude is 0.45 V, so even the
#         no-cell case has 4.2x of margin.
#
#         R32 IS 22k AND NOT 100k FOR EXACTLY THAT CASE, and this is the
#         one number in the network that was got wrong first. The OFF
#         state is a divider, Vgs = -5 x R32/(R32+R33+R34), so the gate
#         offset is set by the RATIO. At the obvious 100k/10k/1M the
#         no-cell arithmetic gives Vgs = -0.455 V — sitting ON the
#         threshold minimum, where the part is specified to pass 250 uA.
#         That is the "undefined level" failure and it appears only in
#         the no-battery-plus-USB state, which is the state a bench
#         operator uses most.
#         The first fix was to raise R34 to 4.7M. It works arithmetically
#         and it was wrong for the board: 4.7M 0805 is not a JLCPCB Basic
#         part, so it would have added an extended-part fee and a feeder
#         to fix a ratio. Shrinking R32 instead fixes the same ratio with
#         parts already on this BOM (22k = C17560 = R26, 1k = C17513 =
#         the LED series resistors) and keeps R34 on the Basic 1M.
#         It is also better electrically twice over: a 23k gate network
#         is far harder to disturb than a 110k one, and the ON-state
#         divider now sits at Vgs = -4.78 V instead of -4.55 V.
#
#   SOFT START — tau_on = (R32||R33) x C32 = 957 ohm x 1uF = 957 us.
#         The rail ramps over roughly 1.5 ms, so the inrush into the
#         ~50 uF of load-side bulk (C1 + C19 + the PAM decoupling) is
#         C dV/dt = 50u x 5/1.5m = 167 mA rather than the several amps
#         a hard switch would draw. Energy deposited in Q2 during the
#         ramp is 1/2 C V^2 = 625 uJ, spread over 1.5 ms.
#         C32 is 1uF and not 100nF because the gate network shrank: at
#         957 ohm a 100nF cap gives tau = 96 us, and a 96 us ramp puts
#         1.7 A through Q2. The time constant is the specification here,
#         not the capacitor value.
#         tau_off = (R32 || (R33+R34)) x C32 = 21.5 ms; Q2 is fully off
#         about 52 ms after the slider moves.
#
#   QUIESCENT — 217 uA through R32/R33 while ON. R34 carries BAT+/1M,
#         which is ~3.7 uA while ON (the gate node is grounded then) and
#         ~1.3 uA in the OFF state, where the whole 23k+1M chain is in
#         series. The ON figure is 0.5 % of the 45 mA the IP5306 already
#         needs to see to stay out of light-load shutdown, so it changes
#         nothing that matters; against a 5000 mAh cell 221 uA is
#         5.3 mAh/day, about 0.11 % per day.
#
#   THERMAL — Rds(on) 55 mohm at 25 C, ~77 mohm hot. At the board's
#         worst-case simultaneous +5V budget of 2.15 A that is 0.356 W;
#         a SOT-23 at ~200 C/W reaches roughly 96 C junction against a
#         150 C limit. At the realistic continuous load (~0.7 A) it is
#         29 mW and a 6 C rise. Drop across Q2: 166 mV at 2.15 A,
#         42 mV at 0.7 A — the buck keeps far more than its dropout.
#
# WAKE NETWORK (C33, and why it is not optional)
#   The IP5306 boost shuts down after 32 s below 45 mA and restarts only
#   on a KEY press or a USB insertion (R30-MED-3). With SW16 OFF the
#   load behind Q2 is ~0.1 mA, so the boost WILL latch off every single
#   time. Flipping back to ON must therefore generate a KEY press by
#   itself. KEY is active-low with an internal pull-up and the chip
#   stays alive from the cell while the boost is off (datasheet p.11
#   fig.4), so a capacitor is enough: C33 couples the PWR_SW step
#   (~4.9 V, or ~3.7 V once the boost has latched off, down to 0 V)
#   into KEY as a low pulse, and recharges through R34 afterwards.
#   The pulse width is tau against the IP5306's UNDOCUMENTED internal
#   pull-up, so 1 uF is a starting value marked BENCH-VALIDATE. There is
#   no button on the net to fall back on: SW17 was specified as the
#   datasheet-blessed manual wake and then dropped, because no site
#   within reach of IP5306_KEY clears the copper the respin itself
#   added. The tuning point is therefore C33's own pads — lift the cap
#   and tack a wire to a momentary button, which reaches KEY and GND
#   directly. This is the one respin value that must be settled on the
#   bench before the design can be called finished.
#
# R16 IS DELETED. It was a 100k pull-up from KEY to +5V — off-datasheet
# to begin with (the reference schematic has a button to GND and no
# external pull-up). On the new LOAD-side +5V it would invert into a
# 100k pull-DOWN the moment the switch is OFF, holding KEY asserted;
# and re-referencing it to +5V_VOUT or BAT+ would only parallel the
# internal pull-up and SHORTEN the wake pulse, which is the one
# direction the design cannot afford.
# ======================================================================
COMPONENT_SPECS["Q2"] = {
    "component": "SI2301CDS P-Channel MOSFET (+5V high-side load switch)",
    "lcsc": "C10487",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("PWR_SW_GATE"), "function": "Gate — R32 22k pull-up to source (default OFF), R33 1k to the switch node", "type": "smd"},
        "2": {"net": _exact("+5V_VOUT"),    "function": "Source — IP5306 VOUT side (always live while the boost runs)", "type": "smd"},
        "3": {"net": _exact("+5V"),         "function": "Drain — load side; the body diode points loads->VOUT so it blocks in OFF", "type": "smd"},
    },
}

COMPONENT_SPECS["R32"] = {
    "component": "22K Q2 gate pull-up (default OFF)",
    "lcsc": "C17560",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("PWR_SW_GATE"), "function": "Q2 gate", "type": "smd"},
        "2": {"net": _exact("+5V_VOUT"),    "function": "Q2 source — pull-up must return to the SOURCE, not to the load rail", "type": "smd"},
    },
}

COMPONENT_SPECS["R33"] = {
    "component": "1K Q2 gate series resistor (soft-start slope)",
    "lcsc": "C17513",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("PWR_SW_GATE"), "function": "Q2 gate", "type": "smd"},
        "2": {"net": _exact("PWR_SW"),      "function": "Switch node (SW16 common)", "type": "smd"},
    },
}

COMPONENT_SPECS["C32"] = {
    "component": "1uF Q2 gate-source capacitor (inrush limiter)",
    "lcsc": "C28323",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("PWR_SW_GATE"), "function": "Q2 gate", "type": "smd"},
        "2": {"net": _exact("+5V_VOUT"),    "function": "Q2 source", "type": "smd"},
    },
}

COMPONENT_SPECS["R34"] = {
    "component": "1M pull to BAT+ (defines the node with the throw open)",
    "lcsc": "C17514",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("PWR_SW"), "function": "Switch node", "type": "smd"},
        "2": {"net": _exact("BAT+"),   "function": "Cell side — present whenever a cell is fitted, which is what keeps C33 charged", "type": "smd"},
    },
}

COMPONENT_SPECS["C33"] = {
    "component": "1uF IP5306 KEY wake capacitor (BENCH-VALIDATE)",
    "lcsc": "C28323",
    "datasheet": None,
    "datasheet_page": 1,
    "pins": {
        "1": {"net": _exact("PWR_SW"),      "function": "Switch node — the 4.9V->0 step that becomes the KEY press", "type": "smd"},
        "2": {"net": _exact("IP5306_KEY"),  "function": "IP5306 KEY (active low, internal pull-up)", "type": "smd"},
    },
}

# SW17 — the DNP manual KEY wake button — HAS NO ENTRY HERE because it is
# NOT ON THE BOARD. It was specified, and then dropped when the placement
# was attempted: every free site within reach of IP5306_KEY copper fails
# clearance against copper the respin itself put there (the PWR_SW spine,
# C33's column, L1's pads, U2.6's BAT+ stitching field), and the nearest
# free 5.1x5.1 tact site is 11.2 mm away. See the block comment at
# scripts/generate_pcb/routing/_shared.py::C33_POS for the enumeration.
#
# A spec entry for a part with no pads is not documentation, it is a
# permanently red gate: verify_datasheet_nets reports every declared pin
# as PAD NOT FOUND. The bench-tune path SW17 was insurance for survives
# without it — C33's own pads are the access point, so lifting the cap and
# tacking a wire to a momentary button reaches KEY and GND directly.
# Fitting a real button needs an IP5306-corner placement reshuffle; that
# is an open respin decision, recorded in docs/open-tasks.md.


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
