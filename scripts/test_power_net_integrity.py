#!/usr/bin/env python3
"""Regression tests for the power-net integrity detector.

The bug being guarded against: PCB v1 shipped with the ``In2.Cu`` ``+3V3``
plane carved into 4 electrically separate groups by two higher-priority
``+5V`` zones. The regulator fed a 4.92 mm² orphan island; the board was dead.
See website/docs/rework/incident-3v3-split-plane.md.

Two classes of test:

  Synthetic  — hand-built copper geometry that reproduces the split-plane
               topology exactly. These are deterministic and stay valid no
               matter what happens to the layout.
  Control    — the real board. GND and +5V must resolve to exactly ONE group.
               This is the false-positive guard: it must hold both before and
               after the layout fix lands. If a future change makes the
               detector report a split on GND, the detector is wrong, not the
               board.

Deliberately NOT tested: "+3V3 currently has 4 groups". That is true today and
must become false when the layout is fixed — asserting it would turn the fix
into a test failure.

Usage:
    python3 scripts/test_power_net_integrity.py
    python3 -m unittest scripts.test_power_net_integrity
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from shapely.geometry import Polygon  # noqa: E402

import pcb_copper_graph as G  # noqa: E402
import verify_power_net_integrity as V  # noqa: E402


# ── Synthetic geometry builders ─────────────────────────────────────

def zone(net, layer, rects, priority=0):
    """A pour zone whose FILL is the given list of (x0, y0, x1, y1) islands."""
    return {
        "net": net,
        "layer": layer,
        "priority": priority,
        "polys": [Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
                  for x0, y0, x1, y1 in rects],
    }


def via(net, x, y, size=0.6):
    return {"net": net, "x": x, "y": y, "size": size}


def seg(net, x1, y1, x2, y2, layer="F.Cu", w=0.25):
    return {"net": net, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "w": w, "layer": layer}


def fp(ref, layer, pads):
    """pads: list of (num, x, y, net) — 0.6 mm square SMD pads."""
    return {
        "ref": ref, "x": 0.0, "y": 0.0, "layer": layer,
        "pads": [{"num": n, "x": x, "y": y, "w": 0.6, "h": 0.6,
                  "net": net, "thru": False} for n, x, y, net in pads],
    }


def geometry(zones=(), vias=(), segs=(), fps=()):
    return G.CopperGeometry(list(zones), list(vias), list(segs), list(fps))


# ── Synthetic detector tests ────────────────────────────────────────

class TestDetectorOnSyntheticCopper(unittest.TestCase):
    """The detector's logic, on geometry we fully control."""

    def test_continuous_plane_is_one_group(self):
        """A single poured island with pads on it is ONE group."""
        geom = geometry(
            zones=[zone("+3V3", "In2.Cu", [(0, 0, 100, 50)])],
            vias=[via("+3V3", 10, 10), via("+3V3", 90, 40)],
            fps=[fp("U3", "F.Cu", [("2", 10, 10, "+3V3")]),
                 fp("U1", "F.Cu", [("2", 90, 40, "+3V3")])],
        )
        self.assertEqual(len(G.groups_for("+3V3", geom)), 1)

    def test_split_plane_is_detected(self):
        """THE REGRESSION.

        A higher-priority zone carved the plane in two. The source pad (U3,
        the regulator) sits on the small island; every load sits on the big
        one. No trace bridges the gap. That is PCB v1, and it must FAIL.
        """
        geom = geometry(
            zones=[
                # +3V3 fill, already carved: main plane + orphan island
                zone("+3V3", "In2.Cu",
                     [(0, 0, 80, 50), (90, 20, 95, 25)], priority=0),
                # the +5V zone that did the carving, at higher priority
                zone("+5V", "In2.Cu", [(80, 0, 100, 50)], priority=1),
            ],
            # every pad drops a via into the plane, as on the real board
            vias=[via("+3V3", 92.5, 22.5), via("+3V3", 40, 25),
                  via("+3V3", 20, 10)],
            fps=[
                fp("U3", "F.Cu", [("2", 92.5, 22.5, "+3V3")]),   # regulator
                fp("U1", "F.Cu", [("2", 40, 25, "+3V3")]),       # ESP32
                fp("J4", "F.Cu", [("3", 20, 10, "+3V3")]),       # display
            ],
        )
        groups = G.groups_for("+3V3", geom)
        self.assertEqual(len(groups), 2,
                         "split plane must resolve to 2 electrical groups")
        # largest first
        self.assertGreater(len(groups[0]), len(groups[1]))
        self.assertEqual(G.group_pads(groups[0]), ["J4.3", "U1.2"])
        self.assertEqual(G.group_pads(groups[1]), ["U3.2"])

    def test_split_plane_fails_the_gate(self):
        """check_net() turns that geometry into a FAIL with actionable text."""
        geom = geometry(
            zones=[zone("+3V3", "In2.Cu", [(0, 0, 80, 50), (90, 20, 95, 25)])],
            vias=[via("+3V3", 92.5, 22.5), via("+3V3", 40, 25)],
            fps=[fp("U3", "F.Cu", [("2", 92.5, 22.5, "+3V3")]),
                 fp("U1", "F.Cu", [("2", 40, 25, "+3V3")])],
        )
        ok, groups, lines = V.check_net("+3V3", geom)
        self.assertFalse(ok)
        self.assertEqual(len(groups), 2)
        report = "\n".join(lines)
        self.assertIn("FAIL", report)
        self.assertIn("U3.2", report)          # which pad is stranded
        self.assertIn("mm²", report)           # island area
        self.assertIn("mm", report)            # distance from the main group

    def test_via_stitches_layers_together(self):
        """A via joins an inner-layer island to a top-layer pad."""
        geom = geometry(
            zones=[zone("+3V3", "In2.Cu", [(0, 0, 50, 50)])],
            vias=[via("+3V3", 25, 25)],
            fps=[fp("U1", "F.Cu", [("2", 25, 25, "+3V3")])],
        )
        self.assertEqual(len(G.groups_for("+3V3", geom)), 1)

    def test_overlap_without_shared_layer_is_not_a_connection(self):
        """Copper that overlaps in 2D but lives on different layers with no
        via is NOT connected — the check is layer-aware."""
        geom = geometry(
            zones=[zone("+3V3", "In2.Cu", [(0, 0, 50, 50)])],
            segs=[seg("+3V3", 10, 10, 40, 40, layer="F.Cu")],
        )
        self.assertEqual(len(G.groups_for("+3V3", geom)), 2)

    def test_other_nets_are_ignored(self):
        """Copper on a different net never joins this net's groups."""
        geom = geometry(
            zones=[zone("+3V3", "In2.Cu", [(0, 0, 40, 40)]),
                   zone("GND", "In1.Cu", [(0, 0, 40, 40)])],
            fps=[fp("U1", "F.Cu", [("2", 20, 20, "+3V3"),
                                   ("41", 21, 20, "GND")])],
        )
        self.assertEqual(len(G.groups_for("+3V3", geom)), 2)  # pad + island
        gnd_pads = {p for g in G.groups_for("GND", geom)
                    for p in G.group_pads(g)}
        self.assertEqual(gnd_pads, {"U1.41"})

    def test_missing_net_fails_instead_of_passing_silently(self):
        """A power net with no copper at all is a FAIL, not a vacuous PASS.

        Without this, renaming a net in the generator would silently disarm
        the gate for that net — exactly the failure mode this whole file
        exists to prevent.
        """
        ok, groups, lines = V.check_net("+12V", geometry())
        self.assertFalse(ok)
        self.assertEqual(groups, [])
        self.assertIn("NO copper", "\n".join(lines))

    def test_no_allowlist_exists(self):
        """The gate must not grow an allowlist of 'accepted' fragmentations.

        Every previous connectivity check in this repo was defeated by one.
        """
        for name in dir(V):
            self.assertNotIn(
                "ACCEPT", name.upper(),
                f"verify_power_net_integrity.{name} looks like an allowlist; "
                f"a split power net is an open circuit, never acceptable")


# ── Reporting helper tests ──────────────────────────────────────────

class TestReportingHelpers(unittest.TestCase):

    def setUp(self):
        self.geom = geometry(
            zones=[zone("+3V3", "In2.Cu", [(0, 0, 10, 10), (20, 0, 22, 5)])],
            vias=[via("+3V3", 5, 5), via("+3V3", 21, 2.5)],
            fps=[fp("U1", "F.Cu", [("2", 5, 5, "+3V3")]),
                 fp("U3", "F.Cu", [("2", 21, 2.5, "+3V3")])],
        )
        self.groups = G.groups_for("+3V3", self.geom)

    def test_area_is_the_poured_island_area(self):
        self.assertAlmostEqual(G.group_area(self.groups[0]), 100.0, places=3)
        self.assertAlmostEqual(G.group_area(self.groups[1]), 10.0, places=3)

    def test_island_gap_is_the_pour_gap(self):
        # islands are 10..20 in x -> 10 mm gap
        self.assertAlmostEqual(
            G.group_island_distance(self.groups[1], self.groups[0]),
            10.0, places=3)

    def test_distance_of_empty_geometry_is_nan(self):
        d = G._min_distance([], [Polygon([(0, 0), (1, 0), (1, 1)])])
        self.assertNotEqual(d, d)  # NaN


# ── Control tests on the real board ─────────────────────────────────

class TestRealBoardControl(unittest.TestCase):
    """False-positive guard. Must hold before AND after the layout fix."""

    @classmethod
    def setUpClass(cls):
        if not G.DEFAULT_PCB.exists():
            raise unittest.SkipTest(f"{G.DEFAULT_PCB} not found")
        cls.geom = G.parse_copper()

    def test_gnd_is_one_group(self):
        groups = G.groups_for("GND", self.geom)
        self.assertEqual(
            len(groups), 1,
            "GND is a continuous In1.Cu plane on this board — if the detector "
            "reports a split here it is producing false positives")

    def test_5v_is_one_group(self):
        groups = G.groups_for("+5V", self.geom)
        self.assertEqual(len(groups), 1, "+5V is the carving zone, not split")

    def test_power_nets_all_exist_on_the_board(self):
        """Every net the gate checks must actually be present, or the gate is
        silently checking nothing."""
        for net in V.POWER_NETS:
            with self.subTest(net=net):
                self.assertTrue(
                    G.groups_for(net, self.geom),
                    f"{net} carries no copper — gate would pass vacuously")

    def test_detector_matches_the_incident_report(self):
        """Cross-check against the numbers recorded in the incident writeup.

        This asserts the DETECTOR reproduces the documented measurement, not
        that the board is still broken — it is skipped once +3V3 is fixed.
        """
        groups = G.groups_for("+3V3", self.geom)
        if len(groups) == 1:
            self.skipTest("+3V3 layout has been fixed — nothing to cross-check")
        pads = {p for g in groups[1:] for p in G.group_pads(g)}
        self.assertEqual(pads, {"C2.1", "U3.2", "U3.4",
                                "J4.29", "J4.34", "J4.35"})
        regulator = next(g for g in groups if "U3.2" in G.group_pads(g))
        self.assertAlmostEqual(G.group_area(regulator), 4.92, places=1)
        self.assertAlmostEqual(
            G.group_island_distance(regulator, groups[0]), 12.1, places=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
