#!/usr/bin/env python3
"""Gate the load-bearing claims ledger — hardware/CLAIMS.md.

Containment layer 2 of docs/containment-roadmap.md (closes residual-risk
class 1: right copper, wrong decision). Gates check the board against
what we declared; a wrong declaration turns every gate green and wrong
together. The ledger holds each load-bearing claim with a status, and
this gate enforces:

    - the ledger exists and holds at least one claim
    - every claim has all required fields, a unique id and a valid status
    - `declared` parses as an ISO date and is not in the future
    - an UNVERIFIED claim older than MAX_AGE_DAYS is RED — "parked" may
      not silently become "forever" (the EN pull-up claim survived 4
      releases; 45 days is enough to schedule a session and short enough
      to hurt before the next order)
    - VERIFIED-* / FALSIFIED claims must cite evidence — a verdict
      without evidence is the justification-comment problem reborn

No soft-passes: a malformed claim is as red as a stale one, because a
claim the parser cannot read is a claim nobody is tracking.
"""
from __future__ import annotations

import datetime
import os
import re
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(PROJECT_DIR, "hardware", "CLAIMS.md")

MAX_AGE_DAYS = 45
VALID_STATUS = {"UNVERIFIED", "VERIFIED-ON-DATASHEET",
                "VERIFIED-ON-BENCH", "FALSIFIED"}
REQUIRED_FIELDS = ["status", "declared", "claim", "where",
                   "risk-if-false", "evidence"]

CLAIM_RE = re.compile(r"^## (CLAIM-\d+)\s+—\s+(.+)$")
FIELD_RE = re.compile(r"^- ([a-z-]+):\s*(.*)$")


def parse_ledger(text: str) -> list[dict]:
    """Claims as dicts. Fields outside a claim block are ignored."""
    claims, current = [], None
    for line in text.splitlines():
        m = CLAIM_RE.match(line)
        if m:
            current = {"id": m.group(1), "title": m.group(2), "fields": {}}
            claims.append(current)
            continue
        if line.startswith("## "):
            current = None  # a non-claim heading ends the block
            continue
        if current is not None:
            f = FIELD_RE.match(line)
            if f:
                current["fields"][f.group(1)] = f.group(2).strip()
    return claims


def check_ledger(path: str = LEDGER,
                 today: datetime.date | None = None) -> int:
    today = today or datetime.date.today()
    if not os.path.exists(path):
        print(f"FAIL  {os.path.relpath(path, PROJECT_DIR)} does not exist "
              "— every load-bearing claim is untracked.")
        return 1
    claims = parse_ledger(open(path).read())
    if not claims:
        print("FAIL  the ledger parses to zero claims — either it is empty "
              "or the format drifted and nothing is being tracked.")
        return 1

    problems = []
    seen_ids = set()
    for c in claims:
        cid, fields = c["id"], c["fields"]
        if cid in seen_ids:
            problems.append(f"{cid}: duplicate id")
            continue
        seen_ids.add(cid)
        missing = [f for f in REQUIRED_FIELDS if f not in fields]
        if missing:
            problems.append(f"{cid}: missing field(s) {', '.join(missing)}")
            continue
        status = fields["status"]
        if status not in VALID_STATUS:
            problems.append(f"{cid}: status '{status}' is not one of "
                            f"{sorted(VALID_STATUS)}")
            continue
        try:
            declared = datetime.date.fromisoformat(fields["declared"])
        except ValueError:
            problems.append(f"{cid}: declared '{fields['declared']}' is not "
                            "an ISO date")
            continue
        if declared > today:
            problems.append(f"{cid}: declared {declared} is in the future")
            continue
        age = (today - declared).days
        evidence = fields["evidence"]
        if status == "UNVERIFIED":
            if age > MAX_AGE_DAYS:
                problems.append(
                    f"{cid}: UNVERIFIED for {age} days (limit "
                    f"{MAX_AGE_DAYS}) — '{c['title']}' must be verified, "
                    "falsified, or the deadline consciously renewed by "
                    "re-dating it with a note")
        elif not evidence or evidence.lower() in ("none", "(none)", "-"):
            problems.append(f"{cid}: status {status} with no evidence — a "
                            "verdict without evidence is just a comment")

    if problems:
        for p in problems:
            print(f"FAIL  {p}")
        return 1

    unverified = [(c["id"],
                   MAX_AGE_DAYS - (today - datetime.date.fromisoformat(
                       c["fields"]["declared"])).days)
                  for c in claims if c["fields"]["status"] == "UNVERIFIED"]
    print(f"PASS  {len(claims)} claim(s) well-formed, "
          f"{len(unverified)} still UNVERIFIED")
    for cid, days_left in sorted(unverified, key=lambda x: x[1]):
        print(f"      {cid}: {days_left} day(s) until this goes red")
    return 0


if __name__ == "__main__":
    sys.exit(check_ledger())
