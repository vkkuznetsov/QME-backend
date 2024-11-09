SERVICE := backend

.PHONY: help init run clean

help:
	@echo "Usage: make <command>"
	@echo "Available commands:"
	@echo "  init   - Create .venv and install dependencies"
	@echo "  run    - Run app $(SERVICE)"
	@echo "  clean  - Clean cache and delete venv"


init:
	@poetry config virtualenvs.create true
	@poetry config virtualenvs.in-project true
	@poetry lock --no-update
	@poetry install --no-root

run:
	@poetry run python -m $(SERVICE)

clean:
	@poetry cache clear packages --all
	@poetry cache clear cache --all
	@rm -rf .venv
