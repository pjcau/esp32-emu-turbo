"""Virtual Bench T3.3 — a microSD card that answers, and a host that asks.

`sdcard.py` checks the four SPI signals against the socket's pad roles and
stops there, because the card's protocol needed two documents the repo did
not hold. It holds them now, so this module builds the half that was
missing: a card state machine that answers real command frames with real
response bytes, and a host that performs the cited init sequence and then
pulls a file off a host directory through 512-byte CMD17 block reads.

Every number comes from `models/card_microsd.py`, which cites it. Nothing
here invents a byte.

## What "reads a file" means, precisely

There is no FAT. `build_card_image()` lays the files of a directory out
linearly, each starting on a 512-byte block boundary, and hands the host
the map out of band. A real host would find that map by reading FAT32
structures — through the same CMD17 path, one block at a time. Parsing
FAT is not what this bench is for: the claim under test is that a byte
written into the card image comes back out of `read_file()` having
crossed a modelled command frame, a modelled response token, a modelled
data token and a modelled CRC. A filesystem in front of that would not
make the claim stronger, and `sdcard.py` was right to refuse to fake one.

## The four things the modelled card will refuse to do

1. **Answer at all before CMD0.** The card powers up in SD mode
   (p.126 sec 7.2.1) and only enters SPI mode if CS is asserted during
   the reception of CMD0. Before that it puts nothing on DataOut.
2. **Return ready for an SDHC card that never saw CMD8.** Not by a rule
   invented here — by two cited ones in series. HCS is ignored by a card
   that did not accept CMD8 (p.33 sec 4.2.3), and "if HCS is set to 0,
   SDHC and SDXC Cards never return ready status" (same section). So the
   card stays busy and the host hits the 1 second ACMD41 timeout. The
   specification never had to write "skipping CMD8 fails"; it follows.
3. **Accept ACMD41 without CMD55 in front of it.** With no APP_CMD
   pending the frame is plain CMD41, which Table 7-3 lists as Reserved
   (p.137 sec 7.3.1.3), so the card sets the illegal command bit.
4. **Read a block outside the transfer state.** Illegal command means
   "command not legal for the card state" (p.146 sec 7.3.4).

## Current accounting, and the number that is missing

Table 6 of the SanDisk datasheet (p.15 sec 2.1) gives three figures for
Standard Mode: Read 100 mA and Write 100 mA under "Maximum Value", Sleep
500 uA under "Typical Value at 25C". It gives nothing for a card that is
powered, selected, and doing neither. So the init phase's current is
printed as NOT ESTABLISHED rather than interpolated — see
`card_microsd.UNESTABLISHED["i_idle"]`. The read phase's current is a
maximum, and the report says so; a total computed from it is an upper
bound on charge, never an estimate.

Usage:
    python3 scripts/vbench/sdcard_protocol.py --demo software/main
"""

import argparse
import dataclasses
import os
import re
import sys
import typing

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE)
sys.path.insert(0, os.path.join(BASE, "scripts"))

from vbench.models.card_microsd import (                     # noqa: E402
    CARD, INIT_LOCATORS, R1_BITS, R1_FLAG_LOCATOR, R1_FLAGS, UNESTABLISHED)

BLOCK = CARD.params["block_len_sdhc"].value
TOKEN_START_BLOCK = CARD.params["token_start_block"].value
CRC_BYTES = CARD.params["data_crc_bits"].value // 8
CMD_BYTES = CARD.params["cmd_len_bytes"].value
T_ACMD41_MAX = CARD.params["t_acmd41_max"].value
F_SCLK_MAX_STANDARD = CARD.params["f_sclk_max_standard"].value
I_READ_MAX = CARD.params["i_read_max"].value
I_SLEEP_TYP = CARD.params["i_sleep_typ"].value
OCR_BIT_CCS = CARD.params["ocr_bit_ccs"].value
OCR_BIT_POWERED_UP = CARD.params["ocr_bit_powered_up"].value

# p.145 sec 7.3.3.3: the data error token. Its four LSBs are the R2 error
# bits; the model only ever raises the generic "error" case, so the
# constant is the token with no error bit set plus the one it does raise.
TOKEN_DATA_ERROR_BASE = 0x00

BOARD_CONFIG = os.path.join(BASE, "software", "main", "board_config.h")
FIRMWARE_SD = os.path.join(BASE, "software", "main", "sdcard.c")


class ProtocolError(Exception):
    """The model was asked something it cannot answer. Never caught to
    continue — a silent fallback here is how a bench starts agreeing
    with whatever it is handed."""


# ── CRC ────────────────────────────────────────────────────────────────

def crc7(data):
    """CRC7, polynomial x^7 + x^3 + 1, for the command frame's CRC field."""
    crc = 0
    for byte in data:
        for i in range(7, -1, -1):
            bit = ((byte >> i) & 1) ^ ((crc >> 6) & 1)
            crc = ((crc << 1) & 0x7F) ^ (0x09 if bit else 0)
    return crc & 0x7F


def crc16_ccitt(data):
    """CRC16 for a data block: x^16 + x^12 + x^5 + 1 (p.128 sec 7.2.3)."""
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 \
                else (crc << 1) & 0xFFFF
    return crc


def _verify_crc7_against_spec():
    """The specification prints one complete command frame — the CMD0
    reset, 0x40 0x0 0x0 0x0 0x0 0x95 (p.128 sec 7.2.2). If this
    implementation of CRC7 does not reproduce that byte, every frame this
    module builds is wrong, so it refuses to import."""
    frame = bytes([0x40, 0, 0, 0, 0])
    got = (crc7(frame) << 1) | 1
    want = int(CARD.params["cmd0_frame"].value.split()[-1], 16)
    if got != want:
        raise ProtocolError(
            f"crc7 produces {got:#04x} for the CMD0 frame, but "
            f"{CARD.params['cmd0_frame'].locator} of "
            f"{CARD.params['cmd0_frame'].doc} prints {want:#04x}")


_verify_crc7_against_spec()


# ── frames and responses ───────────────────────────────────────────────

def command_frame(index, argument):
    """A 6-byte SPI command frame (p.133 sec 7.3.1.1, Table 7-1)."""
    if not 0 <= index <= 63:
        raise ProtocolError(f"command index {index} does not fit 6 bits")
    body = bytes([0x40 | index,
                  (argument >> 24) & 0xFF, (argument >> 16) & 0xFF,
                  (argument >> 8) & 0xFF, argument & 0xFF])
    return body + bytes([(crc7(body) << 1) | 1])


def parse_frame(frame):
    """(index, argument, crc_ok) from a 6-byte frame."""
    if len(frame) != CMD_BYTES:
        raise ProtocolError(
            f"a command frame is {CMD_BYTES} bytes "
            f"({CARD.params['cmd_len_bytes'].locator}), got {len(frame)}")
    if frame[0] & 0xC0 != 0x40:
        raise ProtocolError(
            "start bit / transmission bit are not '01' — Table 7-1 fixes "
            "them at p.133 sec 7.3.1.1")
    index = frame[0] & 0x3F
    argument = int.from_bytes(frame[1:5], "big")
    crc_ok = frame[5] == ((crc7(frame[:5]) << 1) | 1)
    return index, argument, crc_ok


def r1_byte(flags):
    """Encode an R1 response. MSB is always zero (p.141 sec 7.3.2.1)."""
    value = 0
    for flag in flags:
        if flag not in R1_BITS:
            raise ProtocolError(f"{flag!r} is not one of the seven R1 flags")
        value |= 1 << R1_BITS[flag]
    return value


def r1_flags(byte):
    """Decode an R1 byte back to flag names."""
    if byte & 0x80:
        raise ProtocolError(
            f"R1 = {byte:#04x} has its MSB set; p.141 sec 7.3.2.1 fixes it "
            f"at zero, so this is not an R1 response")
    return frozenset(f for f in R1_FLAGS if byte & (1 << R1_BITS[f]))


@dataclasses.dataclass(frozen=True)
class Fault:
    """Something the card or the host did that the documents forbid."""

    where: str
    detail: str
    doc: str
    locator: str

    def __str__(self):
        return f"{self.where}: {self.detail}  [{self.doc} {self.locator}]"


def _fault_from(where, detail, key):
    doc, locator = INIT_LOCATORS[key][0], INIT_LOCATORS[key][1]
    return Fault(where, detail, doc, locator)


# ── the card ───────────────────────────────────────────────────────────

POWER_ON = "power_on"          # in SD mode, has not seen CMD0
IDLE = "idle"                  # SPI mode, in_idle_state = 1
IDENTIFICATION = "identification"   # CMD8 accepted, ACMD41 loop running
TRANSFER = "transfer"          # ACMD41 returned ready


class VirtualCard:
    """A microSD card in SPI mode, at the byte level.

    Faults it raises are recorded on `self.faults` with the locator of the
    rule that was broken, not printed and forgotten.
    """

    def __init__(self, image=b"", sdhc=True, supports_cmd8=True,
                 busy_polls=2, corrupt_crc_blocks=(), read_error_blocks=(),
                 truncate_blocks=(), supported_vhs=0x1):
        if len(image) % BLOCK:
            raise ProtocolError(
                f"a card image is a whole number of {BLOCK}-byte blocks "
                f"({CARD.params['block_len_sdhc'].locator}); got "
                f"{len(image)} bytes")
        self.image = image
        self.sdhc = sdhc
        self.supports_cmd8 = supports_cmd8
        self.busy_polls = busy_polls
        self.corrupt_crc_blocks = frozenset(corrupt_crc_blocks)
        self.read_error_blocks = frozenset(read_error_blocks)
        self.truncate_blocks = frozenset(truncate_blocks)
        # Which VHS value this card accepts. 0001b is 2.7-3.6 V, the
        # range the SanDisk part states (p.6 sec 1.2). A card set to
        # anything else answers CMD8 with VCA=0, which Table 7-5 defines
        # as "the card cannot operate on the supplied voltage".
        self.supported_vhs = supported_vhs

        self.state = POWER_ON
        self.faults = []
        self.blocks_read = 0
        self.bytes_on_wire = 0
        self._app_cmd = False
        self._acmd41_seen = 0
        self._hcs_at_first_acmd41 = None
        self._accepted_cmd8 = False
        # SDHC/SDXC block length is fixed at 512 (p.128 sec 7.2.3). For
        # SDSC it is "the size selected by the SET_BLOCKLEN command", and
        # its power-up default is "as specified in the CSD" (Table 7-3
        # note 2, p.138 sec 7.3.1.3) — the CSD is not modelled, so an
        # SDSC card that has not been given CMD16 has no block length
        # this bench can honestly serve.
        self._block_len = BLOCK if sdhc else None

    # ─ helpers ─
    @property
    def n_blocks(self):
        return len(self.image) // BLOCK

    @property
    def ccs(self):
        """OCR bit 30 (p.104 sec 5.1): 1 for SDHC/SDXC, 0 for SDSC."""
        return 1 if self.sdhc else 0

    def _idle_flag(self):
        return {"in_idle_state"} if self.state != TRANSFER else set()

    def _fault(self, detail, key):
        self.faults.append(_fault_from("card", detail, key))

    # ─ the wire ─
    def spi_transfer(self, frame, cs_asserted=True):
        """Clock a command frame in, return every byte the card clocks out.

        Returns b"" when the card does not answer at all — which in SPI
        mode is itself a finding, because "the selected card always
        responds to the command" (p.125 sec 7.2).
        """
        index, argument, crc_ok = parse_frame(frame)
        out = self._respond(index, argument, crc_ok, cs_asserted)
        self.bytes_on_wire += len(frame) + len(out)
        return out

    def _respond(self, index, argument, crc_ok, cs_asserted):
        app = self._app_cmd
        # APP_CMD arms exactly the next command (p.139 sec 7.3.1.3).
        self._app_cmd = False

        if self.state == POWER_ON:
            # Still in SD mode: it answers CMD0 with CS low and nothing
            # else (p.126 sec 7.2.1).
            if index != 0:
                return b""
            if not cs_asserted:
                self._fault(
                    "CMD0 arrived with CS de-asserted, so the card stayed "
                    "in SD mode and did not answer", "cmd0_enters_spi")
                return b""
            if not crc_ok:
                # CMD0 is received while still in SD mode and therefore
                # needs a valid CRC (p.128 sec 7.2.2).
                self._fault("CMD0 carried an invalid CRC7 while the card "
                            "was still in SD mode", "cmd0_frame")
                return b""
            self.state = IDLE
            return bytes([r1_byte({"in_idle_state"})])

        if index == 0:
            self.state = IDLE
            self._acmd41_seen = 0
            self._hcs_at_first_acmd41 = None
            self._accepted_cmd8 = False
            return bytes([r1_byte({"in_idle_state"})])

        if index == 8:
            return self._cmd8(argument, crc_ok)

        if index == 55:                       # APP_CMD
            self._app_cmd = True
            return bytes([r1_byte(self._idle_flag())])

        if index == 41:
            if not app:
                # Plain CMD41 is Reserved (Table 7-3, p.137 sec 7.3.1.3).
                return bytes([r1_byte(
                    self._idle_flag() | {"illegal_command"})])
            return self._acmd41(argument)

        if index == 58:                       # READ_OCR -> R3
            ocr = (1 << OCR_BIT_POWERED_UP if self.state == TRANSFER else 0)
            ocr |= self.ccs << OCR_BIT_CCS
            ocr |= 0x00FF8000                 # the 2.7-3.6 V window bits
            return bytes([r1_byte(self._idle_flag())]) + \
                ocr.to_bytes(4, "big")

        if index == 16:                       # SET_BLOCKLEN
            if self.sdhc:
                # Accepted, and ignored for memory access
                # (p.136 sec 7.3.1.3).
                return bytes([r1_byte(self._idle_flag())])
            if argument != BLOCK:
                return bytes([r1_byte(
                    self._idle_flag() | {"parameter_error"})])
            self._block_len = argument
            return bytes([r1_byte(self._idle_flag())])

        if index == 17:                       # READ_SINGLE_BLOCK
            return self._cmd17(argument)

        # Anything else this model does not implement is reported as
        # illegal rather than silently accepted.
        return bytes([r1_byte(self._idle_flag() | {"illegal_command"})])

    def _cmd8(self, argument, crc_ok):
        """SEND_IF_COND. Table 7-5, p.140 sec 7.3.1.4."""
        if not self.supports_cmd8:
            # A legacy card: it reports an illegal command, and that is
            # how the host learns it is Ver1.X (p.126 sec 7.2.1).
            return bytes([r1_byte(
                self._idle_flag() | {"illegal_command"})])
        if not crc_ok:
            # "The CMD8 CRC verification is always enabled" — R1 only,
            # 09h, no R7 tail (p.128 sec 7.2.2, p.140 sec 7.3.1.4).
            return bytes([r1_byte({"in_idle_state", "com_crc_error"})])
        vhs = (argument >> 8) & 0x0F
        pattern = argument & 0xFF
        # 'Match' is: exactly one VHS bit set, AND the card supports that
        # voltage (Table 7-5 note *2, both conditions).
        match = bin(vhs).count("1") == 1 and vhs == self.supported_vhs
        self._accepted_cmd8 = True
        if self.state == IDLE:
            self.state = IDENTIFICATION
        vca = vhs if match else 0
        return bytes([r1_byte({"in_idle_state"}), 0x00, 0x00, vca, pattern])

    def _acmd41(self, argument):
        """SD_SEND_OP_COND. p.127 sec 7.2.1 and p.33 sec 4.2.3."""
        hcs = (argument >> 30) & 1
        if self._acmd41_seen == 0:
            # "The card checks the HCS bit in the OCR only at the first
            # ACMD41" (p.127 sec 7.2.1), and a card that did not accept
            # CMD8 ignores HCS entirely (p.33 sec 4.2.3).
            self._hcs_at_first_acmd41 = hcs if self._accepted_cmd8 else 0
        self._acmd41_seen += 1

        if self.sdhc and not self._hcs_at_first_acmd41:
            # "If HCS is set to 0, SDHC and SDXC Cards never return ready
            # status (keep busy bit to 0)" — p.33 sec 4.2.3. This is the
            # whole mechanism behind "skipping CMD8 breaks SDHC init".
            return bytes([r1_byte({"in_idle_state"})])

        if self._acmd41_seen <= self.busy_polls:
            return bytes([r1_byte({"in_idle_state"})])
        self.state = TRANSFER
        return bytes([r1_byte(set())])

    def _cmd17(self, argument):
        """READ_SINGLE_BLOCK. Tokens per p.128 sec 7.2.3 / p.144 sec
        7.3.3.2, addressing per Table 7-3 note 10 (p.138 sec 7.3.1.3)."""
        if self.state != TRANSFER:
            # "Illegal command: command not legal for the card state"
            # (p.146 sec 7.3.4).
            return bytes([r1_byte(
                self._idle_flag() | {"illegal_command"})])

        if self.ccs:
            block = argument
        else:
            if self._block_len is None:
                raise ProtocolError(
                    "CMD17 to an SDSC card that never received CMD16: the "
                    "power-up block length is 'as specified in the CSD' "
                    "(Table 7-3 note 2, p.138 sec 7.3.1.3) and the CSD is "
                    "not modelled, so this bench will not serve a block "
                    "length it cannot cite")
            if argument % BLOCK:
                # "Address error: a misaligned address that did not match
                # the block length" (p.141 sec 7.3.2.1).
                return bytes([r1_byte({"address_error"})])
            block = argument // BLOCK

        if not 0 <= block < self.n_blocks:
            return bytes([r1_byte({"parameter_error"})])

        r1 = bytes([r1_byte(set())])
        if block in self.read_error_blocks:
            # p.145 sec 7.3.3.3: a data error token replaces the data.
            return r1 + bytes([TOKEN_DATA_ERROR_BASE | 0x04])

        data = self.image[block * BLOCK:(block + 1) * BLOCK]
        crc = crc16_ccitt(data)
        if block in self.corrupt_crc_blocks:
            crc ^= 0xFFFF
        packet = bytes([TOKEN_START_BLOCK]) + data + crc.to_bytes(2, "big")
        if block in self.truncate_blocks:
            packet = packet[:-(CRC_BYTES + 7)]
        self.blocks_read += 1
        return r1 + packet


# ── the host ───────────────────────────────────────────────────────────

@dataclasses.dataclass
class Step:
    """One step of the init sequence, with where it is written down."""

    name: str
    outcome: str
    key: str

    def citation(self):
        doc, locator, quote = INIT_LOCATORS[self.key]
        return doc, locator, quote


class VirtualHost:
    """A host that performs the cited SPI init flow, then reads blocks.

    `f_sclk_hz` defaults to the firmware's own SD_SPI_FREQ_KHZ, so the
    current and time figures describe this board rather than a generic
    one.
    """

    def __init__(self, card, f_sclk_hz=None, hcs=1, send_cmd8=True):
        self.card = card
        self.f_sclk = f_sclk_hz if f_sclk_hz is not None \
            else firmware_sclk_hz()
        self.hcs = hcs
        self.send_cmd8 = send_cmd8
        self.faults = []
        self.steps = []
        self.ccs = None
        self.layout = {}
        self.init_bytes = 0
        self.read_bytes = 0
        self._initialised = False

    # ─ helpers ─
    def _cmd(self, index, argument=0, cs_asserted=True):
        frame = command_frame(index, argument)
        out = self.card.spi_transfer(frame, cs_asserted=cs_asserted)
        return out

    def _step(self, name, outcome, key):
        self.steps.append(Step(name, outcome, key))

    def _fault(self, detail, key):
        self.faults.append(_fault_from("host", detail, key))

    # ─ initialisation ─
    def init(self):
        """The flow of Figure 7-2 (p.127 sec 7.2.1). True on success."""
        before = self.card.bytes_on_wire

        self._step("power-up clocks",
                   f"{CARD.params['n_powerup_clocks'].value} clocks with CS "
                   f"high before any command", "power_up_clocks")

        out = self._cmd(0)
        if not out:
            self._fault("CMD0 got no response, so the card never entered "
                        "SPI mode", "cmd0_enters_spi")
            self.init_bytes = self.card.bytes_on_wire - before
            return False
        flags = r1_flags(out[0])
        if "in_idle_state" not in flags:
            self._fault(f"CMD0 answered {sorted(flags)} without "
                        f"in_idle_state", "cmd0_enters_spi")
            self.init_bytes = self.card.bytes_on_wire - before
            return False
        self._step("CMD0 GO_IDLE_STATE",
                   "R1 = in_idle_state, the card is in SPI mode",
                   "cmd0_enters_spi")

        version_2 = False
        if self.send_cmd8:
            # VHS = 0001 (2.7-3.6 V), check pattern 0xAA.
            out = self._cmd(8, (0x1 << 8) | 0xAA)
            flags = r1_flags(out[0])
            if "illegal_command" in flags:
                self._step("CMD8 SEND_IF_COND",
                           "illegal command — the card is Ver1.X / SDSC, "
                           "so the host must send HCS=0",
                           "cmd8_legacy")
                self.hcs = 0
            elif "com_crc_error" in flags:
                self._fault("CMD8 answered with a CRC error; its CRC "
                            "verification is always enabled",
                            "cmd8_echo")
                self.init_bytes = self.card.bytes_on_wire - before
                return False
            else:
                if len(out) != CARD.params["r7_len_bytes"].value:
                    self._fault(f"R7 is "
                                f"{CARD.params['r7_len_bytes'].value} bytes, "
                                f"the card sent {len(out)}", "cmd8_echo")
                    self.init_bytes = self.card.bytes_on_wire - before
                    return False
                vca, pattern = out[3] & 0x0F, out[4]
                if pattern != 0xAA:
                    self._fault(f"CMD8 echoed check pattern {pattern:#04x}, "
                                f"not 0xAA", "cmd8_echo")
                    self.init_bytes = self.card.bytes_on_wire - before
                    return False
                if vca == 0:
                    self._fault("CMD8 returned VCA=0: the card cannot "
                                "operate on the supplied voltage",
                                "cmd8_echo")
                    self.init_bytes = self.card.bytes_on_wire - before
                    return False
                version_2 = True
                self._step("CMD8 SEND_IF_COND",
                           f"R7 echoed VCA={vca:#x} and pattern "
                           f"{pattern:#04x} — Ver2.00 or later",
                           "cmd8_echo")
        else:
            self._step("CMD8 SEND_IF_COND",
                       "SKIPPED by this host, against the specification",
                       "cmd8_mandatory")

        # ACMD41 loop, bounded by the cited 1 second timeout. Wall time is
        # not simulated; the bound is expressed in polls, each of which
        # costs a full command/response on the wire.
        max_polls = self._acmd41_poll_budget()
        ready = False
        for poll in range(1, max_polls + 1):
            r1 = r1_flags(self._cmd(55)[0])
            if "illegal_command" in r1:
                self._fault("CMD55 APP_CMD was rejected",
                            "acmd41_needs_cmd55")
                break
            out = self._cmd(41, (self.hcs & 1) << 30)
            flags = r1_flags(out[0])
            if "illegal_command" in flags:
                self._fault("ACMD41 came back illegal — APP_CMD did not "
                            "arm it", "acmd41_needs_cmd55")
                break
            if "in_idle_state" not in flags:
                ready = True
                self._step("CMD55 + ACMD41 SD_SEND_OP_COND",
                           f"ready after {poll} poll(s) with HCS="
                           f"{self.hcs}", "acmd41_busy")
                break
        if not ready and not self.faults:
            self._fault(
                f"the card never cleared in_idle_state within the "
                f"{T_ACMD41_MAX} s budget ({max_polls} polls at "
                f"{self.f_sclk/1e6:.0f} MHz)"
                + (" — HCS=0 was sent to an SDHC card"
                   if self.hcs == 0 else ""),
                "acmd41_timeout")
        if not ready:
            self.init_bytes = self.card.bytes_on_wire - before
            return False

        out = self._cmd(58)
        if len(out) != CARD.params["r3_len_bytes"].value:
            self._fault(f"R3 is {CARD.params['r3_len_bytes'].value} bytes, "
                        f"the card sent {len(out)}", "cmd58_ccs")
            self.init_bytes = self.card.bytes_on_wire - before
            return False
        ocr = int.from_bytes(out[1:5], "big")
        self.ccs = (ocr >> OCR_BIT_CCS) & 1 if version_2 else 0
        self._step("CMD58 READ_OCR",
                   f"CCS={self.ccs} — "
                   f"{'SDHC/SDXC, block addressing' if self.ccs else 'SDSC, byte addressing'}",
                   "cmd58_ccs")

        if not self.ccs:
            r1 = r1_flags(self._cmd(16, BLOCK)[0])
            if r1:
                self._fault(f"CMD16 SET_BLOCKLEN({BLOCK}) answered "
                            f"{sorted(r1)}", "cmd16_sdsc_only")
                self.init_bytes = self.card.bytes_on_wire - before
                return False
            self._step("CMD16 SET_BLOCKLEN",
                       f"{BLOCK} bytes — SDSC only; SDHC ignores it",
                       "cmd16_sdsc_only")

        self.init_bytes = self.card.bytes_on_wire - before
        self._initialised = True
        return True

    def _acmd41_poll_budget(self):
        """How many CMD55+ACMD41 pairs fit in the cited 1 second."""
        pair_bytes = 2 * (CMD_BYTES + 1)
        return max(1, int(T_ACMD41_MAX * self.f_sclk / (8 * pair_bytes)))

    # ─ block reads ─
    def read_block(self, block):
        """One CMD17. Returns the 512 data bytes, or raises."""
        if not self._initialised:
            raise ProtocolError(
                "read_block before a successful init — the card is not in "
                "the transfer state (p.146 sec 7.3.4)")
        before = self.card.bytes_on_wire
        argument = block if self.ccs else block * BLOCK
        out = self._cmd(17, argument)
        self.read_bytes += self.card.bytes_on_wire - before

        flags = r1_flags(out[0])
        if flags:
            for flag in sorted(flags):
                doc, locator = R1_FLAG_LOCATOR[flag]
                self.faults.append(Fault(
                    "host", f"CMD17 block {block} answered with {flag}",
                    doc, locator))
            raise ProtocolError(f"CMD17 block {block}: R1 = {sorted(flags)}")

        packet = out[1:]
        if not packet:
            raise ProtocolError(f"CMD17 block {block} returned no token")
        token = packet[0]
        if token != TOKEN_START_BLOCK:
            self.faults.append(_fault_from(
                "host",
                f"block {block} came back with token {token:#04x}, not the "
                f"start block token {TOKEN_START_BLOCK:#04x}",
                "data_error_token"))
            raise ProtocolError(
                f"CMD17 block {block}: data error token {token:#04x}")

        want = 1 + BLOCK + CRC_BYTES
        if len(packet) != want:
            # A short packet is a failure, never a partial success — the
            # data token's length is fixed by the block length.
            self.faults.append(_fault_from(
                "host",
                f"block {block} data token is {len(packet)} bytes, not "
                f"{want} ({BLOCK} data + {CRC_BYTES} CRC + 1 token)",
                "cmd17_tokens"))
            raise ProtocolError(
                f"CMD17 block {block}: truncated data token "
                f"({len(packet)} of {want} bytes)")

        data = packet[1:1 + BLOCK]
        got_crc = int.from_bytes(packet[1 + BLOCK:], "big")
        want_crc = crc16_ccitt(data)
        if got_crc != want_crc:
            self.faults.append(_fault_from(
                "host",
                f"block {block} CRC16 is {got_crc:#06x}, the data gives "
                f"{want_crc:#06x}", "cmd17_tokens"))
            raise ProtocolError(
                f"CMD17 block {block}: CRC mismatch "
                f"{got_crc:#06x} != {want_crc:#06x}")
        return data

    # ─ the directory ─
    def mount(self, layout):
        """Take the linear directory map. This is NOT a filesystem: the
        map is handed over out of band, because parsing FAT32 would add a
        second thing under test without making the first one stronger."""
        self.layout = dict(layout)
        return self

    def read_file(self, name):
        """Stream a mounted file through CMD17 block reads."""
        if name not in self.layout:
            raise ProtocolError(
                f"{name!r} is not in the mounted layout "
                f"({sorted(self.layout)})")
        start, size = self.layout[name]
        out = bytearray()
        block = start
        while len(out) < size:
            out += self.read_block(block)
            block += 1
        return bytes(out[:size])

    # ─ current ─
    def current_report(self):
        """Per-phase charge, from the cited figures only."""
        t_init = self.init_bytes * 8 / self.f_sclk
        t_read = self.read_bytes * 8 / self.f_sclk
        return [
            {"phase": "initialisation",
             "bytes": self.init_bytes, "seconds": t_init,
             "current": None,
             "source": "not established — Table 6 (p.15 sec 2.1) has "
                       "Read, Write and Sleep and nothing between them"},
            {"phase": "block read",
             "bytes": self.read_bytes, "seconds": t_read,
             "current": I_READ_MAX,
             "source": f"{I_READ_MAX*1e3:.0f} mA MAXIMUM, Standard Mode "
                       f"25 MHz (p.15 sec 2.1) — an upper bound, not a "
                       f"typical"},
            {"phase": "sleep",
             "bytes": 0, "seconds": None,
             "current": I_SLEEP_TYP,
             "source": f"{I_SLEEP_TYP*1e6:.0f} uA typical at 25 C "
                       f"(p.15 sec 2.1); entered automatically after an "
                       f"operation (p.8 sec 1.5.5)"},
        ]


# ── laying a host directory out on a card ──────────────────────────────

def build_card_image(directory, spare_blocks=1):
    """Concatenate a directory's files, each block-aligned.

    Returns (image, layout) where layout maps name -> (start_block, size).
    """
    if not os.path.isdir(directory):
        raise ProtocolError(f"{directory} is not a directory")
    names = sorted(n for n in os.listdir(directory)
                   if os.path.isfile(os.path.join(directory, n)))
    if not names:
        raise ProtocolError(f"{directory} holds no regular files")
    image = bytearray()
    layout = {}
    for name in names:
        with open(os.path.join(directory, name), "rb") as fh:
            blob = fh.read()
        layout[name] = (len(image) // BLOCK, len(blob))
        image += blob
        pad = (-len(image)) % BLOCK
        image += b"\x00" * pad
    image += b"\x00" * (BLOCK * spare_blocks)
    return bytes(image), layout


# ── the firmware, against the same documents ───────────────────────────

def firmware_sclk_hz():
    """SD_SPI_FREQ_KHZ out of board_config.h. Missing is an error."""
    with open(BOARD_CONFIG) as fh:
        text = fh.read()
    m = re.search(r"#define\s+SD_SPI_FREQ_KHZ\s+(\d+)", text)
    if not m:
        raise ProtocolError(
            f"SD_SPI_FREQ_KHZ is not defined in {BOARD_CONFIG} — the bench "
            f"will not substitute a clock the firmware does not set")
    return int(m.group(1)) * 1000


def firmware_findings():
    """What sdcard.c does, checked against the two cited documents."""
    findings = []
    f_sclk = firmware_sclk_hz()
    findings.append((
        "OK" if f_sclk <= F_SCLK_MAX_STANDARD else "FAULT",
        f"SD_SPI_FREQ_KHZ = {f_sclk/1e6:.0f} MHz against the card's "
        f"{F_SCLK_MAX_STANDARD/1e6:.0f} MHz Standard Mode ceiling "
        f"(p.6 sec 1.2)"))

    with open(FIRMWARE_SD) as fh:
        src = fh.read()

    performs_init = any(tok in src for tok in ("CMD0", "ACMD41", "SEND_IF_COND"))
    findings.append((
        "NOTE",
        "sdcard.c issues no command of its own: the whole cited init flow "
        "(CMD0, CMD8, CMD55+ACMD41, CMD58) happens inside ESP-IDF's "
        "esp_vfs_fat_sdspi_mount, so nothing in this repo's source can be "
        "checked against Figure 7-2 — this model is the only place the "
        "sequence is written down"
        if not performs_init else
        "sdcard.c names SD commands directly; compare its sequence with "
        "the Figure 7-2 flow modelled here"))

    if "SD spec requires pull-ups" in src:
        findings.append((
            "NOTE",
            "sdcard.c comments that 'SD spec requires pull-ups on "
            "CMD(MOSI), DAT0(MISO), CLK, DAT3(CS)'. The simplified "
            "specification in this repo does not state that anywhere — its "
            "bus-circuitry chapter is not included, and the only pull-up it "
            "mentions is the card's own 50 kOhm on CS/CD-DAT3 (p.139 sec "
            "7.3.1.3, ACMD42). The pull-ups are good practice; the citation "
            "in the comment is not checkable against the documents here"))

    return findings


def dat_line_finding():
    """What the documents actually say about DAT1/DAT2 in SPI mode.

    `sdcard.py` and routing.py:6055-6085 both rest on "the card tri-states
    DAT1/DAT2 once CMD0 has arrived". Neither document says it.
    """
    return [INIT_LOCATORS["spi_reserved_contacts"],
            INIT_LOCATORS["dat_input_on_power_up"]]


# ── demo ───────────────────────────────────────────────────────────────

def _print_trace(host):
    print("  Init sequence (Figure 7-2, p.127 sec 7.2.1):")
    for step in host.steps:
        doc, locator, quote = step.citation()
        print(f"    {step.name:<28} {step.outcome}")
        print(f"      {locator:<18} {quote[:80]}")


def _print_current(host):
    print(f"  {'phase':<16} {'bytes':>8} {'time':>10} {'current':>10}  "
          f"source")
    print("  " + "-" * 88)
    total_charge = 0.0
    for row in host.current_report():
        t = f"{row['seconds']*1e3:.3f} ms" if row["seconds"] is not None \
            else "n/a"
        if row["current"] is None:
            cur = "NOT EST."
        elif row["current"] < 1e-3:
            cur = f"{row['current']*1e6:.0f} uA"
        else:
            cur = f"{row['current']*1e3:.1f} mA"
        print(f"  {row['phase']:<16} {row['bytes']:>8} {t:>10} {cur:>10}  "
              f"{row['source'][:60]}")
        if row["current"] is not None and row["seconds"] is not None:
            total_charge += row["current"] * row["seconds"]
    print()
    print(f"  Charge drawn by the modelled read phase: "
          f"{total_charge*1e6:.1f} uC (UPPER BOUND — the read figure is a "
          f"maximum)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--demo", metavar="DIR",
                    help="host directory to lay out on the virtual card")
    ap.add_argument("--file", help="which file to read back (default: the "
                                   "largest, so more than one block moves)")
    args = ap.parse_args(argv)

    directory = args.demo or os.path.join(BASE, "software", "main")

    print("=" * 78)
    print("  Virtual Bench T3.3 — microSD over SPI, protocol modelled")
    print("=" * 78)

    try:
        image, layout = build_card_image(directory)
    except ProtocolError as exc:
        print(f"  ERROR  {exc}", file=sys.stderr)
        return 2

    card = VirtualCard(image=image, sdhc=True)
    host = VirtualHost(card).mount(layout)

    print(f"  Card:  SDHC, {card.n_blocks} blocks of {BLOCK} B = "
          f"{len(image)/1024:.1f} KiB, image laid out from {directory}")
    print(f"  Host:  SCLK = {host.f_sclk/1e6:.0f} MHz "
          f"(SD_SPI_FREQ_KHZ in board_config.h)")
    print()

    if not host.init():
        print("  Init FAILED:")
        for fault in host.faults + card.faults:
            print(f"    {fault}")
        return 1
    _print_trace(host)
    print()

    name = args.file or max(sorted(layout), key=lambda n: layout[n][1])
    try:
        got = host.read_file(name)
    except ProtocolError as exc:
        print(f"  Read FAILED: {exc}")
        for fault in host.faults + card.faults:
            print(f"    {fault}")
        return 1

    with open(os.path.join(directory, name), "rb") as fh:
        want = fh.read()
    identical = got == want
    start, size = layout[name]
    blocks = -(-size // BLOCK)
    print(f"  Read back {name!r}: {size} bytes over {blocks} CMD17 block "
          f"read(s) from block {start}")
    print(f"    byte-identical to the host file: "
          f"{'YES' if identical else 'NO'}")
    print()

    print("  Current accounting:")
    _print_current(host)
    print()

    print("  Firmware against the same documents:")
    for verdict, text in firmware_findings():
        print(f"    [{verdict}] {text}")
    print()

    print("  What the documents say about DAT1/DAT2 in SPI mode:")
    for doc, locator, quote in dat_line_finding():
        print(f"    {locator:<16} {quote}")
    print("    Neither says 'tri-stated after CMD0'. The power-up input "
          "state is the")
    print("    citable reason U6.9 on GPIO3 is inert in the strapping "
          "window.")
    print()

    print("  Not modelled, and not silently:")
    for key in sorted(UNESTABLISHED):
        print(f"    {key:<28} {UNESTABLISHED[key][:88]}")

    print()
    print("=" * 78)
    faults = host.faults + card.faults
    if faults or not identical:
        print(f"  FAIL — {len(faults)} protocol fault(s)"
              f"{'' if identical else ', and the read-back differs'}")
        for fault in faults:
            print(f"    {fault}")
        print("=" * 78)
        return 1
    print(f"  {card.blocks_read} block(s) crossed the modelled protocol "
          f"byte-identical.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
