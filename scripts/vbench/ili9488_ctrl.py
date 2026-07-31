"""Virtual Bench T3.1 — the ILI9488 controller, as a state machine.

`display.py` checks the wires. This checks the silicon behind them: what the
controller does with a stream of (D/CX, byte) writes, where each pixel lands
once MADCTL has had its say, and whether a 20 MHz write clock actually fits
inside the AC minima of section 17.4.1.

Everything here reads its numbers from `models/ds1_ili9488.py`, which reads
them from `hardware/datasheets/DS1_ILI9488-controller_ILITEK.pdf` with a page
locator on each one. Nothing in this file may hardcode an electrical or
protocol constant — if a number is needed and is not in the model, that is a
missing citation, not a licence to type it here.

Three properties are deliberate:

1. **A wrong-state write is a fault, not a silent no-op.** A firmware init
   sequence that sends RAMWR before SLPOUT produces a dark panel on the
   bench and a dark panel on the desk; a model that quietly accepted the
   pixels would produce a correct-looking framebuffer for a board that shows
   nothing. Every fault carries the locator of the rule it broke.

2. **The 18 bit/pixel byte order is flagged, not asserted.** Figure 111 on
   p.124 is an image; the text layer does not carry the R/G/B sequence. The
   16bpp order IS textual (p.113 note 2). So `PixelFormat.order_cited` is
   True for 16bpp and False for 18bpp, `--demo` prints which one it used,
   and anything that renders in 18bpp inherits a stated convention rather
   than a citation.

3. **check_timing() reports what the clock leaves, and names the half of the
   budget it cannot see.** The controller's tdst/tdht are its requirements
   on the host; whether the ESP32-S3's LCD_CAM meets them needs that chip's
   data-to-WRX skew, which this repo does not hold. Each verdict carries the
   basis of its "available" figure so nobody reads a bus-geometry pass as a
   closed setup/hold loop.

Usage:
    python3 scripts/vbench/ili9488_ctrl.py --demo
"""

import argparse
import collections
import os
import struct
import sys
import zlib

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench.models._schema import require_valid                  # noqa: E402
from vbench.models.ds1_ili9488 import DS1, UNESTABLISHED         # noqa: E402

require_valid(DS1)

P = DS1.params


def _v(name):
    """One cited parameter value. KeyError here means a missing citation."""
    return P[name].value


# ── the model's numbers, named once ───────────────────────────────────────
CMD_SLPIN = _v("cmd_slpin")
CMD_SLPOUT = _v("cmd_slpout")
CMD_DISPON = _v("cmd_dispon")
CMD_CASET = _v("cmd_caset")
CMD_PASET = _v("cmd_paset")
CMD_RAMWR = _v("cmd_ramwr")
CMD_MADCTL = _v("cmd_madctl")
CMD_COLMOD = _v("cmd_colmod")
CMD_RAMWRC = _v("cmd_ramwrc")

BIT_MY = _v("madctl_bit_my")
BIT_MX = _v("madctl_bit_mx")
BIT_MV = _v("madctl_bit_mv")
BIT_ML = _v("madctl_bit_ml")
BIT_BGR = _v("madctl_bit_bgr")
BIT_MH = _v("madctl_bit_mh")

DBI_16BPP = _v("colmod_dbi_16bpp")
DBI_18BPP = _v("colmod_dbi_18bpp")

# Panel extents. 013Fh + 1 = 320 columns, 01DFh + 1 = 480 pages when MV = 0.
WIDTH = _v("caset_max_mv0") + 1
HEIGHT = _v("paset_max_mv0") + 1


Fault = collections.namedtuple("Fault", "code detail locator")

PixelFormat = collections.namedtuple(
    "PixelFormat", "dbi name transfers order order_cited order_locator")

# The two formats section 4.7.3 (p.123) lists as available on the 8-bit
# parallel MCU interface. Anything else is rejected against that page — the
# same page that establishes RGB565 IS available here, which is the finding
# recorded in the model's FINDINGS dict.
FORMATS = {
    DBI_16BPP: PixelFormat(
        dbi=DBI_16BPP, name="16 bit/pixel, RGB 5-6-5 (65K colours)",
        transfers=_v("bus_transfers_per_pixel_16bpp"),
        order="byte0 = R[4:0] G[5:3], byte1 = G[2:0] B[4:0]",
        order_cited=True,
        order_locator="p.113 sec 4.6.3 note 2 ('Previous data byte is "
                      "R [0:4] G [0:2]'), with p.112 sec 4.6.3 note 2 "
                      "('RG - GB')"),
    DBI_18BPP: PixelFormat(
        dbi=DBI_18BPP, name="18 bit/pixel, RGB 6-6-6 (262K colours)",
        transfers=_v("bus_transfers_per_pixel_18bpp"),
        order="byte0 = R[5:0]<<2, byte1 = G[5:0]<<2, byte2 = B[5:0]<<2",
        order_cited=False,
        order_locator="Figure 111, p.124 — an image; the PDF text layer does "
                      "not carry the byte sequence, so this order is a "
                      "stated convention (see UNESTABLISHED)"),
}

# Commands with a fixed parameter count. RAMWR/RAMWRC are absent because
# "There is no restriction on the length of parameters" (p.179, p.201).
FIXED_PARAMS = {
    CMD_SLPIN: 0,
    CMD_SLPOUT: 0,
    CMD_DISPON: 0,
    CMD_CASET: 4,
    CMD_PASET: 4,
    CMD_MADCTL: 1,
    CMD_COLMOD: 1,
}

NAMES = {
    CMD_SLPIN: "SLPIN", CMD_SLPOUT: "SLPOUT", CMD_DISPON: "DISPON",
    CMD_CASET: "CASET", CMD_PASET: "PASET", CMD_RAMWR: "RAMWR",
    CMD_MADCTL: "MADCTL", CMD_COLMOD: "COLMOD", CMD_RAMWRC: "RAMWRC",
}


def _to8_from6(v):
    """6-bit component to 8-bit, replicating the high bits (0..63 -> 0..255)."""
    return (v << 2) | (v >> 4)


def _to8_from5(v):
    return (v << 3) | (v >> 2)


class ILI9488Controller:
    """The controller's write-side behaviour, driven one bus byte at a time.

    The framebuffer is the PHYSICAL panel: index (x, y) with x in [0, 320)
    and y in [0, 480), regardless of what MADCTL is doing to the addressing.
    That is the whole point — a rotation bug shows up as a pixel in the wrong
    physical place, which is what the user sees.
    """

    def __init__(self):
        self.reset()

    # ── reset ─────────────────────────────────────────────────────────
    def reset(self):
        """Hardware reset state, Table 37, p.306 — the one consistent table."""
        self.sleep_in = bool(_v("reset_sleep_in"))
        self.display_on = bool(_v("reset_display_on"))
        self.madctl = _v("reset_madctl")
        self.colmod = _v("reset_colmod")
        self.sc = _v("reset_caset_start")
        self.ec = _v("reset_caset_end")
        self.sp = _v("reset_paset_start")
        self.ep = _v("reset_paset_end")
        # "Frame Memory: Random" (p.306 table 37). None means "the spec does
        # not say what is here", which is not the same as black.
        self.fb = [None] * (WIDTH * HEIGHT)
        self.faults = []
        self.pixels_written = 0
        self.pixels_ignored = 0
        self._cmd = None
        self._params = []
        self._bytes = []
        self._col = self.sc
        self._page = self.sp
        self._ramwr_active = False

    # ── MADCTL bits ───────────────────────────────────────────────────
    def _bit(self, n):
        return (self.madctl >> n) & 1

    @property
    def my(self):
        return self._bit(BIT_MY)

    @property
    def mx(self):
        return self._bit(BIT_MX)

    @property
    def mv(self):
        return self._bit(BIT_MV)

    @property
    def ml(self):
        return self._bit(BIT_ML)

    @property
    def bgr(self):
        return self._bit(BIT_BGR)

    @property
    def mh(self):
        return self._bit(BIT_MH)

    @property
    def col_span(self):
        """How many column addresses exist, per the CASET restriction, p.175."""
        return (_v("caset_max_mv1") if self.mv else _v("caset_max_mv0")) + 1

    @property
    def page_span(self):
        """Per the PASET restriction, p.177 — the mirror image of the above."""
        return (_v("paset_max_mv1") if self.mv else _v("paset_max_mv0")) + 1

    @property
    def fmt(self):
        """The active pixel format, or None if COLMOD holds a rejected code."""
        return FORMATS.get(self.colmod & 0b111)

    # ── address mapping ───────────────────────────────────────────────
    def map_address(self, col, page):
        """Frame-memory (column, page) -> physical (x, y).

        Composed straight off the bit NAMES in the p.192 table and their
        plain-language restatement on p.153 (§5.2.5 Read Display Status):

            MY  "Row Address Order"     0 = Top to Bottom, 1 = Bottom to Top
            MX  "Column Address Order"  0 = Left to Right, 1 = Right to Left
            MV  "Row/Column Exchange"   0 = Normal Mode,   1 = Reverse Mode

        So MX reverses the COLUMN address inside its span, MY reverses the
        PAGE address inside its span, and MV then exchanges which span is
        horizontal. The exchange has to come last: p.175 and p.177 make the
        column span 480 and the page span 320 when D5 = 1, which only makes
        sense if the column counter has become the vertical axis.

        The order of composition is NOT stated in one sentence anywhere in
        the text layer; it is derived from those two restrictions. The
        alternative reading — mirror the physical axes after the exchange —
        agrees with this one at the origin and disagrees one address in, so
        it is declared in UNESTABLISHED["madctl_composition_order"] rather
        than settled here.
        """
        c = (self.col_span - 1 - col) if self.mx else col
        p = (self.page_span - 1 - page) if self.my else page
        if self.mv:
            return p, c          # column address runs down the panel
        return c, p

    # ── the bus ───────────────────────────────────────────────────────
    def write(self, dcx, byte):
        """One WRX rising edge: D/CX level and the byte on DB[7:0].

        p.39 sec 4.1: "When D/CX = 1, DB[23:0] bits are RAM data or command
        parameters. When D/CX = 0, DB[23:0] bits are commands." The ILI9488
        "latches the input data at the rising edge of the WRX signal", so one
        call here is one write cycle and `cycles` counts them.
        """
        if not 0 <= byte <= 0xFF:
            raise ValueError(f"DB[7:0] cannot carry {byte!r}")
        if dcx == _v("dcx_command_level"):
            self._command(byte)
        else:
            self._parameter(byte)

    def write_bytes(self, dcx, data):
        for b in data:
            self.write(dcx, b)

    def command(self, opcode, params=()):
        """Convenience: one command byte then its parameter bytes."""
        self.write(0, opcode)
        self.write_bytes(1, params)

    # ── internals ─────────────────────────────────────────────────────
    def _fault(self, code, detail, locator):
        self.faults.append(Fault(code, detail, locator))

    def _command(self, opcode):
        # A fixed-length command that never received all its parameters, cut
        # short by the next command, is a host bug — the controller keeps the
        # stale register and the firmware believes it wrote a new one.
        if self._cmd in FIXED_PARAMS and self._params:
            want = FIXED_PARAMS[self._cmd]
            if len(self._params) != want:
                self._fault(
                    "truncated_parameters",
                    f"{NAMES.get(self._cmd, hex(self._cmd))} received "
                    f"{len(self._params)} of {want} parameter bytes before "
                    f"{NAMES.get(opcode, hex(opcode))} interrupted it",
                    "p.175 sec 5.2.22")
        self._cmd = opcode
        self._params = []
        self._bytes = []
        self._ramwr_active = False

        if opcode not in NAMES:
            self._fault(
                "unknown_opcode",
                f"opcode {opcode:#04x} is not in the modelled command set "
                f"(section 5.2 lists the standard commands one per page); "
                f"the model refuses to guess what it does",
                "p.140 sec 5.1")
            self._cmd = None
            return

        if opcode == CMD_SLPIN:
            self.sleep_in = True
        elif opcode == CMD_SLPOUT:
            self.sleep_in = False
        elif opcode == CMD_DISPON:
            self.display_on = True
        elif opcode in (CMD_RAMWR, CMD_RAMWRC):
            self._start_ram_write(opcode)

    def _start_ram_write(self, opcode):
        if self.sleep_in:
            # p.201 / p.203: "No access to the frame memory in the Sleep In
            # mode." Taken as governing over RAMWR's own availability grid —
            # see FINDINGS["ramwr_in_sleep_in_is_ambiguous"] in the model.
            self._fault(
                "ram_write_while_sleep_in",
                f"{NAMES[opcode]} ({opcode:#04x}) was issued while the "
                f"controller is in Sleep In. Sleep In is the reset state "
                f"(p.306 table 37), so an init sequence that never sent "
                f"SLPOUT ({CMD_SLPOUT:#04x}) lands here and the panel stays "
                f"dark. No access to the frame memory in the Sleep In mode.",
                "p.201 sec 5.2.35")
            self._ramwr_active = False
            return
        fmt = self.fmt
        if fmt is None:
            self._fault(
                "ram_write_without_usable_format",
                f"{NAMES[opcode]} with COLMOD = {self.colmod:#04x} "
                f"(DBI[2:0] = {self.colmod & 0b111:03b}), which section 4.7.3 "
                f"does not list among the formats available on the 8-bit "
                f"parallel MCU interface",
                "p.123 sec 4.7.3")
            self._ramwr_active = False
            return
        self._ramwr_active = True
        self._bytes = []
        if opcode == CMD_RAMWR:
            # p.179: "The column and page registers are reset to the Start
            # Column (SC) and Start Page (SP)". RAMWRC does NOT reset them
            # (p.201), which is the whole difference between the two.
            self._col = self.sc
            self._page = self.sp

    def _parameter(self, byte):
        if self._cmd is None:
            self._fault(
                "parameter_without_command",
                f"a byte {byte:#04x} arrived with D/CX high but no command "
                f"is active; with D/CX = 1 the bus carries RAM data or "
                f"command parameters, and there is neither",
                "p.39 sec 4.1")
            return
        if self._ramwr_active:
            self._ram_byte(byte)
            return
        self._params.append(byte)
        want = FIXED_PARAMS.get(self._cmd)
        if want is None:
            return
        if len(self._params) > want:
            self._fault(
                "excess_parameters",
                f"{NAMES[self._cmd]} takes {want} parameter byte(s) but "
                f"received {len(self._params)}",
                "p.175 sec 5.2.22")
            return
        if len(self._params) == want:
            self._apply(self._cmd, self._params)

    def _apply(self, opcode, params):
        if opcode == CMD_CASET:
            sc = (params[0] << 8) | params[1]
            ec = (params[2] << 8) | params[3]
            self._set_window("column", sc, ec, self.col_span - 1,
                             "p.175 sec 5.2.22")
        elif opcode == CMD_PASET:
            sp = (params[0] << 8) | params[1]
            ep = (params[2] << 8) | params[3]
            self._set_window("page", sp, ep, self.page_span - 1,
                             "p.177 sec 5.2.23")
        elif opcode == CMD_MADCTL:
            self.madctl = params[0]
            if params[0] & 0b11:
                # D1 and D0 are "Reserved" in the p.192 bit table.
                self._fault(
                    "madctl_reserved_bits_set",
                    f"MADCTL = {params[0]:#04x} sets D1/D0, which the bit "
                    f"table lists as Reserved",
                    "p.192 sec 5.2.30")
        elif opcode == CMD_COLMOD:
            self.colmod = params[0]
            dbi = params[0] & 0b111
            if dbi not in FORMATS:
                self._fault(
                    "pixel_format_unavailable_on_8bit_bus",
                    f"COLMOD parameter {params[0]:#04x} selects DBI[2:0] = "
                    f"{dbi:03b}. Section 4.7.3 'the DBI TYPE B 8-bit parallel "
                    f"bus interface ... IM[2:0] as 011' lists exactly two "
                    f"available formats: 65K RGB 5,6,5 (DBI = 101) and 262K "
                    f"RGB 6,6,6 (DBI = 110). Both are available on this bus — "
                    f"including RGB565, which software/main/display.c says is "
                    f"not.",
                    "p.123 sec 4.7.3")

    def _set_window(self, axis, start, end, limit, locator):
        if start > end:
            # p.175: "SC [15:0] must always be equal to or less than EC [15:0]"
            self._fault(
                "window_start_after_end",
                f"{axis} window start {start:#06x} is greater than end "
                f"{end:#06x}",
                locator)
            return
        if end > limit:
            # p.175 / p.177: "data out of range will be ignored" — silent on
            # the real chip, which is exactly why it is loud here.
            self._fault(
                "window_out_of_range",
                f"{axis} window end {end:#06x} exceeds {limit:#06x}, the "
                f"maximum with MADCTL D5 (MV) = {self.mv}. The controller "
                f"ignores out-of-range data silently, so the missing pixels "
                f"never announce themselves.",
                locator)
        if axis == "column":
            self.sc, self.ec = start, min(end, limit)
        else:
            self.sp, self.ep = start, min(end, limit)

    def _ram_byte(self, byte):
        fmt = self.fmt
        self._bytes.append(byte)
        if len(self._bytes) < fmt.transfers:
            return
        raw, self._bytes = self._bytes, []
        if fmt.dbi == DBI_16BPP:
            # p.113 note 2: the first byte is R[0:4] G[0:2].
            r = _to8_from5(raw[0] >> 3)
            g = _to8_from6(((raw[0] & 0b111) << 3) | (raw[1] >> 5))
            b = _to8_from5(raw[1] & 0b11111)
        else:
            # 18bpp: each byte carries a 6-bit component in its high bits.
            # Sequence R, G, B is the stated convention, not a citation.
            r = _to8_from6(raw[0] >> 2)
            g = _to8_from6(raw[1] >> 2)
            b = _to8_from6(raw[2] >> 2)
        if self.bgr:
            r, b = b, r
        self._store(r, g, b)

    def _store(self, r, g, b):
        if self._col > self.ec or self._page > self.ep:
            # "If the number of pixels exceeds (EC - SC + 1) * (EP - SP + 1),
            # the extra pixels are ignored." (p.179)
            self.pixels_ignored += 1
            return
        x, y = self.map_address(self._col, self._page)
        if 0 <= x < WIDTH and 0 <= y < HEIGHT:
            self.fb[y * WIDTH + x] = (r, g, b)
            self.pixels_written += 1
        else:
            self.pixels_ignored += 1
        self._advance()

    def _advance(self):
        """Counter order per p.179, which states both MADCTL D5 cases."""
        if self.mv:
            self._page += 1
            if self._page > self.ep:
                self._page = self.sp
                self._col += 1
        else:
            self._col += 1
            if self._col > self.ec:
                self._col = self.sc
                self._page += 1

    # ── readout ───────────────────────────────────────────────────────
    def pixel(self, x, y):
        return self.fb[y * WIDTH + x]

    def rgb_rows(self, unwritten=(60, 60, 60)):
        """The framebuffer as rows of (r, g, b).

        `unwritten` stands in for pixels the spec calls Random (p.306
        table 37). It is a placeholder, not a colour the controller produces,
        and `--demo` says so next to the export.
        """
        out = []
        for y in range(HEIGHT):
            row = self.fb[y * WIDTH:(y + 1) * WIDTH]
            out.append([px if px is not None else unwritten for px in row])
        return out


# ── PNG export, stdlib only ───────────────────────────────────────────────
def write_png(path, rows):
    """Write 8-bit RGB rows as a PNG. zlib and struct are enough for this."""
    height = len(rows)
    width = len(rows[0]) if height else 0
    raw = bytearray()
    for row in rows:
        raw.append(0)                       # filter type 0 (None)
        for r, g, b in row:
            raw += bytes((r & 0xFF, g & 0xFF, b & 0xFF))

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 6))
           + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return path


# ── timing ────────────────────────────────────────────────────────────────
TimingVerdict = collections.namedtuple(
    "TimingVerdict", "symbol parameter required available verdict basis locator")

PASS, FAILED, UNEVALUATED = "pass", "FAIL", "not evaluated"


def check_timing(f_write_hz, duty_low=0.5, params=None):
    """Evaluate the section 17.4.1 write-side minima at a given WRX clock.

    `params` defaults to the model's; the tests pass a mutated copy to prove
    this function can actually fail.

    The "available" column is what the clock period leaves under one stated
    assumption about the waveform: the i80 write cycle of Figure 2 (p.41),
    data launched with the WRX falling edge and held until the next one, WRX
    at `duty_low` low duty. That bounds the bus geometry. It does NOT include
    the ESP32-S3's own data-to-WRX skew, which lives in that chip's datasheet
    and not in this repo — so tdst/tdht passing here means "the clock period
    is not the reason they would fail", not "setup and hold are met".
    """
    p = params if params is not None else P
    period = 1.0 / f_write_hz
    low = period * duty_low
    high = period * (1.0 - duty_low)

    budget = (
        ("twc", "Write cycle", "t_wc", period,
         "one WRX period at the given clock"),
        ("twrl", "Write Control pulse L duration", "t_wrl", low,
         f"{duty_low:.0%} of the period"),
        ("twrh", "Write Control pulse H duration", "t_wrh", high,
         f"{1 - duty_low:.0%} of the period"),
        ("tdst", "Write data setup time", "t_dst", low,
         "data launched at the WRX falling edge, latched on its rise "
         "(host skew NOT included)"),
        ("tdht", "Write data hold time", "t_dht", high,
         "data held to the next falling edge (host skew NOT included)"),
        ("tcs", "Chip Select setup time (Write)", "t_cs", period,
         "CSX asserted at least one write cycle before the first WRX rise"),
        ("tast", "Address setup time", "t_ast", low,
         "D/CX settled with the WRX falling edge"),
        ("that", "Address hold time (Write/Read)", "t_aht", high,
         "D/CX held to the next falling edge"),
        ("tchw", "CSX 'H' pulse width", "t_chw", period, "one write cycle"),
        ("tcsf", "Chip Select Wait time (Write/Read)", "t_csf", period,
         "one write cycle"),
    )

    out = []
    for symbol, name, key, available, basis in budget:
        required = p[key].value
        verdict = PASS if available >= required else FAILED
        out.append(TimingVerdict(
            symbol=symbol, parameter=name, required=required,
            available=available, verdict=verdict, basis=basis,
            locator=p[key].locator))
    return out


def timing_failures(verdicts):
    return [v for v in verdicts if v.verdict == FAILED]


# ── demo ──────────────────────────────────────────────────────────────────
def test_pattern(ctrl, fmt_dbi=DBI_16BPP):
    """Drive a frame the way firmware would, and return the byte count.

    Colour bars plus a white marker block in the top-left of the ADDRESSED
    area, so a rotation shows up as the marker moving to a different corner
    of the physical panel.
    """
    ctrl.command(CMD_SLPOUT)
    ctrl.command(CMD_COLMOD, [(fmt_dbi << 4) | fmt_dbi])
    w, h = ctrl.col_span, ctrl.page_span
    ctrl.command(CMD_CASET, [0, 0, (w - 1) >> 8, (w - 1) & 0xFF])
    ctrl.command(CMD_PASET, [0, 0, (h - 1) >> 8, (h - 1) & 0xFF])

    bars = [(255, 0, 0), (0, 255, 0), (0, 0, 255),
            (255, 255, 0), (0, 255, 255), (255, 0, 255), (128, 128, 128)]
    fmt = FORMATS[fmt_dbi]
    payload = bytearray()
    for page in range(h):
        for col in range(w):
            if col < w // 8 and page < h // 8:
                r, g, b = (255, 255, 255)
            else:
                r, g, b = bars[(page * len(bars)) // h]
            payload += encode_pixel(fmt, r, g, b)
    ctrl.command(CMD_RAMWR)
    ctrl.write_bytes(1, payload)
    ctrl.command(CMD_DISPON)
    return len(payload)


def encode_pixel(fmt, r, g, b):
    if fmt.dbi == DBI_16BPP:
        v = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
        return bytes(((v >> 8) & 0xFF, v & 0xFF))
    return bytes((r & 0xFC, g & 0xFC, b & 0xFC))


def _firmware_clock_hz():
    """LCD_CLK_HZ out of board_config.h — read, never retyped."""
    path = os.path.join(BASE, "software", "main", "board_config.h")
    with open(path, errors="replace") as fh:
        for line in fh:
            if line.startswith("#define LCD_CLK_HZ"):
                expr = line.split("LCD_CLK_HZ", 1)[1].split("/*")[0].strip()
                return float(eval(expr, {"__builtins__": {}}, {}))
    raise RuntimeError(f"LCD_CLK_HZ not found in {path}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--demo", action="store_true",
                    help="drive a test frame, export it, print the timing")
    # Under software/build/, which .gitignore already covers. A demo frame is
    # a build artifact, not documentation — the rendered images that DO get
    # committed live in website/static/img/ and are produced by the render
    # scripts, not by this.
    ap.add_argument("--out", default=os.path.join(
        BASE, "software", "build", "vbench", "ili9488-frame.png"),
        help="where to write the demo frame (default: an ignored build dir)")
    ap.add_argument("--clock", type=float, default=None,
                    help="WRX clock in Hz (default: the firmware's)")
    args = ap.parse_args(argv)
    if not args.demo:
        ap.print_help()
        return 0

    f = args.clock if args.clock else _firmware_clock_hz()

    print("=" * 72)
    print("  Virtual Bench T3.1 — the ILI9488 controller, behaviourally")
    print("=" * 72)
    print(f"  Spec   : {DS1.datasheet.doc}")
    print(f"  Rev    : {DS1.datasheet.rev}")
    print(f"  Panel  : {WIDTH} x {HEIGHT} (p.175 013Fh + 1, p.177 01DFh + 1)")
    print()

    ctrl = ILI9488Controller()
    print(f"  Reset state (p.306 table 37): sleep_in={ctrl.sleep_in}, "
          f"display_on={ctrl.display_on}, MADCTL={ctrl.madctl:#04x}, "
          f"COLMOD={ctrl.colmod:#04x}")

    # The reset state is Sleep In, so this write must be refused. It is the
    # single most common firmware init bug and the bench has to see it.
    ctrl.command(CMD_RAMWR)
    ctrl.write(1, 0x00)
    expected = [f for f in ctrl.faults if f.code == "ram_write_while_sleep_in"]
    print(f"  Probe  : RAMWR before SLPOUT -> "
          f"{len(expected)} fault(s), as the spec requires")
    for flt in expected:
        print(f"           [{flt.locator}] {flt.detail}")

    ctrl.reset()
    written = test_pattern(ctrl, DBI_16BPP)
    fmt = ctrl.fmt
    print()
    print(f"  Format : {fmt.name}, {fmt.transfers} transfer(s)/pixel")
    print(f"           byte order {'CITED' if fmt.order_cited else 'CONVENTION'}"
          f" — {fmt.order}")
    print(f"           {fmt.order_locator}")
    print(f"  Frame  : {written} bytes -> {ctrl.pixels_written} pixels "
          f"written, {ctrl.pixels_ignored} ignored")

    # Rotation: the same probe pixel under four MADCTL settings.
    print()
    # Two probes, because (0,0) alone does not discriminate: MY on its own
    # and MV|MX together both send the origin to (0,479). The second column
    # address is what tells them apart.
    print("  MADCTL — where frame-memory (col,page) lands on the panel:")
    print(f"    {'MADCTL':>8}  {'MY MX MV':<10}{'span':<12}"
          f"{'(0,0) ->':<12}{'(1,0) ->':<12}")
    for value in (0x00, 1 << BIT_MX, 1 << BIT_MY, (1 << BIT_MV) | (1 << BIT_MX),
                  (1 << BIT_MV) | (1 << BIT_MY)):
        probe = ILI9488Controller()
        probe.sleep_in = False
        probe.madctl = value
        a = probe.map_address(0, 0)
        b = probe.map_address(1, 0)
        print(f"    {value:#08x}  {probe.my}  {probe.mx}  {probe.mv}    "
              f"{probe.col_span:>3}x{probe.page_span:<7}"
              f"({a[0]:>3},{a[1]:>3})   ({b[0]:>3},{b[1]:>3})")

    out = args.out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    write_png(out, ctrl.rgb_rows())
    print()
    print(f"  Export : {os.path.relpath(out, BASE)}")
    print(f"           unwritten pixels are drawn grey; the spec calls the "
          f"reset frame")
    print(f"           memory Random (p.306 table 37), not black")

    verdicts = check_timing(f)
    period_ns = 1e9 / f
    print()
    print("-" * 72)
    print(f"  i80 write timing at {f / 1e6:.3g} MHz "
          f"(period {period_ns:.1f} ns), section 17.4.1 p.329")
    print(f"  {'sym':<7}{'parameter':<34}{'min':>8}{'avail':>9}  verdict")
    print("  " + "-" * 66)
    for v in verdicts:
        print(f"  {v.symbol:<7}{v.parameter:<34}"
              f"{v.required * 1e9:>7.0f}n{v.available * 1e9:>8.1f}n  "
              f"{v.verdict}")
    print()
    print(f"  Fastest WRX the controller permits: "
          f"{P['f_write_max'].value / 1e6:.3g} MHz "
          f"({P['f_write_max'].formula.split(';')[0]})")

    print()
    print("  Not modelled, and not silently:")
    for key, why in sorted(UNESTABLISHED.items()):
        first = why if len(why) <= 58 else why[:57] + "…"
        print(f"    {key:<28} {first}")

    bad_timing = timing_failures(verdicts)
    print()
    print("=" * 72)
    if ctrl.faults or bad_timing:
        print(f"  FAIL — {len(ctrl.faults)} controller fault(s), "
              f"{len(bad_timing)} timing violation(s)")
        for flt in ctrl.faults:
            print(f"    [{flt.code}] {flt.detail}  ({flt.locator})")
        for v in bad_timing:
            print(f"    [{v.symbol}] needs {v.required * 1e9:.0f} ns, the "
                  f"clock leaves {v.available * 1e9:.1f} ns  ({v.locator})")
        print("=" * 72)
        return 1
    print("  A frame went through the state machine and out as a PNG, and a "
          f"{f / 1e6:.3g} MHz")
    print("  write clock fits every write-side minimum on p.329.")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
