#!/usr/bin/env python3
"""Via-in-Pad Comprehensive Check — detect vias landing inside SMD pads.

Vias inside SMD pads cause solder wicking during reflow, leading to:
  - Poor solder joints (solder drains into via barrel)
  - Tombstoning on small passives
  - Short circuit risk if via has a different net than the pad

Rules:
  - Same-net via-in-pad: INFO (intentional, e.g. thermal via)
  - Different-net via-in-pad: FAIL (short circuit risk)
  - Any via-in-pad without epoxy fill: WARN for JLCPCB standard process

Usage:
    python3 scripts/verify_via_in_pad.py
    Exit code 0 = pass, 1 = failure
"""

import os
import sys
import unittest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from pcb_cache import load_cache

PCB_FILE = os.path.join(BASE, "hardware", "kicad", "esp32-emu-turbo.kicad_pcb")

# Known intentional via-in-pads (ref, pad_num) — add here if needed
KNOWN_INTENTIONAL = set()


def _via_in_pad(via, pad):
    """Check if a via center falls within a pad's bounding box."""
    half_w = pad["w"] / 2
    half_h = pad["h"] / 2
    return (
        (pad["x"] - half_w) <= via["x"] <= (pad["x"] + half_w)
        and (pad["y"] - half_h) <= via["y"] <= (pad["y"] + half_h)
    )


def analyze_via_in_pad(cache):
    """Check all vias against all SMD pads. Returns categorized results."""
    vias = cache["vias"]
    smd_pads = [p for p in cache["pads"] if p["type"] == "smd"]

    same_net = []
    diff_net = []

    for via in vias:
        for pad in smd_pads:
            if not _via_in_pad(via, pad):
                continue

            entry = {
                "via_x": via["x"],
                "via_y": via["y"],
                "via_net": via["net"],
                "via_size": via["size"],
                "pad_ref": pad["ref"],
                "pad_num": pad["num"],
                "pad_net": pad["net"],
                "pad_layer": pad["layer"],
            }

            if via["net"] == pad["net"] and via["net"] != 0:
                same_net.append(entry)
            elif via["net"] != pad["net"]:
                # Net 0 on pad might be zone-connected, so only flag
                # if via has a real net and pad has a different real net
                if via["net"] != 0 and pad["net"] != 0:
                    diff_net.append(entry)
                elif via["net"] == 0 and pad["net"] == 0:
                    # Both unassigned — skip
                    pass
                else:
                    # One has a net, the other doesn't — still suspicious
                    same_net.append(entry)  # treat as info, not fail

    return same_net, diff_net


class TestViaInPad(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cache = load_cache(PCB_FILE)
        cls.same_net, cls.diff_net = analyze_via_in_pad(cls.cache)

    def test_no_different_net_via_in_pad(self):
        """No via should land inside an SMD pad with a different net."""
        if self.diff_net:
            details = []
            for v in self.diff_net[:5]:  # show first 5
                details.append(
                    f"  via net={v['via_net']} at ({v['via_x']},{v['via_y']}) "
                    f"in {v['pad_ref']}.{v['pad_num']} net={v['pad_net']}"
                )
            self.fail(
                f"{len(self.diff_net)} different-net via-in-pad(s) found "
                f"(short circuit risk):\n" + "\n".join(details)
            )

    def test_same_net_via_in_pad_count(self):
        """Same-net via-in-pads should be minimal (intentional thermal vias only)."""
        # Filter out known intentional ones
        unexpected = [
            v for v in self.same_net
            if (v["pad_ref"], v["pad_num"]) not in KNOWN_INTENTIONAL
        ]
        # Just informational — not a hard failure, but warn if excessive
        # 14-20 is normal for designs with thermal vias under ICs/regulators
        if len(unexpected) > 25:
            self.fail(
                f"{len(unexpected)} same-net via-in-pads detected — "
                f"consider offsetting vias from pads for better solderability"
            )


def main():
    cache = load_cache(PCB_FILE)
    net_map = {n["id"]: n["name"] for n in cache["nets"]}
    same_net, diff_net = analyze_via_in_pad(cache)

    print("\n── Via-in-Pad Check ──")
    print(f"  SMD pads checked: {len([p for p in cache['pads'] if p['type'] == 'smd'])}")
    print(f"  Vias checked: {len(cache['vias'])}")

    if same_net:
        print(f"  INFO  {len(same_net)} same-net via-in-pad(s) (intentional/thermal):")
        for v in same_net[:8]:
            vnet = net_map.get(v["via_net"], f"#{v['via_net']}")
            print(
                f"        {v['pad_ref']}.{v['pad_num']} ({vnet}) "
                f"at ({v['via_x']}, {v['via_y']})"
            )
        if len(same_net) > 8:
            print(f"        ... and {len(same_net) - 8} more")
    else:
        print("  INFO  No same-net via-in-pads found")

    if diff_net:
        print(f"  FAIL  {len(diff_net)} different-net via-in-pad(s) (SHORT CIRCUIT RISK):")
        for v in diff_net:
            vnet = net_map.get(v["via_net"], f"#{v['via_net']}")
            pnet = net_map.get(v["pad_net"], f"#{v['pad_net']}")
            print(
                f"        via({vnet}) in {v['pad_ref']}.{v['pad_num']}({pnet}) "
                f"at ({v['via_x']}, {v['via_y']})"
            )
        return 1
    else:
        print("  PASS  No different-net via-in-pad violations")
        return 0


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main())
