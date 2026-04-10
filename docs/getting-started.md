# Getting Started with kicad-jlcpcb-skills

Install and use the `kicad-jlcpcb-skills` Claude Code plugin in your own PCB project.

> **Acknowledgments**: Plugin packaging, `.claude-plugin/` layout, and lifecycle slash
> command patterns are borrowed from
> [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills). If you want a
> general-purpose SDLC-focused skill suite (instead of hardware), check out their repo —
> it was the inspiration for ours.

## Requirements

- **Claude Code** ≥ 2.0 ([install guide](https://docs.anthropic.com/en/docs/claude-code))
- **KiCad 10+** with `kicad-cli` available on `$PATH`
- **Python 3.11+**
- **OrbStack** (recommended) or **Docker Desktop** — for zone fill and headless KiCad operations

Optional for renders:
- **Inkscape** — SVG post-processing
- **ffmpeg** — animation frame assembly

## Install the plugin

### Option A — from the Claude Code marketplace

```bash
# Inside Claude Code:
/plugin marketplace add pjcau/esp32-emu-turbo
/plugin install kicad-jlcpcb-skills
```

### Option B — clone and use directly

```bash
git clone https://github.com/pjcau/esp32-emu-turbo.git
cd esp32-emu-turbo
# Skills are already in place under .claude/skills/
# Commands are in .claude/commands/
claude code  # launches Claude Code in this directory
```

This is the recommended path if you want to customize the skills for your project.

## First-run checklist

Once the plugin is installed in a project, verify everything is wired correctly:

1. **List available skills**
   ```bash
   # Inside Claude Code:
   /skills
   ```
   You should see 27 PCB-related skills (plus any firmware/CAD skills local to your project).

2. **List available commands**
   ```bash
   ls .claude/commands/
   ```
   Expected: `design-pcb.md`, `generate-pcb.md`, `verify-pcb.md`, `fix-pcb.md`,
   `release-pcb.md`, `bootstrap-new-pcb.md`.

3. **Verify hooks are active**
   Check `.claude/settings.json` for the `Stop` hook that auto-runs DFM verification
   after PCB file changes. If missing, copy from the reference repo.

4. **Run a sanity check**
   ```bash
   # In Claude Code:
   /verify-pcb
   ```
   This should pass on the reference project (115 DFM + 9 DFA + 26 JLCPCB = 150 tests).

## Your first PCB with this plugin

Follow the 5-phase lifecycle ([`docs/lifecycle.md`](lifecycle.md)):

### 1. Bootstrap

```bash
/bootstrap-new-pcb
```

Scaffolds Python generator files, DFM baseline, and folder structure. Edit
`scripts/generate_schematics/config.py` with your project's GPIO assignments and
`scripts/generate_pcb/board.py` with your board dimensions.

### 2. Design

```bash
/design-pcb
```

Guides you through schematic, board outline, component placement, and routing.
All edits go to Python source files.

### 3. Generate

```bash
/generate-pcb
```

Emits `hardware/kicad/your-project.kicad_pcb` and runs quick checks.

### 4. Verify

```bash
/verify-pcb
```

Runs the full 150-test verification suite. Must pass with 0 failures.

### 5. Fix (if needed)

```bash
/fix-pcb
```

Applies targeted fixes. Loops back through Generate + Verify automatically.

### 6. Release

```bash
/release-pcb
```

Produces the JLCPCB package in `release_jlcpcb/` and commits + pushes.

## Project structure after bootstrap

```
your-project/
├── .claude/
│   ├── commands/          # lifecycle slash commands (6)
│   ├── skills/            # 27 PCB skills (from plugin)
│   ├── agents/            # optional custom agents
│   └── settings.json      # hooks and skill config
├── .claude-plugin/
│   └── plugin.json        # references kicad-jlcpcb-skills
├── hardware/
│   └── kicad/             # generated KiCad files (don't edit manually!)
├── scripts/
│   ├── generate_schematics/   # Python schematic generator
│   ├── generate_pcb/          # Python PCB generator
│   ├── verify_dfm_v2.py       # 115 DFM tests
│   └── verify_dfa.py          # 9 DFA tests
├── release_jlcpcb/        # final JLCPCB upload package
├── docs/                  # skill-anatomy, lifecycle, getting-started (this file)
├── CLAUDE.md              # project-specific instructions for Claude Code
└── README.md
```

## Common commands cheat sheet

| Goal | Command |
|---|---|
| Start a new PCB | `/bootstrap-new-pcb` |
| Design phase | `/design-pcb` |
| Regenerate after Python edits | `/generate-pcb` |
| Full verification | `/verify-pcb` |
| Fix DFM failures | `/fix-pcb` |
| Ship to JLCPCB | `/release-pcb` |
| Quick 5s check | `/check` |
| 3D photorealistic render | `/pcba-render` |
| LCSC part search | `/jlcpcb-parts` |
| Audit docs against source-of-truth | `/doc` (project-local) |

## Troubleshooting

### `kicad-cli` not found

Install KiCad 10+ and add it to `$PATH`. On macOS:
```bash
export PATH="/Applications/KiCad/KiCad.app/Contents/MacOS:$PATH"
```

### Docker zone fill fails

Check OrbStack or Docker Desktop is running. Test with:
```bash
docker run --rm kicad/kicad:latest kicad-cli version
```

### DFM tests fail on first run

Create a baseline by running `/verify` once — it records the current state. Subsequent
runs will only flag *new* violations.

### Hooks not firing

Edit `.claude/settings.json` and ensure the `Stop` hook runs `stop-verify-dfm.sh`:
```json
{
  "hooks": {
    "Stop": [
      { "command": "./.claude/hooks/stop-verify-dfm.sh" }
    ]
  }
}
```

## Next steps

- Read [`docs/lifecycle.md`](lifecycle.md) for a deep dive into the 5 phases
- Read [`docs/skill-anatomy.md`](skill-anatomy.md) to author your own skills on top of the base suite
- Browse [`.claude/README.md`](../.claude/README.md) for the full index of 43 skills
- Study the [reference project](https://github.com/pjcau/esp32-emu-turbo) to see a real 4-layer PCB built entirely with these skills

## License and credits

MIT License. Built on top of Anthropic's Claude Code skills framework.

Inspired by [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) — the
SDLC-focused skill suite that pioneered the `.claude-plugin/` packaging format. If you
want a general-purpose skills marketplace for non-hardware work, go check it out.
