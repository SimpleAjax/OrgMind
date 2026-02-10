# OrgMind Development Commands (Windows-compatible)
# Alternative to Makefile using 'just' (https://github.com/casey/just)
# Install: cargo install just  OR  choco install just

# =============================================================================
# HELP
# =============================================================================
default:
    @just --list

# =============================================================================
# SETUP
# =============================================================================

# Install Python dependencies
install:
    uv sync

# Install with dev dependencies
dev:
    uv sync --all-extras

# Start Docker services
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
    @timeout /t 5 >nul
    docker compose ps

# Stop Docker services
down:
    docker compose down

# View Docker logs
logs:
    docker compose logs -f

# Clean everything (including volumes)
clean:
    docker compose down -v
    if exist data\*.duckdb del /q data\*.duckdb
    if exist .pytest_cache rmdir /s /q .pytest_cache
    if exist .mypy_cache rmdir /s /q .mypy_cache
    if exist .ruff_cache rmdir /s /q .ruff_cache
    if exist htmlcov rmdir /s /q htmlcov

# Copy .env.example to .env
setup-env:
    @if not exist .env (copy .env.example .env && echo Created .env from .env.example) else (echo .env already exists)

# Create necessary directories
create-dirs:
    @if not exist data mkdir data
    @if not exist logs mkdir logs

# =============================================================================
# DEVELOPMENT
# =============================================================================

# Run API server
run:
    uv run uvicorn orgmind.api.main:app --reload --host 0.0.0.0 --port 8000

# Run Temporal worker
worker:
    uv run python -m orgmind.workflows.worker

# Run database migrations
migrate:
    uv run python -m orgmind.storage.migrations

# Open Python shell
shell:
    uv run python

# =============================================================================
# TESTING
# =============================================================================

# Run all tests with coverage
test:
    uv run pytest tests/ -v --cov=src/orgmind --cov-report=term-missing

# Run tests fast (fail on first error)
test-fast:
    uv run pytest tests/ -v -x --tb=short

# Run only unit tests
test-unit:
    uv run pytest tests/unit -v

# Run only integration tests
test-integration:
    uv run pytest tests/integration -v

# =============================================================================
# CODE QUALITY
# =============================================================================

# Format code with Ruff
format:
    uv run ruff check --fix src/ tests/
    uv run ruff format src/ tests/

# Lint code with Ruff
lint:
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/

# Type check with MyPy
typecheck:
    uv run mypy src/

# Run security scan with Bandit
security:
    uv run bandit -r src/ -ll

# Run all checks (lint + typecheck + test)
check: lint typecheck test
    @echo "All checks passed!"

# =============================================================================
# DATABASE
# =============================================================================

# Open DuckDB shell
db-shell:
    @echo "Opening DuckDB shell..."
    uv run python -c "import duckdb; db = duckdb.connect('data/orgmind.duckdb'); print('Connected. Use: db.sql(\"...\").show()')"

# Open Neo4j Cypher shell
neo4j-shell:
    docker exec -it orgmind-neo4j cypher-shell -u neo4j -p orgmind_dev

# Open Redis CLI
redis-cli:
    docker exec -it orgmind-redis redis-cli

# =============================================================================
# DOCKER BUILD
# =============================================================================

# Build Docker images
build:
    docker build -t orgmind-api:latest -f docker/Dockerfile.api .
    docker build -t orgmind-worker:latest -f docker/Dockerfile.worker .

# =============================================================================
# KUBERNETES (if applicable)
# =============================================================================

# Deploy to staging
k8s-deploy-staging:
    kubectl apply -f k8s/staging/

# Deploy to production
k8s-deploy-prod:
    kubectl apply -f k8s/prod/

# View staging pods
k8s-pods-staging:
    kubectl get pods -n orgmind-staging

# View staging logs
k8s-logs-staging:
    kubectl logs -f deployment/orgmind-api -n orgmind-staging
