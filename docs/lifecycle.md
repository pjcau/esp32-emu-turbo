# PCB Design Lifecycle

The `kicad-jlcpcb-skills` plugin organizes its 27 skills into a 5-phase lifecycle. Each
phase has a corresponding slash command in `.claude/commands/` that composes the relevant
skills in the correct order.

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│  Design  │ → │ Generate │ → │  Verify  │ → │   Fix    │ → │ Release  │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
   (5 skills)    (7 skills)    (11 skills)    (4 skills)    (shares Generate)
```

> **Inspiration**: This lifecycle mirrors the `Idea → Spec → Build → Test → Review → Ship`
> lifecycle from [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills),
> adapted to hardware design where "code" becomes "Python generators" and "ship" becomes
> "JLCPCB order".

## Phase 1 — Design (5 skills)

Command: **`/design-pcb`**

Define the schematic, board, component placement, and routing. Everything happens in
Python source files that drive KiCad emission.

| Skill | Purpose |
|---|---|
| `/pcb-schematic` | Define sheets, nets, cross-sheet labels |
| `/pcb-board` | Set board outline, layers, mounting holes, silkscreen |
| `/pcb-components` | Place footprints with rotation, mirroring |
| `/pcb-library` | Manage footprint definitions |
| `/pcb-routing` | Route all traces + vias with collision grid |

**Inputs**: `scripts/generate_schematics/config.py`, `scripts/generate_pcb/board.py`,
`scripts/generate_pcb/routing.py`, `scripts/generate_pcb/footprints.py`

**Outputs**: none yet — only edits Python sources

**Exit criteria**: All target components placed, all nets routed, no manual KiCad edits.

## Phase 2 — Generate (7 skills)

Command: **`/generate-pcb`**

Emit KiCad files and render artifacts from the Python sources.

| Skill | Purpose |
|---|---|
| `/generate` | Full PCB generation — `python3 -m scripts.generate_pcb hardware/kicad` |
| `/render` | SVG layers + animation frames |
| `/pcba-render` | Photorealistic 3D PCBA (top, bottom, iso, detail) via KiCad raytracer |
| `/check` | Quick DFM + 3D + gerber sanity check (~5s) |
| `/release-prep` | Full pipeline without git operations |
| `/full-release` | Full pipeline with git commit + push |
| `/release` | JLCPCB release package with version notes |

**Inputs**: Python sources from Phase 1
**Outputs**: `hardware/kicad/esp32-emu-turbo.kicad_pcb`, `.kicad_sch` files, renders in `website/static/renders/`

**Exit criteria**: `/check` passes (quick DFM + 3D alignment + gerber sanity).

## Phase 3 — Verify (11 skills)

Command: **`/verify-pcb`**

Run the full verification suite. Nothing moves to release without these passing.

| Skill | Purpose |
|---|---|
| `/verify` | 115 DFM + 9 DFA tests |
| `/dfm-test` | DFM regression guards |
| `/drc-native` | KiCad `kicad-cli pcb drc` |
| `/drc-audit` | Shorts, unconnected, dangling vias |
| `/pcb-optimize` | Layout analysis (routing quality) |
| `/pcb-review` | 8-domain scored review |
| `/datasheet-verify` | Pinouts + physical dimensions vs datasheets |
| `/design-intent` | 18-test cross-source adversary (schematic ↔ PCB) |
| `/pad-analysis` | Pad-to-pad spacing (net-aware) |
| `/jlcpcb-alignment` | Batch pin alignment for fine-pitch parts |
| `/jlcpcb-validate` | 26 JLCPCB manufacturing rules |

**Inputs**: Generated KiCad files from Phase 2

**Outputs**: Pass/fail report for every test, baseline file `memory/dfm-state.md`

**Exit criteria**: All tests pass. No regressions against baseline.

## Phase 4 — Fix (4 skills)

Command: **`/fix-pcb`**

Apply targeted fixes when verification fails. Always loop back through Generate + Verify.

| Skill | Purpose |
|---|---|
| `/dfm-fix` | Apply DFM fixes (shift vias, adjust clearance) |
| `/fix-rotation` | Correct CPL rotation for JLCPCB |
| `/jlcpcb-check` | 3D alignment and footprint validation |
| `/jlcpcb-parts` | LCSC part search via EasyEDA API |

**Inputs**: Verification failures from Phase 3

**Outputs**: Updates to `scripts/generate_pcb/routing.py`, `hardware/kicad/jlcpcb/bom.csv`,
`hardware/kicad/jlcpcb/cpl.csv`

**Exit criteria**: Fix is applied, Phase 2 + Phase 3 both re-run clean.

## Phase 5 — Release

Command: **`/release-pcb`**

Produce the final JLCPCB manufacturing package. Gates Phase 3 must pass before release.

Shares skills with Phase 2 (`/full-release`, `/release`, `/release-prep`).

**Inputs**: Fully verified PCB from Phases 2–3

**Outputs**:
- `release_jlcpcb/gerbers.zip`
- `release_jlcpcb/bom.csv`
- `release_jlcpcb/cpl.csv`
- `release_jlcpcb/esp32-emu-turbo.kicad_pcb`
- `release_jlcpcb/gerbers/` (individual layers)
- Git commit + push with version tag

**Exit criteria**: `release_jlcpcb/` is up-to-date, gerbers.zip opens correctly,
JLCPCB web DFM passes on upload.

## The fix-and-verify loop

If `/verify-pcb` fails, the lifecycle becomes iterative:

```
     ┌──────────────────────┐
     │                      ↓
  Generate → Verify → (FAIL?) → Fix ──┐
                         │           │
                         │ PASS      │
                         ↓           │
                      Release  ←─────┘
```

The guard rule: **every iteration must end in `/verify-pcb` passing**. Never commit
a PCB file while verification is failing.

## Quick reference

| Situation | Command |
|---|---|
| Starting a new design | `/bootstrap-new-pcb` |
| Edited Python generator | `/generate-pcb` |
| Need full verification | `/verify-pcb` |
| DFM failures to fix | `/fix-pcb` |
| Ready to ship to JLCPCB | `/release-pcb` |

## Related docs

- `docs/getting-started.md` — installation and first-run
- `docs/skill-anatomy.md` — how to write your own skills
- `.claude/README.md` — full index of all 43 skills
