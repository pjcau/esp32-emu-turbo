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
| **R37**: display FPC connector J4 | first article, 2026-09-11/12 | use a top-contact J4 for the panel's FPC tail |
| **R38**: PDM carrier hiss | first article, 2026-09-12 | see [Audio](audio) |
| **J3 has no "+" marking** | first article | add the "+" silkscreen next to pad 1 (BAT_IN) |
| **Speaker pads unmarked** | article 0004: the first "no sound" was the speaker wires on the wrong pads | add SPK+ / SPK− silkscreen |

## Open verification

| Claim | Status | Next step |
|:---|:---|:---|
| **IP5306 gives a stable VOUT from VIN with no cell attached** (CLAIM-005) | unverified past its deadline; the `verify_claims_ledger` gate is red | measure it on a board with the battery unplugged and record the result in the claims ledger |

**Proof:** each fix is checked at first-article inspection of the respin
(`/first-article-check`), and the claim closes with a measurement.
