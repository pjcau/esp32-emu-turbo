#!/usr/bin/env python3
"""Mutation tests for the pad side of generate_pcb/collision.py.

The bug being guarded against
-----------------------------
A pad only learned its net when a trace endpoint landed on it, and pads at
net 0 were SKIPPED in collision queries. That made the detector
default-OPEN: a pad the router never targets never acquired a net, stayed
invisible for the whole run, and a trace could be laid straight across it
with nothing reported. Only the post-hoc gates (verify_trace_through_pad,
short_circuit_analysis, analyze_pad_distances) stood behind it.

The fix has three moving parts, and each one is planted against here:

1.  `routing.generate_all_traces` routes TWICE — a discovery pass whose
    output is discarded, then the emitted pass, seeded from the pad->net
    map the first pass produced. That is only legitimate because routing is
    idempotent and collision results never steer the router, so the two
    passes must be provably byte-identical and the UUID counter must come
    back to where it started.
2.  net 0 no longer means "not known yet", it means "unconnected copper",
    and unconnected copper is a thing nothing may overlap.
3.  which side a pad is on is DERIVED from the placements, not remembered
    in a literal set. The set that used to do it omitted the three
    fiducials, so F.Cu fiducials were modelled on B.Cu, where the
    BTN_START track at x=12.20 passes through FID3 — a 0.425 mm "overlap"
    that is not on the board at all. That artefact was invisible only
    because net-0 pads were being skipped; closing one default exposed the
    other.

Run: python3 scripts/test_collision_pad_nets.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.generate_pcb import primitives as P            # noqa: E402
from scripts.generate_pcb.collision import CollisionGrid    # noqa: E402
from scripts.generate_pcb.pad_positions import (            # noqa: E402
    get_pads_and_layers,
)

_UUID_RE = re.compile(r'"[0-9a-f]{8}-dead-4000-a000-[0-9a-f]{12}"')


class NetZeroPadsAreNotInvisible(unittest.TestCase):
    """Property 2: default-closed. An unnetted pad is an obstacle."""

    def _grid(self, pad_net):
        g = CollisionGrid()
        g.register_pads({"X1": {"1": (10.0, 10.0, 1.0, 1.0)}},
                        {("X1", "1"): pad_net} if pad_net else None,
                        {"X1": "B.Cu"})
        return g

    def test_a_trace_over_an_unnetted_pad_is_reported(self):
        g = self._grid(pad_net=0)
        v = g.check_segment(8.0, 10.0, 12.0, 10.0, "B.Cu", 0.25, net=7)
        self.assertTrue(
            v, "a trace laid straight over a net-0 pad was not reported — "
               "the detector is default-OPEN again")

    def test_a_trace_over_a_pad_on_another_net_is_still_reported(self):
        g = self._grid(pad_net=3)
        v = g.check_segment(8.0, 10.0, 12.0, 10.0, "B.Cu", 0.25, net=7)
        self.assertTrue(v, "a genuine different-net overlap went unreported")

    def test_a_trace_over_its_own_pad_is_silent(self):
        # The seed's other failure mode: a pad seeded with the WRONG net
        # reports its own connection as a short. Same-net must stay quiet.
        g = self._grid(pad_net=7)
        v = g.check_segment(8.0, 10.0, 12.0, 10.0, "B.Cu", 0.25, net=7)
        self.assertEqual(v, [], "a pad's own net reported as a collision")

    def test_a_pad_on_the_other_layer_is_not_an_obstacle(self):
        g = self._grid(pad_net=0)
        v = g.check_segment(8.0, 10.0, 12.0, 10.0, "F.Cu", 0.25, net=7)
        self.assertEqual(v, [], "a B.Cu pad blocked an F.Cu trace")


class PadSideIsDerivedNotRemembered(unittest.TestCase):
    """Property 3: the fiducial artefact cannot come back."""

    def test_placements_supply_a_side_for_every_ref_with_pads(self):
        pads, layers = get_pads_and_layers()
        missing = sorted(r for r in pads if r not in layers)
        self.assertEqual(missing, [],
                         f"no side derived for {missing} — register_pads "
                         "would silently default them to B.Cu")

    def test_the_fiducials_are_on_the_front(self):
        # The exact omission that produced the 0.425 mm FID3 phantom.
        _pads, layers = get_pads_and_layers()
        for fid in ("FID1", "FID2", "FID3"):
            self.assertEqual(layers.get(fid), "F.Cu",
                             f"{fid} is not modelled on F.Cu; the BTN_START "
                             "track at x=12.20 will report through it")

    def test_a_front_pad_does_not_block_a_back_trace(self):
        # FID3's real coordinates against BTN_START's real track.
        g = CollisionGrid()
        g.register_pads({"FID3": {"1": (12.0, 63.0, 1.0, 1.0)}}, None,
                        {"FID3": "F.Cu"})
        v = g.check_segment(12.20, 52.65, 12.20, 73.955, "B.Cu", 0.25, net=35)
        self.assertEqual(v, [], "the F.Cu fiducial is blocking B.Cu copper — "
                                "the side is being guessed again")

    def test_mislabelling_the_side_would_be_caught(self):
        # Plant the historical mistake and require it to be loud, so this
        # suite is measuring something rather than agreeing with itself.
        g = CollisionGrid()
        g.register_pads({"FID3": {"1": (12.0, 63.0, 1.0, 1.0)}}, None,
                        {"FID3": "B.Cu"})
        v = g.check_segment(12.20, 52.65, 12.20, 73.955, "B.Cu", 0.25, net=35)
        self.assertTrue(v, "the historical FID3 phantom no longer reproduces; "
                           "this test can no longer detect the regression")


class TwoPassRoutingIsSideEffectFree(unittest.TestCase):
    """Property 1: seeding must not move copper or shift a single uuid."""

    @classmethod
    def setUpClass(cls):
        from scripts.generate_pcb import routing
        cls.routing = routing
        cls.mark = P.uid_mark()
        cls.first = routing.generate_all_traces()
        cls.after_first = P.uid_mark()
        cls.pad_nets = routing.get_pad_nets()
        P.uid_restore(cls.mark)
        cls.second = routing.generate_all_traces()
        cls.after_second = P.uid_mark()

    def test_two_generations_are_byte_identical(self):
        self.assertEqual(
            self.first, self.second,
            "routing is not idempotent — the discovery pass would change the "
            "emitted board, and the seeding must be reverted")

    def test_the_uuid_counter_lands_in_the_same_place(self):
        self.assertEqual(
            self.after_first, self.after_second,
            "the discovery pass leaked UUIDs; every id downstream of routing "
            "would shift on a change that moves no copper")

    def test_the_discovery_pass_is_rewound_not_merely_re_run(self):
        # If uid_restore were removed, the emitted pass would start at a
        # higher counter and the very first uuid in the output would differ.
        first_uuid = _UUID_RE.search(self.first)
        self.assertIsNotNone(first_uuid, "no uuid in the routing output")
        self.assertEqual(first_uuid.group(0),
                         _UUID_RE.search(self.second).group(0))

    def test_the_seed_covers_the_pads_the_router_actually_touched(self):
        # The point of the discovery pass: nearly every pad is known BEFORE
        # the first trace is placed. A collapse here means the seed is empty
        # and the detector is back to learning as it goes.
        self.assertGreater(
            len(self.pad_nets), 250,
            f"only {len(self.pad_nets)} pad nets discovered — the seed is "
            "not being collected")

    def test_the_explicit_seeds_survive_the_second_pass(self):
        # These are the ones the discovery pass cannot supply, so they
        # must still be declared by hand and must still win. ("U6", "9") is
        # deliberately NOT in this list: R31-HIGH-2 rerouted BTN_R east of
        # the pad row and the Cd pad carries no net — its reappearance here
        # would be the regression, and the off-net assertion lives in
        # test_vbench's strapping-exposure pair.
        from scripts.generate_pcb.routing import _shared as sh
        seeds = sh._SEED_PAD_NETS
        self.assertTrue(seeds, "the seed map is empty after generation")
        # The explicitly-declared trace-through-pad pads must be in the map
        # the second pass was seeded with.
        for key in (("U6", "8"),
                    ("SW16", "4b"), ("SW16", "4d"), ("U1", "3")):
            self.assertIn(key, seeds,
                          f"{key} dropped out of the discovered pad-net map")
        self.assertNotIn(("U6", "9"), seeds,
                         "U6.9 acquired a net again — R31-HIGH-2 regression")


if __name__ == "__main__":
    unittest.main(verbosity=2)
