#!/usr/bin/env python3
"""Mutation tests for the ERC verdict in erc_check.py.

Why this file exists
--------------------
Until 2026-07-26 the verdict was

    criticals = [i for i in real_issues if i["type"] in CRITICAL_TYPES]
    return len(criticals) == 0

over three hardcoded types, and KiCad's own `severity` field was never read.
Every type in GENERATOR_ARTIFACTS was dropped wholesale -- including
`wire_dangling`, which KiCad raises at severity=error. So the gate printed
"PASS - 0 critical" while the report held a dozen errors.

That was demonstrated, not theorised. Detaching SW3's (BTN_LEFT) ground pin by
2.54 mm -- the same defect 397c854 found on SW15/SW14 -- took SW3.2 off
the GND net in the exported netlist, and the verdict did not move: PASS before,
PASS after.

The fix reads `severity` and requires an exact (type, sheet, item) waiver for
every error. These tests hold that shape in place. They build ERC reports in
memory rather than shelling out to kicad-cli, so they are fast and do not
depend on the schematic of the day.

Usage:
    python3 scripts/test_erc_severity.py
    python3 -m unittest scripts.test_erc_severity
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "scripts"))


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, str(BASE / rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ERC = _load("_erc", "scripts/erc_check.py")


def report(*violations):
    """Build a minimal ERC report: (severity, type, sheet, item) tuples."""
    sheets: dict[str, list] = {}
    for severity, vtype, sheet, item in violations:
        sheets.setdefault(sheet, []).append({
            "type": vtype,
            "severity": severity,
            "description": vtype.replace("_", " "),
            "items": [{"description": item}],
        })
    return {"sheets": [{"path": p, "violations": v} for p, v in sheets.items()]}


def verdict(rep):
    """Run the gate over an in-memory report; return (passes, printed)."""
    fd, path = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(rep, fh)
        res = ERC.parse_report(path)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ok = ERC.print_report(res)
        return ok, buf.getvalue()
    finally:
        os.unlink(path)


# The planted defect, exactly as KiCad reports it for a detached switch pin.
DETACHED_PIN = ("error", "pin_not_connected", "/Controls/",
                "Symbol SW3 Pin 2 [2, Passive, Line]")


class TestErcSeverityVerdict(unittest.TestCase):

    # -- the regression that motivated the rewrite ------------------------

    def test_unwaived_error_fails(self):
        """Any error-severity violation with no waiver must fail the gate."""
        ok, out = verdict(report(DETACHED_PIN))
        self.assertFalse(ok, f"an unwaived KiCad error passed:\n{out}")
        self.assertIn("NOT waived", out)

    def test_dangling_wire_error_is_not_suppressed_by_its_type(self):
        """`wire_dangling` is in GENERATOR_ARTIFACTS but is raised as an error.

        Suppressing it by type is what let a detached pin through. A
        wire_dangling at a NEW identity must fail.
        """
        ok, out = verdict(report(
            ("error", "wire_dangling", "/Controls/", "Symbol SW9 [SW_Push]")))
        self.assertFalse(ok, f"wire_dangling was suppressed by type:\n{out}")

    def test_clean_report_passes(self):
        ok, out = verdict(report(
            ("warning", "endpoint_off_grid", "/Mcu/", "Global Label 'X'")))
        self.assertTrue(ok, out)

    # -- waivers must be exact, and must not become a blanket -------------

    def test_waived_error_passes(self):
        (vtype, sheet, item) = next(iter(ERC.ERROR_WAIVERS))
        ok, out = verdict(report(("error", vtype, sheet, item)))
        self.assertTrue(ok, f"a waived item still failed:\n{out}")

    def test_waiver_does_not_cover_a_different_item_of_the_same_type(self):
        """The whole point: waiving one instance must not waive its type."""
        (vtype, sheet, _item) = next(iter(ERC.ERROR_WAIVERS))
        ok, out = verdict(report(("error", vtype, sheet, "Symbol SW99 [NEW]")))
        self.assertFalse(ok, f"a waiver leaked to a new item:\n{out}")

    def test_waiver_does_not_cover_the_same_item_on_another_sheet(self):
        (vtype, _sheet, item) = next(iter(ERC.ERROR_WAIVERS))
        ok, out = verdict(report(("error", vtype, "/Somewhere Else/", item)))
        self.assertFalse(ok, f"a waiver leaked across sheets:\n{out}")

    def test_waived_errors_are_still_printed(self):
        """A waiver removes an item from the verdict, never from the report."""
        (vtype, sheet, item) = next(iter(ERC.ERROR_WAIVERS))
        ok, out = verdict(report(("error", vtype, sheet, item)))
        self.assertTrue(ok)
        self.assertIn("waived", out)
        self.assertIn(item, out, "a waived error vanished from the output")

    def test_one_unwaived_error_fails_even_beside_many_waived(self):
        rows = [("error", t, s, i) for (t, s, i) in ERC.ERROR_WAIVERS]
        ok, out = verdict(report(*rows, DETACHED_PIN))
        self.assertFalse(ok, f"a new error hid among the waived ones:\n{out}")

    # -- critical types keep failing regardless ---------------------------

    def test_critical_type_still_fails(self):
        ok, out = verdict(report(
            ("warning", "pin_to_pin", "/Mcu/", "Symbol U1 Pin 1 [Output]")))
        self.assertFalse(ok, f"a CRITICAL_TYPES violation passed:\n{out}")

    # -- the live board -----------------------------------------------------

    def test_current_report_has_no_unwaived_errors(self):
        """The checked-in board must be clean under the new rule.

        If this fails, either the schematic changed or a waiver key drifted --
        both of which are meant to be noticed, not absorbed.
        """
        live = BASE / "hardware" / "kicad" / ".erc-report.json"
        if not live.exists():
            self.skipTest("no ERC report generated yet")
        res = ERC.parse_report(str(live))
        self.assertEqual(
            res["errors_unwaived"], [],
            f"unwaived ERC errors on the current board: {res['errors_unwaived']}")

    def test_every_waiver_states_a_reason(self):
        for key, reason in ERC.ERROR_WAIVERS.items():
            self.assertTrue(reason and reason.strip(),
                            f"waiver {key} has no reason")
            self.assertGreater(
                len(reason), 15,
                f"waiver {key} reason is too thin to review: {reason!r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
