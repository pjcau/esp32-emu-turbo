# PCBA Readiness review — 2026-08-17 (v4.9.0 == v4.6.2)

**Verdict: `SUBMISSION-READY`.** Tier-1 (design-error) risk is ZERO; every
tier-2 (prototype-gap) item is either closed by analysis with a cited
number or on the first-article bench checklist. **The only remaining way
this order comes back wrong is a factory/assembly defect (tier-3), which
the first-article inspection catches — plus one non-board compute risk
(SNES full-speed) that is a firmware/silicon question, not a board defect.**

Board never physically prototyped. This review closes the gap by analysis
(datasheets on disk + esp-box-emu/Retro-Go references) and names what
genuinely needs the first article.

## Tier 1 — design-error: ZERO (must be, and is)

- hardware-audit **Round 37**: all Layer-1 gates green (trace-through-pad,
  crossings, clearance 0 DANGER, connectivity, DFM 124, DFA 10, polarity
  304, datasheet-nets 267, design-intent 369, sync, netlist-diff,
  board-config, strapping, decoupling, power-seq/paths, ERC 0, KiCad DRC
  0/0), gate-coverage 13/13, revert-residue clean.
- **JLCDFM v4.9.0** (fab-view ground truth): PCB DFM 0 DANGER; SMT = 2
  proven library-model artifacts only (J4 FPC pin-inner-edge, U2 thermal-EP
  GND lead-to-hole), neither a defect.
- **Five independent domain analyses (below) found NO design error.**

## Tier 2 — prototype-gap ledger

### CLOSED-BY-ANALYSIS (no hardware needed)

| Domain | Closed by |
|---|---|
| **Vout 3.327 V** | R25=100k/R26=22k → 0.6·(1+100/22)=3.327 V [SY8089 p.4]; SPICE 3.322 V, ripple 38 mV<50 mV |
| **Buck current margin** | 2 A cont / 3 A peak, θJA 170 °C/W [SY8089 p.1-2]; real 3.3 V load 0.8-1.2 A (backlight+audio are on +5 V) → 1.7-2.5× margin; Tj≈59 °C at load |
| **Decoupling** | verify_decoupling_adequacy 23/23 (ESP32 VDD bulk 0.10 µF is a logged as-built limitation, non-blocking) |
| **ESP32 straps ×4** | GPIO0=1 SPI-flash boot, GPIO45=0 VDD_SPI 3.3 V (PSRAM), GPIO46=0, GPIO3 don't-care [DS Table 4 p.13]; gate 11/11 |
| **PSRAM pins reserved** | board_config.h uses none of GPIO26-37 [DS note b p.12] |
| **Brownout/supply** | 3.327 V inside 3.0-3.6 V op range [DS §1.1 p.3] |
| **EN/reset** | R3 10k + C31 100nF (τ≈1 ms) + SW15 [DS Table 3/5]; gate PASS |
| **Charge current** | IP5306 1.8 A = 0.36C < cell 0.5C max limit [IP5306 p.8, BAT ds] |
| **Boost hold 5 V** | IP5306 2.4 A @5 V vs 1.5 A peak load = 63%; reflected cell 2.2 A << 5 A [IP5306 p.8] |
| **Battery protection** | verify_battery_protection = FULL (Q1 AO3401A RPP + IP5306 OVP/OCP + cell PCM) |
| **Display transfer** | ILI9488 8-bit @20 MHz (in-spec vs 25 MHz max); SNES region blit 5.7 ms of 16.67 ms budget = 2.7× headroom [DS1 §17.4.1] |
| **Signal integrity** | 20 MHz WR, short 4-layer traces (<80 mm) ≪ ~150 mm critical length |
| **Audio topology** | PAM8403 24 dB BTL filterless, C22 0.47 µF input, VREF/VDD decoupling present [PAM8403 p.1-4] |
| **USB ESD + CC role** | USBLC6 clamp 12 V@1 A, 3.5 pF; R1/R2 5.1k CC pulldowns = device role [USBLC6 ds, J1 ds] |
| **SD SPI wiring** | CS/MOSI/MISO/CLK wired; no external pull-ups → ESP32 internal (documented mitigation) |
| **Buttons** | 12 tact active-low + 10k pull-ups + 100 nF debounce; gate-covered |

### DEFER-TO-FIRST-ARTICLE (the bench checklist)

| # | Test | Pass criterion | Instrument |
|---|---|---|---|
| 1 | Buck U3 thermal, sustained max load | Tcase → Tj < 125 °C (Pdiss < 0.6 W) | IR / thermocouple |
| 2 | Q1 battery-path thermal, sustained max load + depleted (~3.4 V) cell | Q1 Tj < 125 °C; trace ΔT ≤ declared ceilings (BAT+ 60, BAT_IN 36, LX 50 °C) | IR + thermocouple |
| 3 | IP5306 KEY wake pulse (internal pull-up undocumented) | KEY low-pulse in 50 ms-2 s AND boost restarts 10/10 toggles | scope |
| 4 | **SNES measured FPS** (headline) | ≥55 fps sustained, non-coprocessor titles, adaptive frameskip ok | on-board FPS counter |
| 5 | Audio listen test | clean tone, no squeal/motorboating, U5 case <60 °C @5 min | ear + IR |
| 6 | SD enumerate + ROM read | CMD0/8/ACMD41 OK, mounts, ROM reads with correct size/CRC | FAT32 card |
| 7 | Buttons feel / no ghosting | each reads only its bit incl. combos, clean actuation | manual |
| 8 | Power-cycle / reset (optional) | EN crosses V_IH after +3V3≥3.0 V; boot log SPI_FAST_FLASH_BOOT + PSRAM 8 MB | USB console + scope |
| 9 | LED polarity on power-up | all LEDs light (R33-MED-2 _PENDING_VALIDATION closes here) | eye |
| 10 | Enclosure fit (once shell printed) | board seats, connectors/buttons align | printed shell |

## Tier 3 — accepted residual (factory/assembly defect)

Solder bridge, tombstone, wrong-part substitution, mis-registration,
laminate defect. **Not eliminable at design time.** Mitigations: JLC's own
DFM engineering review on the order, the `/jlcdfm-upload` pass (done), and
the first-article visual + electrical inspection on arrival.

## The one honest caveat — SNES full-speed

The single item that "readiness" cannot promise is that **SNES runs at full
speed** — but that is a **compute** limit of the ESP32-S3 CPU+PPU, **not a
board defect**. The board is proven capable of feeding the panel fast
enough (2.7× transfer headroom). Reference designs bound it: **NES is
solidly 60 fps; SNES is marginal** (Retro-Go "SNES slow", esp-box-emu "SNES
WIP"). The v2 audio-coprocessor + ASM-optimization plan targets exactly
this. Ordering v4.9.0 is correct regardless: the hardware is right, and
SNES performance is a firmware/silicon question resolved by measurement on
the first article, not by another board spin.

## Full 25-class catalog cross-check (v4.9.0) — 0 failures

Beyond the 5 domain analyses, v4.9.0 was run against every gate owning a
class in the skill's failure-class catalog (Step 1b). **All pass, 0
failures:**

| Class | Gate | Result |
|---|---|---|
| 15 Protection-FET body-diode | verify_rpp_polarity | PASS — cell on Q1 drain, load on source (the class that was blind for 4 releases is now correct) |
| 18 Reference-plane seam | verify_reference_plane | 0 failed, 15 warn (see below) |
| 19 Bus SI skew/via/crosstalk | verify_length_match / via_discontinuity / crosstalk | 0 failed (5+8+369 pass), warns below |
| 17 Pinch-point ampacity | verify_power_via_ampacity | PASS 15/15 |
| 12 Enclosure drift | verify_enclosure_sync | PASS 17/17 |
| ESD | verify_esd_protection | PASS |
| 22 Stencil / silk | verify_stencil_aperture / verify_silk_holes | PASS / 6 pass |
| 20 Component-body collision | verify_component_bodies | 4 pass, 0 fail |
| 21 Via-in-pad wicking | verify_via_in_pad | PASS (U2 lead-to-hole = same-net GND, benign) |

## Accepted warnings — reviewed one-by-one, none actionable

~38 WARN total across the SI/EMC/clearance gates. Reviewed individually;
**all are accepted-baseline, none is a defect or a submission blocker.**
They group as:

1. **Fast-signal heuristics firing on slow/DC nets** — most reference-plane
   seam-crossings and crosstalk pairs are BUTTON nets (BTN_*), read slowly:
   no fast edge, so seam-crossing / crosstalk is physically irrelevant. The
   gates flag geometry regardless of net speed.
2. **LCD parallel bus + SD SPI @20 MHz, inherent same-bus coupling, within
   margin** — crosstalk pairs all in the relaxed 1W–3W band (none < 1W);
   LCD_WR vs data skew 215 ps = 0.86% of the 20 MHz cycle (electrical limit
   210 mm vs 30 mm actual); SD already derated 40→20 MHz (R2-MED-5).
3. **Intended config / low-current stubs** — GPIO45 R14 DNP (the *desired*
   state; a populated R14 would kill the PSRAM), GND 0.2 mm netclass-min
   stubs, and the 4 same-net button-matrix copper-clearance WARN (0 DANGER).

### Two watch-items (not defects — remember, don't fix now)

- **Buck switching-node seam crossings** (LX / BUCK_LX / BUCK_FB cross the
  +5V/+3V3 plane seam): the only EMC-relevant warns — the noisiest node
  detours its return around the seam. Within the accepted band, short
  traces. *If radiated EMC ever becomes a concern, start here.*
- **LCD_D4 at 8 layer-excursion vias** (warn ceiling; fail is >8; LCD_D1–D3
  at 6): fine at 20 MHz, but a future regen adding one via to LCD_D4 would
  trip the gate to FAIL. *Watch on every regeneration.*

## Iteration loop status

Loop converged: tier-1 = 0, every tier-2 row is CLOSED or on the checklist,
no un-ledgered unknown remains. → **SUBMISSION-READY.** Next: `/first-article-check`
phase A on the JLCPCB 3D preview before payment, then order; run the bench
checklist above on the first article.
