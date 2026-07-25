"""Regression tests for the zone-fill duplication bug and its detector.

The bug: ``kicad_fill_zones.py`` injected each zone's fill just before the
zone's closing paren, which lands *after* any fill already present. Two
overlapping runs — ``drc_native.py --run`` racing a hook-triggered fill — both
read the same unfilled original and both injected, doubling every zone's
copper (4 filled islands -> 8, +3V3 9999 -> 19998 mm² on a 12000 mm² board).

Nothing else in the suite could see it. The duplicated copper is geometrically
identical to the original, so DRC stayed clean and ``verify_power_net_integrity``
still reported one connected group per net. It would have reached the gerbers.

Three classes of test:

  Injection  — ``zone_fill_inject`` is pure text manipulation, so the actual
               fix (replace-not-append) is tested directly on the host. No
               pcbnew, no Docker.
  Detector   — synthetic PCB text with hand-planted corruption. Proves each
               law FIRES, not merely that it passes on good input: a gate that
               never fires is not evidence.
  Control    — the real board must pass, and the real board with every fill
               duplicated (an exact replay of the race) must fail both laws.

Usage:
    python3 scripts/test_zone_fill_sanity.py
    python3 -m unittest scripts.test_zone_fill_sanity
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import verify_zone_fill_sanity as V  # noqa: E402
from zone_fill_inject import (  # noqa: E402
    EXISTING_FILL_RE,
    inject_fills,
    strip_existing_fills,
    zone_spans,
)

REPO = Path(__file__).resolve().parent.parent
REAL_PCB = REPO / "hardware" / "kicad" / "esp32-emu-turbo.kicad_pcb"
SANITY = REPO / "scripts" / "verify_zone_fill_sanity.py"


# ── Fixtures ────────────────────────────────────────────────────────────


def fill_block(pts, layer="In1.Cu"):
    """A filled_polygon block indented exactly as the injector emits it."""
    xy = "\n".join(f"        (xy {x} {y})" for x, y in pts)
    return (f"    (filled_polygon\n"
            f"      (layer \"{layer}\")\n"
            f"      (pts\n{xy}\n      )\n"
            f"    )\n")


def zone_block(uid, net_name, layer="In1.Cu", priority=0, fills=()):
    """A zone block at 2-space indent, closing with a lone '  )'."""
    body = "".join(fills)
    return (f"  (zone\n"
            f"    (net 1)\n"
            f"    (net_name \"{net_name}\")\n"
            f"    (layer \"{layer}\")\n"
            f"    (uuid \"{uid}\")\n"
            f"    (priority {priority})\n"
            f"    (polygon\n"
            f"      (pts (xy 0 0) (xy 10 0) (xy 10 10) (xy 0 10))\n"
            f"    )\n"
            f"{body}"
            f"  )\n")


def pcb_text(zones, width=100.0, height=50.0):
    """A minimal .kicad_pcb: Edge.Cuts rectangle plus the given zone blocks."""
    corners = [(0, 0), (width, 0), (width, height), (0, height)]
    edges = ""
    for i in range(4):
        x1, y1 = corners[i]
        x2, y2 = corners[(i + 1) % 4]
        edges += (f'  (gr_line (start {x1} {y1}) (end {x2} {y2})'
                  f' (stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))\n')
    return "(kicad_pcb\n" + edges + "".join(zones) + ")\n"


SQUARE = [(1, 1), (5, 1), (5, 5), (1, 5)]          # 16 mm²
BIG = [(0, 0), (90, 0), (90, 45), (0, 45)]          # 4050 mm²


def run_sanity(text):
    """Run the gate as a subprocess. Returns (exit_code, output)."""
    with tempfile.NamedTemporaryFile("w", suffix=".kicad_pcb", delete=False) as f:
        f.write(text)
        path = f.name
    try:
        p = subprocess.run(
            [sys.executable, str(SANITY), "--pcb", path],
            capture_output=True, text=True,
        )
        return p.returncode, p.stdout + p.stderr
    finally:
        os.unlink(path)


# ── Injection: the actual fix ───────────────────────────────────────────


class TestInjection(unittest.TestCase):
    UID = "0000085f-dead-4000-a000-00000000085f"

    def _fills(self, layer="In1.Cu"):
        return {self.UID: fill_block(SQUARE, layer).rstrip("\n")}

    def test_injects_into_an_unfilled_zone(self):
        src = pcb_text([zone_block(self.UID, "GND")])
        out, missing = inject_fills(src, self._fills())
        self.assertEqual(missing, [])
        self.assertEqual(len(EXISTING_FILL_RE.findall(out)), 1)

    def test_refilling_replaces_instead_of_appending(self):
        """THE bug. Filling an already-filled zone must not stack a second copy."""
        already = pcb_text([zone_block(self.UID, "GND", fills=[fill_block(SQUARE)])])
        self.assertEqual(len(EXISTING_FILL_RE.findall(already)), 1)

        out, missing = inject_fills(already, self._fills())
        self.assertEqual(missing, [])
        self.assertEqual(
            len(EXISTING_FILL_RE.findall(out)), 1,
            "refilling appended a second fill — this is the doubling bug",
        )

    def test_injection_is_idempotent_byte_for_byte(self):
        src = pcb_text([zone_block(self.UID, "GND")])
        once, _ = inject_fills(src, self._fills())
        twice, _ = inject_fills(once, self._fills())
        thrice, _ = inject_fills(twice, self._fills())
        self.assertEqual(once, twice)
        self.assertEqual(twice, thrice)

    def test_interleaved_writers_cannot_double(self):
        """Simulates the race: two writers both start from the same original.

        Whoever writes last must still produce a single-fill board, because
        each writer strips before injecting rather than appending to what it read.
        """
        original = pcb_text([zone_block(self.UID, "GND")])
        a, _ = inject_fills(original, self._fills())   # writer A reads original
        b, _ = inject_fills(original, self._fills())   # writer B reads original too
        for winner in (a, b):
            self.assertEqual(len(EXISTING_FILL_RE.findall(winner)), 1)
        # And a writer that happens to read A's output still yields one fill.
        c, _ = inject_fills(a, self._fills())
        self.assertEqual(len(EXISTING_FILL_RE.findall(c)), 1)

    def test_zone_structure_survives_injection(self):
        src = pcb_text([zone_block(self.UID, "GND")])
        out, _ = inject_fills(src, self._fills())
        self.assertIn('(net_name "GND")', out)
        self.assertIn('(polygon', out)
        self.assertEqual(out.count("(zone"), 1)

    def test_every_zone_keeps_its_fill_on_a_multi_zone_board(self):
        """Regression: a lazy-regex zone match spanned earlier zones.

        Injecting zone N's fill replaced everything from the FIRST zone up to
        zone N, so each successive injection wiped the fills of the zones
        before it. On the real 4-zone board that left 3 zones with 0 islands —
        a silently de-planed board. Caught only end-to-end, never by a
        single-zone unit test.
        """
        uids = ["uuid-a", "uuid-b", "uuid-c", "uuid-d"]
        src = pcb_text([zone_block(u, f"NET{i}") for i, u in enumerate(uids)])
        fills = {u: fill_block([(x, y + 6 * i) for x, y in SQUARE]).rstrip("\n")
                 for i, u in enumerate(uids)}

        out, missing = inject_fills(src, fills)
        self.assertEqual(missing, [])
        self.assertEqual(out.count("(zone"), 4, "zones were consumed by injection")
        self.assertEqual(
            len(EXISTING_FILL_RE.findall(out)), 4,
            "not every zone kept its fill — injection spanned zone boundaries",
        )
        for i in range(4):
            self.assertIn(f'(net_name "NET{i}")', out)

    def test_multi_zone_injection_is_idempotent(self):
        uids = ["uuid-a", "uuid-b", "uuid-c"]
        src = pcb_text([zone_block(u, f"NET{i}") for i, u in enumerate(uids)])
        fills = {u: fill_block([(x, y + 6 * i) for x, y in SQUARE]).rstrip("\n")
                 for i, u in enumerate(uids)}
        once, _ = inject_fills(src, fills)
        twice, _ = inject_fills(once, fills)
        self.assertEqual(once, twice)
        self.assertEqual(len(EXISTING_FILL_RE.findall(twice)), 3)

    def test_zone_spans_finds_each_zone_exactly_once(self):
        src = pcb_text([zone_block(f"u{i}", f"NET{i}") for i in range(4)])
        self.assertEqual(len(zone_spans(src)), 4)
        for start, end in zone_spans(src):
            block = src[start:end]
            self.assertEqual(block.count("(zone"), 1)

    def test_missing_zone_is_reported_not_swallowed(self):
        src = pcb_text([zone_block(self.UID, "GND")])
        out, missing = inject_fills(src, {"no-such-uuid": fill_block(SQUARE)})
        self.assertEqual(missing, ["no-such-uuid"])
        self.assertEqual(out, src)

    def test_strip_removes_every_fill(self):
        z = zone_block(self.UID, "GND", fills=[fill_block(SQUARE), fill_block(SQUARE)])
        self.assertEqual(len(EXISTING_FILL_RE.findall(z)), 2)
        self.assertEqual(len(EXISTING_FILL_RE.findall(strip_existing_fills(z))), 0)

    def test_strip_preserves_the_zone_outline_polygon(self):
        """(polygon ...) closes like (filled_polygon ...) — it must survive."""
        z = zone_block(self.UID, "GND", fills=[fill_block(SQUARE)])
        stripped = strip_existing_fills(z)
        self.assertIn("(polygon", stripped)
        self.assertTrue(stripped.endswith("\n  )\n"))


# ── Detector: prove each law fires ──────────────────────────────────────


class TestLawA(unittest.TestCase):
    """No two islands in one zone may share a vertex set."""

    def test_clean_board_passes(self):
        text = pcb_text([zone_block("u1", "GND", fills=[fill_block(SQUARE)])])
        code, out = run_sanity(text)
        self.assertEqual(code, 0, out)

    def test_duplicate_island_fires(self):
        text = pcb_text([zone_block("u1", "GND",
                                    fills=[fill_block(SQUARE), fill_block(SQUARE)])])
        code, out = run_sanity(text)
        self.assertEqual(code, 1, out)
        self.assertIn("duplicates island", out)

    def test_duplicate_with_rotated_start_vertex_fires(self):
        """Same closed loop written from a different starting vertex."""
        rotated = SQUARE[2:] + SQUARE[:2]
        text = pcb_text([zone_block("u1", "GND",
                                    fills=[fill_block(SQUARE), fill_block(rotated)])])
        code, out = run_sanity(text)
        self.assertEqual(code, 1, out)
        self.assertIn("duplicates island", out)

    def test_distinct_islands_are_not_flagged(self):
        """False-positive guard: a genuine two-island pour must pass."""
        other = [(20, 20), (25, 20), (25, 25), (20, 25)]
        text = pcb_text([zone_block("u1", "GND",
                                    fills=[fill_block(SQUARE), fill_block(other)])])
        code, out = run_sanity(text)
        self.assertEqual(code, 0, out)


class TestLawB(unittest.TestCase):
    """Poured copper on a layer cannot exceed the board outline."""

    def test_area_within_board_passes(self):
        text = pcb_text([zone_block("u1", "GND", fills=[fill_block(BIG)])])
        code, out = run_sanity(text)
        self.assertEqual(code, 0, out)

    def test_area_exceeding_board_fires(self):
        """Two distinct big islands: Law A is silent, so only Law B can catch it."""
        shifted = [(x, y + 45) for x, y in BIG]   # distinct vertices, still 4050 mm²
        text = pcb_text([zone_block("u1", "GND",
                                    fills=[fill_block(BIG), fill_block(shifted)])],
                        width=90.0, height=45.0)  # board is only 4050 mm²
        code, out = run_sanity(text)
        self.assertEqual(code, 1, out)
        self.assertIn("cannot physically fit", out)

    def test_law_b_sums_across_zones_on_one_layer(self):
        """Zones on a layer are disjoint by priority, so their areas add."""
        shifted = [(x, y + 45) for x, y in BIG]
        text = pcb_text([zone_block("u1", "GND", fills=[fill_block(BIG)]),
                         zone_block("u2", "+5V", priority=1,
                                    fills=[fill_block(shifted)])],
                        width=90.0, height=45.0)
        code, out = run_sanity(text)
        self.assertEqual(code, 1, out)


class TestLawC(unittest.TestCase):
    """Every zone must pour copper — duplication's mirror image.

    The first attempt at fixing the doubling introduced exactly this: three of
    the four real zones silently lost their fill, and laws A and B both passed
    it (zero islands are trivially unique and trivially fit the board).
    """

    def test_a_zone_that_poured_nothing_fires(self):
        text = pcb_text([zone_block("u1", "GND", fills=[fill_block(SQUARE)]),
                         zone_block("u2", "+3V3", fills=[])])
        code, out = run_sanity(text)
        self.assertEqual(code, 1, out)
        self.assertIn("poured NOTHING", out)

    def test_all_zones_filled_passes(self):
        other = [(20, 20), (25, 20), (25, 25), (20, 25)]
        text = pcb_text([zone_block("u1", "GND", fills=[fill_block(SQUARE)]),
                         zone_block("u2", "+3V3", fills=[fill_block(other)])])
        code, out = run_sanity(text)
        self.assertEqual(code, 0, out)

    def test_fill_loss_on_the_real_board_fires(self):
        """Replay of the regression: strip fill from all but the last zone."""
        text = V._read(REAL_PCB)
        spans = [m.span() for m in EXISTING_FILL_RE.finditer(text)]
        self.assertGreaterEqual(len(spans), 2)
        # Drop every fill but the last, back to front to keep offsets valid.
        broken = text
        for start, end in reversed(spans[:-1]):
            broken = broken[:start] + broken[end:]
        code, out = run_sanity(broken)
        self.assertEqual(code, 1, out)
        self.assertIn("poured NOTHING", out)


class TestNoVacuousPass(unittest.TestCase):
    """A gate that passes on missing data is worse than no gate."""

    def test_no_zones_fails(self):
        code, out = run_sanity(pcb_text([]))
        self.assertEqual(code, 1, out)
        self.assertIn("no zones found", out)

    def test_zones_without_fill_fails(self):
        text = pcb_text([zone_block("u1", "GND", fills=[])])
        code, out = run_sanity(text)
        self.assertEqual(code, 1, out)
        self.assertIn("nothing is filled", out)


# ── Control: the real board ─────────────────────────────────────────────


class TestRealBoardControl(unittest.TestCase):
    # Deliberately no skipUnless: a missing board file is a failure, not a
    # reason to pass quietly. Tests that skip themselves stop being evidence.

    @classmethod
    def setUpClass(cls):
        if not REAL_PCB.exists():
            raise AssertionError(f"real board not found: {REAL_PCB}")
        cls.text = V._read(REAL_PCB)
        cls.zones = V.parse_zone_fills(cls.text)

    def test_real_board_passes_the_gate(self):
        p = subprocess.run(
            [sys.executable, str(SANITY), "--pcb", str(REAL_PCB)],
            capture_output=True, text=True,
        )
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_real_board_has_one_island_per_zone(self):
        """Baseline the corruption broke: 4 zones, 4 islands."""
        self.assertEqual(len(self.zones), 4)
        for z in self.zones:
            self.assertEqual(len(z["islands"]), 1,
                             f"{z['net']} on {z['layer']} has {len(z['islands'])} islands")

    def test_doubling_the_real_board_fails_both_laws(self):
        """Exact replay of the race, on real geometry."""
        doubled = EXISTING_FILL_RE.sub(lambda m: m.group(0) + m.group(0), self.text)
        self.assertEqual(len(EXISTING_FILL_RE.findall(doubled)),
                         2 * len(EXISTING_FILL_RE.findall(self.text)))
        code, out = run_sanity(doubled)
        self.assertEqual(code, 1)
        self.assertIn("duplicates island", out)          # Law A
        self.assertIn("cannot physically fit", out)      # Law B


if __name__ == "__main__":
    unittest.main(verbosity=2)
