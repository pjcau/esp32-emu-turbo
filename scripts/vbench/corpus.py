"""Virtual Bench T0.3 — the retro corpus, and the proof it is not fiction.

`scripts/vbench/retro/*.json` holds the bugs this board has actually had,
plus the invariants it deliberately keeps. The plan's rule is that bench
coverage must be *measured rather than claimed* — so every entry names the
round it came from, cites a file and line, states the mutation that
reproduces it, and states what the bench must say.

Two things are enforced here, because a corpus that drifts is worse than no
corpus (it reads as coverage while proving nothing):

* **Provenance.** The cited line must still contain the cited text. If it
  moved, the loader finds it and tells you the new line number; if the text
  is gone from the file entirely, the entry fails. An entry whose evidence
  cannot be located is not a finding, it is a memory.
* **Status is derived, never written.** No entry carries a `status` field.
  Whether the bench catches an entry is decided by running detectors, and
  in Phase 0 there are none, so everything is `NOT-CAUGHT`. That is the
  intended Phase 0 result (T0.3: "corpus written and failing"), and it is
  also why this file refuses a status field outright — a hand-written
  "caught: true" is exactly the sign-off a gate cannot check.

The format is JSON, not the YAML the plan names. PyYAML is not importable
on this machine (PEP 668 externally-managed interpreter) and all 95 scripts
in this repo are stdlib-only, so a YAML corpus would make the gate
un-runnable — and a gate that cannot run is a gate that stops being read.
The plan records the deviation.

Usage:
    python3 scripts/vbench/corpus.py
    python3 scripts/vbench/corpus.py --json
"""

import argparse
import collections
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RETRO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "retro")

REQUIRED = ("id", "round", "title", "source", "source_match", "phase",
            "classes", "mutation", "must_report", "expect")
# `status`/`caught` are refused, not ignored: see the module docstring.
FORBIDDEN = ("status", "caught", "fixed", "verified")
EXPECTS = ("caught", "reproduced")
MUTATION_KINDS = ("none", "detach_pin", "move_pin", "swap_pins",
                  "remove_part", "short_nets", "set_param")


class CorpusError(ValueError):
    """The corpus itself is malformed. Always fatal."""


Entry = collections.namedtuple(
    "Entry", "id round title source source_match phase classes mutation "
             "must_report expect present_now note file")


def _check_provenance(entry_id, source, needle):
    """The cited file:line must still contain the cited text."""
    if ":" not in source:
        raise CorpusError(f"{entry_id}: source {source!r} is not file:line")
    rel, _, lineno = source.rpartition(":")
    path = os.path.join(BASE, rel)
    if not os.path.exists(path):
        raise CorpusError(f"{entry_id}: cited file does not exist: {rel}")
    try:
        want = int(lineno)
    except ValueError:
        raise CorpusError(f"{entry_id}: source {source!r} is not file:line")

    with open(path, errors="replace") as fh:
        lines = fh.readlines()
    if 1 <= want <= len(lines) and needle in lines[want - 1]:
        return
    found = [i for i, line in enumerate(lines, 1) if needle in line]
    if found:
        raise CorpusError(
            f"{entry_id}: {rel}:{want} no longer contains "
            f"{needle!r} — it is now at line "
            f"{', '.join(str(f) for f in found[:3])}. Update the citation.")
    raise CorpusError(
        f"{entry_id}: {needle!r} is not in {rel} at all. Either the evidence "
        f"was deleted — in which case say so in the entry — or this citation "
        f"was never right.")


def load_corpus(check_provenance=True):
    """Load and validate every corpus file. Raises CorpusError on any fault."""
    if not os.path.isdir(RETRO_DIR):
        raise CorpusError(f"no corpus directory at {RETRO_DIR}")
    files = sorted(f for f in os.listdir(RETRO_DIR) if f.endswith(".json"))
    if not files:
        raise CorpusError(
            f"{RETRO_DIR} holds no corpus files. An empty corpus would make "
            f"every coverage claim vacuously true.")

    entries, seen = [], {}
    for name in files:
        path = os.path.join(RETRO_DIR, name)
        with open(path) as fh:
            try:
                doc = json.load(fh)
            except json.JSONDecodeError as exc:
                raise CorpusError(f"{name}: invalid JSON: {exc}") from exc
        for key in ("corpus", "why", "entries"):
            if key not in doc:
                raise CorpusError(f"{name}: missing top-level {key!r}")
        if not doc["entries"]:
            raise CorpusError(f"{name}: no entries")

        for raw in doc["entries"]:
            eid = raw.get("id", "<no id>")
            for key in REQUIRED:
                if key not in raw:
                    raise CorpusError(f"{name}/{eid}: missing {key!r}")
                if raw[key] in ("", [], {}, None):
                    raise CorpusError(f"{name}/{eid}: {key!r} is empty")
            for key in FORBIDDEN:
                if key in raw:
                    raise CorpusError(
                        f"{name}/{eid}: carries {key!r}. Whether the bench "
                        f"catches an entry is derived by running it, never "
                        f"written into the corpus.")
            if raw["expect"] not in EXPECTS:
                raise CorpusError(
                    f"{name}/{eid}: expect must be one of {EXPECTS}")
            kind = raw["mutation"].get("kind")
            if kind not in MUTATION_KINDS:
                raise CorpusError(
                    f"{name}/{eid}: mutation kind {kind!r} not in "
                    f"{MUTATION_KINDS}")
            if kind == "none" and not raw.get("present_now"):
                raise CorpusError(
                    f"{name}/{eid}: mutation kind 'none' means the defect is "
                    f"in the design as it stands, so present_now must be "
                    f"true. Otherwise the entry describes nothing the bench "
                    f"could ever be pointed at.")
            if eid in seen:
                raise CorpusError(
                    f"{name}/{eid}: id already used in {seen[eid]}")
            seen[eid] = name

            if check_provenance:
                _check_provenance(eid, raw["source"], raw["source_match"])

            entries.append(Entry(
                id=eid, round=raw["round"], title=raw["title"],
                source=raw["source"], source_match=raw["source_match"],
                phase=raw["phase"], classes=tuple(raw["classes"]),
                mutation=raw["mutation"], must_report=raw["must_report"],
                expect=raw["expect"],
                present_now=bool(raw.get("present_now", False)),
                note=raw.get("note", ""), file=name))
    return entries


# ── Detectors ───────────────────────────────────────────────────────
#
# Phase 5 (T5.1) wires each entry to the bench run that must catch it.
# Until Phase 1 exists there is nothing to ask, so the result is NOT-CAUGHT
# for every entry — and it is computed that way rather than asserted, so
# the day a detector lands the count moves on its own.

def evaluate(entries):
    """Return (entry, caught, detail) for each entry. Phase 0: none caught."""
    return [(e, False, "no detector — Phase 1+ not implemented")
            for e in entries]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        entries = load_corpus()
    except CorpusError as exc:
        print(f"  ERROR  corpus is malformed: {exc}", file=sys.stderr)
        return 2

    results = evaluate(entries)
    caught = [e for e, ok, _ in results if ok]

    if args.json:
        print(json.dumps({
            "entries": len(entries),
            "caught": len(caught),
            "results": [{"id": e.id, "phase": e.phase, "expect": e.expect,
                         "caught": ok, "detail": why}
                        for e, ok, why in results],
        }, indent=2))
        return 0 if len(caught) == len(entries) else 1

    print("=" * 72)
    print("  Virtual Bench T0.3 — retro corpus")
    print("=" * 72)
    by_phase = collections.defaultdict(list)
    for e, ok, why in results:
        by_phase[e.phase].append((e, ok, why))
    for phase in sorted(by_phase):
        print(f"\n  Phase {phase}")
        for e, ok, why in sorted(by_phase[phase], key=lambda t: t[0].id):
            mark = "CAUGHT    " if ok else "NOT-CAUGHT"
            live = " [live]" if e.present_now else ""
            print(f"    {mark} {e.id:<18} {e.expect:<10} R{e.round}{live}  "
                  f"{e.title}")
            if not ok:
                print(f"               {why}")

    print()
    print("-" * 72)
    print(f"  Entries        : {len(entries)} "
          f"(from {len({e.file for e in entries})} corpus files)")
    print(f"  Live in design : "
          f"{sum(1 for e in entries if e.present_now)}")
    print(f"  Must reproduce : "
          f"{sum(1 for e in entries if e.expect == 'reproduced')}")
    print(f"  Caught         : {len(caught)} / {len(entries)}")
    print(f"  Provenance     : all {len(entries)} citations resolve")
    print()
    if len(caught) != len(entries):
        print("  RESULT: FAILING as designed — Phase 0 writes the corpus, "
              "Phase 5 (T5.1) is where it has to pass.")
        return 1
    print("  RESULT: the bench rediscovers every known historical bug")
    return 0


if __name__ == "__main__":
    sys.exit(main())
