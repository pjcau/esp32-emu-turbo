.PHONY: all docker-build generate-schematic generate-pcb render-schematics \
       render-enclosure render-pcb render-all simulate verify-all verify-fast verify-dfa verify-datasheet verify-trace-through-pad verify-trace-crossings validate-jlcpcb pcb-check external-dfm \
       export-gerbers release-prep firmware-sync-check \
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

generate-pcb: ## Generate KiCad PCB + JLCPCB exports (BOM, CPL)
	@$(T) generate-pcb python3 -m scripts.generate_pcb hardware/kicad

render-schematics: docker-build ## Export KiCad schematic to SVG
	@$(T) render-schematics ./scripts/render-schematics.sh

render-enclosure: docker-build ## Render OpenSCAD enclosure to PNG
	@$(T) render-enclosure ./scripts/render-enclosure.sh

render-pcb: generate-pcb ## Render PCB layout to SVG/PNG/GIF
	@$(T) render-pcb sh -c 'python3 scripts/render_pcb_svg.py website/static/img/pcb && python3 scripts/render_pcb_animation.py website/static/img/pcb'

simulate: ## Run electrical circuit simulation/verification
	@$(T) simulate python3 scripts/simulate_circuit.py

pcb-check: ## Run PCB short circuit / zone fill analysis
	@$(T) pcb-check python3 scripts/short_circuit_analysis.py

verify-all: ## Run all pre-production checks (DRC + DFM + DFA + simulation + consistency)
	@echo "Running verification suite..."
	@$(T) verify-all sh -c '\
		python3 scripts/verify_dfm_v2.py & \
		python3 scripts/verify_dfa.py & \
		python3 scripts/drc_check.py & \
		python3 scripts/simulate_circuit.py & \
		python3 scripts/verify_schematic_pcb.py & \
		python3 scripts/short_circuit_analysis.py & \
		python3 scripts/verify_polarity.py & \
		python3 scripts/verify_datasheet_nets.py & \
		python3 scripts/verify_antenna_keepout.py & \
		python3 scripts/verify_stackup.py & \
		python3 scripts/verify_net_class_widths.py & \
		python3 scripts/verify_design_intent.py & \
		python3 scripts/verify_trace_through_pad.py & \
		python3 scripts/verify_trace_crossings.py & \
		python3 scripts/verify_net_connectivity.py & \
		wait'

verify-trace-through-pad: ## Trace-through-pad overlap check (catches fab-shorts from missing _PAD_NETS)
	@$(T) verify-trace-through-pad python3 scripts/verify_trace_through_pad.py

verify-trace-crossings: ## Trace-crossings check (catches R9-CRIT-1 class: different-net traces intersecting on same layer)
	@$(T) verify-trace-crossings python3 scripts/verify_trace_crossings.py

verify-net-connectivity: ## Per-net copper connectivity — every net must be a single component
	@$(T) verify-net-connectivity python3 scripts/verify_net_connectivity.py

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

export-gerbers-fast: generate-pcb ## Export Gerbers (local kicad-cli + Docker zone fill only)
	@$(T) export-gerbers-fast ./scripts/export-gerbers-fast.sh

fast-check: ## Full pipeline using local kicad-cli (~5s vs ~20s Docker)
	@$(T) fast-check ./scripts/fast-check.sh

external-dfm: ## External DFM analysis via KiBot + Tracespace (Docker)
	@$(T) external-dfm bash scripts/external-dfm.sh

release-prep: generate-pcb export-gerbers-fast verify-trace-through-pad verify-net-connectivity verify-all verify-dfa render-pcb ## Full release pipeline (fast gerber export)
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
