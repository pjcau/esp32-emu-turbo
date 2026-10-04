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

## Candidate for the respin: the 32 MB module (not decided)

The module swap studied in [Plan D](/docs/next-steps/plan-esp32-s3-n32r16v)
(ESP32-S3-WROOM-2-N32R16V, same footprint) would fit the same respin as the
antenna fix. What the software ran into on the current module, measured on
2026-10-04:

| Limit | Measured |
|:---|:---|
| Flash for apps | 64 KB free outside the app partitions, about 18 KB in the launcher's: no new app without removing one |
| Flash for the arcade game cache | 4 MB, one game at a time: changing arcade game costs 20 to 28 s of rewriting, against 9 to 13 s for the same game again |
| PSRAM on the largest CPS1 games | Street Fighter II has about 70 KB free in play |

One point to check against the module's datasheet before adopting it, not
covered in Plan D: with the octal flash at 1.8 V, GPIO 47 and 48 are in the
1.8 V domain, and BTN_X and BTN_B sit there with 10 kΩ pull-ups to +3V3.

## Open verification

| Claim | Status | Next step |
|:---|:---|:---|
| **IP5306 gives a stable VOUT from VIN with no cell attached** (CLAIM-005) | unverified past its deadline; the `verify_claims_ledger` gate is red | measure it on a board with the battery unplugged and record the result in the claims ledger |

**Proof:** each fix is checked at first-article inspection of the respin
(`/first-article-check`), and the claim closes with a measurement.
