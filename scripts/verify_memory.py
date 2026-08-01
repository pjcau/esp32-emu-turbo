"""Memory / context-preamble integrity verification.

The memory directory is the only artefact in this project that is read
*before every question* and was, until this script existed, the only one with
no gate on it. `docs/REPO_MAP.md` has `repo-map-check`; the net-explorer JSON
has `verify_net_explorer_fresh`; MEMORY.md had nothing — and drifted into
claiming 2 red gates when 5 of 6 were red.

Nine checks:

  T1  frontmatter is present and well-formed on every memory file
  T2  `name:` equals the filename stem — one canonical ID per memory
  T3  every [[wikilink]] resolves to a memory that exists
  T4  no orphans — every memory is reachable from the MEMORY.md index
  T5  MEMORY.md asserts no gate state that a tool already derives
  T6  counts MEMORY.md asserts about the repo match the repo
  T7  no index bullet exceeds the hook ceiling — bloated hooks ARE the
      truncation mechanism (the ecosystem's canonical failure: a standing
      rule truncated out of a 281-line index, then violated)
  T8  every index link targets an existing file, and no memory is listed
      twice — condensation may change hook text, never membership
  T9  index link text is a human title, not the filename slug

T5 is the one that matters most. A hand-written "gate X is red" line in the
preamble outranks the truth in practice: it is loaded before any question,
while the derived report has to be read. The rule is therefore not "keep it
updated" but "do not write it down at all" — `scripts/open_issues_report.py`
regenerates it at every SessionStart and cannot go stale.

The memory directory lives outside the repo, under
~/.claude/projects/<slugified-repo-path>/memory/. Override with
CLAUDE_MEMORY_DIR (the mutation tests rely on this).
"""

import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# MEMORY.md is the index and HISTORY.md the archive; neither is a memory and
# neither carries frontmatter. Every other .md in the directory is a memory.
INDEX_FILE = "MEMORY.md"
ARCHIVE_FILE = "HISTORY.md"

VALID_TYPES = {"user", "feedback", "project", "reference"}

# Words that turn a script mention into a state claim.
_STATE_WORDS = r"(?:red|green|fail(?:s|ing|ed)?|pass(?:es|ing|ed)?|exits?\s+[01]|broken|clean)"
# A gate is a verify_*/test_* script or a `make verify-*` / `make test-*` target.
_GATE_NAME = r"(?:(?:verify|test)_[a-z0-9_]+(?:\.py)?|make\s+(?:verify|test|open-issues)[a-z-]*)"

failures = []
passes = []


def check(name, condition, detail=""):
    """Record one pass/fail. Mirrors the helper used by the other verifiers."""
    if condition:
        passes.append(name)
        print(f"  PASS  {name}")
    else:
        failures.append((name, detail))
        print(f"  FAIL  {name}")
        for line in str(detail).splitlines():
            if line.strip():
                print(f"          {line}")


def canonical_repo_root():
    """The main working tree, even when running from a git worktree.

    Worktrees live at <repo>/.claude/worktrees/<name>, and the memory directory
    is keyed on the *repo* path — there is one memory shared by every worktree.
    Deriving the slug from the worktree path would silently point this gate at a
    directory that does not exist, i.e. make it unrunnable exactly when someone
    is doing isolated work.
    """
    marker = "/.claude/worktrees/"
    path = str(REPO_ROOT)
    if marker in path:
        return Path(path.split(marker)[0])
    return REPO_ROOT


def memory_dir():
    """Locate the memory directory for this repo."""
    override = os.environ.get("CLAUDE_MEMORY_DIR")
    if override:
        return Path(override)
    slug = str(canonical_repo_root()).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory"


def parse_frontmatter(text):
    """Return (frontmatter_dict, error). Only the flat keys we care about.

    Deliberately not a YAML parser: memories use a fixed shape, and pulling in
    a dependency for six keys would make this gate skippable when the import
    is missing. A gate that can silently not-run is not a gate.
    """
    if not text.startswith("---"):
        return None, "no frontmatter block (file must start with ---)"
    end = text.find("\n---", 3)
    if end == -1:
        return None, "frontmatter block is never closed"
    block = text[3:end]

    data = {}
    nested_key = None
    for raw in block.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indented = raw[0] in " \t"
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if indented and nested_key:
            data[f"{nested_key}.{key}"] = value
        else:
            nested_key = key if not value else None
            data[key] = value
    return data, None


def memory_files(mdir):
    return sorted(
        p for p in mdir.glob("*.md") if p.name not in (INDEX_FILE, ARCHIVE_FILE)
    )


def test_frontmatter(mdir, files):
    """T1 — every memory has a well-formed frontmatter block."""
    bad = []
    for path in files:
        data, err = parse_frontmatter(path.read_text(encoding="utf-8"))
        if err:
            bad.append(f"{path.name}: {err}")
            continue
        if not data.get("name"):
            bad.append(f"{path.name}: missing 'name:'")
        if not data.get("description"):
            bad.append(f"{path.name}: missing 'description:'")
        mtype = data.get("metadata.type") or data.get("type")
        if not mtype:
            bad.append(f"{path.name}: missing 'metadata.type:'")
        elif mtype not in VALID_TYPES:
            bad.append(
                f"{path.name}: type '{mtype}' not one of {sorted(VALID_TYPES)}"
            )
    check(
        f"[T1] All {len(files)} memories have valid frontmatter",
        not bad,
        "\n".join(bad),
    )


def test_name_matches_filename(mdir, files):
    """T2 — `name:` is the filename stem, so [[link]] has one unambiguous target."""
    bad = []
    for path in files:
        data, err = parse_frontmatter(path.read_text(encoding="utf-8"))
        if err:
            continue  # already reported by T1
        name = data.get("name", "")
        if name != path.stem:
            bad.append(
                f"{path.name}: name '{name}' != stem '{path.stem}' "
                f"— a link cannot target both"
            )
    check(
        "[T2] Every memory's name: equals its filename stem",
        not bad,
        "\n".join(bad),
    )


def test_links_resolve(mdir, files):
    """T3 — no [[wikilink]] points at a memory that does not exist."""
    stems = {p.stem for p in files}
    broken = []
    for path in files:
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), 1
        ):
            for target in re.findall(r"\[\[([^\]]+)\]\]", line):
                if target not in stems:
                    hint = ""
                    swapped = target.replace("-", "_")
                    if swapped in stems:
                        hint = f" (did you mean '{swapped}'? links use _, not -)"
                    broken.append(f"{path.name}:{lineno}: [[{target}]]{hint}")
    check(
        "[T3] Every [[wikilink]] resolves to an existing memory",
        not broken,
        "\n".join(broken),
    )


def test_no_orphans(mdir, files):
    """T4 — every memory is reachable from the index or the archive.

    An unreachable memory is not free: it costs disk and surfaces in recall,
    but nothing points at it, so it is never deliberately read.

    HISTORY.md counts as a referrer, not just MEMORY.md. A closed incident is
    supposed to leave the index — MEMORY.md's own header says "current state
    only" — but it is still deliberately reachable, because MEMORY.md links to
    HISTORY.md. Checking the index alone would report every correctly-archived
    memory as an orphan, i.e. push work back into the preamble this gate exists
    to keep small.
    """
    referrers = "".join(
        (mdir / name).read_text(encoding="utf-8")
        for name in (INDEX_FILE, ARCHIVE_FILE)
        if (mdir / name).is_file()
    )
    orphans = [p.name for p in files if p.name not in referrers and p.stem not in referrers]
    check(
        "[T4] No orphan memories — all reachable from MEMORY.md or HISTORY.md",
        not orphans,
        "\n".join(
            f"{n}: referenced by neither {INDEX_FILE} nor {ARCHIVE_FILE}" for n in orphans
        )
        + (
            f"\n→ add an index line if it is current state, or an {ARCHIVE_FILE}"
            f"\n  entry if it is closed. Delete it only if it is actively wrong."
            if orphans
            else ""
        ),
    )


def test_no_derivable_gate_state(mdir):
    """T5 — the index must not hand-write state a tool already derives.

    Fires on a sentence that names a gate AND makes a pass/fail claim about it.
    Naming a gate is fine ("run make verify-power-nets before committing");
    asserting its colour is not.
    """
    text = (mdir / INDEX_FILE).read_text(encoding="utf-8")
    offenders = []
    for lineno, line in enumerate(text.splitlines(), 1):
        # Sentence-level, so a gate named in one clause is not paired with a
        # colour word three clauses away.
        for sentence in re.split(r"(?<=[.;])\s+|\s+—\s+", line):
            if re.search(_GATE_NAME, sentence, re.I) and re.search(
                _STATE_WORDS, sentence, re.I
            ):
                offenders.append(f"{INDEX_FILE}:{lineno}: {sentence.strip()[:110]}")
                break
    check(
        "[T5] MEMORY.md asserts no gate state that open_issues_report.py derives",
        not offenders,
        "\n".join(offenders)
        + (
            "\n→ delete the claim, do not update it. The SessionStart hook runs"
            "\n  scripts/open_issues_report.py and injects the real state, which"
            "\n  cannot go stale. A written copy silently outranks it."
            if offenders
            else ""
        ),
    )


def repo_map_script_count():
    """The script count as docs/REPO_MAP.md itself defines it.

    Three plausible definitions disagree here — `ls scripts/*.py` (top level
    only), `git ls-files 'scripts/*.py'` (recursive), and REPO_MAP's own index.
    MEMORY.md's sentence is *about REPO_MAP*, so REPO_MAP is the definition
    that makes the claim checkable; picking a different one would make this
    gate the next piece of doc rot. Returns None if REPO_MAP is unreadable, and
    `repo-map-check` is what keeps REPO_MAP honest in turn.
    """
    repo_map = canonical_repo_root() / "docs" / "REPO_MAP.md"
    if not repo_map.is_file():
        return None
    match = re.search(r"^(\d+)\s+scripts\b", repo_map.read_text(encoding="utf-8"), re.M)
    return int(match.group(1)) if match else None


def test_counts_match_repo(mdir):
    """T6 — a script count MEMORY.md asserts must match REPO_MAP's."""
    text = (mdir / INDEX_FILE).read_text(encoding="utf-8")
    actual = repo_map_script_count()
    if actual is None:
        check(
            "[T6] Script counts in MEMORY.md match docs/REPO_MAP.md",
            False,
            "docs/REPO_MAP.md is missing or declares no total — cannot verify.\n"
            "→ run `make repo-map`. Not verifiable is not the same as fine.",
        )
        return
    wrong = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for claimed in re.findall(r"\b(\d+)\s+scripts\b", line):
            if int(claimed) != actual:
                wrong.append(
                    f"{INDEX_FILE}:{lineno}: claims {claimed} scripts, "
                    f"docs/REPO_MAP.md indexes {actual}"
                )
    check(
        f"[T6] Script counts in MEMORY.md match docs/REPO_MAP.md ({actual})",
        not wrong,
        "\n".join(wrong)
        + (
            "\n→ better: drop the number. It is derivable, its definition is"
            "\n  unstable, and REPO_MAP already states it."
            if wrong
            else ""
        ),
    )


# One index line = one hook. Above this, hooks stop being pointers and start
# being bodies — and an index full of bodies is what gets truncated. The
# number comes from GlassOnTin/claude-memory-skills' lint (fail >300, compact
# targets ≤180), adopted as-is rather than re-derived. Detail belongs in the
# memory file the line links to; the KEEP rule in /memory-maintenance governs
# how to shrink a hook without losing a fact.
HOOK_CEILING = 300


def test_hook_ceiling(mdir):
    """T7 — no index bullet exceeds HOOK_CEILING characters."""
    text = (mdir / INDEX_FILE).read_text(encoding="utf-8")
    over = []
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("- ") and len(line) > HOOK_CEILING:
            over.append(
                f"{INDEX_FILE}:{lineno}: {len(line)} chars — {line.strip()[:70]}…"
            )
    check(
        f"[T7] No index bullet exceeds {HOOK_CEILING} chars",
        not over,
        "\n".join(over)
        + (
            "\n→ push the detail down into the memory file the line links to"
            "\n  (KEEP rule: only after every specific — SHA, path, flag, count —"
            "\n  is recoverable from the body), then shrink the hook. Do not"
            "\n  split one bullet into two to duck the ceiling."
            if over
            else ""
        ),
    )


def _index_md_links(text):
    """(lineno, title, target) for every [title](target.md) link in the index."""
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for title, target in re.findall(r"\[([^\]]+)\]\(([A-Za-z0-9_.-]+\.md)\)", line):
            out.append((lineno, title, target))
    return out


def test_index_links(mdir, files):
    """T8 — index links point at real files; no memory is listed twice.

    T4 asks "is every memory reachable"; T8 asks the inverse — "does every
    index line point somewhere real, exactly once". A line linking a deleted
    memory passes T4 (the file is gone, so nothing is orphaned) and quietly
    keeps a dead entry in the preamble; a memory indexed twice doubles its
    context cost and lets the two hooks drift apart.
    """
    text = (mdir / INDEX_FILE).read_text(encoding="utf-8")
    links = _index_md_links(text)
    bad = []
    seen = {}
    for lineno, _title, target in links:
        if not (mdir / target).is_file():
            bad.append(f"{INDEX_FILE}:{lineno}: link to missing file '{target}'")
        if target in (ARCHIVE_FILE, INDEX_FILE):
            continue  # the archive is legitimately linked from several sections
        if target in seen:
            bad.append(
                f"{INDEX_FILE}:{lineno}: '{target}' already indexed on line "
                f"{seen[target]} — one memory, one index line"
            )
        else:
            seen[target] = lineno
    check(
        "[T8] Index links target existing files, each memory listed once",
        not bad,
        "\n".join(bad),
    )


def test_no_slug_titles(mdir):
    """T9 — link text must be a human title, not the filename slug.

    `[project_foo](project_foo.md)` carries zero recall value: the reader
    already sees the target. A 3–8 word title derived from the body is what
    makes the index scannable. The archive link `[HISTORY.md](HISTORY.md)` is
    exempt — naming a file by its name is correct when the file IS the point.
    """
    text = (mdir / INDEX_FILE).read_text(encoding="utf-8")
    bad = []
    for lineno, title, target in _index_md_links(text):
        if target in (ARCHIVE_FILE, INDEX_FILE):
            continue
        stem = target[: -len(".md")]
        norm = title.strip().strip("`*").lower()
        if norm in (stem.lower(), target.lower(), stem.lower().replace("_", " ")):
            bad.append(
                f"{INDEX_FILE}:{lineno}: [{title}]({target}) — slug title;"
                f" give it a 3–8 word human title from the body"
            )
    check(
        "[T9] Index link text is a human title, not the filename slug",
        not bad,
        "\n".join(bad),
    )


def main():
    mdir = memory_dir()
    print("=" * 60)
    print("MEMORY / CONTEXT PREAMBLE INTEGRITY")
    print("=" * 60)
    print(f"  dir: {mdir}")

    if not mdir.is_dir():
        print(f"  FAIL  memory directory not found: {mdir}")
        print(
            "\n  This gate cannot run without it. Do not skip — a missing memory\n"
            "  directory means the preamble is unverifiable, not that it is fine.\n"
            "  Set CLAUDE_MEMORY_DIR if it lives elsewhere."
        )
        return 1
    if not (mdir / INDEX_FILE).is_file():
        print(f"  FAIL  {INDEX_FILE} not found in {mdir}")
        return 1

    files = memory_files(mdir)
    print(f"  {len(files)} memories + {INDEX_FILE}\n")

    test_frontmatter(mdir, files)
    test_name_matches_filename(mdir, files)
    test_links_resolve(mdir, files)
    test_no_orphans(mdir, files)
    test_no_derivable_gate_state(mdir)
    test_counts_match_repo(mdir)
    test_hook_ceiling(mdir)
    test_index_links(mdir, files)
    test_no_slug_titles(mdir)

    total = len(passes) + len(failures)
    print()
    print("=" * 60)
    print(f"  {len(passes)}/{total} checks passed")
    print("=" * 60)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
