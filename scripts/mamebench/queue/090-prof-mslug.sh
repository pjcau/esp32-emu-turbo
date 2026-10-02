# O3: where core 0's time goes with the interpreter and V2h (the production path):
# MAMEPROF=1 samples core 0; profsym.sh gives the per-function profile. The
# "other" 2.6 ms and the mixer 0.9 ms are the targets of phase O.
MAMEPROF=1 NEOBAND=2 scripts/mamebench/board_run.sh prof mslug 70
OUT=scripts/mamebench/results/$(date +%F)-prof-mslug
scripts/mamebench/profsym.sh $OUT.txt 60 > $OUT.prof.txt 2>&1 || true
git add $OUT.prof.txt && git commit -q -m "mamebench: interpreter profile on mslug (V2h)" && (git pull --rebase -q || true) && git push -q
