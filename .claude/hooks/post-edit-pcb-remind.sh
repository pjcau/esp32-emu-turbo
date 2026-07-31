INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

MSG=""

if echo "$FILE_PATH" | grep -q "scripts/generate_pcb/"; then
  FILENAME=$(basename "$FILE_PATH")
  MSG="You edited ${FILENAME}. Remember to regenerate the PCB: python3 -m scripts.generate_pcb hardware/kicad"
fi

# Component-set changes invalidate EVERY render, not just the copper
# checks. The R25 respin trio (2026-07-31) shipped with the PCBA
# raytraced renders 5 days stale and the iBOM missing the new nets —
# nothing reminded anyone, because the render pipeline lives only in
# .claude/skills/full-release/SKILL.md. This arm closes that gap.
#
# Files that can add/remove/move a component or its footprint:
if echo "$FILE_PATH" | grep -qE '(footprints\.py|jlcpcb_export\.py|generate_pcb/board\.py|routing/_shared\.py|bom\.csv|cpl\.csv|inject-3d-models\.py)'; then
  [ -n "$MSG" ] && MSG="${MSG}\n\n"
  MSG="${MSG}Component set may have changed ($(basename "$FILE_PATH")). If parts were added/removed/moved, ALL renders are now stale — the full list (from .claude/skills/full-release/SKILL.md + pcba-render):\n"
  MSG="${MSG}  1. make render-pcb                       (PCB SVG/PNG/GIF)\n"
  MSG="${MSG}  2. /pcba-render                          (11 raytraced views; new footprints need a MODEL_MAP entry in scripts/inject-3d-models.py first)\n"
  MSG="${MSG}  3. scripts/generate_ibom.sh --force      (also auto-runs at Stop via stop-regen-ibom.sh)\n"
  MSG="${MSG}  4. make docs-bom                         (docs BOM table; new LCSC ids need a role in scripts/generate_docs_bom.py)\n"
  MSG="${MSG}  5. make render-schematics                (if the schematic changed too)"
fi

if [ -n "$MSG" ]; then
  printf '{"systemMessage": "%s"}\n' "$MSG"
fi

exit 0
