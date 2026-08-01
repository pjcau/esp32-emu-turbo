#!/bin/bash
# Docs-drift reminder — fires after Edit/Write on files whose behaviour is
# documented on the Docusaurus site, so the docs get updated in the SAME
# session instead of drifting. Deliberately a reminder, not a blocker: only
# the author knows whether the change is behaviour or refactor.
#
# CLAUDE_FILE_PATH is provided by the hook runtime.

FILE="${CLAUDE_FILE_PATH:-}"
[ -z "$FILE" ] && exit 0

case "$FILE" in
  # feature surfaces the website documents
  */scripts/verify_*.py|*/scripts/test_*.py|*/scripts/generate_pcb/*|*/Makefile)
    echo ">>> Documented surface changed: $(basename "$FILE")."
    echo ">>> If behaviour changed, update website/docs/ (verification, rework,"
    echo ">>> vbench or tooling section) and run 'make repo-map' — the site is"
    echo ">>> the single source of truth and it does not update itself."
    ;;
  */scripts/vbench/*)
    echo ">>> Virtual Bench changed: keep website/docs/vbench/virtual-bench.md"
    echo ">>> and docs/archived/virtual-bench-plan.md phase table in sync."
    ;;
  */software/main/*)
    echo ">>> Firmware changed: check website/docs/software/ still describes it"
    echo ">>> (GPIO map must match board_config.h — 'make firmware-sync-check')."
    ;;
esac
exit 0
