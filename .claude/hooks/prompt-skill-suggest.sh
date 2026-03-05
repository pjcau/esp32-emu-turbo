#!/usr/bin/env bash
# prompt-skill-suggest.sh
# UserPromptSubmit hook: analyzes user prompt and suggests relevant skills.
# Inspired by ChrisWiles/claude-code-showcase skill-eval pattern.
# Adapted to bash (no Node.js dependency) for our hardware/PCB project.
#
# Input: JSON on stdin with { "prompt": "..." }
# Output: Skill suggestion on stdout (injected into Claude's context)
# Exit: Always 0

set -euo pipefail

INPUT=$(cat 2>/dev/null || true)
[ -z "$INPUT" ] && exit 0

# Extract prompt text
PROMPT=""
if command -v jq >/dev/null 2>&1; then
    PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || true)
else
    exit 0
fi

[ -z "$PROMPT" ] && exit 0

# Convert to lowercase for matching
PROMPT_LC=$(echo "$PROMPT" | tr '[:upper:]' '[:lower:]')

SUGGESTIONS=""

# --- PCB Pipeline skills ---
if echo "$PROMPT_LC" | grep -qE '\b(generate|regenerate|gen)\b.*\b(pcb|board)\b|\bgenerate\b'; then
    SUGGESTIONS="$SUGGESTIONS /generate (full PCB generation),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(release|package|jlcpcb.*export|gerber)\b'; then
    SUGGESTIONS="$SUGGESTIONS /release (JLCPCB package export),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(render|svg|animation|visual)\b.*\b(pcb|board)\b'; then
    SUGGESTIONS="$SUGGESTIONS /render (SVG + animation),"
fi
if echo "$PROMPT_LC" | grep -qE '\bdrc\b|\bdesign.rule\b'; then
    SUGGESTIONS="$SUGGESTIONS /drc-native (KiCad DRC + baseline),"
fi

# --- DFM & Verification skills ---
if echo "$PROMPT_LC" | grep -qE '\b(verify|verification|dfm|check)\b.*\b(pcb|board|pad|trace|manufacturing)\b'; then
    SUGGESTIONS="$SUGGESTIONS /verify (64 DFM tests),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(fix|repair|resolve)\b.*\b(dfm|pad|spacing|clearance|violation)\b'; then
    SUGGESTIONS="$SUGGESTIONS /dfm-fix (fix DFM issues),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(pad|spacing|distance|clearance)\b.*\b(analy|check|review)\b'; then
    SUGGESTIONS="$SUGGESTIONS /pad-analysis (pad spacing check),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(rotation|cpl|orient)\b'; then
    SUGGESTIONS="$SUGGESTIONS /fix-rotation (CPL rotation fix),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(alignment|align|batch.*pin|pin.*align)\b'; then
    SUGGESTIONS="$SUGGESTIONS /jlcpcb-alignment (batch pin alignment),"
fi

# --- Component & BOM skills ---
if echo "$PROMPT_LC" | grep -qE '\b(bom|bill.*material|component|lcsc|part)\b.*\b(search|find|check|list)\b'; then
    SUGGESTIONS="$SUGGESTIONS /jlcpcb-parts (BOM + LCSC search),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(3d|alignment|jlcpcb.*check|check.*jlcpcb)\b'; then
    SUGGESTIONS="$SUGGESTIONS /jlcpcb-check (3D alignment check),"
fi

# --- Design skills ---
if echo "$PROMPT_LC" | grep -qE '\b(schematic|net|symbol)\b'; then
    SUGGESTIONS="$SUGGESTIONS /pcb-schematic (schematic ops),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(place|placement|component.*position|move.*component)\b'; then
    SUGGESTIONS="$SUGGESTIONS /pcb-components (placement),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(route|routing|trace|wire|via)\b'; then
    SUGGESTIONS="$SUGGESTIONS /pcb-routing (traces + vias),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(footprint|pad.*def|land.*pattern)\b'; then
    SUGGESTIONS="$SUGGESTIONS /pcb-library (footprints),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(board.*setup|outline|stackup|layer)\b'; then
    SUGGESTIONS="$SUGGESTIONS /pcb-board (board setup),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(optimize|layout|improve)\b.*\b(pcb|board|placement)\b'; then
    SUGGESTIONS="$SUGGESTIONS /pcb-optimize (layout analysis),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(review|score|audit)\b.*\b(pcb|board|design)\b'; then
    SUGGESTIONS="$SUGGESTIONS /pcb-review (6-domain scored review),"
fi

# --- Firmware skills ---
if echo "$PROMPT_LC" | grep -qE '\b(firmware|build|flash|esp-idf|compile)\b'; then
    SUGGESTIONS="$SUGGESTIONS /firmware-build (build + flash),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(sync|gpio|pin.*map)\b.*\b(firmware|software|board_config)\b'; then
    SUGGESTIONS="$SUGGESTIONS /firmware-sync (GPIO sync check),"
fi

# --- Website skills ---
if echo "$PROMPT_LC" | grep -qE '\b(website|docusaurus|docs|deploy|page)\b'; then
    SUGGESTIONS="$SUGGESTIONS /website-dev (Docusaurus website),"
fi

# --- Enclosure skills ---
if echo "$PROMPT_LC" | grep -qE '\b(enclosure|case|housing|openscad|3d.*print)\b'; then
    SUGGESTIONS="$SUGGESTIONS /enclosure-design (parametric design),"
fi
if echo "$PROMPT_LC" | grep -qE '\b(stl|export|print)\b.*\b(enclosure|case)\b'; then
    SUGGESTIONS="$SUGGESTIONS /enclosure-export (STL export),"
fi

# --- Pipeline resume ---
if echo "$PROMPT_LC" | grep -qE '\b(resume|continue|retry)\b.*\b(pipeline|generate|release)\b|\bpipeline.*fail'; then
    SUGGESTIONS="$SUGGESTIONS /pipeline-resume (resume failed pipeline),"
fi

# --- Scout ---
if echo "$PROMPT_LC" | grep -qE '\b(scout|discover|search.*pattern|find.*skill)\b'; then
    SUGGESTIONS="$SUGGESTIONS /scout (pattern discovery),"
fi

# Output suggestion if any skills matched
if [ -n "$SUGGESTIONS" ]; then
    # Remove trailing comma
    SUGGESTIONS=$(echo "$SUGGESTIONS" | sed 's/,$//')
    echo "[Skill Hint] Relevant skills for this task:$SUGGESTIONS"
fi

exit 0
