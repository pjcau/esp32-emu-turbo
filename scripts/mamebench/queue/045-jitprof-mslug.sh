# F0 on the board: where the dynarec's time goes on Metal Slug. MAMEPROF=1 samples
# core 0 (MAMESAMPLE lines); profsym.sh turns them into a per-function profile with
# the ELF of this build, written next to the log. Generated code (PSRAM) shows as
# "??": its share against the C handlers and memory.c is the number we want.
MAMEPROF=1 M68KJIT=1 NEOBAND=1 scripts/mamebench/board_run.sh jitprof mslug 70 1
OUT=scripts/mamebench/results/$(date +%F)-jitprof-mslug
scripts/mamebench/profsym.sh $OUT.txt 60 > $OUT.prof.txt 2>&1 || true
git add $OUT.prof.txt && git commit -q -m "mamebench: jitprof profile on mslug" && (git pull --rebase -q || true) && git push -q
