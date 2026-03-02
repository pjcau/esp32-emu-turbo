---
name: create-skill
description: Create a new Claude Code skill for this project. Use when you need to add a new skill, improve an existing skill, or convert a workflow into a reusable skill.
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, WebSearch
---

# Create Skill

Create new Claude Code skills following the project's conventions and Anthropic best practices.

## Important

- Read `.claude/skills/skill-guidelines.md` first for writing conventions
- All content in English (project convention)
- Follow existing skill patterns in `.claude/skills/`

## Steps

### 1. Understand the Intent

Ask or determine:
1. What should this skill enable Claude to do?
2. When should this skill trigger? (what user phrases/contexts)
3. What's the expected output format?
4. Which agent should own this skill? (pcb-engineer, software-dev, cad-engineer, or standalone)

### 2. Research Existing Patterns

```bash
# Check existing skills for patterns
ls -la .claude/skills/
# Read a similar skill for reference
cat .claude/skills/<similar>/SKILL.md
# Read the guidelines
cat .claude/skills/skill-guidelines.md
```

### 3. Create the Skill

```bash
mkdir -p .claude/skills/<skill-name>
```

Write `SKILL.md` with:
- YAML frontmatter (name, description, allowed-tools)
- Clear numbered steps
- Bash commands with project-root `cd`
- Error handling ("if X fails, do Y")
- Key Files section at the bottom

### 4. Register with Agent (if applicable)

Add the skill name to the agent's `skills:` list in `.claude/agents/<agent>.md`.

### 5. Update Documentation

- Update CLAUDE.md skills count and table
- Update `website/docs/claude-agents.md` (skills table + Mermaid graph)

### 6. Test

Invoke the skill: `/<skill-name>` and verify it works end-to-end.

## Skill Template

```markdown
---
name: my-skill
description: What it does + when to use it + key capabilities
disable-model-invocation: true
allowed-tools: Bash, Read, Grep, Glob
---

# Skill Title

Brief description of what this skill does.

## Steps

### 1. First Step

\`\`\`bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
command here
\`\`\`

### 2. Second Step

...

## Key Files

- `path/to/file` — Description
```

## Key Files

- `.claude/skills/skill-guidelines.md` — Writing conventions
- `.claude/skills/` — All existing skills
- `.claude/agents/` — Agent definitions (to register skills)
- `CLAUDE.md` — Project documentation (skills map)
