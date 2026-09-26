---
id: index
title: Next Steps
slug: /next-steps
---

# Next Steps

Studies for new consoles to emulate after the current ones, and for the
next console (v4). These are proposals, not commitments. What is still
needed to close the current console is under [Remediation](/docs/remediation).

Every figure on these pages comes from a measurement (`scripts/emu_check.py`,
`scripts/snes_bench.py`, the serial stats line), and new work keeps that
rule. The feasibility tiers are estimates until a port is measured.

| Page | What it covers |
|:---|:---|
| [More Systems](/docs/next-steps/more-systems) | which consoles fit the ESP32-S3, up to the PlayStation |
| [Arcade (MAME)](/docs/next-steps/arcade) | classic arcade boards, and where MAME stops |
| [Next Console (v4)](/docs/next-steps/v4-platform) | PS1, N64, HDMI and wireless controllers: which platform, in one step or several |
| [Plan A: ESP32-P4 + ESP32-C6](/docs/next-steps/plan-esp32-p4) | stay on Espressif: changes, time, cost, which requirements it meets |
| [Plan B: Rockchip RK3566](/docs/next-steps/plan-rk3566) | Linux module, the chip of RG353-class handhelds |
| [Plan C: Raspberry Pi CM4](/docs/next-steps/plan-cm4) | Linux module with the largest software ecosystem |

## Suggested order

1. Close [Remediation](/docs/remediation) first: those bugs are on
   the board today and affect every game.
2. Port one 🟢 system and one classic arcade board, to size the porting
   effort before planning the rest.
3. Decide on the 🟡 systems from those two measurements.
4. In parallel, the v4 study ([Next Console (v4)](/docs/next-steps/v4-platform)): it decides the platform for
   PS1, N64, HDMI and wireless controllers.
