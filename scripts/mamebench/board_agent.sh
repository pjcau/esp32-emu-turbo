#!/bin/sh
# board_agent.sh: the board PC's side of the two-machine loop. Pulls, runs every
# pending job in scripts/mamebench/queue/*.sh in name order (each job is a shell
# script committed by the development machine, typically one board_run.sh
# call), moves it to queue/done/ with its log, commits and pushes. Safe to run
# every few minutes from a /loop: with nothing queued it only pulls.
#
#   /loop 3m run scripts/mamebench/board_agent.sh and show me its last 15 lines
set -e
cd "$(dirname "$0")/../.."
git pull --ff-only -q
git submodule update --init --recursive -q
Q=scripts/mamebench/queue
for job in $(ls $Q/*.sh 2>/dev/null | sort); do
    name=$(basename "$job" .sh)
    echo "=== job $name"
    log=$Q/done/$name.log
    if sh "$job" > "$log" 2>&1; then status=ok; else status="FAILED ($?)"; fi
    tail -5 "$log"
    git mv "$job" "$Q/done/$name.sh"
    git add "$log" scripts/mamebench/results
    git commit -q -m "board: job $name $status

$(tail -8 "$log")"
    git pull --rebase -q || true
    git push -q
    echo "=== job $name: $status, pushed"
done
echo "queue empty at $(date +%H:%M)"
