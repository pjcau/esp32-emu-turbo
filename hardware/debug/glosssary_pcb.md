# Glossario PCB — ESP32 Emu Turbo

Riferimento rapido ai termini usati nella documentazione di debug e rework della PCB v1.

---

## Struttura fisica di un PCB

Un PCB (Printed Circuit Board) è una scheda con strati di rame separati da materiale isolante (FR4, vetroresina). Il progetto ESP32 Emu Turbo usa una PCB a **4 layer**:

```
  ┌─────────────────────┐  ← F.Cu   (Front Copper — lato display/bottoni)
  ├─────────────────────┤  ← In1.Cu (Inner layer 1 — piano di massa GND)
  ├─────────────────────┤  ← In2.Cu (Inner layer 2 — piano alimentazione +5V)
  └─────────────────────┘  ← B.Cu   (Back Copper — lato componenti/batteria)
```

I layer interni `In1.Cu` e `In2.Cu` sono **piani pieni di rame** che coprono l'intera superficie del loro layer. Questo è il motivo per cui le via di GND e +5V continuano a funzionare anche dopo aver raschiato il rame su F.Cu o B.Cu: il "barile" della via attraversa la scheda e si connette al piano interno.

---

## Termini fondamentali

### Trace

Una **trace** è una striscia di rame che collega due punti elettrici sulla stessa faccia della scheda. È l'equivalente di un filo, ma stampato nel rame. Ha una larghezza definita (es. `w=0.5mm`) e appartiene a un layer specifico.

```
  ──────────────────────────  ← trace (filo di rame su un layer)
```

### Via

Una **via** è un forellino metallizzato che attraversa il PCB per collegare elettricamente due layer diversi. Fisicamente è un cilindro di rame che passa attraverso la scheda.

```
  F.Cu  ─────●─────          ← annular ring (corona di rame)
              │               ← barrel (cilindro di rame nel foro)
  B.Cu  ─────●─────
```

Una via ha tre misure importanti:

| Misura | Descrizione | Esempio |
|--------|-------------|---------|
| **drill** | Diametro del foro fisico | 0.35mm |
| **annular ring** | Corona di rame attorno al foro | raggio 0.45mm dal centro |
| **size** | Diametro totale della pastiglia (drill + 2× anular ring) | 0.9mm |

> **Bug rilevante:** il codice DFM originale usava il raggio del foro (0.175mm) invece del raggio del rame (0.45mm) per calcolare le collisioni — una differenza di 0.275mm che ha reso invisibili tutti gli overlap.

### Annular ring

È la **corona di rame** che circonda il foro di una via. Garantisce la connessione elettrica anche se la foratura non è perfettamente centrata.

```
         ┌──────────┐
         │  annular │  ← corona di rame
         │   ┌──┐   │
         │   │  │   │  ← foro (drill)
         │   └──┘   │
         └──────────┘

  raggio totale = raggio drill + larghezza annular ring
```

### Net

Una **net** è un nome logico assegnato a un insieme di punti che devono essere elettricamente connessi tra loro. È una definizione dello schematico, non una struttura fisica.

Esempi nel progetto:

| Net | Tensione / Funzione |
|-----|---------------------|
| `GND` | Massa, 0V |
| `VBUS` | 5V diretto da USB-C, prima dei regolatori |
| `+5V` | 5V regolato (uscita IP5306) |
| `+3V3` | 3.3V (uscita AMS1117) |
| `BAT+` | Tensione batteria LiPo |
| `LCD_RST` | Segnale reset del display |
| `LCD_DC` | Segnale data/command del display |
| `LCD_D0`–`LCD_D7` | Bus dati 8-bit del display |
| `BTN_UP/DOWN/LEFT/...` | Segnali dei bottoni |
| `SD_CS` | Chip select della SD card |
| `USB_D+` / `USB_D-` | Linee differenziali USB |

Quando si parla di **"via net GND"** si intende: una via che appartiene alla net GND, cioè fa parte del collegamento di massa.

---

## Net di potenza vs net di segnale

Distinzione fondamentale per capire i bug:

- **Net di potenza** — trasportano tensioni di alimentazione: `GND`, `VBUS`, `+5V`, `+3V3`, `BAT+`
- **Net di segnale** — trasportano informazioni logiche: `LCD_RST`, `BTN_UP`, `SD_CS`, `USB_D-`, ecc.

Un **bridge** (ponte) si verifica quando una trace di segnale tocca fisicamente due via di potenza diverse. Il rame della trace diventa un filo accidentale tra le due alimentazioni:

```
  via GND ──── rame LCD_RST ──── via VBUS
               (trace segnale)

  = GND cortocircuitato a VBUS attraverso il rame del segnale
```

---

## Clearance e overlap

**Clearance** è la distanza minima richiesta tra due elementi di rame appartenenti a net diverse. Per le PCB standard JLCPCB è tipicamente 0.1–0.2mm.

**Overlap** è quando quella distanza è negativa: i due pezzi di rame si toccano o si sovrappongono fisicamente, creando un cortocircuito.

```
  Clearance positiva (OK):        Overlap negativo (CORTO!):

  ────────  gap  [○]              ────────[███○───]
  (trace)       (via)             (trace sovrapposta alla via)
```

I valori di overlap nei bug del progetto (es. `−0.475mm`) indicano una sovrapposizione fisica massiccia, non un caso limite.

---

## Short circuit / cortocircuito

Un **short** (corto) è una connessione elettrica involontaria tra due net che dovrebbero essere isolate. Nel contesto del rework si distinguono due tipi:

| Tipo | Descrizione | Effetto |
|------|-------------|---------|
| **Power-to-power bridge** | Una trace di segnale collega due net di alimentazione diverse | Tutti i rail collassano a 0V — scheda non funzionante |
| **Signal-to-power short** | Una trace di segnale tocca una sola net di potenza | Il segnale è bloccato fisso a VCC o GND — funzione non operativa |

---

## Layer del PCB

| Nome KiCad | Lato fisico | Contenuto nel progetto |
|------------|-------------|------------------------|
| `F.Cu` | Fronte (lato display) | Trace VBUS, LCD_RST, alcune trace segnale |
| `B.Cu` | Retro (lato componenti) | Maggior parte dei segnali, bottoni, SD, USB |
| `In1.Cu` | Interno layer 1 | Piano pieno GND |
| `In2.Cu` | Interno layer 2 | Piano pieno +5V |
| `F.SilkS` | Fronte | Serigrafie (testo, contorni componenti) |
| `B.SilkS` | Retro | Serigrafie retro |
| `F.Mask` | Fronte | Maschera di saldatura (lacca verde/nera) |
| `B.Mask` | Retro | Maschera di saldatura retro |

---

## Componenti citati nel debug

| Ref | Tipo | Net+ | Net− | Funzione |
|-----|------|------|------|----------|
| C1 | Condensatore 0805 | +5V | GND | Decoupling +5V |
| C2 | Condensatore 1206 | +3V3 | GND | Decoupling +3V3 |
| C3 | Condensatore 0805 | +3V3 | GND | Decoupling +3V3 |
| C17 | Condensatore 0805 | VBUS | GND | Decoupling VBUS |
| C18 | Condensatore 0805 | BAT+ | GND | Decoupling batteria |
| C19 | Condensatore 1206 | +5V | GND | Decoupling +5V — **origine dei BUG #1 e #2** |
| U1 | ESP32-S3 | — | — | Microcontrollore principale |
| U2 | IP5306 | — | — | Gestore batteria LiPo + boost 5V |
| U3 | AMS1117 | +5V → +3V3 | GND | Regolatore lineare 3.3V |
| U4 | PAM8403 | — | — | Amplificatore audio |
| J1 | USB-C | VBUS, D+, D− | GND | Connettore USB |
| J4 | FPC/FFC | — | — | Connettore display LCD |

**Condensatori di decoupling:** condensatori di piccolo valore (100nF–10µF) posizionati vicino ai pin di alimentazione dei CI. Filtrano il rumore ad alta frequenza sul rail di tensione. Misurano normalmente >1MΩ tra i pad perché sono in parallelo all'alimentazione, non in serie.

---

## Strumenti e processi

### DFM — Design for Manufacturing

Test automatici che verificano che il PCB rispetti i vincoli produttivi: distanze minime tra rame, dimensioni fori, spaziature serigrafie. Nel progetto sono implementati in `verify_dfm_v2.py`.

### DFA — Design for Assembly

Test che verificano che i componenti possano essere assemblati correttamente: rotazioni, footprint corrispondenti al BOM, coordinate nel CPL. Implementati in `verify_dfa.py`.

### BOM — Bill of Materials

Lista di tutti i componenti con quantità, valore, package e codice LCSC (per ordine JLCPCB).

### CPL — Component Placement List

File con le coordinate XY e la rotazione di ogni componente, usato dalla macchina pick-and-place durante l'assemblaggio PCBA.

### PCBA — PCB Assembly

Servizio in cui il produttore (es. JLCPCB) fornisce sia la scheda che monta i componenti SMD. Si contrappone al solo PCB bare (scheda senza componenti).

### FPC / FFC

**FPC** (Flexible Printed Circuit) o **FFC** (Flat Flexible Cable): il nastro piatto e flessibile che collega il display LCD alla scheda. Nel progetto è il connettore `J4`. Quando nei fix si dice "il segnale arriva all'FPC via B.Cu" significa che il cavo del display riceve comunque il segnale dal layer posteriore, indipendentemente da tagli fatti su F.Cu.

### routing.py

Script Python del progetto che genera il file KiCad PCB (`.kicad_pcb`) in modo programmatico. Tutti i posizionamenti di componenti, trace e via sono definiti qui. I BUG #1 e #2 originano da offset di via calcolati in questo file senza verificare la clearance rispetto alle trace VBUS.

---

## Concetti di rework

### Rework

Intervento manuale su una PCB già prodotta e assemblata per correggere errori di design senza doverla rifare da zero.

### Raschiatura (scraping)

Tecnica con bisturi per rimuovere fisicamente uno strato sottile di rame da una trace o dall'annular ring di una via, creando un gap isolante dove prima c'era un overlap.

### Ponticello (jumper wire)

Filo conduttore saldato manualmente tra due punti della PCB per ripristinare una connessione interrotta durante il rework. Si usa filo AWG30 (detto anche kynar o wire-wrap wire) per la sua flessibilità e sezione ridotta.

### AWG30

Standard American Wire Gauge calibro 30: filo con diametro ~0.25mm, comunemente usato per ponticelli di rework su PCB per la sua maneggevolezza e resistenza adeguata per segnali logici.

---

*Glossario del progetto ESP32 Emu Turbo — aggiornato 2026-03-30*
