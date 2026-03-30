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
| Ferro da saldatura + filo stagno fine (0.3mm) | Bridge su fili di ripristino |
| Filo isolato sottile (AWG30 o kynar) | Ponticelli di ripristino funzionalità |
| Isopropanolo 99% + cotton fioc | Pulizia prima e dopo ogni intervento |
| Vernice UV o nail polish trasparente | Protezione finale delle zone raschiate |
| Alimentatore con limite di corrente (100mA / 5V) | Test di accensione sicuro |

---

## 2. Panoramica dei bug e priorità

Eseguire i fix **nell'ordine esatto** indicato. Ogni fix riduce il rischio per i passi successivi.

```
ORDINE OBBLIGATORIO:
  FIX 3  → CRITICO: elimina il principale VBUS↔GND rimasto
  FIX 4  → HIGH:    ripristina isolamento +3V3 (necessario per FIX 5-8)
  FIX 5-8→ HIGH:    eliminano i bridge +3V3↔GND su bottoni
  FIX 9-27→ MEDIUM: ripristinano segnali (LCD, SD, USB, bottoni)
  FIX 28-38→ OPT:   marginali, solo se hai problemi residui
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
5. Verificare con multimetro: continuità tra VBUS (pad+ di C17) e GND → deve essere **APERTA (>1MΩ)**.

### Preservazione funzionalità LCD_RST

LCD_RST raggiunge ancora il connettore FPC tramite il routing su **B.Cu** (lato destro della board).  
**Non serve ponticello.** Il segnale è integro dopo il taglio.

> ✅ Verifica finale: pin LCD_RST del ESP32 → continuità verso FPC J4 pin corrispondente (via B.Cu) = deve essere CONNESSO. Continuità verso VBUS = deve essere APERTA.

---

## 5. FIX 4 — USB_D- ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 | Via 2 | Overlap |
|-------|-------|-------|-------|---------|
| B.Cu | USB_D- verticale (91.7, 64.9)→(91.7, 37.5) w=0.2mm | +3V3 @ (92.05, 44.60) | GND @ (92.05, 52.00) | −0.200mm entrambe |

```
B.Cu — x=91.7mm

  y=44.60  ◉ via +3V3
           ║ USB_D-
           ║
  y=52.00  ◉ via GND

  Risultato: +3V3 ↔ USB_D- copper ↔ GND
```

### Procedura

1. Lavorare su **B.Cu** (lato componenti/sotto).
2. Individuare la trace USB_D- verticale a x≈91.7mm.
3. Tagliare la trace a **y=48** (punto equidistante tra le due via).
4. Raschiare ~1mm di rame con bisturi.
5. Verificare: continuità +3V3 → GND = **APERTA**.

### Impatto e ripristino

Tagliare qui interrompe il segnale USB_D- nel tratto tra y=44.6 e y=52. La funzione USB (flashing, seriale) sarà compromessa senza il ponticello.

**Per ripristinare USB_D-:** saldare un filo AWG30 isolato tra:
- Punto A: trace USB_D- a y=45.5, x=91.7 (sopra la via +3V3, lato ESP32)
- Punto B: trace USB_D- a y=51.0, x=91.7 (sotto la via +3V3, verso connettore USB-C)

Il filo deve passare **al di fuori** della zona delle via.

```
DOPO IL FIX + PONTICELLO:

  y=44.60  ◉ via +3V3
           ║ (segmento superiore intatto)
  y=45.5   ●─────────────────────── filo AWG30
           ╳ (taglio)
  y=51.0   ●─────────────────────── filo AWG30
           ║ (segmento inferiore intatto)
  y=52.00  ◉ via GND
```

---

## 6. FIX 5 — BTN_UP ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 | Via 2 | Overlap |
|-------|-------|-------|-------|---------|
| B.Cu | BTN_UP verticale (67.5, 62.0)→(67.5, 31.1) w=0.25mm | +3V3 @ (67.05, 44.60) | GND @ (67.05, 52.00) | −0.175mm entrambe |

### Procedura

1. Lavorare su **B.Cu**.
2. Tagliare BTN_UP a **y=48, x=67.5**.
3. Raschiare ~1mm.
4. Verificare: continuità +3V3 → GND = **APERTA**.

### Ripristino funzionalità bottone

Saldare filo AWG30 tra:
- Punto A: BTN_UP trace a y=45.5, x=67.5
- Punto B: BTN_UP trace a y=51.0, x=67.5

> ✅ Verifica: premendo BTN_UP → continuità tra i due pad del bottone = sì. Continuità +3V3→GND = APERTA.

---

## 7. FIX 6 — BTN_LEFT ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 | Via 2 | Overlap |
|-------|-------|-------|-------|---------|
| B.Cu | BTN_LEFT verticale (62.5, 64.4)→(62.5, 28.6) w=0.25mm | +3V3 @ (62.05, 44.60) | GND @ (62.05, 52.00) | −0.175mm entrambe |

### Procedura

1. Lavorare su **B.Cu**.
2. Tagliare BTN_LEFT a **y=48, x=62.5**.
3. Raschiare ~1mm.
4. Verificare: continuità +3V3 → GND = **APERTA**.

### Ripristino

Ponticello AWG30:
- Punto A: y=45.5, x=62.5
- Punto B: y=51.0, x=62.5

---

## 8. FIX 7 — BTN_A ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 | Via 2 | Overlap |
|-------|-------|-------|-------|---------|
| B.Cu | BTN_A verticale (52.5, 66.8)→(52.5, 23.5) w=0.25mm | +3V3 @ (52.05, 44.60) | GND @ (52.05, 52.00) | −0.175mm entrambe |

### Procedura

1. Lavorare su **B.Cu**.
2. Tagliare BTN_A a **y=48, x=52.5**.
3. Raschiare ~1mm.
4. Verificare: continuità +3V3 → GND = **APERTA**.

### Ripristino

Ponticello AWG30:
- Punto A: y=45.5, x=52.5
- Punto B: y=51.0, x=52.5

> ⚠️ Nota: BTN_A compare anche nel FIX 9-27 (violazione #18, short su F.Cu verso GND). Dopo questo fix, controllare anche quella violazione.

---

## 9. FIX 8 — BTN_L ponte +3V3↔GND (HIGH)

### Problema

| Layer | Trace | Via 1 | Via 2 | Overlap |
|-------|-------|-------|-------|---------|
| B.Cu | BTN_L verticale (72.5, 73.5)→(72.5, 37.5) w=0.25mm | +3V3 @ (72.05, 44.60) | GND @ (72.05, 52.00) | −0.125mm entrambe |
| B.Cu | BTN_L | GND extra | (73.05, 65.50) | −0.025mm |

### Procedura

1. Lavorare su **B.Cu**.
2. Tagliare BTN_L a **y=48, x=72.5** (elimina i due overlap principali).
3. Se il terzo overlap (−0.025mm a y=65.5) dà ancora continuità, raschiare anche lì.
4. Raschiare ~1mm sul taglio principale.
5. Verificare: continuità +3V3 → GND = **APERTA**.

### Ripristino

Ponticello AWG30:
- Punto A: y=45.5, x=72.5
- Punto B: y=51.0, x=72.5

---

## 10. FIX 9-27 — Short segnale→potenza (MEDIUM)

Queste violazioni non creano bridge di potenza ma bloccano il segnale (fisso a VCC o GND).  
Non compromettono la stabilità del power rail, ma impediscono il funzionamento di LCD, SD, bottoni, USB.

### Tecnica comune per ogni raschiatura

Per ogni voce: individuare la trace sul layer indicato, raschiare ~0.5mm di rame **nel punto esatto di overlap con la via indicata**. Non serve ponticello: la trace rimane connessa al resto del suo percorso, solo isolata dalla via estranea.

```
PRIMA (overlap):
  ════[VIA net A]════
         ║
  ───── trace net B ─────   ← copper si tocca

DOPO (isolata):
  ════[VIA net A]════
      ░░ gap ░░
  ───── trace net B ─────   ← 0.5mm di rame rimosso attorno alla via
```

### Tabella completa

| # | Layer | Segnale | Via estranea (net/pos) | Overlap | Effetto | Azione |
|---|-------|---------|------------------------|---------|---------|--------|
| 9 | F.Cu | BTN_Y | +3V3 @ (70.45, 44.00) | −0.475mm | BTN_Y fisso a +3V3 | Raschiare F.Cu intorno alla via +3V3 |
| 10 | F.Cu | USB_D+ | GND @ (85.05, 66.00) | −0.425mm | USB_D+ a GND | Raschiare F.Cu intorno alla via GND |
| 11 | F.Cu | LCD_DC | GND @ (109.05, 37.00) | −0.395mm | LCD_DC a GND | Raschiare F.Cu intorno alla via GND |
| 12 | F.Cu | BTN_DOWN | +3V3 @ (25.95, 63.00) | −0.375mm | BTN_DOWN a +3V3 | Raschiare F.Cu |
| 13 | F.Cu | BTN_DOWN | +3V3 @ (32.95, 63.00) | −0.375mm | BTN_DOWN a +3V3 (via 2) | Raschiare F.Cu — stesso segnale, via diversa |
| 14 | B.Cu | LCD_D0 | GND @ (134.50, 34.85) | −0.450mm | LCD_D0 a GND | Raschiare B.Cu intorno alla via GND |
| 15 | B.Cu | SD_CS | GND @ (153.50, 34.85) | −0.450mm | SD card non funziona | Raschiare B.Cu intorno alla via GND |
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
| 27 | B.Cu | LCD_D4 | VBUS @ (110.95, 33.00) | −0.000mm | LCD_D4 tocca VBUS | Raschiare B.Cu (overlap nullo ma reale) |

---

## 11. FIX 28-38 — Clearance marginale (opzionale)

Gap tra 0 e +0.025mm — possono manifestarsi o no a seconda della precisione di incisione JLCPCB.  
**Misurare prima di intervenire.** Se il multimetro dà continuità aperta → non toccare.

| # | Layer | Segnale | Via / net | Gap |
|---|-------|---------|-----------|-----|
| 28-32 | B.Cu | LCD_RD | GND vias @ x=133.45 (4 vias) | +0.025mm |
| 33 | B.Cu | LCD_RD | +3V3 @ (133.45, 26.25) | +0.025mm |
| 34-37 | B.Cu | LCD_RST | GND vias @ x=133.45 (4 vias) | +0.025mm |
| 38 | B.Cu | LCD_RST | +3V3 @ (133.45, 26.25) | +0.025mm |

Se continuità chiusa → raschiare come descritto in FIX 9-27.

---

## 12. Sequenza di test e verifica

### Step A — Dopo FIX 3

```
Test 1: VBUS ↔ GND  → C17 pad+ verso C17 pad-  → atteso: >1MΩ
Test 2: +5V  ↔ GND  → C1  pad+ verso C1  pad-  → atteso: >1MΩ
Test 3: BAT+ ↔ GND  → C18 pad+ verso C18 pad-  → atteso: >1MΩ
```

Se Test 1-3 passano → procedere con FIX 4-8.

### Step B — Dopo FIX 4-8

```
Test 4: +3V3 ↔ GND  → C2 pad+ verso C2 pad-   → atteso: >1MΩ
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
| BTN_UP/LEFT/A/L | connessi ai rispettivi pad (ponticello) | connesso |
| USB_D+/D- | isolati da GND/+3V3 | aperto |

---

## 13. Checklist di completamento

```
□ FIX 1  — BUG #1 (via GND su VBUS horiz) — FATTO
□ FIX 2  — BUG #2 (via +5V su VBUS vert)  — FATTO
□ Protezione vernice su FIX 1&2

□ FIX 3  — LCD_RST tagliata a x=95, y=33 (F.Cu)
□   └─ verifica VBUS↔GND = APERTA

□ FIX 4  — USB_D- tagliata a y=48, x=91.7 (B.Cu)
□   └─ ponticello AWG30 saldato (A: y=45.5 → B: y=51.0)
□   └─ verifica +3V3↔GND = APERTA

□ FIX 5  — BTN_UP tagliato a y=48, x=67.5 (B.Cu)
□   └─ ponticello AWG30 saldato

□ FIX 6  — BTN_LEFT tagliato a y=48, x=62.5 (B.Cu)
□   └─ ponticello AWG30 saldato

□ FIX 7  — BTN_A tagliato a y=48, x=52.5 (B.Cu)
□   └─ ponticello AWG30 saldato

□ FIX 8  — BTN_L tagliato a y=48, x=72.5 (B.Cu)
□   └─ ponticello AWG30 saldato

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

## 14. Note sul PCB v2

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

*Documento generato da analisi di `incident-power-short.md` e `all-shorts-rework.md` — PCB v1 commit `adc073b`*
