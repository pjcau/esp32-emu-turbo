# Board job queue

The development machine commits jobs here (`NNN-<what>.sh`, plain shell, run
from the repository root); the board PC's `board_agent.sh` runs them in name
order and moves each to `done/` with its log. Keep a job to one board run.
