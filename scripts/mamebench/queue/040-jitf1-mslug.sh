# Phase J on the board: the dynarec (M68KJIT=1) with F0's counters and F1's density
# forms, on the proven V1 band renderer. Hashes must be the reference ones; the
# "M68KJIT ... bytes/insn" console lines give the Metal Slug numbers F0 asks for,
# the NEOPROF 68000 ms compares with 13.9 (dynarec before F1) and 7.72 (interpreter).
M68KJIT=1 NEOBAND=1 scripts/mamebench/board_run.sh jitf1 mslug 70 1
