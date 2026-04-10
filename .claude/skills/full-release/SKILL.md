---
name: full-release
description: Complete release pipeline — all verifications, 3D PCBA renders, SVG renders, gerber export, BOM/CPL, and release_jlcpcb/ sync. Use after PCB changes to prepare a production-ready JLCPCB package with documentation renders.
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: <version> (e.g. v3.0)
---

# Full Release Pipeline

Complete end-to-end pipeline: generate PCB, run ALL verifications, render all views, export gerbers, and sync release_jlcpcb/. Combines `/verify`, `/render`, `/pcba-render`, and `/release` into a single workflow.

**Argument**: Version tag (e.g., `v3.0`).

## Critical Rules

- ALL verifications must pass before proceeding to gerber export
- NEVER skip `release_jlcpcb/` sync
- If any step fails, STOP and report — do not continue with broken output
- Always run `verify_dfm_v2.py` AFTER gerber export (final gate)
- HARD GATE: `verify_trace_through_pad.py` MUST report 0 failures.
  This catches the v3.3 regression class where `_PAD_NETS` entries were
  removed, leaving netted traces physically crossing unnetted pads —
  real shorts on the fabricated board that the standard DFM/DRC flow
  does not catch together.

## Pipeline Steps

### Step 1: Generate PCB from Python specs

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -m scripts.generate_pcb hardware/kicad
```

### Step 2: Full verification suite

Run all 5 verification scripts. ALL must pass (warnings OK, errors = STOP).

```bash
# 2a. DFM verification (115 tests)
python3 scripts/verify_dfm_v2.py

# 2a-bis. Trace-through-pad overlap — HARD GATE (blocks release)
python3 scripts/verify_trace_through_pad.py

# 2b. DFA verification (9 tests)
python3 scripts/verify_dfa.py

# 2c. Polarity verification
python3 scripts/verify_polarity.py

# 2d. Design Rule Check
python3 scripts/drc_check.py

# 2e. Electrical connectivity
python3 scripts/test_pcb_connectivity.py

# 2f. Schematic-PCB consistency
python3 scripts/verify_schematic_pcb.py

# 2g. Electrical simulation (power budget, timing, GPIO conflicts)
python3 scripts/verify_electrical.py
```

**Gate check**: If DFM or DFA have failures, STOP. Polarity and electrical warnings are OK if previously acknowledged.

### Step 3: SVG renders (PCB layout + animation)

```bash
# PCB SVG visualization (layers, traces, components)
python3 scripts/render_pcb_svg.py website/static/img/pcb

# PCB animated GIF (layer-by-layer reveal)
python3 scripts/render_pcb_animation.py website/static/img/pcb
```

### Step 4: 3D PCBA renders (raytraced, 6 views)

```bash
# Inject 3D component models into temp file
python3 scripts/inject-3d-models.py \
  hardware/kicad/esp32-emu-turbo.kicad_pcb \
  /tmp/pcba-render.kicad_pcb

OUT="website/static/img/renders"
PCB="/tmp/pcba-render.kicad_pcb"
W=1920; H=1080

# Top view
kicad-cli pcb render -o "$OUT/pcba-top.png" \
  --width $W --height $H --side top \
  --quality high --floor --background opaque \
  --light-top 0.85 --light-camera 0.3 --light-side 0.4 \
  "$PCB"

# Bottom view
kicad-cli pcb render -o "$OUT/pcba-bottom.png" \
  --width $W --height $H --side bottom \
  --quality high --floor --background opaque \
  --light-top 0.85 --light-camera 0.3 --light-side 0.4 \
  "$PCB"

# Isometric front-left (hero shot)
kicad-cli pcb render -o "$OUT/pcba-iso-front.png" \
  --width $W --height $H --rotate "-45,0,30" \
  --quality high --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5 \
  "$PCB"

# Isometric back-right
kicad-cli pcb render -o "$OUT/pcba-iso-back.png" \
  --width $W --height $H --rotate "-45,0,210" \
  --quality high --perspective --floor --background opaque \
  --zoom 0.7 --light-top 0.9 --light-camera 0.4 --light-side 0.5 \
  "$PCB"

# Low angle (dramatic)
kicad-cli pcb render -o "$OUT/pcba-low-angle.png" \
  --width $W --height $H --rotate "-25,0,20" \
  --quality high --perspective --floor --background opaque \
  --zoom 0.6 --light-top 0.7 --light-camera 0.5 --light-side 0.6 \
  --light-side-elevation 30 \
  "$PCB"

# Detail MCU (zoomed ESP32 area)
kicad-cli pcb render -o "$OUT/pcba-detail-mcu.png" \
  --width $W --height $H --rotate "-40,0,15" \
  --quality high --perspective --background opaque \
  --zoom 2.0 --pan "2,1,0" \
  --light-top 0.85 --light-camera 0.5 --light-side 0.4 \
  "$PCB"

# Cleanup temp file
rm -f /tmp/pcba-render.kicad_pcb
```

### Step 5: Gerber export (local kicad-cli + Docker zone fill)

```bash
./scripts/export-gerbers-fast.sh
```

If Docker/OrbStack is not available, use full local export:

```bash
rm -rf hardware/kicad/gerbers && mkdir -p hardware/kicad/gerbers

kicad-cli pcb export gerbers \
    --output hardware/kicad/gerbers/ \
    --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" \
    --subtract-soldermask --use-drill-file-origin \
    hardware/kicad/esp32-emu-turbo.kicad_pcb

kicad-cli pcb export drill \
    --output hardware/kicad/gerbers/ \
    --format excellon --drill-origin plot \
    --excellon-units mm --generate-map --map-format gerberx2 \
    hardware/kicad/esp32-emu-turbo.kicad_pcb

cd hardware/kicad/gerbers && \
  zip -j ../jlcpcb/gerbers.zip *.gtl *.g1 *.g2 *.gbl *.gto *.gbo *.gts *.gbs *.gtp *.gbp *.gm1 *.drl *.gbrjob 2>/dev/null
```

### Step 6: Post-export DFM recheck

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 scripts/verify_dfm_v2.py
```

Must still pass 114/114 after gerber export.

### Step 7: Sync to release_jlcpcb/

```bash
cp hardware/kicad/jlcpcb/bom.csv release_jlcpcb/bom.csv
cp hardware/kicad/jlcpcb/cpl.csv release_jlcpcb/cpl.csv
cp hardware/kicad/esp32-emu-turbo.kicad_pcb release_jlcpcb/esp32-emu-turbo.kicad_pcb
rm -rf release_jlcpcb/gerbers
cp -r hardware/kicad/gerbers release_jlcpcb/gerbers
cp hardware/kicad/jlcpcb/gerbers.zip release_jlcpcb/gerbers.zip 2>/dev/null || true
```

### Step 8: Update release README

Edit `release_jlcpcb/README.md`:
- Add version header with date
- List all changes since last version
- Include verification results summary (DFM, DFA, DRC counts)
- Include component count and cost estimate

### Step 9: Verify outputs

```bash
echo "=== Release Files ==="
ls -lh release_jlcpcb/gerbers.zip release_jlcpcb/bom.csv release_jlcpcb/cpl.csv
echo "=== Gerbers ==="
ls release_jlcpcb/gerbers/ | wc -l
echo "=== SVG Renders ==="
ls website/static/img/pcb/*.svg 2>/dev/null | wc -l
echo "=== PCBA Renders ==="
ls website/static/img/renders/pcba/pcba-*.png 2>/dev/null | wc -l
```

### Step 10: Git commit

```bash
git add release_jlcpcb/ hardware/kicad/esp32-emu-turbo.kicad_pcb website/static/img/
git commit -m "release($VERSION): full JLCPCB package + renders"
```

## Summary Report Format

| Step | Status | Detail |
|------|--------|--------|
| 1. PCB generation | OK/FAIL | — |
| 2a. DFM v2 (114 tests) | X/114 pass | — |
| 2b. DFA (9 tests) | X/9 pass | — |
| 2c. Polarity (39 tests) | X/39 pass | N stale |
| 2d. DRC | OK/FAIL | X violations |
| 2e. Connectivity | OK/FAIL | — |
| 2f. Schematic sync | OK/FAIL | — |
| 2g. Electrical sim | OK/WARN | X errors, Y warnings |
| 3. SVG renders | OK/FAIL | X files |
| 4. PCBA 3D renders | OK/FAIL | 6 views |
| 5. Gerber export | OK/FAIL | X files in zip |
| 6. Post-export DFM | OK/FAIL | 114/114 |
| 7. Release sync | OK/FAIL | — |
| 8. README updated | OK/SKIP | — |
| 9. Outputs verified | OK/FAIL | — |
| 10. Git commit | OK/SKIP | — |

## JLCPCB Upload Instructions

After release is ready:
1. Go to https://cart.jlcpcb.com/quote
2. Upload `release_jlcpcb/gerbers.zip`
3. Select: 4-layer, 1.6mm, ENIG/HASL, green solder mask
4. Enable PCBA: upload `bom.csv` and `cpl.csv`
5. Verify 3D viewer alignment for all bottom-side components
6. Check component count matches BOM (21 unique parts, ~71 placements)

## Key Files

- `release_jlcpcb/` — Complete release package
- `release_jlcpcb/gerbers.zip` — Gerber package for JLCPCB upload
- `release_jlcpcb/bom.csv` — Bill of Materials
- `release_jlcpcb/cpl.csv` — Component Placement List
- `website/static/img/pcb/` — SVG renders + animation
- `website/static/img/renders/pcba/pcba-*.png` — 3D raytraced PCBA views
- `scripts/verify_dfm_v2.py` — DFM verification (114 tests)
- `scripts/verify_dfa.py` — DFA verification (9 tests)
