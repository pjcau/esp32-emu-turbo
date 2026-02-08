.PHONY: all docker-build render-schematics render-enclosure render-all \
       website-dev website-build clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

docker-build: ## Build Docker images (KiCad + OpenSCAD)
	docker compose build

render-schematics: docker-build ## Export KiCad schematic to SVG
	./scripts/render-schematics.sh

render-enclosure: docker-build ## Render OpenSCAD enclosure to PNG
	./scripts/render-enclosure.sh

render-all: docker-build ## Render everything (schematics + enclosure)
	./scripts/render-all.sh

website-dev: ## Start Docusaurus dev server
	cd website && npm start

website-build: ## Build Docusaurus site for production
	cd website && npm run build

all: render-all website-build ## Full pipeline: render + build website

clean: ## Remove generated renders
	rm -f website/static/img/schematics/*.svg
	rm -f website/static/img/renders/*.png
