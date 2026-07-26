#!/usr/bin/env python3
"""Mutation tests for the EN check in verify_strapping_pins.test_en_rc_delay.

Why this file exists
--------------------
The EN check used to pass by regex-matching a JUSTIFICATION COMMENT in the
schematic text ("R3 DNP", "WROOM-1 integrates") and computing tau from a
WROOM-1 internal ~45 kOhm pull-up the module does not have. It reported green
on a board carrying neither a pull-up nor an RC cap. `93bf286` rewrote it to
read copper instead.

The rewrite is a **documented-deviation** gate, not a strict one: with no RC
on the board it still passes, provided `docs/known-issues.md` records the
limitation. That is a deliberate trade (a permanently-red gate stops being
read), but it means the gate's entire safety rests on one property:

    no RC on copper AND no record in known-issues.md  ->  MUST FAIL

Nothing tested that. A documented-deviation gate whose "is it documented?"
arm never fires is just a gate that always passes. These tests drive every
arm, including that one.

Usage:
    python3 scripts/test_strapping_en_rc.py
    python3 -m unittest scripts.test_strapping_en_rc
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
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

# The exact sentence the gate looks for in docs/known-issues.md. Kept here so
# that renaming it in the doc without updating the gate fails loudly, rather
# than silently turning the deviation arm into an unconditional pass.
RECORD_ANCHOR = "EN has no RC delay network"


# ---------------------------------------------------------------------------
# A minimal synthetic board: only the fields the EN check reads.
# ---------------------------------------------------------------------------
_NETS = [
    {"id": 0, "name": ""},
    {"id": 1, "name": "GND"},
    {"id": 4, "name": "+3V3"},
    {"id": 53, "name": "EN"},
]

# The board as fabricated: EN reaches only the module and the reset button,
# and C3 is a +3V3 decoupling cap that must NOT be miscredited as the EN RC.
_AS_BUILT = [
    {"ref": "U1", "num": "3", "net": 53},
    {"ref": "SW_RST", "num": "1", "net": 53},
    {"ref": "SW_RST", "num": "3", "net": 1},
    {"ref": "C3", "num": "1", "net": 4},
    {"ref": "C3", "num": "2", "net": 1},
]

# The respin: 10k from +3V3 to EN, 100nF from EN to GND.
_PULLUP = [{"ref": "R3", "num": "1", "net": 53}, {"ref": "R3", "num": "2", "net": 4}]
_RC_CAP = [{"ref": "C31", "num": "1", "net": 53}, {"ref": "C31", "num": "2", "net": 1}]


class FakeBoard:
    """Swap in a synthetic cache, and a synthetic known-issues doc."""

    def __init__(self, pads, recorded=True):
        self.pads = pads
        self.recorded = recorded

    def __enter__(self):
        self._load = STRAP.load_cache
        STRAP.load_cache = lambda *a, **k: {"nets": _NETS, "pads": self.pads}

        # The gate opens docs/known-issues.md directly, so shadow `open` in
        # its module namespace rather than writing to the real file.
        self._had_open = "open" in STRAP.__dict__
        self._prev_open = STRAP.__dict__.get("open")
        real_open = open
        recorded, anchor = self.recorded, RECORD_ANCHOR

        def fake_open(path, *a, **k):
            if "known-issues" in str(path):
                text = (f"- **{anchor}, and no pull-up at all.** ...respin..."
                        if recorded else
                        "- nothing about the EN pin is recorded here.")
                return io.StringIO(text)
            return real_open(path, *a, **k)

        STRAP.open = fake_open
        return self

    def __exit__(self, *exc):
        STRAP.load_cache = self._load
        if self._had_open:
            STRAP.open = self._prev_open
        else:
            del STRAP.open
        return False


def _run(pads, recorded=True):
    """Run only the EN block; return (passed, failed, output)."""
    with FakeBoard(pads, recorded):
        STRAP.PASS = STRAP.FAIL = STRAP.WARN = 0
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            STRAP.test_en_rc_delay()
        return STRAP.PASS, STRAP.FAIL, buf.getvalue()


class TestEnRcGate(unittest.TestCase):

    # -- the property the whole design rests on ---------------------------

    def test_undocumented_missing_rc_fails(self):
        """No RC on copper and no record in the doc -> MUST fail.

        This is the arm that makes a documented-deviation gate safe. If it
        cannot fire, the gate passes unconditionally and the EN defect is
        invisible again -- which is exactly the state 93bf286 fixed.
        """
        _, failed, out = _run(_AS_BUILT, recorded=False)
        self.assertEqual(failed, 1, f"an UNRECORDED missing RC passed:\n{out}")

    def test_documented_missing_rc_passes(self):
        """No RC on copper but recorded in known-issues.md -> passes."""
        _, failed, out = _run(_AS_BUILT, recorded=True)
        self.assertEqual(failed, 0, f"the recorded deviation was rejected:\n{out}")
        self.assertIn("RECORDED as-built limitation", out)

    def test_the_doc_anchor_still_exists_in_the_real_file(self):
        """The real known-issues.md must contain the sentence the gate greps.

        Without this, someone rewording that section turns the deviation arm
        red for the wrong reason -- or, if the gate's string is ever loosened,
        turns it green for no reason.
        """
        doc = (BASE / "docs" / "known-issues.md").read_text(errors="replace")
        self.assertIn(RECORD_ANCHOR, doc,
                      "docs/known-issues.md no longer records the EN "
                      "limitation in the words verify_strapping_pins greps for")

    # -- the board as it exists -------------------------------------------

    def test_reports_what_is_actually_on_en(self):
        _, _, out = _run(_AS_BUILT)
        self.assertIn("U1.3", out)
        self.assertIn("SW_RST.1", out)
        self.assertIn("pull-up from EN to +3V3: NONE", out)
        self.assertIn("capacitor from EN to GND: NONE", out)

    def test_decoupling_cap_on_3v3_is_not_credited_as_the_rc(self):
        """C3 bridges +3V3->GND, not EN->GND.

        The old prose-matching version found a '100nF C3' in the schematic and
        accepted it as the EN RC. Pad membership must not repeat that.
        """
        _, _, out = _run(_AS_BUILT)
        self.assertIn("capacitor from EN to GND: NONE", out)

    # -- the respin, and each half of it ----------------------------------

    def test_full_rc_network_passes_on_the_parts(self):
        """A real 10k + 100nF on EN passes without consulting the doc.

        Checked with the record ABSENT, so a pass here can only come from the
        copper -- otherwise this would silently be re-testing the doc arm.
        """
        _, failed, out = _run(_AS_BUILT + _PULLUP + _RC_CAP, recorded=False)
        self.assertEqual(failed, 0, f"a correct EN network was rejected:\n{out}")
        self.assertIn("RC delay network the datasheet requires", out)
        self.assertIn("R3", out)
        self.assertIn("C31", out)

    def test_pullup_without_cap_is_not_an_rc(self):
        _, failed, out = _run(_AS_BUILT + _PULLUP, recorded=False)
        self.assertEqual(failed, 1, f"half a network counted as whole:\n{out}")

    def test_cap_without_pullup_is_not_an_rc(self):
        _, failed, out = _run(_AS_BUILT + _RC_CAP, recorded=False)
        self.assertEqual(failed, 1, f"half a network counted as whole:\n{out}")

    # -- the regression that motivated the rewrite ------------------------

    def test_prose_cannot_resurrect_a_pass(self):
        """Re-planting the old justification comment must change nothing.

        The previous implementation passed on exactly these strings. The check
        no longer reads schematic text at all; this locks that in, so the
        comment cannot come back as evidence.
        """
        original = STRAP._read_schematics
        STRAP._read_schematics = lambda: (
            '"R3" "10k" "C3" "100nF" R3 DNP -- WROOM-1 integrates a 10k EN '
            'pull-up on-module, internal to WROOM-1, so external is redundant'
        )
        try:
            _, failed, out = _run(_AS_BUILT, recorded=False)
            self.assertEqual(
                failed, 1,
                f"a comment revived the false green -- the check is reading "
                f"prose again:\n{out}")
        finally:
            STRAP._read_schematics = original


if __name__ == "__main__":
    unittest.main(verbosity=2)
