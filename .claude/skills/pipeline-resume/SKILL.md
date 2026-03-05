---
name: pipeline-resume
description: Resume a failed PCB pipeline from the last successful checkpoint
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
argument-hint: [optional step to resume from, e.g. "verify" or "gerbers"]
---

# Pipeline Resume

Resume a previously failed PCB pipeline run from the last successful checkpoint,
instead of restarting from scratch. Saves time on long pipeline runs.

Adapted from J-louage/Gaia-framework checkpoint/resume pattern.

**Argument**: `$ARGUMENTS` (optional: step name to resume from)

## Phase 1: Read checkpoint state

```bash
cat /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo/.claude/pipeline-checkpoint.json 2>/dev/null || echo '{"status": "no_checkpoint"}'
```

If no checkpoint exists, inform the user and suggest running `/generate` or `/release-prep` instead.

## Phase 2: Determine resume point

The pipeline steps and their checkpoint names:

| Step | Checkpoint | Depends on |
|------|-----------|------------|
| 1. Generate PCB | `generate` | -- |
| 2. Zone fill | `zonefill` | generate |
| 3. Export gerbers | `gerbers` | zonefill |
| 4. DFM verification | `dfm_verify` | generate |
| 5. Copy to release | `release_copy` | gerbers + dfm_verify |
| 6. DFA verification | `dfa_verify` | release_copy |

If `$ARGUMENTS` specifies a step, resume from that step.
Otherwise, resume from the step AFTER the last successful checkpoint.

## Phase 3: Execute remaining steps

Run only the steps that have not completed. For each step:

1. Execute the step command (see commands below)
2. If it succeeds, update the checkpoint file
3. If it fails, stop and report (do NOT continue)

### Step commands

**generate**:
```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
python3 -m scripts.generate_pcb hardware/kicad
```

**zonefill**:
```bash
docker compose run --rm --entrypoint python3 kicad-pcb /scripts/kicad_fill_zones.py "/project/esp32-emu-turbo.kicad_pcb"
```

**gerbers** (prefer fast path):
```bash
./scripts/export-gerbers-fast.sh
```

**dfm_verify**:
```bash
python3 scripts/verify_dfm_v2.py
```

**release_copy**:
```bash
cp hardware/kicad/jlcpcb/bom.csv release_jlcpcb/bom.csv
cp hardware/kicad/jlcpcb/cpl.csv release_jlcpcb/cpl.csv
rm -rf release_jlcpcb/gerbers
cp -r hardware/kicad/gerbers release_jlcpcb/gerbers
cp hardware/kicad/jlcpcb/gerbers.zip release_jlcpcb/gerbers.zip 2>/dev/null || true
```

**dfa_verify**:
```bash
python3 scripts/verify_dfa.py
```

### Checkpoint file format

After each successful step, write:

```bash
cat > /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo/.claude/pipeline-checkpoint.json << 'CHECKPOINT'
{
  "pipeline": "release-prep",
  "last_success": "<step_name>",
  "completed": ["generate", "zonefill", ...],
  "timestamp": "<ISO 8601>",
  "pcb_sha": "<sha256 of .kicad_pcb>"
}
CHECKPOINT
```

## Phase 4: Summary

Report what was skipped (already done) and what was executed:

| Step | Status |
|------|--------|
| Generate PCB | Skipped (checkpoint) |
| Zone fill | Skipped (checkpoint) |
| Export gerbers | Resumed -- OK |
| DFM verify | Resumed -- 64/64 pass |
| Release copy | Resumed -- OK |
| DFA verify | Resumed -- 9/9 pass |

## Important Notes

- The checkpoint file is invalidated if `esp32-emu-turbo.kicad_pcb` SHA changes
  (meaning someone regenerated the PCB outside the pipeline)
- If the PCB SHA does not match, warn the user and suggest starting from `generate`
- The checkpoint file is NOT committed to git (add to .gitignore)

## Key Files

- Checkpoint: `.claude/pipeline-checkpoint.json`
- Generate skill: `.claude/skills/generate/SKILL.md`
- Release-prep skill: `.claude/skills/release-prep/SKILL.md`
