---
name: release
model: claude-opus-4-7
description: Prepare a complete JLCPCB release package with version notes
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Edit, Grep, Glob
argument-hint: <version> (e.g. v1.9)
---

# Prepare JLCPCB Release Package

Create a production-ready release package for JLCPCB manufacturing.

**Argument**: Version tag (e.g., `v1.9`).

## Steps

### 1. Run full generation pipeline

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -m scripts.generate_pcb hardware/kicad
```

### 2. Zone fill + gerber export (fast: local kicad-cli + Docker zone fill)

```bash
./scripts/export-gerbers-fast.sh
```

Or via full Docker:
```bash
docker compose run --rm --entrypoint python3 kicad-pcb /scripts/kicad_fill_zones.py "/project/esp32-emu-turbo.kicad_pcb"
docker compose run --rm kicad-pcb pcb export gerbers --output /gerbers/ --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts" --subtract-soldermask --use-drill-file-origin "/project/esp32-emu-turbo.kicad_pcb"
docker compose run --rm kicad-pcb pcb export drill --output /gerbers/ --format excellon --drill-origin plot --excellon-units mm --generate-map --map-format gerberx2 "/project/esp32-emu-turbo.kicad_pcb"
```

### 3. Run full verification suite (~1200 tests)

```bash
# ── BLOCKING: fab-short gate ─────────────────────────────────────
# Catches netted traces physically crossing unnetted pads.
# Missing this check caused the v3.3 regression (commit 775e9fd)
# where _PAD_NETS assignments for U2/U6/SW_PWR were removed,
# leaving 6 real shorts in the fabricated board.
python3 scripts/verify_trace_through_pad.py  # MUST be 0 failures

# ── BLOCKING: net connectivity gate ─────────────────────────────
# Walks the union-find over pads ∪ vias ∪ segments per net and
# asserts every net forms a single connected component. Missing
# this check left R5-CRIT-1..6 bugs shipped in v3.3 — BAT+ inductor
# isolated (no battery boot), VBUS decoupling floating, buttons
# with disconnected pull-ups, SW_BOOT non-functional, etc.
python3 scripts/verify_net_connectivity.py  # MUST be 0 failures

# Manufacturing (must all pass)
python3 scripts/verify_dfm_v2.py
python3 scripts/verify_dfa.py
python3 scripts/validate_jlcpcb.py
python3 scripts/verify_bom_cpl_pcb.py
python3 scripts/verify_polarity.py

# Datasheet + design intent
python3 scripts/verify_datasheet_nets.py
python3 scripts/verify_datasheet.py
python3 scripts/verify_design_intent.py

# Electrical review
python3 scripts/verify_strapping_pins.py
python3 scripts/verify_decoupling_adequacy.py
python3 scripts/verify_power_sequence.py

# Adversarial
python3 scripts/verify_component_connectivity.py
python3 scripts/verify_signal_chain_complete.py

# Power simulation
python3 scripts/spice_power_check.py
```

**ALL tests must pass before proceeding.** If any fail, fix the issues first.

**Hard gate**: if `verify_trace_through_pad.py` reports any failure, STOP
and fix the underlying `_PAD_NETS` assignment in
`scripts/generate_pcb/routing.py`. Never copy gerbers to `release_jlcpcb/`
with trace-through-pad overlaps — they are real shorts on the fabricated
board regardless of DFM/DFA passing.

### 4. Copy to release_jlcpcb/

```bash
cp hardware/kicad/jlcpcb/bom.csv release_jlcpcb/bom.csv
cp hardware/kicad/jlcpcb/cpl.csv release_jlcpcb/cpl.csv
rm -rf release_jlcpcb/gerbers
cp -r hardware/kicad/gerbers release_jlcpcb/gerbers
cd hardware/kicad/gerbers && zip -j ../../release_jlcpcb/gerbers.zip *.gtl *.g1 *.g2 *.gbl *.gto *.gbo *.gts *.gbs *.gtp *.gbp *.gm1 *.drl *.gbrjob 2>/dev/null
```

### 5. Generate PCBA renders (`/pcba-render`)

Inject 3D models and render all 13 views (top/bottom/iso/detail):

```bash
python3 scripts/inject-3d-models.py \
  hardware/kicad/esp32-emu-turbo.kicad_pcb \
  /tmp/pcba-render.kicad_pcb

OUT="website/static/img/renders/pcba"
PCB="/tmp/pcba-render.kicad_pcb"

# Top views (5)
kicad-cli pcb render -o "$OUT/pcba-top.png" --width 1920 --height 1080 --side top --quality high --floor --background opaque "$PCB"
kicad-cli pcb render -o "$OUT/pcba-iso-front.png" --width 1920 --height 1080 --rotate "-45,0,30" --quality high --perspective --floor --background opaque --zoom 0.7 "$PCB"
kicad-cli pcb render -o "$OUT/pcba-iso-back.png" --width 1920 --height 1080 --rotate "-45,0,210" --quality high --perspective --floor --background opaque --zoom 0.7 "$PCB"

# Bottom views (6)
kicad-cli pcb render -o "$OUT/pcba-bottom.png" --width 1920 --height 1080 --side bottom --quality high --floor --background opaque "$PCB"
kicad-cli pcb render -o "$OUT/pcba-bottom-iso-front.png" --width 1920 --height 1080 --side bottom --rotate "-45,0,30" --quality high --perspective --floor --background opaque --zoom 0.7 "$PCB"
kicad-cli pcb render -o "$OUT/pcba-bottom-detail-mcu.png" --width 1920 --height 1080 --side bottom --rotate "-40,0,15" --quality high --perspective --background opaque --zoom 2.0 --pan "2,1,0" "$PCB"

rm /tmp/pcba-render.kicad_pcb
```

See `.claude/skills/pcba-render/SKILL.md` for full 13-view camera presets.

### 6. Sync documentation (`/doc`)

Audit and update all docs to match current PCB state:

```bash
# Regenerate schematics from config
python3 -m scripts.generate_schematics hardware/kicad

# Key values to sync:
# - Via count, segment count, pad count (from .pcb_cache.json)
# - DFM/DFA test counts (from script output)
# - Component count (from BOM)
# - Skills count (from .claude/skills/)
# - Board dimensions (from board.py)
```

Cross-check these docs against source-of-truth files:
- `website/docs/design/pcb.md` — trace counts, via counts
- `website/docs/manufacturing/verification.md` — test counts, drill ops
- `website/docs/manufacturing/manufacturing.md` — component counts, costs
- `website/docs/tooling/claude-agents.md` — skills counts

See `.claude/skills/doc/SKILL.md` for full audit checklist.

### 7. Update release README

Edit `release_jlcpcb/README.md`:
- Add version header with date
- List all changes since last version
- Include verification results summary
- Include component count and cost estimate

### 8. Create git commit

Stage and commit all release files:
```bash
git add release_jlcpcb/ hardware/kicad/esp32-emu-turbo.kicad_pcb
git commit -m "Update release_jlcpcb/ to $VERSION with [summary of changes]"
```

### 9. Print JLCPCB upload instructions

After release is ready, print:
- Go to https://cart.jlcpcb.com/quote
- Upload `release_jlcpcb/gerbers.zip`
- Select 4-layer, 1.6mm, ENIG/HASL
- Enable PCBA: upload `bom.csv` and `cpl.csv`
- Verify 3D viewer alignment for all components
- Check component count matches BOM (26 unique parts, 80 placements)

## Key Files

- `release_jlcpcb/README.md` — Release notes
- `release_jlcpcb/gerbers.zip` — Gerber package
- `release_jlcpcb/bom.csv` — Bill of Materials
- `release_jlcpcb/cpl.csv` — Component Placement List
- `release_jlcpcb/gerbers/` — Individual gerber files
