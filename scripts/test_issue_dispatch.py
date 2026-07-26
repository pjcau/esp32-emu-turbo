#!/usr/bin/env python3
"""Mutation tests for the issue dispatcher's routing law.

A router that always returns an owner looks identical to a router that
thinks. These tests break it on purpose and require it to notice:

  * a failing gate no rule covers must be UNROUTED and exit non-zero —
    not quietly assigned to the PCB engineer;
  * the gate list must come from the Makefile, and a missing
    VERIFY_ALL_SCRIPTS must raise rather than dispatch an empty suite
    (an empty suite and a healthy board print the same thing);
  * a declared exception must beat the law, or exceptions are decoration;
  * severity must separate "the board is dead" from "the board is warm",
    or every finding is equally urgent and none is.

Run: python3 scripts/test_issue_dispatch.py
"""
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import issue_dispatch as D

PROJECT_DIR = D.PROJECT_DIR


class RoutingLaw(unittest.TestCase):

    def test_unknown_gate_is_not_routed(self):
        """The mutation that matters: a name the law never anticipated."""
        for name in ("verify_quantum_flux", "check_zzz", "gate_with_no_domain"):
            self.assertIsNone(D.route(name),
                              f"{name} was given an owner by accident — "
                              "the law must not have a catch-all")

    def test_unrouted_failure_exits_nonzero(self):
        """A finding with no owner must fail the dispatcher, loudly."""
        fake = {"gate": "verify_quantum_flux", "status": "FAIL", "rc": 1,
                "log": "FAIL something nobody mapped"}
        with mock.patch.object(D, "gates_from_makefile",
                               return_value=["verify_quantum_flux"]), \
             mock.patch.object(D, "run_gate", return_value=fake):
            with mock.patch.object(sys, "argv", ["issue_dispatch.py", "--json"]), \
                 mock.patch.object(sys, "stdout", io.StringIO()):
                rc = D.main()
        self.assertEqual(rc, 2, "an unrouted failing gate must exit 2")

    def test_every_shipped_gate_is_routed(self):
        """Every gate verify-all runs today must have an owner."""
        missing = [g for g in D.gates_from_makefile() if D.route(g) is None]
        self.assertEqual(missing, [],
                         f"gates with no routing rule: {missing}")

    def test_exception_beats_the_law(self):
        gate = "verify_cpl_rotation_law"
        by_law = D.route(gate)
        self.assertTrue(by_law["decidedBy"].startswith("law:"))
        with mock.patch.dict(D.ROUTING_EXCEPTIONS,
                             {gate: ("software-dev", "/firmware-sync",
                                     "cosmetic", "test")}, clear=False):
            by_exc = D.route(gate)
        self.assertEqual(by_exc["agent"], "software-dev")
        self.assertEqual(by_exc["decidedBy"], f"exception:{gate}")

    def test_law_order_is_specific_before_generic(self):
        """`verify_netlist_diff` must route as netlist, not as a generic
        schematic gate — the two need different skills."""
        self.assertEqual(D.route("verify_netlist_diff")["decidedBy"],
                         "law:netlist")
        self.assertEqual(D.route("verify_schematic_pin_connectivity")
                         ["decidedBy"], "law:schematic")

    def test_severity_discriminates(self):
        """Not every finding may be dead-board, or the tier says nothing."""
        sevs = {D.route(g)["severity"]
                for g in D.gates_from_makefile() if D.route(g)}
        self.assertIn("dead-board", sevs)
        self.assertIn("degraded", sevs,
                      "no gate is 'degraded' — the severity tier is inert")


class GateList(unittest.TestCase):

    def test_list_comes_from_the_makefile(self):
        gates = D.gates_from_makefile()
        self.assertGreater(len(gates), 50)
        self.assertIn("verify_dfa", gates)
        for g in gates:
            self.assertTrue(
                os.path.exists(os.path.join(PROJECT_DIR, "scripts", f"{g}.py")),
                f"Makefile lists {g} but scripts/{g}.py does not exist")

    def test_missing_variable_raises(self):
        """Renaming VERIFY_ALL_SCRIPTS must break loudly, not silently."""
        with mock.patch("builtins.open",
                        mock.mock_open(read_data="all:\n\techo hi\n")):
            with self.assertRaises(SystemExit):
                D.gates_from_makefile()

    def test_empty_variable_raises(self):
        with mock.patch("builtins.open",
                        mock.mock_open(read_data="VERIFY_ALL_SCRIPTS =\n")):
            with self.assertRaises(SystemExit):
                D.gates_from_makefile()


class ProposalsSurvive(unittest.TestCase):
    """The regression that cost the most: dispatch wiped agent answers.

    Briefings are cheap — re-running the gate regenerates them. A
    proposal is an agent's analysis, is not reproducible by re-running
    anything, and the first version of this script deleted every `.md`
    in the directory including those.
    """

    def test_dispatch_keeps_proposal_files(self):
        import shutil
        import tempfile
        tmp = tempfile.mkdtemp()
        try:
            keep = os.path.join(tmp, "verify_x.proposal.md")
            stale = os.path.join(tmp, "verify_gone.md")
            with open(keep, "w") as f:
                f.write("expensive agent analysis")
            with open(stale, "w") as f:
                f.write("stale briefing")

            fake = {"gate": "verify_dfa", "status": "FAIL", "rc": 1,
                    "log": "FAIL something"}
            with mock.patch.object(D, "OUT_DIR", tmp), \
                 mock.patch.object(D, "gates_from_makefile",
                                   return_value=["verify_dfa"]), \
                 mock.patch.object(D, "run_gate", return_value=fake), \
                 mock.patch.object(sys, "argv", ["issue_dispatch.py"]), \
                 mock.patch.object(sys, "stdout", io.StringIO()):
                D.main()

            self.assertTrue(os.path.exists(keep),
                            "dispatch deleted an agent proposal")
            self.assertEqual(open(keep).read(), "expensive agent analysis")
            self.assertFalse(os.path.exists(stale),
                             "dispatch kept a stale briefing")
        finally:
            shutil.rmtree(tmp)


class Briefing(unittest.TestCase):

    def _finding(self, **over):
        f = {"gate": "verify_x", "agent": "pcb-engineer", "skill": "/dfm-fix",
             "domain": "d", "severity": "dead-board", "severityWhy": "w",
             "decidedBy": "law:x", "rc": 1, "evidence": ["FAIL a"],
             "suiteSize": 65}
        f.update(over)
        return f

    def test_briefing_states_the_propose_only_mandate(self):
        md = D.briefing(self._finding())
        self.assertIn("PROPOSE", md)
        self.assertIn("Do not edit", md)
        self.assertIn("Root cause", md)
        self.assertIn("Blast radius", md)

    def test_briefing_carries_the_reproduction_command(self):
        md = D.briefing(self._finding(gate="verify_dangling_copper"))
        self.assertIn("python3 scripts/verify_dangling_copper.py", md)

    def test_evidence_prefers_fail_lines_over_the_tail(self):
        log = "\n".join(["noise"] * 60 + ["FAIL the real thing"] + ["noise"] * 60)
        self.assertEqual(D.evidence(log), ["FAIL the real thing"])

    def test_evidence_falls_back_to_the_tail_on_a_crash(self):
        """A traceback has no FAIL line; it is still the evidence."""
        log = "Traceback (most recent call last):\n  File x\nKeyError: 'net'"
        ev = D.evidence(log)
        self.assertIn("KeyError: 'net'", ev[-1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
