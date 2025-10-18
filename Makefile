.PHONY: help install up down build test clean logs shell

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies with Poetry
	poetry install

up: ## Start all services with Docker Compose
	docker-compose up -d

down: ## Stop all services
	docker-compose down

build: ## Build Docker images
	docker-compose build

logs: ## Show logs from all containers
	docker-compose logs -f

logs-api: ## Show API logs
	docker-compose logs -f api

logs-worker: ## Show worker logs
	docker-compose logs -f worker

test: ## Run tests
	poetry run pytest -v

test-cov: ## Run tests with coverage
	poetry run pytest --cov=app --cov-report=term-missing --cov-report=html

test-unit: ## Run unit tests only
	poetry run pytest tests/unit/ -v

test-integration: ## Run integration tests only
	poetry run pytest tests/integration/ -v

format: ## Format code with black
	poetry run black app/ tests/ scripts/

lint: ## Lint code with ruff
	poetry run ruff check app/ tests/ scripts/

typecheck: ## Check types with mypy
	poetry run mypy app/

quality: format lint typecheck ## Run all code quality checks

shell: ## Open shell in API container
	docker-compose exec api /bin/bash

shell-db: ## Open psql shell in database
	docker-compose exec timescaledb psql -U postgres -d events_db

import-sample: ## Import sample CSV data
	docker-compose exec api python -m scripts.import_events /app/data/events_sample.csv

clean: ## Clean up generated files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .coverage htmlcov/ .mypy_cache/

reset-db: ## Reset database (WARNING: deletes all data)
	docker-compose exec timescaledb psql -U postgres -d events_db -c "TRUNCATE TABLE events CASCADE;"
	@echo "Database reset complete"

dev-api: ## Run API locally (requires Poetry and running infrastructure)
	poetry run uvicorn app.main:app --reload --log-level debug

dev-worker: ## Run worker locally (requires Poetry and running infrastructure)
	poetry run python -m app.workers.event_processor

monitoring-up: ## Start services with monitoring stack
	docker-compose --profile monitoring up -d

status: ## Show status of all services
	docker-compose ps

health: ## Check health of API
	@curl -s http://localhost:8000/health | python -m json.tool

metrics: ## Show Prometheus metrics
	@curl -s http://localhost:8000/metrics

docs: ## Open API documentation in browser
	@echo "Opening http://localhost:8000/docs"
	@xdg-open http://localhost:8000/docs 2>/dev/null || open http://localhost:8000/docs 2>/dev/null || echo "Please open http://localhost:8000/docs manually"

benchmark: ## Run simple benchmark (requires API to be running)
	@echo "Running benchmark..."
	@poetry run python scripts/benchmark.py || echo "Benchmark script not yet implemented"

.DEFAULT_GOAL := help

