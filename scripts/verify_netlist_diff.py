#!/usr/bin/env python3
"""Netlist Diff — exports KiCad schematic netlist and cross-checks it against PCB cache.

Checks:
  T1  Nets in schematic but NOT in PCB (missing routes)
  T2  Nets in PCB but NOT in schematic (orphan PCB nets)
  T3  Components in schematic but NOT in PCB (missing footprints)
  T4  Pin-to-net mismatches between schematic and PCB

Known exclusions (manual assembly / fiducials / DNP):
  BT1, J2, SPK1 — manual assembly (no PCBA footprint required)
  FID1, FID2, FID3 — fiducials (no electrical nets)
  R14 — DNP (do not populate)

T4 compares EVERY schematic pin of every non-excluded ref. Refs whose
symbol pin numbering deliberately differs from the footprint pad
numbering (logical USB-C / FPC / module symbols, four-pad tact switch
footprints) are translated through SCH_PIN_TO_PCB_PADS rather than
skipped: a wrong entry in that table still fails the check, and a
schematic pin that has no entry on a mapped ref is reported as a hole
in the table.

Remaining suppressions, all narrow and evidence-backed:
  T1_ALLOW  GPIO35/36/37 — ESP32-S3 on-module Octal PSRAM pins, which
            must stay externally unconnected — plus GPIO15/16, unused pins
            labelled for documentation since the I2S reservation was
            retired (R10-LOW-2, 2026-07-26).
  T2_ALLOW  five PCB-internal node names the Power Supply / MCU sheets
            still draw as unlabelled wires (KiCad drops unnamed nets
            from the exported netlist, so they cannot be compared).
  T3_ALLOW  DS1 — schematic-only logical panel symbol; the physical
            part is J4.
  _T4_STRUCTURAL_EXCEPTIONS  EMPTY, and must stay that way. It once held
            four tuples for the PAM8403 input bias network; the board has
            since been re-routed to match the schematic. See the comment
            there before ever adding an entry.

Usage:
    python3 scripts/verify_netlist_diff.py
"""

import atexit
import os
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0

SCH_PATH = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_sch")
# Per-process path. scripts/run-verifiers.sh runs the suite in PARALLEL, so a
# fixed filename here is a race: any other gate that exports the schematic
# netlist — scripts/vbench/netlist.py does, through this module's
# export_netlist() — writes the same file at the same time, and both readers
# get whichever half-written copy they happen to see. That produced an
# intermittent failure in verify_netlist_diff and in test_vbench, on
# alternating runs, which is worse than either of them simply being red.
#
# The same race also crosses checkouts: this repo usually has several worktrees
# open, and the old fixed "/tmp/esp32_emu_turbo_netlist.xml" was shared by all
# of them, surfacing as
#
#     xml.etree.ElementTree.ParseError: junk after document element
#
# A gate that fails for a reason unrelated to the board is the fastest way to
# teach everyone that red means nothing. PID is unique machine-wide, so it
# closes both variants at once.
NETLIST_TMP = os.path.join(
    tempfile.gettempdir(), f"esp32_emu_turbo_netlist.{os.getpid()}.xml")


@atexit.register
def _cleanup_netlist_tmp():
    """Do not leave one file per run behind in the temp directory."""
    try:
        os.unlink(NETLIST_TMP)
    except OSError:
        pass

# Components excluded from cross-checks (manual assembly / fiducials / DNP)
EXCLUDED_REFS = {"BT1", "J2", "SPK1", "FID1", "FID2", "FID3", "R14"}

# Net name prefixes/patterns that are PCB-internal (power flags, unconnected stubs)
_PCB_INTERNAL_PREFIXES = ("unconnected-", "Net-(", "")


# ── Schematic-pin -> PCB-pad maps ──────────────────────────────────
#
# Several refs use a *logical* schematic symbol whose pin numbering is
# deliberately not the footprint's pad numbering: a 6-pin USB-C symbol
# in front of a 16-pad receptacle land, a 16-pin FPC symbol in front of
# a 40-pad connector, module-style symbols in front of real SOP-16 /
# micro-SD lands, two-terminal switch symbols in front of four-pad
# tact-switch footprints.
#
# These refs used to be *skipped* wholesale, which removed 8 refs —
# including U1 (the MCU) and J4 (the display connector) — from the one
# check whose job is catching schematic/PCB divergence. They are now
# compared through an explicit map instead.
#
# Semantics: SCH_PIN_TO_PCB_PADS[ref][sch_pin] = tuple of PCB pad
# numbers that pin electrically is. Every mapped pad that carries a net
# on the board must carry the schematic pin's net. Pads with no net
# (unrouted / mechanical) are skipped, exactly as for unmapped refs.
# A wrong map therefore still fails — this is a translation, not a
# suppression.

# J1 — USB_C 6-pin logical symbol -> 16-pad USB-C receptacle land.
# Pad roles from hardware/datasheet_specs.py::J1 (which in turn quotes
# hardware/datasheets/J1_USB-C-16pin_C2765186.pdf):
#   1,12,13,14 = GND (shell + both rows)   2,11 = VBUS (A4+B9 / B4+A9)
#   4 = CC1     10 = CC2
#   6 = DP1, 8 = DP2 (D+, both plug orientations)
#   7 = DN1, 5 = DN2 (D-, both plug orientations)
#   3,9        = SBU2/SBU1, unused, no net
#
# Corrected 2026-07-26: this comment used to read "3,5,8 = SBU / unused,
# no net" and the map sent D+ to pad 6 only and D- to pad 7 only. Both
# halves were wrong. The SBU pins are 3 and 9; pads 5 and 8 are the
# flipped-orientation half of the differential pair, and they carry
# USB_D-/USB_D+ on this board — datasheet_specs.py::J1 says so pad by
# pad, citing USB-C r2.1 section 4.2, which is why the two rows are tied
# together. The consequence of the old map was that T4 compared two of
# the four data pads and the other two were compared against nothing by
# this gate. Found by scripts/vbench/netlist.py (dispute class D3).
_J1_MAP = {
    "1": ("2", "9", "11"),          # VBUS
    "2": ("4",),                    # CC1
    "3": ("10",),                   # CC2
    "4": ("6", "8"),                # D+ = DP1 (A6) + DP2 (B6)
    "5": ("7", "5"),                # D- = DN1 (A7) + DN2 (B7)
    "6": ("1", "12", "13", "14"),   # GND
}

# J4 — FPC_16P logical symbol -> 40-pad FPC land.
#
# Two independent transforms are stacked here:
#   a) the schematic symbol only breaks out the 16 signals we use, in
#      the order listed in sheets/display.py::fpc_nets;
#   b) the ribbon is not twisted, so connector_pad = 41 - panel_pin
#      (documented at the top of sheets/display.py; do NOT "fix" it).
# sym pin -> panel pin -> pad:
#   1 +3V3   -> panel  6 -> 35      9  D0 -> panel 17 -> 24
#   2 GND    -> panel  5 -> 36      10 D1 -> panel 18 -> 23
#   3 CS     -> panel  9 -> 32      11 D2 -> panel 19 -> 22
#   4 RST    -> panel 15 -> 26      12 D3 -> panel 20 -> 21
#   5 DC     -> panel 10 -> 31      13 D4 -> panel 21 -> 20
#   6 WR     -> panel 11 -> 30      14 D5 -> panel 22 -> 19
#   7 RD     -> panel 12 -> 29      15 D6 -> panel 23 -> 18
#   8 LED-A  -> panel 33 ->  8      16 D7 -> panel 24 -> 17
_J4_PANEL_PIN = {
    "1": 6, "2": 5, "3": 9, "4": 15, "5": 10, "6": 11, "7": 12, "8": 33,
    "9": 17, "10": 18, "11": 19, "12": 20, "13": 21, "14": 22,
    "15": 23, "16": 24,
}
_J4_MAP = {sym: (str(41 - panel),) for sym, panel in _J4_PANEL_PIN.items()}

# U5 — PAM8403_Module 5-pin symbol -> SOP-16 PAM8403.
# Pin roles from hardware/datasheets/U5_PAM8403_C5122557.pdf:
#   4,13 = PVDD   6 = VDD   11,15 = GND   7 = INL   10 = INR
#   14 = OUTR-    16 = OUTR+
# The board bridges INL and INR for mono, so the single AUDIO_IN pin of
# the module symbol maps to both.
_U5_MAP = {
    "1": ("4", "6", "12", "13"),   # VCC  -> VDD + PVDD pins
    "2": ("11", "15"),             # GND
    "3": ("7", "10"),              # AUDIO_IN -> INL + INR (bridged mono)
    "4": ("16",),                  # SPK+ -> OUTR+
    "5": ("14",),                  # SPK- -> OUTR-
}

# U6 — SD_Module 6-pin symbol -> TF-01A micro-SD land.
# Pad roles from hardware/datasheets/U6_TF-01A_MicroSD_C91145.pdf:
#   1 DAT2  2 CD/DAT3 (= SPI CS)  3 CMD (= MOSI)  4 VDD  5 CLK
#   6 VSS   7 DAT0 (= MISO)       8 DAT1          9 CD
#   10,12 = shell tabs tied to VSS on this board
_U6_MAP = {
    "1": ("4",),              # VCC
    "2": ("6", "10", "12"),   # GND + shell
    "3": ("3",),              # MOSI -> CMD
    "4": ("7", "8"),          # MISO -> DAT0 (DAT1 tied to it on this board)
    "5": ("5",),              # CLK
    "6": ("2",),              # CS -> CD/DAT3
}

# SW1..SW13 — SW_Push 2-pin symbol -> 4-pad tact switch.
# The tact footprint has two pads per terminal. Which pads form a pair
# is stated in hardware/datasheet_specs.py (line "4-pin tact switch:
# pins 1+2 shorted, pins 3+4 shorted") and is what routing.py assumes
# for SW13 (pads 1,2 = MENU_K / pads 3,4 = GND). routing.py picks
# whichever pad of a pair is geometrically convenient, so both pads of
# a terminal are accepted.
_TACT_MAP = {"1": ("1", "2"), "2": ("3", "4")}

# SW11 / SW12 (L and R shoulder buttons) are routed with the terminals
# the other way round from the other ten buttons: the button signal
# lands on the 3/4 terminal and GND on the 1/2 terminal (see
# routing.py, `sl_pad = _pad("SW11", "3")` / `sl_gnd = _pad("SW11",
# "2")`). A tact switch is a symmetric SPST, so neither orientation is
# wrong — but the pin numbers do differ and the map has to say so.
_TACT_MAP_REVERSED = {"1": ("3", "4"), "2": ("1", "2")}

# SW_PWR — SW_Push 2-pin symbol -> MSK12C02 slide switch.
# Pad 2 is the common terminal, pads 1 and 3 the two throws. On v1 only
# the common is routed (see sheets/power_supply.py and
# hardware/datasheet_specs.py::SW_PWR).
_SW_PWR_MAP = {"1": ("2",), "2": ("1", "3")}

# LED1 / LED2 — this repo's private LED symbol numbers its pins
# pin 1 = A (anode), pin 2 = K (cathode) (lib_symbols.py:320-321).
# The LED_0805 footprint follows the NCD0805R1 / C84256 datasheet,
# where pad 1 = cathode and pad 2 = anode (routing.py::_led_traces).
# KiCad's own Device:LED agrees with the footprint, so the symbol is
# the outlier.
#
# This is a numbering translation, NOT a polarity waiver, and each side
# was checked independently before writing it: on the PCB pad 2 carries
# LED{n}_RA (through R17/R18 to +3V3) and pad 1 carries GND, i.e. anode
# to the resistor, cathode to ground; in the schematic pin 1 (A) carries
# LED{n}_RA and pin 2 (K) carries GND — the same circuit. Only the
# numbers differ. A wrong entry here still fails T4, exactly as for
# J1/J4/U5/U6.
#
# Deeper fix, deliberately not taken here: renumber the symbol to
# pin 1 = K / pin 2 = A and swap the wires in power_supply.py, which
# would remove the outlier instead of translating it.
_LED_MAP = {"1": ("2",), "2": ("1",)}

SCH_PIN_TO_PCB_PADS = {
    "J1": _J1_MAP,
    "J4": _J4_MAP,
    "U5": _U5_MAP,
    "U6": _U6_MAP,
    "SW_PWR": _SW_PWR_MAP,
    "LED1": _LED_MAP,
    "LED2": _LED_MAP,
}
for _n in range(1, 14):
    SCH_PIN_TO_PCB_PADS[f"SW{_n}"] = _TACT_MAP
SCH_PIN_TO_PCB_PADS["SW11"] = _TACT_MAP_REVERSED
SCH_PIN_TO_PCB_PADS["SW12"] = _TACT_MAP_REVERSED
# SW_RST / SW_BOOT are the same part on the same footprint as SW1..SW13
# (SW-SMD-5.1x5.1, one row each in cpl.csv) wired the same way round:
# routing.py puts the signal on the 1/2 terminal and GND on 3/4. They were
# missing from this table only because their schematic pins were floating,
# so no pin of theirs ever reached the comparison to expose the gap.
SCH_PIN_TO_PCB_PADS["SW_RST"] = _TACT_MAP
SCH_PIN_TO_PCB_PADS["SW_BOOT"] = _TACT_MAP


# T1: schematic nets intentionally absent from the PCB.
#
# - GPIO35/36/37: ESP32-S3 PSRAM pins. These MUST stay externally
#   unconnected to avoid disturbing the on-module Octal PSRAM. The
#   schematic generator labels them for documentation; the PCB has no
#   trace because the WROOM-1 module keeps them internal. See R1 audit
#   `website/docs/feasibility.md` §"PSRAM pins".
#
# Removed: VBUS_SW and VREF. VREF was renamed to PAM_VREF in
# sheets/audio.py so that the schematic and the board use one name for
# one node; VBUS_SW no longer exists in the generated schematic.
T1_ALLOW = {
    "GPIO35", "GPIO36", "GPIO37",
    # GPIO15/16: unused pins, labelled for documentation only, same class
    # as the PSRAM trio above. They carried the I2S_BCLK/I2S_LRCK net
    # reservation until 2026-07-26 (R10-LOW-2): one pin each, zero copper,
    # while the audio path is PDM TX with .clk = I2S_GPIO_UNUSED. The PCB
    # deliberately leaves the pads netless; the schematic labels the pins
    # GPIO15/GPIO16 so a reader knows which pins are free for v2.
    "GPIO15", "GPIO16",
}

# T2: PCB nets that legitimately have no schematic-side counterpart.
#
# Every entry is a node the PCB generator names but the Power Supply /
# MCU sheets draw as an unlabelled wire between two symbols. KiCad drops
# unnamed nets from the exported netlist, so they cannot be compared.
# The fix for each is the same — emit a global label with the PCB's net
# name on that wire — and each one removed here is one more node the
# cross-check actually verifies.
#
# Removed 2026-07-25 because the schematic now names them:
#   BAT_IN, PAM_VREF, SPK+, SPK-, USB_DM_MCU, USB_DP_MCU, VBUS
T2_ALLOW = {
    "EN",           # ESP32 EN pin node (mcu.py skips EN when labelling)
    "IP5306_KEY",   # IP5306 KEY pin <-> R16 <-> SW13 node
    "LED1_RA", "LED2_RA",  # R17/LED1 and R18/LED2 junctions
    "LX",           # IP5306 SW pin <-> L1 boost inductor node
    "RPP_GATE",     # Q1 gate <-> R24 junction
}

# T3: schematic components with no PCB footprint.
#
# - DS1: logical-only ILI9488 display module symbol. R4-HIGH-2 renamed
#   it from the colliding `U4` to `DS1`. The *physical* FPC socket is
#   `J4`, which has a footprint; `DS1` is the schematic's way of showing
#   the LCD panel as a logical unit without drawing a 40-pin symbol.
T3_ALLOW = {"DS1"}

# T4: pin-to-net mismatches that are NOT a numbering convention and
# cannot be closed by fixing one side's drawing.
#
# Each entry is an exact (ref, sch_pin, sch_net, pcb_net) tuple, so any
# other divergence on the same part still fails. Adding an entry here
# requires stating (a) the physical evidence, (b) which side is wrong,
# (c) where the fix has to be made.
#
# ── R20 / R21: PAM8403 input bias network — CLOSED ────────────────
# This set used to carry four tuples for R20/R21, excusing a board that
# tied the amplifier input bias to GND while the schematic specified VREF.
# The exception documented its own fix: re-route R20 pad 1 and R21 pad 1
# from their GND vias to the PAM_VREF node at C21 pad 2. That is done --
# routing.py now builds a VREF bias rail down the x=38.95 lane, and the
# board passes DFM 122/0, native DRC 0 violations and power-net integrity.
#
# Keep this EMPTY. An exception here hides a real schematic/PCB divergence,
# which is the bug class this gate exists to catch: for four releases it
# reported PASS while the two sides described different circuits.
_T4_STRUCTURAL_EXCEPTIONS = set()


def _t4_is_allowed(ref, pin, sch_net, pcb_net):
    """Return True only for exactly-enumerated structural exceptions."""
    return (ref, pin, sch_net, pcb_net) in _T4_STRUCTURAL_EXCEPTIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def check(test_id, name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  [{test_id}] {name}")
    else:
        FAIL += 1
        print(f"  FAIL  [{test_id}] {name}  {detail}")
    return condition


def _is_pcb_internal(net_name):
    """Return True for KiCad auto-generated net names that have no schematic equivalent."""
    return (net_name.startswith("unconnected-")
            or net_name.startswith("Net-(")
            or net_name == "")


# ---------------------------------------------------------------------------
# Step 1 — Export netlist from schematic
# ---------------------------------------------------------------------------

def export_netlist():
    """Run kicad-cli to export KiCadXML netlist. Return True on success."""
    cmd = [
        "kicad-cli", "sch", "export", "netlist",
        "--format", "kicadxml",
        "--output", NETLIST_TMP,
        SCH_PATH,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f"  ERROR  kicad-cli failed (rc={result.returncode}): {result.stderr.strip()}")
            return False
        if not os.path.exists(NETLIST_TMP):
            print(f"  ERROR  Netlist not created at {NETLIST_TMP}")
            return False
        return True
    except FileNotFoundError:
        print("  ERROR  kicad-cli not found — install KiCad or add it to PATH")
        return False
    except subprocess.TimeoutExpired:
        print("  ERROR  kicad-cli timed out")
        return False


# ---------------------------------------------------------------------------
# Step 2 — Parse netlist XML
# ---------------------------------------------------------------------------

def parse_netlist(path):
    """Parse KiCadXML netlist. Return (sch_nets, sch_comps, sch_pin_nets).

    sch_nets   : set of net names
    sch_comps  : set of component references
    sch_pin_nets: dict of (ref, pin_number) -> net_name
    """
    tree = ET.parse(path)
    root = tree.getroot()

    sch_nets = set()
    sch_comps = set()
    sch_pin_nets = {}  # (ref, pin) -> net_name

    # <components> section
    components_el = root.find("components")
    if components_el is not None:
        for comp in components_el.findall("comp"):
            ref = comp.get("ref", "")
            if ref and not ref.startswith("#"):
                sch_comps.add(ref)

    # <nets> section
    nets_el = root.find("nets")
    if nets_el is not None:
        for net_el in nets_el.findall("net"):
            net_name = net_el.get("name", "")
            if not net_name:
                continue
            sch_nets.add(net_name)
            for node in net_el.findall("node"):
                ref = node.get("ref", "")
                pin = node.get("pin", "")
                if ref and pin:
                    sch_pin_nets[(ref, pin)] = net_name

    return sch_nets, sch_comps, sch_pin_nets


# ---------------------------------------------------------------------------
# Step 3 — Build PCB net/pad lookup from cache
# ---------------------------------------------------------------------------

def build_pcb_data(cache):
    """Return (pcb_nets, pcb_refs, pcb_pin_nets) from cache.

    pcb_nets    : set of net names in PCB
    pcb_refs    : set of component refs in PCB
    pcb_pin_nets: dict of (ref, pad_num) -> net_name
    """
    net_id_to_name = {n["id"]: n["name"] for n in cache.get("nets", [])}

    pcb_nets = set(net_id_to_name.values()) - {""}
    pcb_refs = set(cache.get("refs", []))

    pcb_pin_nets = {}
    for pad in cache.get("pads", []):
        ref = pad.get("ref", "")
        num = str(pad.get("num", ""))
        net_id = pad.get("net", 0)
        net_name = net_id_to_name.get(net_id, "")
        if ref and num and net_name:
            # Keep first occurrence (pads may be duplicated per copper layer)
            key = (ref, num)
            if key not in pcb_pin_nets:
                pcb_pin_nets[key] = net_name

    return pcb_nets, pcb_refs, pcb_pin_nets


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def t1_missing_routes(sch_nets, pcb_nets):
    """Nets in schematic but not routed in PCB."""
    missing = set()
    for net in sch_nets:
        if _is_pcb_internal(net):
            continue
        if net in T1_ALLOW:
            continue
        if net not in pcb_nets:
            missing.add(net)
    allowed_hit = (sch_nets & T1_ALLOW) - pcb_nets
    detail = f"{len(missing)} missing: {sorted(missing)[:10]}"
    if allowed_hit:
        detail += f"  (ignored by T1_ALLOW: {sorted(allowed_hit)})"
    check("T1", "Schematic nets all present in PCB",
          len(missing) == 0,
          detail)


def t2_orphan_pcb_nets(sch_nets, pcb_nets):
    """Nets in PCB but not in schematic (excluding auto-generated names)."""
    orphan = set()
    for net in pcb_nets:
        if _is_pcb_internal(net):
            continue
        if net in T2_ALLOW:
            continue
        if net not in sch_nets:
            orphan.add(net)
    allowed_hit = (pcb_nets & T2_ALLOW) - sch_nets
    detail = f"{len(orphan)} orphan: {sorted(orphan)[:10]}"
    if allowed_hit:
        detail += f"  (ignored by T2_ALLOW: {sorted(allowed_hit)})"
    check("T2", "PCB nets all present in schematic",
          len(orphan) == 0,
          detail)


def t3_missing_footprints(sch_comps, pcb_refs):
    """Components in schematic but without a footprint in PCB."""
    # Filter excluded refs
    expected = sch_comps - EXCLUDED_REFS - T3_ALLOW
    missing = expected - pcb_refs
    allowed_hit = (sch_comps & T3_ALLOW) - pcb_refs
    detail = f"{len(missing)} missing: {sorted(missing)[:10]}"
    if allowed_hit:
        detail += f"  (ignored by T3_ALLOW: {sorted(allowed_hit)})"
    check("T3", "All schematic components have PCB footprints",
          len(missing) == 0,
          detail)


def _mapped_pads(ref, pin):
    """PCB pad numbers a schematic pin corresponds to.

    Identity unless the ref has an explicit map. A ref that has a map
    must map every pin it uses — an unmapped pin on a mapped ref is a
    hole in the table and is reported as such rather than skipped.
    """
    ref_map = SCH_PIN_TO_PCB_PADS.get(ref)
    if ref_map is None:
        return (pin,), True
    pads = ref_map.get(pin)
    if pads is None:
        return (), False
    return pads, True


def t4_pin_net_mismatches(sch_pin_nets, pcb_pin_nets):
    """Pin-to-net mismatches between schematic and PCB.

    Refs whose symbol pin numbering differs from the footprint pad
    numbering are translated through SCH_PIN_TO_PCB_PADS instead of
    being skipped, so every schematic pin of every ref is compared.
    """
    mismatches = []
    unmapped = []
    ignored_allow = 0
    for (ref, pin), sch_net in sorted(sch_pin_nets.items()):
        if ref in EXCLUDED_REFS:
            continue
        pads, mapped = _mapped_pads(ref, pin)
        if not mapped:
            unmapped.append(f"{ref}.{pin}")
            continue
        for pad in pads:
            pcb_net = pcb_pin_nets.get((ref, pad))
            if pcb_net is None:
                # Pad carries no net on the board (unrouted / mechanical);
                # missing footprints are covered by T3.
                continue
            if pcb_net == sch_net:
                continue
            if _t4_is_allowed(ref, pin, sch_net, pcb_net):
                ignored_allow += 1
                continue
            via = "" if pads == (pin,) else f" (pad {pad})"
            mismatches.append(
                f"{ref}.{pin}{via}: sch={sch_net!r} pcb={pcb_net!r}")
    detail = f"{len(mismatches)} mismatch(es): {mismatches[:8]}"
    if unmapped:
        detail += f"  (pins missing from SCH_PIN_TO_PCB_PADS: {unmapped})"
    if ignored_allow:
        detail += (
            f"  ({ignored_allow} structural exception(s) — see "
            f"_T4_STRUCTURAL_EXCEPTIONS)")
    check("T4", "No pin-to-net mismatches between schematic and PCB",
          len(mismatches) == 0 and not unmapped,
          detail)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    global PASS, FAIL

    print("=" * 60)
    print("Netlist Diff — schematic vs PCB cross-check")
    print("=" * 60)

    # Export netlist
    print("\n[Exporting schematic netlist via kicad-cli...]")
    if not export_netlist():
        print("\n  ABORT  Cannot proceed without netlist export.")
        sys.exit(2)
    print(f"  OK    Netlist written to {NETLIST_TMP}")

    # Parse netlist
    sch_nets, sch_comps, sch_pin_nets = parse_netlist(NETLIST_TMP)
    print(f"  OK    Schematic: {len(sch_comps)} components, "
          f"{len(sch_nets)} nets, {len(sch_pin_nets)} pin-net entries")

    # Load PCB cache
    cache = load_cache()
    pcb_nets, pcb_refs, pcb_pin_nets = build_pcb_data(cache)
    print(f"  OK    PCB cache: {len(pcb_refs)} refs, "
          f"{len(pcb_nets)} nets, {len(pcb_pin_nets)} pad-net entries")
    print(f"  INFO  Excluded refs: {sorted(EXCLUDED_REFS)}")

    # Run tests
    print("\n[Running checks...]")
    t1_missing_routes(sch_nets, pcb_nets)
    t2_orphan_pcb_nets(sch_nets, pcb_nets)
    t3_missing_footprints(sch_comps, pcb_refs)
    t4_pin_net_mismatches(sch_pin_nets, pcb_pin_nets)

    # Summary
    total = PASS + FAIL
    print("\n" + "=" * 60)
    print(f"Results: {PASS}/{total} passed, {FAIL} failed")
    if FAIL == 0:
        print("STATUS: PASS — schematic and PCB are consistent")
    else:
        print("STATUS: FAIL — fix the issues above before manufacturing")
    print("=" * 60)

    sys.exit(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    main()
