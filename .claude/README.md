# Claude Code Configuration — ESP32 Emu Turbo

This directory configures Claude Code for the ESP32 Emu Turbo project:

- **43 skills** in `.claude/skills/` (27 PCB + 16 project-local)
- **6 lifecycle commands** in `.claude/commands/`
- **6 specialized agents** in `.claude/agents/`
- **Auto-hooks** in `.claude/settings.json` (DFM verification, skill hints, safety guards)

> **Note on plugin vs project-local**: the 27 PCB/JLCPCB skills are packaged as
> `kicad-jlcpcb-skills` in `.claude-plugin/plugin.json` and are reusable by any KiCad project.
> The other 16 skills (firmware, CAD, website, docs, scout) are project-local and remain
> specific to ESP32 Emu Turbo.
>
> Plugin packaging and structure inspired by
> [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) — see
> [`docs/skill-anatomy.md`](../docs/skill-anatomy.md) for credits.

## Lifecycle commands (6)

Composed workflows that chain multiple skills. Use these as the primary entry points.

| Command | Phase | Composes |
|---|---|---|
| [`/design-pcb`](commands/design-pcb.md) | Design | `/pcb-schematic` → `/pcb-board` → `/pcb-components` → `/pcb-routing` |
| [`/generate-pcb`](commands/generate-pcb.md) | Generate | `/generate` → `/check` |
| [`/verify-pcb`](commands/verify-pcb.md) | Verify | `/verify` → `/drc-native` → `/drc-audit` → `/pad-analysis` → `/jlcpcb-validate` → `/datasheet-verify` → `/design-intent` → `/pcb-review` |
| [`/fix-pcb`](commands/fix-pcb.md) | Fix | `/dfm-fix` → `/fix-rotation` → `/jlcpcb-check` → `/jlcpcb-parts` |
| [`/release-pcb`](commands/release-pcb.md) | Release | `/full-release` (which chains verify + gerbers + BOM + CPL + render + commit) |
| [`/bootstrap-new-pcb`](commands/bootstrap-new-pcb.md) | Meta | Scaffolds a new PCB project from scratch |

See [`docs/lifecycle.md`](../docs/lifecycle.md) for the full 5-phase workflow diagram.

## The 27 PCB skills (packaged as `kicad-jlcpcb-skills`)

### Design — MCP Design Skills (5)

| Skill | Description |
|---|---|
| [`pcb-schematic`](skills/pcb-schematic/SKILL.md) | Define sheets, nets, cross-sheet labels |
| [`pcb-board`](skills/pcb-board/SKILL.md) | Board outline, layers, mounting holes, silkscreen |
| [`pcb-components`](skills/pcb-components/SKILL.md) | Footprint placement with rotation/mirroring |
| [`pcb-routing`](skills/pcb-routing/SKILL.md) | Traces + vias with collision grid |
| [`pcb-library`](skills/pcb-library/SKILL.md) | Footprint library management |

### Generate — Pipeline (7)

| Skill | Description |
|---|---|
| [`generate`](skills/generate/SKILL.md) | Full PCB generation from Python sources |
| [`render`](skills/render/SKILL.md) | SVG layers + animation frames |
| [`pcba-render`](skills/pcba-render/SKILL.md) | Photorealistic 3D PCBA (top/bottom/iso/detail) |
| [`check`](skills/check/SKILL.md) | Quick DFM + 3D + gerber sanity (~5s) |
| [`release-prep`](skills/release-prep/SKILL.md) | Full pipeline without git |
| [`full-release`](skills/full-release/SKILL.md) | Full pipeline with git commit + push |
| [`release`](skills/release/SKILL.md) | JLCPCB release package with version notes |

### Verify — Verification (11)

| Skill | Description |
|---|---|
| [`verify`](skills/verify/SKILL.md) | 115 DFM + 9 DFA tests |
| [`dfm-test`](skills/dfm-test/SKILL.md) | DFM regression guards |
| [`drc-native`](skills/drc-native/SKILL.md) | KiCad native DRC with baseline |
| [`drc-audit`](skills/drc-audit/SKILL.md) | Shorts, unconnected, dangling vias |
| [`pcb-optimize`](skills/pcb-optimize/SKILL.md) | Layout analysis (routing quality) |
| [`pcb-review`](skills/pcb-review/SKILL.md) | 8-domain scored review |
| [`datasheet-verify`](skills/datasheet-verify/SKILL.md) | Pinouts + dimensions vs datasheets |
| [`design-intent`](skills/design-intent/SKILL.md) | 18-test cross-source adversary |
| [`pad-analysis`](skills/pad-analysis/SKILL.md) | Pad-to-pad spacing (net-aware) |
| [`jlcpcb-alignment`](skills/jlcpcb-alignment/SKILL.md) | Batch pin alignment |
| [`jlcpcb-validate`](skills/jlcpcb-validate/SKILL.md) | 26 JLCPCB manufacturing rules |

### Fix — Fix & Debug (4)

| Skill | Description |
|---|---|
| [`dfm-fix`](skills/dfm-fix/SKILL.md) | Apply DFM fixes to routing |
| [`fix-rotation`](skills/fix-rotation/SKILL.md) | CPL rotation for JLCPCB |
| [`jlcpcb-check`](skills/jlcpcb-check/SKILL.md) | 3D alignment + footprint validation |
| [`jlcpcb-parts`](skills/jlcpcb-parts/SKILL.md) | LCSC part search via EasyEDA API |

## Project-local skills (16)

These skills are not in the reusable plugin — they stay local to ESP32 Emu Turbo.

### Firmware (5)

| Skill | Description |
|---|---|
| [`firmware-build`](skills/firmware-build/SKILL.md) | Build/flash/test ESP-IDF firmware via Docker |
| [`firmware-sync`](skills/firmware-sync/SKILL.md) | Verify GPIO pins match between firmware and schematic |
| [`hardware-test-gen`](skills/hardware-test-gen/SKILL.md) | Generate Unity tests for prototype validation |
| [`pcb-to-firmware`](skills/pcb-to-firmware/SKILL.md) | Propagate PCB changes to firmware config |
| [`pipeline-resume`](skills/pipeline-resume/SKILL.md) | Resume a crashed pipeline from checkpoint |

### CAD / Enclosure (3)

| Skill | Description |
|---|---|
| [`enclosure-design`](skills/enclosure-design/SKILL.md) | OpenSCAD parametric enclosure design |
| [`enclosure-render`](skills/enclosure-render/SKILL.md) | Render enclosure views to PNG |
| [`enclosure-export`](skills/enclosure-export/SKILL.md) | Export STL for 3D printing |

### Docs & Website (3)

| Skill | Description |
|---|---|
| [`doc`](skills/doc/SKILL.md) | Audit docs against source-of-truth |
| [`website-dev`](skills/website-dev/SKILL.md) | Docusaurus site development |
| [`user-feedback`](skills/user-feedback/SKILL.md) | Process user feedback into memory |

### Specialized audits (2)

| Skill | Description |
|---|---|
| [`hardware-audit`](skills/hardware-audit/SKILL.md) | Deep electrical/functional audit |
| [`electrical-review`](skills/electrical-review/SKILL.md) | Strapping pins, decoupling, power sequence |

### Meta (3)

| Skill | Description |
|---|---|
| [`create-skill`](skills/create-skill/SKILL.md) | Scaffold a new skill |
| [`external-dfm`](skills/external-dfm/SKILL.md) | Run KiBot external DFM pipeline |
| [`scout`](skills/scout/SKILL.md) | GitHub pattern discovery (weekly autonomous) |

## Agents (6)

Specialized sub-agents with delegated tool access and cost control.

| Agent | Model | Role |
|---|---|---|
| [`team-lead`](agents/team-lead.md) | Sonnet | Orchestrator — dispatches work to specialists |
| [`pcb-engineer`](agents/pcb-engineer.md) | Opus | PCB design, DFM, JLCPCB — owns the 27 plugin skills |
| [`software-dev`](agents/software-dev.md) | Opus | ESP-IDF firmware + website |
| [`cad-engineer`](agents/cad-engineer.md) | Haiku | OpenSCAD enclosure |
| [`plan-reviewer`](agents/plan-reviewer.md) | Opus | Pre-implementation plan review |
| [`scout`](agents/scout.md) | Opus | GitHub pattern discovery (autonomous weekly) |

## Hooks (auto-guards)

Configured in `.claude/settings.json`:

| Trigger | Scope | Action |
|---|---|---|
| `UserPromptSubmit` | all | Suggests relevant skills based on keyword matching |
| `PreToolUse` | Bash/Edit/Write/Read | Safety guard for dangerous operations |
| `PreToolUse` | Edit/Write | PCB edit guard — prevents direct `.kicad_pcb` edits |
| `PreToolUse` | Read/Edit/Write/Grep | `.claudeignore` guard |
| `PostToolUse` | Bash (generate/release) | Reminds to run `verify_dfa.py` |
| `PostToolUse` | Edit/Write (PCB) | Reminds to run `verify_dfa.py` |
| `PreCompact` | all | Saves session backup to `.claude/backups/` |
| `Stop` | all | Auto-runs DFM verification if PCB files changed |

## Related docs

- [`docs/getting-started.md`](../docs/getting-started.md) — install and first-run
- [`docs/lifecycle.md`](../docs/lifecycle.md) — 5-phase PCB design lifecycle
- [`docs/skill-anatomy.md`](../docs/skill-anatomy.md) — how to write your own skills
- [`CLAUDE.md`](../CLAUDE.md) — top-level project instructions for Claude Code

## Credits

Plugin packaging layout (`.claude-plugin/plugin.json`, `marketplace.json`, flat `skills/`,
lifecycle slash commands) is modeled on
[addyosmani/agent-skills](https://github.com/addyosmani/agent-skills). Our domain is
hardware instead of web SDLC, but the discoverability and packaging mechanics are the same.
