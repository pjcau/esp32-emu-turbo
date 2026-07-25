#!/usr/bin/env bash
#
# Run a set of pass/fail verifiers in parallel and aggregate their exit
# codes into one.
#
# The previous inline `make verify-all` recipe was of the form
#
#     sh -c 'python3 a.py & python3 b.py & ... & wait'
#
# `wait` with no arguments always returns 0, so that suite could never
# fail no matter how many checks reported errors. Everything here exists
# to make sure a failing verifier actually fails the build.
#
# Usage: scripts/run-verifiers.sh <script-basename> [<script-basename> ...]
#        (basenames are relative to scripts/ and without the .py suffix)

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ "$#" -eq 0 ]; then
  echo "usage: $0 <verifier> [<verifier> ...]" >&2
  exit 2
fi

LOG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/verify-all.XXXXXX")"
trap 'rm -rf "$LOG_DIR"' EXIT

# Warm the shared PCB parse cache in a single process first. Every
# verifier calls pcb_cache.load_cache(); letting 50 of them race to
# rebuild and rewrite hardware/kicad/.pcb_cache.json at once is asking
# for a torn file.
python3 -c "import sys; sys.path.insert(0, 'scripts'); import pcb_cache; pcb_cache.load_cache()" \
  >/dev/null 2>&1 || true

START=$(date +%s)

for name in "$@"; do
  (
    python3 "scripts/${name}.py" >"$LOG_DIR/${name}.log" 2>&1
    echo $? >"$LOG_DIR/${name}.rc"
  ) &
done
wait

FAILED=()
PASSED=0
for name in "$@"; do
  rc_file="$LOG_DIR/${name}.rc"
  rc=$(cat "$rc_file" 2>/dev/null || echo 127)
  if [ "$rc" = "0" ]; then
    PASSED=$((PASSED + 1))
  else
    FAILED+=("${name}:${rc}")
  fi
done

ELAPSED=$(( $(date +%s) - START ))
TOTAL=$#

echo
echo "============================================================"
echo "Verification suite: ${PASSED}/${TOTAL} passed in ${ELAPSED}s"
echo "============================================================"

if [ "${#FAILED[@]}" -ne 0 ]; then
  for entry in "${FAILED[@]}"; do
    name="${entry%%:*}"
    rc="${entry##*:}"
    echo
    echo "------------------------------------------------------------"
    echo "FAIL  scripts/${name}.py (exit ${rc})"
    echo "------------------------------------------------------------"
    tail -25 "$LOG_DIR/${name}.log"
  done
  echo
  echo "FAILED (${#FAILED[@]}): $(printf '%s ' "${FAILED[@]%%:*}")"
  exit 1
fi

echo "All checks passed."
exit 0
