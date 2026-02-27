.PHONY: all docker-build generate-schematic generate-pcb render-schematics \
       render-enclosure render-pcb render-all simulate verify-all verify-fast pcb-check \
       export-gerbers release-prep firmware-sync-check \
       firmware-build firmware-flash firmware-monitor firmware-clean \
       retro-go-build retro-go-build-launcher retro-go-flash retro-go-monitor retro-go-clean \
       website-dev website-build clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

docker-build: ## Build Docker images (KiCad + OpenSCAD) — cached if unchanged
	@docker compose images -q 2>/dev/null | head -1 > /dev/null 2>&1 && \
		echo "Docker images already built (use 'docker compose build --no-cache' to force)" || \
		docker compose build

generate-schematic: ## Generate 7 KiCad schematics from Python spec
	docker compose run --rm generate-sch

generate-pcb: ## Generate KiCad PCB + JLCPCB exports (BOM, CPL)
	python3 -m scripts.generate_pcb hardware/kicad

render-schematics: docker-build ## Export KiCad schematic to SVG
	./scripts/render-schematics.sh

render-enclosure: docker-build ## Render OpenSCAD enclosure to PNG
	./scripts/render-enclosure.sh

render-pcb: generate-pcb ## Render PCB layout to SVG/PNG/GIF
	python3 scripts/render_pcb_svg.py website/static/img/pcb
	python3 scripts/render_pcb_animation.py website/static/img/pcb

simulate: ## Run electrical circuit simulation/verification
	python3 scripts/simulate_circuit.py

pcb-check: ## Run PCB short circuit / zone fill analysis
	python3 scripts/short_circuit_analysis.py

verify-all: ## Run all pre-production checks (DRC + simulation + consistency + short circuit)
	@echo "Running verification suite..."
	@python3 scripts/drc_check.py & \
	 python3 scripts/simulate_circuit.py & \
	 python3 scripts/verify_schematic_pcb.py & \
	 python3 scripts/short_circuit_analysis.py & \
	 wait
	@echo "All verification checks complete."

verify-fast: ## Quick DFM check only (30s vs 2min full suite)
	python3 scripts/verify_dfm_v2.py

firmware-sync-check: ## Verify GPIO sync between firmware and schematic (fail on mismatch)
	python3 scripts/verify_schematic_pcb.py

export-gerbers: generate-pcb docker-build ## Export Gerbers with zone fill via kicad-cli Docker
	./scripts/export-gerbers.sh

export-gerbers-fast: generate-pcb ## Export Gerbers (local kicad-cli + Docker zone fill only)
	./scripts/export-gerbers-fast.sh

fast-check: ## Full pipeline using local kicad-cli (~5s vs ~20s Docker)
	./scripts/fast-check.sh

release-prep: generate-pcb export-gerbers-fast verify-all render-pcb ## Full release pipeline (fast gerber export)
	@echo "Release prep complete: PCB generated, verified, rendered"

render-all: generate-schematic docker-build ## Full render pipeline (generate + export, parallel renders)
	@echo "Running renders in parallel..."
	@$(MAKE) -j3 render-schematics render-enclosure render-pcb

ESP_PORT ?= /dev/ttyUSB0

firmware-build: ## Build ESP-IDF firmware via Docker
	docker compose run --rm idf-build

firmware-flash: ## Flash firmware + open serial monitor (connect board first)
	docker compose run --rm idf-flash

firmware-monitor: ## Open serial monitor only (no flash)
	docker compose run --rm idf-flash idf.py -p $(ESP_PORT) monitor

firmware-clean: ## Clean firmware build artifacts
	docker compose run --rm idf-build idf.py fullclean

# ── Retro-Go emulator (Phase 2) ─────────────────────────────────────

RETRO_GO_COMPOSE = docker compose -f docker-compose.retro-go.yml

retro-go-build: ## Build Retro-Go firmware (all apps)
	$(RETRO_GO_COMPOSE) run --rm retro-go-build

retro-go-build-launcher: ## Build Retro-Go launcher only (quick test)
	$(RETRO_GO_COMPOSE) run --rm retro-go-build-launcher

retro-go-flash: ## Flash Retro-Go firmware + serial monitor
	$(RETRO_GO_COMPOSE) run --rm retro-go-flash

retro-go-monitor: ## Open serial monitor for Retro-Go
	$(RETRO_GO_COMPOSE) run --rm retro-go-monitor

retro-go-clean: ## Clean Retro-Go build artifacts
	$(RETRO_GO_COMPOSE) down -v

website-dev: ## Start Docusaurus dev server
	cd website && npm start

website-build: ## Build Docusaurus site for production
	cd website && npm run build

all: render-all website-build ## Full pipeline: generate + render + build website

clean: ## Remove generated renders
	rm -f website/static/img/schematics/*.svg
	rm -f website/static/img/schematics/*.pdf
	rm -f website/static/img/renders/*.png
	rm -f website/static/img/pcb/*.svg
	rm -f website/static/img/pcb/*.png
	rm -f website/static/img/pcb/*.gif
	rm -f hardware/kicad/0[1-7]-*.kicad_sch
