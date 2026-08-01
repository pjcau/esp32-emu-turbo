.PHONY: all docker-build generate-schematic generate-pcb pcb-filled render-schematics \
       render-enclosure render-pcb render-all simulate verify-all verify-fast verify-dfa verify-datasheet verify-trace-through-pad verify-trace-crossings verify-copper-clearance verify-easyeda docs-bom docs-bom-check verify-power-nets verify-sch-crossings verify-cpl-law test-cpl-law analyze-pin1 context-budget repo-map repo-map-check validate-jlcpcb pcb-check external-dfm \
       verify-isolation verify-jlcpcb-vias verify-zone-fill test-zone-fill verify-sch-overlaps \
       export-gerbers release-prep firmware-sync-check verify-net-connectivity test-power-nets \
       net-explorer net-explorer-check verify-sch-pins verify-dangling verify-netlist-kicad open-issues \
       verify-memory test-memory \
       firmware-build firmware-flash firmware-monitor firmware-clean \
       retro-go-build retro-go-build-launcher retro-go-flash retro-go-monitor retro-go-clean \
       website-dev website-build clean help stats

# ── Task timer wrapper ────────────────────────────────────────────
# Every target logs its execution time to logs/task-times.csv
# View report: make stats
T = scripts/task-timer.sh

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

stats: ## Show task performance report (slowest, most frequent, failures)
	@scripts/task-stats.sh

docker-build: ## Build Docker images (KiCad + OpenSCAD) — cached if unchanged
	@docker compose images -q 2>/dev/null | head -1 > /dev/null 2>&1 && \
		echo "Docker images already built (use 'docker compose build --no-cache' to force)" || \
		$(T) docker-build docker compose build

generate-schematic: ## Generate 7 KiCad schematics from Python spec
	@$(T) generate-schematic docker compose run --rm generate-sch

generate-pcb: ## Generate KiCad PCB + JLCPCB exports (BOM, CPL) + Net Explorer data
	@$(T) generate-pcb python3 -m scripts.generate_pcb hardware/kicad
	@$(T) net-explorer python3 scripts/generate_net_explorer.py

render-schematics: docker-build ## Export KiCad schematic to SVG
	@$(T) render-schematics ./scripts/render-schematics.sh

render-enclosure: docker-build ## Render OpenSCAD enclosure to PNG
	@$(T) render-enclosure ./scripts/render-enclosure.sh

pcb-filled: generate-pcb ## Generate the PCB, fill its copper zones, refresh Net Explorer (what renders and gerbers actually need)
	@$(T) fill-zones ./scripts/fill-zones.sh
	@$(T) net-explorer python3 scripts/generate_net_explorer.py

render-pcb: pcb-filled ## Render PCB layout to SVG/PNG/GIF
	@$(T) render-pcb sh -c 'python3 scripts/render_pcb_svg.py website/static/img/pcb && python3 scripts/render_pcb_animation.py website/static/img/pcb'

simulate: ## Run electrical circuit simulation/verification
	@$(T) simulate python3 scripts/simulate_circuit.py

pcb-check: ## Run PCB short circuit / zone fill analysis
	@$(T) pcb-check python3 scripts/short_circuit_analysis.py

# ── verify-all ────────────────────────────────────────────────────
# Every pass/fail verifier in scripts/. "All" means all: if a script
# exits non-zero on a bad board, it belongs in this list.
#
# Deliberately NOT in the list, with reasons:
#   validate_skills   lints .claude/skills metadata, not the hardware
#   drc_native        needs `--run` plus a live kicad-cli DRC pass; it is
#                     driven by `make fast-check` / the /drc-native skill
#   pcb_review        scored design review, always exits 0
#   pcb_optimize      layout optimisation report, always exits 0
#   violation_matrix  cross-tabulates other tools' output, always exits 0
#   generate_*, render_*, inject-3d-models, kicad_fill_zones,
#   update_component, jlcpcb_parts, net_classifier, pcb_cache, pcb_query
#                     generators/helpers, not checks
VERIFY_ALL_SCRIPTS = \
	analyze_pad_distances \
	drc_check \
	erc_check \
	short_circuit_analysis \
	simulate_circuit \
	spice_power_check \
	test_claims_ledger \
	test_collision_via_metric \
	test_cpl_rotation_law \
	test_enclosure_sync \
	test_esd_protection \
	test_erc_severity \
	test_gate_coverage \
	test_gerber_etest \
	test_strapping_en_rc \
	test_test_points \
	test_issue_dispatch \
	test_order_manifest \
	test_pcb_connectivity \
	test_power_net_integrity \
	test_vbench \
	test_vbench_display \
	test_vbench_sdcard \
	test_verify_memory \
	validate_jlcpcb \
	verify_antenna_keepout \
	verify_battery_protection \
	verify_bom_cpl_pcb \
	verify_bom_values \
	verify_claims_ledger \
	verify_component_connectivity \
	verify_copper_balance \
	verify_copper_clearance \
	verify_context_budget \
	verify_cpl_rotation_law \
	verify_datasheet \
	verify_datasheet_nets \
	verify_decoupling_adequacy \
	verify_decoupling_paths \
	verify_design_intent \
	verify_dangling_copper \
	verify_dfa \
	verify_dfm_v2 \
	verify_drill_standards \
	verify_easyeda_footprint \
	verify_enclosure_sync \
	verify_erc \
	verify_esd_protection \
	verify_firmware_retrogo_sync \
	verify_gerber_etest \
	verify_gerber_integrity \
	verify_ground_loops \
	verify_isolation \
	verify_jlcpcb_capabilities \
	verify_jlcpcb_via_rules \
	verify_memory \
	verify_net_class_widths \
	verify_net_explorer_fresh \
	verify_net_connectivity \
	verify_netlist_diff \
	verify_netlist_vs_kicad \
	verify_order_manifest \
	verify_polarity \
	verify_power_net_integrity \
	verify_power_paths \
	verify_power_resonance \
	verify_power_sequence \
	verify_schematic_crossings \
	verify_schematic_label_attach \
	verify_schematic_pcb \
	verify_schematic_pcb_sync \
	verify_schematic_pin_connectivity \
	verify_sd_interface \
	verify_signal_chain_complete \
	verify_stackup \
	verify_stencil_aperture \
	verify_strapping_pins \
	verify_test_points \
	verify_thermal_budget \
	verify_thermal_relief \
	verify_trace_crossings \
	verify_trace_through_pad \
	verify_usb_impedance \
	verify_usb_impedance_stackup \
	verify_usb_return_path \
	verify_via_in_pad \
	verify_zone_connectivity \
	verify_schematic_overlaps \
	verify_zone_fill_sanity

verify-all: ## Run every pass/fail verification script (fails if any check fails)
	@echo "Running verification suite ($(words $(VERIFY_ALL_SCRIPTS)) checks)..."
	@$(T) verify-all scripts/run-verifiers.sh $(VERIFY_ALL_SCRIPTS)

order-manifest: ## Fingerprint the JLCPCB order files (SHA256 of gerbers.zip/bom.csv/cpl.csv -> release_jlcpcb/order-manifest.json)
	@$(T) order-manifest python3 scripts/order_manifest.py

verify-order-manifest: ## Fail when the order manifest lags the files in release_jlcpcb/
	@$(T) verify-order-manifest python3 scripts/verify_order_manifest.py

verify-claims: ## Gate hardware/CLAIMS.md — stale UNVERIFIED or evidence-free claims go red
	@$(T) verify-claims python3 scripts/verify_claims_ledger.py

context-budget: ## Measure what this repo costs a context window (M1 preamble, M2 landmines, M3 navigation, M4 recency)
	@$(T) context-budget python3 scripts/context_budget.py

repo-map: ## Regenerate docs/REPO_MAP.md — the script index (read it instead of grepping 448k tokens)
	@$(T) repo-map python3 scripts/generate_repo_map.py

repo-map-check: ## Fail if docs/REPO_MAP.md is stale vs the scripts on disk
	@$(T) repo-map-check python3 scripts/generate_repo_map.py --check
verify-sch-crossings: ## Fail when two schematic wires cross without a junction (use a labelled link instead)
	@$(T) verify-sch-crossings python3 scripts/verify_schematic_crossings.py

verify-sch-pins: ## Fail when a schematic symbol pin has no wire/label/junction on it (undeclared floating pin)
	@$(T) verify-sch-pins python3 scripts/verify_schematic_pin_connectivity.py

verify-sch-labels: ## Fail when a label does not lie on the wire it names (the wire stays unnamed and its pins leave the netlist)
	@$(T) verify-sch-labels python3 scripts/verify_schematic_label_attach.py

open-issues: ## Which hardware gates are red right now (same report the SessionStart hook injects)
	@python3 scripts/open_issues_report.py --text

dispatch: ## Turn every red gate into an agent work order in .claude/issues/
	@$(T) dispatch python3 scripts/issue_dispatch.py

dispatch-fast: ## Same, but only the session-start gate subset
	@$(T) dispatch-fast python3 scripts/issue_dispatch.py --fast

# ── Virtual Bench (docs/virtual-bench-plan.md) ───────────────────────
#
# Phase 0: extract the netlist, cross-check the two sources, define what a
# component model must cite, and write down the bugs the bench must
# rediscover. Phase 1: the physics — DC operating point, cited component
# models, electrical conflicts, junction temperatures. Transients (T1.4) are
# the one Phase 1 task still open.
#
# NONE of these are in VERIFY_ALL_SCRIPTS, deliberately. bench-netlist and
# bench-retro are *designed* to exit non-zero at this phase — the plan's own
# done-when for T0.3 is "corpus written and failing" — and parking two
# permanent reds in the suite is how the whole suite stops being read.
# Registration is T5.3, which also has to give the gate an owner in
# issue_dispatch.py: an unowned failing gate is a hard error (exit 2) here.

bench-netlist: ## T0.1 — extracted netlist + the dispute list that blocks the bench
	@$(T) bench-netlist python3 scripts/vbench/netlist.py

bench-delta: ## T0.1 — what changed electrically since the board on the desk (v4.3.1)
	@$(T) bench-delta python3 scripts/vbench/netlist.py --delta

bench-retro: ## T0.3 — historical bugs the bench must rediscover, and how many it does
	@$(T) bench-retro python3 scripts/vbench/corpus.py

bench-test: ## Phase 0 mutation tests — break the schema/corpus/netlist checks on purpose
	@$(T) bench-test python3 scripts/test_vbench.py

bench-phase0: bench-test bench-netlist bench-retro ## Everything Phase 0 delivers, in order

bench-rails: ## T1.1 — DC operating point: every net's voltage, derived from the netlist and the datasheets
	@$(T) bench-rails python3 scripts/vbench/rails.py

bench-conflicts: ## T1.3 — electrical conflicts (two drivers on a node); geometry stays with verify_isolation
	@$(T) bench-conflicts python3 scripts/vbench/conflicts.py

bench-thermal: ## T1.5 — junction temperatures at 30 C external and 40 C in-enclosure, from cited theta_JA
	@$(T) bench-thermal python3 scripts/vbench/thermal.py

bench-header: ## T4.1 — regenerate software/sim/vbench_board.h from the derived board model
	@$(T) bench-header python3 scripts/vbench/export_header.py

bench-build: ## T4.1 — build the model-backed simulator (emu-turbo-bench)
	@$(T) bench-header python3 scripts/vbench/export_header.py
	@$(T) bench-build $(MAKE) -C software/sim bench

bench: bench-build ## T4.4 — open the Virtual Bench window: LCD through the i80 model + live instruments
	cd software/sim && ./emu-turbo-bench ../../test-roms

bench-transients: ## T1.4 — cold start, inrush, load step, sag (ngspice; exits 2 if it is missing)
	@$(T) bench-transients python3 scripts/vbench/transients.py

bench-power: bench-rails bench-conflicts bench-thermal bench-transients ## T1.6 — rails + conflicts + thermal + transients, non-zero on any out-of-spec value

bench-phase1: bench-power ## Everything Phase 1 delivers

bench-pins: ## T2.1 + T2.4 — every ESP32 pin with net/level/role, and the boot mode the copper produces
	@$(T) bench-pins python3 scripts/vbench/pins.py

bench-buttons: ## T2.2 + T2.3 — debounce RC per button, and the switch_off scenario
	@$(T) bench-buttons python3 scripts/vbench/buttons.py

bench-phase2: bench-pins bench-buttons ## Everything Phase 2 delivers

bench-display: ## T3.1 — panel side (40 pins through the 41-N reversal, IM straps, bus order) AND controller side (command sequence, MADCTL, pixel format, i80 timing vs LCD_CLK_HZ)
	@$(T) bench-display python3 scripts/vbench/display.py

bench-display-frame: ## T3.1 — drive a frame through the ILI9488 state machine and export it as a PNG
	@$(T) bench-display-frame python3 scripts/vbench/ili9488_ctrl.py --demo

bench-display-test: ## T3.1 mutation tests — break the controller model on purpose and require it to notice
	@$(T) bench-display-test python3 scripts/test_vbench_display.py

bench-audio: ## T3.2 — audio chain: high-pass corner, 8-ohm output power, rail current
	@$(T) bench-audio python3 scripts/vbench/audio.py

bench-sd: ## T3.3 (part) — SD bus wiring, and the DAT2 pad that shares a net with a strapping pin
	@$(T) bench-sd python3 scripts/vbench/sdcard.py

bench-sdcard: ## T3.3 — the card protocol: CMD0/CMD8/ACMD41 init, CMD17 block reads of a real file, cited currents
	@$(T) bench-sdcard python3 scripts/vbench/sdcard_protocol.py --demo software/main

bench-sdcard-test: ## T3.3 mutation tests — break the card model on purpose and require it to notice
	@$(T) bench-sdcard-test python3 scripts/test_vbench_sdcard.py

bench-phase3: bench-display bench-audio bench-sd bench-sdcard ## Everything Phase 3 delivers

bench-ci: ## T4.3 — every scenario, headless, with assertions; non-zero on any failure
	@$(T) bench-ci python3 scripts/vbench/scenario.py --junit /tmp/vbench-junit.xml

bench-all: bench-test bench-display-test bench-sdcard-test bench-netlist bench-power bench-phase2 bench-phase3 bench-ci ## The whole bench

verify-dangling: ## Fail on track ends that reach no pad, via, junction or zone (dead copper)
	@$(T) verify-dangling python3 scripts/verify_dangling_copper.py

verify-netlist-kicad: ## Cross-check our parsed netlist against KiCad's own IPC-D-356 export
	@$(T) verify-netlist-kicad python3 scripts/verify_netlist_vs_kicad.py

net-explorer: ## Regenerate the PCB Net Explorer data (website/static/net-explorer-data.json)
	@$(T) net-explorer python3 scripts/generate_net_explorer.py

net-explorer-check: ## Fail if the Net Explorer data is stale vs the .kicad_pcb
	@$(T) net-explorer-check python3 scripts/generate_net_explorer.py --check

docs-bom: ## Regenerate the docs BOM table from release_jlcpcb/bom.csv
	@$(T) docs-bom python3 scripts/generate_docs_bom.py

docs-bom-check: ## Fail if the docs BOM table is stale vs the shipped BOM
	@$(T) docs-bom-check python3 scripts/generate_docs_bom.py --check
verify-jlcpcb-vias: ## JLCPCB published via/hole/slot limits (jlcpcb.com/blog/pcb-via-design-best-practices)
	@$(T) verify-jlcpcb-vias python3 scripts/verify_jlcpcb_via_rules.py

verify-isolation: ## Isolation gate — 13 checks: connected where intended, isolated everywhere else (~2s)
	@$(T) verify-isolation python3 scripts/verify_isolation.py

verify-sch-overlaps: ## Fail when a label, junction or text overlaps another item (unreadable schematic)
	@$(T) verify-sch-overlaps python3 scripts/verify_schematic_overlaps.py

verify-easyeda: ## Verify every BOM footprint vs EasyEDA reference (catches pad-1 rotation/polarity bugs before JLCPCB)
	@$(T) verify-easyeda python3 scripts/verify_easyeda_footprint.py

verify-gerber-etest: ## Flying-probe e-test on the SHIPPED artifacts — opens/shorts from release_jlcpcb gerbers vs its IPC-D-356 netlist
	@$(T) verify-gerber-etest python3 scripts/verify_gerber_etest.py

verify-gate-coverage: ## Inject known fault classes (historical + predicted) into a sandbox and demand each one's owning gate goes red (~3-5 min; release-time audit, NOT in verify-all)
	@$(T) verify-gate-coverage python3 scripts/verify_gate_coverage.py

verify-cpl-law: ## CPL rotation law — every part must obey ONE law per layer (replaces per-part sign-off table)
	@$(T) verify-cpl-law python3 scripts/verify_cpl_rotation_law.py

test-cpl-law: ## Mutation tests: plant rotation errors, require the law gate to catch every one
	@$(T) test-cpl-law python3 scripts/test_cpl_rotation_law.py

verify-zone-fill: ## Zone-fill sanity — no duplicated islands, poured area fits the board, no zone left empty
	@$(T) verify-zone-fill python3 scripts/verify_zone_fill_sanity.py

test-zone-fill: ## Mutation tests: double / strip / oversize the fill, require the gate to catch every case
	@$(T) test-zone-fill python3 scripts/test_zone_fill_sanity.py

analyze-pin1: ## Locate each LCSC part's PHYSICAL polarity marker (silk asymmetry + 3D mesh, two independent extractors)
	@$(T) analyze-pin1 python3 scripts/analyze_pin1_marker.py

verify-trace-through-pad: ## Trace-through-pad overlap check (catches fab-shorts from missing _PAD_NETS)
	@$(T) verify-trace-through-pad python3 scripts/verify_trace_through_pad.py

verify-trace-crossings: ## Trace-crossings check (catches R9-CRIT-1 class: different-net traces intersecting on same layer)
	@$(T) verify-trace-crossings python3 scripts/verify_trace_crossings.py

verify-copper-clearance: ## Copper-to-copper clearance gate (JLCDFM preferred 0.15mm)
	@$(T) verify-copper-clearance python3 scripts/verify_copper_clearance.py

verify-net-connectivity: ## Per-net copper connectivity — every net must be a single component
	@$(T) verify-net-connectivity python3 scripts/verify_net_connectivity.py

verify-power-nets: ## Power-net integrity gate — +3V3/+5V/GND/VBUS/BAT+ must each be ONE piece of copper (catches split-plane dead boards)
	@$(T) verify-power-nets python3 scripts/verify_power_net_integrity.py

verify-erc: ## KiCad ERC gate on the generated schematic (error severity, local kicad-cli)
	@$(T) verify-erc python3 scripts/verify_erc.py

verify-enclosure-sync: ## Enclosure <-> PCB mechanical sync gate (scad constants vs board.py / battery model)
	@$(T) verify-enclosure-sync python3 scripts/verify_enclosure_sync.py

test-enclosure-sync: ## Mutation tests for the enclosure-sync gate
	@$(T) test-enclosure-sync python3 scripts/test_enclosure_sync.py

test-power-nets: ## Regression tests for the power-net integrity detector
	@$(T) test-power-nets python3 scripts/test_power_net_integrity.py

verify-memory: ## Memory/preamble integrity — frontmatter, links, orphans, no hand-written gate state
	@$(T) verify-memory python3 scripts/verify_memory.py

test-memory: ## Mutation tests proving each memory check discriminates
	@$(T) test-memory python3 scripts/test_verify_memory.py

verify-intent: ## Design intent adversary (18 tests, 300+ cross-source consistency checks)
	@$(T) verify-intent python3 scripts/verify_design_intent.py

verify-datasheet: ## Verify PCB pad-net assignments against datasheet specs (30 components, 246 checks)
	@$(T) verify-datasheet python3 scripts/verify_datasheet_nets.py

verify-fast: ## Quick DFM check only (1.4s)
	@$(T) verify-fast python3 scripts/verify_dfm_v2.py

verify-dfa: ## Quick DFA check (assembly verification, 9 tests)
	@$(T) verify-dfa python3 scripts/verify_dfa.py

validate-jlcpcb: ## JLCPCB manufacturing validation (drill, edge, copper, gerbers)
	@$(T) validate-jlcpcb python3 scripts/validate_jlcpcb.py

firmware-sync-check: ## Verify GPIO sync between firmware and schematic (fail on mismatch)
	@$(T) firmware-sync-check python3 scripts/verify_schematic_pcb.py

export-gerbers: generate-pcb docker-build ## Export Gerbers with zone fill via kicad-cli Docker
	@$(T) export-gerbers ./scripts/export-gerbers.sh

export-gerbers-fast: pcb-filled ## Export Gerbers (local kicad-cli + Docker zone fill only)
	@$(T) export-gerbers-fast ./scripts/export-gerbers-fast.sh

fast-check: ## Full pipeline using local kicad-cli (~5s vs ~20s Docker)
	@$(T) fast-check ./scripts/fast-check.sh

external-dfm: ## External DFM analysis via KiBot + Tracespace (Docker)
	@$(T) external-dfm bash scripts/external-dfm.sh

release-prep: generate-pcb export-gerbers-fast verify-trace-through-pad verify-power-nets verify-net-connectivity verify-easyeda verify-all verify-dfa render-pcb ## Full release pipeline (fast gerber export)
	@echo "Release prep complete: PCB generated, verified, rendered"

render-all: generate-schematic docker-build ## Full render pipeline (generate + export, parallel renders)
	@echo "Running renders in parallel..."
	@$(MAKE) -j3 render-schematics render-enclosure render-pcb

ESP_PORT ?= /dev/ttyUSB0

firmware-build: ## Build ESP-IDF firmware via Docker
	@$(T) firmware-build docker compose run --rm idf-build

firmware-flash: ## Flash firmware + open serial monitor (connect board first)
	@$(T) firmware-flash docker compose run --rm idf-flash

firmware-monitor: ## Open serial monitor only (no flash)
	docker compose run --rm idf-flash idf.py -p $(ESP_PORT) monitor

firmware-clean: ## Clean firmware build artifacts
	docker compose run --rm idf-build idf.py fullclean

# ── QEMU CPU Benchmark ──────────────────────────────────────────────

benchmark-build: ## Build QEMU benchmark firmware (Docker + ESP-IDF)
	@$(T) benchmark-build docker compose run --rm qemu-bench-build

benchmark-run: ## Run CPU benchmark in QEMU (ESP32-S3 @ 240MHz)
	@$(T) benchmark-run docker compose run --rm qemu-bench-run

benchmark: benchmark-build benchmark-run ## Build + run full benchmark

benchmark-vnc: benchmark-build ## Run QEMU with VNC display (connect vnc://localhost:5900)
	docker compose run --rm -p 5900:5900 qemu-interactive

# ── Retro-Go emulator (Phase 2) ─────────────────────────────────────

RETRO_GO_COMPOSE = docker compose -f docker-compose.retro-go.yml

retro-go-build: ## Build Retro-Go firmware (all apps)
	@$(T) retro-go-build $(RETRO_GO_COMPOSE) run --rm retro-go-build

retro-go-build-launcher: ## Build Retro-Go launcher only (quick test)
	@$(T) retro-go-build-launcher $(RETRO_GO_COMPOSE) run --rm retro-go-build-launcher

retro-go-flash: ## Flash Retro-Go firmware + serial monitor
	$(RETRO_GO_COMPOSE) run --rm retro-go-flash

retro-go-monitor: ## Open serial monitor for Retro-Go
	$(RETRO_GO_COMPOSE) run --rm retro-go-monitor

retro-go-clean: ## Clean Retro-Go build artifacts
	$(RETRO_GO_COMPOSE) down -v

website-dev: ## Start Docusaurus dev server
	cd website && npm start

website-build: ## Build Docusaurus site for production
	@$(T) website-build sh -c 'cd website && npm run build'

all: render-all website-build ## Full pipeline: generate + render + build website

clean: ## Remove generated renders
	rm -f website/static/img/schematics/*.svg
	rm -f website/static/img/schematics/*.pdf
	rm -f website/static/img/renders/*.png
	rm -f website/static/img/pcb/*.svg
	rm -f website/static/img/pcb/*.png
	rm -f website/static/img/pcb/*.gif
	rm -f hardware/kicad/0[1-7]-*.kicad_sch
