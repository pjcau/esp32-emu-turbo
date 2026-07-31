---
id: ecosystem-analysis
title: KiCad + JLCPCB Ecosystem Analysis
sidebar_position: 3
---

# KiCad + JLCPCB Ecosystem Analysis

Comparative analysis of open-source tools, MCP servers, Claude Code skills, and CI/CD pipelines for PCB design with KiCad and JLCPCB manufacturing. Originally conducted 2026-04-09, updated 2026-04-10. **Upstream refresh 2026-07-31** — stars/releases re-checked, two repos archived, KiBot container bumped to KiCad 10, CI workflow added (see [Done — July 2026](#done--upstream-refresh-integrated-2026-07-31)).

---

## Our Position

ESP32 Emu Turbo has the **most advanced Claude Code + KiCad integration** found on GitHub:

| Metric | Our Project | Best Alternative |
|--------|------------|-----------------|
| Claude Code skills total | **43** (27 PCB + 4 firmware + 3 CAD + 9 others) | 10 (atopile-agent-skill) |
| DFM verification tests | **124** (115 at the April analysis) | 0 (no comparable suite) |
| MCP server | None — studied [mixelpixx/KiCAD-MCP-Server](https://github.com/mixelpixx/KiCAD-MCP-Server) (64 tools in April; **171 tools as of v2.6.0, July 2026**) and mapped them to our skills | 28 (Seeed-Studio) |
| Automated checks per commit | **1150+** (DFM+DFA+electrical+adversarial+design intent) | ~10 (KiBot DRC) |

:::info
We do **not** currently run an MCP server. Our pipeline is based on Python scripts, S-expression parsing, and Claude Code skills. The 64-tool inventory in `memory/kicad-mcp-tools.md` is a **reference mapping** of mixelpixx's MCP tools onto our equivalent skills — not an indication we expose 64 MCP tools ourselves. See the ["MCP server consolidation"](#long-term-v2-planning) long-term plan.
:::

---

## Top Tools by Category

### JLCPCB Integration

| Tool | Stars | What It Does | Value for Us |
|------|-------|-------------|--------------|
| [kicad-jlcpcb-tools](https://github.com/Bouni/kicad-jlcpcb-tools) | 1,993 | KiCad plugin: BOM+CPL+LCSC lookup, parts database | Compare with our `/jlcpcb-parts` skill |
| [JLC-Plugin-for-KiCad](https://github.com/bennymeg/JLC-Plugin-for-KiCad) | 657 | JLCPCB fabrication output from KiCad (v5.3.1, May 2026) | Compare with our `/release` skill |
| [JLCPCB-Kicad-Library](https://github.com/CDFER/JLCPCB-Kicad-Library) | 544 | Footprint/symbol library for JLCPCB parts (monthly releases) | Reduce footprint mismatches |
| [JLC2KiCad_lib](https://github.com/TousstNicolas/JLC2KiCad_lib) | 462 | Generate KiCad footprints from LCSC part number | Enhance `/jlcpcb-parts` |
| [jlcpcb-kicad-drc](https://github.com/agausmann/jlcpcb-kicad-drc) | 2 | JLCPCB design rules as `.kicad_dru` (dormant since 2022) | Cross-referenced against our DFM suite (done, April 2026) |

### KiCad Automation & CI/CD

| Tool | Stars | What It Does | Value for Us |
|------|-------|-------------|--------------|
| [KiBot](https://github.com/INTI-CMNB/KiBot) | 728 | Swiss army knife: DRC, gerber, BOM, 3D, PDF (**v1.9.1, July 2026 — KiCad 10 support**) | In use — `docker/kibot` + CI workflow |
| [KDT_Hierarchical_KiBot](https://github.com/nguyen-v/KDT_Hierarchical_KiBot) | 195 | CI/CD template with KiBot + GitHub Actions | Ready-made DRC-on-push workflow |
| [kicad-actions](https://github.com/actions-for-kicad/kicad-actions) | 24 | GitHub Action for KiCad checks (**v2.5-k10.0 — KiCad 10**) | Lighter CI alternative |
| [kicad_auto](https://github.com/INTI-CMNB/kicad_auto) | 70 | Docker image for KiCad automation | In use — `kicad10_auto` is our KiBot base image |
| [InteractiveHtmlBom](https://github.com/openscopeproject/InteractiveHtmlBom) | 4,489 | Interactive HTML BOM with visual overlay (v2.11.2, May 2026) | In use — `/ibom` on the website |

### AI / MCP Servers for PCB

| Tool | Stars | What It Does | Value for Us |
|------|-------|-------------|--------------|
| [kicad-mcp-server (Seeed)](https://github.com/Seeed-Studio/kicad-mcp-server) | 70 | MCP server for KiCad using pcbnew API. Has `CLAUDE.md` | Reference for future MCP wrapping of our skills |
| [kicad-mcp-server (Huaqiu)](https://github.com/Huaqiu-Electronics/kicad-mcp-server) | 3 | MCP server from NextPCB manufacturer — **archived April 2026** | No longer a reference |
| [jlcmcp](https://github.com/hyl64/jlcmcp) | 166 | JLCPCB EDA MCP Server — 39 tools for EasyEDA | Study tool decomposition |
| [atopile-agent-skill](https://github.com/mawildoer/atopile-agent-skill) | 9 | **Only** other hardware Claude Code skills package | `.claude-plugin/` format adopted (see long-term §4 — done) |
| [atopile](https://github.com/atopile/atopile) | 3,554 | "Design circuits with code" — code-first EDA | Alternative paradigm to KiCad |

### KiCad Plugins (Design Quality)

| Tool | Stars | What It Does | Value for Us |
|------|-------|-------------|--------------|
| [kicad-action-plugins](https://github.com/MitjaNemec/Kicad_action_plugins) | 419 | Replicate layout, place footprints, swap pins — **archived** | Historical reference only |
| [kicad-action-scripts](https://github.com/jsreynaud/kicad-action-scripts) | 292 | Via stitching, teardrops, round tracks, length matching | Improve signal integrity |
| [kicad-auto-silkscreen](https://github.com/CGrassin/kicad-auto-silkscreen) | 35 | Auto-optimize silkscreen placement | Pre-manufacturing cleanup |
| [kicad-diff-visualizer](https://github.com/uchan-nos/kicad-diff-visualizer) | 64 | Visual diff between PCB versions (inactive since Aug 2025) | Deprioritized — see medium-term §2 |

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
| DFM verification | Basic DRC | 124 custom tests + JLCPCB rules |
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

KiBot (728 stars, v1.9.1 with KiCad 10 support) is the most mature KiCad automation tool — and since July 2026 it is what our `docker/kibot` container and the `kibot-dfm.yml` CI workflow run. Comparison:

| Feature | KiBot | Our Pipeline |
|---------|-------|-------------|
| Gerber export | YAML config, 1 command | Docker + kicad-cli hybrid |
| DRC | Basic KiCad DRC | 124-test custom suite |
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

### Done — Upstream refresh integrated 2026-07-31

| Item | Status | Detail |
|------|--------|--------|
| **KiBot container: KiCad 9 → KiCad 10** | ✅ Integrated | `docker/kibot/Dockerfile` now builds on `ghcr.io/inti-cmnb/kicad10_auto` (KiBot 1.9.1 + KiCad 10.0.4), matching the local KiCad 10.0.0. The old KiCad 9 container could no longer load the schematic at all. |
| **KiBot + GitHub Actions** (was medium-term §1) | ✅ Integrated | `.github/workflows/kibot-dfm.yml` — board-side DRC + design report on every push touching `hardware/kicad/`, failing on DRC errors, reports uploaded as artifacts. |
| **InteractiveHtmlBom refresh** | ✅ Regenerated | `ibom.html` regenerated with upstream v2.11.2 (May 2026 release). |
| **`.claude-plugin/` packaging** (was long-term §4) | ✅ Shipped | `kicad-jlcpcb-skills` v1.0.0 (`.claude-plugin/plugin.json` + `marketplace.json`, commit `dd3d0d6`). |

:::warning Known blocker — non-IPC references
KiBot (≥ 1.6.5, [upstream #604](https://github.com/INTI-CMNB/KiBot/issues/604) — wontfix) rejects any schematic reference that is not `PREFIX+NUMBER`. Ours has **`SW_PWR`, `SW_BOOT`, `SW_RST`**, so the KiBot **schematic phase (ERC + BOM cross-check) is blocked** until they are renamed in the generator (e.g. `SW13`–`SW15` with descriptive `Value` fields). `scripts/external-dfm.sh` runs the board phase in isolation (works: DRC 0 errors) and reports this blocker as an explicit FAIL. Renaming touches schematic, PCB, BOM, CPL and docs — a deliberate design decision, not a quick fix.
:::

### Next up — Medium-term (next release cycle)

1. **Rename `SW_PWR`/`SW_BOOT`/`SW_RST` to IPC references** — unlocks KiBot ERC + BOM cross-check in `external-dfm.sh` and lets the CI workflow add `-e` (see blocker above).
2. **kicad-diff-visualizer** — Add visual PCB diffs to PR reviews. *Deprioritized: upstream inactive since Aug 2025.*
3. **Seeed-Studio MCP server study** — Evaluate pcbnew API for an optional interactive editing mode alongside the generator pipeline (repo active, 70 stars as of July 2026).

### Long-term (v2 planning)

4. **Contribute to KiBot** — Upstream our JLCPCB DFM rules as a KiBot plugin.
5. **MCP server consolidation** — Wrap our skills as an MCP server so non–Claude-Code agents can consume them, complementing (not replacing) the generator pipeline. Note: mixelpixx/KiCAD-MCP-Server grew from 64 to **171 tools** (v2.6.0, July 2026) and 1,695 stars — worth a fresh mapping pass against `memory/kicad-mcp-tools.md` before designing ours.

---

## Conclusion

The ESP32 Emu Turbo project has built the most comprehensive AI-assisted PCB design pipeline in the open-source ecosystem. With **43 Claude Code skills**, **124 DFM tests**, and **1150+ automated checks per commit**, it significantly exceeds any other project found on GitHub. We do not currently ship an MCP server — our integration is skill-based — and the mixelpixx reference has since grown to 171 tools (v2.6.0), so the `memory/kicad-mcp-tools.md` mapping needs a refresh before any MCP work. The two gaps named in April — **CI/CD automation** and **plugin distribution** — are both closed as of July 2026; the open items are the **non-IPC reference rename** (unblocks KiBot ERC) and the long-term MCP consolidation.
