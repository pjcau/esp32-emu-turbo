"""Mutation tests for the modelled microSD card (Virtual Bench T3.3).

Same discipline as `scripts/test_vbench.py`: break the protocol on purpose
and require the model to notice. The rule this suite exists to enforce is
the repo's own — an assertion that never fires is not evidence — so every
"the host detects X" test is paired with a card that actually does X.

Three of the tests below are the ones that would have caught a plausible
but wrong implementation:

* **A truncated data token is a failure, not a short read.** The easy bug
  is to return the bytes that arrived and let the caller notice. The
  block length is fixed (p.128 sec 7.2.3), so a short token is a fault.
* **A corrupted CRC is caught by recomputing it, not by trusting a flag.**
  The card sends a wrong CRC and no error bit; only the host's own
  CCITT computation can tell.
* **HCS=0 to an SDHC card must never come back ready.** The specification
  says so in one sentence (p.33 sec 4.2.3) and it is the whole reason
  skipping CMD8 breaks SDHC init.

Standalone:
    python3 scripts/test_vbench_sdcard.py
"""

import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench import sdcard_protocol as sp                      # noqa: E402
from vbench.models._schema import validate_model              # noqa: E402
from vbench.models.card_microsd import (                      # noqa: E402
    CARD, R1_BITS, UNESTABLISHED)

PASS = FAIL = 0

BLOCK = sp.BLOCK


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def image(n_blocks=8, seed=7):
    """A deterministic card image with no repeating block."""
    out = bytearray()
    value = seed
    for _ in range(n_blocks * BLOCK):
        value = (value * 1103515245 + 12345) & 0xFFFFFFFF
        out.append((value >> 16) & 0xFF)
    return bytes(out)


def booted(**card_kw):
    """A card and host that have completed init. Fails loudly if not."""
    img = card_kw.pop("image", image())
    host_kw = {k: card_kw.pop(k) for k in ("hcs", "send_cmd8")
               if k in card_kw}
    card = sp.VirtualCard(image=img, **card_kw)
    host = sp.VirtualHost(card, **host_kw)
    ok = host.init()
    return card, host, ok


# ── A. the model itself ────────────────────────────────────────────────

def test_model():
    print("\nA. models/card_microsd.py")

    check("the card model validates against the citation schema",
          validate_model(CARD))

    check("the SPI contact table names CS, DataIn, SCLK, DataOut",
          {p.name for p in CARD.pins} >=
          {"CS", "DataIn", "SCLK", "DataOut", "VDD"},
          f"pins are {[p.name for p in CARD.pins]}")

    check("contacts 8 and 9 are RSV in SPI mode, with no direction",
          CARD.pin("8").name == "RSV" and CARD.pin("8").direction == "nc"
          and CARD.pin("9").name == "RSV",
          "Table 3-2 (p.18 sec 3.1) assigns them no function")

    # The CRC7 implementation is checked against the one complete command
    # frame the specification prints. If this ever disagrees the module
    # refuses to import, so reaching here at all is the assertion — but
    # assert it explicitly so a reader sees the byte.
    frame = sp.command_frame(0, 0)
    check("CMD0 builds the frame the specification prints",
          frame == bytes([0x40, 0, 0, 0, 0, 0x95]),
          f"got {frame.hex(' ')}, p.128 sec 7.2.2 prints 40 00 00 00 00 95")

    check("the block length comes from the model, not a literal",
          BLOCK == 512 and CARD.params["block_len_sdhc"].locator,
          "block_len_sdhc must carry a locator")

    check("the idle current is declared unestablished, not guessed",
          "i_idle" in UNESTABLISHED
          and "i_idle" not in CARD.params,
          "Table 6 has Read, Write and Sleep and nothing between them")

    check("R1 bit 0 is in_idle_state and bit 3 is com_crc_error",
          R1_BITS["in_idle_state"] == 0 and R1_BITS["com_crc_error"] == 3,
          "the only two numeric R1 bytes in either document are 01h and "
          "09h, Table 7-5 p.140 sec 7.3.1.4")

    check("R1 with the MSB set is rejected, not decoded",
          _raises(lambda: sp.r1_flags(0x81)),
          "p.141 sec 7.3.2.1 fixes the MSB at zero")

    samples = [b"", b"\x00", b"\xff" * 16, image(1), bytes(range(256))]
    check("CRC16 matches an independent build of the cited polynomial",
          all(sp.crc16_ccitt(s) == _crc16_from_cited_polynomial(s)
              for s in samples),
          "x16+x12+x5+1 per p.128 sec 7.2.3 — see the note on "
          "_crc16_from_cited_polynomial")


def _crc16_from_cited_polynomial(data):
    """CRC16 written from the polynomial as the specification states it.

    p.128 sec 7.2.3 gives the polynomial in exponent form, x16+x12+x5+1,
    and nothing else — the documents print no worked CRC example. So the
    only way to check `sdcard_protocol.crc16_ccitt` is a second
    implementation built from those exponents rather than from the same
    0x1021 constant. Without this, a wrong polynomial is invisible: the
    card and the host would agree with each other and disagree with every
    real card.
    """
    poly = sum(1 << e for e in (16, 12, 5, 0))
    reg = 0
    for byte in data:
        reg ^= byte << 8
        for _ in range(8):
            reg <<= 1
            if reg & 0x10000:
                reg ^= poly
        reg &= 0xFFFF
    return reg


def _raises(fn, exc=sp.ProtocolError):
    try:
        fn()
    except exc:
        return True
    except Exception:                                    # noqa: BLE001
        return False
    return False


# ── B. initialisation ──────────────────────────────────────────────────

def test_init():
    print("\nB. the init sequence (Figure 7-2, p.127 sec 7.2.1)")

    card, host, ok = booted()
    check("a full CMD0 / CMD8 / ACMD41 sequence reaches transfer state",
          ok and card.state == sp.TRANSFER,
          f"state={card.state} faults={[str(f) for f in host.faults]}")
    check("the initialised host reads CCS=1 for an SDHC card",
          host.ccs == 1, f"ccs={host.ccs}")
    check("the init trace is a citation list, not a log",
          all(step.citation()[1] for step in host.steps)
          and len(host.steps) >= 5,
          f"{len(host.steps)} steps")

    # Skip CMD0: the card is still in SD mode and answers nothing.
    card = sp.VirtualCard(image=image())
    out = card.spi_transfer(sp.command_frame(8, (1 << 8) | 0xAA))
    check("before CMD0 the card answers nothing at all",
          out == b"" and card.state == sp.POWER_ON,
          f"answered {out.hex(' ')!r} in state {card.state}")

    # And the host notices, rather than proceeding on an empty response.
    card = sp.VirtualCard(image=image())
    card.state = sp.POWER_ON
    host = sp.VirtualHost(card)
    # Force the skip by making CMD0 itself unanswerable: CS de-asserted
    # keeps the card in SD mode (p.126 sec 7.2.1).
    saved = host._cmd
    host._cmd = lambda i, a=0, cs_asserted=True: saved(
        i, a, cs_asserted=(i != 0))
    check("init fails when CMD0 never puts the card into SPI mode",
          not host.init() and card.state == sp.POWER_ON
          and any("SPI mode" in str(f) for f in host.faults + card.faults),
          f"faults={[str(f) for f in host.faults + card.faults]}")

    # CMD0 with a broken CRC, while the card is still in SD mode.
    card = sp.VirtualCard(image=image())
    bad = bytearray(sp.command_frame(0, 0))
    bad[5] ^= 0x02
    check("CMD0 with an invalid CRC7 is refused while still in SD mode",
          card.spi_transfer(bytes(bad)) == b""
          and card.state == sp.POWER_ON
          and any("invalid CRC7" in str(f) for f in card.faults),
          "p.128 sec 7.2.2 requires a valid CRC on CMD0")


# ── C. CMD8, and the card that does not have it ────────────────────────

def test_cmd8():
    print("\nC. CMD8 SEND_IF_COND (Table 7-5, p.140 sec 7.3.1.4)")

    card, host, ok = booted()
    check("a matching VHS echoes the check pattern back",
          ok and any("0xaa" in s.outcome for s in host.steps),
          f"steps={[s.outcome for s in host.steps]}")

    # A card that ignores CMD8 reports an illegal command, and the
    # specification is explicit about what that means: "the card is legacy
    # and does not support CMD8" (p.126 sec 7.2.1). Figure 7-2 sends the
    # host down the Ver1.X branch — SDSC, HCS=0, byte addressing. It is
    # NOT a rejection.
    card, host, ok = booted(image=image(), sdhc=False, supports_cmd8=False)
    check("a card that ignores CMD8 takes the SDSC path, it is not rejected",
          ok and host.ccs == 0 and host.hcs == 0,
          f"ok={ok} ccs={host.ccs} hcs={host.hcs} "
          f"faults={[str(f) for f in host.faults]}")
    check("the SDSC path is recorded as the legacy branch, with its locator",
          any(s.key == "cmd8_legacy" for s in host.steps),
          f"keys={[s.key for s in host.steps]}")
    check("the SDSC host then reads blocks by BYTE address",
          host.read_block(3) == card.image[3 * BLOCK:4 * BLOCK],
          "Table 7-3 note 10, p.138 sec 7.3.1.3")

    # An SDHC card whose host skips CMD8 cannot come ready. Not by a rule
    # invented here: HCS is ignored by a card that did not accept CMD8,
    # and HCS=0 means an SDHC card never returns ready (p.33 sec 4.2.3).
    card, host, ok = booted(image=image(), sdhc=True, send_cmd8=False)
    check("an SDHC card never comes ready when CMD8 is skipped",
          not ok and card.state != sp.TRANSFER
          and any("never cleared in_idle_state" in str(f)
                  for f in host.faults),
          f"ok={ok} state={card.state} "
          f"faults={[str(f) for f in host.faults]}")

    # CMD8 with a broken CRC: R1 only, and exactly the byte Table 7-5
    # prints.
    card = sp.VirtualCard(image=image())
    card.spi_transfer(sp.command_frame(0, 0))
    bad = bytearray(sp.command_frame(8, (1 << 8) | 0xAA))
    bad[5] ^= 0x02
    out = card.spi_transfer(bytes(bad))
    check("a CRC error on CMD8 answers R1=09h and no R7 tail",
          out == bytes([CARD.params["r1_idle_plus_crc_error"].value]),
          f"got {out.hex(' ')}, Table 7-5 prints 09h")

    # A card that echoes the wrong check pattern. The specification's own
    # remedy is to retry CMD8 (p.126 sec 7.2.1) because the communication
    # is not valid; what it must never be is ignored, so the host has to
    # notice the mismatch at all.
    class _BadEcho(sp.VirtualCard):
        def _cmd8(self, argument, crc_ok):
            out = bytearray(super()._cmd8(argument, crc_ok))
            if len(out) == 5:
                out[4] ^= 0xFF
            return bytes(out)

    card = _BadEcho(image=image())
    host = sp.VirtualHost(card)
    check("a wrong check pattern echo stops the init",
          not host.init()
          and any("check pattern" in str(f) for f in host.faults),
          f"faults={[str(f) for f in host.faults]}")

    # A card that cannot run on the supplied voltage echoes VCA=0
    # (Table 7-5, row 3). The host must stop, not carry on into ACMD41.
    card, host, ok = booted(image=image(), supported_vhs=0x2)
    check("a card that answers CMD8 with VCA=0 stops the init",
          not ok and any("VCA=0" in str(f) for f in host.faults),
          f"ok={ok} faults={[str(f) for f in host.faults]}")


# ── D. ACMD41 and APP_CMD ──────────────────────────────────────────────

def test_acmd41():
    print("\nD. CMD55 + ACMD41 (Table 7-4, p.139 sec 7.3.1.3)")

    card = sp.VirtualCard(image=image())
    card.spi_transfer(sp.command_frame(0, 0))
    card.spi_transfer(sp.command_frame(8, (1 << 8) | 0xAA))

    out = card.spi_transfer(sp.command_frame(41, 1 << 30))
    check("ACMD41 without CMD55 in front of it is an illegal command",
          "illegal_command" in sp.r1_flags(out[0]),
          f"flags={sorted(sp.r1_flags(out[0]))} — plain CMD41 is Reserved "
          f"in Table 7-3")

    card.spi_transfer(sp.command_frame(55, 0))
    out = card.spi_transfer(sp.command_frame(41, 1 << 30))
    check("ACMD41 preceded by CMD55 is accepted",
          "illegal_command" not in sp.r1_flags(out[0]))

    # APP_CMD arms exactly one command.
    card.spi_transfer(sp.command_frame(55, 0))
    card.spi_transfer(sp.command_frame(41, 1 << 30))
    out = card.spi_transfer(sp.command_frame(41, 1 << 30))
    check("APP_CMD arms exactly one command, not a mode",
          "illegal_command" in sp.r1_flags(out[0]),
          "the second bare CMD41 must be illegal again")

    # HCS=0 against an SDHC card: never ready.
    card, host, ok = booted(image=image(), sdhc=True, hcs=0)
    check("HCS=0 to an SDHC card never returns ready status",
          not ok and any(f.locator == "p.33 sec 4.2.3"
                         for f in host.faults),
          f"ok={ok} faults={[str(f) for f in host.faults]}")

    # The busy loop actually loops.
    card, host, ok = booted(image=image(), busy_polls=5)
    check("the host polls ACMD41 until in_idle_state clears",
          ok and any("6 poll" in s.outcome for s in host.steps),
          f"steps={[s.outcome for s in host.steps]}")


# ── E. block reads ─────────────────────────────────────────────────────

def test_read():
    print("\nE. CMD17 READ_SINGLE_BLOCK (p.128 sec 7.2.3)")

    card, host, ok = booted()
    check("a block read comes back byte-identical to the card image",
          ok and host.read_block(2) == card.image[2 * BLOCK:3 * BLOCK])

    check("the data token carries the start block token 0xFE",
          sp.TOKEN_START_BLOCK == 0xFE
          and CARD.params["token_start_block"].locator ==
          "p.144 sec 7.3.3.2")

    # Reading before the transfer state.
    early = sp.VirtualCard(image=image())
    early.spi_transfer(sp.command_frame(0, 0))
    out = early.spi_transfer(sp.command_frame(17, 0))
    check("CMD17 outside the transfer state is an illegal command",
          "illegal_command" in sp.r1_flags(out[0]),
          "p.146 sec 7.3.4: command not legal for the card state")

    # Past the end of the card.
    card, host, ok = booted(image=image(4))
    check("a block past the end of the card is a parameter error",
          _raises(lambda: host.read_block(99))
          and any("parameter_error" in str(f) for f in host.faults),
          f"faults={[str(f) for f in host.faults]}")

    # A misaligned byte address on an SDSC card.
    sdsc = sp.VirtualCard(image=image(), sdhc=False, supports_cmd8=False)
    h = sp.VirtualHost(sdsc)
    h.init()
    out = sdsc.spi_transfer(sp.command_frame(17, 3))
    check("a misaligned byte address on SDSC is an address error",
          "address_error" in sp.r1_flags(out[0]),
          f"flags={sorted(sp.r1_flags(out[0]))}")

    # An SDSC card that never got CMD16 has no block length this bench
    # can cite — the power-up default is a CSD field, and the CSD is not
    # modelled. Serving 512 anyway would be a guess that happens to be
    # right for most cards, which is the worst kind.
    raw = sp.VirtualCard(image=image(), sdhc=False, supports_cmd8=False)
    raw.spi_transfer(sp.command_frame(0, 0))
    raw.spi_transfer(sp.command_frame(8, (1 << 8) | 0xAA))
    raw.spi_transfer(sp.command_frame(55, 0))
    raw.spi_transfer(sp.command_frame(41, 0))
    raw.spi_transfer(sp.command_frame(55, 0))
    raw.spi_transfer(sp.command_frame(41, 0))
    raw.spi_transfer(sp.command_frame(55, 0))
    raw.spi_transfer(sp.command_frame(41, 0))
    check("an SDSC card in transfer state without CMD16 refuses to read",
          raw.state == sp.TRANSFER
          and _raises(lambda: raw.spi_transfer(sp.command_frame(17, 0))),
          f"state={raw.state}; the CSD default block length is not modelled")


# ── F. the failures that must not pass quietly ─────────────────────────

def test_corruption():
    print("\nF. corruption, truncation, and read errors")

    # A wrong CRC with no error flag: only recomputation catches it.
    card, host, ok = booted(corrupt_crc_blocks={3})
    check("a block with a corrupted CRC16 is detected",
          _raises(lambda: host.read_block(3))
          and any("CRC16" in str(f) for f in host.faults),
          f"faults={[str(f) for f in host.faults]}")
    check("the neighbouring blocks still read clean",
          host.read_block(2) == card.image[2 * BLOCK:3 * BLOCK]
          and host.read_block(4) == card.image[4 * BLOCK:5 * BLOCK],
          "the CRC check must discriminate, not condemn every block")

    # A short data token. The bug this guards against is returning the
    # bytes that arrived.
    card, host, ok = booted(truncate_blocks={1})
    truncated = None
    try:
        truncated = host.read_block(1)
    except sp.ProtocolError as exc:
        truncated = exc
    check("a truncated data token is a failure, not a short read",
          isinstance(truncated, sp.ProtocolError)
          and "truncated" in str(truncated),
          f"read_block returned {type(truncated).__name__}")
    check("the truncation fault names the token length rule",
          any("data token is" in str(f) for f in host.faults),
          f"faults={[str(f) for f in host.faults]}")

    # A data error token instead of the data (p.145 sec 7.3.3.3). The
    # assertion names that token specifically: an earlier version of this
    # test accepted any fault mentioning "token", and so it still passed
    # when the token check was removed — the short packet tripped the
    # LENGTH check instead and the test could not tell the two apart.
    card, host, ok = booted(read_error_blocks={5})
    err = None
    try:
        host.read_block(5)
    except sp.ProtocolError as exc:
        err = exc
    check("a data error token is reported, not mistaken for data",
          err is not None and "data error token" in str(err),
          f"raised {err!r}")
    check("the data error fault cites the data error token section",
          any(f.locator == "p.145 sec 7.3.3.3" for f in host.faults),
          f"faults={[(f.locator, str(f)) for f in host.faults]}")


# ── G. a real file through the modelled protocol ───────────────────────

def test_file_roundtrip():
    print("\nG. a host directory, read back through CMD17")

    directory = os.path.join(BASE, "software", "main")
    img, layout = sp.build_card_image(directory)
    card = sp.VirtualCard(image=img)
    host = sp.VirtualHost(card).mount(layout)
    check("init succeeds against the directory image", host.init())

    name = max(sorted(layout), key=lambda n: layout[n][1])
    with open(os.path.join(directory, name), "rb") as fh:
        want = fh.read()
    got = host.read_file(name)
    check(f"{name!r} ({len(want)} B) reads back byte-identical",
          got == want,
          f"{len(got)} bytes back, first difference at "
          f"{next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), 'n/a')}")
    check("the read crossed more than one CMD17 block",
          card.blocks_read >= 2, f"blocks_read={card.blocks_read}")
    check("no fault was recorded on a clean read",
          not host.faults and not card.faults,
          f"{[str(f) for f in host.faults + card.faults]}")

    # And the same read with one block corrupted must NOT come back
    # identical — the round-trip test has to be able to fail.
    bad_card = sp.VirtualCard(image=img,
                              corrupt_crc_blocks={layout[name][0]})
    bad_host = sp.VirtualHost(bad_card).mount(layout)
    bad_host.init()
    check("the same round-trip fails when a block is corrupted",
          _raises(lambda: bad_host.read_file(name)),
          "a round-trip test that cannot fail is not evidence")

    # An unmounted name is an error, not an empty read.
    check("reading a name that is not in the layout is an error",
          _raises(lambda: host.read_file("no-such-file")))


# ── H. current accounting ──────────────────────────────────────────────

def test_current():
    print("\nH. current accounting")

    directory = os.path.join(BASE, "software", "main")
    img, layout = sp.build_card_image(directory)
    card = sp.VirtualCard(image=img)
    host = sp.VirtualHost(card).mount(layout)
    host.init()
    host.read_file(max(sorted(layout), key=lambda n: layout[n][1]))
    rows = {r["phase"]: r for r in host.current_report()}

    check("the init phase reports NO current, because none is cited",
          rows["initialisation"]["current"] is None,
          "an interpolated idle current would be an invented number")
    check("the read phase uses the cited 100 mA maximum",
          rows["block read"]["current"] == CARD.params["i_read_max"].value)
    check("the read phase is labelled a maximum, not a typical",
          "MAXIMUM" in rows["block read"]["source"])
    check("the sleep figure is the cited 500 uA typical",
          rows["sleep"]["current"] == CARD.params["i_sleep_typ"].value)
    check("read time is derived from the firmware's own SCLK",
          abs(rows["block read"]["seconds"]
              - host.read_bytes * 8 / sp.firmware_sclk_hz()) < 1e-12,
          f"f_sclk={host.f_sclk}")
    check("the firmware clock is inside the card's Standard Mode ceiling",
          sp.firmware_sclk_hz() <= CARD.params["f_sclk_max_standard"].value,
          f"{sp.firmware_sclk_hz()} Hz vs "
          f"{CARD.params['f_sclk_max_standard'].value} Hz (p.6 sec 1.2)")


# ── I. the demo runs ───────────────────────────────────────────────────

def test_demo():
    print("\nI. the demo")
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = sp.main(["--demo", os.path.join(BASE, "software", "main")])
    out = buf.getvalue()
    check("--demo exits 0 on a clean card", rc == 0, f"rc={rc}")
    check("--demo reports the read as byte-identical",
          "byte-identical to the host file: YES" in out)
    check("--demo prints the unestablished list rather than hiding it",
          "Not modelled, and not silently" in out
          and "i_idle" in out)
    check("--demo prints what the documents say about DAT1/DAT2",
          "RSV" in out and "input on power up" in out)


def run(group):
    """Run one group. An exception escaping a test is a FAIL, not a
    traceback that eats the rest of the suite — the remaining groups
    still have to report."""
    global FAIL
    try:
        group()
    except Exception as exc:                             # noqa: BLE001
        FAIL += 1
        print(f"  FAIL  {group.__name__} raised "
              f"{type(exc).__name__}: {exc}")


def main():
    print("=" * 72)
    print("  Virtual Bench T3.3 — microSD protocol mutation tests")
    print("=" * 72)
    for group in (test_model, test_init, test_cmd8, test_acmd41, test_read,
                  test_corruption, test_file_roundtrip, test_current,
                  test_demo):
        run(group)
    print()
    print("=" * 72)
    print(f"  {PASS} passed, {FAIL} failed")
    print("=" * 72)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
