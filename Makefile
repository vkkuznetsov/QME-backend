SERVICE := backend

.PHONY: help init run clean build up down restart delete

help:
	@echo "Local commands:"
	@echo "  init    - Create .venv and install dependencies"
	@echo "  run     - Run app $(SERVICE)"
	@echo "  clean   - Clean cache and delete venv"
	@echo ""
	@echo "Docker commands:"
	@echo "  build   - Build Docker containers"
	@echo "  up      - Start Docker containers in detached mode"
	@echo "  down    - Stop Docker containers"
	@echo "  restart - Restart Docker containers"
	@echo "  delete  - Stop Docker containers, remove volumes and images"


init:
	@poetry config virtualenvs.create true
	@poetry config virtualenvs.in-project true
	@poetry lock
	@poetry install --no-root

run:
	@poetry run python -m $(SERVICE)

clean:
	@poetry cache clear packages --all
	@poetry cache clear cache --all
	@rm -rf .venv

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

delete:
	docker image prune -f

restart: down delete build up
