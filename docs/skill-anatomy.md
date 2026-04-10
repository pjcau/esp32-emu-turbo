# Skill Anatomy

How to write Claude Code skills for the `kicad-jlcpcb-skills` plugin (and any fork).

> **Inspiration & credits**: The plugin layout of this project is heavily inspired by
> [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), the first
> production-grade Claude Code skill suite with `.claude-plugin/` packaging. We adopted
> their flat-`skills/` layout, `plugin.json` + `marketplace.json` convention, and
> lifecycle-based slash commands pattern. Our domain (hardware/PCB) is different but
> the discoverability and packaging mechanics are the same.

## Official references

- [The Complete Guide to Building Skills for Claude (PDF)](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf)
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Agent Skills Quickstart](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/quickstart)
- [Official Skills Repo (anthropics/skills)](https://github.com/anthropics/skills)
- [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) — reference for plugin packaging

## Skill folder structure

Skills live flat under `.claude/skills/`. No nested category folders — grouping exists only
in `.claude/README.md` and in the lifecycle slash commands under `.claude/commands/`.

```
.claude/skills/
├── generate/
│   └── SKILL.md           # required — main instructions
├── verify/
│   ├── SKILL.md
│   └── references/        # optional — loaded on demand
│       └── failure-categories.md
├── pcb-review/
│   ├── SKILL.md
│   └── review-checklist.md  # optional — reference doc at same level
└── dfm-fix/
    ├── SKILL.md
    └── dfm-reference.md
```

Three conventions for supporting files:

1. **None** — most skills have only `SKILL.md` (this is the default).
2. **`references/` subdirectory** — for multiple reference docs loaded on demand (see `verify/`).
3. **Flat adjacent files** — for one supporting doc (see `pcb-review/review-checklist.md`).

Use whichever fits. Don't mix styles inside the same skill.

## YAML frontmatter

Every `SKILL.md` must start with a YAML frontmatter block:

```yaml
---
name: skill-name                    # kebab-case, must match directory name
description: What it does + when to use it + key capabilities (max 1024 chars)
disable-model-invocation: true      # (optional) prevents Claude from auto-invoking
allowed-tools: Bash, Read, Edit, Grep, Glob    # (optional) restrict tools
argument-hint: <expected argument>  # (optional) shown in slash command UI
---
```

### Field semantics

| Field | Required | Purpose |
|---|---|---|
| `name` | ✅ | Must equal the directory name (enforced by `scripts/validate_skills.py`) |
| `description` | ✅ | Used by Claude Code to decide when to activate the skill. Write it in third person: *"Does X. Use when Y. Supports Z."* Max 1024 chars. |
| `disable-model-invocation` | ❌ | When `true`, the skill is only invokable via `/skill-name` (user-initiated). Used for expensive or destructive skills. |
| `allowed-tools` | ❌ | Restricts which tools the skill may call. Omit for unrestricted. |
| `argument-hint` | ❌ | Placeholder shown in the slash-command UI (e.g. `<version>`). |

### Why we use `disable-model-invocation: true` on most skills

addyosmani/agent-skills omits this field entirely — their skills activate automatically
whenever the description matches the user's intent. We take a stricter stance for the
PCB domain because many of our skills have side effects that cost money or break builds:

- `/release-pcb` commits + pushes → reversibility cost
- `/generate-pcb` rewrites `.kicad_pcb` → can mask subtle bugs if run at wrong time
- `/dfm-fix` edits the routing file → must be done deliberately

User-initiated invocation (via `/` slash commands) is safer for these. Read-only skills
(like `/doc` or `/jlcpcb-parts`) may omit `disable-model-invocation` if you want Claude
to auto-trigger them.

## Description writing rules

The description is the most important field. Claude Code uses it to decide when to
activate the skill. Follow addyosmani's pattern (see their
[docs/skill-anatomy.md](https://github.com/addyosmani/agent-skills/blob/main/docs/skill-anatomy.md)):

1. **Third person "what"** — "Runs the full DFM verification suite on the PCB."
2. **"Use when…" triggers** — "Use when PCB files change, before releases, or when investigating manufacturing issues."
3. **Avoid workflow summaries** — let the agent read the body. Don't say "Runs step A, then step B, then step C."
4. **Be slightly pushy** — "Use whenever you touch `hardware/kicad/`" beats "May be useful for PCB checks."
5. **Max 1024 characters**. Over that and Claude Code truncates.

### Examples

BAD:
```yaml
description: Run DFM checks
```
Too terse — Claude can't decide when to trigger.

BAD:
```yaml
description: First runs verify_dfm_v2.py, then verify_dfa.py, then checks the results and reports any violations found during the process.
```
Workflow summary — wastes the 1024-char budget describing *how*, not *when*.

GOOD:
```yaml
description: Run the complete DFM and DFA verification suite for the PCB (115 DFM tests + 9 DFA tests + JLCPCB rules). Use whenever PCB files change, before releases, or when investigating manufacturing issues. Reports violations with file:line references for quick fixes.
```
States *what*, *when*, and *what to expect* in under 300 chars.

## Skill body structure

After the frontmatter, follow this section order (adapted from `addyosmani/agent-skills`):

```markdown
# Skill Name

One-sentence purpose.

## Overview                  (optional — only if the skill is complex)

Context and problem it solves.

## Steps                     (required — the core procedure)

1. Step one — specific, actionable, with command examples
2. Step two
...

## When to use               (optional — if description isn't enough)

Trigger cases beyond the frontmatter description.

## Critical rules            (required if skill has side effects)

Bullet list of MUST and MUST NOT constraints.

## Error handling            (optional — what to do when steps fail)

## Examples                  (optional — common scenarios and expected output)
```

Keep `SKILL.md` under **5000 words**. Move anything longer to `references/`.

## Progressive disclosure

Claude Code loads skill content in three tiers:

1. **Always loaded**: frontmatter (name + description) of every skill
2. **Loaded on invocation**: the full `SKILL.md` body of the invoked skill
3. **Loaded on demand**: files referenced inside `SKILL.md` (e.g. `references/patterns.md`)

Use tier 3 aggressively for long reference material — it keeps the context window small
during skill selection, and Claude will pull them in only when needed.

## Anti-patterns

- ❌ Don't create `README.md` inside skill folders — use `SKILL.md`. The only exception is the
  top-level `.claude/README.md` which indexes all skills.
- ❌ Don't put "when to use" in the body — it belongs in the frontmatter description.
- ❌ Don't make skills too broad — split by concern. `/verify-pcb` orchestrates, the individual
  `/verify`, `/drc-native`, `/jlcpcb-validate` skills each do one thing.
- ❌ Don't hardcode absolute paths — use repo-relative paths. Plugin consumers have different roots.
- ❌ Don't duplicate logic across skills — extract shared behavior to a Python script and call it.

## Project conventions

- All content in **English**. No Italian or any other language in skill files.
- Commit messages in English with Conventional Commits prefix (`docs(skills):`, `feat(skills):`).
- Never silence failing tests — see `memory/feedback_never_silence_errors.md`.
- Every fix must have a guard test — if a skill adds a fix, add a test in `scripts/verify_dfm_v2.py`.

## Related docs

- `docs/lifecycle.md` — the 5-phase PCB lifecycle (design → generate → verify → fix → release)
- `docs/getting-started.md` — how to install and use the plugin
- `.claude/README.md` — index of all 43 skills in this project
