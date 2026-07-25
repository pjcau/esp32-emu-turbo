#!/usr/bin/env python3
"""Measure what this repo costs an AI agent's context window.

Four metrics, all recomputable, so "we slimmed it down" is a number and not
an opinion. Run before and after any restructuring.

  M1  PREAMBLE     tokens loaded into EVERY session before a single question
                   is asked: CLAUDE.md files, the memory index, and the
                   `description:` frontmatter of every skill (skill bodies are
                   progressive-disclosure and are NOT counted).

  M2  LANDMINES    tokens sitting in files big enough that ONE accidental Read
                   damages the session, and that `.claudeignore` does not
                   block. The .kicad_pcb alone is ~475k tokens.

  M3  NAVIGATION   tokens an agent must grep/read to answer "which script
                   checks X?" when there is no index. Equal to the whole
                   Python surface; an index replaces it with its own size.

  M4  RECENCY      share of the always-loaded preamble describing things that
                   ALREADY HAPPENED (incidents, closed audits, past fixes)
                   rather than what is true now. History is worth keeping but
                   not worth re-reading every session.

Usage:
    python3 scripts/context_budget.py
    python3 scripts/context_budget.py --json
"""

from __future__ import annotations

import fnmatch
import glob
import json
import os
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

# Rough but stable: ~4 bytes per token for prose and code alike. The absolute
# value matters less than the delta across runs.
BYTES_PER_TOKEN = 4

# A file above this size cannot be read without materially harming a session.
LANDMINE_TOKENS = 20_000

# Extensions an agent might plausibly open. Binaries are excluded because the
# Read tool refuses them anyway.
READABLE_EXT = {
    ".md", ".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml", ".toml",
    ".txt", ".csv", ".svg", ".html", ".sh", ".kicad_pcb", ".kicad_sch",
    ".kicad_mod", ".kicad_pro", ".kicad_dru", ".scad", ".c", ".h", ".cpp",
}

NEVER_WALK = {
    ".git", "node_modules", "__pycache__", ".easyeda_cache",
    ".claude/worktrees", "website/build", "website/.docusaurus",
    "software/build",
}

# Memory / doc entries that describe a PAST event rather than current state.
HISTORY_MARKERS = re.compile(
    r"\b(incident|root cause|audit|findings?|was |were |used to|"
    r"previously|closed|resolved|fixed in|proto #?\d|R\d+-(CRIT|HIGH|MED|LOW)|"
    r"lesson|postmortem|history|superseded)\b",
    re.I,
)


def tok(nbytes: int) -> int:
    return round(nbytes / BYTES_PER_TOKEN)


def _size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def _claudeignore_patterns() -> list[str]:
    """Patterns from both guard tiers.

    .claudeignore blocks Read/Edit/Write/Grep (secrets, binaries).
    .claudeheavy blocks Read/Edit/Write but allows Grep (token landmines).
    For M2 the distinction does not matter: either way a whole-file Read
    can no longer happen by accident.
    """
    pats: list[str] = []
    for name in (".claudeignore", ".claudeheavy"):
        f = BASE / name
        if not f.exists():
            continue
        pats += [
            ln.strip() for ln in f.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
    return pats


def _ignored(rel: str, patterns: list[str]) -> bool:
    for pat in patterns:
        p = pat.rstrip("/")
        if fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(os.path.basename(rel), p):
            return True
        if rel.startswith(p + "/") or f"/{p}/" in f"/{rel}":
            return True
    return False


def _walk() -> list[Path]:
    out = []
    for root, dirs, files in os.walk(BASE):
        rel_root = os.path.relpath(root, BASE)
        dirs[:] = [
            d for d in dirs
            if not any(
                os.path.normpath(os.path.join(rel_root, d)).startswith(n)
                or d == os.path.basename(n)
                for n in NEVER_WALK
            )
        ]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in READABLE_EXT:
                out.append(p)
    return out


def m1_preamble() -> dict:
    memory = Path.home() / ".claude" / "projects" / (
        "-Users-pierrejonnycau-Documents-WORKS-esp32-emu-turbo"
    ) / "memory"
    items = {
        "CLAUDE.md (project)": BASE / "CLAUDE.md",
        "CLAUDE.md (user)": Path.home() / ".claude" / "CLAUDE.md",
        "RTK.md (user)": Path.home() / ".claude" / "RTK.md",
        "MEMORY.md (index)": memory / "MEMORY.md",
    }
    parts = {k: tok(_size(v)) for k, v in items.items() if _size(v)}

    desc_bytes = 0
    n_skills = 0
    for f in glob.glob(str(BASE / ".claude" / "skills" / "*" / "SKILL.md")):
        head = re.match(r"^---\n(.*?)\n---\n", Path(f).read_text(), re.S)
        if not head:
            continue
        n_skills += 1
        d = re.search(r"description:\s*(.*)", head.group(1))
        if d:
            desc_bytes += len(d.group(1))
    parts[f"skill descriptions ({n_skills})"] = tok(desc_bytes)
    return {"total": sum(parts.values()), "parts": parts}


def m2_landmines() -> dict:
    pats = _claudeignore_patterns()
    exposed, guarded = [], []
    for p in _walk():
        t = tok(_size(p))
        if t < LANDMINE_TOKENS:
            continue
        rel = str(p.relative_to(BASE))
        (guarded if _ignored(rel, pats) else exposed).append((t, rel))
    exposed.sort(reverse=True)
    guarded.sort(reverse=True)
    return {
        "exposed_total": sum(t for t, _ in exposed),
        "exposed_count": len(exposed),
        "guarded_total": sum(t for t, _ in guarded),
        "worst": exposed[:10],
    }


def m3_navigation() -> dict:
    py = [
        p for p in glob.glob(str(BASE / "scripts" / "**" / "*.py"),
                             recursive=True)
        if "__pycache__" not in p and ".easyeda_cache" not in p
    ]
    surface = sum(_size(Path(p)) for p in py)
    index = BASE / "docs" / "REPO_MAP.md"
    idx_tok = tok(_size(index)) if index.exists() else None
    return {
        "python_files": len(py),
        "surface_tokens": tok(surface),
        "index_tokens": idx_tok,
        "cost": idx_tok if idx_tok else tok(surface),
    }


def m4_recency() -> dict:
    memory = Path.home() / ".claude" / "projects" / (
        "-Users-pierrejonnycau-Documents-WORKS-esp32-emu-turbo"
    ) / "memory" / "MEMORY.md"
    targets = [BASE / "CLAUDE.md", memory]
    hist = cur = 0
    for f in targets:
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            if not line.strip():
                continue
            n = len(line)
            if HISTORY_MARKERS.search(line):
                hist += n
            else:
                cur += n
    total = hist + cur
    return {
        "history_tokens": tok(hist),
        "current_tokens": tok(cur),
        "history_share": round(100 * hist / total, 1) if total else 0.0,
    }


def main(argv: list[str]) -> int:
    report = {
        "M1_preamble": m1_preamble(),
        "M2_landmines": m2_landmines(),
        "M3_navigation": m3_navigation(),
        "M4_recency": m4_recency(),
    }
    if "--json" in argv:
        print(json.dumps(report, indent=2))
        return 0

    m1, m2, m3, m4 = (report[k] for k in
                      ("M1_preamble", "M2_landmines", "M3_navigation",
                       "M4_recency"))
    print("=" * 68)
    print("  CONTEXT BUDGET")
    print("=" * 68)
    print(f"\nM1  PREAMBLE — loaded before any question: "
          f"{m1['total']:,} tok")
    for k, v in sorted(m1["parts"].items(), key=lambda kv: -kv[1]):
        print(f"      {v:>7,}  {k}")

    print(f"\nM2  LANDMINES — one Read damages the session: "
          f"{m2['exposed_total']:,} tok exposed "
          f"in {m2['exposed_count']} file(s)")
    print(f"      {m2['guarded_total']:>7,}  already blocked by .claudeignore")
    for t, rel in m2["worst"]:
        print(f"      {t:>7,}  {rel}")

    print(f"\nM3  NAVIGATION — cost to find the right script among "
          f"{m3['python_files']}")
    if m3["index_tokens"] is None:
        print(f"      {m3['surface_tokens']:>7,}  no index — grep the whole "
              f"Python surface")
    else:
        print(f"      {m3['index_tokens']:>7,}  docs/REPO_MAP.md "
              f"(vs {m3['surface_tokens']:,} tok of source)")

    print(f"\nM4  RECENCY — how much of the preamble is about the PAST")
    print(f"      {m4['current_tokens']:>7,}  current state")
    print(f"      {m4['history_tokens']:>7,}  history  "
          f"({m4['history_share']}%)")
    print("\n" + "=" * 68)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
