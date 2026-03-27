# Power Short Circuit Analysis — ESP32 Emu Turbo PCB v1

**Date:** 2026-03-26
**Issue:** All 6 power decoupling capacitors show 0 ohm (short to GND)
**Affected boards:** 5/5 (100%) — confirms DESIGN BUG, not component failure

---

## 1. Symptoms

Six capacitors on the bottom layer (B.Cu) show short circuit between their pads:

| # | Ref   | Position (mm) | Pkg  | Net (pad+) | Net (pad-) | Expected   | Measured |
|---|-------|---------------|------|------------|------------|------------|----------|
| 1 | C17   | (110, 35.0)   | 0805 | VBUS       | GND        | >1MΩ       | ~0Ω      |
| 2 | C1    | (122, 48.5)   | 0805 | +5V        | GND        | >1MΩ       | ~0Ω      |
| 3 | C18   | (118, 55.0)   | 0805 | BAT+       | GND        | >1MΩ       | ~0Ω      |
| 4 | C19   | (110, 58.5)   | 1206 | +5V        | GND        | >1MΩ       | ~0Ω      |
| 5 | C2    | (125, 62.5)   | 1206 | +3V3       | GND        | >1MΩ       | ~0Ω      |
| 6 | C3    | (69.5, 42.0)  | 0805 | +3V3       | GND        | >1MΩ       | ~0Ω      |

USB-C (J1) was desoldered — short persists → not a connector issue.

---

## 2. Root Cause: Routing Violations on F.Cu

Running the collision grid analysis (`generate_all_traces()`) reveals **186 violations**, including **critical power-net shorts**:

### 2.1 PRIMARY SHORT: GND via overlaps VBUS trace

```
F.Cu: GND via @(108.50, 60.50)
  vs VBUS trace F.Cu (82.00, 61.00) → (111.00, 61.00)
  gap = -0.200mm  ← OVERLAP! Direct VBUS-to-GND short
```

**Geometry:**

```
          VBUS horizontal trace (F.Cu, width=0.5mm)
  y=61.25 ─────────────────────────────────────── top edge
  y=61.00 ═══════════════════════════════════════ centerline
  y=60.75 ─────────────────────────────────────── bottom edge
  y=60.95 ·····○····· GND via annular ring top    ← OVERLAP 0.20mm
  y=60.50     (●)     GND via center
  y=60.05 ·····○····· GND via annular ring bottom

           x=82                    x=108.5    x=111
```

The GND via annular ring (r=0.45mm) extends to y=60.95, but the VBUS trace bottom edge is at y=60.75. **0.20mm of copper overlap** creates a direct metallurgical short.

### 2.2 SECONDARY SHORT: +5V via overlaps VBUS trace

```
F.Cu: +5V via @(111.50, 56.50)
  vs VBUS trace F.Cu (111.00, 61.00) → (111.00, 40.09)
  gap = -0.200mm  ← OVERLAP! +5V-to-VBUS short
```

**Geometry:**

```
        VBUS vertical trace (F.Cu, width=0.5mm)
  x=110.75 │     │ x=111.25
           │     │
  x=111.05 │·····│·○  +5V via annular ring left  ← OVERLAP 0.20mm
           │     │(●) +5V via center @x=111.50
  x=111.95 │     │ ○  +5V via annular ring right
```

### 2.3 Additional Violations in Power Area

```
VBUS via @(110.95, 33.00) vs LCD_D4 trace @(111.50, 32.30→36.21)
  gap = 0.000mm  ← TOUCHING (etching variance will short)

GND via @(109.05, 37.00) vs LCD_D0 via @(108.20, 36.84)
  gap = 0.145mm (need 0.25mm)  ← Via-to-via too close
```

---

## 3. Short Propagation Path

The two F.Cu violations create a chain that shorts ALL power rails to GND:

```
                    F.Cu Layer Violations
                    =====================

  GND via ──────── overlaps ──────── VBUS trace
  @(108.5, 60.5)    -0.20mm         @y=61.0
       │                                │
       │                                │ same trace
       │                                │
       │         +5V via ──── overlaps ──── VBUS trace
       │         @(111.5, 56.5) -0.20mm    @x=111.0
       │              │
       ▼              ▼
      GND ══════ VBUS ══════ +5V
                               │
                          AMS1117 (U3)
                               │
                              +3V3
                               │
                          pull-up R → GPIO
```

### Complete Short Circuit Diagram

```
                    ┌──────────────┐
  USB-C ──VBUS────►│   F.Cu via   │◄──── GND via @(108.5, 60.5)
                    │   overlap    │
                    │   -0.20mm    │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
  IP5306 pin8 ─+5V►│   F.Cu via   │ +5V via @(111.5, 56.5)
  (VOUT)            │   overlap    │
                    │   -0.20mm    │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         ┌────────┐  ┌────────┐  ┌────────┐
         │  VBUS  │  │  +5V   │  │  +3V3  │
         │  = GND │  │  = GND │  │  = GND │
         └────┬───┘  └────┬───┘  └────┬───┘
              │            │            │
           C17 ⚡        C1 ⚡       C2 ⚡
           C18 → BAT+    C19 ⚡      C3 ⚡
           (via IP5306)
```

**Result:** Every power rail reads 0Ω to GND through the F.Cu copper overlap.

---

## 4. Why JLCPCB Didn't Catch It

- JLCPCB DRC checks **Gerber files**, not KiCad source
- Zone fill (Docker) was applied AFTER trace generation
- The 0.20mm overlap is below typical Gerber visual inspection threshold
- JLCPCB minimum clearance is 0.1mm — the overlap is only flagged if DRC is run on the filled PCB
- The collision grid in `routing.py` detected it but **these violations were not treated as blockers**

---

## 5. Component Map (B.Cu Bottom Layer)

```
B.Cu viewed from back (X mirrored) — as seen in photos
Board: 160 x 75 mm

     ┌─────────────────────────────────────────────────────────┐
     │ [btn L]                                        [btn R]  │
     │                                                         │
     │    [FPC J4]          [ESP32-S3 U1]        [PAM8403 U4]  │
     │     ║  ║            ┌────────────┐          ┌──────┐    │
     │     ║  ║      ⚡C17 │            │          │      │    │
     │     ║  ║     (110,35)│  (80,27.5) │          │(30,30)│   │
     │               ◆     │            │          │      │    │
     │           U2 IP5306 └────────────┘          └──────┘    │
     │   ⚡C1   (110,42.5)                                     │
     │  (122,49)                              ⚡C3             │
     │           ▓▓L1▓▓                     (69.5,42)          │
     │  ⚡C18   (110,52.5)                                     │
     │  (118,55)  U3 AMS1117                                   │
     │           (125,55.5)    R4 R5 R6 ..... R14 R15 R19      │
     │           ⚡C19         C5 C6 C7 ..... C15 C16 C20      │
     │  ⚡C2    (110,58.5)                                     │
     │  (125,63)                                               │
     │                                                         │
     │ [btn]  [SD]    [JST bat]    [USB-C]   [btn]   [switch]  │
     └─────────────────────────────────────────────────────────┘

     ⚡ = shorted capacitor     ◆ = IP5306 (NOT the culprit)
```

---

## 6. F.Cu Routing — Problem Area

```
F.Cu Layer (front copper) — power trace routing

  y=40 ─── ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                          ║ VBUS vertical @x=111
                          ║ (width 0.5mm)
  y=48 ─── ─ ─ ─ ─ ─ ─ ─║─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                          ║
                          ║
  y=56 ─── ─ ─ ─ ─ ─ ─ ─║─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                         ◉║◄─ BUG #2: +5V via @(111.5, 56.5)
                          ║      overlaps VBUS vert (-0.20mm)
                          ║
  y=60 ─── ─ ─ ─ ─ ─ ─ ─║─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
               ◉          ║
               ▲          ║
  y=61 ═══════╪══════════╬═══ VBUS horizontal @y=61
               │          ║      (width 0.5mm, x=82→111)
               │          ║
        BUG #1: GND via   ║
        @(108.5, 60.5)    ║
        overlaps VBUS     ║
        horiz (-0.20mm)   ║
                          ║
  x=82       x=108.5    x=111

  Legend:  ═══ VBUS trace    ◉ via (wrong clearance)
```

---

## 7. Fix Required

### Immediate (for next PCB revision):

1. **Move GND via at (108.50, 60.50)** — increase Y offset to at least y=59.5
   - Required gap: via_top (59.5+0.45=59.95) < VBUS_bottom (60.75) → gap=0.80mm ✓

2. **Move +5V via at (111.50, 56.50)** — decrease X to at least x=112.5
   - Required gap: via_left (112.5-0.45=112.05) > VBUS_right (111.25) → gap=0.80mm ✓

3. **Fix VBUS via at (110.95, 33.00)** — separate from LCD_D4 trace
   - Current gap=0.000mm, need ≥0.15mm

### In `routing.py`:

```python
# Fix 1: GND via near C19 — increase Y offset from VBUS horizontal
# Was: y = c19_p2_y + 2 → 60.50 (overlaps VBUS @y=61, gap=-0.20mm)
# Fix: y = c19_p2_y + 1.0 → 59.50 (gap to VBUS=0.80mm ✓)

# Fix 2: +5V via near C19 — offset X away from VBUS vertical
# Was: x = 111.50 (overlaps VBUS vert @x=111, gap=-0.20mm)
# Fix: x = 112.50 (gap to VBUS=0.80mm ✓)
```

### Verification after fix:

```bash
make fast-check          # Regenerate + DRC
make verify-fast         # 43 DFM tests
python3 scripts/verify_dfa.py  # 9 assembly tests
```

---

## 8. Why Tests Didn't Catch It

| Check | Why it missed |
|-------|---------------|
| **Collision grid** (routing.py) | Reported 186 violations, but mixed with 180+ FPC/display violations. Power shorts buried in noise. Not treated as blocking errors. |
| **verify_dfm_v2.py** | Checks pad spacing, drill sizes, silk clearance — does NOT check via-to-trace clearance on different layers |
| **verify_dfa.py** | Checks assembly (rotation, BOM, CPL) — not copper routing |
| **KiCad DRC** (kicad-cli) | Runs on filled board, but zone fill might mask the overlap if GND zone on F.Cu fills around the via (creating thermal relief that appears valid) |
| **JLCPCB review** | Checks Gerbers for minimum clearance (0.1mm). A 0.2mm overlap SHOULD have been caught, but JLCPCB DRC focuses on same-net shorts, not cross-net via-to-trace overlaps in power areas |
| **Visual inspection** | The F.Cu side is under the display — overlap not visible during testing |

**Root problem:** C19 was added late (DFM fix moved it to 110, 58.5) but its via offsets (±2mm vertical) were never checked against the VBUS F.Cu traces at y=61 and x=111. The VBUS route was changed in "SHORT FIX v4" to y=61 — this placed it exactly in the path of C19's vias.

---

## 9. Origin of the Bug — C19 Via Placement

Both problematic vias are generated by **C19** (1206 capacitor, +5V/GND, at 110, 58.5):

```python
# routing.py line 2663-2673
# C19 pad "1" (+5V) at (111.5, 58.5) → via at (111.5, 56.5)  ← BUG #2
# C19 pad "2" (GND)  at (108.5, 58.5) → via at (108.5, 60.5)  ← BUG #1
```

C19 is a 1206 package (3.2mm long). On B.Cu (mirrored):
- Pad 1 (+5V) center: x = 110 + 1.5 = 111.5mm
- Pad 2 (GND) center: x = 110 - 1.5 = 108.5mm

Both vias use 2mm vertical offset from pad, which puts them:
- GND via at y=60.5 → 0.5mm below VBUS horizontal @y=61 → **overlaps by 0.20mm**
- +5V via at y=56.5 → 0.5mm right of VBUS vertical @x=111 → **overlaps by 0.20mm**

---

## 10. Existing Boards — REWORK PROCEDURE

The fix is **surgical but simple**: scrape copper on F.Cu to create clearance around 2 vias.

**No jumper wires needed.** The vias still connect to GND (In1.Cu) and +5V (In2.Cu) through the inner power planes. We only need to break the F.Cu annular ring contact with the VBUS trace.

### Tools needed

- Precision knife (X-Acto) or scalpel
- Magnifying glass or loupe (10x)
- Multimeter (continuity mode)
- Isopropyl alcohol + cotton swab
- Optional: fine sandpaper (800 grit)

### Step-by-step

#### PREPARATION
1. Remove display panel if attached (unclip FPC ribbon)
2. Clean F.Cu (top/display) side with isopropyl alcohol
3. Identify the 2 vias on F.Cu — they are near the center of the board:

```
F.Cu (top/display side) — looking down at the board

                     VBUS vertical trace
                     @x=111, width 0.5mm
                          │║│
                          │║│
    +5V via ──────────► ──│◉│── y=56.5
    (111.5, 56.5)         │║│    Scrape HERE: isolate via ring
    r=0.45mm              │║│    from VBUS trace on LEFT side
                          │║│
                          │║│
                          │║│
    ══════════════════════╬║╬════════  VBUS horizontal @y=61
                       ───│◉│───       width 0.5mm
                          │ │
    GND via ────────────► (108.5, 60.5)
    r=0.45mm                 Scrape HERE: isolate via ring
                             from VBUS trace ABOVE
```

#### VIA 1: via GND a (108.5, 60.5) — sovrapposto alla traccia VBUS orizzontale

4. Trova il via GND sul lato F.Cu (lato display) — si trova a ~2.5mm a SINISTRA dell'angolo dove la traccia VBUS orizzontale incontra quella verticale
5. Con la lama del bisturi/cutter, gratta una **linea sottile** (0.3mm) di rame tra:
   - Il bordo SUPERIORE dell'anello del via (y ≈ 60.95)
   - Il bordo INFERIORE della traccia VBUS orizzontale (y ≈ 60.75)
6. Direzione del taglio: **orizzontale**, parallela alla traccia VBUS
7. Verifica col multimetro: tocca il pad del via e la traccia VBUS — deve leggere **CIRCUITO APERTO** (nessuna continuita)

#### VIA 2: via +5V a (111.5, 56.5) — sovrapposto alla traccia VBUS verticale

8. Trova il via +5V sul lato F.Cu — si trova a ~4.5mm PIU IN ALTO (verso il centro della scheda) rispetto al VIA 1, e ~3mm a DESTRA
9. Con la lama del bisturi/cutter, gratta una **linea sottile** (0.3mm) di rame tra:
   - Il bordo SINISTRO dell'anello del via (x ≈ 111.05)
   - Il bordo DESTRO della traccia VBUS verticale (x ≈ 111.25)
10. Direzione del taglio: **verticale**, parallela alla traccia VBUS
11. Verifica col multimetro: tocca il pad del via e la traccia VBUS — deve leggere **CIRCUITO APERTO**

#### VERIFICATION

12. Test ALL 6 capacitors — each should now read **high impedance** (>100kΩ):

| # | Ref | Where to probe (B.Cu) | Expected after fix |
|---|-----|----------------------|-------------------|
| 1 | C17 | Both pads | >100kΩ (was 0Ω) |
| 2 | C1  | Both pads | >100kΩ (was 0Ω) |
| 3 | C18 | Both pads | >100kΩ (was 0Ω) |
| 4 | C19 | Both pads | >100kΩ (was 0Ω) |
| 5 | C2  | Both pads | >100kΩ (was 0Ω) |
| 6 | C3  | Both pads | >100kΩ (was 0Ω) |

13. If ANY cap still reads 0Ω, check:
    - Scrape was deep enough (all copper removed)
    - No solder bridges elsewhere
    - Both vias were correctly isolated

#### POWER-ON TEST

14. Connect USB-C to a **current-limited supply** (set 100mA max, 5V)
15. Expected: current draw < 50mA (idle, no battery)
16. If current immediately hits limit → additional short exists, do NOT continue
17. Measure voltages:

| Test point | Expected |
|-----------|----------|
| VBUS (C17 pad+) | 5.0V |
| +5V (C1 pad+) | 4.8-5.2V |
| +3V3 (C2 pad+) | 3.3V |
| BAT+ (C18 pad+) | 0V (no battery) |

#### PROTECTION

18. Apply a drop of UV solder mask or clear nail polish over the scraped areas
19. This prevents oxidation and accidental re-bridging
20. Reattach display panel

### Rework diagram (cross-section)

```
BEFORE (shorted):

  F.Cu ═══════VBUS═══════●GND═══   ← via ring touches trace
  In1.Cu ──────────────GND────────  ← GND zone
  In2.Cu ──────────────+5V────────  ← +5V zone
  B.Cu ════════C19═pad═●══════════  ← C19 GND pad

AFTER (fixed):

  F.Cu ═══════VBUS═══╳···●GND···   ← scraped gap, via ring isolated
  In1.Cu ──────────────GND────────  ← GND zone still connected to via ✓
  In2.Cu ──────────────+5V────────  ← +5V zone still connected ✓
  B.Cu ════════C19═pad═●══════════  ← C19 still works through inner layers ✓

  ╳ = scraped copper gap (0.3mm)
  ● = via (still connects to inner layers through barrel)
```

### Time estimate per board: ~10 minutes

---

## 11. Software Fix (for next PCB revision)

In `scripts/generate_pcb/routing.py`, change C19 via offsets:

```python
# C19 near L1: VOUT decoupling, pad "1" -> +5V via, pad "2" -> GND via
# FIX: increase offset to 3.5mm (was 2mm) to clear VBUS F.Cu traces
c19_p1 = _pad("C19", "1")
c19_p2 = _pad("C19", "2")
if c19_p1:
    parts.append(_seg(c19_p1[0], c19_p1[1], c19_p1[0], c19_p1[1] - 3.5,  # was -2
                      "B.Cu", W_SIG, NET_ID["+5V"]))
    parts.append(_via_net(c19_p1[0], c19_p1[1] - 3.5, NET_ID["+5V"]))     # was -2
if c19_p2:
    parts.append(_seg(c19_p2[0], c19_p2[1], c19_p2[0], c19_p2[1] + 1.0,   # was +2
                      "B.Cu", W_SIG, n_gnd))
    parts.append(_via_net(c19_p2[0], c19_p2[1] + 1.0, n_gnd))              # was +2
```

New via positions:
- +5V via: (111.5, 55.0) → gap to VBUS vert @x=111: 111.05-111.25 = still tight!
  - Better: route horizontally first, then via at x=113
- GND via: (108.5, 59.5) → gap to VBUS horiz @y=61: 60.75-59.95 = 0.80mm ✓

---

## 12. Analisi Completa: TUTTI gli Overlap nel PCB

L'analisi della collision grid rivela **139 overlap** tra net diverse (gap < 0mm).

### Classificazione per gravita

| Categoria | Quanti | Effetto | Riparabile con rework? |
|-----------|--------|---------|----------------------|
| **A. Power↔Power** | 2 | Board non si accende | SI (grattare 2 via) |
| **B. Power↔Segnale** | 23 | Possibile danno IC, periferiche non funzionano | Alcuni si |
| **C. Segnale↔Segnale (FPC)** | ~60 | Display non funziona | NO (troppi, serve redesign) |
| **D. Segnale↔Segnale (bottoni)** | ~18 | Bottoni con input errato | NO (serve redesign) |
| **E. Segnale↔Segnale (altro)** | ~36 | SD, USB, audio problemi | NO (serve redesign) |

### A. Power↔Power (2) — GIA NOTI, fix con rework

```
1. GND via ↔ VBUS trace     gap=-0.200mm  F.Cu  ← GRATTARE
2. +5V via ↔ VBUS trace     gap=-0.200mm  F.Cu  ← GRATTARE
```

### B. Power↔Segnale — i piu pericolosi dopo i 2 VBUS

```
 #  Net1        Net2         Gap(mm)  Layer  Zona PCB
 1  SD_MOSI   ↔ GND         -2.050   B.Cu   SD card area
 2  LCD_D7    ↔ GND(ESP32)  -1.645   B.Cu   ESP32 thermal pad
 3  LCD_D7    ↔ GND(ESP32)  -1.315   B.Cu   ESP32 thermal pad
 4  +3V3      ↔ BTN_SELECT  -0.750   B.Cu   Pull-up area
 5  GND       ↔ BTN_L       -0.575   B.Cu   Shoulder switch
 6  GND       ↔ BTN_R       -0.575   B.Cu   Shoulder switch
 7  +5V       ↔ SPK-(PAM)   -0.550   B.Cu   PAM8403 area
 8  GND       ↔ I2S_DOUT    -0.550   B.Cu   PAM8403 area
 9  VBUS via  ↔ LCD_RST     -0.515   F.Cu   Power area
10  LCD_RST   ↔ GND via     -0.475   F.Cu   Power area
11  BTN_B     ↔ GND         -0.475   B.Cu   ABXY area
12  +3V3      ↔ BTN_Y       -0.475   F.Cu   Button area
13  GND       ↔ SD_CS       -0.450   B.Cu   SD card area
14  GND       ↔ LCD_D0      -0.450   B.Cu   FPC area
15  GND       ↔ USB_D+      -0.425   F.Cu   USB area
```

### C. LCD Bus (FPC connector area) — ~60 violazioni

Tutte le tracce LCD_D0-D7 + LCD_RST/BL/DC/CS si incrociano
tra loro nell'area di approccio al connettore FPC J4.
Overlap fino a -3.0mm. Il display **non funzionera** senza redesign.

### D. Bottoni — ~18 violazioni

BTN_A/B/X/Y/L/R/START/SELECT tracce si incrociano tra loro
e con via GND/+3V3. Alcuni bottoni potrebbero non funzionare
o dare input errati.

---

### Impatto pratico dopo il rework dei 2 via VBUS

| Funzione | Previsione |
|----------|-----------|
| Accensione (power) | **FUNZIONERA** dopo rework 2 via ✓ |
| ESP32 boot | Probabile ✓ (se USB_D+/D- funzionano per flash) |
| Display LCD | **NON FUNZIONERA** (~60 crossing nel bus dati) |
| SD card | **PROBLEMI** (SD_MOSI↔GND, SD_CS↔GND) |
| Audio | **PROBLEMI** (+5V↔SPK-, GND↔I2S_DOUT su PAM8403) |
| Bottoni D-pad | Alcuni funzionano, alcuni no |
| Bottoni ABXY | **PROBLEMI** (BTN_B↔GND, crossing reciproci) |
| Shoulder L/R | **PROBLEMI** (GND↔BTN_L, GND↔BTN_R) |
| USB (flash) | **RISCHIO** (GND↔USB_D+) |

---

## 13. Conclusione

Il PCB ha **139 violazioni di routing** tra net diverse. Il design richiede un **redesign completo del routing** prima di ordinare una nuova revisione.

### Per le 5 schede attuali

Il rework dei 2 via C19 risolve il corto power e permette l'accensione.
Ma molte funzioni (display, SD, audio, alcuni bottoni) probabilmente non funzioneranno a causa delle altre violazioni nel routing.

**Consiglio:** fai il rework dei 2 via, accendi con limite di corrente, e testa ogni funzione. Alcune violazioni potrebbero essere false positive del collision grid (pad same-net non riconosciuti). Il test reale sulla scheda dira quali problemi sono effettivi.

### Per la prossima revisione PCB

1. Risolvere TUTTE le 139 violazioni in `routing.py`
2. Aggiungere un check bloccante: `generate_all_traces()` deve fallire se ci sono overlap cross-net con gap < 0
3. Eseguire KiCad DRC nativo dopo zone fill
4. Verificare con JLCPCB DRC online prima di ordinare
