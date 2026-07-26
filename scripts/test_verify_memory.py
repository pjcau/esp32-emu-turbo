"""Mutation tests for verify_memory.py.

An assertion that never fires is not evidence. Each test below builds a
*valid* memory directory, breaks exactly one thing, and asserts that the gate
goes red — and that it goes red for the right check, not incidentally.

The control test (a clean directory passes) is what makes the rest meaningful:
without it, a gate that always failed would score 100%.

Run: python3 scripts/test_verify_memory.py
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "verify_memory.py"

INDEX_TEMPLATE = """# Project Memory

## NOW
- [A thing](project_alpha.md) — a pointer to the alpha memory.
- [Another](feedback_beta.md) — a pointer to the beta memory.
- Run `make verify-power-nets` before committing; `make open-issues` shows state.

## Where things are
- `docs/REPO_MAP.md` — generated index of all {n} scripts.
"""

CLEAN_MEMORIES = {
    "project_alpha.md": """---
name: project_alpha
description: "An alpha project memory."
metadata:
  type: project
---

Alpha body text. Related: [[feedback_beta]].
""",
    "feedback_beta.md": """---
name: feedback_beta
description: "A beta feedback memory."
metadata:
  type: feedback
---

Beta body text.

**Why:** because.
**How to apply:** like so.
""",
}

results = []


REPO_MAP = "# Repo map — scripts\n\n{n} scripts, ~1,000 tokens of source.\n"

INDEXED = 2  # what the fake docs/REPO_MAP.md declares


def build(tmp, index=None, memories=None, indexed=INDEXED, repo_map=True):
    """Materialize a memory dir + a fake repo carrying a docs/REPO_MAP.md.

    T6 compares MEMORY.md's claim against REPO_MAP's declared total, so the
    honest index claims `indexed`. Pass a different `index` to stage a stale
    count, or repo_map=False to remove the source of truth entirely.
    """
    mdir = Path(tmp) / "memory"
    mdir.mkdir(parents=True, exist_ok=True)
    if index is None:
        index = INDEX_TEMPLATE.format(n=indexed)
    (mdir / "MEMORY.md").write_text(index, encoding="utf-8")
    for name, body in (memories if memories is not None else CLEAN_MEMORIES).items():
        (mdir / name).write_text(body, encoding="utf-8")

    repo = Path(tmp) / "repo"
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    if repo_map:
        (repo / "docs").mkdir(parents=True, exist_ok=True)
        (repo / "docs" / "REPO_MAP.md").write_text(
            REPO_MAP.format(n=indexed), encoding="utf-8"
        )
    return mdir, repo


def run(mdir, repo):
    """Run the gate against a synthetic memory dir. Returns (rc, stdout)."""
    # A shim keeps REPO_ROOT pointed at the fake repo without copying the
    # whole project: verify_memory derives it from its own __file__.
    shim = repo / "scripts" / "verify_memory.py"
    shim.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(shim)],
        capture_output=True,
        text=True,
        env={"CLAUDE_MEMORY_DIR": str(mdir), "PATH": "/usr/bin:/bin", "HOME": str(repo)},
    )
    return proc.returncode, proc.stdout + proc.stderr


def expect(label, rc, out, should_fail, check_id=None):
    """Assert the gate's verdict, and which check produced it."""
    ok = (rc != 0) if should_fail else (rc == 0)
    if ok and check_id:
        # The named check must be the one that went red — not a bystander.
        ok = bool(re.search(rf"FAIL\s+\[{check_id}\]", out))
    results.append((label, ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    if not ok:
        print("        ---- gate output ----")
        for line in out.splitlines():
            print(f"        {line}")
    return ok


def test_control_clean_passes():
    """A well-formed memory directory must pass all six checks."""
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(tmp)
        rc, out = run(mdir, repo)
        expect("control: a clean memory directory passes", rc, out, should_fail=False)


def test_missing_frontmatter():
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(tmp)
        (mdir / "project_alpha.md").write_text("no frontmatter here\n", encoding="utf-8")
        rc, out = run(mdir, repo)
        expect("T1 fires on a memory with no frontmatter", rc, out, True, "T1")


def test_bad_type():
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(tmp)
        body = (mdir / "project_alpha.md").read_text(encoding="utf-8")
        (mdir / "project_alpha.md").write_text(
            body.replace("type: project", "type: nonsense"), encoding="utf-8"
        )
        rc, out = run(mdir, repo)
        expect("T1 fires on an invalid metadata.type", rc, out, True, "T1")


def test_name_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(tmp)
        body = (mdir / "project_alpha.md").read_text(encoding="utf-8")
        (mdir / "project_alpha.md").write_text(
            body.replace("name: project_alpha", "name: Some Prose Title"),
            encoding="utf-8",
        )
        rc, out = run(mdir, repo)
        expect("T2 fires when name: differs from the filename", rc, out, True, "T2")


def test_broken_link():
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(tmp)
        body = (mdir / "project_alpha.md").read_text(encoding="utf-8")
        (mdir / "project_alpha.md").write_text(
            body.replace("[[feedback_beta]]", "[[feedback-beta]]"), encoding="utf-8"
        )
        rc, out = run(mdir, repo)
        ok = expect("T3 fires on a hyphenated (broken) wikilink", rc, out, True, "T3")
        if ok:
            expect(
                "T3 suggests the underscore spelling",
                0 if "did you mean 'feedback_beta'" in out else 1,
                out,
                should_fail=False,
            )


ORPHAN = (
    "---\nname: project_orphan\ndescription: \"Nobody links me.\"\n"
    "metadata:\n  type: project\n---\n\nBody.\n"
)


def test_orphan():
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(tmp)
        (mdir / "project_orphan.md").write_text(ORPHAN, encoding="utf-8")
        rc, out = run(mdir, repo)
        expect("T4 fires on a memory nothing references", rc, out, True, "T4")


def test_archived_memory_is_not_an_orphan():
    """A closed memory belongs in HISTORY.md, and that must count as reachable.

    Without this, the gate would push archived incidents back into MEMORY.md —
    growing the preamble it exists to protect.
    """
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(tmp)
        (mdir / "project_orphan.md").write_text(ORPHAN, encoding="utf-8")
        (mdir / "HISTORY.md").write_text(
            "# History\n\n## 2026-01-01 — a closed thing\n"
            "[project_orphan.md](project_orphan.md) — resolved.\n",
            encoding="utf-8",
        )
        rc, out = run(mdir, repo)
        expect(
            "T4 does NOT fire on a memory archived in HISTORY.md",
            rc,
            out,
            should_fail=False,
        )


def test_gate_state_in_index():
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(
            tmp,
            index=INDEX_TEMPLATE.format(n=INDEXED)
            + "- `make verify-all` exits 1 — verify_netlist_diff is red.\n",
        )
        rc, out = run(mdir, repo)
        expect("T5 fires on a hand-written gate-state claim", rc, out, True, "T5")


def test_naming_a_gate_without_state_is_allowed():
    """The discriminating case: mentioning a gate is fine, asserting its colour is not."""
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(
            tmp,
            index=INDEX_TEMPLATE.format(n=INDEXED)
            + "- Run `verify_schematic_pcb_sync.py` before every commit.\n"
            + "- `make verify-power-nets` is the gate for split planes.\n",
        )
        rc, out = run(mdir, repo)
        expect(
            "T5 does NOT fire when a gate is merely named (no false positive)",
            rc,
            out,
            should_fail=False,
        )


def test_stale_count():
    """REPO_MAP indexes 2; MEMORY.md still claims 7."""
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(tmp, index=INDEX_TEMPLATE.format(n=7))
        rc, out = run(mdir, repo)
        expect("T6 fires on a stale script count", rc, out, True, "T6")


def test_missing_repo_map_fails_not_skips():
    """No source of truth must mean red, not a quiet pass."""
    with tempfile.TemporaryDirectory() as tmp:
        mdir, repo = build(tmp, repo_map=False)
        rc, out = run(mdir, repo)
        expect(
            "T6 fires when docs/REPO_MAP.md is missing (no soft-pass)",
            rc,
            out,
            True,
            "T6",
        )


def test_missing_memory_dir_is_a_failure_not_a_skip():
    """A gate that silently skips when its input is missing is not a gate."""
    with tempfile.TemporaryDirectory() as tmp:
        _, repo = build(tmp)
        rc, out = run(Path(tmp) / "does-not-exist", repo)
        ok = rc != 0 and "not found" in out
        results.append(("missing memory dir fails loudly (no soft-skip)", ok))
        print(f"  {'PASS' if ok else 'FAIL'}  missing memory dir fails loudly (no soft-skip)")


def main():
    print("=" * 60)
    print("MUTATION TESTS — verify_memory.py")
    print("=" * 60)
    for fn in [
        test_control_clean_passes,
        test_missing_frontmatter,
        test_bad_type,
        test_name_mismatch,
        test_broken_link,
        test_orphan,
        test_archived_memory_is_not_an_orphan,
        test_gate_state_in_index,
        test_naming_a_gate_without_state_is_allowed,
        test_stale_count,
        test_missing_repo_map_fails_not_skips,
        test_missing_memory_dir_is_a_failure_not_a_skip,
    ]:
        fn()

    passed = sum(1 for _, ok in results if ok)
    print()
    print("=" * 60)
    print(f"  {passed}/{len(results)} mutation tests passed")
    print("=" * 60)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
