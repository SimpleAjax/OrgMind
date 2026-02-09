# =============================================================================
# OrgMind Development Makefile
# =============================================================================

.PHONY: help install dev up down logs clean test lint format check migrate run worker

# Default target
help:
	@echo "OrgMind Development Commands"
	@echo "============================"
	@echo ""
	@echo "Setup:"
	@echo "  make install     - Install Python dependencies"
	@echo "  make dev         - Install with dev dependencies"
	@echo "  make up          - Start all Docker services"
	@echo "  make down        - Stop all Docker services"
	@echo "  make clean       - Stop services and remove volumes"
	@echo ""
	@echo "Development:"
	@echo "  make run         - Run API server"
	@echo "  make worker      - Run Temporal worker"
	@echo "  make migrate     - Run database migrations"
	@echo ""
	@echo "Quality:"
	@echo "  make test        - Run tests"
	@echo "  make lint        - Run linter"
	@echo "  make format      - Format code"
	@echo "  make check       - Run all checks (lint + type + test)"
	@echo ""
	@echo "Docker:"
	@echo "  make logs        - View Docker logs"
	@echo "  make build       - Build Docker images"

# =============================================================================
# SETUP
# =============================================================================

install:
	uv sync

dev:
	uv sync --all-extras

up:
	docker compose up -d
	@echo ""
	@echo "Services starting..."
	@echo "  Redis:       localhost:6379"
	@echo "  Neo4j:       localhost:7474 (HTTP) / localhost:7687 (Bolt)"
	@echo "  Qdrant:      localhost:6333"
	@echo "  Meilisearch: localhost:7700"
	@echo "  MinIO:       localhost:9000 (API) / localhost:9001 (Console)"
	@echo "  Temporal:    localhost:7233 (API) / localhost:8080 (UI)"
	@echo ""
	@echo "Waiting for services to be healthy..."
	@sleep 5
	docker compose ps

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	docker compose down -v
	rm -rf data/*.duckdb
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# =============================================================================
# DEVELOPMENT
# =============================================================================

run:
	uv run uvicorn src.orgmind.api.main:app --reload --host 0.0.0.0 --port 8000

worker:
	uv run python -m src.orgmind.workflows.worker

migrate:
	uv run python -m src.orgmind.storage.migrations

shell:
	uv run python

# =============================================================================
# QUALITY
# =============================================================================

test:
	uv run pytest tests/ -v --cov=src/orgmind --cov-report=term-missing

test-fast:
	uv run pytest tests/ -v -x --tb=short

lint:
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/

format:
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

typecheck:
	uv run mypy src/

security:
	uv run bandit -r src/ -ll

check: lint typecheck test
	@echo "All checks passed!"

# =============================================================================
# DOCKER
# =============================================================================

build:
	docker build -t orgmind-api:latest -f docker/Dockerfile.api .
	docker build -t orgmind-worker:latest -f docker/Dockerfile.worker .

# =============================================================================
# DATABASE
# =============================================================================

db-shell:
	@echo "Opening DuckDB shell..."
	uv run python -c "import duckdb; db = duckdb.connect('data/orgmind.duckdb'); print('Connected. Use: db.sql(\"...\").show()')"

neo4j-shell:
	docker exec -it orgmind-neo4j cypher-shell -u neo4j -p orgmind_dev

redis-cli:
	docker exec -it orgmind-redis redis-cli

# =============================================================================
# UTILITIES
# =============================================================================

setup-env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example"; \
	else \
		echo ".env already exists"; \
	fi

create-dirs:
	mkdir -p data
	mkdir -p logs
	mkdir -p src/orgmind/{api,engine,storage,workflows,agents,triggers,platform}
	mkdir -p tests/{unit,integration}
