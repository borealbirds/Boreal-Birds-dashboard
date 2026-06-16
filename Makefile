.PHONY: all build clean help

# Default target run when typing 'make'
all: build-docs

## build: Clean old API reference files, regenerate them with quartodoc, and compile the Quarto site.
build-docs: clean
	@echo "Running quartodoc build..."
	quartodoc build --config docs/_quarto.yml
	@echo "Compiling Quarto website..."
	quarto render docs

## clean: Remove auto-generated quartodoc API reference files.
clean:
	@echo "Clearing docs/reference/..."
	rm -rf docs/reference

## help: Show available commands.
help:
	@echo "Available commands:"
	@sed -n 's/^##//p' $(MAKEFILE_LIST) | column -t -s ':' | sed -e 's/^/ /'