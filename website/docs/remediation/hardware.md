---
id: hardware
title: Hardware
sidebar_position: 3
---

# Hardware

Findings from the first articles (v4.9.0, articles 0003 and 0004) that the
next fabrication should fix. The full record of what is broken, and of what
must not be "fixed", is `docs/known-issues.md` in the repository.

| Item | Found | Fix in the respin |
|:---|:---|:---|
| **Wi-Fi antenna buried** (top priority) | first article, 2026-09-29: RSSI about −90 dBm | antenna over the edge or all-layer keep-out, SD lines rerouted, gate fixed — see [Wi-Fi](wifi) |
| **R37**: display FPC connector J4 | first article, 2026-09-11/12 | use a top-contact J4 for the panel's FPC tail |
| **R38**: PDM carrier hiss | first article, 2026-09-12 | see [Audio](audio) |
| **J3 has no "+" marking** | first article | add the "+" silkscreen next to pad 1 (BAT_IN) |
| **Speaker pads unmarked** | article 0004: the first "no sound" was the speaker wires on the wrong pads | add SPK+ / SPK− silkscreen |

## Candidate for the respin: a module with more flash (not decided)

Raised on 2026-10-04, from what the software ran into. To be checked against
the datasheets before it is adopted; nothing below has been verified on a
board.

| What the software lacks today | Measured |
|:---|:---|
| Flash for apps | 64 KB free outside the app partitions, about 18 KB in the launcher's: no new app without removing one |
| Flash for the arcade game cache | 4 MB, one game at a time: changing arcade game costs 20 to 28 s of rewriting, against 9 to 13 s for the same game again |
| PSRAM on the largest CPS1 games | Street Fighter II has about 70 KB free in play: no second frame bitmap, save states borrow a video cache |

The ESP32-S3-WROOM-1 line stops at 16 MB of flash. The **ESP32-S3-WROOM-2**
(N32R8V: 32 MB flash and 8 MB PSRAM; N32R16V: 16 MB PSRAM) has the same
outline and pinout, with octal flash at 1.8 V. What that changes on this
board, as read from the pin assignments in `board_config.h`:

- GPIO 33 to 37 belong to the memory: not used here (35 to 37 already belong
  to the octal PSRAM of the N16R8).
- **GPIO 47 and 48 work at 1.8 V**: BTN_X and BTN_B are there, each with a
  10 kΩ pull-up to +3V3. Those two pull-ups would have to be left unpopulated
  (internal pull-ups instead) or the buttons moved.
- GPIO 45 (BTN_L, the VDD_SPI strap) already has no external pull-up.
- Firmware: octal flash mode and a 32 MB partition table.

It would not change the internal RAM (0 to 5 KB free in Metal Slug: that is
the chip) nor the antenna. Stock and price at JLCPCB not checked.

## Open verification

| Claim | Status | Next step |
|:---|:---|:---|
| **IP5306 gives a stable VOUT from VIN with no cell attached** (CLAIM-005) | unverified past its deadline; the `verify_claims_ledger` gate is red | measure it on a board with the battery unplugged and record the result in the claims ledger |

**Proof:** each fix is checked at first-article inspection of the respin
(`/first-article-check`), and the claim closes with a measurement.
