#!/usr/bin/env python3
"""
Context Bundle Builder - Claude Code PostToolUse Hook
Tracks files accessed (Read/Write/Edit) during a Claude Code session.
Creates JSONL logs per session for debugging agent workflows.

Adapted from circuit-synth/circuit-synth context_bundle_builder.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")

    # Only track file operations
    if tool_name not in ("Read", "Write", "Edit"):
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    session_id = input_data.get("session_id", "unknown")

    # Extract file path
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # Convert to relative path
    project_dir = os.environ.get(
        "CLAUDE_PROJECT_DIR",
        "/Users/pierrejonnycau/Documents/WORKS/esp32-emu-turbo"
    )
    try:
        rel_path = str(Path(file_path).resolve().relative_to(Path(project_dir).resolve()))
    except ValueError:
        rel_path = file_path

    # Build log entry
    entry = {
        "ts": datetime.now().strftime("%H:%M:%S"),
        "op": tool_name.lower(),
        "file": rel_path,
    }

    # Write to JSONL log
    log_dir = Path(project_dir) / ".claude" / "session_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Use date + truncated session_id for filename
    date_str = datetime.now().strftime("%Y%m%d")
    short_id = session_id[:8] if len(session_id) > 8 else session_id
    log_file = log_dir / f"{date_str}_{short_id}.jsonl"

    try:
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except IOError:
        pass  # Never block on logging errors

    sys.exit(0)


if __name__ == "__main__":
    main()
