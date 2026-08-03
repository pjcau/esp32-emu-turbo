---
id: bring-up-protocol
title: First Power-On Bring-Up Protocol
sidebar_position: 7
---

# First Power-On Bring-Up Protocol

When a fresh board arrives, the question is never "does it work" but "which
net is wrong". Answering that normally takes a multimeter and an
oscilloscope. This project does not have either — the only instruments
available are a camera and a USB cable.

So the board measures itself. `software/bringup_test/` is an ESP-IDF
firmware whose entire output is a serial report: 58 checks, one parseable
line each, naming the net and the component behind every failure. The serial
log is the instrument — and since the next run, the [diagnostic
LEDs](../rework/diagnostic-leds.md) are its cable-free fallback: the
heartbeat LED repeats each failed subsystem as a blink code, so a photo
or video carries the verdict even with no serial connection.
The step-by-step commissioning sequence (USB first, battery last) is
[first-boot.md](./first-boot.md).

It is containment layer 5 of the
[containment roadmap](https://github.com/pjcau/esp32-emu-turbo/blob/main/docs/archived/containment-roadmap.md):
the layer that covers what happens after the board is already fabricated and
every geometric gate was green.

---

## Before you apply power

The bring-up firmware cannot run on a board that is already damaged, and it
cannot see a part that is soldered the wrong way round until that part is
powered. Do the photographic checks first — they are cheaper and they are
what caught the v4.3.1 rotation failure:

1. Run the `/first-article-check` skill, **phase A**, on the JLCPCB 3D
   preview before paying. Orientation is checked per package *family*, not
   per component.
2. On arrival, run **phase B**: photograph each side and compare against
   the render.
3. Only then follow the
   [short-circuit test bible](./short-test-multimeter.md) as far as your
   tools allow, and plug the USB-C cable in.

If the board draws no current or the USB device never enumerates, the
firmware never gets to speak. That failure mode is covered by
[incident: power short](../rework/incident-power-short.md), not by this
page.

---

## Flashing and capturing the report

```bash
# Build only
make bringup-build

# Flash and watch the report (set ESP_PORT to your device)
ESP_PORT=/dev/cu.usbmodem1101 make bringup-flash
```

The firmware is generated from `software/main/board_config.h`, so it can
never disagree with the application about a pin number. Regenerate it after
any GPIO change:

```bash
make bringup-generate     # rewrite software/bringup_test/main/bringup_test.c
make bringup-check        # fail if it is stale (no writes)
```

To keep a copy of the report, capture the monitor output:

```bash
ESP_PORT=/dev/cu.usbmodem1101 make bringup-flash 2>&1 | tee bringup-$(date +%F).log
```

:::caution Do not touch the buttons while the report runs
Two of the checks drive button nets and require every other button net to
stay high. A finger on a button during those seconds is reported as a short
between nets.
:::

---

## What the report looks like

```
BRINGUP-BEGIN;board=esp32-emu-turbo;module=N16R8;built=Aug  1 2026 08:55:14
BRINGUP-FORMAT;seq;result;id;pins;detail
BRINGUP;01;PASS;bringup.previous_run;-;cold power-on — no previous-run state is retained across it
BRINGUP;02;PASS;sys.reset_reason;-;reset=POWERON(1)
BRINGUP;03;PASS;chip.model;-;model=9 cores=2 rev=0.2 features=0x00000012
BRINGUP;04;PASS;chip.flash_size;-;flash=16MB expected=16MB (N16R8)
BRINGUP;05;PASS;chip.psram_size;-;psram=8MB expected=8MB mode=octal
BRINGUP;06;PASS;config.gpio_unique;-;31 GPIO assignments, all distinct
BRINGUP;07;PASS;usb.serial_jtag;GPIO19/20;D-=GPIO19 D+=GPIO20 txfifo_writable=yes ...
BRINGUP;08;PASS;gpio.strapping;GPIO0/3/45/46;post-boot levels (NOT the reset-time latch): GPIO0/BTN_SELECT=1 GPIO3/BTN_R=1 GPIO45/BTN_L=1 GPIO46/LCD_WR=1
BRINGUP;09;PASS;temp.baseline;-;die=38.4C at idle
BRINGUP;10;PASS;btn.UP.idle;GPIO40;GPIO40 idle=1
...
BRINGUP;22;PASS;btn.UP.rc;GPIO40;GPIO40 rise=1402us (expect ~1390us for 10k x 100nF, window 500-4000us)
...
BRINGUP;34;PASS;btn.isolation;all 12;12 nets, every one isolated from the other 11
BRINGUP;38;PASS;lcd.panel.init;D0-D7+CS/RST/DC/WR;display_init()=ESP_OK 320x480 8-bit i80 @ 20MHz
BRINGUP;40;SKIP;lcd.panel.readback;-;LCD_RD is tied HIGH on the PCB, the panel cannot be read back — confirm the colour bars by eye (R,G,B,white,black,cyan,magenta,yellow)
...
BRINGUP-SKIPPED;lcd.panel.readback,lcd.backlight,audio.audible,power.rail3v3.absolute,power.battery_sense,power.ip5306_i2c
BRINGUP-SUMMARY;total=58;pass=52;fail=0;skip=6;verdict=GREEN
BRINGUP-LED;steady 1 Hz — all subsystems green
BRINGUP-END
```

Every line is `BRINGUP;<seq>;<PASS|FAIL|SKIP>;<id>;<pins>;<detail>`, six
`;`-separated fields. A field never contains a `;` — the firmware rewrites
it to a comma before printing. A `FAIL` line appends
`implicates: <net or component>` to its detail, so the log alone is enough
to start reworking.

The verdict is `RED` if anything failed. Skips do not turn it red, because
every skip in this firmware is a permanent property of the board rather
than a test that was not written — see below.

### If the log stops in the middle

A rail that collapses under load does not print a `FAIL` line. It reboots
the chip, and the only symptom is a truncated log followed by a fresh
`BRINGUP-BEGIN`. The firmware handles this: the check it was executing is
written to RTC memory that survives the reset, and the next run reports it:

```
BRINGUP;01;FAIL;bringup.previous_run;-;previous run died during check 'power.load' | implicates: ...
BRINGUP;02;FAIL;sys.reset_reason;-;reset=BROWNOUT(9) | implicates: U3 SY8089A output, its feedback divider R25/R26, or the input path
```

That pair is the signature of a 3V3 rail that cannot hold under current.

---

## What each failure implicates

Each `FAIL` line already carries this text; the table is here so you can
plan rework before flashing.

| Check | A failure points at |
|---|---|
| `bringup.previous_run` | The board reset during the named check on the previous run — almost always a rail collapse in that subsystem |
| `sys.reset_reason` | `BROWNOUT` or `PWR_GLITCH`: U3 SY8089A output, its R25/R26 feedback divider, or the input path |
| `chip.model`, `chip.flash_size` | Wrong module fitted at U1, or a module carrying less flash than `N16R8` |
| `chip.psram_size` | Module variant mismatch, **or** VDD\_SPI strapped to 1.8 V at reset by a pull-up on GPIO45 that must be DNP |
| `config.gpio_unique` | `board_config.h` itself assigns one GPIO twice — a firmware bug, not a board fault |
| `usb.serial_jtag` | J1 USB-C, the D+/D− pair, or the 5.1 k CC resistors |
| `btn.<X>.idle` | That button's net: a shorted switch, a solder bridge to GND, or a switch stuck closed |
| `btn.<X>.rc` | The 10 k pull-up or the 100 nF debounce cap on that net — compare the printed rise time against the other eleven buttons |
| `btn.isolation` | A solder bridge between two button nets, or D1 (the BAT54C that makes SW13 press START and SELECT together) fitted backwards |
| `lcd.data.stuck` | An ILI9488 data pin shorted to +3V3 or GND at J4 or in the FPC fan-out |
| `lcd.data.shorts` | A solder bridge between two adjacent data lines at J4 |
| `lcd.ctrl.toggle` | A control line shorted at J4, or the pin loaded by the panel |
| `lcd.panel.init` | J4 FPC seating, the ILI9488 panel, or panel power |
| `lcd.panel.pattern` | The i80 DMA path, or the panel losing its configuration mid-transfer |
| `sd.lines.stuck` | An SD line shorted to a rail at the TF-01A socket pads |
| `sd.cmd0` | The card answers but not with idle state: marginal CLK, or CS not reaching the socket |
| `sd.cmd8` | Signal integrity on the ~150 mm SD run, or a card that cannot take 3.3 V |
| `sd.acmd41` | Card power: the socket's VDD pin, or the 3V3 rail sagging while the card starts |
| `sd.ocr` | MISO integrity — the command went out but the reply came back wrong |
| `sd.fat.mount` | The same wiring at 20 MHz rather than 400 kHz: trace length, via count, or missing pull-ups |
| `audio.pdm.init`, `audio.tone` | The DMA path only. Nothing after GPIO17 can fail these — see `audio.audible` |
| `psram.pattern` | The module's internal Octal PSRAM, or VDD\_SPI at the wrong voltage |
| `power.load` | U3 SY8089A cannot hold 3V3 under load: L1, the output capacitor, or the feedback divider |
| `power.temp_delta` | Excess current somewhere on the board — a partial short |

### The two checks that measure rather than poll

**`btn.<X>.rc` measures the debounce network without an instrument.** It
drives the button node to 0 V, releases it to a floating input, and times
how long the 10 k pull-up takes to charge the 100 nF cap through the input
threshold. With τ = 1 ms and V<sub>IH</sub> = 0.75·VDD, the crossing should
land near τ·ln 4 = 1.39 ms. A rise far below that means the debounce cap is
missing or open; far above means the pull-up is missing or the cap is
oversized. The measured microseconds are always printed, so the numbers stay
useful even where the pass window is not.

`BTN_L` is the inverted case. `board_config.h` records that its pull-up is
DNP on purpose — an external pull-up on GPIO45 would strap VDD\_SPI to
1.8 V and break the Octal PSRAM — so for that one button, *never rising* is
the pass condition and a fast rise is the failure.

**`power.load` is the closest thing to a rail measurement.** It runs both
cores, PSRAM, the display bus and the audio DMA flat out for three seconds
and checks the board is still alive afterwards.

---

## The six permanent skips

None of these is an unwritten test. Each is something this board revision
physically cannot report, and the reason is printed on the skip line:

| Skip | Why it can never pass or fail |
|---|---|
| `lcd.panel.readback` | `LCD_RD` is tied HIGH on the PCB. With no read line the panel's status and ID registers are unreachable, so no software check can confirm the pixels arrived — **confirm the colour bars by eye** |
| `lcd.backlight` | The backlight is hardwired — LED-A is fed from **+5V through R27 (20 Ω)** with no GPIO control. A dark panel after a passing `lcd.panel.pattern` is R27, the LED_BLA net at J4 pad 8, or FPC seating — never the firmware |
| `audio.audible` | There is no feedback path from the PAM8403 back to any GPIO. If `audio.tone` passed and you heard nothing, the fault is after GPIO17: the coupling cap, the PAM8403 supply or its SD pin, or the speaker |
| `power.rail3v3.absolute` | The ESP32-S3 exposes no ADC channel on VDD3P3. Absolute rail voltage is not a measurable quantity in software; rail health is inferred from the brownout detector and `power.load` |
| `power.battery_sense` | `board_config.h` defines no battery-sense net. There is no divider from BAT+ into any ADC pin on this revision, so battery voltage is not observable from firmware |
| `power.ip5306_i2c` | IP5306 I²C is not routed — GPIO33/34 are reserved for the Octal PSRAM. The charger runs on power-on defaults and reports nothing to the MCU; charge state is the on-board LED only |

Two more skips are conditional rather than permanent, and say so in their
detail field: `sd.cmd0` skips when nothing answers on `SD_MISO`, because
**no card-detect line is read on this revision** and therefore nothing in
software can tell an empty socket from a broken MISO net. Re-run with a
known-good card inserted; if it still reads `0xFF`, the fault is on the
board. Every later SD check then skips naming `sd.cmd0` as the reason, so a
missing card never looks like six independent failures.

The socket itself is not the reason. The TF-01A **does** have a card-detect
contact — its drawing labels the pad row (1)…(8) and then **Cd**, so pad 9
is the socket's detect contact, not a card contact and not DAT2. What this
revision lacks is a *route* for it: pad 9 is deliberately off-net (the
BTN_R track used to cross it and was rerouted east of the pad row in
R31-HIGH-2 — a Cd blade is a switch to the grounded shell, so no signal may
share it), and no firmware reads it. See
[the BTN_R regression check](#u6-pad-9-cd-and-btn_r) below.

---

## Strapping pins

Four ESP32-S3 strapping pins carry board nets:

| GPIO | Net | Latched at reset |
|---|---|---|
| 0 | `BTN_SELECT` | Boot mode — LOW at reset enters serial download |
| 3 | `BTN_R` | JTAG source select |
| 45 | `BTN_L` | VDD\_SPI voltage — LOW at reset selects 3.3 V, which the Octal PSRAM requires |
| 46 | `LCD_WR` | ROM message printing |

**The firmware cannot assert anything about their boot-time state.** Those
latches are sampled once, on the rising edge of reset, and are not exposed
to software afterwards. `gpio.strapping` therefore only prints the
post-boot level and says so on the line; it is informational.

The one that matters is GPIO45, and it is checked indirectly: if VDD\_SPI
had been strapped to 1.8 V, `chip.psram_size` and `psram.pattern` would
fail. That is the evidence, not the strapping line.

GPIO46 carrying `LCD_WR` is benign — a high level at reset only suppresses
ROM boot messages — but it is worth knowing when a boot log looks emptier
than expected. The reset-time expectation for it is LOW, held by the pad's
internal pull-down, and that is enforced on the PCB side by
`scripts/verify_strapping_pins.py`, not here. The firmware derives its
strapping table independently from the ESP32-S3 datasheet set, so the two
agreeing is a cross-check rather than a copy.

:::note
`software/main/board_config.h` documents the GPIO0, GPIO3 and GPIO45 straps
in prose but does not mention GPIO46. The pin is handled correctly
everywhere it matters; only the header comment is silent about it.
:::

### U6 pad 9 (Cd) and BTN\_R — reroute regression check {#u6-pad-9-cd-and-btn_r}

One extra reading belongs to the GPIO3 line above, and it costs nothing:
**read `BTN_R` once with the socket empty and once with a card inserted.**

U6 pad 9 is the TF-01A's own card-detect contact (`Cd` on the socket
drawing) — a blade that mates with the grounded shell, i.e. a switch to
GND, not a data line. Up to R31 the BTN\_R track crossed that pad and the
generator declared the overlap same-net, which tied the R shoulder button
to that switch: pressed-forever in one card state. **R31-HIGH-2 fixed it
in copper** — the BTN\_R riser detours east of the whole pad row and pad 9
carries no net. The two readings verify the board in your hands was built
from post-R31 gerbers:

| `BTN_R`, card inserted, button not pressed | Verdict |
|---|---|
| stays HIGH | Reroute present — BTN\_R is independent of card state, as designed |
| goes LOW | **This board was fabbed from pre-R31 gerbers** (BTN\_R still on pad 9 and the Cd blade grounds it). The R shoulder button is dead whenever a card is inserted; do not ship, refab from the current release |

**Boot is unaffected either way.** GPIO3's strap selects the JTAG signal
source, and per table 8 (p.15) of the module datasheet the pin is *ignored*
unless `EFUSE_STRAP_JTAG_SEL` is burned — which the factory default leaves
unselected. Even on a pre-R31 board a card pulling the pad low cannot
change how the board boots. It would stop being harmless only if someone
burned that eFuse, which is another reason not to.

---

## Related

- [`/first-article-check`](https://github.com/pjcau/esp32-emu-turbo/blob/main/.claude/skills/first-article-check/SKILL.md) — the photographic protocol that runs before this one
- [Short-circuit test bible](./short-test-multimeter.md) — the manual checks for when a multimeter *is* available
- [Incident: v4.3.1 rotations](../rework/incident-v431-rotations.md) — the failure class this layer exists to catch earlier
- [ESP32 firmware](../software/firmware.md) — the application these drivers ship in
