"""CARD — the microSD card itself, in SPI mode. The part the socket holds.

`sdcard.py` models the **bus**: which net lands on which TF-01A pad. It
could not model the **card**, and said so, because the two documents the
card needs were not in the repo:

    "CMD0 / CMD8 / ACMD41 and their R1/R7 responses need the SD Physical
     Layer Simplified Specification, which this repo does not hold"
    "U6_TF-01A_MicroSD_C91145.pdf is the SOCKET, not the card"

Both are now here, so this model exists. It cites two of them:

* `SDCARD_SanDisk-Industrial-microSD_2016.pdf` — the card. Supply
  currents, supply range, clock ceilings, and the SPI-mode contact table.
  This is the model's own document.
* `SD-SPEC_Physical-Layer-Simplified_v3.01.pdf` — the protocol. Command
  formats, response formats, tokens, the init flow. Cited per-parameter
  through `doc=`, because the protocol is not a property of SanDisk's part.
* `SDCARD_SanDisk-SD-ProdManual_v1.9.pdf` — cited for exactly two things
  the simplified specification renders as pictures instead of text (the
  R1 bit ORDER) or omits entirely (the 74-clock power-up preamble).

## Page numbers are PDF pages, not printed footers

Every locator here is the **PDF page index** — what `pdftotext -f N -l N`
extracts and what a viewer's page box shows — because that is the number
a checker can turn to without arithmetic. The printed footers differ:

    SD spec v3.01                printed page = PDF page - 12
    SanDisk industrial microSD   printed page = PDF page - 2
    SanDisk SD Product Manual    prints chapter-relative numbers (5-13)

So `p.140 sec 7.3.1.4` is Table 7-5, footer 128. Sections are quoted as
the documents number them, and the section is the load-bearing half of
every locator: page numbers move between revisions, `7.3.1.4` does not.

## These are the FULL-SIZE SD contact numbers, not microSD's

SanDisk's tables number nine contacts and head every row "SD Card", under
the sentence *"The host uses a dedicated 9-pin connector to connect to SD
cards"* (p.17 sec 3.1) — the document reuses the full-size SD tables for a
microSD part. A microSD card has **eight** contacts, and its numbering is
shifted: microSD 1 = DAT2, 2 = CD/DAT3, 3 = CMD, 4 = VDD, 5 = CLK, 6 = VSS,
7 = DAT0, 8 = DAT1. `PINS` below transcribes what the document prints, so it
is SD-numbered.

**Do not lay these numbers on the TF-01A socket's pads.** Doing that is what
produced four releases of "U6.9 = DAT2": the socket also has nine pads, but
its ninth is the socket's own **Cd** (card-detect) contact, which no card
contact touches. See `sdcard.py` and CLAIM-006 in hardware/CLAIMS.md.

## The finding this model was written to nail down

`sdcard.py` and `routing.py:6055-6085` both rest on one sentence: an SD
card *"tri-states DAT1/DAT2 once CMD0 has arrived"*, which is why U6.8
(DAT1) sharing the SD_MISO net — and, as it was mislabelled then, U6.9 —
is safe next to GPIO3, a strapping pin.

**Neither document says that.** What they say is better:

* In SPI mode contacts 8 and 9 are `RSV`, Reserved, with a type of "—"
  (p.18 sec 3.1, Table 3-2). No direction at all — not an output that is
  tri-stated, a contact with no assigned function.
* In SD-bus mode, footnote b of the pin table (p.17 sec 3.1): *"The
  extended DAT lines (DAT1-DAT3) are input on power up. They start to
  operate as DAT lines after the SET_BUS_WIDTH"*.

The second is the sentence the strapping analysis actually needed, and it
is about the **right** window. `sdcard.py` is correct that "the firmware
keeps the card in SPI mode" is an argument about the wrong window — the
GPIO3 strap is latched at reset, long before CMD0. The citable answer is
that the card does not drive DAT1 in that window either, because DAT1-DAT3
are inputs from power-up until a bus-width command that SPI mode never
sends. The conclusion survives; the reason it was given for does not.

That argument covers U6.8. It never covered U6.9, which is not a card
contact — see the section above.

Usage:
    from vbench.models.card_microsd import CARD, R1_FLAGS, UNESTABLISHED
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "SDCARD_SanDisk-Industrial-microSD_2016.pdf"
REV = "Rev. 1.0, December 2015"

# The protocol documents, cited per-parameter.
SPEC = "SD-SPEC_Physical-Layer-Simplified_v3.01.pdf"
PMAN = "SDCARD_SanDisk-SD-ProdManual_v1.9.pdf"

# p.17-18 sec 3.1, Table 3-2 "SPI Mode Pin Assignment". Contact 1 is on
# p.17, contacts 2-9 on p.18 — the table straddles the page break, so the
# locators differ per pin rather than all claiming one page.
#
# The "Type" column is the datasheet's own: I = input, O = output,
# PP = push-pull, S = power supply, "—" for the reserved contacts.
PINS = (
    Pin("1", "CS", "in", "p.17 sec 3.1"),
    Pin("2", "DataIn", "in", "p.18 sec 3.1"),
    Pin("3", "VSS1", "gnd", "p.18 sec 3.1"),
    Pin("4", "VDD", "power_in", "p.18 sec 3.1"),
    Pin("5", "SCLK", "in", "p.18 sec 3.1"),
    Pin("6", "VSS2", "gnd", "p.18 sec 3.1"),
    Pin("7", "DataOut", "out", "p.18 sec 3.1"),
    # Contacts 8 and 9 — DAT1 and DAT2 in SD-bus mode — are RSV in SPI
    # mode with no type. `nc` is the closest this schema has to "the
    # document assigns no function"; the power-up direction of the same
    # physical contacts is the SD-bus footnote cited above, and it is an
    # INPUT, which is what the GPIO3 strapping question turns on.
    # These are SD contact numbers. On a microSD card contact 9 does not
    # exist, and TF-01A pad 9 is the socket's Cd contact, not this one.
    Pin("8", "RSV", "nc", "p.18 sec 3.1"),
    Pin("9", "RSV", "nc", "p.18 sec 3.1"),
)

CARD = Model(
    ref="CARD",
    part="microSD-SPI",
    mpn="microSD",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="SanDisk Industrial microSD, doc 02-05-WW-02-00005; the SPI "
             "protocol parameters carry doc= overrides into "
             "SD-SPEC_Physical-Layer-Simplified_v3.01.pdf"),
    pins=PINS,
    params={
        # ── the card: supply, clock, current (SanDisk industrial) ─────
        # p.6 sec 1.2, feature list.
        "v_supply_min": Param(2.7, "V", locator="p.6 sec 1.2"),
        "v_supply_max": Param(3.6, "V", locator="p.6 sec 1.2"),
        "f_sclk_max_standard": Param(25e6, "Hz", locator="p.6 sec 1.2"),
        "f_sclk_max_high_perf": Param(50e6, "Hz", locator="p.6 sec 1.2"),
        "f_sclk_max_uhs": Param(104e6, "Hz", locator="p.6 sec 1.2"),

        # p.15 sec 2.1, Table 6 "Typical Card Power Requirements".
        # The table has two columns and they are NOT interchangeable:
        # read and write are printed under "Maximum Value", sleep under
        # "Typical Value at 25C". Rows below are Standard Mode (25 MHz),
        # the only row this board can reach — see f_sclk_board.
        "i_read_max": Param(100e-3, "A", locator="p.15 sec 2.1"),
        "i_write_max": Param(100e-3, "A", locator="p.15 sec 2.1"),
        "i_sleep_typ": Param(500e-6, "A", locator="p.15 sec 2.1"),

        # ── the protocol (SD Physical Layer Simplified v3.01) ─────────
        # p.133 sec 7.3.1.1, Table 7-1: 48 bits = 6 bytes, start bit,
        # transmission bit, 6-bit index, 32-bit argument, CRC7, end bit.
        "cmd_len_bytes": Param(6, "1", locator="p.133 sec 7.3.1.1",
                               doc=SPEC),
        # p.128 sec 7.2.2: SPI is initialised CRC-OFF, but CMD0 is
        # received while the card is still in SD mode and therefore needs
        # a valid CRC. The document prints the whole frame.
        "cmd0_frame": Param("0x40 0x00 0x00 0x00 0x00 0x95", "1",
                            locator="p.128 sec 7.2.2", doc=SPEC),
        # p.125 sec 7.2 and p.128 sec 7.2.3: SDHC/SDXC block length is
        # fixed at 512 bytes regardless of CMD16.
        "block_len_sdhc": Param(512, "byte", locator="p.128 sec 7.2.3",
                                doc=SPEC),
        # p.128 sec 7.2.3: "A valid data block is suffixed with a 16-bit
        # CRC generated by the standard CCITT polynomial x16+x12+x5+1".
        "data_crc_bits": Param(16, "1", locator="p.128 sec 7.2.3",
                               doc=SPEC),
        # p.144 sec 7.3.3.2, start block token 1111_1110 = 0xFE for
        # single block read/write and multiple block read.
        "token_start_block": Param(0xFE, "1", locator="p.144 sec 7.3.3.2",
                                   doc=SPEC),
        # Same section, multiple block WRITE only: 1111_1100 start,
        # 1111_1101 stop-tran. Modelled but never exercised (read-only).
        "token_start_block_multi_write": Param(
            0xFC, "1", locator="p.144 sec 7.3.3.2", doc=SPEC),
        "token_stop_tran": Param(0xFD, "1", locator="p.144 sec 7.3.3.2",
                                 doc=SPEC),
        # p.141 sec 7.3.2.1 (R1 is one byte, MSB always zero) and
        # p.143 sec 7.3.2.6 / 7.3.2.4 (R7 and R3 are five bytes: R1 then
        # four more).
        "r1_len_bytes": Param(1, "1", locator="p.141 sec 7.3.2.1",
                              doc=SPEC),
        "r3_len_bytes": Param(5, "1", locator="p.143 sec 7.3.2.4",
                              doc=SPEC),
        "r7_len_bytes": Param(5, "1", locator="p.143 sec 7.3.2.6",
                              doc=SPEC),
        # p.140 sec 7.3.1.4, Table 7-5 "Card Operation for CMD8 in SPI
        # Mode". These two are the ONLY numeric R1 bytes printed as text
        # anywhere in the specification, and they are what pins bit 0 and
        # bit 3 down — see R1_BITS below and the UNESTABLISHED entry.
        "r1_idle_only": Param(0x01, "1", locator="p.140 sec 7.3.1.4",
                              doc=SPEC),
        "r1_idle_plus_crc_error": Param(0x09, "1",
                                        locator="p.140 sec 7.3.1.4",
                                        doc=SPEC),
        # p.33 sec 4.2.3: "Card initialization shall be completed within
        # 1 second from the first ACMD41", and the application note on
        # the same page: "The host shall set ACMD41 timeout more than
        # 1 second".
        "t_acmd41_max": Param(1.0, "s", locator="p.33 sec 4.2.3",
                              doc=SPEC),
        # p.31 sec 4.2.1: cards come up with a 400 kHz default clock.
        "f_sclk_identification": Param(400e3, "Hz", locator="p.31 sec 4.2.1",
                                       doc=SPEC),
        # p.104 sec 5.1: OCR bit 30 is Card Capacity Status, bit 31 is
        # the power-up status bit. CCS=1 means SDHC or SDXC.
        "ocr_bit_ccs": Param(30, "1", locator="p.104 sec 5.1", doc=SPEC),
        "ocr_bit_powered_up": Param(31, "1", locator="p.104 sec 5.1",
                                    doc=SPEC),
        # p.56 sec 4.3.1 of the SanDisk manual: "at least 74 clock cycles
        # are required prior to starting bus communication". The
        # simplified specification does not state this anywhere; every
        # working SPI host does it.
        "n_powerup_clocks": Param(74, "1", locator="p.56 sec 4.3.1",
                                  doc=PMAN),

        # ── derived ───────────────────────────────────────────────────
        # One CMD17 block on the wire, in bytes, at the byte-oriented SPI
        # layer: the 6-byte command, the 1-byte R1, the 1-byte start
        # token, the data, and the 2-byte CRC. It excludes the card's own
        # read access time (N_ac), which is a CSD property (TAAC/NSAC)
        # and is NOT modelled — so this is a floor on the transfer, not a
        # prediction of the latency.
        "block_read_bytes": Param(
            522, "byte",
            derived_from=("cmd_len_bytes", "r1_len_bytes",
                          "block_len_sdhc", "data_crc_bits"),
            formula="cmd_len_bytes + r1_len_bytes + 1 start token + "
                    "block_len_sdhc + data_crc_bits/8 = "
                    "6 + 1 + 1 + 512 + 2 = 522 bytes"),
    },
)

# The seven R1 flags, in the order the documents list them. Both the
# specification (p.141 sec 7.3.2.1) and the SanDisk manual's Figure 5-7
# (p.95 sec 5.2.3.1) enumerate them in this order under a "7 ... 0" bit
# ruler with the MSB fixed at zero, so index 0 of this tuple is bit 0.
R1_FLAGS = (
    "in_idle_state",
    "erase_reset",
    "illegal_command",
    "com_crc_error",
    "erase_sequence_error",
    "address_error",
    "parameter_error",
)
R1_BITS = {name: i for i, name in enumerate(R1_FLAGS)}

# Locators for the flag semantics, so a fault raised on a flag can print
# where the flag is defined instead of asserting it.
R1_FLAG_LOCATOR = {
    "in_idle_state": (SPEC, "p.146 sec 7.3.4"),
    "erase_reset": (SPEC, "p.141 sec 7.3.2.1"),
    "illegal_command": (SPEC, "p.146 sec 7.3.4"),
    "com_crc_error": (SPEC, "p.146 sec 7.3.4"),
    "erase_sequence_error": (SPEC, "p.141 sec 7.3.2.1"),
    "address_error": (SPEC, "p.145 sec 7.3.4"),
    "parameter_error": (SPEC, "p.145 sec 7.3.4"),
}

# Where each step of the modelled init flow is written down. The host
# prints these as it runs, so the trace is a citation list, not a log.
INIT_LOCATORS = {
    "power_up_clocks": (PMAN, "p.56 sec 4.3.1",
                        "at least 74 clock cycles before bus communication"),
    "cmd0_enters_spi": (SPEC, "p.126 sec 7.2.1",
                        "the card enters SPI mode if CS is asserted during "
                        "the reception of CMD0, and answers with the SPI "
                        "mode R1 response"),
    "cmd0_frame": (SPEC, "p.128 sec 7.2.2",
                   "CMD0 is received while the card is still in SD mode and "
                   "shall carry a valid CRC: 0x40 0x0 0x0 0x0 0x0 0x95"),
    "cmd8_mandatory": (SPEC, "p.127 sec 7.2.1",
                       "it is mandatory to issue CMD8 prior to the first "
                       "ACMD41"),
    "cmd8_legacy": (SPEC, "p.126 sec 7.2.1",
                    "if the card indicates an illegal command, the card is "
                    "legacy and does not support CMD8"),
    "cmd8_echo": (SPEC, "p.140 sec 7.3.1.4",
                  "Table 7-5: correct CRC and matching VHS gives R1=01h "
                  "with VCA and check pattern echoed back"),
    "acmd41_needs_cmd55": (SPEC, "p.139 sec 7.3.1.3",
                           "Table 7-4: all application specific commands "
                           "shall be preceded with APP_CMD (CMD55)"),
    "acmd41_busy": (SPEC, "p.127 sec 7.2.1",
                    "the host repeatedly issues ACMD41 until in_idle_state "
                    "is 0; while repeating it shall not issue another "
                    "command except CMD0"),
    "acmd41_hcs": (SPEC, "p.33 sec 4.2.3",
                   "if HCS is set to 0, SDHC and SDXC cards never return "
                   "ready status"),
    "acmd41_timeout": (SPEC, "p.33 sec 4.2.3",
                       "card initialization shall be completed within "
                       "1 second from the first ACMD41"),
    "cmd58_ccs": (SPEC, "p.104 sec 5.1",
                  "OCR bit 30, Card Capacity Status: 0 = SDSC, "
                  "1 = SDHC or SDXC"),
    "cmd16_sdsc_only": (SPEC, "p.136 sec 7.3.1.3",
                        "in case of SDSC the block length is set by CMD16; "
                        "for SDHC and SDXC it is fixed to 512 bytes"),
    "cmd17_tokens": (SPEC, "p.128 sec 7.2.3",
                     "a valid read command is answered with a response "
                     "token followed by a data token, and a valid data "
                     "block is suffixed with a 16-bit CCITT CRC"),
    "cmd17_addressing": (SPEC, "p.138 sec 7.3.1.3",
                         "Table 7-3 note 10: SDSC (CCS=0) uses byte unit "
                         "address, SDHC and SDXC (CCS=1) use block unit "
                         "address (512 bytes unit)"),
    "data_error_token": (SPEC, "p.145 sec 7.3.3.3",
                         "if a read fails the card sends a data error "
                         "token instead of the data"),
    "always_responds": (SPEC, "p.125 sec 7.2",
                        "the selected card always responds to the command, "
                        "as opposed to SD mode"),
    "dat_input_on_power_up": (DOC, "p.17 sec 3.1",
                              "Table 3-1 footnote b: the extended DAT lines "
                              "(DAT1-DAT3) are input on power up"),
    "spi_reserved_contacts": (DOC, "p.18 sec 3.1",
                              "Table 3-2: in SPI mode contacts 8 and 9 are "
                              "RSV, Reserved, with no type"),
}

# What is deliberately not modelled. Read by sdcard_protocol.py, which
# refuses to report a number for anything named here.
UNESTABLISHED = {
    "r1_bit_positions":
        "only two R1 bytes appear as TEXT in either document — 01h and "
        "09h in Table 7-5 (p.140 sec 7.3.1.4) — and they establish bit 0 "
        "as in_idle_state and bit 3 as com_crc_error. The full mapping "
        "lives in Figure 7-9 (p.141) and Figure 5-7 of the SanDisk manual "
        "(p.95), both images. R1_BITS takes the ORDER those figures list "
        "the flags in and numbers it from the LSB; that ordering is "
        "consistent with the two text bytes but the remaining five "
        "positions are read off a picture, not a table",
    "i_idle": "the card's current while powered, selected and neither "
              "reading nor sleeping is in no table of the datasheet. "
              "Table 6 (p.15 sec 2.1) has Read, Write and Sleep and "
              "nothing between them, so the init phase's current is "
              "reported as not established rather than interpolated",
    "n_ac_read_latency": "the delay between the read command and the data "
                         "token is TAAC + NSAC from the CSD; the CSD "
                         "table (p.22 sec 3.5) gives TAAC 1.5 ms and "
                         "NSAC 0 for CSD v1.0 cards only, and this model "
                         "does not implement the CSD, so block_read_bytes "
                         "is a wire-time floor and not a latency",
    "csd_default_block_len": "an SDSC card's block length before CMD16 is "
                             "'as specified in the CSD' (Table 7-3 note 2, "
                             "p.138 sec 7.3.1.3). The CSD is not modelled, "
                             "so a modelled SDSC card refuses CMD17 until "
                             "CMD16 has set the length rather than "
                             "assuming 512",
    "crc_on_mode": "CMD59 CRC_ON_OFF is not modelled. SPI is initialised "
                   "CRC-OFF by default (p.128 sec 7.2.2) and the modelled "
                   "host never turns it on, so command CRC7 is generated "
                   "for CMD0 and CMD8 (both mandatory) and left at the "
                   "don't-care value elsewhere",
    "cmd58_ocr_voltage_window": "CMD58 is modelled only far enough to "
                                "return the CCS bit. The OCR voltage "
                                "window bits 15-23 (p.104 sec 5.1) are "
                                "reported as a fixed profile and the host "
                                "does not reject a card on them",
    "write_path": "CMD24/CMD25, the data response token (p.144 sec "
                  "7.3.3.1) and the busy signalling are not modelled. "
                  "This board reads ROMs; nothing writes to the card",
    "multi_block_read": "CMD18 and CMD12 are not modelled. Every read "
                        "goes through CMD17, one block per command, which "
                        "is slower than the firmware's real behaviour and "
                        "therefore never optimistic about throughput",
    "bus_timing": "setup/hold at SCLK is section 7.5 of the "
                  "specification, and section 7.5 reads in full: 'This "
                  "section is a blank for the Simplified Specification' "
                  "(p.147). No timing check is possible from the "
                  "documents in this repo",
    "card_detect_pullup": "the 50 kOhm internal pull-up on CS/CD-DAT3 "
                          "(p.17 sec 3.1 footnote c, ACMD42 at p.139 sec "
                          "7.3.1.3) is not modelled as a load; it is a "
                          "detection aid this design does not use",
}
