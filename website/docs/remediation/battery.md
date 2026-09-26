---
id: battery
title: Battery Indicator
sidebar_position: 4
---

# Battery Indicator

**Goal for v3.1:** a battery level icon in the top-right corner of the
retro-go launcher, and only there (not inside the games).

## Why it is missing today

The board cannot measure the battery. The IP5306 variant on the board has
no I2C wired (`board_config.h`: "IP5306 I2C not routed on PCB"), and no ADC
pin is connected to BAT+. The debug stats line reports `BATT:0` and the
retro-go target sets `RG_BATTERY_DRIVER 0`.

Retro-go already has everything above the measurement: an ADC battery
driver (`RG_BATTERY_DRIVER 1` in `rg_input.c`) and a battery icon drawn in
the top-right of the launcher header (`rg_gui_draw_icons()`), shown when a
battery reading is present.

## Plan

| Step | Work |
|:---|:---|
| **1. Hardware rework (v3 boards)** | A resistor divider from BAT+ to the free GPIO16 (ADC2 channel 5): 2 × 220 kΩ plus 100 nF to GND at the pin. The 3.0–4.2 V cell becomes 1.5–2.1 V at the ADC; the divider draws about 10 µA. Locate the module's IO16 pad against the WROOM-1 datasheet pin table before soldering |
| **2. Firmware** | `RG_BATTERY_DRIVER 1` with `ADC_UNIT_2` / channel 5 in the target `config.h`; `RG_BATTERY_CALC_VOLTAGE` = raw × divider ratio, `RG_BATTERY_CALC_PERCENT` from a LiPo discharge curve (3.3 V ≈ 0%, 4.15 V ≈ 100%). Report "not present" when the reading is outside 2.8–4.5 V, so a board without the rework shows no icon instead of a wrong one |
| **3. Launcher only** | draw the icon from the launcher header and skip it in the emulators' menus |
| **4. Respin** | route the divider in the schematic, preferably to an ADC1 pin or through an IP5306 variant with I2C, so no rework is needed |

## Known limits

- **ADC2 and Wi-Fi share hardware.** The launcher runs Wi-Fi for the web
  UI, and ADC2 reads can fail while Wi-Fi is active. The driver keeps the
  last good value and retries; to confirm on the bench.
- **Voltage is not charge.** The reading sags under load and rises while
  charging (no charge-status pin reaches the ESP32), so the icon shows a
  few coarse levels, not an exact percentage.

## Proof

Readings compared with a multimeter on BAT+ at three cell voltages
(about 3.5, 3.8 and 4.1 V); the icon present with the rework and absent
without it; the icon visible in the launcher and absent in games.
