"""Virtual Bench — a netlist-driven bench test for the ESP32 Emu Turbo board.

Plan and phase boundaries: docs/archived/virtual-bench-plan.md. Read the boundary
table there before adding anything: this package deliberately does NOT
cover geometry (clearance, acid traps, shorts by distance), which belong
to verify_isolation / drc_native / short_circuit_analysis, nor signal
integrity, EMI or assembly.

Phase 0 (this commit) is the honesty baseline: extract the netlist,
cross-check the two sources, define what a component model must cite, and
write down the historical bugs the bench will have to rediscover. Nothing
electrical is modelled yet.
"""
