# Windows PowerShell Commands for OrgMind
# Alternative to Makefile/justfile for Windows users

Write-Host "OrgMind Development Commands" -ForegroundColor Cyan
Write-Host "============================" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# FUNCTIONS
# =============================================================================

function Show-Help {
    Write-Host "Setup:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 install     - Install Python dependencies"
    Write-Host "  .\dev.ps1 dev         - Install with dev dependencies"
    Write-Host "  .\dev.ps1 up          - Start Docker services"
    Write-Host "  .\dev.ps1 down        - Stop Docker services"
    Write-Host "  .\dev.ps1 clean       - Stop services and remove volumes"
    Write-Host ""
    Write-Host "Development:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 run         - Run API server"
    Write-Host "  .\dev.ps1 worker      - Run Temporal worker"
    Write-Host "  .\dev.ps1 migrate     - Run database migrations"
    Write-Host ""
    Write-Host "Quality:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 test        - Run tests"
    Write-Host "  .\dev.ps1 lint        - Run linter"
    Write-Host "  .\dev.ps1 format      - Format code"
    Write-Host "  .\dev.ps1 check       - Run all checks"
    Write-Host ""
    Write-Host "Docker:" -ForegroundColor Yellow
    Write-Host "  .\dev.ps1 logs        - View Docker logs"
    Write-Host "  .\dev.ps1 build       - Build Docker images"
}

# =============================================================================
# COMMAND HANDLER
# =============================================================================

$command = $args[0]

switch ($command) {
    "install" {
        Write-Host "Installing Python dependencies..." -ForegroundColor Green
        uv sync
    }
    "dev" {
        Write-Host "Installing with dev dependencies..." -ForegroundColor Green
        uv sync --all-extras
    }
    "up" {
        Write-Host "Starting Docker services..." -ForegroundColor Green
        docker compose up -d
        Write-Host ""
        Write-Host "Services:" -ForegroundColor Cyan
        Write-Host "  Redis:       localhost:6379"
        Write-Host "  Neo4j:       localhost:7474 / localhost:7687"
        Write-Host "  Qdrant:      localhost:6333"
        Write-Host "  Meilisearch: localhost:7700"
        Write-Host "  MinIO:       localhost:9000 / localhost:9001"
        Write-Host "  Temporal:    localhost:7233 / localhost:8080"
        Start-Sleep -Seconds 5
        docker compose ps
    }
    "down" {
        Write-Host "Stopping Docker services..." -ForegroundColor Green
        docker compose down
    }
    "logs" {
        docker compose logs -f
    }
    "clean" {
        Write-Host "Cleaning everything..." -ForegroundColor Yellow
        docker compose down -v
        Remove-Item -Path "data\*.duckdb" -ErrorAction SilentlyContinue
        Remove-Item -Path ".pytest_cache" -Recurse -ErrorAction SilentlyContinue
        Remove-Item -Path ".mypy_cache" -Recurse -ErrorAction SilentlyContinue
        Remove-Item -Path ".ruff_cache" -Recurse -ErrorAction SilentlyContinue
        Write-Host "Cleanup complete!" -ForegroundColor Green
    }
    "run" {
        Write-Host "Starting API server..." -ForegroundColor Green
        uv run uvicorn orgmind.api.main:app --reload --host 0.0.0.0 --port 8000
    }
    "worker" {
        Write-Host "Starting Temporal worker..." -ForegroundColor Green
        uv run python -m orgmind.workflows.worker
    }
    "migrate" {
        Write-Host "Running database migrations..." -ForegroundColor Green
        uv run python -m orgmind.storage.migrations
    }
    "test" {
        Write-Host "Running tests..." -ForegroundColor Green
        uv run pytest tests/ -v --cov=src/orgmind --cov-report=term-missing
    }
    "test-fast" {
        Write-Host "Running tests (fail-fast)..." -ForegroundColor Green
        uv run pytest tests/ -v -x --tb=short
    }
    "lint" {
        Write-Host "Linting code..." -ForegroundColor Green
        uv run ruff check src/ tests/
        uv run ruff format --check src/ tests/
    }
    "format" {
        Write-Host "Formatting code..." -ForegroundColor Green
        uv run ruff check --fix src/ tests/
        uv run ruff format src/ tests/
    }
    "typecheck" {
        Write-Host "Type checking..." -ForegroundColor Green
        uv run mypy src/
    }
    "security" {
        Write-Host "Running security scan..." -ForegroundColor Green
        uv run bandit -r src/ -ll
    }
    "check" {
        Write-Host "Running all checks..." -ForegroundColor Green
        & $PSCommandPath lint
        & $PSCommandPath typecheck
        & $PSCommandPath test
        Write-Host "All checks passed!" -ForegroundColor Green
    }
    "build" {
        Write-Host "Building Docker images..." -ForegroundColor Green
        docker build -t orgmind-api:latest -f docker/Dockerfile.api .
        docker build -t orgmind-worker:latest -f docker/Dockerfile.worker .
    }
    default {
        Show-Help
    }
}
