---
id: short-test-multimeter
title: "Short-Circuit Test Bible (Multimeter)"
sidebar_position: 4
---

# Short-Circuit Test Bible

A dedicated, step-by-step procedure to hunt **short circuits** on an assembled board
with a multimeter (reference: **UNI-T UT890D+**), and — most importantly — a
**diagnostic matrix** that maps *your* measured results to the *likely location* of the
fault.

This is the check that would have caught the PCB v1 disaster (44 routing violations,
6 decoupling caps shorted to GND — see
[Incident: Power Short](../rework/incident-power-short.md)).

:::danger Golden rule
Every measurement in the continuity section is done with the board **completely
unpowered**: USB-C unplugged, battery disconnected, power switch OFF. The meter injects
its own test current — external power falsifies the reading and can damage the meter.
:::

:::info Pass / Fail in one line
Two **different** nets must **never** beep (never read ~0 Ω). The **same** net measured
at two points **must** beep (~0 Ω). Anything else is a defect — look it up in the
[Diagnostic Matrix](#diagnostic-matrix).
:::

---

## 1. Power topology (what connects to what)

Extracted from the schematic generator (`scripts/generate_schematics/sheets/power_supply.py`).
Knowing this is what turns "it beeps" into "the fault is *there*".

```
USB-C ─VBUS─► C17 ─► IP5306(VIN)                 [VBUS: raw USB 5V]
                     IP5306(VOUT) ─► C19,C27,C1 ─► +5V rail
                                                    │
Battery ─BAT_IN─► Q1(RPP) ─BAT+─► IP5306(BAT)      +5V ─► AMS1117(VIN)
                             │                             AMS1117(VOUT/tab) ─► C2 ─► +3V3 rail
                             └─► C18, L1                                              │
                                                       +3V3 ─► ESP32-S3, 12× button pull-ups (10k),
                                                                LEDs, all decoupling caps
```

| Net | Source | Also present on (probe points) |
|-----|--------|-------------------------------|
| **VBUS** | USB-C VBUS pin | **C17**+, IP5306 VIN(pin 1) |
| **+5V** | IP5306 VOUT (pin 8) | **C19**+, **C27**+, **C1**+, R16, AMS1117 VIN(pin 3), USBLC6 |
| **BAT+** | IP5306 BAT (pin 6), post-RPP | **C18**+, L1, Q1 drain |
| **BAT_IN** | Battery connector J3.1 | Q1 source, BT1+ (pre-RPP) |
| **+3V3** | AMS1117 VOUT / **tab** | **C2**+, C26, C_dec, ESP32 3V3 pins, R4–R15 (button pull-ups), R17/R18 (LEDs) |
| **GND** | everywhere | USB-C shell, every cap − pad, ESP32 GND pad |

---

## 2. Probe-point map

![Power rail map — component side](/img/debug/short-test-rail-map.png)

| Color | Net | Where to touch |
|-------|-----|----------------|
| 🔵 Blue | **GND** | USB-C metal shell (keep BLACK probe here) |
| 🔴 Red | **+3V3** | large **tab** of the AMS1117 |
| 🟠 Orange | **+5V** | IP5306 (output side) or AMS1117 input pin |
| 🟣 Purple | **VBUS** | C17, next to the IP5306 VIN pin |
| 🟢 Green | **BAT+ / BAT_IN** | battery connector (silk "BATT") |

Close-ups:

| +3V3 | +5V | GND |
|------|-----|-----|
| ![](/img/debug/probe-3v3-ams1117.png) | ![](/img/debug/probe-5v-ip5306.png) | ![](/img/debug/probe-gnd-usbc.png) |

:::note AMS1117 (SOT-223) — exact pins
Large **tab = VOUT = +3V3**. Looking at the render (component side), the three legs are,
**left → right: GND · +3V3 · +5V** (pin 1 = GND, pin 2 = VOUT/tab, pin 3 = VIN = +5V).
Aim at the wide tab for +3V3 — easiest target.
:::

:::note IP5306 — exact pins (this is the ambiguity you asked about)
The IP5306 is an eSOP-8. The **pin-1 dot is top-LEFT** in the render, so the left
column is pins 1–4 (top→bottom) and the right column is pins 8–5 (top→bottom).
**VBUS is pin 1**, the **top-LEFT** pin. **+5V is pin 8**, the **top-RIGHT** pin
(same height as pin 1). **LX is pin 7**, **BAT+ is pin 6** (below pin 8 on the right).
The large center pad under the chip is **GND**.
So "+5V on the IP5306" means specifically **pin 8 (top-right)**, *not* just "the chip".
See card **T7** / **T14** below for the exact spot.
:::

---

## 3. Multimeter setup (UT890D+)

1. Rotary switch → the position marked with **diode `▶|` + sound-waves `🔊)))`**.
2. Press the yellow **SELECT** until the display shows **`🔊)))`** (continuity, buzzer on).
   It boots in diode mode by default.
3. **RED probe → `VΩ`**, **BLACK probe → `COM`**.
4. Self-test: touch the tips together → must **beep** + read ~0 Ω.

For a numeric reading press **SELECT** again to reach **Ω** (manual range: step up
2k → 20k → 200k → 2M until the value settles). Buzzer threshold ≈ 30–50 Ω.

:::tip Capacitor charging is not a short
On the Ω range the number may **climb slowly** from low to high — that is a decoupling
cap charging from the meter, **not** a short. A real short stays pinned at ~0 Ω in **both**
probe directions.
:::

---

## 4. The 20 tests

Legend: **PASS** = what a healthy board shows. **If FAIL** → jump to the
[Diagnostic Matrix](#diagnostic-matrix).

:::danger The one rule that prevents false alarms
**Any probe point that reaches an IC pin** (ESP32, IP5306, USBLC6/ESD, SD card) can read a
**diode drop in ONE direction** — that is an internal protection/steering diode, **not a
short**. Confirm with **diode mode (`▶|`)**: *directional* (≈0.3–0.7 V one way, OL the
other) = **normal, proceed**; **~0 Ω / 0 V in BOTH directions** = **real short, stop**.

Only nets that are purely passive read a genuine open. The buzzer alone is reliable for
**T1–T5** (rails vs GND) and **T6/T8/T10/T12** (across the linear AMS1117). For **T7, T9,
T11, T17** (and any signal→IC test) use the directional diode check.
:::

### Group A — Rails vs GND (the fatal shorts)

Black probe **fixed on GND**. These five are the most important — a short here can kill
the ESP32 on power-up.

| # | Black | Red | PASS | If it beeps (~0 Ω) |
|---|-------|-----|------|--------------------|
| **T1** | GND | **+3V3** (AMS1117 tab) | no beep, >100 kΩ | short on 3.3 V rail → A1 |
| **T2** | GND | **+5V** (IP5306) | no beep | short on 5 V rail → A2 |
| **T3** | GND | **VBUS** (C17) | no beep | short on VBUS → A3 |
| **T4** | GND | **BAT+** (C18) | no beep | short on BAT+ → A4 |
| **T5** | GND | **BAT_IN** (J3.1) | no beep | short on battery input → A4 |

### Group B — Rail vs Rail (power bridges)

Neither probe on GND — two different rails. A beep here *usually* means the two rails are
welded together (the classic v1 via/trace bridge) — **except** across the IP5306 (see the
warning below).

| # | Probe A | Probe B | PASS | If it beeps |
|---|---------|---------|------|-------------|
| **T6** | +5V | +3V3 | no beep (AMS1117 blocks) | B1 (AMS1117 VIN–VOUT) |
| **T7** | VBUS | +5V | ⚠️ **may conduct** — verify with diode mode | B2 only if 0 Ω *both* directions |
| **T8** | VBUS | +3V3 | no beep | B3 (multi-rail bridge) |
| **T9** | BAT+ | +5V | ⚠️ **may conduct** — verify with diode mode | B4 only if 0 Ω *both* directions |
| **T10** | BAT+ | +3V3 | no beep | B3 |
| **T11** | BAT+ | VBUS | ⚠️ **may conduct** — verify with diode mode | B3 only if 0 Ω *both* directions |

:::danger IP5306 internal paths — T7 / T9 / T11 are NOT plain continuity tests
BAT+, VBUS and +5V are joined *inside* the IP5306 by the charger and the synchronous
boost (`BAT+ → L1 → SW → body diode → +5V`). So a **low-resistance / diode reading between
these three is normal**, not a short. **Do not** judge T7/T9/T11 with the buzzer.

**Disambiguate in diode mode (`▶|`):**
- Semiconductor path → **~0.3–0.7 V one direction, OL the other** → **normal, proceed**.
- Real short → **~0.000 V / 0 Ω in *both* directions** → defect, stop.

Tests that cross the **AMS1117** (T6, T8, T10, T12) have no such path — a linear regulator
blocks at 0 V bias — so those must read genuinely **open**.
:::

:::caution If T8/T10/T11 all beep together
That is the **v1 signature**: a single trace or via bridging *all* power nets to each
other and to GND. See [BUG #1/#2/#3](../rework/incident-power-short.md).
:::

### Group C — Regulator & decoupling checks

| # | Probe A | Probe B | PASS | If it beeps |
|---|---------|---------|------|-------------|
| **T12** | AMS1117 **pin 3** (VIN/+5V) | AMS1117 **tab** (VOUT/+3V3) | no beep (regulator doesn't conduct at 0 V) | C1 (solder bridge across regulator) |
| **T13** | AMS1117 **pin 1** (GND) | AMS1117 **tab** (VOUT) | no beep | A1 |
| **T14** | IP5306 **VOUT** (pin 8) | IP5306 **GND** (exposed pad) | no beep | A2 |
| **T15** | each +3V3 cap **C2 / C26 / C_dec** +pad | GND | no beep, all identical | A1 (find *which* cap beeps) |
| **T16** | each +5V cap **C1 / C19 / C27** +pad | GND | no beep | A2 |

:::note Isolating with per-cap tests
T15/T16 are how you *localize* a rail short: probe every cap on that rail; the ones
nearest the physical short beep loudest / most directly. The short is between the two
caps that both read 0 Ω.
:::

### Group D — Signal → power shorts (the hidden killers)

These caused 24 of the 44 v1 defects. A signal line must never be welded to a power rail
or GND (except through its intended pull-up).

| # | Probe A | Probe B | PASS | If it beeps |
|---|---------|---------|------|-------------|
| **T17** | USB **D+ (GPIO20)** and **D− (GPIO19)** | GND, then +5V | ⚠️ **may conduct** (USBLC6 ESD + ESP32 clamp) — verify with diode mode | D1 only if 0 Ω *both* directions |
| **T18** | any **button GPIO** pad | **+3V3** | ~**10 kΩ** (pull-up) — **not** 0, **not** open | D2 (0 Ω = short; open = missing pull-up) |
| **T19** | any **button GPIO** pad | **GND** | open (button not pressed) | D3 (button stuck / bridge) |
| **T20** | **LCD data** (D0–D7) & **SD SPI** (MOSI/MISO/SCK/CS) pads | +3V3, +5V, GND | no beep to any power/GND | D4 (fine-pitch bridge near FPC/SD) |

:::tip T18 is special — it should NOT be open and NOT zero
Each button GPIO has a 10 kΩ pull-up to +3V3. So T18 reading ≈ 10 kΩ is **correct**.
`0 Ω` = GPIO shorted to +3V3. `OL/open` = the pull-up resistor is missing or unsoldered.
For T18/T19 **any** resistor in the pull-up row works (the card shows R8 as an example).
:::

---

## 4b. Precise photo per test

Every card is generated from the **exact pad coordinates** in `esp32-emu-turbo.kicad_pcb`
(calibrated to the render), so there is no ambiguity: **🔴 ROSSO = red probe**,
**🔵 NERO = black probe**.

### Group A — Rails vs GND
![T1](/img/debug/tests/T1.png)
![T2](/img/debug/tests/T2.png)
![T3](/img/debug/tests/T3.png)
![T4](/img/debug/tests/T4.png)
![T5](/img/debug/tests/T5.png)

### Group B — Rail vs Rail
![T6](/img/debug/tests/T6.png)
![T7](/img/debug/tests/T7.png)
![T8](/img/debug/tests/T8.png)
![T9](/img/debug/tests/T9.png)
![T10](/img/debug/tests/T10.png)
![T11](/img/debug/tests/T11.png)

### Group C — Regulator & caps
![T12](/img/debug/tests/T12.png)
![T13](/img/debug/tests/T13.png)
![T14](/img/debug/tests/T14.png)
![T15](/img/debug/tests/T15.png)
![T16](/img/debug/tests/T16.png)

### Group D — Signal → power
![T17](/img/debug/tests/T17.png)
![T18](/img/debug/tests/T18.png)
![T19](/img/debug/tests/T19.png)
![T20](/img/debug/tests/T20.png)

---

## 4c. Extended full-board sweep (other subsystems)

Once the power rails are clean, sweep the rest of the board the same way. Two generic checks
per connector/IC:

- **Adjacent-pin bridge check** — probe each pin against its immediate neighbor → must be
  **open** (a beep = solder bridge, the fine-pitch failure).
- **Pin-to-power check** — each signal pin to the nearest **+3V3 / +5V / GND** → **open**,
  or a *directional* diode drop (ESP32 clamp) — never 0 Ω in both directions.

Buzzer is fine for adjacent-pin checks; for signal-to-power use the directional diode rule.

### E1 — Display FPC (J4, 40-pin, 0.5 mm pitch — highest bridge risk)

![J4 pinout](/img/debug/j4-fpc-pinout.png)

**Full pinout** (from `esp32-emu-turbo.kicad_pcb`):

| pin | net | pin | net | pin | net | pin | net |
|-----|-----|-----|-----|-----|-----|-----|-----|
| 1 | GND | 11 | NC | 21 | LCD_D3 | 31 | LCD_DC |
| 2 | +3V3 | 12 | NC | 22 | LCD_D2 | 32 | LCD_CS |
| 3 | +3V3 | 13 | NC | 23 | LCD_D1 | 33 | NC |
| 4 | GND | 14 | NC | 24 | LCD_D0 | 34 | +3V3 |
| 5 | GND | 15 | NC | 25 | GND | 35 | +3V3 |
| 6 | GND | 16 | NC | 26 | LCD_RST | 36 | GND |
| 7 | GND | 17 | LCD_D7 | 27 | NC | 37 | NC |
| 8 | +3V3 | 18 | LCD_D6 | 28 | NC | 38 | NC |
| 9 | NC | 19 | LCD_D5 | 29 | +3V3 | 39 | NC |
| 10 | NC | 20 | LCD_D4 | 30 | LCD_WR | 40 | NC |

:::caution Most adjacent J4 pins are the SAME net — a beep there is NORMAL
- **GND pins:** 1, 4, 5, 6, 7, 25, 36 — all one net, connected by design.
- **+3V3 pins:** 2, 3, 8, 29, 34, 35 — all one net.

So "contacts between pins" in a photo (e.g. **5 of the first 10 pins are GND**) are the
ground pins tied together — **not a solder defect**. `T1 (+3V3↔GND) clean` proves GND and
+3V3 are not shorted to each other on the FPC.
:::

| Check | Expected |
|-------|----------|
| GND pins ↔ each other / +3V3 pins ↔ each other | ~0 Ω **by design** (ignore) |
| GND ↔ +3V3 | open (already ✅ via T1) |
| **LCD_D0–D7 adjacent** (pins 17↔18…23↔24) | **open** — a beep here = real bridge |
| LCD_WR / DC / CS (30/31/32) adjacent | open |
| any LCD_* ↔ GND / +3V3 | open or directional (ESP32 clamp) |

### E2 — SD card (U6)
Nets: `SD_CS`, `SD_MOSI`, `SD_CLK`, `SD_MISO`, `+3V3`, `GND`.

| Check | Expected |
|-------|----------|
| adjacent U6 pins | open |
| any SPI line ↔ +3V3 / GND | open / directional |
| U6 `+3V3` (pin 4) ↔ GND (pin 6/10) | open |

### E3 — Audio amp (U5, PAM8403)
Bottom row (pins 9–16): `NC · I2S_DOUT · GND(11) · +5V(12) · +5V(13) · SPK-(14) · GND(15) · SPK+(16)`.

![PAM8403 pin map](/img/debug/audio-pam8403-pins.png)

| Check | Expected |
|-------|----------|
| pin 12 ↔ pin 13 | **~0 Ω by design** (both are +5V, same net) — not a fault |
| +5V pin ↔ GND pin (11/15) | low reading = **decoupling-cap charging**, not a short (T2 already proved +5V≠GND). Confirm in Ω: value **climbs**, doesn't stay pinned at 0 |
| `SPK+` ↔ `SPK-` | open |
| `SPK±` ↔ +5V / GND | directional (output-stage body diodes) — not 0 Ω both ways |

:::note proto #1 — audio "short" is a false alarm
The adjacent bottom pins read low because they are **power pins + the VCC decoupling cap**
(pin 12/13 = same +5V net; the cap ties +5V↔GND). Since **T2 (+5V↔GND) is clean**, this is
the capacitor-charging artifact, **not** a solder bridge. Same class as [T17](#t17--false-alarm-resolved).
:::

### E4 — Buttons (pull-ups R4–R15)
| Check | Expected |
|-------|----------|
| across any pull-up (BTN_x ↔ +3V3) | ≈ **10 kΩ** (not 0, not open) |
| BTN_x pad ↔ GND (button not pressed) | open |
| BTN_x pad ↔ GND (button pressed) | ~0 Ω (that is the switch working) |

### E5 — I2S audio bus (not a connector — 3 signals ESP32 → audio)

I2S is **3 traces**, not a header. Source = **ESP32-S3 (U1) pins 8, 9, 10** (three adjacent
pins on the module edge):

![I2S ESP32 pins](/img/debug/i2s-esp32-pins.png)

| ESP32 pin | net | goes to |
|-----------|-----|---------|
| 8 | `I2S_BCLK` | (stays at MCU) |
| 9 | `I2S_LRCK` | (stays at MCU) |
| 10 | `I2S_DOUT` | → RC filter **R20 / R21 / C22** → **PAM8403 (U5) pin 7 & 10** |

Only `I2S_DOUT` is routed to the amplifier (through an RC filter, since the PAM8403 input is
analog). Test points: U1 pins 8-9-10, or the audio-side filter (R20/R21/C22) next to U5.

| Check | Expected |
|-------|----------|
| U1 pin 8 ↔ 9 ↔ 10 (adjacent) | open — a beep = bridge on the MCU edge |
| any I2S pin ↔ +3V3 / GND | open or directional (ESP32 clamp) |
| `I2S_DOUT` at U5 pin 7 ↔ pin 10 | ~0 Ω (same net, by design) |

:::note Log anything unexpected
Add any beep found here to the [findings table](#5b-current-board-findings--proto-1-2026-07-14)
with the exact pins, the same way T9/T17 were recorded.
:::

---

## 5. Diagnostic Matrix {#diagnostic-matrix}

Find your failing test(s) in the left column → the likely root cause and where to inspect.

| Code | Failing tests | Most likely cause | Where to look first |
|------|---------------|-------------------|---------------------|
| **A1** | T1, T13, T15 | Short on **+3V3** to GND | C2/C26/C_dec (cracked/whiskered MLCC), AMS1117 VOUT↔GND bridge, ESP32 3V3 pad, a button pull-up node, LED solder blob |
| **A2** | T2, T14, T16 | Short on **+5V** to GND | C1/C19/C27, IP5306 VOUT↔GND, AMS1117 pin 3 area |
| **A3** | T3 | Short on **VBUS** to GND | C17, USB-C VBUS pin ↔ shell, IP5306 VIN |
| **A4** | T4, T5 | Short on **BAT+ / BAT_IN** | C18, Q1 (RPP MOSFET) drain↔GND, L1, IP5306 BAT pin, reversed JST |
| **B1** | T6 | **+5V welded to +3V3** | AMS1117 VIN (pin 3) ↔ VOUT (tab) solder bridge, or a trace/via crossing |
| **B2** | T7 (0 Ω both dirs) | **VBUS welded to +5V** | IP5306 VIN (pin 1) ↔ VOUT (pin 8) bridge. ⚠️ a *directional* diode reading is the normal internal charge path, not this |
| **B3** | T8, T10 (esp. together) | **Multi-rail power bridge** — the v1 signature | A via or signal trace overlapping two power traces on F.Cu; see incident BUG #1–#3. Inspect vias near C19 / under the display |
| **B4** | T9 (0 Ω both dirs) | **BAT welded to +5V** | IP5306 BAT (pin 6) ↔ VOUT (pin 8), or L1 pad bridge. ⚠️ a *directional* diode reading (~0.4 V) is the **normal boost path** — only a both-directions 0 Ω is the defect |
| **C1** | T12 | Solder bridge **across the AMS1117** | Reflow the SOT-223; check tab↔pin 3 whisker |
| **D1** | T17 (0 Ω both dirs) | **USB D± shorted** | USBLC6 (U4) reflow, USB-C connector D-pin bridge, R22/R23. ⚠️ a *directional* diode reading is the normal ESD/clamp path, not this |
| **D2** | T18 = 0 Ω | **Button GPIO shorted to +3V3** | Pull-up resistor blob, GPIO trace pinched to 3V3 |
| **D2′** | T18 = open | **Missing pull-up** | R4–R15 not soldered / wrong value |
| **D3** | T19 beeps | **Button stuck closed / GPIO↔GND bridge** | The tact switch, its pads, debounce cap C5–C16 |
| **D4** | T20 | **Fine-pitch signal bridge** | FPC connector J4 (0.5 mm pitch) or SD card slot solder bridges |

### Reading combinations

- **Only one rail-to-GND test beeps** → localized short on that rail → use T15/T16 to find the cap.
- **Several rail-to-rail tests beep together** → power bridge (B3), not a component — inspect copper/vias.
- **A rail-to-GND *and* rail-to-rail both beep** → the bridge has chained a rail to GND *through* another rail (exactly the v1 chain GND↔VBUS↔+5V↔+3V3).

---

## 5b. Current board findings — proto #1 (2026-07-14)

:::danger U2 is likely fine — the AMS1117 burn is the real, separate fault
**Symptom:** connecting only USB-C (5 V), the **AMS1117 (U3)** overheats and burns —
repeatedly, across several replacement regulators. **This is the real, confirmed problem.**

**Re-evaluated (was "confirmed U2 short"):** the T9 0 Ω was read between the **two middle-right
pads of U2 — pin 7 (LX) and pin 6 (BAT+)**. Those two pins are the **terminals of the boost
inductor L1** (verified in the PCB: `L1 pad 1 = BAT+, pad 2 = LX`). An inductor is a coil of
wire → a DC short (~50–150 mΩ), so **0 Ω in both directions there is normal, not a defect.**
The "internal LX↔VOUT short" is **not confirmed** — see the corrected T9 test below.

**Why the AMS1117 dies (nothing to do with U2):** it is a **linear** regulator dropping
5 V→3.3 V, so it burns `P = (5 − 3.3)·I₃ᵥ₃ = 1.7 V · I` as heat inside a tiny SOT-223. A linear
reg that dies *repeatedly* almost always has a **short/overload on its OUTPUT (+3V3)** —
replacing it without removing the load simply cooks the next one. ⚠️ **T1 (+3V3↔GND) clean at
DC does NOT rule this out** — a tantalum leak or chip over-current appears only *under voltage*.

**Do this, in order:**
1. **Retest U2 properly** — measure **pin 7 (LX) ↔ pin 8 (+5V)** (the *upper* pair, the one L1
   does **not** bridge). Directional/open → U2 is healthy; drop the "remove U2" plan.
2. **Find the +3V3 load** ([3.3 V-side verification](#33-v-side-verification-esp32--c2)) — remove
   U3, measure +3V3↔GND: hundreds of Ω–kΩ = OK; **tens of Ω = the fault that burns your
   regulators.** Fix it **before** fitting a fresh AMS1117.
:::

:::danger T9 revisited — the 0 Ω is inductor L1, not a short
The reading was between **pin 7 (LX) and pin 6 (BAT+)** — the two middle-right pads. **L1 sits
directly across those two pins** (`BAT+ ─ L1 ─ LX`), so **0 Ω in both directions is exactly
what a healthy board reads**: you measured the inductor's DC resistance, not a fault. That is
*why* the "short" was so perfectly localized — L1 is the only external part tying two U2 pins
together at near-zero Ω; every other adjacent pin pair reads open.

**To actually test the suspected LX↔VOUT internal short**, probe the pair L1 does **not**
bridge — **pin 7 (LX) ↔ pin 8 (+5V)**:

- **directional (~0.3–0.5 V one way, open the other) or fully open** → **U2 is fine.** The whole
  T9 alarm was L1. Move on to the +3V3 side (the real AMS1117 cause).
- **0 Ω both ways** → *only then* is it a genuine LX↔VOUT short (internal sync-FET or a hidden
  pin 7–8 bridge): reflow pins 7–8 with flux; still 0 Ω both ways → remove U2 and re-measure the
  bare pads.
:::

| Test | Nets | Result | Localized to | Verdict |
|------|------|--------|--------------|---------|
| +3V3 ↔ GND (T1) | +3V3 / GND | no beep | — | ✅ clean |
| +5V ↔ GND (T2) | +5V / GND | no beep | — | ✅ clean |
| **T9** | **BAT+ ↔ +5V** (pin 6 ↔ pin 8) | 0 Ω recorded — but probes hit **pin 6–7** | mislabeled image → wrong pads; **pin 6–7 = inductor L1**, 0 Ω by design | ✅ **NOT a defect** — re-run in diode mode (directional = healthy chip) |
| **T17** | USB D+ ↔ GND | U4 pin 3 ↔ pin 4 = 0 Ω; **pin 2 (GND) verified isolated** | pin 3 & 4 are **both USB_D+** (same net) | ✅ **NOT a defect** (false alarm) |
| T3/T4/T5, T6, T8, T10, T12 | rails & rail-pairs | verified | — | ✅ all clean |
| E2 — SD (U6) | SPI + power | verified | — | ✅ clean |
| E3 — Audio (U5) | PAM8403 bottom pins | adjacent power pins read low | pin 12/13 = same +5V net; +5V↔GND via decoupling cap (T2 clean) | ✅ **NOT a defect** (cap artifact) |
| E1 — Display FPC (J4) | GND/+3V3 same-net + LCD_D0–D7 data lines | verified | 5× GND in first 10 = same net (matches schematic) | ✅ **clean** — data lines isolated, no bridge |
| E5 — I2S bus (U1 pins 8-10) | BCLK/LRCK/DOUT | verified | — | ✅ clean |
| USB-C (J1) | photo inspection + T17 | solder OK, CC pull-down (5101) present | — | ✅ clean (T17 already verified) |

**Bottom line:** no confirmed short on U2 — the T9 0 Ω is the inductor L1. The **one real fault
is the repeated AMS1117 burning**, and it points to a **+3V3-side overload** (see root cause).

### T9 re-evaluated — the 0 Ω is inductor L1, not an IP5306 short {#t9-inductor-l1}

The 0 Ω was read between **pin 7 (LX) and pin 6 (BAT+)** — the two middle-right pads. In the
boost, **BAT+ connects to LX through inductor L1** (verified: `L1 pad 1 = BAT+, pad 2 = LX`). An
inductor is a piece of wire → a DC short (~50–150 mΩ), so a multimeter reads **~0 Ω in both
directions there on a perfectly healthy board.** This is exactly *why* the "short" looked so
localized: L1 is the only external part tying two U2 pins together at near-zero Ω; every other
adjacent pin pair reads open.

Two things compounded into the false "confirmed short":

1. The **mislabeled T9 image** (now fixed) shifted the pin circles down one pad, so the probes
   actually landed on **pin 6–7** while being read as "pin 7–8 (LX↔+5V)".
2. Even so, **pin 6↔7 = across L1 = 0 Ω expected** — it proves nothing about the chip.

**Correct test:** measure **pin 7 (LX) ↔ pin 8 (+5V)** (the pair L1 does *not* bridge).
Directional/open → **U2 is healthy**; the real problem is the AMS1117 / +3V3 side above.

![T9 — IP5306 pins (pin 6–7 are the inductor L1 terminals)](/img/debug/short-t9-ip5306.png)

**Only if** pin 7↔8 truly reads 0 Ω both ways does the internal-short story apply (then +5V would
be welded to the battery net — keep the battery disconnected until that pair reads directional).

### T17 — false alarm (resolved)

On U4 (USBLC6) **pin 3 and pin 4 are both `USB_D+`** (same net by design), so 0 Ω between
them is expected. Pin 2 (GND) was verified **isolated** from pin 3 and pin 4 → no D+↔GND short.

![T17 — USBLC6 pins](/img/debug/short-t17-usblc6.png)

#### Why the diode/continuity reading on D+↔GND was misleading

Two effects stack on the D+ net and fake a short:

1. **ESD diodes** — D+ is tied to GND and VBUS through the USBLC6 internal steering diodes
   and the ESP32 GPIO clamp diodes → always a low-voltage path.
2. **Rail capacitance (the real culprit)** — D+ links (through a USBLC6 diode) to **VBUS**,
   which carries tens of µF to GND (C17, C1, C19, C27). The meter's test current first
   **charges those caps**, so the display sits near **0 for a moment in *both* directions**
   (a cap charges regardless of polarity). It *looks* like a short but is not.

**How to tell them apart:** a real short stays **pinned at 0** and stable; a cap+diode
reading **starts low then climbs** (to OL, or a ~0.3–0.5 V diode drop). When in doubt,
**measure pin-to-pin at the component** (as done here for U4 pin 2 vs 3/4) — that beats the
rail-level reading because there is no bulk capacitance in the path. This is the practical
face of [the one rule](#the-one-rule-that-prevents-false-alarms) above.

### Understand T9 before touching it — bridge vs chip damage

The short is already localized to **U2 pin 7 ↔ pin 8**. Before reworking, confirm *what* it
is so you don't chase the wrong fix:

1. **Look** — a phone macro shot or a 10× loupe on U2 pins 7–8. A **visible solder blob**
   bridging the two pins → simple assembly defect, reworkable (most likely).
2. **Nothing visible?** The bridge may be **under the exposed pad** or a whisker — reflow the
   whole side; if it persists, the IC may be internally damaged (rare) and needs replacing.
3. **Isolate the culprit** — lift/verify: probe **pin 8 (+5V) vs pin 6 (BAT+)** and
   **pin 8 vs L1**. If only 7↔8 reads 0 Ω and 6↔7 does not, the bridge is precisely the 7–8 gap.
4. **After power-on (later):** if +5V never reaches 5 V and the IP5306 gets hot with the
   bridge removed, the boost stage was damaged — replace U2.

### Rework — remove the IP5306 pin 7–8 bridge

**Both pins stay soldered — you remove only the excess solder in the gap between them.**
Pin 7 (LX) must keep its joint to the L1 pad; pin 8 (+5V/VOUT) must keep its joint. You are
*not* leaving them unsoldered — you only delete the blob that bridges the two.

:::note "There's no gap between the two pins" — that IS the bridge
The IP5306 has 1.27 mm pitch, so a good board shows **~0.6 mm of bare PCB (soldermask)**
between the pin 7 and pin 8 pads. If you see no gap, solder is filling it. The rework goal is
to **make that gap reappear**: remove excess solder until the dark/green soldermask strip
shows between the two separate, shiny pads. Then pin 7 ↔ pin 8 reads open/directional.
:::

**Technique B (drag — best for bridges):** apply **plenty of flux** on pins 7-8, then drag a
**clean, hot, fine iron tip** along the pins. Surface tension pulls solder back onto each pad
and the excess onto the tip → each pin stays soldered, the bridge is gone. No added solder.

**Technique A (wick):** flux + solder wick over the two pins + hot iron to soak the excess.
⚠️ It often removes **too much** — then **re-solder each pin** with a tiny amount of fresh
solder, without re-bridging.

**Verify after rework (continuity):**
1. Pin 7 ↔ its pad / L1 = connected (you didn't lift the pin).
2. Pin 8 ↔ +5V = connected.
3. Pin 7 ↔ Pin 8 = now **open / directional** (diode mode, no longer 0 V both ways).

Then re-measure **T9** (BAT+ ↔ +5V) in diode mode → must be **directional** (~0.4 V one way,
OL the other) = healthy boost path. Only then proceed to **controlled power-on** (5 V,
100 mA limit, no battery first).

### Alternative — USB-only bypass (skip the IP5306)

If the IP5306 is internally shorted (or you have no replacement), you can **isolate it** and
run the board from USB-C, **sacrificing battery power + charging** (the IP5306's only jobs).
Everything else works, because the supply chain is `USB 5V (VBUS) → +5V → AMS1117 → 3V3 →
ESP32 & peripherals`.

![USB-only bypass](/img/debug/bypass-usb-only.png)

1. **Remove U2 (IP5306)** — eliminates the short, isolates the faulty chip.
2. **Jumper VBUS → +5V**: a short wire from the **pin 1 pad (VBUS)** to the **pin 8 pad
   (+5V)**, running along the top edge of the now-empty footprint (they are already the right
   traces). USB 5V now feeds the +5V rail directly.

![IP5306 full pinout](/img/debug/ip5306-pinout-full.png)

:::note Pin 1 and pin 8 are on opposite sides — that's correct (SOP-8)
Pins 1-4 run down one side, 5-8 up the other, so **pin 1 (VBUS) and pin 8 (+5V) sit at the
two top corners, facing each other**. Pin 8 is both "top of the 6-7-8 side" (T9 photo) *and*
"opposite pin 1" — same pin. **Note:** the render photos are a **mirrored bottom view**, so
left/right look swapped vs the physical chip. Foolproof ID: **pin 1 = the dot (VBUS, trace to
C17/USB-C)**, **pin 8 = opposite the dot (+5V, trace to C19/AMS1117)**.
:::

:::tip Easier — jumper between two capacitors (no pin counting)
To avoid the pin-numbering / mirror confusion entirely, run the jumper between two **large,
obvious capacitors** instead of the IC pads. Electrically identical (VBUS→+5V):
**C17 (VBUS) → C19 (+5V)**. Which exact IP5306 pins are shorted (6-7 vs 7-8) does **not**
matter — you remove the whole chip anyway.

![Cap-to-cap bypass](/img/debug/bypass-cap-to-cap.png)
:::

**Verify:** with U2 gone, pin 7 ↔ pin 8 pads = open (confirms the short was internal); after
the jumper, VBUS ↔ +5V = 0 Ω (intended) and +5V ↔ GND still open. Then power on (5 V, 100 mA).

**Kept:** ESP32, display, SD, audio, buttons, USB flashing. **Lost:** battery, charging.

### 3.3 V-side verification (ESP32 + C2) {#33-v-side-verification-esp32--c2}

#### Why the AMS1117 burns — root cause

The repeated AMS1117 death is the **one real, confirmed fault** on proto #1 — and it is
**not** related to U2/L1 (that was a false alarm; see [T9 re-evaluated](#t9-inductor-l1)).

The AMS1117 is a **linear** regulator: it drops 5 V→3.3 V by dissipating the difference as
**heat** inside a tiny SOT-223.

```
P = (Vin − Vout) × I₃ᵥ₃ = 1.7 V × I₃ᵥ₃
```

- ~500 mA (ESP32-S3 WiFi TX + display): **P ≈ 0.85 W** → with modest copper the junction runs
  ~100 °C. Hot, but it survives.
- Pushed into **current-limit / a partial short** (~1 A): **P ≈ 1.7 W** → junction well past
  150 °C → death.
- A **hard short on +3V3**: full current at ≥1.7 V across the part → it cooks **instantly**.

**The decisive clue is that it died *repeatedly*, across several regulators.** A linear reg
that dies again and again almost always has a **persistent short/overload on its OUTPUT
(+3V3)** — swapping the regulator without removing the load just cooks the next one. So the
genuine short you were hunting is on the **+3.3 V rail**, not on U2. Likely culprits, in order:

1. **Solder bridge / short** on the dense ESP32-S3 3V3 pins or its decoupling caps.
2. **Damaged ESP32-S3 (U1)** drawing excessive current (e.g. from a bypass-jumper slip that put
   5 V onto 3V3).
3. **`LCD_BL` backlight** mis-wired / over-drawing on +3V3.
4. **C2 tantalum** failed short (polarity is audited-correct, but inrush can still short a
   tantalum — verify by ohm-check).

⚠️ **A clean T1 (+3V3↔GND) at DC does NOT clear this** — a leaky tantalum or an over-current IC
only shows up *under voltage*. Do the checks below **before** trusting a fresh regulator.

**Step 1 — C2 tantalum (22 µF on +3V3).** Tantalums fail **short**; C2 is already flagged as
a suspect in this project.
- Board unpowered, AMS1117 **removed** (or +3V3 isolated): measure **C2 pad+ ↔ C2 pad−**
  (= +3V3 ↔ GND). Should read **open / high** and **climb** (cap charging). A pinned **0 Ω** =
  shorted tantalum → replace C2 (watch polarity: band = +).

![Step 1 — C2 tantalum test](/img/debug/v33-c2-test.png)

**Step 2 — +3V3 rail idle current (needs the bypass + a fresh AMS1117).**
- Power via bench supply **5 V, 100 mA limit** (USB-only bypass in place).
- Healthy idle (ESP32 not running yet / in reset): board draws **< 50 mA**, AMS1117 stays
  **cool**.
- AMS1117 hot again / current pegged → **downstream load on +3V3** → the ESP32 (U1) or C2 is
  damaged and pulling current.

**Step 3 — isolate ESP32 vs C2.**
- If step 1 cleared C2 but the AMS1117 still overheats → the **ESP32-S3 module (U1)** likely
  took over-voltage damage on its 3V3 pins and now draws excessive current → replace U1.
- Confirm: with AMS1117 fitted, feel U1 — a damaged module often gets **warm/hot** with no
  firmware running.

![Step 3 — ESP32 3.3V side](/img/debug/v33-esp32-test.png)

**Order of repair:** retest U2 pin 7↔8 (diode — probably fine, skip removal) → **find & clear
the +3V3 load** (C2, then U1) → fit a fresh AMS1117 → power-on current-limited → if still hot,
the +3V3 load is not gone.

---

## 6. Controlled power-on (after all 20 pass)

**Bench supply (preferred):** 5 V, **100 mA current limit**, connect USB-C.
- Idle draw expected **< 50 mA**.
- Current instantly at the limit → hidden short the meter missed → disconnect, re-check.

**Normal USB charger:** right after plugging in, touch **AMS1117** and **IP5306**.
- Hot within seconds → short → unplug immediately.
- Then measure voltages (meter in **V⎓ / DC**): VBUS = 5.0 V · +5V ≈ 5 V · +3V3 = 3.3 V ·
  BAT+ = 0 V (no battery).

---

## 7. Test log

Fill this in per board. `✅` = no beep / expected. `🔴` = short found.

| Date | Board | T1 3V3-GND | T2 5V-GND | T9 BAT-5V | T17 D+-GND | T6 5V-3V3 | T8 VBUS-3V3 | Power-on mA | Notes |
|------|-------|-----------|-----------|-----------|------------|-----------|-------------|-------------|-------|
| 2026-07-14 | proto #1 | ✅ | ✅ | ⚠️ L1 (false alarm) | ✅ (false alarm) | ✅ | ✅ | ⛔ not yet | **Full board swept clean.** T9 "short" was **inductor L1** across pin 6–7 (mislabeled image) — **no confirmed U2 short**. **Real fault: AMS1117 (U3) burns repeatedly → +3V3-side overload.** Retest U2 pin 7↔8 (diode), then hunt the +3V3 load before fitting a new AMS1117 |

---

## 8. Repair & bring-up plan (do it in this order)

Everything needed to get proto #1 running, start to finish. **Keep the battery
disconnected** until the very end; power only from a **current-limited bench supply
(5 V, 100 mA)** or a USB source you can monitor.

### A. First: confirm U2 is actually faulty (probably it isn't)
- [ ] **Diode mode, pin 7 (LX) ↔ pin 8 (+5V)** — the pair L1 does *not* bridge.
      **Directional or open → U2 is healthy, SKIP the removal**, go straight to C.
      *(Do not judge pin 6↔7: that's just inductor L1 = 0 Ω by design — the T9 false alarm.)*
- [ ] **Only if pin 7↔8 = 0 Ω both ways:** remove U2 (hot air ~350 °C / Chip-Quik), clean the
      pads (wick + flux), and confirm empty-footprint **pin 7 pad ↔ pin 8 pad = open**.

### B. USB-only bypass (gives up battery + charging)
- [ ] Solder a jumper **VBUS (pin 1 pad) → +5V (pin 8 pad)** across the top of the U2 footprint.
- [ ] **Verify:** `VBUS ↔ +5V = 0 Ω` (intended), `+5V ↔ GND = open`.

### C. Check the 3.3 V side (find any downstream load)
- [ ] **C2 tantalum** (+3V3 ↔ GND): open/climbing = ok; pinned 0 Ω = shorted → replace C2
      (band = +).
- [ ] Inspect ESP32 (U1) for prior damage (visual + later thermal check).

### D. Fit the regulator — prefer a buck over a fresh AMS1117

The AMS1117 is a **linear** reg: it burns `(5 − 3.3)·I` as heat and self-destructs under
overload. A **buck** (switching) reg is ~90 % efficient (vs 66 %), runs **~5× cooler**, and has
current-limit + thermal-shutdown + **hiccup** — so it **stops the "keep killing regulators"
cycle** and doubles as a fault detector: delivers 3.3 V clean = OK; drops into hiccup/foldback =
a real downstream load still to find.

| At 500 mA | AMS1117 linear | Buck |
|---|---|---|
| Efficiency | 66 % | ~90 % |
| Dissipated as heat | ~0.85 W 🔥 | ~0.18 W ❄️ |

- [ ] **Recommended (proto #1):** wire a small **buck module** (e.g. MP1584 mini, ~€0.5) to the
      U3 pads — `+5V → IN`, `GND → GND`, `OUT → +3V3 pad`. ⚠️ **Set its output to 3.3 V *before*
      connecting it** — adjustable modules ship at a random voltage; 5 V on +3V3 kills the ESP32.
- [ ] **Or (simplest):** solder a **new AMS1117-3.3** drop-in — works, but stays thermally
      marginal for the ESP32-S3 + 3.95″ display load.
- [ ] **v2 PCB:** design in a dedicated **buck IC** (MP2315 / TPS563 / MP1584) with inductor +
      in/out caps + feedback divider. 3 W @ 3.3 V ≈ 900 mA — ample for ESP32-S3 + display + SD +
      audio. Keep good output caps / an LC filter on the audio DAC (switching ripple).

### E. Controlled power-on

Heat = power = V·I, so if the reg ever got hot, real power flowed — measure it, don't guess.

- [ ] Bench supply **5 V, 200 mA limit**, **no battery**, **ammeter in series on +5V**.
- [ ] Read the **actual current**: idle **< 50 mA** = OK. Limit pegged / buck in **hiccup** →
      real +3V3 load (C2 or U1) — find it before trusting the rail.
- [ ] Measure: **+5V = 5.0 V** (steady, **not higher** — a high Vin also cooks a linear), and
      **+3V3 = 3.3 V**.
- [ ] Touch the regulator + **ESP32** — must stay **cool**. ESP32 hot with no firmware → U1
      damaged, replace it.

### F. Functional bring-up (once voltages are good)
- [ ] Connect USB-C, open serial monitor (115200) → ESP32 boot messages.
- [ ] Flash firmware ([firmware build](../development/workflow-guide.md)).
- [ ] Test display (fill test), SD (mount), audio (tone), all 12 buttons.

### Result if all pass
Board runs as a **USB-powered** handheld (no battery). To restore battery + charging later,
fit a **known-good IP5306** in place of the bypass and re-run tests **T4, T5, T9** (must be
directional, not shorted).
