#!/usr/bin/env python3
"""Mutation tests for the EN RC-delay check in verify_strapping_pins.py.

Why this file exists
--------------------
The EN check used to pass by regex-matching a JUSTIFICATION COMMENT in the
schematic text ("R3 DNP", "WROOM-1 integrates") and then computing tau from a
WROOM-1 internal ~45 kOhm pull-up that the module does not have. It therefore
reported green on a fabricated board carrying neither a pull-up nor an RC cap
-- the gate asserted a network that exists only in prose.

It now judges pad membership on copper, and it FAILS on the board as built.
That is the correct verdict, but a check that can only ever fail is no more
evidence than one that can only ever pass. These tests drive it BOTH ways:

  * plant a real EN pull-up + RC cap  -> the check must go GREEN
  * take either half away            -> the check must go RED, naming which
  * restore the old prose            -> the check must STAY red

The last one is the regression that matters. If someone re-adds a comment
like "WROOM-1 integrates a 10k EN pull-up" to a schematic or a generator, the
gate must not notice, because copper is the only thing it reads.

Usage:
    python3 scripts/test_strapping_en_rc.py
    python3 -m unittest scripts.test_strapping_en_rc
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


STRAP = _load("_strap", "scripts/verify_strapping_pins.py")


# ---------------------------------------------------------------------------
# A minimal synthetic board. Only the fields the EN check reads are present:
# nets by id->name, and pads carrying (ref, net). Everything else the real
# cache holds is irrelevant here, and leaving it out keeps the fixture honest
# about what the check actually depends on.
# ---------------------------------------------------------------------------
_NETS = [
    {"id": 0, "name": ""},
    {"id": 1, "name": "GND"},
    {"id": 4, "name": "+3V3"},
    {"id": 53, "name": "EN"},
]

# The board as fabricated: EN reaches only the module and the reset button.
_AS_BUILT = [
    {"ref": "U1", "net": 53},
    {"ref": "SW_RST", "net": 53},
    {"ref": "SW_RST", "net": 1},
    {"ref": "C3", "net": 4},      # decoupling cap, NOT on EN
    {"ref": "C3", "net": 1},
]

# The respin: 10k from +3V3 to EN, 100nF from EN to GND.
_PULLUP = [{"ref": "R3", "net": 53}, {"ref": "R3", "net": 4}]
_RC_CAP = [{"ref": "C31", "net": 53}, {"ref": "C31", "net": 1}]


class FakeBoard:
    """Swap in a synthetic cache and BOM for the duration of a test."""

    def __init__(self, pads, values=None):
        self.pads = pads
        self.values = values or {}

    def __enter__(self):
        self._load = STRAP.load_cache
        self._bom = STRAP._bom_value
        STRAP.load_cache = lambda *a, **k: {"nets": _NETS, "pads": self.pads}
        STRAP._bom_value = lambda ref: self.values.get(ref)
        return self

    def __exit__(self, *exc):
        STRAP.load_cache = self._load
        STRAP._bom_value = self._bom
        return False


def _run_en_check(pads, values=None):
    """Run only the EN block; return (passed, failed, output)."""
    import io
    import contextlib

    with FakeBoard(pads, values):
        STRAP.PASS = STRAP.FAIL = STRAP.WARN = 0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            STRAP.test_en_rc_delay()
        return STRAP.PASS, STRAP.FAIL, buf.getvalue()


class TestEnRcGate(unittest.TestCase):

    # -- the board as it exists -------------------------------------------

    def test_as_built_board_fails(self):
        """No pull-up and no RC cap on EN -> the check must fail."""
        _, failed, out = _run_en_check(_AS_BUILT)
        self.assertEqual(failed, 2, f"expected both halves to fail:\n{out}")
        self.assertIn("pull-up resistor to +3V3", out)
        self.assertIn("RC delay capacitor to GND", out)

    def test_failure_names_the_pads_actually_on_en(self):
        """The report must show what IS on EN, not just what is missing."""
        _, _, out = _run_en_check(_AS_BUILT)
        self.assertIn("SW_RST", out)
        self.assertIn("U1", out)

    def test_decoupling_cap_on_3v3_does_not_count_as_the_rc(self):
        """C3 bridges +3V3->GND, not EN->GND. It must not satisfy the check.

        This is the exact substitution the old prose-matching version made:
        it found a '100nF C3' in the schematic and accepted it as the EN RC.
        """
        _, failed, out = _run_en_check(_AS_BUILT)
        self.assertEqual(failed, 2, f"C3 was miscredited as the EN RC:\n{out}")

    # -- the respin, and each half of it ----------------------------------

    def test_full_rc_network_passes(self):
        """Plant a real 10k + 100nF on EN -> the check must go green."""
        pads = _AS_BUILT + _PULLUP + _RC_CAP
        values = {"R3": "10k 0805", "C31": "100nF 0805"}
        passed, failed, out = _run_en_check(pads, values)
        self.assertEqual(failed, 0, f"a correct EN network was rejected:\n{out}")
        self.assertGreaterEqual(passed, 3, out)
        self.assertIn("RC margin", out)

    def test_pullup_without_cap_fails(self):
        passed, failed, out = _run_en_check(_AS_BUILT + _PULLUP,
                                            {"R3": "10k 0805"})
        self.assertEqual(failed, 1, out)
        self.assertIn("RC delay capacitor to GND", out)

    def test_cap_without_pullup_fails(self):
        passed, failed, out = _run_en_check(_AS_BUILT + _RC_CAP,
                                            {"C31": "100nF 0805"})
        self.assertEqual(failed, 1, out)
        self.assertIn("pull-up resistor to +3V3", out)

    # -- the margin must be computed, not asserted ------------------------

    def test_absurdly_slow_rc_fails_on_margin(self):
        """A 10M + 10uF network solders fine but samples far too late.

        Proves the margin arm can fail, rather than being decorative once the
        two parts are present.
        """
        pads = _AS_BUILT + _PULLUP + _RC_CAP
        values = {"R3": "10M 0805", "C31": "10uF 0805"}
        _, failed, out = _run_en_check(pads, values)
        self.assertEqual(failed, 1, f"3*tau >> 50ms should fail:\n{out}")
        self.assertIn("RC margin", out)

    def test_margin_uses_the_planted_values(self):
        """tau must track the BOM values, not a hardcoded constant."""
        pads = _AS_BUILT + _PULLUP + _RC_CAP
        _, _, out = _run_en_check(pads, {"R3": "10k 0805", "C31": "100nF 0805"})
        self.assertIn("tau=1.0ms", out)      # 10k * 100nF = 1 ms
        _, _, out2 = _run_en_check(pads, {"R3": "20k 0805", "C31": "100nF 0805"})
        self.assertIn("tau=2.0ms", out2)     # doubling R must double tau

    # -- the regression that motivated the rewrite ------------------------

    def test_prose_cannot_resurrect_a_pass(self):
        """Re-adding the old justification comment must NOT turn it green.

        The previous implementation passed on exactly these strings. The check
        no longer reads schematic text at all, so planting them changes
        nothing -- which is the property being locked in.
        """
        original = STRAP._read_schematics
        STRAP._read_schematics = lambda: (
            '"R3" "10k" "C3" "100nF" R3 DNP -- WROOM-1 integrates a 10k '
            'EN pull-up on-module, internal to WROOM-1, so external is redundant'
        )
        try:
            _, failed, out = _run_en_check(_AS_BUILT)
            self.assertEqual(
                failed, 2,
                f"a comment revived the false green -- the check is reading "
                f"prose again:\n{out}")
        finally:
            STRAP._read_schematics = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
