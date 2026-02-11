---
id: prototyping
title: Breadboard Prototyping Guide
sidebar_position: 6
---

# Breadboard Prototyping Guide

Step-by-step guide to assemble the ESP32 Emu Turbo prototype on a breadboard.

## Required Tools

- Breadboard (830 points, or 2x smaller ones)
- Jumper wires (M-M, M-F, F-F assorted)
- Multimeter
- USB-C cable
- Soldering iron (for speaker wires and module headers)

## Step-by-Step Wiring

### Step 1: Power Rail

Connect the IP5306 USB-C module to provide 5V power, then regulate down to 3.3V with the AMS1117.

```
[IP5306 Module]
  OUT+ ──> Breadboard 5V rail
  OUT- ──> Breadboard GND rail
  BAT+ ──> LiPo battery (+)
  BAT- ──> LiPo battery (-)
  USB  ──> USB-C cable (for charging + power)

[AMS1117-3.3]
  VIN  ──> 5V rail (through 10µF cap)
  GND  ──> GND rail
  VOUT ──> Breadboard 3.3V rail (through 22µF cap)
```

:::caution Capacitors are mandatory
The AMS1117 requires both input (10µF) and output (22µF) capacitors for stable operation. Tantalum capacitors are recommended. Without them, the regulator may oscillate.
:::

### Step 2: ESP32-S3 DevKit

Place the ESP32-S3 N16R8 DevKitC-1 on the breadboard.

```
DevKit VIN  ──> 5V rail (if USB not connected directly)
  — OR —
DevKit USB  ──> Direct USB-C (for programming/debug)

DevKit GND  ──> GND rail
```

Add decoupling capacitors:
- 100nF ceramic cap between 3V3 and GND (close to the module)

### Step 3: Display Connection (8080 Parallel)

Connect the ILI9488 3.95" display panel with 8-bit 8080 parallel interface (via 40-pin FPC):

| Display Pin | Wire to | ESP32-S3 GPIO |
|---|---|---|
| VCC | 3.3V rail | — |
| GND | GND rail | — |
| D0 | jumper | GPIO4 |
| D1 | jumper | GPIO5 |
| D2 | jumper | GPIO6 |
| D3 | jumper | GPIO7 |
| D4 | jumper | GPIO8 |
| D5 | jumper | GPIO9 |
| D6 | jumper | GPIO10 |
| D7 | jumper | GPIO11 |
| CS | jumper | GPIO12 |
| RST | jumper | GPIO13 |
| DC/RS | jumper | GPIO14 |
| WR | jumper | GPIO46 |
| RD | jumper | GPIO3 |
| BL | jumper | GPIO45 (or 3.3V for always-on) |

:::tip Color-coding
Use colored wires for the 8 data lines (e.g., rainbow order) to make debugging easier. Use a different color for control lines.
:::

### Step 4: SD Card Module

Connect the SD card SPI module:

| SD Module Pin | Wire to | ESP32-S3 GPIO |
|---|---|---|
| VCC | 3.3V rail | — |
| GND | GND rail | — |
| MOSI | jumper | GPIO36 |
| MISO | jumper | GPIO37 |
| CLK | jumper | GPIO38 |
| CS | jumper | GPIO39 |

### Step 5: Audio

Connect the I2S DAC and PAM8403 amplifier:

| Connection | From | To |
|---|---|---|
| I2S BCLK | GPIO15 | DAC BCLK input |
| I2S LRCK | GPIO16 | DAC LRCK input |
| I2S DOUT | GPIO17 | DAC DIN input |
| DAC analog out | DAC output | PAM8403 AUDIO_IN |
| PAM8403 VCC | 5V rail | PAM8403 VCC |
| PAM8403 GND | GND rail | PAM8403 GND |
| PAM8403 SPK+ | wire | Speaker (+) |
| PAM8403 SPK- | wire | Speaker (-) |

### Step 6: Buttons

For each button, wire a 6x6mm tact switch with a 10kΩ pull-up resistor:

```
3.3V ──[10kΩ]──┬── GPIO pin
               │
            [switch]
               │
              GND
```

**Button wiring table:**

| Button | GPIO | Wire Color (suggested) |
|---|---|---|
| UP | GPIO40 | White |
| DOWN | GPIO41 | White |
| LEFT | GPIO42 | White |
| RIGHT | GPIO1 | White |
| A | GPIO2 | Red |
| B | GPIO48 | Blue |
| X | GPIO47 | Yellow |
| Y | GPIO21 | Green |
| START | GPIO18 | Orange |
| SELECT | GPIO0 | Orange |
| L | GPIO35 | Purple |
| R | GPIO19 | Purple |

### Step 7: Joystick (Optional)

Connect the PSP-style joystick:

| Joystick Pin | Wire to |
|---|---|
| VCC | 3.3V rail |
| GND | GND rail |
| X axis | GPIO20 (ADC) |
| Y axis | GPIO33 (ADC) |

## Wiring Checklist

Before powering on, verify with a multimeter:

- [ ] 3.3V rail is NOT shorted to GND
- [ ] 5V rail is NOT shorted to GND
- [ ] AMS1117 input cap (10µF) is connected correctly (polarity!)
- [ ] AMS1117 output cap (22µF) is connected correctly
- [ ] All display data lines (D0-D7) are connected to correct GPIOs
- [ ] Display control lines (CS, RST, DC, WR, RD) are correct
- [ ] SD card SPI lines are not swapped (MOSI/MISO confusion is common)
- [ ] Button pull-up resistors are connected to 3.3V, not 5V
- [ ] No wires touching where they shouldn't

:::caution Before powering on
Double-check all connections with a multimeter in continuity mode. A short circuit on the 3.3V rail can damage the ESP32-S3 permanently.
:::

## Testing Procedure

### Test 1: Power
1. Connect USB-C to IP5306 module
2. Verify 5V on the 5V rail with multimeter
3. Verify 3.3V on the 3.3V rail
4. Check the AMS1117 is not getting hot (if it is, there's a short)

### Test 2: ESP32-S3 Boot
1. Connect ESP32-S3 DevKit via USB
2. Open serial monitor (115200 baud)
3. Press reset button — you should see boot messages
4. Flash a simple "Hello World" sketch

### Test 3: Display
1. Flash a display test program (solid color fill)
2. Verify all pixels light up uniformly
3. Test basic graphics (rectangles, text)
4. If the display is garbled, check D0-D7 wiring order

### Test 4: SD Card
1. Insert a FAT32-formatted micro SD card
2. Flash SD card test program
3. Verify file listing and read operations
4. Test write speed (should be >1 MB/s over SPI)

### Test 5: Buttons
1. Flash a button test program that prints GPIO state
2. Press each button individually and verify correct GPIO triggers
3. Check for bouncing (rapid on/off) — debounce caps should prevent this
4. Test simultaneous button presses (D-pad + face button combos)

### Test 6: Audio
1. Flash an audio test program (sine wave or beep)
2. Verify sound output from speaker
3. Test volume control via PAM8403 potentiometer
4. Check for crackling or distortion (adjust I2S buffer size if needed)

### Test 7: Emulation
1. Flash NES emulator firmware (start simple)
2. Load a test ROM from SD card
3. Verify display, controls, and audio work together
4. Test SNES emulator — load a simple game
5. Monitor frame rate (target: 60 fps NES, best-effort SNES)

## Common Issues

| Problem | Likely Cause | Solution |
|---|---|---|
| Display shows nothing | BL not connected or wrong GPIO | Connect BL to 3.3V directly to test |
| Display shows garbled image | D0-D7 wired in wrong order | Check each data line individually |
| SD card not detected | MOSI/MISO swapped | Swap the two wires |
| Buttons always read LOW | Pull-up resistor missing | Add 10kΩ to 3.3V |
| Audio crackling | Buffer underrun | Increase I2S DMA buffer size |
| ESP32-S3 won't boot | EN pin floating | Add 10kΩ pull-up + 100nF cap |
| AMS1117 overheating | Excessive current draw | Check for shorts on 3.3V rail |
