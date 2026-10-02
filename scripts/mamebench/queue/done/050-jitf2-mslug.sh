# Phase J, F2: the dynarec with interrupts taken between instructions (no flag
# materialisation before memory call-outs). Hashes must be the reference ones; the
# "M68KJIT ... bytes/insn ... irq in mem call-out N" line must show N = 0, and the
# memory instruction fewer bytes than in job 040.
M68KJIT=1 NEOBAND=1 scripts/mamebench/board_run.sh jitf2 mslug 70 1
