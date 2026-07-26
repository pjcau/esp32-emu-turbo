#!/usr/bin/env python3
"""Mutation tests for the via clearance checker in generate_pcb/collision.py.

An assertion that has never fired is not evidence, so every test here plants a
specific geometry and requires the checker to reach a specific verdict. Half of
them plant a REAL breach and require it to be caught; the other half plant the
exact false positive this checker used to produce and require silence.

The bug being guarded against
-----------------------------
Vias enter the spatial index as their bounding SQUARE, which is correct for
indexing and wrong for measuring: for two vias offset diagonally the square
corners face each other and the gap comes out smaller than the real one. That
approximated ring-to-ring number was then compared against CLEARANCE_VIA_VIA,
which is the DRILL rule. Every generation reported 14 via-to-via violations
whose true hole gaps were 0.55-0.67 mm against a 0.25 mm limit — a report that
is always wrong is a report nobody reads, which is how a real violation gets
through.

Run: python3 scripts/test_collision_via_metric.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.generate_pcb.collision import (  # noqa: E402
    CLEARANCE_VIA_VIA,
    CLEARANCE_VIA_VIA_COPPER,
    JLCPCB_COPPER_MIN,
    CollisionGrid,
    _hard_minimum,
    _via_pair_gaps,
)


def grid_with_via(x, y, net, size, drill):
    g = CollisionGrid()
    g.add_via(x, y, net=net, size=size, drill=drill)
    return g


class ViaPairGeometry(unittest.TestCase):
    """The measurement itself, before any rule is applied."""

    def test_gaps_are_measured_between_circles_not_squares(self):
        # The worst real pair on this board: 0.7 mm apart in X, 0.28 in Y,
        # both 0.5 mm ring / 0.2 mm drill.
        cop, hole = _via_pair_gaps(136.60, 22.20, 0.5, 0.2,
                                   137.30, 22.48, 0.5, 0.2)
        self.assertAlmostEqual(cop, 0.2539, places=3)
        self.assertAlmostEqual(hole, 0.5539, places=3)
        # The square approximation this replaced reported 0.200 for the same
        # pair. If someone reintroduces it, cop lands there and this fails.
        self.assertGreater(cop, 0.24,
                           "ring gap collapsed toward the square-AABB value")

    def test_hole_gap_is_always_wider_than_copper_gap(self):
        cop, hole = _via_pair_gaps(0, 0, 0.9, 0.35, 1.5, 0, 0.9, 0.35)
        self.assertGreater(hole, cop,
                           "a drill is smaller than its annular ring, so the "
                           "hole gap cannot be the tighter of the two")


class RealBreachesAreCaught(unittest.TestCase):
    """Plant a genuine violation; the checker must report it."""

    def test_hole_to_hole_breach_is_reported(self):
        # Centres 0.5 mm apart, 0.35 mm drills -> hole gap 0.15 mm < 0.25.
        g = grid_with_via(10.0, 10.0, net=1, size=0.45, drill=0.35)
        v = g.check_via(10.5, 10.0, net=2, size=0.45, drill=0.35)
        self.assertTrue(v, "a 0.15 mm hole gap must breach the 0.25 mm rule")
        self.assertAlmostEqual(v[0].required_mm, CLEARANCE_VIA_VIA, places=4)
        self.assertLess(v[0].gap_mm, CLEARANCE_VIA_VIA)

    def test_copper_breach_is_reported_when_holes_are_fine(self):
        # Big rings, tiny drills: copper touches while the holes stay far
        # apart, so only the copper rule may fire.
        g = grid_with_via(10.0, 10.0, net=1, size=0.9, drill=0.2)
        v = g.check_via(11.0, 10.0, net=2, size=0.9, drill=0.2)
        self.assertTrue(v, "a 0.10 mm ring gap must breach the copper rule")
        self.assertAlmostEqual(v[0].required_mm, CLEARANCE_VIA_VIA_COPPER,
                               places=4)

    def test_same_net_vias_are_never_a_violation(self):
        g = grid_with_via(10.0, 10.0, net=7, size=0.9, drill=0.35)
        self.assertEqual(g.check_via(10.2, 10.0, net=7, size=0.9, drill=0.35),
                         [], "two vias on the same net cannot short")


class FalsePositivesStaySilent(unittest.TestCase):
    """Plant the exact geometry that used to be misreported."""

    def test_the_diagonal_pair_that_used_to_be_reported_is_clean(self):
        # Verbatim from the board: reported 0.200 mm against the 0.25 mm DRILL
        # rule for months. True copper 0.254, true hole 0.554 — breaches
        # neither.
        g = grid_with_via(136.60, 22.20, net=8, size=0.5, drill=0.2)
        v = g.check_via(137.30, 22.48, net=7, size=0.5, drill=0.2)
        self.assertEqual(
            v, [],
            "the diagonal via pair breaches no rule and must not be reported; "
            "if this fires, the square-AABB measurement is back")

    def test_ring_gap_is_not_judged_against_the_drill_rule(self):
        # Rings 0.20 mm apart — under CLEARANCE_VIA_VIA (0.25) but over the
        # copper limit (0.175). Judging copper by the drill rule is precisely
        # the conflation that produced the noise.
        g = grid_with_via(10.0, 10.0, net=1, size=0.5, drill=0.2)
        v = g.check_via(10.7, 10.0, net=2, size=0.5, drill=0.2)
        self.assertEqual(
            v, [],
            "0.20 mm of copper clears the 0.175 mm copper rule; only the "
            "drill rule is 0.25 and it applies to drills")


class SeverityIsSeparated(unittest.TestCase):
    """Below the house target and below the manufacturer floor differ."""

    def test_house_margin_is_above_the_manufacturer_floor(self):
        self.assertGreater(CLEARANCE_VIA_VIA_COPPER, JLCPCB_COPPER_MIN,
                           "the house target must leave room, or the split "
                           "between margin and breach is meaningless")

    def test_copper_rules_fall_back_to_the_manufacturer_floor(self):
        self.assertEqual(_hard_minimum(CLEARANCE_VIA_VIA_COPPER),
                         JLCPCB_COPPER_MIN)

    def test_drill_and_edge_rules_have_no_softer_floor(self):
        # These are the manufacturer's own numbers, not a house margin on top
        # of one, so nothing may relax them.
        self.assertEqual(_hard_minimum(CLEARANCE_VIA_VIA), CLEARANCE_VIA_VIA)


if __name__ == "__main__":
    unittest.main(verbosity=2)
