#!/usr/bin/env python3
"""Via-in-Pad Comprehensive Check — via holes must clear SMD pad edges.

Vias whose HOLE touches or crosses an SMD pad edge cause solder wicking
during reflow (solder drains into the barrel — starved joint), and JLC's
SMT DFM flags every one as a "Lead to hole distance 0mm" DANGER: the
2026-08-03 JLCDFM report counted 18 of them, all same-net vias placed on
or grazing bottom-side pads.

Rules (distance-based, on the HOLE, not the via centre — the old
centre-containment test missed 4 of the 18 because the via centre sat
outside the pad while the hole still crossed its edge):
  - Different-net via hole inside/near a pad: FAIL (short circuit risk)
  - ANY via hole closer than MIN_HOLE_TO_PAD to an SMD pad boundary:
    FAIL. No count threshold and no intentional-list: a thermal via
    belongs >= MIN_HOLE_TO_PAD outside the pad, connected by a stub.

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

# JLC flags any hole touching a pad (0mm). Keep the hole edge at least
# this far outside the pad boundary so paste/joint stay intact.
MIN_HOLE_TO_PAD = 0.15


def _hole_pad_gap(via, pad):
    """Distance from the via HOLE edge to the pad's bounding box.

    Negative = the hole overlaps the pad outline; 0 = touching.
    """
    half_w = pad["w"] / 2
    half_h = pad["h"] / 2
    dx = max(abs(via["x"] - pad["x"]) - half_w, 0.0)
    dy = max(abs(via["y"] - pad["y"]) - half_h, 0.0)
    outside = (dx * dx + dy * dy) ** 0.5
    if outside > 0:
        return outside - via["drill"] / 2
    # centre inside the pad: negative penetration depth
    pen_x = half_w - abs(via["x"] - pad["x"])
    pen_y = half_h - abs(via["y"] - pad["y"])
    return -min(pen_x, pen_y) - via["drill"] / 2


def analyze_via_in_pad(cache):
    """Check all via holes against all SMD pads. Returns categorized results."""
    vias = cache["vias"]
    smd_pads = [p for p in cache["pads"] if p["type"] == "smd"]

    same_net = []
    diff_net = []

    for via in vias:
        for pad in smd_pads:
            gap = _hole_pad_gap(via, pad)
            if gap >= MIN_HOLE_TO_PAD:
                continue

            entry = {
                "via_x": via["x"],
                "via_y": via["y"],
                "via_net": via["net"],
                "via_size": via["size"],
                "gap": round(gap, 3),
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

    def test_same_net_hole_clearance(self):
        """Every via hole must clear every SMD pad edge by MIN_HOLE_TO_PAD."""
        if self.same_net:
            details = [
                f"  via at ({v['via_x']},{v['via_y']}) hole gap "
                f"{v['gap']}mm to {v['pad_ref']}.{v['pad_num']}"
                for v in self.same_net[:8]
            ]
            self.fail(
                f"{len(self.same_net)} via hole(s) within {MIN_HOLE_TO_PAD}mm "
                f"of an SMD pad edge (JLC 'lead to hole' DANGER):\n"
                + "\n".join(details)
            )


def main(diff_net_only=False):
    """diff_net_only: exit code reflects only the short-circuit class —
    used by verify_isolation.py, whose verdict must mean 'shorted', not
    'solderability'. The full run (default, in verify-all) fails on both."""
    cache = load_cache(PCB_FILE)
    net_map = {n["id"]: n["name"] for n in cache["nets"]}
    same_net, diff_net = analyze_via_in_pad(cache)

    print("\n── Via-in-Pad Check ──")
    print(f"  SMD pads checked: {len([p for p in cache['pads'] if p['type'] == 'smd'])}")
    print(f"  Vias checked: {len(cache['vias'])}")

    rc = 0
    if diff_net:
        rc = 1
        print(f"  FAIL  {len(diff_net)} different-net via-in-pad(s) (SHORT CIRCUIT RISK):")
        for v in diff_net:
            vnet = net_map.get(v["via_net"], f"#{v['via_net']}")
            pnet = net_map.get(v["pad_net"], f"#{v['pad_net']}")
            print(
                f"        via({vnet}) in {v['pad_ref']}.{v['pad_num']}({pnet}) "
                f"at ({v['via_x']}, {v['via_y']}) gap={v['gap']}mm"
            )
    else:
        print("  PASS  No different-net via-in-pad violations")

    if same_net:
        if not diff_net_only:
            rc = 1
        tag = "WARN " if diff_net_only else "FAIL "
        print(f"  {tag} {len(same_net)} via hole(s) within {MIN_HOLE_TO_PAD}mm of an "
              f"SMD pad edge (JLC 'lead to hole' DANGER — move the via, "
              f"do not whitelist it):")
        for v in sorted(same_net, key=lambda e: e["gap"]):
            vnet = net_map.get(v["via_net"], f"#{v['via_net']}")
            print(
                f"        {v['pad_ref']}.{v['pad_num']} ({vnet}) "
                f"via at ({v['via_x']}, {v['via_y']}) hole gap {v['gap']}mm"
            )
    else:
        print(f"  PASS  Every via hole clears every SMD pad by >= {MIN_HOLE_TO_PAD}mm")
    return rc


if __name__ == "__main__":
    if "--test" in sys.argv:
        sys.argv = [sys.argv[0]]
        unittest.main()
    else:
        sys.exit(main(diff_net_only="--diff-net-only" in sys.argv))
