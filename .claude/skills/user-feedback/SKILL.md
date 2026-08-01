---
name: user-feedback
model: claude-opus-5
description: Record user feedback, preferences, and rules — automatically distribute to the right agents, skills, and memory files
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Grep, Glob
argument-hint: <user feedback in natural language>
---

# User Feedback Processor

Takes user feedback, preferences, or rules and intelligently distributes them to the correct locations.

**Argument**: The user's feedback or rule in natural language: `$ARGUMENTS`

## Steps

### 1. Understand the feedback

Parse the user's input and classify it:

Memory rule (matches how the store actually works now): behavioral feedback
becomes a `feedback_*` memory FILE (frontmatter + **Why** + **How to
apply**) plus a ≤300-char hook line in MEMORY.md's "How I work here" —
never a paragraph pasted into the index. MEMORY.md's real sections are:
NOW / How I work here / Hardware invariants / DFM constraints / Where
things are. `make verify-memory` gates the result (hook ceiling, links,
titles).

| Category | Target Files |
|----------|-------------|
| **Project convention** | `CLAUDE.md`; if not repo-derivable, a memory + hook in "How I work here" |
| **DFM/PCB rule** | MEMORY.md "DFM constraints" hook, `.claude/skills/dfm-fix/dfm-reference.md` |
| **Agent behavior** | agent definition in `.claude/agents/`; behavioral lesson → `feedback_*` memory |
| **Workflow preference** | `feedback_*` memory + hook in "How I work here", `memory/session-guide.md` |
| **Tool/Docker rule** | relevant skill SKILL.md files; a memory hook only if not repo-derivable |
| **Skill improvement** | The specific skill's SKILL.md in `.claude/skills/<name>/` |
| **Build/deploy rule** | `Makefile`, `docker-compose.yml`; a memory hook only if not repo-derivable |

### 2. Read current state of target files

Read all files that need updating to avoid duplicates or contradictions.

### 3. Apply the feedback

For each target file:
1. Check if a similar rule already exists → update it instead of duplicating
2. Add the new rule in the appropriate section
3. If the rule contradicts an existing one → replace the old one

### 4. Propagate to skills

If the feedback affects how skills work, update the relevant SKILL.md files:

```bash
# Find skills that might be affected
grep -rl "keyword_from_feedback" .claude/skills/*/SKILL.md
```

Update each affected skill's instructions.

### 5. Propagate to agents

If the feedback affects agent behavior, update the agent definition:

```bash
ls .claude/agents/*.md
```

Add the rule to the agent's system prompt or instructions.

### 6. Summary

Print what was updated:

| File | Change |
|------|--------|
| `memory/MEMORY.md` | Added rule: "..." |
| `.claude/skills/check/SKILL.md` | Updated Docker requirement |
| `.claude/agents/pcb-engineer.md` | Added anti-stall rule |

## Examples

**Input**: "tutti i comandi devono passare per docker"
- → hook in MEMORY.md "How I work here": "ALL commands via Docker"
- → `.claude/skills/check/SKILL.md`: replace `kicad-cli` with `docker compose run`
- → `.claude/skills/release/SKILL.md`: ensure all steps use Docker
- → `.claude/skills/drc-native/SKILL.md`: use Docker for DRC

**Input**: "non voglio regressioni, ogni fix deve avere un test"
- → `feedback_*` memory + hook in "How I work here": "No regressions — every fix must have a guard test"
- → `.claude/skills/dfm-fix/SKILL.md`: add step "Add regression test for each fix"

**Input**: "gli agenti non devono stallare, max 3 tentativi"
- → `feedback_*` memory + hook in "How I work here"
- → `.claude/agents/pcb-engineer.md`: add anti-stall protocol
- → `.claude/agents/team-lead.md`: add monitoring rules
