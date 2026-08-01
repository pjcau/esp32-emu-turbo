---
name: memory-maintenance
description: Audit and improve the persistent project memory (MEMORY.md + memory files) — detect stale claims against the live repo, archive resolved items to HISTORY.md, condense the NOW section, dedupe against CLAUDE.md/docs, verify with make verify-memory. Use when memory quality degrades, after closing a large work item, or on explicit /memory-maintenance.
allowed-tools: Bash, Read, Grep, Glob, Edit, Write
argument-hint: [audit | condense | full]
---

# Memory Maintenance — keep the memory current, small, and true

The memory lives at
`~/.claude/projects/-Users-pierrejonnycau-Documents-WORKS-esp32-emu-turbo/memory/`
(MEMORY.md index + HISTORY.md archive + one file per fact).
`make verify-memory` already gates the *mechanical* invariants (frontmatter,
name==stem, wikilinks resolve, no orphans, no hand-written gate state, no
stale counts). This skill covers what a gate cannot judge: whether the
**content** is still true, still needed, and still cheap to load.

Modes: `audit` (report only, default), `condense` (index/NOW hygiene),
`full` (audit + apply fixes + condense).

## Non-negotiable principles

1. **Green before, green after.** Run `make verify-memory` first; if it is
   red, fix that before touching content. Run it again after every batch of
   edits.
2. **Resolved ≠ deleted.** A closed incident or audit moves to
   `HISTORY.md` (dated, one paragraph, link to the repo record); its memory
   file is deleted only when HISTORY.md carries the pointer. Deleting
   without archiving is how lessons get relearned.
3. **Never write derived state.** No gate red/green status, no counts a
   generator owns (script counts → REPO_MAP.md, gate state →
   `open_issues_report.py`). T5/T6 of the gate reject some of this, but not
   all — apply the rule, not just the gate.
4. **Dated record → leave, current-state claim → fix** (memory:
   `feedback_deleting_list_entries_leaves_doc_rot`). A memory that says
   "on 2026-04-16 we found X" stays as written; one that says "X is
   currently true" must be re-verified or rewritten as dated.
5. **The repo outranks the memory.** If a memory and the repo disagree, the
   repo wins; update or delete the memory, never "fix" the repo to match.

## Steps

### 1. Baseline

```bash
cd /Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo
make verify-memory        # must be green before starting
git log --oneline -15     # what landed recently — resolved items feed step 3
```

Measure the load cost: `wc -w` on MEMORY.md (it is injected into every
session). Note memories not linked from the NOW section whose `modified:`
frontmatter is older than ~30 days — candidates for step 3/4, not
automatically stale.

### 2. Staleness sweep — claims vs live repo

For each memory file (start with the ones referenced from NOW):

- **Paths**: every `path/to/file` mentioned must exist (`ls` / `Grep`).
  Renamed or archived docs (e.g. `docs/` → `docs/archived/`) are the
  common case.
- **Commits**: every commit hash cited must resolve
  (`git cat-file -t <sha>`).
- **Identifiers**: table names, gate names, Make targets, function names
  quoted in the memory must still exist — grep the *name*, and remember a
  renamed identifier is a deliberate semantic signal in this repo.
- **"Still open" claims**: cross-check against `docs/open-tasks.md`,
  `docs/known-issues.md` and recent git log. A memory claiming an item is
  open after the repo closed it is the highest-value find of this sweep.
- **Deadlines**: any dated deadline (e.g. CLAIMS.md expiry) still in the
  future? If passed, escalate in the report — that is work, not doc rot.

### 3. Resolution sweep — archive what is finished

For each NOW bullet and each `project_*` memory describing in-flight work:

1. Is the work merged/closed in the repo? (git log, docs, gates)
2. If yes: append a dated one-paragraph entry to `HISTORY.md` with the
   lesson and the repo pointer (commit / doc path), delete or gut the
   memory file down to its permanent lesson, remove the NOW bullet.
3. If the lesson is behavioral ("how I work here"), keep it as a
   `feedback_*` memory instead of deleting — the incident goes to HISTORY,
   the rule stays live.

### 4. Condensation — the index must stay cheap

The body is the source of truth; the hook is a derived pointer.
`verify_memory.py` T7 enforces a 300-char ceiling per index bullet — this
step is HOW to get under it without losing a fact.

- **The KEEP rule (shrink the pointer, never the fact).** A hook may be
  shortened *only if* every specific it carries — commit SHA, path,
  deadline, "still open" flag, count, dimension — is already recoverable
  from the linked memory's body or a named repo record. If it carries
  anything the body does not: first push that fact down into the body (or
  a new memory file), THEN shrink. If pushing down is not possible, leave
  the hook verbatim and flag it in the report — an over-length true hook
  beats a short lossy one. Never rewrite a body just to make its hook
  shrinkable.
- **Membership assertion.** Before/after any index rewrite, the set of
  linked `(file.md)` targets must be identical, each listed exactly once —
  condensation changes hook *text*, never membership. `verify_memory.py`
  T8 enforces this; run it immediately after the rewrite, not at the end.
- MEMORY.md: **one line per memory**, human title (T9), hook only.
- NOW section: current state only, aim for ≤8 bullets. Anything that has
  not changed in weeks probably belongs in a linked memory, not in NOW.
- Merge near-duplicate memories (same lesson from two incidents → one
  memory, two dated examples). Update inbound `[[links]]` when merging.
- Delete duplication with CLAUDE.md / repo docs: memory records what the
  repo *cannot* derive (decisions, user context, lessons), never code
  structure, skill lists, or Makefile targets.

### 5. Cross-sync — things that point INTO the memory

```bash
grep -rn 'MEMORY.md\|memory/' .claude/skills/*/SKILL.md .claude/agents/*.md | grep -v memory-maintenance
```

Skills/agents that name MEMORY.md sections or memory files must match
reality (known offender pattern: a skill routing feedback to a MEMORY.md
section that no longer exists). Fix the pointer or flag it.

### 6. Verify and report

```bash
make verify-memory        # must be green after
```

Report: memories touched (updated / archived to HISTORY / merged /
deleted), stale claims found and their fix, NOW bullet count before/after,
MEMORY.md word count before/after, and anything escalated (passed
deadlines, open-item mismatches). "Swept" without the per-file list is not
a pass.

## Backlog — from the 2026-08-01 ecosystem scout, not implemented on purpose

- **CANDIDATES.md advisory backlog** (GlassOnTin): a file beside the index,
  deliberately NOT loaded into context, listing linking candidates (2–5
  memories that read as one sub-thread) and abstraction candidates (≥3
  memories sharing a root cause). Adopt when merges start feeling risky.
- **Batching for the deep pass**: reading every body costs ~10–16k tokens
  per hook; beyond ~30 over-length hooks, split across parallel agents
  writing JSON, merged mechanically. Irrelevant at the current store size.
- **Recall priority rule**: memories governing the *mechanics of the exact
  action* outrank topically-adjacent ones. Relevant only if a /recall-style
  retrieval skill is ever added.

Rejected (do not adopt): usage-count priority and auto-expiry (would demote
exactly the landmines — J4 reversal, polarity audit — that are rarely read
and catastrophic to lose); LLM passes that *synthesize new entries*
(fabrication path into every future session); "current session is fresher
so it wins" as contradiction resolution (the C2 incident proves recency is
not correctness); DB/embedding memory backends (give up git-inspectable
markdown for nothing at this scale).

## Key Files

- `~/.claude/projects/-Users-pierrejonnycau-Documents-WORKS-esp32-emu-turbo/memory/` — MEMORY.md, HISTORY.md, memory files
- `scripts/verify_memory.py` — the mechanical gate (T1–T6); this skill is its semantic half
- `scripts/test_verify_memory.py` — mutation tests for the gate; extend it if this skill's work reveals a new checkable invariant
- `docs/open-tasks.md`, `docs/known-issues.md` — ground truth for "is it still open"
