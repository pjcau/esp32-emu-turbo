---
id: ecosystem-analysis
title: KiCad + JLCPCB Ecosystem Analysis
sidebar_position: 3
---

# KiCad + JLCPCB Ecosystem Analysis

Comparative analysis of open-source tools, MCP servers, Claude Code skills, and CI/CD pipelines for PCB design with KiCad and JLCPCB manufacturing. Originally conducted 2026-04-09, updated 2026-04-10.

---

## Our Position

ESP32 Emu Turbo has the **most advanced Claude Code + KiCad integration** found on GitHub:

| Metric | Our Project | Best Alternative |
|--------|------------|-----------------|
| Claude Code skills total | **43** (27 PCB + 4 firmware + 3 CAD + 9 others) | 10 (atopile-agent-skill) |
| DFM verification tests | **115** | 0 (no comparable suite) |
| MCP server | None — studied [mixelpixx/KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server) (64 tools) and mapped them to our skills | 28 (Seeed-Studio) |
| Automated checks per commit | **1150+** (DFM+DFA+electrical+adversarial+design intent) | ~10 (KiBot DRC) |

:::info
We do **not** currently run an MCP server. Our pipeline is based on Python scripts, S-expression parsing, and Claude Code skills. The 64-tool inventory in `memory/kicad-mcp-tools.md` is a **reference mapping** of mixelpixx's MCP tools onto our equivalent skills — not an indication we expose 64 MCP tools ourselves. See the ["MCP server consolidation"](#long-term-v2-planning) long-term plan.
:::

---

## Top Tools by Category

### JLCPCB Integration

| Tool | Stars | What It Does | Value for Us |
|------|-------|-------------|--------------|
| [kicad-jlcpcb-tools](https://github.com/Bouni/kicad-jlcpcb-tools) | 1,831 | KiCad plugin: BOM+CPL+LCSC lookup, parts database | Compare with our `/jlcpcb-parts` skill |
| [JLC-Plugin-for-KiCad](https://github.com/bennymeg/JLC-Plugin-for-KiCad) | 604 | JLCPCB fabrication output from KiCad | Compare with our `/release` skill |
| [JLCPCB-Kicad-Library](https://github.com/CDFER/JLCPCB-Kicad-Library) | 480 | Footprint/symbol library for JLCPCB parts | Reduce footprint mismatches |
| [JLC2KiCad_lib](https://github.com/TousstNicolas/JLC2KiCad_lib) | 342 | Generate KiCad footprints from LCSC part number | Enhance `/jlcpcb-parts` |
| [jlcpcb-kicad-drc](https://github.com/agausmann/jlcpcb-kicad-drc) | 2 | JLCPCB design rules as `.kicad_dru` | Cross-reference our 115 tests |

### KiCad Automation & CI/CD

| Tool | Stars | What It Does | Value for Us |
|------|-------|-------------|--------------|
| [KiBot](https://github.com/INTI-CMNB/KiBot) | 704 | Swiss army knife: DRC, gerber, BOM, 3D, PDF | Could simplify Docker pipeline |
| [KDT_Hierarchical_KiBot](https://github.com/nguyen-v/KDT_Hierarchical_KiBot) | 164 | CI/CD template with KiBot + GitHub Actions | Ready-made DRC-on-push workflow |
| [kicad-actions](https://github.com/actions-for-kicad/kicad-actions) | 17 | GitHub Action for KiCad checks | Lighter CI alternative |
| [kicad_auto](https://github.com/INTI-CMNB/kicad_auto) | 67 | Docker image for KiCad automation | Could replace our custom Docker |
| [InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom) | 4,350 | Interactive HTML BOM with visual overlay | Add to website for assembly |

### AI / MCP Servers for PCB

| Tool | Stars | What It Does | Value for Us |
|------|-------|-------------|--------------|
| [kicad-mcp-server (Seeed)](https://github.com/Seeed-Studio/kicad-mcp-server) | 28 | MCP server for KiCad using pcbnew API. Has `CLAUDE.md` | Reference for future MCP wrapping of our skills |
| [kicad-mcp-server (Huaqiu)](https://github.com/Huaqiu-Electronics/kicad-mcp-server) | 3 | MCP server from NextPCB manufacturer | Manufacturer-specific rules |
| [jlcmcp](https://github.com/hyl64/jlcmcp) | 19 | JLCPCB EDA MCP Server — 39 tools for EasyEDA | Study tool decomposition |
| [atopile-agent-skill](https://github.com/mawildoer/atopile-agent-skill) | 5 | **Only** hardware Claude Code skills package | Study `.claude-plugin/` format |
| [atopile](https://github.com/atopile/atopile) | 3,158 | "Design circuits with code" — code-first EDA | Alternative paradigm to KiCad |

### KiCad Plugins (Design Quality)

| Tool | Stars | What It Does | Value for Us |
|------|-------|-------------|--------------|
| [kicad-action-plugins](https://github.com/MitjaNemec/Kicad_action_plugins) | 418 | Replicate layout, place footprints, swap pins | Repetitive placement patterns |
| [kicad-action-scripts](https://github.com/jsreynaud/kicad-action-scripts) | 285 | Via stitching, teardrops, round tracks, length matching | Improve signal integrity |
| [kicad-auto-silkscreen](https://github.com/CGrassin/kicad-auto-silkscreen) | 31 | Auto-optimize silkscreen placement | Pre-manufacturing cleanup |
| [kicad-diff-visualizer](https://github.com/uchan-nos/kicad-diff-visualizer) | 63 | Visual diff between PCB versions | PR review for PCB changes |

---

## Deep Dive: Key Repos

### Seeed-Studio/kicad-mcp-server vs Our Pipeline

| Aspect | Seeed-Studio | Our Project |
|--------|-------------|-------------|
| Approach | MCP server over pcbnew Python API (live KiCad) | Claude Code skills + S-expression parsing (standalone) |
| Tool count | 28 MCP tools | 43 Claude Code skills (no MCP server) |
| Requires running KiCad | Yes | No |
| Schematic access | Yes (eeschema) | Yes (custom parser) |
| PCB edit capability | Yes (live edit) | Yes (generator-based, deterministic) |
| DFM verification | Basic DRC | 115 custom tests + JLCPCB rules |
| Claude integration | CLAUDE.md only | 43 skills + 5 agents + hooks |

**Takeaway**: Their pcbnew API approach gives real-time editing but requires a running KiCad instance. Our generator-based pipeline is standalone, CI-friendly, and fully deterministic. Wrapping our skills as an MCP server (tracked in [long-term plan](#long-term-v2-planning)) would complement — not replace — the generator pipeline.

### atopile-agent-skill — Claude Skills for Hardware

The only other hardware-focused Claude Code skills package. Structure:

```
.claude-plugin/
  marketplace.json    # Plugin metadata
  plugin.json         # Tool definitions
skills/
  agent/              # Agent coordination
  ato-language/       # Language reference
  code-review/        # Design review patterns
  fabll/              # Fabrication rules
  library/            # Component library
  lsp/                # Language server integration
```

**Takeaway**: Their `.claude-plugin/` format enables marketplace distribution. We should consider packaging our 43 PCB skills as a distributable plugin for other KiCad projects.

### KiBot — The Automation Standard

KiBot (704 stars) is the most mature KiCad automation tool. Comparison:

| Feature | KiBot | Our Pipeline |
|---------|-------|-------------|
| Gerber export | YAML config, 1 command | Docker + kicad-cli hybrid |
| DRC | Basic KiCad DRC | 115-test custom suite |
| BOM generation | Multiple formats | JLCPCB-specific with LCSC |
| 3D rendering | Blender/raytracer | kicad-cli raytracer (11 views) |
| CI/CD | First-class GitHub Actions | Custom hooks + Makefile |
| JLCPCB output | Supported | Native (custom export) |
| Setup complexity | YAML file | Python scripts + Docker |

**Takeaway**: KiBot could replace our Docker pipeline for gerber/BOM export, but our DFM test suite and JLCPCB-specific validation go far beyond what KiBot offers. Best approach: use KiBot for CI/CD gerber generation, keep our custom DFM tests.

---

## Recommendations

### Done — Short-term items completed 2026-04-09

All three short-term items were integrated within hours of this analysis being published:

| Item | Status | Commit |
|------|--------|--------|
| **InteractiveHtmlBom** on website for visual BOM inspection | ✅ Integrated | `b1660ba` — `feat(website): add InteractiveHtmlBom for visual assembly inspection` (+4717 lines); `7bb75b5` adds links from components/PCB docs |
| **agausmann/jlcpcb-kicad-drc** cross-reference against our 115 tests | ✅ Analyzed | `dbfd653` — `docs: add JLCPCB DRC gap analysis (6 threshold gaps found)` |
| **JLC2KiCad_lib** LCSC→footprint lookup in `/jlcpcb-parts` | ✅ Integrated (via EasyEDA API) | `0c69f32` — `feat(jlcpcb-parts): add LCSC footprint lookup via EasyEDA API` (+149 lines) |

### Next up — Medium-term (next release cycle)

1. **KiBot + GitHub Actions** — The KiBot config already exists at `hardware/kicad/external-dfm.kibot.yaml` and a Docker image at `docker/kibot/Dockerfile`. The missing piece is a `.github/workflows/` file to trigger DRC + gerber export on every push. This is the highest-leverage remaining gap.
2. **kicad-diff-visualizer** — Add visual PCB diffs to PR reviews.
3. **Seeed-Studio MCP server study** — Evaluate pcbnew API for an optional interactive editing mode alongside the generator pipeline.

### Long-term (v2 planning)

4. **Package skills as `.claude-plugin/`** — Following [atopile-agent-skill](https://github.com/mawildoer/atopile-agent-skill) format to distribute our 43 skills as a reusable plugin for other KiCad projects.
5. **Contribute to KiBot** — Upstream our JLCPCB DFM rules as a KiBot plugin.
6. **MCP server consolidation** — Wrap our skills as an MCP server so non–Claude-Code agents can consume them, complementing (not replacing) the generator pipeline.

---

## Conclusion

The ESP32 Emu Turbo project has built the most comprehensive AI-assisted PCB design pipeline in the open-source ecosystem. With **43 Claude Code skills**, **115 DFM tests**, and **1150+ automated checks per commit**, it significantly exceeds any other project found on GitHub. We do not currently ship an MCP server — our integration is skill-based — but the reference mapping in `memory/kicad-mcp-tools.md` shows our skill coverage matches or exceeds the 64-tool mixelpixx reference. The remaining gaps are **CI/CD automation** (KiBot + GitHub Actions) and **plugin distribution** (`.claude-plugin/` packaging).
