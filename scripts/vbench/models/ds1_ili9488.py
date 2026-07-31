"""DS1 — the ILI9488 CONTROLLER, from the ILITEK specification itself.

`display.py` has always been able to check the panel's WIRING: which J4 pad
each of the 40 panel pins touches, that the IM straps select 8080 8-bit, that
DB0..DB7 arrive in order. What it could not check was anything the silicon
DOES with those wires, and it said so — its `UNMODELLED` dict named the
command set, MADCTL, the pixel format and the 20 MHz timing budget as
"needs the CONTROLLER datasheet, which this repo does not hold".

The repo now holds it: `hardware/datasheets/DS1_ILI9488-controller_ILITEK.pdf`,
343 pages, footer "Version: 100", ILI Technology Corp. Every page footer reads
"Page N of 343" and N equals the PDF page index, so a locator here can be
turned to directly with `pdftotext -f N -l N`.

Two things this file establishes that the repo previously had backwards.

**1. RGB565 over the 8-bit parallel bus is SUPPORTED, and the firmware says
it is not.** `software/main/display.c` opens with

    NOTE: ILI9488 in 8-bit parallel mode only supports RGB666 (18-bit color,
    3 bytes/pixel).

Section 4.7.3, p.123, "8-bit Parallel MCU Interface", lists the available
display data formats for exactly that interface:

    65K-Colors, RGB 5, 6, 5 bits input data (set Standard Command 3Ah,
                                             DBI [2:0] as 101)
    262K-Colors, RGB 6, 6, 6 bits input data (set Standard Command 3Ah,
                                              DBI [2:0] as 110)

and gives 4.7.3.1 its own subsection and figure (Figure 110) for the 16
bit/pixel case, with p.124 note 2 stating "2-times transfer is used to
transmit 1 pixel data to the 16-bit color depth information". The COLMOD
table itself (p.200) lists DBI [2:0] = 101 as "16 bits / pixel" with no
interface qualifier. Nothing in the text layer restricts DBI = 101 to the
16-bit bus. `software/sim/vbench_hal.c:110` already assumes the supported
reading ("RGB565 crosses the 8-bit 8080 bus as two byte transfers"), so the
repo contradicts itself; the spec sides with the HAL. This is
memory/feedback_comment_outranked_datasheet.md happening a second time —
a justification comment asserting a datasheet restriction the datasheet
does not contain. Consequence: at 3 bytes/pixel the firmware moves 1.5x the
bus traffic RGB565 would need, on a 20 MHz bus that is already the frame-rate
bottleneck. This model does NOT change the firmware; it records the finding
so the claim cannot regress silently (see `FINDINGS` and the test suite).

**2. The reset state is one table, not nine.** Every command page carries
its own "Default Value" box and they disagree — p.175 gives HW-reset
EC = 013Fh while p.177 gives HW-reset EP = 01EFh (479+1 is 01E0h; 01EFh is
neither the 480th nor the 320th address). Table 37, p.306, "Initial Values
of Registers", is the one table that states all of them together and is
self-consistent: Sleep In, Display Off, frame memory Random, SC/EC =
0000h/013Fh, SP/EP = 0000h/01DFh, MADCTL 00h, COLMOD 06h. Every reset value
below cites p.306 table 37 for that reason, not the per-command boxes.

What this file is NOT: an electrical model. The ILI9488 is a bare die
bonded into the panel module, so it has pads and no package pins, its supply
rails are inside the module, and none of that is on this board's netlist.
The `pins` tuple below is the bus interface only, keyed by the spec's own
pin NAMES (section 3.3 is a name-keyed table; the die's numbered pads are
section 3.4/3.5 and are irrelevant to a 40-pin FPC).

The behavioural half lives in `scripts/vbench/ili9488_ctrl.py`.
"""

from ._schema import DatasheetRef, Model, Param, Pin

DOC = "DS1_ILI9488-controller_ILITEK.pdf"
REV = "V100 (Version: 100, printed in every page footer)"

# Section 3.3 "Pin Descriptions", the "Bus Interface Pins" table. The table is
# keyed by pin NAME, so the Pin.number field carries the name — writing an
# invented number here would be the fabrication the schema exists to stop.
# DB[23:0] is one row of that table and continues onto p.24; in DBI Type B
# 8-bit only DB[7:0] is in use (Table 3, p.39).
PINS = (
    Pin("RESX", "RESX", "in", "p.23 sec 3.3"),
    Pin("CSX", "CSX", "in", "p.23 sec 3.3"),
    Pin("D/CX", "D/CX", "in", "p.23 sec 3.3"),
    Pin("WRX", "WRX/SCL", "in", "p.23 sec 3.3"),
    Pin("RDX", "RDX", "in", "p.23 sec 3.3"),
    Pin("IM2", "IM2", "in", "p.23 sec 3.3"),
    Pin("IM1", "IM1", "in", "p.23 sec 3.3"),
    Pin("IM0", "IM0", "in", "p.23 sec 3.3"),
    Pin("DB0", "DB0", "inout", "p.24 sec 3.3"),
    Pin("DB1", "DB1", "inout", "p.24 sec 3.3"),
    Pin("DB2", "DB2", "inout", "p.24 sec 3.3"),
    Pin("DB3", "DB3", "inout", "p.24 sec 3.3"),
    Pin("DB4", "DB4", "inout", "p.24 sec 3.3"),
    Pin("DB5", "DB5", "inout", "p.24 sec 3.3"),
    Pin("DB6", "DB6", "inout", "p.24 sec 3.3"),
    Pin("DB7", "DB7", "inout", "p.24 sec 3.3"),
)

DS1 = Model(
    ref="DS1",
    part="ILI9488",
    mpn="ILI9488",
    datasheet=DatasheetRef(
        doc=DOC, rev=REV,
        note="ILI Technology Corp., 'a-Si TFT LCD Single Chip Driver, "
             "320RGB x 480 Resolution and 16.7M-color'; page footers read "
             "'Page N of 343', N == PDF page index"),
    pins=PINS,
    params={
        # ── interface selection and bus protocol ────────────────────────
        # Table 3 "Interface Selection": IM2:IM1:IM0 = 011 is DBI Type B
        # 8-bit, command/parameter on DB[7:0], GRAM on DB[7:0]. This is the
        # strap combination display.py reads off the copper.
        "im_strap_dbi_b_8bit": Param("011", "1", locator="p.39 table 3"),
        # "The ILI9488 latches the input data at the rising edge of the WRX
        # signal." — so WRX rising is the sampling instant every timing
        # number below is measured against.
        "wrx_latch_edge": Param("rising", "1", locator="p.39 sec 4.1"),
        # "When D/CX = 1, DB[23:0] bits are RAM data or command parameters.
        # When D/CX = 0, DB[23:0] bits are commands."
        "dcx_command_level": Param(0, "1", locator="p.39 sec 4.1"),
        "dcx_parameter_level": Param(1, "1", locator="p.39 sec 4.1"),

        # ── command opcodes (section 5.2.x, one page each) ──────────────
        "cmd_slpin": Param(0x10, "1", locator="p.165 sec 5.2.12"),
        "cmd_slpout": Param(0x11, "1", locator="p.166 sec 5.2.13"),
        "cmd_dispon": Param(0x29, "1", locator="p.174 sec 5.2.21"),
        "cmd_caset": Param(0x2A, "1", locator="p.175 sec 5.2.22"),
        "cmd_paset": Param(0x2B, "1", locator="p.177 sec 5.2.23"),
        "cmd_ramwr": Param(0x2C, "1", locator="p.179 sec 5.2.24"),
        "cmd_madctl": Param(0x36, "1", locator="p.192 sec 5.2.30"),
        "cmd_colmod": Param(0x3A, "1", locator="p.200 sec 5.2.34"),
        "cmd_ramwrc": Param(0x3C, "1", locator="p.201 sec 5.2.35"),

        # ── MADCTL (36h) bit positions, p.192 bit table ─────────────────
        # D7 MY  Row Address Order      | "These 3 bits control the
        # D6 MX  Column Address Order   |  direction from the MPU to
        # D5 MV  Row/Column Exchange    |  memory write/read."
        # D4 ML  Vertical Refresh Order
        # D3 BGR RGB-BGR Order (0 = RGB colour filter, 1 = BGR)
        # D2 MH  Horizontal Refresh Order
        "madctl_bit_my": Param(7, "1", locator="p.192 sec 5.2.30"),
        "madctl_bit_mx": Param(6, "1", locator="p.192 sec 5.2.30"),
        "madctl_bit_mv": Param(5, "1", locator="p.192 sec 5.2.30"),
        "madctl_bit_ml": Param(4, "1", locator="p.192 sec 5.2.30"),
        "madctl_bit_bgr": Param(3, "1", locator="p.192 sec 5.2.30"),
        "madctl_bit_mh": Param(2, "1", locator="p.192 sec 5.2.30"),

        # ── COLMOD (3Ah) parameter encoding, p.200 pixel-format table ───
        # The parameter is X DPI[2:0] X DBI[2:0]; DBI is the MCU-interface
        # format, DPI the RGB-interface format. This board has no DPI link
        # (no VSYNC/HSYNC/DOTCLK on the FPC), so only DBI governs — but the
        # firmware still writes both nibbles, which is why the whole-byte
        # values are derived below.
        "colmod_dbi_3bpp": Param(0b001, "1", locator="p.200 sec 5.2.34"),
        "colmod_dbi_16bpp": Param(0b101, "1", locator="p.200 sec 5.2.34"),
        "colmod_dbi_18bpp": Param(0b110, "1", locator="p.200 sec 5.2.34"),
        "colmod_dbi_24bpp": Param(0b111, "1", locator="p.200 sec 5.2.34"),
        # THE FINDING, as a citable number: section 4.7.3 is titled "8-bit
        # Parallel MCU Interface" and lists 65K-colour RGB 5,6,5 among the
        # available display data formats for it. 1 = available.
        "dbi_16bpp_available_on_8bit_bus": Param(
            1, "1", locator="p.123 sec 4.7.3"),
        "dbi_18bpp_available_on_8bit_bus": Param(
            1, "1", locator="p.123 sec 4.7.3"),
        # p.124 notes: "2-times transfer is used to transmit 1 pixel data to
        # the 16-bit color depth information" / "3-times transfer ... to the
        # 18-bit colour depth information".
        "bus_transfers_per_pixel_16bpp": Param(2, "1", locator="p.124 sec 4.7.3"),
        "bus_transfers_per_pixel_18bpp": Param(3, "1", locator="p.124 sec 4.7.3"),

        # ── frame memory extents, from the CASET/PASET restrictions ─────
        # p.175: "When SC[15:0] or EC[15:0] is greater than 013Fh (when
        # MADCTL's D5 = 0) or 01DFh (when MADCTL's D5 = 1), data out of range
        # will be ignored."  p.177 says the mirror image for SP/EP. So MV
        # exchanges which counter spans 320 and which spans 480 — that is the
        # spec's own statement of what "Row/Column Exchange" costs.
        "caset_max_mv0": Param(0x013F, "1", locator="p.175 sec 5.2.22"),
        "caset_max_mv1": Param(0x01DF, "1", locator="p.175 sec 5.2.22"),
        "paset_max_mv0": Param(0x01DF, "1", locator="p.177 sec 5.2.23"),
        "paset_max_mv1": Param(0x013F, "1", locator="p.177 sec 5.2.23"),

        # ── reset state: Table 37, p.306, the one self-consistent table ──
        "reset_sleep_in": Param(1, "1", locator="p.306 table 37"),
        "reset_display_on": Param(0, "1", locator="p.306 table 37"),
        "reset_caset_start": Param(0x0000, "1", locator="p.306 table 37"),
        "reset_caset_end": Param(0x013F, "1", locator="p.306 table 37"),
        "reset_paset_start": Param(0x0000, "1", locator="p.306 table 37"),
        "reset_paset_end": Param(0x01DF, "1", locator="p.306 table 37"),
        "reset_madctl": Param(0x00, "1", locator="p.306 table 37"),
        "reset_colmod": Param(0x06, "1", locator="p.306 table 37"),

        # ── command-sequence timing (not bus timing) ────────────────────
        # p.166: "It is necessary to wait 5msec before sending the next
        # command" after SLPOUT, and "wait 120msec after sending the Sleep In
        # command ... before the Sleep Out command can be sent".
        "t_slpout_settle": Param(5e-3, "s", locator="p.166 sec 5.2.13"),
        "t_slpin_to_slpout": Param(120e-3, "s", locator="p.166 sec 5.2.13"),
        # p.308 Table 39 / Table 40: reset pulse and reset cancel.
        "t_reset_pulse_min": Param(10e-6, "s", locator="p.308 table 39"),
        "t_reset_cancel_max": Param(120e-3, "s", locator="p.308 table 39"),
        "t_reset_reject_below": Param(5e-6, "s", locator="p.308 table 40"),

        # ── DBI Type B AC characteristics, section 17.4.1, p.329 ────────
        # This is the whole write-side of the i80 bus. Every entry is the
        # table's min column; the table's max column is "-" for all of them,
        # which is why only minima are modelled. Symbols are the TABLE's
        # (twrl/twrh), not the timing diagram's (twcl/twch) — the two
        # disagree on that page and the table is the normative one.
        "t_ast": Param(0.0, "s", locator="p.329 sec 17.4.1"),
        "t_aht": Param(0.0, "s", locator="p.329 sec 17.4.1"),
        "t_chw": Param(0.0, "s", locator="p.329 sec 17.4.1"),
        "t_cs": Param(15e-9, "s", locator="p.329 sec 17.4.1"),
        "t_csf": Param(0.0, "s", locator="p.329 sec 17.4.1"),
        "t_wc": Param(40e-9, "s", locator="p.329 sec 17.4.1"),
        "t_wrh": Param(15e-9, "s", locator="p.329 sec 17.4.1"),
        "t_wrl": Param(15e-9, "s", locator="p.329 sec 17.4.1"),
        "t_dst": Param(10e-9, "s", locator="p.329 sec 17.4.1"),
        "t_dht": Param(10e-9, "s", locator="p.329 sec 17.4.1"),

        # ── derived ─────────────────────────────────────────────────────
        "f_write_max": Param(
            25e6, "Hz", derived_from=("t_wc",),
            formula="1 / t_wc = 1 / 40e-9 = 25.0 MHz — the fastest WRX the "
                    "controller's write cycle permits. The firmware's "
                    "LCD_CLK_HZ is 20 MHz (software/main/board_config.h), "
                    "which is 80% of this."),
        "colmod_param_16bpp": Param(
            0x55, "1",
            derived_from=("colmod_dbi_16bpp",),
            formula="the 3Ah parameter is X DPI[2:0] X DBI[2:0] (p.200), so "
                    "DPI=101 and DBI=101 pack to 0b0101_0101 = 0x55; the DPI "
                    "half is don't-care on this board (no RGB interface on "
                    "the FPC) but is what every driver writes"),
        "colmod_param_18bpp": Param(
            0x66, "1",
            derived_from=("colmod_dbi_18bpp",),
            formula="same packing with DPI=110 and DBI=110: 0b0110_0110 = "
                    "0x66. Equals the reset value 06h in its DBI half, which "
                    "is why an ILI9488 that never receives 3Ah still shows "
                    "18 bit/pixel"),
        "bytes_per_frame_16bpp": Param(
            307200, "byte",
            derived_from=("bus_transfers_per_pixel_16bpp", "caset_max_mv0",
                          "paset_max_mv0"),
            formula="(caset_max_mv0+1) * (paset_max_mv0+1) * transfers = "
                    "320 * 480 * 2 = 307200 bytes per full frame"),
        "bytes_per_frame_18bpp": Param(
            460800, "byte",
            derived_from=("bus_transfers_per_pixel_18bpp", "caset_max_mv0",
                          "paset_max_mv0"),
            formula="320 * 480 * 3 = 460800 bytes per full frame — 1.5x the "
                    "16bpp figure, on the same 20 MHz bus"),
    },
)

# Findings this model established against the repo, kept as data so
# test_vbench_display.py can pin them and they cannot quietly regress.
FINDINGS = {
    "rgb565_over_8bit_is_supported": {
        "claim_in_repo": "software/main/display.c, file header: 'ILI9488 in "
                         "8-bit parallel mode only supports RGB666 (18-bit "
                         "color, 3 bytes/pixel).'",
        "what_the_spec_says": "section 4.7.3 '8-bit Parallel MCU Interface', "
                             "p.123, lists 65K-Colors RGB 5,6,5 (3Ah, "
                             "DBI[2:0] = 101) as an available display data "
                             "format for that interface, and gives it "
                             "subsection 4.7.3.1 and Figure 110; p.124 "
                             "note 2 states 2-times transfer per pixel. The "
                             "COLMOD table on p.200 places no interface "
                             "qualifier on DBI = 101.",
        "locator": "p.123 sec 4.7.3",
        "consequence": "the firmware sends 460800 bytes per frame where "
                       "307200 would do — 1.5x the traffic on the 20 MHz "
                       "bus that sets the frame rate. software/sim/"
                       "vbench_hal.c:110 already assumes the supported "
                       "reading, so the two halves of the repo disagree.",
        "verdict": "the comment is wrong; the spec permits RGB565 here",
    },
    "reset_defaults_disagree_between_pages": {
        "claim_in_repo": "(none — this is an internal contradiction in the "
                         "specification itself)",
        "what_the_spec_says": "the per-command Default boxes give HW-reset "
                              "EC = 013Fh (p.175) but HW-reset EP = 01EFh "
                              "(p.177), and 01EFh is neither 479 nor 319. "
                              "Table 37 on p.306 gives EP = 01DFh = 479, "
                              "which is the only value consistent with a "
                              "480-page display.",
        "locator": "p.306 table 37",
        "consequence": "any model built from the per-command boxes inherits "
                       "a one-off page-end error; this model reads Table 37 "
                       "for every reset value instead.",
        "verdict": "Table 37 governs; p.177's 01EFh is a typo in the spec",
    },
    "ramwr_in_sleep_in_is_ambiguous": {
        "claim_in_repo": "(none)",
        "what_the_spec_says": "RAMWR's own Register Availability table "
                              "(p.179) says 'Sleep In: Yes', while RAMWRC "
                              "(p.201) and RAMRD (p.203) both carry the "
                              "restriction 'No access to the frame memory in "
                              "the Sleep In mode.' SLPIN itself (p.165) says "
                              "'The MCU interface and memory are still "
                              "working, and the memory keeps its contents.'",
        "locator": "p.201 sec 5.2.35",
        "consequence": "the controller model treats a RAMWR issued while "
                       "Sleep In as a FAULT, taking the restriction wording "
                       "as governing over the availability grid — the "
                       "conservative reading, and the one that catches a "
                       "firmware init sequence that forgot 11h.",
        "verdict": "modelled as a fault; the spec does not speak with one "
                   "voice and this is recorded rather than hidden",
    },
    "mv_landscape_raster_is_contradictory": {
        "claim_in_repo": "(none — the firmware calls "
                         "esp_lcd_panel_swap_xy(false) and stays portrait, "
                         "so nothing here is currently exercised)",
        "what_the_spec_says": "two statements about MADCTL D5 = 1 that do "
                              "not compose into a usable landscape mode. "
                              "p.175 and p.177 put the column span at 480 "
                              "and the page span at 320 when D5 = 1. p.179 "
                              "then says that with D5 = 1 it is the PAGE "
                              "register that increments first. So the "
                              "fastest-moving counter is the one spanning "
                              "320 — the panel's short axis — and the "
                              "physical raster order is unchanged by D5. A "
                              "host streaming a row-major 480x320 image "
                              "would have to feed it column-major.",
        "locator": "p.179 sec 5.2.24",
        "consequence": "ili9488_ctrl.py implements both statements "
                       "literally, so a landscape frame driven the obvious "
                       "way comes out transposed on the bench. That is the "
                       "spec's behaviour as written, not a modelling "
                       "shortcut. Anyone enabling swap_xy in the firmware "
                       "must resolve this against real silicon before "
                       "trusting either the bench or the datasheet.",
        "verdict": "unresolved in the document; implemented literally and "
                   "flagged rather than quietly 'corrected' to what drivers "
                   "do",
    },
}

# What this model deliberately does not cover. Downstream code must not read
# an absence here as a pass.
UNESTABLISHED = {
    "pixel_byte_order_18bpp": "the byte order within an 18 bit/pixel "
                              "transfer over the 8-bit bus is Figure 111 "
                              "(p.124), an image the PDF text layer does not "
                              "carry. The 16bpp order IS textually "
                              "established — p.113 note 2, 'Previous data "
                              "byte is R [0:4] G [0:2]', with p.112 note 2 "
                              "'RG - GB' — so ili9488_ctrl.py renders 16bpp "
                              "from a citation and 18bpp from a stated "
                              "convention it flags at runtime.",
    "madctl_composition_order": "whether MX/MY reverse the addresses inside "
                                "the MEMORY axes before MV exchanges them, "
                                "or mirror the PHYSICAL axes after, is not "
                                "stated in one place in the text layer. "
                                "ili9488_ctrl.map_address() reverses first "
                                "and exchanges last, because the p.192 bit "
                                "names bind MX to the column ADDRESS and MY "
                                "to the row ADDRESS, and because p.175/p.177 "
                                "make the column span 480 under MV — which "
                                "only holds if the exchange is the last "
                                "step. The two orders agree at the origin "
                                "and disagree one address in, so any bench "
                                "result that depends on a non-zero MADCTL is "
                                "conditional on this reading.",
    "electrical_dc": "no VIH/VIL/IOL/leakage numbers are modelled. The die "
                     "is inside the panel module and its IOVCC comes from "
                     "the module, not from this board's netlist, so a DC "
                     "level check here would be checking a rail the bench "
                     "cannot see.",
    "read_timing": "trc/trcfm/trdh/trdl/trat and the read path generally. "
                   "LCD_RD is tied HIGH on this PCB "
                   "(software/main/board_config.h) so the board cannot read "
                   "the controller at all; modelling the read window would "
                   "describe a transaction that is physically impossible "
                   "here.",
    "esp32s3_side_of_the_budget": "tdst and tdht are the CONTROLLER's "
                                  "requirements. Whether the ESP32-S3's "
                                  "LCD_CAM peripheral meets them depends on "
                                  "its data-to-WRX skew, which is in the "
                                  "ESP32-S3 chip datasheet / TRM, not in the "
                                  "WROOM-1 module datasheet this repo holds. "
                                  "check_timing() therefore reports the "
                                  "bus-geometry budget (what the clock "
                                  "period leaves) and says so, rather than "
                                  "claiming a closed setup/hold loop.",
    "gamma_power_vcom": "the gamma (E0h/E1h), power control (C0h-C5h) and "
                        "VCOM registers. The panel vendor's init sequence "
                        "sets these and this repo does not hold that "
                        "sequence; nothing the bench checks depends on them.",
    "tearing_effect": "TE / FMARK (35h, 44h) and the tearing-effect line. "
                      "Panel pin 8 is left open on this board by the panel "
                      "datasheet's own instruction (display.py, "
                      "LEAVE_OPEN_IF_UNUSED), so there is no TE signal to "
                      "model.",
    "partial_idle_inversion": "partial mode (30h/12h), idle mode (38h/39h) "
                              "and inversion (20h/21h). The firmware never "
                              "issues them.",
    "cabc_backlight": "CABC and the 51h-55h brightness registers. This "
                      "board's backlight is hardwired to +3V3 through a "
                      "resistor with no controller involvement.",
    "frame_rate": "the frame rate control registers (B1h-B3h) and therefore "
                  "the panel's actual refresh rate. Frames-per-second "
                  "computed from bus traffic alone is a BUS bound, not a "
                  "display refresh figure.",
}
