#!/usr/bin/env python3
"""Mutation tests for the CPL rotation law gate.

An assertion that has never fired is not evidence. These tests deliberately
inject rotation errors and require the gate to catch every one of them.

This is the check the previous mechanism could not perform on itself: in
`verify_easyeda_footprint.py`, a part with an override reports
"override present, geometric match -> OK", but the override was chosen to
make the geometry match, so the OK is self-confirming and would survive a
wrong override. A gate that cannot fail on a planted bug is asleep.

Usage:
    python3 scripts/test_cpl_rotation_law.py
    python3 -m unittest scripts.test_cpl_rotation_law
"""

from __future__ import annotations

import importlib.util
import sys
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


LAW = _load("_law", "scripts/verify_cpl_rotation_law.py")
from scripts.generate_pcb import jlcpcb_export as EXPORT  # noqa: E402


def _statuses() -> dict[str, str]:
    return {r["ref"]: r["status"] for r in LAW.evaluate()}


class InjectOverride:
    """Temporarily force a component's emitted CPL angle."""

    def __init__(self, ref: str, value: int):
        self.ref, self.value = ref, value
        self.had = ref in EXPORT._JLCPCB_ROT_OVERRIDES
        self.prev = EXPORT._JLCPCB_ROT_OVERRIDES.get(ref)

    def __enter__(self):
        EXPORT._JLCPCB_ROT_OVERRIDES[self.ref] = self.value
        return self

    def __exit__(self, *exc):
        if self.had:
            EXPORT._JLCPCB_ROT_OVERRIDES[self.ref] = self.prev
        else:
            EXPORT._JLCPCB_ROT_OVERRIDES.pop(self.ref, None)
        return False


class TestBaseline(unittest.TestCase):
    def test_some_components_are_evaluated(self):
        """Guard against the gate silently evaluating nothing."""
        st = _statuses()
        self.assertGreaterEqual(
            len(st), 8, "too few components reached the law check")
        self.assertGreaterEqual(
            sum(1 for v in st.values() if v == "OK"), 5,
            "fewer than 5 components satisfy the law — the law constants or "
            "the pad parsing are wrong, not the board")

    def test_law_constants_are_pinned_not_fitted(self):
        """The law must be a constant, never re-derived from the data.

        If a future change fits LAW_BOTTOM at runtime, a board-wide rotation
        error would redefine the law and every part would pass.
        """
        self.assertIsInstance(LAW.LAW_TOP, float)
        self.assertIsInstance(LAW.LAW_BOTTOM, float)
        src = (BASE / "scripts" / "verify_cpl_rotation_law.py").read_text()
        body = src.split("def evaluate", 1)[1]
        for name in ("LAW_TOP", "LAW_BOTTOM"):
            self.assertNotIn(
                f"{name} =", body,
                f"{name} is assigned inside evaluate() — the law must stay a "
                f"pinned constant, otherwise the gate fits itself to the data")


class TestMutations(unittest.TestCase):
    """Every currently-compliant component must be detectable when rotated."""

    def test_injected_rotation_errors_are_caught(self):
        baseline = _statuses()
        compliant = [ref for ref, st in baseline.items() if st == "OK"]
        self.assertTrue(compliant, "no compliant component to mutate")

        missed = []
        for ref in compliant:
            for wrong in (90, 180, 270):
                current = next(
                    r["cpl"] for r in LAW.evaluate() if r["ref"] == ref)
                with InjectOverride(ref, int((current + wrong) % 360)):
                    st = _statuses().get(ref)
                if st != "FAIL":
                    missed.append(f"{ref} +{wrong}deg -> {st}")
        self.assertEqual(
            missed, [],
            "the gate did not flag these planted rotation errors:\n  "
            + "\n  ".join(missed))

    def test_reinjecting_the_correct_angle_keeps_it_passing(self):
        """Rules out a gate that fails on everything (trivially "catching" all)."""
        baseline = _statuses()
        compliant = [ref for ref, st in baseline.items() if st == "OK"]
        for ref in compliant[:5]:
            current = next(
                r["cpl"] for r in LAW.evaluate() if r["ref"] == ref)
            with InjectOverride(ref, int(current % 360)):
                self.assertEqual(
                    _statuses().get(ref), "OK",
                    f"{ref} failed when re-given its own correct angle — the "
                    f"gate rejects everything and its failures are worthless")

    def test_overrides_are_restored_after_mutation(self):
        """A leaked mutation would corrupt every later check in the suite."""
        before = dict(EXPORT._JLCPCB_ROT_OVERRIDES)
        with InjectOverride("LED1", 123):
            pass
        self.assertEqual(dict(EXPORT._JLCPCB_ROT_OVERRIDES), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
