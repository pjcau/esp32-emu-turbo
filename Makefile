.PHONY: all docker-build generate-schematic generate-pcb render-schematics \
       render-enclosure render-pcb render-all website-dev website-build clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

docker-build: ## Build Docker images (KiCad + OpenSCAD)
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

render-all: generate-schematic docker-build ## Full render pipeline (generate + export)
	./scripts/render-all.sh

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
