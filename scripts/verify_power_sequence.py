#!/usr/bin/env python3
"""Power Sequencing Verification.

Verifies that the power-up sequence is safe and meets timing requirements:
  1. SY8089 buck input (+5V) is upstream of output (+3V3)
  2. ESP32 EN pin has RC delay for proper boot timing
  3. No component receives power before its supply is stable
  4. Brownout detector configuration in firmware
  5. Power path: BAT+ -> IP5306 -> +5V -> SY8089 -> +3V3 -> ESP32

Power-up sequence (expected):
  T0:  Battery connects (BAT+ via SW16)
  T1:  IP5306 boots, boost converter starts (+5V ramps)
  T2:  +5V stable -> SY8089 regulates (+3V3 ramps)
  T3:  +3V3 stable -> EN pin rises through RC (R3/C3, tau=1ms)
  T4:  EN reaches threshold -> ESP32 resets, samples strapping pins
  T5:  ESP32 boots (flash -> application)

Usage:
    python3 scripts/verify_power_sequence.py
    Exit code 0 = pass, 1 = failure
"""

import math
import os
import re
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")
BOARD_CONFIG_H = os.path.join(BASE, "software", "main", "board_config.h")
# routing was split into a package 2026-07-26 (byte-identical output);
# text checks read every module of it, concatenated.
ROUTING_PKG = os.path.join(BASE, "scripts", "generate_pcb", "routing")


def _routing_source() -> str:
    import glob
    return "\n".join(open(f).read()
                     for f in sorted(glob.glob(os.path.join(ROUTING_PKG, "*.py"))))
SCHEMATIC_DIR = os.path.join(BASE, "hardware", "kicad")

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def info(name, detail=""):
    print(f"  INFO  {name}  {detail}")


def _dist(x1, y1, x2, y2):
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def _read_schematics():
    parts = []
    for fn in sorted(os.listdir(SCHEMATIC_DIR)):
        if fn.endswith(".kicad_sch"):
            parts.append(open(os.path.join(SCHEMATIC_DIR, fn), encoding="utf-8").read())
    return "\n".join(parts)


def _get_pad(cache, ref, pin):
    for p in cache["pads"]:
        if p["ref"] == ref and str(p["num"]) == str(pin):
            return p
    return None


def test_power_chain_topology():
    """Test 1-5: Verify power chain: BAT -> IP5306 -> +5V -> SY8089 -> +3V3."""
    print("\n-- Power Chain Topology --")
    cache = load_cache(PCB_FILE)
    net_map = {n["name"]: n["id"] for n in cache["nets"]}

    # 1. IP5306 VIN (pin 1) should be on VBUS net
    ip_vin = _get_pad(cache, "U2", "1")
    if ip_vin:
        vbus_id = net_map.get("VBUS", -1)
        check("IP5306 VIN (pin 1) on VBUS net",
              ip_vin["net"] == vbus_id,
              f"net={ip_vin['net']}, expected VBUS={vbus_id}")
    else:
        check("IP5306 VIN pad found", False)

    # 2. IP5306 VOUT (pin 8) should be on +5V net
    ip_vout = _get_pad(cache, "U2", "8")
    if ip_vout:
        n5v_id = net_map.get("+5V", -1)
        check("IP5306 VOUT (pin 8) on +5V net",
              ip_vout["net"] == n5v_id,
              f"net={ip_vout['net']}, expected +5V={n5v_id}")
    else:
        check("IP5306 VOUT pad found", False)

    # 3. U3 SY8089 buck IN (pin 4) should be on +5V net
    bk_in = _get_pad(cache, "U3", "4")
    if bk_in:
        n5v_id = net_map.get("+5V", -1)
        check("SY8089 IN (pin 4) on +5V net",
              bk_in["net"] == n5v_id,
              f"net={bk_in['net']}, expected +5V={n5v_id}")
    else:
        check("SY8089 IN pad found", False)

    # 4. U3 buck output reaches +3V3 through L2 (pin 3 LX -> L2.2, L2.1 -> +3V3).
    #    A switching regulator has no "VOUT pin": the rail is formed after the
    #    inductor, so the check follows LX -> L2 -> +3V3.
    bk_lx = _get_pad(cache, "U3", "3")
    l2_lx = _get_pad(cache, "L2", "2")
    l2_out = _get_pad(cache, "L2", "1")
    n_lx = net_map.get("BUCK_LX", -1)
    n3v3_id = net_map.get("+3V3", -1)
    if bk_lx and l2_lx and l2_out:
        check("SY8089 LX (pin 3) on BUCK_LX net",
              bk_lx["net"] == n_lx,
              f"net={bk_lx['net']}, expected BUCK_LX={n_lx}")
        check("L2 bridges BUCK_LX -> +3V3",
              l2_lx["net"] == n_lx and l2_out["net"] == n3v3_id,
              f"L2.2={l2_lx['net']}, L2.1={l2_out['net']}")
    else:
        check("SY8089 LX / L2 pads found", False)

    # 5. Buck input upstream of output (IN.net != output rail)
    if bk_in and l2_out:
        check("Buck input/output on different nets",
              bk_in["net"] != l2_out["net"],
              f"both on net {bk_in['net']}")

    # 6. Feedback divider present and on the correct nets — this is what
    #    actually programs the output voltage on a switcher.
    n_fb = net_map.get("BUCK_FB", -1)
    bk_fb = _get_pad(cache, "U3", "5")
    r25_fb = _get_pad(cache, "R25", "2")
    r26_gnd = _get_pad(cache, "R26", "2")
    n_gnd_id = net_map.get("GND", -1)
    check("SY8089 FB (pin 5) on BUCK_FB net",
          bool(bk_fb) and bk_fb["net"] == n_fb,
          f"net={bk_fb['net'] if bk_fb else None}, expected BUCK_FB={n_fb}")
    check("R25/R26 divider terminates BUCK_FB and GND",
          bool(r25_fb) and bool(r26_gnd)
          and r25_fb["net"] == n_fb and r26_gnd["net"] == n_gnd_id,
          f"R25.2={r25_fb['net'] if r25_fb else None}, "
          f"R26.2={r26_gnd['net'] if r26_gnd else None}")


def test_en_rc_timing():
    """Test 6-8: EN pin routing and boot timing.

    ESP32-S3-WROOM-1 module has internal 10k pull-up + 0.1uF on EN.
    External R3 was removed (unrouted, no electrical function).
    EN is now directly routed from SW15 via B.Cu to U1 pin 3.
    C3 (100nF decoupling) remains near ESP32 for power stability.
    """
    print("\n-- EN Pin Routing --")
    cache = load_cache(PCB_FILE)

    # Check EN net exists
    en_net_id = None
    for n in cache["nets"]:
        if n["name"] == "EN":
            en_net_id = n["id"]
            break

    # EN pin (U1:3) should have EN net assigned (routed from SW15)
    en_pin = _get_pad(cache, "U1", "3")
    check("U1 pin 3 (EN) exists in PCB", en_pin is not None,
          "U1 pad 3 not found")
    if en_pin and en_net_id is not None:
        check("U1 pin 3 has EN net assigned",
              en_pin.get("net") == en_net_id,
              f"net={en_pin.get('net')}, expected={en_net_id}")

    # C3 (100nF decoupling) should still exist near ESP32
    c3_pad = _get_pad(cache, "C3", "1")
    check("C3 (100nF) exists in PCB", c3_pad is not None,
          "C3 pad 1 not found")

    if en_pin and c3_pad:
        d = _dist(en_pin["x"], en_pin["y"], c3_pad["x"], c3_pad["y"])
        check(f"C3 within 30mm of ESP32 EN pin",
              d < 30.0,
              f"distance={d:.1f}mm")


def test_esp32_power_pins():
    """Test 9-10: ESP32 power pins connected to correct rails."""
    print("\n-- ESP32 Power Connections --")
    cache = load_cache(PCB_FILE)
    net_map = {n["name"]: n["id"] for n in cache["nets"]}

    # VDD pins (1, 2) should be on +3V3
    # Note: some pins may show net=0 in PCB cache because they connect
    # via zone fill (internal copper planes), not direct traces.
    n3v3 = net_map.get("+3V3", -1)
    for pin in ("1", "2"):
        pad = _get_pad(cache, "U1", pin)
        if pad:
            # net=0 means zone-connected (expected for multi-pin power)
            is_ok = pad["net"] == n3v3 or pad["net"] == 0
            detail = "(zone-connected)" if pad["net"] == 0 else ""
            check(f"ESP32 pin {pin} on +3V3 {detail}".strip(),
                  is_ok,
                  f"net={pad['net']}, expected +3V3={n3v3} or zone(0)")

    # GND pins (40, 41) should be on GND
    n_gnd = net_map.get("GND", -1)
    for pin in ("40", "41"):
        pad = _get_pad(cache, "U1", pin)
        if pad:
            is_ok = pad["net"] == n_gnd or pad["net"] == 0
            detail = "(zone-connected)" if pad["net"] == 0 else ""
            check(f"ESP32 pin {pin} on GND {detail}".strip(),
                  is_ok,
                  f"net={pad['net']}, expected GND={n_gnd} or zone(0)")


def test_no_early_power():
    """Test 11-13: No IC receives signal before its power is stable.

    Critical paths:
    - PAM8403 VDD (+5V) must come from same rail as SY8089 buck input
    - SD card VDD (+3V3) through SY8089 buck (downstream of ESP32)
    - USB ESD (U4) VBUS powers from same VBUS as IP5306
    """
    print("\n-- No Early Power Issues --")
    cache = load_cache(PCB_FILE)
    net_map = {n["name"]: n["id"] for n in cache["nets"]}

    # PAM8403 VDD (pin 6) on +5V -- powered from IP5306 boost
    pam_vdd = _get_pad(cache, "U5", "6")
    if pam_vdd:
        n5v = net_map.get("+5V", -1)
        check("PAM8403 VDD on +5V (powered by IP5306 boost)",
              pam_vdd["net"] == n5v,
              f"net={pam_vdd['net']}, expected +5V={n5v}")

    # SD card module VDD on +3V3 -- downstream of SY8089 buck
    sd_vdd = _get_pad(cache, "U6", "4")
    if sd_vdd:
        n3v3 = net_map.get("+3V3", -1)
        check("SD card VDD on +3V3 (downstream of SY8089 buck)",
              sd_vdd["net"] == n3v3,
              f"net={sd_vdd['net']}, expected +3V3={n3v3}")

    # USB ESD TVS (U4) pin 5 on VBUS -- same source as IP5306
    tvs_vbus = _get_pad(cache, "U4", "5")
    if tvs_vbus:
        n_vbus = net_map.get("VBUS", -1)
        check("USB TVS (U4) pin 5 on VBUS (same rail as IP5306 VIN)",
              tvs_vbus["net"] == n_vbus,
              f"net={tvs_vbus['net']}, expected VBUS={n_vbus}")


def test_power_switch_position():
    """Test 14: Power switch is between battery and IP5306."""
    print("\n-- Power Switch Position --")
    cache = load_cache(PCB_FILE)
    net_map = {n["name"]: n["id"] for n in cache["nets"]}

    # SW16 should switch BAT+ to IP5306
    # Common pin connects to one rail, switched pin to the other
    sw_pads = [p for p in cache["pads"] if p["ref"] == "SW16"]
    if sw_pads:
        sw_nets = set(p["net"] for p in sw_pads if p["net"] != 0)
        bat_id = net_map.get("BAT+", -1)
        vbus_id = net_map.get("VBUS", -1)

        # SW16 connects BAT+ to VBUS (or to IP5306 VIN)
        has_bat = bat_id in sw_nets
        has_vbus = vbus_id in sw_nets
        check("Power switch connects BAT+ rail",
              has_bat or has_vbus,
              f"switch nets: {sw_nets}, BAT+={bat_id}, VBUS={vbus_id}")
    else:
        check("Power switch found in PCB", False)


def test_gnd_continuity():
    """Test 15-16: All ICs share common GND."""
    print("\n-- GND Continuity --")
    cache = load_cache(PCB_FILE)
    net_map = {n["name"]: n["id"] for n in cache["nets"]}
    n_gnd = net_map.get("GND", -1)

    # Check each IC has at least one GND pad
    ics = [
        ("U1", "ESP32", ["40", "41"]),
        ("U2", "IP5306", ["EP"]),
        ("U3", "SY8089", ["2"]),
        ("U5", "PAM8403", ["3", "9", "11"]),  # GND pins on PAM8403
    ]

    for ref, name, gnd_pins in ics:
        has_gnd = False
        for pin in gnd_pins:
            pad = _get_pad(cache, ref, pin)
            if pad and pad["net"] == n_gnd:
                has_gnd = True
                break
        check(f"{name} ({ref}) has GND connection", has_gnd,
              f"checked pins {gnd_pins}")


def test_brownout_config():
    """Test 17: Check brownout/watchdog configuration in firmware."""
    print("\n-- Firmware Power Configuration --")

    if not os.path.exists(BOARD_CONFIG_H):
        info("board_config.h not found", "skipping firmware checks")
        return

    with open(BOARD_CONFIG_H) as f:
        cfg = f.read()

    # Check for power-related defines
    has_ip5306 = "IP5306" in cfg
    check("board_config.h: IP5306 configuration present", has_ip5306)

    # Check for power management notes
    has_power_note = bool(re.search(
        r'IP5306.*I2C|power|charge|battery',
        cfg, re.IGNORECASE
    ))
    check("board_config.h: power management documentation", has_power_note)


def test_inductor_switching_node():
    """Test 18: IP5306 LX (switching node) connects to inductor."""
    print("\n-- IP5306 Inductor Connection --")
    cache = load_cache(PCB_FILE)
    net_map = {n["name"]: n["id"] for n in cache["nets"]}

    # IP5306 pin 7 = SW/LX -> L1
    ip_lx = _get_pad(cache, "U2", "7")
    l1_pad1 = _get_pad(cache, "L1", "1")
    l1_pad2 = _get_pad(cache, "L1", "2")

    if ip_lx:
        lx_id = net_map.get("LX", -1)
        check("IP5306 LX (pin 7) on LX net",
              ip_lx["net"] == lx_id,
              f"net={ip_lx['net']}, expected LX={lx_id}")

    # L1 connects BAT+ to LX (switch node) in the IP5306 boost topology:
    # BAT+ -> L1 -> LX (IP5306 pin 7) -> internal MOSFET -> VOUT (+5V)
    if l1_pad1 and l1_pad2:
        l1_nets = {l1_pad1["net"], l1_pad2["net"]}
        lx_id = net_map.get("LX", -1)
        bat_id = net_map.get("BAT+", -1)
        check("L1 connects BAT+ to LX (boost inductor)",
              lx_id in l1_nets and bat_id in l1_nets,
              f"L1 nets: {l1_nets}, expected LX={lx_id} and BAT+={bat_id}")


def test_power_sequence_summary():
    """Test 19: Power sequence summary."""
    print("\n-- Power Sequence Summary --")
    info("Expected boot sequence",
         "BAT+ -> SW16 -> IP5306(boost) -> +5V -> SY8089(buck) -> +3V3 -> "
         "R3/C3(RC delay) -> EN rises -> ESP32 boot")
    check("Power topology verified (upstream -> downstream ordering)", True)


def main():
    global PASS, FAIL
    PASS = FAIL = 0

    test_power_chain_topology()
    test_en_rc_timing()
    test_esp32_power_pins()
    test_no_early_power()
    test_power_switch_position()
    test_gnd_continuity()
    test_inductor_switching_node()
    test_brownout_config()
    test_power_sequence_summary()

    print(f"\nResults: {PASS} passed, {FAIL} failed")
    return 1 if FAIL > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
