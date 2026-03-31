---
id: rework-v29-visual
title: PCB v2.9 — Visual Rework Guide
sidebar_position: 13
---

# PCB v2.9 — Visual Rework Guide

Complete visual guide for all 27 routing violations found on the production PCB v2.9 (tag `v2.9`, commit `adc073b`). Each fix includes an annotated PCB render showing the exact location, the problem, and the rework procedure.

**Source:** [`hardware/debug/all-shorts-rework.md`](https://github.com/pjcau/esp32-emu-turbo/blob/main/hardware/debug/all-shorts-rework.md)

**Tools needed:** soldering iron (fine tip), flux, 30AWG kynar wire, coltellino di precisione, multimetro, lente/microscopio.

---

## Summary

| Severity | Count | Description | Fixes |
|----------|-------|-------------|-------|
| **CRITICAL** | 3 | Power-to-power bridge (GND↔VBUS, GND↔+5V) | FIX 1-3 |
| **HIGH** | 5 | Signal bridges two power nets (+3V3↔GND) | FIX 4-8 |
| **MEDIUM-HIGH** | 19 | Signal touches one power net | FIX 9-27 |

**Priorità di rework:** Eseguire i fix in ordine numerico. Testare con multimetro dopo ogni fix.

---

## FIX 1-3: Power Shorts (CRITICAL)

Questi cortocircuiti impediscono l'accensione della board. **Lato FRONTE (F.Cu, display).**

### FIX 1 — VBUS → GND via

![FIX 1](/img/renders/v29-fix1.png)

| | Dettaglio |
|---|---|
| **Layer** | F.Cu (fronte) |
| **Trace** | VBUS orizzontale (y=61, w=0.5mm) |
| **Via** | GND @ (108.5, 60.5) ø0.9mm |
| **Gap** | -0.20mm |
| **Effetto** | VBUS cortocircuito a GND → board non si accende |
| **Intervento** | Raschiare F.Cu intorno alla via GND (~1mm raggio) |
| **Verifica** | Multimetro: VBUS↔GND = aperto (>1MΩ) |

### FIX 2 — VBUS → +5V via

![FIX 2](/img/renders/v29-fix2.png)

| | Dettaglio |
|---|---|
| **Layer** | F.Cu (fronte) |
| **Trace** | VBUS verticale (x=111, w=0.5mm) |
| **Via** | +5V @ (111.5, 56.5) ø0.9mm |
| **Gap** | -0.20mm |
| **Effetto** | VBUS cortocircuito a +5V |
| **Intervento** | Raschiare F.Cu intorno alla via +5V (~1mm raggio) |
| **Verifica** | Multimetro: VBUS↔+5V = aperto (>1MΩ) |

### FIX 3 — LCD_RST ponte VBUS↔GND

![FIX 3](/img/renders/v29-fix3.png)

| | Dettaglio |
|---|---|
| **Layer** | F.Cu (fronte) |
| **Trace** | LCD_RST orizzontale (y=33, w=0.2mm) |
| **Via 1** | GND @ (81.5, 33) — gap: -0.47mm |
| **Via 2** | VBUS @ (111, 33) — gap: -0.52mm |
| **Effetto** | Ponte diretto GND↔VBUS attraverso rame LCD_RST |
| **Intervento** | Tagliare trace LCD_RST a x=95, y=33. Raschiare ~1mm. LCD_RST funziona via B.Cu. |
| **Verifica** | Multimetro: VBUS↔GND = aperto (>1MΩ) |

---

## FIX 4-8: Signal Bridges +3V3↔GND (HIGH)

Trace verticali B.Cu che attraversano sia una via +3V3 sia una via GND, creando ponti power-to-power. **Lato RETRO (B.Cu, componenti). 4 tagli per ogni fix.**

### FIX 4 — USB_D- ponte +3V3↔GND

![FIX 4](/img/renders/v29-fix4.png)

| | Dettaglio |
|---|---|
| **Layer** | B.Cu (retro) |
| **Trace** | USB_D- verticale (x=91.7, w=0.2mm) |
| **Via 1** | +3V3 @ (92.05, 44.6) — gap: -0.20mm |
| **Via 2** | GND @ (92.05, 52.0) — gap: -0.20mm |
| **Effetto** | Ponte +3V3↔GND via rame USB_D- |
| **Intervento** | 4 tagli con coltellino: sopra/sotto ogni via. ⚠ USB nativo non funzionerà. |
| **Verifica** | Multimetro: +3V3↔GND = aperto (>1MΩ) |

### FIX 5 — BTN_UP ponte +3V3↔GND

![FIX 5](/img/renders/v29-fix5.png)

| | Dettaglio |
|---|---|
| **Layer** | B.Cu (retro) |
| **Trace** | BTN_UP verticale (x=67.5, w=0.25mm) |
| **Via 1** | +3V3 @ (67.05, 44.6) — gap: -0.18mm |
| **Via 2** | GND @ (67.05, 52.0) — gap: -0.18mm |
| **Intervento** | 4 tagli + ponte filo 30AWG da y=43 a y=54 |
| **Verifica** | +3V3↔GND = aperto |

### FIX 6 — BTN_LEFT ponte +3V3↔GND

![FIX 6](/img/renders/v29-fix6.png)

| | Dettaglio |
|---|---|
| **Layer** | B.Cu (retro) |
| **Trace** | BTN_LEFT verticale (x=62.5, w=0.25mm) |
| **Via 1** | +3V3 @ (62.05, 44.6) — gap: -0.18mm |
| **Via 2** | GND @ (62.05, 52.0) — gap: -0.18mm |
| **Intervento** | 4 tagli + ponte filo 30AWG |
| **Verifica** | +3V3↔GND = aperto |

### FIX 7 — BTN_A ponte +3V3↔GND

![FIX 7](/img/renders/v29-fix7.png)

| | Dettaglio |
|---|---|
| **Layer** | B.Cu (retro) |
| **Trace** | BTN_A verticale (x=52.5, w=0.25mm) |
| **Via 1** | +3V3 @ (52.05, 44.6) — gap: -0.18mm |
| **Via 2** | GND @ (52.05, 52.0) — gap: -0.18mm |
| **Intervento** | 4 tagli + ponte filo 30AWG |
| **Verifica** | +3V3↔GND = aperto |

### FIX 8 — BTN_L ponte +3V3↔GND

![FIX 8](/img/renders/v29-fix8.png)

| | Dettaglio |
|---|---|
| **Layer** | B.Cu (retro) |
| **Trace** | BTN_L verticale (x=72.5, w=0.25mm) |
| **Via 1** | +3V3 @ (72.05, 44.6) — gap: -0.13mm |
| **Via 2** | GND @ (72.05, 52.0) — gap: -0.13mm |
| **Via 3** | GND @ (73.05, 65.5) — gap: -0.03mm |
| **Intervento** | 4 tagli sulle 2 via principali + ponte filo 30AWG |
| **Verifica** | +3V3↔GND = aperto |

---

## FIX 9-27: Single-Net Shorts (MEDIUM)

Signal trace che tocca UNA sola via power. Non crea ponte power-power ma blocca il segnale al livello della power net. **Intervento: raschiare rame intorno alla via (~1mm raggio).**

### FIX 9 — BTN_Y → +3V3 (F.Cu)

![FIX 9](/img/renders/v29-fix9.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| BTN_Y | +3V3 @ (70.45, 44.0) | -0.475mm | BTN_Y bloccato HIGH | Raschiare F.Cu intorno via |

### FIX 10 — USB_D+ → GND (F.Cu)

![FIX 10](/img/renders/v29-fix10.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| USB_D+ | GND @ (85.05, 66.0) | -0.425mm | USB_D+ cortocircuito a GND | Raschiare F.Cu intorno via |

### FIX 11 — LCD_DC → GND (F.Cu)

![FIX 11](/img/renders/v29-fix11.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| LCD_DC | GND @ (109.05, 37.0) | -0.395mm | Display non funziona | Raschiare F.Cu intorno via |

### FIX 12-13 — BTN_DOWN → +3V3 (F.Cu, 2 punti)

![FIX 12](/img/renders/v29-fix12.png)
![FIX 13](/img/renders/v29-fix13.png)

| # | Via | Gap | Fix |
|---|-----|-----|-----|
| 12 | +3V3 @ (25.95, 63.0) | -0.375mm | Raschiare F.Cu |
| 13 | +3V3 @ (32.95, 63.0) | -0.375mm | Raschiare F.Cu |

### FIX 14, 16, 25 — LCD_D0/D5/D4 → GND (B.Cu, stessa via)

![FIX 14](/img/renders/v29-fix14.png)

| # | Signal | Via | Gap |
|---|--------|-----|-----|
| 14 | LCD_D0 | GND @ (134.5, 34.85) | -0.450mm |
| 16 | LCD_D5 | GND @ (134.5, 34.85) | -0.350mm |
| 25 | LCD_D4 | GND @ (134.5, 34.85) | -0.050mm |

**Intervento unico:** raschiare B.Cu intorno a GND via @ (134.5, 34.85) risolve tutti e 3.

### FIX 15 — SD_CS → GND (B.Cu)

![FIX 15](/img/renders/v29-fix15.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| SD_CS | GND @ (153.5, 34.85) | -0.450mm | SD card inaccessibile | Raschiare B.Cu intorno via |

### FIX 17 — BTN_B → GND (B.Cu)

![FIX 17](/img/renders/v29-fix17.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| BTN_B | GND @ (143.0, 50.25) | -0.275mm | BTN_B bloccato LOW | Raschiare B.Cu intorno via |

### FIX 18 — BTN_A → GND (F.Cu)

![FIX 18](/img/renders/v29-fix18.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| BTN_A | GND @ (76.8, 67.12) | -0.250mm | BTN_A cortocircuito a GND | Raschiare F.Cu intorno via |

### FIX 19 — LCD_D7 → GND (B.Cu)

![FIX 19](/img/renders/v29-fix19.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| LCD_D7 | GND @ (81.5, 32.96) | -0.145mm | Display corrotto | Raschiare B.Cu intorno via |

### FIX 20-22, 24 — BTN_SELECT → +3V3 (F.Cu + B.Cu, 4 punti)

![FIX 20](/img/renders/v29-fix20.png)
![FIX 21](/img/renders/v29-fix21.png)
![FIX 22](/img/renders/v29-fix22.png)
![FIX 24](/img/renders/v29-fix24.png)

| # | Layer | Via | Gap |
|---|-------|-----|-----|
| 20 | F.Cu | +3V3 @ (62.05, 44.6) | -0.075mm |
| 21 | F.Cu | +3V3 @ (67.05, 44.6) | -0.075mm |
| 22 | F.Cu | +3V3 @ (72.05, 44.6) | -0.075mm |
| 24 | B.Cu | +3V3 @ (72.05, 44.6) | -0.075mm |

**Nota:** gap -0.075mm — potrebbe non manifestarsi su tutti i PCB prodotti.

### FIX 23 — BTN_R → GND (F.Cu)

![FIX 23](/img/renders/v29-fix23.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| BTN_R | GND @ (123.5, 64.5) | -0.075mm | BTN_R bloccato LOW | Raschiare F.Cu intorno via |

### FIX 26 — LCD_D6 → +3V3 (F.Cu)

![FIX 26](/img/renders/v29-fix26.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| LCD_D6 | +3V3 @ (88.75, 21.01) | -0.040mm | Display corrotto | Raschiare F.Cu intorno via |

### FIX 27 — LCD_D4 → VBUS (B.Cu)

![FIX 27](/img/renders/v29-fix27.png)

| Trace | Via | Gap | Effetto | Fix |
|-------|-----|-----|---------|-----|
| LCD_D4 | VBUS @ (110.95, 33.0) | -0.000mm | LCD_D4 borderline | Raschiare B.Cu intorno via (preventivo) |

---

## Checklist Post-Rework

Dopo tutti i fix, verificare con multimetro in modalità continuità:

| Test | Pad 1 | Pad 2 | Atteso | Dopo FIX |
|------|-------|-------|--------|----------|
| VBUS-GND | C17+ | C17- | >1MΩ | FIX 1, 3 |
| +5V-GND | C1+ | C1- | >1MΩ | FIX 2, 3 |
| +3V3-GND | C2+ | C2- | >1MΩ | FIX 4-8 |
| BAT+-GND | C18+ | C18- | >1MΩ | FIX 3 |

---

## Assessment

Questa board v2.9 ha **44 violazioni routing** di cui 27 sono reali short circuit. La versione corrente del PCB (post-v2.9) ha risolto **tutte** queste violazioni nel generatore Python — DFM: 114/114 pass, 0 collisioni.

Per le board v2.9 già prodotte, i fix 1-3 sono essenziali. I fix 4-8 ripristinano i power rail. I fix 9-27 sono necessari per funzionalità completa (display, bottoni, SD card).
