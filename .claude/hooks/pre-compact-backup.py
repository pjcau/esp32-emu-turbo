#!/usr/bin/env python3
"""
Pre-Compact Backup Hook — saves session context before auto-compaction.

When Claude Code compacts conversation history, detailed context is lost.
This hook fires on PreCompact events and saves a structured snapshot of
the current session state to .claude/backups/ for manual recovery.

Adapted from:
- claudefa.st context recovery hook pattern
- Edmonds-Commerce-Limited/claude-code-hooks-daemon workflow_state_pre_compact

Usage: Registered as a PreCompact hook in .claude/settings.json
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_DIR",
    "/Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo"
))

BACKUP_DIR = PROJECT_DIR / ".claude" / "backups"

# Key files to snapshot for state recovery
STATE_FILES = [
    ".claude/pipeline-checkpoint.json",
    "memory/dfm-state.md",
]


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    # Only act on PreCompact events
    hook_event = input_data.get("hook_event_name", "")
    if hook_event != "PreCompact":
        sys.exit(0)

    session_id = input_data.get("session_id", "unknown")
    trigger = input_data.get("trigger", "unknown")

    # Create backup directory
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Build snapshot
    now = datetime.now()
    snapshot = {
        "timestamp": now.isoformat(),
        "session_id": session_id,
        "trigger": trigger,
        "state_files": {},
        "recent_session_log": None,
    }

    # Capture state file contents
    for rel_path in STATE_FILES:
        full_path = PROJECT_DIR / rel_path
        if full_path.exists():
            try:
                snapshot["state_files"][rel_path] = full_path.read_text()[:5000]
            except (IOError, UnicodeDecodeError):
                snapshot["state_files"][rel_path] = "<read error>"

    # Capture most recent session log
    session_log_dir = PROJECT_DIR / ".claude" / "session_logs"
    if session_log_dir.exists():
        log_files = sorted(session_log_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
        if log_files:
            latest = log_files[-1]
            try:
                lines = latest.read_text().strip().split("\n")
                # Keep last 50 entries
                snapshot["recent_session_log"] = lines[-50:]
            except (IOError, UnicodeDecodeError):
                pass

    # Write backup file
    date_str = now.strftime("%Y%m%d_%H%M%S")
    short_id = session_id[:8] if len(session_id) > 8 else session_id
    backup_file = BACKUP_DIR / f"compact_{date_str}_{short_id}.json"

    try:
        with open(backup_file, "w") as f:
            json.dump(snapshot, f, indent=2)
    except IOError:
        sys.exit(0)

    # Clean old backups (keep last 10)
    backups = sorted(BACKUP_DIR.glob("compact_*.json"), key=lambda p: p.stat().st_mtime)
    for old in backups[:-10]:
        try:
            old.unlink()
        except IOError:
            pass

    # Output context message for Claude to see after compaction
    print(f"Session backup saved to {backup_file.relative_to(PROJECT_DIR)}")
    print("After compaction, read this file to restore context.")

    sys.exit(0)


if __name__ == "__main__":
    main()
