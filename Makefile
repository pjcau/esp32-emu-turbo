.PHONY: all docker-build generate-schematic render-schematics render-enclosure \
       render-all website-dev website-build clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

docker-build: ## Build Docker images (KiCad + OpenSCAD)
	docker compose build

generate-schematic: ## Generate 7 KiCad schematics from Python spec
	docker compose run --rm generate-sch

render-schematics: docker-build ## Export KiCad schematic to SVG
	./scripts/render-schematics.sh

render-enclosure: docker-build ## Render OpenSCAD enclosure to PNG
	./scripts/render-enclosure.sh

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
	rm -f hardware/kicad/0[1-7]-*.kicad_sch
