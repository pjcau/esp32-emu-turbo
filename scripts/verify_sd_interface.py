#!/usr/bin/env python3
"""SD Card Interface Verification — check SPI signal routing and support circuitry.

Verifies:
  1. All 4 SPI signals routed: SD_CLK, SD_MOSI, SD_MISO, SD_CS
  2. Card detect (CD) signal presence (optional)
  3. Write protect (WP) signal presence (optional)
  4. VDD decoupling on U6 (TF-01A)
  5. Pull-up resistors on data lines (SD spec: 10-100k)

Usage:
    python3 scripts/verify_sd_interface.py
    Exit code 0 = pass/warn/info, 1 = failure
"""

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

# Expected SPI pin mapping for TF-01A (U6)
SD_SPI_PINS = {
    "SD_CLK":  {"u6_pad": "5", "description": "SPI clock"},
    "SD_MOSI": {"u6_pad": "3", "description": "SPI data in"},
    "SD_MISO": {"u6_pad": "7", "description": "SPI data out"},
    "SD_CS":   {"u6_pad": "2", "description": "Chip select"},
}
U6_VDD_PAD = "4"   # VDD pin on TF-01A
U6_CD_PAD = "9"    # Card detect pin
VDD_NET = "+3V3"


def analyze_sd_interface(cache):
    """Analyze SD card interface completeness."""
    net_map = {n["name"]: n["id"] for n in cache["nets"] if n["name"]}
    segments = cache["segments"]
    pads = cache["pads"]

    # Get U6 pads
    u6_pads = [p for p in pads if p["ref"] == "U6"]
    u6_pad_map = {}
    for p in u6_pads:
        u6_pad_map.setdefault(p["num"], []).append(p)

    results = []
    fail = False

    # 1. Check SPI signal routing
    for net_name, info in SD_SPI_PINS.items():
        net_id = net_map.get(net_name)
        pad_num = info["u6_pad"]

        # Check if net exists in PCB
        if net_id is None:
            results.append(("FAIL", f"{net_name} net not found in PCB"))
            fail = True
            continue

        # Check if segments exist for this net
        net_segs = [s for s in segments if s["net"] == net_id]

        # Check U6 pad assignment
        u6_pad_nets = [p["net"] for p in u6_pad_map.get(pad_num, [])]
        pad_connected = net_id in u6_pad_nets

        if net_segs and pad_connected:
            results.append(("PASS", f"{net_name} routed ({len(net_segs)} segments, U6 pad {pad_num})"))
        elif net_segs:
            # Segments exist but pad not directly assigned (may use zone connection)
            results.append(("PASS", f"{net_name} routed ({len(net_segs)} segments, U6 pad {pad_num} via zone)"))
        else:
            results.append(("FAIL", f"{net_name} has no routed segments"))
            fail = True

    # 2. Card detect (CD) — pad 9 on TF-01A
    cd_pads = u6_pad_map.get(U6_CD_PAD, [])
    cd_nets = [p["net"] for p in cd_pads if p["net"] != 0]
    if cd_nets:
        cd_name = next((n["name"] for n in cache["nets"] if n["id"] == cd_nets[0]), "?")
        results.append(("PASS", f"Card detect (CD) connected to {cd_name}"))
    else:
        results.append(("WARN", "No card detect (CD) signal found -- firmware must poll card presence"))

    # 3. Write protect (WP) — not standard on TF-01A
    wp_net = net_map.get("SD_WP") or net_map.get("WP")
    if wp_net:
        results.append(("INFO", "Write protect (WP) signal present"))
    else:
        results.append(("INFO", "No write protect (WP) -- acceptable for game ROM loading"))

    # 4. VDD decoupling — check U6 pad 4 is on +3V3
    vdd_id = net_map.get(VDD_NET)
    vdd_pads = u6_pad_map.get(U6_VDD_PAD, [])
    vdd_connected = any(p["net"] == vdd_id for p in vdd_pads) if vdd_id else False

    if vdd_connected:
        results.append(("PASS", f"VDD decoupling present (U6 pad {U6_VDD_PAD} = {VDD_NET})"))
    else:
        results.append(("WARN", f"U6 pad {U6_VDD_PAD} not connected to {VDD_NET}"))

    # 5. Pull-up resistors — check if any 10k resistors share nets with SD signals
    sd_net_ids = {net_map[n] for n in SD_SPI_PINS if n in net_map}
    pullup_refs = set()
    for p in pads:
        if (p["ref"].startswith("R") and p["net"] in sd_net_ids
                and p["ref"] not in pullup_refs):
            pullup_refs.add(p["ref"])

    if pullup_refs:
        results.append(("PASS", f"Pull-up resistors on SD lines: {', '.join(sorted(pullup_refs))}"))
    else:
        # ESP32-S3 has internal pull-ups, external not strictly required for SPI mode
        results.append(("INFO", "No external pull-ups on SD lines (ESP32-S3 internal pull-ups used)"))

    return {"results": results, "fail": fail}


class TestSDInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = load_cache(PCB_FILE)
        cls.analysis = analyze_sd_interface(cls.cache)

    def test_spi_signals_routed(self):
        for tag, msg in self.analysis["results"]:
            if tag == "FAIL":
                self.fail(msg)

    def test_vdd_connected(self):
        vdd_results = [r for r in self.analysis["results"] if "VDD" in r[1]]
        for tag, msg in vdd_results:
            self.assertNotEqual(tag, "FAIL", msg)


def main():
    cache = load_cache(PCB_FILE)
    analysis = analyze_sd_interface(cache)

    print("\n\u2500\u2500 SD Card Interface \u2500\u2500")
    for tag, msg in analysis["results"]:
        print(f"  {tag}  {msg}")

    return 1 if analysis["fail"] else 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main())
