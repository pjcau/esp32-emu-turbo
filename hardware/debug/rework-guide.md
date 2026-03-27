# Guida Rework — Riparazione Corto Circuito Power

## Il Problema

Due via di C19 toccano la traccia VBUS sul lato F.Cu (lato display/bottoni).
Questo crea un corto tra tutte le alimentazioni e GND su tutte e 5 le schede.

```
SITUAZIONE ATTUALE (vista dall'alto, lato F.Cu)

    La traccia VBUS orizzontale (rame, larghezza 0.5mm)
    passa SOPRA il via GND, toccando il suo anello di rame.

    La traccia VBUS verticale (rame, larghezza 0.5mm)
    passa A FIANCO del via +5V, toccando il suo anello di rame.

         traccia VBUS verticale
              (0.5mm largo)
                  ║
                  ║
                  ║
           ╔══════╬═══════════════  traccia VBUS orizzontale
           ║      ║                 (0.5mm largo)
           ║      ║
      GND ◉╝      ║
     via 1         ║
    TOCCA la    +5V◉╗
    traccia      via 2
    VBUS orizzontale  TOCCA la
                      traccia
                      VBUS verticale
```

---

## Attrezzi Necessari

- Cutter/bisturi di precisione (lama nuova e affilata)
- Lente di ingrandimento o lente da orologiaio
- Multimetro (modalita continuita/bip)
- Alcool isopropilico + cotton fioc (per pulire)
- Smalto trasparente o vernice UV (per proteggere dopo)

---

## Procedura Step-by-Step

### STEP 0 — Preparazione

- Scollega tutto (USB, batteria)
- Se il display e attaccato, rimuovi il cavo flat FPC
- Pulisci il lato F.Cu (lato bottoni) con alcool
- Il lavoro si fa TUTTO sul lato F.Cu (bottoni/display)

---

### STEP 1 — Trova i 2 via

Parti dal **foro di montaggio MH6** (foro grande 2.5mm, al centro-destra della scheda).

```
    Lato F.Cu (bottoni/display) — vista dall'alto

              ● MH6 (foro montaggio 2.5mm)
              │       ← LO VEDI, e un foro grande
              │
              │ scendi ~19mm
              │
              ◉ VIA 2 (+5V) — forellino piccolo 0.35mm
              │
              │ scendi altri ~4mm
              │
     ═════════◉══════════  VIA 1 (GND) — forellino piccolo 0.35mm
              │            QUI c'e la traccia VBUS orizzontale
              │            (pista di rame visibile)
```

I via sono **forellini piccoli** (0.35mm di diametro, anello di rame 0.9mm).
La traccia VBUS e una **pista di rame** larga 0.5mm visibile sul lato F.Cu.

---

### STEP 2 — Ripara VIA 1 (GND) — il piu importante

Questo via GND tocca la traccia VBUS orizzontale. E il corto principale.

```
PRIMA (zoom sul via GND):

    ══════════════════════  traccia VBUS (rame, 0.5mm)
    ──────────────────────  bordo inferiore traccia
    ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓  RAME CHE SI TOCCA (0.2mm)  ← PROBLEMA!
    ┌─────────────────────  bordo superiore anello via
    │         ◉           │ anello via GND (0.9mm)
    │         │           │
    └─────────────────────┘


COME GRATTARE:

    ══════════════════════  traccia VBUS (NON toccare!)
    ──────────────────────  bordo inferiore traccia

    ←←←←←←←←←←←←←←←←←←←←  GRATTA QUI con la lama
                              linea orizzontale, 2-3mm lunga
                              profondita: solo il rame (0.035mm)

    ┌─────────────────────  bordo superiore anello via
    │         ◉           │ anello via GND
    │         │           │
    └─────────────────────┘


DOPO (risultato corretto):

    ══════════════════════  traccia VBUS intatta ✓
    ──────────────────────
    ░░░░░░░░░░░░░░░░░░░░░░  gap di 0.3mm (vetronite verde visibile)
    ┌─────────────────────
    │         ◉           │ anello via GND intatto ✓
    │         │           │
    └─────────────────────┘
```

**Come fare:**
1. Appoggia la lama del cutter **piatta** sulla traccia VBUS (per protezione)
2. Inclina leggermente e gratta verso il BASSO, tra la traccia e il via
3. Fai 3-4 passate leggere — devi vedere la **vetronite verde** apparire
4. La striscia da grattare e lunga ~2-3mm e larga ~0.3mm
5. **NON** tagliare la traccia VBUS! **NON** tagliare l'anello del via!

**Verifica STEP 2:**
```
Multimetro in continuita:
  Puntale 1: sul foro del via GND
  Puntale 2: sulla traccia VBUS (la pista di rame sopra)

  Prima:  BIP (continuita) ← corto
  Dopo:   silenzio (aperto) ← OK! ✓
```

---

### STEP 3 — Ripara VIA 2 (+5V)

Questo via +5V tocca la traccia VBUS verticale. Stessa tecnica, direzione diversa.

```
PRIMA (zoom sul via +5V):

           ║                ┌──────────┐
           ║                │          │
    traccia║VBUS verticale  │    ◉     │ anello via +5V
           ║                │    │     │
           ║▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│          │
           ║  RAME CHE      └──────────┘
           ║  SI TOCCA
           ║  (0.2mm) ← PROBLEMA!


COME GRATTARE:

           ║         ↑      ┌──────────┐
           ║         ↑      │          │
    traccia║VBUS     ↑      │    ◉     │ anello via +5V
           ║    GRATTA QUI  │    │     │
           ║    con la lama │          │
           ║    linea       └──────────┘
           ║    verticale
           ║    2-3mm alta


DOPO (risultato corretto):

           ║                ┌──────────┐
           ║  ░░            │          │
    traccia║  ░░ gap 0.3mm  │    ◉     │ anello via +5V intatto ✓
           ║  ░░ (vetronite)│    │     │
           ║  ░░            │          │
           ║                └──────────┘
    traccia VBUS intatta ✓
```

**Come fare:**
1. Appoggia la lama **verticalmente** tra la traccia VBUS e il via
2. Gratta verso il BASSO con passate leggere
3. Devi vedere la **vetronite verde** apparire tra traccia e via
4. Striscia lunga ~2-3mm, larga ~0.3mm
5. **NON** tagliare la traccia VBUS! **NON** tagliare l'anello del via!

**Verifica STEP 3:**
```
Multimetro in continuita:
  Puntale 1: sul foro del via +5V
  Puntale 2: sulla traccia VBUS (la pista di rame a fianco)

  Prima:  BIP (continuita) ← corto
  Dopo:   silenzio (aperto) ← OK! ✓
```

---

### STEP 4 — Verifica Finale

Gira la scheda sul lato B.Cu (lato ESP32). Testa tutti e 6 i condensatori:

```
Multimetro in ohm (scala 200Ω o 2kΩ):
Tocca i 2 pad di ogni condensatore.

  C17  →  prima: ~0Ω   dopo: OL (aperto) ✓
  C1   →  prima: ~0Ω   dopo: OL (aperto) ✓
  C18  →  prima: ~0Ω   dopo: OL (aperto) ✓
  C19  →  prima: ~0Ω   dopo: OL (aperto) ✓
  C2   →  prima: ~0Ω   dopo: OL (aperto) ✓
  C3   →  prima: ~0Ω   dopo: OL (aperto) ✓
```

Se anche UN SOLO condensatore legge ancora ~0Ω:
- Controlla che il grattamento sia completo (guarda con la lente)
- Potrebbe esserci un ponte di stagno residuo — pulisci con alcool
- Rigratta se necessario

---

### STEP 5 — Test di Accensione

1. Collega USB-C a un alimentatore con **limite di corrente a 100mA**
2. Se la corrente sale subito a 100mA → c'e ancora un corto, SCOLLEGA
3. Se la corrente resta sotto 50mA → OK, procedi

```
Misure tensione (multimetro in V, puntale nero su GND):

  Punto          │ Atteso  │ Se sbagliato
  ───────────────┼─────────┼──────────────────
  C17 pad VBUS   │ ~5.0V   │ 0V = corto resta
  C1  pad +5V    │ ~5.0V   │ 0V = IP5306 guasto
  C2  pad +3V3   │ ~3.3V   │ 0V = AMS1117 guasto
  C18 pad BAT+   │ ~0V     │ (normale senza batteria)
```

---

### STEP 6 — Protezione

1. Pulisci l'area grattata con alcool isopropilico
2. Applica una goccia di **smalto trasparente per unghie** o vernice UV sulle 2 zone grattate
3. Questo previene ossidazione e ponti accidentali
4. Lascia asciugare 5 minuti
5. Riattacca il display

---

## Schema Riassuntivo

```
SEZIONE TRASVERSALE DEL PCB (4 strati)

PRIMA (cortocircuito):

  F.Cu  ═══VBUS═══●GND══   ← anello via tocca traccia = CORTO
  In1   ─────────GND─────   ← piano GND (via connesso qui ✓)
  In2   ─────────+5V─────   ← piano +5V
  B.Cu  ═══C19══pad══════   ← condensatore C19


DOPO (riparato):

  F.Cu  ═══VBUS══░●░GND░   ← gap grattato = APERTO ✓
  In1   ─────────GND─────   ← piano GND (via ANCORA connesso ✓)
  In2   ─────────+5V─────   ← piano +5V (via ANCORA connesso ✓)
  B.Cu  ═══C19══pad══════   ← condensatore C19 funziona ancora ✓

  ░ = rame rimosso (vetronite esposta)
  ● = foro via (barilotto metallico passa attraverso TUTTI i layer)
```

**Il via continua a funzionare** perche il barilotto metallico dentro il foro
collega comunque il pad di C19 ai piani interni (In1.Cu per GND, In2.Cu per +5V).
Grattare il rame sul lato F.Cu rompe SOLO il contatto indesiderato con VBUS.

---

## Tempo: ~10 minuti per scheda × 5 schede = ~50 minuti totali
