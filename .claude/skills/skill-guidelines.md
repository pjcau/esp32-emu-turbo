# Skill Writing Guidelines

Best practices for writing Claude Code skills in this project.
Sourced from official Anthropic docs + ondrasek/cc-plugins patterns.

## Official References

- [The Complete Guide to Building Skills for Claude (PDF)](https://resources.anthropic.com/hubfs/The-Complete-Guide-to-Building-Skill-for-Claude.pdf)
- [Claude Code Best Practices](https://www.anthropic.com/engineering/claude-code-best-practices)
- [Agent Skills Quickstart](https://docs.anthropic.com/en/docs/agents-and-tools/agent-skills/quickstart)
- [Official Skills Repo](https://github.com/anthropics/skills)

## Skill Folder Structure

```
skill-name/
├── SKILL.md           (required — main instructions)
└── references/        (optional — detailed docs loaded on demand)
    ├── patterns.md
    └── examples.md
```

## YAML Frontmatter (required)

```yaml
---
name: skill-name          # kebab-case, no spaces/underscores
description: What it does + when to use it + key capabilities
disable-model-invocation: true    # agent cannot self-invoke
allowed-tools: Bash, Read, Edit, Grep, Glob
argument-hint: <expected argument>  # optional
---
```

## Key Rules

1. **SKILL.md naming**: Must be exactly `SKILL.md` (case-sensitive)
2. **Skill folder naming**: kebab-case only
3. **Description formula**: `[What it does] + [When to use it] + [Key capabilities]`
4. **Keep SKILL.md under 5,000 words** — move detailed docs to `references/`
5. **Progressive disclosure**: frontmatter (always loaded) -> SKILL.md body (on invocation) -> references/ (on demand)
6. **Be specific and actionable** — use numbered steps, not vague instructions
7. **Critical instructions at top** — use `## Critical Rules` or `## Important`
8. **Include error handling** — what to do when steps fail
9. **Include examples** of common scenarios and expected outcomes
10. **All content in English** (project convention)

## Description Tips

Make descriptions slightly "pushy" to improve triggering accuracy:
- BAD: "Run DFM checks"
- GOOD: "Run the complete DFM and design verification suite for the PCB. Use this whenever PCB files change, before releases, or when investigating manufacturing issues."

## Anti-Patterns

- Don't create README.md inside skill folders (use SKILL.md)
- Don't put "when to use" instructions in the body (put in description)
- Don't make skills too broad (split into focused skills)
- Don't hardcode absolute paths in skills meant for sharing
