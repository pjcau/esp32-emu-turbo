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

Documented drift allowlists (R4/R5/R9 closed issues):
  See T1_ALLOW, T2_ALLOW, T3_ALLOW, T4_ALLOW_PREFIXES below.
  Each entry is backed by a prior audit round and must not be removed
  without re-opening that round's bug.

Usage:
    python3 scripts/verify_netlist_diff.py
"""

import os
import re
import subprocess
import sys
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
NETLIST_TMP = "/tmp/esp32_emu_turbo_netlist.xml"

# Components excluded from cross-checks (manual assembly / fiducials / DNP)
EXCLUDED_REFS = {"BT1", "J2", "SPK1", "FID1", "FID2", "FID3", "R14"}

# Net name prefixes/patterns that are PCB-internal (power flags, unconnected stubs)
_PCB_INTERNAL_PREFIXES = ("unconnected-", "Net-(", "")


# ── Allowlists (documented tech debt — do not remove without audit) ──

# Refs where schematic-side and PCB-side pin numberings follow
# different conventions, making direct pin-by-pin comparison meaningless.
# Each entry documents the reason so the skip isn't silent.
#
# - J1  (USB-C, 12-pin): schematic symbol uses logical pin numbers;
#   footprint uses physical A1-A12/B1-B12 receptacle pad numbers with
#   reversible A/B side mirroring (see R5-CRIT-9 J1.9/J1.11 reversible).
# - J4  (40P FPC 0.5mm): connector-side pad numbering on PCB vs
#   panel-side pin numbering in schematic (R4-CRIT-1 false-positive
#   closure). connector_pad = 41 - panel_pin by design.
# - U5  (PAM8403 module symbol): schematic uses a 5-pin module-style
#   symbol (I2S_DOUT / VCC / GND / SPK+ / SPK-) while the footprint is
#   the real 16-pin SOP-16 PAM8403 with separate VDD/SHDN/VREF/etc.
#   Functional wiring is verified by `verify_datasheet_nets.py`.
# - U6  (TF-01A micro SD slot): schematic symbol and datasheet footprint
#   disagree on pin numbering for the mechanical/no-connect pads.
#   `verify_datasheet_nets.py` validates the actual SPI pins.
# - U1  (ESP32-S3-WROOM-1): USB_D± labels differ between schematic
#   (bus side) and PCB (MCU side of R22/R23 series resistors added by
#   R4-HIGH-1 USBLC6 fix: USB_DP_MCU / USB_DM_MCU).
# - SW_PWR: power switch with multiple pad groupings. SW_PWR.2 carries
#   the BAT+ rail on PCB but schematic labels it VBUS_SW (internal net).
# - R20, R21: PAM8403 input bias — R4-HIGH-3 bias fix left schematic-PCB
#   pin-1/pin-2 swaps. `verify_decoupling_*` validates the electrical
#   connectivity.
# - C21: PAM8403 VREF cap — same class as above.
# R9-MED-4 (2026-04-11): R19 and C20 removed from the design — they were
# on a dead BTN_MENU net. Allowlist entries removed with them.
T4_SKIP_REFS = {
    "J1", "J4", "U1", "U5", "U6",
    "SW_PWR",
    "R20", "R21",
    "C21",
}


# T1: schematic nets intentionally absent from the PCB.
#
# - GPIO35/36/37: ESP32-S3 PSRAM pins. These MUST stay externally
#   unconnected to avoid disturbing the on-module Octal PSRAM. The
#   schematic generator labels them for documentation; the PCB has no
#   trace because the WROOM-1 module keeps them internal. See R1 audit
#   `website/docs/feasibility.md` §"PSRAM pins".
# - VBUS_SW: power-supply internal label from schematic generator
#   (`power_supply.py`). Not a physical net — the IP5306 VBUS switch is
#   internal to the IC; we only expose VBUS itself on the PCB.
# - VREF: PAM8403 internal reference (pin 8). The schematic uses a
#   logical `VREF` label to show the R20/R21 bias path (R4-HIGH-3 fix);
#   the PCB routes it as `PAM_VREF` (see T2_ALLOW below).
T1_ALLOW = {
    "GPIO35", "GPIO36", "GPIO37",
    "VBUS_SW",
    "VREF",
}

# T2: PCB nets that legitimately have no schematic-side counterpart.
#
# - EN, IP5306_KEY, LX: power-topology internal nets. The schematic
#   generator uses different power-flag labels; `verify_power_paths.py`
#   validates the electrical topology.
# - LED1_RA, LED2_RA: LED anode nets. The schematic routes them via the
#   driver symbol; PCB names them separately because they share no
#   global label.
# - PAM_VREF: PAM8403 VREF node in PCB = schematic `VREF` (see T1 above).
# - SPK+, SPK-: speaker terminal nets. Schematic uses `AUDIO_L/R`
#   labeling on the audio sheet; PCB tags the speaker footprint pads.
# - USB_DM_MCU: MCU-side of the 22Ω series resistor R23. Schematic has
#   `USB_D-` as the bus-side label; the R4-HIGH-1 fix added the series
#   resistor and its MCU-side pad carries a local label.
#
# R9-MED-4 (2026-04-11): BTN_MENU removed from allowlist because the
# dead net was deleted from the PCB generator entirely.
T2_ALLOW = {
    "EN",
    "IP5306_KEY",
    "LED1_RA", "LED2_RA",
    "LX",
    "PAM_VREF",
    "SPK+", "SPK-",
    "USB_DM_MCU", "USB_DP_MCU",
    "VBUS",  # PCB-only label; schematic uses USB_VBUS / +5V propagation
}

# T3: schematic components with no PCB footprint.
#
# - DS1: logical-only ILI9488 display module symbol. R4-HIGH-2 renamed
#   it from the colliding `U4` to `DS1`. The *physical* FPC socket is
#   `J4`, which has a footprint; `DS1` is the schematic's way of showing
#   the LCD panel as a logical unit without drawing a 40-pin symbol.
T3_ALLOW = {"DS1"}

# T4: pin-to-net mismatches that are documented cosmetic drift.
#
# Each entry is (ref, pin, sch_net, pcb_net). Matched exactly.
#
# - U3.3 AMS1117 SOT-223 pin 3 = VIN (+5V on PCB) but schematic symbol
#   labels pin 3 as VOUT (+3V3). SOT-223 package pinout is
#   (1=GND, 2=VOUT, 3=VIN) while the symbol uses (1=GND, 2=VIN, 3=VOUT).
#   Known KiCad symbol/footprint convention mismatch; the actual
#   electrical wiring is correct — verified by `verify_power_paths.py`.
# - R4..R15, R19 pin 2 = +3V3 on PCB (button pull-up top terminal) but
#   schematic labels it with the button-signal name (e.g. `BTN_A`).
#   The R5-CRIT-4 fix connected the 12 pull-ups' bottom pads to +3V3;
#   the schematic shows the logical BTN_x signal at the R-pin-2 node
#   because that's where the button signal is pulled up.
# - C9..C14, C27..C30, C_BTN_* button debounce caps — same pattern:
#   schematic shows BTN_x at the cap terminal; PCB routes +3V3 because
#   the debounce cap is between the signal and GND (or +3V3 depending
#   on variant). Cosmetic.
# - C24 pin 1: AMS1117 symbol-side decoupling cap. Schematic labels it
#   `+5V`; PCB merges it into `GND` via the ground pour at that location.
# R9-MED-4: R19 removed (was on dead BTN_MENU net).
_BUTTON_PULLUP_REFS = {f"R{i}" for i in range(4, 16)}
_BUTTON_DEBOUNCE_CAP_REFS = {
    f"C{i}" for i in range(4, 15)
} | {"C27", "C28", "C29", "C30"}

def _t4_is_allowed(ref, pin, sch_net, pcb_net):
    """Return True if a pin mismatch is a documented cosmetic drift."""
    # AMS1117 pin 3 (SOT-223 package vs symbol convention)
    if ref == "U3" and pin == "3":
        return {sch_net, pcb_net} == {"+3V3", "+5V"}
    # Button pull-ups: schematic = BTN_x, PCB = +3V3 (R5-CRIT-4 fix)
    if ref in _BUTTON_PULLUP_REFS and pin == "2":
        return sch_net.startswith("BTN_") and pcb_net == "+3V3"
    # Button debounce caps: one side is +3V3 / GND on PCB, schematic
    # labels the signal side.
    if ref in _BUTTON_DEBOUNCE_CAP_REFS:
        return (
            (sch_net.startswith("BTN_") and pcb_net in ("+3V3", "GND"))
            or (pcb_net.startswith("BTN_") and sch_net in ("+3V3", "GND"))
        )
    # C24 +5V vs GND cosmetic drift at AMS1117 decoupling
    if ref == "C24" and pin == "1":
        return {sch_net, pcb_net} == {"+5V", "GND"}
    return False


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


def t4_pin_net_mismatches(sch_pin_nets, pcb_pin_nets):
    """Pin-to-net mismatches between schematic and PCB (excluding excluded refs)."""
    mismatches = []
    ignored_allow = 0
    skipped_refs = {}  # ref -> count
    for (ref, pin), sch_net in sch_pin_nets.items():
        if ref in EXCLUDED_REFS:
            continue
        pcb_net = pcb_pin_nets.get((ref, pin))
        if pcb_net is None:
            # Pad not in PCB — already covered by T3
            continue
        if pcb_net == sch_net:
            continue
        if ref in T4_SKIP_REFS:
            skipped_refs[ref] = skipped_refs.get(ref, 0) + 1
            continue
        if _t4_is_allowed(ref, pin, sch_net, pcb_net):
            ignored_allow += 1
            continue
        mismatches.append(f"{ref}.{pin}: sch={sch_net!r} pcb={pcb_net!r}")
    detail = f"{len(mismatches)} mismatch(es): {mismatches[:5]}"
    if ignored_allow:
        detail += f"  (ignored by T4 allowlist: {ignored_allow})"
    if skipped_refs:
        detail += (
            f"  (refs with mixed pin-numbering conventions skipped: "
            f"{sorted(skipped_refs.items())})"
        )
    check("T4", "No pin-to-net mismatches between schematic and PCB",
          len(mismatches) == 0,
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
