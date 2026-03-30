# PCB v1 — Guida Completa di Rework

**Versione PCB:** commit `adc073b` (2026-03-19)  
**Data analisi:** 2026-03-28  
**Violazioni totali:** 44 (3 critiche, 5 alte, 19 medie, 11 marginali)  
**Obiettivo:** ripristinare la funzionalità senza perdere nessun segnale

---

## Indice

1. [Attrezzatura necessaria](#1-attrezzatura-necessaria)
2. [Panoramica dei bug e priorità](#2-panoramica-dei-bug-e-priorità)
3. [FIX 1 & 2 — BUG #1 e #2: short VBUS (già eseguiti)](#3-fix-1--2--già-eseguiti)
4. [FIX 3 — BUG #3: LCD_RST ponte VBUS↔GND (CRITICO)](#4-fix-3--bug-3-lcd_rst-critico)
5. [FIX 4 — USB_D- ponte +3V3↔GND (HIGH)](#5-fix-4--usb_d-)
6. [FIX 5 — BTN_UP ponte +3V3↔GND (HIGH)](#6-fix-5--btn_up)
7. [FIX 6 — BTN_LEFT ponte +3V3↔GND (HIGH)](#7-fix-6--btn_left)
8. [FIX 7 — BTN_A ponte +3V3↔GND (HIGH)](#8-fix-7--btn_a)
9. [FIX 8 — BTN_L ponte +3V3↔GND (HIGH)](#9-fix-8--btn_l)
10. [FIX 9-27 — Short segnale→potenza (MEDIUM)](#10-fix-9-27--short-segnalepotenenza)
11. [FIX 28-38 — Clearance marginale (opzionale)](#11-fix-28-38--marginali)
12. [Sequenza di test e verifica](#12-sequenza-di-test-e-verifica)
13. [Checklist di completamento](#13-checklist-di-completamento)
14. [Note sul PCB v2](#14-note-sul-pcb-v2)

---

## 1. Attrezzatura necessaria

| Strumento | Uso |
|-----------|-----|
| Bisturi / X-Acto (lama #11) | Raschiare il rame su F.Cu e B.Cu |
| Lente d'ingrandimento 10× o lente binoculare | Individuare trace e via |
| Multimetro (modalità continuità + ohm) | Verificare ogni fix prima di procedere |
| Ferro da saldatura + filo stagno fine (0.3mm) | Saldare i ponticelli di ripristino |
| Filo isolato sottile (AWG30 o kynar) | Ponticelli di ripristino funzionalità |
| Isopropanolo 99% + cotton fioc | Pulizia prima e dopo ogni intervento |
| Vernice UV o nail polish trasparente | Protezione finale delle zone raschiate |
| Alimentatore con limite di corrente (100mA / 5V) | Test di accensione sicuro |

---

## 2. Panoramica dei bug e priorità

Eseguire i fix **nell'ordine esatto** indicato. Ogni fix riduce il rischio per i passi successivi.

```
ORDINE OBBLIGATORIO:
  FIX 3   → CRITICO: elimina il principale VBUS↔GND rimasto
  FIX 4-8 → HIGH:    eliminano i bridge +3V3↔GND su segnali
  FIX 9-27→ MEDIUM:  ripristinano segnali (LCD, SD, USB, bottoni)
  FIX 28-38→ OPT:    marginali, solo se ci sono problemi residui
```

Mappa visiva della board (160×75mm):

```
  ┌─────────────────────────────────────────────────────────────────┐
  │ [btn L]                                            [btn R]      │
  │                                                                 │
  │   [FPC J4]           [ESP32-S3 U1]          [PAM8403 U4]       │
  │    ||  ||           +--------------+          +--------+        │
  │    ||  ||      !C17 |              |          |        |        │
  │    ||  ||    (110,35)|   (80,27.5) |          |(30,30) |        │
  │                     |              |          +--------+        │
  │         U2 IP5306   +--------------+                            │
  │  !C1   (110,42.5)                                               │
  │ (122,49)                               !C3                      │
  │         ##L1##                       (69.5,42)                  │
  │ !C18  (110,52.5)                                                │
  │ (118,55)  U3 AMS1117                                            │
  │          (125,55.5)                                             │
  │ !C19                                                            │
  │ !C2    (110,58.5)                                               │
  │ (125,63)                                                        │
  │                                                                 │
  │ [btn] [SD]  [JST bat]  [USB-C]  [btn]  [switch]                │
  └─────────────────────────────────────────────────────────────────┘
  ! = condensatori che misuravano 0 ohm verso GND prima dei fix
```

---

## 3. FIX 1 & 2 — Già eseguiti

| Bug | Layer | Problema | Stato |
|-----|-------|----------|-------|
| BUG #1 | F.Cu | Via GND (108.5, 60.5) sovrapposta alla VBUS horiz. @ y=61 — overlap 0.20mm | ✅ RISOLTO |
| BUG #2 | F.Cu | Via +5V (111.5, 56.5) sovrapposta alla VBUS vert. @ x=111 — overlap 0.20mm | ✅ RISOLTO |

Questi due fix hanno eliminato il corto iniziale che teneva ogni rail a 0Ω verso GND.  
**Non rifare nulla in questa zona.** Applicare vernice protettiva sulle aree raschiate se non ancora fatto.

---

## 4. FIX 3 — BUG #3: LCD_RST ponte VBUS↔GND (CRITICO)

### Problema

La trace LCD_RST su F.Cu (y=33mm) è lunga 40mm e sovrappone **due via di potenza diverse**:

| Via | Net | Posizione | Overlap |
|-----|-----|-----------|---------|
| Via 1 | GND | (81.50, 32.96) | **−0.475mm** |
| Via 2 | VBUS | (110.95, 33.00) | **−0.515mm** |

Risultato: GND ← LCD_RST copper → VBUS = bridge diretto. I rail rimangono in corto anche dopo FIX 1&2.

### Dove tagliare

La trace corre orizzontalmente a y=33mm, circa 5mm sopra il bordo superiore del modulo ESP32.  
Tagliare **ovunque tra x=83 e x=110** (zona libera da entrambe le via).  
Punto consigliato: **x=95, y=33** (centro board, facile da raggiungere).

```
F.Cu — y=33mm (sotto area display)

  x=79.4                      x=95           x=110.95    x=119.6
  ════◉═══════════════════════╳══════════════════◉════════════════
      Via GND              TAGLIA QUI          Via VBUS
   (81.50, 32.96)          raschia ~1mm      (110.95, 33.00)

  PRIMA:  GND ──── rame LCD_RST ──── VBUS   (BRIDGE!)
  DOPO:   GND ────╳                  VBUS   (ISOLATI)
```

### Procedura

1. Rimuovere il pannello display (clip FPC).
2. Pulire F.Cu con isopropanolo.
3. Trovare la trace LCD_RST: filo sottile (w=0.2mm) orizzontale a y≈33mm, visibile con lente 10×.
4. Con bisturi, raschiare **~1mm di rame** centrato su x=95 (taglio verticale, perpendicolare alla trace).
5. Verificare con multimetro: VBUS (pad+ di C17) → GND = **APERTA (>1MΩ)**.

### Preservazione funzionalità LCD_RST

LCD_RST raggiunge ancora il connettore FPC tramite il routing su **B.Cu** (lato destro della board).  
**Non serve ponticello.** Il segnale è integro dopo il taglio.

> ✅ Verifica: pin LCD_RST ESP32 → FPC J4 = CONNESSO. LCD_RST → VBUS = APERTA.

---

## 5. FIX 4-8 — Tecnica comune: 4 tagli + ponticello

I FIX 4-8 affrontano tutti lo stesso schema: una trace di segnale verticale su B.Cu che attraversa **due via di potenza** (+3V3 e GND), creando un bridge +3V3↔GND attraverso il rame del segnale.

### Perché servono 4 tagli, non 1

Un singolo taglio tra le due via lascia il segnale attaccato a una delle due via. Ad esempio, tagliando a y=48 (punto mediano), il troncone superiore rimane connesso alla via +3V3 → il segnale è ancora fisso a +3V3, solo il bridge di potenza è risolto a metà.

La strategia corretta è **isolare completamente entrambe le via** dalla trace:

```
B.Cu — vista laterale (asse Y, la trace scorre verticale)

  [ESP32]
     │
     │  ← troncone ATTIVO (segnale verso ESP32)
     │
  ───A───  ← taglio A  (appena sopra annular ring via +3V3)
  ·······  ← annular ring via +3V3  } via +3V3
  ·· ● ··  ← centro via +3V3        } ISOLATA
  ·······  ← annular ring via +3V3  }
  ───B───  ← taglio B  (appena sotto annular ring via +3V3)
     │
     │  ← troncone MORTO (rame isolato — non collegato a niente)
     │
  ───C───  ← taglio C  (appena sopra annular ring via GND)
  ·······  ← annular ring via GND   } via GND
  ·· ● ··  ← centro via GND         } ISOLATA
  ·······  ← annular ring via GND   }
  ───D───  ← taglio D  (appena sotto annular ring via GND)
     │
     │  ← troncone ATTIVO (segnale verso connettore/bottone)
     │
  [connettore / pad bottone]

  Ponticello AWG30: salda dal troncone sopra A al troncone sotto D
  Il troncone morto tra B e C è rame galleggiante — non fa danno.
```

### Dimensioni di riferimento per i tagli

L'annular ring delle via misura raggio 0.45mm dal centro (size via = 0.9mm).  
Ogni taglio va posizionato a **~0.6mm dal centro della via** (fuori dall'annular ring, con margine).

| Taglio | Posizione rispetto al centro via |
|--------|----------------------------------|
| A | centro_via_3v3_y − 0.6mm |
| B | centro_via_3v3_y + 0.6mm |
| C | centro_via_gnd_y − 0.6mm |
| D | centro_via_gnd_y + 0.6mm |

### Tecnica di taglio

1. Con bisturi (lama #11), fare un taglio **perpendicolare alla trace** — la lama taglia trasversalmente il filo di rame.
2. Profondità: appena sufficiente a attraversare lo strato di rame (non serve incidere il substrato FR4).
3. Confermare con la punta del bisturi che il rame è reciso su tutta la larghezza della trace.
4. Pulire con isopropanolo.
5. **Verificare subito con multimetro** prima di procedere al taglio successivo.

### Ponticello AWG30

Dopo i 4 tagli, saldare un filo AWG30 isolato tra il troncone superiore (lato ESP32/sorgente segnale) e il troncone inferiore (lato destinazione). Il filo va **intorno** alla zona delle via — non sopra — per evitare contatti accidentali.

---

## 6. FIX 4 — USB_D- ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 (+3V3) | Via 2 (GND) | Overlap |
|-------|-------|--------------|-------------|---------|
| B.Cu | USB_D- verticale x=91.7mm, da y=64.9 a y=37.5, w=0.2mm | (92.05, 44.60) | (92.05, 52.00) | −0.200mm entrambe |

### Coordinate tagli

| Taglio | Posizione | Note |
|--------|-----------|------|
| A | x=91.7, y=44.0 | 0.6mm sopra centro via +3V3 @ y=44.6 |
| B | x=91.7, y=45.2 | 0.6mm sotto centro via +3V3 @ y=44.6 |
| C | x=91.7, y=51.4 | 0.6mm sopra centro via GND @ y=52.0 |
| D | x=91.7, y=52.6 | 0.6mm sotto centro via GND @ y=52.0 |

### Procedura

1. Lavorare su **B.Cu** (lato componenti).
2. Eseguire i tagli A, B, C, D nell'ordine.
3. Verificare dopo ogni coppia: A+B → via +3V3 isolata dalla trace. C+D → via GND isolata dalla trace.
4. Verificare continuità +3V3 → GND = **APERTA**.
5. Saldare ponticello AWG30: troncone superiore (y < 44.0) → troncone inferiore (y > 52.6).

> ✅ Risultato: +3V3 e GND isolate. USB_D⁻ segnale integro via ponticello.

---

## 7. FIX 5 — BTN_UP ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 (+3V3) | Via 2 (GND) | Overlap |
|-------|-------|--------------|-------------|---------|
| B.Cu | BTN_UP verticale x=67.5mm, da y=62.0 a y=31.1, w=0.25mm | (67.05, 44.60) | (67.05, 52.00) | −0.175mm entrambe |

### Coordinate tagli

| Taglio | Posizione |
|--------|-----------|
| A | x=67.5, y=44.0 |
| B | x=67.5, y=45.2 |
| C | x=67.5, y=51.4 |
| D | x=67.5, y=52.6 |

### Procedura

1. Lavorare su **B.Cu**.
2. Eseguire tagli A, B, C, D.
3. Verificare +3V3 → GND = **APERTA**.
4. Ponticello AWG30: troncone sopra A → troncone sotto D.

> ✅ Verifica funzionalità: premendo BTN_UP → continuità tra i pad del bottone = sì.

---

## 8. FIX 6 — BTN_LEFT ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 (+3V3) | Via 2 (GND) | Overlap |
|-------|-------|--------------|-------------|---------|
| B.Cu | BTN_LEFT verticale x=62.5mm, da y=64.4 a y=28.6, w=0.25mm | (62.05, 44.60) | (62.05, 52.00) | −0.175mm entrambe |

### Coordinate tagli

| Taglio | Posizione |
|--------|-----------|
| A | x=62.5, y=44.0 |
| B | x=62.5, y=45.2 |
| C | x=62.5, y=51.4 |
| D | x=62.5, y=52.6 |

### Procedura

1. Lavorare su **B.Cu**.
2. Eseguire tagli A, B, C, D.
3. Verificare +3V3 → GND = **APERTA**.
4. Ponticello AWG30: troncone sopra A → troncone sotto D.

---

## 9. FIX 7 — BTN_A ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 (+3V3) | Via 2 (GND) | Overlap |
|-------|-------|--------------|-------------|---------|
| B.Cu | BTN_A verticale x=52.5mm, da y=66.8 a y=23.5, w=0.25mm | (52.05, 44.60) | (52.05, 52.00) | −0.175mm entrambe |

### Coordinate tagli

| Taglio | Posizione |
|--------|-----------|
| A | x=52.5, y=44.0 |
| B | x=52.5, y=45.2 |
| C | x=52.5, y=51.4 |
| D | x=52.5, y=52.6 |

### Procedura

1. Lavorare su **B.Cu**.
2. Eseguire tagli A, B, C, D.
3. Verificare +3V3 → GND = **APERTA**.
4. Ponticello AWG30: troncone sopra A → troncone sotto D.

> ⚠️ BTN_A compare anche nella violazione #18 (F.Cu → GND). Dopo questo fix controllare anche quella.

---

## 10. FIX 8 — BTN_L ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 (+3V3) | Via 2 (GND) | Overlap |
|-------|-------|--------------|-------------|---------|
| B.Cu | BTN_L verticale x=72.5mm, da y=73.5 a y=37.5, w=0.25mm | (72.05, 44.60) | (72.05, 52.00) | −0.125mm entrambe |
| B.Cu | BTN_L | — | GND extra (73.05, 65.50) | −0.025mm |

### Coordinate tagli (overlap principali)

| Taglio | Posizione |
|--------|-----------|
| A | x=72.5, y=44.0 |
| B | x=72.5, y=45.2 |
| C | x=72.5, y=51.4 |
| D | x=72.5, y=52.6 |

### Procedura

1. Lavorare su **B.Cu**.
2. Eseguire tagli A, B, C, D.
3. Verificare +3V3 → GND = **APERTA**.
4. Se la via GND extra a (73.05, 65.50) dà ancora continuità, raschiare ~0.5mm di rame intorno a quella via sulla trace BTN_L.
5. Ponticello AWG30: troncone sopra A → troncone sotto D.

---

## 11. FIX 9-27 — Short segnale→potenza (MEDIUM)

Queste violazioni non creano bridge di potenza ma bloccano il segnale (fisso a VCC o GND). Non compromettono la stabilità del power rail, ma impediscono il funzionamento di LCD, SD, bottoni, USB.

### Tecnica: raschiatura singola

A differenza dei FIX 4-8, qui la trace tocca **una sola via estranea** — non forma un bridge tra due net di potenza. Basta isolare il punto di contatto senza recidere la trace: raschiare ~0.5mm di rame **attorno all'annular ring** della via estranea, sul lato in cui la trace si avvicina.

```
PRIMA (overlap):               DOPO (isolata):

  ════[VIA net A]════            ════[VIA net A]════
         ║                           ░░ gap ░░
  ─── trace net B ───          ─── trace net B ───

  La trace tocca la via.       0.5mm di rame rimosso.
                               La trace rimane connessa
                               al suo percorso originale.
```

Non serve ponticello: la trace continua a portare il segnale, semplicemente senza essere cortocircuitata alla via di potenza.

### Tabella completa

| # | Layer | Segnale | Via estranea (net / posizione) | Overlap | Effetto se non risolto | Azione |
|---|-------|---------|-------------------------------|---------|----------------------|--------|
| 9 | F.Cu | BTN_Y | +3V3 @ (70.45, 44.00) | −0.475mm | BTN_Y fisso a +3V3 | Raschiare F.Cu attorno alla via |
| 10 | F.Cu | USB_D+ | GND @ (85.05, 66.00) | −0.425mm | USB_D+ a GND | Raschiare F.Cu attorno alla via |
| 11 | F.Cu | LCD_DC | GND @ (109.05, 37.00) | −0.395mm | LCD_DC a GND | Raschiare F.Cu attorno alla via |
| 12 | F.Cu | BTN_DOWN | +3V3 @ (25.95, 63.00) | −0.375mm | BTN_DOWN a +3V3 | Raschiare F.Cu |
| 13 | F.Cu | BTN_DOWN | +3V3 @ (32.95, 63.00) | −0.375mm | BTN_DOWN a +3V3 (via 2) | Raschiare F.Cu — stesso segnale, via diversa |
| 14 | B.Cu | LCD_D0 | GND @ (134.50, 34.85) | −0.450mm | LCD_D0 a GND | Raschiare B.Cu attorno alla via |
| 15 | B.Cu | SD_CS | GND @ (153.50, 34.85) | −0.450mm | SD card non funziona | Raschiare B.Cu attorno alla via |
| 16 | B.Cu | LCD_D5 | GND @ (134.50, 34.85) | −0.350mm | LCD_D5 a GND | Raschiare B.Cu |
| 17 | B.Cu | BTN_B | GND @ (143.00, 50.25) | −0.275mm | BTN_B a GND | Raschiare B.Cu |
| 18 | F.Cu | BTN_A | GND @ (76.80, 67.12) | −0.250mm | BTN_A anche a GND su F.Cu | Raschiare F.Cu (vedi anche FIX 7) |
| 19 | B.Cu | LCD_D7 | GND @ (81.50, 32.96) | −0.145mm | LCD_D7 a GND | Raschiare B.Cu |
| 20 | F.Cu | BTN_SELECT | +3V3 @ (62.05, 44.60) | −0.075mm | BTN_SELECT a +3V3 | Raschiare F.Cu |
| 21 | F.Cu | BTN_SELECT | +3V3 @ (67.05, 44.60) | −0.075mm | BTN_SELECT a +3V3 (via 2) | Raschiare F.Cu |
| 22 | F.Cu | BTN_SELECT | +3V3 @ (72.05, 44.60) | −0.075mm | BTN_SELECT a +3V3 (via 3) | Raschiare F.Cu |
| 23 | F.Cu | BTN_R | GND @ (123.50, 64.50) | −0.075mm | BTN_R a GND | Raschiare F.Cu |
| 24 | B.Cu | BTN_SELECT | +3V3 @ (72.05, 44.60) | −0.075mm | BTN_SELECT (seg. B.Cu) | Raschiare B.Cu |
| 25 | B.Cu | LCD_D4 | GND @ (134.50, 34.85) | −0.050mm | LCD_D4 a GND | Raschiare B.Cu |
| 26 | F.Cu | LCD_D6 | +3V3 @ (88.75, 21.01) | −0.040mm | LCD_D6 a +3V3 | Raschiare F.Cu |
| 27 | B.Cu | LCD_D4 | VBUS @ (110.95, 33.00) | −0.000mm | LCD_D4 tocca VBUS | Raschiare B.Cu |

---

## 12. FIX 28-38 — Clearance marginale (opzionale)

Gap tra 0 e +0.025mm — possono manifestarsi o no a seconda della precisione di incisione JLCPCB.  
**Misurare prima di intervenire.** Se il multimetro legge continuità aperta → non toccare nulla.

| # | Layer | Segnale | Via / net | Gap |
|---|-------|---------|-----------|-----|
| 28-32 | B.Cu | LCD_RD | GND vias @ x=133.45 (4 vias) | +0.025mm |
| 33 | B.Cu | LCD_RD | +3V3 @ (133.45, 26.25) | +0.025mm |
| 34-37 | B.Cu | LCD_RST | GND vias @ x=133.45 (4 vias) | +0.025mm |
| 38 | B.Cu | LCD_RST | +3V3 @ (133.45, 26.25) | +0.025mm |

Se continuità chiusa → raschiare come descritto in FIX 9-27.

---

## 13. Sequenza di test e verifica

### Step A — Dopo FIX 3

```
Test 1: VBUS ↔ GND  →  C17 pad+ verso C17 pad-  →  atteso: >1MΩ
Test 2: +5V  ↔ GND  →  C1  pad+ verso C1  pad-  →  atteso: >1MΩ
Test 3: BAT+ ↔ GND  →  C18 pad+ verso C18 pad-  →  atteso: >1MΩ
```

Se Test 1-3 passano → procedere con FIX 4-8.

### Step B — Dopo FIX 4-8

```
Test 4: +3V3 ↔ GND  →  C2 pad+ verso C2 pad-  →  atteso: >1MΩ
```

Se passa → procedere al test di accensione.

### Step C — Test di accensione

⚠️ Usare **alimentatore con limite di corrente** impostato a **100mA / 5V**.

1. Collegare USB-C.
2. Corrente attesa a riposo: **< 50mA** (senza batteria).
3. Se la corrente va immediatamente al limite → short residuo. **Non continuare.** Ricontrollare tutti i fix.

### Step D — Misura tensioni

| Punto di test | Atteso |
|---------------|--------|
| VBUS (C17 pad+) | 5.0V |
| +5V  (C1  pad+) | 4.8–5.2V |
| +3V3 (C2  pad+) | 3.3V |
| BAT+ (C18 pad+) | 0V (senza batteria) |

### Step E — Test segnali (dopo FIX 9-27)

| Segnale | Test | Atteso |
|---------|------|--------|
| LCD_RST | continuità ESP32 → FPC J4 | connesso |
| LCD_DC | continuità ESP32 → FPC J4 | connesso |
| LCD_D0–D7 | ognuno isolato da GND e +3V3 | aperto |
| SD_CS | isolato da GND | aperto |
| BTN_UP/LEFT/A/L | connessi ai rispettivi pad (via ponticello) | connesso |
| USB_D+/D- | isolati da GND/+3V3 | aperto |

---

## 14. Checklist di completamento

```
□ FIX 1  — BUG #1 (via GND su VBUS horiz) — FATTO
□ FIX 2  — BUG #2 (via +5V su VBUS vert)  — FATTO
□ Protezione vernice su FIX 1&2

□ FIX 3  — LCD_RST tagliata a x=95, y=33 (F.Cu)
□   └─ verifica VBUS↔GND = APERTA

□ FIX 4  — USB_D- (B.Cu, x=91.7)
□   └─ taglio A: y=44.0  taglio B: y=45.2
□   └─ taglio C: y=51.4  taglio D: y=52.6
□   └─ ponticello AWG30: sopra A → sotto D
□   └─ verifica +3V3↔GND = APERTA

□ FIX 5  — BTN_UP (B.Cu, x=67.5)
□   └─ taglio A: y=44.0  taglio B: y=45.2
□   └─ taglio C: y=51.4  taglio D: y=52.6
□   └─ ponticello AWG30: sopra A → sotto D

□ FIX 6  — BTN_LEFT (B.Cu, x=62.5)
□   └─ taglio A: y=44.0  taglio B: y=45.2
□   └─ taglio C: y=51.4  taglio D: y=52.6
□   └─ ponticello AWG30: sopra A → sotto D

□ FIX 7  — BTN_A (B.Cu, x=52.5)
□   └─ taglio A: y=44.0  taglio B: y=45.2
□   └─ taglio C: y=51.4  taglio D: y=52.6
□   └─ ponticello AWG30: sopra A → sotto D

□ FIX 8  — BTN_L (B.Cu, x=72.5)
□   └─ taglio A: y=44.0  taglio B: y=45.2
□   └─ taglio C: y=51.4  taglio D: y=52.6
□   └─ ponticello AWG30: sopra A → sotto D
□   └─ via GND extra (73.05, 65.50): raschiare se dà continuità

□ FIX 9-27 — Short segnale→potenza (raschiature individuali)
□   □ #9  BTN_Y    @ F.Cu (70.45, 44.00)
□   □ #10 USB_D+   @ F.Cu (85.05, 66.00)
□   □ #11 LCD_DC   @ F.Cu (109.05, 37.00)
□   □ #12 BTN_DOWN @ F.Cu (25.95, 63.00)
□   □ #13 BTN_DOWN @ F.Cu (32.95, 63.00)
□   □ #14 LCD_D0   @ B.Cu (134.50, 34.85)
□   □ #15 SD_CS    @ B.Cu (153.50, 34.85)
□   □ #16 LCD_D5   @ B.Cu (134.50, 34.85)
□   □ #17 BTN_B    @ B.Cu (143.00, 50.25)
□   □ #18 BTN_A    @ F.Cu (76.80, 67.12)
□   □ #19 LCD_D7   @ B.Cu (81.50, 32.96)
□   □ #20 BTN_SELECT @ F.Cu (62.05, 44.60)
□   □ #21 BTN_SELECT @ F.Cu (67.05, 44.60)
□   □ #22 BTN_SELECT @ F.Cu (72.05, 44.60)
□   □ #23 BTN_R    @ F.Cu (123.50, 64.50)
□   □ #24 BTN_SELECT @ B.Cu (72.05, 44.60)
□   □ #25 LCD_D4   @ B.Cu (134.50, 34.85)
□   □ #26 LCD_D6   @ F.Cu (88.75, 21.01)
□   □ #27 LCD_D4   @ B.Cu (110.95, 33.00)

□ FIX 28-38 — misurati, intervenuti solo se continuità chiusa

□ Vernice protettiva su tutte le aree raschiate
□ Test A: VBUS/+5V/BAT+ → GND = >1MΩ
□ Test B: +3V3 → GND = >1MΩ
□ Test C: accensione con limite 100mA — corrente < 50mA
□ Test D: tensioni corrette su tutti i rail
□ Test E: segnali LCD, SD, bottoni verificati
□ FPC display ricollegato
□ Test finale con display e SD card
```

**Tempo stimato rework completo per 1 board: 2-3 ore**  
(FIX 3-8 ~45min, FIX 9-27 ~60min, test e verifica ~30min)

---

## 15. Note sul PCB v2

Questo rework permette di **validare il circuito** e testare il firmware sulla PCB v1.  
Con 44 violazioni di routing, la board v1 non è adatta alla produzione.

Il file `routing.py` è stato aggiornato con le correzioni di BUG #1 e #2. Quattro nuovi test DFM sono stati aggiunti a `verify_dfm_v2.py` per prevenire recidive:

| Test | Cosa controlla |
|------|----------------|
| `test_via_annular_ring_trace_clearance` | Rame della via (non solo il foro) che overlappa trace |
| `test_signal_power_via_overlap` | Trace di segnale che tocca qualsiasi via di potenza |
| `test_trace_crossing_same_layer` | Trace perpendicolari che si incrociano sullo stesso layer |
| `test_power_bridge_detection` | Trace di segnale che ponte due net di potenza diversi |

Il PCB v2 generato da `routing.py` corretto supera tutti gli 88 test DFM e 9 DFA.

---

*Documento aggiornato — PCB v1 commit `adc073b` — tecnica 4 tagli per FIX 4-8*
