---
description: Bootstrap a new KiCad + JLCPCB project from scratch using this skill suite. Sets up Python generator scaffolding, DFM baseline, and release pipeline.
---

# Bootstrap New PCB Project

Initialize a brand-new PCB project that uses the `kicad-jlcpcb-skills` workflow.

## What this does

Scaffolds the minimum structure to start designing a PCB with the full skill suite:

```
my-new-pcb/
├── .claude/
│   ├── commands/          ← symlink or copy from plugin
│   └── settings.json      ← hooks for DFM auto-check
├── .claude-plugin/
│   └── plugin.json        ← references kicad-jlcpcb-skills
├── hardware/
│   └── kicad/             ← output of generator (empty at bootstrap)
├── scripts/
│   ├── generate_schematics/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── config.py      ← GPIO_NETS, ESP_PINS skeleton
│   ├── generate_pcb/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── board.py       ← BOARD_W, BOARD_H placeholders
│   │   ├── routing.py     ← empty trace list
│   │   └── config.py
│   ├── verify_dfm_v2.py   ← 115 DFM tests (copy from kicad-jlcpcb-skills)
│   └── verify_dfa.py      ← 9 DFA tests
├── release_jlcpcb/        ← output of /release-pcb
├── CLAUDE.md              ← project-specific instructions
└── README.md
```

## Bootstrap steps

1. **Install the plugin**
   ```bash
   # From Claude Code:
   /plugin marketplace add pjcau/esp32-emu-turbo
   /plugin install kicad-jlcpcb-skills
   ```

2. **Scaffold the Python generator**
   - Copy `scripts/generate_schematics/` and `scripts/generate_pcb/` templates from the reference repo
   - Edit `config.py` with your project's GPIO assignments
   - Edit `board.py` with your board dimensions

3. **Configure hooks**
   - Copy `.claude/settings.json` hooks section from the reference repo
   - Ensures DFM verification runs automatically after PCB changes

4. **First design pass**
   - Run `/design-pcb` to define schematic + board + components + routing
   - Run `/generate-pcb` to emit KiCad files
   - Run `/verify-pcb` to confirm DFM baseline

5. **Establish DFM baseline**
   - Run `/verify` once on empty/initial state → records 0 violations baseline
   - All subsequent runs will fail on any new violation

6. **First release**
   - When initial design is stable, run `/release-pcb` to generate the JLCPCB package

## Requirements

Before bootstrapping, ensure you have:

- **KiCad 10+** (for `kicad-cli` native DRC and gerber export)
- **Python 3.11+** (for generator scripts)
- **OrbStack** or **Docker Desktop** (for zone fill via pcbnew Python API)
- **Claude Code** with `kicad-jlcpcb-skills` plugin installed

## After bootstrap

Read `docs/lifecycle.md` for the full design → release workflow, and `docs/skill-anatomy.md` for how to author custom skills on top of the base suite.

## Critical rules

- Never start designing without first committing the bootstrap state — it establishes the DFM baseline.
- Always use the Python generator pipeline — never edit `.kicad_pcb` files directly.
- Configure `.claude/settings.json` hooks BEFORE running `/design-pcb` the first time.
