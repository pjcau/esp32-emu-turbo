#!/usr/bin/env python3
"""Validator for Claude Code skills, slash commands, and plugin metadata.

Checks:
  1. Every .claude/skills/<name>/SKILL.md has valid frontmatter
     - `name` field exists, matches directory name, is kebab-case
     - `description` field exists, non-empty, ≤ 1024 chars
     - optional `allowed-tools`, `disable-model-invocation`, `argument-hint` parse cleanly
  2. Every .claude/commands/*.md has a `description` field in frontmatter
  3. .claude-plugin/plugin.json is valid JSON with required keys
  4. .claude-plugin/marketplace.json is valid JSON with required keys
  5. No orphan files in .claude/skills/ (only directories + SKILL.md)
  6. docs/ contains skill-anatomy.md, lifecycle.md, getting-started.md
  7. .claude/README.md exists

Exit codes:
  0 — all checks pass
  1 — at least one check failed
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".claude" / "skills"
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"
PLUGIN_DIR = REPO_ROOT / ".claude-plugin"
DOCS_DIR = REPO_ROOT / "docs"

KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_DESCRIPTION_CHARS = 1024
MAX_SKILL_BODY_WORDS = 5000  # soft warning only


# ── Result tracking ────────────────────────────────────────────────

class Results:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.warnings: list[str] = []

    def ok(self, msg: str) -> None:
        self.passed.append(msg)

    def fail(self, msg: str) -> None:
        self.failed.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def print_report(self) -> None:
        total = len(self.passed) + len(self.failed)
        print()
        print("─" * 70)
        print(f"Results: {len(self.passed)}/{total} passed, "
              f"{len(self.failed)} failed, {len(self.warnings)} warnings")
        print("─" * 70)
        for msg in self.failed:
            print(f"  FAIL  {msg}")
        for msg in self.warnings:
            print(f"  WARN  {msg}")
        if not self.failed:
            print("  All checks passed.")

    @property
    def exit_code(self) -> int:
        return 1 if self.failed else 0


# ── Frontmatter parser ─────────────────────────────────────────────

def parse_frontmatter(path: Path) -> tuple[dict[str, str], str] | None:
    """Return (frontmatter_dict, body_after_frontmatter) or None if no frontmatter."""
    text = path.read_text()
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    raw = text[4:end]
    body = text[end + 5 :]
    fm: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm, body


# ── Skill validation ───────────────────────────────────────────────

def validate_skill(skill_dir: Path, r: Results) -> None:
    name = skill_dir.name
    skill_md = skill_dir / "SKILL.md"
    label = f"skill:{name}"

    if not skill_md.is_file():
        r.fail(f"{label}: missing SKILL.md")
        return

    parsed = parse_frontmatter(skill_md)
    if parsed is None:
        r.fail(f"{label}: missing or malformed YAML frontmatter")
        return

    fm, body = parsed

    # name field
    if "name" not in fm:
        r.fail(f"{label}: frontmatter missing `name`")
    elif fm["name"] != name:
        r.fail(f"{label}: frontmatter name={fm['name']!r} ≠ directory name {name!r}")

    if not KEBAB_CASE.match(name):
        r.fail(f"{label}: directory name {name!r} is not kebab-case")

    # description field
    if "description" not in fm:
        r.fail(f"{label}: frontmatter missing `description`")
    else:
        desc = fm["description"]
        if not desc:
            r.fail(f"{label}: `description` is empty")
        elif len(desc) > MAX_DESCRIPTION_CHARS:
            r.fail(f"{label}: description {len(desc)} chars > {MAX_DESCRIPTION_CHARS} max")

    # optional allowed-tools syntax check
    if "allowed-tools" in fm:
        tools = [t.strip() for t in fm["allowed-tools"].split(",")]
        if not all(tools):
            r.fail(f"{label}: `allowed-tools` contains empty entries")

    # optional disable-model-invocation check
    if "disable-model-invocation" in fm:
        val = fm["disable-model-invocation"].lower()
        if val not in ("true", "false"):
            r.fail(f"{label}: disable-model-invocation must be 'true' or 'false', got {val!r}")

    # body word count soft warning
    word_count = len(body.split())
    if word_count > MAX_SKILL_BODY_WORDS:
        r.warn(f"{label}: body is {word_count} words (>{MAX_SKILL_BODY_WORDS}) — consider moving content to references/")

    if not r.failed or r.failed[-1].split(":")[0] != label:
        r.ok(label)


def validate_skills_dir(r: Results) -> set[str]:
    if not SKILLS_DIR.is_dir():
        r.fail(f".claude/skills/ does not exist")
        return set()

    # orphan file check
    orphans = [p for p in SKILLS_DIR.iterdir() if p.is_file()]
    if orphans:
        r.fail(
            ".claude/skills/ contains stray files (must be directories only): "
            + ", ".join(p.name for p in orphans)
        )

    skill_names: set[str] = set()
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        validate_skill(skill_dir, r)
        skill_names.add(skill_dir.name)
    return skill_names


# ── Command validation ────────────────────────────────────────────

def validate_commands(r: Results) -> set[str]:
    if not COMMANDS_DIR.is_dir():
        r.fail(".claude/commands/ does not exist")
        return set()

    command_names: set[str] = set()
    for cmd_file in sorted(COMMANDS_DIR.glob("*.md")):
        name = cmd_file.stem
        label = f"command:{name}"
        command_names.add(name)

        if not KEBAB_CASE.match(name):
            r.fail(f"{label}: filename {name!r} is not kebab-case")
            continue

        parsed = parse_frontmatter(cmd_file)
        if parsed is None:
            r.fail(f"{label}: missing or malformed frontmatter")
            continue

        fm, _ = parsed
        if "description" not in fm or not fm["description"]:
            r.fail(f"{label}: frontmatter missing `description`")
            continue

        if len(fm["description"]) > MAX_DESCRIPTION_CHARS:
            r.fail(f"{label}: description > {MAX_DESCRIPTION_CHARS} chars")
            continue

        r.ok(label)
    return command_names


# ── Agent validation ──────────────────────────────────────────────

def validate_agents(r: Results) -> None:
    if not AGENTS_DIR.is_dir():
        r.warn(".claude/agents/ does not exist")
        return

    for agent_file in sorted(AGENTS_DIR.glob("*.md")):
        name = agent_file.stem
        label = f"agent:{name}"
        if not KEBAB_CASE.match(name):
            r.fail(f"{label}: filename {name!r} is not kebab-case")
            continue
        parsed = parse_frontmatter(agent_file)
        if parsed is None:
            r.warn(f"{label}: no YAML frontmatter (optional for agents)")
            continue
        r.ok(label)


# ── Plugin metadata validation ─────────────────────────────────────

PLUGIN_REQUIRED_KEYS = {"name", "description", "version", "author", "repository", "license"}
MARKETPLACE_REQUIRED_KEYS = {"name", "description", "plugins"}


def validate_plugin_metadata(r: Results) -> None:
    plugin_json = PLUGIN_DIR / "plugin.json"
    marketplace_json = PLUGIN_DIR / "marketplace.json"

    if not plugin_json.is_file():
        r.fail(".claude-plugin/plugin.json missing")
    else:
        try:
            data = json.loads(plugin_json.read_text())
        except json.JSONDecodeError as e:
            r.fail(f"plugin.json: invalid JSON — {e}")
        else:
            missing = PLUGIN_REQUIRED_KEYS - data.keys()
            if missing:
                r.fail(f"plugin.json: missing required keys {sorted(missing)}")
            else:
                if not KEBAB_CASE.match(data["name"]):
                    r.fail(f"plugin.json: name {data['name']!r} is not kebab-case")
                else:
                    r.ok(f"plugin.json: {data['name']} v{data.get('version', '?')}")

    if not marketplace_json.is_file():
        r.fail(".claude-plugin/marketplace.json missing")
    else:
        try:
            data = json.loads(marketplace_json.read_text())
        except json.JSONDecodeError as e:
            r.fail(f"marketplace.json: invalid JSON — {e}")
        else:
            missing = MARKETPLACE_REQUIRED_KEYS - data.keys()
            if missing:
                r.fail(f"marketplace.json: missing required keys {sorted(missing)}")
            elif not isinstance(data["plugins"], list) or not data["plugins"]:
                r.fail("marketplace.json: `plugins` must be a non-empty list")
            else:
                r.ok(f"marketplace.json: {len(data['plugins'])} plugin(s) registered")


# ── Docs validation ───────────────────────────────────────────────

REQUIRED_DOCS = ["skill-anatomy.md", "lifecycle.md", "getting-started.md"]


def validate_docs(r: Results) -> None:
    if not DOCS_DIR.is_dir():
        r.fail("docs/ directory missing")
        return
    for doc_name in REQUIRED_DOCS:
        doc_path = DOCS_DIR / doc_name
        if not doc_path.is_file():
            r.fail(f"docs/{doc_name} missing")
        else:
            # Sanity check: file must mention addyosmani somewhere for credits
            if "addyosmani" not in doc_path.read_text().lower():
                r.warn(f"docs/{doc_name}: no credit to addyosmani/agent-skills found")
            else:
                r.ok(f"docs/{doc_name}")

    claude_readme = REPO_ROOT / ".claude" / "README.md"
    if not claude_readme.is_file():
        r.fail(".claude/README.md missing")
    else:
        r.ok(".claude/README.md")


# ── Main ──────────────────────────────────────────────────────────

def main() -> int:
    r = Results()

    print(f"Validating skills suite at {REPO_ROOT}")
    print()

    print("→ Checking .claude/skills/")
    skill_names = validate_skills_dir(r)
    print(f"  Found {len(skill_names)} skill(s)")

    print("→ Checking .claude/commands/")
    command_names = validate_commands(r)
    print(f"  Found {len(command_names)} command(s)")

    print("→ Checking .claude/agents/")
    validate_agents(r)

    print("→ Checking .claude-plugin/")
    validate_plugin_metadata(r)

    print("→ Checking docs/")
    validate_docs(r)

    r.print_report()
    return r.exit_code


if __name__ == "__main__":
    sys.exit(main())
