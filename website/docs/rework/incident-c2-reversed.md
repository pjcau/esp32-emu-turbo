---
id: incident-c2-reversed
title: "Incident: C2 Tantalum Mounted Reversed (Proto #1)"
sidebar_position: 4
---

# Incident: C2 Tantalum Mounted Reversed — Proto #1

**Date:** 2026-07-24
**Severity:** Critical (repeated regulator destruction, board unusable on +3V3)
**Affected boards:** Proto #1 (assembled from pre-fix production files)
**Status:** Root cause identified from photo evidence — repair pending
**Related:** [Short-Circuit Test Bible](../manufacturing/short-test-multimeter.md), `hardware/datasheets/POLARITY_AUDIT.md`

## TL;DR — what is wrong, in one picture

**C2, the 22 µF tantalum capacitor on the AMS1117 output, is soldered 180° rotated.**
Its polarity stripe (which on a tantalum marks the **positive** terminal) sits on the
**GND** pad instead of the **+3V3** pad. A reverse-biased MnO₂ tantalum conducts,
overheats and degrades into a **hard short between +3V3 and GND** — which is why
every AMS1117 soldered onto this board overheated and died.

![C2 polarity: as built vs correct](/img/debug/c2-polarity-diagram.svg)

## Symptoms

1. Every AMS1117 mounted on proto #1 overheated badly as soon as power was applied
   ("brucia maledettamente"), one regulator after another.
2. With the regulator **removed**, the multimeter reads **0 Ω between the +3V3 output
   pad and GND** (chassis / USB shell / any ground) — a permanent short on the 3.3 V
   rail, present with no regulator on the board.
3. The J4 display FPC connector tested clean: no shorts, expected voltages on its pins.

## The measurement

With U3 (AMS1117) desoldered, continuity was measured from the +3V3 output pad toward
ground: **beep / ~0 Ω in both directions**. The 5 V rail and VBUS were unaffected.

![Probing the bare AMS1117 pads after removing the regulator](/img/debug/c2-short-probe.png)

*Probing the AMS1117 area after removing the regulator. The 0 Ω reading between the
+3V3 pad and chassis ground is the "anomalous load" that had been killing regulators.*

## False trails (kept for the record)

| # | Hypothesis | Why it was wrong |
|---|-----------|------------------|
| 1 | IP5306 internal LX↔VOUT short (test T9) | The 0 Ω was measured across inductor L1's own terminals — an inductor **is** a DC short. See [T9 re-evaluated](../manufacturing/short-test-multimeter.md#t9-inductor-l1). |
| 2 | AMS1117 defective batch | The regulators died shorted (0 Ω pin 1↔2 on the removed part), but that is the *consequence* of thermal death, not the cause. |
| 3 | "A diode with its cathode wired to chassis ground" | The component next to the regulator is **not a diode** — it is C2, the tantalum output cap. The stripe on a tantalum marks the **anode (+)**, the *opposite* of a diode's cathode band. And "chassis" is not a separate net: the USB shell and all 7 J4 ground pins are the one GND net by design. |

## Root cause — photo evidence

C2 sits 7 mm below the AMS1117, on the same (bottom) copper layer. Left pad is routed
to **+3V3** (the AMS1117 VOUT/tab), right pad to **GND**:

![AMS1117 area with C2 below, pads labeled](/img/debug/c2-reversed-photo.png)

Zooming in on C2, the polarity stripe (red box) is on the **right** end — the **GND**
side. On the Vishay TMCM tantalum the stripe marks the **positive** terminal, so the
part is reverse-mounted. Note the body marking is also printed upside-down, consistent
with a 180° rotation at assembly:

![C2 close-up: polarity stripe on the GND side](/img/debug/c2-reversed-zoom.png)

### Failure chain

```
C2 mounted 180° rotated (anode → GND, cathode → +3V3)
        │
        ▼
MnO₂ tantalum permanently reverse-biased at 3.3 V
        │  (reverse leakage → self-heating → dielectric damage)
        ▼
C2 degrades into a hard short: +3V3 rail ≈ 0 Ω to GND
        │
        ▼
AMS1117 sources its full current limit into the short,
dissipates (5 V − 0 V) × I_limit ≈ several watts in SOT-223
        │
        ▼
Regulator overheats and dies shorted → replaced → dies again → …
```

## Why it happened

The C2 polarity problem was **already known and fixed** in the production files:
commit `dabf830` (2026-04-15) added `_JLCPCB_ROT_OVERRIDES["C2"] = 180` after the
iBOM-vs-JLCPCB-preview mismatch was spotted (full evidence in
`hardware/datasheets/POLARITY_AUDIT.md`). That fix required **re-uploading the
BOM + CPL to order SMT026041362110**.

Proto #1 was evidently assembled from the **pre-fix CPL**, so the SMT line placed C2
(and likely LED2, which was part of the same fix) with the old, wrong rotation.

## Repair plan

1. **Desolder C2.** Re-measure +3V3 pad ↔ GND: the short must disappear.
   (Definitive proof: the removed part will read shorted/leaky out of circuit too.)
2. **Do not reuse the tantalum** — it is electrically compromised even if it still
   reads "okay" after cooling.
3. **Replace with a 22 µF MLCC** (≥10 V, X5R/X7R, same 1206 pad). The tantalum was
   only there for the AMS1117's output-ESR stability window (0.3–22 Ω); since the
   linear regulator is being replaced by an **MP1584 buck module**
   (see [repair plan D](../manufacturing/short-test-multimeter.md)), the ESR
   constraint is gone and an MLCC is strictly better.
4. **Set the MP1584 output to 3.3 V with no load connected, before wiring it to the
   board.** The trimmer usually ships well above 3.3 V.
5. **Check LED2** (green charge LED): it was in the same polarity fix, so it is likely
   also mounted reversed. Harmless — a reversed LED simply never lights — but flip it
   180° if the charge indicator is wanted.

## Lessons learned

- **Tantalum stripe = plus.** Opposite of the diode convention. When a "mystery diode"
  appears next to a regulator, first check whether it is a polarized capacitor.
- **A shorted regulator is usually the victim.** Before replacing a burned linear
  regulator, measure the rail it feeds: if the output is ~0 Ω to GND, find the load
  first (test **T13/T15** of the Short-Circuit Test Bible do exactly this).
- **A polarity fix is not done until the CPL is re-uploaded.** The design-side fix
  existed for three months; the assembled board never received it. Any future order
  must verify the uploaded CPL hash matches `release_jlcpcb/cpl.csv` at HEAD.
- **Incoming inspection for polarized parts:** after assembly, photo-verify stripe/dot
  orientation of every part listed in `POLARITY_AUDIT.md` *before first power-on*.
  A 30-second visual check would have saved several regulators and hours of debugging.
