---
id: ecosystem-analysis
title: KiCad + JLCPCB Ecosystem Analysis
sidebar_position: 3
---

# KiCad + JLCPCB Ecosystem Analysis

Comparative analysis of open-source tools, MCP servers, Claude Code skills, and CI/CD pipelines for PCB design with KiCad and JLCPCB manufacturing. Conducted April 2026.

---

## Our Position

ESP32 Emu Turbo has the **most advanced Claude Code + KiCad integration** found on GitHub:

| Metric | Our Project | Best Alternative |
|--------|------------|-----------------|
| Claude Code PCB skills | **43** | 10 (atopile-agent-skill) |
| DFM verification tests | **115** | 0 (no comparable suite) |
| KiCad MCP tools | **64** | 28 (Seeed-Studio) |
| Automated checks per commit | **1150+** (DFM+DFA+electrical+adversarial+design intent) | ~10 (KiBot DRC) |

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
| [kicad-mcp-server (Seeed)](https://github.com/Seeed-Studio/kicad-mcp-server) | 28 | MCP server for KiCad using pcbnew API. Has `CLAUDE.md` | Compare 28 tools vs our 64 |
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

### Seeed-Studio/kicad-mcp-server vs Our MCP Tools

| Aspect | Seeed-Studio | Our Project |
|--------|-------------|-------------|
| API approach | pcbnew Python API (live KiCad) | S-expression parsing (standalone) |
| Tool count | 28 | 64 |
| Requires running KiCad | Yes | No |
| Schematic access | Yes (eeschema) | Yes (custom parser) |
| PCB edit capability | Yes (live edit) | Yes (generator-based) |
| DFM verification | Basic DRC | 115 custom tests + JLCPCB rules |
| Claude integration | CLAUDE.md only | 39 skills + 5 agents + hooks |

**Takeaway**: Their pcbnew API approach gives real-time editing but requires a running KiCad instance. Our S-expression parser is standalone and CI-friendly. Consider adding pcbnew API as a secondary path for interactive design sessions.

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

### Short-term (integrate now)

1. **InteractiveHtmlBom** — Add to website for visual BOM inspection during prototyping
2. **agausmann/jlcpcb-kicad-drc** — Cross-reference their DRC rules against our 115 tests to find gaps
3. **JLC2KiCad_lib** — Add LCSC→footprint lookup to `/jlcpcb-parts` skill

### Medium-term (next release cycle)

4. **KiBot + GitHub Actions** — Automate gerber generation and DRC on every push
5. **kicad-diff-visualizer** — Add visual PCB diffs to PR reviews
6. **Seeed-Studio MCP server** — Study pcbnew API for live editing mode

### Long-term (v2 planning)

7. **Package skills as `.claude-plugin/`** — Following atopile-agent-skill format for distribution
8. **Contribute to KiBot** — Add our JLCPCB DFM rules as a KiBot plugin
9. **MCP server consolidation** — Merge our 64 tools with the emerging MCP standard

---

## Conclusion

The ESP32 Emu Turbo project has built the most comprehensive AI-assisted PCB design pipeline in the open-source ecosystem. With 43 Claude Code skills, 115 DFM tests, 1150+ automated checks, and 64 MCP tools, it significantly exceeds any other project found on GitHub. The main gap is CI/CD automation (KiBot) and plugin distribution (`.claude-plugin/` format).
